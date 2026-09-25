"""Scoped original readback: protocol faults and real NTFS, no devices.

Pure cases model only ownership/storage callbacks. Actual NTFS cases retain
explicit incapable bytes; any predecessor PASS fixtures are storage tests, not
physical source, identity, receipt, power or runtime qualifications.
"""

from contextlib import contextmanager
from dataclasses import replace
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application import commissioning_camera_persistence as module
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from test_camera_stage_evidence_readback import PAYLOAD, retain, stage
from test_commissioning_camera_persistence import (
    core_and_request,
    facts,
    runtime_and_adapter,
)
from test_physical_camera_coordinator import CELL, LEASES, SESSION, SOURCE
from test_physical_configuration_epochs import reference


WINDOWS = pytest.mark.skipif(os.name != "nt", reason="actual qualified NTFS and leases")


@pytest.fixture(autouse=True)
def no_device_or_process(monkeypatch):
    import subprocess

    def forbidden(*args, **kwargs):
        pytest.fail("original readback must not execute processes or access devices")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    for method in (
        "enumerate_metadata",
        "resolve_identity_metadata",
        "probe",
        "capture",
    ):
        monkeypatch.setattr(WindowsCameraWorkerClient, method, forbidden)


@pytest.fixture
def modeled_scope(tmp_path, monkeypatch):
    """Actual reader methods with explicitly modeled lease/package primitives."""
    ref = reference(STAGE_ORDER[0], PAYLOAD, salt="camera-readback-model")
    snapshot = SimpleNamespace(
        header=SimpleNamespace(cell_id=CELL, session_id=SESSION), evidence=(ref,)
    )
    tx = object.__new__(module.M1PhysicalCameraTransaction)
    tx._active = True
    tx._specs = LEASES
    tx._held = SimpleNamespace(
        closed=False,
        owners=tuple(
            SimpleNamespace(level=spec.level, resource_id=spec.resource_id)
            for spec in LEASES
        ),
    )
    counts = {"audit": 0, "verify": 0, "read": 0, "guard": 0}
    tx._guard = lambda: None
    tx._session = SimpleNamespace(directory=tmp_path, snapshot=lambda: snapshot)
    tx._retention_authorized = False
    tx._permit = None

    def audit():
        tx._check_scope()
        counts["audit"] += 1
        return {}

    tx._audit_records = audit

    def no_mutation(*args, **kwargs):
        pytest.fail("readback called a mutation or admission path")

    tx.store_evidence = tx.commit_stage_state = tx.read_admission = no_mutation
    tx._facts_provider = no_mutation

    @contextmanager
    def guard(path):
        assert path == tmp_path / "evidence" / ref.evidence_id
        counts["guard"] += 1
        yield

    def verify(path, header):
        assert path == tmp_path / "evidence" / ref.evidence_id
        assert header is snapshot.header
        counts["verify"] += 1
        return ref

    def read(path, **kwargs):
        assert path == tmp_path / "evidence" / ref.evidence_id / "payload.bin"
        assert kwargs["maximum_bytes"] == len(PAYLOAD)
        counts["read"] += 1
        return PAYLOAD

    monkeypatch.setattr(module, "_directory_guard", guard)
    monkeypatch.setattr(module, "_verify_evidence_directory", verify)
    monkeypatch.setattr(module, "read_bounded_regular_file", read)
    return SimpleNamespace(
        tx=tx, reference=ref, snapshot=snapshot, counts=counts, read=read, verify=verify
    )


def test_camera_reader_uses_audit_inventory_and_both_original_checks(modeled_scope):
    value = modeled_scope
    assert value.tx.read_camera_evidence(value.reference) == PAYLOAD
    assert value.counts == {"audit": 1, "verify": 2, "read": 1, "guard": 1}
    assert value.tx._retention_authorized is False and value.tx._permit is None


@pytest.mark.parametrize(
    "kind", ["dict", "path", "boolean_bytes", "length", "digest", "stage", "id"]
)
def test_exact_reference_and_inventory_required(modeled_scope, kind):
    value = modeled_scope
    ref = value.reference
    invalid = {
        "dict": ref.to_dict(),
        "path": Path("payload.bin"),
        "boolean_bytes": replace(ref, payload_bytes=True),
        "length": replace(ref, payload_bytes=ref.payload_bytes + 1),
        "digest": replace(ref, payload_sha256="f" * 64),
        "stage": replace(ref, stage=STAGE_ORDER[1]),
        "id": replace(ref, evidence_id="../other-store"),
    }[kind]
    with pytest.raises(M1CommissioningPersistenceError):
        value.tx.read_camera_evidence(invalid)
    assert value.counts["read"] == value.counts["verify"] == 0


@pytest.mark.parametrize(
    "leases",
    [LEASES[:2], LEASES[::-1], (*LEASES, LeaseSpec(LeaseLevel.ARM_CONTROLLER, CELL))],
)
def test_camera_reader_denies_other_lease_sets_before_package_read(
    modeled_scope, leases
):
    value = modeled_scope
    value.tx._specs = leases
    value.tx._held.owners = tuple(
        SimpleNamespace(level=spec.level, resource_id=spec.resource_id)
        for spec in leases
    )
    with pytest.raises(M1CommissioningPersistenceError, match="camera leases"):
        value.tx.read_camera_evidence(value.reference)
    assert value.counts == {"audit": 0, "verify": 0, "read": 0, "guard": 0}


@pytest.mark.parametrize(
    "fault",
    [
        "audit",
        "hash",
        "length",
        "pre_package",
        "post_package",
        "scope",
        "owner",
        "guard_exit",
    ],
)
def test_camera_reader_rejects_partial_or_changed_readback(
    modeled_scope, monkeypatch, fault
):
    value = modeled_scope
    tx = value.tx
    if fault == "audit":

        def audit():
            raise M1CommissioningPersistenceError(
                "modeled inconsistent original records"
            )

        tx._audit_records = audit
    elif fault in {"pre_package", "post_package"}:

        def verify(path, header):
            result = value.verify(path, header)
            if value.counts["verify"] == (1 if fault == "pre_package" else 2):
                return replace(result, payload_sha256="f" * 64)
            return result

        monkeypatch.setattr(module, "_verify_evidence_directory", verify)
    elif fault == "guard_exit":

        @contextmanager
        def guard(path):
            yield
            tx.close_scope()

        monkeypatch.setattr(module, "_directory_guard", guard)
    else:

        def read(path, **kwargs):
            payload = value.read(path, **kwargs)
            if fault == "hash":
                return b"x" * len(payload)
            if fault == "length":
                return payload + b"x"
            if fault == "scope":
                tx.close_scope()
            if fault == "owner":
                tx._held.owners = tx._held.owners[:2]
            return payload

        monkeypatch.setattr(module, "read_bounded_regular_file", read)
    with pytest.raises(M1CommissioningPersistenceError):
        tx.read_camera_evidence(value.reference)


@WINDOWS
def test_actual_original_camera_lease_read_is_inert_and_reopens(tmp_path):
    runtime, adapter = runtime_and_adapter(tmp_path, ready=False)
    with stage(adapter) as tx:
        ref = retain(tx)
        original = tx.snapshot()
        assert tx.read_stage_evidence(ref) == PAYLOAD
        with pytest.raises(M1CommissioningPersistenceError, match="camera leases"):
            tx.read_camera_evidence(ref)
    with adapter.transaction(LEASES) as tx:
        assert tx.read_camera_evidence(ref) == PAYLOAD
        with pytest.raises(M1CommissioningPersistenceError, match="stage-only"):
            tx.read_stage_evidence(ref)
        assert tx.snapshot() == original
        assert not tx._audit_records()
    with pytest.raises(M1CommissioningPersistenceError, match="scope has ended"):
        tx.read_camera_evidence(ref)
    reopened = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=module.physical_camera_source_binding(SOURCE),
        cell_id=CELL,
    )
    fresh = module.M1PhysicalCameraPersistence(
        reopened, workspace_source_sha256=SOURCE, admission_facts=facts
    )
    with fresh.transaction(LEASES) as tx:
        assert tx.read_camera_evidence(ref) == PAYLOAD
        assert tx.snapshot() == original
    verified = reopened.verify(SESSION)
    assert verified.attempt_event_count == 0
    assert not verified.active_lease_owners and not verified.quarantined
    assert all(row.state is V2StageState.PENDING for row in original.stages[1:])


@WINDOWS
def test_actual_result_reader_restores_known_and_later_uncertain_seals(
    tmp_path, monkeypatch
):
    runtime, adapter = runtime_and_adapter(tmp_path)
    core, worker, request = core_and_request(adapter)
    permit = core.prepare(request)
    known = core.execute(permit)
    assert known.state is AttemptState.SEALED_KNOWN
    with adapter.transaction(LEASES) as tx:
        assert tx.read_campaign_result(permit.attempt_id) == known
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert tx.read_campaign_evidence(permit.attempt_id)[0].payload
        with pytest.raises(M1CommissioningPersistenceError):
            tx.read_campaign_result("attempt-" + "0" * 32)
    with pytest.raises(M1CommissioningPersistenceError, match="scope has ended"):
        tx.read_campaign_result(permit.attempt_id)

    abort_core, abort_worker, abort_request = core_and_request(
        adapter, key="explicit-cancel-before-effect"
    )
    abort_permit = abort_core.prepare(abort_request)
    abort_core.cancel(abort_permit)
    aborted = abort_core.execute(abort_permit)
    assert aborted.state is AttemptState.ABORTED_PRE_EFFECT
    assert abort_worker.calls == 0
    with adapter.transaction(LEASES) as tx:
        assert tx.read_campaign_result(abort_permit.attempt_id) == aborted

    # Explicit second protocol-model operation: persist known result then fail
    # the seal. Only the durable uncertain result may be returned afterwards.
    next_core, next_worker, next_request = core_and_request(
        adapter, key="explicit-seal-fault"
    )
    next_permit = next_core.prepare(next_request)
    transition = module.M1PhysicalCameraTransaction.transition

    def failed_seal(self, attempt_id, state, receipt):
        if state is AttemptState.SEALED_KNOWN:
            with pytest.raises(M1CommissioningPersistenceError, match="terminal state"):
                self.read_campaign_result(attempt_id)
            raise M1CommissioningPersistenceError(
                "modeled known seal publication failure"
            )
        return transition(self, attempt_id, state, receipt)

    with monkeypatch.context() as patch:
        patch.setattr(module.M1PhysicalCameraTransaction, "transition", failed_seal)
        uncertain = next_core.execute(next_permit)
    assert (
        uncertain.state is AttemptState.SEALED_UNCERTAIN
        and uncertain.quarantine_latched
    )
    with stage(adapter) as tx:
        records = tx._audit_records()
        assert f"result-{next_permit.attempt_id}-sealed_known.json" in records
        assert tx.read_campaign_result(next_permit.attempt_id) == uncertain
        assert tx.read_campaign_result(permit.attempt_id) == known  # historical only
    assert worker.calls == next_worker.calls == 1
    assert runtime.verify(SESSION).quarantined
