"""The held-out two-goal review remains reproducible from exported records."""
from pathlib import Path

import pytest

from rocell.application.air_typing_r83_review import review, summarize


ROOT = Path(__file__).resolve().parents[2] / "runs/wizard-exports"


def test_raw_records_reproduce_two_goal_direction_prediction():
    report = review(ROOT)
    assert report["held_out_observed_elbow_positions"] == [2592, 2599, 2629, 2621, 2592, 2599, 2631, 2622]
    assert report["held_out_predicted_elbow_positions"] == [2592, 2599, 2629, 2622, 2592, 2599, 2629, 2622]
    assert report["held_out_prediction_errors_counts"] == [0, 0, 0, -1, 0, 0, 2, 0]
    assert report["held_out_prediction_mean_abs_error_counts"] == 0.375
    assert report["unadjusted_goal_mean_abs_error_counts"] == 5.625
    assert report["same_direction_repeatability_counts"] == {
        "2590_from_low": 0, "2590_from_high": 0,
        "2620_from_high": 2, "2620_from_low": 1,
    }
    assert report["general_compensation_supported"] is False


def test_two_goal_review_rejects_missing_records():
    with pytest.raises(ValueError, match="sixteen"):
        summarize([], {})
