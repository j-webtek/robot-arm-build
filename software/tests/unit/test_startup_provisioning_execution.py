"""Synthetic device only; verifies write scope and fault-stop control flow."""
import pytest

from rocell.application import startup_provisioning_execution as execution
from rocell.application import hold_provisioning_execution as hold
from rocell.application import pair_settings_provisioning as pair
from rocell.application import negative_pair_provisioning as negative


@pytest.fixture(params=['startup', 'hold', 'pair-settings', 'negative-pair'])
def rig(monkeypatch, request):
    source = b's' * execution.IMAGE_SIZE
    candidate = b'c' * execution.IMAGE_SIZE
    memory = bytearray(execution.FLASH_SIZE)
    memory[execution.FS_START:execution.FS_END] = source
    # Real installed hash matching belongs to integration; synthetic bytes use
    # synthetic hashes. The exact byte/range checks are the production code.
    profile, runner_type = {'hold':(hold,hold.HoldProvisioningExecution),
        'startup':(execution,execution.StartupProvisioningExecution),
        'pair-settings':(pair,pair.PairSettingsExecution),
        'negative-pair':(negative,negative.NegativePairExecution)}[request.param]
    monkeypatch.setattr(profile, 'APP_SHA256', execution.digest(memory[execution.APP_START:execution.APP_START+profile.APP_SIZE]))
    monkeypatch.setattr(execution, 'PARTITION_SHA256', execution.digest(memory[0x8000:0x8c00]))

    class Device:
        def __init__(self):
            self.reads = 0
            self.writes = 0
            self.calls = []
            self.fault = None

        def identity(self):
            self.calls.append('identity')
            return dict(mac='wrong' if self.fault == 'identity' else execution.MAC,
                flash_id=0x164020, secure_boot=False, flash_encryption=False, secure_download_mode=False)

        def read_flash(self, offset, length):
            self.reads += 1
            self.calls.append('read')
            assert offset == 0 and length == execution.FLASH_SIZE
            data = bytes(memory)
            if self.fault == 'short' and self.reads == 2:
                return data[:-1]
            return data

        def write_flash_once(self, offset, image):
            self.calls.append('write')
            self.writes += 1
            assert offset == execution.FS_START and image == candidate
            memory[offset:offset+len(image)] = image
            if self.fault == 'uncertain':
                return False
            if self.fault == 'exception':
                raise OSError('Synthetic uncertain write')
            if self.fault == 'readback':
                memory[offset] ^= 1
            if self.fault == 'protected':
                memory[0] ^= 1
            return True

    device = Device()
    events = []

    def reserve(record):
        device.calls.append('reserve')
        return True

    def preserve(data):
        device.calls.append('preserve')
        assert data == source
        return True

    def event(record):
        events.append(record)
        device.calls.append(record['stage'])
        return True

    args = dict(source_sha256=execution.digest(source), candidate_sha256=execution.digest(candidate),
                reserve=reserve, preserve_source=preserve, event=event)
    return device, candidate, args, events, memory, runner_type, request.param


def test_success_has_one_exact_write_and_no_startup(rig):
    device, candidate, args, events, _, runner_type, mode = rig
    runner = runner_type()
    result = runner.execute(device, candidate, **args)
    assert result['status'] == 'FLASH_READBACK_VERIFIED'
    assert result['schema'] == f'rocell.{mode}_provisioning_result.v1'
    assert not result['startup_attempted'] and not result['motion_authorized']
    assert device.calls == ['reserve', 'identity', 'read', 'preserve', 'PREWRITE_VERIFIED',
                            'WRITE_ATTEMPT_STARTED', 'write', 'read', 'FLASH_READBACK_VERIFIED']
    with pytest.raises(ValueError, match='consumed'): runner.execute(device, candidate, **args)
    assert device.writes == 1


@pytest.mark.parametrize('fault', ['identity', 'source', 'application', 'partition', 'candidate',
    'reserve', 'preserve', 'prewrite-export', 'uncertain', 'exception', 'readback', 'protected', 'short', 'final-export'])
def test_fault_stops_without_retry_or_reset(rig, fault):
    device, candidate, args, events, memory, runner_type, _ = rig
    device.fault = fault
    expected_writes = int(fault in ('uncertain', 'exception', 'readback', 'protected', 'short', 'final-export'))
    if fault == 'source': memory[execution.FS_START] ^= 1
    if fault == 'application': memory[execution.APP_START] ^= 1
    if fault == 'partition': memory[0x8000] ^= 1
    if fault == 'candidate': args['candidate_sha256'] = '0' * 64
    if fault == 'reserve': args['reserve'] = lambda record: False
    if fault == 'preserve': args['preserve_source'] = lambda data: False
    if fault in ('prewrite-export', 'final-export'):
        original = args['event']
        failing_stage = 'WRITE_ATTEMPT_STARTED' if fault == 'prewrite-export' else 'FLASH_READBACK_VERIFIED'
        args['event'] = lambda record: False if record['stage'] == failing_stage else original(record)
    runner = runner_type()
    with pytest.raises((ValueError, OSError)): runner.execute(device, candidate, **args)
    assert device.writes == expected_writes
    calls = list(device.calls)
    with pytest.raises(ValueError, match='consumed'): runner.execute(device, candidate, **args)
    assert device.calls == calls
    if fault in ('uncertain', 'exception'): assert device.reads == 1
