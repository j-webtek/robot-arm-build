import math
import pytest
from test_wrist_correction_proposal import pair
from rocell.application.wrist_correction_preview import preview_wrist_correction, simulate_wrist_correction


def inputs():
    originals = [pair(1),pair(2)]
    body = originals[0][0].to_dict()
    samples = [dict(host_received_ns=1_000_000_000+i*50_000_000,
                    joints_rad=dict(body['draft']['expected_start_joints_rad'])) for i in range(5)]
    return originals, dict(samples=samples, now_ns=1_200_000_000, usb_identity=body['usb_identity'])


def test_preview_does_not_confuse_motor_and_nominal_targets():
    original, args = inputs()
    p = preview_wrist_correction(original,expected_basis='SYNTHETIC_WIRE_REHEARSAL',**args)
    assert p['nominal_endpoint_rad'] == 0
    assert p['candidate_command']['rad'] < 0
    assert not p['motion_authorized'] and not p['native_admission_implemented']


@pytest.mark.parametrize('fault',['stale','future','wrong_side','changed_joint','wrong_unit','delta'])
def test_bad_start_is_rejected(fault):
    originals,args = inputs()
    if fault == 'stale': args['now_ns'] += 3_000_000_000
    if fault == 'future': args['now_ns'] -= 1
    if fault == 'wrong_unit': args['usb_identity'] = {}
    if fault in ('wrong_side','changed_joint','delta'):
        for s in args['samples']:
            if fault=='wrong_side': s['joints_rad']['t']=-.01
            if fault=='changed_joint': s['joints_rad']['b']+=.1
            if fault=='delta': s['joints_rad']['t']=math.radians(4.2)
    with pytest.raises(ValueError):
        preview_wrist_correction(originals,expected_basis='SYNTHETIC_WIRE_REHEARSAL',**args)


def test_constant_bias_hypothesis_reaches_nominal_endpoint_in_simulation():
    originals,args=inputs()
    r=simulate_wrist_correction(originals,residual_bias_deg=.87,**args)
    assert r['endpoint']['status']=='REPORTED_SETTLED'
    assert abs(r['endpoint']['final_error_rad']) < math.radians(.01)
    assert r['serial_write_count']==0 and not r['motion_authorized']


def test_reaching_adjusted_motor_target_is_not_success_at_nominal_zero():
    originals,args=inputs()
    r=simulate_wrist_correction(originals,residual_bias_deg=0,**args)
    assert not r['endpoint']['endpoint_verified']
    assert r['endpoint']['status']=='WRIST_EXCURSION'


def test_transient_overshoot_does_not_disappear_when_final_recovers():
    originals,args=inputs()
    r=simulate_wrist_correction(originals,residual_bias_deg=.87,transient_overshoot_deg=-.7,**args)
    assert r['endpoint']['status']=='WRIST_EXCURSION'
    assert not r['automatic_next_command_allowed']


@pytest.mark.parametrize('bias',[True,float('nan'),float('inf'),11])
def test_invalid_bias_is_not_simulated(bias):
    originals,args=inputs()
    with pytest.raises(ValueError): simulate_wrist_correction(originals,residual_bias_deg=bias,**args)
