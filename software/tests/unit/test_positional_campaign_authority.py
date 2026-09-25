import json
import pytest

from rocell.application.first_motion_contract import canonical
from rocell.motion.positional_campaign import compile_wrist_campaign
from rocell.safety.positional_campaign_authority import (
    CHECKS,REFERENCES,PositionalCampaignIntent,PositionalCampaignReviewAuthority,fixed_campaign_limits,
)


def body():
    return dict(schema='rocell.attended_positional_intent.v1',mode='ATTENDED_TWO_LEG',
        session_id='wizard-'+'a'*32,campaign_id='campaign-'+'b'*32,
        usb_identity=dict(vid=0x10c4,pid=0xea60,serial_number='A'*32),
        references=dict.fromkeys(REFERENCES,'c'*64),issued_ns=1_000_000_000,
        deadline_ns=31_000_000_000,start_joints_rad=[0.]*6,
        legs=compile_wrist_campaign().to_dict()['legs'],limits=fixed_campaign_limits())


def review():
    return dict(operator_id='test-fixture-not-live-review',recorded_ns=1_000_000_000,
        checks=dict.fromkeys(CHECKS,True))


def test_bounded_attended_v2_uses_completion_risk_not_stop_qualification():
    from rocell.safety.positional_campaign_authority import BOUNDED_CHECKS
    value = body()
    value['schema'] = 'rocell.attended_positional_intent.v2'
    value['references']['bounded_motion_risk_sha256'] = value['references'].pop('stop_qualification_sha256')
    intent = PositionalCampaignIntent(canonical(value))
    authority = PositionalCampaignReviewAuthority(b'k'*32)
    reviewed = dict(review(), checks=dict.fromkeys(BOUNDED_CHECKS, True))
    raw = authority.seal(intent, reviewed, now_ns=value['issued_ns'])
    assert not verify(authority, raw, intent)['physical_truth_verified']
    with pytest.raises(ValueError): authority.seal(intent, review(), now_ns=value['issued_ns'])
    reviewed['checks']['accepted_goal_completion_risk_reviewed'] = False
    with pytest.raises(ValueError): authority.seal(intent, reviewed, now_ns=value['issued_ns'])
    value['mode'] = 'UNATTENDED'
    with pytest.raises(ValueError): PositionalCampaignIntent(canonical(value))


def verify(authority,raw,intent,**overrides):
    values=dict(intent=intent,current_usb_identity=intent.to_dict()['usb_identity'],
        current_references=intent.to_dict()['references'],now_ns=2_000_000_000)
    values.update(overrides)
    return authority.verify(raw,**values)


def test_association_is_authenticated_but_not_permission():
    intent = PositionalCampaignIntent(canonical(body()))
    authority = PositionalCampaignReviewAuthority(b'k'*32)
    raw = authority.seal(intent,review(),now_ns=1_000_000_000)
    result = verify(authority,raw,intent)
    assert not result['motion_authorized']
    assert not result['physical_truth_verified']
    assert result['intent_sha256'] == intent.sha256
    with pytest.raises(ValueError): verify(PositionalCampaignReviewAuthority(b'z'*32),raw,intent)


def test_campaign_key_is_derived_in_a_separate_host_domain():
    from rocell.safety.bench_review_authority import BenchReviewAuthority
    intent=PositionalCampaignIntent(canonical(body()))
    authority=BenchReviewAuthority(b'k'*32).for_positional_campaign()
    raw=authority.seal(intent,review(),now_ns=1_000_000_000)
    assert not verify(authority,raw,intent)['motion_authorized']
    with pytest.raises(ValueError): verify(PositionalCampaignReviewAuthority(b'k'*32),raw,intent)
    with pytest.raises(ValueError):
        verify(BenchReviewAuthority(b'z'*32).for_positional_campaign(),raw,intent)


@pytest.mark.parametrize('fault',['mode','identity','reference','start','bool','target','command',
    'predecessor','duplicate','extra_leg','limit','expiry','zero_hash'])
def test_unsafe_or_ambiguous_contract_rejected(fault):
    value=body()
    if fault=='mode': value['mode']='UNATTENDED'
    if fault=='identity': value['usb_identity']['vid']=False
    if fault=='reference': del value['references']['stop_qualification_sha256']
    if fault=='start': value['start_joints_rad'][3]=float('nan')
    if fault=='bool': value['legs'][0]['expected_start_rad']=False
    if fault=='target': value['legs'][0]['target_rad']=1.
    if fault=='command': value['legs'][0]['command']['spd']=100
    if fault=='predecessor': value['legs'][1]['expected_start_rad']=0.
    if fault=='duplicate': value['legs'][1]['leg_id']='leg-01'
    if fault=='extra_leg': value['legs'].append(value['legs'][1])
    if fault=='limit': value['limits']['maximum_writes']=3
    if fault=='expiry': value['deadline_ns']+=1
    if fault=='zero_hash': value['references']['workcell_sha256']='0'*64
    with pytest.raises(ValueError): PositionalCampaignIntent(canonical(value))


@pytest.mark.parametrize('fault',['checks','time','operator'])
def test_missing_or_invented_review_not_defaulted(fault):
    value=review()
    if fault=='checks': value['checks'].pop('stop_behavior_reviewed')
    if fault=='time': value['recorded_ns']=1
    if fault=='operator': value['operator_id']=''
    with pytest.raises(ValueError):
        PositionalCampaignReviewAuthority(b'k'*32).seal(PositionalCampaignIntent(canonical(body())),value,now_ns=1_000_000_000)


@pytest.mark.parametrize('fault',['target','review','mode','schema'])
def test_changed_signed_bytes_rejected(fault):
    intent=PositionalCampaignIntent(canonical(body()))
    authority=PositionalCampaignReviewAuthority(b'k'*32)
    value=json.loads(authority.seal(intent,review(),now_ns=1_000_000_000))
    if fault=='target': value['intent']['legs'][0]['target_rad']+=.001
    if fault=='review': value['review']['operator_id']='someone-else'
    if fault=='mode': value['intent']['mode']='UNATTENDED'
    if fault=='schema': value['schema']='rocell.observational_review_bundle.v1'
    with pytest.raises(ValueError): verify(authority,canonical(value),intent)


def test_current_context_and_deadline_must_still_match():
    intent=PositionalCampaignIntent(canonical(body()))
    authority=PositionalCampaignReviewAuthority(b'k'*32)
    raw=authority.seal(intent,review(),now_ns=1_000_000_000)
    for field in REFERENCES:
        refs=dict(intent.to_dict()['references'],**{field:'d'*64})
        with pytest.raises(ValueError): verify(authority,raw,intent,current_references=refs)
    with pytest.raises(ValueError): verify(authority,raw,intent,current_usb_identity={})
    with pytest.raises(ValueError): verify(authority,raw,intent,now_ns=31_000_000_000)
    with pytest.raises(ValueError): verify(authority,raw,intent,now_ns=1)
    with pytest.raises(ValueError): intent.require_start_time(8_000_000_000)
    with pytest.raises(ValueError): PositionalCampaignIntent(compile_wrist_campaign().canonical_bytes)
