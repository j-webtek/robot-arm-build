"""Trusted admission and wizard routing without a connected controller."""
import time
from dataclasses import replace
import pytest
from rocell.application import wizard_held_pair as pair
from rocell.application.wizard_actions import WizardError
from test_arrival_wizard_service import make_service, _run, _ticket


@pytest.fixture
def binding(monkeypatch):
    state=dict(admit=True,key_calls=0,runs=0)
    source=dict(preparation_sha256='a'*64,preparation=dict(historical_anchor=2902,
        pair_plan=dict(boot_id='b'*32,offset_counts=6,tolerance_counts=2)))
    monkeypatch.setattr(pair,'replay_held_pair_preparation',lambda *args:source)
    def reader(subject):
        state['subject']=subject
        return dict(schema='rocell.held_pair_admission.v1',subject=subject,
            approval_reference='synthetic-approval',expires_ns=time.monotonic_ns()+5_000_000_000,
            installed_image_verified=True,pair_configuration_verified=True,
            powered_trial_approved=state['admit'],supported_and_clear=True,exclusive_controller=True)
    def key():state['key_calls']+=1;return b'k'*32
    def run(*args,**kwargs):
        state['runs']+=1
        assert kwargs['approved'] is True and not kwargs['cancelled']()
        return dict(export_path=str(args[0]/'synthetic-result'),
            report=dict(schema='rocell.held_pair_trial.v1',phase='CONTROLLER_REPORTED_PAIR_ARRIVAL',
                steps=[],retry_allowed=False,physical_tip_accuracy_verified=False))
    monkeypatch.setattr(pair,'run_admitted_pair',run)
    return pair.HeldPairWizardBinding('preparation','a'*64,'192.168.0.225',reader,key),state


def test_admission_then_key_and_run(binding,tmp_path):
    bound,state=binding
    result=pair.run_wizard_held_pair(bound,tmp_path,cancelled=lambda:False,
        deadline_ns=time.monotonic_ns()+10_000_000_000)
    assert state['key_calls']==state['runs']==1
    assert state['subject']['forward_target_count']==2908
    assert result['admission_export_id'].startswith('wizard-')


def test_r13_preview_and_admission_identify_selected_image(binding,tmp_path):
    from rocell.application.held_pair_installation_evidence import _profile
    bound,state=binding
    selected=replace(bound,app_sha256=_profile(13)[0])
    assert selected.preview(tmp_path)['app_sha256']==_profile(13)[0]
    pair.run_wizard_held_pair(selected,tmp_path,cancelled=lambda:False,
        deadline_ns=time.monotonic_ns()+10_000_000_000)
    assert state['subject']['app_sha256']==_profile(13)[0]
    with pytest.raises(ValueError):replace(bound,app_sha256='0'*64)


def test_r13_rejects_receipt_for_old_image_before_key(binding,tmp_path):
    from rocell.application.held_pair_installation_evidence import _profile
    bound,state=binding
    def stale(subject):
        receipt=bound.admission_reader(subject)
        receipt['subject']={**subject,'app_sha256':pair.R10_APP_SHA256}
        return receipt
    selected=replace(bound,app_sha256=_profile(13)[0],admission_reader=stale)
    with pytest.raises(ValueError):
        pair.run_wizard_held_pair(selected,tmp_path,cancelled=lambda:False,
            deadline_ns=time.monotonic_ns()+10_000_000_000)
    assert state['key_calls']==state['runs']==0


def test_denial_and_cancellation_never_load_key(binding,tmp_path):
    bound,state=binding;state['admit']=False
    for cancel in (False,True):
        with pytest.raises(ValueError):
            pair.run_wizard_held_pair(bound,tmp_path,cancelled=lambda:cancel,
                deadline_ns=time.monotonic_ns()+10_000_000_000)
    assert state['key_calls']==state['runs']==0


@pytest.mark.parametrize('fault',['subject','expired','image','configuration'])
def test_wrong_or_stale_admission_never_loads_key(binding,tmp_path,fault):
    bound,state=binding
    def reader(subject):
        receipt=bound.admission_reader(subject)
        if fault=='subject':receipt['subject']={**subject,'forward_target_count':3000}
        if fault=='expired':receipt['expires_ns']=0
        if fault=='image':receipt['installed_image_verified']=False
        if fault=='configuration':receipt['pair_configuration_verified']=False
        return receipt
    changed=replace(bound,admission_reader=reader)
    with pytest.raises(ValueError):
        pair.run_wizard_held_pair(changed,tmp_path,cancelled=lambda:False,
            deadline_ns=time.monotonic_ns()+10_000_000_000)
    assert state['key_calls']==state['runs']==0


def test_admission_export_failure_precedes_key(binding,tmp_path,monkeypatch):
    bound,state=binding
    def fail(*args,**kwargs):raise OSError('disk full')
    monkeypatch.setattr(pair.WizardDiagnosticExporter,'export',fail)
    with pytest.raises(OSError):
        pair.run_wizard_held_pair(bound,tmp_path,cancelled=lambda:False,
            deadline_ns=time.monotonic_ns()+10_000_000_000)
    assert state['key_calls']==state['runs']==0


def test_wizard_unbound_and_browser_overrides_blocked(make_service,binding):
    service,runner,_=make_service(mode='physical')
    with pytest.raises(WizardError):_ticket(service,'run_held_pair',dict(acknowledge=True))
    service._held_pair_binding=binding[0]
    for values in (dict(acknowledge=False),dict(acknowledge=True,address='192.168.0.1'),
                   dict(acknowledge=True,key='key'),dict(acknowledge=True,approved=True)):
        with pytest.raises(WizardError):_ticket(service,'run_held_pair',values)
    assert not runner.calls and binding[1]['key_calls']==0


def test_wizard_routes_once_and_publishes_owned_result(make_service,binding):
    service,runner,_=make_service(mode='physical');service._held_pair_binding=binding[0]
    ticket=_ticket(service,'run_held_pair',dict(acknowledge=True))
    assert '2908' in str(ticket['effects']) and binding[1]['runs']==0
    result=_run(service,'run_held_pair',dict(acknowledge=True))
    assert result['status']=='SUCCEEDED',result
    assert binding[1]['runs']==1 and not runner.calls
    with pytest.raises(WizardError):_ticket(service,'run_held_pair',dict(acknowledge=True))
    assert service.view()['arm']['status']=='NOT_CONNECTED'


def test_wizard_denial_consumes_attempt(make_service,binding):
    service,runner,_=make_service(mode='physical');service._held_pair_binding=binding[0]
    binding[1]['admit']=False
    result=_run(service,'run_held_pair',dict(acknowledge=True))
    assert result['status']=='FAILED'
    assert binding[1]['key_calls']==0 and not runner.calls
    with pytest.raises(WizardError):_ticket(service,'run_held_pair',dict(acknowledge=True))


def test_trial_result_rendering_is_not_tip_accuracy():
    from test_movement_campaign_ui import render
    operation=dict(action_id='run_held_pair',result=dict(export_path='trial-export',admission_export_id='admission',
        steps=[dict(report=dict(schema='rocell.held_pair_trial.v1',phase='STOPPED',
            reason='DELIVERY_NOT_ACCEPTED',retry_allowed=False,physical_tip_accuracy_verified=False,
            steps=[dict(stage='FORWARD_DELIVERY',export_id='delivery-export')]))]))
    page=render(operation)
    assert 'NOT QUALIFIED' in page and 'DELIVERY_NOT_ACCEPTED' in page and 'delivery-export' in page
    operation['result']['steps'][0]['report']['retry_allowed']=True
    assert 'no completion claim' in render(operation)
