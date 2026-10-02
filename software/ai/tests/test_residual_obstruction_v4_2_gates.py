from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pytest


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "train"))
sys.path.insert(0, str(AI_ROOT / "eval"))
sys.path.insert(0, str(AI_ROOT.parent / "integrations/isaac_sim"))

from prepare_residual_obstruction_v4_2_gates import (  # noqa: E402
    _load_report,
    build_preparation,
    select_memorization_subset,
)
from run_residual_obstruction_v4_2_memorization import (  # noqa: E402
    normalize_pair,
    spatial_model,
)
from score_residual_obstruction_v4_2_baseline import (  # noqa: E402
    linear_q05,
    score_rows,
    select_normalization,
)
from residual_obstruction_v4_2_isaac_probe import normalization_difference_metrics  # noqa: E402


def rows() -> list[dict[str, object]]:
    output = []
    for decision in ("VISIBLE", "ABSTAIN"):
        for target in range(5):
            for index in range(12):
                output.append({
                    "split": "training",
                    "expected_decision": decision,
                    "device": "keyboard",
                    "target_id": f"K{target}",
                    "variant_id": "clear" if decision == "VISIBLE" else "cable_rubber",
                    "observation_id": f"{decision}:{target}:{index}",
                    "rgb_path": "rgb.jpg",
                    "rgb_sha256": f"{target:02x}{index:062x}",
                    "rgb_bytes": 1,
                    "reference_rgb_path": "reference.jpg",
                    "reference_rgb_sha256": f"{target + 10:02x}{index:062x}",
                    "reference_rgb_bytes": 1,
                    "shard_root": "root",
                })
    return output


def test_memorization_subset_is_deterministic_balanced_and_target_covering() -> None:
    first = select_memorization_subset(rows(), 50, 19201)
    second = select_memorization_subset(list(reversed(rows())), 50, 19201)
    assert [row["observation_id"] for row in first] == [row["observation_id"] for row in second]
    assert sum(row["expected_decision"] == "VISIBLE" for row in first) == 25
    assert sum(row["expected_decision"] == "ABSTAIN" for row in first) == 25
    assert {row["target_id"] for row in first} == {f"K{index}" for index in range(5)}


def test_preparation_freezes_gate_order_without_development_access() -> None:
    fixture = {
        "bundle_sha256": "fixture",
        "pretraining_gates": {
            "memorization_subset_count": 50,
            "memorization_accuracy_minimum": 0.995,
            "memorization_loss_maximum": 0.01,
        },
        "training_plan": {"seed": 19200},
    }
    result = build_preparation(fixture, {"report_sha256": "admission"}, rows())
    assert result["subset_count"] == 50
    assert result["visible_count"] == result["abstain_count"] == 25
    assert result["development_pixels_opened"] is False
    assert result["evaluation_opened"] is False
    assert result["gate_order"][:2] == [
        "COMPLETE_ADMISSION",
        "BOTH_NORMALIZATION_MEMORIZATION_RUNS",
    ]


def test_pair_normalization_reproduces_renderer_difference_metrics() -> None:
    rng = np.random.default_rng(5)
    reference = rng.integers(0, 256, size=(96, 96, 3), dtype=np.uint8)
    observation = rng.integers(0, 256, size=(96, 96, 3), dtype=np.uint8)
    expected = normalization_difference_metrics(reference, observation, np)
    self_pair = normalize_pair(reference, observation, "SELF_CROP_P05_P95")
    context_pair = normalize_pair(reference, observation, "REFERENCE_CONTEXT_WHITEPOINT")
    assert float(self_pair[6:].mean()) == pytest.approx(
        expected["self_crop_normalized_mean_absolute_difference"], abs=1e-7
    )
    assert float(context_pair[6:].mean()) == pytest.approx(
        expected["context_normalized_mean_absolute_difference"], abs=1e-7
    )


def test_spatial_model_preserves_six_by_six_map() -> None:
    torch = pytest.importorskip("torch")
    model = spatial_model(torch)
    assert model(torch.zeros(2, 9, 96, 96)).shape == (2, 1)
    assert any(isinstance(module, torch.nn.AvgPool2d) for module in model.modules())
    assert not any(isinstance(module, torch.nn.AdaptiveAvgPool2d) for module in model.modules())


def test_baseline_scoring_and_frozen_tie_break() -> None:
    development = []
    for target in ("A", "B"):
        for label, self_score, context_score in (
            ("VISIBLE", 0.1, 0.1),
            ("VISIBLE", 0.2, 0.2),
            ("ABSTAIN", 0.8, 0.8),
            ("ABSTAIN", 0.9, 0.9),
        ):
            development.append({
                "device": "keyboard",
                "target_id": target,
                "expected_decision": label,
                "difference_metrics": {
                    "self_crop_normalized_mean_absolute_difference": self_score,
                    "context_normalized_mean_absolute_difference": context_score,
                },
            })
    result = score_rows(development, "self_crop_normalized_mean_absolute_difference")
    assert result["pooled_auc"] == result["q05_per_target_auc"] == 1.0
    assert linear_q05([0.8, 1.0]) == pytest.approx(0.81)
    selected = select_normalization(
        {
            "SELF_CROP_P05_P95": {"q05_per_target_auc": 0.95},
            "REFERENCE_CONTEXT_WHITEPOINT": {"q05_per_target_auc": 0.954},
        },
        {"practical_tie_band_absolute_auc": 0.005, "tie_break_normalization_id": "SELF_CROP_P05_P95"},
    )
    assert selected == "SELF_CROP_P05_P95"


def test_report_loader_rejects_tampering(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"schema": "x", "value": 1, "report_sha256": "bad"}))
    with pytest.raises(ValueError, match="report hash mismatch"):
        _load_report(path, "x")
