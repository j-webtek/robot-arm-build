"""Retained raw multi-joint hover records reproduce the repeatability result."""
from pathlib import Path

import pytest

from rocell.application.air_typing_r84_review import review, summarize


ROOT = Path(__file__).resolve().parents[2] / "runs/wizard-exports"


def test_raw_multi_hover_records_reproduce_result():
    report = review(ROOT)
    assert report["lateral_first_positions"] == report["lateral_second_positions"]
    assert report["lateral_repeat_delta_counts"] == [0]*7
    assert report["a_repeat_delta_counts"] == [-1,1,0,0,0,0,0]
    assert report["maximum_repeat_difference_counts"] == 1
    assert report["all_endpoints_controller_verified"]
    assert report["physical_tip_accuracy_verified"] is False


def test_review_rejects_missing_records():
    with pytest.raises(ValueError,match="Five verified"):
        summarize([])
