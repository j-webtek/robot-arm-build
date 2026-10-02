from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pytest


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "eval"))

from diagnose_residual_obstruction_v3 import (  # noqa: E402
    _mixed_group_diagnostics,
    _single_label_diagnostics,
    load_model,
    pairwise_auc,
    probability_summary,
)


def test_pairwise_auc_and_probability_summary_are_exact():
    labels = np.asarray([0, 0, 1, 1], dtype=np.int8)
    probabilities = np.asarray([0.1, 0.2, 0.8, 0.9], dtype=np.float32)
    assert pairwise_auc(labels, probabilities) == 1.0
    assert probability_summary(probabilities) == {
        "minimum": pytest.approx(0.1),
        "mean": pytest.approx(0.5),
        "median": pytest.approx(0.5),
        "maximum": pytest.approx(0.9),
    }


def test_mixed_group_diagnostics_expose_negative_local_margin():
    labels = np.asarray([0, 1, 0, 1], dtype=np.int8)
    probabilities = np.asarray([0.8, 0.7, 0.1, 0.9], dtype=np.float32)
    rows = _mixed_group_diagnostics(
        labels, probabilities, ["bad", "bad", "good", "good"], "scene_id"
    )
    bad = next(row for row in rows if row["scene_id"] == "bad")
    good = next(row for row in rows if row["scene_id"] == "good")
    assert bad["locally_separable"] is False
    assert bad["separation_margin"] < 0
    assert good["locally_separable"] is True
    assert good["separation_margin"] > 0


def test_single_label_diagnostics_reject_mixed_identity_labels():
    labels = np.asarray([0, 1], dtype=np.int8)
    probabilities = np.asarray([0.1, 0.9], dtype=np.float32)
    with pytest.raises(ValueError, match="mixed labels"):
        _single_label_diagnostics(labels, probabilities, ["same", "same"], "variant_id")


def test_model_loader_rejects_wrong_hash_before_parsing(tmp_path):
    model = tmp_path / "model.bin"
    model.write_bytes(b"not-a-model")
    with pytest.raises(ValueError, match="model hash mismatch"):
        load_model(model, "0" * 64)
