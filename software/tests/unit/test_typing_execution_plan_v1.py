from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest

from rocell.application.typing_execution_plan_v1 import (
    TransitionKindV1,
    TypingExecutionConfigV1,
    TypingExecutionPlanV1,
    TypingExecutionPlanV1Error,
    compile_typing_execution_plan_v1,
)
from rocell.models import (
    Interaction,
    ModelMotionBatchV2,
    ModelMotionProposalV2,
    MotionCapabilityV2,
    MotionEvidenceV2,
    MotionGeometryV2,
    MotionUncertaintyV2,
    Point3Mm,
    ProposalDevice,
    SpeedClass,
    UncertaintyBoundType,
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _batch() -> ModelMotionBatchV2:
    target_points = (
        ("R", 0.0, 0.0),
        ("O", 20.0, 0.0),
        ("B", 15.0, 20.0),
        ("O", 20.0, 0.0),
        ("T", 5.0, 0.0),
    )
    proposals = tuple(
        ModelMotionProposalV2(
            proposal_id=f"proposal-{index}", action_index=index,
            device=ProposalDevice.KEYBOARD, target_id=target_id,
            target=Point3Mm("board", x, y, 2.0),
            interaction=Interaction.CONTACT, observation_confidence=0.99,
        )
        for index, (target_id, x, y) in enumerate(target_points)
    )
    return ModelMotionBatchV2(
        batch_id="batch-robot", request_id="request-robot",
        intent_plan_sha256="1" * 64, device=ProposalDevice.KEYBOARD,
        capability=MotionCapabilityV2("keyboard-development-v1", "2" * 64),
        geometry=MotionGeometryV2(
            coordinate_profile="board_mm_xy_plane_v2", coordinate_units="mm",
            board_frame_definition_sha256="3" * 64,
            placement_observation_sha256="4" * 64,
            target_catalog_sha256="5" * 64),
        evidence=MotionEvidenceV2(
            capture_id="capture-1", frame_id="frame-1", image_sha256="6" * 64,
            camera_identity_sha256="7" * 64,
            capture_clock_domain_id="clock-1", model_id="model-1",
            model_sha256="8" * 64, scene_observation_sha256="9" * 64,
            precision_observation_sha256="a" * 64,
            fusion_decision_sha256="b" * 64, scene_lease_id="lease-1",
            scene_lease_issuer_id="issuer-1", scene_lease_sha256="c" * 64,
            captured_at_epoch_ms=1_000, evaluated_at_epoch_ms=2_000,
            expires_at_epoch_ms=10_000),
        uncertainty=MotionUncertaintyV2(
            bound_type=UncertaintyBoundType.PLANAR_L2_DISK,
            error_bound_mm=1.0, coverage_probability=0.99,
            qualification_sha256="d" * 64, evidence_method_sha256="e" * 64,
            domain_id="keyboard-final-camera-v1",
            covered_target_ids=("R", "O", "B", "T")),
        proposals=proposals,
    )


def _ingress(batch: ModelMotionBatchV2) -> dict[str, object]:
    report: dict[str, object] = {
        "schema": "rocell.model_motion_ingress.v2",
        "status": "ACCEPTED_V2_FOR_FRESH_SEQUENTIAL_PLANNER_GATES",
        "batch_sha256": batch.batch_sha256,
        "intent_plan_sha256": batch.intent_plan_sha256,
        "request_id": batch.request_id,
        "ordered_target_ids": [item.target_id for item in batch.proposals],
        "controller_commands": [],
        "hardware_commands_generated": 0,
        "hardware_access": False,
        "physical_authority": False,
    }
    report["ingress_sha256"] = hashlib.sha256(_canonical(report)).hexdigest()
    return report


def _config() -> TypingExecutionConfigV1:
    return TypingExecutionConfigV1(
        config_id="keyboard-s0-offline-v1",
        calibration_snapshot_sha256="f" * 64,
        tool_profile_sha256="0" * 64,
        dynamics_profile_sha256="1" * 64,
        route_reference_point=Point3Mm("board", -30.0, 0.0, 22.0),
        hover_clearance_mm=20.0,
        settle_position_tolerance_mm=0.5,
        settle_velocity_tolerance_mm_s=1.0,
        settle_hold_ms=100,
        preview_horizon=1,
        speed_class=SpeedClass.SLOW,
    )


def test_robot_plan_preserves_order_and_builds_direct_local_cycles():
    batch = _batch()
    plan = compile_typing_execution_plan_v1(
        batch, _ingress(batch), config=_config())

    assert [item.target_id for item in plan.actions] == ["R", "O", "B", "O", "T"]
    assert plan.actions[0].transition_kind is TransitionKindV1.START_REFERENCE_TO_HOVER
    assert all(
        item.transition_kind is TransitionKindV1.DIRECT_RETRACT_TO_HOVER
        for item in plan.actions[1:]
    )
    assert plan.actions[3].target_id == "O"
    assert plan.actions[3].transition_source == plan.actions[2].retract_point
    assert all(item.local_cycle_distance_mm == 40.0 for item in plan.actions)
    assert plan.metrics.direct_total_distance_mm < plan.metrics.park_total_distance_mm
    assert plan.metrics.distance_saved_mm > 0.0
    assert plan.metrics.distance_reduction_fraction > 0.0
    document = plan.to_dict()
    assert document["commit_horizon"] == 1
    assert document["preview_horizon"] == 1
    assert document["controller_commands"] == []
    assert document["hardware_commands_generated"] == 0
    assert document["hardware_access"] is document["physical_authority"] is False


def test_plan_serialization_is_canonical_deterministic_and_round_trips():
    batch = _batch()
    first = compile_typing_execution_plan_v1(batch, _ingress(batch), config=_config())
    second = compile_typing_execution_plan_v1(batch, _ingress(batch), config=_config())

    assert first.to_bytes() == second.to_bytes()
    assert first.plan_sha256 == second.plan_sha256
    restored = TypingExecutionPlanV1.from_bytes(first.to_bytes())
    assert restored == first
    assert restored.to_bytes() == first.to_bytes()


def test_noncanonical_or_tampered_plan_bytes_fail_closed():
    batch = _batch()
    plan = compile_typing_execution_plan_v1(batch, _ingress(batch), config=_config())
    with pytest.raises(TypingExecutionPlanV1Error, match="not canonical"):
        TypingExecutionPlanV1.from_bytes(plan.to_bytes() + b"\n")

    document = plan.to_dict()
    document["actions"][1]["target_id"] = "X"
    payload = _canonical(document)
    with pytest.raises(TypingExecutionPlanV1Error, match="plan_sha256"):
        TypingExecutionPlanV1.from_bytes(payload)


def test_ingress_order_or_hash_mutation_is_rejected():
    batch = _batch()
    ingress = _ingress(batch)
    ingress["ordered_target_ids"] = ["R", "B", "O", "O", "T"]
    ingress["ingress_sha256"] = hashlib.sha256(_canonical({
        key: value for key, value in ingress.items() if key != "ingress_sha256"
    })).hexdigest()
    with pytest.raises(TypingExecutionPlanV1Error, match="order differs"):
        compile_typing_execution_plan_v1(batch, ingress, config=_config())

    ingress = _ingress(batch)
    ingress["hardware_access"] = True
    with pytest.raises(TypingExecutionPlanV1Error, match="content hash"):
        compile_typing_execution_plan_v1(batch, ingress, config=_config())


def test_phone_or_noncontact_batches_are_not_typing_plans():
    batch = _batch()
    phone = replace(batch, device=ProposalDevice.PHONE,
                    proposals=tuple(replace(item, device=ProposalDevice.PHONE)
                                    for item in batch.proposals))
    with pytest.raises(TypingExecutionPlanV1Error, match="keyboard batches"):
        compile_typing_execution_plan_v1(phone, _ingress(phone), config=_config())

    proposals = list(batch.proposals)
    proposals[0] = replace(proposals[0], interaction=Interaction.HOVER)
    noncontact = replace(batch, proposals=tuple(proposals))
    with pytest.raises(TypingExecutionPlanV1Error, match="CONTACT"):
        compile_typing_execution_plan_v1(
            noncontact, _ingress(noncontact), config=_config())


def test_config_rejects_unbounded_preview_or_zero_clearance():
    with pytest.raises(TypingExecutionPlanV1Error, match="preview_horizon"):
        replace(_config(), preview_horizon=3)
    with pytest.raises(TypingExecutionPlanV1Error, match="hover_clearance"):
        replace(_config(), hover_clearance_mm=0.0)
