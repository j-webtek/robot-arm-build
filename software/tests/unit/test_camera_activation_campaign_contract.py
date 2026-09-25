"""Camera-v2 core joins with modeled owner/scope facts; never physical access."""

from dataclasses import replace
from threading import Event

import pytest

from rocell.application.camera_activation_campaign_contract import (
    ACTION_IDS,
    WORKER_IDS,
    RetainedCameraActivationExecution,
    validate_camera_activation_binding,
    validate_camera_activation_execution,
    validate_camera_activation_permit,
    validate_camera_activation_receipt,
)
from rocell.application.camera_activation_campaign_evidence import (
    MAX_CAMERA_ACTIVATION_CAMPAIGN_BYTES,
    camera_activation_evidence,
    validate_camera_activation_evidence,
)
from rocell.application.cell_commissioning_coordinator import (
    CampaignBudget,
    CommissioningMode,
    ObservedPowerState,
    PHYSICAL_CAMERA_COMPOSITION,
    PhysicalCameraAcquisitionCoordinator,
    RegisteredActionRequest,
    WorkerReceipt,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.safety.effects import EffectCertainty
from rocell.providers.windows import native_camera_activation_supervisor as supervisor
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from rocell.providers.windows.native_camera_activation_registration import (
    prepare_owned_activation,
)
from rocell.providers.windows.native_camera_protocol import canonical
from test_native_camera_activation_registration import inputs, ready
from test_native_camera_activation_protocol import fixture as result_fixture
from test_native_camera_activation_evidence import modeled
from test_native_camera_activation_supervisor import (
    ModelOwner,
    Clock,
    no_physical_owner,
)
from test_physical_camera_coordinator import (
    CELL,
    SESSION,
    CameraProtocolStore,
    admission,
    registration,
)


def profile(purpose="probe"):
    return registration(
        action_id=ACTION_IDS[purpose],
        worker_id=WORKER_IDS[purpose],
        worker_executable_sha256="c" * 64,
        operation_sha256="e" * 64,
        stage=(
            PhysicalOnboardingStage.CAMERA_MODE_CONTROLS
            if purpose == "probe"
            else PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS
        ),
        budget=CampaignBudget(
            20_000 if purpose == "probe" else 25_000,
            MAX_CAMERA_ACTIVATION_CAMPAIGN_BYTES,
            1,
            int(purpose == "capture"),
            0,
            int(purpose == "capture"),
            1,
        ),
    )


def build_execution(
    directory,
    monkeypatch,
    permit,
    deadline,
    *,
    purpose="probe",
    fault=None,
    current=lambda exact: None,
    clock=None,
    cancellation=None,
):
    """Exercise the installed parent/supervisor with only a modeled owner."""
    runtime, old, expectation, args = inputs(directory, purpose)
    client = WindowsCameraWorkerClient(runtime.to_dict()["helper"]["path"], "c" * 64)
    binding = replace(
        old.request.binding, binding_sha256=permit.admission.selected_identity_sha256
    )
    common = dict(
        source_sha256="a" * 64, campaign_id=permit.attempt_id, budget=old.request.budget
    )
    plan = (
        client.prepare_probe(binding, **common)
        if purpose == "probe"
        else client.prepare_capture(
            binding,
            old.request.mode,
            directory / ("capture-" + permit.attempt_id),
            controls=old.request.controls,
            **common,
        )
    )
    args.update(
        session_id=permit.request.session_id,
        operation_sha256=permit.registration.operation_sha256,
        permit_sha256=permit.permit_sha256,
    )
    prepared = prepare_owned_activation(runtime, plan, expectation, **args)
    raw_owner, owner_args = modeled(directory, purpose)
    owner_args["ready_wire"] = ready(prepared)
    _, _, raw = result_fixture(purpose)
    raw["request_sha256"] = prepared.admission_request.request_sha256
    raw["permit_sha256"] = permit.permit_sha256
    raw_owner.stdout = owner_args["ready_wire"] + canonical(raw) + b"\n"
    owner = ModelOwner(raw_owner, owner_args, fault)
    if fault == "large":
        owner.result = b"x" * (256 * 1024 - len(owner.ready))
    monkeypatch.setattr(supervisor, "_new_owner", lambda: owner)
    if clock is None:
        clock = Clock()
        clock.tick = permit.issued_at_ns
    outcome = supervisor._supervise(
        prepared,
        prepared.registration,
        revalidate_consumed_permit=current,
        cancellation=cancellation or Event(),
        deadline_ns=deadline,
        _clock=clock,
    )
    artifacts = camera_activation_evidence(prepared, outcome)
    assessment = outcome.run_evidence(prepared).assessment()
    if assessment.native is None:
        return RetainedCameraActivationExecution(
            None, artifacts, ("NATIVE_ACCOUNTING_UNAVAILABLE",)
        )
    native = assessment.native.receipt
    receipt = WorkerReceipt(
        permit.attempt_id,
        permit.permit_sha256,
        permit.registration.worker_executable_sha256,
        permit.admission.selected_identity_sha256,
        (
            EffectCertainty.CONFIRMED
            if assessment.status == "SUCCEEDED_NATIVE_DIAGNOSTIC"
            else EffectCertainty.UNCERTAIN
        ),
        assessment.process_cleanup_confirmed and native.cleanup_confirmed,
        ObservedPowerState.UNKNOWN,
        native.counts["source_activation_attempts"],
        native.counts["samples_received"],
        native.counts["control_set_attempts"],
        native.counts["frames_written"],
        native.counts["source_shutdown_attempts"],
        sum(len(item.payload) for item in artifacts),
        tuple(item.payload_sha256 for item in artifacts),
        PHYSICAL_CAMERA_COMPOSITION,
    )
    return RetainedCameraActivationExecution(receipt, artifacts)


class CameraV2Store(CameraProtocolStore):
    def retain_camera_activation_evidence(self, permit, evidence):
        assert self.acknowledged
        validate_camera_activation_binding(permit, evidence)
        self.evidence = evidence
        self.trace.append("CAMERA_V2_EVIDENCE_RETAINED")


class ModeledCameraV2Worker:
    composition = PHYSICAL_CAMERA_COMPOSITION
    worker_executable_sha256 = "c" * 64

    def __init__(self, directory, monkeypatch, clock, purpose="probe", fault=None):
        self.directory, self.patch, self.clock = directory, monkeypatch, clock
        self.purpose, self.fault = purpose, fault
        self.calls = 0
        self.execution = None

    def run_scoped_campaign(self, permit, *, deadline_ns, cancellation, authorization):
        self.calls += 1
        authorization.acknowledge(permit)
        self.execution = build_execution(
            self.directory,
            self.patch,
            permit,
            deadline_ns + int(self.fault == "deadline-binding"),
            purpose=self.purpose,
            fault=self.fault,
            clock=self.clock,
            cancellation=cancellation,
            current=lambda exact: authorization.revalidate(permit),
        )
        if self.fault == "late-cancel":
            cancellation.set()
        return self.execution


def components(directory, monkeypatch, purpose="probe", fault=None, store=None):
    item, clock = profile(purpose), Clock()
    if store is None:
        store = CameraV2Store(admission(stage=item.stage))
    worker = ModeledCameraV2Worker(directory, monkeypatch, clock, purpose, fault)
    core = PhysicalCameraAcquisitionCoordinator(
        persistence=store,
        registrations=(item,),
        workers={item.worker_id: worker},
        retained_campaign_actions=(item.action_id,),
        scoped_campaign_actions=(item.action_id,),
        monotonic_ns=clock,
    )
    request = RegisteredActionRequest(
        CELL,
        SESSION,
        item.action_id,
        "camera-v2-one-use",
        store.snapshot.challenge_sha256,
    )
    return core, store, worker, request


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_original_core_known_accounting_and_one_use(tmp_path, monkeypatch, purpose):
    core, store, worker, request = components(tmp_path, monkeypatch, purpose)
    permit = core.prepare(request)
    assert validate_camera_activation_permit(permit) == purpose
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN
    assert result.receipt.opens == result.receipt.closes == 1
    assert result.receipt.frames == int(purpose == "capture")
    assert result.receipt.final_power_state is ObservedPowerState.UNKNOWN
    assert result.physical_authority == "NONE"
    assert store.evidence == worker.execution.evidence
    assert store.trace.index("CAMERA_V2_EVIDENCE_RETAINED") < store.trace.index(
        "EFFECT_OBSERVED"
    )
    assert core.execute(permit) == result and worker.calls == 1


@pytest.mark.parametrize(
    "fault", ["bad-result", "large", "cleanup-missing-resource", "late-cancel"]
)
def test_failed_observations_retained_before_uncertainty(tmp_path, monkeypatch, fault):
    core, store, worker, request = components(tmp_path, monkeypatch, fault=fault)
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert store.evidence == worker.execution.evidence
    assert store.trace.index("CAMERA_V2_EVIDENCE_RETAINED") < store.trace.index(
        "QUARANTINE_LATCHED"
    )
    if fault in {"bad-result", "large"}:
        assert result.receipt is None
        assert result.reason_codes == ("NATIVE_ACCOUNTING_UNAVAILABLE",)
    elif fault == "late-cancel":
        assert "CONSUMED_SCOPE_REVALIDATION_FAILED" in result.reason_codes
    else:
        assert result.receipt.cleanup_confirmed is False


def test_other_deadline_cannot_be_retained_as_original(tmp_path, monkeypatch):
    core, store, worker, request = components(
        tmp_path, monkeypatch, fault="deadline-binding"
    )
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert "CAMERA_V2_EVIDENCE_RETAINED" not in store.trace


@pytest.mark.parametrize(
    "field,value",
    [
        ("opens", True),
        ("output_bytes", 0),
        ("reads", 1),
        ("cleanup_confirmed", 1),
        ("effect_certainty", "CONFIRMED"),
        ("final_power_state", "UNKNOWN"),
        ("evidence_sha256s", ("a" * 64,)),
        ("composition", "HARDWARE_INCAPABLE_REHEARSAL"),
    ],
)
def test_exact_native_receipt_cannot_be_inflated_or_type_coerced(
    tmp_path, monkeypatch, field, value
):
    core, _, _, request = components(tmp_path, monkeypatch)
    permit = core.prepare(request)
    deadline = permit.issued_at_ns + 20_000_000_000
    execution = build_execution(tmp_path, monkeypatch, permit, deadline)
    validate_camera_activation_execution(
        execution, permit, expected_deadline_ns=deadline
    )
    validate_camera_activation_receipt(
        execution.receipt, permit, execution.evidence, expected_deadline_ns=deadline
    )
    changed = replace(execution, receipt=replace(execution.receipt, **{field: value}))
    with pytest.raises(ValueError):
        validate_camera_activation_execution(
            changed, permit, expected_deadline_ns=deadline
        )
    with pytest.raises(ValueError):
        validate_camera_activation_receipt(
            changed.receipt, permit, execution.evidence, expected_deadline_ns=deadline
        )


@pytest.mark.parametrize(
    "change",
    ["mode", "stage", "worker", "budget", "source", "identity", "operation", "session"],
)
def test_original_permit_binding_cannot_be_substituted(tmp_path, monkeypatch, change):
    core, _, _, request = components(tmp_path, monkeypatch)
    permit = core.prepare(request)
    execution = build_execution(
        tmp_path, monkeypatch, permit, permit.issued_at_ns + 20_000_000_000
    )
    if change == "mode":
        bad = replace(
            permit,
            admission=replace(permit.admission, mode=CommissioningMode.REHEARSAL),
        )
    elif change == "stage":
        bad = replace(
            permit,
            registration=replace(
                permit.registration,
                stage=PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS,
            ),
        )
    elif change == "worker":
        bad = replace(
            permit, registration=replace(permit.registration, worker_id="other-worker")
        )
    elif change == "budget":
        bad = replace(
            permit,
            registration=replace(
                permit.registration,
                budget=replace(
                    permit.registration.budget, maximum_output_bytes=128 * 1024
                ),
            ),
        )
    elif change in {"source", "identity"}:
        field = (
            "source_binding_sha256"
            if change == "source"
            else "selected_identity_sha256"
        )
        bad = replace(permit, admission=replace(permit.admission, **{field: "8" * 64}))
    elif change == "operation":
        bad = replace(
            permit, registration=replace(permit.registration, operation_sha256="8" * 64)
        )
    else:
        bad = replace(
            permit,
            request=replace(permit.request, session_id="physical-camera-" + "8" * 32),
        )
    with pytest.raises(ValueError):
        validate_camera_activation_binding(bad, execution.evidence)
    with pytest.raises(ValueError):
        validate_camera_activation_receipt(
            execution.receipt,
            bad,
            execution.evidence,
            expected_deadline_ns=permit.issued_at_ns + 20_000_000_000,
        )


def test_complete_native_counts_cannot_be_discarded(tmp_path, monkeypatch):
    core, _, _, request = components(tmp_path, monkeypatch)
    permit = core.prepare(request)
    execution = build_execution(
        tmp_path, monkeypatch, permit, permit.issued_at_ns + 20_000_000_000
    )
    assert (
        validate_camera_activation_evidence(execution.evidence).run.assessment().native
        is not None
    )
    with pytest.raises(ValueError):
        RetainedCameraActivationExecution(
            None, execution.evidence, ("INVENTED_MISSING_COUNTS",)
        )
    with pytest.raises(ValueError):
        validate_camera_activation_receipt(
            None,
            permit,
            execution.evidence,
            expected_deadline_ns=permit.issued_at_ns + 20_000_000_000,
        )


@pytest.mark.parametrize("purpose", ["probe", "capture"])
@pytest.mark.parametrize("fault", [None, "bad-result", "cleanup-missing-resource"])
def test_direct_original_receipt_preserves_native_availability(
    tmp_path, monkeypatch, purpose, fault
):
    core, _, _, request = components(tmp_path, monkeypatch, purpose)
    permit = core.prepare(request)
    deadline = permit.issued_at_ns + 20_000_000_000
    execution = build_execution(
        tmp_path, monkeypatch, permit, deadline, purpose=purpose, fault=fault
    )
    validate_camera_activation_receipt(
        execution.receipt, permit, execution.evidence, expected_deadline_ns=deadline
    )
    assert (execution.receipt is None) is (fault == "bad-result")
    # The independently retained parent deadline remains exact, even when the
    # native result is absent. A direct receipt read does not renew it.
    with pytest.raises(ValueError):
        validate_camera_activation_receipt(
            execution.receipt,
            permit,
            execution.evidence,
            expected_deadline_ns=deadline + 1,
        )
