import hashlib
import base64
import json
import os
from dataclasses import replace

import pytest

from rocell.application.positional_campaign_native_retention import retain_native_trial, publish_native_campaign_result
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from test_positional_campaign_launch import setup
from test_positional_campaign_native_protocol import fixture, seal
from test_positional_campaign_native_capture import exercise


def prepared(tmp_path, monkeypatch, **kwargs):
    result = exercise(tmp_path, monkeypatch, **kwargs)[-1]
    context = tmp_path / 'reader-context'
    context.mkdir()
    reader, _ = setup(context)
    body = reader.request.to_dict()
    assert result['intent_sha256'] == reader.request.sha256
    prefix = body['campaign_id'] + '-positional-'
    launch = hashlib.sha256((tmp_path / (prefix + 'launch.json')).read_bytes()).hexdigest()
    claim = hashlib.sha256((tmp_path / (prefix + 'claimed.json')).read_bytes()).hexdigest()
    child = retain_native_trial(tmp_path, reader.request, result, claim_sha256=claim)
    wire = fixture(tmp_path)
    wire['payload'].update(campaign_intent=body, registration={'fixture_only': True}, launch_sha256=launch)
    wire['operation_sha256'] = reader.request.sha256
    wire['registration_sha256'] = body['references']['runtime_sha256']
    wire['expires_at_monotonic_ns'] = wire['parent_deadline_monotonic_ns'] = body['deadline_ns']
    raw = seal(wire)
    finished = result['cleanup']['finished_ns'] + 1_000_000
    receipt = OwnedWorkerResult('SUCCEEDED', None, (), wire['request_sha256'], body['campaign_id'],
        True, True, True, 0, finished - 2_000_000_000, len(raw), 10, 1, child, b'',
        owned_process_id=os.getpid(), finished_monotonic_ns=finished)
    return reader, raw, receipt


@pytest.mark.parametrize('missed_leg', [None, 1, 2])
def test_parent_retains_and_reconstructs_original_bound_native_results(tmp_path, monkeypatch, missed_leg):
    reader, raw, receipt = prepared(tmp_path, monkeypatch, missed_leg=missed_leg)
    path, report = publish_native_campaign_result(tmp_path, reader, request_original=raw, receipt=receipt)
    assert json.loads(path.read_bytes()) == report
    assert report['status'] == 'DATA_RECONSTRUCTED'
    assert report['endpoint_reported_complete'] is (missed_leg is None)
    assert report['process']['process_completion_verified']
    assert len(receipt.stdout) < 1024  # No expanded capture tree in IPC.
    for original in report['originals'].values():
        wrapper = json.loads((tmp_path / original['file']).read_bytes())
        stored = base64.b64decode(wrapper['base64'], validate=True)
        assert wrapper['bytes'] == len(stored)
        assert len(stored) == original['bytes']
        assert hashlib.sha256(stored).hexdigest() == original['sha256']
    with pytest.raises(Exception):
        publish_native_campaign_result(tmp_path, reader, request_original=raw, receipt=receipt)


@pytest.mark.parametrize('fault', ['child', 'empty_child', 'trial', 'pid', 'process_cleanup', 'lifetime'])
def test_bad_child_or_process_evidence_never_reports_endpoint_success(tmp_path, monkeypatch, fault):
    reader, raw, receipt = prepared(tmp_path, monkeypatch)
    if fault == 'child': receipt = replace(receipt, stdout=b'bad-json')
    if fault == 'empty_child': receipt = replace(receipt, stdout=b'')
    if fault == 'trial':
        (tmp_path / (reader.request.to_dict()['campaign_id'] + '-native-trial.json')).write_bytes(b'{}')
    if fault == 'pid': receipt = replace(receipt, owned_process_id=1)
    if fault == 'process_cleanup': receipt = replace(receipt, cleanup_errors=('failure',))
    if fault == 'lifetime': receipt = replace(receipt, elapsed_ns=1)
    _, report = publish_native_campaign_result(tmp_path, reader, request_original=raw, receipt=receipt)
    assert not report['endpoint_reported_complete']
    wrapper = json.loads((tmp_path / report['originals']['stdout']['file']).read_bytes())
    assert base64.b64decode(wrapper['base64']) == receipt.stdout
    assert not report['replay_allowed'] and not report['physical_movement_verified']


def test_cancelled_trial_is_retained_as_diagnostic_without_retry(tmp_path, monkeypatch):
    reader, raw, receipt = prepared(tmp_path, monkeypatch, cancel_after_write=True)
    _, report = publish_native_campaign_result(tmp_path, reader, request_original=raw, receipt=receipt)
    assert report['status'] == 'DIAGNOSTIC_RETAINED'
    assert report['reconstruction'] is None
    assert 'trial' in report['originals']
