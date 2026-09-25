"""Full absolute command/observe/verify path with incapable callbacks."""
import json
import math
from threading import Event

import pytest

from rocell.application.absolute_wrist_command_binding import AbsoluteWristCommandBinding
from rocell.application.absolute_wrist_owned_trial import run_owned_absolute_wrist_trial
from rocell.application.endpoint_owned_trial import EndpointCleanupResult
from test_absolute_wrist_binding import fixture


def run(tmp_path, fault=None):
    request, reader, clock, _, _ = fixture(tmp_path)
    binding = AbsoluteWristCommandBinding(request, reader=reader, root=tmp_path)
    binding.claim_open()
    writes, closes, event = [], [], Event()
    count = [0]
    def read(n, timeout):
        count[0] += 1
        clock[0] += 20_000_000
        value = math.radians(-4) if not writes else 0.
        if writes and fault == 'miss': value = math.radians(-.87)
        if writes and fault == 'corrupt': return b'broken\n'
        if writes and fault == 'cancel_post': event.set()
        raw = json.dumps(dict(T=1051, x=1, y=2, z=3, tit=0,
            b=0, s=0, e=0, t=value, r=0, g=0), separators=(',', ':')).encode()+b'\n'
        assert len(raw) <= n
        return raw
    def write(payload):
        writes.append(payload)
        clock[0] += 1_000_000
        if fault == 'write_exception': raise OSError('synthetic uncertain submission')
        if fault == 'short': return len(payload)-1
        if fault == 'bool_write': return True
        return len(payload)
    def close(timeout):
        closes.append(timeout)
        if fault == 'close_exception': raise OSError('synthetic cleanup fault')
        return EndpointCleanupResult(fault != 'unclean', 0)
    if fault == 'cancel_before': event.set()
    result = run_owned_absolute_wrist_trial(request, binding, read_once=read, write_once=write,
        close_once=close, cancellation=event, basis='SYNTHETIC_WIRE_REHEARSAL',
        clock_ns=(lambda: 0) if fault == 'clock' else lambda: clock[0],
        idle_wait=lambda seconds: clock.__setitem__(0, clock[0]+round(seconds*1e9)))
    return result, writes, closes, binding


@pytest.mark.parametrize('fault,status,writes_expected', [
    (None, 'REPORTED_SETTLED', 1), ('miss', 'HELD_TARGET_MISSED', 1),
    ('corrupt', 'HELD_FEEDBACK_INVALID', 1), ('short', 'HELD_TRANSPORT_FAULT', 1),
    ('write_exception', 'HELD_TRANSPORT_FAULT', 1), ('bool_write', 'HELD_TRANSPORT_FAULT', 1),
    ('unclean', 'HELD_TRANSPORT_FAULT', 1), ('close_exception', 'CLEANUP_UNCERTAIN', 1),
    ('cancel_before', 'CANCELLED_BEFORE_WRITE', 0), ('cancel_post', 'RESULT_NOT_RECONSTRUCTABLE', 1),
    ('clock', 'CLEANUP_UNCERTAIN', 0),
])
def test_integrated_outcomes_and_unconditional_cleanup(tmp_path, fault, status, writes_expected):
    result, writes, closes, binding = run(tmp_path, fault)
    assert result['status'] == status, result
    assert len(writes) == writes_expected and closes == [2000]
    if writes:
        assert json.loads(writes[0]) == dict(T=101, joint=4, rad=0., spd=20, acc=1)
    if fault in ('short', 'write_exception', 'bool_write'):
        assert result['trial']['post']['raw']['bytes'] > 0
        assert not result['review']['endpoint']['endpoint_verified']
    assert not result['physical_stop_verified'] and not result['campaign_advance_allowed']
    assert not result['motion_authorized'] and not result['replay_allowed']
    with pytest.raises(ValueError): binding.consume_command()
    with pytest.raises(ValueError): binding.claim_open()


def test_native_basis_rejected_before_callbacks(tmp_path):
    request, reader, _, _, _ = fixture(tmp_path)
    binding = AbsoluteWristCommandBinding(request, reader=reader, root=tmp_path)
    def forbidden(*args): pytest.fail('Unreleased native provenance reached a callback')
    with pytest.raises(ValueError):
        run_owned_absolute_wrist_trial(request, binding, read_once=forbidden,
            write_once=forbidden, close_once=forbidden, cancellation=Event(),
            basis='RETAINED_PHYSICAL_CAPTURE', clock_ns=forbidden)
