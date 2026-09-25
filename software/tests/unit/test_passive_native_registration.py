"""Exact native registration membership; dispatch remains physically held."""

from dataclasses import replace
import hashlib
from pathlib import Path
import sys
from threading import Event
import time

import pytest

from rocell.providers.windows import passive_native_registration as codec
from rocell.providers.windows import passive_native_package as package
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessRegistration,
    WorkerProcessBudget,
    OwnedWorkerRequest,
    OwnedWindowsWorker,
    owned_registration_document,
)
from rocell.application.arm_bench_qualification_contract import (
    PassiveBenchRequest,
    _canonical,
)
from test_arm_bench_qualification_contract import document


ATTEMPT = "operation-" + "b" * 32


def pin(path):
    return PinnedWorkerFile(path, hashlib.sha256(path.read_bytes()).hexdigest())


def registration(root):
    child_dir = root / (ATTEMPT + "-native-child")
    child_dir.mkdir()
    archive = pin(package.prepare(child_dir))
    return WorkerProcessRegistration(
        codec.WORKER_ID,
        pin(Path(getattr(sys, "_base_executable", sys.executable))),
        ("-I", "-S", str(package.CHILD), str(archive.path), archive.sha256, "observe"),
        (pin(package.CHILD), archive),
        child_dir,
        WorkerProcessBudget(
            run_timeout_ms=20_000,
            cleanup_timeout_ms=2000,
            stdout_bytes=256 * 1024,
            stderr_bytes=8192,
            process_count=1,
        ),
        "PHYSICAL_UNQUALIFIED",
        codec.REQUEST_SCHEMA,
        codec.RESULT_SCHEMA,
    )


def outer(reg, root):
    value = document()
    value.update(
        mode="physical",
        attempt_id=ATTEMPT,
        parent_deadline_monotonic_ns=time.monotonic_ns() + 40_000_000_000,
    )
    runtime = owned_registration_document(reg)
    value["references"]["runtime_sha256"] = hashlib.sha256(
        _canonical(runtime)
    ).hexdigest()
    request = PassiveBenchRequest(_canonical(value))
    handoff = dict(
        schema=codec.PAYLOAD_SCHEMA,
        root=str(root),
        request=request.to_dict(),
        setup_operation_id="operation-" + "a" * 32,
        consumption_sha256="c" * 64,
        registration=runtime,
    )
    return OwnedWorkerRequest(
        ATTEMPT,
        value["launch_id"],
        value["references"]["source_sha256"],
        request.request_sha256,
        value["references"]["native_metadata_review_sha256"],
        value["parent_deadline_monotonic_ns"],
        _canonical(handoff),
    )


def test_exact_registration_without_consumed_originals_does_not_dispatch(tmp_path):
    reg = registration(tmp_path)
    request = outer(reg, tmp_path)
    assert codec.validate_registration(reg, request)["schema"] == codec.PAYLOAD_SCHEMA
    result = OwnedWindowsWorker(reg, authorizer=lambda *args: None).run(
        request, cancellation=Event(), deadline_ns=request.expires_at_ns
    )
    assert result.process_created is False
    assert result.primary_error == "ValueError"


@pytest.mark.parametrize(
    "field,value",
    [
        ("worker_id", "other-worker"),
        ("composition", "INCAPABLE_PROCESS_FIXTURE"),
        ("request_schema", "other.request"),
        ("result_schema", "other.result"),
    ],
)
def test_registration_identity_cannot_be_substituted(tmp_path, field, value):
    reg = replace(registration(tmp_path), **{field: value})
    with pytest.raises(ValueError, match="REGISTRATION_IDENTITY"):
        codec.validate_registration(reg, outer(reg, tmp_path))


def test_import_probe_cannot_be_registered_as_observation(tmp_path):
    reg = registration(tmp_path)
    reg = replace(reg, argv=reg.argv[:-1] + ("check-imports",))
    with pytest.raises(ValueError, match="FIXED_COMMAND"):
        codec.validate_registration(reg, outer(reg, tmp_path))


def test_arbitrary_archive_hash_is_not_sufficient(tmp_path):
    reg = registration(tmp_path)
    altered_pin = replace(reg.package_files[1], sha256="e" * 64)
    reg = replace(
        reg,
        package_files=(reg.package_files[0], altered_pin),
        argv=reg.argv[:4] + (altered_pin.sha256, "observe"),
    )
    with pytest.raises(ValueError, match="CURRENT_SOURCE"):
        codec.validate_registration(reg, outer(reg, tmp_path))


@pytest.mark.parametrize(
    "field,value",
    [
        ("process_count", 2),
        ("run_timeout_ms", 21000),
        ("cleanup_timeout_ms", 3000),
        ("stderr_bytes", 16384),
    ],
)
def test_limits_are_not_caller_adjustable(tmp_path, field, value):
    reg = registration(tmp_path)
    reg = replace(reg, budget=replace(reg.budget, **{field: value}))
    with pytest.raises(ValueError, match="EXACT_PROCESS_BUDGET"):
        codec.validate_registration(reg, outer(reg, tmp_path))


def test_cross_request_binding_is_rejected(tmp_path):
    reg = registration(tmp_path)
    request = replace(outer(reg, tmp_path), source_sha256="f" * 64)
    with pytest.raises(ValueError, match="REQUEST_BINDING"):
        codec.validate_registration(reg, request)
