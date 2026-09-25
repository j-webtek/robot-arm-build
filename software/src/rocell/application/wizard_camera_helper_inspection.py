"""Fixed-file metadata helper inspection, never native execution or approval.

This separate development catalog does not update the historical build record.
Its current Python compatibility pin is explicit; the historical Python hash
disagreement remains visible. Only inventory/identity may be registered later.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from types import MappingProxyType
from typing import Any, Mapping

from rocell.application.wizard_diagnostic_coordinator import (
    require_regular_path,
    source_fingerprint,
)
from rocell.application.wizard_native_camera_metadata import (
    FIXTURE_HELPER_SHA256,
    SCENARIOS,
    NativeCameraMetadataProvider,
    RehearsalNativeCameraMetadataProvider,
)
from rocell.providers.windows.camera_worker_client import (
    CameraCandidate,
    WindowsCameraWorkerClient,
)


SCHEMA = "rocell.wizard_camera_helper_inspection.v1"
CATALOG_ID = "windows-camera-metadata-development-v1"
CATALOG_LABEL = "Windows camera metadata-only development helper"
HELPER_RELATIVE_PATH = (
    "software/native/windows_camera/build/Release/rocell_windows_camera.exe"
)
NATIVE_HELPER_SHA256 = (
    "a0410e866563738bbe0c60c2a763adf094deceba10ae9c81f4becba80a06c797"
)
MAX_REPORT_BYTES = 64 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_READS = 512
BLOCK_BYTES = 64 * 1024
INSPECTION_SECONDS = 5.0
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_NATIVE_ROOT = "software/native/windows_camera/"
# role/path/hash/recorded byte length. Values are reviewed catalog constants,
# never learned from whatever file happens to be present during inspection.
_PINS = (
    ("NATIVE_HELPER", HELPER_RELATIVE_PATH, NATIVE_HELPER_SHA256, 179200),
    (
        "HISTORICAL_RECORD",
        _NATIVE_ROOT + "integrated_build_manifest.json",
        "435fce4a83f2536cb0c2fa4b02c1aaacfb2a9dda58796d763fff4547095168f5",
        4116,
    ),
    (
        "NATIVE_SOURCE",
        _NATIVE_ROOT + "camera_worker.cpp",
        "e0b113f35959252d36c7d43bde274d42a899d16bd47a8154e84bd682ce32481d",
        34202,
    ),
    (
        "NATIVE_SOURCE",
        _NATIVE_ROOT + "CMakeLists.txt",
        "77e4bbe903caf44e7cb0c783fed67ac5fd891573dddd64645f8d2452e677a7fc",
        2900,
    ),
    (
        "NATIVE_SOURCE",
        _NATIVE_ROOT + "identity_metadata.h",
        "3cf6e8da5d18bdea4336d57a1e34ebb174373bfecf1efe22c19b8b29507cb06a",
        5108,
    ),
    (
        "NATIVE_SOURCE",
        _NATIVE_ROOT + "identity_metadata.cpp",
        "b4459ca9f9d0d99ed58ed87b7ce8ac9f6f6ed37a37090cf7b13b768a58bf93bd",
        22670,
    ),
    (
        "NATIVE_TEST_SOURCE",
        _NATIVE_ROOT + "identity_metadata_tests.cpp",
        "b88b9c535441ff8ed5c257f4949f9b20228b4c313d8cc765a8eace75816b6834",
        14803,
    ),
    (
        "NATIVE_TEST_SOURCE",
        _NATIVE_ROOT + "identity_metadata_wire_test.py",
        "0e0958c1204145cd4b4e00f301dfdbec5e10e0dd49140c7cf55d3cb99b333ad5",
        2851,
    ),
    (
        "CURRENT_METADATA_CLIENT",
        "software/src/rocell/providers/windows/camera_worker_client.py",
        "1c486cb4ad4a084aa0ee898130c79f86f37e6824cacafc1e18b40c84ac73369c",
        56759,
    ),
    (
        "HISTORICAL_PYTHON_TEST",
        "software/tests/unit/test_windows_camera_identity.py",
        "a7105115b06134c9d7f101e926ce9fbc26006eb31489907c7df603c31aeb9bf8",
        10820,
    ),
    (
        "HISTORICAL_PYTHON_TEST",
        "software/tests/unit/test_windows_camera_worker.py",
        "fe0260630c55e5295d6f262961b00ebb5fb39d225637ffd6a250b772303742e0",
        17805,
    ),
)
_WARNINGS = [
    "CLIENT_CHANGED_SINCE_BUILD_RECORD",
    "DEVELOPMENT_METADATA_CATALOG_NOT_TRUSTED_RELEASE",
    "HASH_CHECK_NOT_FILESYSTEM_TOCTOU_QUALIFICATION",
    "OWNED_PROCESS_AND_DRIVER_QUALIFICATION_PENDING",
    "NO_CAMERA_ACTIVATION_OR_HARDWARE_QUALIFICATION",
]
_REPORT_KEYS = {
    "schema",
    "mode",
    "source_sha256",
    "catalog_id",
    "catalog_label",
    "catalog_sha256",
    "helper_sha256",
    "inspection_provenance",
    "inspection_status",
    "metadata_eligible",
    "files",
    "historical_full_build_match",
    "warnings",
    "blockers",
    "allowed_operations",
    "physical_authority",
    "camera_activation_allowed",
    "driver_qualified",
    "trusted_release",
    "inspection_sha256",
}


class CameraHelperInspectionError(ValueError):
    def __init__(
        self, code: str, detail: str, *, inspection_report: dict | None = None
    ):
        super().__init__(detail)
        self.code = code
        self._inspection = (
            None if inspection_report is None else deepcopy(inspection_report)
        )

    @property
    def inspection_report(self) -> dict | None:
        return None if self._inspection is None else deepcopy(self._inspection)


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise CameraHelperInspectionError("INVALID_HELPER_INSPECTION", detail)


def _sha(value: object) -> str:
    _require(
        type(value) is str and _SHA.fullmatch(value) is not None,
        "Expected lowercase SHA-256",
    )
    return str(value)


def _bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _catalog_configuration(catalog_id: str | None = None) -> tuple:
    """Closed catalog dispatch; the original constants remain unmodified.

    Retained reports can name either known version, never supply their own pins
    or executable. Default remains v1 for historical callers/inspection.
    """
    if catalog_id is None or catalog_id == CATALOG_ID:
        return (
            CATALOG_ID,
            CATALOG_LABEL,
            HELPER_RELATIVE_PATH,
            NATIVE_HELPER_SHA256,
            _PINS,
        )
    from . import wizard_camera_metadata_successor_catalog as successor

    _require(
        type(catalog_id) is str and catalog_id == successor.CATALOG_ID,
        "Unknown fixed metadata catalog",
    )
    return (
        successor.CATALOG_ID,
        successor.CATALOG_LABEL,
        successor.HELPER_RELATIVE_PATH,
        successor.NATIVE_HELPER_SHA256,
        successor.PINS,
    )


def camera_helper_catalog(catalog_id: str | None = None) -> dict[str, Any]:
    """Pure owned catalog data; this is not a discovery or approval operation."""
    identifier, label, _, helper_sha, pins = _catalog_configuration(catalog_id)
    body = {
        "schema": "rocell.wizard_camera_metadata_helper_catalog.v1",
        "catalog_id": identifier,
        "catalog_label": label,
        "allowed_operations": ["inventory", "identity"],
        "native_helper_sha256": helper_sha,
        "fixture_helper_sha256": FIXTURE_HELPER_SHA256,
        "historical_client_sha256": "9e664b30f2e327a06dd24a589c260642354d7f8c3b2454e52dc19bd8ce11cca4",
        "files": [
            {
                "role": role,
                "relative_path": path,
                "expected_sha256": digest,
                "recorded_bytes": size,
            }
            for role, path, digest, size in pins
        ],
        "maximum_file_bytes": MAX_FILE_BYTES,
        "maximum_total_bytes": MAX_TOTAL_BYTES,
        "maximum_read_calls": MAX_READS,
        "maximum_seconds": INSPECTION_SECONDS,
        "trusted_release": False,
        "physical_authority": False,
    }
    return {**body, "catalog_sha256": _digest(body)}


def _helper(mode: str, catalog_id: str | None = None) -> str:
    return (
        FIXTURE_HELPER_SHA256
        if mode == "rehearsal"
        else _catalog_configuration(catalog_id)[3]
    )


def _expected_rows(mode: str, catalog_id: str | None = None) -> list[dict[str, Any]]:
    return [
        {
            "relative_path": path,
            "role": role,
            "expected_sha256": (
                _helper(mode, catalog_id) if role == "NATIVE_HELPER" else digest
            ),
        }
        for role, path, digest, _ in _catalog_configuration(catalog_id)[4]
    ]


def _report(
    mode: str, source: str, rows: list[dict[str, Any]], catalog_id: str | None = None
) -> dict[str, Any]:
    catalog = camera_helper_catalog(catalog_id)
    statuses = {row["status"] for row in rows}
    status = (
        "UNSAFE_OR_UNREADABLE"
        if "UNSAFE_OR_UNREADABLE" in statuses
        else (
            "MISSING_FILES"
            if "MISSING" in statuses
            else (
                "HASH_DRIFT" if "HASH_DRIFT" in statuses else "MATCHED_METADATA_CATALOG"
            )
        )
    )
    report = {
        "schema": SCHEMA,
        "mode": mode,
        "source_sha256": source,
        "catalog_id": catalog["catalog_id"],
        "catalog_label": catalog["catalog_label"],
        "catalog_sha256": catalog["catalog_sha256"],
        "helper_sha256": _helper(mode, catalog_id),
        "inspection_provenance": (
            "INCAPABLE_FIXTURE" if mode == "rehearsal" else "WORKSPACE_FILE_INSPECTION"
        ),
        "inspection_status": status,
        "metadata_eligible": status == "MATCHED_METADATA_CATALOG",
        "files": rows,
        "historical_full_build_match": False,
        "warnings": list(_WARNINGS),
        "blockers": [] if status == "MATCHED_METADATA_CATALOG" else [status],
        "allowed_operations": ["inventory", "identity"],
        "physical_authority": False,
        "camera_activation_allowed": False,
        "driver_qualified": False,
        "trusted_release": False,
    }
    return {**report, "inspection_sha256": _digest(report)}


def verify_camera_helper_inspection(
    report: object,
    *,
    expected_source_sha256: str,
    expected_inspection_sha256: str,
    expected_provenance: str,
) -> dict[str, Any]:
    """Strict pure retained-report verification; held reports remain valid data."""
    _sha(expected_source_sha256)
    _sha(expected_inspection_sha256)
    _require(
        type(report) is dict and set(report) == _REPORT_KEYS,
        "Inspection fields differ from v1",
    )
    assert isinstance(report, dict)
    mode = report["mode"]
    _require(
        type(mode) is str and mode in {"physical", "rehearsal"},
        "Unknown inspection mode",
    )
    provenance = (
        "INCAPABLE_FIXTURE" if mode == "rehearsal" else "WORKSPACE_FILE_INSPECTION"
    )
    _require(
        expected_provenance == provenance
        and report["inspection_provenance"] == provenance,
        "Inspection provenance differs from selected mode",
    )
    catalog_id = report["catalog_id"]
    pins = _catalog_configuration(catalog_id)[4]
    rows = report["files"]
    _require(
        type(rows) is list and len(rows) == len(pins),
        "Wrong fixed inspection file inventory",
    )
    owned = []
    for row, expected, pin in zip(rows, _expected_rows(mode, catalog_id), pins):
        _require(
            type(row) is dict
            and set(row)
            == {
                "relative_path",
                "role",
                "expected_sha256",
                "observed_sha256",
                "bytes",
                "status",
            },
            "Unexpected file observation fields",
        )
        _require(
            all(
                row[key] == value and type(row[key]) is str
                for key, value in expected.items()
            ),
            "File observation changed the fixed catalog",
        )
        status = row["status"]
        _require(
            type(status) is str
            and status in {"MATCHED", "MISSING", "HASH_DRIFT", "UNSAFE_OR_UNREADABLE"},
            "Invalid file observation status",
        )
        if status in {"MATCHED", "HASH_DRIFT"}:
            observed = _sha(row["observed_sha256"])
            _require(
                type(row["bytes"]) is int and 0 <= row["bytes"] <= MAX_FILE_BYTES,
                "Observed file byte count is invalid",
            )
            _require(
                (observed == expected["expected_sha256"]) == (status == "MATCHED"),
                "File match status disagrees with hashes",
            )
            _require(
                status != "MATCHED" or row["bytes"] == pin[3],
                "Matched catalog file has the wrong recorded byte length",
            )
        else:
            _require(
                row["observed_sha256"] is None and row["bytes"] is None,
                "Unreadable/missing files cannot fabricate observations",
            )
        owned.append(dict(row))
    rebuilt = _report(mode, expected_source_sha256, owned, catalog_id)
    # Bounded rebuild prevents arbitrary report strings/nesting reaching JSON.
    _require(len(_bytes(rebuilt)) <= MAX_REPORT_BYTES, "Inspection report byte limit")
    _require(
        all(type(report[key]) is type(rebuilt[key]) for key in rebuilt),
        "Inspection fields require exact JSON types",
    )
    for key in ("warnings", "blockers", "allowed_operations"):
        _require(
            len(report[key]) <= 16
            and all(type(item) is str and len(item) <= 256 for item in report[key]),
            "Invalid inspection labels",
        )
    _require(
        report == rebuilt
        and type(report["metadata_eligible"]) is bool
        and all(
            report[key] is False
            for key in (
                "historical_full_build_match",
                "physical_authority",
                "camera_activation_allowed",
                "driver_qualified",
                "trusted_release",
            )
        ),
        "Inspection derived fields differ",
    )
    _require(
        rebuilt["inspection_sha256"] == expected_inspection_sha256,
        "Retained inspection differs from independently expected hash",
    )
    return rebuilt


def rehearsal_camera_helper_inspection(
    *, source_sha256: str, scenario: str = "nominal", catalog_id: str | None = None
) -> dict:
    _sha(source_sha256)
    _require(
        type(scenario) is str
        and scenario in {"nominal", "missing-helper", "hash-drift"},
        "Unknown incapable helper inspection scenario",
    )
    rows = []
    for expected, pin in zip(
        _expected_rows("rehearsal", catalog_id), _catalog_configuration(catalog_id)[4]
    ):
        rows.append(
            {
                **expected,
                "observed_sha256": expected["expected_sha256"],
                "bytes": pin[3],
                "status": "MATCHED",
            }
        )
    if scenario == "missing-helper":
        rows[0].update(status="MISSING", observed_sha256=None, bytes=None)
    elif scenario == "hash-drift":
        rows[0].update(status="HASH_DRIFT", observed_sha256="f" * 64)
    return _report("rehearsal", source_sha256, rows, catalog_id)


def _file_identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_nlink


def _hash_scoped_file(
    path: Path, *, usage: list[int], deadline: float
) -> tuple[str, int]:
    """Stream bounded bytes and compare named/opened identities before/after.

    This is change detection, not a path lock spanning a later native launch.
    Slow OS calls cannot be forcibly interrupted; deadline checks occur between
    bounded operations. No filesystem/driver/process qualification is inferred.
    """
    require_regular_path(path, directory=False)
    before = path.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size > MAX_FILE_BYTES
        or time.monotonic() >= deadline
    ):
        raise OSError("Unsafe or over-budget file")
    digest, total = hashlib.sha256(), 0
    with path.open("rb") as stream:
        if _file_identity(os.fstat(stream.fileno())) != _file_identity(before):
            raise OSError("Opened file differs from named file")
        while True:
            if time.monotonic() >= deadline or usage[1] >= MAX_READS:
                raise OSError("Inspection deadline/read-call limit")
            remaining = min(MAX_FILE_BYTES - total, MAX_TOTAL_BYTES - usage[0])
            if remaining < 0:
                raise OSError("Inspection byte limit")
            block = stream.read(min(BLOCK_BYTES, remaining + 1))
            usage[1] += 1
            usage[0] += len(block)
            total += len(block)
            if total > MAX_FILE_BYTES or usage[0] > MAX_TOTAL_BYTES:
                raise OSError("Inspection byte limit")
            if not block:
                break
            digest.update(block)
        opened = os.fstat(stream.fileno())
    require_regular_path(path, directory=False)
    after = path.stat(follow_symlinks=False)
    if (
        _file_identity(before) != _file_identity(opened)
        or _file_identity(before) != _file_identity(after)
        or total != before.st_size
        or time.monotonic() >= deadline
    ):
        raise OSError("File changed during bounded inspection")
    return digest.hexdigest(), total


def inspect_camera_helper(
    workspace: Path,
    *,
    source_sha256: str,
    mode: str,
    scenario: str | None = None,
    catalog_id: str | None = None,
) -> dict:
    """Explicit fixed-file hashing only. Source context is supplied by the caller."""
    _sha(source_sha256)
    _require(
        type(mode) is str and mode in {"physical", "rehearsal"},
        "Unknown inspection mode",
    )
    if mode == "rehearsal":
        return rehearsal_camera_helper_inspection(
            source_sha256=source_sha256,
            scenario="nominal" if scenario is None else scenario,
            catalog_id=catalog_id,
        )
    _require(scenario is None, "Physical inspection cannot select a fixture scenario")
    root = Path(workspace)
    _require(
        root.is_absolute() and ".." not in root.parts,
        "Server-owned absolute workspace required",
    )
    deadline = time.monotonic() + INSPECTION_SECONDS
    usage = [0, 0]
    rows = []
    for expected in _expected_rows(mode, catalog_id):
        path = root / expected["relative_path"]
        try:
            digest, size = _hash_scoped_file(path, usage=usage, deadline=deadline)
            row = {
                **expected,
                "observed_sha256": digest,
                "bytes": size,
                "status": (
                    "MATCHED" if digest == expected["expected_sha256"] else "HASH_DRIFT"
                ),
            }
        except FileNotFoundError:
            row = {
                **expected,
                "observed_sha256": None,
                "bytes": None,
                "status": "MISSING",
            }
        except Exception:
            row = {
                **expected,
                "observed_sha256": None,
                "bytes": None,
                "status": "UNSAFE_OR_UNREADABLE",
            }
        rows.append(row)
    return _report(mode, source_sha256, rows, catalog_id)


def inspect_current_camera_helper(
    workspace: Path, *, source_sha256: str, mode: str, scenario: str | None = None
) -> dict:
    """New wizard launches explicitly inspect the dedicated metadata successor.

    No version fallback is performed; missing/drifted successor files stay held.
    The existing v1 entry point remains available for historical diagnostics.
    """
    from .wizard_camera_metadata_successor_catalog import CATALOG_ID as current

    return inspect_camera_helper(
        workspace,
        source_sha256=source_sha256,
        mode=mode,
        scenario=scenario,
        catalog_id=current,
    )


def _verified_registration(
    artifact: object, *, mode: str, source: str
) -> tuple[dict, dict]:
    # Local import avoids a cycle: the pure registration state uses this file's
    # inspection verifier, while this factory accepts only its immutable type.
    from rocell.application.wizard_camera_helper_registration import (
        ReviewedCameraHelperRegistration,
    )

    _require(
        type(artifact) is ReviewedCameraHelperRegistration,
        "Exact immutable reviewed registration required",
    )
    assert isinstance(artifact, ReviewedCameraHelperRegistration)
    payload, inspection = artifact.payload, artifact.inspection
    fields = {
        "schema",
        "status",
        "mode",
        "session_id",
        "source_sha256",
        "catalog_id",
        "catalog_sha256",
        "helper_sha256",
        "inspection_provenance",
        "inspection_sha256",
        "inspection_operation_id",
        "inspection_operator_id",
        "review_operation_id",
        "reviewer_id",
        "distinct_operator_labels",
        "allowed_operations",
        "probe_allowed",
        "capture_allowed",
        "connected",
        "qualified",
        "physical_authority",
        "trust_scope",
    }
    _require(
        set(payload) == fields
        and payload["schema"] == "rocell.wizard_camera_helper_registration_artifact.v1"
        and payload["status"] == "METADATA_ONLY_REGISTERED"
        and payload["trust_scope"] == "DEVELOPMENT_METADATA_ONLY_NOT_TRUSTED_RELEASE",
        "Invalid metadata registration schema/scope",
    )
    _require(
        mode in {"physical", "rehearsal"}
        and payload["mode"] == mode
        and payload["source_sha256"] == _sha(source),
        "Registration source/mode changed",
    )
    provenance = (
        "INCAPABLE_FIXTURE" if mode == "rehearsal" else "WORKSPACE_FILE_INSPECTION"
    )
    checked = verify_camera_helper_inspection(
        inspection,
        expected_source_sha256=source,
        expected_inspection_sha256=payload["inspection_sha256"],
        expected_provenance=provenance,
    )
    _require(
        checked["metadata_eligible"] is True
        and all(
            payload[key] == checked[key]
            for key in (
                "catalog_id",
                "catalog_sha256",
                "helper_sha256",
                "inspection_provenance",
            )
        ),
        "Registration cannot use a held/changed inspection",
    )
    _require(
        payload["allowed_operations"] == ["inventory", "identity"]
        and payload["distinct_operator_labels"] is True
        and all(
            payload[key] is False
            for key in (
                "probe_allowed",
                "capture_allowed",
                "connected",
                "qualified",
                "physical_authority",
            )
        ),
        "Registration claims unsupported authority",
    )
    for key in ("session_id", "inspection_operation_id", "review_operation_id"):
        _require(
            type(payload[key]) is str and _ID.fullmatch(payload[key]) is not None,
            "Registration label is invalid",
        )
    for key in ("inspection_operator_id", "reviewer_id"):
        actor = payload[key]
        _require(
            type(actor) is str
            and actor == actor.strip()
            and 0 < len(actor.encode("utf-8")) <= 128
            and not any(ord(char) < 32 or ord(char) == 127 for char in actor),
            "Registration operator label is invalid",
        )
    _require(
        payload["inspection_operator_id"].casefold()
        != payload["reviewer_id"].casefold()
        and payload["inspection_operation_id"] != payload["review_operation_id"],
        "Inspection/review actors or operations are not distinct",
    )
    _require(
        _digest(payload) == artifact.registration_sha256, "Registration hash mismatch"
    )
    return payload, checked


class _RevalidatingMetadataProvider:
    """Closed metadata surface; deliberately exposes no client/probe/capture."""

    def __init__(
        self, workspace: Path, payload: dict, inspection: dict, scenario: str | None
    ):
        self._workspace = Path(workspace)
        self._payload = _bytes(payload)
        self._inspection = _bytes(inspection)
        self._scenario = scenario
        self._descriptor = MappingProxyType(
            {
                "provenance": (
                    "INCAPABLE_FIXTURE"
                    if payload["mode"] == "rehearsal"
                    else "WINDOWS_NATIVE_METADATA"
                ),
                "helper_sha256": payload["helper_sha256"],
            }
        )

    def descriptor(self) -> Mapping[str, str]:
        return self._descriptor

    def _provider(
        self,
    ) -> NativeCameraMetadataProvider | RehearsalNativeCameraMetadataProvider:
        payload = json.loads(self._payload)
        if payload["mode"] == "physical":
            try:
                current_source = source_fingerprint(self._workspace)
            except Exception as exc:
                raise CameraHelperInspectionError(
                    "HELPER_SOURCE_CHANGED", "Current source could not be verified"
                ) from exc
            if current_source != payload["source_sha256"]:
                raise CameraHelperInspectionError(
                    "HELPER_SOURCE_CHANGED",
                    "Current source differs from metadata registration",
                )
        current = inspect_camera_helper(
            self._workspace,
            source_sha256=payload["source_sha256"],
            mode=payload["mode"],
            catalog_id=payload["catalog_id"],
        )
        if _bytes(current) != self._inspection:
            raise CameraHelperInspectionError(
                "HELPER_INSPECTION_CHANGED",
                "Fixed helper catalog files changed; explicit new inspection/review required",
                inspection_report=current,
            )
        if payload["mode"] == "rehearsal":
            return RehearsalNativeCameraMetadataProvider(self._scenario or "nominal")
        return NativeCameraMetadataProvider(
            WindowsCameraWorkerClient(
                self._workspace / _catalog_configuration(payload["catalog_id"])[2],
                payload["helper_sha256"],
            )
        )

    def inventory(self) -> dict:
        return self._provider().inventory()

    def identity(self, candidate: CameraCandidate) -> dict:
        return self._provider().identity(candidate)


def create_metadata_provider(
    workspace: Path,
    registration_artifact: object,
    *,
    mode: str,
    source_sha256: str,
    scenario: str | None = None,
) -> _RevalidatingMetadataProvider:
    """Pure factory for reviewed context; revalidation occurs on each lookup."""
    _require(
        scenario is None
        or (mode == "rehearsal" and type(scenario) is str and scenario in SCENARIOS),
        "Only rehearsal metadata can select a closed fixture scenario",
    )
    payload, inspection = _verified_registration(
        registration_artifact, mode=mode, source=source_sha256
    )
    return _RevalidatingMetadataProvider(workspace, payload, inspection, scenario)
