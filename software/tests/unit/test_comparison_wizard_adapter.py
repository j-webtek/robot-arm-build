import json
import pytest
from rocell.application.comparison_wizard_adapter import SessionJournal, WizardComparisonAdapter


def test_journal_exclusive_linked_and_change_detected(tmp_path):
    j=SessionJournal(tmp_path,'a'*32)
    with pytest.raises(Exception):SessionJournal(tmp_path,'a'*32)
    j(dict(session_id='a'*32,event='START'))
    j(dict(session_id='a'*32,event='FINISHED'))
    assert len(list(tmp_path.glob('*-000*.json')))==2
    first=next(tmp_path.glob('*-0000.json'))
    # Deliberate test tampering, not production publication.
    first.write_text('{}')
    with pytest.raises(ValueError):j(dict(session_id='a'*32,event='OTHER'))
    with pytest.raises(ValueError):j(dict(session_id='a'*32,event='OTHER'))


def test_publication_failure_poisoned(tmp_path,monkeypatch):
    j=SessionJournal(tmp_path,'b'*32)
    def fail(*a,**k):raise OSError('fault')
    monkeypatch.setattr('rocell.application.comparison_wizard_adapter.publish_reservation_bytes',fail)
    with pytest.raises(OSError):j(dict(session_id='b'*32,event='START'))
    with pytest.raises(ValueError):j(dict(session_id='b'*32,event='START'))


@pytest.mark.parametrize('fault',[None,'move','hold','exception','export','observer'])
def test_adapter_exports_and_shuts_down(tmp_path,fault):
    calls=[];exports=[]
    class Service:
        def __init__(self,*a,**k):pass
        def view(self):return dict(revision=1)
        def prepare_action(self,name,*a):calls.append(name);return dict(ticket_id=name)
        def execute_action(self,name):
            if fault=='exception' and name.startswith('run_'):raise ValueError('failure')
            return dict(operation_id=name)
        def operation(self,name):
            status='FAILED' if (fault=='move' and name.startswith('run_') or
                fault=='hold' and name.startswith('observe_') or fault=='export' and name=='export_logs') else 'SUCCEEDED'
            return dict(status=status,result=dict(receipt=dict(path=str(tmp_path))))
        def shutdown(self):calls.append('shutdown')
    def observer(path):
        exports.append(path)
        if fault=='observer':raise OSError('failure')
    a=WizardComparisonAdapter(tmp_path,service_factory=Service,export_observer=observer)
    if fault in ('exception','export','observer'):
        with pytest.raises(Exception):a('high')
    else:assert a('high')==tmp_path
    assert calls[-2:]==['export_logs','shutdown']
    assert calls.count('run_wifi_roll_high_trial')==1
    assert ('observe_arm_wifi_bounded' in calls)==(fault not in ('move','exception'))
    with pytest.raises(ValueError):a('arbitrary')
