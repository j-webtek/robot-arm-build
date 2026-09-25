import json
import pytest
from rocell.application.baseline_only_client import BaselineOnlyClient,run_baseline_only


class FakeClient:
    address='127.0.0.1';port=80
    def __init__(self,mode):self.mode=mode;self.posts=0;self.gets=0
    def request(self,body):
        self.posts+=1
        if self.mode=='lost':raise OSError('lost reply')
        return b'{"status":"BASELINE_QUEUED"}'
    def collect(self):
        self.gets+=1
        if self.mode=='collect':raise OSError('timeout')
        return json.dumps(dict(schema='rocell.baseline_only.v1',boot_id='boot',scan_id='scan',
            profile_id='waveshare-sms-sts-reference-b8b377642b3e',byte_order='little',
            complete=False,reason='BASELINE_READ_FAILED',reads=[])).encode()


@pytest.mark.parametrize('mode,status', [('lost','DELIVERY_UNCERTAIN'),
    ('collect','COLLECTION_INCONCLUSIVE'),('partial','INCONCLUSIVE')])
def test_export_and_persistent_no_retry(tmp_path,mode,status):
    claims=tmp_path/'claims';claims.mkdir(); client=FakeClient(mode)
    result=run_baseline_only(client,boot_id='boot',scan_id='scan',claim_root=claims,export_root=tmp_path/'exports')
    assert result['status']==status and client.posts==1 and not result['retry_allowed']
    replacement=FakeClient(mode)
    with pytest.raises(Exception):
        run_baseline_only(replacement,boot_id='boot',scan_id='different',claim_root=claims,export_root=tmp_path/'exports')
    assert replacement.posts==0


def test_transport_wire_and_consumed_attempt(monkeypatch):
    from rocell.application import baseline_only_client as module
    sent=[]
    class Connection:
        def __init__(self,*args):
            body=b'{"status":"BASELINE_QUEUED"}'
            self.response=bytearray(b'HTTP/1.0 202 Accepted\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body)
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def settimeout(self,value):assert 0<value<=10
        def connect(self,address):assert address==('127.0.0.1',80)
        def sendall(self,data):sent.append(data)
        def recv(self,count):
            data=bytes(self.response[:count]);del self.response[:count];return data
    monkeypatch.setattr(module.socket,'socket',Connection)
    client=BaselineOnlyClient('127.0.0.1')
    body=b'{"boot_id":"boot","scan_id":"scan"}'
    assert client.request(body)==b'{"status":"BASELINE_QUEUED"}'
    assert sent[0].startswith(b'POST /rocell/diagnostics/baseline HTTP/1.0')
    assert sent[0].endswith(body)
    with pytest.raises(ValueError):client.request(body)
    assert len(sent)==1


def test_result_export_failure_keeps_claim(tmp_path,monkeypatch):
    from rocell.application import baseline_only_client as module
    original=module.WizardDiagnosticExporter.export
    calls=[]
    def export(self,*args,**kwargs):
        calls.append(1)
        if len(calls)==2:raise OSError('injected output failure')
        return original(self,*args,**kwargs)
    monkeypatch.setattr(module.WizardDiagnosticExporter,'export',export)
    claims=tmp_path/'claims';claims.mkdir();client=FakeClient('partial')
    with pytest.raises(OSError):
        run_baseline_only(client,boot_id='boot',scan_id='scan',claim_root=claims,export_root=tmp_path/'exports')
    assert client.posts==1 and len(list(claims.iterdir()))==1


def test_complete_capture_is_not_motion_authority(tmp_path):
    client=FakeClient('partial')
    rows=[]
    for index in range(7):
        rows.append([[index*2,100+index*4,101+index*4,2,0,True,'0008'],
                     [index*2+1,102+index*4,103+index*4,15,0,True,'0008'+'00'*13]])
    client.collect=lambda:json.dumps(dict(schema='rocell.baseline_only.v1',boot_id='boot',scan_id='scan',
        profile_id='waveshare-sms-sts-reference-b8b377642b3e',byte_order='little',
        complete=True,reason='BASELINE_CAPTURED',reads=rows)).encode()
    claims=tmp_path/'claims';claims.mkdir()
    result=run_baseline_only(client,boot_id='boot',scan_id='scan',claim_root=claims,export_root=tmp_path/'exports')
    assert result['status']=='BASELINE_CAPTURED'
    assert not result['assessment']['progression_authority']


@pytest.mark.parametrize('response', [
    b'',
    b'HTTP/1.0 302 Found\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}',
    b'HTTP/1.0 202 Accepted\r\nContent-Type: application/json\r\nContent-Length: 300\r\n\r\n{}',
    b'HTTP/1.0 202 Accepted\r\nContent-Type: application/json\r\nContent-Length: 2\r\nContent-Length: 2\r\n\r\n{}',
    b'HTTP/1.0 202 Accepted\r\nContent-Type: application/json\r\nContent-Length: 20\r\n\r\n{}',
    b'HTTP/1.0 202 Accepted\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}',
])
def test_transport_rejection_never_resends_or_collects(monkeypatch,response):
    from rocell.application import baseline_only_client as module
    calls=[]
    class Connection:
        def __init__(self,*args):self.raw=bytearray(response);calls.append('connect-object')
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def settimeout(self,value):pass
        def connect(self,address):pass
        def sendall(self,data):calls.append('send')
        def recv(self,count):
            data=bytes(self.raw[:count]);del self.raw[:count];return data
    monkeypatch.setattr(module.socket,'socket',Connection)
    client=BaselineOnlyClient('127.0.0.1')
    body=b'{"boot_id":"boot","scan_id":"scan"}'
    with pytest.raises(ValueError):client.request(body)
    with pytest.raises(ValueError):client.request(body)
    with pytest.raises(ValueError):client.collect()
    assert calls==['connect-object','send']


def test_collection_failure_is_not_retried(monkeypatch):
    client=BaselineOnlyClient('127.0.0.1');calls=[]
    def exchange(method,*args):
        calls.append(method)
        if method=='POST':return b'{"status":"BASELINE_QUEUED"}'
        raise OSError('simulated lost GET')
    monkeypatch.setattr(client,'_exchange',exchange)
    client.request(b'{"boot_id":"boot","scan_id":"scan"}')
    with pytest.raises(OSError):client.collect()
    with pytest.raises(ValueError):client.collect()
    assert calls==['POST','GET']
