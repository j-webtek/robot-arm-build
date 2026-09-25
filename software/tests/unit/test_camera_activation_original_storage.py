"""Real local NTFS/lease retention with explicitly modeled camera/process facts.

No native helper or device is opened. These isolated predecessor PASS records
are storage fixtures, not original application onboarding/hardware qualification.
"""

from dataclasses import asdict, replace
import hashlib
import json

import pytest

from rocell.application.cell_commissioning_coordinator import (
    CommissioningCoordinatorError,
    PhysicalCameraAcquisitionCoordinator,
    RegisteredActionRequest,
    WorkerReceipt,
    ObservedPowerState,
    PHYSICAL_CAMERA_COMPOSITION,
)
from rocell.safety.effects import EffectCertainty
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    M1PhysicalCameraTransaction,
    physical_camera_source_binding,
)
from rocell.application import commissioning_m1_persistence as persistence
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.application.camera_activation_evidence_parts import (
    PART_KIND,
    INDEX_KIND,
    encode_camera_evidence_parts,
)
from rocell.application.physical_onboarding_attempts import (
    AttemptState,
    canonical_json_bytes,
)
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from test_commissioning_camera_persistence import (
    WINDOWS,
    forbid_device_and_process_calls,
    runtime_and_adapter,
    records_root,
    facts,
)
from test_physical_camera_coordinator import CELL, SESSION, SOURCE, LEASES
from test_camera_activation_campaign_contract import ModeledCameraV2Worker, profile
from test_native_camera_activation_supervisor import Clock, no_physical_owner


def actual_components(tmp_path, monkeypatch, purpose="probe", fault=None):
    # The existing fixture is explicitly incapable. Selecting its next stage
    # does not modify any application admission policy or received-device facts.
    import test_commissioning_camera_persistence as fixture_module

    monkeypatch.setattr(fixture_module, "STAGE", profile(purpose).stage)
    runtime, adapter = runtime_and_adapter(tmp_path)
    clock, item = Clock(), profile(purpose)
    worker = ModeledCameraV2Worker(tmp_path, monkeypatch, clock, purpose, fault)
    core = PhysicalCameraAcquisitionCoordinator(
        persistence=adapter,
        registrations=(item,),
        workers={item.worker_id: worker},
        retained_campaign_actions=(item.action_id,),
        scoped_campaign_actions=(item.action_id,),
        monotonic_ns=clock,
    )
    request = RegisteredActionRequest(
        CELL, SESSION, item.action_id, "camera-v2-original", "1" * 64
    )
    with adapter.transaction(LEASES) as tx:
        request = replace(
            request,
            expected_challenge_sha256=tx.read_admission(request).challenge_sha256,
        )
    return runtime, adapter, core, worker, request


def reopen(runtime):
    fresh_runtime = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        cell_id=CELL,
    )
    return fresh_runtime, M1PhysicalCameraPersistence(
        fresh_runtime,
        workspace_source_sha256=SOURCE,
        admission_facts=facts,
    )


@WINDOWS
@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_actual_parts_known_result_and_fresh_audited_reopen(
    tmp_path, monkeypatch, purpose
):
    runtime, adapter, core, worker, request = actual_components(
        tmp_path, monkeypatch, purpose
    )
    permit = core.prepare(request)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN
    assert result.receipt.opens == 1 and result.physical_authority == "NONE"
    encoded = encode_camera_evidence_parts(worker.execution.evidence)
    with adapter.transaction(LEASES) as tx:
        assert (
            tx.read_camera_activation_evidence(permit.attempt_id)
            == worker.execution.evidence
        )
        assert len(tx._audit_records()) == len(encoded) + 4
        with pytest.raises(M1CommissioningPersistenceError):
            tx.read_campaign_evidence(permit.attempt_id)  # v1 does not coerce v2.
        with pytest.raises(M1CommissioningPersistenceError):
            tx.retain_camera_activation_evidence(permit, worker.execution.evidence)
    fresh_runtime, fresh = reopen(runtime)
    with fresh.transaction(LEASES) as tx:
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert tx.read_campaign_result(permit.attempt_id) == result
        assert (
            tx.read_camera_activation_evidence(permit.attempt_id)
            == worker.execution.evidence
        )
        # All camera-family facades audit the complete same original ledger.
        for domain in persistence._CAMERA_FAMILY:
            monkeypatch.setattr(tx, "_domain", domain)
            assert len(tx._audit_records(include_family=True)) == len(encoded) + 4
    assert fresh_runtime.verify(SESSION).attempt_event_count == 5
    assert not fresh_runtime.verify(SESSION).active_lease_owners
    assert core.execute(permit) == result and worker.calls == 1
    item = profile(purpose)
    fresh_core = PhysicalCameraAcquisitionCoordinator(
        persistence=fresh,
        registrations=(item,),
        workers={item.worker_id: worker},
        retained_campaign_actions=(item.action_id,),
        scoped_campaign_actions=(item.action_id,),
        monotonic_ns=worker.clock,
    )
    with pytest.raises(CommissioningCoordinatorError, match="unknown"):
        fresh_core.execute(permit)
    assert worker.calls == 1


@WINDOWS
@pytest.mark.parametrize("published", [0, 1, 2, 3])
def test_each_actual_publication_boundary_stays_uncertain(
    tmp_path, monkeypatch, published
):
    runtime, adapter, core, worker, request = actual_components(tmp_path, monkeypatch)
    original = M1PhysicalCameraTransaction._write_record
    count = 0

    def fail(self, name, kind, data):
        nonlocal count
        if kind in {PART_KIND, INDEX_KIND}:
            if published == 0:
                raise OSError("MODELED_PUBLICATION_BEFORE_FIRST_PART")
            result = original(self, name, kind, data)
            count += 1
            if count == published:
                raise OSError("MODELED_PUBLICATION_AFTER_IMMUTABLE_PART")
            return result
        return original(self, name, kind, data)

    monkeypatch.setattr(M1PhysicalCameraTransaction, "_write_record", fail)
    permit = core.prepare(request)
    result = core.execute(permit)
    assert len(encode_camera_evidence_parts(worker.execution.evidence)) == 3
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert count == published
    fresh_runtime, fresh = reopen(runtime)
    with fresh.transaction(LEASES) as tx:
        records = tx._audit_records()
        assert (
            sum(
                record["kind"] in {PART_KIND, INDEX_KIND} for record in records.values()
            )
            == published
        )
        assert tx.read_campaign_result(permit.attempt_id) == result
        if published < 3:
            with pytest.raises(M1CommissioningPersistenceError, match="incomplete"):
                tx.read_camera_activation_evidence(permit.attempt_id)
        else:
            assert (
                tx.read_camera_activation_evidence(permit.attempt_id)
                == worker.execution.evidence
            )
    assert fresh_runtime.verify(SESSION).quarantined
    assert worker.calls == 1


@WINDOWS
def test_large_unknown_native_counts_remain_absent_after_real_reopen(
    tmp_path, monkeypatch
):
    runtime, adapter, core, worker, request = actual_components(
        tmp_path, monkeypatch, fault="large"
    )
    permit = core.prepare(request)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.receipt is None
    assert result.reason_codes == ("NATIVE_ACCOUNTING_UNAVAILABLE",)
    assert len(encode_camera_evidence_parts(worker.execution.evidence)) > 4
    _, fresh = reopen(runtime)
    with fresh.transaction(LEASES) as tx:
        assert tx.read_campaign_result(permit.attempt_id).receipt is None
        assert (
            tx.read_camera_activation_evidence(permit.attempt_id)
            == worker.execution.evidence
        )


@WINDOWS
@pytest.mark.parametrize(
    "change", ["native-counters", "fabricated-zero-receipt", "discard-native-counts"]
)
def test_uncertain_original_does_not_waive_accounting_integrity(
    tmp_path, monkeypatch, change
):
    fault = "bad-result" if change == "fabricated-zero-receipt" else "late-cancel"
    runtime, adapter, core, worker, request = actual_components(
        tmp_path, monkeypatch, fault=fault
    )
    permit = core.prepare(request)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    with adapter.transaction(LEASES) as tx:
        assert tx.read_campaign_result(permit.attempt_id) == result
    path = records_root(runtime) / f"result-{permit.attempt_id}-sealed_uncertain.json"
    record = json.loads(path.read_bytes())
    stored = record["data"]["result"]
    if change == "native-counters":
        stored["receipt"]["opens"] = 0
    elif change == "discard-native-counts":
        stored["receipt"] = None
    else:
        # Fully shaped, bound, within-budget zeros are still invented when no
        # native receipt exists. A self-consistent outer hash is not enough.
        stored["receipt"] = asdict(
            WorkerReceipt(
                permit.attempt_id,
                permit.permit_sha256,
                permit.registration.worker_executable_sha256,
                permit.admission.selected_identity_sha256,
                EffectCertainty.UNCERTAIN,
                False,
                ObservedPowerState.UNKNOWN,
                0,
                0,
                0,
                0,
                0,
                sum(len(item.payload) for item in worker.execution.evidence),
                tuple(item.payload_sha256 for item in worker.execution.evidence),
                PHYSICAL_CAMERA_COMPOSITION,
            )
        )
    record["record_sha256"] = hashlib.sha256(
        canonical_json_bytes(
            {key: value for key, value in record.items() if key != "record_sha256"}
        )
    ).hexdigest()
    path.write_bytes(canonical_json_bytes(record))
    with pytest.raises(M1CommissioningPersistenceError):
        with adapter.transaction(LEASES) as tx:
            tx.read_camera_activation_evidence(permit.attempt_id)


@WINDOWS
@pytest.mark.parametrize("quota", ["files", "bytes"])
def test_shared_family_quota_rejects_before_any_part_publication(
    tmp_path, monkeypatch, quota
):
    runtime, adapter, core, worker, request = actual_components(tmp_path, monkeypatch)
    if quota == "files":
        monkeypatch.setattr(
            persistence, "MAX_RECORDS", 6
        )  # request + parts + 3 terminal reserves needs 7.
    else:
        monkeypatch.setattr(
            persistence, "MAX_RECORD_TOTAL_BYTES", 3 * persistence.MAX_RECORD_BYTES
        )
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN
    with adapter.transaction(LEASES) as tx:
        assert all(
            record["kind"] not in {PART_KIND, INDEX_KIND}
            for record in tx._audit_records().values()
        )


@WINDOWS
@pytest.mark.parametrize(
    "fault",
    [
        "changed-part",
        "extra-part",
        "missing-index",
        "wrong-domain",
        "receipt-accounting",
    ],
)
def test_original_audit_rejects_changed_or_rehomed_records(
    tmp_path, monkeypatch, fault
):
    runtime, adapter, core, worker, request = actual_components(tmp_path, monkeypatch)
    permit = core.prepare(request)
    assert core.execute(permit).state is AttemptState.SEALED_KNOWN
    encoded = encode_camera_evidence_parts(worker.execution.evidence)
    root = records_root(runtime)
    part = root / encoded[0].filename
    record = json.loads(part.read_bytes())
    if fault == "changed-part":
        record["data"]["payload_base64"] = "e30="
    elif fault == "extra-part":
        part = root / (
            "receipt-" + permit.attempt_id + "-camera_activation_extra_a.json"
        )
    elif fault == "missing-index":
        # Test-only modeled absent enumeration; leave the original file intact.
        original = persistence._M1CoordinatorTransaction._read_domain_records

        def missing(self, domain, budget):
            records = original(self, domain, budget)
            records.pop(encoded[-1].filename, None)
            return records

        monkeypatch.setattr(
            persistence._M1CoordinatorTransaction, "_read_domain_records", missing
        )
    elif fault == "wrong-domain":
        # Rehome only in the test-owned store, leaving an unexpected duplicate
        # original name. All records are retained; no deletion/move is needed.
        other = root.parent / persistence._PHYSICAL_USB_IDENTITY_DOMAIN.record_directory
        other.mkdir()
        part = other / encoded[0].filename
        record["schema"] = persistence._PHYSICAL_USB_IDENTITY_DOMAIN.record_schema
        record["composition"] = persistence._PHYSICAL_USB_IDENTITY_DOMAIN.composition
    else:
        # A consistently rehashed result plus both lifecycle receipts must still
        # agree with the retained native counters, not just with each other.
        for filename in (
            f"receipt-{permit.attempt_id}-effect_observed.json",
            f"receipt-{permit.attempt_id}-cleanup_confirmed.json",
            f"result-{permit.attempt_id}-sealed_known.json",
        ):
            destination = root / filename
            changed = json.loads(destination.read_bytes())
            data = changed["data"]
            receipt = data["result"]["receipt"] if "result" in data else data["receipt"]
            receipt["opens"] = 0
            changed["record_sha256"] = hashlib.sha256(
                canonical_json_bytes(
                    {
                        key: value
                        for key, value in changed.items()
                        if key != "record_sha256"
                    }
                )
            ).hexdigest()
            destination.write_bytes(canonical_json_bytes(changed))
    if fault not in {"missing-index", "receipt-accounting"}:
        record["record_sha256"] = hashlib.sha256(
            canonical_json_bytes(
                {key: value for key, value in record.items() if key != "record_sha256"}
            )
        ).hexdigest()
        part.write_bytes(canonical_json_bytes(record))
    with pytest.raises(M1CommissioningPersistenceError):
        with adapter.transaction(LEASES) as tx:
            tx.read_camera_activation_evidence(permit.attempt_id)
    assert worker.calls == 1
