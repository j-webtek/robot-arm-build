from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest
from jsonschema import Draft202012Validator


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

from eval.evaluate_physical_camera_localization import (  # noqa: E402
    PLAN_SCHEMA_PATH,
    RESULT_SCHEMA_PATH,
    TRUTH_SCHEMA_PATH,
    evaluate,
)
from eval.preflight_physical_camera_campaign import (  # noqa: E402
    canonical_hash,
    load_strict_json,
    preflight,
)
from test_physical_camera_localization_campaign import _campaign  # noqa: E402


TARGETS = {"H": [10.0, 10.0], "I": [20.0, 20.0]}
UNSAFE = {"arm_occlusion", "tool_occlusion", "cable_occlusion", "device_absent"}


def _rewrite_truth(root: Path, campaign: dict) -> None:
    for capture in campaign["calibration_captures"] + campaign["evaluation_captures"]:
        absent = "device_absent" in capture["conditions"]
        truth = {
            "schema": "rocell.physical_camera_localization_ground_truth.v1",
            "capture_id": capture["capture_id"],
            "device_present": not absent,
            "target_points_mm": {} if absent else TARGETS,
        }
        payload = json.dumps(truth, sort_keys=True, separators=(",", ":")).encode()
        path = root / capture["ground_truth"]["relative_path"]
        path.write_bytes(payload)
        capture["ground_truth"]["size_bytes"] = len(payload)
        capture["ground_truth"]["sha256"] = hashlib.sha256(payload).hexdigest()
    campaign["campaign_sha256"] = canonical_hash(
        {key: value for key, value in campaign.items() if key != "campaign_sha256"}
    )


def _prediction(capture: dict, *, error: float = 0.5, force_accept: bool = False) -> dict:
    unsafe = bool(set(capture["conditions"]) & UNSAFE)
    identity = {
        "image_sha256": capture["image"]["sha256"],
        "model_sha256": "2" * 64,
        "preprocessing_sha256": "3" * 64,
    }
    if unsafe and not force_accept:
        return {
            "capture_id": capture["capture_id"],
            **identity,
            "abstained": True,
            "abstain_reasons": ["unsafe_scene"],
            "target_points_mm": {},
        }
    return {
        "capture_id": capture["capture_id"],
        **identity,
        "abstained": False,
        "abstain_reasons": [],
        "target_points_mm": {
            target_id: [point[0] + error, point[1]] for target_id, point in TARGETS.items()
        },
    }


def _plan(campaign: dict, receipt: dict) -> dict:
    target_map = {
        "schema": "rocell.keyboard_target_safe_regions.v1",
        "coordinate_frame": "board",
        "targets": {
            target_id: {"center_mm": point, "safe_radius_mm": 2.0}
            for target_id, point in TARGETS.items()
        },
    }
    target_map["target_map_sha256"] = canonical_hash(target_map)
    campaign["keyboard_target_map_sha256"] = target_map["target_map_sha256"]
    campaign["campaign_sha256"] = canonical_hash(
        {key: value for key, value in campaign.items() if key != "campaign_sha256"}
    )
    plan = {
        "schema": "rocell.physical_camera_localization_evaluation_plan.v1",
        "plan_id": "physical-camera-evaluation-v1",
        "source_commit": "1" * 40,
        "campaign_sha256": campaign["campaign_sha256"],
        "preflight_receipt_sha256": receipt["receipt_sha256"],
        "model_id": "keyboard-pose-test-v1",
        "model_sha256": "2" * 64,
        "model_artifact_manifest_sha256": campaign["model_artifact_manifest_sha256"],
        "preprocessing_sha256": "3" * 64,
        "keyboard_target_map_sha256": campaign["keyboard_target_map_sha256"],
        "declared_coverage_probability": 0.99,
        "unsafe_conditions": sorted(UNSAFE),
        "keyboard_target_map": target_map,
        "additional_uncertainty": {
            "camera_to_board": {"bound_mm": 0.1, "evidence_sha256": "4" * 64},
            "board_to_robot": {"bound_mm": 0.1, "evidence_sha256": "5" * 64},
            "tracking_and_settling": {"bound_mm": 0.1, "evidence_sha256": "6" * 64},
            "tool_tip": {"bound_mm": 0.1, "evidence_sha256": "7" * 64},
        },
        "calibration_predictions": [
            _prediction(capture, error=1.0) for capture in campaign["calibration_captures"]
        ],
        "evaluation_predictions": [
            _prediction(capture) for capture in campaign["evaluation_captures"]
        ],
        "controller_start_authorized": False,
        "execution_authorized": False,
        "hardware_writes": 0,
        "physical_movements": 0,
    }
    plan["plan_sha256"] = canonical_hash(plan)
    return plan


def _write(path: Path, document: dict) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _rehash_plan(plan: dict) -> None:
    plan["plan_sha256"] = canonical_hash(
        {key: value for key, value in plan.items() if key != "plan_sha256"}
    )


@pytest.fixture(scope="module")
def evaluation_fixture(tmp_path_factory):
    root = tmp_path_factory.mktemp("physical-camera-evaluator")
    campaign = _campaign(root)
    _rewrite_truth(root, campaign)
    placeholder_path = _write(root / "campaign-evaluator.json", campaign)
    placeholder_receipt = preflight(placeholder_path, root)
    plan = _plan(campaign, placeholder_receipt)
    campaign_path = _write(root / "campaign-evaluator.json", campaign)
    receipt = preflight(campaign_path, root)
    receipt_path = _write(root / "preflight.json", receipt)
    plan["campaign_sha256"] = campaign["campaign_sha256"]
    plan["preflight_receipt_sha256"] = receipt["receipt_sha256"]
    _rehash_plan(plan)
    return root, campaign_path, receipt_path, campaign, receipt, plan


def _evaluate_variant(evaluation_fixture, tmp_path: Path, plan: dict):
    root, campaign_path, receipt_path, _, _, _ = evaluation_fixture
    _rehash_plan(plan)
    return evaluate(campaign_path, receipt_path, _write(tmp_path / "plan.json", plan), root)


def test_schemas_are_valid():
    for path in (PLAN_SCHEMA_PATH, RESULT_SCHEMA_PATH, TRUTH_SCHEMA_PATH):
        Draft202012Validator.check_schema(load_strict_json(path))


def test_good_held_out_result_recommends_but_installs_nothing(evaluation_fixture, tmp_path):
    plan = deepcopy(evaluation_fixture[-1])
    result = _evaluate_variant(evaluation_fixture, tmp_path, plan)
    assert result["status"] == "QUALIFICATION_RECOMMENDED"
    assert result["measured_coverage_probability"] == 1.0
    assert result["calibration_localization_bound_mm"] == 1.0
    assert result["composed_error_bound_mm"] == pytest.approx(1.4)
    assert result["unsafe_false_accept_count"] == 0
    assert result["criteria"] == {
        "calibration_has_zero_abstentions": True,
        "held_out_coverage_met": True,
        "unsafe_false_accepts_zero": True,
        "all_targets_have_metrics": True,
        "composed_bound_fits_all_safe_regions": True,
    }
    assert result["qualification_recommended"] is True
    assert result["qualification_installed"] is False
    assert result["physical_deployment_qualified"] is False
    assert result["model_motion_batch_emitted"] is False
    assert result["controller_started"] is False
    assert result["hardware_writes"] == 0
    assert result["physical_movements"] == 0
    core = {key: value for key, value in result.items() if key != "result_sha256"}
    assert result["result_sha256"] == canonical_hash(core)


def test_composed_bound_crossing_safe_region_blocks(evaluation_fixture, tmp_path):
    plan = deepcopy(evaluation_fixture[-1])
    plan["additional_uncertainty"]["tool_tip"]["bound_mm"] = 0.8
    result = _evaluate_variant(evaluation_fixture, tmp_path, plan)
    assert result["status"] == "QUALIFICATION_BLOCKED"
    assert result["safe_region_failure_target_ids"] == ["H", "I"]
    assert result["criteria"]["composed_bound_fits_all_safe_regions"] is False


def test_unsafe_scene_acceptance_blocks(evaluation_fixture, tmp_path):
    plan = deepcopy(evaluation_fixture[-1])
    campaign = evaluation_fixture[3]
    unsafe_index = next(
        index for index, capture in enumerate(campaign["evaluation_captures"])
        if set(capture["conditions"]) & UNSAFE
    )
    plan["evaluation_predictions"][unsafe_index] = _prediction(
        campaign["evaluation_captures"][unsafe_index], force_accept=True
    )
    result = _evaluate_variant(evaluation_fixture, tmp_path, plan)
    assert result["status"] == "QUALIFICATION_BLOCKED"
    assert result["unsafe_false_accept_count"] == 1
    assert result["criteria"]["unsafe_false_accepts_zero"] is False


def test_held_out_uncovered_events_block(evaluation_fixture, tmp_path):
    plan = deepcopy(evaluation_fixture[-1])
    campaign = evaluation_fixture[3]
    changed = 0
    for index, capture in enumerate(campaign["evaluation_captures"]):
        if not (set(capture["conditions"]) & UNSAFE):
            plan["evaluation_predictions"][index] = _prediction(capture, error=2.0)
            changed += 1
            if changed == 3:
                break
    result = _evaluate_variant(evaluation_fixture, tmp_path, plan)
    assert result["measured_coverage_probability"] < 0.99
    assert result["criteria"]["held_out_coverage_met"] is False
    assert result["qualification_recommended"] is False


def test_prediction_coverage_and_preflight_identity_fail_closed(evaluation_fixture, tmp_path):
    plan = deepcopy(evaluation_fixture[-1])
    plan["evaluation_predictions"].pop()
    with pytest.raises(ValueError, match="schema validation failed|prediction coverage mismatch"):
        _evaluate_variant(evaluation_fixture, tmp_path, plan)

    root, campaign_path, receipt_path, _, receipt, original_plan = evaluation_fixture
    altered = deepcopy(receipt)
    altered["evaluation_capture_count"] += 1
    altered["receipt_sha256"] = canonical_hash(
        {key: value for key, value in altered.items() if key != "receipt_sha256"}
    )
    altered_path = _write(tmp_path / "altered-preflight.json", altered)
    plan = deepcopy(original_plan)
    plan["preflight_receipt_sha256"] = altered["receipt_sha256"]
    _rehash_plan(plan)
    with pytest.raises(ValueError, match="preflight receipt does not match"):
        evaluate(campaign_path, altered_path, _write(tmp_path / "altered-plan.json", plan), root)


def test_nonfinite_plan_number_is_rejected(evaluation_fixture, tmp_path):
    root, campaign_path, receipt_path, _, _, original_plan = evaluation_fixture
    plan = deepcopy(original_plan)
    plan["additional_uncertainty"]["tool_tip"]["bound_mm"] = float("nan")
    plan_path = tmp_path / "nonfinite.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite JSON number"):
        evaluate(campaign_path, receipt_path, plan_path, root)
