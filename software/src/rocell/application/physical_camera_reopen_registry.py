"""Bounded camera-store metadata discovery, never an M1 or device opener."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from itertools import islice
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
from typing import Any, Callable, Iterator
import uuid

from .commissioning_camera_persistence import physical_camera_source_binding
from .physical_onboarding_durability import (
    PhysicalOnboardingDurabilityError,
    parse_durability_qualification_report,
    read_bounded_regular_file,
    safe_root,
)
from .physical_onboarding_m1 import M1CellDescriptor, PhysicalOnboardingM1Error
from .physical_onboarding_v2 import _parse_header
from .wizard_diagnostic_coordinator import source_fingerprint
from .wizard_diagnostic_export import _directory_guard

SCHEMA = "rocell.physical_camera_reopen_registry.v1"
DESCRIPTOR_SCHEMA = "rocell.physical_camera_store_descriptor.v1"
MAX_STORES = 32
MAX_STORE_ENTRIES = 128
MAX_METADATA_BYTES = 16 * 1024
MAX_DESCRIPTOR_BYTES = 32 * 1024
_LAUNCH = re.compile(r"wizard-[0-9a-f]{32}\Z")
_CELL = re.compile(r"wizard-physical-camera-[0-9a-f]{16}\Z")
_SESSION = re.compile(r"physical-camera-[0-9a-f]{32}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MEANING = (
    "Metadata discovery only. Original M1 storage, evidence, source and physical "
    "prerequisites must be independently verified; no device is opened or replayed."
)
_MESSAGES = {
    "NO_STORE_ROOT": "The assigned camera-store root does not exist; nothing was created.",
    "UNRECOGNIZED_ENTRY": "An entry is not an original camera launch directory.",
    "UNSAFE_PATH": "A retained path is unavailable, linked, reparsed or not a regular owned metadata path.",
    "METADATA_LIMIT": "Store metadata exceeds its bounded file or entry budget.",
    "AMBIGUOUS_STORE": "Exactly one original camera cell and session are required.",
    "INVALID_METADATA": "Original canonical camera metadata is missing, malformed or contradictory.",
    "DOMAIN_MISMATCH": "Metadata does not describe the distinct physical-camera storage domain.",
    "LINEAGE_MISMATCH": "Original camera cell/session identifiers do not match their launch and source.",
    "METADATA_CHANGED": "Original metadata or file identity changed; discover again without replay.",
    "SOURCE_CHANGED": "The original current-source snapshot changed; no store was selected.",
    "CANCELLED": "Discovery or selected-store verification was cancelled; no automatic replay.",
    "DEADLINE_EXPIRED": "The original finite metadata-verification deadline expired.",
    "DISCOVERY_LIMIT": "The assigned root exceeds the 32-entry discovery budget.",
    "REGISTRY_INVALIDATED": "Current discovery choices were explicitly invalidated.",
    "INVALID_REQUEST": "An exact server-assigned registry request is required.",
    "REGISTRY_BUSY": "Another registry operation owns the current selection scope.",
    "STALE_CHOICE": "The opaque choice does not belong to the current discovery snapshot.",
}


class PhysicalCameraReopenError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(_MESSAGES[code])


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PhysicalCameraReopenError(code)


def _json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        _require(key not in result, "INVALID_METADATA")
        result[key] = value
    return result


def _stamp(path: Path, *, directory: bool) -> dict[str, Any]:
    value = path.stat(follow_symlinks=False)
    _require(
        not getattr(value, "st_file_attributes", 0) & 0x400
        and not stat.S_ISLNK(value.st_mode)
        and (stat.S_ISDIR(value.st_mode) if directory else stat.S_ISREG(value.st_mode))
        and (directory or value.st_nlink == 1),
        "UNSAFE_PATH",
    )
    # File IDs can exceed JavaScript/signed-64-bit integers; retain decimal text.
    result: dict[str, Any] = {"device": str(value.st_dev), "file_id": str(value.st_ino)}
    if not directory:
        _require(0 < value.st_size <= MAX_METADATA_BYTES, "METADATA_LIMIT")
        result.update(
            bytes=value.st_size, mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns
        )
    return result


def _entries(
    path: Path, maximum: int, *, overflow: str = "METADATA_LIMIT"
) -> list[Path]:
    safe_root(path, label="camera discovery directory")
    values = list(islice(path.iterdir(), maximum + 1))
    _require(len(values) <= maximum, overflow)
    return sorted(values, key=lambda item: item.name)


def _metadata(
    path: Path, *, pretty: bool, check: Callable[[], None]
) -> tuple[dict[str, Any], dict[str, Any]]:
    check()
    before = _stamp(path, directory=False)
    payload = read_bounded_regular_file(path, maximum_bytes=MAX_METADATA_BYTES)
    check()
    _require(before == _stamp(path, directory=False), "METADATA_CHANGED")
    value = json.loads(payload.decode("ascii"), object_pairs_hook=_pairs)
    _require(type(value) is dict, "INVALID_METADATA")
    canonical = (
        json.dumps(
            value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False
        ).encode("ascii")
        if pretty
        else _json(value)
    ) + b"\n"
    _require(canonical == payload, "INVALID_METADATA")
    return value, {**before, "sha256": _hash(payload)}


@dataclass(frozen=True, slots=True)
class PhysicalCameraStoreDescriptor:
    """Immutable server-side discovery data, not an independently issued permit."""

    payload: bytes

    def __post_init__(self) -> None:
        try:
            self._validate()
        except PhysicalCameraReopenError:
            raise
        except (
            ValueError,
            TypeError,
            KeyError,
            RecursionError,
            PhysicalOnboardingM1Error,
            PhysicalOnboardingDurabilityError,
        ) as error:
            raise PhysicalCameraReopenError("INVALID_METADATA") from error

    def _validate(self) -> None:
        _require(
            type(self.payload) is bytes
            and 0 < len(self.payload) <= MAX_DESCRIPTOR_BYTES,
            "INVALID_METADATA",
        )
        value = json.loads(self.payload.decode("ascii"), object_pairs_hook=_pairs)
        _require(
            type(value) is dict and _json(value) == self.payload, "INVALID_METADATA"
        )
        _require(
            value.get("schema") == DESCRIPTOR_SCHEMA
            and value.get("physical_authority") is False,
            "INVALID_METADATA",
        )
        _require(
            set(value)
            == {
                "schema",
                "workspace",
                "directory",
                "current_launch_id",
                "origin_launch_id",
                "workspace_source_sha256",
                "source_binding_sha256",
                "cell_id",
                "session_id",
                "header_sha256",
                "cell_sha256",
                "anchor_sha256",
                "source_matches",
                "directory_identities",
                "metadata_files",
                "metadata",
                "physical_authority",
            },
            "INVALID_METADATA",
        )
        for name, pattern in (
            ("current_launch_id", _LAUNCH),
            ("origin_launch_id", _LAUNCH),
            ("cell_id", _CELL),
            ("session_id", _SESSION),
            *(
                (name, _SHA)
                for name in (
                    "workspace_source_sha256",
                    "source_binding_sha256",
                    "header_sha256",
                    "cell_sha256",
                    "anchor_sha256",
                )
            ),
        ):
            _require(
                type(value[name]) is str and pattern.fullmatch(value[name]) is not None,
                "INVALID_METADATA",
            )
        _require(type(value["source_matches"]) is bool, "INVALID_METADATA")
        for name in ("workspace", "directory"):
            _require(
                type(value[name]) is str and 0 < len(value[name]) <= 4096,
                "INVALID_METADATA",
            )
        workspace, directory = Path(value["workspace"]), Path(value["directory"])
        _require(
            workspace.is_absolute()
            and workspace != Path(workspace.anchor)
            and ".." not in workspace.parts
            and not str(workspace).startswith(("\\\\", "//"))
            and directory
            == workspace
            / "software/runs/physical-camera-acquisition"
            / value["origin_launch_id"],
            "INVALID_METADATA",
        )
        metadata = value["metadata"]
        _require(
            type(metadata) is dict and set(metadata) == {"header", "cell", "anchor"},
            "INVALID_METADATA",
        )
        header = _parse_header(metadata["header"])
        cell = M1CellDescriptor.from_dict(metadata["cell"])
        anchor = parse_durability_qualification_report(
            _json(metadata["anchor"]) + b"\n"
        )
        _require(
            header.mode == "PHYSICAL_DIAGNOSTIC"
            and header.cell_id == cell.cell_id == value["cell_id"]
            and header.session_id == value["session_id"]
            and header.source_binding_sha256
            == cell.source_binding_sha256
            == anchor.source_binding_sha256
            == value["source_binding_sha256"]
            and header.header_sha256 == value["header_sha256"]
            and cell.cell_sha256 == value["cell_sha256"]
            and header.durability_qualification_sha256
            == cell.durability_qualification_sha256
            == anchor.report_sha256
            == value["anchor_sha256"]
            and anchor.root_sha256 == _hash(str(directory).encode("utf-8"))
            and anchor.qualified_for_effects is True,
            "INVALID_METADATA",
        )
        matches = header.source_binding_sha256 == physical_camera_source_binding(
            value["workspace_source_sha256"]
        )
        _require(value["source_matches"] is matches, "INVALID_METADATA")
        if matches:
            lineage = _hash(
                _json(
                    {
                        "launch": value["origin_launch_id"],
                        "source": value["workspace_source_sha256"],
                    }
                )
            )
            _require(
                cell.cell_id == "wizard-physical-camera-" + lineage[:16]
                and header.session_id == "physical-camera-" + lineage[16:48],
                "LINEAGE_MISMATCH",
            )
        session = Path("onboarding-" + header.session_id)
        cell_path = Path("cells") / ("cell-" + cell.cell_key_sha256)
        files = value["metadata_files"]
        _require(type(files) is list and len(files) == 3, "INVALID_METADATA")
        for index, (name, relative) in enumerate(
            (
                ("header", session / "header.json"),
                ("cell", cell_path / "cell.json"),
                ("anchor", Path("durability-anchor.json")),
            )
        ):
            row = files[index]
            _require(
                type(row) is dict
                and set(row)
                == {
                    "relative_path",
                    "device",
                    "file_id",
                    "bytes",
                    "mtime_ns",
                    "ctime_ns",
                    "sha256",
                },
                "INVALID_METADATA",
            )
            raw = (
                json.dumps(
                    metadata[name],
                    sort_keys=True,
                    indent=2,
                    ensure_ascii=True,
                    allow_nan=False,
                ).encode("ascii")
                if index == 0
                else _json(metadata[name])
            ) + b"\n"
            _require(
                row["relative_path"] == str(relative)
                and row["sha256"] == _hash(raw)
                and type(row["bytes"]) is int
                and row["bytes"] == len(raw) <= MAX_METADATA_BYTES
                and all(
                    type(row[key]) is int and 0 <= row[key] < 2**63
                    for key in ("mtime_ns", "ctime_ns")
                ),
                "INVALID_METADATA",
            )
        directories = value["directory_identities"]
        expected_paths = (
            ".",
            str(Path(value["origin_launch_id"])),
            str(Path(value["origin_launch_id"]) / "cells"),
            str(Path(value["origin_launch_id"]) / session),
            str(Path(value["origin_launch_id"]) / cell_path),
        )
        _require(
            type(directories) is list and len(directories) == 5, "INVALID_METADATA"
        )
        for row, expected in zip(directories, expected_paths):
            _require(
                type(row) is dict
                and set(row) == {"path", "device", "file_id"}
                and row["path"] == expected,
                "INVALID_METADATA",
            )
        for row in files + directories:
            _require(
                all(
                    type(row[key]) is str
                    and re.fullmatch(r"[0-9]{1,128}", row[key]) is not None
                    for key in ("device", "file_id")
                ),
                "INVALID_METADATA",
            )

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.payload)

    @property
    def descriptor_sha256(self) -> str:
        return _hash(self.payload)

    @property
    def directory(self) -> Path:
        return Path(self.to_dict()["directory"])

    @property
    def origin_launch_id(self) -> str:
        return str(self.to_dict()["origin_launch_id"])

    @property
    def cell_id(self) -> str:
        return str(self.to_dict()["cell_id"])

    @property
    def session_id(self) -> str:
        return str(self.to_dict()["session_id"])

    @property
    def workspace_source_sha256(self) -> str:
        return str(self.to_dict()["workspace_source_sha256"])

    @property
    def source_binding_sha256(self) -> str:
        return str(self.to_dict()["source_binding_sha256"])

    @property
    def header_sha256(self) -> str:
        return str(self.to_dict()["header_sha256"])


class PhysicalCameraReopenRegistry:
    def __init__(
        self, workspace: Path, *, current_launch_id: str, source_sha256: str
    ) -> None:
        _require(
            isinstance(workspace, Path)
            and workspace.is_absolute()
            and workspace != Path(workspace.anchor)
            and ".." not in workspace.parts
            and not str(workspace).startswith(("\\\\", "//"))
            and len(str(workspace)) <= 2048
            and type(current_launch_id) is str
            and _LAUNCH.fullmatch(current_launch_id) is not None
            and type(source_sha256) is str
            and _SHA.fullmatch(source_sha256) is not None
            and source_sha256 != "0" * 64,
            "INVALID_REQUEST",
        )
        self._workspace = workspace
        self._current_launch_id = current_launch_id
        self._source_sha256 = source_sha256
        self._lock = threading.RLock()
        self._operation_lock = threading.Lock()
        self._generation = 0
        self._descriptors: dict[str, PhysicalCameraStoreDescriptor] = {}
        self._cached = self._empty("NOT_DISCOVERED")

    @property
    def workspace(self) -> Path:
        return self._workspace

    @property
    def current_launch_id(self) -> str:
        return self._current_launch_id

    @property
    def source_sha256(self) -> str:
        return self._source_sha256

    @property
    def root(self) -> Path:
        return self.workspace / "software/runs/physical-camera-acquisition"

    def _empty(self, status: str) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "status": status,
            "current_launch_id": self.current_launch_id,
            "source_sha256": self.source_sha256,
            "discovery_sha256": None,
            "stores": [],
            "issues": [],
            "invalidation_reason": None,
            "physical_authority": False,
            "device_io_performed": False,
            "meaning": _MEANING,
        }

    def view(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(_json(self._cached))

    def invalidate(self, reason: str = "REGISTRY_INVALIDATED") -> None:
        _require(type(reason) is str and reason in _MESSAGES, "INVALID_REQUEST")
        with self._lock:
            self._generation += 1
            self._descriptors.clear()
            self._cached = self._empty("INVALIDATED")
            self._cached["invalidation_reason"] = reason

    def choices(self) -> list[dict[str, str]]:
        return [
            {
                "value": row["choice_id"],
                "label": row["origin_launch_id"] + " / " + row["session_id"][-12:],
            }
            for row in self.view()["stores"]
            if row["selectable"]
        ]

    def preview(self, choice_id: str) -> dict[str, Any]:
        with self._lock:
            _require(
                type(choice_id) is str and choice_id in self._descriptors,
                "STALE_CHOICE",
            )
            row = next(
                item
                for item in self._cached["stores"]
                if item["choice_id"] == choice_id
            )
            return json.loads(
                _json(
                    {
                        **row,
                        "discovery_sha256": self._cached["discovery_sha256"],
                        "current_launch_id": self.current_launch_id,
                        "source_sha256": self.source_sha256,
                    }
                )
            )

    def descriptor(self, choice_id: str) -> PhysicalCameraStoreDescriptor:
        """Pure server-only copy, captured before entering an explicit scope.

        This is not a browser path resolver. Revoking opaque choices does not
        mutate a descriptor already retained by the trusted setup service.
        """
        with self._lock:
            _require(
                type(choice_id) is str and choice_id in self._descriptors,
                "STALE_CHOICE",
            )
            return PhysicalCameraStoreDescriptor(self._descriptors[choice_id].payload)

    def _checks(
        self, cancellation: threading.Event, deadline_ns: int, maximum_s: int
    ) -> Callable[[], None]:
        started = time.monotonic_ns()
        _require(
            type(cancellation) is threading.Event
            and type(deadline_ns) is int
            and started < deadline_ns <= started + maximum_s * 1_000_000_000,
            "INVALID_REQUEST",
        )
        with self._lock:
            generation = self._generation
        last = started

        def check() -> None:
            nonlocal last
            _require(not cancellation.is_set(), "CANCELLED")
            now = time.monotonic_ns()
            _require(last <= now < deadline_ns, "DEADLINE_EXPIRED")
            last = now
            with self._lock:
                _require(generation == self._generation, "STALE_CHOICE")

        return check

    def _source_check(self, check: Callable[[], None]) -> None:
        check()
        _require(
            source_fingerprint(self.workspace) == self.source_sha256, "SOURCE_CHANGED"
        )
        check()

    def _read_store(
        self, directory: Path, check: Callable[[], None]
    ) -> PhysicalCameraStoreDescriptor:
        _require(
            directory.parent == self.root
            and _LAUNCH.fullmatch(directory.name) is not None,
            "UNRECOGNIZED_ENTRY",
        )
        check()
        safe_root(directory, label="original camera store")
        entries = _entries(directory, MAX_STORE_ENTRIES)
        for item in entries:
            value = item.stat(follow_symlinks=False)
            _require(
                not stat.S_ISLNK(value.st_mode)
                and not getattr(value, "st_file_attributes", 0) & 0x400,
                "UNSAFE_PATH",
            )
            _require(
                stat.S_ISDIR(value.st_mode)
                or (stat.S_ISREG(value.st_mode) and value.st_nlink == 1),
                "UNSAFE_PATH",
            )
        sessions = [item for item in entries if item.name.startswith("onboarding-")]
        cells = _entries(directory / "cells", 2)
        _require(len(sessions) == len(cells) == 1, "AMBIGUOUS_STORE")
        session, cell = sessions[0], cells[0]
        directories = (self.root, directory, directory / "cells", session, cell)
        before = [
            {"path": str(path.relative_to(self.root)), **_stamp(path, directory=True)}
            for path in directories
        ]
        paths = (
            session / "header.json",
            cell / "cell.json",
            directory / "durability-anchor.json",
        )
        observed = [
            _metadata(path, pretty=index == 0, check=check)
            for index, path in enumerate(paths)
        ]
        header = _parse_header(observed[0][0])
        descriptor = M1CellDescriptor.from_dict(observed[1][0])
        anchor = parse_durability_qualification_report(_json(observed[2][0]) + b"\n")
        _require(
            header.mode == "PHYSICAL_DIAGNOSTIC"
            and _CELL.fullmatch(header.cell_id) is not None
            and _SESSION.fullmatch(header.session_id) is not None
            and header.cell_id == descriptor.cell_id
            and header.source_binding_sha256
            == descriptor.source_binding_sha256
            == anchor.source_binding_sha256
            and header.durability_qualification_sha256
            == descriptor.durability_qualification_sha256
            == anchor.report_sha256
            and session.name == "onboarding-" + header.session_id
            and cell.name == "cell-" + descriptor.cell_key_sha256
            and anchor.root_sha256 == _hash(str(directory).encode("utf-8"))
            and anchor.qualified_for_effects is True,
            "DOMAIN_MISMATCH",
        )
        matches = header.source_binding_sha256 == physical_camera_source_binding(
            self.source_sha256
        )
        if matches:
            lineage = _hash(
                _json({"launch": directory.name, "source": self.source_sha256})
            )
            _require(
                header.cell_id == "wizard-physical-camera-" + lineage[:16]
                and header.session_id == "physical-camera-" + lineage[16:48],
                "LINEAGE_MISMATCH",
            )
        check()
        after = [
            {"path": str(path.relative_to(self.root)), **_stamp(path, directory=True)}
            for path in directories
        ]
        _require(before == after, "METADATA_CHANGED")
        _require(
            observed
            == [
                _metadata(path, pretty=index == 0, check=check)
                for index, path in enumerate(paths)
            ],
            "METADATA_CHANGED",
        )
        return PhysicalCameraStoreDescriptor(
            _json(
                {
                    "schema": DESCRIPTOR_SCHEMA,
                    "workspace": str(self.workspace),
                    "directory": str(directory),
                    "current_launch_id": self.current_launch_id,
                    "origin_launch_id": directory.name,
                    "workspace_source_sha256": self.source_sha256,
                    "source_binding_sha256": header.source_binding_sha256,
                    "cell_id": header.cell_id,
                    "session_id": header.session_id,
                    "header_sha256": header.header_sha256,
                    "cell_sha256": descriptor.cell_sha256,
                    "anchor_sha256": anchor.report_sha256,
                    "source_matches": matches,
                    "directory_identities": before,
                    "metadata_files": [
                        {"relative_path": str(path.relative_to(directory)), **item[1]}
                        for path, item in zip(paths, observed)
                    ],
                    "metadata": {
                        "header": observed[0][0],
                        "cell": observed[1][0],
                        "anchor": observed[2][0],
                    },
                    "physical_authority": False,
                }
            )
        )

    @staticmethod
    def _issue(code: str, directory: Path | None = None) -> dict[str, Any]:
        label = (
            directory.name
            if directory is not None and _LAUNCH.fullmatch(directory.name)
            else None
        )
        return {"store_label": label, "code": code, "meaning": _MESSAGES[code]}

    def discover(
        self, *, cancellation: threading.Event, deadline_ns: int
    ) -> dict[str, Any]:
        _require(self._operation_lock.acquire(blocking=False), "REGISTRY_BUSY")
        try:
            with self._lock:
                self._generation += 1
                self._descriptors.clear()
                self._cached = self._empty("HELD")
            check = self._checks(cancellation, deadline_ns, 30)
            self._source_check(check)
            rows, issues, descriptors = [], [], {}
            if not os.path.lexists(self.root):
                issues.append(self._issue("NO_STORE_ROOT"))
            else:
                with _directory_guard(self.root):
                    entries = _entries(
                        self.root, MAX_STORES, overflow="DISCOVERY_LIMIT"
                    )
                    for directory in entries:
                        check()
                        try:
                            item = self._read_store(directory, check)
                        except PhysicalCameraReopenError as error:
                            if error.code in {
                                "CANCELLED",
                                "DEADLINE_EXPIRED",
                                "STALE_CHOICE",
                            }:
                                raise
                            issues.append(self._issue(error.code, directory))
                            continue
                        except (
                            OSError,
                            ValueError,
                            TypeError,
                            KeyError,
                            PhysicalOnboardingM1Error,
                            PhysicalOnboardingDurabilityError,
                        ):
                            issues.append(self._issue("INVALID_METADATA", directory))
                            continue
                        document = item.to_dict()
                        matches = document["source_matches"]
                        token = "reopen-" + uuid.uuid4().hex if matches else None
                        if token is not None:
                            descriptors[token] = item
                        rows.append(
                            {
                                "choice_id": token,
                                "origin_launch_id": item.origin_launch_id,
                                "cell_id": item.cell_id,
                                "session_id": item.session_id,
                                "source_binding_sha256": item.source_binding_sha256,
                                "header_sha256": item.header_sha256,
                                "descriptor_sha256": item.descriptor_sha256,
                                "source_matches": matches,
                                "selectable": matches,
                                "status": (
                                    "METADATA_DISCOVERED_NOT_OPENED"
                                    if matches
                                    else "SOURCE_DRIFT_HELD"
                                ),
                                "physical_authority": False,
                            }
                        )
                    check()
            self._source_check(check)
            with self._lock:
                check()
                self._descriptors = descriptors
                self._cached = {
                    **self._empty("DISCOVERED"),
                    "stores": rows,
                    "issues": issues,
                }
                self._cached["discovery_sha256"] = _hash(
                    _json({"snapshot": self._cached, "nonce": uuid.uuid4().hex})
                )
            return self.view()
        except BaseException as error:
            code = (
                error.code
                if type(error) is PhysicalCameraReopenError
                else "UNSAFE_PATH"
            )
            with self._lock:
                self._descriptors.clear()
                self._cached = {**self._empty("HELD"), "issues": [self._issue(code)]}
            if not isinstance(error, Exception):
                raise
            if type(error) is PhysicalCameraReopenError:
                raise
            raise PhysicalCameraReopenError(code) from error
        finally:
            self._operation_lock.release()

    @contextmanager
    def _guarded_original(
        self, original: PhysicalCameraStoreDescriptor, check: Callable[[], None]
    ) -> Iterator[PhysicalCameraStoreDescriptor]:
        self._source_check(check)
        with ExitStack() as guards:
            # M1 child lease-pointer ReplaceFileW compatibility, never DELETE sharing.
            for path in (
                original.directory,
                original.directory / ("onboarding-" + original.session_id),
                original.directory
                / "cells"
                / ("cell-" + original.to_dict()["metadata"]["cell"]["cell_key_sha256"]),
            ):
                guards.enter_context(
                    _directory_guard(path, allow_directory_write_sharing=True)
                )
                check()
            _require(
                self._read_store(original.directory, check).payload == original.payload,
                "METADATA_CHANGED",
            )
            self._source_check(check)
            yield original
            check()
            _require(
                self._read_store(original.directory, check).payload == original.payload,
                "METADATA_CHANGED",
            )
            self._source_check(check)
        check()

    def _original_descriptor(
        self, descriptor: PhysicalCameraStoreDescriptor, expected_descriptor_sha256: str
    ) -> PhysicalCameraStoreDescriptor:
        _require(type(descriptor) is PhysicalCameraStoreDescriptor, "INVALID_REQUEST")
        original = PhysicalCameraStoreDescriptor(descriptor.payload)
        _require(
            type(expected_descriptor_sha256) is str
            and _SHA.fullmatch(expected_descriptor_sha256) is not None
            and original.descriptor_sha256 == expected_descriptor_sha256,
            "METADATA_CHANGED",
        )
        document = original.to_dict()
        _require(
            document["workspace"] == str(self.workspace)
            and document["current_launch_id"] == self.current_launch_id
            and document["workspace_source_sha256"] == self.source_sha256
            and document["source_binding_sha256"]
            == physical_camera_source_binding(self.source_sha256)
            and document["source_matches"] is True
            and original.directory.parent == self.root,
            "DOMAIN_MISMATCH",
        )
        return original

    @contextmanager
    def revalidate_original(
        self,
        descriptor: PhysicalCameraStoreDescriptor,
        expected_descriptor_sha256: str,
        *,
        cancellation: threading.Event,
        deadline_ns: int,
    ) -> Iterator[PhysicalCameraStoreDescriptor]:
        """Explicit inspection of the exact already-retained original only.

        Does not revive/mint a choice, search for alternatives, open M1 or repair
        anything. The caller must supply its independent original descriptor
        digest and retain the distinction between inspection and acceptance.
        """
        _require(self._operation_lock.acquire(blocking=False), "REGISTRY_BUSY")
        consumer_failed = False
        try:
            check = self._checks(cancellation, deadline_ns, 120)
            original = self._original_descriptor(descriptor, expected_descriptor_sha256)
            with self._guarded_original(original, check):
                try:
                    yield original
                except BaseException:
                    consumer_failed = True
                    raise
        except BaseException as error:
            code = (
                error.code
                if type(error) is PhysicalCameraReopenError
                else "INVALID_METADATA"
            )
            self.invalidate(code)
            if (
                consumer_failed
                or not isinstance(error, Exception)
                or type(error) is PhysicalCameraReopenError
            ):
                raise
            raise PhysicalCameraReopenError(code) from error
        finally:
            self._operation_lock.release()

    @contextmanager
    def selected(
        self,
        choice_id: str,
        expected_discovery_sha256: str,
        *,
        cancellation: threading.Event,
        deadline_ns: int,
    ) -> Iterator[PhysicalCameraStoreDescriptor]:
        _require(self._operation_lock.acquire(blocking=False), "REGISTRY_BUSY")
        consumer_failed = False
        try:
            check = self._checks(cancellation, deadline_ns, 120)
            with self._lock:
                self.preview(choice_id)
                _require(
                    type(expected_discovery_sha256) is str
                    and expected_discovery_sha256 == self._cached["discovery_sha256"],
                    "STALE_CHOICE",
                )
                retained = self._descriptors[choice_id]
                original = self._original_descriptor(
                    retained, retained.descriptor_sha256
                )
            with self._guarded_original(original, check):
                try:
                    yield original
                except BaseException:
                    consumer_failed = True
                    raise
        except BaseException as error:
            code = (
                error.code
                if type(error) is PhysicalCameraReopenError
                else "INVALID_METADATA"
            )
            self.invalidate(code)
            if consumer_failed or not isinstance(error, Exception):
                raise
            if type(error) is PhysicalCameraReopenError:
                raise
            raise PhysicalCameraReopenError(code) from error
        finally:
            self._operation_lock.release()
