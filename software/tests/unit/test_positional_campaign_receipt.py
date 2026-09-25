import os
from dataclasses import replace

import pytest

from rocell.application.positional_campaign_launch import (
    reserve_campaign_launch, claim_campaign_worker, verify_campaign_claim_receipt,
)
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from test_positional_campaign_launch import setup
from test_positional_campaign_native_protocol import fixture, seal


def prepared(tmp_path):
    reader, runtime = setup(tmp_path)
    launch = reserve_campaign_launch(tmp_path, reader, runtime_original=runtime)
    claim = claim_campaign_worker(tmp_path, reader, launch_sha256=launch)
    claim.consume()
    wire = fixture(tmp_path)
    body = reader.request.to_dict()
    wire['payload'].update(campaign_intent=body, registration={'fixture_only': True}, launch_sha256=launch)
    wire['operation_sha256'] = reader.request.sha256
    wire['registration_sha256'] = body['references']['runtime_sha256']
    raw = seal(wire)
    receipt = OwnedWorkerResult('SUCCEEDED', None, (), wire['request_sha256'], body['campaign_id'],
        True, True, True, 0, 8_000_000_000, len(raw), 10, 1, b'', b'',
        owned_process_id=os.getpid(), finished_monotonic_ns=10_000_000_000)
    return reader, raw, claim.claim_sha256, receipt


def verify(root, reader, raw, digest, receipt):
    return verify_campaign_claim_receipt(root, reader, request_original=raw,
        claim_sha256=digest, receipt=receipt)


def test_parent_receipt_does_not_promote_other_verification_layers(tmp_path):
    args = prepared(tmp_path)
    result = verify(tmp_path, *args)
    assert result['claim_receipt_association_verified'] and result['process_completion_verified']
    assert not any(result[key] for key in ('serial_cleanup_verified', 'endpoint_verified',
        'review_authenticity_verified', 'physical_stop_verified', 'motion_authorized', 'replay_allowed'))


@pytest.mark.parametrize('change', [dict(owned_process_id=1), dict(request_sha256='f'*64),
    dict(attempt_id='campaign-'+'f'*32), dict(finished_monotonic_ns=1), dict(owned_process_id=True)])
def test_wrong_parent_association_rejected(tmp_path, change):
    reader, raw, digest, receipt = prepared(tmp_path)
    with pytest.raises(ValueError):
        verify(tmp_path, reader, raw, digest, replace(receipt, **change))


@pytest.mark.parametrize('change', [dict(status='CANCELLED'), dict(tree_exit_confirmed=False),
    dict(returncode=True), dict(stdin_bytes_written=0), dict(cleanup_errors=('failure',)),
    dict(finished_monotonic_ns=32_000_000_000), dict(elapsed_ns=0)])
def test_uncertain_completion_retains_association_without_success(tmp_path, change):
    reader, raw, digest, receipt = prepared(tmp_path)
    result = verify(tmp_path, reader, raw, digest, replace(receipt, **change))
    assert result['claim_receipt_association_verified']
    assert not result['process_completion_verified']


@pytest.mark.parametrize('stage', ['launch', 'claimed'])
def test_changed_stored_original_rejects_parent_association(tmp_path, stage):
    reader, raw, digest, receipt = prepared(tmp_path)
    path = tmp_path / (reader.request.to_dict()['campaign_id'] + '-positional-' + stage + '.json')
    path.write_bytes(b'{}')
    with pytest.raises(ValueError):
        verify(tmp_path, reader, raw, digest, receipt)
