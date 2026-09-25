"""Append-only, bounded diagnostic logs; deliberately not commissioning state.

These records aid debugging and export. They cannot advance an M1/v2 stage,
authorize a device, clear quarantine or resume an operation. Each application
launch receives a fresh namespace. A truncated/tampered log is rejected rather
than repaired or replayed.
"""

from __future__ import annotations

import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Mapping

from .wizard_diagnostic_coordinator import decode_diagnostic_json, require_regular_path
from .wizard_actions import WizardError
from .wizard_diagnostic_export import sanitize_diagnostic_record

_ID = re.compile(r"wizard-[a-f0-9]{32}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_FIELDS = {
    "schema",
    "sequence",
    "session_id",
    "source_sha256",
    "mode",
    "created_at_ns",
    "kind",
    "details",
    "previous_sha256",
    "physical_authority",
    "sha256",
}
MAX_EVENTS = 1000
MAX_EVENT_BYTES = 128 * 1024


def _encoded(value: Mapping[str, Any]) -> bytes:
    result = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()
    if len(result) > MAX_EVENT_BYTES:
        raise WizardError(
            "LOG_EVENT_LIMIT", "Diagnostic event exceeded its byte limit."
        )
    return result


class WizardDiagnosticLog:
    def __init__(
        self, root: Path, session_id: str, *, source_sha256: str, mode: str
    ) -> None:
        if type(session_id) is not str or not _ID.fullmatch(session_id):
            raise WizardError("INVALID_SESSION", "Invalid diagnostic session ID.")
        if type(source_sha256) is not str or not _SHA.fullmatch(source_sha256):
            raise WizardError(
                "INVALID_SOURCE", "Diagnostic source must be a SHA-256 digest."
            )
        if mode not in {"rehearsal", "physical"}:
            raise WizardError("INVALID_MODE", "Diagnostic mode is not registered.")
        self.root = Path(os.path.abspath(root))
        self.session_id = session_id
        self.source_sha256 = source_sha256
        self.mode = mode
        self.directory = self.root / session_id
        self._events: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self._created = False

    def _initialize(self) -> None:
        if self._created:
            require_regular_path(self.directory, directory=True)
            return
        require_regular_path(self.root.parent, directory=True)
        if not self.root.exists():
            self.root.mkdir()
        require_regular_path(self.root, directory=True)
        self.directory.mkdir(exist_ok=False)
        require_regular_path(self.directory, directory=True)
        self._created = True

    def append(self, kind: str, details: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            if (
                type(kind) is not str
                or not 1 <= len(kind) <= 96
                or any(ord(c) < 32 for c in kind)
            ):
                raise WizardError(
                    "INVALID_LOG_EVENT", "Diagnostic event kind must be bounded text."
                )
            if not isinstance(details, Mapping):
                raise WizardError(
                    "INVALID_LOG_EVENT", "Diagnostic event details must be a mapping."
                )
            if len(self._events) >= MAX_EVENTS:
                raise WizardError(
                    "SESSION_LOG_FULL",
                    "Export this diagnostic session and start a new one.",
                )
            core = {
                "schema": "rocell.wizard_diagnostic_event.v1",
                "sequence": len(self._events),
                "session_id": self.session_id,
                "source_sha256": self.source_sha256,
                "mode": self.mode,
                "created_at_ns": time.time_ns(),
                "kind": kind,
                "details": sanitize_diagnostic_record(dict(details)),
                "previous_sha256": (
                    self._events[-1]["sha256"] if self._events else "0" * 64
                ),
                "physical_authority": False,
            }
            record = {**core, "sha256": hashlib.sha256(_encoded(core)).hexdigest()}
            data = _encoded(record)
            self._initialize()
            target = self.directory / f"event-{len(self._events):08d}.json"
            # Exclusive publication cannot overwrite earlier logs. A process
            # interruption may leave a partial final record; verification holds
            # the whole diagnostic log in that case. It never resumes work.
            with target.open("xb") as stream:
                if stream.write(data) != len(data):
                    raise OSError("Short diagnostic log write")
                stream.flush()
                os.fsync(stream.fileno())
            # The retained projection must be detached from every caller-owned
            # nested object, including future sanitizer implementation changes.
            self._events.append(json.loads(data))
            return json.loads(data)

    def events(self) -> list[dict[str, Any]]:
        with self._lock:
            return json.loads(json.dumps(self._events))

    @staticmethod
    def verify(directory: Path) -> dict[str, Any]:
        directory = require_regular_path(directory, directory=True)
        if not _ID.fullmatch(directory.name):
            raise WizardError("INVALID_SESSION", "Not a diagnostic log directory.")
        files = sorted(islice(directory.iterdir(), MAX_EVENTS + 1))
        if not files or len(files) > MAX_EVENTS:
            raise WizardError("INVALID_LOG", "Empty or oversized diagnostic log.")
        records = []
        previous = "0" * 64
        source: str | None = None
        mode: str | None = None
        for index, path in enumerate(files):
            if path.name != f"event-{index:08d}.json":
                raise WizardError("INVALID_LOG", "Unexpected diagnostic log entry.")
            require_regular_path(path, directory=False)
            if path.stat().st_size > MAX_EVENT_BYTES:
                raise WizardError("INVALID_LOG", "Oversized event.")
            try:
                with path.open("rb") as stream:
                    raw = stream.read(MAX_EVENT_BYTES + 1)
                item = decode_diagnostic_json(raw, maximum=MAX_EVENT_BYTES)
                if type(item) is not dict or item.keys() != _FIELDS:
                    raise ValueError("Wrong event fields")
                if (
                    type(item["sequence"]) is not int
                    or type(item["created_at_ns"]) is not int
                    or not 0 < item["created_at_ns"] < 2**63
                ):
                    raise ValueError("Wrong event sequence or timestamp")
                if (
                    type(item["kind"]) is not str
                    or not 1 <= len(item["kind"]) <= 96
                    or any(ord(c) < 32 for c in item["kind"])
                ):
                    raise ValueError("Wrong event kind")
                if type(item["details"]) is not dict or item["mode"] not in {
                    "rehearsal",
                    "physical",
                }:
                    raise ValueError("Wrong event details or mode")
                for key in ("source_sha256", "previous_sha256", "sha256"):
                    if type(item[key]) is not str or not _SHA.fullmatch(item[key]):
                        raise ValueError("Wrong event digest")
                digest = item.pop("sha256")
                if _encoded({**item, "sha256": digest}) != raw:
                    raise ValueError("Noncanonical event")
                if digest != hashlib.sha256(_encoded(item)).hexdigest():
                    raise ValueError("Hash mismatch")
                if (
                    item["sequence"] != index
                    or item["previous_sha256"] != previous
                    or item["session_id"] != directory.name
                ):
                    raise ValueError("Chain mismatch")
                if (
                    item["schema"] != "rocell.wizard_diagnostic_event.v1"
                    or item["physical_authority"] is not False
                ):
                    raise ValueError("Wrong event schema or authority")
                if index and (item["source_sha256"] != source or item["mode"] != mode):
                    raise ValueError("Mixed session sources")
                source, mode = item["source_sha256"], item["mode"]
                records.append({**item, "sha256": digest})
                previous = digest
            except (
                KeyError,
                ValueError,
                TypeError,
                UnicodeError,
                RecursionError,
            ) as exc:
                raise WizardError(
                    "INVALID_LOG", f"Diagnostic event {index} failed verification."
                ) from exc
        return {
            "schema": "rocell.wizard_log_verification.v1",
            "status": "VERIFIED_DIAGNOSTIC_ONLY",
            "session_id": directory.name,
            "events": records,
            "head_sha256": previous,
            "physical_authority": False,
            "replay_allowed": False,
        }
