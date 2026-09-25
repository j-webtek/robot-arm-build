"""Reserved-entry verification using fixture keys; no device or process IO."""
import json

import pytest

from rocell.application.absolute_wrist_worker_preparation import prepare_absolute_wrist_worker
from rocell.providers.windows import absolute_wrist_prelaunch as prelaunch
from rocell.providers.windows import bench_review_key
from test_absolute_wrist_timed_preparation import fixture


def prepared(tmp_path, monkeypatch):
    workspace, staged, request, signed, _, _ = fixture(tmp_path, monkeypatch)
    authority = bench_review_key.load_host_absolute_wrist_review_authority(workspace)
    monkeypatch.setattr(prelaunch, 'load_host_absolute_wrist_review_authority', lambda _: authority)
    result = prepare_absolute_wrist_worker(workspace, staged, request,
        review_original=signed, clock_ns=lambda: 2_000_000_000)
    return workspace, request, json.loads(result.request.payload_json)


def test_reserved_entry_verifies_without_launch(tmp_path, monkeypatch):
    workspace, request, payload = prepared(tmp_path, monkeypatch)
    assert prelaunch.verify_reserved_absolute_wrist_entry(payload,
        workspace=workspace, clock_ns=lambda: 3_000_000_000) == request
    assert not list(tmp_path.glob('*-claimed.json'))


@pytest.mark.parametrize('fault', ['review', 'launch', 'runtime', 'expired', 'clock_regression', 'key', 'source'])
def test_reserved_entry_refuses_changed_context(tmp_path, monkeypatch, fault):
    workspace, request, payload = prepared(tmp_path, monkeypatch)
    attempt = request.to_dict()['attempt_id']
    if fault in ('review', 'launch'):
        suffix = 'reviews' if fault == 'review' else fault
        (tmp_path/(attempt+'-absolute-wrist-'+suffix+'.json')).write_bytes(b'{}')
    if fault == 'runtime':
        (tmp_path/(attempt+'-absolute-wrist-native-child')/'runtime.original.json').write_bytes(b'{}')
    if fault == 'key':
        def missing(_): raise ValueError('Fixture missing key')
        monkeypatch.setattr(prelaunch, 'load_host_absolute_wrist_review_authority', missing)
    if fault == 'source':
        monkeypatch.setattr('rocell.application.absolute_wrist_reference_reader.source_fingerprint', lambda _: 'f'*64)
    ticks = iter([3_000_000_000, 2_000_000_000])
    clock = (lambda: next(ticks)) if fault == 'clock_regression' else lambda: (
        32_000_000_000 if fault == 'expired' else 3_000_000_000)
    with pytest.raises(ValueError):
        prelaunch.verify_reserved_absolute_wrist_entry(payload, workspace=workspace, clock_ns=clock)
    assert not list(tmp_path.glob('*-claimed.json'))


def test_preparation_rejects_clock_regression_before_reservation(tmp_path, monkeypatch):
    workspace, staged, request, signed, _, _ = fixture(tmp_path, monkeypatch)
    ticks = iter([3_000_000_000, 2_000_000_000])
    with pytest.raises(ValueError, match='clock regressed'):
        prepare_absolute_wrist_worker(workspace, staged, request,
            review_original=signed, clock_ns=lambda: next(ticks))
    assert not list(tmp_path.glob('*-launch.json'))


def test_host_absolute_key_loader_only_derives_existing_authority(monkeypatch):
    from rocell.safety.bench_review_authority import BenchReviewAuthority
    from test_absolute_wrist_review_authority import intent, review
    calls = []
    authority = BenchReviewAuthority(b'J'*32)
    def load(workspace):
        calls.append(workspace)
        return authority
    monkeypatch.setattr(bench_review_key, 'load_host_bench_review_authority', load)
    monkeypatch.setattr(bench_review_key, 'provision_bench_review_key',
        lambda _: pytest.fail('Loading must not provision keys'))
    derived = bench_review_key.load_host_absolute_wrist_review_authority('fixture-workspace')
    body = intent()
    raw = derived.seal(body, review(), now_ns=1_000_000_002)
    authority.for_absolute_wrist_diagnostic().verify(raw, expected_intent=body,
        current_usb_identity=body['usb_identity'], current_references=body['references'],
        now_ns=1_000_000_003)
    assert calls == ['fixture-workspace']
