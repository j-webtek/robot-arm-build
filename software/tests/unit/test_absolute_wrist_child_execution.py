from dataclasses import replace
from threading import Event

import pytest

from rocell.application.absolute_wrist_worker_preparation import prepare_absolute_wrist_worker
from rocell.providers.windows.owned_worker_process import owned_request_wire
from rocell.providers.windows import absolute_wrist_child_execution as module
from rocell.providers.windows.absolute_wrist_prelaunch import verify_reserved_absolute_wrist_entry
from rocell.providers.windows.absolute_wrist_native_protocol import decode_request
from test_absolute_wrist_timed_preparation import fixture as preparation_fixture
from test_endpoint_current_context import fixture as endpoint_fixture


def prepared(tmp_path, monkeypatch):
    workspace, staged, request, signed, _, _ = preparation_fixture(tmp_path, monkeypatch)
    worker = prepare_absolute_wrist_worker(workspace, staged, request, review_original=signed,
                                         clock_ns=lambda: 2_000_000_000)
    raw, _ = owned_request_wire(worker.registration, worker.request, deadline_ns=worker.request.expires_at_ns)
    # The child imports its own host loader symbol; use the same synthetic key.
    from rocell.providers.windows import bench_review_key
    from rocell.providers.windows import absolute_wrist_prelaunch
    monkeypatch.setattr(module, 'load_host_absolute_wrist_review_authority',
                        bench_review_key.load_host_absolute_wrist_review_authority)
    monkeypatch.setattr(absolute_wrist_prelaunch, 'load_host_absolute_wrist_review_authority',
                        bench_review_key.load_host_absolute_wrist_review_authority)
    return workspace, request, raw


def test_child_reaches_incapable_execution_boundary_after_real_checks(tmp_path, monkeypatch):
    workspace, request, raw = prepared(tmp_path, monkeypatch)
    _, snapshots, _, _ = endpoint_fixture()
    snapshot = replace(snapshots[0], started_monotonic_ns=2_000_000_000, finished_monotonic_ns=2_000_000_000)
    def metadata(**kwargs):
        assert kwargs['maximum_acquisitions'] == 7
        assert kwargs['deadline_ns'] == request.to_dict()['deadline_ns']-2_000_000_000
        return lambda: snapshot
    monkeypatch.setattr(module, 'WindowsControllerMetadataAcquirer', metadata)
    def forbidden(*args, **kwargs): pytest.fail('No native kernel access permitted')
    monkeypatch.setattr(module.WindowsAbsoluteWristSerialApi, '_load_kernel', forbidden)
    reached = []
    def incapable(actual_request, permit, api, **kwargs):
        assert actual_request == request
        assert api.matches_authorization(actual_request, permit)
        assert kwargs['worker_claim'].claim_sha256
        reached.append(actual_request.request_sha256)
        return {'synthetic_boundary_reached': True}
    monkeypatch.setattr(module, 'execute_native_absolute_wrist_trial', incapable)
    result = module.execute_absolute_wrist_child(workspace, raw, cancellation=Event(), clock_ns=lambda: 2_000_000_000)
    assert result == {'synthetic_boundary_reached': True}
    assert reached == [request.request_sha256]
    with pytest.raises(Exception):
        module.execute_absolute_wrist_child(workspace, raw, cancellation=Event(), clock_ns=lambda: 2_000_000_000)
    assert len(reached) == 1


@pytest.mark.parametrize('fault', ['review','launch','controller','cancel'])
def test_child_stops_before_metadata_for_changed_originals(tmp_path, monkeypatch, fault):
    workspace, request, raw = prepared(tmp_path, monkeypatch)
    def forbidden(*args, **kwargs): pytest.fail('Metadata/native execution reached after refusal')
    monkeypatch.setattr(module, 'WindowsControllerMetadataAcquirer', forbidden)
    event = Event()
    attempt = request.to_dict()['attempt_id']
    if fault == 'cancel': event.set()
    elif fault == 'controller':
        (tmp_path/(attempt+'-absolute-wrist-native-child')/'controller.original.json').write_bytes(b'{}')
    else:
        (tmp_path/(attempt+'-absolute-wrist-'+('reviews' if fault == 'review' else 'launch')+'.json')).write_bytes(b'{}')
    with pytest.raises(ValueError):
        module.execute_absolute_wrist_child(workspace, raw, cancellation=event, clock_ns=lambda: 2_000_000_000)


def test_parent_prelaunch_rechecks_reserved_originals(tmp_path, monkeypatch):
    workspace, request, raw = prepared(tmp_path, monkeypatch)
    assert verify_reserved_absolute_wrist_entry(decode_request(raw)['payload'], workspace=workspace,
                                               clock_ns=lambda: 2_000_000_000) == request
