import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
AI = ROOT / "software/ai"
sys.path.insert(0, str(AI))

from train.train_compact_metric_scaler import balanced_weights, corrected_metric
from vision.compact_metric_scaler import CompactMetricScaler, bounded_multiplier


def test_compact_scaler_has_three_parameters_and_bounded_output():
    model = CompactMetricScaler(np.zeros(2), np.ones(2))
    assert sum(parameter.numel() for parameter in model.parameters()) == 3
    raw = model(torch.tensor([[0.0, 0.0], [1.0, -1.0]]))
    multiplier = bounded_multiplier(raw, 0.5, 2.0)
    assert torch.all(multiplier >= 0.5)
    assert torch.all(multiplier <= 2.0)

    plan = {
        "minimum_multiplier": 0.5,
        "maximum_multiplier": 2.0,
        "minimum_bound_mm": 0.25,
        "maximum_bound_mm": 10.0,
    }
    corrected = corrected_metric(torch.tensor([0.1, 9.0]), raw, plan)
    assert torch.all(corrected >= 0.25)
    assert torch.all(corrected <= 10.0)


def test_balanced_weights_match_preregistered_objective():
    plan = json.loads((AI / "train/compact_metric_scaler_v1_plan.json").read_text())
    rows = [{"condition": condition} for condition in plan["conditions"]]
    weights = balanced_weights(
        rows, plan["condition_weights"], plan["tail_loss_fraction"]
    )
    expected_tail = np.array([1, 1, 2, 4], dtype=np.float32)
    expected = 0.75 + 0.25 * expected_tail / expected_tail.mean()
    np.testing.assert_allclose(weights, expected)
    assert np.isclose(weights.mean(), 1.0)
