import pytest

from rocell.application.characterization_report import render_batch_review


def test_readable_report_retains_scope_units_and_failures():
    summary = dict(schema='rocell.characterization_batch_review.v1',
                   basis='SYNTHETIC_ONLY', movement_authorized=False,
                   campaign_state='STOPPED',
                   grouped_endpoints=[dict(servo_id=12, target_counts=2397,
                       approach_direction=-1, speed=20, acceleration=1, samples=3,
                       mean_error_counts=9, max_absolute_error_counts=9,
                       endpoint_range_counts=0)],
                   excluded_legs=[dict(leg_id=4, reason='INCOMPLETE_OR_STOPPED')])
    text = render_batch_review(summary)
    assert 'Synthetic simulation only' in text
    assert 'encoder counts, not millimetres' in text
    assert '| 12 | 2397 | - | 20 | 1 | 3 | 9.000 | 9 | 0 |' in text
    assert 'Leg 4: INCOMPLETE_OR_STOPPED' in text


def test_reject_unknown_scope():
    with pytest.raises(ValueError):
        render_batch_review({'basis': 'LIVE'})
