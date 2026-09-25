import copy
import json
from pathlib import Path

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.servo_transport_export import capture_transport_export, replay_transport_bundle


def status(**updates):
    value=dict(schema='rocell.diagnostic_transport.v3',instance_id='a'*32,
        state='FAULT',reason='OWNER_FAULT',records=0,storage_fault=False,
        start_supported=True,durable_export_verified=False)
    return canonical(dict(value,**updates))


@pytest.mark.parametrize('fault',['timeout','json','oversize','changed','second-timeout'])
def test_failed_collection_retained_without_retry(tmp_path,fault):
    calls=[]
    def reader(path,**kwargs):
        calls.append(path)
        if fault=='timeout' or (fault=='second-timeout' and len(calls)==2):
            raise TimeoutError('private detail must not be exported')
        if fault=='json':return b'{broken'
        if fault=='oversize':return b'x'*513
        return status(reason='CHANGED' if fault=='changed' and len(calls)==2 else 'OWNER_FAULT')
    result=capture_transport_export(tmp_path,reader,startup=True)
    assert len(calls)==(2 if fault in ('changed','second-timeout') else 1)
    assert result['export_verified'] and result['replay_verified']
    assert result['summary']['status']=='COLLECTION_INCONCLUSIVE'
    raw=(Path(result['export_path'])/'attachment-transport-capture.json').read_text()
    assert 'private detail' not in raw
    bundle=json.loads(raw)
    assert replay_transport_bundle(bundle)['matches']
    altered=copy.deepcopy(bundle);altered['responses'].append(copy.deepcopy(bundle['responses'][-1]))
    with pytest.raises(ValueError):replay_transport_bundle(altered)
    altered=copy.deepcopy(bundle);altered['responses'][0]['path']='/other'
    with pytest.raises(ValueError):replay_transport_bundle(altered)
    altered=copy.deepcopy(bundle);altered['summary']['status']='ASSESSED'
    with pytest.raises(ValueError):replay_transport_bundle(altered)
    for field,value in [('sha256','0'*64),('base64','!!!!')]:
        if 'base64' in bundle['responses'][0]:
            altered=copy.deepcopy(bundle);altered['responses'][0][field]=value
            with pytest.raises(ValueError):replay_transport_bundle(altered)


def test_failure_export_error_propagates_without_retry(tmp_path,monkeypatch):
    from rocell.application import servo_transport_export as module
    calls=[]
    def reader(path,**kwargs):calls.append(path);raise TimeoutError()
    monkeypatch.setattr(module,'verify_export',lambda _:dict(valid=False))
    with pytest.raises(ValueError,match='Failure export'):
        capture_transport_export(tmp_path,reader,startup=True)
    assert len(calls)==1


def test_valid_collection_cannot_be_relabeled_failure():
    import base64,hashlib
    raw=status()
    item=dict(path='/rocell/diagnostics/status',base64=base64.b64encode(raw).decode(),
              sha256=hashlib.sha256(raw).hexdigest())
    bundle=dict(schema='rocell.startup_transport_failure.v1',responses=[item,item],
        summary=dict(status='COLLECTION_INCONCLUSIVE',progression_authority=False),progression_authority=False)
    with pytest.raises(ValueError,match='did not replay'):replay_transport_bundle(bundle)


def test_planned_run_retains_failure_and_replays_inconclusive(tmp_path):
    from test_startup_command_contract import fixture,BOOT
    from rocell.application.startup_command_contract import freeze_startup_plan
    from rocell.application.startup_planned_run import collect_startup_run,replay_startup_run
    normal,policy,_=fixture();plan=freeze_startup_plan(normal,policy);calls=[]
    def reader(path,**kwargs):calls.append(path);raise ConnectionError()
    result=collect_startup_run(tmp_path,reader,plan,boot_id=BOOT,approved_policy=policy)
    assert result['outcome']==dict(status='INCONCLUSIVE',assessment=None)
    assert result['export_verified'] and result['replay_verified'] and len(calls)==1
    assert replay_startup_run(tmp_path,Path(result['export_path']).name)['matches']
