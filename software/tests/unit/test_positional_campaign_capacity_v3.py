"""Versioned byte budgets at recorded-rate-like throughput, no hardware IO."""
import base64
from threading import Event
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.positional_campaign_capture import capture_campaign_window, validate_campaign_capture
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent, fixed_campaign_limits, CAPACITY_SCHEMA
from test_positional_campaign_authority import body


def request(version):
    value = body()
    value['schema'] = 'rocell.attended_positional_intent.'+version
    value['references']['bounded_motion_risk_sha256'] = value['references'].pop('stop_qualification_sha256')
    value['limits'] = fixed_campaign_limits(value['schema'])
    return PositionalCampaignIntent(canonical(value))


def test_only_storage_capacity_changes_and_old_records_keep_their_limits():
    old, new = request('v2'), request('v3')
    changed = {k for k,v in old.to_dict()['limits'].items() if new.to_dict()['limits'][k] != v}
    assert changed == {'maximum_total_raw_bytes', 'maximum_raw_bytes_per_leg'}
    assert old.runtime_body()['limits']['maximum_post_bytes'] == 49152
    assert new.runtime_body()['limits']['maximum_post_bytes'] == 81920
    assert new.to_dict()['limits']['maximum_total_raw_bytes'] == 196608
    value = old.to_dict()
    value['schema'] = CAPACITY_SCHEMA
    with pytest.raises(ValueError): PositionalCampaignIntent(canonical(value))


@pytest.mark.parametrize('step_ms', [20, 18])
@pytest.mark.parametrize('version,expected', [('v2','BYTE_CAPACITY_REACHED'), ('v3','WINDOW_COMPLETE')])
def test_realistic_stream_size_fits_v3_without_dropping_bytes(version, expected, step_ms):
    intent = request(version)
    clock = [2_000_000_000]
    frame = canonical(dict(T=1051,b=0,s=0,e=0,t=.06981317,r=0,g=0,x=344,y=2,z=204,tit=.08))
    frame = frame + b' '*(245-len(frame)) + b'\n'
    assert len(frame) == 246
    sent = []
    def read(size, timeout):
        clock[0] = min(7_000_000_000, clock[0]+step_ms*1_000_000)
        chunk = frame[:size]
        sent.append(chunk)
        return chunk
    capture = capture_campaign_window(intent,'post',read_once=read,cancellation=Event(),
        clock_ns=lambda:clock[0],command_completed_ns=2_000_000_000,
        idle_wait=lambda seconds:clock.__setitem__(0,clock[0]+round(seconds*1e9)))
    assert capture['status'] == expected
    raw = b''.join(base64.b64decode(c) for c in capture['raw']['base64_chunks'])
    assert raw == b''.join(sent)
    if version == 'v3':
        assert capture['finished_ns']-capture['started_ns'] == 5_000_000_000
        assert 49152 < len(raw) < 81920
        validate_campaign_capture(intent,capture,phase='post',command_completed_ns=2_000_000_000)
        from rocell.arm.first_motion_analysis import _window
        rows, issues, _ = _window(raw,capture['read_windows'],capture['started_ns'],capture['finished_ns'],
            maximum_bytes=intent.to_dict()['limits']['maximum_raw_bytes_per_leg'])
        assert rows and not issues
        if step_ms == 18:
            assert len(raw) > 65536
    else:
        with pytest.raises(ValueError):
            validate_campaign_capture(intent,capture,phase='post',command_completed_ns=2_000_000_000)


def test_v3_over_capacity_remains_a_hold_not_an_early_success():
    intent = request('v3')
    clock = [2_000_000_000]
    capture = capture_campaign_window(intent,'post',read_once=lambda size, timeout:b'x'*size,
        cancellation=Event(),clock_ns=lambda:clock[0],command_completed_ns=clock[0],
        idle_wait=lambda seconds:clock.__setitem__(0,clock[0]+round(seconds*1e9)))
    assert capture['status'] == 'BYTE_CAPACITY_REACHED'
    assert capture['raw']['bytes'] == 81920
    with pytest.raises(ValueError):
        validate_campaign_capture(intent,capture,phase='post',command_completed_ns=2_000_000_000)
