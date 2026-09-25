import socket

import pytest
from test_startup_command_contract import fixture, KEY
from test_servo_diagnostic_http import response
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_session_plan import SessionPlan
from rocell.application.startup_command_contract import freeze_startup_plan, sign_startup
from rocell.application.startup_prepared_start import StartupStartSender, send_prepared_startup
from rocell.application.servo_diagnostic_start_http import DiagnosticStartError, DiagnosticStartSender
from rocell.application.servo_prepared_start import send_prepared_start


def inputs():
    normal, policy, challenge = fixture()
    doc = normal.to_dict(); doc['origin'] = 'DEVICE_CAPTURE'
    normal = SessionPlan(canonical(doc))
    return freeze_startup_plan(normal, policy), policy, challenge, normal


def fake_socket(monkeypatch, *, lost=False):
    calls=[]; sent=[]
    class FakeSocket:
        def __init__(self,*args):
            calls.append('create')
            self.reply = b'' if lost else response(canonical(dict(accepted=True,retry_allowed=False)),status=b'202 Accepted')
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def settimeout(self,value):pass
        def connect(self,address):calls.append('connect')
        def sendall(self,data):calls.append('send');sent.append(data)
        def recv(self,count):
            raw,self.reply=self.reply[:count],self.reply[count:]
            return raw
    monkeypatch.setattr(socket,'socket',FakeSocket)
    return calls,sent


@pytest.mark.parametrize('lost',[False,True])
def test_exact_startup_send_claim_and_no_cross_mode_retry(tmp_path,monkeypatch,lost):
    calls,sent=fake_socket(monkeypatch,lost=lost)
    plan,policy,challenge,normal=inputs()
    sender=StartupStartSender('127.0.0.1',8081,policy)
    report=send_prepared_startup(tmp_path,sender,plan,challenge,KEY,approved_policy=policy)
    assert calls==['create','connect','send'] and len(sent)==1
    assert sent[0].split(b'\r\n\r\n',1)[1]==sign_startup(plan,challenge,KEY,policy)
    assert report['delivery']['schema']=='rocell.host_startup_delivery.v1'
    assert report['delivery']['result']==('DELIVERY_UNCERTAIN' if lost else 'CONTROLLER_REPORTED_ACCEPTANCE')
    assert report['delivery']['endpoint_verified'] is False and report['export_verified']
    assert (tmp_path/report['claim_file']).exists()
    with pytest.raises(Exception):
        send_prepared_startup(tmp_path,StartupStartSender('127.0.0.1',8081,policy),
            plan,challenge,KEY,approved_policy=policy)
    with pytest.raises(Exception):
        send_prepared_start(tmp_path,DiagnosticStartSender('127.0.0.1',8081),normal,challenge,KEY)
    assert calls==['create','connect','send']
    for path in tmp_path.rglob('*.json'):
        assert KEY.hex() not in path.read_text() and sign_startup(plan,challenge,KEY,policy).hex() not in path.read_text()


def test_startup_sender_rejects_normal_plan_without_socket(monkeypatch):
    calls,_=fake_socket(monkeypatch)
    plan,policy,challenge,normal=inputs()
    sender=StartupStartSender('127.0.0.1',8081,policy)
    with pytest.raises(DiagnosticStartError):sender.send(normal,challenge,KEY)
    assert not calls
    with pytest.raises(ValueError):sender.send(plan,challenge,KEY)


def test_pre_export_failure_prevents_send(tmp_path,monkeypatch):
    from rocell.application import startup_prepared_start as module
    calls,_=fake_socket(monkeypatch)
    plan,policy,challenge,_=inputs()
    monkeypatch.setattr(module,'verify_export',lambda _:dict(valid=False))
    with pytest.raises(ValueError):send_prepared_startup(tmp_path,StartupStartSender('127.0.0.1',8081,policy),
        plan,challenge,KEY,approved_policy=policy)
    assert not calls and not list(tmp_path.glob('diagnostic-start-*'))


def test_post_export_failure_keeps_claim(tmp_path,monkeypatch):
    from rocell.application import startup_prepared_start as module
    calls,_=fake_socket(monkeypatch)
    plan,policy,challenge,_=inputs();original=module.verify_export;checks=[]
    def verify(path):
        checks.append(path)
        return original(path) if len(checks)==1 else dict(valid=False)
    monkeypatch.setattr(module,'verify_export',verify)
    with pytest.raises(ValueError):send_prepared_startup(tmp_path,StartupStartSender('127.0.0.1',8081,policy),
        plan,challenge,KEY,approved_policy=policy)
    assert len(list(tmp_path.glob('diagnostic-start-*')))==1 and calls.count('send')==1
