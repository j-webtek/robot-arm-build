"""Real Windows process owner, fixed incapable child, synthetic device evidence."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

import pytest

from rocell.application.arm_bench_qualification_contract import (
    PassiveBenchRequest,
    _canonical,
)
from rocell.providers.windows import passive_arm_process_codec as codec
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessBudget,
    WorkerProcessRegistration,
    OwnedWorkerRequest,
    OwnedWindowsWorker,
    owned_registration_document,
)
from test_arm_bench_qualification_contract import document


def prepared(tmp_path, scenario="nominal", run_timeout_ms=None):
    def pin(path):
        return PinnedWorkerFile(path, hashlib.sha256(path.read_bytes()).hexdigest())

    if scenario.startswith("lifecycle-"):
        from rocell.providers.windows.passive_arm_lifecycle_package import (
            prepare,
            CHILD,
        )

        package = pin(prepare(tmp_path))
        argv = ("-I", "-S", str(CHILD), str(package.path), package.sha256, scenario)
        files = (pin(CHILD), package)
    else:
        argv = ("-I", "-S", str(codec.FIXTURE_PATH), scenario)
        files = (pin(codec.FIXTURE_PATH),)
    registration = WorkerProcessRegistration(
        "incapable-passive-arm",
        pin(Path(sys._base_executable)),
        argv,
        files,
        tmp_path,
        WorkerProcessBudget(
            run_timeout_ms=run_timeout_ms
            or (8000 if scenario.startswith("lifecycle-") else 1000),
            cleanup_timeout_ms=1000,
            stdout_bytes=128 * 1024,
            stderr_bytes=8192,
            process_count=1,
        ),
        "INCAPABLE_PROCESS_FIXTURE",
        codec.REQUEST_SCHEMA,
        codec.RESULT_SCHEMA,
    )
    body = document()
    body["parent_deadline_monotonic_ns"] = time.monotonic_ns() + 20_000_000_000
    body["references"]["runtime_sha256"] = hashlib.sha256(
        _canonical(owned_registration_document(registration))
    ).hexdigest()
    passive = PassiveBenchRequest(_canonical(body))
    payload = dict(
        schema=codec.PAYLOAD_SCHEMA,
        scenario=scenario,
        request=passive.to_dict(),
        selected_identity_sha256="c" * 64,
    )
    outer = OwnedWorkerRequest(
        body["attempt_id"],
        body["launch_id"],
        body["references"]["source_sha256"],
        passive.request_sha256,
        "c" * 64,
        body["parent_deadline_monotonic_ns"],
        _canonical(payload),
    )
    return registration, outer, payload


def execute(registration, outer, *, cancel=None):
    calls = []

    def authorize(reg, request, digest):
        assert reg == registration and request == outer
        calls.append(digest)

    runner = OwnedWindowsWorker(registration, authorizer=authorize)
    result = runner.run(
        outer, cancellation=cancel or threading.Event(), deadline_ns=outer.expires_at_ns
    )
    return runner, result, calls


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("nominal", "OBSERVED_CLOSED"),
        ("open-failed", "FAILED_KNOWN"),
        ("cleanup-unknown", "CLEANUP_UNCERTAIN"),
        ("lifecycle-nominal", "OBSERVED_CLOSED"),
        ("lifecycle-open-failed", "FAILED_KNOWN"),
        ("lifecycle-cleanup-unknown", "CLEANUP_UNCERTAIN"),
    ],
)
def test_actual_process_delivers_bound_passive_result(tmp_path, scenario, expected):
    registration, outer, payload = prepared(tmp_path, scenario)
    runner, owned, calls = execute(registration, outer)
    assert owned.status == "SUCCEEDED", (owned.to_dict(), owned.stdout, owned.stderr)
    assert (
        owned.process_created
        and owned.initial_thread_resumed
        and owned.tree_exit_confirmed
    )
    assert not owned.cleanup_errors and len(calls) == 1
    result = codec.validate_result(
        json.loads(owned.stdout),
        payload=payload,
        request_sha256=owned.request_sha256,
        attempt_id=outer.attempt_id,
    )
    assert result.summary()["status"] == expected
    assert result.summary()["origin"] == "SYNTHETIC_REHEARSAL"
    assert owned.to_dict()["device_cleanup_confirmed"] is False
    assert result.summary()["physical_authority"] is False
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        runner.run(
            outer, cancellation=threading.Event(), deadline_ns=outer.expires_at_ns
        )


@pytest.mark.parametrize("scenario", ["malformed", "wrong-binding", "stall"])
def test_invalid_output_or_stall_retains_owned_failure(tmp_path, scenario):
    registration, outer, _ = prepared(tmp_path, scenario)
    _, owned, calls = execute(registration, outer)
    assert owned.status != "SUCCEEDED"
    assert owned.parsed_result is None
    assert owned.tree_exit_confirmed and not owned.cleanup_errors
    assert len(calls) == 1
    if scenario != "stall":
        assert owned.stdout  # malformed/untrusted raw output is not erased


def test_precancel_never_creates_child(tmp_path):
    registration, outer, _ = prepared(tmp_path)
    cancel = threading.Event()
    cancel.set()
    _, owned, calls = execute(registration, outer, cancel=cancel)
    assert owned.status == "CANCELLED" and not owned.process_created
    assert calls == []


def test_physical_payload_cannot_activate_this_runner(tmp_path):
    _, _, payload = prepared(tmp_path)
    payload["request"]["mode"] = "physical"
    with pytest.raises(ValueError, match="PHYSICAL_DISPATCH_HELD"):
        codec.validate_payload(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("worker_id", "other"),
        ("argv", ("-c", "print(1)")),
        ("composition", "PHYSICAL_UNQUALIFIED"),
    ],
)
def test_wrong_registration_refused_before_process_creation(tmp_path, field, value):
    registration, outer, _ = prepared(tmp_path)
    changed = replace(registration, **{field: value})
    _, owned, calls = execute(changed, outer)
    assert not owned.process_created and calls == []


def test_changed_runtime_binding_refused(tmp_path):
    registration, outer, _ = prepared(tmp_path)
    changed = replace(
        registration, budget=replace(registration.budget, run_timeout_ms=2000)
    )
    _, owned, calls = execute(changed, outer)
    assert not owned.process_created and calls == []


def test_lifecycle_process_timeout_never_infers_device_cleanup(tmp_path):
    registration, outer, _ = prepared(
        tmp_path, "lifecycle-nominal", run_timeout_ms=1000
    )
    _, owned, _ = execute(registration, outer)
    assert owned.status == "TIMED_OUT"
    assert owned.process_created and owned.tree_exit_confirmed
    assert owned.parsed_result is None
    assert owned.to_dict()["device_cleanup_confirmed"] is False


def test_lifecycle_archive_changed_after_pin_prevents_dispatch(tmp_path):
    registration, outer, _ = prepared(tmp_path, "lifecycle-nominal")
    package = registration.package_files[1].path
    package.write_bytes(package.read_bytes() + b"changed")
    _, owned, calls = execute(registration, outer)
    assert not owned.process_created and calls == []


def test_lifecycle_arbitrary_archive_digest_is_not_a_source_approval(tmp_path):
    registration, outer, _ = prepared(tmp_path, "lifecycle-nominal")
    package = registration.package_files[1]
    changed = replace(package, sha256="f" * 64)
    argv = (*registration.argv[:4], changed.sha256, registration.argv[-1])
    replacement = replace(
        registration, package_files=(registration.package_files[0], changed), argv=argv
    )
    with pytest.raises(ValueError, match="PASSIVE_LIFECYCLE_SOURCE_MISMATCH"):
        codec.validate_registration(replacement, outer)
    _, owned, calls = execute(replacement, outer)
    assert not owned.process_created and calls == []
