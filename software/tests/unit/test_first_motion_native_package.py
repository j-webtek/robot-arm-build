"""Real isolated import subprocess, with native/process/network access held."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from rocell.providers.windows import first_motion_native_package as package


def child(tmp_path,mode='check-imports',digest=None):
    archive=package.prepare(tmp_path)
    return subprocess.run([str(Path(getattr(sys,'_base_executable',sys.executable))),'-I','-S',
        str(package.CHILD),str(archive),digest or hashlib.sha256(archive.read_bytes()).hexdigest(),mode],
        cwd=tmp_path,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        timeout=10,check=False)


def test_explicit_deterministic_roster():
    raw=package.expected_archive()
    assert raw==package.expected_archive()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert all('rocell/'+name in archive.namelist() for name in package.EXTRA)
        assert 'rocell/application/arrival_wizard_service.py' not in archive.namelist()


def test_isolated_imports_without_host_access(tmp_path):
    result=child(tmp_path)
    assert result.returncode==0,result.stderr.decode(errors='replace')
    report=json.loads(result.stdout)
    assert report['status']=='IMPORTS_OK_NOT_HARDWARE_TESTED'
    assert report['native']['native_api_loaded'] is False
    assert report['connected'] is report['physical_authority'] is report['live_entry_enabled'] is False


@pytest.mark.parametrize('mode',['execute','observe','rehearse'])
def test_unknown_modes_remain_unavailable(tmp_path,mode):
    result=child(tmp_path,mode=mode)
    assert result.returncode==5 and result.stdout==b''
    assert not list(tmp_path.glob('*-worker-*'))


def test_execute_one_without_request_refuses_before_claim_or_open(tmp_path):
    result=child(tmp_path,mode='execute-one')
    assert result.returncode==1
    report=json.loads(result.stdout)
    assert report['schema']=='rocell.first_motion_child_error.v1'
    assert report['physical_authority'] is False
    assert not list(tmp_path.glob('*-worker-*'))


def test_wrong_digest_refused(tmp_path):
    result=child(tmp_path,digest='f'*64)
    assert result.returncode==4 and result.stdout==b''
