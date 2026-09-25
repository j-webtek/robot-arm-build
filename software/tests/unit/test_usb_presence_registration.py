"""Fixed actual files and modeled source seams; no helper or device execution."""

from contextlib import contextmanager
from dataclasses import FrozenInstanceError
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from threading import Event
import time
from types import SimpleNamespace

import pytest

from rocell.providers.windows import usb_presence_registration as m


WORKSPACE = Path(__file__).resolve().parents[3]
SOURCE = "a" * 64


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Runtime inspection must never execute a process")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


@pytest.fixture
def files(tmp_path, monkeypatch):
    # Copy the exact existing pinned files, never regenerate or alter a pin.
    for name in (
        *(p for p, _, _ in m.FIXED_SOURCE_PINS),
        m.BUILD_RECORD_PATH,
        m.HELPER_PATH,
        m.INCAPABLE_HELPER_PATH,
    ):
        source, dest = m._file_path(WORKSPACE, name), m._file_path(tmp_path, name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    # Only whole-workspace identity is modeled for this tiny fixture. Every
    # reported fixed-file hash/size is obtained by the actual inspector.
    monkeypatch.setattr(m, "source_fingerprint", lambda _: SOURCE)
    return tmp_path


def inspect(workspace, *, incapable=False, stop=None, deadline=None, progress=None):
    builder = (
        m.incapable_usb_presence_runtime_candidate
        if incapable
        else m.usb_presence_runtime_candidate
    )
    runtime = builder(workspace, source_sha256=SOURCE)
    report = m.inspect_usb_presence_runtime(
        runtime,
        cancellation=Event() if stop is None else stop,
        deadline_ns=(
            time.monotonic_ns() + 5_000_000_000 if deadline is None else deadline
        ),
        progress=progress,
    )
    return runtime, report


def test_candidates_and_pure_restore_are_inert_and_detached(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No file/source lookup during runtime construction")

    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(m, "source_fingerprint", forbidden)
    actual = m.usb_presence_runtime_candidate(WORKSPACE, source_sha256=SOURCE)
    fake = m.incapable_usb_presence_runtime_candidate(WORKSPACE, source_sha256=SOURCE)
    for item in (actual, fake):
        restored = type(item)(item.payload)
        assert restored.payload == item.payload
        assert restored.sha256 == hashlib.sha256(item.payload).hexdigest()
        doc = item.to_dict()
        assert doc["physical_authority"] is doc["hardware_qualified"] is False
        assert len(item.payload) < m.MAX_RUNTIME_BYTES
        doc["helper"]["path"] = "changed.exe"
        assert item.to_dict()["helper"]["path"] != "changed.exe"
        with pytest.raises(FrozenInstanceError):
            item.payload = b"{}"
    with pytest.raises(ValueError):
        m.UsbPresenceRuntimeRegistration(fake.payload)
    with pytest.raises(ValueError):
        m.IncapableUsbPresenceRuntimeRegistration(actual.payload)


@pytest.mark.parametrize(
    "path",
    [
        "relative",
        "C:\\",
        r"\\server\share",
        r"C:\test\..\other",
        r"C:\test\x" + "\\",
        r"C:\test" + "\n",
    ],
)
def test_untrusted_workspace_wire_is_rejected(path):
    doc = m.usb_presence_runtime_candidate(WORKSPACE, source_sha256=SOURCE).to_dict()
    doc["workspace"] = path
    with pytest.raises(ValueError):
        m.UsbPresenceRuntimeRegistration(m.canonical(doc))


@pytest.mark.parametrize(
    "field,value",
    [
        (("schema",), "rocell.usb_identity_runtime_registration.v1"),
        (("source_sha256",), "A" * 64),
        (("helper", "path"), "arbitrary.exe"),
        (("helper", "sha256"), "0" * 64),
        (("helper", "bytes"), 1),
        (("build_record", "sha256"), "0" * 64),
        (("argv_prefix",), ["--endpoint", "typed-target"]),
        (("request_hash_argument",), "CALLER_INPUT"),
        (("working_directory",), "software/native/windows_usb_identity"),
        (("budget", "process_count"), True),
        (("budget", "run_timeout_ms"), 13001),
        (("budget", "cleanup_timeout_ms"), 2001),
        (("budget", "stdout_bytes"), 66560),
        (("physical_authority",), 0),
        (("hardware_qualified",), True),
        (("process_model",), "NO_WINDOW"),
        (("required_lifetime_ns",), 20_000_000_000),
        (("composition",), "INCAPABLE_USB_PRESENCE"),
        (("source_files",), []),
    ],
)
def test_rehashed_runtime_cannot_substitute_fixed_contract(field, value):
    doc = m.usb_presence_runtime_candidate(WORKSPACE, source_sha256=SOURCE).to_dict()
    target = doc
    for key in field[:-1]:
        target = target[key]
    target[field[-1]] = value
    with pytest.raises(ValueError):
        m.UsbPresenceRuntimeRegistration(m.canonical(doc))


def test_build_record_and_immutable_roster_match_existing_actual_bytes():
    raw = m._file_path(WORKSPACE, m.BUILD_RECORD_PATH).read_bytes()
    assert (
        len(raw) == m.BUILD_RECORD_BYTES
        and hashlib.sha256(raw).hexdigest() == m.BUILD_RECORD_SHA256
    )
    record = json.loads(raw)
    assert record["production_executed"] is record["runtime_qualified"] is False
    assert record["sources"] == {p: h for p, h, _ in m.FIXED_SOURCE_PINS}
    for p, h, n in m.FIXED_SOURCE_PINS:
        payload = m._file_path(WORKSPACE, p).read_bytes()
        assert len(payload) == n and hashlib.sha256(payload).hexdigest() == h
    assert record["artifacts"][m.HELPER_PATH] == m.HELPER_SHA256
    assert record["artifacts"][m.INCAPABLE_HELPER_PATH] == m.INCAPABLE_HELPER_SHA256


def test_actual_current_workspace_source_and_fixed_files_match_without_execution():
    # Unlike the small copied fixtures, this check uses the real production
    # whole-workspace source calculator before and after actual file reads.
    source = m.source_fingerprint(WORKSPACE)
    runtime = m.usb_presence_runtime_candidate(WORKSPACE, source_sha256=source)
    report = m.inspect_usb_presence_runtime(
        runtime, cancellation=Event(), deadline_ns=time.monotonic_ns() + 5_000_000_000
    )
    assert report["source_sha256"] == source and report["status"] == "FILES_MATCHED"
    assert len(report["files"]) == 14 and report["device_io_performed"] is False


@pytest.mark.parametrize("incapable", [False, True])
def test_actual_fixed_file_inspection_checks_source_twice(
    files, monkeypatch, incapable
):
    calls, progress = [], []
    monkeypatch.setattr(
        m, "source_fingerprint", lambda path: calls.append(path) or SOURCE
    )
    runtime, report = inspect(files, incapable=incapable, progress=progress.append)
    assert calls == [files, files] and len(progress) == 14
    assert report["status"] == "FILES_MATCHED"
    assert report["runtime_registration_sha256"] == runtime.sha256
    assert report["source_sha256"] == SOURCE
    assert (
        report["physical_authority"]
        is report["hardware_qualified"]
        is report["device_io_performed"]
        is False
    )
    assert report["files"] == [
        {"path": p, "sha256": h, "bytes": n} for p, h, n in m.FIXED_SOURCE_PINS
    ] + [runtime.to_dict()["build_record"], runtime.to_dict()["helper"]]
    other = m.HELPER_PATH if incapable else m.INCAPABLE_HELPER_PATH
    assert other not in {row["path"] for row in report["files"]}


@pytest.mark.parametrize("change", ["same-size", "length", "hardlink", "missing"])
def test_changed_original_file_cannot_match(files, change):
    path = m._file_path(files, "entry.cpp")
    if change == "same-size":
        content = path.read_bytes()
        path.write_bytes(bytes([content[0] ^ 1]) + content[1:])
    elif change == "length":
        path.write_bytes(path.read_bytes() + b"x")
    elif change == "hardlink":
        os.link(path, path.with_suffix(".alias"))
    else:
        path.unlink()
    with pytest.raises((ValueError, OSError)):
        inspect(files)


@pytest.mark.parametrize("boundary", [0, 1])
def test_source_drift_before_or_after_files_is_not_match(files, monkeypatch, boundary):
    replies = iter(["b" * 64] if boundary == 0 else [SOURCE, "b" * 64])
    monkeypatch.setattr(m, "source_fingerprint", lambda _: next(replies))
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        inspect(files)


@pytest.mark.parametrize("cause", ["stop", "deadline"])
def test_preflight_refusal_performs_no_file_or_source_read(monkeypatch, cause):
    def forbidden(*args, **kwargs):
        pytest.fail("No reads after original Stop/deadline")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(m, "source_fingerprint", forbidden)
    stop = Event()
    if cause == "stop":
        stop.set()
    with pytest.raises(ValueError, match="CANCELLED|TIMED_OUT"):
        inspect(WORKSPACE, stop=stop, deadline=time.monotonic_ns() - 1)


@pytest.mark.parametrize("boundary", [0, 1])
@pytest.mark.parametrize("cause", ["stop", "deadline"])
def test_late_source_read_never_publishes(files, monkeypatch, boundary, cause):
    stop, clock, calls = Event(), [time.monotonic_ns()], []
    deadline = clock[0] + 1_000_000_000
    monkeypatch.setattr(m.time, "monotonic_ns", lambda: clock[0])

    def source(path):
        calls.append(path)
        if len(calls) == boundary + 1:
            stop.set() if cause == "stop" else clock.__setitem__(0, deadline)
        return SOURCE

    monkeypatch.setattr(m, "source_fingerprint", source)
    with pytest.raises(ValueError, match="CANCELLED|TIMED_OUT"):
        inspect(files, stop=stop, deadline=deadline)
    assert len(calls) == boundary + 1


def test_stop_after_successful_block_read_is_checked_before_hash_publication(
    files, monkeypatch
):
    stop = Event()
    original_open = Path.open
    target = m._file_path(files, "entry.cpp")

    @contextmanager
    def opened(path, *args, **kwargs):
        with original_open(path, *args, **kwargs) as stream:

            def read(size):
                data = stream.read(size)
                if path == target:
                    stop.set()
                return data

            yield SimpleNamespace(read=read, fileno=stream.fileno)

    monkeypatch.setattr(Path, "open", opened)
    with pytest.raises(ValueError, match="CANCELLED"):
        inspect(files, stop=stop)


def test_stop_from_last_progress_callback_cannot_publish_files_matched(files):
    stop, count = Event(), []

    def progress(message):
        count.append(message)
        if len(count) == 14:
            stop.set()

    with pytest.raises(ValueError, match="CANCELLED"):
        inspect(files, stop=stop, progress=progress)
    assert len(count) == 14


def test_path_open_swap_to_identical_bytes_is_detected_by_fd_identity(
    files, monkeypatch
):
    path = m._file_path(files, "entry.cpp")
    other = files / "identical-copy"
    shutil.copyfile(path, other)
    original_open = Path.open

    def opened(target, *args, **kwargs):
        return original_open(other if target == path else target, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    with pytest.raises(ValueError, match="PRESENCE_PIN_CHANGED"):
        inspect(files)


def test_reparse_ancestor_is_rejected_before_opening_file(files, monkeypatch):
    ancestor = files / "software/native/windows_usb_presence"
    original_stat = Path.stat

    def checked(path, *args, **kwargs):
        original = original_stat(path, *args, **kwargs)
        if path == ancestor:
            return SimpleNamespace(st_mode=original.st_mode, st_file_attributes=0x400)
        return original

    monkeypatch.setattr(Path, "stat", checked)
    with pytest.raises(ValueError, match="PRESENCE_PIN_PATH_LINK"):
        inspect(files)


def test_fixed_shared_source_mapping_never_accepts_arbitrary_traversal():
    for p in ("../../outside", "../windows_usb_identity/main.cpp", "C:/elsewhere.exe"):
        with pytest.raises(ValueError, match="FIXED_PRESENCE_FILE_REQUIRED"):
            m._file_path(WORKSPACE, p)
    expected = WORKSPACE / "software/native/windows_usb_identity/admission.cpp"
    assert m._file_path(WORKSPACE, "../windows_usb_identity/admission.cpp") == expected


def test_budget_is_exact_and_candidate_is_not_executable_preparation():
    doc = m.usb_presence_runtime_candidate(WORKSPACE, source_sha256=SOURCE).to_dict()
    assert doc["budget"]["stdout_bytes"] == 66 * 1024
    assert doc["budget"]["run_timeout_ms"] == 13000
    assert doc["budget"]["cleanup_timeout_ms"] == 2000
    assert doc["budget"]["process_count"] == 1
    assert doc["required_lifetime_ns"] == 15_000_000_000
    assert (
        doc["required_lifetime_ns"]
        == (doc["budget"]["run_timeout_ms"] + doc["budget"]["cleanup_timeout_ms"])
        * 1_000_000
    )
    # Preparation is now separately available, but an inert runtime candidate
    # still has no original review, consumed scope, target request or run method.
    assert not hasattr(
        m.usb_presence_runtime_candidate(WORKSPACE, source_sha256=SOURCE), "request"
    )
    assert not hasattr(m, "review_usb_presence_runtime")
