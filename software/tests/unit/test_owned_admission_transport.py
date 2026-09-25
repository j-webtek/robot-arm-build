"""Real owned pipes with a fixed incapable child; never hardware helpers."""

import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from rocell.providers.windows._owned_worker_win32 import (
    WindowsOwnedProcess,
    _Overlapped,
)
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessBudget,
    WorkerProcessRegistration,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "owned_admission_transport_child.py"
)
windows = pytest.mark.skipif(os.name != "nt", reason="Actual owned Windows pipes")


def registration(tmp_path):
    def pin(path):
        return PinnedWorkerFile(path, hashlib.sha256(path.read_bytes()).hexdigest())

    return WorkerProcessRegistration(
        "transport-unit-incapable",
        pin(Path(sys._base_executable)),
        ("-I", "-S", str(FIXTURE)),
        (pin(FIXTURE),),
        tmp_path,
        WorkerProcessBudget(run_timeout_ms=3000),
        "INCAPABLE_PROCESS_FIXTURE",
    )


def until(owner, reg, predicate, deadline):
    stop = threading.Event()
    while time.monotonic_ns() < deadline:
        ended = owner.poll(reg.budget)
        if predicate(ended):
            return
        assert not ended, owner.stdout
        stop.wait(0.005)
    pytest.fail("Fixed incapable transport child exceeded the test deadline")


@windows
@pytest.mark.parametrize("repeat", range(5))
def test_two_writes_keep_first_pipe_open_then_send_eof(tmp_path, repeat):
    reg = registration(tmp_path)
    owner = WindowsOwnedProcess()
    checks = []
    deadline = time.monotonic_ns() + 3_000_000_000

    def check():
        assert time.monotonic_ns() < deadline
        checks.append(True)

    try:
        owner.pin(reg)
        owner.start(reg, b"request\n", check=check, keep_stdin_open=True)
        until(
            owner,
            reg,
            lambda _: owner.stdout == b"READY\n" and not owner.pending,
            deadline,
        )
        assert owner.stdin and owner.written == 8
        assert not owner.tree_exited and owner._stdin_completed_count == 1
        owner.send_final_input(b"release\n", check=check)
        until(owner, reg, lambda ended: ended, deadline)
        assert owner.returncode == 0 and owner.written == 16 and not owner.stdin
        assert owner._stdin_completed_count == 2 and len(checks) == 4
        assert json.loads(owner.stdout.split(b"\n", 1)[1]) == {
            "request_bytes": 8,
            "release_bytes": 8,
        }
        with pytest.raises(ValueError, match="NOT_AVAILABLE"):
            owner.send_final_input(b"release\n", check=check)
    finally:
        assert owner.cleanup(time.monotonic_ns() + 2_000_000_000) == ()
    assert owner.tree_exited and not owner.handles and not owner.pins


@windows
def test_denied_final_check_never_writes_and_cannot_retry(tmp_path):
    reg, owner = registration(tmp_path), WindowsOwnedProcess()
    try:
        owner.pin(reg)
        owner.start(reg, b"request\n", check=lambda: None, keep_stdin_open=True)
        until(
            owner,
            reg,
            lambda _: owner.stdout == b"READY\n" and not owner.pending,
            time.monotonic_ns() + 3_000_000_000,
        )

        def denied():
            raise PermissionError("Exact parent admission was refused")

        with pytest.raises(PermissionError):
            owner.send_final_input(b"release\n", check=denied)
        assert owner.written == 8
        with pytest.raises(ValueError, match="NOT_AVAILABLE"):
            owner.send_final_input(b"release\n", check=lambda: None)
    finally:
        assert owner.cleanup(time.monotonic_ns() + 2_000_000_000) == ()
    assert owner.tree_exited and not owner.handles and not owner.pins


@windows
def test_cleanup_before_release_retains_only_request_write(tmp_path):
    reg, owner = registration(tmp_path), WindowsOwnedProcess()
    try:
        owner.pin(reg)
        owner.start(reg, b"request\n", check=lambda: None, keep_stdin_open=True)
        until(
            owner,
            reg,
            lambda _: owner.stdout == b"READY\n" and not owner.pending,
            time.monotonic_ns() + 3_000_000_000,
        )
    finally:
        assert owner.cleanup(time.monotonic_ns() + 2_000_000_000) == ()
    assert owner.written == 8 and owner.tree_exited
    with pytest.raises(ValueError, match="NOT_AVAILABLE"):
        owner.send_final_input(b"release\n", check=lambda: None)


def memory_owner(*, short=False, pending=False):
    """Injected kernel calls exercise actual owner write state without DLLs."""
    calls = []

    class Kernel:
        def ResetEvent(self, event):
            calls.append(("reset", event))
            return True

        def WriteFile(self, handle, buffer, size, transferred, overlapped):
            calls.append(("write", size))
            ctypes.cast(transferred, ctypes.POINTER(wintypes.DWORD))[0] = size - int(
                short
            )
            if pending:
                ctypes.set_last_error(997)
                return False
            return True

        def GetOverlappedResult(self, handle, overlapped, transferred, wait):
            ctypes.cast(transferred, ctypes.POINTER(wintypes.DWORD))[0] = (
                owner.expected_write - int(short)
            )
            return True

    owner = WindowsOwnedProcess.__new__(WindowsOwnedProcess)
    owner.k, owner.resumed, owner.stdin, owner.pending = Kernel(), True, 7, False
    owner._stdin_limit = 512
    owner._stdin_scheduled_bytes = owner._stdin_write_count = (
        owner._stdin_completed_count
    ) = 0
    owner._stdin_final_scheduled = False
    owner._close_after_write = True
    owner.expected_write = owner.written = 0
    owner.overlapped = _Overlapped()
    owner.overlapped.event = 8
    owner._close = lambda handle: calls.append(("close", handle))
    return owner, calls


@pytest.mark.parametrize("wire", [b"", "request", b"x" * 513, bytearray(b"x")])
def test_initial_invalid_input_cannot_be_followed_by_final_write(wire):
    owner, calls = memory_owner()
    with pytest.raises(ValueError, match="STDIN_BYTE_LIMIT"):
        owner._begin_input(wire, final=False, check=lambda: None)
    with pytest.raises(ValueError, match="NOT_AVAILABLE"):
        owner.send_final_input(b"release\n", check=lambda: None)
    assert calls == []


def test_initial_failed_check_cannot_be_followed_by_final_write():
    owner, calls = memory_owner()

    def fail():
        raise PermissionError("Denied before WriteFile")

    with pytest.raises(PermissionError):
        owner._begin_input(b"request\n", final=False, check=fail)
    with pytest.raises(ValueError, match="NOT_AVAILABLE"):
        owner.send_final_input(b"release\n", check=lambda: None)
    assert not any(call[0] == "write" for call in calls)


@pytest.mark.parametrize("pending", [False, True])
@windows
def test_short_initial_write_blocks_final_input(pending):
    owner, calls = memory_owner(short=True, pending=pending)
    with pytest.raises(OSError, match="SHORT_STDIN_WRITE"):
        owner._begin_input(b"request\n", final=False, check=lambda: None)
        owner._poll_write()
    assert owner.written == 7 and owner._stdin_completed_count == 0
    with pytest.raises(ValueError, match="NOT_AVAILABLE"):
        owner.send_final_input(b"release\n", check=lambda: None)
    assert sum(call[0] == "write" for call in calls) == 1


@windows
def test_pending_buffer_cannot_be_replaced_and_budget_is_cumulative():
    owner, calls = memory_owner(pending=True)
    owner._begin_input(b"request\n", final=False, check=lambda: None)
    original_buffer, original_overlapped = owner.write_buffer, owner.overlapped
    with pytest.raises(ValueError, match="NOT_AVAILABLE"):
        owner.send_final_input(b"release\n", check=lambda: None)
    assert (
        owner.write_buffer is original_buffer
        and owner.overlapped is original_overlapped
    )
    owner._poll_write()
    with pytest.raises(ValueError, match="STDIN_BYTE_LIMIT"):
        owner.send_final_input(b"x" * 505, check=lambda: None)
    assert owner.written == 8 and owner._stdin_final_scheduled
    assert sum(call[0] == "write" for call in calls) == 1


@pytest.mark.parametrize("wire, keep", [(b"", False), (b"x", 1), (b"x" * 513, False)])
def test_invalid_start_and_repeat_refused_before_kernel_creation(wire, keep):
    owner = WindowsOwnedProcess.__new__(WindowsOwnedProcess)
    owner._started = False
    reg = SimpleNamespace(budget=SimpleNamespace(stdin_bytes=512))
    with pytest.raises(ValueError):
        owner.start(reg, wire, check=lambda: None, keep_stdin_open=keep)
    with pytest.raises(ValueError, match="ALREADY_STARTED"):
        owner.start(reg, b"request\n", check=lambda: None)
