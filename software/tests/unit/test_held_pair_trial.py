"""Execution-order tests with inert hardware seams and real durable exports."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application import held_pair_trial as trial


@pytest.fixture
def rig(monkeypatch, tmp_path):
    calls=[]
    state=dict(fault=None, cancel=False, waits=[])
    monkeypatch.setattr(trial, 'replay_held_pair_preparation', lambda *args:
        dict(preparation_sha256='a'*64, preparation=dict(pair_plan=dict(boot_id='b'*32),
            policy=dict(deadline_us=2000000,maximum_gap_us=500000))))
    def step(name):
        calls.append(name)
        if state['fault']==name:
            raise RuntimeError('sensitive adapter details must not reach export')
    def capabilities(**kwargs):
        step('capabilities')
        return dict(firmware_identity_verified=False)
    def challenge(root, **kwargs):
        leg='forward' if kwargs['operation']=='prepare' else 'return'
        step(leg+'_challenge')
        return dict(export_path=str(tmp_path/(leg+'-challenge')),
            report=dict(result=dict(category='CHALLENGE_RECEIVED')))
    def authorize(root, receipt, source, key, **kwargs):
        leg=kwargs['leg'];step(leg+'_authorize')
        assert source == ('preparation' if leg=='forward' else 'forward-observation')
        assert kwargs['forward_delivery_export_id'] == (None if leg=='forward' else 'forward-delivery')
        return dict(export_path=str(tmp_path/(leg+'-workflow')),
            authorization=SimpleNamespace(context_export_id=leg+'-context'))
    def deliver(root, authorization, **kwargs):
        leg=kwargs['leg'];step(leg+'_delivery')
        return dict(export_path=str(tmp_path/(leg+'-delivery')),
            report=dict(delivery=dict(result='DELIVERY_UNCERTAIN' if state.get('uncertain') else 'CONTROLLER_REPORTED_ACCEPTANCE')))
    def forward(*args, **kwargs):
        step('forward_observation')
        if state.get('cancel_after_forward'):state['cancel']=True
        return dict(export_path=str(tmp_path/'forward-observation'), assessment=dict(
            category=state.get('forward_category','CONTROLLER_REPORTED_ARRIVAL'),
            stable_status_observed=True,historical_anchor_matches=True,controller_state='AWAITING_EXPORT'))
    def reverse(*args, **kwargs):
        step('return_observation')
        return dict(export_path=str(tmp_path/'return-observation'),
            review=dict(category=state.get('return_category','CONTROLLER_REPORTED_PAIR_ARRIVAL')))
    for name, function in [('read_pair_capabilities',capabilities),('request_pair_challenge',challenge),
            ('authorize_pair_from_receipt',authorize),('send_authorized_pair',deliver),
            ('collect_authorized_pair_forward',forward),('collect_authorized_pair_return',reverse)]:
        monkeypatch.setattr(trial,name,function)
    def run(**kwargs):
        def pause(seconds):
            assert calls[-1] in ('forward_delivery','return_delivery')
            state['waits'].append(seconds)
            if state.get('cancel_during_wait'):state['cancel']=True
        return trial.run_admitted_pair(tmp_path,'preparation',address='192.168.0.225',
            key=b'k'*32,approved=kwargs.pop('approved',True),cancelled=lambda:state['cancel'],pause=pause,**kwargs)
    return run,calls,state


ORDER=['capabilities','forward_challenge','forward_authorize','forward_delivery',
       'forward_observation','return_challenge','return_authorize','return_delivery','return_observation']


def test_complete_and_duplicate_stops_before_hardware(rig):
    run,calls,state=rig
    result=run()
    assert calls==ORDER
    assert result['report']['phase']=='CONTROLLER_REPORTED_PAIR_ARRIVAL'
    assert len(result['report']['steps'])==8
    assert state['waits']==[5.5,5.5]
    with pytest.raises(Exception):run()
    assert calls==ORDER


@pytest.mark.parametrize('fault',ORDER)
def test_each_failure_prevents_next_operation(rig,fault):
    run,calls,state=rig;state['fault']=fault
    result=run()
    assert calls==ORDER[:ORDER.index(fault)+1]
    assert result['report']['phase']=='STOPPED'
    assert 'sensitive' not in str(result)


def test_uncertain_delivery_does_not_collect_or_return(rig):
    run,calls,state=rig;state['uncertain']=True
    assert run()['report']['reason']=='DELIVERY_NOT_ACCEPTED'
    assert calls==ORDER[:4]
    assert state['waits']==[]


def test_cancel_during_observation_wait_prevents_collection_and_return(rig):
    run,calls,state=rig;state['cancel_during_wait']=True
    assert run()['report']['reason']=='CANCELLED_BEFORE_NEXT_OPERATION'
    assert calls==ORDER[:4] and state['waits']==[5.5]


@pytest.mark.parametrize('category',['CONTROLLER_REPORTED_NON_ARRIVAL','INCONCLUSIVE'])
def test_nonarrival_does_not_request_return(rig,category):
    run,calls,state=rig;state['forward_category']=category
    assert run()['report']['reason']=='FORWARD_ENDPOINT_NOT_ELIGIBLE'
    assert calls==ORDER[:5]


def test_cancel_and_no_approval(rig):
    run,calls,state=rig
    with pytest.raises(ValueError):run(approved=False)
    assert calls==[]
    state['cancel']=True
    assert run()['report']['reason']=='CANCELLED_BEFORE_NEXT_OPERATION'
    assert calls==[]


def test_cancel_after_forward_leaves_return_unsent(rig):
    run,calls,state=rig;state['cancel_after_forward']=True
    assert run()['report']['reason']=='CANCELLED_BEFORE_NEXT_OPERATION'
    assert calls==ORDER[:5]


def test_return_nonarrival_is_not_success_or_retried(rig):
    run,calls,state=rig;state['return_category']='CONTROLLER_REPORTED_RETURN_NON_ARRIVAL'
    assert run()['report']['reason']=='RETURN_ENDPOINT_NOT_VERIFIED'
    assert calls==ORDER


def test_export_loss_after_forward_prevents_return(rig,monkeypatch):
    run,calls,state=rig
    original=trial.WizardDiagnosticExporter.export
    def export(self,*args,**kwargs):
        if calls and calls[-1]=='forward_observation':
            raise OSError('disk unavailable')
        return original(self,*args,**kwargs)
    monkeypatch.setattr(trial.WizardDiagnosticExporter,'export',export)
    with pytest.raises(OSError):run()
    assert calls==ORDER[:5]
