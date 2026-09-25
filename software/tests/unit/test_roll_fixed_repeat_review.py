"""The offline repeat comparison must reject mismatched experimental context."""
from copy import deepcopy
from pathlib import Path
import runpy

import pytest


review = runpy.run_path(str(Path(__file__).resolve().parents[2] /
                           'scripts/review_roll_fixed_repeat_20260915.py'))


def pair():
    left = dict(campaign_id='first', schema='rocell.attended_positional_intent.v17',
                start=[0, 0, 0, 0, .0015, 0], final=[0, 0, 0, 0, .0123, 0],
                command=dict(T=101, joint=5, rad=.016, spd=20, acc=1),
                endpoint=dict(direction='INCREASING'),
                references={key: 'same' for key in (
                    'configuration_sha256', 'native_controller_review_sha256',
                    'protocol_review_sha256', 'tool_payload_sha256',
                    'workcell_sha256', 'bounded_motion_risk_sha256', 'source_sha256')})
    right = deepcopy(left)
    right['campaign_id'] = 'second'
    return left, right


def test_matching_pair_reports_zero_spread_without_fitting():
    left, right = pair()
    result = review['compare_pair'](left, right)
    assert result['sample_count'] == 2 and result['reported_spread_deg'] == 0
    assert result['signed_errors_deg'][0] < 0


@pytest.mark.parametrize('change', ['duplicate', 'schema', 'start', 'target',
                                    'speed', 'protocol', 'payload', 'source'])
def test_unmatched_pair_is_not_scored(change):
    left, right = pair()
    if change == 'duplicate': right['campaign_id'] = left['campaign_id']
    elif change == 'schema': right['schema'] = 'rocell.attended_positional_intent.v16'
    elif change == 'start': right['start'][4] += .001
    elif change == 'target': right['command']['rad'] += .001
    elif change == 'speed': right['command']['spd'] = 10
    else:
        key = {'protocol': 'protocol_review_sha256', 'payload': 'tool_payload_sha256',
               'source': 'source_sha256'}[change]
        right['references'][key] = 'changed'
    with pytest.raises(ValueError): review['compare_pair'](left, right)
