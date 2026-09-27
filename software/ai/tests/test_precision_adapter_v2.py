"""Precision adapter and zero-authority V2 producer contract tests."""

from dataclasses import replace
from pathlib import Path
import sys

import pytest

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src"), str(AI.parent / "tests/unit")]

import test_model_motion_ingress_v2 as arm
from rocell.models import ActionPlan, Device, PressKey, decode_model_motion_batch_v2_json
from rocell_ai.precision_adapter_v2 import (
    InstalledSyntheticQualificationV0,
    PoseModelOutputV2,
    adapt_pose_model_output,
)
from rocell_ai.precision_batch_producer_v2 import (
    PlacedTargetRegionMapV2,
    produce_model_motion_batch_v2,
)
from rocell_ai.scene_observation import canonical_hash

DOMAIN = "synthetic-controlled-keyboard-v1"
NOW = 1_800_000_000_000
H = {letter: letter * 64 for letter in "abcdef"}


def _output(*, model_sha256=H["a"], confidence=0.99, evaluated=NOW):
    return PoseModelOutputV2(
        model_id="keyboard-pose-model-v1",
        model_sha256=model_sha256,
        frame_id="frame-precision-001",
        image_sha256=H["b"],
        normalized_pose=(0.0, 0.0, 0.0),
        evaluated_at_epoch_ms=evaluated,
        observation_confidence=confidence,
    )


def _qualification(catalog_sha256, *, model_sha256=H["a"], domain=DOMAIN,
                   radius=1.0):
    core = {
        "schema": "rocell.ai_localization_qualification.v0",
        "scope": "SYNTHETIC_OFFLINE_ONLY",
        "model_sha256": model_sha256,
        "target_catalog_sha256": catalog_sha256,
        "calibration_dataset_sha256": H["c"],
        "evaluation_dataset_sha256": H["d"],
        "domain_id": domain,
        "coverage_probability": 0.99,
        "error_bound_mm": radius,
        "target_ids": ["H", "1", "PERIOD"],
    }
    return {**core, "qualification_sha256": canonical_hash(core)}


def _accepted(*, output=None, targets=("H", "H", "1", "PERIOD")):
    context = arm.load_simulation_context(arm.WORKSPACE, arm.MANIFEST)
    output = output or _output()
    qualification = _qualification(context.targets.content_sha256,
                                   model_sha256=output.model_sha256)
    installed = InstalledSyntheticQualificationV0(qualification, H["e"])
    result = adapt_pose_model_output(
        ROOT,
        output,
        domain_id=DOMAIN,
        required_target_ids=targets,
        trusted_qualifications={qualification["qualification_sha256"]: installed},
        expected_domain_id=DOMAIN,
        now_epoch_ms=NOW,
    )
    return context, result, qualification


def _producer_inputs(result):
    context = arm.load_simulation_context(arm.WORKSPACE, arm.MANIFEST)
    fixture = arm._batch(context)
    precision = result.precision_observation
    prediction = precision["prediction"]
    placement_sha256 = H["f"]
    regions = {}
    for target_id in dict.fromkeys(result.required_target_ids):
        x, y, _ = prediction["targets"][target_id]["center_board_mm"]
        regions[target_id] = (x - 2.0, y - 2.0, x + 2.0, y + 2.0)
    placed = PlacedTargetRegionMapV2(
        prediction["target_catalog_sha256"], placement_sha256, regions
    )
    geometry = replace(
        fixture.geometry,
        placement_observation_sha256=placement_sha256,
        target_catalog_sha256=prediction["target_catalog_sha256"],
    )
    evidence = replace(
        fixture.evidence,
        frame_id=prediction["frame_id"],
        image_sha256=prediction["image_sha256"],
        model_id=result.model_output.model_id,
        model_sha256=prediction["model_sha256"],
        precision_observation_sha256=precision["observation_sha256"],
        captured_at_epoch_ms=NOW - 100,
        evaluated_at_epoch_ms=NOW,
        expires_at_epoch_ms=NOW + 1_000,
    )
    plan = ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id="keyboard-development-v1",
        text="hh1.",
        actions=tuple(PressKey(target) for target in result.required_target_ids),
        required_calibrations=("keyboard_pose", "keyboard_tcp"),
    )
    return fixture, plan, placed, geometry, evidence


def test_accepted_observation_and_actual_batch_preserve_punctuation_numbers_repeats():
    _, result, qualification = _accepted()
    assert result.accepted
    assert result.precision_observation["qualification_sha256"] == qualification["qualification_sha256"]
    fixture, plan, placed, geometry, evidence = _producer_inputs(result)
    payload = produce_model_motion_batch_v2(
        plan,
        adapter_result=result,
        batch_id="precision-adapter-fixture-v2",
        request_id="precision-adapter-request-v2",
        capability=fixture.capability,
        geometry=geometry,
        evidence=evidence,
        placed_targets=placed,
        now_epoch_ms=NOW,
    )
    batch = decode_model_motion_batch_v2_json(payload)
    assert [proposal.target_id for proposal in batch.proposals] == ["H", "H", "1", "PERIOD"]
    assert [proposal.action_index for proposal in batch.proposals] == [0, 1, 2, 3]
    assert batch.to_dict()["controller_commands"] == []
    assert batch.to_dict()["hardware_access"] is False
    assert batch.to_dict()["physical_authority"] is False


def test_missing_qualification_abstains_localization_uncalibrated():
    result = adapt_pose_model_output(
        ROOT, _output(), domain_id=DOMAIN, required_target_ids=("H",),
        trusted_qualifications={}, expected_domain_id=DOMAIN, now_epoch_ms=NOW,
    )
    assert not result.accepted
    assert result.precision_observation["abstain_reasons"] == ["localization_uncalibrated"]


def test_wrong_domain_and_altered_model_or_catalog_hash_abstain():
    context = arm.load_simulation_context(arm.WORKSPACE, arm.MANIFEST)
    qualification = _qualification(context.targets.content_sha256)
    installed = InstalledSyntheticQualificationV0(qualification, H["e"])
    registry = {qualification["qualification_sha256"]: installed}
    wrong_domain = adapt_pose_model_output(
        ROOT, _output(), domain_id=DOMAIN, required_target_ids=("H",),
        trusted_qualifications=registry, expected_domain_id="different-domain",
        now_epoch_ms=NOW,
    )
    altered_model = adapt_pose_model_output(
        ROOT, _output(model_sha256=H["f"]), domain_id=DOMAIN,
        required_target_ids=("H",), trusted_qualifications=registry,
        expected_domain_id=DOMAIN, now_epoch_ms=NOW,
    )
    altered_catalog = _qualification(H["f"])
    altered_catalog_registry = {
        altered_catalog["qualification_sha256"]:
            InstalledSyntheticQualificationV0(altered_catalog, H["e"])
    }
    catalog_result = adapt_pose_model_output(
        ROOT, _output(), domain_id=DOMAIN, required_target_ids=("H",),
        trusted_qualifications=altered_catalog_registry,
        expected_domain_id=DOMAIN, now_epoch_ms=NOW,
    )
    assert all(not value.accepted for value in (wrong_domain, altered_model, catalog_result))
    assert "localization_domain_unverified" in wrong_domain.diagnostics


def test_altered_qualification_hash_is_rejected():
    context = arm.load_simulation_context(arm.WORKSPACE, arm.MANIFEST)
    qualification = _qualification(context.targets.content_sha256)
    qualification["qualification_sha256"] = H["f"]
    with pytest.raises(ValueError, match="Qualification hash mismatch"):
        InstalledSyntheticQualificationV0(qualification, H["e"])


@pytest.mark.parametrize(
    "output, diagnostic",
    [
        (_output(confidence=0.2), "observation_confidence_below_threshold"),
        (_output(evaluated=NOW - 2_001), "precision_evidence_stale"),
    ],
)
def test_low_confidence_and_stale_evidence_abstain(output, diagnostic):
    _, result, _ = _accepted(output=output, targets=("H",))
    assert not result.accepted
    assert diagnostic in result.diagnostics
    assert result.precision_observation["abstain_reasons"] == ["localization_uncalibrated"]


def test_uncertainty_crossing_safe_region_abstains_batch():
    _, result, _ = _accepted(targets=("H",))
    fixture, plan, placed, geometry, evidence = _producer_inputs(result)
    x, y, _ = result.precision_observation["prediction"]["targets"]["H"]["center_board_mm"]
    crossing = PlacedTargetRegionMapV2(
        placed.target_catalog_sha256,
        placed.placement_observation_sha256,
        {"H": (x - 0.5, y - 0.5, x + 0.5, y + 0.5)},
    )
    assert produce_model_motion_batch_v2(
        plan,
        adapter_result=result,
        batch_id="precision-crossing-v2",
        request_id="precision-crossing-request-v2",
        capability=fixture.capability,
        geometry=geometry,
        evidence=evidence,
        placed_targets=crossing,
        now_epoch_ms=NOW,
    ) is None
