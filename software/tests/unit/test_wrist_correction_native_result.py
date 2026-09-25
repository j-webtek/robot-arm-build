import json
import os
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.providers.windows import wrist_correction_native_protocol as protocol
from rocell.providers.windows import wrist_correction_native_result as results
from rocell.providers.windows.wrist_correction_trial_execution import _execute_claimed_correction_trial
from test_wrist_correction_trial_execution import fixture
from test_observational_native_protocol import rehash


def request_bytes(payload):
    ctx=payload['context']
    return canonical(rehash(dict(schema=protocol.REQUEST_SCHEMA,worker_id=protocol.WORKER_ID,
        attempt_id=ctx['attempt_id'],session_id=ctx['session_id'],source_sha256=ctx['references']['source_sha256'],
        operation_sha256=protocol.digest(canonical(payload)),selected_identity_sha256=protocol.digest(canonical(ctx['usb_identity'])),
        expires_at_monotonic_ns=ctx['deadline_ns'],parent_deadline_monotonic_ns=ctx['deadline_ns'],payload=payload,
        registration_sha256=ctx['references']['runtime_sha256'])))


def test_complete_trial_reference_roundtrip_and_store_tamper(tmp_path,monkeypatch):
    payload,permit,api,kwargs,kernel=fixture(tmp_path,monkeypatch)
    start=kwargs['clock_ns']()
    child=_execute_claimed_correction_trial(payload,permit,api,**kwargs)
    request=request_bytes(payload)
    raw=results.encode_result(child,request_raw=request)
    assert len(raw)<results.MAX_BYTES and b'REPORTED_SETTLED' not in raw
    loadargs=dict(request_raw=request,assigned_root=tmp_path,authority=permit._binding._reader._authority,
        owned_process_id=os.getpid(),process_started_ns=start,process_finished_ns=kwargs['clock_ns']())
    loaded=results.load_result_original(raw,**loadargs)
    assert json.loads(loaded['original_bytes'])['status']=='REPORTED_SETTLED'
    assert not loaded['endpoint_verified'] and not loaded['campaign_advance_allowed']
    path=tmp_path/json.loads(raw)['outcome']['file']
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError,match='changed'): results.load_result_original(raw,**loadargs)
    assert len(kernel.writes)==1


@pytest.mark.parametrize('fault',['path','extra','authority','hash','bytes','bool_bytes','request','attempt'])
def test_reference_rejects_override_fields(tmp_path,fault):
    from test_wrist_correction_native_protocol import fixture as protocol_fixture
    wire,_,_=protocol_fixture(tmp_path)
    request=canonical(wire)
    value=dict(schema=results.SCHEMA,request_sha256=wire['request_sha256'],attempt_id=wire['attempt_id'],
        claim_sha256='c'*64,outcome=dict(file=wire['attempt_id']+'-wrist-correction-outcome.original.json',
            bytes=100,sha256='d'*64),physical_authority=False,replay_allowed=False)
    if fault=='path': value['outcome']['file']='../other.json'
    if fault=='extra': value['status']='REPORTED_SETTLED'
    if fault=='authority': value['physical_authority']=True
    if fault=='hash': value['outcome']['sha256']='invalid'
    if fault=='bytes': value['outcome']['bytes']=results.MAX_OUTCOME_BYTES+1
    if fault=='bool_bytes': value['outcome']['bytes']=True
    if fault=='request': value['request_sha256']='f'*64
    if fault=='attempt': value['attempt_id']='operation-'+'e'*32
    with pytest.raises(ValueError): results.decode_result(canonical(value),request_raw=request)


def test_failed_retention_cannot_be_encoded_as_retained(tmp_path):
    from test_wrist_correction_native_protocol import fixture as protocol_fixture
    wire,_,_=protocol_fixture(tmp_path)
    child=dict(schema='rocell.claimed_wrist_correction_trial.v1',owned_process_verified=False,
        physical_authority=False,replay_allowed=False,result=dict(outcome_retention=dict(status='FAILED')))
    with pytest.raises(ValueError,match='Retained'): results.encode_result(child,request_raw=canonical(wire))


def test_retained_outcome_budget_accepts_bounded_duplicated_windows_not_small_ipc():
    from rocell.providers.windows.owned_worker_process import decode_owned_json
    raw=canonical(dict(trial_windows=[[0,1,2,3]]*768,capture_windows=[[0,1,2,3]]*768))
    assert results.decode_outcome(raw)['trial_windows'][0]==[0,1,2,3]
    with pytest.raises(ValueError,match='IPC_STRUCTURE_LIMIT'): decode_owned_json(raw,maximum=results.MAX_OUTCOME_BYTES)


@pytest.mark.parametrize('raw',[canonical(dict(nodes=[0]*16384)), b'{"a":1,"a":2}',
    b'{"a":NaN}', b'{"a":'+b'['*17+b'0'+b']'*17+b'}', b'x'*(results.MAX_OUTCOME_BYTES+1)],
    ids=['nodes','duplicate','nonfinite','depth','bytes'])
def test_retained_outcome_still_has_strict_bounded_parser(raw):
    with pytest.raises(ValueError): results.decode_outcome(raw)
