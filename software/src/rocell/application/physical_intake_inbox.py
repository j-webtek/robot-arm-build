"""Explicit, bounded local attachment choices; no device or evidence approval.

Only the assigned inbox is enumerated. Opaque selections bind exact original
bytes and disk identity. Windows sharing pins span the caller's eventual M1
copy/readback; observing a filename or hash does not authenticate its contents.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from itertools import islice
import os
from pathlib import Path
import re
import stat
from threading import Event, Lock, RLock
import time
from typing import Any, Callable, Iterator
import uuid

from .physical_onboarding_durability import read_bounded_regular_file, safe_root
from .physical_source_stage_evidence import _pins
from .wizard_actions import WizardError
from .wizard_diagnostic_coordinator import source_fingerprint
from .wizard_diagnostic_export import _directory_guard
from rocell.providers.windows.native_camera_protocol import canonical, digest

SCHEMA = "rocell.physical_intake_inbox.v1"
MAX_FILES = 32
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_SCAN_BYTES = 16 * 1024 * 1024
MAX_SELECTION_BYTES = 4 * 1024 * 1024
MEDIA_TYPES = {
    ".txt": "text/plain",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
}
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,94}\Z")
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_MESSAGES = {
    "INTAKE_INBOX_BUSY": "Another inbox operation owns the file-selection scope.",
    "INTAKE_INBOX_INVALID": "The assigned inbox context is invalid.",
    "INTAKE_INBOX_LIMIT": "The inbox exceeds its bounded file or byte inventory; reduce the input set explicitly.",
    "INTAKE_INBOX_UNSAFE_FILE": "A selected input is linked, reparsed, multiply linked, or not a regular file.",
    "INTAKE_INBOX_FILE_LIMIT": "An input is empty or exceeds the 2 MiB original-file limit; it was not converted or truncated.",
    "INTAKE_INBOX_FILE_TYPE": "Use a portable filename and an allowed TXT, JSON, PNG, JPEG or PDF input.",
    "INTAKE_INBOX_CONTENT": "Input bytes do not match the declared text/header type; this check does not validate physical evidence.",
    "INTAKE_INBOX_CHANGED": "The selected input or its disk identity changed; discover explicitly again.",
    "INTAKE_INBOX_STALE_CHOICE": "The choice does not belong to the current explicit discovery.",
    "INTAKE_INBOX_SOURCE_CHANGED": "Application sources changed; this file choice is historical.",
    "INTAKE_INBOX_CANCELLED": "The file operation was cancelled; no automatic retry.",
    "INTAKE_INBOX_DEADLINE": "The original bounded file-operation deadline expired.",
    "INTAKE_INBOX_READ_FAILED": "The original input could not be read under its guarded disk scope.",
}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise WizardError(code, _MESSAGES[code])


def _stamp(path: Path) -> dict[str, Any]:
    observed = path.stat(follow_symlinks=False)
    _require(
        stat.S_ISREG(observed.st_mode)
        and not stat.S_ISLNK(observed.st_mode)
        and not getattr(observed, "st_file_attributes", 0) & 0x400
        and observed.st_nlink == 1,
        "INTAKE_INBOX_UNSAFE_FILE",
    )
    _require(0 < observed.st_size <= MAX_FILE_BYTES, "INTAKE_INBOX_FILE_LIMIT")
    return {
        "device": str(observed.st_dev),
        "file_id": str(observed.st_ino),
        "bytes": observed.st_size,
        "mtime_ns": str(observed.st_mtime_ns),
        "ctime_ns": str(observed.st_ctime_ns),
    }


def _media(basename: str, payload: bytes) -> str:
    _require(
        type(basename) is str
        and _NAME.fullmatch(basename) is not None
        and not basename.endswith((".", " "))
        and basename.split(".", 1)[0].upper() not in _RESERVED
        and Path(basename).suffix.lower() in MEDIA_TYPES,
        "INTAKE_INBOX_FILE_TYPE",
    )
    media = MEDIA_TYPES[Path(basename).suffix.lower()]
    if media in {"text/plain", "application/json"}:
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeError as error:
            raise WizardError(
                "INTAKE_INBOX_CONTENT", _MESSAGES["INTAKE_INBOX_CONTENT"]
            ) from error
        _require("\0" not in text, "INTAKE_INBOX_CONTENT")
    else:
        signature = {
            "image/png": b"\x89PNG\r\n\x1a\n",
            "image/jpeg": b"\xff\xd8\xff",
            "application/pdf": b"%PDF-",
        }[media]
        _require(payload.startswith(signature), "INTAKE_INBOX_CONTENT")
    # Opaque retention only. Neither parsing a PDF nor decoding an image is
    # necessary to copy its original bytes, and no input is ever executed.
    return media


@dataclass(frozen=True, slots=True)
class IntakeInboxFile:
    choice_id: str
    basename: str
    media_type: str
    payload: bytes

    @property
    def payload_sha256(self) -> str:
        return digest(self.payload)


class PhysicalIntakeInbox:
    def __init__(self, workspace: Path, *, launch_id: str, source_sha256: str) -> None:
        _require(
            isinstance(workspace, Path)
            and workspace.is_absolute()
            and ".." not in workspace.parts
            and workspace != Path(workspace.anchor)
            and not str(workspace).startswith(("\\\\", "//"))
            and type(launch_id) is str
            and re.fullmatch(r"wizard-[0-9a-f]{32}", launch_id) is not None
            and type(source_sha256) is str
            and re.fullmatch(r"[0-9a-f]{64}", source_sha256) is not None
            and source_sha256 != "0" * 64,
            "INTAKE_INBOX_INVALID",
        )
        self.workspace, self.launch_id, self.source_sha256 = (
            workspace,
            launch_id,
            source_sha256,
        )
        self.root = workspace / "software/runs/physical-intake-inbox"
        self._lock, self._operation_lock = RLock(), Lock()
        self._choices: dict[str, dict[str, Any]] = {}
        self._cached = self._empty("NOT_DISCOVERED")

    def _empty(self, status: str) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "status": status,
            "directory": str(self.root),
            "source_sha256": self.source_sha256,
            "launch_session_id": self.launch_id,
            "discovery_sha256": None,
            "files": [],
            "issues": [],
            "physical_authority": False,
            "device_io_performed": False,
        }

    def view(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._cached)

    def choices(self) -> list[dict[str, str]]:
        return [
            {"value": row["choice_id"], "label": row["basename"]}
            for row in self.view()["files"]
        ]

    def preview(self, choice_id: str) -> dict[str, Any]:
        with self._lock:
            _require(
                type(choice_id) is str and choice_id in self._choices,
                "INTAKE_INBOX_STALE_CHOICE",
            )
            return deepcopy(self._choices[choice_id]["summary"])

    def _checks(self, cancellation: Event, deadline_ns: int) -> Callable[[], None]:
        _require(
            isinstance(cancellation, Event)
            and type(deadline_ns) is int
            and 0 < deadline_ns < 2**63,
            "INTAKE_INBOX_INVALID",
        )

        def check() -> None:
            _require(not cancellation.is_set(), "INTAKE_INBOX_CANCELLED")
            _require(time.monotonic_ns() < deadline_ns, "INTAKE_INBOX_DEADLINE")

        return check

    def _source(self, check: Callable[[], None]) -> None:
        check()
        _require(
            source_fingerprint(self.workspace) == self.source_sha256,
            "INTAKE_INBOX_SOURCE_CHANGED",
        )
        check()

    def discover(self, *, cancellation: Event, deadline_ns: int) -> dict[str, Any]:
        _require(self._operation_lock.acquire(blocking=False), "INTAKE_INBOX_BUSY")
        try:
            with self._lock:
                self._choices.clear()
                self._cached = self._empty("HELD")
            check = self._checks(
                cancellation, min(deadline_ns, time.monotonic_ns() + 30_000_000_000)
            )
            self._source(check)
            safe_root(self.root.parent)
            with _directory_guard(self.root.parent):
                check()
                if not os.path.lexists(self.root):
                    self.root.mkdir()  # Explicit discovery creates only this fixed inbox.
                safe_root(self.root)
            choices, rows, issues, total = {}, [], [], 0
            with _directory_guard(self.root):
                entries = list(islice(self.root.iterdir(), MAX_FILES + 1))
                _require(len(entries) <= MAX_FILES, "INTAKE_INBOX_LIMIT")
                for path in sorted(entries, key=lambda value: value.name):
                    check()
                    try:
                        _require(
                            _NAME.fullmatch(path.name) is not None
                            and path.name.split(".", 1)[0].upper() not in _RESERVED
                            and path.suffix.lower() in MEDIA_TYPES,
                            "INTAKE_INBOX_FILE_TYPE",
                        )
                        before = _stamp(path)
                        total += before["bytes"]
                        _require(total <= MAX_SCAN_BYTES, "INTAKE_INBOX_LIMIT")
                        with _pins(self.root, (path.name,), check):
                            raw = read_bounded_regular_file(
                                path, maximum_bytes=MAX_FILE_BYTES
                            )
                            media = _media(path.name, raw)
                            _require(before == _stamp(path), "INTAKE_INBOX_CHANGED")
                            check()
                        _require(before == _stamp(path), "INTAKE_INBOX_CHANGED")
                        choice = "intake-file-" + uuid.uuid4().hex
                        summary = {
                            "choice_id": choice,
                            "basename": path.name,
                            "media_type": media,
                            "payload_bytes": len(raw),
                            "payload_sha256": digest(raw),
                        }
                        choices[choice] = {"summary": summary, "identity": before}
                        rows.append(summary)
                    except WizardError as error:
                        if error.code in {
                            "INTAKE_INBOX_LIMIT",
                            "INTAKE_INBOX_CANCELLED",
                            "INTAKE_INBOX_DEADLINE",
                        }:
                            raise
                        issues.append(
                            {
                                "code": error.code,
                                "basename": (
                                    path.name if _NAME.fullmatch(path.name) else None
                                ),
                            }
                        )
                    except (OSError, ValueError):
                        issues.append(
                            {
                                "code": "INTAKE_INBOX_READ_FAILED",
                                "basename": (
                                    path.name if _NAME.fullmatch(path.name) else None
                                ),
                            }
                        )
            self._source(check)
            candidate = {**self._empty("READY"), "files": rows, "issues": issues}
            candidate["discovery_sha256"] = digest(canonical(candidate))
            with self._lock:
                check()
                self._choices, self._cached = choices, candidate
            return self.view()
        finally:
            self._operation_lock.release()

    @contextmanager
    def selected_files(
        self, choice_ids: tuple[str, ...], *, cancellation: Event, deadline_ns: int
    ) -> Iterator[tuple[IntakeInboxFile, ...]]:
        """Keep original regular-file pins through the caller's copy/readback.

        At most 4 MiB total is held, independent of image dimensions or client
        speed. Store quota preflight must also include existing M1 evidence.
        """
        _require(self._operation_lock.acquire(blocking=False), "INTAKE_INBOX_BUSY")
        try:
            check = self._checks(cancellation, deadline_ns)
            _require(
                type(choice_ids) is tuple
                and len(choice_ids) <= 16
                and len(set(choice_ids)) == len(choice_ids),
                "INTAKE_INBOX_INVALID",
            )
            with self._lock:
                _require(
                    all(
                        type(value) is str and value in self._choices
                        for value in choice_ids
                    ),
                    "INTAKE_INBOX_STALE_CHOICE",
                )
                selected = {
                    value: deepcopy(self._choices[value]) for value in choice_ids
                }
            _require(
                sum(value["summary"]["payload_bytes"] for value in selected.values())
                <= MAX_SELECTION_BYTES,
                "INTAKE_INBOX_LIMIT",
            )
            self._source(check)
            roster = tuple(
                sorted(value["summary"]["basename"] for value in selected.values())
            )
            # M1 may replace its own lease pointer in a sibling subtree while
            # we retain these input-file sharing pins. Directory write sharing
            # permits that operation; neither ancestry nor input files allow
            # delete/rename sharing, and the inputs still deny write sharing.
            with _pins(self.root, roster, check, allow_directory_write_sharing=True):
                files = []
                for choice_id, item in selected.items():
                    check()
                    row = item["summary"]
                    path = self.root / row["basename"]
                    _require(_stamp(path) == item["identity"], "INTAKE_INBOX_CHANGED")
                    payload = read_bounded_regular_file(
                        path, maximum_bytes=MAX_FILE_BYTES
                    )
                    _require(
                        len(payload) == row["payload_bytes"]
                        and digest(payload) == row["payload_sha256"]
                        and _media(path.name, payload) == row["media_type"]
                        and _stamp(path) == item["identity"],
                        "INTAKE_INBOX_CHANGED",
                    )
                    files.append(
                        IntakeInboxFile(
                            choice_id, path.name, row["media_type"], payload
                        )
                    )
                self._source(check)
                yield tuple(files)
                self._source(check)
                for item in selected.values():
                    _require(
                        _stamp(self.root / item["summary"]["basename"])
                        == item["identity"],
                        "INTAKE_INBOX_CHANGED",
                    )
            self._source(check)
        finally:
            self._operation_lock.release()
