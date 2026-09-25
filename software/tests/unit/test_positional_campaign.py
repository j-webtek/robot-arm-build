import math
import pytest

from rocell.application.first_motion_contract import canonical
from rocell.motion.positional_campaign import PositionalCampaign, compile_wrist_campaign
from rocell.application.positional_campaign_rehearsal import (
    FAULTS, simulate_positional_campaign, verify_rehearsal_report,
)


@pytest.mark.parametrize('count',[2,4,8])
def test_finite_sequence_advances_only_after_verified_endpoint(count):
    plan = compile_wrist_campaign(leg_count=count)
    report = simulate_positional_campaign(plan)
    assert report['status'] == 'SIMULATION_COMPLETE'
    assert report['simulated_write_count'] == count
    assert report['physical_write_count'] == report['device_open_count'] == 0
    assert report['skipped_leg_ids'] == []
    assert all(leg['transitions'][-1] == 'LEG_COMMITTED' for leg in report['legs'])
    assert all(leg['incremental_matches_final'] for leg in report['legs'])
    assert verify_rehearsal_report(report)['valid']


def test_opposite_approaches_include_repositioning_to_same_absolute_target():
    body = compile_wrist_campaign('OPPOSITE_APPROACH',4).to_dict()
    assert [round(math.degrees(leg['target_rad'])) for leg in body['legs']] == [-4,0,4,0]
    assert body['legs'][1]['target_rad'] == body['legs'][3]['target_rad']
    assert body['legs'][1]['expected_start_rad'] < 0 < body['legs'][3]['expected_start_rad']


@pytest.mark.parametrize('fault',[f for f in FAULTS if f not in ('NONE','DIRECTIONAL_OFFSET')])
@pytest.mark.parametrize('leg_number',[1,2])
def test_fault_stops_all_later_simulated_commands(fault,leg_number):
    report = simulate_positional_campaign(compile_wrist_campaign(leg_count=4),
        fault=fault,fault_leg=leg_number)
    assert report['status'] == 'SIMULATION_HELD'
    assert report['legs'][-1]['leg_id'] == f'leg-{leg_number:02d}'
    assert report['simulated_write_count'] <= leg_number
    assert len(report['legs']) == leg_number
    assert report['skipped_leg_ids'] == [f'leg-{i:02d}' for i in range(leg_number+1,5)]
    assert report['physical_write_count'] == 0
    assert not report['unattended_release']
    assert verify_rehearsal_report(report)['valid']


def test_observed_negative_offset_holds_instead_of_compensating():
    report = simulate_positional_campaign(compile_wrist_campaign(leg_count=4),
        fault='DIRECTIONAL_OFFSET',fault_leg=2)
    assert report['simulated_write_count'] == 2
    assert report['legs'][-1]['endpoint']['status'] == 'TARGET_MISSED'
    assert report['legs'][-1]['endpoint']['final_error_rad'] == pytest.approx(math.radians(.957))
    assert report['skipped_leg_ids'] == ['leg-03','leg-04']


@pytest.mark.parametrize('fault,expected',[
    ('REVERSED_DIRECTION','WRIST_EXCURSION'),
    ('DELAYED_RESPONSE','NOT_SETTLED'),
    ('TIMESTAMP_REGRESSION','FEEDBACK_INVALID'),
    ('MISSING_JOINT','FEEDBACK_INVALID'),
    ('CPU_STALL','FEEDBACK_INVALID'),
    ('NO_SAMPLES','FEEDBACK_INVALID'),
])
def test_feedback_failures_have_explicit_machine_reasons(fault,expected):
    report = simulate_positional_campaign(compile_wrist_campaign(),fault=fault)
    assert report['legs'][0]['endpoint']['status'] == expected
    assert report['legs'][0]['incremental_matches_final']


def test_wizard_catalog_exposes_exact_closed_fault_set():
    from rocell.application.wizard_actions import ACTION_BY_ID
    action = ACTION_BY_ID['positional_campaign_rehearse']
    field = next(field for field in action.fields if field['name'] == 'fault')
    assert tuple(option['value'] for option in field['options']) == FAULTS


@pytest.mark.parametrize('fault',['mode','target','speed','joint','predecessor','id','limit','bool','extra','count'])
def test_invalid_or_expanded_contract_rejected(fault):
    body = compile_wrist_campaign().to_dict()
    if fault == 'mode': body['mode'] = 'UNATTENDED'
    if fault == 'target': body['legs'][0]['target_rad'] = math.radians(90)
    if fault == 'speed': body['legs'][0]['command']['spd'] = 100
    if fault == 'joint': body['legs'][0]['command']['joint'] = 1
    if fault == 'predecessor': body['legs'][1]['expected_start_rad'] = 0
    if fault == 'id': body['legs'][1]['leg_id'] = 'leg-01'
    if fault == 'limit': body['limits']['maximum_legs'] = 100
    if fault == 'bool': body['start_rad'] = False
    if fault == 'extra': body['approved'] = True
    if fault == 'count': body['legs'] = body['legs']*5
    with pytest.raises(ValueError): PositionalCampaign(canonical(body))


@pytest.mark.parametrize('field',['raw','endpoint','command','plan','order'])
def test_changed_retained_result_cannot_reconstruct(field):
    report = simulate_positional_campaign(compile_wrist_campaign())
    if field == 'raw': report['legs'][0]['post']['raw_base64'] = 'e30='
    if field == 'endpoint': report['legs'][0]['endpoint']['endpoint_verified'] = False
    if field == 'command': report['simulated_commands'][0]['command']['rad'] = 0
    if field == 'plan': report['plan']['mode'] = 'UNATTENDED'
    if field == 'order': report['legs'].reverse()
    with pytest.raises(ValueError): verify_rehearsal_report(report)


def test_plan_is_immutable_and_inputs_cannot_supply_backend():
    plan = compile_wrist_campaign()
    body = plan.to_dict()
    body['legs'].clear()
    assert len(plan.to_dict()['legs']) == 2
    with pytest.raises(TypeError): simulate_positional_campaign(plan,backend=object())
    with pytest.raises(ValueError): simulate_positional_campaign(body)
