"""Bounded installed-file observations for two dormant native camera builds.

This module never constructs a worker or grants dispatch authority. The fixed
historical probe and current capture records are separate claims: matching a
binary is not matching today's source, received hardware or a qualified runtime.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
from typing import Any, Callable

from .wizard_diagnostic_coordinator import require_regular_path, source_fingerprint
from rocell.providers.windows.native_camera_registration import (
    NativeCameraRuntimeRegistration,
)
from rocell.providers.windows.native_camera_capture_registration import (
    NativeCameraCaptureRuntimeRegistration,
)
from rocell.providers.windows.native_camera_capture_protocol import local_capture_path

SCHEMA = "rocell.physical_camera_runtime_inspection.v1"
SUMMARY_SCHEMA = "rocell.physical_camera_runtime_inspection_summary.v1"
MAX_REPORT_BYTES = 128 * 1024
MAX_NATIVE_BYTES = 32 * 1024 * 1024
MAX_READ_CALLS = 512
INSPECTION_SECONDS = 30
_PREFIX = "software/native/windows_camera/"
_COMMON_SOURCES = (
    "camera_worker.cpp",
    "identity_metadata.cpp",
    "identity_metadata.h",
    "admission_protocol.h",
    "admission_protocol.cpp",
    "admission_entry.h",
    "admission_entry.cpp",
)
_SOURCES = {
    "probe": (
        *_COMMON_SOURCES,
        "CMakeLists.txt",
        "admission_protocol_tests.cpp",
        "admission_entry_tests.cpp",
    ),
    "capture": (
        *_COMMON_SOURCES,
        "capture/CMakeLists.txt",
        "capture_admission_protocol.h",
        "capture_admission_protocol.cpp",
        "capture_admission_entry.h",
        "capture_admission_entry.cpp",
        "capture_admission_protocol_tests.cpp",
        "capture_admission_entry_tests.cpp",
        "capture/admission_entry_wire_test.py",
    ),
}
_ARTIFACTS = {
    "probe": (
        "build-owned/Release/rocell_windows_camera.exe",
        "build-owned/Release/rocell_camera_admission_tests.exe",
        "build-owned/Release/rocell_camera_admission_entry_tests.exe",
    ),
    "capture": (
        "build-owned-capture/Release/rocell_windows_camera.exe",
        "build-owned-capture/Release/rocell_windows_camera_probe_compile_check.exe",
        "build-owned-capture/Release/rocell_camera_capture_admission_tests.exe",
        "build-owned-capture/Release/rocell_camera_capture_admission_entry_tests.exe",
    ),
}
_RECORDS = {
    "probe": "owned_build_manifest.json",
    "capture": "owned_capture_build_manifest.json",
}
# Independent reviewed-development pins, never learned from files being checked.
# Tests may replace this private catalog only inside an isolated fixture scope.
_PINS = {
    "probe": {
        "helper": "e6072f26efa335ada46ef1459a66830a687b2d66c7ff45584aa4ac949eb027a1",
        "record": "705228b1595e1efeb2b8ceef171e3f6fdffad505b6e680b847cec352d712d7b6",
    },
    "capture": {
        "helper": "31d2f2742b18c0935b3d7af07f8058f129421871be00860a3d7768e1e940ae2f",
        "record": "b6b60e92b1f95487be7c9230ddade77827b64a30063377b2f41a66d526eda2a5",
    },
}
FIXED_PATHS = tuple(
    sorted(
        {_PREFIX + item for items in _SOURCES.values() for item in items}
        | {_PREFIX + item for items in _ARTIFACTS.values() for item in items}
        | {_PREFIX + item for item in _RECORDS.values()}
    )
)
_FALSE_FIELDS = (
    "dispatch_enabled",
    "driver_qualified",
    "hardware_qualified",
    "connected",
    "physical_authority",
)
_EFFECTS = {
    "process_start_count": 0,
    "device_open_count": 0,
    "metadata_inventory_count": 0,
    "serial_write_count": 0,
    "power_event_count": 0,
    "motion_command_count": 0,
    "contact_command_count": 0,
}
_LIMITATIONS = (
    "FILE_OBSERVATIONS_NOT_PINNED_EXECUTION_WINDOW",
    "SYNCHRONOUS_FILESYSTEM_CALLS_NOT_FORCIBLY_INTERRUPTIBLE",
    "HISTORICAL_PROBE_AND_CAPTURE_BUILDS_ARE_DISTINCT",
    "NO_NATIVE_HELPER_OR_DEVICE_EXECUTED",
    "RUNTIME_DRIVER_AND_RECEIVED_HARDWARE_QUALIFICATION_REQUIRED",
    "SOURCE_CHECKS_HAVE_SEPARATE_EXISTING_128MIB_PER_CHECK_BOUND",
)
_OBSERVATIONS = frozenset(
    {
        "OBSERVED",
        "MISSING",
        "UNREADABLE",
        "UNSAFE_PATH",
        "SIZE_LIMIT",
        "CHANGED_DURING_READ",
        "NOT_INSPECTED",
    }
)
_TERMINAL_ERRORS = frozenset(
    {
        "CANCELLED",
        "TIMED_OUT",
        "SOURCE_CHANGED",
        "SOURCE_CHECK_FAILED",
        "TOTAL_READ_LIMIT",
        "READ_CALL_LIMIT",
        "PROGRESS_FAILED",
    }
)


class PhysicalCameraRuntimeInspectionError(ValueError):
    def __init__(self, code: str, *, inspection_report: dict[str, Any] | None = None):
        super().__init__(code)
        self.code = code
        self._report = (
            None if inspection_report is None else _canonical(inspection_report)
        )

    @property
    def inspection_report(self) -> dict[str, Any] | None:
        return None if self._report is None else _decode(self._report)


def _require(ok: bool, code: str = "RUNTIME_INSPECTION_CONTRACT") -> None:
    if not ok:
        raise PhysicalCameraRuntimeInspectionError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _sha(value: Any) -> None:
    _require(
        type(value) is str
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
        and value != "0" * 64
    )


def _integer(value: Any, maximum: int = 2**63 - 1) -> None:
    _require(type(value) is int and 0 <= value <= maximum)


def _bounded(value: Any, depth: int = 0, nodes: list[int] | None = None) -> None:
    nodes = [0] if nodes is None else nodes
    nodes[0] += 1
    _require(depth <= 14 and nodes[0] <= 10000)
    if isinstance(value, dict):
        _require(type(value) is dict and len(value) <= 64)
        for key, child in value.items():
            _require(type(key) is str and len(key) <= 160)
            _bounded(child, depth + 1, nodes)
    elif isinstance(value, list):
        _require(type(value) is list and len(value) <= 64)
        for child in value:
            _bounded(child, depth + 1, nodes)
    elif type(value) is str:
        _require(len(value.encode("utf-8")) <= 16000)
    else:
        _require(value is None or type(value) is bool or type(value) is int)
        if type(value) is int:
            _integer(value)


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in values:
        _require(key not in output, "DUPLICATE_JSON_KEY")
        output[key] = value
    return output


def _decode(payload: bytes, maximum: int = MAX_REPORT_BYTES) -> dict[str, Any]:
    _require(
        type(payload) is bytes and 0 < len(payload) <= maximum, "REPORT_BYTE_LIMIT"
    )
    try:
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise PhysicalCameraRuntimeInspectionError("INVALID_JSON") from error
    _require(type(value) is dict)
    _bounded(value)
    return value


def _keys(value: Any, names: set[str]) -> None:
    _require(type(value) is dict and set(value) == names)


def _catalog_sha256() -> str:
    return hashlib.sha256(
        _canonical(
            {
                "schema": "rocell.physical_camera_development_runtime_pair.v1",
                "probe_helper": _PINS["probe"]["helper"],
                "probe_record": _PINS["probe"]["record"],
                "capture_helper": _PINS["capture"]["helper"],
                "capture_record": _PINS["capture"]["record"],
                "qualified": False,
            }
        )
    ).hexdigest()


def _candidates(
    workspace: Path, source: str, probe: Any, capture: Any
) -> dict[str, Any]:
    _sha(source)
    _require(
        isinstance(workspace, Path)
        and str(local_capture_path(str(workspace))) == str(workspace)
    )
    _require(
        type(probe) is NativeCameraRuntimeRegistration
        and type(capture) is NativeCameraCaptureRuntimeRegistration,
        "EXACT_RUNTIME_CANDIDATES_REQUIRED",
    )
    result = {}
    for purpose, candidate in (("probe", probe), ("capture", capture)):
        candidate.__post_init__()
        data = candidate.to_dict()
        _require(
            data["workspace"] == str(workspace)
            and data["source_sha256"] == source
            and data["catalog_sha256"] == _catalog_sha256(),
            "RUNTIME_CANDIDATE_CONTEXT",
        )
        _require(
            data["helper"]["sha256"] == _PINS[purpose]["helper"]
            and data["build_record"]["sha256"] == _PINS[purpose]["record"],
            "FIXED_RUNTIME_PINS_REQUIRED",
        )
        result[purpose] = data
    return result


def _specs() -> dict[str, tuple[str, int]]:
    source = {_PREFIX + name for names in _SOURCES.values() for name in names}
    records = {_PREFIX + name for name in _RECORDS.values()}
    _require(len(FIXED_PATHS) <= 40)
    return {
        path: (
            ("SOURCE", 1024 * 1024)
            if path in source
            else (
                ("BUILD_RECORD", 128 * 1024)
                if path in records
                else ("ARTIFACT", 8 * 1024 * 1024)
            )
        )
        for path in FIXED_PATHS
    }


def _manifest(raw: bytes, purpose: str) -> dict[str, Any]:
    """Only a pinned known record may supply expected hashes, never paths."""
    _require(
        hashlib.sha256(raw).hexdigest() == _PINS[purpose]["record"],
        "MANIFEST_PIN_MISMATCH",
    )
    data = _decode(raw)
    common = {
        "schema",
        "status",
        "build_date",
        "physical_authority",
        "runtime_dispatch_enabled",
        "driver_qualified",
        "native_helper_executed",
        "hardware_or_metadata_access_performed",
        "compiler",
        "windows_sdk",
        "cmake",
        "configuration",
        "compile_policy",
        "purpose",
        "source_files",
        "artifacts",
        "verification",
        "limitations",
    }
    extra = (
        {"historical_metadata_build"}
        if purpose == "probe"
        else {
            "historical_builds",
            "request_schema",
            "admission_timeout_ms",
            "native_duration_ms",
        }
    )
    _keys(data, common | extra)
    _require(
        data["schema"]
        == (
            "rocell.windows_camera_owned_development_build.v1"
            if purpose == "probe"
            else "rocell.windows_camera_owned_capture_development_build.v1"
        )
        and data["status"] == "COMPILED_NOT_EXECUTED_NOT_REGISTERED"
    )
    _require(
        all(
            data[key] is False
            for key in (
                "physical_authority",
                "runtime_dispatch_enabled",
                "driver_qualified",
                "native_helper_executed",
                "hardware_or_metadata_access_performed",
            )
        )
    )
    for key in (
        "build_date",
        "compiler",
        "windows_sdk",
        "cmake",
        "configuration",
        "compile_policy",
        "purpose",
    ):
        _require(type(data[key]) is str and 0 < len(data[key]) <= 256)
    if purpose == "capture":
        _require(
            data["request_schema"]
            == "rocell.native_camera_capture_admission_request.v1"
            and type(data["admission_timeout_ms"]) is int
            and data["admission_timeout_ms"] == 5000
            and type(data["native_duration_ms"]) is int
            and data["native_duration_ms"] == 5000
        )
    _keys(data["source_files"], set(_SOURCES[purpose]))
    for sha in data["source_files"].values():
        _sha(sha)
    artifacts = data["artifacts"]
    _require(type(artifacts) is list and len(artifacts) == len(_ARTIFACTS[purpose]))
    for index, row in enumerate(artifacts):
        _keys(
            row,
            {"path", "sha256", "length_bytes", "executed"}
            | ({"scope"} if index else set()),
        )
        _require(row["path"] == _ARTIFACTS[purpose][index])
        _sha(row["sha256"])
        _integer(row["length_bytes"], 8 * 1024 * 1024)
        _require(row["length_bytes"] > 0 and type(row["executed"]) is bool)
        if index == 0:
            _require(
                row["sha256"] == _PINS[purpose]["helper"] and row["executed"] is False
            )
        else:
            _require(type(row["scope"]) is str and 0 < len(row["scope"]) <= 128)
    _require(type(data["verification"]) is dict and type(data["limitations"]) is list)
    return data


def _comparison(row: dict[str, Any], sha: str, length: int | None = None) -> str:
    if row["observation"] != "OBSERVED":
        return "NOT_OBSERVED"
    if row["observed_sha256"] != sha:
        return "HASH_MISMATCH"
    if length is not None and row["observed_bytes"] != length:
        return "LENGTH_MISMATCH"
    return "MATCHED"


def _purpose(
    purpose: str, files: dict[str, Any], raw_encoded: str | None
) -> dict[str, Any]:
    gaps: list[dict[str, str]] = []

    def gap(path: str, reason: str) -> None:
        item = {"relative_path": path, "reason": reason}
        if item not in gaps:
            gaps.append(item)

    def comparison(path: str, sha: str, length: int | None = None) -> str:
        row = files[path]
        result = _comparison(row, sha, length)
        if result != "MATCHED":
            gap(path, row["observation"] if result == "NOT_OBSERVED" else result)
        return result

    helper_path, record_path = (
        _PREFIX + _ARTIFACTS[purpose][0],
        _PREFIX + _RECORDS[purpose],
    )
    binary = comparison(helper_path, _PINS[purpose]["helper"])
    build = comparison(record_path, _PINS[purpose]["record"])
    manifest = None
    if raw_encoded is not None:
        _require(type(raw_encoded) is str)
        try:
            raw = base64.b64decode(raw_encoded, validate=True)
        except (ValueError, TypeError) as error:
            raise PhysicalCameraRuntimeInspectionError(
                "INVALID_MANIFEST_ENCODING"
            ) from error
        _require(
            base64.b64encode(raw).decode("ascii") == raw_encoded
            and files[record_path]["observation"] == "OBSERVED"
            and len(raw) == files[record_path]["observed_bytes"]
            and hashlib.sha256(raw).hexdigest() == files[record_path]["observed_sha256"]
        )
        _require(build == "MATCHED", "UNPINNED_MANIFEST_CONTENT_RETAINED")
        try:
            manifest = _manifest(raw, purpose)
        except PhysicalCameraRuntimeInspectionError:
            build = "MANIFEST_INVALID"
            gap(record_path, "MANIFEST_INVALID")
    else:
        _require(build != "MATCHED", "MATCHED_MANIFEST_BYTES_MISSING")

    def section(role: str) -> tuple[str, dict[str, int]]:
        names = _SOURCES[purpose] if role == "source" else _ARTIFACTS[purpose]
        count = {"total": len(names), "matched": 0, "gaps": 0, "unverified": 0}
        if manifest is None:
            count["unverified"] = len(names)
            gap(record_path, "MANIFEST_UNVERIFIED")
            return "NOT_VERIFIED", count
        artifacts = {item["path"]: item for item in manifest["artifacts"]}
        for name in names:
            expected = (
                manifest["source_files"][name]
                if role == "source"
                else artifacts[name]["sha256"]
            )
            length = None if role == "source" else artifacts[name]["length_bytes"]
            state = comparison(_PREFIX + name, expected, length)
            count["matched" if state == "MATCHED" else "gaps"] += 1
        return ("MATCHED" if count["gaps"] == 0 else "GAPS"), count

    source_status, source_counts = section("source")
    artifact_status, artifact_counts = section("artifact")
    if manifest is not None:
        binary = comparison(
            helper_path,
            _PINS[purpose]["helper"],
            manifest["artifacts"][0]["length_bytes"],
        )
    return {
        "purpose": purpose,
        "binary_status": binary,
        "build_status": build,
        "source_status": source_status,
        "artifact_status": artifact_status,
        "source_counts": source_counts,
        "artifact_counts": artifact_counts,
        "gaps": gaps,
    }


def _derived(document: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int], str]:
    files = {row["relative_path"]: row for row in document["files"]}
    purposes = {
        purpose: _purpose(purpose, files, document["manifests"][purpose])
        for purpose in ("probe", "capture")
    }
    observed = sum(row["observation"] == "OBSERVED" for row in files.values())
    coverage = {
        "planned_paths": len(files),
        "observed_paths": observed,
        "unobserved_paths": len(files) - observed,
    }
    matched = document["terminal_error"] is None and all(
        row[key] == "MATCHED"
        for row in purposes.values()
        for key in ("binary_status", "build_status", "source_status", "artifact_status")
    )
    return purposes, coverage, "FILES_MATCHED" if matched else "HELD"


def _validate(document: dict[str, Any]) -> None:
    _bounded(document)
    _keys(
        document,
        {
            "schema",
            "binding",
            "candidates",
            "files",
            "manifests",
            "purposes",
            "coverage",
            "status",
            "read_budget",
            "terminal_error",
            "effects",
            "limitations",
            *_FALSE_FIELDS,
        },
    )
    _require(document["schema"] == SCHEMA)
    binding = document["binding"]
    _keys(
        binding,
        {
            "workspace",
            "source_sha256",
            "launch_session_id",
            "operator_id",
            "recorded_at_ns",
            "probe_registration_sha256",
            "capture_registration_sha256",
            "catalog_sha256",
        },
    )
    _require(
        type(binding["workspace"]) is str
        and type(binding["launch_session_id"]) is str
        and re.fullmatch(r"wizard-[0-9a-f]{32}", binding["launch_session_id"])
        is not None
    )
    _require(
        type(binding["operator_id"]) is str
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", binding["operator_id"])
        is not None
    )
    _integer(binding["recorded_at_ns"])
    _keys(document["candidates"], {"probe", "capture"})
    candidates = document["candidates"]
    probe = NativeCameraRuntimeRegistration(_canonical(candidates["probe"]))
    capture = NativeCameraCaptureRuntimeRegistration(_canonical(candidates["capture"]))
    _candidates(Path(binding["workspace"]), binding["source_sha256"], probe, capture)
    _require(
        binding["probe_registration_sha256"] == probe.registration_sha256
        and binding["capture_registration_sha256"] == capture.registration_sha256
        and binding["catalog_sha256"] == _catalog_sha256()
    )
    _keys(document["manifests"], {"probe", "capture"})
    _require(
        type(document["files"]) is list and len(document["files"]) == len(FIXED_PATHS)
    )
    specs = _specs()
    for path, row in zip(FIXED_PATHS, document["files"]):
        _keys(
            row,
            {
                "relative_path",
                "kind",
                "maximum_bytes",
                "observation",
                "observed_sha256",
                "observed_bytes",
            },
        )
        _require(
            row["relative_path"] == path
            and row["kind"] == specs[path][0]
            and type(row["maximum_bytes"]) is int
            and row["maximum_bytes"] == specs[path][1]
            and row["observation"] in _OBSERVATIONS
        )
        if row["observation"] == "OBSERVED":
            _sha(row["observed_sha256"])
            _integer(row["observed_bytes"], row["maximum_bytes"])
        else:
            _require(row["observed_sha256"] is None and row["observed_bytes"] is None)
    budget = document["read_budget"]
    _keys(
        budget,
        {
            "maximum_native_bytes",
            "native_bytes_read",
            "native_read_calls",
            "maximum_duration_ms",
            "elapsed_ns",
            "source_checks",
            "maximum_source_bytes_per_check",
        },
    )
    for key, maximum in (
        ("native_bytes_read", MAX_NATIVE_BYTES),
        ("native_read_calls", MAX_READ_CALLS),
        ("source_checks", 2),
        ("elapsed_ns", 2**63 - 1),
    ):
        _integer(budget[key], maximum)
    for key, value in (
        ("maximum_native_bytes", MAX_NATIVE_BYTES),
        ("maximum_duration_ms", 30000),
        ("maximum_source_bytes_per_check", 128 * 1024 * 1024),
    ):
        _require(type(budget[key]) is int and budget[key] == value)
    _require(
        budget["native_bytes_read"]
        >= sum(row["observed_bytes"] or 0 for row in document["files"])
    )
    # A completed nonempty file needs at least one bounded read per block.
    # Failed partial files may add calls/bytes, so equality would invent detail.
    _require(
        budget["native_read_calls"]
        >= sum(
            ((row["observed_bytes"] or 0) + 128 * 1024 - 1) // (128 * 1024)
            for row in document["files"]
        )
        and budget["native_bytes_read"] <= budget["native_read_calls"] * 128 * 1024,
        "READ_BUDGET_OBSERVATIONS_INCONSISTENT",
    )
    _require(
        document["terminal_error"] is None
        or document["terminal_error"] in _TERMINAL_ERRORS
    )
    if document["terminal_error"] is None:
        _require(
            budget["source_checks"] == 2
            and budget["elapsed_ns"] < 30_000_000_000
            and all(row["observation"] != "NOT_INSPECTED" for row in document["files"])
        )
    _require(all(document[key] is False for key in _FALSE_FIELDS))
    _keys(document["effects"], set(_EFFECTS))
    _require(
        all(
            type(document["effects"][key]) is int and document["effects"][key] == 0
            for key in _EFFECTS
        )
        and document["limitations"] == list(_LIMITATIONS)
    )
    purposes, coverage, status = _derived(document)
    _require(
        _canonical(document["purposes"]) == _canonical(purposes)
        and _canonical(document["coverage"]) == _canonical(coverage)
        and document["status"] == status,
        "DERIVED_INSPECTION_TAMPERED",
    )


@dataclass(frozen=True, slots=True)
class PhysicalCameraRuntimeInspection:
    payload: bytes

    def __post_init__(self) -> None:
        document = _decode(self.payload)
        _require(_canonical(document) == self.payload, "CANONICAL_REPORT_REQUIRED")
        _validate(document)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return _decode(self.payload)

    def safe_summary(self) -> dict[str, Any]:
        value = self.to_dict()
        return {
            "schema": SUMMARY_SCHEMA,
            "report_sha256": self.sha256,
            **{
                key: value["binding"][key]
                for key in ("operator_id", "source_sha256", "launch_session_id")
            },
            **{
                key: value[key]
                for key in ("status", "purposes", "coverage", *_FALSE_FIELDS)
            },
        }


def verify_physical_camera_runtime_inspection(
    value: bytes | dict[str, Any] | PhysicalCameraRuntimeInspection,
    *,
    expected_source_sha256: str,
    expected_launch_session_id: str,
    expected_probe_candidate: NativeCameraRuntimeRegistration,
    expected_capture_candidate: NativeCameraCaptureRuntimeRegistration,
    expected_report_sha256: str,
) -> PhysicalCameraRuntimeInspection:
    """Pure admission of retained bytes against independently held bindings."""
    _sha(expected_report_sha256)
    _require(type(value) in (bytes, dict, PhysicalCameraRuntimeInspection))
    if type(value) is PhysicalCameraRuntimeInspection:
        payload = value.payload
    elif type(value) is bytes:
        payload = value
    else:
        _bounded(value)
        payload = _canonical(value)
    report = PhysicalCameraRuntimeInspection(payload)
    data = report.to_dict()
    _require(
        report.sha256 == expected_report_sha256
        and data["binding"]["source_sha256"] == expected_source_sha256
        and data["binding"]["launch_session_id"] == expected_launch_session_id,
        "RETAINED_INSPECTION_BINDING",
    )
    expected = _candidates(
        Path(data["binding"]["workspace"]),
        expected_source_sha256,
        expected_probe_candidate,
        expected_capture_candidate,
    )
    _require(data["candidates"] == expected, "RETAINED_RUNTIME_PAIR_CHANGED")
    return report


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_nlink


def _read_fixed(
    path: Path,
    maximum: int,
    usage: list[int],
    check: Callable[[], None],
    *,
    retain: bool,
) -> tuple[str, int, bytes | None]:
    """Hash bounded reads and check named/open identities, not a future lock."""
    check()
    require_regular_path(path, directory=False)
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise PhysicalCameraRuntimeInspectionError("UNSAFE_PATH")
    if before.st_size > maximum:
        raise PhysicalCameraRuntimeInspectionError("SIZE_LIMIT")
    if usage[0] + before.st_size > MAX_NATIVE_BYTES:
        raise PhysicalCameraRuntimeInspectionError("TOTAL_READ_LIMIT")
    digest, retained, size = hashlib.sha256(), bytearray(), 0
    with path.open("rb") as stream:
        if _identity(os.fstat(stream.fileno())) != _identity(before):
            raise PhysicalCameraRuntimeInspectionError("CHANGED_DURING_READ")
        while size < before.st_size:
            check()
            if usage[1] >= MAX_READ_CALLS:
                raise PhysicalCameraRuntimeInspectionError("READ_CALL_LIMIT")
            block = stream.read(min(128 * 1024, before.st_size - size))
            usage[0] += len(block)
            usage[1] += 1
            size += len(block)
            if not block:
                raise PhysicalCameraRuntimeInspectionError("CHANGED_DURING_READ")
            digest.update(block)
            if retain:
                retained.extend(block)
            check()
        opened = os.fstat(stream.fileno())
    require_regular_path(path, directory=False)
    after = path.stat(follow_symlinks=False)
    if (
        _identity(before) != _identity(opened)
        or _identity(before) != _identity(after)
        or size != before.st_size
    ):
        raise PhysicalCameraRuntimeInspectionError("CHANGED_DURING_READ")
    check()
    return digest.hexdigest(), size, bytes(retained) if retain else None


def inspect_physical_camera_runtime_pair(
    workspace: Path,
    *,
    expected_source_sha256: str,
    launch_session_id: str,
    operator_id: str,
    probe_candidate: NativeCameraRuntimeRegistration,
    capture_candidate: NativeCameraCaptureRuntimeRegistration,
    cancellation: threading.Event,
    progress: Callable[[str], None] | None = None,
) -> PhysicalCameraRuntimeInspection:
    """Explicit fixed-file read only; two separately bounded source checks.

    Common missing/drifted files produce HELD reports. Stop, source/deadline and
    progress failure raise with a bounded historical partial report; no retry.
    """
    candidates = _candidates(
        workspace, expected_source_sha256, probe_candidate, capture_candidate
    )
    _require(
        type(cancellation) is threading.Event
        and (progress is None or callable(progress))
    )
    _require(
        type(launch_session_id) is str
        and re.fullmatch(r"wizard-[0-9a-f]{32}", launch_session_id) is not None
    )
    _require(
        type(operator_id) is str
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", operator_id) is not None
    )
    started, usage, source_checks = time.monotonic_ns(), [0, 0], 0
    specs = _specs()
    document: dict[str, Any] = {
        "schema": SCHEMA,
        "binding": {
            "workspace": str(workspace),
            "source_sha256": expected_source_sha256,
            "launch_session_id": launch_session_id,
            "operator_id": operator_id,
            "recorded_at_ns": time.time_ns(),
            "catalog_sha256": _catalog_sha256(),
            "probe_registration_sha256": probe_candidate.registration_sha256,
            "capture_registration_sha256": capture_candidate.registration_sha256,
        },
        "candidates": candidates,
        "files": [
            {
                "relative_path": path,
                "kind": kind,
                "maximum_bytes": maximum,
                "observation": "NOT_INSPECTED",
                "observed_sha256": None,
                "observed_bytes": None,
            }
            for path, (kind, maximum) in specs.items()
        ],
        "manifests": {"probe": None, "capture": None},
        "effects": dict(_EFFECTS),
        "limitations": list(_LIMITATIONS),
        **{key: False for key in _FALSE_FIELDS},
    }

    def check() -> None:
        if cancellation.is_set():
            raise PhysicalCameraRuntimeInspectionError("CANCELLED")
        if time.monotonic_ns() - started >= 30_000_000_000:
            raise PhysicalCameraRuntimeInspectionError("TIMED_OUT")

    def current_source() -> None:
        nonlocal source_checks
        check()
        source_checks += 1
        try:
            observed = source_fingerprint(workspace)
        except Exception as error:
            raise PhysicalCameraRuntimeInspectionError("SOURCE_CHECK_FAILED") from error
        check()
        if observed != expected_source_sha256:
            raise PhysicalCameraRuntimeInspectionError("SOURCE_CHANGED")

    def report(error: str | None) -> PhysicalCameraRuntimeInspection:
        elapsed = max(0, time.monotonic_ns() - started)
        # Preserve completed rows if the budget expires between the final
        # source check and report construction; do not lose them to validation.
        if error is None and elapsed >= 30_000_000_000:
            raise PhysicalCameraRuntimeInspectionError("TIMED_OUT")
        document["terminal_error"] = error
        document["read_budget"] = {
            "maximum_native_bytes": MAX_NATIVE_BYTES,
            "native_bytes_read": usage[0],
            "native_read_calls": usage[1],
            "maximum_duration_ms": 30000,
            "elapsed_ns": elapsed,
            "source_checks": source_checks,
            "maximum_source_bytes_per_check": 128 * 1024 * 1024,
        }
        document["purposes"], document["coverage"], document["status"] = _derived(
            document
        )
        return PhysicalCameraRuntimeInspection(_canonical(document))

    try:
        current_source()
        for row in document["files"]:
            check()
            try:
                sha, size, raw = _read_fixed(
                    workspace / row["relative_path"],
                    row["maximum_bytes"],
                    usage,
                    check,
                    retain=row["kind"] == "BUILD_RECORD",
                )
                row.update(
                    observation="OBSERVED", observed_sha256=sha, observed_bytes=size
                )
                for purpose in ("probe", "capture"):
                    if (
                        row["relative_path"] == _PREFIX + _RECORDS[purpose]
                        and sha == _PINS[purpose]["record"]
                    ):
                        assert raw is not None
                        document["manifests"][purpose] = base64.b64encode(raw).decode(
                            "ascii"
                        )
            except FileNotFoundError:
                row["observation"] = "MISSING"
            except PhysicalCameraRuntimeInspectionError as error:
                if error.code in _TERMINAL_ERRORS:
                    raise
                row["observation"] = (
                    error.code if error.code in _OBSERVATIONS else "UNREADABLE"
                )
            except Exception as error:
                row["observation"] = (
                    "UNSAFE_PATH"
                    if getattr(error, "code", None) in {"UNSAFE_PATH", "INVALID_PATH"}
                    else "UNREADABLE"
                )
            check()
            if progress is not None:
                try:
                    progress(row["relative_path"])
                except Exception as error:
                    raise PhysicalCameraRuntimeInspectionError(
                        "PROGRESS_FAILED"
                    ) from error
            check()
        current_source()
        completed = report(None)
        check()  # Serialization/validation cannot publish after a late Stop.
        return completed
    except PhysicalCameraRuntimeInspectionError as error:
        if error.code not in _TERMINAL_ERRORS:
            raise
        retained = report(error.code)
        raise PhysicalCameraRuntimeInspectionError(
            error.code, inspection_report=retained.to_dict()
        ) from error
