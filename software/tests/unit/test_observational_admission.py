from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor

import pytest

from rocell.safety.observational_admission import admit_observational
from rocell.providers.windows.observational_serial_api import WindowsObservationalSerialApi
from test_observational_current_context import fixture
from test_first_motion_analysis import wire


def prepared(tmp_path):
    reader, snapshots, _, binding = fixture(tmp_path)
    clock = [2_030_000_000]
    reader._clock = reader._context._clock = lambda: clock[0]
    reader._context._metadata = lambda: replace(snapshots[0],
        started_monotonic_ns=clock[0], finished_monotonic_ns=clock[0])
    request = reader.request
    permit = admit_observational(request, reader=reader, root=tmp_path)
    return request, permit, reader, snapshots, clock, binding.identity.port_name


def select(state):
    request, permit, reader, snapshots, clock, port = state
    connection = request.to_dict()['attempt_id']
    permit.claim_native_open(request, connection, port)
    permit.validate_native_open(request, connection, port)
    clock[0] = 2_510_000_000
    snapshots[0] = replace(snapshots[0], started_monotonic_ns=2_500_000_000,
                           finished_monotonic_ns=2_505_000_000)
    raw, windows = wire([.02]*10, 2_000_000_000)
    return permit.bind_owned_baseline(request, connection, port, raw, windows,
        started_ns=2_000_000_000, finished_ns=2_500_000_000)


def test_admission_binds_one_command_after_owned_baseline(tmp_path):
    state = prepared(tmp_path)
    request, permit, reader, _, _, port = state
    connection = request.to_dict()['attempt_id']
    with pytest.raises(ValueError): permit.selected_payload()
    report = select(state)
    assert report['motion_authorized'] is False
    assert permit.selected_payload().endswith(b'\n')
    permit.claim_native_dispatch(request, connection, port)
    with pytest.raises(ValueError): permit.claim_native_dispatch(request, connection, port)
    with pytest.raises(ValueError): permit.selected_payload()
    with pytest.raises(Exception): admit_observational(request, reader=reader, root=tmp_path)


@pytest.mark.parametrize('fault', ['port', 'missing', 'stale', 'review', 'revoke'])
def test_dispatch_change_revokes_without_retry(tmp_path, fault):
    state = prepared(tmp_path)
    request, permit, _, snapshots, clock, port = state
    select(state)
    connection = request.to_dict()['attempt_id']
    if fault == 'port': port = 'COM4096'
    if fault == 'missing': snapshots[0] = replace(snapshots[0], native_observations=())
    if fault == 'stale': clock[0] += 200_000_000
    if fault == 'review': (tmp_path/(connection+'-observational-reviews.json')).write_bytes(b'{}')
    if fault == 'revoke': permit.revoke()
    with pytest.raises(ValueError): permit.claim_native_dispatch(request, connection, port)
    with pytest.raises(ValueError): permit.claim_native_dispatch(request, connection, port)


def test_concurrent_dispatch_has_only_one_winner(tmp_path):
    state = prepared(tmp_path)
    request, permit, _, _, _, port = state
    select(state)
    def claim(_):
        try:
            permit.claim_native_dispatch(request, request.to_dict()['attempt_id'], port)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(claim, range(4))) == 1


def test_native_facade_factory_is_inert_and_open_is_one_use(tmp_path, monkeypatch):
    request, permit, _, _, _, port = prepared(tmp_path)
    def forbidden(*args, **kwargs):
        pytest.fail('Native kernel must not be loaded during facade construction')
    monkeypatch.setattr(WindowsObservationalSerialApi, '_load_kernel', forbidden)
    facade = WindowsObservationalSerialApi.from_observational_permit(request, permit,
        port_name=port, connection_id=request.to_dict()['attempt_id'])
    assert facade.admitted_request_sha256 == request.request_sha256
    with pytest.raises(ValueError): facade._motion_payload()
    with pytest.raises(ValueError):
        WindowsObservationalSerialApi.from_observational_permit(request, permit,
            port_name=port, connection_id=request.to_dict()['attempt_id'])
