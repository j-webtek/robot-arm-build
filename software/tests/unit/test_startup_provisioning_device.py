"""USB adapter control-flow doubles; no serial imports or connected hardware."""
from types import SimpleNamespace
import pytest

from rocell.providers.windows.startup_provisioning_device import StartupProvisioningDevice
from rocell.application.startup_provisioning_execution import FLASH_SIZE, FS_START, IMAGE_SIZE
from rocell.application.startup_provisioning_journal import StartupProvisioningJournal


def adapter(fault=None):
    calls = []
    loader = SimpleNamespace(WRITE_BLOCK_ATTEMPTS=3)

    class Port:
        def __init__(self, **kwargs): calls.append('port-created')
        def open(self): calls.append('open')
        def close(self): calls.append('close')

    class ROM:
        secure_download_mode = False
        stub_is_disabled = False
        def __init__(self, port, baud): pass
        def connect(self, mode, attempts):
            assert attempts == 1 and mode == 'default_reset'
            calls.append('connect')
            if fault == 'connect': raise OSError('Synthetic connection failure')
        def read_mac(self): return bytes.fromhex('000000000000' if fault == 'identity' else 'fce8c0f8d538')
        def get_secure_boot_enabled(self): return False
        def get_flash_encryption_enabled(self): return False
        def run_stub(self): calls.append('stub'); return self
        def flash_id(self): return 0x164020
        def hard_reset(self): calls.append('startup')
        def read_flash(self, offset, length):
            calls.append('read')
            if fault == 'read': raise OSError('Synthetic read failure')
            return bytes(length)

    def write(stub, args):
        calls.append('write')
        assert loader.WRITE_BLOCK_ATTEMPTS == 1
        assert args.addr_filename[0][0] == FS_START
        assert args.addr_filename[0][1].read() == b'x' * IMAGE_SIZE
        assert not args.erase_all and not args.force and not args.encrypt
        assert args.flash_size == args.flash_mode == args.flash_freq == 'keep'
        if fault == 'write': raise OSError('Synthetic uncertain write')

    device = StartupProvisioningDevice(esptool=SimpleNamespace(__version__='4.6', ESP32ROM=ROM),
        cmds=SimpleNamespace(write_flash=write), loader=loader, serial=SimpleNamespace(Serial=Port))
    assert calls == []  # Construction cannot open or reset.
    return device, calls


def test_adapter_exact_single_write_no_reset():
    device, calls = adapter()
    device.identity()
    device.read_flash(0, FLASH_SIZE)
    with pytest.raises(ValueError): device.read_flash(0, FLASH_SIZE)
    assert device.write_flash_once(FS_START, b'x' * IMAGE_SIZE)
    device.read_flash(0, FLASH_SIZE)
    with pytest.raises(ValueError): device.write_flash_once(FS_START, b'x' * IMAGE_SIZE)
    with pytest.raises(ValueError): device.read_flash(0, FLASH_SIZE)
    device.close()
    assert calls == ['port-created', 'open', 'connect', 'stub', 'read', 'write', 'read', 'close']


def test_explicit_startup_is_once_and_requires_postwrite_read():
    device, calls = adapter()
    with pytest.raises(ValueError): device.startup_once()
    device.identity()
    device.read_flash(0, FLASH_SIZE)
    device.write_flash_once(FS_START, b'x' * IMAGE_SIZE)
    with pytest.raises(ValueError): device.startup_once()
    device.read_flash(0, FLASH_SIZE)
    device.startup_once()
    with pytest.raises(ValueError): device.startup_once()
    assert calls[-2:] == ['startup', 'close']


@pytest.mark.parametrize('fault', ['identity', 'connect', 'read', 'write'])
def test_adapter_closes_without_retry(fault):
    device, calls = adapter(fault)
    with pytest.raises((ValueError, OSError)):
        device.identity()
        device.read_flash(0, FLASH_SIZE)
        device.write_flash_once(FS_START, b'x' * IMAGE_SIZE)
    assert calls[-1] == 'close'
    count = list(calls)
    with pytest.raises(ValueError): device.identity()
    with pytest.raises(ValueError): device.write_flash_once(FS_START, b'x' * IMAGE_SIZE)
    assert calls == count


def test_journal_survives_new_instance_and_never_resumes(tmp_path):
    journal = StartupProvisioningJournal(tmp_path)
    assert journal.reserve(dict(candidate_sha256='a' * 64))
    assert journal.event(dict(stage='PREWRITE_VERIFIED'))
    journal.close()
    raw = journal.path.read_bytes()
    with pytest.raises(FileExistsError):
        StartupProvisioningJournal(tmp_path).reserve(dict(candidate_sha256='b' * 64))
    assert journal.path.read_bytes() == raw


def test_failed_journal_flush_keeps_reservation(tmp_path, monkeypatch):
    from rocell.application import startup_provisioning_journal as module
    def fail(fd): raise OSError('Synthetic disk failure')
    monkeypatch.setattr(module.os, 'fsync', fail)
    journal = StartupProvisioningJournal(tmp_path)
    with pytest.raises(OSError): journal.reserve(dict(candidate_sha256='a' * 64))
    assert journal.path.exists() and journal.stream.closed
    with pytest.raises(FileExistsError):
        StartupProvisioningJournal(tmp_path).reserve(dict(candidate_sha256='a' * 64))
