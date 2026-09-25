"""Real temporary disk journal, no serial/process dispatch or native arm access."""

import hashlib
import base64
from concurrent.futures import ThreadPoolExecutor

import pytest

from rocell.application import passive_arm_attempt_store as store
from rocell.application.physical_onboarding_durability import (
    PhysicalOnboardingDurabilityError,
)
from rocell.application.arm_bench_qualification_contract import (
    PassiveBenchRequest,
    _canonical,
)
from rocell.application.passive_arm_entry_policy import PassiveEntryEvidence
from test_passive_arm_entry_policy import prepared


ATTEMPT = "operation-" + "a" * 32


def journal(root):
    request, evidence, originals = prepared()
    request["attempt_id"] = evidence["attempt_id"] = ATTEMPT
    registration = {"test_only": "not a worker registration"}
    request["references"]["runtime_sha256"] = hashlib.sha256(
        _canonical(registration)
    ).hexdigest()
    return store.PassiveAttemptJournal(
        root,
        PassiveBenchRequest(_canonical(request)),
        PassiveEntryEvidence(_canonical(evidence)),
        originals,
        registration,
        now_monotonic_ns=2_000_000_000,
    )


def test_exact_originals_consumption_and_invalid_raw_outcome_retained(tmp_path):
    attempt = journal(tmp_path)
    assert (
        store.inspect_attempt(tmp_path, ATTEMPT)["status"] == "PREPARED_NOT_REPLAYABLE"
    )
    receipt = attempt.consume(now_monotonic_ns=3_000_000_000)
    assert receipt["physical_authority"] is False
    assert (
        store.inspect_attempt(tmp_path, ATTEMPT)["status"]
        == "OUTCOME_UNKNOWN_NO_REPLAY"
    )
    attempt.retain_outcome(
        stdout=b"malformed JSON", stderr=b"error", process_status="FAILED"
    )
    recovered = store.inspect_attempt(tmp_path, ATTEMPT)
    assert recovered["status"] == "OUTCOME_RETAINED_NOT_DEVICE_ACCEPTANCE"
    assert recovered["records"]["outcome"]["body"]["process_status"] == "FAILED"
    assert recovered["authenticated"] is False


def test_restart_cannot_replace_prepared_attempt_or_replay(tmp_path):
    attempt = journal(tmp_path)
    attempt.consume(now_monotonic_ns=3_000_000_000)
    with pytest.raises(PhysicalOnboardingDurabilityError, match="already exists"):
        journal(tmp_path)
    with pytest.raises(ValueError, match="already consumed"):
        attempt.consume(now_monotonic_ns=3_000_000_001)


def test_concurrent_consumers_have_exactly_one_winner(tmp_path):
    attempt = journal(tmp_path)

    def consume():
        try:
            attempt.consume(now_monotonic_ns=3_000_000_000)
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(lambda _: consume(), range(4))).count(True) == 1


def test_failed_consume_publication_burns_live_instance(tmp_path, monkeypatch):
    attempt = journal(tmp_path)

    def fail(*args, **kwargs):
        raise OSError("simulated storage interruption")

    monkeypatch.setattr(store, "_publish", fail)
    with pytest.raises(OSError):
        attempt.consume(now_monotonic_ns=3_000_000_000)
    with pytest.raises(ValueError, match="already consumed"):
        attempt.consume(now_monotonic_ns=3_000_000_000)
    with pytest.raises(ValueError):
        attempt.retain_outcome(stdout=b"", stderr=b"", process_status="UNKNOWN")


def test_deadline_failure_does_not_permit_retry(tmp_path):
    attempt = journal(tmp_path)
    with pytest.raises(ValueError):
        attempt.consume(now_monotonic_ns=19_000_000_000)
    with pytest.raises(ValueError, match="already consumed"):
        attempt.consume(now_monotonic_ns=3_000_000_000)


def test_outcome_once_only_and_process_exit_not_device_cleanup(tmp_path):
    attempt = journal(tmp_path)
    attempt.consume(now_monotonic_ns=3_000_000_000)
    attempt.retain_outcome(stdout=b"{}", stderr=b"", process_status="SUCCEEDED")
    with pytest.raises(ValueError):
        attempt.retain_outcome(stdout=b"{}", stderr=b"", process_status="SUCCEEDED")
    body = store.inspect_attempt(tmp_path, ATTEMPT)["records"]["outcome"]["body"]
    assert body["device_cleanup"] == "NOT_ESTABLISHED_BY_PROCESS_STATUS"


def test_no_record_is_not_permission(tmp_path):
    result = store.inspect_attempt(tmp_path, ATTEMPT)
    assert result["status"] == "NO_ATTEMPT"
    assert result["replay_allowed"] is result["physical_authority"] is False


def test_full_supervisor_output_retained_byte_for_byte(tmp_path):
    attempt = journal(tmp_path)
    attempt.consume(now_monotonic_ns=3_000_000_000)
    # Include non-UTF8 data: retaining diagnostics must not depend on decoding
    # or on the worker returning a valid result document.
    stdout = bytes(range(256)) * (store.MAX_STDOUT_BYTES // 256)
    stderr = b"\xff" * store.MAX_STDERR_BYTES
    attempt.retain_outcome(stdout=stdout, stderr=stderr, process_status="FAILED")
    body = store.inspect_attempt(tmp_path, ATTEMPT)["records"]["outcome"]["body"]
    assert base64.b64decode(body["stdout_base64"], validate=True) == stdout
    assert base64.b64decode(body["stderr_base64"], validate=True) == stderr
    assert body["device_cleanup"] == "NOT_ESTABLISHED_BY_PROCESS_STATUS"


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_output_over_budget_burns_outcome_without_truncation(tmp_path, stream):
    attempt = journal(tmp_path)
    attempt.consume(now_monotonic_ns=3_000_000_000)
    output = {"stdout": b"", "stderr": b"", "process_status": "FAILED"}
    limit = store.MAX_STDOUT_BYTES if stream == "stdout" else store.MAX_STDERR_BYTES
    output[stream] = b"x" * (limit + 1)
    with pytest.raises(ValueError, match="Bounded raw process output"):
        attempt.retain_outcome(**output)
    with pytest.raises(ValueError, match="first outcome"):
        attempt.retain_outcome(stdout=b"", stderr=b"", process_status="UNKNOWN")
    recovered = store.inspect_attempt(tmp_path, ATTEMPT)
    assert recovered["records"]["outcome"] is None
    assert recovered["status"] == "OUTCOME_UNKNOWN_NO_REPLAY"


@pytest.mark.parametrize("value", ["../escape", "COM6", "operation-xxx", "", None])
def test_no_path_or_device_input(tmp_path, value):
    with pytest.raises(ValueError):
        store.inspect_attempt(tmp_path, value)
