"""Actual owned child + scoped coordinator; this store models protocol, not disk durability."""

from dataclasses import replace
import hashlib
from pathlib import Path
from threading import Event
import time

import pytest

from rocell.application import owned_arm_feedback_rehearsal_campaign as campaign
from rocell.application import cell_commissioning_coordinator as core
from rocell.application.arm_feedback_rehearsal_campaign import (
    ArmFeedbackRehearsalPlan,
    SyntheticFinalPowerObservationSpec,
)
from rocell.application.commissioning_m1_persistence import rehearsal_source_binding
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.owned_arm_feedback_package import (
    prepare_owned_arm_runtime,
)
from rocell.providers.windows.incapable_controller_metadata import (
    synthetic_native_identity,
)
from test_arm_feedback_rehearsal_campaign import RetainingMemoryStore, controller
from test_commissioning_coordinator import _components

WORKSPACE = Path(__file__).parents[3]


class ScopedStore(RetainingMemoryStore):
    def revalidate_consumed_permit(self, permit):
        assert self.held_leases
        assert permit.attempt_id in self.authorized
        assert self.permits[permit.attempt_id] == permit
        assert self.attempts[permit.attempt_id] is AttemptState.EFFECT_ARMED
        self.trace.append("CURRENT_CONSUMED_PERMIT_RECHECK")
        if self.fail == "REVALIDATE":
            raise OSError("consumed scope injected refusal")


def components(
    tmp_path, scenario="nominal", final_state=core.ObservedPowerState.DEENERGIZED
):
    _, old, _, _, _ = _components(serial=True)
    runtime = prepare_owned_arm_runtime(WORKSPACE, tmp_path / "packages")
    generic = controller()
    modeled = replace(generic, identity=synthetic_native_identity(generic))
    plan = ArmFeedbackRehearsalPlan(
        "9" * 64,
        runtime.to_dict()["workspace_source_sha256"],
        modeled,
        "7" * 64,
        final_power_observation=(
            None
            if final_state is None
            else SyntheticFinalPowerObservationSpec("observer-2", final_state)
        ),
    )
    directory = tmp_path / "owned-arm-feedback"
    directory.mkdir()
    worker = campaign.OwnedArmFeedbackRehearsalCampaign(
        plan, runtime=runtime, directory=directory, scenario=scenario
    )
    reg = worker.registration()
    snapshot = replace(
        old.snapshot,
        source_binding_sha256=rehearsal_source_binding(plan.source_sha256),
        selected_identity_sha256=plan.controller.identity.identity_sha256,
    )
    store = ScopedStore(snapshot)
    now = time.monotonic_ns()
    store.envelope = replace(
        old.envelope,
        operation_sha256=reg.operation_sha256,
        issued_at_ns=now,
        expires_at_ns=now + core.MAX_PERMIT_TTL_NS,
    )
    coordinator = core.CellCommissioningCoordinator(
        persistence=store,
        registrations=(reg,),
        workers={reg.worker_id: worker},
        retained_campaign_actions=(reg.action_id,),
        scoped_campaign_actions=(reg.action_id,),
    )
    request = core.RegisteredActionRequest(
        snapshot.cell_id,
        snapshot.session_id,
        reg.action_id,
        "request-owned",
        snapshot.challenge_sha256,
    )
    return coordinator, store, worker, request


def execute(
    tmp_path, scenario="nominal", final_state=core.ObservedPowerState.DEENERGIZED
):
    coordinator, store, worker, request = components(tmp_path, scenario, final_state)
    permit = coordinator.prepare(request)
    result = coordinator.execute(permit)
    return coordinator, store, worker, permit, result


def verify(worker, permit, payload=None, directory=None):
    payload = payload if payload is not None else worker.evidence.canonical_bytes()
    return campaign.verify_retained_owned_arm_feedback_campaign(
        payload,
        expected_plan=worker.plan,
        expected_permit=permit,
        expected_evidence_sha256=hashlib.sha256(payload).hexdigest(),
        expected_directory=directory or worker.directory,
    )


def test_actual_child_known_full_retention_before_seal_and_no_replay(tmp_path):
    coordinator, store, worker, permit, result = execute(tmp_path)
    assert result.state is AttemptState.SEALED_KNOWN, result.reason_codes
    assert store.trace.count("EXACT_ARMED_AUTHORIZATION") == 1
    assert store.trace.count("CURRENT_CONSUMED_PERMIT_RECHECK") == 2
    assert store.trace.index("EFFECT_ARMED") < store.trace.index(
        "CURRENT_CONSUMED_PERMIT_RECHECK"
    )
    assert store.trace.index("FULL_EVIDENCE_RETAINED") < store.trace.index(
        "SEALED_KNOWN"
    )
    evidence = verify(worker, permit)
    operation = evidence.to_dict()["operation"]
    assert operation["ipc_request_schema"] == "rocell.arm_owned_request.v3"
    assert operation["schema"] == "rocell.owned_arm_feedback_operation.v2"
    assert operation["admission_timeout_ms"] == 5000
    assert evidence.process_summary()["process"]["process_created"]
    assert all(campaign.owned_feedback_checks(evidence.process_summary()).values())
    trace = evidence.process_summary()["resolution"]
    assert trace["status"] == "PRE_WRITE_MATCHED" and trace["attempt_count"] == 2
    assert evidence.safe_summary()["technical_response_valid"] is True
    assert (
        evidence.final_power_observation["feedback_evidence_sha256"]
        == evidence.owned.feedback.evidence_sha256
    )
    assert (
        evidence.final_power_observation["owned_evidence_sha256"]
        == evidence.owned.evidence_sha256
    )
    assert (
        evidence.final_power_observation["process_cleanup_used_to_infer_power"] is False
    )
    assert (
        evidence.process_summary()["final_power_state"]
        == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    )
    assert result.receipt.opens == result.receipt.writes == result.receipt.closes == 1
    assert store.evidence[permit.attempt_id][0].payload == evidence.canonical_bytes()
    assert coordinator.execute(permit) is result
    assert store.trace.count("CURRENT_CONSUMED_PERMIT_RECHECK") == 2


@pytest.mark.parametrize(
    "scenario", ["boot-bytes", "short-write", "close-failure", "malformed-result"]
)
def test_faults_retain_full_process_evidence_and_never_known(tmp_path, scenario):
    _, store, worker, permit, result = execute(tmp_path, scenario)
    assert result.state is AttemptState.SEALED_UNCERTAIN, result
    assert result.quarantine_latched
    assert worker.evidence is not None, result.reason_codes
    assert permit.attempt_id in store.evidence
    verify(worker, permit)
    assert "SEALED_KNOWN" not in store.trace
    if scenario == "malformed-result":
        assert worker.evidence.result is None
        assert worker.evidence.safe_summary()["api_counts"] is None
        assert (
            worker.evidence.final_power_observation["feedback_evidence_sha256"] is None
        )
    else:
        assert worker.evidence.result is not None, worker.evidence.process_summary()


@pytest.mark.parametrize("state", [None, core.ObservedPowerState.UNKNOWN])
def test_actual_child_cleanup_does_not_establish_final_deenergization(tmp_path, state):
    _, store, worker, permit, result = execute(tmp_path, final_state=state)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert "FINAL_DEENERGIZATION_UNCONFIRMED" in result.reason_codes
    assert all(
        campaign.owned_feedback_checks(worker.evidence.process_summary()).values()
    ), worker.evidence.process_summary()
    assert worker.evidence.safe_summary()["technical_response_valid"] is True
    assert permit.attempt_id in store.evidence


def test_pure_reopen_does_not_rebuild_or_read_and_rejects_relabeling(
    tmp_path, monkeypatch
):
    _, _, worker, permit, result = execute(tmp_path)
    assert result.state is AttemptState.SEALED_KNOWN, result.reason_codes

    def forbidden(*args, **kwargs):
        pytest.fail("pure retained reconstruction attempted I/O")

    monkeypatch.setattr(campaign, "prepare_owned_arm_runtime", forbidden)
    monkeypatch.setattr(campaign, "IncapableOwnedArmFeedbackRunner", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    reconstructed = campaign.OwnedArmFeedbackRehearsalCampaign(
        worker.plan, runtime=worker.runtime, directory=worker.directory
    )
    assert reconstructed.status()["consumed"] is False
    assert verify(worker, permit).canonical_bytes() == worker.evidence.canonical_bytes()
    with pytest.raises(ValueError):
        verify(worker, permit, directory=tmp_path / "other" / "owned-arm-feedback")
    for field, value in (
        ("physical_authority", True),
        ("scenario", "timeout"),
        ("permit_sha256", "a" * 64),
    ):
        document = worker.evidence.to_dict()
        document[field] = value
        with pytest.raises(ValueError):
            verify(worker, permit, campaign._canonical(document))
    document = worker.evidence.to_dict()
    document["final_power_observation"]["feedback_evidence_sha256"] = document[
        "owned_evidence_sha256"
    ]
    with pytest.raises(ValueError):
        verify(worker, permit, campaign._canonical(document))


def test_scoped_revalidation_refusal_retains_available_process_failure(tmp_path):
    coordinator, store, worker, request = components(tmp_path)
    permit = coordinator.prepare(request)
    store.fail = "REVALIDATE"
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert worker.evidence is not None, result.reason_codes
    assert permit.attempt_id in store.evidence
    assert not worker.evidence.process_summary()["process"]["process_created"]
    assert store.trace.count("EXACT_ARMED_AUTHORIZATION") == 1


def test_cancel_before_dispatch_creates_no_child(tmp_path):
    coordinator, store, worker, request = components(tmp_path)
    permit = coordinator.prepare(request)
    cancel = Event()
    cancel.set()
    result = coordinator.execute(permit, cancellation=cancel)
    assert result.state is AttemptState.ABORTED_PRE_EFFECT
    assert not worker.status()["consumed"]
    assert not store.evidence
    assert not list(worker.directory.iterdir())


def test_no_unscoped_execution_or_runtime_source_relabel(tmp_path):
    _, _, worker, _ = components(tmp_path)
    for name in ("run_campaign", "run_retained_campaign"):
        with pytest.raises(ValueError, match="SCOPED_RETAINED"):
            getattr(worker, name)()
    with pytest.raises(ValueError, match="RUNTIME_PLAN_SOURCE"):
        campaign.OwnedArmFeedbackRehearsalCampaign(
            replace(worker.plan, source_sha256="a" * 64),
            runtime=worker.runtime,
            directory=worker.directory,
        )
    assert not worker.status()["consumed"]


def test_reopen_rejects_understated_process_lifetime_without_feedback(tmp_path):
    # This is one actual incapable child with a malformed result. Keeping its
    # original process bytes/duration makes the timing contradiction observable
    # even though no inner feedback result can supply its own elapsed time.
    _, _, worker, permit, result = execute(tmp_path, "malformed-result")
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert worker.evidence is not None
    assert worker.evidence.result is None
    document = worker.evidence.to_dict()
    process = document["owned_evidence"]["process"]["report"]
    assert process["elapsed_ns"] > 0
    started = document["request_started_monotonic_ns"]
    document["worker_finished_monotonic_ns"] = started
    observation = document["final_power_observation"]
    assert observation is not None
    observation["worker_finished_monotonic_ns"] = started
    observation["observed_monotonic_ns"] = started
    observation["observation_sha256"] = campaign._hash(
        {
            key: value
            for key, value in observation.items()
            if key != "observation_sha256"
        }
    )
    # The helper recomputes the outer digest deliberately: exact hashes alone
    # must not allow a post-process observation to precede retained process time.
    with pytest.raises(ValueError, match="WRAPPER_COMPLETION_PRECEDES_PROCESS"):
        verify(worker, permit, campaign._canonical(document))


@pytest.mark.parametrize(
    "scenario,attempts,opens",
    [
        ("identity-change-preopen", 1, 0),
        ("malformed-metadata", 1, 0),
        ("identity-change", 2, 1),
        ("boot-bytes", 1, 1),
    ],
)
def test_actual_child_metadata_faults_stop_at_the_right_boundary(
    tmp_path, scenario, attempts, opens
):
    _, store, worker, permit, result = execute(tmp_path, scenario)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert result.quarantine_latched and permit.attempt_id in store.evidence
    evidence = verify(worker, permit)
    resolution = evidence.process_summary()["resolution"]
    assert resolution["attempt_count"] == attempts
    assert evidence.result.api_counts.open_attempts == opens
    assert evidence.result.api_counts.write_attempts == 0
    full = evidence.resolution_diagnostics()
    assert full["status"] == "RETAINED"
    assert full["trace_sha256"] == resolution["trace_sha256"]
    assert len(full["trace"]["attempts"]) == attempts
    assert not campaign.owned_feedback_checks(evidence.process_summary())[
        "controller_resolution_before_open_and_write"
    ]
