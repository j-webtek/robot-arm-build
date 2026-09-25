"""Actual isolated Python import audit, with native access disabled."""
import hashlib
import io
import json
import subprocess
import sys
import zipfile
import pytest
from rocell.providers.windows import wrist_correction_native_package as package


def invoke(path,digest,mode='check-imports',flags=('-I','-S'),raw=b''):
    return subprocess.run([getattr(sys,'_base_executable',sys.executable),*flags,str(package.CHILD),
        str(path),digest,mode],input=raw,capture_output=True,timeout=20)


def test_deterministic_explicit_roster():
    raw=package.expected_archive()
    assert raw==package.expected_archive()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names=archive.namelist()
        assert len(names)==len(set(names))
        assert all('rocell/'+name in names for name in package.EXTRA)
        assert not any(name.startswith(('tests/','runs/')) for name in names)


def test_actual_isolated_imports_no_execution(tmp_path):
    path=package.prepare(tmp_path);digest=hashlib.sha256(path.read_bytes()).hexdigest()
    child=invoke(path,digest)
    assert child.returncode==0,child.stderr.decode()
    report=json.loads(child.stdout)
    assert report['status']=='IMPORTS_OK_NOT_HARDWARE_TESTED'
    assert report['connected'] is False and report['live_entry_enabled'] is False
    assert report['registered_execution_mode']=='execute-one' and report['signed_reserved_request_required']
    denied=invoke(path,digest,'execute-one')
    assert denied.returncode==1 and json.loads(denied.stdout)['physical_authority'] is False


def test_isolated_entry_rejects_hash_consistent_unpinned_request(tmp_path):
    from test_wrist_correction_native_protocol import fixture
    from rocell.application.first_motion_contract import canonical
    wire,_,_=fixture(tmp_path)
    path=package.prepare(tmp_path);digest=hashlib.sha256(path.read_bytes()).hexdigest()
    denied=invoke(path,digest,'execute-one',raw=canonical(wire))
    assert denied.returncode==1
    assert json.loads(denied.stdout)==dict(schema='rocell.wrist_correction_child_error.v1',
        error_type='ValueError',physical_authority=False,replay_allowed=False)


@pytest.mark.parametrize('fault,code',[('digest',4),('bytes',4),('filename',3),('flags',2)])
def test_wrong_package_or_flags_rejected(tmp_path,fault,code):
    path=package.prepare(tmp_path);digest=hashlib.sha256(path.read_bytes()).hexdigest();flags=('-I','-S')
    if fault=='digest': digest='f'*64
    if fault=='bytes': path.write_bytes(path.read_bytes()+b'changed')
    if fault=='filename':
        other=tmp_path/'other.zip';other.write_bytes(path.read_bytes());path=other
    if fault=='flags': flags=('-I',)
    child=invoke(path,digest,flags=flags)
    assert child.returncode==code and child.stdout==b'',child.stderr.decode()
