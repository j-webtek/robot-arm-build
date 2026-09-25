"""Ordered, process-owned leases for physical-onboarding coordination.

The effectful Windows path holds exclusive one-byte ``LockFileEx`` locks and
publishes separately flushed owner metadata.  A lock that becomes available
while its last metadata still says ``ACTIVE`` is stale and requires explicit
reconciliation; this module never steals or clears it based on a PID check.

No device/provider module is imported here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
import ctypes
from ctypes import wintypes
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import time
from typing import Any, BinaryIO, Callable, Iterable, Mapping, Sequence

from rocell.application.physical_onboarding_durability import (
    DurabilityQualificationReport,
    PhysicalOnboardingDurabilityError,
    PublicationMode,
    canonical_bytes,
    canonical_sha256,
    contained_path,
    publish_canonical_json,
    read_bounded_regular_file,
    require_effect_durability,
    safe_root,
)


LEASE_OWNER_SCHEMA = "rocell.physical_onboarding_lease_owner.v1"
LEASE_RECONCILIATION_RECEIPT_SCHEMA = (
    "rocell.physical_onboarding_lease_reconciliation_receipt.v1"
)
LEASE_ORDER = ("CELL", "SESSION", "CAMERA", "ARM_CONTROLLER")
MAX_OWNER_BYTES = 64 * 1024
MAX_RECONCILIATION_RECEIPT_BYTES = 64 * 1024

_RECONCILIATION_RECEIPT_FIELDS = frozenset(
    {
        "schema",
        "lease_level",
        "resource_id",
        "resource_sha256",
        "source_binding_sha256",
        "active_owner_sha256",
        "abandoned_owner_sha256",
        "reviewed_reconciliation_sha256",
        "reconciled_at_ns",
        "receipt_sha256",
    }
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_NONCE = re.compile(r"[0-9a-f]{32,128}\Z")
_OPERATION = re.compile(r"[A-Z][A-Z0-9_]{0,95}\Z")
_ZERO_SHA256 = "0" * 64

ChallengeCallback = Callable[[], str]


class PhysicalOnboardingLeaseError(RuntimeError):
    """A lease request, owner record, or lock lifecycle failed."""


class LeaseBusyError(PhysicalOnboardingLeaseError):
    """Another process currently owns the requested OS lease."""


class StaleLeaseOwnerError(PhysicalOnboardingLeaseError):
    """The OS lock is free but an unclean ACTIVE owner record remains."""


class LeaseOrderError(PhysicalOnboardingLeaseError):
    """A lease request violates the canonical global acquisition order."""


class LeaseChallengeError(PhysicalOnboardingLeaseError):
    """The complete state challenge changed while leases were acquired."""


class LeaseReconciliationError(PhysicalOnboardingLeaseError):
    """A reviewed stale-owner reconciliation could not be proven exactly."""


class LeaseLevel(IntEnum):
    CELL = 0
    SESSION = 1
    CAMERA = 2
    ARM_CONTROLLER = 3


class LeaseOwnerState(str, Enum):
    ACTIVE = "ACTIVE"
    ABANDONED = "ABANDONED"
    RELEASED = "RELEASED"


class PriorOwnerProcessState(str, Enum):
    SAME_PROCESS_START = "SAME_PROCESS_START"
    PID_REUSED = "PID_REUSED"
    ABSENT_OR_INACCESSIBLE = "ABSENT_OR_INACCESSIBLE"


class _LockResult(str, Enum):
    ACQUIRED = "ACQUIRED"
    BUSY = "BUSY"


class _OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PhysicalOnboardingLeaseError(f"{label} must be a lowercase SHA-256")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise PhysicalOnboardingLeaseError(f"{label} is not a bounded identifier")
    if value.split(".", 1)[0].upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }:
        raise PhysicalOnboardingLeaseError(f"{label} is a reserved Windows name")
    return value


def _positive_integer(value: object, label: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
        or value > 2**63 - 1
    ):
        raise PhysicalOnboardingLeaseError(
            f"{label} must be a bounded positive integer"
        )
    return value


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PhysicalOnboardingLeaseError(f"duplicate owner field {key!r}")
        result[key] = value
    return result


def _read_owner(path: Path) -> "LeaseOwnerMetadata | None":
    if not os.path.lexists(path):
        return None
    try:
        payload = read_bounded_regular_file(
            path,
            maximum_bytes=MAX_OWNER_BYTES,
            label="lease owner metadata",
        )
    except PhysicalOnboardingDurabilityError as exc:
        raise PhysicalOnboardingLeaseError(str(exc)) from exc
    try:
        document = json.loads(
            payload.decode("ascii"),
            object_pairs_hook=_strict_object,
            parse_float=lambda value: (_ for _ in ()).throw(
                PhysicalOnboardingLeaseError("owner metadata contains a float")
            ),
            parse_constant=lambda value: (_ for _ in ()).throw(
                PhysicalOnboardingLeaseError(
                    "owner metadata contains a nonfinite value"
                )
            ),
        )
    except PhysicalOnboardingLeaseError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PhysicalOnboardingLeaseError(
            "lease owner metadata is not strict JSON"
        ) from exc
    if (
        not isinstance(document, dict)
        or canonical_bytes(document, maximum_bytes=MAX_OWNER_BYTES) != payload
    ):
        raise PhysicalOnboardingLeaseError("lease owner metadata is not canonical JSON")
    return LeaseOwnerMetadata.from_dict(document)


def _kernel32() -> Any:
    if os.name != "nt":
        raise PhysicalOnboardingLeaseError("Win32 lease API is unavailable")
    return ctypes.WinDLL("kernel32", use_last_error=True)


def _win_error(operation: str) -> PhysicalOnboardingLeaseError:
    return PhysicalOnboardingLeaseError(
        f"{operation} failed with Win32 error {ctypes.get_last_error()}"
    )


def _windows_process_start_identity(pid: int) -> str | None:
    kernel32 = _kernel32()
    current_pid = os.getpid()
    close_required = pid != current_pid
    if close_required:
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        handle = open_process(0x1000, False, pid)
        if not handle:
            return None
    else:
        get_current = kernel32.GetCurrentProcess
        get_current.argtypes = []
        get_current.restype = wintypes.HANDLE
        handle = get_current()
    try:
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        get_times = kernel32.GetProcessTimes
        get_times.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        get_times.restype = wintypes.BOOL
        if not get_times(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        ):
            return None
        value = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
        return f"windows-filetime-{value:016x}"
    finally:
        if close_required:
            close = kernel32.CloseHandle
            close.argtypes = [wintypes.HANDLE]
            close.restype = wintypes.BOOL
            close(handle)


_PORTABLE_PROCESS_START = f"portable-launch-{time.monotonic_ns():016x}"


def process_start_identity(pid: int | None = None) -> str | None:
    selected_pid = os.getpid() if pid is None else pid
    if (
        isinstance(selected_pid, bool)
        or not isinstance(selected_pid, int)
        or selected_pid <= 0
    ):
        raise PhysicalOnboardingLeaseError("pid must be a positive integer")
    if os.name == "nt":
        return _windows_process_start_identity(selected_pid)
    proc_stat = Path(f"/proc/{selected_pid}/stat")
    try:
        raw = proc_stat.read_text(encoding="ascii")
        tail = raw[raw.rfind(")") + 2 :].split()
        start_ticks = tail[19]
        boot_id = (
            Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
        )
        return f"proc-{boot_id}-{start_ticks}"
    except (OSError, IndexError, UnicodeError):
        return _PORTABLE_PROCESS_START if selected_pid == os.getpid() else None


def classify_prior_owner_process(owner: "LeaseOwnerMetadata") -> PriorOwnerProcessState:
    observed = process_start_identity(owner.pid)
    if observed is None:
        return PriorOwnerProcessState.ABSENT_OR_INACCESSIBLE
    if observed == owner.process_start_identity:
        return PriorOwnerProcessState.SAME_PROCESS_START
    return PriorOwnerProcessState.PID_REUSED


@dataclass(frozen=True, slots=True)
class LeaseSpec:
    level: LeaseLevel
    resource_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.level, LeaseLevel):
            raise TypeError("lease level must be LeaseLevel")
        _identifier(self.resource_id, "lease resource_id")

    @property
    def resource_sha256(self) -> str:
        return hashlib.sha256(
            f"{self.level.name}:{self.resource_id}".encode("ascii")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class LeaseOwnerMetadata:
    level: LeaseLevel
    resource_id: str
    resource_sha256: str
    source_binding_sha256: str
    pid: int
    process_start_identity: str
    launch_nonce: str
    operation: str
    acquired_at_ns: int
    state: LeaseOwnerState
    released_at_ns: int | None
    previous_owner_sha256: str | None
    owner_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.level, LeaseLevel):
            raise PhysicalOnboardingLeaseError("owner level is invalid")
        spec = LeaseSpec(self.level, self.resource_id)
        if self.resource_sha256 != spec.resource_sha256:
            raise PhysicalOnboardingLeaseError("owner resource hash mismatch")
        _digest(self.source_binding_sha256, "owner source binding")
        _positive_integer(self.pid, "owner pid")
        if (
            not isinstance(self.process_start_identity, str)
            or not self.process_start_identity
            or len(self.process_start_identity) > 192
        ):
            raise PhysicalOnboardingLeaseError(
                "owner process-start identity is invalid"
            )
        if (
            not isinstance(self.launch_nonce, str)
            or _NONCE.fullmatch(self.launch_nonce) is None
        ):
            raise PhysicalOnboardingLeaseError("owner launch nonce is invalid")
        if (
            not isinstance(self.operation, str)
            or _OPERATION.fullmatch(self.operation) is None
        ):
            raise PhysicalOnboardingLeaseError("owner operation is invalid")
        _positive_integer(self.acquired_at_ns, "owner acquired_at_ns")
        if not isinstance(self.state, LeaseOwnerState):
            raise PhysicalOnboardingLeaseError("owner state is invalid")
        if self.state in {LeaseOwnerState.ACTIVE, LeaseOwnerState.ABANDONED}:
            if self.released_at_ns is not None:
                raise PhysicalOnboardingLeaseError(
                    f"{self.state.value.lower()} owner has a release time"
                )
        else:
            released = _positive_integer(self.released_at_ns, "owner released_at_ns")
            if released < self.acquired_at_ns:
                raise PhysicalOnboardingLeaseError("owner release precedes acquisition")
        if self.previous_owner_sha256 is not None:
            _digest(self.previous_owner_sha256, "previous owner hash")
        if (
            self.state is LeaseOwnerState.ABANDONED
            and self.previous_owner_sha256 is None
        ):
            raise PhysicalOnboardingLeaseError(
                "abandoned owner must identify its exact active predecessor"
            )
        _digest(self.owner_sha256, "owner hash")
        if self.owner_sha256 != canonical_sha256(self.core_dict()):
            raise PhysicalOnboardingLeaseError("owner metadata hash mismatch")

    def core_dict(self) -> dict[str, object]:
        return {
            "acquired_at_ns": self.acquired_at_ns,
            "launch_nonce": self.launch_nonce,
            "lease_level": self.level.name,
            "operation": self.operation,
            "pid": self.pid,
            "previous_owner_sha256": self.previous_owner_sha256,
            "process_start_identity": self.process_start_identity,
            "released_at_ns": self.released_at_ns,
            "resource_id": self.resource_id,
            "resource_sha256": self.resource_sha256,
            "schema": LEASE_OWNER_SCHEMA,
            "source_binding_sha256": self.source_binding_sha256,
            "state": self.state.value,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self.core_dict(), "owner_sha256": self.owner_sha256}

    @classmethod
    def build_active(
        cls,
        spec: LeaseSpec,
        *,
        source_binding_sha256: str,
        launch_nonce: str,
        operation: str,
        acquired_at_ns: int,
        previous_owner_sha256: str | None,
    ) -> "LeaseOwnerMetadata":
        identity = process_start_identity()
        if identity is None:
            raise PhysicalOnboardingLeaseError(
                "current process-start identity is unavailable"
            )
        core: dict[str, object] = {
            "acquired_at_ns": acquired_at_ns,
            "launch_nonce": launch_nonce,
            "lease_level": spec.level.name,
            "operation": operation,
            "pid": os.getpid(),
            "previous_owner_sha256": previous_owner_sha256,
            "process_start_identity": identity,
            "released_at_ns": None,
            "resource_id": spec.resource_id,
            "resource_sha256": spec.resource_sha256,
            "schema": LEASE_OWNER_SCHEMA,
            "source_binding_sha256": source_binding_sha256,
            "state": LeaseOwnerState.ACTIVE.value,
        }
        return cls(
            level=spec.level,
            resource_id=spec.resource_id,
            resource_sha256=spec.resource_sha256,
            source_binding_sha256=source_binding_sha256,
            pid=os.getpid(),
            process_start_identity=identity,
            launch_nonce=launch_nonce,
            operation=operation,
            acquired_at_ns=acquired_at_ns,
            state=LeaseOwnerState.ACTIVE,
            released_at_ns=None,
            previous_owner_sha256=previous_owner_sha256,
            owner_sha256=canonical_sha256(core),
        )

    def released(self, *, released_at_ns: int) -> "LeaseOwnerMetadata":
        if self.state is not LeaseOwnerState.ACTIVE:
            raise PhysicalOnboardingLeaseError("only an active owner can be released")
        released = _positive_integer(released_at_ns, "released_at_ns")
        core = self.core_dict()
        core["state"] = LeaseOwnerState.RELEASED.value
        core["released_at_ns"] = released
        # Bind the clean-release tombstone to the exact ACTIVE owner it closes.
        core["previous_owner_sha256"] = self.owner_sha256
        return LeaseOwnerMetadata(
            level=self.level,
            resource_id=self.resource_id,
            resource_sha256=self.resource_sha256,
            source_binding_sha256=self.source_binding_sha256,
            pid=self.pid,
            process_start_identity=self.process_start_identity,
            launch_nonce=self.launch_nonce,
            operation=self.operation,
            acquired_at_ns=self.acquired_at_ns,
            state=LeaseOwnerState.RELEASED,
            released_at_ns=released,
            previous_owner_sha256=self.owner_sha256,
            owner_sha256=canonical_sha256(core),
        )

    def abandoned(self) -> "LeaseOwnerMetadata":
        if self.state is not LeaseOwnerState.ACTIVE:
            raise PhysicalOnboardingLeaseError("only an active owner can be abandoned")
        core = self.core_dict()
        core["state"] = LeaseOwnerState.ABANDONED.value
        core["released_at_ns"] = None
        core["previous_owner_sha256"] = self.owner_sha256
        return LeaseOwnerMetadata(
            level=self.level,
            resource_id=self.resource_id,
            resource_sha256=self.resource_sha256,
            source_binding_sha256=self.source_binding_sha256,
            pid=self.pid,
            process_start_identity=self.process_start_identity,
            launch_nonce=self.launch_nonce,
            operation=self.operation,
            acquired_at_ns=self.acquired_at_ns,
            state=LeaseOwnerState.ABANDONED,
            released_at_ns=None,
            previous_owner_sha256=self.owner_sha256,
            owner_sha256=canonical_sha256(core),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LeaseOwnerMetadata":
        fields = {
            "schema",
            "lease_level",
            "resource_id",
            "resource_sha256",
            "source_binding_sha256",
            "pid",
            "process_start_identity",
            "launch_nonce",
            "operation",
            "acquired_at_ns",
            "state",
            "released_at_ns",
            "previous_owner_sha256",
            "owner_sha256",
        }
        if set(value) != fields or value.get("schema") != LEASE_OWNER_SCHEMA:
            raise PhysicalOnboardingLeaseError("owner metadata fields or schema differ")
        try:
            level = LeaseLevel[str(value["lease_level"])]
            state = LeaseOwnerState(value["state"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PhysicalOnboardingLeaseError(
                "owner level or state is invalid"
            ) from exc
        return cls(
            level=level,
            resource_id=value["resource_id"],
            resource_sha256=value["resource_sha256"],
            source_binding_sha256=value["source_binding_sha256"],
            pid=value["pid"],
            process_start_identity=value["process_start_identity"],
            launch_nonce=value["launch_nonce"],
            operation=value["operation"],
            acquired_at_ns=value["acquired_at_ns"],
            state=state,
            released_at_ns=value["released_at_ns"],
            previous_owner_sha256=value["previous_owner_sha256"],
            owner_sha256=value["owner_sha256"],
        )


def _reconciliation_receipt_document(
    spec: LeaseSpec,
    *,
    source_binding_sha256: str,
    active_owner_sha256: str,
    abandoned_owner_sha256: str,
    reviewed_reconciliation_sha256: str,
    reconciled_at_ns: int,
) -> dict[str, object]:
    core: dict[str, object] = {
        "abandoned_owner_sha256": abandoned_owner_sha256,
        "active_owner_sha256": active_owner_sha256,
        "lease_level": spec.level.name,
        "reconciled_at_ns": reconciled_at_ns,
        "resource_id": spec.resource_id,
        "resource_sha256": spec.resource_sha256,
        "reviewed_reconciliation_sha256": reviewed_reconciliation_sha256,
        "schema": LEASE_RECONCILIATION_RECEIPT_SCHEMA,
        "source_binding_sha256": source_binding_sha256,
    }
    return {**core, "receipt_sha256": canonical_sha256(core)}


def _require_exact_reconciliation_receipt(
    path: Path, expected: Mapping[str, object]
) -> None:
    try:
        observed = read_bounded_regular_file(
            path,
            maximum_bytes=MAX_RECONCILIATION_RECEIPT_BYTES,
            label="lease reconciliation receipt",
        )
    except PhysicalOnboardingDurabilityError as exc:
        raise LeaseReconciliationError(str(exc)) from exc
    expected_bytes = canonical_bytes(
        expected, maximum_bytes=MAX_RECONCILIATION_RECEIPT_BYTES
    )
    if observed != expected_bytes:
        raise LeaseReconciliationError(
            "existing lease reconciliation receipt differs from exact review"
        )


def _load_reconciliation_receipt(path: Path) -> dict[str, Any]:
    """Strictly load and self-verify one immutable reconciliation receipt."""

    try:
        payload = read_bounded_regular_file(
            path,
            maximum_bytes=MAX_RECONCILIATION_RECEIPT_BYTES,
            label="lease reconciliation receipt",
        )
    except PhysicalOnboardingDurabilityError as exc:
        raise LeaseReconciliationError(str(exc)) from exc
    try:
        document = json.loads(
            payload.decode("ascii"),
            object_pairs_hook=_strict_object,
            parse_float=lambda value: (_ for _ in ()).throw(
                LeaseReconciliationError(
                    "lease reconciliation receipt contains a float"
                )
            ),
            parse_constant=lambda value: (_ for _ in ()).throw(
                LeaseReconciliationError(
                    "lease reconciliation receipt contains a nonfinite value"
                )
            ),
        )
    except LeaseReconciliationError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise LeaseReconciliationError(
            "lease reconciliation receipt is not strict JSON"
        ) from exc
    if (
        not isinstance(document, dict)
        or set(document) != _RECONCILIATION_RECEIPT_FIELDS
        or document.get("schema") != LEASE_RECONCILIATION_RECEIPT_SCHEMA
        or canonical_bytes(document, maximum_bytes=MAX_RECONCILIATION_RECEIPT_BYTES)
        != payload
    ):
        raise LeaseReconciliationError(
            "lease reconciliation receipt fields or encoding differ"
        )
    _identifier(document["resource_id"], "receipt resource_id")
    for field in (
        "resource_sha256",
        "source_binding_sha256",
        "active_owner_sha256",
        "abandoned_owner_sha256",
        "reviewed_reconciliation_sha256",
        "receipt_sha256",
    ):
        _digest(document[field], f"receipt {field}")
    if document["reviewed_reconciliation_sha256"] == _ZERO_SHA256:
        raise LeaseReconciliationError(
            "receipt reviewed reconciliation hash must be nonzero"
        )
    _positive_integer(document["reconciled_at_ns"], "receipt reconciled_at_ns")
    unsigned = dict(document)
    stored = unsigned.pop("receipt_sha256")
    if canonical_sha256(unsigned) != stored:
        raise LeaseReconciliationError("lease reconciliation receipt hash mismatch")
    return document


class _WindowsRangeLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: Any = None
        self.overlapped = _OVERLAPPED()

    def open_and_try_acquire(self) -> _LockResult:
        kernel32 = _kernel32()
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        self.handle = create_file(
            str(self.path),
            0x80000000 | 0x40000000,
            0x1 | 0x2,
            None,
            4,
            0x80 | 0x80000000 | 0x00200000,
            None,
        )
        if self.handle == wintypes.HANDLE(-1).value:
            self.handle = None
            raise _win_error("CreateFileW(lease)")
        lock = kernel32.LockFileEx
        lock.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(_OVERLAPPED),
        ]
        lock.restype = wintypes.BOOL
        if lock(
            self.handle,
            0x2 | 0x1,
            0,
            1,
            0,
            ctypes.byref(self.overlapped),
        ):
            return _LockResult.ACQUIRED
        error = ctypes.get_last_error()
        if error in {32, 33}:
            self.close_without_unlock()
            return _LockResult.BUSY
        self.close_without_unlock()
        raise PhysicalOnboardingLeaseError(
            f"LockFileEx failed with Win32 error {error}"
        )

    def release(self) -> None:
        if self.handle is None:
            return
        kernel32 = _kernel32()
        unlock = kernel32.UnlockFileEx
        unlock.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(_OVERLAPPED),
        ]
        unlock.restype = wintypes.BOOL
        failure: PhysicalOnboardingLeaseError | None = None
        if not unlock(self.handle, 0, 1, 0, ctypes.byref(self.overlapped)):
            failure = _win_error("UnlockFileEx")
        self.close_without_unlock()
        if failure is not None:
            raise failure

    def close_without_unlock(self) -> None:
        if self.handle is None:
            return
        kernel32 = _kernel32()
        close = kernel32.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        close(self.handle)
        self.handle = None


class _PortableRangeLock:
    """Inspection/test fallback; never qualifies physical effects."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.stream: BinaryIO | None = None

    def open_and_try_acquire(self) -> _LockResult:
        fcntl: Any = importlib.import_module("fcntl")

        self.stream = self.path.open("a+b")
        try:
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.stream.close()
            self.stream = None
            return _LockResult.BUSY
        return _LockResult.ACQUIRED

    def release(self) -> None:
        if self.stream is None:
            return
        fcntl: Any = importlib.import_module("fcntl")

        try:
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        finally:
            self.stream.close()
            self.stream = None

    def close_without_unlock(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None


RangeLock = _WindowsRangeLock | _PortableRangeLock


def _range_lock(path: Path) -> RangeLock:
    return _WindowsRangeLock(path) if os.name == "nt" else _PortableRangeLock(path)


def windows_lockfileex_self_test(directory: Path) -> bool:
    """Prove same-file nonblocking exclusion and unlock on the actual volume."""

    if os.name != "nt":
        return False
    root = safe_root(directory, label="lease self-test root")
    path = contained_path(
        root, f".lockfileex-self-test-{secrets.token_hex(12)}.lock", label="lease probe"
    )
    first = _WindowsRangeLock(path)
    second = _WindowsRangeLock(path)
    try:
        if first.open_and_try_acquire() is not _LockResult.ACQUIRED:
            return False
        if second.open_and_try_acquire() is not _LockResult.BUSY:
            return False
        first.release()
        if second.open_and_try_acquire() is not _LockResult.ACQUIRED:
            return False
        second.release()
        return True
    finally:
        first.close_without_unlock()
        second.close_without_unlock()
        try:
            if path.is_file() and not path.is_symlink():
                path.unlink()
        except OSError:
            return False


@dataclass(slots=True)
class _HeldLease:
    lock: RangeLock
    owner_path: Path
    owner: LeaseOwnerMetadata


@dataclass(slots=True)
class HeldLeaseSet:
    """A reverse-released set of leases; not serializable or transferable."""

    _leases: list[_HeldLease]
    expected_challenge_sha256: str
    _closed: bool = False

    @property
    def owners(self) -> tuple[LeaseOwnerMetadata, ...]:
        return tuple(item.owner for item in self._leases)

    @property
    def closed(self) -> bool:
        return self._closed

    def recheck_challenge(self, callback: ChallengeCallback) -> None:
        if self._closed:
            raise PhysicalOnboardingLeaseError("lease set is already closed")
        observed = callback()
        if observed != self.expected_challenge_sha256:
            raise LeaseChallengeError("state challenge changed while leases were held")
        for held in self._leases:
            if _read_owner(held.owner_path) != held.owner:
                raise PhysicalOnboardingLeaseError(
                    "active lease owner metadata drifted"
                )

    def close(self, *, released_at_ns: int | None = None) -> None:
        if self._closed:
            return
        observed_release = time.time_ns() if released_at_ns is None else released_at_ns
        _positive_integer(observed_release, "released_at_ns")
        first_error: BaseException | None = None
        for index, held in enumerate(reversed(self._leases)):
            try:
                current = _read_owner(held.owner_path)
                if current != held.owner:
                    raise PhysicalOnboardingLeaseError(
                        "cannot cleanly release lease with changed owner metadata"
                    )
                released = held.owner.released(released_at_ns=observed_release + index)
                publish_canonical_json(
                    held.owner_path.parent,
                    held.owner_path.name,
                    released.to_dict(),
                    mode=PublicationMode.REPLACE,
                    maximum_bytes=MAX_OWNER_BYTES,
                )
            except BaseException as exc:
                if first_error is None:
                    first_error = exc
            finally:
                try:
                    held.lock.release()
                except BaseException as exc:
                    if first_error is None:
                        first_error = exc
        self._closed = True
        if first_error is not None:
            raise PhysicalOnboardingLeaseError(
                "lease set did not release cleanly"
            ) from first_error

    def __enter__(self) -> "HeldLeaseSet":
        if self._closed:
            raise PhysicalOnboardingLeaseError("lease set is already closed")
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


@dataclass(frozen=True, slots=True)
class OnboardingLeaseManager:
    coordination_root: Path
    source_binding_sha256: str
    launch_nonce: str
    durability_report: DurabilityQualificationReport | None = None

    def __post_init__(self) -> None:
        root = safe_root(self.coordination_root, label="lease coordination root")
        object.__setattr__(self, "coordination_root", root)
        _digest(self.source_binding_sha256, "lease source binding")
        if (
            not isinstance(self.launch_nonce, str)
            or _NONCE.fullmatch(self.launch_nonce) is None
        ):
            raise PhysicalOnboardingLeaseError(
                "launch_nonce must be 32..128 lowercase hex"
            )

    @staticmethod
    def new_launch_nonce() -> str:
        return secrets.token_hex(32)

    def _paths(self, spec: LeaseSpec) -> tuple[Path, Path]:
        stem = f"lease-{spec.level.value:02d}-{spec.resource_sha256}"
        lock_path = contained_path(
            self.coordination_root, f"{stem}.lock", label="lease lock path"
        )
        owner_path = contained_path(
            self.coordination_root, f"{stem}.owner.json", label="lease owner path"
        )
        return lock_path, owner_path

    def _reconciliation_receipt_path(
        self, spec: LeaseSpec, active_owner_sha256: str
    ) -> Path:
        stem = f"lease-{spec.level.value:02d}-{spec.resource_sha256}"
        return contained_path(
            self.coordination_root,
            f"{stem}.reconciliation-{active_owner_sha256}.receipt.json",
            label="lease reconciliation receipt path",
        )

    def prior_owner(self, spec: LeaseSpec) -> LeaseOwnerMetadata | None:
        _, owner_path = self._paths(spec)
        owner = _read_owner(owner_path)
        if owner is None:
            return None
        self._require_prior_owner_binding(spec, owner)
        if owner.state is LeaseOwnerState.ABANDONED:
            self._require_abandoned_receipt(spec, owner)
        return owner

    def _require_prior_owner_binding(
        self, spec: LeaseSpec, owner: LeaseOwnerMetadata
    ) -> None:
        if (
            owner.level is not spec.level
            or owner.resource_id != spec.resource_id
            or owner.resource_sha256 != spec.resource_sha256
        ):
            raise PhysicalOnboardingLeaseError(
                "prior lease owner does not match the exact resource"
            )
        if owner.source_binding_sha256 != self.source_binding_sha256:
            raise PhysicalOnboardingLeaseError(
                "prior lease owner source binding differs"
            )

    def _require_abandoned_receipt(
        self, spec: LeaseSpec, owner: LeaseOwnerMetadata
    ) -> None:
        active_hash = owner.previous_owner_sha256
        if active_hash is None:
            raise LeaseReconciliationError("abandoned owner has no active predecessor")
        receipt = _load_reconciliation_receipt(
            self._reconciliation_receipt_path(spec, active_hash)
        )
        if (
            receipt["lease_level"] != spec.level.name
            or receipt["resource_id"] != spec.resource_id
            or receipt["resource_sha256"] != spec.resource_sha256
            or receipt["source_binding_sha256"] != self.source_binding_sha256
            or receipt["active_owner_sha256"] != active_hash
            or receipt["abandoned_owner_sha256"] != owner.owner_sha256
        ):
            raise LeaseReconciliationError(
                "abandoned lease owner lacks its exact reconciliation receipt"
            )

    def reconcile_stale_owner(
        self,
        spec: LeaseSpec,
        *,
        expected_active_owner_sha256: str,
        reviewed_reconciliation_sha256: str,
        reconciled_at_ns: int,
    ) -> LeaseOwnerMetadata:
        """Mark one exactly reviewed stale ACTIVE owner as ABANDONED.

        This is an explicit evidence-only recovery operation.  Process identity
        is never authority to reconcile, and no hardware provider is involved.
        """

        if not isinstance(spec, LeaseSpec):
            raise TypeError("spec must be LeaseSpec")
        expected_active = _digest(
            expected_active_owner_sha256, "expected active owner hash"
        )
        reviewed = _digest(
            reviewed_reconciliation_sha256, "reviewed reconciliation hash"
        )
        if reviewed == _ZERO_SHA256:
            raise LeaseReconciliationError(
                "reviewed reconciliation hash must be nonzero"
            )
        reconciled = _positive_integer(reconciled_at_ns, "reconciled_at_ns")
        lock_path, owner_path = self._paths(spec)
        receipt_path = self._reconciliation_receipt_path(spec, expected_active)
        lock = _range_lock(lock_path)
        try:
            if lock.open_and_try_acquire() is _LockResult.BUSY:
                raise LeaseBusyError(
                    f"lease {spec.level.name}:{spec.resource_id} is busy"
                )
            verified_lock_path, verified_owner_path = self._paths(spec)
            verified_receipt_path = self._reconciliation_receipt_path(
                spec, expected_active
            )
            if (
                verified_lock_path != lock_path
                or verified_owner_path != owner_path
                or verified_receipt_path != receipt_path
            ):
                raise LeaseReconciliationError(
                    "lease reconciliation path changed after lock acquisition"
                )

            owner = _read_owner(owner_path)
            if owner is None:
                raise LeaseReconciliationError(
                    "lease reconciliation requires existing owner metadata"
                )
            if (
                owner.level is not spec.level
                or owner.resource_id != spec.resource_id
                or owner.resource_sha256 != spec.resource_sha256
            ):
                raise LeaseReconciliationError(
                    "lease reconciliation owner does not match exact resource"
                )
            if owner.source_binding_sha256 != self.source_binding_sha256:
                raise LeaseReconciliationError(
                    "lease reconciliation owner source binding differs"
                )
            if reconciled < owner.acquired_at_ns:
                raise LeaseReconciliationError(
                    "lease reconciliation timestamp precedes acquisition"
                )

            if owner.state is LeaseOwnerState.ACTIVE:
                if owner.owner_sha256 != expected_active:
                    raise LeaseReconciliationError(
                        "active lease owner hash differs from exact review"
                    )
                abandoned = owner.abandoned()
            elif owner.state is LeaseOwnerState.ABANDONED:
                if owner.previous_owner_sha256 != expected_active:
                    raise LeaseReconciliationError(
                        "abandoned lease owner differs from exact reviewed predecessor"
                    )
                abandoned = owner
            else:
                raise LeaseReconciliationError(
                    "lease reconciliation requires ACTIVE owner metadata"
                )

            receipt = _reconciliation_receipt_document(
                spec,
                source_binding_sha256=self.source_binding_sha256,
                active_owner_sha256=expected_active,
                abandoned_owner_sha256=abandoned.owner_sha256,
                reviewed_reconciliation_sha256=reviewed,
                reconciled_at_ns=reconciled,
            )
            receipt_exists = os.path.lexists(receipt_path)
            if owner.state is LeaseOwnerState.ABANDONED and not receipt_exists:
                raise LeaseReconciliationError(
                    "abandoned owner is missing its prior immutable receipt"
                )
            if receipt_exists:
                _require_exact_reconciliation_receipt(receipt_path, receipt)
            else:
                try:
                    publish_canonical_json(
                        self.coordination_root,
                        receipt_path.name,
                        receipt,
                        mode=PublicationMode.IMMUTABLE,
                        maximum_bytes=MAX_RECONCILIATION_RECEIPT_BYTES,
                    )
                except PhysicalOnboardingDurabilityError as exc:
                    raise LeaseReconciliationError(
                        "immutable lease reconciliation receipt was not published"
                    ) from exc

            if owner.state is LeaseOwnerState.ACTIVE:
                if _read_owner(owner_path) != owner:
                    raise LeaseReconciliationError(
                        "active lease owner changed after receipt publication"
                    )
                try:
                    publish_canonical_json(
                        self.coordination_root,
                        owner_path.name,
                        abandoned.to_dict(),
                        mode=PublicationMode.REPLACE,
                        maximum_bytes=MAX_OWNER_BYTES,
                    )
                except PhysicalOnboardingDurabilityError as exc:
                    raise LeaseReconciliationError(
                        "abandoned lease owner metadata was not published"
                    ) from exc
                if _read_owner(owner_path) != abandoned:
                    raise LeaseReconciliationError(
                        "abandoned lease owner did not reload exactly"
                    )
            return abandoned
        finally:
            lock.close_without_unlock()

    def acquire(
        self,
        specs: Sequence[LeaseSpec],
        *,
        operation: str,
        expected_challenge_sha256: str,
        challenge_callback: ChallengeCallback,
        effectful: bool,
        acquired_at_ns: int | None = None,
    ) -> HeldLeaseSet:
        if isinstance(specs, (str, bytes)) or not specs:
            raise LeaseOrderError("at least one typed lease is required")
        requested = tuple(specs)
        if any(not isinstance(item, LeaseSpec) for item in requested):
            raise TypeError("specs must contain LeaseSpec values")
        ranks = tuple(int(item.level) for item in requested)
        if ranks != tuple(sorted(ranks)) or len(set(ranks)) != len(ranks):
            raise LeaseOrderError(
                "leases must be unique and ordered CELL -> SESSION -> CAMERA -> ARM_CONTROLLER"
            )
        if effectful and tuple(item.level for item in requested[:2]) != (
            LeaseLevel.CELL,
            LeaseLevel.SESSION,
        ):
            raise LeaseOrderError("effectful lease sets must begin CELL -> SESSION")
        if not isinstance(operation, str) or _OPERATION.fullmatch(operation) is None:
            raise PhysicalOnboardingLeaseError("operation is invalid")
        expected = _digest(expected_challenge_sha256, "expected challenge")
        if not callable(challenge_callback):
            raise TypeError("challenge_callback must be callable")
        if effectful:
            try:
                require_effect_durability(
                    self.durability_report,
                    root=self.coordination_root,
                    source_binding_sha256=self.source_binding_sha256,
                )
            except PhysicalOnboardingDurabilityError as exc:
                raise PhysicalOnboardingLeaseError(
                    "effectful lease acquisition requires current qualified durability"
                ) from exc
        acquired = _positive_integer(
            time.time_ns() if acquired_at_ns is None else acquired_at_ns,
            "acquired_at_ns",
        )
        held: list[_HeldLease] = []
        try:
            for index, spec in enumerate(requested):
                lock_path, owner_path = self._paths(spec)
                lock = _range_lock(lock_path)
                try:
                    result = lock.open_and_try_acquire()
                    if result is _LockResult.BUSY:
                        prior = _read_owner(owner_path)
                        detail = "owner metadata unavailable"
                        if prior is not None:
                            detail = (
                                f"pid={prior.pid} "
                                f"process={classify_prior_owner_process(prior).value}"
                            )
                        raise LeaseBusyError(
                            f"lease {spec.level.name}:{spec.resource_id} is busy ({detail})"
                        )
                    # Re-resolve every component after CreateFileW/LockFileEx so a
                    # newly created or concurrently substituted lock target cannot
                    # bypass the hardlink/reparse checks.
                    verified_lock_path, verified_owner_path = self._paths(spec)
                    if (
                        verified_lock_path != lock_path
                        or verified_owner_path != owner_path
                    ):
                        raise PhysicalOnboardingLeaseError(
                            "lease path changed during acquisition"
                        )
                    prior = self.prior_owner(spec)
                    if prior is not None and prior.state is LeaseOwnerState.ACTIVE:
                        # PID/process-start information is diagnostic only.  Never
                        # truncate, replace, or clear an ACTIVE record automatically.
                        process_state = classify_prior_owner_process(prior)
                        raise StaleLeaseOwnerError(
                            "stale ACTIVE lease owner requires reconciliation; "
                            f"pid-only takeover is forbidden ({process_state.value})"
                        )
                    owner = LeaseOwnerMetadata.build_active(
                        spec,
                        source_binding_sha256=self.source_binding_sha256,
                        launch_nonce=self.launch_nonce,
                        operation=operation,
                        acquired_at_ns=acquired + index,
                        previous_owner_sha256=(
                            None if prior is None else prior.owner_sha256
                        ),
                    )
                    publish_canonical_json(
                        self.coordination_root,
                        owner_path.name,
                        owner.to_dict(),
                        mode=(
                            PublicationMode.IMMUTABLE
                            if prior is None
                            else PublicationMode.REPLACE
                        ),
                        maximum_bytes=MAX_OWNER_BYTES,
                    )
                    held.append(_HeldLease(lock, owner_path, owner))
                finally:
                    if all(item.lock is not lock for item in held):
                        lock.close_without_unlock()
            lease_set = HeldLeaseSet(held, expected)
            try:
                lease_set.recheck_challenge(challenge_callback)
            except BaseException:
                lease_set.close(released_at_ns=acquired + len(held) + 1)
                raise
            return lease_set
        except BaseException:
            if held:
                cleanup = HeldLeaseSet(held, expected)
                try:
                    cleanup.close(released_at_ns=acquired + len(held) + 1)
                except PhysicalOnboardingLeaseError:
                    pass
            raise


__all__ = [
    "LEASE_ORDER",
    "LEASE_OWNER_SCHEMA",
    "LEASE_RECONCILIATION_RECEIPT_SCHEMA",
    "ChallengeCallback",
    "HeldLeaseSet",
    "LeaseBusyError",
    "LeaseChallengeError",
    "LeaseLevel",
    "LeaseOrderError",
    "LeaseOwnerMetadata",
    "LeaseOwnerState",
    "LeaseReconciliationError",
    "LeaseSpec",
    "OnboardingLeaseManager",
    "PhysicalOnboardingLeaseError",
    "PriorOwnerProcessState",
    "StaleLeaseOwnerError",
    "classify_prior_owner_process",
    "process_start_identity",
    "windows_lockfileex_self_test",
]
