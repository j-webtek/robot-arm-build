import importlib.util
from pathlib import Path
import pytest


def inspect(esp):
    path = Path(__file__).resolve().parents[2] / 'scripts/inspect_controller_security.py'
    spec = importlib.util.spec_from_file_location('security_review', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.inspect_security(esp)


class Device:
    def read_mac(self): return bytes.fromhex('fce8c0f8d538')
    def get_chip_revision(self): return 301
    def get_secure_boot_enabled(self): return 0
    def get_flash_encryption_enabled(self): return False
    def get_encrypted_download_disabled(self): return 0


def test_named_getters_only():
    report = inspect(Device())
    assert report['chip_revision'] == 301
    assert report['secure_boot_enabled'] is False
    assert report['flash_encryption_enabled'] is False
    assert not report['key_material_read'] and not report['efuses_written']


def test_read_error_does_not_become_disabled():
    class Failure(Device):
        def get_secure_boot_enabled(self): raise OSError('read failed')
    with pytest.raises(OSError): inspect(Failure())


def test_identity_checked_first():
    class Wrong:
        def read_mac(self): return bytes(6)
    with pytest.raises(ValueError, match='identity'): inspect(Wrong())
