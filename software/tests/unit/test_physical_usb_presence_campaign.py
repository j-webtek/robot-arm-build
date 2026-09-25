"""Campaign joins with explicitly MODELED originals/observations/ownership.

No helper/process/device/CIM API runs. The successful physical-shaped reports
below are closed test models, not real ownership evidence or hardware approval.
Their purpose is to exercise every production codec and full campaign join.
"""

from dataclasses import asdict, replace
from pathlib import Path
from threading import Event
import os
import subprocess
import time
from types import SimpleNamespace

import pytest

from rocell.application import physical_usb_presence_campaign as m
from rocell.application.cell_commissioning_coordinator import (
    ExactOperationPermit,
    RegisteredActionRequest,
    UsbPresenceAdmissionSnapshot,
    RetainedCampaignExecution,
    RetainedUncertainCampaignExecution,
    ObservedPowerState,
)
from rocell.application.consumed_commissioning_scope import ConsumedCommissioningScope
from rocell.providers.windows import owned_usb_presence_evidence as evidence
from rocell.providers.windows import owned_usb_presence_runner as runner
from rocell.providers.windows import usb_presence_protocol as wire
from rocell.providers.windows.usb_presence_review import review_usb_presence_runtime
from rocell.safety.effects import EffectCertainty
from test_physical_camera_coordinator import admission
from test_physical_received_camera import prerequisites, workspace
from test_owned_usb_identity_runner import ModeledScopeTransaction
from test_usb_presence_review import review_fixture

_BASE = None
_FROZEN_PHYSICAL_RUNNER = runner.OwnedUsbPresenceRunner


def modeled_presence_campaign(
    prerequisites,
    *,
    outcome="ABSENT",
    launch_session_id="wizard-presence-current",
    operation_id="usbphase-" + "d" * 32,
    reviewed_at_ns=None,
    started_utc_ns=None,
):
    """Pure physical-shaped fixture; every original and OS observation MODELED.

    Returns operation/campaign/review/permit/prepared/owned_run/observation plus
    original_baseline kwargs, phase_binding, runtime, policy and timing. This
    helper is not suitable for asserting actual NTFS or process qualification.
    """
    global _BASE
    if _BASE is None:
        _BASE = review_fixture(prerequisites, incapable=False)
    phase, runtime, policy = _BASE.phase, _BASE.runtime, _BASE.args["policy"]
    operation = m.usb_presence_operation(
        phase_binding=phase,
        runtime=runtime,
        policy=policy,
        operation_id=operation_id,
        launch_session_id=launch_session_id,
        request_nonce="a" * 64,
    )
    review_time = (
        phase.to_dict()["not_before_utc_ns"] + 1
        if reviewed_at_ns is None
        else reviewed_at_ns
    )
    review = review_usb_presence_runtime(
        runtime,
        phase_binding=phase,
        policy=policy,
        operation_sha256=operation.sha256,
        operator_id="MODELED-inspector",
        reviewer_id="MODELED-reviewer",
        launch_session_id=launch_session_id,
        reviewed_at_ns=review_time,
    )
    campaign = m.PhysicalUsbPresenceCampaign(operation, review=review)
    context = phase.to_dict()["binding"]
    old = asdict(admission())
    old.update(
        cell_id=context["cell_id"],
        session_id=context["session_id"],
        selected_identity_sha256=phase.sha256,
        stage=campaign.registration().stage,
    )
    snapshot = UsbPresenceAdmissionSnapshot(
        **old,
        usb_presence_policy_sha256=policy.sha256,
        phase_binding_sha256=phase.sha256,
        runtime_review_sha256=review.sha256,
    )
    issued = time.monotonic_ns()
    permit = ExactOperationPermit(
        "attempt-" + "8" * 32,
        RegisteredActionRequest(
            context["cell_id"],
            context["session_id"],
            campaign.registration().action_id,
            "MODELED-original-request",
            snapshot.challenge_sha256,
        ),
        snapshot,
        campaign.registration(),
        issued,
        issued + 30_000_000_000,
        "9" * 64,
    )
    prepared = campaign.preparation_for_permit(permit)
    deadline = issued + 25_000_000_000
    request = prepared.request
    native_start = review_time + 1_000_000 if started_utc_ns is None else started_utc_ns

    def moment(ms):
        return dict(monotonic_ms=ms, utc_ns=native_start + ms * 1_000_000)

    ids = [] if outcome == "ABSENT" else [request.to_dict()["target_instance_id"]]
    observation = dict(
        schema=wire.OBSERVATION_SCHEMA,
        request=request.to_dict(),
        request_sha256=request.sha256,
        # This is an explicit model of the physical wire, not a relabeled
        # incapable execution. No claim is made that this API actually ran.
        provider="WINDOWS_CONFIGURATION_MANAGER",
        filter=wire.physical_device_filter(request.to_dict()["target_instance_id"]),
        scope="PRESENT_PHYSICAL_USB_DEVICE_INSTANCES",
        outcome=outcome,
        error=None if outcome != "HELD" else "SIZE_API_FAILED",
        started=moment(10),
        finished=moment(30),
        samples=(
            [
                dict(
                    started=moment(11 + i * 5),
                    finished=moment(14 + i * 5),
                    required_chars=8192,
                    used_chars=sum(len(x) + 1 for x in ids) + 1,
                    api_calls=2,
                    native_code=0,
                    complete=True,
                    target_present=bool(ids),
                    error=None,
                    instance_ids=list(ids),
                )
                for i in range(2)
            ]
            if outcome != "HELD"
            else [
                dict(
                    started=moment(11),
                    finished=moment(12),
                    required_chars=0,
                    used_chars=0,
                    api_calls=1,
                    native_code=13,
                    complete=False,
                    target_present=None,
                    error="SIZE_API_FAILED",
                    instance_ids=[],
                )
            ]
        ),
        api_calls=1 if outcome == "HELD" else 4,
        device_handle_opens=0,
        configuration_writes=0,
        frames=0,
        physical_authority=False,
    )
    observed = wire.UsbPresenceObservation(wire.canonical(observation))
    ready = dict(
        schema=wire.READY_SCHEMA,
        request_sha256=request.sha256,
        permit_sha256=permit.permit_sha256,
        child_pid=31415,
        challenge="e" * 64,
    )
    ready_raw = wire.canonical(ready) + b"\n"
    release = wire.encode_usb_presence_release(ready, request, child_pid=31415) + b"\n"
    result = (
        wire.canonical(
            dict(
                schema=wire.RESULT_SCHEMA,
                request_sha256=request.sha256,
                child_pid=31415,
                challenge_sha256=wire.digest(ready["challenge"].encode("ascii")),
                permit_sha256=permit.permit_sha256,
                observation=observation,
            )
        )
        + b"\n"
    )
    start = issued + 1_000_000
    cleanup_start = start + 250_000_000
    raw = dict(
        schema=evidence.SCHEMA,
        preparation=prepared.to_dict(),
        preparation_sha256=prepared.sha256,
        provenance="PHYSICAL_USB_PRESENCE",
        original_deadline_ns=deadline,
        run_deadline_ns=start + 13_000_000_000,
        cleanup_started_ns=cleanup_start,
        cleanup_deadline_ns=cleanup_start + 2_000_000_000,
        cleanup_finished_ns=cleanup_start + 1_000_000,
        started_monotonic_ns=start,
        finished_monotonic_ns=cleanup_start + 2_000_000,
        started_utc_ns=native_start,
        finished_utc_ns=native_start + 300_000_000,
        scope_checks=[
            dict(
                boundary=b,
                started_ns=start + (i + 1) * 40_000_000,
                finished_ns=start + (i + 1) * 40_000_000 + 1,
                passed=True,
            )
            for i, b in enumerate(evidence.BOUNDARIES)
        ],
        owner_constructed=True,
        process=dict(
            evidence.PROCESS_DEFAULTS,
            created=True,
            resumed=True,
            tree_exited=True,
            returncode=1 if outcome == "HELD" else 0,
            pid=31415,
            written=len(request.payload) + 1 + len(release),
            peak_handles=14,
            peak_processes=1,
            stdout_eof=True,
            stderr_eof=True,
        ),
        stdout=evidence.stream_record(ready_raw + result, complete=True),
        stderr=evidence.stream_record(b"", complete=True),
        ready_length=len(ready_raw),
        ready_wire=evidence.stream_record(ready_raw, complete=True),
        release_wire=evidence.stream_record(release, complete=True),
        release_write_attempted=True,
        release_check_passed=True,
        release_delivery_confirmed=True,
        result_validated=False,
        primary_error=None,
        cleanup_errors=[],
        status="FAILED",
        physical_authority=False,
        hardware_qualified=False,
        retries=0,
    )
    owned_run = evidence.retain_owned_usb_presence_run(raw)
    cancellation = Event()
    tx = ModeledScopeTransaction(permit)
    scope = ConsumedCommissioningScope(
        permit,
        transaction=tx,
        deadline_ns=deadline,
        cancellation=cancellation,
        monotonic_ns=time.monotonic_ns,
    )
    return SimpleNamespace(
        original_baseline=_BASE.original,
        phase_binding=phase,
        runtime=runtime,
        policy=policy,
        operation=operation,
        review=review,
        campaign=campaign,
        permit=permit,
        prepared=prepared,
        request=request,
        observation=observed,
        owned_run=owned_run,
        cancellation=cancellation,
        deadline_ns=deadline,
        transaction=tx,
        scope=scope,
    )


@pytest.fixture
def case(prerequisites):
    return modeled_presence_campaign(prerequisites)


@pytest.fixture(autouse=True)
def no_process_or_devices(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Campaign unit test must not execute any process/device/host API")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(os, "system", denied)
    monkeypatch.setattr(runner, "_new_owner", denied)


def execute_model(case, monkeypatch, report=None):
    retained = case.owned_run if report is None else report

    class ModeledRunner:
        def __init__(self, prepared, *, permit, authorization, application_guard):
            assert prepared.payload == case.prepared.payload
            assert permit is case.permit and authorization is case.scope
            self.scope, self.guard = authorization, application_guard

        def run(self, *, cancellation, deadline_ns):
            assert cancellation is case.cancellation and deadline_ns == case.deadline_ns
            assert self.guard() is None
            self.scope.acknowledge(case.permit)
            for _ in range(5):
                self.scope.revalidate(case.permit)
            return retained

    monkeypatch.setattr(runner, "OwnedUsbPresenceRunner", ModeledRunner)
    case.campaign._bind_application_guard(lambda: None)
    return case.campaign.run_scoped_campaign(
        case.permit,
        deadline_ns=case.deadline_ns,
        cancellation=case.cancellation,
        authorization=case.scope,
    )


def test_operation_review_preparation_are_pure_inert_and_exact(case, monkeypatch):
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("constructor file read")
    )
    restored = m.PhysicalUsbPresenceCampaign(
        m.UsbPresenceOperation(case.operation.payload), review=case.review
    )
    prepared = restored.preparation_for_permit(case.permit)
    assert prepared.payload == case.prepared.payload
    assert (
        prepared.request.to_dict()["request_nonce"]
        == case.operation.to_dict()["request_nonce"]
    )
    assert prepared.phase_binding.sha256 == restored.phase_binding.sha256
    assert restored.registration().budget.maximum_reads == 4
    assert (
        restored.registration().budget.maximum_opens
        == restored.registration().budget.maximum_closes
        == 0
    )
    assert restored.retained_evidence is None and case.transaction.acks == 0
    d = case.operation.to_dict()
    assert "review" not in d and "permit" not in d
    assert (
        d["operation_id"].startswith("usbphase-")
        and d["launch_session_id"] == case.review.to_dict()["launch_session_id"]
    )


@pytest.mark.parametrize("outcome", ["PRESENT", "ABSENT", "HELD"])
def test_complete_modeled_observation_maps_known_effect_not_qualification(
    prerequisites, monkeypatch, outcome
):
    case = modeled_presence_campaign(prerequisites, outcome=outcome)
    result = execute_model(case, monkeypatch)
    assert type(result) is RetainedCampaignExecution
    receipt = result.receipt
    assert (
        receipt.effect_certainty is EffectCertainty.CONFIRMED
        and receipt.cleanup_confirmed
    )
    assert receipt.reads == (1 if outcome == "HELD" else 4)
    assert receipt.opens == receipt.writes == receipt.frames == receipt.closes == 0
    assert receipt.final_power_state is ObservedPowerState.UNKNOWN
    assert receipt.selected_identity_sha256 == case.phase_binding.sha256
    assert receipt.evidence_sha256s == (case.owned_run.sha256,)
    assert receipt.output_bytes == len(case.owned_run.payload)
    assert result.evidence[0].payload == case.owned_run.payload
    assert result.evidence[0].label == m.ARTIFACT_LABEL
    assert case.transaction.acks == 1 and case.transaction.checks == 5
    assert case.campaign.retained_evidence.payload == case.owned_run.payload
    with pytest.raises(ValueError, match="ALREADY_USED"):
        case.campaign.run_scoped_campaign(
            case.permit,
            deadline_ns=case.deadline_ns,
            cancellation=case.cancellation,
            authorization=case.scope,
        )


@pytest.mark.parametrize("fault", ["unknown", "cleanup", "source-drift", "cancelled"])
def test_failed_owned_run_retains_original_counts_or_honest_unknown(
    case, monkeypatch, fault
):
    d = case.owned_run.to_dict()
    if fault == "unknown":
        d["stdout"] = evidence.stream_record(
            evidence.stream_bytes(d["ready_wire"], 1024) + b"PARTIAL_NATIVE",
            complete=False,
        )
        d["primary_error"] = "MALFORMED_NATIVE_RESULT"
    elif fault == "cleanup":
        d["cleanup_errors"] = ["CLOSE_FAILED"]
        d["process"]["pins_remaining"] = 1
    else:
        d["primary_error"] = (
            "CANCELLED"
            if fault == "cancelled"
            else "CURRENT_USB_WORKSPACE_SOURCE_CHANGED"
        )
        d["scope_checks"][-1]["passed"] = False
    report = evidence.retain_owned_usb_presence_run(d)
    result = execute_model(case, monkeypatch, report)
    assert (
        result.evidence[0].payload
        == report.payload
        == case.campaign.retained_evidence.payload
    )
    if fault == "unknown":
        assert type(result) is RetainedUncertainCampaignExecution
        assert report.actual_counts is None
        assert result.reason_codes == ("PRESENCE_ACCOUNTING_UNAVAILABLE",)
    else:
        assert type(result) is RetainedCampaignExecution
        assert result.receipt.effect_certainty is EffectCertainty.UNCERTAIN
        assert not result.receipt.cleanup_confirmed and result.receipt.reads == 4


@pytest.mark.parametrize("fault", ["stop", "source"])
def test_real_frozen_runner_refuses_without_owner_or_double_ack(
    case, monkeypatch, fault
):
    if fault == "stop":
        case.cancellation.set()
    monkeypatch.setattr(runner, "source_fingerprint", lambda _: "f" * 64)
    case.campaign._bind_application_guard(lambda: None)
    result = case.campaign.run_scoped_campaign(
        case.permit,
        deadline_ns=case.deadline_ns,
        cancellation=case.cancellation,
        authorization=case.scope,
    )
    assert result.receipt.effect_certainty is EffectCertainty.UNCERTAIN
    assert result.receipt.reads == result.receipt.opens == 0
    assert case.campaign.retained_evidence.no_attempt
    assert case.transaction.acks == (0 if fault == "stop" else 1)


@pytest.mark.parametrize(
    "field,value",
    [
        ("operation_id", "usbphase-bad"),
        ("request_nonce", "x" * 64),
        ("launch_session_id", "different launch"),
        ("cell_id", "other"),
        ("session_id", "other"),
        ("header_sha256", "f" * 64),
        ("trial_id", "other"),
        ("source_sha256", "f" * 64),
        ("workspace", "C:\\wrong"),
        ("policy_sha256", "f" * 64),
        ("physical_authority", 0),
        ("hardware_qualified", True),
        ("schema", "rocell.physical_usb_identity_operation.v1"),
    ],
)
def test_operation_closed_original_context(case, field, value):
    d = case.operation.to_dict()
    d[field] = value
    with pytest.raises(ValueError):
        m.UsbPresenceOperation(wire.canonical(d))


@pytest.mark.parametrize(
    "field", ["operation_id", "launch_session_id", "request_nonce"]
)
def test_new_operation_identity_requires_its_exact_original_review(case, field):
    d = case.operation.to_dict()
    d[field] = {
        "operation_id": "usbphase-" + "c" * 32,
        "launch_session_id": "new-launch",
        "request_nonce": "b" * 64,
    }[field]
    with pytest.raises(ValueError):
        m.PhysicalUsbPresenceCampaign(
            m.UsbPresenceOperation(wire.canonical(d)), review=case.review
        )


@pytest.mark.parametrize(
    "fault", ["operation", "helper", "review", "phase", "domain", "challenge"]
)
def test_permit_cannot_swap_reviewed_operation_or_original_subject(case, fault):
    p = case.permit
    if fault in {"operation", "helper"}:
        field = (
            "operation_sha256" if fault == "operation" else "worker_executable_sha256"
        )
        p = replace(p, registration=replace(p.registration, **{field: "f" * 64}))
    elif fault == "challenge":
        p = replace(p, request=replace(p.request, expected_challenge_sha256="f" * 64))
    elif fault == "domain":
        p = replace(p, admission=admission())
    else:
        field = "runtime_review_sha256" if fault == "review" else "phase_binding_sha256"
        changes = {field: "f" * 64}
        if fault == "phase":
            changes["selected_identity_sha256"] = "f" * 64
        p = replace(p, admission=replace(p.admission, **changes))
    with pytest.raises(ValueError):
        case.campaign.preparation_for_permit(p)
    assert case.transaction.acks == 0


def test_unscoped_and_unreviewed_entrypoints_never_dispatch(case):
    with pytest.raises(ValueError, match="SCOPED_PRESENCE"):
        case.campaign.run_campaign()
    with pytest.raises(ValueError, match="SCOPED_PRESENCE"):
        case.campaign.run_retained_campaign()
    case.campaign._bind_application_guard(lambda: None)
    with pytest.raises(ValueError, match="GUARD_REQUIRED_ONCE"):
        case.campaign._bind_application_guard(lambda: None)


def test_independent_full_evidence_readback_does_not_reexecute_or_extend_time(
    case, monkeypatch
):
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("readback opens file")
    )
    checked = m.verify_usb_presence_campaign_evidence(
        case.owned_run,
        campaign=case.campaign,
        permit=case.permit,
        expected_evidence_sha256=case.owned_run.sha256,
    )
    assert checked.payload == case.owned_run.payload and case.transaction.acks == 0
    with pytest.raises(ValueError):
        m.verify_usb_presence_campaign_evidence(
            case.owned_run,
            campaign=case.campaign,
            permit=case.permit,
            expected_evidence_sha256="f" * 64,
        )
    altered = replace(case.permit, nonce="b" * 64)
    with pytest.raises(ValueError):
        m.verify_usb_presence_campaign_evidence(
            case.owned_run,
            campaign=case.campaign,
            permit=altered,
            expected_evidence_sha256=case.owned_run.sha256,
        )


def test_reconstructed_campaign_cannot_reuse_an_acknowledged_original_scope(
    case, monkeypatch
):
    execute_model(case, monkeypatch)
    # Restore the real frozen runner, whose original scope still remembers its
    # one acknowledgement. No new wrapper can turn that scope into a retry.
    monkeypatch.setattr(runner, "OwnedUsbPresenceRunner", _FROZEN_PHYSICAL_RUNNER)
    monkeypatch.setattr(runner, "_new_owner", lambda: pytest.fail("replayed process"))
    monkeypatch.setattr(
        runner,
        "source_fingerprint",
        lambda _: case.operation.to_dict()["source_sha256"],
    )
    rebuilt = m.PhysicalUsbPresenceCampaign(case.operation, review=case.review)
    rebuilt._bind_application_guard(lambda: None)
    result = rebuilt.run_scoped_campaign(
        case.permit,
        deadline_ns=case.deadline_ns,
        cancellation=case.cancellation,
        authorization=case.scope,
    )
    assert case.transaction.acks == 1 and case.transaction.checks == 5
    assert rebuilt.retained_evidence.no_attempt
    assert result.receipt.effect_certainty is EffectCertainty.UNCERTAIN
    assert result.receipt.reads == 0


@pytest.mark.parametrize(
    "fault",
    ["deadline-expiry", "deadline-issued", "deadline-duration", "launch-review"],
)
def test_independent_campaign_verifier_preserves_original_time_and_launch(case, fault):
    if fault == "launch-review":
        reviewed = case.review.to_dict()
        reviewed["launch_session_id"] = "another-launch"
        with pytest.raises(ValueError, match="CURRENT_LAUNCH"):
            m.PhysicalUsbPresenceCampaign(
                case.operation, review=type(case.review)(wire.canonical(reviewed))
            )
        return
    d = case.owned_run.to_dict()
    d["original_deadline_ns"] = {
        "deadline-expiry": case.permit.expires_at_ns + 1,
        "deadline-issued": case.permit.issued_at_ns,
        "deadline-duration": d["started_monotonic_ns"] + 25_000_000_001,
    }[fault]
    with pytest.raises(ValueError):
        m.verify_usb_presence_campaign_evidence(
            evidence.OwnedUsbPresenceRunEvidence(wire.canonical(d)),
            campaign=case.campaign,
            permit=case.permit,
            expected_evidence_sha256=wire.digest(wire.canonical(d)),
        )
