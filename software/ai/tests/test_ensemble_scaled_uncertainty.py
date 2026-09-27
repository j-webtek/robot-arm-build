import hashlib
import json
import sys
from pathlib import Path

import pytest

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path.insert(0, str(AI))

from evidence_artifacts import verify_frozen_artifacts
from vision.evaluate_ensemble_scaled_uncertainty import summarize
from vision.evaluate_grouped_uncertainty import calibrate


def test_summary_tracks_acceptance_coverage_and_tolerance_errors():
    rows = [
        {"seed": 1, "error_mm": 1.0, "scale_mm": 1.0},
        {"seed": 1, "error_mm": 3.2, "scale_mm": 1.0},
        {"seed": 2, "error_mm": 2.0, "scale_mm": 2.0},
    ]
    result = summarize(rows, 2.0, 3.0)
    assert result["scene_coverage"] == pytest.approx(0.5)
    assert result["image_coverage"] == pytest.approx(2 / 3)
    assert result["accepted_images"] == 2
    assert result["accepted_bound_violations"] == 1
    assert result["accepted_errors_over_tolerance"] == 1
    assert result["accepted_image_coverage"] == pytest.approx(0.5)


def test_report_lineage_population_recount_and_failed_confirmation():
    plan_path = AI / "eval/ensemble_scaled_uncertainty_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report = json.loads((AI / "eval/ensemble_scaled_uncertainty_v1_report.json").read_text())
    assert report["plan_sha256"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report["development_report_sha256"] == plan["file_sha256"][plan["development_report"]]

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
        assert all(
            row["scale_mm"]
            == pytest.approx(max(row["disagreement_mm"], plan["scale_floor_mm"]))
            for row in rows
        )

    calibration = report["calibration"]
    start, count = plan["groups"]["calibration"]
    expected_scores = [
        {
            "seed": seed,
            "normalized_max": max(
                row["error_mm"] / row["scale_mm"]
                for row in calibration["rows"]
                if row["seed"] == seed
            ),
        }
        for seed in range(start, start + count)
    ]
    assert calibration["scene_scores"] == expected_scores
    rank, quantile = calibrate(
        [row["normalized_max"] for row in expected_scores], plan["alpha"]
    )
    assert report["rank"] == rank == 991
    assert report["normalized_quantile"] == pytest.approx(quantile)

    confirmation = report["confirmation"]
    expected_summary = summarize(
        confirmation["rows"], quantile, plan["tolerance_mm"]
    )
    assert confirmation["summary"] == expected_summary
    expected_conditions = {
        condition: summarize(
            [row for row in confirmation["rows"] if row["condition"] == condition],
            quantile,
            plan["tolerance_mm"],
        )
        for condition in plan["conditions"]
    }
    assert confirmation["conditions"] == expected_conditions
    checks = {
        "overall_scene_coverage": expected_summary["scene_coverage"]
        >= plan["minimum_scene_coverage"],
        "overall_accepted_fraction": expected_summary["accepted_fraction"]
        >= plan["minimum_accepted_fraction"],
        "overall_accepted_image_coverage": expected_summary["accepted_image_coverage"]
        is not None
        and expected_summary["accepted_image_coverage"]
        >= plan["minimum_accepted_image_coverage"],
        "overall_accepted_scene_coverage": expected_summary["accepted_scene_coverage"]
        is not None
        and expected_summary["accepted_scene_coverage"]
        >= plan["minimum_accepted_scene_coverage"],
        "zero_accepted_errors_over_tolerance": expected_summary[
            "accepted_errors_over_tolerance"
        ]
        == 0,
        "condition_accepted_fraction": {
            condition: values["accepted_fraction"]
            >= plan["minimum_condition_accepted_fraction"]
            for condition, values in expected_conditions.items()
        },
        "condition_accepted_image_coverage": {
            condition: values["accepted_image_coverage"] is not None
            and values["accepted_image_coverage"]
            >= plan["minimum_accepted_image_coverage"]
            for condition, values in expected_conditions.items()
        },
    }
    assert report["checks"] == checks
    assert not report["passed"]
    assert report["calibration_fits"] == 1
    assert report["new_model_fits"] == report["optimizer_updates"] == 0
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]
