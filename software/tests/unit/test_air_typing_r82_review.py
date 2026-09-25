"""Held-out cross-pose result remains reproducible from saved raw records."""
from pathlib import Path

import pytest

from rocell.application.air_typing_r82_review import review,summarize


ROOT=Path(__file__).resolve().parents[2]/"runs/wizard-exports"


def test_retained_raw_records_reproduce_cross_pose_prediction():
    report=review(ROOT)
    assert report["held_out_observed_elbow_positions"]==[2610,2619,2611,2619]
    assert report["held_out_predicted_elbow_positions"]==[2612,2619,2612,2619]
    assert report["held_out_prediction_errors_counts"]==[-2,0,-1,0]
    assert report["held_out_prediction_mean_abs_error_counts"]==0.75
    assert report["unadjusted_goal_mean_abs_error_counts"]==4.75
    assert report["general_compensation_supported"] is False


def test_cross_pose_review_rejects_missing_records():
    with pytest.raises(ValueError,match="Verified"):
        summarize([],{})
