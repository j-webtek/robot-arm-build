"""Offline native-shaped export joins; all device work uses fake native APIs."""

from dataclasses import replace
import hashlib
import json
import os

import pytest

from rocell.application.endpoint_campaign_import import load_endpoint_observation, summarize_saved_endpoint_campaign
from rocell.application.endpoint_trial_contract import EndpointTrialRequest, _canonical
from rocell.arm.movement_campaign_analysis import summarize_endpoint_campaign
from rocell.motion.characterization_plan import freeze_campaign
from rocell.providers.windows.endpoint_result_publication import publish_endpoint_result
from rocell.providers.windows.endpoint_native_result import encode_result
from rocell.providers.windows.endpoint_native_wire import decode_request
from rocell.providers.windows.owned_worker_process import owned_request_wire
from rocell.application.physical_onboarding_durability import publish_bytes, PublicationMode
from test_endpoint_native_registration import registration
from test_endpoint_trial_execution import execute


def exported(tmp_path,monkeypatch,*,closed=True,invalid=False):
    reg,outer = registration(tmp_path)
    payload = json.loads(outer.payload_json)
    request = EndpointTrialRequest(_canonical(payload['endpoint_request']))
    attempt = request.to_dict()['attempt_id']
    if invalid:
        raw,_ = owned_request_wire(reg,outer,deadline_ns=outer.expires_at_ns)
        stdout=b'invalid retained output'
    else:
        execution,_ = execute(tmp_path,monkeypatch,request=request,
                              runtime_original=_canonical(payload['registration']))
        payload['launch_sha256']=hashlib.sha256((tmp_path/(attempt+'-endpoint-worker-launch.json')).read_bytes()).hexdigest()
        outer=replace(outer,payload_json=_canonical(payload))
        raw,_=owned_request_wire(reg,outer,deadline_ns=outer.expires_at_ns)
        claim=hashlib.sha256((tmp_path/(attempt+'-endpoint-worker-claimed.json')).read_bytes()).hexdigest()
        stdout=encode_result({'schema':'rocell.endpoint_native_child_result.v1',
            'claim_sha256':claim,'execution':execution,'physical_authority':False},decode_request(raw))
    output=tmp_path/'exports'
    output.mkdir()
    path,report=publish_endpoint_result(output,request_raw=raw,stdout=stdout,stderr=b'',
        owned_process_id=os.getpid(),returncode=0,process_tree_closed=closed,finished_ns=40_000_000_000)
    return output,attempt,freeze_campaign(request.to_dict()['campaign']),path,report


def test_native_result_reconstructs_endpoint_campaign_row(tmp_path,monkeypatch):
    root,attempt,plan,_,_=exported(tmp_path,monkeypatch)
    row=load_endpoint_observation(root,attempt,plan)
    assert row['outcome']=='OBSERVATION_COMPLETED'
    report=summarize_endpoint_campaign(plan,[row])
    assert report['trials'][0]['eligible_for_descriptive_comparison']
    assert report['trials'][0]['analysis']['status']=='OBSERVED_ENDPOINT_DWELL'
    assert report['groups'][0]['status']=='INSUFFICIENT_REPETITIONS'
    assert report['recommended_settings'] is None
    saved=summarize_saved_endpoint_campaign(root,plan,[attempt])
    assert saved['selected_attempt_ids']==[attempt]
    assert saved['trials']==report['trials']
    with pytest.raises(ValueError): summarize_saved_endpoint_campaign(root,plan,[attempt,attempt])


@pytest.mark.parametrize('invalid',[False,True])
def test_failed_parent_or_invalid_output_stays_ineligible(tmp_path,monkeypatch,invalid):
    root,attempt,plan,_,_=exported(tmp_path,monkeypatch,closed=False,invalid=invalid)
    row=load_endpoint_observation(root,attempt,plan)
    assert row['outcome']!='OBSERVATION_COMPLETED'
    assert not summarize_endpoint_campaign(plan,[row])['trials'][0]['eligible_for_descriptive_comparison']


@pytest.mark.parametrize('change',['path','digest','summary','campaign'])
def test_changed_original_association_refused(tmp_path,monkeypatch,change):
    root,attempt,plan,path,report=exported(tmp_path,monkeypatch)
    if change=='path': report['originals']['stdout.bin']['file']='../unrelated'
    if change=='digest': report['originals']['stderr.bin']['sha256']='f'*64
    if change=='summary': report['summary']['endpoint_observed']=False
    if change=='campaign':
        body=plan.to_dict()
        body['campaign_id']='different-campaign'
        plan=freeze_campaign(body)
    publish_bytes(root,path.name,_canonical(report),mode=PublicationMode.REPLACE)
    with pytest.raises(ValueError): load_endpoint_observation(root,attempt,plan)
