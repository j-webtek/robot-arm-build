"""Real isolated import audit and invalid-entry checks; no hardware execution."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from rocell.providers.windows import absolute_wrist_native_package as package


def invoke(path, digest, mode='check-imports', flags=('-I', '-S'), raw=b''):
    return subprocess.run([getattr(sys, '_base_executable', sys.executable), *flags,
        str(package.CHILD), str(path), digest, mode], input=raw, capture_output=True, timeout=20)


def test_package_deterministic_and_explicit():
    raw = package.expected_archive()
    assert raw == package.expected_archive()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert all('rocell/'+name in names for name in package.EXTRA)
        assert not any(name.startswith(('tests/', 'runs/')) for name in names)


def test_real_isolated_import_audit_and_empty_execution_refusal(tmp_path):
    path = package.prepare(tmp_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    child = invoke(path, digest)
    assert child.returncode == 0, child.stderr.decode()
    report = json.loads(child.stdout)
    assert report['status'] == 'IMPORTS_OK_NOT_HARDWARE_TESTED'
    assert not report['connected'] and not report['physical_authority']
    assert not report['live_entry_enabled'] and report['registered_execution_mode'] == 'execute-one'
    assert report['signed_reserved_request_required']
    refused = invoke(path, digest, 'execute-one')
    assert refused.returncode == 1
    assert json.loads(refused.stdout)['physical_authority'] is False


@pytest.mark.parametrize('fault,code', [('digest', 4), ('bytes', 4), ('filename', 3), ('flags', 2)])
def test_altered_package_or_invocation_rejected(tmp_path, fault, code):
    path = package.prepare(tmp_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    flags = ('-I', '-S')
    if fault == 'digest': digest = 'f'*64
    if fault == 'bytes': path.write_bytes(path.read_bytes()+b'changed')
    if fault == 'filename':
        wrong = tmp_path/'other.zip'
        wrong.write_bytes(path.read_bytes())
        path = wrong
    if fault == 'flags': flags = ('-I',)
    child = invoke(path, digest, flags=flags)
    assert child.returncode == code, child.stderr.decode()
    assert child.stdout == b''


def test_real_child_rejects_internally_valid_but_unpinned_invocation(tmp_path):
    from test_absolute_wrist_native_protocol import wire
    from rocell.application.first_motion_contract import canonical
    path = package.prepare(tmp_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    # The fixture wire has valid hashes but no actual executable/argv pins.
    child = invoke(path, digest, 'execute-one', raw=canonical(wire(tmp_path)))
    assert child.returncode == 1
    assert json.loads(child.stdout) == dict(schema='rocell.absolute_wrist_child_error.v1',
        error_type='ValueError', physical_authority=False, replay_allowed=False)
