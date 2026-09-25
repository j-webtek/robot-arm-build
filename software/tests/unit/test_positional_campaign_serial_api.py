"""Real facade logic with an incapable fake kernel; never load a Windows DLL."""
import base64
from threading import Event

import pytest

from rocell.application.positional_campaign_launch import reserve_campaign_launch, claim_campaign_worker
from rocell.application.positional_campaign_rehearsal import _capture
from rocell.safety.positional_campaign_admission import admit_positional_campaign
from rocell.providers.windows.positional_campaign_serial_api import WindowsPositionalCampaignSerialApi
from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi, IoToken, NativeSerialError
from test_positional_campaign_launch import setup
from test_positional_campaign_admission import baseline
from test_endpoint_serial_api import FakeKernel


def admitted(tmp_path, monkeypatch, *, opened=True):
    reader, runtime = setup(tmp_path)
    evidence = reader.verify_endpoint()
    clock = [evidence['verified_at_ns']]
    # The actual resolver/signature were checked above. Fixed current evidence
    # isolates native IO ownership and state transitions from metadata scheduling.
    reader.verify_endpoint = lambda port=None: dict(evidence, verified_at_ns=clock[0])
    launch = reserve_campaign_launch(tmp_path, reader, runtime_original=runtime)
    claim = claim_campaign_worker(tmp_path, reader, launch_sha256=launch)
    permit = admit_positional_campaign(reader.request, reader=reader, root=tmp_path)
    kernel = FakeKernel()
    def load(api):
        api._dll = kernel
        return kernel
    monkeypatch.setattr(WindowsNativeSerialApi, '_load_kernel', load)
    api = WindowsPositionalCampaignSerialApi.from_campaign_claim(reader.request, permit, claim,
        port_name=evidence['port_name'], connection_id=reader.request.to_dict()['campaign_id'],
        cancellation=Event(),
        clock_ns=lambda: clock[0])
    handle = api.create_file(api.expected_path) if opened else None
    event = api.create_event() if opened else None
    if opened:
        baseline(permit, clock)
    return permit, api, handle, event, kernel, clock


def test_two_native_shaped_submissions_share_one_owned_connection(tmp_path, monkeypatch):
    permit, api, handle, event, kernel, clock = admitted(tmp_path, monkeypatch)
    start = 0.
    for index, leg in enumerate(permit.request.to_dict()['legs']):
        if index:
            baseline(permit, clock, start, 9_100_000_000)
        payload = permit.consume_command()
        finished = clock[0]
        token = IoToken(event, 'write', len(payload), payload)
        assert api.submit_io(handle, token).state == 'COMPLETE'
        post = _capture(start, leg['target_rad'], finished + 20_000_000)
        clock[0] = post['finished_ns'] + 20_000_000
        result = permit.commit_endpoint(base64.b64decode(post['raw_base64']), post['read_windows'],
            started_ns=post['started_ns'], finished_ns=post['finished_ns'],
            confirmed_write_bytes=len(payload), write_finished_ns=finished, write_uncertain=False)
        assert result['endpoint']['endpoint_verified']
        start = leg['target_rad']
    assert len(kernel.writes) == 2
    with pytest.raises(NativeSerialError):
        api.create_file(api.expected_path)
    api.close_handle(event)
    api.close_handle(handle)


@pytest.mark.parametrize('fault', ['payload', 'event', 'handle', 'stale', 'submitted'])
def test_invalid_submission_holds_without_native_write(tmp_path, monkeypatch, fault):
    permit, api, handle, event, kernel, clock = admitted(tmp_path, monkeypatch)
    payload = permit.consume_command()
    token = IoToken(event, 'write', len(payload), payload)
    used_handle = handle
    if fault == 'payload': token.payload = b'{}\n'
    if fault == 'event': token.event += 100
    if fault == 'handle': used_handle += 100
    if fault == 'stale': clock[0] += 251_000_000
    if fault == 'submitted': token.submitted = True
    with pytest.raises((ValueError, NativeSerialError)):
        api.submit_io(used_handle, token)
    with pytest.raises(NativeSerialError):
        api.submit_io(handle, IoToken(event, 'write', len(payload), payload))
    assert kernel.writes == []
    api.close_handle(event)
    api.close_handle(handle)


def test_unadmitted_campaign_cannot_load_native_kernel(monkeypatch):
    monkeypatch.setattr(WindowsNativeSerialApi, '_load_kernel',
        lambda *_: pytest.fail('Unadmitted native load'))
    api = WindowsPositionalCampaignSerialApi('COM7')
    with pytest.raises(NativeSerialError):
        api.create_file(api.expected_path)


@pytest.mark.parametrize('fault', ['short_complete', 'pending_then_aborted'])
def test_failed_completion_holds_later_commands_but_allows_cleanup(tmp_path, monkeypatch, fault):
    permit, api, handle, event, kernel, clock = admitted(tmp_path, monkeypatch)
    payload = permit.consume_command()
    token = IoToken(event, 'write', len(payload), payload)
    if fault == 'short_complete':
        def short(handle, overlapped, count, timeout, alertable):
            count._obj.value = 1
            return True
        kernel.GetOverlappedResultEx = short
        assert api.submit_io(handle, token).transferred == 1
    else:
        kernel.pending = True
        monkeypatch.setattr('ctypes.get_last_error', lambda: 997)
        assert api.submit_io(handle, token).state == 'PENDING'
        kernel.GetOverlappedResultEx = lambda *args: False
        monkeypatch.setattr('ctypes.get_last_error', lambda: 995)
        assert api.complete_io(handle, token, 0).state == 'ABORTED'
    with pytest.raises(NativeSerialError):
        api.submit_io(handle, IoToken(event, 'write', len(payload), payload))
    assert kernel.writes == [payload]
    api.close_handle(event)
    api.close_handle(handle)
