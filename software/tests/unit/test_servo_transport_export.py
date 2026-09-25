import copy
import json
from pathlib import Path
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_transport_export import capture_transport_export,replay_transport_export,replay_transport_bundle


def idle_reader(path,*,maximum_bytes,timeout_seconds):
    assert path=='/rocell/diagnostics/status'
    return canonical(dict(schema='rocell.diagnostic_transport.v2',instance_id='a'*32,
        state='IDLE',reason='NONE',records=0,storage_fault=False,start_supported=False,
        durable_export_verified=False))


def saved(tmp_path):
    result=capture_transport_export(tmp_path,idle_reader)
    path=Path(result['export_path'])
    bundle=json.loads((path/'attachment-transport-capture.json').read_text())
    return result,path,bundle


def test_real_export_and_replay(tmp_path):
    result,path,bundle=saved(tmp_path)
    assert result['export_verified'] and result['replay_verified']
    assert replay_transport_export(tmp_path,path.name)['matches']
    assert result['summary']['instance_identity_bound']
    assert not result['summary']['endpoint_assessed']
    assert not result['progression_authority']


@pytest.mark.parametrize('fault',['hash','order','extra','missing','summary','authority','encoding'])
def test_rejects_rehashed_bad_bundle(tmp_path,fault):
    _,_,bundle=saved(tmp_path)
    if fault=='hash':bundle['responses'][0]['sha256']='0'*64
    if fault=='order':bundle['responses'][0]['path']='/js'
    if fault=='extra':bundle['responses'].append(copy.deepcopy(bundle['responses'][0]))
    if fault=='missing':bundle['responses'].pop()
    if fault=='summary':bundle['summary']['progression_authority']=True
    if fault=='authority':bundle['progression_authority']=True
    if fault=='encoding':bundle['responses'][0]['base64']='!!!'
    with pytest.raises(ValueError):replay_transport_bundle(bundle)


def test_attachment_tamper(tmp_path):
    _,path,_=saved(tmp_path)
    (path/'attachment-transport-capture.json').write_text('{}')
    with pytest.raises(ValueError):replay_transport_export(tmp_path,path.name)


def test_export_verification_failure_propagates(tmp_path,monkeypatch):
    from rocell.application import servo_transport_export as module
    monkeypatch.setattr(module,'verify_export',lambda _:dict(valid=False))
    with pytest.raises(ValueError):capture_transport_export(tmp_path,idle_reader)
