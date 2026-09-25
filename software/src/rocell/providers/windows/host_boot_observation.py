"""Explicit, bounded local CIM boot observations; never reboot or device authority.

Construction and pure codecs are inert. Only ``observe`` may launch the fixed
local command. Windows LastBootUpTime and SMBIOS UUID are provider reports, not
cryptographic attestation. An app launch, PID or inferred uptime is not a boot.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys
import threading
import time
from typing import Any, Callable, Protocol

from .owned_worker_process import PinnedWorkerFile, WorkerProcessBudget

REQUEST_SCHEMA = "rocell.host_boot_request.v1"
RESPONSE_SCHEMA = "rocell.windows_local_cim_boot.v1"
SCHEMA = "rocell.host_boot_observation.v1"
OWNED_SCHEMA = "rocell.host_boot_observation.v2"
OWNERSHIP_SCHEMA = "rocell.host_boot_process_ownership.v1"
PROCESS_MODEL = "DETACHED_PIPE_JOB_ONE_PROCESS"
MAX_OUTPUT = 4096
MAX_RECORD = 32 * 1024
PHASES = ("BASELINE", "RECONNECT_ABSENCE", "AFTER_RECONNECT", "AFTER_REBOOT")
LIMITATIONS = (
    "PROVIDER_REPORTED_BOOT_EPOCH_NOT_CRYPTOGRAPHIC_ATTESTATION",
    "SMBIOS_UUID_NOT_AUTHENTICATED_OR_CLONE_PROOF",
    "APP_LAUNCH_AND_PROCESS_ID_ARE_NOT_BOOT_IDENTITY",
    "FAST_STARTUP_MAY_PRESERVE_KERNEL_SESSION",
)
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z\Z")
_ERRORS = frozenset(
    {
        "CANCELLED",
        "TIMED_OUT",
        "BUDGET_DOES_NOT_FIT",
        "ADMISSION_DENIED",
        "EXECUTION_FAILED",
        "STDOUT_LIMIT",
        "STDERR_LIMIT",
        "OBSERVED_HANDLE_LIMIT",
        "OBSERVED_PROCESS_LIMIT",
        "DESCENDANTS_REMAIN_AFTER_ROOT_EXIT",
        "PROCESS_EXIT_FAILED",
        "PROCESS_CLEANUP_HOLD",
        "EXECUTOR_BUSY",
        "COMMAND_CHANGED",
        "WINDOWS_REQUIRED",
        "INVALID_EXECUTOR_RESULT",
    }
)

# No interpolation of request fields into code, class names, properties or argv.
# Module-qualified CIM calls without ComputerName/CimSession use local WMI COM.
# The second boot read detects an inconsistent observation interval. Methods
# (including Reboot/Shutdown), remote endpoints and device APIs are absent.
CIM_SCRIPT = r"""$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
try {
 $wire=[Console]::In.ReadToEnd()
 if ($wire.Length -gt 4096 -or $wire.Length -eq 0) { throw 'request' }
 $sha=[System.Security.Cryptography.SHA256]::Create()
 try { $digest=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::ASCII.GetBytes($wire)))).Replace('-','').ToLowerInvariant() } finally { $sha.Dispose() }
 $o=@(CimCmdlets\Get-CimInstance -Namespace root/cimv2 -ClassName Win32_OperatingSystem -Property LastBootUpTime,Version,BuildNumber -OperationTimeoutSec 3 -ErrorAction Stop)
 $m=@(CimCmdlets\Get-CimInstance -Namespace root/cimv2 -ClassName Win32_ComputerSystemProduct -Property UUID -OperationTimeoutSec 3 -ErrorAction Stop)
 $z=@(CimCmdlets\Get-CimInstance -Namespace root/cimv2 -ClassName Win32_OperatingSystem -Property LastBootUpTime -OperationTimeoutSec 3 -ErrorAction Stop)
 if ($o.Count -ne 1 -or $m.Count -ne 1 -or $z.Count -ne 1) { throw 'cardinality' }
 if ($o[0].LastBootUpTime -isnot [DateTime] -or $z[0].LastBootUpTime -isnot [DateTime]) { throw 'date' }
 if ($o[0].LastBootUpTime.Kind -eq [DateTimeKind]::Unspecified -or $z[0].LastBootUpTime.Kind -eq [DateTimeKind]::Unspecified) { throw 'ambiguous-date' }
 $fmt="yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'"
 $ci=[Globalization.CultureInfo]::InvariantCulture
 $result=[ordered]@{schema='rocell.windows_local_cim_boot.v1';request_sha256=$digest;provider='WINDOWS_LOCAL_CIM';machine_uuid=([string]$m[0].UUID).ToLowerInvariant();last_boot_up_time_utc=$o[0].LastBootUpTime.ToUniversalTime().ToString($fmt,$ci);confirmation_boot_up_time_utc=$z[0].LastBootUpTime.ToUniversalTime().ToString($fmt,$ci);os_version=[string]$o[0].Version;os_build=[string]$o[0].BuildNumber}
 [Console]::Write(($result | Microsoft.PowerShell.Utility\ConvertTo-Json -Compress -Depth 3))
} catch { [Console]::Error.Write('LOCAL_CIM_OBSERVATION_FAILED'); exit 70 }
"""
SCRIPT_SHA256 = hashlib.sha256(CIM_SCRIPT.encode("ascii")).hexdigest()
CIM_ARGV = ("-NoLogo", "-NoProfile", "-NonInteractive", "-Command", CIM_SCRIPT)
_DISPATCH = threading.Lock()
_UNRESOLVED_OWNER: Any = None


class HostBootError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise HostBootError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hash(value: Any) -> bool:
    return type(value) is str and bool(_HASH.fullmatch(value))


def _int(value: Any, low: int = 0, high: int = 2**63 - 1) -> bool:
    return type(value) is int and low <= value <= high


def _decode(payload: bytes, maximum: int) -> dict[str, Any]:
    _require(type(payload) is bytes and 0 < len(payload) <= maximum, "BYTE_LIMIT")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            _require(key not in result, "DUPLICATE_FIELD")
            result[key] = value
        return result

    def bad(_: str) -> Any:
        raise HostBootError("NONFINITE_JSON")

    try:
        value = json.loads(
            payload.decode("ascii"), object_pairs_hook=pairs, parse_constant=bad
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise HostBootError("INVALID_JSON") from exc
    _require(type(value) is dict, "OBJECT_REQUIRED")
    nodes = 0

    def structure(item: Any, depth: int = 0) -> None:
        nonlocal nodes
        nodes += 1
        _require(nodes <= 1024 and depth <= 12, "JSON_STRUCTURE_LIMIT")
        if type(item) is dict:
            for key, child in item.items():
                structure(key, depth + 1)
                structure(child, depth + 1)
        elif type(item) is list:
            for child in item:
                structure(child, depth + 1)
        else:
            _require(item is None or type(item) in {str, int, bool}, "JSON_VALUE_TYPE")

    structure(value)
    return value


def _utc_ns(value: Any) -> int:
    _require(type(value) is str and bool(_UTC.fullmatch(value)), "INVALID_BOOT_DATE")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=timezone.utc
        )
        delta = parsed - datetime(1970, 1, 1, tzinfo=timezone.utc)
        result = (
            delta.days * 86400 + delta.seconds
        ) * 1_000_000_000 + delta.microseconds * 1000
    except ValueError as exc:
        raise HostBootError("INVALID_BOOT_DATE") from exc
    _require(_int(result, 1), "INVALID_BOOT_DATE")
    return result


@dataclass(frozen=True)
class HostBootRequest:
    source_sha256: str
    session_id: str
    launch_session_id: str
    operation_id: str
    trial_id: str
    phase: str
    expires_at_ns: int

    def __post_init__(self) -> None:
        _require(_hash(self.source_sha256), "INVALID_SOURCE")
        for name in ("session_id", "launch_session_id", "operation_id", "trial_id"):
            value = getattr(self, name)
            _require(
                type(value) is str and bool(_ID.fullmatch(value)), "INVALID_BINDING_ID"
            )
        _require(self.phase in PHASES and type(self.phase) is str, "INVALID_PHASE")
        _require(_int(self.expires_at_ns, 1), "INVALID_EXPIRATION")

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {"schema": REQUEST_SCHEMA, **asdict(self)}

    @property
    def payload(self) -> bytes:
        return _canonical(self.to_dict())

    @property
    def sha256(self) -> str:
        return _sha(self.payload)


@dataclass(frozen=True)
class HostBootExecution:
    """Executor transport receipt. Injected executors are never physical evidence."""

    command: dict[str, Any]
    status: str
    primary_error: str | None
    cleanup_errors: tuple[str, ...]
    process_created: bool
    initial_thread_resumed: bool
    tree_exit_confirmed: bool
    returncode: int | None
    stdin_bytes_written: int
    stdout: bytes
    stderr: bytes
    started_monotonic_ns: int
    finished_monotonic_ns: int
    started_utc_ns: int
    finished_utc_ns: int
    stdout_eof: bool = False
    stderr_eof: bool = False
    ownership: dict[str, Any] | None = None


class HostBootExecutor(Protocol):
    def execute(
        self,
        request: HostBootRequest,
        *,
        cancellation: threading.Event,
        deadline_ns: int,
        admission_check: Callable[[], None],
    ) -> HostBootExecution: ...


@dataclass(frozen=True)
class _Command:
    executable: PinnedWorkerFile
    argv: tuple[str, ...]
    working_directory: Path
    budget: WorkerProcessBudget
    package_files: tuple[PinnedWorkerFile, ...] = ()

    def document(self) -> dict[str, Any]:
        return {
            "executable": str(self.executable.path),
            "executable_sha256": self.executable.sha256,
            "argv": list(self.argv),
            "working_directory": str(self.working_directory),
            "package_files": [
                {"path": str(p.path), "sha256": p.sha256} for p in self.package_files
            ],
            "budget": asdict(self.budget),
            "script_sha256": SCRIPT_SHA256,
            "process_model": PROCESS_MODEL,
        }


def _pin(path: Path, check: Callable[[], None]) -> PinnedWorkerFile:
    check()
    _require(
        path.is_absolute()
        and not str(path).startswith(("\\\\", "//"))
        and ".." not in path.parts,
        "EXECUTION_FAILED",
    )
    before = path.stat(follow_symlinks=False)
    _require(
        stat.S_ISREG(before.st_mode)
        and not getattr(before, "st_file_attributes", 0) & 0x400
        and 0 < before.st_size <= 64 * 1024 * 1024,
        "EXECUTION_FAILED",
    )
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        remaining = before.st_size
        while remaining:
            check()
            block = stream.read(min(remaining, 64 * 1024))
            _require(bool(block), "EXECUTION_FAILED")
            remaining -= len(block)
            digest.update(block)
        _require(not stream.read(1), "EXECUTION_FAILED")
        opened = os.fstat(stream.fileno())
    after = path.stat(follow_symlinks=False)
    _require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        "EXECUTION_FAILED",
    )
    return PinnedWorkerFile(path, digest.hexdigest())


def _system_powershell() -> Path:
    # Explicit-run only. Resolve the real system directory, not PATH or a
    # caller-provided executable. GetSystemDirectoryW is a supported local API.
    _require(os.name == "nt", "WINDOWS_REQUIRED")
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    fn = kernel.GetSystemDirectoryW
    fn.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    fn.restype = wintypes.UINT
    buffer = ctypes.create_unicode_buffer(32768)
    count = fn(buffer, len(buffer))
    _require(0 < count < len(buffer), "EXECUTION_FAILED")
    return Path(buffer.value) / "WindowsPowerShell" / "v1.0" / "powershell.exe"


def _native_owner() -> Any:
    from ._owned_worker_win32 import WindowsOwnedHostBootPipeProcess

    # Exact type is required by the backend's closed detached-console branch.
    return WindowsOwnedHostBootPipeProcess()


class LocalCimHostBootExecutor:
    """One fixed local PowerShell command, contained before its first instruction.

    Job caps cover the launched process tree, not the pre-existing Windows WMI
    service. Terminating our owned tree does not claim to cancel provider work
    inside an OS service. No serial, camera or USB handles are opened here.
    """

    def __init__(self) -> None:
        self._consumed = False
        self._lock = threading.Lock()

    def _command(self, check: Callable[[], None]) -> _Command:
        check()
        executable = _system_powershell()
        return _Command(
            _pin(executable, check),
            CIM_ARGV,
            executable.parent,
            WorkerProcessBudget(
                run_timeout_ms=10_000,
                cleanup_timeout_ms=2000,
                stdin_bytes=4096,
                stdout_bytes=MAX_OUTPUT,
                stderr_bytes=MAX_OUTPUT,
                process_count=1,
                observed_handles_per_process=1024,
            ),
        )

    def execute(
        self,
        request: HostBootRequest,
        *,
        cancellation: threading.Event,
        deadline_ns: int,
        admission_check: Callable[[], None],
    ) -> HostBootExecution:
        return _execute(self, request, cancellation, deadline_ns, admission_check)


def _ownership_snapshot(native: Any, cleanup_deadline: int | None) -> dict[str, Any]:
    """Retain observed owner state; unavailable accounting is never zero."""
    result: dict[str, Any] = {
        "schema": OWNERSHIP_SCHEMA,
        "accounting_complete": True,
        "cleanup_deadline_ns": cleanup_deadline,
    }
    for name in ("pid", "peak_processes", "peak_handles"):
        try:
            value = 0 if native is None else getattr(native, name)
            _require(_int(value, 0, 2**32 - 1), "INVALID_EXECUTOR_RESULT")
            result[name] = value
        except Exception:
            result[name] = None
            result["accounting_complete"] = False
    for name in ("handles", "pins", "unclosed_handles"):
        try:
            result[name + "_remaining"] = (
                0 if native is None else len(getattr(native, name))
            )
        except Exception:
            result[name + "_remaining"] = None
            result["accounting_complete"] = False
    try:
        pending = False if native is None else native.pending
        _require(type(pending) is bool, "INVALID_EXECUTOR_RESULT")
        result["stdin_pending"] = pending
    except Exception:
        result["stdin_pending"] = None
        result["accounting_complete"] = False
    return result


def _ownership_document(value: Any, execution: HostBootExecution) -> None:
    counters = (
        "pid",
        "peak_processes",
        "peak_handles",
        "handles_remaining",
        "pins_remaining",
        "unclosed_handles_remaining",
    )
    _require(
        type(value) is dict
        and set(value)
        == {
            "schema",
            "accounting_complete",
            "cleanup_deadline_ns",
            "stdin_pending",
            *counters,
        }
        and value["schema"] == OWNERSHIP_SCHEMA
        and type(value["accounting_complete"]) is bool,
        "OWNERSHIP_FIELDS",
    )
    for name in counters:
        _require(
            value[name] is None or _int(value[name], 0, 2**32 - 1), "OWNERSHIP_COUNTER"
        )
    _require(
        value["stdin_pending"] is None or type(value["stdin_pending"]) is bool,
        "OWNERSHIP_PENDING",
    )
    _require(
        value["accounting_complete"]
        == all(value[name] is not None for name in (*counters, "stdin_pending")),
        "OWNERSHIP_COVERAGE",
    )
    _require(
        value["cleanup_deadline_ns"] is None or _int(value["cleanup_deadline_ns"], 1),
        "OWNERSHIP_CLEANUP_DEADLINE",
    )
    if execution.status == "SUCCEEDED":
        budget = execution.command["budget"]
        _require(
            value["accounting_complete"]
            and value["pid"] > 0
            and 1 <= value["peak_processes"] <= budget["process_count"]
            and value["peak_handles"] <= budget["observed_handles_per_process"]
            and all(
                value[name] == 0
                for name in (
                    "handles_remaining",
                    "pins_remaining",
                    "unclosed_handles_remaining",
                )
            )
            and value["stdin_pending"] is False
            and value["cleanup_deadline_ns"] is not None
            and execution.finished_monotonic_ns <= value["cleanup_deadline_ns"],
            "OWNERSHIP_SUCCESS_UNCONFIRMED",
        )


def _execute(
    executor: LocalCimHostBootExecutor,
    request: HostBootRequest,
    cancellation: threading.Event,
    deadline_ns: int,
    admission_check: Callable[[], None],
) -> HostBootExecution:
    global _UNRESOLVED_OWNER
    with executor._lock:
        _require(not executor._consumed, "EXECUTOR_ALREADY_CONSUMED")
        executor._consumed = True
    started, wall = time.monotonic_ns(), time.time_ns()
    primary = None
    cleanup: tuple[str, ...] = ()
    native: Any = None
    command: _Command | None = None
    document: dict[str, Any] = {}
    locked = False
    cleanup_deadline: int | None = None
    stop_at = deadline_ns - 2_000_000_000
    sealed = request.payload

    def check() -> None:
        _require(not cancellation.is_set(), "CANCELLED")
        _require(time.monotonic_ns() < stop_at, "TIMED_OUT")
        _require(request.payload == sealed, "COMMAND_CHANGED")
        if command is not None:
            _require(command.document() == document, "COMMAND_CHANGED")

    def admit() -> None:
        check()
        try:
            returned: Any = admission_check()  # type: ignore[func-returns-value]
            _require(returned is None, "ADMISSION_DENIED")
        except HostBootError:
            raise
        except BaseException as exc:
            raise HostBootError("ADMISSION_DENIED") from exc
        check()
        if native is not None and native.created and not native.resumed:
            assert command is not None
            # The root is still suspended and its Job membership has been
            # verified by start(). Sample that actual Job before ResumeThread;
            # a very fast child must not leave only an inferred peak of one.
            native._active(
                observe_handles=True,
                handle_limit=command.budget.observed_handles_per_process,
            )
            resources()
            check()

    def resources() -> None:
        assert native is not None and command is not None
        _require(
            _int(native.peak_processes, 0, command.budget.process_count),
            "OBSERVED_PROCESS_LIMIT",
        )
        _require(
            _int(native.peak_handles, 0, command.budget.observed_handles_per_process),
            "OBSERVED_HANDLE_LIMIT",
        )

    try:
        _require(_UNRESOLVED_OWNER is None, "PROCESS_CLEANUP_HOLD")
        locked = _DISPATCH.acquire(blocking=False)
        _require(locked, "EXECUTOR_BUSY")
        _require(_UNRESOLVED_OWNER is None, "PROCESS_CLEANUP_HOLD")
        admit()
        command = executor._command(check)
        document = command.document()
        needed = (
            command.budget.run_timeout_ms + command.budget.cleanup_timeout_ms
        ) * 1_000_000
        _require(time.monotonic_ns() + needed <= deadline_ns, "BUDGET_DOES_NOT_FIT")
        stop_at = min(
            stop_at, time.monotonic_ns() + command.budget.run_timeout_ms * 1_000_000
        )
        native = _native_owner()
        native.pin(command)
        check()
        native.start(command, sealed, check=admit)
        while True:
            check()
            finished = native.poll(command.budget)
            resources()
            check()
            if finished:
                break
            cancellation.wait(0.01)
        _require(native.returncode == 0, "PROCESS_EXIT_FAILED")
    except BaseException as exc:
        primary = str(exc) if str(exc) in _ERRORS else "EXECUTION_FAILED"
    finally:
        if native is not None:
            cleanup_deadline = min(deadline_ns, time.monotonic_ns() + 2_000_000_000)
            try:
                errors = native.cleanup(cleanup_deadline)
                if (
                    errors
                    or native.handles
                    or native.pins
                    or native.unclosed_handles
                    or native.pending
                ):
                    cleanup = ("OWNED_RESOURCE_CLEANUP_UNCONFIRMED",)
                if native.created and not native.tree_exited:
                    cleanup = (*cleanup, "OWNED_TREE_EXIT_UNCONFIRMED")
            except BaseException:
                cleanup = ("OWNED_RESOURCE_CLEANUP_EXCEPTION",)
            if time.monotonic_ns() > cleanup_deadline:
                cleanup = (*cleanup, "CLEANUP_DEADLINE_EXCEEDED")
            if cleanup:
                _UNRESOLVED_OWNER = native
        if locked:
            _DISPATCH.release()
    if primary is None:
        try:
            admit()
        except BaseException as exc:
            primary = str(exc) if str(exc) in _ERRORS else "EXECUTION_FAILED"
    ownership = _ownership_snapshot(native, cleanup_deadline)
    if not ownership["accounting_complete"]:
        cleanup = (*cleanup, "OWNERSHIP_ACCOUNTING_UNCONFIRMED")
        if native is not None:
            _UNRESOLVED_OWNER = native
    finished = time.monotonic_ns()
    if primary is None and cleanup_deadline is not None and finished > cleanup_deadline:
        # Final admission is still bounded. Keep the completed response as a
        # held observation instead of losing it in the strict success codec.
        primary = "TIMED_OUT"
    state = "SUCCEEDED" if primary is None and not cleanup else "FAILED"
    if primary == "CANCELLED":
        state = "CANCELLED"
    elif primary in {"TIMED_OUT", "BUDGET_DOES_NOT_FIT"}:
        state = "TIMED_OUT"
    return HostBootExecution(
        document,
        state,
        primary,
        cleanup,
        bool(native and native.created),
        bool(native and native.resumed),
        bool(native and native.tree_exited),
        native.returncode if native else None,
        native.written if native else 0,
        native.stdout if native else b"",
        native.stderr if native else b"",
        started,
        finished,
        wall,
        time.time_ns(),
        stdout_eof=bool(native and native.stdout_eof),
        stderr_eof=bool(native and native.stderr_eof),
        ownership=ownership,
    )


class IncapableHostBootExecutor(LocalCimHostBootExecutor):
    """Explicit sealed child lifecycle fixture: synthetic bytes, never CIM."""

    def __init__(self, directory: Path, scenario: str = "nominal") -> None:
        super().__init__()
        _require(
            type(scenario) is str
            and scenario
            in {
                "nominal",
                "stall",
                "stdout-flood",
                "stderr-flood",
                "spawn-child",
                "wrong-binding",
                "malformed",
                "exit-failure",
            },
            "INVALID_FIXTURE_SCENARIO",
        )
        _require(
            isinstance(directory, Path) and directory.is_absolute(),
            "INVALID_FIXTURE_DIRECTORY",
        )
        self._directory, self._scenario = directory, scenario

    def _command(self, check: Callable[[], None]) -> _Command:
        child = Path(__file__).with_name("_host_boot_fixture.py")
        return _Command(
            _pin(Path(getattr(sys, "_base_executable", sys.executable)), check),
            ("-I", "-S", str(child), self._scenario),
            self._directory,
            WorkerProcessBudget(
                run_timeout_ms=700,
                cleanup_timeout_ms=2000,
                stdin_bytes=4096,
                stdout_bytes=MAX_OUTPUT,
                stderr_bytes=MAX_OUTPUT,
                process_count=1,
            ),
            (_pin(child, check),),
        )


def _response(payload: bytes, request_sha: str) -> dict[str, Any]:
    value = _decode(payload, MAX_OUTPUT)
    _require(
        set(value)
        == {
            "schema",
            "request_sha256",
            "provider",
            "machine_uuid",
            "last_boot_up_time_utc",
            "confirmation_boot_up_time_utc",
            "os_version",
            "os_build",
        },
        "PROVIDER_FIELDS",
    )
    _require(
        value["schema"] == RESPONSE_SCHEMA
        and value["request_sha256"] == request_sha
        and value["provider"] == "WINDOWS_LOCAL_CIM",
        "PROVIDER_BINDING",
    )
    _require(
        type(value["machine_uuid"]) is str
        and bool(_UUID.fullmatch(value["machine_uuid"])),
        "INVALID_MACHINE_UUID",
    )
    for name in ("last_boot_up_time_utc", "confirmation_boot_up_time_utc"):
        _utc_ns(value[name])
    _require(
        type(value["os_version"]) is str
        and bool(re.fullmatch(r"[0-9]{1,5}(?:\.[0-9]{1,5}){1,3}", value["os_version"])),
        "INVALID_OS_VERSION",
    )
    _require(
        type(value["os_build"]) is str
        and bool(re.fullmatch(r"[0-9]{1,10}", value["os_build"])),
        "INVALID_OS_BUILD",
    )
    return value


def _execution_document(value: HostBootExecution) -> dict[str, Any]:
    _require(type(value) is HostBootExecution, "INVALID_EXECUTOR_RESULT")
    _require(
        type(value.status) is str
        and value.status in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"},
        "INVALID_EXECUTOR_RESULT",
    )
    _require(
        value.primary_error is None
        or (type(value.primary_error) is str and value.primary_error in _ERRORS),
        "INVALID_EXECUTOR_RESULT",
    )
    _require(
        type(value.cleanup_errors) is tuple
        and len(value.cleanup_errors) <= 4
        and all(
            type(x) is str
            and x
            in {
                "OWNED_RESOURCE_CLEANUP_UNCONFIRMED",
                "OWNED_TREE_EXIT_UNCONFIRMED",
                "OWNED_RESOURCE_CLEANUP_EXCEPTION",
                "CLEANUP_DEADLINE_EXCEEDED",
                "OWNERSHIP_ACCOUNTING_UNCONFIRMED",
            }
            for x in value.cleanup_errors
        ),
        "INVALID_EXECUTOR_RESULT",
    )
    for name in (
        "process_created",
        "initial_thread_resumed",
        "tree_exit_confirmed",
        "stdout_eof",
        "stderr_eof",
    ):
        _require(type(getattr(value, name)) is bool, "INVALID_EXECUTOR_RESULT")
    _require(
        not value.initial_thread_resumed or value.process_created,
        "INVALID_EXECUTOR_RESULT",
    )
    _require(
        not value.tree_exit_confirmed or value.process_created,
        "INVALID_EXECUTOR_RESULT",
    )
    _require(
        value.returncode is None or _int(value.returncode, 0, 2**32 - 1),
        "INVALID_EXECUTOR_RESULT",
    )
    _require(_int(value.stdin_bytes_written, 0, 4096), "INVALID_EXECUTOR_RESULT")
    _require(
        type(value.stdout) is bytes
        and len(value.stdout) <= MAX_OUTPUT
        and type(value.stderr) is bytes
        and len(value.stderr) <= MAX_OUTPUT,
        "INVALID_EXECUTOR_RESULT",
    )
    for name in (
        "started_monotonic_ns",
        "finished_monotonic_ns",
        "started_utc_ns",
        "finished_utc_ns",
    ):
        _require(_int(getattr(value, name), 1), "INVALID_EXECUTOR_RESULT")
    _require(
        value.finished_monotonic_ns >= value.started_monotonic_ns,
        "INVALID_EXECUTOR_RESULT",
    )
    if value.status == "SUCCEEDED":
        _require(
            value.primary_error is None
            and not value.cleanup_errors
            and value.process_created
            and value.initial_thread_resumed
            and value.tree_exit_confirmed
            and value.returncode == 0,
            "INVALID_EXECUTOR_RESULT",
        )
        _require(value.stdout_eof and value.stderr_eof, "PIPE_COMPLETION_UNCONFIRMED")
    else:
        _require(
            value.primary_error is not None or bool(value.cleanup_errors),
            "INVALID_EXECUTOR_RESULT",
        )
    _require(
        (value.status != "CANCELLED" or value.primary_error == "CANCELLED")
        and (
            value.status != "TIMED_OUT"
            or value.primary_error in {"TIMED_OUT", "BUDGET_DOES_NOT_FIT"}
        ),
        "INVALID_EXECUTOR_RESULT",
    )
    result = asdict(value)
    if value.ownership is None:
        # Retained v1/external modeled executions do not gain ownership facts.
        result.pop("ownership")
    else:
        _ownership_document(value.ownership, value)
    result.pop("stdout")
    result.pop("stderr")
    result.pop("command")
    result["cleanup_errors"] = list(value.cleanup_errors)
    for name in ("stdout", "stderr"):
        raw = getattr(value, name)
        result[name + "_hex"] = raw.hex()
        result[name + "_bytes"] = len(raw)
        result[name + "_sha256"] = _sha(raw)
        result[name + "_retention"] = (
            "COMPLETE_PIPE_EOF"
            if getattr(value, name + "_eof")
            else "BOUNDED_PREFIX_ONLY" if raw else "NO_OUTPUT_RETAINED"
        )
    return result


def _derived(
    request: HostBootRequest,
    execution: HostBootExecution,
    response: dict[str, Any] | None,
    deadline: int,
) -> tuple[list[str], str | None, str | None]:
    reasons: list[str] = []
    if execution.status != "SUCCEEDED":
        reasons.append("HOST_BOOT_EXECUTION_UNCONFIRMED")
    if execution.stderr:
        reasons.append("HOST_BOOT_STDERR_RETAINED")
    if response is None:
        reasons.append("HOST_BOOT_PROVIDER_RESPONSE_INVALID")
    if execution.finished_utc_ns < execution.started_utc_ns:
        reasons.append("HOST_CLOCK_CHRONOLOGY_INCONSISTENT")
    if (
        abs(
            (execution.finished_utc_ns - execution.started_utc_ns)
            - (execution.finished_monotonic_ns - execution.started_monotonic_ns)
        )
        > 1_000_000_000
    ):
        reasons.append("HOST_CLOCK_DISCONTINUITY_OBSERVED")
    if execution.finished_monotonic_ns > deadline or deadline > request.expires_at_ns:
        reasons.append("HOST_BOOT_DEADLINE_EXCEEDED")
    if response is not None:
        if response["machine_uuid"].replace("-", "") in {"0" * 32, "f" * 32}:
            reasons.append("HOST_IDENTITY_UNAVAILABLE")
        if (
            response["last_boot_up_time_utc"]
            != response["confirmation_boot_up_time_utc"]
        ):
            reasons.append("HOST_BOOT_CHANGED_DURING_OBSERVATION")
        if _utc_ns(response["last_boot_up_time_utc"]) > execution.started_utc_ns:
            reasons.append("HOST_BOOT_CHRONOLOGY_INCONSISTENT")
    if reasons:
        return reasons, None, None
    assert response is not None
    host = _sha(
        _canonical({"basis": "SMBIOS_SYSTEM_UUID", "uuid": response["machine_uuid"]})
    )
    boot = _sha(
        _canonical(
            {
                "host_key_sha256": host,
                "last_boot_up_time_utc": response["last_boot_up_time_utc"],
            }
        )
    )
    return reasons, host, boot


def _command_document(
    value: Any, origin: str, execution: HostBootExecution, *, owned: bool = False
) -> None:
    _require(type(value) is dict, "COMMAND_FIELDS")
    if not value:
        _require(
            not execution.process_created and execution.status != "SUCCEEDED",
            "COMMAND_REQUIRED",
        )
        return
    _require(
        set(value)
        == {
            "executable",
            "executable_sha256",
            "argv",
            "working_directory",
            "package_files",
            "budget",
            "script_sha256",
        }
        | ({"process_model"} if owned else set()),
        "COMMAND_FIELDS",
    )
    if owned:
        _require(value["process_model"] == PROCESS_MODEL, "COMMAND_PROCESS_MODEL")
    for name in ("executable", "working_directory"):
        path = value[name]
        _require(
            type(path) is str
            and 0 < len(path) <= 4096
            and not any(ord(x) < 32 for x in path),
            "COMMAND_PATH",
        )
        # Retained Windows paths can be checked on other hosts without resolving
        # them or treating the record as a launchable registration.
        win = PureWindowsPath(path)
        _require(
            win.is_absolute()
            and not win.drive.startswith("\\\\")
            and ".." not in win.parts,
            "COMMAND_PATH",
        )
    _require(
        _hash(value["executable_sha256"]) and value["script_sha256"] == SCRIPT_SHA256,
        "COMMAND_PIN",
    )
    try:
        budget = WorkerProcessBudget(**value["budget"])
    except (TypeError, ValueError) as exc:
        raise HostBootError("COMMAND_BUDGET") from exc
    _require(
        asdict(budget) == value["budget"]
        and budget.stdin_bytes == 4096
        and budget.stdout_bytes == MAX_OUTPUT
        and budget.stderr_bytes == MAX_OUTPUT
        and budget.cleanup_timeout_ms == 2000,
        "COMMAND_BUDGET",
    )
    if origin == "INCAPABLE_OWNED_CHILD":
        child = str(Path(__file__).with_name("_host_boot_fixture.py"))
        _require(
            type(value["argv"]) is list
            and len(value["argv"]) == 4
            and value["argv"][:3] == ["-I", "-S", child]
            and type(value["argv"][3]) is str
            and value["argv"][3]
            in {
                "nominal",
                "stall",
                "stdout-flood",
                "stderr-flood",
                "spawn-child",
                "wrong-binding",
                "malformed",
                "exit-failure",
            },
            "FIXTURE_COMMAND",
        )
        _require(
            type(value["package_files"]) is list
            and len(value["package_files"]) == 1
            and type(value["package_files"][0]) is dict
            and set(value["package_files"][0]) == {"path", "sha256"}
            and value["package_files"][0]["path"] == child
            and _hash(value["package_files"][0]["sha256"]),
            "FIXTURE_PACKAGE",
        )
        _require(
            budget
            == WorkerProcessBudget(
                run_timeout_ms=700,
                cleanup_timeout_ms=2000,
                stdin_bytes=4096,
                stdout_bytes=MAX_OUTPUT,
                stderr_bytes=MAX_OUTPUT,
                process_count=1 if owned else 2,
            ),
            "FIXTURE_BUDGET",
        )
    else:
        _require(
            value["argv"] == list(CIM_ARGV) and value["package_files"] == [],
            "FIXED_LOCAL_CIM_COMMAND",
        )
        path = PureWindowsPath(value["executable"])
        _require(
            tuple(p.lower() for p in path.parts[-3:])
            == ("windowspowershell", "v1.0", "powershell.exe")
            and str(path.parent) == str(PureWindowsPath(value["working_directory"])),
            "FIXED_LOCAL_CIM_EXECUTABLE",
        )
        _require(
            budget
            == WorkerProcessBudget(
                run_timeout_ms=10000,
                cleanup_timeout_ms=2000,
                stdin_bytes=4096,
                stdout_bytes=MAX_OUTPUT,
                stderr_bytes=MAX_OUTPUT,
                process_count=1,
                observed_handles_per_process=1024,
            ),
            "FIXED_LOCAL_CIM_BUDGET",
        )


@dataclass(frozen=True)
class HostBootObservation:
    payload: bytes

    def __post_init__(self) -> None:
        value = _decode(self.payload, MAX_RECORD)
        _require(
            set(value)
            == {
                "schema",
                "request",
                "request_sha256",
                "deadline_ns",
                "origin",
                "command",
                "command_sha256",
                "execution",
                "response",
                "status",
                "blockers",
                "host_key_sha256",
                "boot_key_sha256",
                "limitations",
                "physical_authority",
                "hardware_qualified",
                "device_io_performed",
            },
            "OBSERVATION_FIELDS",
        )
        _require(
            value["schema"] in {SCHEMA, OWNED_SCHEMA}
            and type(value["origin"]) is str
            and value["origin"]
            in {"WINDOWS_LOCAL_CIM", "INJECTED_CIM_EXECUTOR", "INCAPABLE_OWNED_CHILD"},
            "OBSERVATION_SCHEMA",
        )
        _require(
            type(value["request"]) is dict and type(value["execution"]) is dict,
            "OBSERVATION_OBJECTS_REQUIRED",
        )
        raw_request = dict(value["request"])
        _require(raw_request.pop("schema", None) == REQUEST_SCHEMA, "REQUEST_SCHEMA")
        try:
            request = HostBootRequest(**raw_request)
        except TypeError as exc:
            raise HostBootError("REQUEST_FIELDS") from exc
        _require(
            value["request_sha256"] == request.sha256
            and _int(value["deadline_ns"], 1, request.expires_at_ns),
            "REQUEST_BINDING",
        )
        command = value["command"]
        _require(
            type(command) is dict
            and len(_canonical(command)) <= 12 * 1024
            and value["command_sha256"] == _sha(_canonical(command)),
            "COMMAND_BINDING",
        )
        raw_execution = dict(value["execution"])
        try:
            streams = {}
            for name in ("stdout", "stderr"):
                encoded = raw_execution.pop(name + "_hex")
                _require(
                    type(encoded) is str
                    and len(encoded) <= MAX_OUTPUT * 2
                    and bool(re.fullmatch(r"(?:[0-9a-f]{2})*", encoded)),
                    "STREAM_ENCODING",
                )
                streams[name] = bytes.fromhex(encoded)
                count = raw_execution.pop(name + "_bytes")
                _require(
                    _int(count, 0, MAX_OUTPUT)
                    and count == len(streams[name])
                    and raw_execution.pop(name + "_sha256") == _sha(streams[name]),
                    "STREAM_HASH",
                )
                retained = raw_execution.pop(name + "_retention")
                expected = (
                    "COMPLETE_PIPE_EOF"
                    if raw_execution.get(name + "_eof") is True
                    else (
                        "BOUNDED_PREFIX_ONLY" if streams[name] else "NO_OUTPUT_RETAINED"
                    )
                )
                _require(retained == expected, "STREAM_RETENTION")
            raw_execution["cleanup_errors"] = tuple(raw_execution["cleanup_errors"])
            execution = HostBootExecution(
                command=command,
                stdout=streams["stdout"],
                stderr=streams["stderr"],
                **raw_execution,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HostBootError("EXECUTION_FIELDS") from exc
        _require(
            _execution_document(execution) == value["execution"], "EXECUTION_FIELDS"
        )
        owned = value["schema"] == OWNED_SCHEMA
        _require(owned == (execution.ownership is not None), "OWNERSHIP_VERSION")
        _command_document(command, value["origin"], execution, owned=owned)
        if owned:
            assert execution.ownership is not None
            if execution.ownership["cleanup_deadline_ns"] is not None:
                _require(
                    execution.ownership["cleanup_deadline_ns"] <= value["deadline_ns"],
                    "OWNERSHIP_CLEANUP_DEADLINE",
                )
        if execution.status == "SUCCEEDED":
            _require(
                execution.stdin_bytes_written == len(request.payload),
                "REQUEST_DELIVERY_UNCONFIRMED",
            )
        response = None
        try:
            response = _response(execution.stdout, request.sha256)
        except HostBootError:
            pass
        _require(response == value["response"], "RESPONSE_BINDING")
        blockers, host, boot = _derived(
            request, execution, response, value["deadline_ns"]
        )
        _require(
            value["blockers"] == blockers
            and value["host_key_sha256"] == host
            and value["boot_key_sha256"] == boot
            and value["status"] == ("HELD" if blockers else "OBSERVED_HOST_BOOT"),
            "DERIVED_BINDING",
        )
        _require(value["limitations"] == list(LIMITATIONS), "LIMITATIONS")
        _require(
            all(
                value[x] is False
                for x in (
                    "physical_authority",
                    "hardware_qualified",
                    "device_io_performed",
                )
            ),
            "NO_AUTHORITY",
        )
        _require(self.payload == _canonical(value), "CANONICAL_RECORD_REQUIRED")

    @property
    def sha256(self) -> str:
        return _sha(self.payload)

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return _decode(self.payload, MAX_RECORD)

    def safe_summary(self) -> dict[str, Any]:
        value = self.to_dict()
        return {
            "schema": (
                "rocell.host_boot_summary.v2"
                if value["schema"] == OWNED_SCHEMA
                else "rocell.host_boot_summary.v1"
            ),
            "observation_sha256": self.sha256,
            **{
                key: value[key]
                for key in (
                    "request",
                    "origin",
                    "status",
                    "response",
                    "blockers",
                    "host_key_sha256",
                    "boot_key_sha256",
                    "limitations",
                    "physical_authority",
                    "hardware_qualified",
                    "device_io_performed",
                )
            },
            "process_status": value["execution"]["status"],
            "tree_exit_confirmed": value["execution"]["tree_exit_confirmed"],
            **(
                {"ownership": value["execution"]["ownership"]}
                if value["schema"] == OWNED_SCHEMA
                else {}
            ),
        }


class WindowsHostBootObserver:
    def __init__(self, executor: HostBootExecutor | None = None) -> None:
        self._executor = executor
        self._used = False
        self._lock = threading.Lock()
        self.evidence: HostBootObservation | None = None

    def observe(
        self,
        request: HostBootRequest,
        *,
        cancellation: threading.Event,
        deadline_ns: int,
        admission_check: Callable[[], None],
    ) -> HostBootObservation:
        with self._lock:
            _require(not self._used, "OBSERVER_ALREADY_CONSUMED")
            self._used = True
        _require(type(request) is HostBootRequest, "EXACT_REQUEST_REQUIRED")
        request.__post_init__()
        _require(
            isinstance(cancellation, threading.Event)
            and callable(admission_check)
            and _int(deadline_ns, 1, request.expires_at_ns),
            "INVALID_EXECUTION_CONTEXT",
        )
        executor = (
            self._executor if self._executor is not None else LocalCimHostBootExecutor()
        )
        original = request.to_dict()
        execution = executor.execute(
            request,
            cancellation=cancellation,
            deadline_ns=deadline_ns,
            admission_check=admission_check,
        )
        if execution.status == "SUCCEEDED" and cancellation.is_set():
            execution = replace(
                execution, status="CANCELLED", primary_error="CANCELLED"
            )
        elif execution.status == "SUCCEEDED" and time.monotonic_ns() >= deadline_ns:
            execution = replace(
                execution, status="TIMED_OUT", primary_error="TIMED_OUT"
            )
        # Preserve the admitted subject even if a hostile injected implementation
        # mutated a nominally frozen request. Such a response cannot match it.
        sealed_request = HostBootRequest(
            **{k: v for k, v in original.items() if k != "schema"}
        )
        result = _execution_document(execution)
        response = None
        try:
            response = _response(execution.stdout, sealed_request.sha256)
        except HostBootError:
            pass
        blockers, host, boot = _derived(
            sealed_request, execution, response, deadline_ns
        )
        origin = (
            "WINDOWS_LOCAL_CIM"
            if type(executor) is LocalCimHostBootExecutor
            else (
                "INCAPABLE_OWNED_CHILD"
                if type(executor) is IncapableHostBootExecutor
                else "INJECTED_CIM_EXECUTOR"
            )
        )
        value = {
            "schema": OWNED_SCHEMA if execution.ownership is not None else SCHEMA,
            "request": original,
            "request_sha256": sealed_request.sha256,
            "deadline_ns": deadline_ns,
            "origin": origin,
            "command": execution.command,
            "command_sha256": _sha(_canonical(execution.command)),
            "execution": result,
            "response": response,
            "blockers": blockers,
            "status": "HELD" if blockers else "OBSERVED_HOST_BOOT",
            "host_key_sha256": host,
            "boot_key_sha256": boot,
            "limitations": list(LIMITATIONS),
            "physical_authority": False,
            "hardware_qualified": False,
            "device_io_performed": False,
        }
        evidence = HostBootObservation(_canonical(value))
        self.evidence = evidence
        return evidence


def compare_boot_observations(
    before: HostBootObservation, after: HostBootObservation
) -> dict[str, Any]:
    _require(
        type(before) is HostBootObservation and type(after) is HostBootObservation,
        "EXACT_OBSERVATIONS_REQUIRED",
    )
    a, b = before.to_dict(), after.to_dict()
    reasons = []
    if before.sha256 == after.sha256:
        reasons.append("OBSERVATION_REUSED")
    if a["status"] != "OBSERVED_HOST_BOOT" or b["status"] != "OBSERVED_HOST_BOOT":
        reasons.append("BOOT_OBSERVATION_HELD")
    if any(
        a["request"][key] != b["request"][key]
        for key in ("source_sha256", "session_id", "trial_id")
    ):
        reasons.append("ORIGINAL_CONTEXT_MISMATCH")
    if a["origin"] != b["origin"]:
        reasons.append("OBSERVATION_ORIGIN_MISMATCH")
    if a["host_key_sha256"] != b["host_key_sha256"]:
        reasons.append("HOST_IDENTITY_CHANGED")
    if a["execution"]["finished_utc_ns"] > b["execution"]["started_utc_ns"]:
        reasons.append("OBSERVATION_CHRONOLOGY_INCONSISTENT")
    same = a["boot_key_sha256"] == b["boot_key_sha256"]
    if not same and a["response"] and b["response"]:
        new_boot = _utc_ns(b["response"]["last_boot_up_time_utc"])
        if new_boot <= a["execution"]["finished_utc_ns"]:
            reasons.append("RESTART_NOT_AFTER_PREVIOUS_OBSERVATION")
    return {
        "schema": "rocell.host_boot_comparison.v1",
        "before_sha256": before.sha256,
        "after_sha256": after.sha256,
        "status": (
            "HELD"
            if reasons
            else "SAME_HOST_SAME_BOOT" if same else "SAME_HOST_DIFFERENT_BOOT"
        ),
        "blockers": reasons,
        "physical_authority": False,
        "hardware_qualified": False,
        "cryptographic_attestation": False,
        "device_io_performed": False,
        "limitations": list(LIMITATIONS),
    }
