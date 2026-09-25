import base64
import copy
import hashlib
import pytest
from rocell.application import supported_recovery_installation as module
from rocell.application.first_motion_contract import canonical
from test_held_pair_capabilities import fixture


@pytest.mark.parametrize('fault', [None, 'revision', 'installation', 'boot', 'hash', 'path', 'status', 'flags', 'capabilities'])
@pytest.mark.parametrize('revision', [16, 17, 19, 20, 21, 26, 27, 28, 29, 31, 33, 34, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 61, 64, 65, 66, 67, 68, 69, 70, 71])
def test_startup_binding_replays_retained_responses(tmp_path, monkeypatch, fault, revision):
    installed = dict(app='reviewed-r16')
    monkeypatch.setattr(module, 'review_pair_installation', lambda root, revision: installed if revision in (16,17,19,20,21,26,27,28,29,31,33,34,37,38,39,40,41,42,43,44,45,46,47,48,49,50,61,64,65,66,67,68,69,70,71,72) else None)
    status = dict(schema='rocell.hold_transport.v1', instance_id='11'*16, state='IDLE',
        reason='NOT_CONFIGURED', records=0, record_bytes=4096, storage_fault=False, durable_export_verified=False)
    caps = fixture()
    responses = []
    for path, document in ((module.STATUS, status), (module.PATH, caps), (module.STATUS, status)):
        raw = canonical(document)
        responses.append(dict(path=path, raw_base64=base64.b64encode(raw).decode(), sha256=hashlib.sha256(raw).hexdigest()))
    startup = dict(schema=f'rocell.r{revision}_startup_observation.v1', status='IDLE_AND_PAIR_PROTOCOL_OBSERVED',
        address='192.168.0.225', installation_export_id='installation', responses=responses,
        hold_status=copy.deepcopy(status), capability_observation=module.validate_pair_capabilities(canonical(caps),expected_boot='11'*16),
        challenge_requested=False, servo_commands_sent=False, provisioning_performed=False,
        reset_performed=False, retry_allowed=False)
    if fault=='revision': startup['schema']='rocell.r14_startup_observation.v1'
    if fault=='boot': startup['hold_status']['instance_id']='22'*16
    if fault=='hash': responses[0]['sha256']='0'*64
    if fault=='path': responses[0]['path']=module.PATH
    if fault=='status': startup['hold_status']['state']='CAPTURED'
    if fault=='flags': startup['reset_performed']=True
    if fault=='capabilities': startup['capability_observation']['capabilities']['boot_id']='22'*16
    def read(root, ident, name):
        if ident=='startup': return startup,'a'*64
        return (dict(app='old') if fault=='installation' else installed),'b'*64
    monkeypatch.setattr(module, '_read', read)
    if fault:
        with pytest.raises(ValueError): module.review_recovery_startup(tmp_path, 'startup', revision=revision)
    else:
        result = module.review_recovery_startup(tmp_path, 'startup', revision=revision)
        assert result['expected_boot']=='11'*16
        assert result['motion_authorized'] is result['current_device_bytes_verified'] is False
