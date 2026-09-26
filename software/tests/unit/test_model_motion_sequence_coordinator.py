from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rocell.application.context import load_simulation_context
from rocell.application.model_motion_ingress import ingest_model_motion_batch
from rocell.application.model_motion_sequence_coordinator import (
    READY_PLANNER_STATUS,
    ActionDisposition,
    ModelMotionSequenceCoordinator,
    ModelMotionSequenceError,
    SequencePhase,
    VerifiedActionResult,
)
from rocell.application.observed_planner_start_state import ObservedPlannerStartState
from rocell.models import (
    ActionPlan,
    Device,
    Interaction,
    ModelMotionBatch,
    ModelMotionProposal,
    Point3Mm,
    PressKey,
    ProposalDevice,
    ProposalSource,
    SpeedClass,
)


WORKSPACE = Path(__file__).resolve().parents[3]
MANIFEST = WORKSPACE / "software/config/system_manifest.json"
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _setup():
    context = load_simulation_context(WORKSPACE, MANIFEST)
    plan = ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id="keyboard-development-v1",
        text="hi",
        actions=(PressKey("H"), PressKey("I")),
        required_calibrations=("keyboard_pose", "keyboard_tcp"),
    )
    proposals = []
    for index, target_id in enumerate(("H", "I")):
        center = context.targets.resolve("keyboard", target_id).center
        proposals.append(
            ModelMotionProposal(
                proposal_id=f"request-001-action-{index}",
                device=ProposalDevice.KEYBOARD,
                target_id=target_id,
                target=Point3Mm("board", center.x, center.y, center.z),
                interaction=Interaction.CONTACT,
                approach_clearance_mm=25.0,
                speed_class=SpeedClass.SLOW,
                confidence=0.99,
                source=ProposalSource("model-a", "frame-001", HASH_A),
            )
        )
    batch = ModelMotionBatch(
        batch_id="batch-001",
        request_id="request-001",
        intent_plan_sha256=plan.plan_hash,
        scene_observation_sha256=HASH_B,
        precision_observation_sha256=HASH_C,
        fusion_decision_sha256="d" * 64,
        proposals=tuple(proposals),
    )
    ingress = ingest_model_motion_batch(
        batch,
        plan,
        context,
        expected_scene_observation_sha256=HASH_B,
        expected_precision_observation_sha256=HASH_C,
        expected_fusion_decision_sha256="d" * 64,
    )
    return context, batch, ingress


def _observed(seed: str, *, available: int = 100) -> ObservedPlannerStartState:
    return ObservedPlannerStartState(
        run_id=f"run-{seed}",
        arm_identity_sha256="1" * 64,
        controller_session_id="session-1",
        request_context_sha256="2" * 64,
        feedback_receipt_sha256=seed * 64,
        calibration_snapshot_sha256="4" * 64,
        manifest_id="manifest-1",
        active_build_id="build-1",
        response_completed_monotonic_ns=available - 10,
        available_monotonic_ns=available,
        valid_until_monotonic_ns=available + 100,
        controller_joint_positions_rad={
            name: 0.0 for name in ("b", "s", "e", "t", "r", "g")
        },
        model_joint_positions_rad={
            name: 0.0
            for name in (
                "b_base",
                "s_shoulder",
                "e_elbow",
                "t_wrist_pitch",
                "r_wrist_roll",
                "g_gripper",
            )
        },
    )


def _ready_gate(ingress):
    calls = []

    def gate(proposal, context, *, observed_start_state, evaluation_monotonic_ns):
        index = len(calls)
        calls.append(
            (proposal.target_id, observed_start_state.observed_start_state_sha256)
        )
        report = {
            "status": READY_PLANNER_STATUS,
            "model_motion_candidate_sha256": ingress["ordered_candidate_sha256"][index],
            "trajectory_candidate": {
                "observed_start_state_sha256": (
                    observed_start_state.observed_start_state_sha256
                ),
            },
            "controller_commands": [],
            "hardware_commands_generated": 0,
            "hardware_access": False,
            "physical_authority": False,
        }
        report["planner_gate_sha256"] = hashlib.sha256(
            json.dumps(
                report, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode("utf-8")
        ).hexdigest()
        return report

    return gate, calls


def _result(batch, coordinator, disposition=ActionDisposition.VERIFIED_COMPLETED):
    proposal = coordinator.current_proposal
    assert proposal is not None
    snapshot = coordinator.snapshot()
    return VerifiedActionResult(
        batch_sha256=batch.batch_sha256,
        action_index=coordinator.action_index,
        proposal_sha256=proposal.proposal_sha256,
        planner_gate_sha256=snapshot["planner_gate_sha256"][-1],
        execution_receipt_sha256=str(coordinator.action_index + 7) * 64,
        outcome_evidence_sha256=(
            "9" * 64 if disposition is ActionDisposition.VERIFIED_COMPLETED else None
        ),
        disposition=disposition,
    )


def test_sequence_requires_fresh_state_after_each_verified_action() -> None:
    context, batch, ingress = _setup()
    gate, calls = _ready_gate(ingress)
    coordinator = ModelMotionSequenceCoordinator(
        batch, ingress, context, planner_gate=gate
    )

    coordinator.evaluate_next(_observed("a"), evaluation_monotonic_ns=110)
    assert coordinator.phase is SequencePhase.READY_FOR_SINGLE_ACTION_EXECUTOR
    assert calls == [("H", _observed("a").observed_start_state_sha256)]
    coordinator.record_result(_result(batch, coordinator))
    assert coordinator.phase is SequencePhase.WAITING_FOR_FRESH_STATE
    assert coordinator.current_proposal.target_id == "I"

    coordinator.evaluate_next(
        _observed("b", available=300), evaluation_monotonic_ns=310
    )
    coordinator.record_result(_result(batch, coordinator))
    snapshot = coordinator.snapshot()
    assert coordinator.phase is SequencePhase.COMPLETED
    assert snapshot["completed_action_count"] == 2
    assert snapshot["current_action_index"] is None
    assert snapshot["automatic_retry_allowed"] is False
    assert snapshot["lookahead_planning_allowed"] is False
    assert snapshot["controller_commands"] == []
    assert snapshot["hardware_commands_generated"] == 0


def test_sequence_forbids_lookahead_and_observed_state_reuse() -> None:
    context, batch, ingress = _setup()
    gate, _ = _ready_gate(ingress)
    coordinator = ModelMotionSequenceCoordinator(
        batch, ingress, context, planner_gate=gate
    )
    first = _observed("a")
    coordinator.evaluate_next(first, evaluation_monotonic_ns=110)
    with pytest.raises(ModelMotionSequenceError, match="not waiting"):
        coordinator.evaluate_next(_observed("b"), evaluation_monotonic_ns=110)
    coordinator.record_result(_result(batch, coordinator))
    with pytest.raises(ModelMotionSequenceError, match="cannot be reused"):
        coordinator.evaluate_next(first, evaluation_monotonic_ns=120)


def test_sequence_blocks_on_planner_rejection_and_emits_no_commands() -> None:
    context, batch, ingress = _setup()

    def blocked(proposal, context, *, observed_start_state, evaluation_monotonic_ns):
        report = {
            "status": "BLOCKED_COLLISION_SCREENING_REQUIRED",
            "model_motion_candidate_sha256": ingress["ordered_candidate_sha256"][0],
            "trajectory_candidate": {
                "observed_start_state_sha256": (
                    observed_start_state.observed_start_state_sha256
                ),
            },
            "controller_commands": [],
            "hardware_commands_generated": 0,
            "hardware_access": False,
            "physical_authority": False,
        }
        report["planner_gate_sha256"] = hashlib.sha256(
            json.dumps(
                report, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode("utf-8")
        ).hexdigest()
        return report

    coordinator = ModelMotionSequenceCoordinator(
        batch, ingress, context, planner_gate=blocked
    )
    coordinator.evaluate_next(_observed("a"), evaluation_monotonic_ns=110)
    snapshot = coordinator.snapshot()
    assert coordinator.phase is SequencePhase.BLOCKED
    assert snapshot["blocker"] == "BLOCKED_COLLISION_SCREENING_REQUIRED"
    with pytest.raises(ModelMotionSequenceError, match="no action"):
        coordinator.record_result(_result(batch, coordinator))


def test_uncertain_outcome_is_terminal_and_cannot_retry() -> None:
    context, batch, ingress = _setup()
    gate, calls = _ready_gate(ingress)
    coordinator = ModelMotionSequenceCoordinator(
        batch, ingress, context, planner_gate=gate
    )
    coordinator.evaluate_next(_observed("a"), evaluation_monotonic_ns=110)
    coordinator.record_result(
        _result(batch, coordinator, ActionDisposition.OUTCOME_UNCERTAIN)
    )
    assert coordinator.phase is SequencePhase.OUTCOME_UNCERTAIN
    assert coordinator.action_index == 0
    assert len(calls) == 1
    with pytest.raises(ModelMotionSequenceError, match="not waiting"):
        coordinator.evaluate_next(_observed("b"), evaluation_monotonic_ns=110)


def test_result_must_bind_exact_current_action() -> None:
    context, batch, ingress = _setup()
    gate, _ = _ready_gate(ingress)
    coordinator = ModelMotionSequenceCoordinator(
        batch, ingress, context, planner_gate=gate
    )
    coordinator.evaluate_next(_observed("a"), evaluation_monotonic_ns=110)
    wrong = _result(batch, coordinator)
    wrong = VerifiedActionResult(
        batch_sha256=wrong.batch_sha256,
        action_index=1,
        proposal_sha256=wrong.proposal_sha256,
        planner_gate_sha256=wrong.planner_gate_sha256,
        execution_receipt_sha256=wrong.execution_receipt_sha256,
        outcome_evidence_sha256=wrong.outcome_evidence_sha256,
        disposition=wrong.disposition,
    )
    with pytest.raises(ModelMotionSequenceError, match="current action"):
        coordinator.record_result(wrong)
