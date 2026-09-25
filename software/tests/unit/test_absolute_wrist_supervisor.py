"""Exact parent registration checks using no-process backends only."""
from dataclasses import replace
from threading import Event

import pytest

from rocell.application.absolute_wrist_worker_preparation import prepare_absolute_wrist_worker
from rocell.providers.windows import owned_worker_process as supervisor
from rocell.providers.windows import absolute_wrist_prelaunch, bench_review_key
from test_absolute_wrist_timed_preparation import fixture


@pytest.mark.parametrize('fault', ['cancel', 'review', 'deadline', 'argv'])
def test_invalid_absolute_dispatch_never_constructs_backend(tmp_path, monkeypatch, fault):
    workspace, staged, request, signed, _, _ = fixture(tmp_path, monkeypatch)
    worker = prepare_absolute_wrist_worker(workspace, staged, request,
        review_original=signed, clock_ns=lambda: 2_000_000_000)
    monkeypatch.setattr(absolute_wrist_prelaunch, 'load_host_absolute_wrist_review_authority',
                        bench_review_key.load_host_absolute_wrist_review_authority)
    event = Event()
    deadline = worker.request.expires_at_ns
    registration = worker.registration
    if fault == 'cancel': event.set()
    if fault == 'review':
        (tmp_path/(request.to_dict()['attempt_id']+'-absolute-wrist-reviews.json')).write_bytes(b'{}')
    if fault == 'deadline': deadline -= 1
    if fault == 'argv': registration = replace(registration, argv=(*registration.argv[:-1], 'check-imports'))
    def forbidden(*args): pytest.fail('No backend or authorization after invalid entry')
    result = supervisor.OwnedWindowsWorker(registration, authorizer=forbidden,
        _backend_factory=forbidden, _clock=lambda: 2_000_000_000).run(
        worker.request, cancellation=event, deadline_ns=deadline)
    assert result.status != 'SUCCEEDED' and not result.process_created


def test_approval_changed_after_pinning_is_rechecked_before_execution(tmp_path, monkeypatch):
    workspace, staged, request, signed, _, _ = fixture(tmp_path, monkeypatch)
    worker = prepare_absolute_wrist_worker(workspace, staged, request,
        review_original=signed, clock_ns=lambda: 2_000_000_000)
    monkeypatch.setattr(absolute_wrist_prelaunch, 'load_host_absolute_wrist_review_authority',
                        bench_review_key.load_host_absolute_wrist_review_authority)
    monkeypatch.setattr(supervisor.time, 'monotonic_ns', lambda: 2_000_000_000)
    calls = []
    class Backend:
        def pin(self, reg): calls.append('pin')
        def start(self, reg, wire, *, check):
            calls.append('start-check')
            check()
            pytest.fail('Changed review reached execution')
        def cleanup(self, deadline):
            calls.append('cleanup')
            return ()
    def change(*args):
        calls.append('authorize')
        (tmp_path/(request.to_dict()['attempt_id']+'-absolute-wrist-reviews.json')).write_bytes(b'{}')
    result = supervisor.OwnedWindowsWorker(worker.registration, authorizer=change,
        _backend_factory=Backend, _clock=lambda: 2_000_000_000).run(
        worker.request, cancellation=Event(), deadline_ns=worker.request.expires_at_ns)
    assert result.status == 'FAILED' and not result.process_created
    assert calls == ['pin', 'authorize', 'start-check', 'cleanup']


@pytest.mark.parametrize('fault', [None, 'wrong_pid', 'missing_claim', 'wrong_claim_hash', 'changed_result'])
def test_complete_result_receipt_path_with_incapable_backend(tmp_path, monkeypatch, fault):
    import json
    import os
    from rocell.application.absolute_wrist_worker_claim import claim_absolute_wrist_worker
    from rocell.application.first_motion_contract import canonical
    from rocell.providers.windows.absolute_wrist_native_protocol import decode_request
    from rocell.providers.windows.absolute_wrist_native_result import encode_result
    import test_absolute_wrist_native_result as result_fixture

    workspace, staged, request, signed, _, _ = fixture(tmp_path, monkeypatch)
    worker = prepare_absolute_wrist_worker(workspace, staged, request,
        review_original=signed, clock_ns=lambda: 2_000_000_000)
    monkeypatch.setattr(absolute_wrist_prelaunch, 'load_host_absolute_wrist_review_authority',
                        bench_review_key.load_host_absolute_wrist_review_authority)
    clock = [2_000_000_000]
    monkeypatch.setattr(supervisor.time, 'monotonic_ns', lambda: clock[0])
    class Backend:
        # Synthetic process accounting: this backend never creates any process.
        pid = os.getpid() + (1 if fault == 'wrong_pid' else 0)
        created = resumed = tree_exited = False
        stdout, stderr, returncode = b'', b'', 0
        def pin(self, registration): assert registration == worker.registration
        def start(self, registration, raw, *, check):
            check()
            decoded = decode_request(raw)
            payload = decoded['payload']
            monkeypatch.setattr(result_fixture, 'wire', lambda _: decoded)
            child, _ = result_fixture.fixture(tmp_path, monkeypatch)
            if fault != 'missing_claim':
                refs = request.to_dict()['references']
                claim = claim_absolute_wrist_worker(tmp_path, request,
                    launch_sha256=payload['launch_sha256'], current_source_sha256=refs['source_sha256'],
                    current_runtime_sha256=refs['runtime_sha256'], now_ns=clock[0])
                child['claim_sha256'] = claim.claim_sha256
            if fault == 'wrong_claim_hash': child['claim_sha256'] = 'a'*64
            self.stdout = encode_result(child, wire=decoded)
            if fault == 'changed_result':
                changed = json.loads(self.stdout)
                changed['child_result']['result']['review']['endpoint']['status'] = 'TARGET_MISSED'
                self.stdout = canonical(changed)
        def poll(self, budget):
            clock[0] = 10_000_000_000
            return True
        def cleanup(self, deadline): return ()
    result = supervisor.OwnedWindowsWorker(worker.registration, authorizer=lambda *args: None,
        _backend_factory=Backend, _clock=lambda: clock[0]).run(worker.request,
        cancellation=Event(), deadline_ns=worker.request.expires_at_ns)
    assert not result.process_created
    assert result.status == ('SUCCEEDED' if fault is None else 'FAILED'), result
    assert (result.parsed_result is not None) == (fault is None)
    assert result.stdout  # Failed receipts retain the original diagnostic bytes.
    if fault != 'missing_claim':
        clock[0] = 2_000_000_000
        def forbidden(): pytest.fail('Consumed attempt must not create another backend')
        replay = supervisor.OwnedWindowsWorker(worker.registration, authorizer=lambda *args: None,
            _backend_factory=forbidden, _clock=lambda: clock[0]).run(worker.request,
            cancellation=Event(), deadline_ns=worker.request.expires_at_ns)
        assert replay.status == 'FAILED' and not replay.process_created
