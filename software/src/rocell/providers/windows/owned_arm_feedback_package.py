"""Explicit deterministic packaging for the closed, hardware-incapable arm child.

This is a source-pinned development artifact, not a signed runtime or physical
qualification. Construction/deserialization is inert; only the explicit build
and revalidation functions read files. The archive isolates package namespaces
without replacing any actual feedback worker/backend implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any
import uuid
import zipfile

from .owned_worker_process import PinnedWorkerFile, decode_owned_json

LEGACY_SCHEMA = "rocell.owned_arm_runtime.v1"
SCHEMA = "rocell.owned_arm_runtime.v2"
MAX_PACKAGE_BYTES = 8 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024
CHILD_PATH = Path(__file__).with_name("_owned_arm_feedback_child.py")
_WORKSPACE = Path(__file__).parents[5]
_STUB = b'"""Isolated owned-arm child namespace; no application bootstrap."""\n'
NAMESPACES = (
    "rocell",
    "rocell/application",
    "rocell/arm",
    "rocell/providers",
    "rocell/providers/windows",
)
LEGACY_ROCELL_MODULES = (
    "application/physical_connection_contracts.py",
    "application/rehearsal_arm_feedback_evidence.py",
    "arm/protocol.py",
    "arm/feedback.py",
    "arm/feedback_wire.py",
    "providers/windows/arm_feedback_worker.py",
    "providers/windows/arm_nonpurging_adapter.py",
    "providers/windows/nonpurging_serial_api.py",
    "providers/windows/nonpurging_serial_backend.py",
    "providers/windows/owned_worker_process.py",
    "providers/windows/arm_owned_protocol.py",
)
ROCELL_MODULES = LEGACY_ROCELL_MODULES + (
    "application/arm_controller_resolution.py",
    "application/physical_device_inventory.py",
    "providers/windows/controller_metadata.py",
    "providers/windows/incapable_controller_metadata.py",
)
# Closed dependency roster, not a glob or arbitrary import-root interface.
PACKAGING_MODULES = (
    "__init__.py",
    "_elffile.py",
    "_manylinux.py",
    "_musllinux.py",
    "_parser.py",
    "_ranges.py",
    "_structures.py",
    "_tokenizer.py",
    "dependency_groups.py",
    "direct_url.py",
    "errors.py",
    "markers.py",
    "metadata.py",
    "pylock.py",
    "ranges.py",
    "requirements.py",
    "specifiers.py",
    "tags.py",
    "utils.py",
    "version.py",
)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _path(value: Any) -> Path:
    require(type(value) is str, "RUNTIME_PATH_REQUIRED")
    path = Path(value)
    require(
        path.is_absolute()
        and path != Path(path.anchor)
        and ".." not in path.parts
        and not value.startswith(("\\\\", "//"))
        and len(path.parts) <= 128
        and len(value) <= 4096
        and all(ord(char) >= 32 for char in value)
        and all(
            ":" not in part and part.rstrip(" .") == part for part in path.parts[1:]
        ),
        "RUNTIME_PATH_REQUIRED",
    )
    return path


def _plain(path: Path, *, directory: bool) -> None:
    for current in (*reversed(path.parents), path):
        item = current.lstat()
        require(
            not stat.S_ISLNK(item.st_mode)
            and not getattr(item, "st_file_attributes", 0) & 0x400,
            "RUNTIME_LINK_REJECTED",
        )
        if current != path or directory:
            require(stat.S_ISDIR(item.st_mode), "RUNTIME_DIRECTORY_REQUIRED")
        else:
            require(
                stat.S_ISREG(item.st_mode) and item.st_nlink == 1,
                "RUNTIME_REGULAR_FILE_REQUIRED",
            )


def _read(path: Path, maximum: int) -> bytes:
    _plain(path, directory=False)
    before = path.stat()
    require(0 < before.st_size <= maximum, "RUNTIME_FILE_BOUND")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require(
            (before.st_dev, before.st_ino, before.st_size)
            == (opened.st_dev, opened.st_ino, opened.st_size),
            "RUNTIME_FILE_CHANGED",
        )
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    _plain(path, directory=False)
    require(
        len(raw) == before.st_size
        and len(raw) <= maximum
        and (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        and path.stat().st_ino == before.st_ino,
        "RUNTIME_FILE_CHANGED",
    )
    return raw


def _pin(path: Path, raw: bytes, maximum: int) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "maximum_bytes": maximum,
    }


def pin_from_dict(value: Any) -> PinnedWorkerFile:
    require(
        type(value) is dict and set(value) == {"path", "sha256", "maximum_bytes"},
        "RUNTIME_PIN_SCHEMA",
    )
    return PinnedWorkerFile(
        _path(value["path"]), value["sha256"], value["maximum_bytes"]
    )


def _sources(workspace: Path) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    require(workspace == _WORKSPACE, "FIXED_WORKSPACE_REQUIRED")
    # Use the reviewed workspace environment, never an arbitrary imported
    # package location, PYTHONPATH, browser field or caller-provided roster.
    package_root = workspace / ".venv/Lib/site-packages/packaging"
    rows: list[dict[str, Any]] = []
    entries: dict[str, bytes] = {}
    for namespace in NAMESPACES:
        name = namespace + "/__init__.py"
        original = workspace / "software/src" / name
        raw = _read(original, MAX_FILE_BYTES)
        rows.append(
            {
                "name": name,
                "path": str(original),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "role": "NAMESPACE_SOURCE_ONLY",
                "archive_sha256": hashlib.sha256(_STUB).hexdigest(),
            }
        )
        entries[name] = _STUB
    for name, path in (
        *(
            ("rocell/" + name, workspace / "software/src/rocell" / name)
            for name in ROCELL_MODULES
        ),
        *(("packaging/" + name, package_root / name) for name in PACKAGING_MODULES),
    ):
        raw = _read(path, MAX_FILE_BYTES)
        sha = hashlib.sha256(raw).hexdigest()
        rows.append(
            {
                "name": name,
                "path": str(path),
                "sha256": sha,
                "bytes": len(raw),
                "role": "EXACT_SOURCE",
                "archive_sha256": sha,
            }
        )
        entries[name] = raw
    require(
        sum(map(len, entries.values())) <= MAX_PACKAGE_BYTES, "RUNTIME_PACKAGE_BOUND"
    )
    return sorted(rows, key=lambda row: row["name"]), entries


def _archive(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_STORED, allowZip64=False
    ) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system, info.external_attr = 3, 0o100444 << 16
            archive.writestr(info, entries[name])
    raw = output.getvalue()
    require(len(raw) <= MAX_PACKAGE_BYTES, "RUNTIME_PACKAGE_BOUND")
    return raw


@dataclass(frozen=True, slots=True)
class OwnedArmRuntime:
    """Owned bytes; structural reconstruction does not authenticate its source."""

    payload: bytes

    def __post_init__(self) -> None:
        doc = decode_owned_json(self.payload, maximum=32 * 1024)
        require(
            canonical(doc) == self.payload
            and set(doc)
            == {
                "schema",
                "workspace",
                "workspace_source_sha256",
                "source_closure_sha256",
                "files",
                "executable",
                "child",
                "package",
                "physical_authority",
                "composition",
                "packaging_qualification",
                "namespace_isolation",
            }
            and doc["schema"] in (LEGACY_SCHEMA, SCHEMA)
            and doc["physical_authority"] is False
            and doc["composition"] == "INCAPABLE_NONPURGING_ARM_WORKER"
            and doc["packaging_qualification"]
            == "SOURCE_PINNED_DEVELOPMENT_NOT_TRUSTED_RELEASE"
            and doc["namespace_isolation"]
            == "FIXED_INERT_STUBS_ORIGINAL_HASHES_RETAINED",
            "RUNTIME_SCHEMA",
        )
        _path(doc["workspace"])
        require(
            type(doc["workspace_source_sha256"]) is str
            and re.fullmatch(r"[0-9a-f]{64}", doc["workspace_source_sha256"])
            is not None,
            "RUNTIME_SOURCE_HASH",
        )
        expected_names = sorted(
            [n + "/__init__.py" for n in NAMESPACES]
            + [
                "rocell/" + n
                for n in (
                    ROCELL_MODULES if doc["schema"] == SCHEMA else LEGACY_ROCELL_MODULES
                )
            ]
            + ["packaging/" + n for n in PACKAGING_MODULES]
        )
        rows = doc["files"]
        require(
            type(rows) is list and len(rows) == len(expected_names), "RUNTIME_ROSTER"
        )
        for row, name in zip(rows, expected_names, strict=True):
            require(
                type(row) is dict
                and set(row)
                == {"name", "path", "sha256", "bytes", "role", "archive_sha256"}
                and row["name"] == name,
                "RUNTIME_ROSTER",
            )
            _path(row["path"])
            require(
                type(row["bytes"]) is int
                and 0 < row["bytes"] <= MAX_FILE_BYTES
                and all(
                    type(row[k]) is str and re.fullmatch(r"[0-9a-f]{64}", row[k])
                    for k in ("sha256", "archive_sha256")
                ),
                "RUNTIME_ROSTER_BOUND",
            )
            stub = name in {n + "/__init__.py" for n in NAMESPACES}
            require(
                row["role"] == ("NAMESPACE_SOURCE_ONLY" if stub else "EXACT_SOURCE")
                and row["archive_sha256"]
                == (hashlib.sha256(_STUB).hexdigest() if stub else row["sha256"]),
                "RUNTIME_ROSTER_ROLE",
            )
        require(digest(rows) == doc["source_closure_sha256"], "RUNTIME_CLOSURE_HASH")
        for key in ("executable", "child", "package"):
            pin_from_dict(doc[key])
        require(
            doc["executable"]["maximum_bytes"] == 64 * 1024 * 1024
            and doc["child"]["maximum_bytes"] == MAX_FILE_BYTES
            and doc["package"]["maximum_bytes"] == MAX_PACKAGE_BYTES,
            "RUNTIME_PIN_BUDGET_MISMATCH",
        )
        require(
            Path(doc["child"]["path"])
            == Path(doc["workspace"])
            / "software/src/rocell/providers/windows/_owned_arm_feedback_child.py",
            "FIXED_CHILD_REQUIRED",
        )
        require(
            Path(doc["package"]["path"]).name == "runtime.zip",
            "FIXED_PACKAGE_NAME_REQUIRED",
        )

    def to_dict(self) -> dict[str, Any]:
        return decode_owned_json(self.payload, maximum=32 * 1024)

    @property
    def runtime_sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    @property
    def executable(self) -> PinnedWorkerFile:
        return pin_from_dict(self.to_dict()["executable"])

    @property
    def package(self) -> PinnedWorkerFile:
        return pin_from_dict(self.to_dict()["package"])

    @property
    def child(self) -> PinnedWorkerFile:
        return pin_from_dict(self.to_dict()["child"])


def prepare_owned_arm_runtime(
    workspace: Path, assigned_package_parent: Path
) -> OwnedArmRuntime:
    """Explicit bounded build. Each new UUID tree is retained; no overwrite/reuse."""
    from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
    from rocell.application.wizard_diagnostic_export import _directory_guard

    require(
        isinstance(workspace, Path) and workspace == _WORKSPACE,
        "FIXED_WORKSPACE_REQUIRED",
    )
    _path(str(assigned_package_parent))
    _plain(assigned_package_parent.parent, directory=True)
    with _directory_guard(assigned_package_parent.parent):
        assigned_package_parent.mkdir(exist_ok=True)
    _plain(assigned_package_parent, directory=True)
    source_before = source_fingerprint(workspace)
    rows, entries = _sources(workspace)
    package_raw = _archive(entries)
    executable = Path(getattr(sys, "_base_executable"))
    exe_raw, child_raw = _read(executable, 64 * 1024 * 1024), _read(
        CHILD_PATH, MAX_FILE_BYTES
    )
    require(source_fingerprint(workspace) == source_before, "WORKSPACE_SOURCE_CHANGED")
    directory = assigned_package_parent / ("arm-runtime-" + uuid.uuid4().hex)
    package = directory / "runtime.zip"
    runtime = OwnedArmRuntime(
        canonical(
            {
                "schema": SCHEMA,
                "workspace": str(workspace),
                "workspace_source_sha256": source_before,
                "source_closure_sha256": digest(rows),
                "files": rows,
                "executable": _pin(executable, exe_raw, 64 * 1024 * 1024),
                "child": _pin(CHILD_PATH, child_raw, MAX_FILE_BYTES),
                "package": _pin(package, package_raw, MAX_PACKAGE_BYTES),
                "composition": "INCAPABLE_NONPURGING_ARM_WORKER",
                "physical_authority": False,
                "packaging_qualification": "SOURCE_PINNED_DEVELOPMENT_NOT_TRUSTED_RELEASE",
                "namespace_isolation": "FIXED_INERT_STUBS_ORIGINAL_HASHES_RETAINED",
            }
        )
    )
    # Pin directory ancestry for publication; the manifest is written last.
    # This diagnostic package is still not qualified M1/power-loss persistence.
    with _directory_guard(assigned_package_parent):
        directory.mkdir(exist_ok=False)
        with _directory_guard(directory):
            for path, payload in (
                (package, package_raw),
                (directory / "runtime.json", runtime.payload),
            ):
                with path.open("xb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
            revalidate_owned_arm_runtime(runtime)
            require(
                source_fingerprint(workspace) == source_before,
                "WORKSPACE_SOURCE_CHANGED",
            )
    return runtime


def revalidate_owned_arm_runtime(runtime: OwnedArmRuntime) -> None:
    """Explicit file-only check; never refreshes pins or imports archive content."""
    require(type(runtime) is OwnedArmRuntime, "EXACT_RUNTIME_REQUIRED")
    doc = OwnedArmRuntime(runtime.payload).to_dict()
    # A historical descriptor is not eligible for a new read/launch cycle.
    require(doc["schema"] == SCHEMA, "ARM_RUNTIME_VERSION_HELD")
    require(
        Path(doc["workspace"]) == _WORKSPACE
        and runtime.child.path == CHILD_PATH
        and runtime.executable.path == Path(getattr(sys, "_base_executable")),
        "FIXED_RUNTIME_REQUIRED",
    )
    rows, entries = _sources(_WORKSPACE)
    require(
        rows == doc["files"] and digest(rows) == doc["source_closure_sha256"],
        "RUNTIME_SOURCE_CHANGED",
    )
    require(
        hashlib.sha256(_archive(entries)).hexdigest() == runtime.package.sha256,
        "RUNTIME_ARCHIVE_CHANGED",
    )
    for pin in (runtime.executable, runtime.child, runtime.package):
        require(
            hashlib.sha256(_read(pin.path, pin.maximum_bytes)).hexdigest()
            == pin.sha256,
            "RUNTIME_FILE_CHANGED",
        )
