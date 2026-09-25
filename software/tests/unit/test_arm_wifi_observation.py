import copy
import json
import os
import subprocess
import sys
import pytest
from rocell.providers.windows.arm_wifi_observation import observe,review_observation
from rocell.providers.windows.arm_wifi_feedback import probe,MAC
from rocell.providers.windows.arm_transport_lock import arm_transport_lock
from test_arm_wifi_feedback import Connection
from test_arrival_wizard_service import make_service,_run,_ticket


def simulation(fault_at=None,cancel_at=None,fast=False):
    now=[0.];calls=[]
    def clock():return now[0]
    def wait(delay):now[0]+=delay
    def sample(**kw):
        index=len(calls);calls.append(index)
        result=probe(connection_factory=lambda *a,**k:Connection(status=500 if index==fault_at else 200),
            identity=lambda:MAC,clock=clock,**kw)
        now[0]+=.05
        return result
    from rocell.providers.windows.arm_wifi_observation import observe_fast
    result=(observe_fast if fast else observe)(run_probe=sample,clock=clock,wait=wait,
        cancelled=lambda:cancel_at is not None and len(calls)>=cancel_at)
    return result,calls


def test_duration_pacing_originals_and_no_motion():
    result,calls=simulation()
    assert result['status']=='SUCCEEDED' and 174<=len(calls)<=176
    assert result['elapsed_s']==pytest.approx(35)
    assert result['motion_commands']==0 and result['serial_ports_opened']==0
    rebuilt=review_observation(result)
    assert rebuilt['successful_originals']==len(calls)
    assert rebuilt['maximum_response_gap_ms']==pytest.approx(200)
    assert not rebuilt['movement_ready'] and not rebuilt['freshness_verified']


@pytest.mark.parametrize('at',[0,3,12])
def test_first_fault_stops(at):
    r,calls=simulation(fault_at=at)
    assert len(calls)==at+1 and r['stop_reason']=='FIRST_FAULT'


def test_cancel_stops():
    r,calls=simulation(cancel_at=3)
    assert len(calls)==3 and r['stop_reason']=='CANCELLED'


@pytest.mark.parametrize('field,value',[('response_base64','e30='),('response_sha256','0'*64),
    ('response_bytes',1),('joints_rad',{}),('response_finished_monotonic_s',-1)])
def test_tampered_evidence_rejected(field,value):
    r,_=simulation(fault_at=1);r=copy.deepcopy(r)
    r['samples'][0][field]=value
    with pytest.raises(ValueError):review_observation(r)


@pytest.mark.parametrize('raw',[
    b'{"T":1051,"b":0,"s":0,"e":1,"t":0,"r":0,"g":3,"password":"secret-value"}',
    b'{"T":1051,"b":"secret-value","b":0,"s":0,"e":1,"t":0,"r":0,"g":3}'])
def test_raw_retention_does_not_leak_unknown_or_duplicate_fields(raw):
    c=Connection();c.raw=raw
    r=probe(identity=lambda:MAC,connection_factory=lambda *a,**k:c,retain_response=True)
    assert r['status']=='FAILED' and 'response_base64' not in r
    assert 'secret-value' not in json.dumps(r)


@pytest.mark.skipif(os.name!='nt',reason='Windows named mutex')
def test_cross_process_exclusion_and_release():
    program='''
from rocell.providers.windows.arm_transport_lock import arm_transport_lock
try:
    with arm_transport_lock(): print('ACQUIRED')
except RuntimeError: print('BLOCKED')
'''
    def child():
        return subprocess.run([sys.executable,'-c',program],capture_output=True,text=True,check=True,timeout=5).stdout.strip()
    with arm_transport_lock():assert child()=='BLOCKED'
    assert child()=='ACQUIRED'


def test_wizard_retains_observation_and_exports(make_service,monkeypatch):
    calls=[]
    def run(**kw):
        calls.append(1)
        return simulation()[0]
    monkeypatch.setattr('rocell.providers.windows.arm_wifi_observation.observe',run)
    service,runner,_=make_service(mode='physical')
    _ticket(service,'observe_arm_wifi_feedback',{})
    assert not calls
    result=_run(service,'observe_arm_wifi_feedback')
    assert result['status']=='SUCCEEDED',result
    assert _run(service,'export_logs')['status']=='SUCCEEDED'
    assert len(calls)==1 and not runner.calls
