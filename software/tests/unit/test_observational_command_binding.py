import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from rocell.application.observational_command_binding import ObservationalCommandBinding
from test_first_motion_analysis import wire


def inputs(root):
    return dict(root=root, session_id='wizard-'+'1'*32, attempt_id='operation-'+'2'*32,
        connection_id='operation-'+'2'*32,
        usb_identity=dict(vid=0x10c4, pid=0xea60, serial_number='A'*32),
        issued_ns=1_000_000_000, deadline_ns=21_000_000_000)


def context(root):
    values = inputs(root)
    return {k: values[k] for k in ('session_id', 'connection_id', 'usb_identity')}


def bound(root):
    binding = ObservationalCommandBinding(**inputs(root))
    raw, windows = wire([.02]*10, 2_000_000_000)
    report = binding.bind_baseline(raw, windows, started_ns=2_000_000_000,
        finished_ns=2_500_000_000, now_ns=2_500_000_000, **context(root))
    return binding, report


def test_derives_command_and_consumes_once(tmp_path):
    binding, report = bound(tmp_path)
    payload = binding.consume_command(now_ns=2_500_000_001, **context(tmp_path))
    assert json.loads(payload) == report['preview']['candidate_command']
    assert report['motion_authorized'] is False
    with pytest.raises(ValueError):
        binding.consume_command(now_ns=2_500_000_002, **context(tmp_path))
    with pytest.raises(Exception):
        ObservationalCommandBinding(**inputs(tmp_path))


@pytest.mark.parametrize('fault', ['session', 'connection', 'identity', 'stale', 'backwards', 'selection'])
def test_failed_consumption_cannot_retry(tmp_path, fault):
    binding, _ = bound(tmp_path)
    current = context(tmp_path)
    now = 2_500_000_001
    if fault == 'session': current['session_id'] = 'wizard-'+'3'*32
    if fault == 'connection': current['connection_id'] = 'operation-'+'4'*32
    if fault == 'identity': current['usb_identity']['serial_number'] = 'B'*32
    if fault == 'stale': now = 2_800_000_000
    if fault == 'backwards': now = 2_499_999_999
    if fault == 'selection':
        binding._selection_path.write_bytes(b'{}')
    with pytest.raises(ValueError):
        binding.consume_command(now_ns=now, **current)
    with pytest.raises(ValueError):
        binding.consume_command(now_ns=2_500_000_002, **context(tmp_path))


def test_concurrent_consumption_has_one_winner(tmp_path):
    binding, _ = bound(tmp_path)
    def consume(_):
        try:
            return binding.consume_command(now_ns=2_500_000_001, **context(tmp_path))
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(consume, range(4)))
    assert sum(value is not None for value in outputs) == 1


def test_invalid_baseline_burns_attempt(tmp_path):
    binding = ObservationalCommandBinding(**inputs(tmp_path))
    for _ in range(2):
        with pytest.raises(ValueError):
            binding.bind_baseline(b'bad\n', [[0,4,2_000_000_000,2_000_000_001]],
                started_ns=2_000_000_000, finished_ns=2_500_000_000,
                now_ns=2_500_000_000, **context(tmp_path))


@pytest.mark.parametrize('age_ns,accepted', [
    (125_000_000, True),
    (250_000_000, True),
    (250_000_001, False),
])
def test_dispatch_host_age_boundary_is_one_use(tmp_path, age_ns, accepted):
    binding, report = bound(tmp_path)
    now = report['preview']['baseline_last_host_received_ns'] + age_ns
    if accepted:
        assert json.loads(binding.consume_command(now_ns=now, **context(tmp_path))) == report['preview']['candidate_command']
    else:
        with pytest.raises(ValueError, match='Selected baseline'):
            binding.consume_command(now_ns=now, **context(tmp_path))
    with pytest.raises(ValueError, match='No unconsumed'):
        binding.consume_command(now_ns=now, **context(tmp_path))


def test_dispatch_allowance_does_not_relax_baseline_end_recency(tmp_path):
    binding = ObservationalCommandBinding(**inputs(tmp_path))
    raw, windows = wire([.02]*10, 2_000_000_000)
    with pytest.raises(ValueError, match='Baseline recency'):
        binding.bind_baseline(raw, windows, started_ns=2_000_000_000,
            finished_ns=2_500_000_000, now_ns=2_600_000_001, **context(tmp_path))
    with pytest.raises(ValueError, match='No unconsumed'):
        binding.consume_command(now_ns=2_600_000_001, **context(tmp_path))
