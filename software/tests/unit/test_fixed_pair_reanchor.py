from copy import deepcopy

import pytest

from rocell.application import fixed_pair_reanchor as reanchor


def pose(goals=(2386, 1728), positions=(2390, 1725)):
    rows = []
    for servo_id in range(11, 18):
        selected = servo_id in (12, 13)
        index = servo_id-12
        rows.append(dict(servo_id=servo_id, last_goal=goals[index] if selected else 2000,
                         last_position=positions[index] if selected else 2000,
                         position_span=0, controls_unchanged=True, torque=1))
    return dict(category='STABLE_SAMPLED_POSE', origin='DEVICE_CAPTURE', joints=rows)


def test_plan_binds_verified_capture(monkeypatch):
    monkeypatch.setattr(reanchor, 'replay_pose_observation', lambda *a, **k:
        dict(replay_verified=True, assessment=pose(), raw_bundle_sha256='a'*64))
    plan = reanchor.plan_fixed_pair_reanchor('unused', 'capture-id')
    assert plan['source_goals'] == [2386, 1728]
    assert plan['target_goals'] == [2389, 1725]
    assert plan['maximum_writes'] == 1
    assert plan['movement_authorized'] is False


@pytest.mark.parametrize('change', [
    lambda p: p.update(category='FAULT'),
    lambda p: p.update(origin='SIMULATION'),
    lambda p: p['joints'][1].update(last_goal=2385),
    lambda p: p['joints'][1].update(last_position=2387),
    lambda p: p['joints'][2].update(position_span=2),
    lambda p: p['joints'][3].update(torque=0),
])
def test_plan_rejects_non_matching_or_unstable_capture(monkeypatch, change):
    measured = pose(); change(measured)
    monkeypatch.setattr(reanchor, 'replay_pose_observation', lambda *a, **k:
        dict(replay_verified=True, assessment=measured, raw_bundle_sha256='a'*64))
    with pytest.raises(ValueError):
        reanchor.plan_fixed_pair_reanchor('unused', 'capture-id')


def test_endpoint_requires_target_readback_and_neighbor_stability():
    before = pose()
    after = pose(goals=(2389, 1725), positions=(2391, 1724))
    plan = {'schema': 'rocell.fixed_pair_reanchor_plan.v1',
            'target_goals': [2389, 1725], 'expected_positions': [2391, 1724]}
    result = reanchor.verify_reanchor_endpoint(plan,
                                                before, after)
    assert result['status'] == 'GOAL_AND_ENDPOINT_VERIFIED'
    assert result['position_delta'] == [1, -1]
    for change in (
        lambda p: p['joints'][1].update(last_goal=2388),
        lambda p: p['joints'][1].update(last_position=2394),
        lambda p: p['joints'][4].update(last_position=2003),
        lambda p: p['joints'][4].update(last_goal=2001),
    ):
        altered = deepcopy(after); change(altered)
        with pytest.raises(ValueError):
            reanchor.verify_reanchor_endpoint(plan, before, altered)
