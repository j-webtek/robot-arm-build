"""Synthetic metadata, wire captures and fixture keys; zero native IO."""
from dataclasses import replace
import math
from concurrent.futures import ThreadPoolExecutor

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import (
    publish_reservation_bytes, PhysicalOnboardingDurabilityError,
)
from rocell.application.absolute_wrist_command_binding import AbsoluteWristCommandBinding
from rocell.providers.windows.absolute_wrist_current_context import (
    AbsoluteWristCurrentContextReader, AuthenticatedAbsoluteWristReader,
)
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from rocell.safety.bench_review_authority import BenchReviewAuthority
from test_absolute_wrist_review_authority import intent, review
from test_endpoint_current_context import fixture as endpoint_fixture
from test_first_motion_analysis import wire


def fixture(tmp_path):
    _, snapshots, _, binding = endpoint_fixture()
    body = intent()
    body['references']['native_controller_review_sha256'] = binding.binding_sha256
    body['draft']['expected_start_joints_rad'] = dict(b=0., s=0., e=0., t=math.radians(-4), r=0., g=0.)
    request = AbsoluteWristIntent(canonical(body))
    clock = [2_000_000_000]
    refs = [tuple(sorted(body['references'].items()))]
    def metadata():
        return replace(snapshots[0], started_monotonic_ns=clock[0], finished_monotonic_ns=clock[0])
    context = AbsoluteWristCurrentContextReader(request, binding=binding,
        connection_id=body['attempt_id'], metadata_reader=metadata,
        references_reader=lambda: refs[0], clock_ns=lambda: clock[0])
    authority = BenchReviewAuthority(b'Z' * 32).for_absolute_wrist_diagnostic()
    raw = authority.seal(body, review(), now_ns=1_000_000_002)
    publish_reservation_bytes(tmp_path, body['attempt_id'] + '-absolute-wrist-reviews.json', raw,
                              maximum_bytes=8192)
    reader = AuthenticatedAbsoluteWristReader(request, root=tmp_path, authority=authority,
        context_reader=context, clock_ns=lambda: clock[0])
    return request, reader, clock, refs, snapshots


def selected(tmp_path):
    request, reader, clock, refs, snapshots = fixture(tmp_path)
    latch = AbsoluteWristCommandBinding(request, reader=reader, root=tmp_path)
    latch.claim_open()
    raw, windows = wire([math.radians(-4)] * 10, 2_000_000_000)
    clock[0] = 2_500_000_000
    result = latch.bind_baseline(raw, windows, started_ns=2_000_000_000,
                                 finished_ns=2_500_000_000)
    assert result['candidate_command']['rad'] == 0
    return latch, request, reader, clock, refs, snapshots


def test_one_use_selection_and_no_reopen(tmp_path):
    latch, request, reader, _, _, _ = selected(tmp_path)
    assert latch.consume_command() == b'{"T":101,"joint":4,"rad":0.0,"spd":20,"acc":1}\n'
    for operation in (latch.consume_command, latch.claim_open):
        with pytest.raises(ValueError): operation()
    with pytest.raises((ValueError, FileExistsError, PhysicalOnboardingDurabilityError)):
        AbsoluteWristCommandBinding(request, reader=reader, root=tmp_path)
    assert len(list(tmp_path.glob('*-dispatch-claim.json'))) == 1


def test_concurrent_consumers_only_one_receives_command(tmp_path):
    latch, *_ = selected(tmp_path)
    def consume(_):
        try: return latch.consume_command()
        except ValueError: return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(consume, range(4)))
    assert sum(value is not None for value in results) == 1


@pytest.mark.parametrize('fault', ['stale', 'references', 'bundle', 'selection', 'process', 'cancel'])
def test_fault_burns_selection_without_retry(tmp_path, monkeypatch, fault):
    latch, request, _, clock, refs, _ = selected(tmp_path)
    if fault == 'stale': clock[0] += 300_000_000
    if fault == 'references': refs[0] = ()
    if fault in ('bundle', 'selection'):
        suffix = 'reviews' if fault == 'bundle' else 'selection'
        (tmp_path/(request.to_dict()['attempt_id'] + '-absolute-wrist-' + suffix + '.json')).write_bytes(b'{}')
    if fault == 'process':
        monkeypatch.setattr('rocell.application.absolute_wrist_command_binding.os.getpid', lambda: -1)
    if fault == 'cancel': latch.revoke()
    with pytest.raises(ValueError): latch.consume_command()
    with pytest.raises(ValueError): latch.consume_command()


def test_storage_delay_rechecks_selected_baseline(tmp_path, monkeypatch):
    latch, _, _, clock, _, _ = selected(tmp_path)
    original = latch._save
    def delayed(suffix, body):
        original(suffix, body)
        if suffix == 'dispatch-claim': clock[0] += 300_000_000
    monkeypatch.setattr(latch, '_save', delayed)
    with pytest.raises(ValueError): latch.consume_command()
    assert len(list(tmp_path.glob('*-dispatch-claim.json'))) == 1
    with pytest.raises(ValueError): latch.consume_command()


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'port', 'references', 'bundle'])
def test_current_metadata_and_original_changes_rejected(tmp_path, fault):
    request, reader, _, refs, snapshots = fixture(tmp_path)
    if fault == 'missing': snapshots[0] = replace(snapshots[0], native_observations=())
    if fault == 'duplicate': snapshots[0] = replace(snapshots[0], native_observations=snapshots[0].native_observations*2)
    if fault == 'port':
        snapshots[0] = replace(snapshots[0], native_observations=(replace(
            snapshots[0].native_observations[0], port_name='COM8'),))
    if fault == 'references': refs[0] = ()
    if fault == 'bundle':
        (tmp_path/(request.to_dict()['attempt_id']+'-absolute-wrist-reviews.json')).write_bytes(b'{}')
    with pytest.raises(ValueError): AbsoluteWristCommandBinding(request, reader=reader, root=tmp_path)
    assert not list(tmp_path.glob('*-reservation.json'))


@pytest.mark.parametrize('fault', ['corrupt', 'drift', 'predates', 'too_large', 'expired'])
def test_bad_baseline_burns_attempt(tmp_path, fault):
    request, reader, clock, _, _ = fixture(tmp_path)
    latch = AbsoluteWristCommandBinding(request, reader=reader, root=tmp_path)
    latch.claim_open()
    values = [math.radians(-4)] * 10
    if fault == 'drift': values = [math.radians(-3)] * 10
    raw, windows = wire(values, 2_000_000_000, corrupt_at=3 if fault == 'corrupt' else None)
    clock[0] = 2_500_000_000
    start = 2_000_000_000
    if fault == 'predates': start = request.to_dict()['issued_ns'] - 1
    if fault == 'too_large': raw = b'x' * 16385
    if fault == 'expired': clock[0] = 20_000_000_000
    with pytest.raises(ValueError):
        latch.bind_baseline(raw, windows, started_ns=start, finished_ns=2_500_000_000)
    with pytest.raises(ValueError): latch.consume_command()
    with pytest.raises(ValueError): latch.claim_open()


def test_dispatch_publication_failure_never_returns_or_retries(tmp_path, monkeypatch):
    latch, *_ = selected(tmp_path)
    original = latch._save
    def fail_after_publish(suffix, body):
        original(suffix, body)
        if suffix == 'dispatch-claim': raise OSError('synthetic storage failure')
    monkeypatch.setattr(latch, '_save', fail_after_publish)
    with pytest.raises(OSError): latch.consume_command()
    with pytest.raises(ValueError): latch.consume_command()
    assert len(list(tmp_path.glob('*-dispatch-claim.json'))) == 1
