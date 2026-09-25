"""Read-only software review: real installed bytes and isolated bad-file copies."""

import os
from pathlib import Path
import shutil
import subprocess
from threading import Event
import time

import pytest

from rocell.application import camera_activation_runtime_policy as policy
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.native_camera_activation_registration import (
    NativeCameraActivationRuntime,
    build_record_relative_path,
    helper_relative_path,
)
from rocell.providers.windows.native_camera_protocol import canonical

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="Installed Windows native runtime"
)


@pytest.fixture(autouse=True)
def no_processes_or_devices(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Software review attempted process/device startup")

    monkeypatch.setattr(subprocess, "Popen", denied)
    from rocell.providers.windows._owned_worker_win32 import WindowsOwnedProcess

    monkeypatch.setattr(WindowsOwnedProcess, "start", denied)


def candidate(workspace, purpose="probe", source="a" * 64):
    return policy.reviewed_activation_runtime_candidate(
        workspace, purpose=purpose, source_sha256=source
    )


def verify(runtime, cancel=None):
    return policy.verify_reviewed_activation_runtime(
        runtime,
        cancellation=Event() if cancel is None else cancel,
        deadline_ns=time.monotonic_ns() + 10_000_000_000,
    )


def copied_runtime(tmp_path, monkeypatch, purpose="probe"):
    # Only ordinary files from the fixed runtime are copied; no helper executes.
    names = [build_record_relative_path(purpose), helper_relative_path(purpose)]
    names += [policy._NATIVE_PREFIX + name for name in policy._NATIVE_INPUTS]
    for relative in names:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    monkeypatch.setattr(policy, "source_fingerprint", lambda _: "a" * 64)
    return candidate(tmp_path, purpose)


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_factory_is_inert_and_has_no_physical_permission(monkeypatch, purpose):
    def denied(*args, **kwargs):
        pytest.fail("Inert factory inspected files")

    with monkeypatch.context() as patch:
        for name in ("open", "stat", "lstat", "resolve", "exists"):
            patch.setattr(Path, name, denied)
        runtime = candidate(ROOT, purpose)
    value = runtime.to_dict()
    assert value["status"] == "BUILD_REVIEW_REQUIRED"
    assert value["dispatch_enabled"] is False
    assert value["helper"]["sha256"] == policy._PINS[purpose]["helper"]


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_actual_installed_build_matches_without_hardware_qualification(purpose):
    source = source_fingerprint(ROOT)
    runtime = candidate(ROOT, purpose, source)
    review = verify(runtime)
    assert review["status"] == "REVIEWED_SOFTWARE_MATCHED"
    assert review["files_checked"] == 26
    assert review["source_sha256"] == source
    assert review["runtime_registration_sha256"] == runtime.registration_sha256
    assert 0 < review["bytes_read"] <= policy.MAX_NATIVE_READ_BYTES
    assert 0 < review["read_calls"] <= policy.MAX_NATIVE_READ_CALLS
    for name in (
        "original_context_authenticated",
        "physical_authority",
        "connected",
        "hardware_qualified",
    ):
        assert review[name] is False
    assert review["device_operations"] == 0


@pytest.mark.parametrize("field", ["helper", "build_record", "catalog_sha256"])
def test_unreviewed_candidate_cannot_learn_trust_from_its_own_bytes(field):
    value = candidate(ROOT).to_dict()
    if field == "catalog_sha256":
        value[field] = "9" * 64
    else:
        value[field]["sha256"] = "9" * 64
    with pytest.raises(
        policy.CameraActivationSoftwareError, match="UNREVIEWED_CAMERA_RUNTIME"
    ):
        verify(NativeCameraActivationRuntime(canonical(value)))


@pytest.mark.parametrize("kind", ["helper", "record", "native"])
@pytest.mark.parametrize("fault", ["changed", "missing", "directory"])
def test_missing_or_changed_software_is_actionable(tmp_path, monkeypatch, kind, fault):
    runtime = copied_runtime(tmp_path, monkeypatch)
    relative = {
        "helper": helper_relative_path("probe"),
        "record": build_record_relative_path("probe"),
        "native": policy._NATIVE_PREFIX + "activation_v2/camera_worker.cpp",
    }[kind]
    path = tmp_path / relative
    if fault == "changed":
        raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    else:
        path.unlink()  # Isolated test copy only.
        if fault == "directory":
            path.mkdir()
    with pytest.raises(policy.CameraActivationSoftwareError) as failure:
        verify(runtime)
    assert failure.value.relative_path == relative
    assert failure.value.code == (
        "RUNTIME_FILE_HASH_MISMATCH"
        if fault == "changed"
        else "RUNTIME_FILE_UNAVAILABLE_OR_UNSAFE"
    )


@pytest.mark.parametrize("boundary", [1, 2])
def test_application_source_is_current_before_and_after_reads(
    tmp_path, monkeypatch, boundary
):
    runtime = copied_runtime(tmp_path, monkeypatch)
    calls = []

    def source(_):
        calls.append(True)
        return "9" * 64 if len(calls) == boundary else "a" * 64

    monkeypatch.setattr(policy, "source_fingerprint", source)
    with pytest.raises(
        policy.CameraActivationSoftwareError, match="RUNTIME_APPLICATION_SOURCE_CHANGED"
    ):
        verify(runtime)
    assert len(calls) == boundary


@pytest.mark.parametrize("boundary", [0, 1, 2])
def test_stop_before_or_during_check_cannot_return_a_match(
    tmp_path, monkeypatch, boundary
):
    runtime = copied_runtime(tmp_path, monkeypatch)
    stop, calls = Event(), []

    def source(_):
        calls.append(True)
        if len(calls) == boundary:
            stop.set()
        return "a" * 64

    monkeypatch.setattr(policy, "source_fingerprint", source)
    if boundary == 0:
        stop.set()
    with pytest.raises(
        policy.CameraActivationSoftwareError, match="RUNTIME_CHECK_CANCELLED"
    ):
        verify(runtime, stop)
    assert len(calls) == boundary


@pytest.mark.parametrize("limit", ["MAX_NATIVE_READ_BYTES", "MAX_NATIVE_READ_CALLS"])
def test_finite_native_read_limits(tmp_path, monkeypatch, limit):
    runtime = copied_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(policy, limit, 1)
    with pytest.raises(
        policy.CameraActivationSoftwareError, match="RUNTIME_READ_(BYTE|CALL)_LIMIT"
    ):
        verify(runtime)


@pytest.mark.parametrize("fault", ["expired", "regressed", "catalog"])
def test_current_check_rejects_late_or_changed_context(tmp_path, monkeypatch, fault):
    runtime = copied_runtime(tmp_path, monkeypatch)
    now = [1000]
    monkeypatch.setattr(policy.time, "monotonic_ns", lambda: now[0])

    def source(_):
        if fault == "catalog":
            monkeypatch.setattr(policy, "_catalog", lambda: b"changed")
        else:
            now[0] = 2000 if fault == "expired" else 999
        return "a" * 64

    monkeypatch.setattr(policy, "source_fingerprint", source)
    with pytest.raises(
        policy.CameraActivationSoftwareError,
        match="RUNTIME_(SOFTWARE_POLICY_CHANGED|CHECK_EXPIRED_OR_CLOCK_REGRESSED)",
    ):
        policy.verify_reviewed_activation_runtime(
            runtime, cancellation=Event(), deadline_ns=2000
        )


@pytest.mark.parametrize("deadline", [True, 0, -1])
def test_bad_original_deadline_cannot_start_inspection(deadline):
    with pytest.raises(
        policy.CameraActivationSoftwareError, match="RUNTIME_ORIGINAL_DEADLINE_REQUIRED"
    ):
        policy.verify_reviewed_activation_runtime(
            candidate(ROOT), cancellation=Event(), deadline_ns=deadline
        )


def test_legacy_runtime_pins_and_worker_are_preserved():
    import hashlib
    from rocell.application.physical_camera_runtime_inspection import _PINS

    assert (
        _PINS["probe"]["helper"]
        == "e6072f26efa335ada46ef1459a66830a687b2d66c7ff45584aa4ac949eb027a1"
    )
    assert (
        _PINS["capture"]["helper"]
        == "31d2f2742b18c0935b3d7af07f8058f129421871be00860a3d7768e1e940ae2f"
    )
    assert (
        hashlib.sha256(
            (ROOT / policy._NATIVE_PREFIX / "camera_worker.cpp").read_bytes()
        ).hexdigest()
        == "0bc84f21e99d1d72eb7bc4a4969945016c7593247e67bf586f14101f59e298be"
    )


def test_file_change_during_read_is_not_a_successful_snapshot(tmp_path, monkeypatch):
    runtime = copied_runtime(tmp_path, monkeypatch)
    relative = helper_relative_path("probe")
    target = tmp_path / relative
    original_open = Path.open
    mutated = []

    class ChangingStream:
        def __enter__(self):
            self.stream = original_open(target, "rb")
            return self

        def __exit__(self, *args):
            self.stream.close()

        def fileno(self):
            return self.stream.fileno()

        def read(self, count):
            chunk = self.stream.read(count)
            if not mutated:
                with original_open(target, "ab") as writer:
                    writer.write(b"changed isolated test copy")
                mutated.append(True)
            return chunk

    def opened(path, mode="r", *args, **kwargs):
        if path == target and mode == "rb":
            return ChangingStream()
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    with pytest.raises(
        policy.CameraActivationSoftwareError, match="RUNTIME_FILE_CHANGED"
    ) as error:
        verify(runtime)
    assert mutated and error.value.relative_path == relative


def test_stop_during_native_read_keeps_actionable_file_context(tmp_path, monkeypatch):
    runtime = copied_runtime(tmp_path, monkeypatch)
    stop = Event()
    original_fstat = policy.os.fstat

    def stopped(fd):
        observed = original_fstat(fd)
        stop.set()
        return observed

    monkeypatch.setattr(policy.os, "fstat", stopped)
    with pytest.raises(
        policy.CameraActivationSoftwareError, match="RUNTIME_CHECK_CANCELLED"
    ) as error:
        verify(runtime, stop)
    assert error.value.relative_path == build_record_relative_path("probe")
