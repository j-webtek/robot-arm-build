"""Raw load reporting must not invent values or accept corrupted originals."""
import base64
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from review_roll_load import summarize_samples


def sample(body):
    raw = json.dumps(body).encode()
    return dict(status='SUCCEEDED', response_base64=base64.b64encode(raw).decode(),
                response_sha256=hashlib.sha256(raw).hexdigest())


def test_missing_and_failure_not_filled():
    result = summarize_samples([sample({'tR': -20}), sample({'tR': 24}),
                                sample({}), {'status': 'FAILED'}])
    assert result['raw_tR_mean'] == 2
    assert result['missing_field_samples'] == 1
    assert result['failed_samples'] == 1
    assert summarize_samples([])['raw_tR_mean'] is None


def test_corrupted_original_rejected():
    row = sample({'tR': 24})
    row['response_sha256'] = '0'*64
    with pytest.raises(ValueError, match='hash mismatch'):
        summarize_samples([row])


@pytest.mark.parametrize('value', [True, '24', float('nan'), float('inf')])
def test_invalid_field_rejected(value):
    with pytest.raises(ValueError, match='Invalid raw'):
        summarize_samples([sample({'tR': value})])
