"""Actual qualified NTFS storage/leases; source-only workers and no devices."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any

import pytest

from rocell.application.cell_commissioning_coordinator import (
    AdmissionSnapshot,
    CampaignBudget,
    CampaignEvidence,
    CampaignRegistration,
    CellCommissioningCoordinator,
    CommissioningCoordinatorError,
    CommissioningMode,
    EnergizationEnvelope,
    ExactOperationPermit,
    ObservedPowerState,
    PHYSICAL_DIAGNOSTIC_COMPOSITION,
    PhysicalDiagnosticPreflightCoordinator,
    RegisteredActionRequest,
    RetainedCampaignExecution,
    WorkerReceipt,
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
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import (
    AttemptBinding,
    AttemptState,
    canonical_json_bytes,
)
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.physical_onboarding_m1 import (
    PhysicalOnboardingM1Error,
    PhysicalOnboardingM1Runtime,
)
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.safety.effects import EffectClass, EffectCertainty


SOURCE_BYTES = b'{"actual_selected_source":"preflight only, not a device observation"}'
SOURCE = hashlib.sha256(SOURCE_BYTES).hexdigest()
CELL = "wizard-physical-diagnostic-" + "b" * 16
SESSION = "physical-diagnostic-" + "c" * 32
FIRST = PhysicalOnboardingStage.WORKSPACE_SOURCES
LEASES = (LeaseSpec(LeaseLevel.CELL, CELL), LeaseSpec(LeaseLevel.SESSION, SESSION))
WINDOWS = pytest.mark.skipif(
    os.name != "nt", reason="actual M1 requires qualified NTFS"
)


def facts(request: Any, snapshot: Any) -> PhysicalDiagnosticAdmissionFacts:
    return PhysicalDiagnosticAdmissionFacts(
        {"source_sha256": SOURCE, "device_io_permitted": False},
        tuple({"epoch": i, "source_sha256": SOURCE} for i in range(8)),
        None,
    )


def runtime_and_adapter(tmp_path: Path) -> tuple[Any, Any, Path]:
    root = tmp_path / "physical-source-preflight"
    root.mkdir()
    source_file = tmp_path / "selected-source.json"
    source_file.write_bytes(SOURCE_BYTES)
    runtime = PhysicalOnboardingM1Runtime.initialize(
        root,
        source_binding_sha256=physical_diagnostic_source_binding(SOURCE),
        cell_id=CELL,
        created_at_ns=1000,
    )
    runtime.create_session(
        SESSION,
        created_at_ns=2000,
        mode="PHYSICAL_DIAGNOSTIC",
        workspace_source_sha256=SOURCE,
    )
    adapter = M1PhysicalDiagnosticPersistence(
        runtime,
        workspace_source_sha256=SOURCE,
        admission_facts=facts,
    )
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        tx.commit_stage_state(
            FIRST,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=2001,
            detail_code="SOURCE_PREFLIGHT_PENDING",
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
    return runtime, adapter, source_file


class SourceOnlyWorker:
    """Tests the real storage lifecycle, not the separately integrated source worker."""

    composition = PHYSICAL_DIAGNOSTIC_COMPOSITION
    worker_executable_sha256 = "d" * 64

    def __init__(self, source_file: Path, *, fail: bool = False) -> None:
        self.source_file, self.fail, self.calls = source_file, fail, 0
        self.error: BaseException | None = None

    def run_retained_campaign(
        self, *args: Any, **kwargs: Any
    ) -> RetainedCampaignExecution:
        try:
            return self._source_campaign(*args, **kwargs)
        except BaseException as exc:
            self.error = exc
            raise

    def _source_campaign(
        self,
        permit: ExactOperationPermit,
        *,
        deadline_ns: int,
        cancellation: Any,
        authorize_consumed_permit: Any,
    ) -> RetainedCampaignExecution:
        authorize_consumed_permit(permit)
        self.calls += 1
        if self.fail:
            raise RuntimeError("bounded source-reader fixture failure")
        payload = self.source_file.read_bytes()
        assert hashlib.sha256(payload).hexdigest() == SOURCE
        evidence = CampaignEvidence(
            "rocell.physical-source-fixture.v1", "actual-source", payload
        )
        receipt = WorkerReceipt(
            permit.attempt_id,
            permit.permit_sha256,
            self.worker_executable_sha256,
            None,
            EffectCertainty.CONFIRMED,
            True,
            ObservedPowerState.UNKNOWN,
            0,
            0,
            0,
            0,
            0,
            len(payload),
            (evidence.payload_sha256,),
            composition=self.composition,
        )
        return RetainedCampaignExecution(receipt, (evidence,))


def core_and_request(
    adapter: Any, source_file: Path, *, key: str = "source-once", fail: bool = False
):
    worker = SourceOnlyWorker(source_file, fail=fail)
    registration = CampaignRegistration(
        "physical-source-preflight",
        FIRST,
        EffectClass.NO_DEVICE_IO,
        "physical-source-worker",
        worker.worker_executable_sha256,
        SOURCE,
        (),
        CampaignBudget(10000, 4096, 0, 0, 0, 0, 0),
    )
    core = PhysicalDiagnosticPreflightCoordinator(
        persistence=adapter,
        registrations=(registration,),
        workers={registration.worker_id: worker},
        retained_campaign_actions=(registration.action_id,),
    )
    request = RegisteredActionRequest(
        CELL, SESSION, registration.action_id, key, "a" * 64
    )
    with adapter.transaction(LEASES) as tx:
        request = replace(
            request,
            expected_challenge_sha256=tx.read_admission(request).challenge_sha256,
        )
    return core, worker, request


def records_root(runtime: Any) -> Path:
    return (
        runtime.deployment_root
        / "cells"
        / f"cell-{runtime.cell.cell_key_sha256}"
        / "physical-diagnostic-records"
    )


@contextmanager
def armed_transaction(adapter: Any, source_file: Path):
    core, worker, request = core_and_request(adapter, source_file)
    permit = core.prepare(request)
    admission = permit.admission
    binding = AttemptBinding(
        permit.attempt_id,
        SESSION,
        admission.stage.value,
        permit.registration.effect_class,
        permit.registration.action_id,
        permit.permit_sha256,
        admission.source_binding_sha256,
        admission.stage_plan_sha256,
        admission.journal_head_sha256,
        admission.evidence_inventory_sha256,
        time.time_ns(),
    )
    with adapter.transaction(LEASES) as tx:
        tx.read_admission(request)
        tx.begin_intent(binding, permit)
        tx.consume_permit(permit)
        yield tx, permit, worker


def test_domains_and_facts_are_distinct_and_inert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("pure domain helper did I/O")
    )
    assert physical_diagnostic_source_binding(SOURCE) not in {
        SOURCE,
        rehearsal_source_binding(SOURCE),
    }
    mutable = {"source": SOURCE}
    selected = PhysicalDiagnosticAdmissionFacts(mutable, ({},) * 8, None)
    mutable["source"] = "changed"
    assert json.loads(selected._hazard)["source"] == SOURCE
    assert type(selected) is not RehearsalAdmissionFacts
    for bad in (None, True, "0" * 64, "bad"):
        with pytest.raises(M1CommissioningPersistenceError):
            physical_diagnostic_source_binding(bad)


def pure_permit() -> ExactOperationPermit:
    """Codec input only, not a dispatchable/store-issued permit."""
    admission = AdmissionSnapshot(
        CELL,
        SESSION,
        CommissioningMode.PHYSICAL_DIAGNOSTIC,
        FIRST,
        V2StageState.WAITING_OPERATOR,
        1,
        physical_diagnostic_source_binding(SOURCE),
        *(["a" * 64] * 7),
        ("b" * 64,) * 8,
        None,
        False,
        0,
    )
    registration = CampaignRegistration(
        "physical-source-preflight",
        FIRST,
        EffectClass.NO_DEVICE_IO,
        "physical-source-worker",
        "d" * 64,
        SOURCE,
        (),
        CampaignBudget(10000, 4096, 0, 0, 0, 0, 0),
    )
    request = RegisteredActionRequest(
        CELL, SESSION, registration.action_id, "source-once", admission.challenge_sha256
    )
    return ExactOperationPermit(
        "attempt-" + "e" * 32, request, admission, registration, 100, 200, "f" * 64
    )


@pytest.mark.parametrize(
    "defect",
    [
        "mode",
        "camera",
        "inventory",
        "other_stage",
        "opens",
        "reads",
        "writes",
        "frames",
        "closes",
        "envelope",
        "namespace",
        "extra_field",
        "bool_budget",
    ],
)
def test_physical_permit_codec_is_closed_without_any_store_or_device_access(
    defect: str,
) -> None:
    permit = pure_permit()
    if defect == "mode":
        admission = replace(permit.admission, mode=CommissioningMode.REHEARSAL)
        permit = replace(
            permit,
            admission=admission,
            request=replace(
                permit.request, expected_challenge_sha256=admission.challenge_sha256
            ),
        )
    elif defect in {"camera", "inventory"}:
        effect = (
            EffectClass.BOUNDED_CAMERA_CAMPAIGN
            if defect == "camera"
            else EffectClass.READ_ONLY_OS_INVENTORY
        )
        resources = (LeaseLevel.CAMERA,) if defect == "camera" else ()
        permit = replace(
            permit,
            registration=replace(
                permit.registration, effect_class=effect, resources=resources
            ),
        )
    elif defect == "other_stage":
        stage = PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION
        admission = replace(permit.admission, stage=stage)
        permit = replace(
            permit,
            admission=admission,
            registration=replace(permit.registration, stage=stage),
            request=replace(
                permit.request, expected_challenge_sha256=admission.challenge_sha256
            ),
        )
    elif defect == "envelope":
        permit = replace(
            permit,
            envelope=EnergizationEnvelope(
                "energy-one", SOURCE, *("a" * 64,) * 4, "operator", "observer", 100, 200
            ),
        )
    elif defect == "namespace":
        admission = replace(permit.admission, cell_id="wizard-rehearsal-" + "b" * 16)
        permit = replace(
            permit,
            admission=admission,
            request=replace(
                permit.request,
                cell_id=admission.cell_id,
                expected_challenge_sha256=admission.challenge_sha256,
            ),
        )
    value = json.loads(canonical_json_bytes(asdict(permit)))
    if defect in {"opens", "reads", "writes", "frames", "closes"}:
        value["registration"]["budget"]["maximum_" + defect] = 1
    elif defect == "extra_field":
        value["physical_authority"] = True
    elif defect == "bool_budget":
        value["registration"]["budget"]["maximum_opens"] = False
    with pytest.raises(
        (M1CommissioningPersistenceError, CommissioningCoordinatorError)
    ):
        decode_physical_diagnostic_permit(value)


def test_legacy_decoder_stays_exact_and_physical_facts_reject_energy_envelope() -> None:
    permit = pure_permit()
    value = json.loads(canonical_json_bytes(asdict(permit)))
    assert decode_physical_diagnostic_permit(value) == permit
    with pytest.raises(M1CommissioningPersistenceError):
        _decode_permit(value)
    envelope = EnergizationEnvelope(
        "energy-one", SOURCE, *("a" * 64,) * 4, "operator", "observer", 100, 200
    )
    with pytest.raises(M1CommissioningPersistenceError, match="energy"):
        PhysicalDiagnosticAdmissionFacts({}, ({},) * 8, None, envelope=envelope)


@WINDOWS
def test_actual_physical_source_result_is_retained_known_and_not_replayed(
    tmp_path: Path,
) -> None:
    runtime, adapter, source_file = runtime_and_adapter(tmp_path)
    core, worker, request = core_and_request(adapter, source_file)
    permit = core.prepare(request)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN, (
        result.reason_codes,
        worker.error,
    )
    assert result.composition == PHYSICAL_DIAGNOSTIC_COMPOSITION
    assert result.receipt.final_power_state is ObservedPowerState.UNKNOWN
    assert core.execute(permit) == result and worker.calls == 1
    assert runtime.session_snapshot(SESSION).header.mode == "PHYSICAL_DIAGNOSTIC"
    assert runtime.verify(SESSION).to_dict()["runtime_activation"] is False
    with adapter.transaction(LEASES) as tx:
        assert (
            tx.read_campaign_evidence(permit.attempt_id)[0].payload
            == source_file.read_bytes()
        )
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert len(tx._audit_records()) == 5
    assert all(
        json.loads(p.read_bytes())["composition"] == PHYSICAL_DIAGNOSTIC_COMPOSITION
        for p in records_root(runtime).iterdir()
    )
    reopened = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=physical_diagnostic_source_binding(SOURCE),
        cell_id=CELL,
    )
    fresh = M1PhysicalDiagnosticPersistence(
        reopened, workspace_source_sha256=SOURCE, admission_facts=facts
    )
    other, unused, repeated = core_and_request(fresh, source_file)
    with pytest.raises(
        (M1CommissioningPersistenceError, CommissioningCoordinatorError)
    ):
        other.execute(other.prepare(repeated))
    assert unused.calls == 0
    assert runtime.verify(SESSION).attempt_event_count == 5


@WINDOWS
def test_stage_storage_owns_real_leases_then_refuses_use_after_close(
    tmp_path: Path,
) -> None:
    runtime, adapter, _ = runtime_and_adapter(tmp_path)
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        assert tx.held_leases == LEASES
        assert len(runtime.verify(SESSION).active_lease_owners) == 2
        ref = tx.store_evidence(
            FIRST,
            SOURCE_BYTES,
            label="physical-source-document",
            media_type="application/json",
            captured_at_ns=3000,
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        assert ref.payload_sha256 == SOURCE
    for operation in (
        tx.snapshot,
        tx.verification,
        lambda: tx.held_leases,
        tx._audit_records,
    ):
        with pytest.raises(M1CommissioningPersistenceError, match="scope"):
            operation()
    with pytest.raises(M1CommissioningPersistenceError, match="CELL"):
        with adapter.transaction((*LEASES, LeaseSpec(LeaseLevel.ARM_CONTROLLER, CELL))):
            pytest.fail("device lease admitted")


@WINDOWS
def test_wrong_domains_and_source_never_relabel_existing_session(
    tmp_path: Path,
) -> None:
    runtime, adapter, source_file = runtime_and_adapter(tmp_path)
    with pytest.raises(M1CommissioningPersistenceError):
        M1CommissioningPersistence(
            runtime,
            workspace_source_sha256=SOURCE,
            admission_facts=lambda *_: RehearsalAdmissionFacts({}, ({},) * 8, None),
        )
    with pytest.raises(PhysicalOnboardingM1Error):
        with runtime.rehearsal_transaction(SESSION):
            pytest.fail("physical session reinterpreted")
    for workspace in (None, "f" * 64):
        with pytest.raises(PhysicalOnboardingM1Error):
            runtime.create_session(
                "physical-diagnostic-" + "e" * 32, workspace_source_sha256=workspace
            )
    with pytest.raises(M1CommissioningPersistenceError):
        M1PhysicalDiagnosticPersistence(
            runtime, workspace_source_sha256="f" * 64, admission_facts=facts
        )
    core, worker, request = core_and_request(adapter, source_file)
    permit = core.prepare(request)
    serialized = json.loads(canonical_json_bytes(asdict(permit)))
    assert decode_physical_diagnostic_permit(serialized) == permit
    with pytest.raises(M1CommissioningPersistenceError):
        _decode_permit(serialized)
    with pytest.raises(CommissioningCoordinatorError):
        CellCommissioningCoordinator(
            persistence=adapter,
            registrations=(permit.registration,),
            workers={permit.registration.worker_id: worker},
        )


@WINDOWS
def test_acknowledgement_once_revalidation_readonly_and_scope_bound(
    tmp_path: Path,
) -> None:
    runtime, adapter, source_file = runtime_and_adapter(tmp_path)
    with armed_transaction(adapter, source_file) as (tx, permit, worker):
        with pytest.raises(M1CommissioningPersistenceError, match="prior"):
            tx.revalidate_consumed_permit(permit)
        tx.assert_consumed_permit(permit)
        before = {p.name: p.read_bytes() for p in records_root(runtime).iterdir()}
        elapsed_checks = []
        for _ in range(2):
            started = time.perf_counter()
            tx.revalidate_consumed_permit(permit)
            elapsed_checks.append(time.perf_counter() - started)
        # Diagnostic measurement only: not a portable latency qualification or
        # permission to enlarge a child release/permit deadline.
        print("minimal M1 revalidation seconds:", elapsed_checks)
        assert before == {
            p.name: p.read_bytes() for p in records_root(runtime).iterdir()
        }
        assert runtime.verify(SESSION).attempt_event_count == 2
        with pytest.raises(M1CommissioningPersistenceError, match="one-use"):
            tx.assert_consumed_permit(permit)
        with pytest.raises(M1CommissioningPersistenceError):
            tx.revalidate_consumed_permit(replace(permit, nonce="e" * 64))
        assert worker.calls == 0
        tx.seal_uncertain(permit.attempt_id, ("TEST_NO_DEVICE_IO",))
        with pytest.raises(M1CommissioningPersistenceError):
            tx.revalidate_consumed_permit(permit)
    with pytest.raises(M1CommissioningPersistenceError, match="scope"):
        tx.revalidate_consumed_permit(permit)


@WINDOWS
def test_revalidation_rejects_actual_server_fact_drift_without_ledger_writes(
    tmp_path: Path,
) -> None:
    runtime, adapter, source_file = runtime_and_adapter(tmp_path)
    with armed_transaction(adapter, source_file) as (tx, permit, _):
        tx.assert_consumed_permit(permit)
        original = tx._facts_provider
        baseline = facts(None, None)
        for replacement in (
            PhysicalDiagnosticAdmissionFacts({"source": "changed"}, ({},) * 8, None),
            PhysicalDiagnosticAdmissionFacts(
                baseline.hazard_assessment_document, ({"epoch": "changed"},) * 8, None
            ),
            PhysicalDiagnosticAdmissionFacts(
                baseline.hazard_assessment_document,
                baseline.configuration_epoch_documents,
                {"selected": "changed"},
            ),
            PhysicalDiagnosticAdmissionFacts(
                baseline.hazard_assessment_document,
                baseline.configuration_epoch_documents,
                None,
                ("HOLD",),
            ),
            RehearsalAdmissionFacts(
                baseline.hazard_assessment_document,
                baseline.configuration_epoch_documents,
                None,
            ),
        ):
            tx._facts_provider = lambda *_: replacement
            with pytest.raises(M1CommissioningPersistenceError):
                tx.revalidate_consumed_permit(permit)
        tx._facts_provider = original
        tx.revalidate_consumed_permit(permit)
        assert runtime.verify(SESSION).attempt_event_count == 2


@WINDOWS
@pytest.mark.parametrize("defect", ["missing", "payload", "composition"])
def test_known_physical_source_requires_exact_retained_bytes_after_restart(
    tmp_path: Path, defect: str
) -> None:
    runtime, adapter, source_file = runtime_and_adapter(tmp_path)
    core, _, request = core_and_request(adapter, source_file)
    permit = core.prepare(request)
    assert core.execute(permit).state is AttemptState.SEALED_KNOWN
    path = records_root(runtime) / f"evidence-{permit.attempt_id}-retained.json"
    if defect == "missing":
        # Test-owned corruption only, not a recovery or production delete path.
        path.unlink()
    else:
        record = json.loads(path.read_bytes())
        if defect == "payload":
            record["data"]["evidence"][0]["payload_base64"] = "e30="
        else:
            record["composition"] = "HARDWARE_INCAPABLE_REHEARSAL"
        record["record_sha256"] = hashlib.sha256(
            canonical_json_bytes(
                {k: v for k, v in record.items() if k != "record_sha256"}
            )
        ).hexdigest()
        path.write_bytes(canonical_json_bytes(record))
    with pytest.raises(M1CommissioningPersistenceError):
        with adapter.transaction(LEASES) as tx:
            tx._audit_records()


@WINDOWS
def test_worker_failure_retains_uncertainty_and_no_source_success(
    tmp_path: Path,
) -> None:
    runtime, adapter, source_file = runtime_and_adapter(tmp_path)
    core, worker, request = core_and_request(adapter, source_file, fail=True)
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert result.composition == PHYSICAL_DIAGNOSTIC_COMPOSITION
    assert runtime.verify(SESSION).quarantined and worker.calls == 1


@WINDOWS
def test_constructor_is_inert_on_an_existing_qualified_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, _, _ = runtime_and_adapter(tmp_path)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("adapter construction performed I/O")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(PhysicalOnboardingM1Runtime, "verify", forbidden)
    M1PhysicalDiagnosticPersistence(
        runtime, workspace_source_sha256=SOURCE, admission_facts=facts
    )
