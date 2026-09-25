"""Owned USB lifecycle tests: explicit incapable/model data, no USB adapter calls."""

from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
from threading import Event
import time
from types import SimpleNamespace

import pytest

from rocell.application.cell_commissioning_coordinator import (
    ExactOperationPermit,
    RegisteredActionRequest,
    UsbIdentityAdmissionSnapshot,
    CampaignRegistration,
    CampaignBudget,
    CommissioningMode,
)
from rocell.application.consumed_commissioning_scope import ConsumedCommissioningScope
from rocell.application.commissioning_camera_persistence import (
    physical_camera_source_binding,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage as Stage
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.usb_identity_stage_policy import (
    UsbIdentityAdmissionIdentity,
    usb_identity_stage_policy,
)
from rocell.providers.windows import owned_usb_identity_runner as runner_module
from rocell.providers.windows import owned_worker_process as shared
from rocell.providers.windows.usb_identity_registration import (
    UsbIdentityRuntimeRegistration,
    UsbIdentityRuntimeReview,
    PreparedOwnedUsbIdentity,
    PreparedIncapableUsbIdentity,
    incapable_usb_identity_runtime_candidate,
    usb_identity_runtime_candidate,
    review_usb_identity_runtime,
    prepare_incapable_usb_identity,
    prepare_owned_usb_identity,
    inspect_usb_identity_runtime,
)
from rocell.providers.windows.usb_identity_protocol import (
    UsbIdentityAdmissionRequest,
    REQUEST_SCHEMA,
    canonical,
    digest,
)
from rocell.providers.windows.owned_usb_identity_runner import (
    IncapableUsbIdentityRunner,
    OwnedUsbIdentityRunner,
)
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
    verify_owned_usb_identity_run_evidence,
    stream_bytes,
)
from test_usb_identity_stage_policy import identity_document

WORKSPACE = Path(__file__).parents[3]
ENDPOINT = r"\\?\usb#vid_1234&pid_5678#MODELED-ONLY"
INSTANCE = r"USB\VID_1234&PID_5678&MI_00\MODELED-ENDPOINT"


@pytest.fixture(autouse=True)
def modeled_workspace_source(monkeypatch):
    """The fixture source is synthetic; native files/process remain real."""
    monkeypatch.setattr(runner_module, "source_fingerprint", lambda workspace: "a" * 64)


class ModeledScopeTransaction:
    """Explicitly incapable transaction-body model; not an NTFS/physical proof."""

    def __init__(self, permit, fail_at=None):
        self.permit = permit
        self.held_leases = (
            LeaseSpec(LeaseLevel.CELL, permit.request.cell_id),
            LeaseSpec(LeaseLevel.SESSION, permit.request.session_id),
            LeaseSpec(LeaseLevel.CAMERA, permit.request.cell_id),
        )
        self.acks = self.checks = 0
        self.fail_at = fail_at

    def assert_consumed_permit(self, permit):
        assert canonical(asdict(permit)) == canonical(asdict(self.permit))
        self.acks += 1
        assert self.acks == 1

    def revalidate_consumed_permit(self, permit):
        assert canonical(asdict(permit)) == canonical(asdict(self.permit))
        self.checks += 1
        if self.checks == self.fail_at:
            raise ValueError("MODELED_CURRENT_SCOPE_REFUSED")


def usb_fixture(
    workspace=WORKSPACE,
    *,
    incapable=True,
    source_sha256="a" * 64,
    selection_sha256="a" * 64,
    native_identity_sha256="b" * 64,
    endpoint=ENDPOINT,
    instance=INSTANCE,
    fail_at=None,
    cell_id=None,
    session_id=None,
    header_sha256=None,
    launch_session_id="modeled-usb-launch",
    operation_sha256="d" * 64,
    attempt_id="attempt-modeled-usb",
):
    """Actual codecs + explicit modeled original refs/scope; constructor performs no I/O."""
    runtime = (
        incapable_usb_identity_runtime_candidate
        if incapable
        else usb_identity_runtime_candidate
    )(workspace, source_sha256=source_sha256)
    review = review_usb_identity_runtime(
        runtime,
        selection_sha256=selection_sha256,
        native_identity_sha256=native_identity_sha256,
        endpoint_sha256=digest(endpoint.encode()),
        device_instance_id_sha256=digest(instance.encode()),
        operation_sha256=operation_sha256,
        operator_id="modeled-inspector",
        reviewer_id="modeled-reviewer",
        launch_session_id=launch_session_id,
        reviewed_at_ns=1,
    )
    document = identity_document()
    if cell_id is not None:
        document["cell_id"] = cell_id
    if session_id is not None:
        document["session_id"] = session_id
    if header_sha256 is not None:
        document["header_sha256"] = header_sha256
    document.update(
        source_sha256=source_sha256,
        runtime_review_sha256=review.sha256,
        runtime_registration_sha256=runtime.sha256,
        selection_sha256=selection_sha256,
        native_identity_sha256=native_identity_sha256,
        endpoint_sha256=digest(endpoint.encode()),
        device_instance_id_sha256=digest(instance.encode()),
        operation_sha256=operation_sha256,
    )
    subject = document["original_subjects"][2]
    subject["document_sha256"] = review.sha256
    subject["reference"].update(
        evidence_id="evidence-" + review.sha256,
        package_sha256=review.sha256,
        manifest_sha256=review.sha256,
        payload_sha256=review.sha256,
        payload_bytes=len(review.payload),
    )
    identity = UsbIdentityAdmissionIdentity(canonical(document))
    admission = UsbIdentityAdmissionSnapshot(
        cell_id=document["cell_id"],
        session_id=document["session_id"],
        mode=CommissioningMode.PHYSICAL_DIAGNOSTIC,
        stage=Stage.CAMERA_IDENTITY,
        stage_state=V2StageState.WAITING_OPERATOR,
        stage_revision=4,
        source_binding_sha256=physical_camera_source_binding(source_sha256),
        stage_plan_sha256="a" * 64,
        journal_head_sha256="b" * 64,
        global_attempt_head_sha256="c" * 64,
        quarantine_head_sha256="d" * 64,
        evidence_inventory_sha256="e" * 64,
        hazard_assessment_sha256="f" * 64,
        durability_qualification_sha256="1" * 64,
        configuration_epoch_hashes=("2" * 64,) * 8,
        selected_identity_sha256=identity.sha256,
        quarantine_latched=False,
        unresolved_attempts=0,
        usb_query_policy_sha256=usb_identity_stage_policy().sha256,
    )
    action = RegisteredActionRequest(
        document["cell_id"],
        document["session_id"],
        "physical-native-usb-identity",
        "modeled-usb-request",
        admission.challenge_sha256,
    )
    registration = CampaignRegistration(
        "physical-native-usb-identity",
        Stage.CAMERA_IDENTITY,
        runner_module.EffectClass.BOUNDED_CAMERA_CAMPAIGN,
        "scoped-physical-native-usb-identity",
        runtime.to_dict()["helper"]["sha256"],
        operation_sha256,
        (LeaseLevel.CAMERA,),
        CampaignBudget(25000, 128 * 1024, 32, 128, 0, 0, 32),
    )
    started = time.monotonic_ns()
    permit = ExactOperationPermit(
        attempt_id,
        action,
        admission,
        registration,
        started,
        started + 30_000_000_000,
        "modeled-usb-nonce",
    )
    request = UsbIdentityAdmissionRequest(
        canonical(
            {
                "schema": REQUEST_SCHEMA,
                "attempt_id": permit.attempt_id,
                "session_id": document["session_id"],
                "source_sha256": source_sha256,
                "operation_sha256": operation_sha256,
                "selected_identity_sha256": identity.sha256,
                "native_identity_sha256": native_identity_sha256,
                "endpoint": endpoint,
                "endpoint_sha256": digest(endpoint.encode()),
                "expected_device_instance_id": instance,
                "expected_device_instance_id_sha256": digest(instance.encode()),
                "helper_sha256": runtime.to_dict()["helper"]["sha256"],
                "runtime_registration_sha256": runtime.sha256,
                "permit_sha256": permit.permit_sha256,
                "native_duration_ms": 10000,
                "admission_timeout_ms": 5000,
            }
        )
    )
    prepared = (
        prepare_incapable_usb_identity if incapable else prepare_owned_usb_identity
    )(
        runtime,
        review=review,
        expected_review_sha256=review.sha256,
        identity=identity,
        request=request,
    )
    cancel = Event()
    tx = ModeledScopeTransaction(permit, fail_at)
    deadline = started + 25_000_000_000
    scope = ConsumedCommissioningScope(
        permit,
        transaction=tx,
        deadline_ns=deadline,
        cancellation=cancel,
        monotonic_ns=time.monotonic_ns,
    )
    return SimpleNamespace(
        runtime=runtime,
        review=review,
        identity=identity,
        request=request,
        prepared=prepared,
        permit=permit,
        cancellation=cancel,
        deadline_ns=deadline,
        transaction=tx,
        scope=scope,
    )


def run_case(case, guard=lambda: None):
    cls = (
        IncapableUsbIdentityRunner
        if type(case.prepared) is PreparedIncapableUsbIdentity
        else OwnedUsbIdentityRunner
    )
    runner = cls(
        case.prepared,
        permit=case.permit,
        authorization=case.scope,
        application_guard=guard,
    )
    evidence = runner.run(cancellation=case.cancellation, deadline_ns=case.deadline_ns)
    return runner, evidence


def test_fixture_is_pure(monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("constructor performed I/O")

    monkeypatch.setattr(Path, "open", forbidden)
    case = usb_fixture()
    assert case.prepared.request.payload == case.request.payload
    assert len(case.prepared.payload) < 24 * 1024


@pytest.mark.parametrize(
    "path,value",
    [
        (("physical_authority",), 0),
        (("hardware_qualified",), 0),
        (("source_files", 0, "bytes"), True),
        (("helper", "path"), "arbitrary.exe"),
        (("helper", "sha256"), "0" * 64),
    ],
)
def test_runtime_exact_frozen_values(path, value):
    case = usb_fixture()
    doc = case.runtime.to_dict()
    target = doc
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        type(case.runtime)(canonical(doc))


@pytest.mark.parametrize(
    "field,value",
    [
        ("reviewer_id", "MODELED-INSPECTOR"),
        ("reviewer_id", ""),
        ("physical_authority", 0),
        ("reviewed_at_ns", True),
        ("runtime_registration_sha256", "f" * 64),
        ("endpoint_sha256", "f" * 64),
    ],
)
def test_review_subjects_are_not_replaceable(field, value):
    case = usb_fixture()
    doc = case.review.to_dict()
    doc[field] = value
    with pytest.raises(ValueError):
        changed = UsbIdentityRuntimeReview(canonical(doc))
        prepare_incapable_usb_identity(
            case.runtime,
            review=changed,
            expected_review_sha256=changed.sha256,
            identity=case.identity,
            request=case.request,
        )


def test_preflight_stop_retains_no_attempt(monkeypatch):
    case = usb_fixture()
    case.cancellation.set()
    monkeypatch.setattr(
        runner_module, "_new_owner", lambda: pytest.fail("owner constructed afterStop")
    )
    runner, evidence = run_case(case)
    assert evidence.status == "CANCELLED" and evidence.no_attempt
    assert evidence.actual_counts["hub_open_attempts"] == 0 and not evidence.released
    assert runner.retained_evidence.payload == evidence.payload
    with pytest.raises(ValueError):
        runner.run(cancellation=case.cancellation, deadline_ns=case.deadline_ns)


def test_review_cannot_enable_physical_without_scope():
    case = usb_fixture(incapable=False)
    with pytest.raises(ValueError):
        OwnedUsbIdentityRunner(
            case.prepared,
            permit=case.permit,
            authorization=object(),
            application_guard=lambda: None,
        )
    with pytest.raises(ValueError):
        IncapableUsbIdentityRunner(
            case.prepared,
            permit=case.permit,
            authorization=case.scope,
            application_guard=lambda: None,
        )


def test_scope_refusal_before_pin_retained(monkeypatch):
    case = usb_fixture(fail_at=1)
    monkeypatch.setattr(
        runner_module, "_new_owner", lambda: pytest.fail("owner afterscope refusal")
    )
    _, evidence = run_case(case)
    assert evidence.no_attempt and evidence.status == "FAILED"
    assert case.transaction.acks == 1 and case.transaction.checks == 1


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: replace(
            p, registration=replace(p.registration, stage=Stage.CAMERA_MODE_CONTROLS)
        ),
        lambda p: replace(
            p, registration=replace(p.registration, worker_id="other-worker")
        ),
        lambda p: replace(
            p, admission=replace(p.admission, selected_identity_sha256="e" * 64)
        ),
        lambda p: replace(
            p, admission=replace(p.admission, usb_query_policy_sha256="e" * 64)
        ),
    ],
)
def test_permit_crossdomain_or_target_refused(mutation):
    case = usb_fixture()
    with pytest.raises(ValueError):
        IncapableUsbIdentityRunner(
            case.prepared,
            permit=mutation(case.permit),
            authorization=case.scope,
            application_guard=lambda: None,
        )


def test_actual_incapable_job_pipe(monkeypatch):
    """Real Windows Job/files/pipes; native USB adapter is not linked into target."""
    assert shared._UNRESOLVED_BACKEND is None
    case = usb_fixture()
    runner, evidence = run_case(case)
    assert evidence.status == "OBSERVED", evidence.to_dict()
    assert case.transaction.acks == 1 and case.transaction.checks == 5
    assert (
        evidence.released
        and evidence.process_cleanup_confirmed
        and evidence.usb_cleanup_confirmed
    )
    assert evidence.actual_counts["hub_open_attempts"] == 5
    assert evidence.to_dict()["process"]["peak_processes"] == 1
    assert evidence.preparation.request.payload == case.request.payload
    assert evidence.observation.to_dict()["requested_endpoint"] == ENDPOINT
    assert evidence.to_dict()["provenance"] == "INCAPABLE_USB_QUERY"
    assert len(evidence.payload) <= 128 * 1024
    checked = verify_owned_usb_identity_run_evidence(
        evidence,
        expected_preparation_sha256=case.prepared.sha256,
        expected_evidence_sha256=evidence.sha256,
    )
    assert checked.payload == runner.retained_evidence.payload
    assert shared._UNRESOLVED_BACKEND is None


class FaultOwner:
    """Pure fixed API-body model: never creates a process, file, DLL or USB handle."""

    def __init__(self, case, fault):
        self.case, self.fault = case, fault
        self.created = self.resumed = self.tree_exited = self.pending = False
        self.stdout_eof = self.stderr_eof = False
        self.returncode = None
        self.pid = self.written = self.peak_handles = self.peak_processes = 0
        self.stdout = self.stderr = b""
        self.handles, self.unclosed_handles, self.pins = {}, {}, []
        self.errors = []
        self.cleanup_calls = 0

    def pin(self, registration):
        self.pins.append(object())
        if self.fault == "pin":
            raise OSError("PIN_FAILED")

    def start(self, registration, wire, *, check, keep_stdin_open):
        from rocell.providers.windows.usb_identity_protocol import READY_SCHEMA

        check()
        self.created = True
        self.pid = 31415
        check()
        self.resumed = True
        check()
        self.written = len(wire)
        self.stdout = (
            canonical(
                {
                    "schema": READY_SCHEMA,
                    "request_sha256": self.case.request.request_sha256,
                    "child_pid": self.pid,
                    "challenge": "e" * 64,
                }
            )
            + b"\n"
        )
        if self.fault == "bad-ready":
            self.stdout = b'{"broken":1}\n'
        if self.fault == "partial-ready":
            self.stdout = self.stdout[:40]
            self.returncode = 2
        if self.fault == "early-output":
            self.stdout += b"UNAUTHORIZED_EXTRA"
        if self.fault == "oversize-ready":
            self.stdout = b"x" * 1024

    def poll(self, budget):
        if self.fault == "process-count":
            self.peak_processes = 2
        if self.fault == "cancel-poll":
            self.case.cancellation.set()
        if self.returncode is not None:
            self.tree_exited = self.stdout_eof = self.stderr_eof = True
            return True
        return False

    def send_final_input(self, wire, *, check):
        check()
        self.written += len(wire)
        self.stdout += b"ORIGINAL_MALFORMED_RESULT"
        self.stderr = b"INCAPABLE_FAULT_DIAGNOSTIC"
        if self.fault == "full-streams":
            self.stdout = self.stdout.split(b"\n", 1)[0] + b"\n"
            self.stdout += b"x" * (66 * 1024 - len(self.stdout))
            self.stderr = b"y" * (4 * 1024)
            raise ValueError("STDOUT_LIMIT")
        if self.fault == "write":
            raise OSError("WRITE_FAILED")
        self.returncode = 1

    def cleanup(self, deadline_ns):
        self.cleanup_calls += 1
        self.tree_exited = self.created
        if self.fault == "cleanup":
            return ("PIN_CLOSE_UNCONFIRMED",)
        self.pins.clear()
        if self.fault == "late-stop":
            self.case.cancellation.set()
        return ()


def modeled_owner(case, monkeypatch, fault):
    owner = FaultOwner(case, fault)
    monkeypatch.setattr(runner_module, "_new_owner", lambda: owner)
    monkeypatch.setattr(
        runner_module, "inspect_usb_identity_runtime", lambda *a, **k: None
    )
    return owner


@pytest.mark.parametrize(
    "fault",
    [
        "pin",
        "bad-ready",
        "partial-ready",
        "early-output",
        "oversize-ready",
        "cancel-poll",
        "write",
        "malformed-result",
        "cleanup",
        "full-streams",
        "process-count",
    ],
)
def test_injected_failures_keep_original_prefixes(monkeypatch, fault):
    case = usb_fixture()
    owner = modeled_owner(case, monkeypatch, fault)
    # This owner is incapable and only a Python object; isolate its held storage.
    monkeypatch.setattr(shared, "_UNRESOLVED_BACKEND", None)
    runner, evidence = run_case(case)
    assert owner.cleanup_calls == 1
    assert evidence.status != "OBSERVED"
    assert stream_bytes(evidence.to_dict()["stdout"], 66 * 1024) == owner.stdout
    assert stream_bytes(evidence.to_dict()["stderr"], 4 * 1024) == owner.stderr
    assert len(evidence.payload) <= 128 * 1024
    assert runner.retained_evidence.payload == evidence.payload
    if owner.created:
        assert evidence.actual_counts is None and not evidence.no_attempt
    else:
        assert evidence.no_attempt and evidence.actual_counts["api_calls"] == 0
    if fault == "cleanup":
        assert shared._UNRESOLVED_BACKEND is owner
        assert evidence.status == "CLEANUP_UNCERTAIN"
    if fault == "process-count":
        assert evidence.error == "USB_OWNED_PROCESS_COUNT_EXCEEDED"
        assert evidence.to_dict()["process"]["peak_processes"] == 2
        assert not evidence.to_dict()["release_write_attempted"]


@pytest.mark.parametrize("boundary", [2, 3, 4])
def test_stale_scope_does_not_schedule_release(monkeypatch, boundary):
    case = usb_fixture(fail_at=boundary)
    owner = modeled_owner(case, monkeypatch, "malformed-result")
    _, evidence = run_case(case)
    data = evidence.to_dict()
    assert case.transaction.checks == boundary
    assert not data["release_write_attempted"] and not data["release_check_passed"]
    assert not evidence.released and evidence.status == "FAILED"
    assert owner.cleanup_calls == 1
    if boundary == 4:
        assert data["ready_length"] > 0
        assert stream_bytes(data["stdout"], 66 * 1024).endswith(b"\n")
        assert evidence.actual_counts is None


def test_each_scope_boundary_checks_fresh_source(monkeypatch):
    case = usb_fixture()
    owner = modeled_owner(case, monkeypatch, "malformed-result")
    calls = []

    def source(path):
        calls.append(path)
        return "f" * 64 if len(calls) == 4 else "a" * 64

    monkeypatch.setattr(runner_module, "source_fingerprint", source)
    _, evidence = run_case(case)
    assert len(calls) == 4 and case.transaction.checks == 3
    assert evidence.error == "CURRENT_USB_WORKSPACE_SOURCE_CHANGED"
    assert not evidence.to_dict()["release_check_passed"]
    assert owner.cleanup_calls == 1


def test_inspection_does_not_become_review(monkeypatch):
    case = usb_fixture()
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("file opened afterStop")
    )
    case.cancellation.set()
    with pytest.raises(ValueError, match="CANCELLED"):
        inspect_usb_identity_runtime(
            case.runtime, cancellation=case.cancellation, deadline_ns=case.deadline_ns
        )


@pytest.mark.parametrize(
    "field",
    ["status", "preparation_sha256", "provenance", "physical_authority", "retries"],
)
def test_rehashed_evidence_cannot_override_meaning(monkeypatch, field):
    case = usb_fixture()
    case.cancellation.set()
    _, evidence = run_case(case)
    doc = evidence.to_dict()
    doc[field] = {
        "status": "OBSERVED",
        "preparation_sha256": "f" * 64,
        "provenance": "PHYSICAL_USB_QUERY",
        "physical_authority": 0,
        "retries": True,
    }[field]
    with pytest.raises(ValueError):
        OwnedUsbIdentityRunEvidence(canonical(doc))


def test_malformed_cleanup_and_preparation_are_closed_rejections(monkeypatch):
    case = usb_fixture()
    case.cancellation.set()
    _, evidence = run_case(case)
    for key, value in (("cleanup_errors", [[]]), ("preparation", [])):
        document = evidence.to_dict()
        document[key] = value
        with pytest.raises(ValueError):
            OwnedUsbIdentityRunEvidence(canonical(document))


def test_short_original_deadline_never_constructs_owner(monkeypatch):
    case = usb_fixture()
    case.deadline_ns = time.monotonic_ns() + 19_000_000_000
    monkeypatch.setattr(runner_module, "_new_owner", lambda: pytest.fail("owner"))
    _, evidence = run_case(case)
    assert evidence.no_attempt and evidence.error == "FULL_USB_LIFETIME_DOES_NOT_FIT"
    assert evidence.to_dict()["original_deadline_ns"] == case.deadline_ns


def test_failure_stream_capacity_reserves_complete_preparation(monkeypatch):
    # Worst retained streams, not a synthetic successful device observation.
    case = usb_fixture(endpoint="\\\\?\\" + "x" * 4080, instance="USB\\" + "y" * 4080)
    modeled_owner(case, monkeypatch, "full-streams")
    _, evidence = run_case(case)
    document = evidence.to_dict()
    assert len(evidence.preparation.payload) > 16000
    assert stream_bytes(document["stdout"], 66 * 1024)
    assert len(stream_bytes(document["stderr"], 4 * 1024)) == 4 * 1024
    assert len(evidence.payload) < 128 * 1024
    assert document["preparation"] == case.prepared.to_dict()
    assert all(len(s) <= 21848 for s in document["stdout"]["base64_chunks"])
