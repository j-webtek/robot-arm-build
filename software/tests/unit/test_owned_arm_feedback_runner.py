"""Real owned child tests use only its sealed in-memory Win32 serial facade."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from typing import Any
import zipfile

import pytest

from rocell.providers.windows import owned_arm_feedback_package as package
from rocell.providers.windows import owned_arm_feedback_runner as runner_module
from rocell.providers.windows import owned_worker_process as shared
from rocell.providers.windows.owned_arm_feedback_package import (
    OwnedArmRuntime,
    canonical,
    prepare_owned_arm_runtime,
    revalidate_owned_arm_runtime,
)
from rocell.providers.windows.owned_arm_feedback_runner import (
    PreparedOwnedArmFeedback,
    prepare_owned_arm_feedback,
    reconstruct_owned_arm_feedback,
    ARM_PREPARATION_VERSIONS,
    IncapableOwnedArmFeedbackRunner,
    OwnedArmFeedbackRunner,
)
from rocell.providers.windows.arm_owned_protocol import (
    ArmOwnedRequest,
    LEGACY_REQUEST_SCHEMA,
    PREVIOUS_REQUEST_SCHEMA,
    REQUEST_SCHEMA,
)
from test_arm_feedback_worker import Clock, _request
from test_arm_owned_protocol import rehash
from rocell.providers.windows.incapable_controller_metadata import (
    synthetic_native_identity,
)

WORKSPACE = Path(__file__).parents[3]


@pytest.fixture
def runtime(tmp_path: Path) -> OwnedArmRuntime:
    return prepare_owned_arm_runtime(WORKSPACE, tmp_path / "packages")


def preparation(
    runtime: OwnedArmRuntime, tmp_path: Path, scenario: str = "nominal"
) -> PreparedOwnedArmFeedback:
    clock = Clock()
    clock.value = time.monotonic_ns()
    request = _request(clock)
    identity = synthetic_native_identity(request.controller)
    request = replace(
        request,
        controller=replace(request.controller, identity=identity),
        feedback=replace(
            request.feedback, arm_identity_sha256=identity.identity_sha256
        ),
    )
    request = replace(
        request,
        source_sha256=runtime.to_dict()["workspace_source_sha256"],
        expires_monotonic_ns=clock.value + 20_000_000_000,
    )
    cwd = tmp_path / "child-cwd"
    cwd.mkdir()
    return prepare_owned_arm_feedback(
        runtime,
        request,
        session_id=request.feedback.run_id,
        permit_sha256=request.feedback.safety_permit_sha256,
        selected_identity_sha256=request.controller.identity.identity_sha256,
        working_directory=cwd,
        scenario=scenario,
    )


def execute(prepared: PreparedOwnedArmFeedback, callback: Any = None):
    calls = []

    def authorize(exact):
        assert exact.payload == prepared.payload
        calls.append(exact.payload)
        if callback:
            callback(exact)

    runner = IncapableOwnedArmFeedbackRunner(
        prepared, revalidate_consumed_permit=authorize
    )
    evidence = runner.run(
        cancellation=threading.Event(),
        deadline_ns=prepared.request.to_dict()["parent_deadline_monotonic_ns"],
    )
    return runner, evidence, calls


def test_actual_package_and_child_nominal(runtime, tmp_path):
    prepared = preparation(runtime, tmp_path)
    runner, evidence, calls = execute(prepared)
    result = runner.owned_result
    assert result is not None
    assert result.status == "SUCCEEDED", (
        result.to_dict(),
        result.stderr,
        result.stdout[:2048],
    )
    assert len(calls) == 2
    assert (
        result.process_created
        and result.initial_thread_resumed
        and result.tree_exit_confirmed
    )
    assert result.returncode == 0 and not result.cleanup_errors
    assert len(result.stdout.splitlines()) == 2 and result.stderr == b""
    assert result.parsed_result["status"] == "FEEDBACK_RETAINED"
    assert evidence.to_dict()["physical_authority"] is False
    assert evidence.feedback.result.api_counts.write_attempts == 1
    assert evidence.feedback.result.api_counts.writes_confirmed == 1
    assert evidence.feedback.result.api_counts.write_bytes_confirmed == len(
        b'{"T":105}\n'
    )
    assert evidence.feedback.result.connection_closed
    assert evidence.feedback.result.response_bytes == b'{"T":1051,"x":0,"y":0,"z":0}\n'
    assert evidence.native.view()["physical_authority"] is False
    assert len(evidence.payload) <= 128 * 1024
    print(
        "nominal byte sizes",
        {
            "runtime": len(runtime.payload),
            "owned_evidence": len(evidence.payload),
            "stdout": len(result.stdout),
            "stderr": len(result.stderr),
        },
    )
    assert not list(prepared.registration.working_directory.iterdir())
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        runner.run(
            cancellation=threading.Event(),
            deadline_ns=prepared.request.to_dict()["parent_deadline_monotonic_ns"],
        )


def test_package_is_deterministic_closed_and_owned(runtime, tmp_path):
    second = prepare_owned_arm_runtime(WORKSPACE, tmp_path / "packages")
    assert runtime.package.path != second.package.path
    assert runtime.package.sha256 == second.package.sha256
    assert runtime.to_dict()["files"] == second.to_dict()["files"]
    with zipfile.ZipFile(runtime.package.path) as archive:
        assert len(archive.namelist()) == len(runtime.to_dict()["files"])
        assert archive.read("rocell/application/__init__.py") == package._STUB
        source = (
            WORKSPACE / "software/src/rocell/providers/windows/arm_feedback_worker.py"
        )
        assert (
            archive.read("rocell/providers/windows/arm_feedback_worker.py")
            == source.read_bytes()
        )
    doc = runtime.to_dict()
    doc["files"][0]["sha256"] = "a" * 64
    assert runtime.to_dict()["files"] != doc["files"]
    with pytest.raises(ValueError):
        OwnedArmRuntime(canonical(doc))


def test_pure_preparation_status_and_reconstruction_do_not_read(
    runtime, tmp_path, monkeypatch
):
    prepared = preparation(runtime, tmp_path)
    inner = prepared.request.feedback_request

    def forbidden(*args, **kwargs):
        pytest.fail("inert operation performed I/O")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(runner_module, "_new_owner", forbidden)
    repeated = prepare_owned_arm_feedback(
        OwnedArmRuntime(runtime.payload),
        inner,
        session_id=inner.feedback.run_id,
        permit_sha256=inner.feedback.safety_permit_sha256,
        selected_identity_sha256=inner.controller.identity.identity_sha256,
        working_directory=prepared.registration.working_directory,
    )
    assert repeated.payload == prepared.payload
    assert PreparedOwnedArmFeedback(prepared.payload).payload == prepared.payload
    runner = IncapableOwnedArmFeedbackRunner(
        prepared, revalidate_consumed_permit=forbidden
    )
    assert not runner.status()["consumed"]
    assert not runner.status()["physical_dispatch_enabled"]


@pytest.mark.parametrize(
    "mutation", ["source", "registration", "scenario", "origin", "line_limit"]
)
def test_preparation_rejects_changed_nested_request(runtime, tmp_path, mutation):
    prepared = preparation(runtime, tmp_path)
    doc = prepared.to_dict()
    if mutation == "source":
        doc["runtime"]["workspace_source_sha256"] = "b" * 64
    elif mutation == "registration":
        doc["registration"]["argv"][0] = "-c"
    elif mutation == "scenario":
        doc["request"]["scenario"] = "open-physical"
    elif mutation == "origin":
        doc["request"]["provenance"] = "PHYSICAL_NONPURGING_ARM_HELD"
    else:
        doc["request"]["feedback_request"]["feedback"]["maximum_line_bytes"] = 2049
    with pytest.raises(ValueError):
        PreparedOwnedArmFeedback(canonical(doc))


@pytest.mark.parametrize(
    "case", ["physical-held", "cancelled", "deadline", "cleanup-hold", "other-owner"]
)
def test_no_dispatch_admission_holds(runtime, tmp_path, monkeypatch, case):
    prepared = preparation(runtime, tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("held run reached a file/authority/process effect")

    monkeypatch.setattr(runner_module, "_new_owner", forbidden)
    monkeypatch.setattr(runner_module, "revalidate_owned_arm_runtime", forbidden)
    cls = (
        OwnedArmFeedbackRunner
        if case == "physical-held"
        else IncapableOwnedArmFeedbackRunner
    )
    runner = cls(prepared, revalidate_consumed_permit=forbidden)
    event = threading.Event()
    deadline = prepared.request.to_dict()["parent_deadline_monotonic_ns"]
    if case == "cancelled":
        event.set()
    elif case == "deadline":
        deadline -= 1
    elif case == "cleanup-hold":
        monkeypatch.setattr(shared, "_UNRESOLVED_BACKEND", object())
    elif case == "other-owner":
        assert shared._DISPATCH_LOCK.acquire(blocking=False)
    try:
        evidence = runner.run(cancellation=event, deadline_ns=deadline)
    finally:
        if case == "other-owner":
            shared._DISPATCH_LOCK.release()
    assert runner.owned_result.primary_error
    assert not runner.owned_result.process_created
    assert runner.owned_result.stdout == b""
    assert evidence.to_dict()["physical_authority"] is False


def test_package_drift_holds_before_owner_or_authorizer(runtime, tmp_path, monkeypatch):
    prepared = preparation(runtime, tmp_path)
    raw = runtime.package.path.read_bytes()
    runtime.package.path.write_bytes(raw + b"drift")
    monkeypatch.setattr(
        runner_module, "_new_owner", lambda: pytest.fail("drift reached process")
    )
    runner, _, calls = execute(prepared)
    assert not calls and not runner.owned_result.process_created
    assert runner.owned_result.primary_error == "RUNTIME_FILE_CHANGED"


@pytest.mark.parametrize(
    "scenario",
    [
        "boot-bytes",
        "short-write",
        "timeout",
        "identity-change",
        "identity-change-preopen",
        "malformed-metadata",
        "close-failure",
        "malformed-response",
        "extra-response",
    ],
)
def test_actual_child_serial_faults_retain_complete_diagnostics(
    runtime, tmp_path, scenario
):
    runner, evidence, calls = execute(preparation(runtime, tmp_path, scenario))
    result = runner.owned_result
    assert result.status == "SUCCEEDED", (
        result.primary_error,
        result.cleanup_errors,
        result.stderr,
    )
    assert result.returncode == 0 and not result.cleanup_errors
    assert result.parsed_result["status"] == "FEEDBACK_RETAINED"
    assert len(calls) == 2 and len(result.stdout.splitlines()) == 2
    assert evidence.to_dict()["physical_authority"] is False
    assert evidence.feedback.result.outcome.value != "SUCCEEDED_DIAGNOSTIC"
    if scenario == "close-failure":
        assert evidence.feedback.safe_summary()["technical_response_valid"] is True
        assert not evidence.feedback.result.connection_closed
    if scenario in {"identity-change", "boot-bytes"}:
        assert evidence.feedback.result.api_counts.write_attempts == 0
    if scenario in {"identity-change-preopen", "malformed-metadata"}:
        assert evidence.feedback.result.api_counts.open_attempts == 0
        assert evidence.feedback.result.api_counts.write_attempts == 0
        assert evidence.resolution.safe_summary()["status"] == "HELD"
        assert evidence.resolution.safe_summary()["attempts"][0]["phase"] == "PRE_OPEN"


def test_actual_child_malformed_output_is_raw_only(runtime, tmp_path):
    runner, evidence, calls = execute(
        preparation(runtime, tmp_path, "malformed-result")
    )
    result = runner.owned_result
    assert result.status == "FAILED" and result.parsed_result is None
    assert result.stdout.endswith(b"malformed-result\n") and len(calls) == 2
    assert result.tree_exit_confirmed and not result.cleanup_errors
    assert evidence.to_dict()["physical_authority"] is False
    print(
        "malformed byte sizes",
        {
            "runtime": len(runtime.payload),
            "owned_evidence": len(evidence.payload),
            "stdout": len(result.stdout),
            "stderr": len(result.stderr),
        },
    )


@pytest.mark.parametrize("when", [1, 2])
def test_actual_denied_scope_never_releases_child(runtime, tmp_path, when):
    calls = 0

    def denied(exact):
        nonlocal calls
        calls += 1
        if calls == when:
            raise ValueError("SCOPE_CHANGED")

    runner, evidence, _ = execute(preparation(runtime, tmp_path), denied)
    assert runner.owned_result.primary_error == "SCOPE_CHANGED"
    assert runner.owned_result.parsed_result is None
    assert runner.owned_result.process_created is (when == 2)
    if when == 2:
        assert len(runner.owned_result.stdout.splitlines()) == 1
        assert runner.owned_result.tree_exit_confirmed
    assert evidence.to_dict()["physical_authority"] is False


def test_pure_preparation_refuses_legacy_execution_even_with_current_registration(
    runtime, tmp_path
):
    prepared = preparation(runtime, tmp_path)
    document = prepared.to_dict()
    document["request"].update(schema=LEGACY_REQUEST_SCHEMA, admission_timeout_ms=2000)
    legacy = ArmOwnedRequest(rehash(document["request"]))
    document["request"] = legacy.to_dict()
    assert document["registration"]["request_schema"] == REQUEST_SCHEMA
    with pytest.raises(ValueError, match="ARM_PREPARATION_VERSION_MISMATCH"):
        PreparedOwnedArmFeedback(canonical(document))


def historical_runtime(runtime):
    """Modeled old descriptor with the immutable old roster, never executed."""
    doc = runtime.to_dict()
    doc["schema"] = package.LEGACY_SCHEMA
    names = {"rocell/" + name for name in package.LEGACY_ROCELL_MODULES}
    names |= {name + "/__init__.py" for name in package.NAMESPACES}
    names |= {"packaging/" + name for name in package.PACKAGING_MODULES}
    doc["files"] = [row for row in doc["files"] if row["name"] in names]
    doc["source_closure_sha256"] = package.digest(doc["files"])
    return OwnedArmRuntime(canonical(doc))


@pytest.mark.parametrize("schema", [LEGACY_REQUEST_SCHEMA, PREVIOUS_REQUEST_SCHEMA])
def test_historical_runtime_and_preparation_reconstruct_purely_but_never_launch(
    runtime, tmp_path, monkeypatch, schema
):
    old_runtime = historical_runtime(runtime)
    current = preparation(runtime, tmp_path)
    inner = current.request.feedback_request

    def forbidden(*args, **kwargs):
        pytest.fail("historical reconstruction attempted effect")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(runner_module, "_new_owner", forbidden)
    kwargs = dict(
        session_id=inner.feedback.run_id,
        permit_sha256=inner.feedback.safety_permit_sha256,
        selected_identity_sha256=inner.controller.identity.identity_sha256,
        working_directory=current.registration.working_directory,
    )
    historical = reconstruct_owned_arm_feedback(
        old_runtime, inner, request_schema=schema, **kwargs
    )
    assert PreparedOwnedArmFeedback(historical.payload).payload == historical.payload
    assert historical.registration.request_schema == schema
    assert historical.registration.result_schema == "rocell.arm_owned_result.v1"
    assert historical.to_dict()["schema"] == ARM_PREPARATION_VERSIONS[schema][1]
    for runner_class in (OwnedArmFeedbackRunner, IncapableOwnedArmFeedbackRunner):
        with pytest.raises(ValueError, match="ARM_PREPARATION_VERSION_HELD"):
            runner_class(historical, revalidate_consumed_permit=forbidden)
    with pytest.raises(ValueError, match="ARM_RUNTIME_VERSION_HELD"):
        revalidate_owned_arm_runtime(old_runtime)
    with pytest.raises(ValueError, match="ARM_RUNTIME_VERSION_MISMATCH"):
        prepare_owned_arm_feedback(old_runtime, inner, **kwargs)
    with pytest.raises(TypeError):
        ARM_PREPARATION_VERSIONS[schema] = ("x", "y", "z")


def test_historical_runtime_roster_is_not_reinterpreted_as_current(runtime):
    old = historical_runtime(runtime).to_dict()
    old["schema"] = package.SCHEMA
    with pytest.raises(ValueError, match="RUNTIME_ROSTER"):
        OwnedArmRuntime(canonical(old))
    current = runtime.to_dict()
    current["schema"] = package.LEGACY_SCHEMA
    with pytest.raises(ValueError, match="RUNTIME_ROSTER"):
        OwnedArmRuntime(canonical(current))


@pytest.mark.parametrize("delay,accepted", [(3.0, True), (5.1, False)])
def test_actual_current_child_release_wait_is_finite_without_deadline_renewal(
    runtime, tmp_path, delay, accepted
):
    prepared = preparation(runtime, tmp_path)
    original_request = prepared.request.payload
    original_deadline = prepared.request.to_dict()["parent_deadline_monotonic_ns"]
    calls = 0

    def fresh_scope_check(exact):
        nonlocal calls
        calls += 1
        assert exact.request.payload == original_request
        if calls == 2:
            # Model expensive live M1 revalidation, not a cached admission or
            # retry. The actual fixed child is waiting for RELEASE and EOF.
            time.sleep(delay)

    runner, evidence, _ = execute(prepared, fresh_scope_check)
    result = runner.owned_result
    assert calls == 2 and result.tree_exit_confirmed and not result.cleanup_errors
    assert (
        prepared.request.to_dict()["parent_deadline_monotonic_ns"] == original_deadline
    )
    assert prepared.request.payload == original_request
    if accepted:
        assert result.status == "SUCCEEDED", (result.to_dict(), result.stderr)
        assert evidence.feedback.result.api_counts.writes_confirmed == 1
        assert evidence.native is not None
        assert result.stdin_bytes_written > len(prepared.request.wire())
    else:
        assert result.primary_error == "ARM_RELEASE_TIMED_OUT", result.to_dict()
        assert result.stdin_bytes_written == len(prepared.request.wire())
        assert evidence.feedback is None and evidence.native is None
        assert result.parsed_result is None
    assert evidence.to_dict()["physical_authority"] is False


def test_rehashed_foreign_archive_is_not_an_arbitrary_code_registration(
    runtime, tmp_path, monkeypatch
):
    with zipfile.ZipFile(runtime.package.path, "a") as archive:
        archive.writestr("foreign_code.py", "raise RuntimeError('must never import')")
    doc = runtime.to_dict()
    doc["package"]["sha256"] = hashlib.sha256(
        runtime.package.path.read_bytes()
    ).hexdigest()
    forged = OwnedArmRuntime(canonical(doc))
    monkeypatch.setattr(
        runner_module,
        "_new_owner",
        lambda: pytest.fail("foreign archive reached process"),
    )
    runner, _, calls = execute(preparation(forged, tmp_path))
    assert runner.owned_result.primary_error == "RUNTIME_ARCHIVE_CHANGED"
    assert not calls and not runner.owned_result.process_created


def test_closed_roster_constants_match_bootstrap():
    from rocell.providers.windows import _owned_arm_feedback_child as child

    assert child.ROCELL_MODULES == package.ROCELL_MODULES
    assert child.PACKAGING_MODULES == package.PACKAGING_MODULES
    assert child.NAMESPACES == package.NAMESPACES and child.STUB == package._STUB


def test_nonempty_working_directory_is_held_before_authorizer(runtime, tmp_path):
    prepared = preparation(runtime, tmp_path)
    existing = prepared.registration.working_directory / "existing.txt"
    existing.write_bytes(b"user-owned")
    runner, _, calls = execute(prepared)
    assert not calls and not runner.owned_result.process_created
    assert runner.owned_result.primary_error == "WORKING_DIRECTORY_NOT_EMPTY"
    assert existing.read_bytes() == b"user-owned"


def test_actual_cancelled_ready_check_sends_no_release(runtime, tmp_path):
    prepared = preparation(runtime, tmp_path)
    cancellation = threading.Event()
    calls = 0

    def cancel_at_ready(exact):
        nonlocal calls
        calls += 1
        if calls == 2:
            cancellation.set()

    runner = IncapableOwnedArmFeedbackRunner(
        prepared, revalidate_consumed_permit=cancel_at_ready
    )
    evidence = runner.run(
        cancellation=cancellation,
        deadline_ns=prepared.request.to_dict()["parent_deadline_monotonic_ns"],
    )
    assert runner.owned_result.status == "CANCELLED"
    assert runner.owned_result.stdin_bytes_written == len(prepared.request.wire())
    assert (
        runner.owned_result.tree_exit_confirmed
        and not runner.owned_result.cleanup_errors
    )
    assert evidence.feedback is None and evidence.native is None


def test_actual_child_timeout_is_owned_tree_cleanup_not_serial_receipt(
    runtime, tmp_path
):
    prepared = preparation(runtime, tmp_path, "child-timeout")
    inner = prepared.request.feedback_request
    inner = replace(
        inner,
        expires_monotonic_ns=inner.feedback.requested_monotonic_ns + 9_000_000_000,
    )
    prepared = prepare_owned_arm_feedback(
        runtime,
        inner,
        session_id=inner.feedback.run_id,
        permit_sha256=inner.feedback.safety_permit_sha256,
        selected_identity_sha256=inner.controller.identity.identity_sha256,
        working_directory=prepared.registration.working_directory,
        scenario="child-timeout",
    )
    runner, evidence, calls = execute(prepared)
    assert len(calls) == 2
    assert runner.owned_result.status == "TIMED_OUT"
    assert (
        runner.owned_result.tree_exit_confirmed
        and not runner.owned_result.cleanup_errors
    )
    assert len(runner.owned_result.stdout.splitlines()) == 1
    assert evidence.feedback is None and evidence.native is None
    print(
        "timeout byte sizes",
        {
            "runtime": len(runtime.payload),
            "owned_evidence": len(evidence.payload),
            "stdout": len(runner.owned_result.stdout),
            "stderr": len(runner.owned_result.stderr),
        },
    )


class FailingOwner:
    """No OS effects: exercises primary/cleanup retention and cross-runner hold."""

    def __init__(self):
        self.created = self.resumed = self.tree_exited = False
        self.returncode = None
        self.written = self.peak_handles = self.peak_processes = 0
        self.stdout = self.stderr = b""
        self.pending = False
        self.handles, self.unclosed_handles, self.pins = {}, {}, []

    def pin(self, registration):
        pass

    def start(self, registration, wire, *, check, keep_stdin_open):
        check()
        self.created = self.resumed = True
        self.written = len(wire)

    def poll(self, budget):
        raise ValueError("PRIMARY_FIXTURE_ERROR")

    def cleanup(self, deadline):
        self.tree_exited = self.created
        raise RuntimeError("cleanup failure")


def test_cleanup_exception_retains_primary_and_global_owner(
    runtime, tmp_path, monkeypatch
):
    monkeypatch.setattr(shared, "_UNRESOLVED_BACKEND", None)
    owner = FailingOwner()
    monkeypatch.setattr(runner_module, "_new_owner", lambda: owner)
    runner, evidence, _ = execute(preparation(runtime, tmp_path))
    assert runner.owned_result.primary_error == "PRIMARY_FIXTURE_ERROR"
    assert runner.owned_result.cleanup_errors == ("CLEANUP_EXCEPTION:RuntimeError",)
    assert shared._UNRESOLVED_BACKEND is owner
    assert not shared._DISPATCH_LOCK.locked()
    assert evidence.feedback is None
    another = tmp_path / "another"
    another.mkdir()
    second, _, calls = execute(preparation(runtime, another))
    assert second.owned_result.primary_error == "PROCESS_CLEANUP_HOLD" and not calls
    assert shared._UNRESOLVED_BACKEND is owner


@pytest.mark.parametrize("bad", ["package", "child", "executable"])
def test_runtime_pin_budgets_cannot_be_expanded(runtime, bad):
    doc = runtime.to_dict()
    doc[bad]["maximum_bytes"] += 1
    with pytest.raises(ValueError, match="RUNTIME_PIN_BUDGET_MISMATCH"):
        OwnedArmRuntime(canonical(doc))


@pytest.mark.parametrize("fault", ["late-poll", "cancel-poll", "late-cleanup"])
def test_post_poll_and_cleanup_budgets_cannot_become_success(
    runtime, tmp_path, monkeypatch, fault
):
    prepared = preparation(runtime, tmp_path)
    event = threading.Event()
    now = [time.monotonic_ns()]
    monkeypatch.setattr(
        runner_module, "time", SimpleNamespace(monotonic_ns=lambda: now[0])
    )
    monkeypatch.setattr(shared, "_UNRESOLVED_BACKEND", None)

    class Owner(FailingOwner):
        def poll(self, budget):
            self.tree_exited, self.returncode = True, 0
            if fault == "late-poll":
                now[0] = prepared.request.to_dict()["parent_deadline_monotonic_ns"]
            elif fault == "cancel-poll":
                event.set()
            else:
                raise ValueError("PRIMARY_FIXTURE_ERROR")
            return True

        def cleanup(self, deadline):
            self.tree_exited, self.returncode = True, 0
            if fault == "late-cleanup":
                now[0] = deadline + 1
            return ()

    owner = Owner()
    monkeypatch.setattr(runner_module, "_new_owner", lambda: owner)
    runner = IncapableOwnedArmFeedbackRunner(
        prepared, revalidate_consumed_permit=lambda exact: None
    )
    evidence = runner.run(
        cancellation=event,
        deadline_ns=prepared.request.to_dict()["parent_deadline_monotonic_ns"],
    )
    assert runner.owned_result.status != "SUCCEEDED" and evidence.feedback is None
    if fault == "late-poll":
        assert runner.owned_result.primary_error == "TIMED_OUT"
    elif fault == "cancel-poll":
        assert runner.owned_result.primary_error == "CANCELLED"
    else:
        assert runner.owned_result.primary_error == "PRIMARY_FIXTURE_ERROR"
        assert "CLEANUP_DEADLINE_EXCEEDED" in runner.owned_result.cleanup_errors
        assert shared._UNRESOLVED_BACKEND is owner


def test_callback_cannot_mutate_copied_preparation(runtime, tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "_UNRESOLVED_BACKEND", None)
    owner = FailingOwner()
    monkeypatch.setattr(runner_module, "_new_owner", lambda: owner)
    prepared = preparation(runtime, tmp_path)

    def mutate(exact):
        doc = exact.to_dict()
        doc["runtime"]["workspace_source_sha256"] = "f" * 64
        object.__setattr__(exact, "payload", canonical(doc))

    runner = IncapableOwnedArmFeedbackRunner(
        prepared, revalidate_consumed_permit=mutate
    )
    runner.run(
        cancellation=threading.Event(),
        deadline_ns=prepared.request.to_dict()["parent_deadline_monotonic_ns"],
    )
    assert runner.owned_result.primary_error == "ARM_PREPARATION_CHANGED"
    assert not owner.created
