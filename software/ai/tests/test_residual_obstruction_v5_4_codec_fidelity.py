from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "eval" / "evaluate_residual_v5_4_codec_fidelity.py"
SPEC = importlib.util.spec_from_file_location("codec_fidelity", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_yuy2_round_trip_preserves_shape_type_and_neutral_luma() -> None:
    source = np.full((8, 10, 3), 96, dtype=np.uint8)
    result = MODULE.yuy2_round_trip(source)
    assert result.shape == source.shape
    assert result.dtype == np.uint8
    assert np.max(np.abs(result.astype(np.int16) - source.astype(np.int16))) <= 1


def test_gate_requires_every_frozen_limit() -> None:
    limits = {
        "minimum_median_rgb_contrast_retention": 0.95,
        "minimum_q05_rgb_contrast_retention": 0.85,
        "minimum_every_row_rgb_contrast_retention": 0.60,
        "maximum_median_codec_distortion_to_signal": 0.05,
        "maximum_q95_codec_distortion_to_signal": 0.15,
        "maximum_every_row_codec_distortion_to_signal": 0.30,
        "minimum_q05_edge_contrast_retention": 0.80,
        "minimum_every_row_edge_contrast_retention": 0.50,
        "minimum_encoded_rgb_signal_when_raw_meets_floor_levels": 1.5,
    }
    summary = {
        "median_rgb_contrast_retention": 1.0,
        "q05_rgb_contrast_retention": 0.9,
        "minimum_rgb_contrast_retention": 0.7,
        "median_codec_distortion_to_signal": 0.01,
        "q95_codec_distortion_to_signal": 0.1,
        "maximum_codec_distortion_to_signal": 0.2,
        "q05_edge_contrast_retention": 0.9,
        "minimum_edge_contrast_retention": 0.6,
        "minimum_encoded_rgb_signal_when_raw_meets_floor": 1.6,
    }
    assert MODULE._gate(summary, limits)["status"] == "PASS"
    summary["minimum_edge_contrast_retention"] = 0.49
    result = MODULE._gate(summary, limits)
    assert result["status"] == "FAIL"
    assert result["checks"]["every_edge"] is False
