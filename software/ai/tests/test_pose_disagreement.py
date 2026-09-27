import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path.insert(0, str(AI))

from evidence_artifacts import verify_frozen_artifacts
from train.compare_backbone_uncertainty import scene_metrics
from vision.audit_pose_disagreement import disagreement
from vision.synthetic_keyboard import catalog_for_workspace


def test_disagreement_is_zero_for_equal_pose_and_tracks_translation():
    targets = list(catalog_for_workspace(ROOT).keyboard_targets.values())
    center = np.asarray([0.0, 0.0, 0.0])
    assert disagreement(center, center, targets) == pytest.approx(0.0, abs=1e-12)
    shifted = np.asarray([1 / 30, 0.0, 0.0])
    assert disagreement(center, shifted, targets) == pytest.approx(1.0, abs=1e-12)
    rotated = np.asarray([0.0, 0.0, math.radians(1) / 0.2])
    assert disagreement(center, rotated, targets) > 0


def test_report_lineage_population_recount_and_failed_rule():
    path = AI / "eval/pose_disagreement_v1_plan.json"
    plan = json.loads(path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report = json.loads((AI / "eval/pose_disagreement_v1_report.json").read_text())
    source = json.loads((ROOT / plan["source_report"]).read_text())
    assert report["plan_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert report["source_report_sha256"] == plan["file_sha256"][plan["source_report"]]
    assert report["pixels_sha256"] == source["pixels_sha256"]
    assert report["candidate_error_recount_max_delta_mm"] <= plan["error_recount_tolerance_mm"]
    rows = report["rows"]
    expected = {
        (seed, style, condition)
        for seed in range(33000000, 33000600)
        for style in plan["styles"]
        for condition in plan["conditions"]
    }
    assert len(rows) == 4800
    assert {(row["seed"], row["style"], row["condition"]) for row in rows} == expected
    assert all(row["pose_disagreement_mm"] >= 0 for row in rows)
    fractions = plan["retention_fractions"]
    assert report["scene_ranking"]["pose_disagreement"] == scene_metrics(
        rows, "pose_disagreement_mm", fractions
    )
    assert report["scene_ranking"]["nonlinear_regression"] == scene_metrics(
        rows, "nonlinear_scale_mm", fractions
    )
    candidate = {p["requested_fraction"]: p for p in report["scene_ranking"]["pose_disagreement"]["retention_curve"]}
    reference = {p["requested_fraction"]: p for p in report["scene_ranking"]["nonlinear_regression"]["retention_curve"]}
    checks = {
        "scene_tail_auc": report["scene_ranking"]["pose_disagreement"]["tail_auc"]
        > report["scene_ranking"]["nonlinear_regression"]["tail_auc"],
        "retention_tail_rate_0_25": candidate[0.25]["tail_rate"] < reference[0.25]["tail_rate"],
        "retention_tail_rate_0_5": candidate[0.5]["tail_rate"] < reference[0.5]["tail_rate"],
    }
    assert report["checks"] == checks
    assert report["passed"] == all(checks.values())
    assert not report["passed"]
    assert report["new_fits"] == report["new_images"] == report["calibration_fits"] == 0
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]
