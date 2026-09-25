"""Sequencing simulation tests: no hardware and no physical dynamics claims."""

import pytest
from rocell.motion.characterization_plan import freeze_campaign
from rocell.motion.characterization_sim import simulate_campaign
from test_characterization_plan import candidate


def test_deterministic_pair_returns_only_through_explicit_second_trial():
    plan=freeze_campaign(candidate())
    first=simulate_campaign(plan,travel_s=.5,sample_period_s=.05)
    assert first == simulate_campaign(plan,travel_s=.5,sample_period_s=.05)
    assert first['status']=='MODEL_COMPLETED'
    assert len(first['trial_results'])==2
    assert first['trial_results'][-1]['samples'][-1]['pose']['x_mm']==0
    assert first['checks']['full_link_collision']=='UNKNOWN'
    assert first['device_opens']==first['command_writes']==0
    assert not first['physical_ready']


@pytest.mark.parametrize('fault',['NO_RESPONSE','STALE','DISCONNECT','CANCELLED'])
def test_fault_never_executes_the_return(fault):
    result=simulate_campaign(freeze_campaign(candidate()),travel_s=.5,sample_period_s=.05,faults={'out':fault})
    assert result['status']=='STOPPED'
    assert result['skipped_trial_ids']==['back']
    assert len(result['trial_results'])==1
    assert not result['trial_results'][0]['observed_settling_verified']


def test_timeout_and_gap_fail_closed():
    plan=freeze_campaign(candidate())
    assert simulate_campaign(plan,travel_s=4,sample_period_s=.05)['trial_results'][0]['status']=='TIMEOUT'
    assert simulate_campaign(plan,travel_s=.5,sample_period_s=.2)['trial_results'][0]['status']=='GAP_POLICY_FAILED'


def test_speed_is_not_converted_into_physical_travel_time():
    data=candidate(); plan=freeze_campaign(data)
    data['trials'][0]['spd']=.08
    other=freeze_campaign(data)
    a=simulate_campaign(plan,travel_s=.5,sample_period_s=.05)
    b=simulate_campaign(other,travel_s=.5,sample_period_s=.05)
    assert a['trial_results'][0]['samples']==b['trial_results'][0]['samples']
    assert not b['speed_controls_model_duration']


def test_unknown_fault_and_unbounded_sample_work_rejected():
    plan=freeze_campaign(candidate())
    for faults in ({'missing':'STALE'},{'out':'typo'}):
        with pytest.raises(ValueError): simulate_campaign(plan,travel_s=.5,sample_period_s=.05,faults=faults)
    with pytest.raises(ValueError): simulate_campaign(plan,travel_s=.5,sample_period_s=1e-20)
    with pytest.raises(ValueError): simulate_campaign(plan,travel_s=.5,sample_period_s=5e-324)


@pytest.mark.parametrize('fault',['OVERSHOOT','DRIFT','DROPOUT','MALFORMED'])
def test_wire_faults_flow_through_real_analysis_and_stop_return(fault):
    result=simulate_campaign(freeze_campaign(candidate()),travel_s=.5,sample_period_s=.05,faults={'out':fault})
    assert result['status']=='STOPPED'
    assert result['skipped_trial_ids']==['back']
    evidence=result['trial_results'][0]['wire_evidence']
    assert evidence['analysis']['status']=='INSUFFICIENT_EVIDENCE'
    assert evidence['basis']=='SYNTHETIC_WIRE_REHEARSAL'
    if fault=='OVERSHOOT':
        assert evidence['analysis']['peak_observed_directional_overshoot_mm']==pytest.approx(.2)
    if fault=='MALFORMED':
        assert 'INVALID_OR_INCOMPLETE_POSE' in evidence['analysis']['issues']


def test_success_keeps_originals_for_reconstruction():
    import base64,hashlib
    result=simulate_campaign(freeze_campaign(candidate()),travel_s=.5,sample_period_s=.05)
    for trial in result['trial_results']:
        evidence=trial['wire_evidence']; raw=base64.b64decode(evidence['raw']['base64'])
        assert hashlib.sha256(raw).hexdigest()==evidence['raw']['sha256']
        assert len(raw)==evidence['raw']['bytes']
        assert evidence['analysis']['status']=='OBSERVED_SETTLING'
        assert not evidence['physical_authority']
