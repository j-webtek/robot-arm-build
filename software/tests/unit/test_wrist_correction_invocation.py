from pathlib import Path
import pytest
from test_wrist_correction_native_registration import fixture
from test_wrist_correction_native_result import request_bytes
from rocell.providers.windows.owned_worker_process import decode_owned_json
from rocell.providers.windows.wrist_correction_invocation import verify_actual_invocation


def prepared(tmp_path):
    reg,outer=fixture(tmp_path)
    payload=decode_owned_json(outer.payload_json,maximum=65536)
    args=dict(entry_path=reg.package_files[0].path,executable=reg.executable.path,
        argv=reg.argv,working_directory=reg.working_directory)
    return request_bytes(payload),args,reg


def test_actual_observations_match_pinned_runtime_without_launch(tmp_path):
    raw,args,reg=prepared(tmp_path)
    wire=verify_actual_invocation(raw,**args)
    assert wire['payload']['registration']['worker_id']==reg.worker_id


@pytest.mark.parametrize('fault',['cwd','exe','entry','argv','archive','controller','protocol'])
def test_actual_invocation_changes_rejected(tmp_path,fault):
    raw,args,reg=prepared(tmp_path)
    if fault=='cwd': args['working_directory']=tmp_path
    if fault=='exe': args['executable']=tmp_path/'other.exe'
    if fault=='entry': args['entry_path']=tmp_path/'other.py'
    if fault=='argv': args['argv']=args['argv'][:-1]+('check-imports',)
    if fault in ('archive','controller','protocol'):
        reg.package_files[{'archive':1,'controller':2,'protocol':3}[fault]].path.write_bytes(b'changed')
    with pytest.raises(ValueError): verify_actual_invocation(raw,**args)
