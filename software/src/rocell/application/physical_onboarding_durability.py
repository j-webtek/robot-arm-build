"""Fail-closed publication primitives for physical-onboarding V2.

This module is deliberately independent of camera, serial, power, and motion
providers.  Its Windows path uses Win32 write-through handles,
``FlushFileBuffers`` and ``MoveFileExW``.  The portable path exists so the
formats can be inspected and tested elsewhere, but is never qualified for a
physical effect.

The committed-ledger primitive publishes an immutable record first and advances
an independently hashed head second.  A stop between those publications is a
detectable, uncommitted tail.  It is not silently deleted, adopted, or replayed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path, PurePath
import re
import secrets
import shutil
import stat
import time
from typing import Any, Callable, Iterable, Mapping, Sequence


MAX_PUBLICATION_BYTES = 4 * 1024 * 1024
MAX_QUALIFICATION_REPORT_BYTES = 64 * 1024
MAX_LEDGER_RECORDS = 16_384
MAX_LEDGER_RECORD_BYTES = 512 * 1024
ZERO_SHA256 = "0" * 64

DURABILITY_REPORT_SCHEMA = "rocell.physical_onboarding_durability_report.v1"
DURABLE_LEDGER_HEADER_SCHEMA = "rocell.physical_onboarding_durable_ledger_header.v1"
DURABLE_LEDGER_RECORD_SCHEMA = "rocell.physical_onboarding_durable_ledger_record.v1"
DURABLE_LEDGER_HEAD_SCHEMA = "rocell.physical_onboarding_durable_ledger_head.v1"
DURABILITY_ADAPTER_ID = "ROCELL-WINDOWS-NTFS-WRITETHROUGH-001"

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_RECORD_KIND = re.compile(r"[A-Z][A-Z0-9_]{0,95}\Z")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}

FaultInjector = Callable[[str], None]
LeaseProbe = Callable[[Path], bool]


class PhysicalOnboardingDurabilityError(RuntimeError):
    """A storage, integrity, qualification, or recovery boundary failed."""


class DurabilityQualificationError(PhysicalOnboardingDurabilityError):
    """The deployment volume is not qualified for possible physical effects."""


class PublicationMode(str, Enum):
    IMMUTABLE = "IMMUTABLE"
    REPLACE = "REPLACE"


class LedgerRecoveryState(str, Enum):
    CLEAN = "CLEAN"
    UNCOMMITTED_TAIL = "UNCOMMITTED_TAIL"


class DurabilityCheckpoint(str, Enum):
    BEFORE_TEMP_CREATE = "publication.before_temp_create"
    AFTER_TEMP_CREATE = "publication.after_temp_create"
    AFTER_TEMP_WRITE = "publication.after_temp_write"
    AFTER_TEMP_FLUSH = "publication.after_temp_flush"
    BEFORE_MOVE = "publication.before_move"
    AFTER_MOVE = "publication.after_move"
    AFTER_DESTINATION_FLUSH = "publication.after_destination_flush"
    LEDGER_AFTER_RECORD_PUBLISH = "ledger.after_record_publish_before_head"
    LEDGER_AFTER_HEAD_PUBLISH = "ledger.after_head_publish"
    SELF_TEST_BEFORE = "self_test.before"
    SELF_TEST_AFTER = "self_test.after"


def _checkpoint(
    injector: FaultInjector | None, checkpoint: str | DurabilityCheckpoint
) -> None:
    if injector is not None:
        injector(
            checkpoint.value
            if isinstance(checkpoint, DurabilityCheckpoint)
            else checkpoint
        )


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PhysicalOnboardingDurabilityError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise PhysicalOnboardingDurabilityError(f"{label} is not a bounded identifier")
    if value.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
        raise PhysicalOnboardingDurabilityError(f"{label} is a reserved Windows name")
    if value.endswith((".", " ")):
        raise PhysicalOnboardingDurabilityError(f"{label} has an unsafe suffix")
    return value


def _positive_integer(value: object, label: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
        or value > 2**63 - 1
    ):
        raise PhysicalOnboardingDurabilityError(
            f"{label} must be a bounded positive integer"
        )
    return value


def _validate_json_tree(value: object, *, depth: int = 0) -> None:
    if depth > 16:
        raise PhysicalOnboardingDurabilityError("canonical JSON exceeds nesting limit")
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        if value < -(2**63) or value > 2**63 - 1:
            raise PhysicalOnboardingDurabilityError(
                "canonical JSON integer is unbounded"
            )
        return
    if isinstance(value, list) or isinstance(value, tuple):
        if len(value) > 16_384:
            raise PhysicalOnboardingDurabilityError("canonical JSON array is oversized")
        for item in value:
            _validate_json_tree(item, depth=depth + 1)
        return
    if isinstance(value, Mapping):
        if len(value) > 16_384:
            raise PhysicalOnboardingDurabilityError(
                "canonical JSON object is oversized"
            )
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 256:
                raise PhysicalOnboardingDurabilityError(
                    "canonical JSON object has an invalid key"
                )
            _validate_json_tree(item, depth=depth + 1)
        return
    raise PhysicalOnboardingDurabilityError(
        f"canonical JSON contains unsupported value {type(value).__name__}"
    )


def canonical_bytes(
    value: object, *, maximum_bytes: int = MAX_PUBLICATION_BYTES
) -> bytes:
    _validate_json_tree(value)
    try:
        payload = (
            json.dumps(
                value,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise PhysicalOnboardingDurabilityError("value is not canonical JSON") from exc
    if len(payload) > maximum_bytes:
        raise PhysicalOnboardingDurabilityError("canonical JSON exceeds its byte limit")
    return payload


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PhysicalOnboardingDurabilityError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _parse_canonical_json(
    payload: bytes, *, maximum_bytes: int, label: str
) -> dict[str, Any]:
    if len(payload) > maximum_bytes:
        raise PhysicalOnboardingDurabilityError(f"{label} exceeds its byte limit")
    try:
        value = json.loads(
            payload.decode("ascii"),
            object_pairs_hook=_strict_object,
            parse_float=lambda value: (_ for _ in ()).throw(
                PhysicalOnboardingDurabilityError(f"{label} contains a float")
            ),
            parse_constant=lambda value: (_ for _ in ()).throw(
                PhysicalOnboardingDurabilityError(
                    f"{label} contains nonfinite constant {value!r}"
                )
            ),
        )
    except PhysicalOnboardingDurabilityError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PhysicalOnboardingDurabilityError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict):
        raise PhysicalOnboardingDurabilityError(f"{label} must contain an object")
    if canonical_bytes(value, maximum_bytes=maximum_bytes) != payload:
        raise PhysicalOnboardingDurabilityError(f"{label} is not canonical JSON")
    return value


def _win32() -> Any:
    if os.name != "nt":
        raise PhysicalOnboardingDurabilityError("Win32 durability API is unavailable")
    return ctypes.WinDLL("kernel32", use_last_error=True)


def _win_error(operation: str) -> PhysicalOnboardingDurabilityError:
    code = ctypes.get_last_error()
    return PhysicalOnboardingDurabilityError(
        f"{operation} failed with Win32 error {code}"
    )


class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


def _reject_unsafe_component(path: Path, label: str) -> None:
    # One non-following observation supplies existence, link mode, Windows
    # reparse attributes and link count together. This is never cached: every
    # caller and every ancestor in safe_root still receives a fresh lstat.
    # Qualified file reads also retain their independent opened-handle checks.
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        # Permission/IO errors are not evidence that a component is absent.
        raise PhysicalOnboardingDurabilityError(f"cannot inspect {label}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise PhysicalOnboardingDurabilityError(f"{label} traverses a symlink")
    attributes = getattr(metadata, "st_file_attributes", None)
    if os.name == "nt" and (
        type(attributes) is not int or not 0 <= attributes < 0xFFFFFFFF
    ):
        raise PhysicalOnboardingDurabilityError(
            f"cannot inspect Windows attributes for {label}"
        )
    if attributes is not None and attributes & 0x400:
        raise PhysicalOnboardingDurabilityError(f"{label} traverses a reparse point")
    if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink != 1:
        raise PhysicalOnboardingDurabilityError(f"{label} contains a hard-linked file")


def safe_root(path: Path, *, label: str = "durability root") -> Path:
    selected = Path(os.path.abspath(path))
    cursor = Path(selected.anchor)
    for part in selected.parts[1:]:
        cursor /= part
        _reject_unsafe_component(cursor, label)
    try:
        resolved = selected.resolve(strict=True)
    except OSError as exc:
        raise PhysicalOnboardingDurabilityError(f"{label} is unavailable") from exc
    if resolved != selected or not resolved.is_dir():
        raise PhysicalOnboardingDurabilityError(f"{label} is not a canonical directory")
    return resolved


def contained_path(root: Path, relative: Path | str, *, label: str) -> Path:
    selected_root = safe_root(root)
    relative_path = PurePath(relative)
    if (
        relative_path.is_absolute()
        or not relative_path.parts
        or any(part in {"", ".", ".."} for part in relative_path.parts)
    ):
        raise PhysicalOnboardingDurabilityError(f"{label} is not a safe relative path")
    candidate = selected_root.joinpath(*relative_path.parts)
    try:
        candidate.resolve(strict=False).relative_to(selected_root)
    except (OSError, ValueError) as exc:
        raise PhysicalOnboardingDurabilityError(f"{label} escapes its root") from exc
    cursor = selected_root
    for part in relative_path.parts:
        cursor /= part
        _reject_unsafe_component(cursor, label)
    return candidate


def _read_regular_file(path: Path, *, maximum_bytes: int, label: str) -> bytes:
    _reject_unsafe_component(path, label)
    if path.is_symlink() or not path.is_file():
        raise PhysicalOnboardingDurabilityError(f"{label} must be a regular file")
    if os.name == "nt":
        return _windows_read_regular_file(
            path, maximum_bytes=maximum_bytes, label=label
        )
    try:
        with path.open("rb") as stream:
            payload = stream.read(maximum_bytes + 1)
    except OSError as exc:
        raise PhysicalOnboardingDurabilityError(f"cannot read {label}") from exc
    if len(payload) > maximum_bytes:
        raise PhysicalOnboardingDurabilityError(f"{label} exceeds its byte limit")
    return payload


def read_bounded_regular_file(
    path: Path,
    *,
    maximum_bytes: int,
    label: str = "bounded regular file",
) -> bytes:
    """Read one regular file through the qualified, substitution-aware path.

    On Windows this opens the file with delete sharing so a concurrent atomic
    replacement is not wedged, then validates the opened handle itself for
    disk-file type, reparse state, link count, and size before reading.  The
    public wrapper keeps callers out of the module's Win32 implementation
    details while retaining an explicit byte bound.
    """

    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")
    if (
        isinstance(maximum_bytes, bool)
        or not isinstance(maximum_bytes, int)
        or maximum_bytes <= 0
    ):
        raise PhysicalOnboardingDurabilityError(
            "maximum_bytes must be a positive integer"
        )
    if not isinstance(label, str) or not label:
        raise PhysicalOnboardingDurabilityError("file label must be nonempty")
    return _read_regular_file(path, maximum_bytes=maximum_bytes, label=label)


def _windows_open_regular_read_handle(
    path: Path, *, maximum_bytes: int, label: str
) -> Any:
    """Open a validated disk file without blocking same-volume replacement."""

    kernel32 = _win32()
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
    handle = create_file(
        str(path),
        0x80000000,
        0x1 | 0x2 | 0x4,
        None,
        3,
        0x80 | 0x00200000,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise _win_error("CreateFileW(read regular file)")
    try:
        get_file_type = kernel32.GetFileType
        get_file_type.argtypes = [wintypes.HANDLE]
        get_file_type.restype = wintypes.DWORD
        if int(get_file_type(handle)) != 0x1:
            raise PhysicalOnboardingDurabilityError(
                f"{label} must be a regular disk file"
            )

        information = _BY_HANDLE_FILE_INFORMATION()
        get_information = kernel32.GetFileInformationByHandle
        get_information.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_BY_HANDLE_FILE_INFORMATION),
        ]
        get_information.restype = wintypes.BOOL
        if not get_information(handle, ctypes.byref(information)):
            raise _win_error("GetFileInformationByHandle(read regular file)")
        if int(information.dwFileAttributes) & (0x10 | 0x400):
            raise PhysicalOnboardingDurabilityError(
                f"{label} must not be a directory or reparse point"
            )
        if int(information.nNumberOfLinks) != 1:
            raise PhysicalOnboardingDurabilityError(f"{label} is hard-linked")
        observed_size = (int(information.nFileSizeHigh) << 32) | int(
            information.nFileSizeLow
        )
        if observed_size > maximum_bytes:
            raise PhysicalOnboardingDurabilityError(f"{label} exceeds its byte limit")
        return handle
    except BaseException:
        close = kernel32.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        close(handle)
        raise


def _windows_read_regular_file(path: Path, *, maximum_bytes: int, label: str) -> bytes:
    handle = _windows_open_regular_read_handle(
        path, maximum_bytes=maximum_bytes, label=label
    )
    kernel32 = _win32()
    try:
        read_file = kernel32.ReadFile
        read_file.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        read_file.restype = wintypes.BOOL
        payload = bytearray()
        # Most original manifests/records are small. Reuse one modest buffer,
        # including for the EOF read, and grow only after a full chunk. Large
        # frame payloads still reach the existing 1 MiB read ceiling quickly.
        # This changes allocation/copying only: the opened-handle checks and
        # actual-byte limit (including one overflow byte) remain independent.
        buffer_size = min(65_536, maximum_bytes + 1)
        buffer = ctypes.create_string_buffer(buffer_size)
        while len(payload) <= maximum_bytes:
            request_size = min(buffer_size, maximum_bytes + 1 - len(payload))
            read = wintypes.DWORD(0)
            if not read_file(handle, buffer, request_size, ctypes.byref(read), None):
                raise _win_error("ReadFile(read regular file)")
            if read.value == 0:
                break
            if read.value > request_size:
                raise PhysicalOnboardingDurabilityError(
                    "ReadFile made invalid progress"
                )
            # .raw copies the entire allocation before slicing. Copy only the
            # validated bytes returned by ReadFile, preserving embedded NULs.
            payload.extend(ctypes.string_at(buffer, read.value))
            remaining = maximum_bytes + 1 - len(payload)
            if read.value == request_size and buffer_size < min(1_048_576, remaining):
                buffer_size = min(buffer_size * 2, 1_048_576, remaining)
                buffer = ctypes.create_string_buffer(buffer_size)
        if len(payload) > maximum_bytes:
            raise PhysicalOnboardingDurabilityError(f"{label} exceeds its byte limit")
        return bytes(payload)
    finally:
        close = kernel32.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        close(handle)


def _portable_directory_sync(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _windows_write_file(
    path: Path,
    payload: bytes,
    *,
    injector: FaultInjector | None,
) -> None:
    kernel32 = _win32()
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
    handle = create_file(
        str(path),
        0x40000000,
        0,
        None,
        1,
        0x80 | 0x80000000 | 0x00200000,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise _win_error("CreateFileW(CREATE_NEW|WRITE_THROUGH)")
    try:
        _checkpoint(injector, DurabilityCheckpoint.AFTER_TEMP_CREATE)
        write_file = kernel32.WriteFile
        write_file.argtypes = [
            wintypes.HANDLE,
            wintypes.LPCVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        write_file.restype = wintypes.BOOL
        offset = 0
        while offset < len(payload):
            chunk = payload[offset : offset + min(1_048_576, len(payload) - offset)]
            buffer = ctypes.create_string_buffer(chunk)
            written = wintypes.DWORD(0)
            if not write_file(handle, buffer, len(chunk), ctypes.byref(written), None):
                raise _win_error("WriteFile")
            if written.value <= 0 or written.value > len(chunk):
                raise PhysicalOnboardingDurabilityError(
                    "WriteFile made invalid progress"
                )
            offset += int(written.value)
        _checkpoint(injector, DurabilityCheckpoint.AFTER_TEMP_WRITE)
        flush = kernel32.FlushFileBuffers
        flush.argtypes = [wintypes.HANDLE]
        flush.restype = wintypes.BOOL
        if not flush(handle):
            raise _win_error("FlushFileBuffers")
        _checkpoint(injector, DurabilityCheckpoint.AFTER_TEMP_FLUSH)
    finally:
        close = kernel32.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        close(handle)


def _windows_move(source: Path, destination: Path, *, replace: bool) -> None:
    kernel32 = _win32()
    if replace:
        replace_file = kernel32.ReplaceFileW
        replace_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.LPVOID,
        ]
        replace_file.restype = wintypes.BOOL
        if not replace_file(str(destination), str(source), None, 0, None, None):
            raise _win_error("ReplaceFileW")
        return
    move = kernel32.MoveFileExW
    move.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    move.restype = wintypes.BOOL
    if not move(str(source), str(destination), 0x8):
        raise _win_error("MoveFileExW(MOVEFILE_WRITE_THROUGH)")


def _windows_flush_existing(path: Path) -> None:
    kernel32 = _win32()
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
    handle = create_file(
        str(path),
        0x40000000,
        0x1 | 0x2 | 0x4,
        None,
        3,
        0x80 | 0x80000000 | 0x00200000,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise _win_error("CreateFileW(OPEN_EXISTING|WRITE_THROUGH)")
    try:
        flush = kernel32.FlushFileBuffers
        flush.argtypes = [wintypes.HANDLE]
        flush.restype = wintypes.BOOL
        if not flush(handle):
            raise _win_error("FlushFileBuffers(destination)")
    finally:
        close = kernel32.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        close(handle)


def publish_bytes(
    root: Path,
    relative_path: Path | str,
    payload: bytes,
    *,
    mode: PublicationMode,
    maximum_bytes: int = MAX_PUBLICATION_BYTES,
    fault_injector: FaultInjector | None = None,
) -> Path:
    """Publish bounded bytes using a same-directory, same-volume temporary.

    ``IMMUTABLE`` never overwrites an existing destination. ``REPLACE`` is for
    independently validated heads only.  No parent directory is created here.
    """

    if not isinstance(mode, PublicationMode):
        raise TypeError("mode must be PublicationMode")
    if type(payload) is not bytes or not payload:
        raise PhysicalOnboardingDurabilityError("publication payload must be bytes")
    if (
        isinstance(maximum_bytes, bool)
        or not isinstance(maximum_bytes, int)
        or maximum_bytes <= 0
        or len(payload) > maximum_bytes
    ):
        raise PhysicalOnboardingDurabilityError("publication payload exceeds its limit")
    selected_root = safe_root(root)
    destination = contained_path(selected_root, relative_path, label="publication path")
    parent_relative = destination.parent.relative_to(selected_root)
    parent = (
        selected_root
        if not parent_relative.parts
        else contained_path(selected_root, parent_relative, label="publication parent")
    )
    if not parent.is_dir():
        raise PhysicalOnboardingDurabilityError("publication parent must already exist")
    if mode is PublicationMode.IMMUTABLE and os.path.lexists(destination):
        raise PhysicalOnboardingDurabilityError("immutable publication already exists")
    if mode is PublicationMode.REPLACE and not destination.is_file():
        raise PhysicalOnboardingDurabilityError(
            "replace publication requires an existing file"
        )
    temporary = parent / f".{destination.name}.{secrets.token_hex(16)}.tmp"
    _reject_unsafe_component(temporary, "publication temporary")
    _checkpoint(fault_injector, DurabilityCheckpoint.BEFORE_TEMP_CREATE)
    try:
        if os.name == "nt":
            _windows_write_file(temporary, payload, injector=fault_injector)
        else:
            with temporary.open("xb") as stream:
                _checkpoint(fault_injector, DurabilityCheckpoint.AFTER_TEMP_CREATE)
                written = stream.write(payload)
                if written != len(payload):
                    raise PhysicalOnboardingDurabilityError("short publication write")
                _checkpoint(fault_injector, DurabilityCheckpoint.AFTER_TEMP_WRITE)
                stream.flush()
                os.fsync(stream.fileno())
                _checkpoint(fault_injector, DurabilityCheckpoint.AFTER_TEMP_FLUSH)
        _checkpoint(fault_injector, DurabilityCheckpoint.BEFORE_MOVE)
        if os.name == "nt":
            _windows_move(
                temporary,
                destination,
                replace=mode is PublicationMode.REPLACE,
            )
        elif mode is PublicationMode.IMMUTABLE:
            try:
                os.link(temporary, destination)
            except FileExistsError as exc:
                raise PhysicalOnboardingDurabilityError(
                    "immutable publication concurrently appeared"
                ) from exc
            temporary.unlink()
            _portable_directory_sync(parent)
        else:
            os.replace(temporary, destination)
            _portable_directory_sync(parent)
        _checkpoint(fault_injector, DurabilityCheckpoint.AFTER_MOVE)
        _reject_unsafe_component(destination, "published file")
        if os.name == "nt":
            _windows_flush_existing(destination)
        _checkpoint(fault_injector, DurabilityCheckpoint.AFTER_DESTINATION_FLUSH)
        observed = _read_regular_file(
            destination, maximum_bytes=maximum_bytes, label="published file"
        )
        if observed != payload:
            raise PhysicalOnboardingDurabilityError(
                "published bytes differ after reopen"
            )
        return destination
    finally:
        try:
            if temporary.is_file() and not temporary.is_symlink():
                temporary.unlink()
        except OSError:
            pass


def publish_reservation_bytes(
    root: Path,
    relative_path: Path | str,
    payload: bytes,
    *,
    maximum_bytes: int = MAX_PUBLICATION_BYTES,
    fault_injector: FaultInjector | None = None,
) -> Path:
    """Exclusively reserve a final name, flush and verify; never erase a tail.

    Unlike immutable *publication*, reservation linearizes at CREATE_NEW, before
    the record is complete. A crash/short write can leave an incomplete final
    file, which readers MUST treat as a held, consumed reservation. It must not
    be deleted, repaired or retried automatically. This is for one-use claims,
    not ledger commits or replacing atomic publication elsewhere.

    No rename is needed, so a supervised child can reserve a file under a pinned
    journal directory without weakening the owner's rename/reparse protections.
    """
    if type(payload) is not bytes or not payload:
        raise PhysicalOnboardingDurabilityError("reservation payload must be bytes")
    if (
        type(maximum_bytes) is not int
        or maximum_bytes <= 0
        or len(payload) > maximum_bytes
    ):
        raise PhysicalOnboardingDurabilityError("reservation payload exceeds its limit")
    selected_root = safe_root(root)
    destination = contained_path(selected_root, relative_path, label="reservation path")
    if not destination.parent.is_dir():
        raise PhysicalOnboardingDurabilityError("reservation parent must already exist")
    _checkpoint(fault_injector, DurabilityCheckpoint.BEFORE_TEMP_CREATE)
    if os.name == "nt":
        _windows_write_file(destination, payload, injector=fault_injector)
    else:
        with destination.open("xb") as stream:
            _checkpoint(fault_injector, DurabilityCheckpoint.AFTER_TEMP_CREATE)
            if stream.write(payload) != len(payload):
                raise PhysicalOnboardingDurabilityError("short reservation write")
            _checkpoint(fault_injector, DurabilityCheckpoint.AFTER_TEMP_WRITE)
            stream.flush()
            os.fsync(stream.fileno())
            _checkpoint(fault_injector, DurabilityCheckpoint.AFTER_TEMP_FLUSH)
        _portable_directory_sync(destination.parent)
    if (
        _read_regular_file(
            destination, maximum_bytes=maximum_bytes, label="reserved file"
        )
        != payload
    ):
        raise PhysicalOnboardingDurabilityError("reservation readback mismatch")
    return destination


def publish_canonical_json(
    root: Path,
    relative_path: Path | str,
    document: Mapping[str, object],
    *,
    mode: PublicationMode,
    maximum_bytes: int = MAX_PUBLICATION_BYTES,
    fault_injector: FaultInjector | None = None,
) -> Path:
    return publish_bytes(
        root,
        relative_path,
        canonical_bytes(document, maximum_bytes=maximum_bytes),
        mode=mode,
        maximum_bytes=maximum_bytes,
        fault_injector=fault_injector,
    )


@dataclass(frozen=True, slots=True)
class DurabilityQualificationCheck:
    check_id: str
    passed: bool
    detail: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.check_id, str)
            or _RECORD_KIND.fullmatch(self.check_id) is None
        ):
            raise PhysicalOnboardingDurabilityError("qualification check_id is invalid")
        if not isinstance(self.passed, bool):
            raise PhysicalOnboardingDurabilityError(
                "qualification check passed must be bool"
            )
        if (
            not isinstance(self.detail, str)
            or not self.detail
            or len(self.detail) > 256
        ):
            raise PhysicalOnboardingDurabilityError("qualification detail is invalid")

    def to_dict(self) -> dict[str, object]:
        return {"check_id": self.check_id, "detail": self.detail, "passed": self.passed}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DurabilityQualificationCheck":
        _exact_fields(value, {"check_id", "detail", "passed"}, "qualification check")
        return cls(
            check_id=value["check_id"],
            passed=value["passed"],
            detail=value["detail"],
        )


@dataclass(frozen=True, slots=True)
class DurabilityQualificationReport:
    source_binding_sha256: str
    root_sha256: str
    platform: str
    filesystem: str
    volume_identity: str
    adapter_id: str
    checked_at_ns: int
    checks: tuple[DurabilityQualificationCheck, ...]
    qualified_for_effects: bool
    report_sha256: str

    def __post_init__(self) -> None:
        _digest(self.source_binding_sha256, "qualification source binding")
        _digest(self.root_sha256, "qualification root hash")
        _positive_integer(self.checked_at_ns, "qualification checked_at_ns")
        if (
            not isinstance(self.platform, str)
            or not isinstance(self.filesystem, str)
            or not isinstance(self.volume_identity, str)
            or not self.platform
            or not self.filesystem
            or not self.volume_identity
        ):
            raise PhysicalOnboardingDurabilityError(
                "qualification platform fields are empty"
            )
        if self.adapter_id != DURABILITY_ADAPTER_ID:
            raise PhysicalOnboardingDurabilityError(
                "qualification adapter identity changed"
            )
        required = (
            "LOCKFILEEX_EXCLUSIVE_LEASE",
            "WRITE_THROUGH_FILE_OPEN",
            "FLUSH_FILE_BUFFERS",
            "ATOMIC_REPLACE",
            "DIRECTORY_ENTRY_DURABILITY_TEST",
        )
        if tuple(item.check_id for item in self.checks) != required:
            raise PhysicalOnboardingDurabilityError(
                "qualification check set or order changed"
            )
        expected_qualified = (
            self.platform == "Windows"
            and self.filesystem == "NTFS"
            and all(item.passed for item in self.checks)
        )
        if self.qualified_for_effects is not expected_qualified:
            raise PhysicalOnboardingDurabilityError(
                "qualification disposition is inconsistent"
            )
        _digest(self.report_sha256, "qualification report hash")
        if self.report_sha256 != canonical_sha256(self.core_dict()):
            raise PhysicalOnboardingDurabilityError(
                "qualification report hash mismatch"
            )

    def core_dict(self) -> dict[str, object]:
        return {
            "adapter_id": self.adapter_id,
            "checked_at_ns": self.checked_at_ns,
            "checks": [item.to_dict() for item in self.checks],
            "filesystem": self.filesystem,
            "platform": self.platform,
            "qualified_for_effects": self.qualified_for_effects,
            "root_sha256": self.root_sha256,
            "schema": DURABILITY_REPORT_SCHEMA,
            "source_binding_sha256": self.source_binding_sha256,
            "volume_identity": self.volume_identity,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self.core_dict(), "report_sha256": self.report_sha256}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DurabilityQualificationReport":
        _exact_fields(
            value,
            {
                "schema",
                "source_binding_sha256",
                "root_sha256",
                "platform",
                "filesystem",
                "volume_identity",
                "adapter_id",
                "checked_at_ns",
                "checks",
                "qualified_for_effects",
                "report_sha256",
            },
            "durability qualification report",
        )
        if value["schema"] != DURABILITY_REPORT_SCHEMA:
            raise PhysicalOnboardingDurabilityError(
                "unsupported durability qualification report schema"
            )
        raw_checks = value["checks"]
        if not isinstance(raw_checks, list):
            raise PhysicalOnboardingDurabilityError(
                "durability qualification checks must be an array"
            )
        checks: list[DurabilityQualificationCheck] = []
        for raw_check in raw_checks:
            if not isinstance(raw_check, dict):
                raise PhysicalOnboardingDurabilityError(
                    "durability qualification check must be an object"
                )
            checks.append(DurabilityQualificationCheck.from_dict(raw_check))
        return cls(
            source_binding_sha256=value["source_binding_sha256"],
            root_sha256=value["root_sha256"],
            platform=value["platform"],
            filesystem=value["filesystem"],
            volume_identity=value["volume_identity"],
            adapter_id=value["adapter_id"],
            checked_at_ns=value["checked_at_ns"],
            checks=tuple(checks),
            qualified_for_effects=value["qualified_for_effects"],
            report_sha256=value["report_sha256"],
        )


def parse_durability_qualification_report(
    payload: bytes,
) -> DurabilityQualificationReport:
    """Strictly reconstruct one canonical, self-hashed qualification receipt."""

    document = _parse_canonical_json(
        payload,
        maximum_bytes=MAX_QUALIFICATION_REPORT_BYTES,
        label="durability qualification report",
    )
    return DurabilityQualificationReport.from_dict(document)


def load_durability_qualification_report(path: Path) -> DurabilityQualificationReport:
    """Read a persisted qualification receipt without blocking head replacement."""

    selected = Path(os.path.abspath(path))
    payload = read_bounded_regular_file(
        selected,
        maximum_bytes=MAX_QUALIFICATION_REPORT_BYTES,
        label="durability qualification report",
    )
    return parse_durability_qualification_report(payload)


def _windows_volume_identity(root: Path) -> tuple[str, str]:
    kernel32 = _win32()
    volume_path_buffer = ctypes.create_unicode_buffer(261)
    volume_path = kernel32.GetVolumePathNameW
    volume_path.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    volume_path.restype = wintypes.BOOL
    if not volume_path(str(root), volume_path_buffer, len(volume_path_buffer)):
        raise _win_error("GetVolumePathNameW")
    filesystem_buffer = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD(0)
    maximum_component = wintypes.DWORD(0)
    flags = wintypes.DWORD(0)
    get_information = kernel32.GetVolumeInformationW
    get_information.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    get_information.restype = wintypes.BOOL
    if not get_information(
        volume_path_buffer.value,
        None,
        0,
        ctypes.byref(serial),
        ctypes.byref(maximum_component),
        ctypes.byref(flags),
        filesystem_buffer,
        len(filesystem_buffer),
    ):
        raise _win_error("GetVolumeInformationW")
    get_drive_type = kernel32.GetDriveTypeW
    get_drive_type.argtypes = [wintypes.LPCWSTR]
    get_drive_type.restype = wintypes.UINT
    drive_type = int(get_drive_type(volume_path_buffer.value))
    drive_type_name = {
        0: "UNKNOWN",
        1: "NO_ROOT",
        2: "REMOVABLE",
        3: "FIXED",
        4: "REMOTE",
        5: "CDROM",
        6: "RAMDISK",
    }.get(drive_type, f"UNRECOGNIZED_{drive_type}")
    filesystem = filesystem_buffer.value.upper()
    if drive_type != 3:
        # A mapped/UNC share can report NTFS while providing remote caching and
        # server-side rename/durability semantics that this local Win32 adapter
        # has not qualified.  Removable media likewise needs its own explicit
        # deployment qualification rather than inheriting the fixed-disk claim.
        filesystem = f"{filesystem}_{drive_type_name}_UNQUALIFIED"
    identity = f"{volume_path_buffer.value}|{serial.value:08x}|drive={drive_type_name}"
    return filesystem, identity


class _InjectedTornTail(RuntimeError):
    pass


def run_on_volume_startup_self_test(
    root: Path,
    *,
    source_binding_sha256: str,
    lease_probe: LeaseProbe | None = None,
    checked_at_ns: int | None = None,
    fault_injector: FaultInjector | None = None,
) -> DurabilityQualificationReport:
    """Exercise the exact deployment volume and return a source-bound report."""

    # The production gate always executes the controlled LockFileEx probe.  The
    # parameter remains only for source-compatible callers and must be that exact
    # function; accepting a caller-authored ``lambda: True`` would make this
    # qualification receipt meaningless.
    from rocell.application.physical_onboarding_leases import (
        windows_lockfileex_self_test,
    )

    if lease_probe is not None and lease_probe is not windows_lockfileex_self_test:
        raise DurabilityQualificationError(
            "custom durability lease probes are forbidden"
        )
    controlled_lease_probe: LeaseProbe = windows_lockfileex_self_test
    source_binding = _digest(source_binding_sha256, "source binding")
    selected_root = safe_root(root)
    checked = _positive_integer(
        time.time_ns() if checked_at_ns is None else checked_at_ns,
        "checked_at_ns",
    )
    _checkpoint(fault_injector, DurabilityCheckpoint.SELF_TEST_BEFORE)
    platform_name = "Windows" if os.name == "nt" else os.name
    filesystem = "UNQUALIFIED_PORTABLE"
    volume_identity = f"portable:{selected_root.anchor}"
    if os.name == "nt":
        try:
            filesystem, volume_identity = _windows_volume_identity(selected_root)
        except PhysicalOnboardingDurabilityError:
            filesystem = "UNKNOWN"
            volume_identity = "windows-volume-unavailable"
    test_directory = (
        selected_root / f".rocell-durability-self-test-{secrets.token_hex(12)}"
    )
    checks: dict[str, DurabilityQualificationCheck] = {}
    try:
        test_directory.mkdir(exist_ok=False)
        lock_ok = False
        lock_detail = "controlled LockFileEx lease probe did not pass"
        try:
            lock_ok = bool(controlled_lease_probe(test_directory))
            if lock_ok:
                lock_detail = "exclusive nonblocking LockFileEx probe passed"
        except Exception as exc:  # a failed probe is evidence, not startup success
            lock_detail = f"controlled lease probe failed: {type(exc).__name__}"
        checks["LOCKFILEEX_EXCLUSIVE_LEASE"] = DurabilityQualificationCheck(
            "LOCKFILEEX_EXCLUSIVE_LEASE", lock_ok and os.name == "nt", lock_detail
        )

        write_ok = flush_ok = replace_ok = directory_ok = False
        try:
            publish_bytes(
                test_directory,
                "immutable.bin",
                b"rocell-durability-v1",
                mode=PublicationMode.IMMUTABLE,
                fault_injector=fault_injector,
            )
            write_ok = True
            flush_ok = True
            publish_bytes(
                test_directory,
                "head.bin",
                b"head-a",
                mode=PublicationMode.IMMUTABLE,
                fault_injector=fault_injector,
            )
            publish_bytes(
                test_directory,
                "head.bin",
                b"head-b",
                mode=PublicationMode.REPLACE,
                fault_injector=fault_injector,
            )
            replace_ok = (test_directory / "head.bin").read_bytes() == b"head-b"

            ledger = DurableCommittedLedger.create(
                test_directory,
                ledger_id="durability-self-test",
                source_binding_sha256=source_binding,
                qualification_sha256=ZERO_SHA256,
                created_at_ns=checked,
                fault_injector=fault_injector,
            )

            def stop_after_record(checkpoint: str) -> None:
                if checkpoint == DurabilityCheckpoint.LEDGER_AFTER_RECORD_PUBLISH.value:
                    raise _InjectedTornTail()
                _checkpoint(fault_injector, checkpoint)

            try:
                ledger.append(
                    "SELF_TEST_RECORD",
                    {"probe": "torn-tail"},
                    recorded_at_ns=checked + 1,
                    fault_injector=stop_after_record,
                )
            except _InjectedTornTail:
                pass
            directory_ok = (
                ledger.inspect().recovery_state is LedgerRecoveryState.UNCOMMITTED_TAIL
            )
        except Exception:
            # Individual false checks below preserve the fail-closed report.
            pass
        checks["WRITE_THROUGH_FILE_OPEN"] = DurabilityQualificationCheck(
            "WRITE_THROUGH_FILE_OPEN",
            write_ok and os.name == "nt",
            (
                "same-volume write-through temporary created"
                if write_ok
                else "write-through publication failed"
            ),
        )
        checks["FLUSH_FILE_BUFFERS"] = DurabilityQualificationCheck(
            "FLUSH_FILE_BUFFERS",
            flush_ok and os.name == "nt",
            (
                "file and reopened destination flushes passed"
                if flush_ok
                else "buffer flush failed"
            ),
        )
        checks["ATOMIC_REPLACE"] = DurabilityQualificationCheck(
            "ATOMIC_REPLACE",
            replace_ok and os.name == "nt",
            (
                "write-through replacement reopened exactly"
                if replace_ok
                else "atomic replacement failed"
            ),
        )
        checks["DIRECTORY_ENTRY_DURABILITY_TEST"] = DurabilityQualificationCheck(
            "DIRECTORY_ENTRY_DURABILITY_TEST",
            directory_ok and os.name == "nt",
            (
                "published record without head was classified as uncommitted"
                if directory_ok
                else "torn-tail classification failed"
            ),
        )
    finally:
        try:
            if test_directory.is_dir() and not test_directory.is_symlink():
                shutil.rmtree(test_directory)
        except OSError:
            # Cleanup failure must make the directory-entry check fail.
            item = checks.get("DIRECTORY_ENTRY_DURABILITY_TEST")
            if item is not None:
                checks["DIRECTORY_ENTRY_DURABILITY_TEST"] = (
                    DurabilityQualificationCheck(
                        item.check_id, False, "self-test cleanup could not be confirmed"
                    )
                )

    ordered_ids = (
        "LOCKFILEEX_EXCLUSIVE_LEASE",
        "WRITE_THROUGH_FILE_OPEN",
        "FLUSH_FILE_BUFFERS",
        "ATOMIC_REPLACE",
        "DIRECTORY_ENTRY_DURABILITY_TEST",
    )
    ordered = tuple(
        checks.get(identifier)
        or DurabilityQualificationCheck(
            identifier, False, "self-test did not reach check"
        )
        for identifier in ordered_ids
    )
    qualified = (
        platform_name == "Windows"
        and filesystem == "NTFS"
        and all(item.passed for item in ordered)
    )
    core: dict[str, object] = {
        "adapter_id": DURABILITY_ADAPTER_ID,
        "checked_at_ns": checked,
        "checks": [item.to_dict() for item in ordered],
        "filesystem": filesystem,
        "platform": platform_name,
        "qualified_for_effects": qualified,
        "root_sha256": hashlib.sha256(str(selected_root).encode("utf-8")).hexdigest(),
        "schema": DURABILITY_REPORT_SCHEMA,
        "source_binding_sha256": source_binding,
        "volume_identity": volume_identity,
    }
    report = DurabilityQualificationReport(
        source_binding_sha256=source_binding,
        root_sha256=str(core["root_sha256"]),
        platform=platform_name,
        filesystem=filesystem,
        volume_identity=volume_identity,
        adapter_id=DURABILITY_ADAPTER_ID,
        checked_at_ns=checked,
        checks=ordered,
        qualified_for_effects=qualified,
        report_sha256=canonical_sha256(core),
    )
    _checkpoint(fault_injector, DurabilityCheckpoint.SELF_TEST_AFTER)
    return report


def require_effect_durability(
    report: DurabilityQualificationReport | None,
    *,
    root: Path,
    source_binding_sha256: str,
) -> DurabilityQualificationReport:
    """Reject absent, failed, stale-source, or wrong-volume qualifications."""

    if report is None:
        raise DurabilityQualificationError("durability qualification is absent")
    if not isinstance(report, DurabilityQualificationReport):
        raise DurabilityQualificationError("durability qualification type is invalid")
    source_binding = _digest(source_binding_sha256, "source binding")
    selected_root = safe_root(root)
    if os.name != "nt":
        raise DurabilityQualificationError(
            "portable durability fallback is never qualified for physical effects"
        )
    expected_root = hashlib.sha256(str(selected_root).encode("utf-8")).hexdigest()
    if report.source_binding_sha256 != source_binding:
        raise DurabilityQualificationError("durability qualification source is stale")
    if report.root_sha256 != expected_root:
        raise DurabilityQualificationError(
            "durability qualification belongs to another root"
        )
    try:
        current_filesystem, current_volume = _windows_volume_identity(selected_root)
    except PhysicalOnboardingDurabilityError as exc:
        raise DurabilityQualificationError(
            "deployment volume identity cannot be reverified"
        ) from exc
    if (
        report.filesystem != current_filesystem
        or report.volume_identity != current_volume
    ):
        raise DurabilityQualificationError(
            "durability qualification belongs to another deployment volume"
        )
    if not report.qualified_for_effects:
        raise DurabilityQualificationError(
            "deployment filesystem is unqualified for physical effects"
        )
    return report


def require_effect_durability_pair(
    anchor: DurabilityQualificationReport | None,
    startup: DurabilityQualificationReport | None,
    *,
    root: Path,
    source_binding_sha256: str,
) -> None:
    """Validate both receipts against one fresh root/volume observation.

    The first validation performs the ordinary uncached path and native volume
    checks. Only within this invocation can its immutable receipt describe that
    observation for the companion receipt. No caller can supply an observation,
    cached approval or volume identity. The next call repeats all live checks.

    This is a point-in-time gate, not a claim that the filesystem cannot change
    afterwards. Publication still needs its own path/handle and lease checks.
    The publication owner separately enforces stable check identities and the
    startup/anchor timestamp order.
    """
    observed = require_effect_durability(
        anchor, root=root, source_binding_sha256=source_binding_sha256
    )
    if startup is None:
        raise DurabilityQualificationError("durability qualification is absent")
    if not isinstance(startup, DurabilityQualificationReport):
        raise DurabilityQualificationError("durability qualification type is invalid")
    if startup.source_binding_sha256 != observed.source_binding_sha256:
        raise DurabilityQualificationError("durability qualification source is stale")
    if startup.root_sha256 != observed.root_sha256:
        raise DurabilityQualificationError(
            "durability qualification belongs to another root"
        )
    if (
        startup.filesystem != observed.filesystem
        or startup.volume_identity != observed.volume_identity
    ):
        raise DurabilityQualificationError(
            "durability qualification belongs to another deployment volume"
        )
    if not startup.qualified_for_effects:
        raise DurabilityQualificationError(
            "deployment filesystem is unqualified for physical effects"
        )


@dataclass(frozen=True, slots=True)
class DurableLedgerRecord:
    ledger_id: str
    header_sha256: str
    sequence: int
    previous_record_sha256: str
    record_kind: str
    recorded_at_ns: int
    payload: Mapping[str, object]
    payload_sha256: str
    record_sha256: str

    def core_dict(self) -> dict[str, object]:
        return {
            "header_sha256": self.header_sha256,
            "ledger_id": self.ledger_id,
            "payload": dict(self.payload),
            "payload_sha256": self.payload_sha256,
            "previous_record_sha256": self.previous_record_sha256,
            "record_kind": self.record_kind,
            "recorded_at_ns": self.recorded_at_ns,
            "schema": DURABLE_LEDGER_RECORD_SCHEMA,
            "sequence": self.sequence,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self.core_dict(), "record_sha256": self.record_sha256}


@dataclass(frozen=True, slots=True)
class DurableLedgerSnapshot:
    ledger_id: str
    source_binding_sha256: str
    qualification_sha256: str
    header_sha256: str
    head_sha256: str
    committed_records: tuple[DurableLedgerRecord, ...]
    uncommitted_records: tuple[DurableLedgerRecord, ...]
    recovery_state: LedgerRecoveryState

    @property
    def append_allowed(self) -> bool:
        return self.recovery_state is LedgerRecoveryState.CLEAN


def _exact_fields(
    document: Mapping[str, object], expected: set[str], label: str
) -> None:
    if set(document) != expected:
        raise PhysicalOnboardingDurabilityError(
            f"{label} fields differ from exact schema"
        )


class DurableCommittedLedger:
    """Hash-chained immutable records plus one replaceable committed head."""

    def __init__(self, directory: Path) -> None:
        self.directory = safe_root(directory, label="durable ledger")

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        ledger_id: str,
        source_binding_sha256: str,
        qualification_sha256: str,
        created_at_ns: int,
        fault_injector: FaultInjector | None = None,
    ) -> "DurableCommittedLedger":
        container = safe_root(root, label="durable ledger container")
        selected_id = _identifier(ledger_id, "ledger_id")
        source_binding = _digest(source_binding_sha256, "source binding")
        qualification = _digest(qualification_sha256, "qualification hash")
        created = _positive_integer(created_at_ns, "created_at_ns")
        destination = contained_path(
            container, f"ledger-{selected_id}", label="durable ledger directory"
        )
        if os.path.lexists(destination):
            raise PhysicalOnboardingDurabilityError("durable ledger already exists")
        temporary = container / f".partial-ledger-{selected_id}-{secrets.token_hex(12)}"
        try:
            temporary.mkdir(exist_ok=False)
            (temporary / "records").mkdir(exist_ok=False)
            header_core: dict[str, object] = {
                "created_at_ns": created,
                "ledger_id": selected_id,
                "qualification_sha256": qualification,
                "schema": DURABLE_LEDGER_HEADER_SCHEMA,
                "source_binding_sha256": source_binding,
            }
            header = {**header_core, "header_sha256": canonical_sha256(header_core)}
            head_core: dict[str, object] = {
                "committed_record_sha256": ZERO_SHA256,
                "committed_sequence": None,
                "event_count": 0,
                "header_sha256": header["header_sha256"],
                "ledger_id": selected_id,
                "schema": DURABLE_LEDGER_HEAD_SCHEMA,
            }
            head = {**head_core, "head_sha256": canonical_sha256(head_core)}
            publish_canonical_json(
                temporary,
                "header.json",
                header,
                mode=PublicationMode.IMMUTABLE,
                maximum_bytes=MAX_LEDGER_RECORD_BYTES,
                fault_injector=fault_injector,
            )
            publish_canonical_json(
                temporary,
                "head.json",
                head,
                mode=PublicationMode.IMMUTABLE,
                maximum_bytes=MAX_LEDGER_RECORD_BYTES,
                fault_injector=fault_injector,
            )
            if os.name == "nt":
                _windows_move(temporary, destination, replace=False)
            else:
                temporary.rename(destination)
                _portable_directory_sync(container)
        finally:
            try:
                if temporary.is_dir() and not temporary.is_symlink():
                    shutil.rmtree(temporary)
            except OSError:
                pass
        ledger = cls(destination)
        ledger.inspect()
        return ledger

    @classmethod
    def open(cls, directory: Path) -> "DurableCommittedLedger":
        ledger = cls(directory)
        ledger.inspect()
        return ledger

    def _load_header(self) -> dict[str, Any]:
        payload = _read_regular_file(
            self.directory / "header.json",
            maximum_bytes=MAX_LEDGER_RECORD_BYTES,
            label="durable ledger header",
        )
        document = _parse_canonical_json(
            payload,
            maximum_bytes=MAX_LEDGER_RECORD_BYTES,
            label="durable ledger header",
        )
        _exact_fields(
            document,
            {
                "schema",
                "ledger_id",
                "source_binding_sha256",
                "qualification_sha256",
                "created_at_ns",
                "header_sha256",
            },
            "durable ledger header",
        )
        if document["schema"] != DURABLE_LEDGER_HEADER_SCHEMA:
            raise PhysicalOnboardingDurabilityError("unsupported durable ledger header")
        _identifier(document["ledger_id"], "ledger_id")
        _digest(document["source_binding_sha256"], "source binding")
        _digest(document["qualification_sha256"], "qualification hash")
        _positive_integer(document["created_at_ns"], "created_at_ns")
        stored = _digest(document["header_sha256"], "header hash")
        core = dict(document)
        del core["header_sha256"]
        if canonical_sha256(core) != stored:
            raise PhysicalOnboardingDurabilityError(
                "durable ledger header hash mismatch"
            )
        if self.directory.name != f"ledger-{document['ledger_id']}":
            raise PhysicalOnboardingDurabilityError(
                "durable ledger directory identity mismatch"
            )
        return document

    def _load_head(self, header: Mapping[str, Any]) -> dict[str, Any]:
        payload = _read_regular_file(
            self.directory / "head.json",
            maximum_bytes=MAX_LEDGER_RECORD_BYTES,
            label="durable ledger head",
        )
        document = _parse_canonical_json(
            payload, maximum_bytes=MAX_LEDGER_RECORD_BYTES, label="durable ledger head"
        )
        _exact_fields(
            document,
            {
                "schema",
                "ledger_id",
                "header_sha256",
                "event_count",
                "committed_sequence",
                "committed_record_sha256",
                "head_sha256",
            },
            "durable ledger head",
        )
        if (
            document["schema"] != DURABLE_LEDGER_HEAD_SCHEMA
            or document["ledger_id"] != header["ledger_id"]
            or document["header_sha256"] != header["header_sha256"]
        ):
            raise PhysicalOnboardingDurabilityError(
                "durable ledger head binding mismatch"
            )
        count = document["event_count"]
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or not 0 <= count <= MAX_LEDGER_RECORDS
        ):
            raise PhysicalOnboardingDurabilityError(
                "durable ledger head count is invalid"
            )
        if count == 0:
            if (
                document["committed_sequence"] is not None
                or document["committed_record_sha256"] != ZERO_SHA256
            ):
                raise PhysicalOnboardingDurabilityError(
                    "empty durable ledger head is inconsistent"
                )
        elif document["committed_sequence"] != count - 1 or not isinstance(
            document["committed_sequence"], int
        ):
            raise PhysicalOnboardingDurabilityError(
                "durable ledger head sequence is invalid"
            )
        _digest(document["committed_record_sha256"], "committed record hash")
        stored = _digest(document["head_sha256"], "head hash")
        core = dict(document)
        del core["head_sha256"]
        if canonical_sha256(core) != stored:
            raise PhysicalOnboardingDurabilityError("durable ledger head hash mismatch")
        return document

    def _load_record(
        self, path: Path, *, sequence: int, header: Mapping[str, Any]
    ) -> DurableLedgerRecord:
        payload_bytes = _read_regular_file(
            path,
            maximum_bytes=MAX_LEDGER_RECORD_BYTES,
            label=f"durable ledger record {sequence}",
        )
        document = _parse_canonical_json(
            payload_bytes,
            maximum_bytes=MAX_LEDGER_RECORD_BYTES,
            label=f"durable ledger record {sequence}",
        )
        _exact_fields(
            document,
            {
                "schema",
                "ledger_id",
                "header_sha256",
                "sequence",
                "previous_record_sha256",
                "record_kind",
                "recorded_at_ns",
                "payload",
                "payload_sha256",
                "record_sha256",
            },
            "durable ledger record",
        )
        if (
            document["schema"] != DURABLE_LEDGER_RECORD_SCHEMA
            or document["ledger_id"] != header["ledger_id"]
            or document["header_sha256"] != header["header_sha256"]
            or document["sequence"] != sequence
        ):
            raise PhysicalOnboardingDurabilityError(
                "durable ledger record binding mismatch"
            )
        previous = _digest(document["previous_record_sha256"], "previous record hash")
        kind = document["record_kind"]
        if not isinstance(kind, str) or _RECORD_KIND.fullmatch(kind) is None:
            raise PhysicalOnboardingDurabilityError(
                "durable ledger record_kind is invalid"
            )
        recorded = _positive_integer(document["recorded_at_ns"], "recorded_at_ns")
        raw_payload = document["payload"]
        if not isinstance(raw_payload, dict):
            raise PhysicalOnboardingDurabilityError(
                "durable ledger payload must be an object"
            )
        payload_hash = _digest(document["payload_sha256"], "payload hash")
        if canonical_sha256(raw_payload) != payload_hash:
            raise PhysicalOnboardingDurabilityError(
                "durable ledger payload hash mismatch"
            )
        stored = _digest(document["record_sha256"], "record hash")
        core = dict(document)
        del core["record_sha256"]
        if canonical_sha256(core) != stored:
            raise PhysicalOnboardingDurabilityError(
                "durable ledger record hash mismatch"
            )
        return DurableLedgerRecord(
            ledger_id=str(document["ledger_id"]),
            header_sha256=str(document["header_sha256"]),
            sequence=sequence,
            previous_record_sha256=previous,
            record_kind=kind,
            recorded_at_ns=recorded,
            payload=dict(raw_payload),
            payload_sha256=payload_hash,
            record_sha256=stored,
        )

    def inspect(self) -> DurableLedgerSnapshot:
        safe_root(self.directory, label="durable ledger")
        expected_top = {"header.json", "head.json", "records"}
        try:
            top_entries = list(os.scandir(self.directory))
        except OSError as exc:
            raise PhysicalOnboardingDurabilityError(
                "cannot enumerate durable ledger"
            ) from exc
        if {entry.name for entry in top_entries} != expected_top:
            raise PhysicalOnboardingDurabilityError(
                "durable ledger entry set is not exact"
            )
        for entry in top_entries:
            if entry.is_symlink():
                raise PhysicalOnboardingDurabilityError(
                    "durable ledger contains a symlink"
                )
        records_root = self.directory / "records"
        _reject_unsafe_component(records_root, "durable ledger records")
        if not records_root.is_dir():
            raise PhysicalOnboardingDurabilityError(
                "durable ledger records is not a directory"
            )
        header = self._load_header()
        head = self._load_head(header)
        paths: list[tuple[int, Path]] = []
        try:
            entries = list(os.scandir(records_root))
        except OSError as exc:
            raise PhysicalOnboardingDurabilityError(
                "cannot enumerate durable ledger records"
            ) from exc
        if len(entries) > MAX_LEDGER_RECORDS:
            raise PhysicalOnboardingDurabilityError(
                "durable ledger record limit exceeded"
            )
        pattern = re.compile(r"record-([0-9]{6})\.json\Z")
        for entry in entries:
            match = pattern.fullmatch(entry.name)
            if (
                entry.is_symlink()
                or not entry.is_file(follow_symlinks=False)
                or match is None
            ):
                raise PhysicalOnboardingDurabilityError(
                    "durable ledger has an unexpected record entry"
                )
            paths.append((int(match.group(1)), Path(entry.path)))
        paths.sort(key=lambda item: item[0])
        if [item[0] for item in paths] != list(range(len(paths))):
            raise PhysicalOnboardingDurabilityError(
                "durable ledger sequence is not contiguous"
            )
        records: list[DurableLedgerRecord] = []
        previous_hash = ZERO_SHA256
        previous_time = int(header["created_at_ns"]) - 1
        for sequence, path in paths:
            record = self._load_record(path, sequence=sequence, header=header)
            if record.previous_record_sha256 != previous_hash:
                raise PhysicalOnboardingDurabilityError(
                    "durable ledger hash chain is broken"
                )
            if record.recorded_at_ns <= previous_time:
                raise PhysicalOnboardingDurabilityError(
                    "durable ledger time is not increasing"
                )
            records.append(record)
            previous_hash = record.record_sha256
            previous_time = record.recorded_at_ns
        committed_count = int(head["event_count"])
        if committed_count > len(records):
            raise PhysicalOnboardingDurabilityError(
                "durable ledger committed suffix is missing"
            )
        if committed_count:
            committed_tail = records[committed_count - 1]
            if (
                head["committed_sequence"] != committed_tail.sequence
                or head["committed_record_sha256"] != committed_tail.record_sha256
            ):
                raise PhysicalOnboardingDurabilityError(
                    "durable ledger head differs from committed tail"
                )
        extra = len(records) - committed_count
        if extra > 1:
            raise PhysicalOnboardingDurabilityError(
                "durable ledger has multiple uncommitted tail records"
            )
        recovery = (
            LedgerRecoveryState.CLEAN
            if extra == 0
            else LedgerRecoveryState.UNCOMMITTED_TAIL
        )
        return DurableLedgerSnapshot(
            ledger_id=str(header["ledger_id"]),
            source_binding_sha256=str(header["source_binding_sha256"]),
            qualification_sha256=str(header["qualification_sha256"]),
            header_sha256=str(header["header_sha256"]),
            head_sha256=str(head["head_sha256"]),
            committed_records=tuple(records[:committed_count]),
            uncommitted_records=tuple(records[committed_count:]),
            recovery_state=recovery,
        )

    def append(
        self,
        record_kind: str,
        payload: Mapping[str, object],
        *,
        recorded_at_ns: int,
        fault_injector: FaultInjector | None = None,
    ) -> DurableLedgerSnapshot:
        if (
            not isinstance(record_kind, str)
            or _RECORD_KIND.fullmatch(record_kind) is None
        ):
            raise PhysicalOnboardingDurabilityError("record_kind is invalid")
        if not isinstance(payload, Mapping):
            raise PhysicalOnboardingDurabilityError("ledger payload must be a mapping")
        canonical_bytes(payload, maximum_bytes=MAX_LEDGER_RECORD_BYTES)
        recorded = _positive_integer(recorded_at_ns, "recorded_at_ns")
        current = self.inspect()
        if not current.append_allowed:
            raise PhysicalOnboardingDurabilityError(
                "uncommitted ledger tail requires read-only reconciliation"
            )
        sequence = len(current.committed_records)
        if sequence >= MAX_LEDGER_RECORDS:
            raise PhysicalOnboardingDurabilityError(
                "durable ledger record limit reached"
            )
        previous = (
            ZERO_SHA256
            if not current.committed_records
            else current.committed_records[-1].record_sha256
        )
        if (
            current.committed_records
            and recorded <= current.committed_records[-1].recorded_at_ns
        ):
            raise PhysicalOnboardingDurabilityError(
                "recorded_at_ns must strictly increase"
            )
        payload_document = dict(payload)
        core: dict[str, object] = {
            "header_sha256": current.header_sha256,
            "ledger_id": current.ledger_id,
            "payload": payload_document,
            "payload_sha256": canonical_sha256(payload_document),
            "previous_record_sha256": previous,
            "record_kind": record_kind,
            "recorded_at_ns": recorded,
            "schema": DURABLE_LEDGER_RECORD_SCHEMA,
            "sequence": sequence,
        }
        record = {**core, "record_sha256": canonical_sha256(core)}
        publish_canonical_json(
            self.directory,
            Path("records") / f"record-{sequence:06d}.json",
            record,
            mode=PublicationMode.IMMUTABLE,
            maximum_bytes=MAX_LEDGER_RECORD_BYTES,
            fault_injector=fault_injector,
        )
        _checkpoint(fault_injector, DurabilityCheckpoint.LEDGER_AFTER_RECORD_PUBLISH)
        head_core: dict[str, object] = {
            "committed_record_sha256": record["record_sha256"],
            "committed_sequence": sequence,
            "event_count": sequence + 1,
            "header_sha256": current.header_sha256,
            "ledger_id": current.ledger_id,
            "schema": DURABLE_LEDGER_HEAD_SCHEMA,
        }
        head = {**head_core, "head_sha256": canonical_sha256(head_core)}
        publish_canonical_json(
            self.directory,
            "head.json",
            head,
            mode=PublicationMode.REPLACE,
            maximum_bytes=MAX_LEDGER_RECORD_BYTES,
            fault_injector=fault_injector,
        )
        _checkpoint(fault_injector, DurabilityCheckpoint.LEDGER_AFTER_HEAD_PUBLISH)
        result = self.inspect()
        if result.recovery_state is not LedgerRecoveryState.CLEAN:
            raise PhysicalOnboardingDurabilityError(
                "ledger did not reload at a clean head"
            )
        return result


__all__ = [
    "DURABILITY_ADAPTER_ID",
    "DURABILITY_REPORT_SCHEMA",
    "DURABLE_LEDGER_HEAD_SCHEMA",
    "DURABLE_LEDGER_HEADER_SCHEMA",
    "DURABLE_LEDGER_RECORD_SCHEMA",
    "DurabilityCheckpoint",
    "DurabilityQualificationCheck",
    "DurabilityQualificationError",
    "DurabilityQualificationReport",
    "DurableCommittedLedger",
    "DurableLedgerRecord",
    "DurableLedgerSnapshot",
    "FaultInjector",
    "LedgerRecoveryState",
    "MAX_QUALIFICATION_REPORT_BYTES",
    "PhysicalOnboardingDurabilityError",
    "PublicationMode",
    "ZERO_SHA256",
    "canonical_bytes",
    "canonical_sha256",
    "contained_path",
    "load_durability_qualification_report",
    "parse_durability_qualification_report",
    "publish_bytes",
    "publish_canonical_json",
    "read_bounded_regular_file",
    "require_effect_durability",
    "run_on_volume_startup_self_test",
    "safe_root",
]
