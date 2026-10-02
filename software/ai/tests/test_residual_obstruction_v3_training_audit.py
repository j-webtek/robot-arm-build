from __future__ import annotations

from pathlib import Path
import sys

import numpy as np


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "eval"))

from audit_residual_obstruction_v3_training import (  # noqa: E402
    fit_identity_geometry_baseline,
    select_memorization_subset,
)


def test_identity_geometry_baseline_is_chance_when_every_target_has_same_base_rate():
    entries = []
    geometry = {
        "keyboard:A": [0.0, 0.0, 1.0, 7.0, 7.0, 0.0],
        "phone:key_a": [100.0, 50.0, 2.0, 3.0, 5.5, 1.0],
    }
    for device, target_id in (("keyboard", "A"), ("phone", "key_a")):
        for index in range(8):
            entries.append({
                "device": device,
                "target_id": target_id,
                "expected_decision": "VISIBLE" if index < 2 else "ABSTAIN",
            })
    result = fit_identity_geometry_baseline(entries, geometry)
    assert result["positive_rate"] == 0.75
    assert result["minimum_target_positive_rate"] == 0.75
    assert result["maximum_target_positive_rate"] == 0.75
    assert result["pooled_training_auc"] == 0.5
    assert result["minimum_probability"] == result["maximum_probability"]


def test_memorization_subset_is_deterministic_and_label_balanced():
    entries = [
        {
            "device": "keyboard",
            "target_id": f"K{index % 75}",
            "expected_decision": "VISIBLE" if index < 600 else "ABSTAIN",
            "observation_id": f"row-{index}",
        }
        for index in range(1200)
    ]
    first = select_memorization_subset(entries, 500, 19031)
    second = select_memorization_subset(entries, 500, 19031)
    assert np.array_equal(first, second)
    assert len(set(first.tolist())) == 500
    selected = [entries[index] for index in first]
    assert sum(row["expected_decision"] == "VISIBLE" for row in selected) == 250
    assert sum(row["expected_decision"] == "ABSTAIN" for row in selected) == 250
