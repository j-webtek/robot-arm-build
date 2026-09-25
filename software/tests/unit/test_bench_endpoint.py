"""All service reviews/writers below are synthetic; no native imports or I/O."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
import time

import pytest

from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.application.endpoint_write_boundary import EndpointWriteBoundary, EndpointWriteContext
from rocell.safety.bench_endpoint import (
    BenchEndpointEvidence, REQUIRED_CHECKS, authorize_bench_endpoint,
)
from test_endpoint_trial_contract import request, encoded


def setup():
    body = request().to_dict()
    now = time.monotonic_ns()
    body.update(issued_monotonic_ns=now, deadline_monotonic_ns=now+20_000_000_000)
    req = EndpointTrialRequest(encoded(body))
    def evidence():
        return BenchEndpointEvidence(req.request_sha256, 'owned-test',
            tuple(sorted(body['references'].items())),
            tuple((name, 'c'*64) for name in sorted(REQUIRED_CHECKS)),
            time.monotonic_ns(), body['deadline_monotonic_ns'])
    return req, evidence


def test_bench_admission_has_no_cell_capability_and_is_one_use(tmp_path):
    req, reader = setup()
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader, attempt_root=tmp_path)
    assert not hasattr(permit, 'capability') and not hasattr(permit, 'allows')
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: permit.consume(req, 'owned-test'), range(16)))
    assert outcomes.count(True) == 1


@pytest.mark.parametrize('change', [
    {'request_sha256':'f'*64}, {'connection_id':'other'}, {'references':()},
    {'checks':()}, {'verified_at_ns':True}, {'expires_at_ns':True},
    {'verified_at_ns':1}, {'expires_at_ns':2**63},
])
def test_invalid_reviews_refused(change, tmp_path):
    req, reader = setup()
    with pytest.raises(ValueError):
        authorize_bench_endpoint(req, connection_id='owned-test', attempt_root=tmp_path,
            evidence_reader=lambda: replace(reader(), **change))


def test_each_review_is_required(tmp_path):
    req, reader = setup()
    for missing in REQUIRED_CHECKS:
        evidence = reader()
        with pytest.raises(ValueError):
            authorize_bench_endpoint(req, connection_id='owned-test', attempt_root=tmp_path, evidence_reader=lambda:
                replace(evidence, checks=tuple(row for row in evidence.checks if row[0] != missing)))


def test_changed_originals_after_admission_burn_attempt(tmp_path):
    req, reader = setup()
    current = [reader()]
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=lambda: current[0], attempt_root=tmp_path)
    current[0] = replace(reader(), references=())
    assert not permit.consume(req, 'owned-test')
    current[0] = reader()
    assert not permit.consume(req, 'owned-test')


def test_wrong_connection_burns_attempt(tmp_path):
    req, reader = setup()
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader, attempt_root=tmp_path)
    assert not permit.consume(req, 'different')
    assert not permit.consume(req, 'owned-test')


def test_changed_review_hash_cannot_replace_approved_original(tmp_path):
    req, reader = setup()
    current = [reader()]
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=lambda: current[0], attempt_root=tmp_path)
    current[0] = replace(reader(), checks=tuple((name, 'd'*64) for name in sorted(REQUIRED_CHECKS)))
    assert not permit.consume(req, 'owned-test')


def test_changed_exact_target_is_refused(tmp_path):
    req, reader = setup()
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader, attempt_root=tmp_path)
    body = req.to_dict()
    body['trial_id'] = 'back'
    assert not permit.consume(EndpointTrialRequest(encoded(body)), 'owned-test')


def test_cancellation_before_dispatch_writes_nothing_and_revokes(tmp_path):
    req, reader = setup()
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader, attempt_root=tmp_path)
    boundary = EndpointWriteBoundary(req, permit, connection_id='owned-test')
    cancel = Event()
    cancel.set()
    def forbidden(*args):
        pytest.fail('Cancelled boundary must not read context or write')
    result = boundary.attempt(context_reader=forbidden, write_once=forbidden, cancellation=cancel)
    assert not result['write_attempted']
    assert not permit.consume(req, 'owned-test')


@pytest.mark.parametrize('short', [False, True])
def test_bench_boundary_writes_once_without_full_cell_release(short, tmp_path):
    req, reader = setup()
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader, attempt_root=tmp_path)
    boundary = EndpointWriteBoundary(req, permit, connection_id='owned-test')
    writes = []
    def write(payload):
        writes.append(payload)
        return len(payload)-1 if short else len(payload)
    def context():
        return EndpointWriteContext('owned-test', 'A'*32, reader().references,
            (0,0,0,0,0,0), time.monotonic_ns(), req.to_dict()['deadline_monotonic_ns'])
    result = boundary.attempt(context_reader=context, write_once=write, cancellation=Event())
    assert len(writes) == 1
    assert result['status'] == ('WRITE_UNCERTAIN_NO_RETRY' if short else 'BYTES_WRITTEN_NOT_MOVEMENT_VERIFIED')
    assert not result['physical_movement_verified']
    assert not permit.consume(req, 'owned-test')
    with pytest.raises(ValueError):
        boundary.attempt(context_reader=context, write_once=write, cancellation=Event())
