from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from rocell.application.context import load_simulation_context
from rocell.application.model_motion_ingress import (
    ModelMotionIngressError,
    ingest_model_motion_batch,
)
from rocell.models import (
    ActionPlan,
    Device,
    Interaction,
    ModelMotionBatch,
    ModelMotionBatchError,
    ModelMotionProposal,
    Point3Mm,
    PressKey,
    ProposalDevice,
    ProposalSource,
    SpeedClass,
    decode_model_motion_batch_json,
)


WORKSPACE = Path(__file__).resolve().parents[3]
MANIFEST = WORKSPACE / "software/config/system_manifest.json"
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _plan() -> ActionPlan:
    return ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id="keyboard-development-v1",
        text="hi",
        actions=(PressKey("H"), PressKey("I")),
        required_calibrations=("keyboard_pose", "keyboard_tcp"),
    )


def _proposal(context, target_id: str, index: int) -> ModelMotionProposal:
    center = context.targets.resolve("keyboard", target_id).center
    return ModelMotionProposal(
        proposal_id=f"request-001-action-{index}",
        device=ProposalDevice.KEYBOARD,
        target_id=target_id,
        target=Point3Mm("board", center.x, center.y, center.z),
        interaction=Interaction.CONTACT,
        approach_clearance_mm=25.0,
        speed_class=SpeedClass.SLOW,
        confidence=0.99,
        source=ProposalSource("keyboard-pose-net-checkpoint-a", "frame-001", HASH_A),
    )


def _batch(context, plan: ActionPlan | None = None) -> ModelMotionBatch:
    selected_plan = _plan() if plan is None else plan
    return ModelMotionBatch(
        batch_id="batch-001",
        request_id="request-001",
        intent_plan_sha256=selected_plan.plan_hash,
        scene_observation_sha256=HASH_B,
        precision_observation_sha256=HASH_C,
        fusion_decision_sha256="d" * 64,
        proposals=(_proposal(context, "H", 0), _proposal(context, "I", 1)),
    )


def _ingest(batch, plan, context):
    return ingest_model_motion_batch(
        batch,
        plan,
        context,
        expected_scene_observation_sha256=HASH_B,
        expected_precision_observation_sha256=HASH_C,
        expected_fusion_decision_sha256="d" * 64,
    )


def test_batch_round_trip_and_ingress_preserve_order_and_zero_authority() -> None:
    context = load_simulation_context(WORKSPACE, MANIFEST)
    plan = _plan()
    batch = _batch(context, plan)

    decoded = ModelMotionBatch.from_mapping(batch.to_dict())
    decoded_bytes = decode_model_motion_batch_json(
        json.dumps(batch.to_dict(), sort_keys=True).encode("utf-8")
    )
    report = _ingest(decoded, plan, context)

    assert decoded == batch
    assert decoded_bytes == batch
    assert report["batch_sha256"] == batch.batch_sha256
    assert report["intent_plan_sha256"] == plan.plan_hash
    assert report["ordered_target_ids"] == ["H", "I"]
    assert [item["target_id"] for item in report["candidates"]] == ["H", "I"]
    assert report["source_bindings"]["image_sha256"] == HASH_A
    assert report["source_bindings"]["scene_observation_sha256"] == HASH_B
    assert report["controller_commands"] == []
    assert report["hardware_commands_generated"] == 0
    assert report["hardware_access"] is False
    assert report["physical_authority"] is False


def test_batch_rejects_tampered_hash_and_mixed_frame_sources() -> None:
    context = load_simulation_context(WORKSPACE, MANIFEST)
    document = _batch(context).to_dict()
    document["request_id"] = "tampered"
    with pytest.raises(ModelMotionBatchError, match="batch_sha256"):
        ModelMotionBatch.from_mapping(document)

    second = replace(
        _proposal(context, "I", 1),
        source=ProposalSource("keyboard-pose-net-checkpoint-a", "frame-002", HASH_A),
    )
    with pytest.raises(ModelMotionBatchError, match="same model, frame, and image"):
        replace(_batch(context), proposals=(_proposal(context, "H", 0), second))

    encoded = json.dumps(_batch(context).to_dict(), separators=(",", ":"))
    duplicate = encoded.replace(
        '"batch_id":"batch-001"',
        '"batch_id":"batch-001","batch_id":"other"',
        1,
    )
    with pytest.raises(ModelMotionBatchError, match="duplicate JSON field"):
        decode_model_motion_batch_json(duplicate.encode("utf-8"))


def test_ingress_rejects_wrong_intent_or_proposal_order() -> None:
    context = load_simulation_context(WORKSPACE, MANIFEST)
    plan = _plan()
    batch = _batch(context, plan)

    other_plan = ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id=plan.profile_id,
        text="ih",
        actions=(PressKey("I"), PressKey("H")),
        required_calibrations=plan.required_calibrations,
    )
    with pytest.raises(ModelMotionIngressError, match="semantic plan"):
        _ingest(batch, other_plan, context)

    reordered = replace(
        batch,
        intent_plan_sha256=other_plan.plan_hash,
        proposals=(batch.proposals[1], batch.proposals[0]),
    )
    report = _ingest(reordered, other_plan, context)
    assert report["ordered_target_ids"] == ["I", "H"]


def test_ingress_rejects_coordinate_outside_named_target() -> None:
    context = load_simulation_context(WORKSPACE, MANIFEST)
    plan = _plan()
    bad = replace(
        _proposal(context, "H", 0),
        target=Point3Mm("board", -900.0, -900.0, 0.0),
    )
    batch = replace(_batch(context, plan), proposals=(bad, _proposal(context, "I", 1)))

    with pytest.raises(ModelMotionIngressError, match="coordinate admission"):
        _ingest(batch, plan, context)


def test_ingress_rejects_batch_evidence_hash_not_independently_supplied() -> None:
    context = load_simulation_context(WORKSPACE, MANIFEST)
    plan = _plan()
    batch = _batch(context, plan)
    with pytest.raises(ModelMotionIngressError, match="validated evidence"):
        ingest_model_motion_batch(
            batch,
            plan,
            context,
            expected_scene_observation_sha256="e" * 64,
            expected_precision_observation_sha256=HASH_C,
            expected_fusion_decision_sha256="d" * 64,
        )
