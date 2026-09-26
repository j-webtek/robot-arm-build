from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application.context import load_simulation_context
from rocell.application.trajectory_execution_envelope import (
    JointTrajectoryLimits, TimedJointWaypoint, TrajectoryExecutionEnvelope,
    TrajectorySettlePolicy)
from rocell.application.trajectory_execution_envelope_v2 import (
    TrajectoryExecutionEnvelopeV2Error,
    bind_trajectory_execution_envelope_v2)
from rocell.kinematics import ARM_JOINT_NAMES

import test_model_motion_ingress_v2 as arm

WORKSPACE = Path(__file__).resolve().parents[3]
MANIFEST = WORKSPACE / "software/config/system_manifest.json"


def _joints(value):
    return {name: value for name in ARM_JOINT_NAMES}


def _inner(batch_sha256, surrogate_sha256, measured_gate_sha256):
    limits = JointTrajectoryLimits(
        _joints(-2.0), _joints(2.0), _joints(1.0), _joints(5.0),
        _joints(20.0))
    return TrajectoryExecutionEnvelope(
        correlation_id="v2-shadow-action-0", batch_sha256=batch_sha256,
        action_index=0, proposal_sha256=surrogate_sha256,
        planner_gate_sha256=measured_gate_sha256,
        trajectory_screening_sha256="5" * 64,
        collision_screening_sha256="6" * 64,
        observed_start_state_sha256="7" * 64,
        observed_start_joint_positions_rad=_joints(0.0),
        build_snapshot_sha256="8" * 64,
        calibration_snapshot_sha256="9" * 64,
        configuration_epoch_sha256="a" * 64,
        controller_session_id="offline-session", issued_monotonic_ns=1,
        deadline_monotonic_ns=3_000_000_000, limits=limits,
        settle_policy=TrajectorySettlePolicy(
            _joints(0.01), _joints(0.02), 100_000_000),
        waypoints=(TimedJointWaypoint(0, 0, _joints(0.0)),
                   TimedJointWaypoint(1, 1_000_000_000, _joints(0.1))))


def _planner_inputs():
    context = load_simulation_context(WORKSPACE, MANIFEST)
    batch = arm._batch(context)
    ingress = arm._ingest(batch, arm._plan(), context)
    preplanner = arm.revalidate_model_motion_ingress_v2(
        ingress, current_monotonic_ns=10_000_000_000,
        expected_capability_profile_sha256=arm.H["e"],
        active_scene_lease_sha256=arm.H["f"],
        active_placement_observation_sha256=arm.H["e"],
        active_target_catalog_sha256=context.targets.content_sha256)
    policy = arm.ArmMotionPolicyV2(
        "keyboard-contact-conservative-v1", 25.0, arm.SpeedClass.SLOW)
    report = arm.evaluate_model_motion_planner_gate_v2(
        batch.proposals[0], batch, ingress, preplanner, context,
        policy=policy, evaluation_monotonic_ns=10_500_000_000)
    return batch, report


def _synthetic_ready(report):
    measured = dict(report["measured_planner_gate"])
    measured["status"] = "READY_FOR_SINGLE_ACTION_EXECUTION_ADMISSION"
    measured_unsigned = {
        key: value for key, value in measured.items()
        if key != "planner_gate_sha256"
    }
    measured["planner_gate_sha256"] = hashlib.sha256(json.dumps(
        measured_unsigned, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    ready = dict(report)
    ready["status"] = "READY_FOR_SINGLE_ACTION_EXECUTION_ADMISSION"
    ready["measured_planner_gate"] = measured
    ready["measured_planner_gate_sha256"] = measured["planner_gate_sha256"]
    ready_unsigned = {
        key: value for key, value in ready.items()
        if key != "planner_gate_v2_sha256"
    }
    ready["planner_gate_v2_sha256"] = hashlib.sha256(json.dumps(
        ready_unsigned, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    return ready


def test_v2_envelope_binds_original_and_measured_surrogate_lineages():
    batch, report = _planner_inputs()
    with pytest.raises(TrajectoryExecutionEnvelopeV2Error, match="must be ready"):
        bind_trajectory_execution_envelope_v2(
            batch, batch.proposals[0], report,
            _inner(batch.batch_sha256,
                   report["derived_v1_surrogate_sha256"],
                   report["measured_planner_gate_sha256"]))
    report = _synthetic_ready(report)
    inner = _inner(batch.batch_sha256,
                   report["derived_v1_surrogate_sha256"],
                   report["measured_planner_gate_sha256"])
    envelope = bind_trajectory_execution_envelope_v2(
        batch, batch.proposals[0], report, inner)
    document = envelope.to_dict()
    assert document["proposal_v2_sha256"] == batch.proposals[0].proposal_sha256
    assert document["measured_envelope"]["proposal_sha256"] == (
        report["derived_v1_surrogate_sha256"])
    assert document["wire_commands"] == []
    assert document["hardware_access"] is document["physical_authority"] is False


def test_v2_envelope_rejects_crossed_surrogate_or_planner_lineage():
    batch, report = _planner_inputs()
    report = _synthetic_ready(report)
    inner = _inner(batch.batch_sha256, "b" * 64,
                   report["measured_planner_gate_sha256"])
    with pytest.raises(TrajectoryExecutionEnvelopeV2Error, match="lineage"):
        bind_trajectory_execution_envelope_v2(
            batch, batch.proposals[0], report, inner)
    tampered = dict(report); tampered["action_index"] = 1
    with pytest.raises(TrajectoryExecutionEnvelopeV2Error, match="content hash"):
        bind_trajectory_execution_envelope_v2(
            batch, batch.proposals[0], tampered,
            replace(inner,
                    proposal_sha256=report["derived_v1_surrogate_sha256"]))
