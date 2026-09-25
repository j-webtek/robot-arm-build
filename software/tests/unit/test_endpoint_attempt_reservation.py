"""Crash/restart/concurrent admission tests; no serial provider is used."""

from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
import multiprocessing

import pytest

from rocell.application import endpoint_attempt_reservation as storage
from rocell.application.physical_onboarding_durability import (
    publish_bytes, PublicationMode,
)
from rocell.safety.bench_endpoint import authorize_bench_endpoint
from test_bench_endpoint import setup


def _issue_in_separate_process(root):
    # Each process creates fresh request timing but uses the SAME attempt ID.
    # Changing timing/request content must not bypass the persistent ID claim.
    req, reader = setup()
    try:
        authorize_bench_endpoint(req, connection_id='owned-test',
                                 evidence_reader=reader, attempt_root=root)
        return True
    except Exception:
        return False


def test_separate_processes_can_issue_only_one_permit(tmp_path):
    with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context('spawn')) as pool:
        results = list(pool.map(_issue_in_separate_process, [str(tmp_path)]*2))
    assert results.count(True) == 1
    # A new process/later request cannot resume the winning attempt either.
    assert not _issue_in_separate_process(str(tmp_path))


def test_revocation_does_not_free_attempt_id(tmp_path):
    req, reader = setup()
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader,
                                     attempt_root=tmp_path)
    permit.revoke()
    with pytest.raises(Exception):
        authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader,
                                 attempt_root=tmp_path)


def test_partial_reservation_survives_failure_and_prevents_retry(tmp_path, monkeypatch):
    real_publish = storage.publish_reservation_bytes
    def crash(checkpoint):
        if checkpoint == 'publication.after_temp_create':
            raise RuntimeError('Injected process interruption')
    def interrupted(*args, **kwargs):
        return real_publish(*args, **kwargs, fault_injector=crash)
    req, reader = setup()
    monkeypatch.setattr(storage, 'publish_reservation_bytes', interrupted)
    with pytest.raises(RuntimeError):
        authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader,
                                 attempt_root=tmp_path)
    records = list(tmp_path.glob('*-bench-endpoint-reserved.json'))
    assert len(records) == 1 and records[0].stat().st_size == 0
    monkeypatch.setattr(storage, 'publish_reservation_bytes', real_publish)
    with pytest.raises(Exception):
        authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader,
                                 attempt_root=tmp_path)


def test_changed_reservation_refuses_consumption(tmp_path):
    req, reader = setup()
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader,
                                     attempt_root=tmp_path)
    record = next(tmp_path.glob('*-bench-endpoint-reserved.json'))
    publish_bytes(tmp_path, record.name, b'{}', mode=PublicationMode.REPLACE)
    assert not permit.consume(req, 'owned-test')


def test_review_change_during_publication_burns_id(tmp_path):
    req, reader = setup()
    calls = 0
    def changed():
        nonlocal calls
        calls += 1
        evidence = reader()
        if calls > 1:
            evidence = replace(evidence, checks=tuple((name, 'd'*64) for name, _ in evidence.checks))
        return evidence
    with pytest.raises(ValueError, match='changed during reservation'):
        authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=changed,
                                 attempt_root=tmp_path)
    with pytest.raises(Exception):
        authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader,
                                 attempt_root=tmp_path)
