import pytest

from rocell.application.park_step_plan import plan_first_park_step


BOOT = 'ab' * 16
EXPORT = 'wizard-20260921T222818692793Z-d7ac20b0fb0f4f0580935575a9cd35f6'
GOALS = [2047, 2389, 1725, 2907, 1589, 2040, 2047]
POSITIONS = [2047, 2390, 1724, 2904, 1591, 2041, 2047]


def evidence():
    reference = dict(schema='rocell.standard_start_encoder_reference.v1',
                     label='REFERENCE_A', encoder_reference_verified=True,
                     physical_park_verified=False,
                     safe_to_replay_without_fresh_capture=False,
                     joints=[dict(servo_id=11+i, goal=GOALS[i],
                                  position=POSITIONS[i], torque=1)
                             for i in range(7)])
    observation = dict(category='STABLE_SAMPLED_POSE', origin='DEVICE_CAPTURE',
                       joints=[dict(servo_id=11+i, last_goal=GOALS[i],
                                    last_position=POSITIONS[i], torque=1,
                                    controls_unchanged=True, position_span=0)
                               for i in range(7)])
    return reference, observation


def test_first_step_is_inert_and_bounded():
    reference, observation = evidence()
    plan = plan_first_park_step(reference, observation,
                                observation_boot=BOOT, observation_export_id=EXPORT)
    assert plan['target_servo_ids'] == [12, 13]
    assert plan['target_goals'] == [2377, 1737]
    assert plan['maximum_writes'] == 1
    assert plan['movement_authorized'] is False
    assert plan['firmware_support_installed'] is False
    assert plan['physical_clearance_verified'] is False


@pytest.mark.parametrize('change', [
    lambda r, o: o.update(origin='SIMULATION'),
    lambda r, o: o['joints'][1].update(last_goal=2388),
    lambda r, o: o['joints'][2].update(last_position=1720),
    lambda r, o: o['joints'][3].update(position_span=2),
    lambda r, o: o['joints'][3].update(position_span=-1),
    lambda r, o: o['joints'][4].update(torque=0),
    lambda r, o: o['joints'][4].update(torque=True),
    lambda r, o: o['joints'].pop(),
    lambda r, o: r['joints'][1].update(goal=2388),
    lambda r, o: r.update(physical_park_verified=True),
])
def test_rejects_wrong_or_drifting_start(change):
    reference, observation = evidence()
    change(reference, observation)
    with pytest.raises(ValueError):
        plan_first_park_step(reference, observation,
                             observation_boot=BOOT, observation_export_id=EXPORT)
