import json
import pytest
from rocell.providers.windows.arm_wifi_feedback import probe, MAC, PATH
from test_arrival_wizard_service import make_service, _run


class Connection:
    def __init__(self, data=None, status=200):
        self.raw=json.dumps(data if data is not None else dict(T=1051,b=0,s=0,e=1,t=0,r=0,g=3)).encode()
        self.status=status;self.requests=[];self.closed=False
    def request(self,*args,**kw):self.requests.append((args,kw))
    def getresponse(self):return self
    def read1(self,n):
        chunk,self.raw=self.raw[:n],self.raw[n:]
        return chunk
    def close(self):self.closed=True


def run(connection,**kwargs):
    return probe(identity=lambda:MAC,connection_factory=lambda *a,**k:connection,**kwargs)


def test_one_feedback_only_request_and_secret_filter():
    c=Connection(dict(T=1051,b=0,s=0,e=1,t=0,r=0,g=3,password='secret-value'))
    r=run(c)
    assert r['status']=='SUCCEEDED' and c.closed
    assert c.requests[0][0]==('GET',PATH) and len(c.requests)==1
    assert 'secret-value' not in json.dumps(r)
    assert r['motion_commands']==0 and not r['freshness_verified']


@pytest.mark.parametrize('fields,state,voltage',[
    ({},None,None),({'torswitchE':0,'v':1200},False,12),
    ({'torswitchE':1,'v':1210,'tE':65},True,12.1)])
def test_optional_servo_status_never_infers_missing_states(fields,state,voltage):
    report=run(Connection(dict(T=1051,b=0,s=0,e=1,t=0,r=0,g=3,**fields)))
    assert report['status']=='SUCCEEDED'
    servo=report['servo_status']
    assert servo['torque_switches']['elbow'] is state
    assert servo['voltage_v']==voltage
    assert ('elbow' in servo['missing_torque_switches']) == (state is None)
    assert servo['loads_raw']['elbow']==fields.get('tE')
    assert not servo['actuator_health_verified']


@pytest.mark.parametrize('fields,status,missing', [
    ({}, 'NOT_REPORTED', ['x','y','z','tit']),
    ({'x':0,'y':-1}, 'REPORTED_PARTIAL', ['z','tit']),
    ({'x':0,'y':1,'z':2,'tit':.3}, 'REPORTED_COMPLETE', [])])
def test_cartesian_coverage_preserves_absent_vs_zero(fields,status,missing):
    result = run(Connection(dict(T=1051,b=0,s=0,e=1,t=0,r=0,g=3,**fields)))
    cart = result['controller_cartesian']
    assert cart['status'] == status and cart['missing_fields'] == missing
    assert all(cart['values'][key] is None for key in missing)
    assert all(cart['values'][key] == value for key,value in fields.items())
    assert not cart['controller_model_correlation_verified']
    assert not cart['physical_accuracy_verified']


@pytest.mark.parametrize('status',[301,302,404,500])
def test_no_redirect_retry(status):
    c=Connection(status=status);r=run(c)
    assert r['status']=='FAILED' and len(c.requests)==1 and c.closed


@pytest.mark.parametrize('raw',[b'not-json',b'[]',b'x'*16385,
    b'{"T":1051,"b":NaN}',b'{"T":101}',b'{"password":"secret-value"}'])
def test_invalid_feedback_redacted(raw):
    c=Connection();c.raw=raw;r=run(c)
    assert r['status']=='FAILED' and c.closed
    assert 'secret-value' not in json.dumps(r)


def test_wrong_identity_or_cancel_prevents_request():
    for kw in (dict(identity=lambda:None),dict(identity=lambda:MAC,cancelled=lambda:True)):
        c=Connection()
        r=probe(connection_factory=lambda *a,**k:c,**kw)
        assert r['request_attempts']==0 and not c.requests


def test_identity_change_after_response_fails():
    identities=iter([MAC,None]);c=Connection()
    r=probe(identity=lambda:next(identities),connection_factory=lambda *a,**k:c)
    assert r['reason']=='IDENTITY_CHANGED' and 'joints_rad' not in r


def test_timeout_no_retry():
    c=Connection()
    def timeout():raise TimeoutError('secret-value')
    c.getresponse=timeout
    r=run(c)
    assert r['status']=='FAILED' and len(c.requests)==1 and c.closed
    assert 'secret-value' not in json.dumps(r)
    assert r['failure_phase']=='RESPONSE_HEADERS' and r['error_category']=='TIMEOUT'


def test_remote_disconnect_classified_without_exception_text():
    import http.client
    c=Connection()
    def disconnect():raise http.client.RemoteDisconnected('secret-value')
    c.getresponse=disconnect
    r=run(c)
    assert r['failure_phase']=='RESPONSE_HEADERS'
    assert r['error_category']=='REMOTE_DISCONNECTED'
    assert c.closed and len(c.requests)==1 and 'secret-value' not in json.dumps(r)


def test_wizard_retains_and_exports(make_service,monkeypatch):
    service,runner,_=make_service(mode='physical')
    c=Connection()
    monkeypatch.setattr('rocell.providers.windows.arm_wifi_feedback.probe',lambda **kw:run(c))
    result=_run(service,'read_arm_wifi_feedback')
    assert result['status']=='SUCCEEDED',result
    report=result['result']['steps'][0]['report']
    assert report['status']=='SUCCEEDED' and report['motion_commands']==0
    assert _run(service,'export_logs')['status']=='SUCCEEDED'
    assert not runner.calls


def test_preview_is_inert(make_service,monkeypatch):
    from test_arrival_wizard_service import _ticket
    calls=[]
    monkeypatch.setattr('rocell.providers.windows.arm_wifi_feedback.probe',lambda **kw:calls.append(kw))
    service,_,_=make_service(mode='physical')
    service.view()
    _ticket(service,'read_arm_wifi_feedback',{})
    assert calls==[]


def test_body_budget_and_cleanup_failure():
    c=Connection();ticks=iter([0,0,6,7])
    assert run(c,clock=lambda:next(ticks))['reason']=='BODY_TIME_BUDGET_EXCEEDED'
    c=Connection()
    def fail():raise RuntimeError('secret-value')
    c.close=fail
    r=run(c)
    assert r['status']=='FAILED' and r['reason']=='CLEANUP_FAILED'
