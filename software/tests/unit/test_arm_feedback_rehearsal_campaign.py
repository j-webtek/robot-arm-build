"""Coordinator integration with real ArmFeedbackWorker and memory-only serial."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from threading import Event
from typing import Any

import pytest

from rocell.application import arm_feedback_rehearsal_campaign as campaign
from rocell.application import cell_commissioning_coordinator as core
from rocell.application.commissioning_m1_persistence import rehearsal_source_binding
from rocell.application.physical_connection_contracts import (
    EvidenceOrigin,
    RoArmUsbSerialIdentity,
    UsbDriverIdentity,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.providers.windows import arm_feedback_worker as arm
from test_commissioning_coordinator import InMemoryProtocolStore, _components


class Clock:
    value = 1_000_000_000

    def __call__(self):
        self.value += 1
        return self.value

    def wait(self, event, seconds):
        self.value += int(seconds * 1_000_000_000)
        return event.is_set()


def controller():
    return arm.ReviewedControllerBinding(
        RoArmUsbSerialIdentity(
            "1234",
            "5678",
            "INCPABLEARM001",
            "USB\\VID_1234&PID_5678\\INCPABLEARM001",
            "usb-unit:1234:5678:INCPABLEARM001",
            "COM42",
            UsbDriverIdentity(
                "SYNTHETIC", "memory-only", "UNMEASURED", "not-installed.inf"
            ),
        ),
        "1" * 64,
        "2" * 64,
        "3" * 64,
        "4" * 64,
        "5" * 64,
        EvidenceOrigin.SYNTHETIC_REHEARSAL,
    )


class RetainingMemoryStore(InMemoryProtocolStore):
    def __init__(self, snapshot):
        super().__init__(snapshot)
        self.authorized: set[str] = set()
        self.evidence: dict[str, tuple[core.CampaignEvidence, ...]] = {}
        self.permits: dict[str, core.ExactOperationPermit] = {}

    def begin_intent(self, binding, permit):
        super().begin_intent(binding, permit)
        self.permits[permit.attempt_id] = permit

    def assert_consumed_permit(self, permit):
        assert self.held_leases
        assert self.permits[permit.attempt_id] == permit
        assert self.attempts[permit.attempt_id] is AttemptState.EFFECT_ARMED
        assert permit.attempt_id not in self.authorized
        self.authorized.add(permit.attempt_id)
        self.trace.append("EXACT_ARMED_AUTHORIZATION")
        if self.fail == "AUTHORIZE":
            raise OSError("injected consumed-permit verification failure")

    def retain_campaign_evidence(self, permit, evidence):
        assert (
            self.held_leases
            and self.attempts[permit.attempt_id] is AttemptState.EFFECT_ARMED
        )
        assert permit.attempt_id in self.authorized
        core.validate_campaign_evidence(evidence)
        self.trace.append("FULL_EVIDENCE_RETAINED")
        if self.fail == "FULL_EVIDENCE_RETAINED":
            raise OSError("injected full evidence retention failure")
        assert permit.attempt_id not in self.evidence
        self.evidence[permit.attempt_id] = evidence


def components(scenario="nominal", final_state=core.ObservedPowerState.DEENERGIZED):
    _, old_store, _, _, _ = _components(serial=True)
    clock = Clock()
    plan = campaign.ArmFeedbackRehearsalPlan(
        "9" * 64,
        "8" * 64,
        controller(),
        "7" * 64,
        scenario,
        (
            None
            if final_state is None
            else campaign.SyntheticFinalPowerObservationSpec("observer-2", final_state)
        ),
    )
    worker = campaign.ArmFeedbackRehearsalCampaign(
        plan, worker_executable_sha256="b" * 64, monotonic_ns=clock, wait=clock.wait
    )
    registration = worker.registration()
    snapshot = replace(
        old_store.snapshot,
        stage=PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION,
        source_binding_sha256=rehearsal_source_binding(plan.source_sha256),
        selected_identity_sha256=plan.controller.identity.identity_sha256,
    )
    store = RetainingMemoryStore(snapshot)
    store.envelope = replace(
        old_store.envelope,
        operation_sha256=registration.operation_sha256,
        issued_at_ns=clock.value,
        expires_at_ns=clock.value + core.MAX_PERMIT_TTL_NS,
    )
    coordinator = core.CellCommissioningCoordinator(
        persistence=store,
        registrations=(registration,),
        workers={registration.worker_id: worker},
        retained_campaign_actions=(registration.action_id,),
        monotonic_ns=clock,
    )
    request = core.RegisteredActionRequest(
        snapshot.cell_id,
        snapshot.session_id,
        registration.action_id,
        "request-1",
        snapshot.challenge_sha256,
    )
    return coordinator, store, worker, clock, request


def test_actual_worker_known_result_retains_complete_bytes_before_seal():
    coordinator, store, worker, _, request = components()
    permit = coordinator.prepare(request)
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN, result.reason_codes
    assert worker.evidence is not None
    assert store.trace.index("EFFECT_ARMED") < store.trace.index(
        "EXACT_ARMED_AUTHORIZATION"
    )
    assert store.trace.index("EXACT_ARMED_AUTHORIZATION") < store.trace.index(
        "FULL_EVIDENCE_RETAINED"
    )
    assert store.trace.index("FULL_EVIDENCE_RETAINED") < store.trace.index(
        "EFFECT_OBSERVED"
    )
    assert store.trace.index("RESULT_RETAINED") < store.trace.index("SEALED_KNOWN")
    assert result.receipt.opens == result.receipt.writes == result.receipt.closes == 1
    assert result.receipt.evidence_sha256s == (worker.evidence.evidence_sha256,)
    assert (
        store.evidence[permit.attempt_id][0].payload
        == worker.evidence.canonical_bytes()
    )
    assert result.receipt.output_bytes == len(worker.evidence.canonical_bytes())
    assert (
        worker.evidence.safe_summary()["final_power_state"]
        == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    )
    observed = worker.evidence.final_power_observation
    assert observed["observed_power_state"] == "DEENERGIZED"
    assert observed["serial_close_used_to_infer_power"] is False
    assert observed["physical_observation"] is False
    assert coordinator.execute(permit) is result
    assert store.trace.count("EXACT_ARMED_AUTHORIZATION") == 1


@pytest.mark.parametrize(
    "scenario",
    [
        "boot-bytes",
        "short-write",
        "timeout",
        "identity-change",
        "close-failure",
        "malformed-response",
        "wrong-response",
        "extra-response",
    ],
)
def test_faults_have_private_evidence_and_quarantine_not_expected_fault_stage_pass(
    scenario,
):
    coordinator, store, worker, _, request = components(scenario)
    permit = coordinator.prepare(request)
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN, result
    assert result.quarantine_latched
    assert worker.evidence is not None, result.reason_codes
    assert permit.attempt_id in store.evidence
    assert "SEALED_KNOWN" not in store.trace
    assert worker.evidence.safe_summary()["technical_response_valid"] is (
        scenario == "close-failure"
    )
    assert (
        worker.evidence.final_power_observation["observed_power_state"] == "DEENERGIZED"
    )
    assert coordinator.execute(permit) is result
    assert store.trace.count("EXACT_ARMED_AUTHORIZATION") == 1


@pytest.mark.parametrize(
    "state", [None, core.ObservedPowerState.UNKNOWN, core.ObservedPowerState.ENERGIZED]
)
def test_serial_success_cannot_supply_independent_final_deenergization(state):
    coordinator, store, worker, _, request = components(final_state=state)
    permit = coordinator.prepare(request)
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert "FINAL_DEENERGIZATION_UNCONFIRMED" in result.reason_codes
    assert worker.evidence.safe_summary()["technical_response_valid"] is True
    assert worker.evidence.safe_summary()["serial_cleanup_confirmed"] is True
    if state is None:
        assert worker.evidence.final_power_observation is None
    else:
        assert (
            worker.evidence.final_power_observation["observed_power_state"]
            == state.value
        )
    assert permit.attempt_id in store.evidence


def test_construction_and_status_are_device_and_file_inert(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected I/O or worker construction")

    with monkeypatch.context() as patch:
        patch.setattr(campaign, "ArmFeedbackWorker", forbidden)
        patch.setattr(campaign, "IncapableSerialBackend", forbidden)
        for name in ("open", "read_bytes", "stat", "lstat", "iterdir"):
            patch.setattr(Path, name, forbidden)
        _, store, worker, _, _ = components()
        assert worker.status()["consumed"] is False
        assert store.trace == []


def test_no_unretained_path_can_run_adapter():
    coordinator, store, worker, clock, request = components()
    permit = coordinator.prepare(request)
    with pytest.raises(campaign.ArmFeedbackRehearsalError, match="retention path"):
        worker.run_campaign(
            permit, deadline_ns=clock.value + 10_000_000_000, cancellation=Event()
        )
    assert not worker.status()["consumed"]
    assert not store.attempts


@pytest.mark.parametrize("fault", ["FULL_EVIDENCE_RETAINED", "AUTHORIZE"])
def test_retention_or_consumption_proof_failure_never_known(fault):
    coordinator, store, worker, _, request = components()
    permit = coordinator.prepare(request)
    store.fail = fault
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert result.quarantine_latched
    assert "SEALED_KNOWN" not in store.trace
    assert coordinator.execute(permit) is result


@pytest.mark.parametrize(
    "field,value",
    [
        ("stage_revision", 2),
        ("selected_identity_sha256", "a" * 64),
        ("source_binding_sha256", "c" * 64),
        ("journal_head_sha256", "a" * 64),
    ],
)
def test_stale_admission_never_dispatches(field, value):
    coordinator, store, worker, _, request = components()
    permit = coordinator.prepare(request)
    store.snapshot = replace(store.snapshot, **{field: value})
    with pytest.raises(core.CommissioningCoordinatorError):
        coordinator.execute(permit)
    assert not store.attempts
    assert worker.status()["consumed"] is False


def test_cancel_before_arm_has_no_worker_or_evidence():
    coordinator, store, worker, _, request = components()
    permit = coordinator.prepare(request)
    cancel = Event()
    cancel.set()
    result = coordinator.execute(permit, cancellation=cancel)
    assert result.state is AttemptState.ABORTED_PRE_EFFECT
    assert worker.evidence is None and not store.evidence
    assert worker.status()["consumed"] is False


def test_cancel_during_worker_retains_failure_and_quarantines():
    coordinator, store, worker, clock, request = components()
    cancel = Event()

    def wait(event, seconds):
        clock.value += int(seconds * 1_000_000_000)
        event.set()
        return True

    worker._wait = wait
    permit = coordinator.prepare(request)
    result = coordinator.execute(permit, cancellation=cancel)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert worker.evidence is not None and permit.attempt_id in store.evidence
    assert worker.evidence.result.primary_error.code == "CANCELLED"


def test_deadline_after_full_retention_never_known():
    coordinator, store, worker, clock, request = components()
    original = store.retain_campaign_evidence

    def delayed(permit, evidence):
        original(permit, evidence)
        clock.value += 20_000_000_000

    store.retain_campaign_evidence = delayed
    result = coordinator.execute(coordinator.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert "WORKER_DEADLINE_EXCEEDED" in result.reason_codes
    assert "SEALED_KNOWN" not in store.trace


def test_callback_is_one_use_and_cannot_be_saved_for_later():
    coordinator, store, worker, _, request = components()
    original = worker.run_retained_campaign
    retained_callback = []

    def save(permit, **kwargs):
        retained_callback.append(kwargs["authorize_consumed_permit"])
        return original(permit, **kwargs)

    worker.run_retained_campaign = save
    permit = coordinator.prepare(request)
    coordinator.execute(permit)
    with pytest.raises(core.CommissioningCoordinatorError, match="scope-bound"):
        retained_callback[0](permit)
    assert store.trace.count("EXACT_ARMED_AUTHORIZATION") == 1


@pytest.mark.parametrize(
    "fault", ["missing", "empty", "hash", "bytes", "authorization"]
)
def test_core_rejects_missing_or_mismatched_retention_contract(fault):
    coordinator, store, worker, _, request = components()
    original = worker.run_retained_campaign

    def wrong(permit, **kwargs):
        if fault == "authorization":
            kwargs["authorize_consumed_permit"] = lambda exact: None
        execution = original(permit, **kwargs)
        if fault == "missing":
            return execution.receipt
        if fault == "empty":
            return core.RetainedCampaignExecution(execution.receipt, ())
        if fault == "hash":
            return replace(
                execution,
                receipt=replace(execution.receipt, evidence_sha256s=("d" * 64,)),
            )
        if fault == "bytes":
            return replace(
                execution, receipt=replace(execution.receipt, output_bytes=0)
            )
        return execution

    worker.run_retained_campaign = wrong
    result = coordinator.execute(coordinator.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert "SEALED_KNOWN" not in store.trace


def test_retained_verification_rebuilds_no_worker_or_os_action(monkeypatch):
    coordinator, _, worker, _, request = components()
    permit = coordinator.prepare(request)
    coordinator.execute(permit)
    evidence = worker.evidence

    def forbidden(*args, **kwargs):
        raise AssertionError("retained verification replayed I/O")

    with monkeypatch.context() as patch:
        patch.setattr(campaign, "ArmFeedbackWorker", forbidden)
        patch.setattr(campaign, "IncapableSerialBackend", forbidden)
        for name in ("open", "read_bytes", "stat", "lstat", "iterdir"):
            patch.setattr(Path, name, forbidden)
        restored = campaign.verify_retained_arm_feedback_campaign(
            evidence.canonical_bytes(),
            expected_plan=worker.plan,
            expected_permit=permit,
            expected_evidence_sha256=evidence.evidence_sha256,
        )
        assert restored.result == evidence.result
        assert restored.request == worker.request
        assert restored.final_power_observation == evidence.final_power_observation


@pytest.mark.parametrize(
    "mutation",
    [
        "source",
        "permit",
        "request",
        "context",
        "observer",
        "post_time",
        "serial_inference",
        "worker_hash",
        "actual_effects",
        "extra",
        "physical",
    ],
)
def test_retained_wrapper_tamper_rejected_even_with_rehashed_outer_bytes(mutation):
    coordinator, _, worker, _, request = components()
    permit = coordinator.prepare(request)
    coordinator.execute(permit)
    doc = worker.evidence.to_dict()
    if mutation == "source":
        doc["plan"]["source_sha256"] = "c" * 64
    elif mutation == "permit":
        doc["context"]["permit_sha256"] = "c" * 64
    elif mutation == "request":
        doc["request"]["operation_sha256"] = "c" * 64
    elif mutation == "context":
        doc["context"]["binding_sha256"] = "c" * 64
    elif mutation == "observer":
        doc["final_power_observation"]["observer_id"] = "operator-1"
    elif mutation == "post_time":
        doc["final_power_observation"]["observed_monotonic_ns"] = 1
    elif mutation == "serial_inference":
        doc["final_power_observation"]["serial_close_used_to_infer_power"] = True
    elif mutation == "worker_hash":
        doc["worker_executable_sha256"] = "c" * 64
    elif mutation == "actual_effects":
        doc["actual_effect_counts"]["device_opens"] = False
    elif mutation == "extra":
        doc["unexpected"] = True
    elif mutation == "physical":
        doc["physical_authority"] = True
    payload = json.dumps(
        doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    with pytest.raises(ValueError):
        campaign.verify_retained_arm_feedback_campaign(
            payload,
            expected_plan=worker.plan,
            expected_permit=permit,
            expected_evidence_sha256=hashlib.sha256(payload).hexdigest(),
        )


def test_plan_cannot_admit_physical_controller_or_arbitrary_scenario():
    _, _, worker, _, _ = components()
    with pytest.raises(ValueError):
        replace(worker.plan, scenario="raw-command")
    with pytest.raises(ValueError):
        replace(
            worker.plan,
            controller=replace(
                controller(), origin=EvidenceOrigin.PHYSICAL_OBSERVATION
            ),
        )


def test_post_observer_must_match_distinct_envelope_identity():
    coordinator, store, worker, _, request = components()
    worker.plan = replace(
        worker.plan,
        final_power_observation=campaign.SyntheticFinalPowerObservationSpec(
            "operator-1", core.ObservedPowerState.DEENERGIZED
        ),
    )
    with pytest.raises(ValueError):
        campaign._validate_permit(
            worker.plan, coordinator.prepare(request), worker.worker_executable_sha256
        )
