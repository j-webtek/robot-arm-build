from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from rocell.application.context import load_simulation_context
from rocell.application.model_motion_ingress_v2 import (
    MeasuredTargetRegionV2, ModelMotionIngressV2Error,
    TrustedLocalizationQualificationV2, ingest_model_motion_batch_v2,
    revalidate_model_motion_ingress_v2)
from rocell.models import (
    ActionPlan, Device, Interaction, ModelMotionBatchV2, ModelMotionBatchV2Error,
    ModelMotionProposalV2, MotionCapabilityV2, MotionEvidenceV2, MotionGeometryV2,
    MotionUncertaintyV2, Point3Mm, PressKey, ProposalDevice, UncertaintyBoundType,
    decode_model_motion_batch_json, decode_model_motion_batch_v2_json)

WORKSPACE = Path(__file__).resolve().parents[3]
MANIFEST = WORKSPACE / "software/config/system_manifest.json"
H = {letter: letter * 64 for letter in "abcdef"}
T0 = 1_800_000_000_000


def _plan():
    return ActionPlan.from_text(device=Device.KEYBOARD,
        profile_id="keyboard-development-v1", text="hi",
        actions=(PressKey("H"), PressKey("I")),
        required_calibrations=("keyboard_pose", "keyboard_tcp"))


def _evidence(**changes):
    values = dict(capture_id="capture-001", frame_id="frame-001",
        image_sha256=H["a"], camera_identity_sha256=H["b"],
        capture_clock_domain_id="capture-clock-001",
        model_id="keyboard-pose-net-robust-v0", model_sha256=H["c"],
        scene_observation_sha256=H["b"], precision_observation_sha256=H["c"],
        fusion_decision_sha256=H["d"], scene_lease_id="lease-001",
        scene_lease_issuer_id="capture-service-001", scene_lease_sha256=H["f"],
        captured_at_epoch_ms=T0, evaluated_at_epoch_ms=T0 + 2_000,
        expires_at_epoch_ms=T0 + 10_000)
    values.update(changes)
    return MotionEvidenceV2(**values)


def _qualification(context, **changes):
    values = dict(qualification_sha256=H["f"],
        model_id="keyboard-pose-net-robust-v0", model_sha256=H["c"],
        evidence_method_sha256=H["a"], domain_id="static-overhead-keyboard-v1",
        target_catalog_sha256=context.targets.content_sha256,
        bound_type=UncertaintyBoundType.PLANAR_L2_DISK, error_bound_mm=1.0,
        coverage_probability=0.99, target_ids=("H", "I"))
    values.update(changes)
    return TrustedLocalizationQualificationV2(**values)


def _proposal(context, target_id, index, **changes):
    center = context.targets.resolve("keyboard", target_id).center
    values = dict(proposal_id=f"batch-001-action-{index}", action_index=index,
        device=ProposalDevice.KEYBOARD, target_id=target_id,
        target=Point3Mm("board", center.x, center.y, center.z),
        interaction=Interaction.CONTACT, observation_confidence=0.95)
    values.update(changes)
    return ModelMotionProposalV2(**values)


def _batch(context, **changes):
    plan = changes.pop("plan", _plan())
    values = dict(batch_id="batch-001", request_id="request-001",
        intent_plan_sha256=plan.plan_hash, device=ProposalDevice.KEYBOARD,
        capability=MotionCapabilityV2("keyboard-development-v1", H["e"]),
        geometry=MotionGeometryV2("board_mm_xy_plane_v2", "mm", H["d"],
                                  H["e"], context.targets.content_sha256),
        evidence=_evidence(),
        uncertainty=MotionUncertaintyV2(UncertaintyBoundType.PLANAR_L2_DISK,
            1.0, 0.99, H["f"], H["a"], "static-overhead-keyboard-v1", ("H", "I")),
        proposals=(_proposal(context, "H", 0), _proposal(context, "I", 1)))
    values.update(changes)
    return ModelMotionBatchV2(**values)


def _regions(context, **changes):
    result = {}
    for target_id in ("H", "I"):
        target = context.targets.resolve("keyboard", target_id)
        left, front, right, rear = target.safe_rectangle_board_mm
        values = dict(target_id=target_id, coordinate_frame="board",
            coordinate_profile="board_mm_xy_plane_v2",
            board_frame_definition_sha256=H["d"],
            vertices_xy_mm=((left, front), (right, front), (right, rear), (left, rear)),
            surface_z_mm=target.center.z, surface_normal_error_bound_mm=0.1,
            placement_error_bound_mm=0.25, placement_observation_sha256=H["e"],
            target_catalog_sha256=context.targets.content_sha256)
        values.update(changes.get(target_id, {}))
        result[target_id] = MeasuredTargetRegionV2(**values)
    return result


def _ingest(batch, plan, context, **changes):
    values = dict(current_time_epoch_ms=T0 + 3_000, current_monotonic_ns=9_000_000_000,
        maximum_scene_age_ms=5_000, trusted_scene_lease_expires_at_epoch_ms=T0 + 10_000,
        expected_capability_profile_id="keyboard-development-v1",
        expected_capability_profile_sha256=H["e"],
        expected_capture_clock_domain_id="capture-clock-001",
        expected_camera_identity_sha256=H["b"], expected_scene_lease_id="lease-001",
        expected_scene_lease_issuer_id="capture-service-001",
        expected_scene_lease_sha256=H["f"], expected_scene_observation_sha256=H["b"],
        expected_precision_observation_sha256=H["c"],
        expected_fusion_decision_sha256=H["d"],
        expected_placement_observation_sha256=H["e"],
        expected_board_frame_definition_sha256=H["d"],
        trusted_qualification=_qualification(context), measured_target_regions=_regions(context))
    values.update(changes)
    return ingest_model_motion_batch_v2(batch, plan, context, **values)


def test_round_trip_and_admission_are_zero_authority():
    context, plan = load_simulation_context(WORKSPACE, MANIFEST), _plan()
    batch = _batch(context, plan=plan)
    decoded = decode_model_motion_batch_v2_json(json.dumps(batch.to_dict()).encode())
    report = _ingest(decoded, plan, context)
    assert decoded == batch
    assert report["ordered_target_ids"] == ["H", "I"]
    assert report["valid_until_monotonic_ns"] == 16_000_000_000
    assert report["admitted_actions"][0]["composed_planar_error_bound_mm"] == 1.25
    assert report["controller_commands"] == []
    assert report["hardware_access"] is report["physical_authority"] is False
    assert "speed_class" not in decoded.proposals[0].to_dict()


def test_strict_decoder_rejects_tamper_duplicate_and_authority():
    context = load_simulation_context(WORKSPACE, MANIFEST)
    document = _batch(context).to_dict(); document["request_id"] = "changed"
    with pytest.raises(ModelMotionBatchV2Error, match="batch_sha256"):
        ModelMotionBatchV2.from_mapping(document)
    payload = json.dumps(_batch(context).to_dict(), separators=(",", ":"))
    duplicate = payload.replace('"batch_id":"batch-001"',
                                '"batch_id":"batch-001","batch_id":"other"', 1)
    with pytest.raises(ModelMotionBatchV2Error, match="duplicate JSON"):
        decode_model_motion_batch_v2_json(duplicate.encode())
    authority = _batch(context).to_dict(); authority["hardware_access"] = True
    with pytest.raises(ModelMotionBatchV2Error, match="zero authority"):
        ModelMotionBatchV2.from_mapping(authority)


@pytest.mark.parametrize("now", [T0 - 1, T0 + 10_000])
def test_rejects_future_and_exact_expiry(now):
    context = load_simulation_context(WORKSPACE, MANIFEST)
    with pytest.raises(ModelMotionIngressV2Error, match="future-dated or expired"):
        _ingest(_batch(context), _plan(), context, current_time_epoch_ms=now)


def test_rejects_excess_age_and_untrusted_lease_extension():
    context = load_simulation_context(WORKSPACE, MANIFEST)
    with pytest.raises(ModelMotionIngressV2Error, match="maximum scene age"):
        _ingest(_batch(context), _plan(), context, maximum_scene_age_ms=2_000)
    with pytest.raises(ModelMotionIngressV2Error, match="trusted scene lease"):
        _ingest(_batch(context), _plan(), context,
                trusted_scene_lease_expires_at_epoch_ms=T0 + 9_000)


@pytest.mark.parametrize("field,value", [
    ("expected_capture_clock_domain_id", "other-clock"),
    ("expected_camera_identity_sha256", "1" * 64),
    ("expected_scene_lease_id", "other-lease"),
    ("expected_scene_lease_issuer_id", "other-issuer"),
    ("expected_scene_lease_sha256", "2" * 64),
    ("expected_precision_observation_sha256", "3" * 64)])
def test_rejects_independent_evidence_mismatch(field, value):
    context = load_simulation_context(WORKSPACE, MANIFEST)
    with pytest.raises(ModelMotionIngressV2Error, match="trusted evidence"):
        _ingest(_batch(context), _plan(), context, **{field: value})


def test_rejects_wrong_qualification_scope_or_model():
    context = load_simulation_context(WORKSPACE, MANIFEST)
    with pytest.raises(ModelMotionIngressV2Error, match="qualification"):
        _ingest(_batch(context), _plan(), context,
                trusted_qualification=_qualification(context, model_sha256="1" * 64))
    with pytest.raises(ModelMotionIngressV2Error, match="qualification"):
        _ingest(_batch(context), _plan(), context,
                trusted_qualification=_qualification(context, target_ids=("H",)))


def test_rejects_low_confidence_and_composed_disk_edge_crossing():
    context = load_simulation_context(WORKSPACE, MANIFEST)
    low = _batch(context, proposals=(_proposal(context, "H", 0,
        observation_confidence=0.4), _proposal(context, "I", 1)))
    with pytest.raises(ModelMotionIngressV2Error, match="confidence"):
        _ingest(low, _plan(), context)
    target = context.targets.resolve("keyboard", "H")
    left = target.safe_rectangle_board_mm[0]
    edge = _batch(context, proposals=(_proposal(context, "H", 0,
        target=Point3Mm("board", left + 1.1, target.center.y, target.center.z)),
        _proposal(context, "I", 1)))
    with pytest.raises(ModelMotionIngressV2Error, match="composed uncertainty"):
        _ingest(edge, _plan(), context)


def test_rejects_wrong_geometry_and_surface_plane():
    context = load_simulation_context(WORKSPACE, MANIFEST)
    with pytest.raises(ModelMotionIngressV2Error, match="region binding"):
        _ingest(_batch(context), _plan(), context,
                measured_target_regions=_regions(context,
                    H={"board_frame_definition_sha256": "1" * 64}))
    with pytest.raises(ModelMotionIngressV2Error, match="surface plane"):
        _ingest(_batch(context), _plan(), context,
                measured_target_regions=_regions(context,
                    H={"surface_normal_error_bound_mm": 0.6}))


def test_action_index_is_semantic_and_contiguous():
    context = load_simulation_context(WORKSPACE, MANIFEST)
    with pytest.raises(ModelMotionBatchV2Error, match="ordered and contiguous"):
        _batch(context, proposals=(_proposal(context, "H", 1),
                                   _proposal(context, "I", 0)))


def test_v1_and_v2_decoders_do_not_auto_upgrade_each_other():
    context = load_simulation_context(WORKSPACE, MANIFEST)
    v2 = json.dumps(_batch(context).to_dict()).encode()
    with pytest.raises(Exception):
        decode_model_motion_batch_json(v2)
    v1_fixture = WORKSPACE / "software/tests/fixtures/model_motion_batch_valid.json"
    if v1_fixture.exists():
        with pytest.raises(ModelMotionBatchV2Error):
            decode_model_motion_batch_v2_json(v1_fixture.read_bytes())


def test_preplanner_recheck_uses_monotonic_deadline_and_active_registry_hashes():
    context, plan = load_simulation_context(WORKSPACE, MANIFEST), _plan()
    ingress = _ingest(_batch(context, plan=plan), plan, context)
    values = dict(current_monotonic_ns=15_999_999_999,
        expected_capability_profile_sha256=H["e"],
        active_scene_lease_sha256=H["f"],
        active_placement_observation_sha256=H["e"],
        active_target_catalog_sha256=context.targets.content_sha256)
    gate = revalidate_model_motion_ingress_v2(ingress, **values)
    assert gate["status"] == "FRESH_FOR_DETERMINISTIC_PLANNING"
    assert gate["controller_commands"] == []
    with pytest.raises(ModelMotionIngressV2Error, match="expired before planning"):
        revalidate_model_motion_ingress_v2(
            ingress, **{**values, "current_monotonic_ns": 16_000_000_000})
    with pytest.raises(ModelMotionIngressV2Error, match="changed or revoked"):
        revalidate_model_motion_ingress_v2(
            ingress, **{**values, "active_placement_observation_sha256": "1" * 64})


def test_preplanner_recheck_rejects_tampered_ingress():
    context, plan = load_simulation_context(WORKSPACE, MANIFEST), _plan()
    ingress = _ingest(_batch(context, plan=plan), plan, context)
    ingress["request_id"] = "tampered"
    with pytest.raises(ModelMotionIngressV2Error, match="ingress_sha256"):
        revalidate_model_motion_ingress_v2(ingress,
            current_monotonic_ns=10_000_000_000,
            expected_capability_profile_sha256=H["e"],
            active_scene_lease_sha256=H["f"],
            active_placement_observation_sha256=H["e"],
            active_target_catalog_sha256=context.targets.content_sha256)
