"""The feedback card preserves controller coordinates without implying calibration."""
import json
import pytest
from test_wizard_activity_ui import render, view, operation


@pytest.mark.parametrize('value', [0, None, 345.6206222])
def test_cartesian_display_distinguishes_zero_and_absent(value):
    report = dict(schema='rocell.arm_wifi_feedback.v1', status='SUCCEEDED', joints_rad=dict(b=0), controller_cartesian=dict(
        status='REPORTED_PARTIAL', values=dict(x=value), missing_fields=['y','z','tit']))
    op = operation(action_id='read_arm_wifi_feedback', result=dict(steps=[dict(report=report)]))
    result = render(view([op]), steps=[dict(load='op-0')], results={'op-0':op})
    text = json.dumps(result)
    for label in ('controller X (mm)', 'controller pitch (rad)', 'not verified',
                  'Missing Cartesian fields are not zero coordinates'):
        assert label in text
    assert ('unavailable' if value is None else str(value)) in text


@pytest.mark.parametrize('state,label',[(True,'ON'),(False,'OFF'),(None,'NOT REPORTED')])
def test_torque_status_distinguishes_missing_and_off(state,label):
    report=dict(schema='rocell.arm_wifi_feedback.v1',status='SUCCEEDED',servo_status=dict(
        torque_switches=dict(elbow=state),loads_raw=dict(elbow=65),voltage_v=None,
        missing_torque_switches=['base']))
    op=operation(action_id='read_arm_wifi_feedback',result=dict(steps=[dict(report=report)]))
    text=json.dumps(render(view([op]),steps=[dict(load='op-0')],results={'op-0':op}))
    assert 'reported elbow torque switch' in text and label in text
    assert 'not calibrated contact force' in text
