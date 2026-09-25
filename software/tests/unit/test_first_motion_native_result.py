"""Synthetic child envelopes; physical-labelled bytes are not physical proof."""
import pytest

from rocell.application.first_motion_contract import canonical
from rocell.providers.windows import first_motion_native_result as module
from test_first_motion_native_protocol import fixture,signed
from test_first_motion_owned_trial import run


def prepared(tmp_path):
    a=tmp_path/'wire'; a.mkdir()
    b=tmp_path/'trial'; b.mkdir()
    wire=fixture(a); signed(wire)
    trial,_=run(b)
    # Protocol test only: synthetic bytes exercise the production-labelled codec.
    trial['basis']=trial['analysis']['basis']='RETAINED_PHYSICAL_CAPTURE'
    life=dict(schema='rocell.first_motion_connection_lifecycle.v1',phase='CLOSED',
        request_sha256=trial['request_sha256'],connection_id=wire['attempt_id'],
        owned_handle_count=0,pending_io_count=0,confirmed_write_bytes=trial['write']['confirmed_write_bytes'],
        read_calls={p:trial[p]['read_calls'] for p in ('baseline','post')},
        read_bytes={p:trial[p]['raw']['bytes'] for p in ('baseline','post')},physical_stop_verified=False)
    execution=dict(schema='rocell.native_first_motion_execution.v1',request_sha256=trial['request_sha256'],
        status=trial['status'],trial=trial,lifecycle=life,errors=[],physical_movement_verified=False,
        physical_stop_verified=False,replay_allowed=False)
    child=dict(schema='rocell.first_motion_native_child_result.v1',claim_sha256='c'*64,
        execution=execution,physical_authority=False)
    return wire,child


def test_full_trial_rebuilt_without_process_or_physical_approval(tmp_path):
    wire,child=prepared(tmp_path)
    raw=module.encode_result(child,wire)
    value=module.decode_result(raw,wire=wire)
    summary=module.validate_result(value,wire=wire)
    assert summary['status']=='COMPLETED_DATA_CONSISTENT'
    assert not summary['owned_process_receipt_verified'] and not summary['physical_movement_verified']


@pytest.mark.parametrize('fault',['analysis','lifecycle','identity','physical','byte-count','read-count'])
def test_changed_child_claims_refused(tmp_path,fault):
    wire,child=prepared(tmp_path)
    execution=child['execution']
    if fault=='analysis': execution['trial']['analysis']['post_count']+=1
    if fault=='lifecycle': execution['lifecycle']['pending_io_count']=1
    if fault=='identity': execution['lifecycle']['connection_id']='other'
    if fault=='physical': execution['physical_movement_verified']=True
    if fault=='byte-count': execution['lifecycle']['confirmed_write_bytes']-=1
    if fault=='read-count': execution['lifecycle']['read_calls']['post']-=1
    with pytest.raises(ValueError): module.encode_result(child,wire)


def test_failed_form_is_not_completed_trial_validation(tmp_path):
    wire,child=prepared(tmp_path)
    child['execution']['status']='NATIVE_TRIAL_FAILED'
    child['execution']['trial']=None
    summary=module.validate_result(module.decode_result(module.encode_result(child,wire),wire=wire),wire=wire)
    assert summary['status']=='FAILURE_DIAGNOSTIC_ONLY' and summary['rebuilt_trial'] is None


def test_wrong_envelope_and_oversized_stream_refused(tmp_path):
    wire,child=prepared(tmp_path)
    value=module.decode_result(module.encode_result(child,wire),wire=wire)
    value['request_sha256']='f'*64
    with pytest.raises(ValueError): module.decode_result(canonical(value),wire=wire)
    with pytest.raises(ValueError): module.decode_result(b'x'*(256*1024+1),wire=wire)
