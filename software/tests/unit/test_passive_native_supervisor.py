"""Owned real child tests which reject fixture setup before metadata/device I/O."""

import hashlib
from threading import Event
import time

from rocell.application.arm_bench_qualification_contract import (
    PassiveBenchRequest,
    _canonical,
)
from rocell.application.passive_arm_entry_policy import PassiveEntryEvidence
from rocell.application.passive_arm_attempt_store import (
    PassiveAttemptJournal,
    inspect_attempt,
)
from rocell.providers.windows.owned_worker_process import (
    OwnedWorkerRequest,
    OwnedWindowsWorker,
    owned_registration_document,
)
from test_passive_arm_entry_policy import prepared
from test_passive_native_registration import registration, ATTEMPT


def prepared_dispatch(root):
    reg = registration(root)
    raw, evidence, originals = prepared()
    now = time.monotonic_ns()
    raw["attempt_id"] = evidence["attempt_id"] = ATTEMPT
    evidence["setup_confirmed_monotonic_ns"] = now
    raw["parent_deadline_monotonic_ns"] = now + 40_000_000_000
    runtime = owned_registration_document(reg)
    raw["references"]["runtime_sha256"] = hashlib.sha256(
        _canonical(runtime)
    ).hexdigest()
    request = PassiveBenchRequest(_canonical(raw))
    journal = PassiveAttemptJournal(
        root,
        request,
        PassiveEntryEvidence(_canonical(evidence)),
        originals,
        runtime,
        now_monotonic_ns=now,
    )
    receipt = journal.consume(now_monotonic_ns=time.monotonic_ns())
    payload = dict(
        schema="rocell.passive_native_child_handoff.v1",
        root=str(root),
        request=request.to_dict(),
        setup_operation_id="operation-" + "a" * 32,
        consumption_sha256=receipt["consumption_sha256"],
        registration=runtime,
    )
    outer = OwnedWorkerRequest(
        ATTEMPT,
        raw["launch_id"],
        raw["references"]["source_sha256"],
        request.request_sha256,
        raw["references"]["native_metadata_review_sha256"],
        raw["parent_deadline_monotonic_ns"],
        _canonical(payload),
    )
    return reg, outer, journal


def test_supervisor_owns_child_claim_and_retains_failed_raw_output(tmp_path):
    reg, request, journal = prepared_dispatch(tmp_path)
    authorizations = []

    def authorize(*args):
        authorizations.append(args[2])

    result = OwnedWindowsWorker(reg, authorizer=authorize).run(
        request, cancellation=Event(), deadline_ns=request.expires_at_ns
    )
    assert len(authorizations) == 1
    assert result.process_created and result.initial_thread_resumed
    assert result.tree_exit_confirmed
    assert result.primary_error == "WORKER_EXIT_FAILED"
    assert b"JSONDecodeError" in result.stderr
    assert result.stdout == b"" and result.parsed_result is None
    history = inspect_attempt(tmp_path, ATTEMPT)
    assert history["records"]["claimed"] is not None
    assert history["status"] == "OUTCOME_UNKNOWN_NO_REPLAY"
    journal.retain_outcome(
        stdout=result.stdout, stderr=result.stderr, process_status=result.status
    )
    assert (
        inspect_attempt(tmp_path, ATTEMPT)["status"]
        == "OUTCOME_RETAINED_NOT_DEVICE_ACCEPTANCE"
    )
    replay = OwnedWindowsWorker(reg, authorizer=authorize).run(
        request, cancellation=Event(), deadline_ns=request.expires_at_ns
    )
    assert not replay.process_created
    assert len(authorizations) == 1


def test_cancelled_dispatch_never_resumes_a_child(tmp_path):
    reg, request, _ = prepared_dispatch(tmp_path)
    cancel = Event()
    cancel.set()
    result = OwnedWindowsWorker(reg, authorizer=lambda *args: None).run(
        request, cancellation=cancel, deadline_ns=request.expires_at_ns
    )
    assert not result.process_created
    assert inspect_attempt(tmp_path, ATTEMPT)["records"]["claimed"] is None


def test_consumed_record_changed_during_authorization_blocks_execution(tmp_path):
    reg, request, _ = prepared_dispatch(tmp_path)

    def changed(*args):
        # Intentional corruption of this test's private journal, not user data.
        (tmp_path / (ATTEMPT + "-physical-passive-consumed.json")).write_bytes(b"{}")

    result = OwnedWindowsWorker(reg, authorizer=changed).run(
        request, cancellation=Event(), deadline_ns=request.expires_at_ns
    )
    assert not result.initial_thread_resumed
    assert not (tmp_path / (ATTEMPT + "-physical-passive-claimed.json")).exists()
