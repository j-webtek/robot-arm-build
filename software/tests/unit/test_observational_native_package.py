import hashlib
import io
import json
import subprocess
import sys
import zipfile

import pytest

from rocell.providers.windows.observational_native_package import CHILD, expected_archive, prepare


def test_deterministic_explicit_package():
    raw = expected_archive()
    assert raw == expected_archive()
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        names = package.namelist()
        assert 'rocell/providers/windows/observational_trial_execution.py' in names
        assert 'rocell/arm/wrist_endpoint_verification.py' in names
        assert 'rocell/application/arrival_wizard_service.py' not in names


def test_isolated_child_imports_without_native_access(tmp_path):
    archive = prepare(tmp_path)
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    result = subprocess.run([sys.executable, '-I', '-S', str(CHILD), str(archive), sha, 'check-imports'],
        capture_output=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    report = json.loads(result.stdout)
    assert report['status'] == 'IMPORTS_OK_NOT_HARDWARE_TESTED'
    assert report['live_entry_enabled'] is False


@pytest.mark.parametrize('fault,code', [('hash',4), ('mode',5)])
def test_changed_archive_or_execution_mode_rejected(tmp_path, fault, code):
    archive = prepare(tmp_path)
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    result = subprocess.run([sys.executable, '-I', '-S', str(CHILD), str(archive),
        '0'*64 if fault == 'hash' else sha, 'arbitrary-mode' if fault == 'mode' else 'check-imports'],
        capture_output=True, timeout=20, check=False)
    assert result.returncode == code


def test_execute_rejects_missing_request_without_hardware(tmp_path):
    archive = prepare(tmp_path)
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    result = subprocess.run([sys.executable, '-I','-S',str(CHILD),str(archive),sha,'execute-one'],
        input=b'{}', capture_output=True, timeout=20, check=False)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report['schema'] == 'rocell.observational_child_error.v1'
    assert report['physical_authority'] is False
