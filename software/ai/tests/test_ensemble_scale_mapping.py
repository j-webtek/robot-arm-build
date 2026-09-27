import hashlib
import json
import sys
from pathlib import Path

import pytest

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path.insert(0, str(AI))

from evidence_artifacts import verify_frozen_artifacts
from train.select_ensemble_scale_mapping import (
    checks_pass,
    evaluate_checks,
    scaled_rows,
)
from vision.evaluate_ensemble_scaled_uncertainty import summarize
from vision.evaluate_grouped_uncertainty import calibrate


def test_power_mapping_is_monotonic_and_respects_floor():
    rows = [
        {"disagreement_mm": 0.5, "error_mm": 1.0, "seed": 1},
        {"disagreement_mm": 1.0, "error_mm": 1.0, "seed": 2},
        {"disagreement_mm": 2.0, "error_mm": 1.0, "seed": 3},
    ]
    mapped = scaled_rows(rows, 2.0, 1.0)
    assert [row["scale_mm"] for row in mapped] == pytest.approx([1.0, 1.0, 4.0])
    assert [row["error_mm"] for row in mapped] == [1.0, 1.0, 1.0]


def test_report_recounts_all_mappings_and_selects_nothing():
    plan_path = AI / "train/ensemble_scale_mapping_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report = json.loads((AI / "eval/ensemble_scale_mapping_v1_report.json").read_text())
    assert report["plan_sha256"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report["failed_confirmation_report_sha256"] == plan["file_sha256"][
        plan["failed_confirmation_report"]
    ]

    for cohort_name, (start, count) in plan["groups"].items():
        rows = report[cohort_name]["rows"]
        expected = {
            (seed, style, condition)
            for seed in range(start, start + count)
            for style in plan["styles"]
            for condition in plan["conditions"]
        }
        assert len(rows) == count * 2 * 4
        assert {(row["seed"], row["style"], row["condition"]) for row in rows} == expected

    calibration_rows = report["mapping_calibration"]["rows"]
    selection_rows = report["selection"]["rows"]
    start, count = plan["groups"]["mapping_calibration"]
    passing = []
    for power in plan["powers"]:
        name = f"power_{power:g}"
        result = report["results"][name]
        mapped_calibration = scaled_rows(
            calibration_rows, power, plan["scale_floor_mm"]
        )
        scene_scores = [
            {
                "seed": seed,
                "normalized_max": max(
                    row["error_mm"] / row["scale_mm"]
                    for row in mapped_calibration
                    if row["seed"] == seed
                ),
            }
            for seed in range(start, start + count)
        ]
        assert result["mapping_calibration_scene_scores"] == scene_scores
        rank, quantile = calibrate(
            [row["normalized_max"] for row in scene_scores], plan["alpha"]
        )
        assert result["rank"] == rank == 991
        assert result["normalized_quantile"] == pytest.approx(quantile)
        mapped_selection = scaled_rows(
            selection_rows, power, plan["scale_floor_mm"]
        )
        summary = summarize(mapped_selection, quantile, plan["tolerance_mm"])
        conditions = {
            condition: summarize(
                [row for row in mapped_selection if row["condition"] == condition],
                quantile,
                plan["tolerance_mm"],
            )
            for condition in plan["conditions"]
        }
        checks = evaluate_checks(summary, conditions, plan)
        assert result["selection_summary"] == summary
        assert result["selection_conditions"] == conditions
        assert result["checks"] == checks
        assert result["passed"] == checks_pass(checks)
        if result["passed"]:
            passing.append(name)

    assert passing == []
    assert report["selected_mapping"] is None
    assert not report["passed_selection"]
    assert report["calibration_fits"] == 5
    assert report["new_model_fits"] == report["optimizer_updates"] == 0
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]
