"""Actual local-file observations for a physical diagnostic's software subset.

This module never inventories, opens, initializes or commands a device. A
coherent report is NOT canonical stage completion: installed power isolation,
HZ-012 evidence, received articles and physical release remain unverified.
Constructors and retained-report verification are inert. Only an explicit run
reads the fixed source closure; Windows file pins exclude concurrent writers
to that closure while its existing semantic validators run.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from threading import Event
import time
from typing import Any, Callable, Iterator, cast

from rocell.application.cell_commissioning_coordinator import (
    CampaignBudget,
    CampaignEvidence,
    CampaignRegistration,
    CommissioningMode,
    ExactOperationPermit,
    ObservedPowerState,
    RetainedCampaignExecution,
    WorkerReceipt,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_durability import read_bounded_regular_file
from rocell.application.physical_onboarding_foundation import (
    load_physical_onboarding_foundation,
)
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_diagnostic_export import _directory_guard
from rocell.safety.effects import EffectCertainty, EffectClass


SOURCE_PREFLIGHT_SCHEMA = "rocell.physical_source_preflight.v1"
SOURCE_PREFLIGHT_ACTION_ID = "physical_source_preflight"
SOURCE_PREFLIGHT_COMPOSITION = "PHYSICAL_DIAGNOSTIC_NO_DEVICE_IO"
SOURCE_PREFLIGHT_MAX_REPORT_BYTES = 96 * 1024
SOURCE_PREFLIGHT_TIMEOUT_MS = 20_000
SOURCE_PREFLIGHT_WORKER_PATH = (
    "software/src/rocell/application/physical_source_preflight.py"
)
_MAX_FILE_BYTES = 2 * 1024 * 1024
_MAX_BINARY_BYTES = 8 * 1024 * 1024
_MAX_TOTAL_BYTES = 32 * 1024 * 1024
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}\Z")
_NATIVE_ROOT = "software/native/windows_camera/"
_NATIVE_MANIFEST = _NATIVE_ROOT + "owned_build_manifest.json"
_NATIVE_SOURCES = (
    "CMakeLists.txt",
    "camera_worker.cpp",
    "identity_metadata.cpp",
    "identity_metadata.h",
    "admission_protocol.h",
    "admission_protocol.cpp",
    "admission_entry.h",
    "admission_entry.cpp",
    "admission_protocol_tests.cpp",
    "admission_entry_tests.cpp",
)
_NATIVE_ARTIFACTS = (
    "build-owned/Release/rocell_windows_camera.exe",
    "build-owned/Release/rocell_camera_admission_tests.exe",
    "build-owned/Release/rocell_camera_admission_entry_tests.exe",
)
_CONTRACT_FILES = (
    "software/config/physical_onboarding_foundation.json",
    "software/config/authority_effect_policy.json",
    "software/config/physical_onboarding_stage_catalog.json",
    "software/config/configuration_epochs.json",
    "software/config/physical_onboarding_hazards.json",
    "software/config/workcell_icd.json",
    "software/config/accuracy_budget_policy.json",
    "software/config/arm_frame_contract.json",
    "software/config/arm_connection.json",
    "software/config/camera_profiles/arducam_b0477_imx283_16mm.json",
    "software/config/camera_architecture_plan.json",
    "software/config/physical_onboarding_policy.json",
    "active-project/RoCell_v0_3/config/workcell_layout.json",
    "active-project/RoCell_v0_3/config/robot_reach_screening.json",
    "hardware/static_overhead_camera/config/support_design.json",
    "hardware/static_overhead_camera/hardware_intake_template.csv",
)
_IMPLEMENTATIONS = (
    "application/physical_source_preflight.py",
    "application/physical_onboarding_foundation.py",
    "application/physical_onboarding_stage_catalog.py",
    "application/physical_onboarding_policy.py",
    "application/configuration_epochs.py",
    "application/physical_onboarding_durability.py",
    "application/physical_onboarding_m1.py",
    "application/commissioning_m1_persistence.py",
    "application/commissioning_physical_persistence.py",
    "application/cell_commissioning_coordinator.py",
    "application/wizard_diagnostic_coordinator.py",
    "application/wizard_diagnostic_export.py",
    "workcell/interface_contract.py",
    "workcell/static_camera_support.py",
    "calibration/accuracy_budget.py",
    "safety/effects.py",
    "safety/onboarding_hazards.py",
    "vision/camera_profile.py",
    "providers/windows/camera_worker_client.py",
    "providers/windows/native_camera_protocol.py",
    "providers/windows/native_camera_registration.py",
    "providers/windows/native_camera_parent_admission.py",
    "providers/windows/owned_native_camera_runner.py",
    "providers/windows/owned_worker_process.py",
    "providers/windows/_owned_worker_win32.py",
    "providers/windows/arm_feedback_worker.py",
    "providers/windows/arm_nonpurging_adapter.py",
    "providers/windows/nonpurging_serial_api.py",
    "providers/windows/nonpurging_serial_backend.py",
)
SOURCE_PREFLIGHT_SCOPE = tuple(
    sorted(
        (
            *_CONTRACT_FILES,
            *("software/src/rocell/" + name for name in _IMPLEMENTATIONS),
            _NATIVE_MANIFEST,
            *(_NATIVE_ROOT + name for name in _NATIVE_SOURCES),
            *(_NATIVE_ROOT + name for name in _NATIVE_ARTIFACTS),
        )
    )
)
_CHECK_IDS = (
    "fixed_source_closure",
    "current_software_fingerprint",
    "worker_source_binding",
    "foundation_semantics",
    "native_development_build_bytes",
    "unchanged_source_snapshot",
)
_HOLDS = (
    "DISCONNECTED_REQUIRED_NOT_OBSERVED",
    "HZ_012_CANONICAL_EVIDENCE_NOT_CLOSED",
    "RECEIVED_HARDWARE_NOT_VERIFIED",
    "STATIC_CAMERA_INSTALLATION_NOT_VERIFIED",
    "NATIVE_DRIVER_AND_PROCESS_QUALIFICATION_NOT_GRANTED",
    "CANONICAL_STAGE_COMPLETION_NOT_GRANTED",
    "PHYSICAL_RELEASE_NOT_GRANTED",
)
_LIMITATIONS = (
    "Actual local file observations only; no synthetic probes or received-hardware observations.",
    "Software fingerprint excludes hardware/native trees; the separately listed fixed closure covers only the reported files.",
    "Byte agreement with a local development manifest is not a trusted release, reproducible-build proof or installed-driver qualification.",
    "Windows pins protect the fixed closure; the broad software fingerprint uses before/after diagnostic checks, not a hostile-writer or off-machine rollback guarantee.",
)


class PhysicalSourcePreflightError(ValueError):
    """Bounded diagnostic rejection, not evidence of a physical effect."""

    def __init__(self, code: str, *, relative_path: str | None = None) -> None:
        self.code = code
        self.relative_path = relative_path
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PhysicalSourcePreflightError(code)


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


SOURCE_PREFLIGHT_OPERATION_SHA256 = _hash(
    _canonical(
        {
            "schema": SOURCE_PREFLIGHT_SCHEMA,
            "action": SOURCE_PREFLIGHT_ACTION_ID,
            "scope": SOURCE_PREFLIGHT_SCOPE,
            "checks": _CHECK_IDS,
            "composition": SOURCE_PREFLIGHT_COMPOSITION,
            "canonical_stage_pass": False,
        }
    )
)


def _digest(value: Any) -> bool:
    return type(value) is str and _DIGEST.fullmatch(value) is not None


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def _parse(payload: bytes) -> dict[str, Any]:
    _require(
        type(payload) is bytes
        and 0 < len(payload) <= SOURCE_PREFLIGHT_MAX_REPORT_BYTES,
        "REPORT_BYTE_BOUND",
    )
    try:
        value = json.loads(
            payload,
            object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (ValueError, UnicodeError, RecursionError) as error:
        raise PhysicalSourcePreflightError("STRICT_JSON_REQUIRED") from error
    _require(type(value) is dict, "REPORT_OBJECT_REQUIRED")
    return value


def _checked(path: Path, *, directory: bool = False) -> Path:
    _require(
        path.is_absolute()
        and path != Path(path.anchor)
        and not str(path).startswith(("\\\\", "//"))
        and ".." not in path.parts,
        "LOCAL_FIXED_PATH_REQUIRED",
    )
    for component in (path, *path.parents):
        info = component.lstat()
        _require(
            not stat.S_ISLNK(info.st_mode)
            and not getattr(info, "st_file_attributes", 0) & 0x400,
            "LINK_OR_REPARSE_REJECTED",
        )
    info = path.lstat()
    _require(
        stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode),
        "REGULAR_SOURCE_REQUIRED",
    )
    if not directory:
        _require(info.st_nlink == 1, "HARD_LINK_REJECTED")
    return path


def _maximum(relative: str) -> int:
    return _MAX_BINARY_BYTES if relative.endswith(".exe") else _MAX_FILE_BYTES


def _fixed_metadata(root: Path, check: Callable[[], None]) -> None:
    """Reject missing/oversized closure entries before any source content read."""
    total = 0
    for relative in SOURCE_PREFLIGHT_SCOPE:
        check()
        try:
            path = _checked(root / relative)
            size = path.stat().st_size
            _require(
                0 < size <= _maximum(relative) and total + size <= _MAX_TOTAL_BYTES,
                "FIXED_SOURCE_BYTE_BOUND",
            )
            total += size
        except PhysicalSourcePreflightError as error:
            raise PhysicalSourcePreflightError(
                error.code, relative_path=relative
            ) from error
        except OSError as error:
            raise PhysicalSourcePreflightError(
                "SOURCE_FILE_UNAVAILABLE", relative_path=relative
            ) from error


@contextmanager
def _pins(root: Path, check: Callable[[], None]) -> Iterator[None]:
    """Hold fixed Windows files and ancestry while old loaders re-read paths.

    No helper is loaded: these are ordinary disk-file handles only. Portable
    tests retain before/after checks without claiming the Windows sharing pin.
    """
    with ExitStack() as stack:
        for parent in sorted({(root / name).parent for name in SOURCE_PREFLIGHT_SCOPE}):
            check()
            _checked(parent, directory=True)
            stack.enter_context(_directory_guard(parent))
        kernel = None
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateFileW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.LPVOID,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            ]
            kernel.CreateFileW.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle.restype = wintypes.BOOL
        total = 0
        for relative in SOURCE_PREFLIGHT_SCOPE:
            check()
            path = _checked(root / relative)
            size = path.stat().st_size
            _require(
                0 < size <= _maximum(relative) and total + size <= _MAX_TOTAL_BYTES,
                "FIXED_SOURCE_BYTE_BOUND",
            )
            total += size
            if kernel is not None:
                handle = kernel.CreateFileW(
                    str(path), 0x80000000, 0x1, None, 3, 0x00200080, None
                )
                _require(handle != wintypes.HANDLE(-1).value, "SOURCE_PIN_FAILED")

                def close_file(selected: Any = handle) -> None:
                    _require(
                        bool(kernel.CloseHandle(selected)), "SOURCE_PIN_CLOSE_FAILED"
                    )

                stack.callback(close_file)
                _checked(path)
        yield


def _snapshot(
    root: Path, check: Callable[[], None]
) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    rows, content = [], {}
    total = 0
    for relative in SOURCE_PREFLIGHT_SCOPE:
        check()
        path = _checked(root / relative)
        size = path.stat().st_size
        _require(
            0 < size <= _maximum(relative) and total + size <= _MAX_TOTAL_BYTES,
            "FIXED_SOURCE_BYTE_BOUND",
        )
        # Remaining aggregate budget is enforced before content I/O.
        payload = read_bounded_regular_file(
            path,
            maximum_bytes=min(_maximum(relative), _MAX_TOTAL_BYTES - total),
            label="fixed preflight source",
        )
        check()
        _require(len(payload) == size, "SOURCE_CHANGED_DURING_READ")
        total += len(payload)
        rows.append({"path": relative, "bytes": len(payload), "sha256": _hash(payload)})
        # Only bounded JSON contracts need retained in-memory content.
        if relative.endswith(".json"):
            content[relative] = payload
    return rows, content


def _native_manifest(
    content: dict[str, bytes], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    manifest = _parse(content[_NATIVE_MANIFEST])
    _require(
        set(manifest)
        == {
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
            "historical_metadata_build",
            "limitations",
        },
        "NATIVE_MANIFEST_FIELDS",
    )
    _require(
        manifest.get("schema") == "rocell.windows_camera_owned_development_build.v1"
        and manifest.get("status") == "COMPILED_NOT_EXECUTED_NOT_REGISTERED",
        "NATIVE_MANIFEST_SCHEMA",
    )
    for name in (
        "physical_authority",
        "runtime_dispatch_enabled",
        "driver_qualified",
        "native_helper_executed",
        "hardware_or_metadata_access_performed",
    ):
        _require(manifest.get(name) is False, "NATIVE_MANIFEST_AUTHORITY")
    sources, artifacts = manifest.get("source_files"), manifest.get("artifacts")
    _require(
        type(sources) is dict and set(sources) == set(_NATIVE_SOURCES),
        "NATIVE_MANIFEST_SOURCE_SET",
    )
    _require(
        type(artifacts) is list and len(artifacts) == len(_NATIVE_ARTIFACTS),
        "NATIVE_MANIFEST_ARTIFACT_SET",
    )
    sources = cast(dict[str, Any], sources)
    artifacts = cast(list[dict[str, Any]], artifacts)
    indexed = {item["path"]: item for item in rows}
    comparisons = []
    for name in _NATIVE_SOURCES:
        expected = sources[name]
        _require(_digest(expected), "NATIVE_MANIFEST_HASH")
        actual = indexed[_NATIVE_ROOT + name]["sha256"]
        comparisons.append(
            {
                "path": _NATIVE_ROOT + name,
                "expected_sha256": expected,
                "observed_sha256": actual,
                "expected_bytes": None,
                "observed_bytes": indexed[_NATIVE_ROOT + name]["bytes"],
                "matched": expected == actual,
            }
        )
    _require(
        all(type(item) is dict and type(item.get("path")) is str for item in artifacts),
        "NATIVE_MANIFEST_ARTIFACT_SCHEMA",
    )
    _require(
        [item["path"] for item in artifacts] == list(_NATIVE_ARTIFACTS),
        "NATIVE_MANIFEST_ARTIFACT_SET",
    )
    for item in artifacts:
        path = _NATIVE_ROOT + item["path"]
        _require(
            set(item)
            == {"path", "sha256", "length_bytes", "executed"}
            | (set() if item["path"] == _NATIVE_ARTIFACTS[0] else {"scope"}),
            "NATIVE_ARTIFACT_FIELDS",
        )
        _require(
            _digest(item.get("sha256"))
            and type(item.get("length_bytes")) is int
            and 0 < item["length_bytes"] <= _MAX_BINARY_BYTES,
            "NATIVE_MANIFEST_ARTIFACT_SCHEMA",
        )
        if item["path"] == _NATIVE_ARTIFACTS[0]:
            _require(item.get("executed") is False, "NATIVE_MANIFEST_AUTHORITY")
        comparisons.append(
            {
                "path": path,
                "expected_sha256": item["sha256"],
                "observed_sha256": indexed[path]["sha256"],
                "expected_bytes": item["length_bytes"],
                "observed_bytes": indexed[path]["bytes"],
                "matched": item["sha256"] == indexed[path]["sha256"]
                and item["length_bytes"] == indexed[path]["bytes"],
            }
        )
    return {
        "manifest_sha256": indexed[_NATIVE_MANIFEST]["sha256"],
        "comparisons": comparisons,
        "trusted_release": False,
        "helper_executed_by_preflight": False,
    }


def _checks(data: dict[str, Any]) -> list[dict[str, Any]]:
    facts, binding = data["observations"], data["binding"]
    rows = data["files"]
    native = facts["native_development_build"]
    foundation = facts["foundation"]
    values = (
        len(rows) == len(SOURCE_PREFLIGHT_SCOPE),
        facts["software_fingerprint_before"]
        == binding["workspace_source_sha256"]
        == facts["software_fingerprint_after"],
        any(
            row["path"] == SOURCE_PREFLIGHT_WORKER_PATH
            and row["sha256"] == binding["worker_sha256"]
            for row in rows
        ),
        foundation is not None and foundation["zero_physical_authority"] is True,
        native is not None and all(row["matched"] for row in native["comparisons"]),
        facts["fixed_snapshot_sha256_before"] is not None
        and facts["fixed_snapshot_sha256_before"]
        == facts["fixed_snapshot_sha256_after"],
    )
    return [
        {"check_id": name, "passed": value} for name, value in zip(_CHECK_IDS, values)
    ]


@dataclass(frozen=True, slots=True)
class PhysicalSourcePreflightReport:
    payload: bytes

    def __post_init__(self) -> None:
        try:
            _validate_report(self.payload)
        except (TypeError, KeyError, RecursionError, OverflowError) as error:
            raise PhysicalSourcePreflightError("REPORT_SCHEMA") from error

    @property
    def sha256(self) -> str:
        return _hash(self.payload)

    def safe_summary(self) -> dict[str, Any]:
        data = _validate_report(self.payload)
        return {
            "schema": "rocell.physical_source_preflight_summary.v1",
            "outcome": data["outcome"],
            "report_sha256": self.sha256,
            "binding": data["binding"],
            "checks": data["checks"],
            "file_count": len(data["files"]),
            "logical_bytes": sum(row["bytes"] for row in data["files"]),
            "file_scope_sha256": SOURCE_PREFLIGHT_OPERATION_SHA256,
            "errors": data["errors"],
            "failed_source": data["observations"]["failed_source"],
            "canonical_stage_holds": data["canonical_stage_holds"],
            "canonical_stage_pass": False,
            "physical_authority": False,
            "power_state": "UNKNOWN",
            "device_io_performed": False,
            "meaning": "Actual source-file checks only, not received-hardware qualification or permission to complete a canonical physical stage.",
        }


def _validate_report(payload: bytes) -> dict[str, Any]:
    data = _parse(payload)
    _require(
        _canonical(data) == payload
        and set(data)
        == {
            "schema",
            "composition",
            "binding",
            "files",
            "observations",
            "checks",
            "outcome",
            "errors",
            "canonical_stage_holds",
            "canonical_stage_pass",
            "physical_authority",
            "device_io_performed",
            "power_state",
            "limitations",
        },
        "REPORT_SCHEMA",
    )
    _require(
        data["schema"] == SOURCE_PREFLIGHT_SCHEMA
        and data["composition"] == SOURCE_PREFLIGHT_COMPOSITION
        and all(
            data[key] is False
            for key in (
                "canonical_stage_pass",
                "physical_authority",
                "device_io_performed",
            )
        )
        and data["power_state"] == "UNKNOWN"
        and data["canonical_stage_holds"] == list(_HOLDS)
        and data["limitations"] == list(_LIMITATIONS),
        "REPORT_AUTHORITY",
    )
    binding = data["binding"]
    _require(
        type(binding) is dict
        and set(binding)
        == {
            "cell_id",
            "session_id",
            "attempt_id",
            "operator_id",
            "workspace_source_sha256",
            "permit_sha256",
            "worker_sha256",
            "operation_sha256",
        },
        "BINDING_SCHEMA",
    )
    for name in ("cell_id", "session_id", "attempt_id", "operator_id"):
        _require(
            type(binding[name]) is str and _ID.fullmatch(binding[name]) is not None,
            "BINDING_IDENTIFIER",
        )
    for name in (
        "workspace_source_sha256",
        "permit_sha256",
        "worker_sha256",
        "operation_sha256",
    ):
        _require(_digest(binding[name]), "BINDING_DIGEST")
    _require(
        binding["operation_sha256"] == SOURCE_PREFLIGHT_OPERATION_SHA256,
        "OPERATION_SCOPE_CHANGED",
    )
    rows = data["files"]
    _require(
        type(rows) is list and len(rows) in (0, len(SOURCE_PREFLIGHT_SCOPE)), "FILE_SET"
    )
    if rows:
        _require(
            all(
                type(row) is dict and set(row) == {"path", "bytes", "sha256"}
                for row in rows
            ),
            "FILE_SCHEMA",
        )
        _require(
            [row["path"] for row in rows] == list(SOURCE_PREFLIGHT_SCOPE), "FILE_SET"
        )
        for row in rows:
            _require(
                type(row["bytes"]) is int
                and 0 < row["bytes"] <= _maximum(row["path"])
                and _digest(row["sha256"]),
                "FILE_VALUE",
            )
        _require(
            sum(row["bytes"] for row in rows) <= _MAX_TOTAL_BYTES, "FILE_AGGREGATE"
        )
    facts = data["observations"]
    _require(
        type(facts) is dict
        and set(facts)
        == {
            "software_fingerprint_before",
            "software_fingerprint_after",
            "fixed_snapshot_sha256_before",
            "fixed_snapshot_sha256_after",
            "foundation",
            "native_development_build",
            "fixed_file_pin",
            "failed_source",
        },
        "OBSERVATION_SCHEMA",
    )
    for name in (
        "software_fingerprint_before",
        "software_fingerprint_after",
        "fixed_snapshot_sha256_before",
        "fixed_snapshot_sha256_after",
    ):
        _require(facts[name] is None or _digest(facts[name]), "OBSERVATION_HASH")
    _require(
        facts["fixed_file_pin"]
        in ("WINDOWS_READ_ONLY_SHARING", "PORTABLE_BEFORE_AFTER_ONLY"),
        "OBSERVATION_PIN",
    )
    _require(
        facts["failed_source"] is None
        or type(facts["failed_source"]) is str
        and facts["failed_source"] in SOURCE_PREFLIGHT_SCOPE,
        "FAILED_SOURCE_SCOPE",
    )
    if rows:
        _require(
            facts["fixed_snapshot_sha256_before"] == _hash(_canonical(rows)),
            "FILE_HASH",
        )
    foundation = facts["foundation"]
    if foundation is not None:
        _require(
            type(foundation) is dict
            and set(foundation)
            == {
                "foundation_sha256",
                "catalog_sha256",
                "icd_sha256",
                "support_sha256",
                "zero_physical_authority",
                "runtime_activation",
                "open_implementation_gates",
            },
            "FOUNDATION_SCHEMA",
        )
        _require(
            foundation["zero_physical_authority"] is True
            and foundation["runtime_activation"] is False,
            "FOUNDATION_AUTHORITY",
        )
        for name in (
            "foundation_sha256",
            "catalog_sha256",
            "icd_sha256",
            "support_sha256",
        ):
            _require(_digest(foundation[name]), "FOUNDATION_HASH")
        indexed = {row["path"]: row for row in rows}
        for name, path in (
            (
                "foundation_sha256",
                "software/config/physical_onboarding_foundation.json",
            ),
            (
                "catalog_sha256",
                "software/config/physical_onboarding_stage_catalog.json",
            ),
            ("icd_sha256", "software/config/workcell_icd.json"),
            (
                "support_sha256",
                "hardware/static_overhead_camera/config/support_design.json",
            ),
        ):
            _require(
                path in indexed and foundation[name] == indexed[path]["sha256"],
                "FOUNDATION_FILE_BINDING",
            )
        gates = foundation["open_implementation_gates"]
        _require(
            type(gates) is list
            and 1 <= len(gates) <= 64
            and all(
                type(item) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", item)
                for item in gates
            )
            and len(set(gates)) == len(gates),
            "FOUNDATION_GATES",
        )
    native = facts["native_development_build"]
    if native is not None:
        _require(
            type(native) is dict
            and set(native)
            == {
                "manifest_sha256",
                "comparisons",
                "trusted_release",
                "helper_executed_by_preflight",
            }
            and native["trusted_release"] is False
            and native["helper_executed_by_preflight"] is False
            and _digest(native["manifest_sha256"]),
            "NATIVE_OBSERVATION_SCHEMA",
        )
        comparisons = native["comparisons"]
        _require(
            type(comparisons) is list
            and len(comparisons) == len(_NATIVE_SOURCES) + len(_NATIVE_ARTIFACTS),
            "NATIVE_COMPARISON_SET",
        )
        _require(
            all(
                type(row) is dict
                and set(row)
                == {
                    "path",
                    "expected_sha256",
                    "observed_sha256",
                    "matched",
                    "expected_bytes",
                    "observed_bytes",
                }
                for row in comparisons
            ),
            "NATIVE_COMPARISON_SCHEMA",
        )
        _require(
            [row["path"] for row in comparisons]
            == [_NATIVE_ROOT + name for name in (*_NATIVE_SOURCES, *_NATIVE_ARTIFACTS)],
            "NATIVE_COMPARISON_SET",
        )
        indexed = {row["path"]: row for row in rows}
        _require(
            _NATIVE_MANIFEST in indexed
            and native["manifest_sha256"] == indexed[_NATIVE_MANIFEST]["sha256"],
            "NATIVE_MANIFEST_FILE_BINDING",
        )
        for row in comparisons:
            _require(
                _digest(row["expected_sha256"])
                and _digest(row["observed_sha256"])
                and type(row["matched"]) is bool
                and row["path"] in indexed
                and row["observed_sha256"] == indexed[row["path"]]["sha256"]
                and type(row["observed_bytes"]) is int
                and row["observed_bytes"] == indexed[row["path"]]["bytes"]
                and (
                    (row["expected_bytes"] is None and not row["path"].endswith(".exe"))
                    or (
                        row["path"].endswith(".exe")
                        and type(row["expected_bytes"]) is int
                        and 0 < row["expected_bytes"] <= _MAX_BINARY_BYTES
                    )
                )
                and row["matched"]
                == (
                    row["expected_sha256"] == row["observed_sha256"]
                    and (
                        row["expected_bytes"] is None
                        or row["expected_bytes"] == row["observed_bytes"]
                    )
                ),
                "NATIVE_COMPARISON_VALUE",
            )
    errors = data["errors"]
    _require(
        type(errors) is list
        and len(errors) <= 8
        and all(
            type(code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code)
            for code in errors
        )
        and len(set(errors)) == len(errors),
        "ERROR_SCHEMA",
    )
    expected = _checks(data)
    _require(
        data["checks"] == expected
        and all(type(row.get("passed")) is bool for row in data["checks"]),
        "CHECKS_CHANGED",
    )
    outcome = (
        "FILE_CHECKS_COHERENT"
        if not errors and all(row["passed"] for row in expected)
        else "HELD"
    )
    _require(data["outcome"] == outcome, "OUTCOME_CHANGED")
    return data


def verify_physical_source_preflight(
    payload: bytes,
    *,
    expected_source_sha256: str,
    expected_permit_sha256: str,
    expected_worker_sha256: str,
    expected_report_sha256: str | None = None,
) -> PhysicalSourcePreflightReport:
    """Pure receipt integrity/binding check, not a new current-source observation."""
    report = PhysicalSourcePreflightReport(payload)
    _require(
        expected_report_sha256 is None
        or (
            _digest(expected_report_sha256) and report.sha256 == expected_report_sha256
        ),
        "RETAINED_REPORT_HASH_CHANGED",
    )
    binding = _validate_report(payload)["binding"]
    _require(
        binding["workspace_source_sha256"] == expected_source_sha256
        and binding["permit_sha256"] == expected_permit_sha256
        and binding["worker_sha256"] == expected_worker_sha256,
        "RETAINED_BINDING_CHANGED",
    )
    return report


def source_preflight_registration(workspace: Path) -> CampaignRegistration:
    """Explicit registration preparation reads only the fixed worker file."""
    root = _checked(Path(workspace), directory=True)
    worker = _checked(root / SOURCE_PREFLIGHT_WORKER_PATH)
    digest = _hash(
        read_bounded_regular_file(
            worker, maximum_bytes=_MAX_FILE_BYTES, label="physical source worker"
        )
    )
    return CampaignRegistration(
        SOURCE_PREFLIGHT_ACTION_ID,
        PhysicalOnboardingStage.WORKSPACE_SOURCES,
        EffectClass.NO_DEVICE_IO,
        "physical-source-preflight-v1",
        digest,
        SOURCE_PREFLIGHT_OPERATION_SHA256,
        (),
        CampaignBudget(
            SOURCE_PREFLIGHT_TIMEOUT_MS,
            SOURCE_PREFLIGHT_MAX_REPORT_BYTES,
            0,
            0,
            0,
            0,
            0,
        ),
    )


class PhysicalSourcePreflightWorker:
    """One-use file-check worker. Creating it performs no filesystem/device I/O."""

    composition = SOURCE_PREFLIGHT_COMPOSITION

    def __init__(
        self,
        workspace: Path,
        *,
        expected_source_sha256: str,
        worker_executable_sha256: str,
        operator_id: str,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        _require(isinstance(workspace, Path), "WORKSPACE_PATH_REQUIRED")
        _require(
            _digest(expected_source_sha256) and _digest(worker_executable_sha256),
            "WORKER_BINDING_DIGEST",
        )
        _require(
            type(operator_id) is str and _ID.fullmatch(operator_id) is not None,
            "OPERATOR_IDENTIFIER",
        )
        self.workspace = workspace
        self.expected_source_sha256 = expected_source_sha256
        self.worker_executable_sha256 = worker_executable_sha256
        self.operator_id = operator_id
        self._clock = clock_ns
        self._used = False
        self.report: PhysicalSourcePreflightReport | None = None

    def run_campaign(
        self, permit: ExactOperationPermit, *, deadline_ns: int, cancellation: Event
    ) -> WorkerReceipt:
        raise PhysicalSourcePreflightError("RETAINED_EXACT_ADMISSION_REQUIRED")

    def run_retained_campaign(
        self,
        permit: ExactOperationPermit,
        *,
        deadline_ns: int,
        cancellation: Event,
        authorize_consumed_permit: Callable[[ExactOperationPermit], None],
    ) -> RetainedCampaignExecution:
        _require(not self._used, "WORKER_ALREADY_USED")
        self._used = True
        _require(type(permit) is ExactOperationPermit, "EXACT_PERMIT_REQUIRED")
        registration = permit.registration
        from rocell.application.commissioning_physical_persistence import (
            physical_diagnostic_source_binding,
        )

        _require(
            registration.action_id == SOURCE_PREFLIGHT_ACTION_ID
            and registration.stage is PhysicalOnboardingStage.WORKSPACE_SOURCES
            and registration.effect_class is EffectClass.NO_DEVICE_IO
            and registration.resources == ()
            and permit.envelope is None
            and registration.operation_sha256 == SOURCE_PREFLIGHT_OPERATION_SHA256
            and registration.worker_id == "physical-source-preflight-v1"
            and registration.worker_executable_sha256 == self.worker_executable_sha256
            and permit.admission.mode is CommissioningMode.PHYSICAL_DIAGNOSTIC
            and permit.admission.source_binding_sha256
            == physical_diagnostic_source_binding(self.expected_source_sha256)
            and permit.admission.stage is PhysicalOnboardingStage.WORKSPACE_SOURCES
            and permit.admission.selected_identity_sha256 is None
            and permit.request.cell_id == permit.admission.cell_id
            and permit.request.session_id == permit.admission.session_id
            and permit.request.action_id == registration.action_id
            and registration.budget.timeout_ms == SOURCE_PREFLIGHT_TIMEOUT_MS
            and registration.budget.maximum_output_bytes
            == SOURCE_PREFLIGHT_MAX_REPORT_BYTES
            and all(
                getattr(registration.budget, name) == 0
                for name in (
                    "maximum_opens",
                    "maximum_reads",
                    "maximum_writes",
                    "maximum_frames",
                    "maximum_closes",
                )
            ),
            "ZERO_DEVICE_PERMIT_REQUIRED",
        )
        _require(
            type(deadline_ns) is int and 0 < deadline_ns <= permit.expires_at_ns,
            "EXACT_DEADLINE_REQUIRED",
        )

        def check() -> None:
            _require(not cancellation.is_set(), "CANCELLED")
            _require(self._clock() < deadline_ns, "DEADLINE_EXPIRED")

        check()
        permit_hash = permit.permit_sha256
        authorize_consumed_permit(permit)
        check()
        _require(permit.permit_sha256 == permit_hash, "PERMIT_CHANGED")
        data: dict[str, Any] = {
            "schema": SOURCE_PREFLIGHT_SCHEMA,
            "composition": self.composition,
            "binding": {
                "cell_id": permit.request.cell_id,
                "session_id": permit.request.session_id,
                "attempt_id": permit.attempt_id,
                "operator_id": self.operator_id,
                "workspace_source_sha256": self.expected_source_sha256,
                "permit_sha256": permit.permit_sha256,
                "worker_sha256": self.worker_executable_sha256,
                "operation_sha256": SOURCE_PREFLIGHT_OPERATION_SHA256,
            },
            "files": [],
            "observations": {
                "software_fingerprint_before": None,
                "software_fingerprint_after": None,
                "fixed_snapshot_sha256_before": None,
                "fixed_snapshot_sha256_after": None,
                "foundation": None,
                "native_development_build": None,
                "failed_source": None,
                "fixed_file_pin": (
                    "WINDOWS_READ_ONLY_SHARING"
                    if os.name == "nt"
                    else "PORTABLE_BEFORE_AFTER_ONLY"
                ),
            },
            "errors": [],
            "canonical_stage_holds": list(_HOLDS),
            "canonical_stage_pass": False,
            "physical_authority": False,
            "device_io_performed": False,
            "power_state": "UNKNOWN",
            "limitations": list(_LIMITATIONS),
        }
        facts = data["observations"]
        try:
            root = _checked(self.workspace, directory=True)
            _fixed_metadata(root, check)
            with _pins(root, check):
                rows, content = _snapshot(root, check)
                data["files"] = rows
                facts["fixed_snapshot_sha256_before"] = _hash(_canonical(rows))
                facts["software_fingerprint_before"] = source_fingerprint(root)
                check()
                actual_worker = next(
                    row["sha256"]
                    for row in rows
                    if row["path"] == SOURCE_PREFLIGHT_WORKER_PATH
                )
                _require(
                    actual_worker == self.worker_executable_sha256,
                    "WORKER_SOURCE_CHANGED",
                )
                _require(
                    facts["software_fingerprint_before"] == self.expected_source_sha256,
                    "SOFTWARE_SOURCE_CHANGED",
                )
                foundation = load_physical_onboarding_foundation(root)
                check()
                facts["foundation"] = {
                    "foundation_sha256": foundation.source_sha256,
                    "catalog_sha256": foundation.stage_catalog.source_sha256,
                    "icd_sha256": foundation.workcell_interface_contract.content_sha256,
                    "support_sha256": foundation.workcell_interface_contract.source_bindings[
                        "static_camera_support_design"
                    ].sha256,
                    "zero_physical_authority": foundation.zero_physical_authority,
                    "runtime_activation": foundation.runtime_activation,
                    "open_implementation_gates": list(
                        foundation.open_implementation_gates
                    ),
                }
                facts["native_development_build"] = _native_manifest(content, rows)
                after, _ = _snapshot(root, check)
                facts["fixed_snapshot_sha256_after"] = _hash(_canonical(after))
                facts["software_fingerprint_after"] = source_fingerprint(root)
                check()
        except PhysicalSourcePreflightError as error:
            if error.code in {"CANCELLED", "DEADLINE_EXPIRED"}:
                raise
            data["errors"].append(error.code)
            facts["failed_source"] = error.relative_path
        except (OSError, ValueError, RuntimeError):
            data["errors"].append("SOURCE_OR_CONTRACT_VERIFICATION_FAILED")
        check()
        _require(permit.permit_sha256 == permit_hash, "PERMIT_CHANGED")
        data["checks"] = _checks(data)
        data["outcome"] = (
            "FILE_CHECKS_COHERENT"
            if not data["errors"] and all(row["passed"] for row in data["checks"])
            else "HELD"
        )
        report = PhysicalSourcePreflightReport(_canonical(data))
        _require(
            len(report.payload) <= registration.budget.maximum_output_bytes,
            "REGISTERED_OUTPUT_BOUND",
        )
        check()
        evidence = CampaignEvidence(
            SOURCE_PREFLIGHT_SCHEMA, "physical-source-preflight", report.payload
        )
        receipt = WorkerReceipt(
            permit.attempt_id,
            permit.permit_sha256,
            self.worker_executable_sha256,
            None,
            EffectCertainty.CONFIRMED,
            True,
            ObservedPowerState.UNKNOWN,
            0,
            0,
            0,
            0,
            0,
            len(report.payload),
            (report.sha256,),
            self.composition,
        )
        self.report = report
        return RetainedCampaignExecution(receipt, (evidence,))
