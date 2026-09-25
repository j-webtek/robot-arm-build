"""Collect original files without accepting their meaning or dispatching."""

import base64
import hashlib

import pytest

from rocell.application.passive_arm_attempt_export import collect_attempt
from test_passive_arm_attempt_store import journal, ATTEMPT


def restored(record):
    return b"".join(
        base64.b64decode(part, validate=True) for part in record["base64_chunks"]
    )


def test_consumed_unknown_attempt_preserves_originals(tmp_path):
    attempt = journal(tmp_path)
    attempt.consume(now_monotonic_ns=3_000_000_000)
    result = collect_attempt(tmp_path, ATTEMPT)
    for stage in ("prepared", "consumed"):
        expected = (
            tmp_path / (ATTEMPT + "-physical-passive-" + stage + ".json")
        ).read_bytes()
        assert restored(result["stages"][stage]) == expected
        assert result["stages"][stage]["sha256"] == hashlib.sha256(expected).hexdigest()
    assert result["stages"]["outcome"] == {"status": "MISSING"}
    assert result["authenticated"] is result["replay_allowed"] is False


def test_malformed_partial_claim_is_preserved_not_repaired(tmp_path):
    journal(tmp_path)
    path = tmp_path / (ATTEMPT + "-physical-passive-claimed.json")
    path.write_bytes(b"{\xffpartial")  # Deliberately corrupted test fixture only.
    result = collect_attempt(tmp_path, ATTEMPT)
    assert restored(result["stages"]["claimed"]) == b"{\xffpartial"
    assert path.read_bytes() == b"{\xffpartial"
    assert result["physical_authority"] is False


@pytest.mark.parametrize("value", ["../escape", "COM6", "operation-invalid"])
def test_rejects_arbitrary_paths(tmp_path, value):
    with pytest.raises(ValueError):
        collect_attempt(tmp_path, value)
