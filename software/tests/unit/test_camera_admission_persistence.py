"""Actual NTFS/scoped facts retention; all device/admission facts are MODELED.

The fixture predecessor cannot pass application onboarding. The real core,
immutable publisher, OS leases and fact/hash readback run with incapable workers.
"""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json

import pytest

from rocell.application import commissioning_camera_persistence as m
from rocell.application.cell_commissioning_coordinator import (
    PhysicalCameraAcquisitionCoordinator,
    CommissioningCoordinatorError,
)
from rocell.application.physical_onboarding_attempts import (
    AttemptState,
    canonical_json_bytes,
)
from test_camera_activation_original_storage import (
    actual_components,
    reopen,
    records_root,
    profile,
    SOURCE,
    SESSION,
    LEASES,
    WINDOWS,
    forbid_device_and_process_calls,
    no_physical_owner,
    facts,
)


def scoped_components(tmp_path, monkeypatch, purpose="probe", refuse=False):
    runtime, _, _, worker, request = actual_components(tmp_path, monkeypatch, purpose)
    calls = []

    def scoped(tx, requested, snapshot):
        assert type(tx) is m.M1PhysicalCameraTransaction
        assert tx.held_leases == LEASES
        assert tx.snapshot() == snapshot
        calls.append(tx)
        if refuse:
            raise m.M1CommissioningPersistenceError("MODELED_CURRENT_CONTEXT_WITHDRAWN")
        return facts(requested, snapshot)

    adapter = m.M1PhysicalCameraPersistence(
        runtime, workspace_source_sha256=SOURCE, scoped_admission_facts=scoped
    )
    item = profile(purpose)
    core = PhysicalCameraAcquisitionCoordinator(
        persistence=adapter,
        registrations=(item,),
        workers={item.worker_id: worker},
        retained_campaign_actions=(item.action_id,),
        scoped_campaign_actions=(item.action_id,),
        monotonic_ns=worker.clock,
    )
    return runtime, adapter, core, worker, request, calls


@WINDOWS
@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_original_facts_join_actual_scope_reservation_and_fresh_readback(
    tmp_path, monkeypatch, purpose
):
    runtime, adapter, core, worker, request, calls = scoped_components(
        tmp_path, monkeypatch, purpose
    )
    assert adapter.requires_original_admission_evidence is True
    permit = core.prepare(request)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN
    assert worker.calls == 1  # Incapable modeled worker, not a device open.
    assert len({id(tx) for tx in calls}) >= 2
    for old in calls:
        with pytest.raises(m.M1CommissioningPersistenceError, match="scope has ended"):
            old._check_scope()
    with adapter.transaction(LEASES) as tx:
        original = tx.read_campaign_admission_evidence(permit.attempt_id)
        assert original == facts(request, tx.snapshot()).retained_documents()
        m.verify_camera_admission_evidence(original, permit)
        changed = deepcopy(original)
        for role in ("hazard_assessment", "selected_identity"):
            changed = deepcopy(original)
            changed[role]["MODELED_CHANGED"] = True
            with pytest.raises(m.M1CommissioningPersistenceError, match="joins differ"):
                m.verify_camera_admission_evidence(changed, permit)
        changed = deepcopy(original)
        changed["configuration_epochs"].reverse()
        with pytest.raises(m.M1CommissioningPersistenceError, match="joins differ"):
            m.verify_camera_admission_evidence(changed, permit)
        original["hazard_assessment"]["MODELED_CHANGED"] = True
        assert (
            "MODELED_CHANGED"
            not in tx.read_campaign_admission_evidence(permit.attempt_id)[
                "hazard_assessment"
            ]
        )

    # An old reader composition may inspect new historical facts, but it does
    # not reconstruct this scoped provider or obtain an executable permit.
    _, fresh = reopen(runtime)
    assert fresh.requires_original_admission_evidence is False
    with fresh.transaction(LEASES) as tx:
        assert tx.read_campaign_result(permit.attempt_id) == result
        original = tx.read_campaign_admission_evidence(permit.attempt_id)
        m.verify_camera_admission_evidence(original, permit)
    assert core.execute(permit) == result and worker.calls == 1


@WINDOWS
def test_scoped_fact_refusal_occurs_before_any_native_effect(tmp_path, monkeypatch):
    runtime, adapter, core, worker, request, calls = scoped_components(
        tmp_path, monkeypatch, refuse=True
    )
    with pytest.raises(m.M1CommissioningPersistenceError, match="WITHDRAWN"):
        core.prepare(request)
    assert worker.calls == 0
    assert runtime.verify(SESSION).attempt_event_count == 0
    assert calls
    assert not runtime.verify(SESSION).active_lease_owners


@WINDOWS
def test_exactly_one_server_facts_composition_is_required(tmp_path, monkeypatch):
    runtime, _, _, _, _ = actual_components(tmp_path, monkeypatch)
    for kwargs in (
        {},
        {"admission_facts": facts, "scoped_admission_facts": facts},
        {"scoped_admission_facts": True},
        {"admission_facts": True},
    ):
        with pytest.raises(m.M1CommissioningPersistenceError):
            m.M1PhysicalCameraPersistence(
                runtime, workspace_source_sha256=SOURCE, **kwargs
            )


@WINDOWS
def test_legacy_records_remain_readable_but_cannot_supply_missing_facts(
    tmp_path, monkeypatch
):
    runtime, adapter, core, worker, request = actual_components(tmp_path, monkeypatch)
    permit = core.prepare(request)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN
    with adapter.transaction(LEASES) as tx:
        assert tx.read_campaign_result(permit.attempt_id) == result
        with pytest.raises(m.M1CommissioningPersistenceError, match="unavailable"):
            tx.read_campaign_admission_evidence(permit.attempt_id)


@WINDOWS
def test_rehashing_changed_fact_copy_cannot_match_ledger_bound_permit(
    tmp_path, monkeypatch
):
    runtime, adapter, core, worker, request, _ = scoped_components(
        tmp_path, monkeypatch
    )
    permit = core.prepare(request)
    core.execute(permit)
    filename = (
        "request-"
        + hashlib.sha256(request.request_key.encode("ascii")).hexdigest()
        + ".json"
    )
    path = records_root(runtime) / filename
    record = json.loads(path.read_bytes())
    record["data"]["admission_evidence"]["hazard_assessment"]["source_sha256"] = (
        "9" * 64
    )
    record["record_sha256"] = hashlib.sha256(
        canonical_json_bytes(
            {key: value for key, value in record.items() if key != "record_sha256"}
        )
    ).hexdigest()
    # Only this isolated pytest fixture is deliberately corrupted.
    path.write_bytes(canonical_json_bytes(record))
    with pytest.raises(m.M1CommissioningPersistenceError, match="joins differ"):
        with adapter.transaction(LEASES) as tx:
            tx.read_campaign_admission_evidence(permit.attempt_id)
    assert worker.calls == 1
