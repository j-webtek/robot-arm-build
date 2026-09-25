"""Native composition with fake connection methods: never a serial device."""
import hashlib
import json
from threading import Event

import pytest

import test_absolute_wrist_binding as binding_fixture
from test_absolute_wrist_review_authority import intent
from rocell.application.first_motion_contract import canonical
from rocell.application.absolute_wrist_worker_claim import reserve_absolute_wrist_launch, claim_absolute_wrist_worker
from rocell.application.endpoint_owned_trial import EndpointCleanupResult
from rocell.providers.windows import absolute_wrist_trial_execution as execution
from rocell.providers.windows.absolute_wrist_serial_api import WindowsAbsoluteWristSerialApi
from rocell.providers.windows.absolute_wrist_serial_connection import AbsoluteWristSerialConnection
from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi
from rocell.safety.absolute_wrist_admission import admit_absolute_wrist


def run(tmp_path, monkeypatch, fault=None):
    runtime = canonical({'synthetic': 'not a production runtime registration'})
    body = intent()
    body['references']['runtime_sha256'] = hashlib.sha256(runtime).hexdigest()
    monkeypatch.setattr(binding_fixture, 'intent', lambda: json.loads(canonical(body)))
    request, reader, clock, _, _ = binding_fixture.fixture(tmp_path)
    request_body = request.to_dict()
    review = (tmp_path/(request_body['attempt_id']+'-absolute-wrist-reviews.json')).read_bytes()
    launch = reserve_absolute_wrist_launch(tmp_path, request, runtime_original=runtime,
        review_bundle_sha256=hashlib.sha256(review).hexdigest(), now_ns=clock[0])
    refs = request_body['references']
    claim = claim_absolute_wrist_worker(tmp_path, request, launch_sha256=launch,
        current_source_sha256=refs['source_sha256'], current_runtime_sha256=refs['runtime_sha256'], now_ns=clock[0])
    permit = admit_absolute_wrist(request, reader=reader, root=tmp_path)
    api = WindowsAbsoluteWristSerialApi.from_absolute_wrist_permit(request, permit,
        port_name=permit._binding._port, connection_id=request_body['attempt_id'])
    calls = dict(opens=0, writes=[], closes=0)
    event = Event()
    if fault == 'cancel_before': event.set()
    monkeypatch.setattr(WindowsNativeSerialApi, '_load_kernel', lambda *_: pytest.fail('No DLL allowed'))
    def opened(self):
        permit.validate_native_open(request, api.connection_id, api._port_name)
        calls['opens'] += 1
        if fault == 'open': raise OSError('synthetic open error')
    def read(self, size, timeout):
        clock[0] += 20_000_000
        joints = dict(request_body['draft']['expected_start_joints_rad'])
        if calls['writes']:
            joints['t'] = -.02 if fault == 'miss' else .02 if fault == 'excursion' else 0.
        raw = json.dumps(dict(T=1051, x=1, y=2, z=3, tit=0, **joints), separators=(',', ':')).encode()+b'\n'
        assert len(raw) <= size
        return raw
    def write(self, payload):
        # Emulates the facade's exact dispatch boundary, not an unchecked write.
        assert payload == permit.selected_payload()
        permit.claim_native_dispatch(request, api.connection_id, api._port_name)
        calls['writes'].append(payload)
        clock[0] += 1_000_000
        return len(payload) - (1 if fault == 'short' else 0)
    def close(self, timeout):
        calls['closes'] += 1
        return EndpointCleanupResult(fault != 'cleanup', 0)
    monkeypatch.setattr(AbsoluteWristSerialConnection, 'open', opened)
    monkeypatch.setattr(AbsoluteWristSerialConnection, 'read', read)
    monkeypatch.setattr(AbsoluteWristSerialConnection, 'write_once', write)
    monkeypatch.setattr(AbsoluteWristSerialConnection, 'close', close)
    monkeypatch.setattr(AbsoluteWristSerialConnection, 'snapshot',
                        lambda self: dict(test_only=True, physical_stop_verified=False))
    original_loop = execution._run_absolute_wrist_trial
    def paced(*args, **kwargs):
        kwargs['idle_wait'] = lambda seconds: clock.__setitem__(0, clock[0]+round(seconds*1e9))
        return original_loop(*args, **kwargs)
    monkeypatch.setattr(execution, '_run_absolute_wrist_trial', paced)
    kwargs = dict(worker_claim=claim, current_source_sha256='f'*64 if fault == 'source' else refs['source_sha256'],
        current_runtime_sha256=refs['runtime_sha256'], cancellation=event, clock_ns=lambda: clock[0])
    if fault == 'source':
        with pytest.raises(ValueError): execution.execute_native_absolute_wrist_trial(request, permit, api, **kwargs)
        assert calls == dict(opens=0, writes=[], closes=0)
        return None, calls
    result = execution.execute_native_absolute_wrist_trial(request, permit, api, **kwargs)
    previous = calls['opens']
    with pytest.raises(ValueError): execution.execute_native_absolute_wrist_trial(request, permit, api, **kwargs)
    assert calls['opens'] == previous
    return result, calls


@pytest.mark.parametrize('fault,status', [(None, 'REPORTED_SETTLED'), ('miss', 'HELD_TARGET_MISSED'),
    ('excursion', 'HELD_WRIST_EXCURSION'),
    ('short', 'HELD_TRANSPORT_FAULT'), ('cleanup', 'CLEANUP_UNCONFIRMED'),
    ('open', 'NATIVE_TRIAL_FAILED'), ('cancel_before', 'CANCELLED_BEFORE_OPEN'), ('source', None)])
def test_process_bound_composition_no_double_consumption(tmp_path, monkeypatch, fault, status):
    result, calls = run(tmp_path, monkeypatch, fault)
    if result is None: return
    assert result['status'] == status, result
    assert calls['closes'] >= 1
    assert len(calls['writes']) == (0 if fault in ('open', 'cancel_before') else 1)
    assert not result['physical_authority']
    if result['result']:
        assert not result['result']['campaign_advance_allowed']
        assert not result['result']['physical_stop_verified']


def test_complete_native_composition_has_seven_current_context_checks(tmp_path, monkeypatch):
    from rocell.providers.windows.absolute_wrist_current_context import AuthenticatedAbsoluteWristReader
    original = AuthenticatedAbsoluteWristReader.verify_endpoint
    checks = []
    def counted(self, *args, **kwargs):
        checks.append(len(checks)+1)
        assert len(checks) <= 7, 'Unexpected extra metadata acquisition'
        return original(self, *args, **kwargs)
    monkeypatch.setattr(AuthenticatedAbsoluteWristReader, 'verify_endpoint', counted)
    result, calls = run(tmp_path, monkeypatch)
    assert result['status'] == 'REPORTED_SETTLED'
    assert len(checks) == 7
    assert calls['opens'] == 1 and len(calls['writes']) == 1
