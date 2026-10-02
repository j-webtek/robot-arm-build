from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "software/integrations/isaac_sim/residual_obstruction_v4_2_isaac_probe.py"
SPEC = importlib.util.spec_from_file_location("v4_2_renderer", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
FIXTURE = ROOT / "software/ai/sim/evidence/residual_obstruction_successor_v4_2.json"


def test_v4_2_fixture_is_unconsumed_and_evaluation_absent() -> None:
    fixture, payload = MODULE.load_fixture(FIXTURE)
    assert payload
    assert fixture["schema"].endswith("v4_2")
    assert fixture["images_generated"] is False
    assert fixture["training_started"] is False
    assert fixture["evaluation_opened"] is False
    assert fixture["split_policy"]["evaluation_pairs_rendered"] == 0


def test_variant_overlap_admission_is_fail_closed() -> None:
    fixture, _ = MODULE.load_fixture(FIXTURE)
    MODULE.admit_variant_measurement(fixture, "cable_rubber", 0.55, 0.0)
    MODULE.admit_variant_measurement(fixture, "adjacent_left", 0.0, 0.0)
    with pytest.raises(RuntimeError, match="outside"):
        MODULE.admit_variant_measurement(fixture, "tool_matte_edge", 0.75, 0.0)
    with pytest.raises(RuntimeError, match="unexpectedly overlaps"):
        MODULE.admit_variant_measurement(fixture, "clear", 0.01, 0.0)
    with pytest.raises(RuntimeError, match="distractor overlaps"):
        MODULE.admit_variant_measurement(fixture, "adjacent_right", 0.0, 0.01)
