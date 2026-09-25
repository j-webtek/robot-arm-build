"""Private Win32 ownership backend; instantiated only by explicit run().

No global DLL loads, device enumeration, implicit destructors, or PID-based kill.
Only owned Job/process/pipe/file handles are used. Jobs are process containment,
not a security sandbox, serial shutdown proof, or hardware qualification.
"""

from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import time
import uuid
from typing import Any


class _Security(C.Structure):
    _fields_ = [("length", W.DWORD), ("descriptor", W.LPVOID), ("inherit", W.BOOL)]


class _Startup(C.Structure):
    _fields_ = [
        ("cb", W.DWORD),
        ("reserved", W.LPWSTR),
        ("desktop", W.LPWSTR),
        ("title", W.LPWSTR),
        ("x", W.DWORD),
        ("y", W.DWORD),
        ("xs", W.DWORD),
        ("ys", W.DWORD),
        ("xc", W.DWORD),
        ("yc", W.DWORD),
        ("fill", W.DWORD),
        ("flags", W.DWORD),
        ("show", W.WORD),
        ("reserved_size", W.WORD),
        ("reserved_bytes", C.POINTER(C.c_ubyte)),
        ("stdin", W.HANDLE),
        ("stdout", W.HANDLE),
        ("stderr", W.HANDLE),
    ]


class _StartupEx(C.Structure):
    _fields_ = [("startup", _Startup), ("attributes", W.LPVOID)]


class _Process(C.Structure):
    _fields_ = [
        ("process", W.HANDLE),
        ("thread", W.HANDLE),
        ("pid", W.DWORD),
        ("tid", W.DWORD),
    ]


class _BasicLimits(C.Structure):
    _fields_ = [
        ("process_time", C.c_longlong),
        ("job_time", C.c_longlong),
        ("flags", W.DWORD),
        ("minimum_working_set", C.c_size_t),
        ("maximum_working_set", C.c_size_t),
        ("processes", W.DWORD),
        ("affinity", C.c_size_t),
        ("priority", W.DWORD),
        ("scheduling", W.DWORD),
    ]


class _IoCounters(C.Structure):
    _fields_ = [
        (name, C.c_ulonglong)
        for name in (
            "reads",
            "writes",
            "other",
            "read_bytes",
            "write_bytes",
            "other_bytes",
        )
    ]


class _Limits(C.Structure):
    _fields_ = [
        ("basic", _BasicLimits),
        ("io", _IoCounters),
        ("process_memory", C.c_size_t),
        ("job_memory", C.c_size_t),
        ("peak_process_memory", C.c_size_t),
        ("peak_job_memory", C.c_size_t),
    ]


class _Pids(C.Structure):
    _fields_ = [("assigned", W.DWORD), ("listed", W.DWORD), ("pids", C.c_size_t * 4)]


class _Overlapped(C.Structure):
    _fields_ = [
        ("internal", C.c_size_t),
        ("high", C.c_size_t),
        ("offset", W.DWORD),
        ("offset_high", W.DWORD),
        ("event", W.HANDLE),
    ]


class _FileInformation(C.Structure):
    _fields_ = [
        ("attributes", W.DWORD),
        ("created", W.FILETIME),
        ("accessed", W.FILETIME),
        ("written", W.FILETIME),
        ("volume", W.DWORD),
        ("size_high", W.DWORD),
        ("size_low", W.DWORD),
        ("links", W.DWORD),
        ("index_high", W.DWORD),
        ("index_low", W.DWORD),
    ]


class WindowsOwnedProcess:
    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("WINDOWS_REQUIRED")
        self.k = C.WinDLL("kernel32", use_last_error=True)
        definitions = {
            "CreateJobObjectW": (W.HANDLE, [W.LPVOID, W.LPCWSTR]),
            "SetInformationJobObject": (W.BOOL, [W.HANDLE, C.c_int, W.LPVOID, W.DWORD]),
            "QueryInformationJobObject": (
                W.BOOL,
                [W.HANDLE, C.c_int, W.LPVOID, W.DWORD, W.LPVOID],
            ),
            "TerminateJobObject": (W.BOOL, [W.HANDLE, W.UINT]),
            "CreatePipe": (
                W.BOOL,
                [C.POINTER(W.HANDLE), C.POINTER(W.HANDLE), W.LPVOID, W.DWORD],
            ),
            "SetHandleInformation": (W.BOOL, [W.HANDLE, W.DWORD, W.DWORD]),
            "CreateNamedPipeW": (
                W.HANDLE,
                [
                    W.LPCWSTR,
                    W.DWORD,
                    W.DWORD,
                    W.DWORD,
                    W.DWORD,
                    W.DWORD,
                    W.DWORD,
                    W.LPVOID,
                ],
            ),
            "CreateFileW": (
                W.HANDLE,
                [W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID, W.DWORD, W.DWORD, W.HANDLE],
            ),
            "ConnectNamedPipe": (W.BOOL, [W.HANDLE, W.LPVOID]),
            "CreateEventW": (W.HANDLE, [W.LPVOID, W.BOOL, W.BOOL, W.LPCWSTR]),
            "ResetEvent": (W.BOOL, [W.HANDLE]),
            "WriteFile": (
                W.BOOL,
                [W.HANDLE, W.LPVOID, W.DWORD, C.POINTER(W.DWORD), W.LPVOID],
            ),
            "ReadFile": (
                W.BOOL,
                [W.HANDLE, W.LPVOID, W.DWORD, C.POINTER(W.DWORD), W.LPVOID],
            ),
            "PeekNamedPipe": (
                W.BOOL,
                [W.HANDLE, W.LPVOID, W.DWORD, W.LPVOID, C.POINTER(W.DWORD), W.LPVOID],
            ),
            "GetOverlappedResult": (
                W.BOOL,
                [W.HANDLE, W.LPVOID, C.POINTER(W.DWORD), W.BOOL],
            ),
            "CancelIoEx": (W.BOOL, [W.HANDLE, W.LPVOID]),
            "InitializeProcThreadAttributeList": (
                W.BOOL,
                [W.LPVOID, W.DWORD, W.DWORD, C.POINTER(C.c_size_t)],
            ),
            "UpdateProcThreadAttribute": (
                W.BOOL,
                [
                    W.LPVOID,
                    W.DWORD,
                    C.c_size_t,
                    W.LPVOID,
                    C.c_size_t,
                    W.LPVOID,
                    W.LPVOID,
                ],
            ),
            "DeleteProcThreadAttributeList": (None, [W.LPVOID]),
            "CreateProcessW": (
                W.BOOL,
                [
                    W.LPCWSTR,
                    W.LPWSTR,
                    W.LPVOID,
                    W.LPVOID,
                    W.BOOL,
                    W.DWORD,
                    W.LPVOID,
                    W.LPCWSTR,
                    W.LPVOID,
                    W.LPVOID,
                ],
            ),
            "ResumeThread": (W.DWORD, [W.HANDLE]),
            "WaitForSingleObject": (W.DWORD, [W.HANDLE, W.DWORD]),
            "GetExitCodeProcess": (W.BOOL, [W.HANDLE, C.POINTER(W.DWORD)]),
            "IsProcessInJob": (W.BOOL, [W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)]),
            "OpenProcess": (W.HANDLE, [W.DWORD, W.BOOL, W.DWORD]),
            "GetProcessHandleCount": (W.BOOL, [W.HANDLE, C.POINTER(W.DWORD)]),
            "GetFileInformationByHandle": (
                W.BOOL,
                [W.HANDLE, C.POINTER(_FileInformation)],
            ),
            "CloseHandle": (W.BOOL, [W.HANDLE]),
        }
        for name, (result, args) in definitions.items():
            fn = getattr(self.k, name)
            fn.restype, fn.argtypes = result, args
        self.handles: dict[int, str] = {}
        self.unclosed_handles: dict[int, str] = {}
        self.pins: list[Any] = []
        self.errors: list[str] = []
        self.created = self.resumed = self.tree_exited = False
        self.returncode: int | None = None
        self.written = self.peak_handles = self.peak_processes = 0
        self.stdout = self.stderr = b""
        self.job = self.process = self.thread = self.stdin = 0
        self.outpipe = self.errpipe = 0
        self.pid = 0
        self.pending = False
        self.overlapped: Any = None
        self.write_buffer: Any = None
        # The normal fixture has one write followed by EOF. A guarded native
        # child needs exactly two bounded writes: request, then final release.
        # This transport supplies neither a permit nor a physical dispatcher.
        self._started = False
        self._stdin_limit = self._stdin_scheduled_bytes = self._stdin_write_count = 0
        self._stdin_completed_count = 0
        self._stdin_final_scheduled = False
        self._close_after_write = True
        self.expected_write = 0
        self.stdout_eof = self.stderr_eof = False
        self.root_exit_observed_ns: int | None = None

    def _fail(self, operation: str) -> None:
        raise OSError(C.get_last_error(), operation)

    def _check(self, result: Any, operation: str) -> None:
        if not result:
            self._fail(operation)

    def _own(self, handle: Any, name: str) -> int:
        value = int(handle or 0)
        if value in {0, C.c_void_p(-1).value}:
            self._fail(name)
        self.handles[value] = name
        return value

    def _close(self, handle: int) -> None:
        # Exactly one explicit close attempt; failed close remains an error,
        # never an automatic second close on a possibly reused handle value.
        name = self.handles.pop(handle, None)
        if name is not None and not self.k.CloseHandle(handle):
            self.errors.append("CLOSE_FAILED:" + name)
            self.unclosed_handles[handle] = name

    @staticmethod
    def _regular(path: Path, *, directory: bool = False) -> os.stat_result:
        parts = (path,) + tuple(path.parents)
        if len(parts) > 128:
            raise ValueError("PIN_PATH_DEPTH_LIMIT")
        for index, part in enumerate(parts):
            value = part.stat(follow_symlinks=False)
            if (
                stat.S_ISLNK(value.st_mode)
                or getattr(value, "st_file_attributes", 0) & 0x400
            ):
                raise ValueError("PIN_PATH_LINK")
            if index == 0:
                selected = value
            if (index > 0 or directory) and not stat.S_ISDIR(value.st_mode):
                raise ValueError("PIN_PARENT_NOT_DIRECTORY")
        if not directory and (
            not stat.S_ISREG(selected.st_mode) or selected.st_nlink != 1
        ):
            raise ValueError("PIN_NOT_SINGLE_LINK_REGULAR_FILE")
        return selected

    def pin(self, registration: Any) -> None:
        self._regular(registration.working_directory, directory=True)
        directories = {
            registration.working_directory,
            *registration.working_directory.parents,
        }
        for pin in (registration.executable,) + registration.package_files:
            directories.update(pin.path.parents)
        self._pin_directories(directories)
        self._pin_files(registration)

    def _pin_directories(self, directories: set[Path]) -> None:
        if len(directories) > 128:
            raise ValueError("PIN_DIRECTORY_HANDLE_BUDGET")
        # Hold every path component against rename/reparse replacement while
        # CreateProcess resolves the registered path. Locks alone do not qualify
        # the interpreter/DLL dependency graph; native execution remains held.
        for directory in sorted(
            directories, key=lambda path: (len(path.parts), str(path))
        ):
            before = self._regular(directory, directory=True)
            handle = self._own(
                self.k.CreateFileW(
                    str(directory),
                    0x80000000,
                    0x1,
                    None,
                    3,
                    0x02000000 | 0x00200000,
                    None,
                ),
                "pinned-directory",
            )
            opened_directory = _FileInformation()
            self._check(
                self.k.GetFileInformationByHandle(handle, C.byref(opened_directory)),
                "ReadPinnedDirectoryIdentity",
            )
            if (
                (opened_directory.index_high << 32) | opened_directory.index_low
            ) != before.st_ino or opened_directory.attributes & 0x400:
                raise ValueError("PIN_DIRECTORY_CHANGED_WHILE_OPENING")

    def _pin_files(self, registration: Any) -> None:
        import msvcrt

        for pin in (registration.executable,) + registration.package_files:
            before = self._regular(pin.path)
            if not 0 < before.st_size <= pin.maximum_bytes:
                raise ValueError("PIN_BYTE_LIMIT")
            handle = self._own(
                self.k.CreateFileW(
                    str(pin.path), 0x80000000, 0x1, None, 3, 0x00200000, None
                ),
                "pinned-file",
            )
            descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            self.handles.pop(handle)  # Ownership is now the CRT descriptor.
            try:
                stream = os.fdopen(descriptor, "rb")
            except BaseException:
                os.close(descriptor)
                raise
            self.pins.append(stream)
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino, opened.st_size) != (
                before.st_dev,
                before.st_ino,
                before.st_size,
            ):
                raise ValueError("PIN_CHANGED_WHILE_OPENING")
            digest = hashlib.sha256()
            remaining = before.st_size
            while remaining:
                block = stream.read(min(1024 * 1024, remaining))
                if not block:
                    raise ValueError("PIN_TRUNCATED")
                remaining -= len(block)
                digest.update(block)
            if stream.read(1) or digest.hexdigest() != pin.sha256:
                raise ValueError("PIN_HASH_MISMATCH")

    def _output_pipe(self, name: str) -> tuple[int, int]:
        read, write = W.HANDLE(), W.HANDLE()
        sa = _Security(C.sizeof(_Security), None, True)
        self._check(
            self.k.CreatePipe(C.byref(read), C.byref(write), C.byref(sa), 4096),
            "CreatePipe",
        )
        parent = self._own(read.value, name + "-parent")
        child = self._own(write.value, name + "-child")
        self._check(self.k.SetHandleInformation(parent, 1, 0), "SetHandleInformation")
        return parent, child

    def start(
        self,
        registration: Any,
        wire: bytes,
        *,
        check: Any,
        keep_stdin_open: bool = False,
    ) -> None:
        """Start one contained child; optionally keep stdin for one final write.

        Existing callers retain their one-write/EOF behavior. The closed parent
        protocol must validate READY and recheck consumed authority before
        calling ``send_final_input``; this low-level owner does not authorize it.
        """
        if self._started:
            raise ValueError("PROCESS_OWNER_ALREADY_STARTED")
        self._started = True
        budget = registration.budget
        if type(keep_stdin_open) is not bool or not callable(check):
            raise ValueError("INVALID_STDIN_PROTOCOL")
        if (
            type(wire) is not bytes
            or not 0 < len(wire) <= budget.stdin_bytes
            or type(budget.stdin_bytes) is not int
            or not 512 <= budget.stdin_bytes <= 64 * 1024
        ):
            raise ValueError("STDIN_BYTE_LIMIT")
        self._stdin_limit = budget.stdin_bytes
        self.job = self._own(self.k.CreateJobObjectW(None, None), "job")
        limits = _Limits()
        # Kill-on-close, no breakaway, active-process and committed-memory caps.
        limits.basic.flags = 0x2000 | 0x8 | 0x100 | 0x200 | 0x400
        limits.basic.processes = budget.process_count
        limits.process_memory = budget.process_memory_bytes
        limits.job_memory = budget.job_memory_bytes
        self._check(
            self.k.SetInformationJobObject(
                self.job, 9, C.byref(limits), C.sizeof(limits)
            ),
            "SetJobLimits",
        )
        self.outpipe, child_out = self._output_pipe("stdout")
        self.errpipe, child_err = self._output_pipe("stderr")
        # Anonymous pipes do not support overlapped I/O. Only stdin uses a
        # private, remote-rejecting named pipe so a non-reading child cannot
        # block the supervisor in WriteFile. Both ends are opened by this parent.
        pipe_name = "\\\\.\\pipe\\rocell-owned-" + uuid.uuid4().hex
        self.stdin = self._own(
            self.k.CreateNamedPipeW(
                pipe_name, 0x2 | 0x40000000 | 0x80000, 0x8, 1, 4096, 4096, 0, None
            ),
            "stdin-parent",
        )
        sa = _Security(C.sizeof(_Security), None, True)
        child_in = self._own(
            self.k.CreateFileW(pipe_name, 0x80000000, 0, C.byref(sa), 3, 0, None),
            "stdin-child",
        )
        event = self._own(self.k.CreateEventW(None, True, False, None), "stdin-event")
        self.overlapped = _Overlapped()
        self.overlapped.event = event
        # The already-open client means ERROR_PIPE_CONNECTED is successful.
        if not self.k.ConnectNamedPipe(self.stdin, C.byref(self.overlapped)):
            self._check(C.get_last_error() == 535, "ConnectNamedPipe")
        child_handles = (W.HANDLE * 3)(child_in, child_out, child_err)
        jobs = (W.HANDLE * 1)(self.job)
        size = C.c_size_t()
        self.k.InitializeProcThreadAttributeList(None, 2, 0, C.byref(size))
        if not 0 < size.value <= 64 * 1024:
            raise OSError("ATTRIBUTE_LIST_SIZE_INVALID")
        attributes = C.create_string_buffer(size.value)
        self._check(
            self.k.InitializeProcThreadAttributeList(attributes, 2, 0, C.byref(size)),
            "InitializeAttributes",
        )
        try:
            self._check(
                self.k.UpdateProcThreadAttribute(
                    attributes,
                    0,
                    0x20002,
                    child_handles,
                    C.sizeof(child_handles),
                    None,
                    None,
                ),
                "InheritExplicitHandles",
            )
            # Windows 10+: atomic assignment before the first instruction.
            # No fallback to create-then-assign or breakaway is permitted.
            self._check(
                self.k.UpdateProcThreadAttribute(
                    attributes, 0, 0x2000D, jobs, C.sizeof(jobs), None, None
                ),
                "AtomicJobAssignment",
            )
            startup = _StartupEx()
            startup.startup.cb = C.sizeof(startup)
            startup.startup.flags = 0x100 | 0x1
            startup.startup.show = 0
            startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = (
                child_in,
                child_out,
                child_err,
            )
            startup.attributes = C.cast(attributes, W.LPVOID)
            process = _Process()
            command = C.create_unicode_buffer(
                subprocess.list2cmdline(
                    [str(registration.executable.path), *registration.argv]
                )
            )
            # Exact application name; no shell or inherited environment secrets.
            system_root = os.environ.get("SystemRoot", "")
            if not system_root or "\0" in system_root:
                raise ValueError("SYSTEM_ROOT_UNAVAILABLE")
            environment = C.create_unicode_buffer("SystemRoot=" + system_root + "\0\0")
            check()
            # These purpose-specific owners speak only through inherited pipes.
            # Detach it from console creation so a hidden conhost does not add
            # a second live Job member. Legacy owners keep CREATE_NO_WINDOW.
            # This is a closed class choice, never caller-supplied flag bits;
            # suspended creation and atomic Job containment stay unchanged.
            console_flag = (
                0x8
                if type(self)
                in (
                    WindowsOwnedUsbPipeProcess,
                    WindowsOwnedHostBootPipeProcess,
                    WindowsOwnedCameraActivationPipeProcess,
                    WindowsOwnedPassivePipeProcess,
                )
                else 0x8000000
            )
            self._check(
                self.k.CreateProcessW(
                    str(registration.executable.path),
                    command,
                    None,
                    None,
                    True,
                    0x4 | console_flag | 0x80000 | 0x400,
                    environment,
                    str(registration.working_directory),
                    C.byref(startup),
                    C.byref(process),
                ),
                "CreateContainedSuspendedProcess",
            )
            self.process = self._own(process.process, "process")
            self.thread = self._own(process.thread, "initial-thread")
            self.pid, self.created = process.pid, True
        finally:
            self.k.DeleteProcThreadAttributeList(attributes)
        for handle in (child_in, child_out, child_err):
            self._close(handle)
        if self.errors:
            raise OSError("CHILD_PIPE_PARENT_CLOSE_FAILED")
        in_job = W.BOOL()
        self._check(
            self.k.IsProcessInJob(self.process, self.job, C.byref(in_job)),
            "IsProcessInJob",
        )
        self._check(in_job.value, "ChildNotInOwnedJob")
        check()
        if self.k.ResumeThread(self.thread) != 1:
            self._fail("ResumeThread")
        self.resumed = True
        self._close(self.thread)
        self.thread = 0
        self._begin_input(wire, final=not keep_stdin_open, check=check)

    def send_final_input(self, wire: bytes, *, check: Any) -> None:
        """One final, non-retryable write and EOF after the first write drained.

        A failed check consumes this opportunity too. No second write can
        replace a pending OVERLAPPED buffer or extend the original byte budget.
        """
        if (
            not self.resumed
            or not self.stdin
            or self.pending
            or self._stdin_write_count != 1
            or self._stdin_completed_count != 1
            or self._stdin_final_scheduled
        ):
            raise ValueError("FINAL_STDIN_WRITE_NOT_AVAILABLE")
        self._begin_input(wire, final=True, check=check)

    def _begin_input(self, wire: bytes, *, final: bool, check: Any) -> None:
        # Mark the slot consumed before validation/check/Win32 work. An error
        # must lead to cleanup, not an automatic second authorization attempt.
        self._stdin_write_count += 1
        self._stdin_final_scheduled = final
        if (
            type(wire) is not bytes
            or not wire
            or len(wire) + self._stdin_scheduled_bytes > self._stdin_limit
        ):
            raise ValueError("STDIN_BYTE_LIMIT")
        if not callable(check):
            raise ValueError("STDIN_CHECK_REQUIRED")
        self._stdin_scheduled_bytes += len(wire)
        self._close_after_write = final
        self.expected_write = len(wire)
        # Reuse the event only after the previous operation completed. Each
        # write gets a fresh zeroed OVERLAPPED while retaining the owned event.
        event = self.overlapped.event
        self._check(self.k.ResetEvent(event), "ResetStdinEvent")
        self.overlapped = _Overlapped()
        self.overlapped.event = event
        self.write_buffer = C.create_string_buffer(wire)
        transferred = W.DWORD()
        check()
        if self.k.WriteFile(
            self.stdin,
            self.write_buffer,
            len(wire),
            C.byref(transferred),
            C.byref(self.overlapped),
        ):
            self._completed_input(transferred.value)
        elif C.get_last_error() == 997:
            self.pending = True
        else:
            self._fail("WriteStdin")

    def _completed_input(self, count: int) -> None:
        self.written += count
        if count != self.expected_write:
            raise OSError("SHORT_STDIN_WRITE")
        self._stdin_completed_count += 1
        if self._close_after_write:
            self._close(self.stdin)
            self.stdin = 0

    def _poll_write(self) -> None:
        if not self.pending:
            return
        transferred = W.DWORD()
        if self.k.GetOverlappedResult(
            self.stdin, C.byref(self.overlapped), C.byref(transferred), False
        ):
            self.pending = False
            self._completed_input(transferred.value)
        else:
            error = C.get_last_error()
            if error == 996:
                return
            if error in {995, 109}:
                self.pending = False
            raise OSError(error, "StdinCompletion")

    def _read_available(self, name: str, handle: int, maximum: int) -> None:
        available = W.DWORD()
        if not self.k.PeekNamedPipe(handle, None, 0, None, C.byref(available), None):
            if C.get_last_error() == 109:
                setattr(self, name + "_eof", True)
                return
            self._fail("Peek" + name)
        if not available.value:
            return
        retained = getattr(self, name)
        size = min(available.value, 4096, maximum - len(retained) + 1)
        block = C.create_string_buffer(size)
        read = W.DWORD()
        self._check(
            self.k.ReadFile(handle, block, size, C.byref(read), None), "Read" + name
        )
        combined = retained + block.raw[: read.value]
        setattr(self, name, combined[:maximum])
        if len(combined) > maximum:
            from rocell.providers.windows.owned_worker_process import OwnedWorkerError

            raise OwnedWorkerError(name.upper() + "_LIMIT")

    def _active(self, *, observe_handles: bool = False, handle_limit: int = 0) -> int:
        pids = _Pids()
        self._check(
            self.k.QueryInformationJobObject(
                self.job, 3, C.byref(pids), C.sizeof(pids), None
            ),
            "QueryOwnedJob",
        )
        if pids.listed > 4 or pids.assigned > 4:
            raise OSError("JOB_PROCESS_LIST_EXCEEDED")
        self.peak_processes = max(self.peak_processes, pids.assigned)
        if observe_handles:
            for pid in pids.pids[: pids.listed]:
                temporary = pid != self.pid
                handle = (
                    self.k.OpenProcess(0x1000 | 0x100000, False, pid)
                    if temporary
                    else self.process
                )
                if not handle:
                    if (
                        C.get_last_error() == 87
                    ):  # Child exited between bounded observations.
                        continue
                    self._fail("OpenOwnedJobMember")
                if temporary:
                    handle = self._own(handle, "member-observation")
                try:
                    if self.k.WaitForSingleObject(handle, 0) == 0:
                        continue
                    in_job, count = W.BOOL(), W.DWORD()
                    membership_ok = self.k.IsProcessInJob(
                        handle, self.job, C.byref(in_job)
                    )
                    if not membership_ok or not in_job.value:
                        if self.k.WaitForSingleObject(handle, 0) == 0:
                            continue
                        self._fail("ObservedPidNoLongerOwned")
                    if not self.k.GetProcessHandleCount(handle, C.byref(count)):
                        if self.k.WaitForSingleObject(handle, 0) == 0:
                            continue
                        self._fail("GetProcessHandleCount")
                    self.peak_handles = max(self.peak_handles, count.value)
                    if count.value > handle_limit:
                        from rocell.providers.windows.owned_worker_process import (
                            OwnedWorkerError,
                        )

                        raise OwnedWorkerError("OBSERVED_HANDLE_LIMIT")
                finally:
                    if temporary:
                        self._close(handle)
        return pids.assigned

    def poll(self, budget: Any) -> bool:
        self._poll_write()
        self._read_available("stdout", self.outpipe, budget.stdout_bytes)
        self._read_available("stderr", self.errpipe, budget.stderr_bytes)
        active = self._active(
            observe_handles=True, handle_limit=budget.observed_handles_per_process
        )
        if self.errors:
            raise OSError("HANDLE_OBSERVATION_CLEANUP_UNCERTAIN")
        waited = self.k.WaitForSingleObject(self.process, 0)
        if waited == 0:
            code = W.DWORD()
            self._check(
                self.k.GetExitCodeProcess(self.process, C.byref(code)), "GetExitCode"
            )
            self.returncode = code.value
            # The root may have exited since the prior handle-count sample.
            active = self._active()
            if active:
                # Job membership/accounting can lag a signaled process handle.
                # Allow a finite drain observation, within the outer campaign
                # deadline; do not classify that transient as a live descendant.
                if self.root_exit_observed_ns is None:
                    self.root_exit_observed_ns = time.monotonic_ns()
                if time.monotonic_ns() - self.root_exit_observed_ns < 100_000_000:
                    return False
                from rocell.providers.windows.owned_worker_process import (
                    OwnedWorkerError,
                )

                raise OwnedWorkerError("DESCENDANTS_REMAIN_AFTER_ROOT_EXIT")
            self.tree_exited = True
            return self.stdout_eof and self.stderr_eof and not self.pending
        if waited != 258:
            self._fail("WaitOwnedProcess")
        return False

    def cleanup(self, deadline_ns: int) -> tuple[str, ...]:
        """Retain uncertainty independently; termination is never device close."""
        self._stdin_final_scheduled = True
        if self.pending:
            if (
                not self.k.CancelIoEx(self.stdin, C.byref(self.overlapped))
                and C.get_last_error() != 1168
            ):
                self.errors.append("STDIN_CANCEL_UNCONFIRMED")
        if self.job and self.created and not self.tree_exited:
            if not self.k.TerminateJobObject(self.job, 0xE0000001):
                self.errors.append("JOB_TERMINATION_UNCONFIRMED")
            while time.monotonic_ns() < deadline_ns:
                try:
                    self.tree_exited = self._active() == 0
                except OSError:
                    self.errors.append("JOB_EXIT_OBSERVATION_FAILED")
                    break
                if self.tree_exited:
                    break
                time.sleep(0.01)
            if not self.tree_exited:
                self.errors.append("JOB_TREE_EXIT_UNCONFIRMED")
        while self.pending and time.monotonic_ns() < deadline_ns:
            try:
                self._poll_write()
            except OSError:
                if self.pending:
                    self.errors.append("STDIN_COMPLETION_UNCONFIRMED")
                    break
            if self.pending:
                time.sleep(0.005)
        if self.pending:
            self.errors.append("PENDING_STDIN_STORAGE_RETAINED")
            # Buffer + OVERLAPPED must outlive outstanding kernel use. The one-use
            # owner retains them; no retry or successful-cleanup claim follows.
        for handle in tuple(reversed(self.handles)):
            if self.pending and (
                handle == self.stdin or handle == self.overlapped.event
            ):
                continue
            self._close(handle)
        failed_pins = []
        for stream in self.pins:
            try:
                stream.close()
            except Exception:
                self.errors.append("PIN_CLOSE_UNCONFIRMED")
                failed_pins.append(stream)
        self.pins = failed_pins
        return tuple(dict.fromkeys(self.errors))


class WindowsOwnedCameraActivationPipeProcess(WindowsOwnedProcess):
    """Exact v2 camera pipe transport, not a camera permission or runtime review.

    The new protocol is pipe-only. Detaching its console avoids spending the
    single-process budget on a hidden console host. Suspended creation, atomic
    Job assignment, pinned inputs and inherited-handle restrictions stay shared.
    Legacy camera owners and subclasses retain their previous flag policy.
    """

    def pin(self, registration: Any) -> None:
        """Own fresh campaign directories inside the same cleanup lifecycle.

        Only the formal application campaign namespace opts into creation.
        Existing generic v2 preparation/contained-process tests retain their
        existing-directory policy; the legacy owner never enters this method.
        There is no caller flag, directory reuse, recursive mkdir or deletion.
        """
        from .native_camera_activation_protocol import (
            PROBE_SCHEMA,
            CAPTURE_SCHEMA,
            RESULT_SCHEMA,
        )
        from .native_camera_activation_registration import process_budget
        from .owned_worker_process import WorkerProcessRegistration

        if type(registration) is not WorkerProcessRegistration:
            raise ValueError("EXACT_CAMERA_DIRECTORY_REGISTRATION_REQUIRED")
        registration.__post_init__()
        working = registration.working_directory
        if not working.name.startswith("native-camera-"):
            return super().pin(registration)
        match = re.fullmatch(r"native-camera-(attempt-[0-9a-f]{32})", working.name)
        purpose = (
            "probe"
            if registration.worker_id == "windows-native-camera-activation-probe"
            else (
                "capture"
                if registration.worker_id == "windows-native-camera-activation-capture"
                else None
            )
        )
        if (
            match is None
            or purpose is None
            or working.parent == Path(working.anchor)
            or registration.composition != "PHYSICAL_UNQUALIFIED"
            or registration.request_schema
            != (PROBE_SCHEMA if purpose == "probe" else CAPTURE_SCHEMA)
            or registration.result_schema != RESULT_SCHEMA
            or registration.budget != process_budget(purpose)
            or len(registration.argv) != 3
            or registration.argv[:2]
            != ("--owned-" + purpose + "-v2", "--request-sha256")
            or re.fullmatch(r"[0-9a-f]{64}", registration.argv[2]) is None
        ):
            raise ValueError("EXACT_CAMERA_DIRECTORY_POLICY_REQUIRED")
        if getattr(self, "_camera_directory_attempted", False):
            raise ValueError("CAMERA_DIRECTORY_CREATION_ALREADY_ATTEMPTED")
        self._camera_directory_attempted = True
        directories = set(working.parents)
        for pin in (registration.executable,) + registration.package_files:
            directories.update(pin.path.parents)
        if len(directories) + (2 if purpose == "capture" else 1) > 128:
            raise ValueError("PIN_DIRECTORY_HANDLE_BUDGET")
        # Ancestors cannot be renamed/reparsed while creation and child I/O run.
        # New directory handles join the existing owner's exact close accounting.
        self._pin_directories(directories)
        working.mkdir(exist_ok=False)
        self._pin_directories({working})
        if purpose == "capture":
            output = working / ("capture-" + match[1])
            output.mkdir(exist_ok=False)
            self._pin_directories({output})
        self._pin_files(registration)


class WindowsOwnedUsbPipeProcess(WindowsOwnedProcess):
    """USB-specific detached pipe transport, not a different device authority.

    Only the new owned USB runner constructs this exact class. DETACHED_PROCESS
    changes console attachment, not Job membership, limits or handle ownership.
    Any observed extra process remains a USB-runner resource violation.
    """


class WindowsOwnedPassivePipeProcess(WindowsOwnedProcess):
    """Fixed passive child uses pipes only; no hidden console-host process.

    Keep all existing path pins, suspended creation, atomic Job assignment and
    cleanup unchanged. This class supplies no serial permission or flag input.
    """


class WindowsOwnedHostBootPipeProcess(WindowsOwnedProcess):
    """Exact local host-boot owner; no console, breakaway or caller flag choice.

    Windows-serviced executables may have WinSxS hard links. The inherited
    handle pin denies write/delete sharing across aliases and verifies the
    opened inode/size/hash. Reparse points and non-directory parents remain
    prohibited. This exception does not change any legacy owner pin policy.
    """

    @staticmethod
    def _regular(path: Path, *, directory: bool = False) -> os.stat_result:
        parts = (path,) + tuple(path.parents)
        if len(parts) > 128:
            raise ValueError("PIN_PATH_DEPTH_LIMIT")
        for index, part in enumerate(parts):
            value = part.stat(follow_symlinks=False)
            if (
                stat.S_ISLNK(value.st_mode)
                or getattr(value, "st_file_attributes", 0) & 0x400
            ):
                raise ValueError("PIN_PATH_LINK")
            if index == 0:
                selected = value
            if (index > 0 or directory) and not stat.S_ISDIR(value.st_mode):
                raise ValueError("PIN_PARENT_NOT_DIRECTORY")
        if not directory and not stat.S_ISREG(selected.st_mode):
            raise ValueError("PIN_NOT_REGULAR_FILE")
        return selected
