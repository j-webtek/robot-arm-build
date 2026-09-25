"""Actual NTFS publication and Windows leases with incapable contract workers.

These isolated test stores use a fixed synthetic source and explicitly labeled
predecessor fixture evidence. Their PASS journal entries exercise storage only;
they are not received-camera, identity, source, or operator qualification.
No native helper, camera, serial, inventory, or child process is invoked.
"""

from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from rocell.application.cell_commissioning_coordinator import (
    CommissioningCoordinatorError,
    EnergizationEnvelope,
    ObservedPowerState,
    PHYSICAL_CAMERA_COMPOSITION,
    PhysicalCameraAcquisitionCoordinator,
    RegisteredActionRequest,
)
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    M1PhysicalCameraTransaction,
    PhysicalCameraAdmissionFacts,
    RECORD_SCHEMA,
    decode_physical_camera_permit,
    physical_camera_source_binding,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistence,
    M1CommissioningPersistenceError,
    RehearsalAdmissionFacts,
    _decode_permit,
    rehearsal_source_binding,
)
from rocell.application.commissioning_physical_persistence import (
    M1PhysicalDiagnosticPersistence,
    PhysicalDiagnosticAdmissionFacts,
    decode_physical_diagnostic_permit,
    physical_diagnostic_source_binding,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_attempts import (
    AttemptState,
    canonical_json_bytes,
)
from rocell.application.physical_onboarding_leases import (
    LeaseLevel,
    LeaseSpec,
    PhysicalOnboardingLeaseError,
)
from rocell.application.physical_onboarding_m1 import (
    PhysicalOnboardingM1Error,
    PhysicalOnboardingM1Runtime,
)
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient

from test_physical_camera_coordinator import (
    ACTION,
    CELL,
    LEASES,
    PAYLOAD,
    SESSION,
    SOURCE,
    STAGE,
    IncapableCameraContractWorker,
    registration,
)


WINDOWS = pytest.mark.skipif(
    os.name != "nt", reason="actual qualified NTFS and OS leases"
)


@pytest.fixture(autouse=True)
def forbid_device_and_process_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    def denied(*args: Any, **kwargs: Any) -> None:
        pytest.fail(
            "camera persistence tests must not execute a process or access devices"
        )

    monkeypatch.setattr(subprocess, "Popen", denied)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, denied)


def facts(request: Any, snapshot: Any) -> PhysicalCameraAdmissionFacts:
    return PhysicalCameraAdmissionFacts(
        {"provenance": "INCAPABLE_CONTRACT_TEST", "source_sha256": SOURCE},
        tuple({"epoch": i, "source_sha256": SOURCE} for i in range(8)),
        {"provenance": "INCAPABLE_CONTRACT_TEST", "selected_camera": "NO_DEVICE"},
    )


def runtime_and_adapter(tmp_path: Path, *, ready: bool = True):
    assigned = tmp_path / "isolated-camera-contract"
    assigned.mkdir()
    runtime = PhysicalOnboardingM1Runtime.initialize(
        assigned,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        cell_id=CELL,
        created_at_ns=1000,
    )
    runtime.create_session(
        SESSION,
        created_at_ns=2000,
        mode="PHYSICAL_DIAGNOSTIC",
        workspace_source_sha256=SOURCE,
    )
    adapter = M1PhysicalCameraPersistence(
        runtime,
        workspace_source_sha256=SOURCE,
        admission_facts=facts,
    )
    if ready:
        # Storage fixture, not application evidence admission. Every predecessor
        # remains explicitly marked incapable inside its immutable payload.
        with adapter.stage_transaction(
            SESSION,
            expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
        ) as tx:
            timestamp = 2001
            for stage in STAGE_ORDER[: STAGE_ORDER.index(STAGE) + 1]:
                tx.commit_stage_state(
                    stage,
                    V2StageState.WAITING_OPERATOR,
                    occurred_at_ns=timestamp,
                    detail_code="INCAPABLE_CONTRACT_TEST_PENDING",
                    expected_head_sha256=tx.snapshot().head.head_sha256,
                )
                timestamp += 1
                if stage is STAGE:
                    break
                reference = tx.store_evidence(
                    stage,
                    canonical_json_bytes(
                        {
                            "schema": "rocell.incapable-stage-contract.v1",
                            "stage": stage.value,
                            "physical_authority": False,
                            "hardware_qualification": "NOT_TESTED",
                        }
                    ),
                    label="incapable predecessor storage fixture",
                    media_type="application/json",
                    captured_at_ns=timestamp,
                    expected_head_sha256=tx.snapshot().head.head_sha256,
                )
                for state in (V2StageState.REVIEW_PENDING, V2StageState.PASS):
                    tx.commit_stage_state(
                        stage,
                        state,
                        occurred_at_ns=timestamp,
                        detail_code="INCAPABLE_CONTRACT_STORAGE_ONLY",
                        expected_head_sha256=tx.snapshot().head.head_sha256,
                        evidence=(reference,),
                    )
                    timestamp += 1
    return runtime, adapter


def core_and_request(adapter: Any, *, fault: str | None = None, key: str = "one-use"):
    worker = IncapableCameraContractWorker(fault=fault)
    item = registration()
    core = PhysicalCameraAcquisitionCoordinator(
        persistence=adapter,
        registrations=(item,),
        workers={item.worker_id: worker},
        retained_campaign_actions=(ACTION,),
        scoped_campaign_actions=(ACTION,),
    )
    request = RegisteredActionRequest(CELL, SESSION, ACTION, key, "1" * 64)
    with adapter.transaction(LEASES) as tx:
        request = replace(
            request,
            expected_challenge_sha256=tx.read_admission(request).challenge_sha256,
        )
    return core, worker, request


def records_root(runtime: PhysicalOnboardingM1Runtime) -> Path:
    return (
        runtime.deployment_root
        / "cells"
        / f"cell-{runtime.cell.cell_key_sha256}"
        / "physical-camera-records"
    )


def test_camera_facts_and_source_binding_are_distinct_immutable_and_inert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("pure helper did file I/O")
    )
    binding = physical_camera_source_binding(SOURCE)
    assert (
        len(
            {
                binding,
                SOURCE,
                rehearsal_source_binding(SOURCE),
                physical_diagnostic_source_binding(SOURCE),
            }
        )
        == 4
    )
    identity = {"selected": "NO_DEVICE"}
    selected = PhysicalCameraAdmissionFacts({}, ({},) * 8, identity)
    identity["selected"] = "changed"
    assert json.loads(selected._identity)["selected"] == "NO_DEVICE"
    assert type(selected) not in {
        PhysicalDiagnosticAdmissionFacts,
        RehearsalAdmissionFacts,
    }
    with pytest.raises(M1CommissioningPersistenceError, match="selected identity"):
        PhysicalCameraAdmissionFacts({}, ({},) * 8, None)
    envelope = EnergizationEnvelope(
        "energy", SOURCE, *("a" * 64,) * 4, "operator", "observer", 0, 1
    )
    with pytest.raises(M1CommissioningPersistenceError, match="energy"):
        PhysicalCameraAdmissionFacts({}, ({},) * 8, {}, envelope=envelope)
    for invalid in (None, True, 1, "bad", "0" * 64):
        with pytest.raises(M1CommissioningPersistenceError):
            physical_camera_source_binding(invalid)


@WINDOWS
def test_actual_camera_lifecycle_retains_reopens_and_refuses_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, adapter = runtime_and_adapter(tmp_path)
    counts = {"admission": 0, "revalidation": 0}
    original_read = M1PhysicalCameraTransaction.read_admission
    original_revalidate = M1PhysicalCameraTransaction.revalidate_consumed_permit

    def read(self: Any, request: Any):
        counts["admission"] += 1
        assert self.held_leases == LEASES
        return original_read(self, request)

    def revalidate(self: Any, permit: Any):
        counts["revalidation"] += 1
        assert self.held_leases == LEASES
        return original_revalidate(self, permit)

    monkeypatch.setattr(M1PhysicalCameraTransaction, "read_admission", read)
    monkeypatch.setattr(
        M1PhysicalCameraTransaction, "revalidate_consumed_permit", revalidate
    )
    core, worker, request = core_and_request(adapter)
    permit = core.prepare(request)
    assert permit.envelope is None
    assert permit.admission.selected_identity_sha256 is not None
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN, (
        result.reason_codes,
        worker.error,
    )
    assert result.composition == PHYSICAL_CAMERA_COMPOSITION
    assert result.physical_authority == "NONE"
    assert result.receipt.final_power_state is ObservedPowerState.UNKNOWN
    assert (
        result.receipt.opens,
        result.receipt.reads,
        result.receipt.writes,
        result.receipt.frames,
        result.receipt.closes,
    ) == (0, 0, 0, 0, 0)
    assert counts["admission"] >= 4 and counts["revalidation"] == 2
    assert core.execute(permit) == result and worker.calls == 1
    with pytest.raises(CommissioningCoordinatorError):
        worker.authority.revalidate(permit)
    with adapter.transaction(LEASES) as tx:
        assert tx.held_leases == LEASES
        assert tuple(owner.level for owner in tx._held.owners) == tuple(
            spec.level for spec in LEASES
        )
        assert tx.read_campaign_evidence(permit.attempt_id)[0].payload == PAYLOAD
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert len(tx._audit_records()) == 5
    assert not runtime.verify(SESSION).active_lease_owners
    assert runtime.verify(SESSION).attempt_event_count == 5
    for path in records_root(runtime).iterdir():
        value = json.loads(path.read_bytes())
        assert value["schema"] == RECORD_SCHEMA
        assert value["composition"] == PHYSICAL_CAMERA_COMPOSITION
    value = json.loads(canonical_json_bytes(asdict(permit)))
    assert decode_physical_camera_permit(value) == permit
    for decoder in (_decode_permit, decode_physical_diagnostic_permit):
        with pytest.raises(M1CommissioningPersistenceError):
            decoder(value)

    reopened = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        cell_id=CELL,
    )
    fresh = M1PhysicalCameraPersistence(
        reopened, workspace_source_sha256=SOURCE, admission_facts=facts
    )
    other, unused, repeated = core_and_request(fresh)
    with pytest.raises(CommissioningCoordinatorError, match="unknown"):
        other.execute(permit)
    with pytest.raises(
        (M1CommissioningPersistenceError, CommissioningCoordinatorError)
    ):
        other.execute(other.prepare(repeated))
    assert unused.calls == 0 and runtime.verify(SESSION).attempt_event_count == 5
    with fresh.transaction(LEASES) as tx:
        assert tx.read_campaign_evidence(permit.attempt_id)[0].payload == PAYLOAD
    # Corrupt only the test-owned copy after the successful original-store join.
    # Rehashing the outer record cannot conceal damaged substantive evidence.
    path = records_root(runtime) / f"evidence-{permit.attempt_id}-retained.json"
    record = json.loads(path.read_bytes())
    record["data"]["evidence"][0]["payload_base64"] = "e30="
    record["record_sha256"] = hashlib.sha256(
        canonical_json_bytes({k: v for k, v in record.items() if k != "record_sha256"})
    ).hexdigest()
    path.write_bytes(canonical_json_bytes(record))
    with pytest.raises(M1CommissioningPersistenceError):
        with fresh.transaction(LEASES) as tx:
            tx.read_campaign_evidence(permit.attempt_id)
    assert unused.calls == 0


@WINDOWS
def test_stage_only_real_scope_cannot_supply_camera_admission_or_device_lease(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, adapter = runtime_and_adapter(tmp_path, ready=False)
    before = adapter.verification(SESSION)
    request = RegisteredActionRequest(CELL, SESSION, ACTION, "no-acquisition", "a" * 64)
    with adapter.stage_transaction(
        SESSION, expected_challenge_sha256=before.challenge_sha256
    ) as tx:
        assert tx.held_leases == LEASES[:2]
        assert len(runtime.verify(SESSION).active_lease_owners) == 2
        with pytest.raises(M1CommissioningPersistenceError, match="admission policy"):
            tx.read_admission(request)
        with pytest.raises(PhysicalOnboardingLeaseError):
            with runtime.physical_camera_transaction(
                SESSION, device_levels=(LeaseLevel.CAMERA,)
            ):
                pytest.fail("second writer acquired the live cell lease")
    for action in (
        tx.snapshot,
        tx.verification,
        lambda: tx.held_leases,
        lambda: tx.read_admission(request),
    ):
        with pytest.raises(M1CommissioningPersistenceError, match="scope"):
            action()
    assert runtime.verify(SESSION).attempt_event_count == 0
    for invalid in (
        LEASES[:2],
        (*LEASES[:2], LeaseSpec(LeaseLevel.ARM_CONTROLLER, CELL)),
        tuple(reversed(LEASES)),
        [*LEASES],
    ):
        with pytest.raises(M1CommissioningPersistenceError):
            with adapter.transaction(invalid):
                pytest.fail("wrong acquisition leases admitted")
    for levels in (
        (LeaseLevel.ARM_CONTROLLER,),
        (LeaseLevel.CAMERA, LeaseLevel.ARM_CONTROLLER),
        [LeaseLevel.CAMERA],
    ):
        with pytest.raises(PhysicalOnboardingM1Error):
            with runtime.physical_camera_transaction(SESSION, device_levels=levels):
                pytest.fail("non-camera levels admitted")
    with pytest.raises(M1CommissioningPersistenceError):
        M1PhysicalCameraPersistence(
            runtime, workspace_source_sha256="f" * 64, admission_facts=facts
        )
    for constructor, provider in (
        (
            M1CommissioningPersistence,
            lambda *_: RehearsalAdmissionFacts({}, ({},) * 8, None),
        ),
        (
            M1PhysicalDiagnosticPersistence,
            lambda *_: PhysicalDiagnosticAdmissionFacts({}, ({},) * 8, None),
        ),
    ):
        with pytest.raises(M1CommissioningPersistenceError):
            constructor(
                runtime, workspace_source_sha256=SOURCE, admission_facts=provider
            )
    for method in (
        runtime.rehearsal_transaction,
        runtime.physical_diagnostic_transaction,
    ):
        with pytest.raises(PhysicalOnboardingM1Error):
            with method(SESSION):
                pytest.fail("camera store interpreted as another domain")
    for workspace in (None, "f" * 64):
        with pytest.raises(PhysicalOnboardingM1Error):
            runtime.create_session(
                "physical-camera-" + "e" * 32, workspace_source_sha256=workspace
            )
    # Construction is still an inert composition check on an existing runtime.
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("constructor file I/O")
    )
    monkeypatch.setattr(
        PhysicalOnboardingM1Runtime,
        "verify",
        lambda *a, **k: pytest.fail("constructor activation"),
    )
    M1PhysicalCameraPersistence(
        runtime, workspace_source_sha256=SOURCE, admission_facts=facts
    )


@WINDOWS
@pytest.mark.parametrize("domain", ["source-only", "rehearsal"])
def test_other_actual_store_namespaces_and_source_bindings_are_refused(
    tmp_path: Path, domain: str
) -> None:
    is_source = domain == "source-only"
    cell = (
        "wizard-physical-diagnostic-" if is_source else "wizard-rehearsal-"
    ) + "b" * 16
    session = ("physical-diagnostic-" if is_source else "rehearsal-") + "c" * 32
    root = tmp_path / domain
    root.mkdir()
    runtime = PhysicalOnboardingM1Runtime.initialize(
        root,
        source_binding_sha256=(
            physical_diagnostic_source_binding
            if is_source
            else rehearsal_source_binding
        )(SOURCE),
        cell_id=cell,
        created_at_ns=1000,
    )
    runtime.create_session(
        session,
        mode="PHYSICAL_DIAGNOSTIC" if is_source else "REHEARSAL",
        created_at_ns=2000,
        workspace_source_sha256=SOURCE,
    )
    with pytest.raises(M1CommissioningPersistenceError):
        M1PhysicalCameraPersistence(
            runtime, workspace_source_sha256=SOURCE, admission_facts=facts
        )
    with pytest.raises(PhysicalOnboardingM1Error):
        with runtime.physical_camera_transaction(
            session, device_levels=(LeaseLevel.CAMERA,)
        ):
            pytest.fail("foreign store provided camera leases")
    assert runtime.verify(session).attempt_event_count == 0


@WINDOWS
def test_actual_scope_omission_retains_failure_bytes_and_quarantines(
    tmp_path: Path,
) -> None:
    runtime, adapter = runtime_and_adapter(tmp_path)
    core, worker, request = core_and_request(adapter, fault="omit-check")
    permit = core.prepare(request)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert result.composition == PHYSICAL_CAMERA_COMPOSITION and worker.calls == 1
    assert runtime.verify(SESSION).quarantined
    assert core.execute(permit) == result
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        assert tx.read_campaign_evidence(permit.attempt_id)[0].payload == PAYLOAD
    with pytest.raises(CommissioningCoordinatorError):
        worker.authority.revalidate(permit)
