"""Closed registration and fail-before-dispatch checks; no device process starts."""

from dataclasses import replace
import hashlib
from pathlib import Path
import sys
import time
from threading import Event

import pytest

from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.powered_arm_feedback_contract import PoweredFeedbackIntent
from rocell.providers.windows import powered_feedback_native_registration as codec
from rocell.providers.windows import powered_feedback_native_package as package
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessRegistration,
    WorkerProcessBudget,
    OwnedWorkerRequest,
    OwnedWindowsWorker,
    owned_registration_document,
)
from test_powered_arm_feedback_contract import document


def registered(tmp_path):
    body = document()
    body["mode"] = "physical"
    now = time.monotonic_ns()
    body["startup_recorded_monotonic_ns"] = now
    body["parent_deadline_monotonic_ns"] = now + 30_000_000_000
    directory = tmp_path / (body["attempt_id"] + "-powered-native-child")
    directory.mkdir()

    def pin(path):
        return PinnedWorkerFile(path, hashlib.sha256(path.read_bytes()).hexdigest())

    archive = pin(package.prepare(directory))
    reg = WorkerProcessRegistration(
        codec.WORKER_ID,
        pin(Path(getattr(sys, "_base_executable", sys.executable))),
        ("-I", "-S", str(package.CHILD), str(archive.path), archive.sha256, "observe"),
        (pin(package.CHILD), archive),
        directory,
        WorkerProcessBudget(
            run_timeout_ms=20000,
            cleanup_timeout_ms=2000,
            stdin_bytes=65536,
            stdout_bytes=256 * 1024,
            stderr_bytes=8192,
            process_count=1,
        ),
        "PHYSICAL_UNQUALIFIED",
        codec.REQUEST_SCHEMA,
        codec.RESULT_SCHEMA,
    )
    runtime = owned_registration_document(reg)
    body["references"]["runtime_sha256"] = hashlib.sha256(
        _canonical(runtime)
    ).hexdigest()
    intent = PoweredFeedbackIntent(_canonical(body))
    payload = dict(
        schema=codec.PAYLOAD_SCHEMA,
        root=str(tmp_path),
        intent=intent.to_dict(),
        consumption_sha256="e" * 64,
        registration=runtime,
    )
    outer = OwnedWorkerRequest(
        body["attempt_id"],
        body["session_id"],
        body["references"]["source_sha256"],
        intent.request_sha256,
        body["references"]["native_identity_original_sha256"],
        body["parent_deadline_monotonic_ns"],
        _canonical(payload),
    )
    return reg, outer, payload


def test_exact_current_registration_validates_but_missing_originals_prevent_dispatch(
    tmp_path,
):
    reg, outer, payload = registered(tmp_path)
    assert codec.validate_registration(reg, outer) == payload

    def forbidden(*args):
        pytest.fail("Missing consumed originals must fail before process creation")

    result = OwnedWindowsWorker(
        reg, authorizer=forbidden, _backend_factory=forbidden
    ).run(outer, cancellation=Event(), deadline_ns=outer.expires_at_ns)
    assert result.process_created is False
    assert result.status != "SUCCEEDED"


@pytest.mark.parametrize("change", ["command", "budget", "child-pin"])
def test_changed_registration_is_rejected(tmp_path, change):
    reg, outer, _ = registered(tmp_path)
    if change == "command":
        reg = replace(reg, argv=reg.argv[:-1] + ("other",))
    elif change == "budget":
        reg = replace(reg, budget=replace(reg.budget, process_count=2))
    else:
        reg = replace(
            reg,
            package_files=(
                replace(reg.package_files[0], sha256="a" * 64),
                reg.package_files[1],
            ),
        )
    with pytest.raises(ValueError):
        codec.validate_registration(reg, outer)
