"""v21 native-shaped execution uses exact crossing-frame evidence, never repair."""
import hashlib
import base64
import json
import pytest
from test_roll_long_fixed_campaign import long_fixed_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_capture import exercise
from test_positional_campaign_native_export import bundle
from rocell.application.first_motion_contract import canonical
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from rocell.safety.positional_campaign_authority import (
    PositionalCampaignIntent, ROLL_FRAMED_SCHEMA, roll_long_fixed_configuration,
    fixed_campaign_limits)


def framed_body(direction=1):
    b=long_fixed_body(direction)
    p=roll_long_fixed_configuration('INCREASING' if direction==1 else 'DECREASING',framed=True)
    b.update(schema=ROLL_FRAMED_SCHEMA,roll_probe=p,limits=fixed_campaign_limits(ROLL_FRAMED_SCHEMA))
    b['references']['configuration_sha256']=hashlib.sha256(canonical(p)).hexdigest()
    PositionalCampaignIntent(canonical(b))
    return b


@pytest.mark.parametrize('direction',[-1,1])
@pytest.mark.parametrize('fragment_size',[None,37,79])
def test_framed_native_export_reproduces(tmp_path,monkeypatch,direction,fragment_size):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:framed_body(direction))
    root,name,_=bundle(tmp_path,monkeypatch,fragment_size=fragment_size)
    v=verify_native_retained_export(root,name)
    assert v['valid'] and v['reconstruction_consistent'] and v['endpoint_completion_consistent']
    proof=v['endpoint_diagnostics'][0]['cross_window_framing']
    assert not proof['crossing_frame_counted_as_post'] and not proof['motion_authorized']


@pytest.mark.parametrize('fault',['delayed','malformed','other_joint','miss','cancel'])
def test_framing_never_bypasses_endpoint_or_fault_hold(tmp_path,monkeypatch,fault):
    install(monkeypatch);b=framed_body()
    monkeypatch.setattr('test_positional_current_context.body',lambda:b)
    kernel,_,verdicts,_,result=exercise(tmp_path,monkeypatch,fragment_size=79,
        delayed_response_target_rad=b['legs'][0]['target_rad']+.001533981 if fault=='delayed' else None,
        failure=fault if fault in ('malformed','other_joint') else None,
        missed_leg=1 if fault=='miss' else None,cancel_after_write=fault=='cancel')
    assert len(kernel.writes)==1 and result['status']!='REPORTED_CAMPAIGN_COMPLETE'
    assert result['cleanup']['all_handles_closed']
    if fault=='delayed':
        assert verdicts[-1]['endpoint']['persistence']['status']=='REPORTED_ENDPOINT_CHANGED'
    if fault=='malformed':
        assert result['errors'][-1]['reason'] in (
            'POST_FEEDBACK_INVALID','CROSSING_FRAME_NOT_VALID_POSE')


def test_v20_cannot_opt_in_by_configuration_substitution():
    b=framed_body();b['schema']='rocell.attended_positional_intent.v20'
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(b))


def test_late_change_export_reconstructs_hold_with_framing_proof(tmp_path,monkeypatch):
    install(monkeypatch);b=framed_body()
    monkeypatch.setattr('test_positional_current_context.body',lambda:b)
    root,name,_=bundle(tmp_path,monkeypatch,fragment_size=79,
        delayed_response_target_rad=b['legs'][0]['target_rad']+.001533981)
    v=verify_native_retained_export(root,name)
    assert v['valid'] and v['reconstruction_consistent']
    assert not v['endpoint_completion_consistent']
    row=v['endpoint_diagnostics'][0]
    assert row['persistence']['status']=='REPORTED_ENDPOINT_CHANGED'
    assert not row['reported_endpoint_verified']
    assert 'cross_window_framing' in row


def test_malformed_capture_exports_named_reason_without_endpoint_claim(tmp_path,monkeypatch):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',framed_body)
    root,name,report=bundle(tmp_path,monkeypatch,fragment_size=79,failure='malformed')
    v=verify_native_retained_export(root,name)
    assert v['valid'] and not v['reconstruction_consistent']
    assert not v['endpoint_completion_consistent'] and not v['endpoint_diagnostics']
    wrapper=json.loads((root/report['originals']['trial']['file']).read_bytes())
    trial=json.loads(base64.b64decode(wrapper['base64'],validate=True))
    assert trial['errors'][-1]['reason'] in (
        'POST_FEEDBACK_INVALID','CROSSING_FRAME_NOT_VALID_POSE')
    assert trial['native_submission_attempts']==1
