"""Actual AI v2 bytes through the consumer-owned arm registry; zero hardware."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "software/ai"), str(ROOT / "software/tests/unit")]

import test_model_motion_ingress_v2 as arm  # noqa: E402
from rocell_ai.batch_emitter_v2 import TargetObservationV2, assemble  # noqa: E402
from rocell.application.model_motion_registry_v2 import (  # noqa: E402
    ingest_with_trusted_registry_v2, revalidate_with_trusted_registry_v2)
from rocell.application.model_motion_planner_gate_v2 import (  # noqa: E402
    ArmMotionPolicyV2)
from rocell.application.model_motion_shadow_v2 import (  # noqa: E402
    ModelMotionShadowV2Error, run_model_motion_shadow_v2)
from rocell.application.model_motion_sequence_coordinator_v2 import (  # noqa: E402
    ModelMotionSequenceCoordinatorV2, ModelMotionSequenceV2Error)
from rocell.application.observed_planner_start_state import (  # noqa: E402
    ObservedPlannerStartState)


def _actual_bytes_and_registry():
    context = arm.load_simulation_context(arm.WORKSPACE, arm.MANIFEST)
    plan = arm.ActionPlan.from_text(device=arm.Device.KEYBOARD,
        profile_id="keyboard-development-v1", text="hhi",
        actions=(arm.PressKey("H"), arm.PressKey("H"), arm.PressKey("I")),
        required_calibrations=("keyboard_pose", "keyboard_tcp"))
    fixture = arm._batch(context)
    args = dict(batch_id="shared-gate-v2", request_id="shared-request-v2",
        capability=fixture.capability, geometry=fixture.geometry,
        evidence=fixture.evidence, uncertainty=fixture.uncertainty,
        observations={proposal.target_id: TargetObservationV2(
            proposal.target, 0.93) for proposal in fixture.proposals})
    return context, plan, args, arm._registry(context)


def test_actual_ai_bytes_pass_registry_ingress_and_preplanner_gate():
    context, plan, args, registry = _actual_bytes_and_registry()
    payload = assemble(plan, **args)
    schema_root = ROOT / "software/ai/schemas"
    batch_schema = json.loads((schema_root / "model_motion_batch_v2.schema.json").read_text())
    proposal_schema = json.loads((schema_root / "model_motion_proposal_v2.schema.json").read_text())
    inline_proposal = {key: value for key, value in proposal_schema.items()
                       if key not in {"$schema", "$id", "$defs"}}
    batch_schema["properties"]["proposals"]["items"] = inline_proposal
    jsonschema.Draft202012Validator(batch_schema).validate(json.loads(payload))
    batch = arm.decode_model_motion_batch_v2_json(payload)
    ingress = ingest_with_trusted_registry_v2(batch, plan, context,
        registry=registry, current_time_epoch_ms=arm.T0 + 3_000,
        current_monotonic_ns=9_000_000_000)
    gate = revalidate_with_trusted_registry_v2(ingress, registry=registry,
        current_monotonic_ns=10_000_000_000)
    assert ingress["ordered_target_ids"] == ["H", "H", "I"]
    assert gate["status"] == "FRESH_FOR_DETERMINISTIC_PLANNING"
    assert ingress["controller_commands"] == gate["controller_commands"] == []
    assert ingress["hardware_access"] is gate["hardware_access"] is False
    assert ingress["physical_authority"] is gate["physical_authority"] is False


@pytest.mark.parametrize("mutation", [
    "plan", "image", "frame", "time", "capability", "camera", "clock",
    "lease", "placement", "target_map", "qualification", "domain",
    "uncertainty", "edge"])
def test_actual_ai_bytes_fail_closed_for_each_trust_or_geometry_mutation(mutation):
    context, plan, args, registry = _actual_bytes_and_registry()
    emitter_plan = plan
    if mutation == "plan":
        emitter_plan = arm.ActionPlan.from_text(device=arm.Device.KEYBOARD,
            profile_id="keyboard-development-v1", text="different-request",
            actions=(arm.PressKey("H"), arm.PressKey("H"), arm.PressKey("I")),
            required_calibrations=("keyboard_pose", "keyboard_tcp"))
    elif mutation == "image":
        args["evidence"] = replace(args["evidence"], image_sha256="1" * 64)
    elif mutation == "frame":
        args["evidence"] = replace(args["evidence"], frame_id="other-frame")
    elif mutation == "time":
        args["evidence"] = replace(args["evidence"],
            captured_at_epoch_ms=arm.T0 + 4_000,
            evaluated_at_epoch_ms=arm.T0 + 5_000)
    elif mutation == "capability":
        args["capability"] = replace(args["capability"], profile_sha256="1" * 64)
    elif mutation == "camera":
        args["evidence"] = replace(args["evidence"], camera_identity_sha256="1" * 64)
    elif mutation == "clock":
        args["evidence"] = replace(args["evidence"], capture_clock_domain_id="other-clock")
    elif mutation == "lease":
        args["evidence"] = replace(args["evidence"], scene_lease_sha256="1" * 64)
    elif mutation == "placement":
        args["geometry"] = replace(args["geometry"],
                                   placement_observation_sha256="1" * 64)
    elif mutation == "target_map":
        args["geometry"] = replace(args["geometry"], target_catalog_sha256="1" * 64)
    elif mutation == "qualification":
        args["uncertainty"] = replace(args["uncertainty"],
                                      qualification_sha256="1" * 64)
    elif mutation == "domain":
        args["uncertainty"] = replace(args["uncertainty"], domain_id="other-domain")
    elif mutation == "uncertainty":
        args["uncertainty"] = replace(args["uncertainty"], error_bound_mm=1.1)
    elif mutation == "edge":
        target = context.targets.resolve("keyboard", "H")
        left = target.safe_rectangle_board_mm[0]
        args["observations"]["H"] = TargetObservationV2(
            arm.Point3Mm("board", left + 1.1, target.center.y, target.center.z), 0.93)
    payload = assemble(emitter_plan, **args)
    batch = arm.decode_model_motion_batch_v2_json(payload)
    with pytest.raises(ValueError):
        ingest_with_trusted_registry_v2(batch, plan, context, registry=registry,
            current_time_epoch_ms=arm.T0 + 3_000,
            current_monotonic_ns=9_000_000_000)


def test_actual_ai_bytes_expire_at_exact_deadline_and_never_reach_commands():
    context, plan, args, registry = _actual_bytes_and_registry()
    batch = arm.decode_model_motion_batch_v2_json(assemble(plan, **args))
    with pytest.raises(ValueError, match="future-dated or expired"):
        ingest_with_trusted_registry_v2(batch, plan, context, registry=registry,
            current_time_epoch_ms=args["evidence"].expires_at_epoch_ms,
            current_monotonic_ns=9_000_000_000)


def _fresh_observed_state(context):
    return ObservedPlannerStartState(
        run_id="shadow-v2", arm_identity_sha256="1" * 64,
        controller_session_id="offline-fixture",
        request_context_sha256="2" * 64, feedback_receipt_sha256="3" * 64,
        calibration_snapshot_sha256="4" * 64,
        manifest_id=context.snapshot.manifest_id,
        active_build_id=context.snapshot.active_build_id,
        response_completed_monotonic_ns=10_100_000_000,
        available_monotonic_ns=10_200_000_000,
        valid_until_monotonic_ns=11_000_000_000,
        controller_joint_positions_rad={name: 0.0 for name in ("b", "s", "e", "t", "r", "g")},
        model_joint_positions_rad={name: 0.0 for name in (
            "b_base", "s_shoulder", "e_elbow", "t_wrist_pitch",
            "r_wrist_roll", "g_gripper")})


def test_actual_ai_bytes_produce_one_hash_linked_zero_hardware_shadow_trace():
    context, plan, args, registry = _actual_bytes_and_registry()
    payload = assemble(plan, **args)
    report = run_model_motion_shadow_v2(
        payload, plan, context, registry=registry,
        policy=ArmMotionPolicyV2("keyboard-contact-conservative-v1", 25.0,
                                 arm.SpeedClass.SLOW),
        observed_start_state=_fresh_observed_state(context),
        current_time_epoch_ms=arm.T0 + 3_000,
        ingress_monotonic_ns=9_000_000_000,
        preplanner_monotonic_ns=10_000_000_000,
        planner_monotonic_ns=10_500_000_000)
    assert report["status"] == "BLOCKED_CALIBRATION_MISSING_OR_STALE"
    assert report["requested_text_sha256"] == plan.requested_text_sha256
    assert report["intent_plan_sha256"] == plan.plan_hash
    assert report["actions"][0]["target_id"] == "H"
    assert len(report["actions"]) == 1
    assert report["sequence_snapshot"]["action_count"] == 3
    assert report["sequence_snapshot"]["current_action_index"] == 0
    assert report["sequence_snapshot"]["phase"] == "BLOCKED"
    assert report["sequence_snapshot"]["lookahead_planning_allowed"] is False
    assert report["sequence_snapshot"]["v1_envelope_auto_upgrade_allowed"] is False
    assert report["trajectory_execution_envelope_sha256"] is None
    assert report["waveshare_bytes"] == report["controller_commands"] == []
    assert report["hardware_commands_generated"] == 0
    assert report["hardware_access"] is report["physical_authority"] is False


def test_shadow_trace_rejects_stale_observed_state_before_planning():
    context, plan, args, registry = _actual_bytes_and_registry()
    with pytest.raises(ModelMotionShadowV2Error, match="not fresh"):
        run_model_motion_shadow_v2(
            assemble(plan, **args), plan, context, registry=registry,
            policy=ArmMotionPolicyV2("keyboard-contact-conservative-v1", 25.0,
                                     arm.SpeedClass.SLOW),
            observed_start_state=_fresh_observed_state(context),
            current_time_epoch_ms=arm.T0 + 3_000,
            ingress_monotonic_ns=9_000_000_000,
            preplanner_monotonic_ns=10_000_000_000,
            planner_monotonic_ns=11_000_000_001)


def test_v2_coordinator_forbids_lookahead_or_retry_after_first_blocker():
    context, plan, args, registry = _actual_bytes_and_registry()
    batch = arm.decode_model_motion_batch_v2_json(assemble(plan, **args))
    ingress = ingest_with_trusted_registry_v2(
        batch, plan, context, registry=registry,
        current_time_epoch_ms=arm.T0 + 3_000,
        current_monotonic_ns=9_000_000_000)
    preplanner = revalidate_with_trusted_registry_v2(
        ingress, registry=registry, current_monotonic_ns=10_000_000_000)
    coordinator = ModelMotionSequenceCoordinatorV2(
        batch, ingress, preplanner, context,
        policy=ArmMotionPolicyV2("keyboard-contact-conservative-v1", 25.0,
                                 arm.SpeedClass.SLOW))
    observed = _fresh_observed_state(context)
    report = coordinator.evaluate_next(
        observed, evaluation_monotonic_ns=10_500_000_000)
    assert report["status"] == "BLOCKED_CALIBRATION_MISSING_OR_STALE"
    assert coordinator.current_proposal.target_id == "H"
    with pytest.raises(ModelMotionSequenceV2Error, match="not waiting"):
        coordinator.evaluate_next(
            observed, evaluation_monotonic_ns=10_500_000_001)
