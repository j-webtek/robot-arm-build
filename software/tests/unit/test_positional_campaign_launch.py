from concurrent.futures import ThreadPoolExecutor
from itertools import cycle

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.positional_campaign_launch import reserve_campaign_launch, claim_campaign_worker
from test_positional_current_context import fixture


def setup(tmp_path):
    runtime = canonical(dict(fixture_only=True))
    reader, _, _, _ = fixture(tmp_path, runtime_original=runtime)
    # Repeat real metadata resolution and signed-review verification for each
    # boundary. This fixed fake clock does not replace the authenticated reader.
    clock = cycle((2_000_000_000, 2_020_000_000))
    reader._context._clock = lambda: next(clock)
    return reader, runtime


def test_launch_and_process_claim_are_each_durable_and_one_use(tmp_path):
    reader, runtime = setup(tmp_path)
    launch = reserve_campaign_launch(tmp_path, reader, runtime_original=runtime)
    with pytest.raises(Exception):
        reserve_campaign_launch(tmp_path, reader, runtime_original=runtime)
    claim = claim_campaign_worker(tmp_path, reader, launch_sha256=launch)
    claim.consume()
    with pytest.raises(ValueError, match='consumed'):
        claim.consume()
    with pytest.raises(Exception):
        claim_campaign_worker(tmp_path, reader, launch_sha256=launch)


@pytest.mark.parametrize('fault', ['review', 'launch', 'claimed', 'pid'])
def test_changed_original_or_process_burns_claim_without_replay(tmp_path, monkeypatch, fault):
    reader, runtime = setup(tmp_path)
    launch = reserve_campaign_launch(tmp_path, reader, runtime_original=runtime)
    claim = claim_campaign_worker(tmp_path, reader, launch_sha256=launch)
    if fault == 'pid':
        monkeypatch.setattr('rocell.application.positional_campaign_launch.os.getpid', lambda: 0)
    else:
        suffix = 'review' if fault == 'review' else fault
        path = tmp_path / (reader.request.to_dict()['campaign_id'] + '-positional-' + suffix + '.json')
        path.write_bytes(b'{}')
    with pytest.raises(ValueError):
        claim.consume()
    with pytest.raises(ValueError, match='consumed'):
        claim.consume()


def test_concurrent_process_claimants_cannot_both_succeed(tmp_path):
    reader, runtime = setup(tmp_path)
    launch = reserve_campaign_launch(tmp_path, reader, runtime_original=runtime)
    # Each contender has its own resolver clock, as separate workers would.
    def contender(_):
        from copy import copy
        local = copy(reader)
        local._context = copy(reader._context)
        clock = cycle((2_000_000_000, 2_020_000_000))
        local._context._clock = lambda: next(clock)
        try:
            return claim_campaign_worker(tmp_path, local, launch_sha256=launch)
        except (ValueError, OSError, RuntimeError):
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(contender, range(2)))
    assert sum(claim is not None for claim in claims) == 1


def test_runtime_mismatch_creates_no_launch_record(tmp_path):
    reader, _ = setup(tmp_path)
    with pytest.raises(ValueError, match='runtime original differs'):
        reserve_campaign_launch(tmp_path, reader, runtime_original=canonical(dict(other=True)))
    assert not list(tmp_path.glob('*-positional-launch.json'))


def test_stale_current_context_cannot_claim_reserved_launch(tmp_path):
    reader, runtime = setup(tmp_path)
    launch = reserve_campaign_launch(tmp_path, reader, runtime_original=runtime)
    reader._clock = lambda: 7_000_000_001
    with pytest.raises(ValueError):
        claim_campaign_worker(tmp_path, reader, launch_sha256=launch)
    assert not list(tmp_path.glob('*-positional-claimed.json'))
    assert list(tmp_path.glob('*-positional-launch.json'))
