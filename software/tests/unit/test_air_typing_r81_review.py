"""Controller-count direction result is independently reproducible."""
from pathlib import Path

import pytest

from rocell.application.air_typing_r81_review import review, summarize


ROOT=Path(__file__).resolve().parents[2]/"runs/wizard-exports"


def test_retained_raw_records_reproduce_direction_effect():
    report=review(ROOT)
    assert report["first_cycle_arrival_prediction"]=={
        "from_low_elbow_position":2602,"from_high_elbow_position":2609}
    assert report["held_out_second_cycle_arrival"]==report["first_cycle_arrival_prediction"]
    assert report["first_cycle_high_minus_low_counts"]==7
    assert report["held_out_high_minus_low_counts"]==7
    assert report["general_compensation_supported"] is False


def test_review_requires_all_eight_records():
    with pytest.raises(ValueError,match="Eight"):
        summarize([])
