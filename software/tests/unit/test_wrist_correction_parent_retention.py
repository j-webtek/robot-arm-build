import base64
import json
from dataclasses import replace
import pytest
from test_wrist_correction_native_protocol import fixture
from rocell.application.first_motion_contract import canonical
from rocell.application import wrist_correction_parent_retention as retention
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult


def inputs(tmp_path):
    wire,_,_=fixture(tmp_path)
    result=OwnedWorkerResult(status='FAILED',primary_error='TIMED_OUT',cleanup_errors=(),
        request_sha256=wire['request_sha256'],attempt_id=wire['attempt_id'],process_created=True,
        initial_thread_resumed=True,tree_exit_confirmed=True,returncode=1,elapsed_ns=25_000_000_000,
        stdin_bytes_written=0,peak_observed_handles=10,peak_active_processes=1,
        stdout=b'partial child output',stderr=b'error details',owned_process_id=123,finished_monotonic_ns=27_000_000_000)
    return wire,result


@pytest.mark.parametrize('scenario',['timeout','early_rejection','cleanup_unknown','child_present','corrupt_child'])
def test_failure_retention_without_child_success(tmp_path,scenario):
    wire,result=inputs(tmp_path)
    if scenario=='early_rejection': result=replace(result,request_sha256='0'*64,process_created=False,owned_process_id=0)
    if scenario=='cleanup_unknown': result=replace(result,tree_exit_confirmed=False,cleanup_errors=('CLEANUP_UNCONFIRMED',))
    child=tmp_path/(wire['attempt_id']+'-wrist-correction-outcome.original.json')
    if scenario in ('child_present','corrupt_child'): child.write_bytes(b'{}' if scenario=='child_present' else b'not json')
    receipt=retention.retain_correction_parent_result(canonical(wire),result,assigned_root=tmp_path)
    raw=(tmp_path/receipt['file']).read_bytes();report=json.loads(raw)
    assert receipt['sha256']==retention.digest(raw)
    assert base64.b64decode(report['stdout']['base64'])==result.stdout
    assert report['process']['primary_error']==result.primary_error
    assert not report['endpoint_verified'] and not report['replay_allowed']
    assert report['request_hash_matches']==(scenario!='early_rejection')
    assert report['child_outcome']['status']==('PRESENT_UNVERIFIED' if child.exists() else 'MISSING')


def test_oversized_output_is_explicitly_truncated(tmp_path):
    wire,result=inputs(tmp_path)
    result=replace(result,stdout=b'x'*(300*1024),stderr=b'e'*10000,parsed_result={'status':'SUCCESS'})
    receipt=retention.retain_correction_parent_result(canonical(wire),result,assigned_root=tmp_path)
    report=json.loads((tmp_path/receipt['file']).read_bytes())
    assert report['stdout']['truncated'] and report['stderr']['truncated']
    assert report['stdout']['observed_sha256']==retention.digest(result.stdout)
    assert report['process']['parsed_result'] is None


def test_repeat_and_storage_failure_do_not_overwrite(tmp_path,monkeypatch):
    wire,result=inputs(tmp_path);raw=canonical(wire)
    receipt=retention.retain_correction_parent_result(raw,result,assigned_root=tmp_path)
    original=(tmp_path/receipt['file']).read_bytes()
    with pytest.raises((OSError,RuntimeError)): retention.retain_correction_parent_result(raw,result,assigned_root=tmp_path)
    assert (tmp_path/receipt['file']).read_bytes()==original
    def fail(*args,**kwargs): raise OSError('synthetic disk failure')
    monkeypatch.setattr(retention,'publish_reservation_bytes',fail)
    with pytest.raises(OSError): retention.retain_correction_parent_result(raw,result,assigned_root=tmp_path)


def test_unreadable_child_does_not_prevent_parent_failure_record(tmp_path):
    wire,result=inputs(tmp_path)
    (tmp_path/(wire['attempt_id']+'-wrist-correction-outcome.original.json')).mkdir()
    receipt=retention.retain_correction_parent_result(canonical(wire),result,assigned_root=tmp_path)
    report=json.loads((tmp_path/receipt['file']).read_bytes())
    assert report['child_outcome']['status']=='UNREADABLE'
