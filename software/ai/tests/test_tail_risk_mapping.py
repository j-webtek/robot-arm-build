import hashlib
import json
import sys
from pathlib import Path

import numpy as np

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path.insert(0, str(AI))

from evidence_artifacts import verify_frozen_artifacts
from train.select_ensemble_scale_mapping import evaluate_checks, checks_pass
from train.select_tail_risk_mapping import scaled_rows
from vision.evaluate_ensemble_scaled_uncertainty import summarize
from vision.evaluate_grouped_uncertainty import calibrate


def test_two_level_scale_assignment_is_bounded():
    rows = [
        {"tail_risk_score": -2.0},
        {"tail_risk_score": -1.0},
        {"tail_risk_score": 0.0},
    ]
    mapped = scaled_rows(rows, threshold=-1.0, high_scale_mm=10.0)
    assert [row["scale_mm"] for row in mapped] == [1.0, 1.0, 10.0]
    assert all("scale_mm" not in row for row in rows)


def test_report_recounts_all_mappings_and_preserves_failure():
    plan_path = AI / "train/tail_risk_mapping_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report = json.loads((AI / "eval/tail_risk_mapping_v1_report.json").read_text())

    assert report["plan_sha256"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report["risk_checkpoint_sha256"] == plan["file_sha256"][plan["risk_checkpoint"]]
    for name, (start, count) in plan["groups"].items():
        rows = report["cohorts"][name]["rows"]
        assert len(rows) == count * len(plan["styles"]) * len(plan["conditions"])
        assert {(row["seed"], row["style"], row["condition"]) for row in rows} == {
            (seed, style, condition)
            for seed in range(start, start + count)
            for style in plan["styles"]
            for condition in plan["conditions"]
        }

    calibration = report["cohorts"]["mapping_calibration"]["rows"]
    selection = report["cohorts"]["selection"]["rows"]
    start, count = plan["groups"]["mapping_calibration"]
    for fraction in plan["low_risk_fractions"]:
        result = report["results"][f"fraction_{fraction:g}"]
        threshold = float(
            np.quantile(
                [row["tail_risk_score"] for row in calibration],
                fraction,
                method="higher",
            )
        )
        assert result["risk_threshold"] == threshold
        mapped_calibration = scaled_rows(calibration, threshold, plan["high_scale_mm"])
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
        assert result["rank"] == rank
        assert result["normalized_quantile"] == quantile

        mapped_selection = scaled_rows(selection, threshold, plan["high_scale_mm"])
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
        assert not result["passed"]

    assert report["selected_mapping"] is None
    assert not report["passed_selection"]
    assert report["mapping_fits"] == 4
    assert report["new_model_fits"] == report["optimizer_updates"] == 0
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]
