"""Actual file-only workspace receipt and permanently BLOCKED V2 review chain.

This module never calls a V1 controller, device enumerator, native helper or
serial/camera backend. Existing source/foundation/host calculators provide the
software observations. Missing installed isolation and HZ-012 evidence cannot
be filled by these observations, operator labels, or a consent checkbox.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
from threading import Event
import time
from typing import Any, Callable, Iterator

from packaging.version import Version

from rocell.application import physical_host_readiness as host_module
from rocell.application import physical_onboarding_foundation as foundation_module
from rocell.application import physical_onboarding_policy as policy_module
from rocell.application.physical_camera_prerequisites import (
    PhysicalCameraPrerequisites,
    verify_physical_camera_prerequisites,
)
from rocell.application.physical_onboarding_durability import read_bounded_regular_file
from rocell.application.physical_source_preflight import _checked
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_diagnostic_export import _directory_guard
from rocell.rc03 import BuildSnapshot, import_build_snapshot


RECEIPT_SCHEMA = "rocell.workspace_source_receipt.v1"
ASSESSMENT_SCHEMA = "rocell.workspace_source_assessment.v1"
REVIEW_SCHEMA = "rocell.workspace_source_review.v1"
RECEIPT_LABEL = "workspace-source-receipt-v1"
ASSESSMENT_LABEL = "workspace-source-assessment-v1"
REVIEW_LABEL = "workspace-source-review-v1"
MAX_EVIDENCE_BYTES = 256 * 1024
MAX_SUMMARY_BYTES = 24 * 1024
MAX_COLLECTION_DURATION_NS = 30_000_000_000
MAX_SOURCE_FILES = 128
MAX_SOURCE_FILE_BYTES = 2 * 1024 * 1024
MAX_SOURCE_TOTAL_BYTES = 32 * 1024 * 1024
CHECK_IDS = (
    "controlled_build_sources",
    "foundation_semantics",
    "unchanged_file_snapshot",
    "runtime_fail_closed",
    "launcher_and_bootstrap_present",
    "base_software_ready",
    "static_camera_plan_selected",
)
MISSING_REQUIREMENTS = (
    "DISCONNECTED_ACTUATOR_POWER_NOT_OBSERVED",
    "HZ_012_QUALIFICATION_EVIDENCE_MISSING",
    "STATIC_CAMERA_RELEASE_NOT_QUALIFIED",
)
_FLAGS = {
    "physical_authority": False,
    "canonical_stage_pass": False,
    "device_io_performed": False,
    "power_state": "UNKNOWN",
}
_EFFECTS = {
    "device_open_count": 0,
    "serial_write_count": 0,
    "power_event_count": 0,
    "motion_command_count": 0,
    "contact_command_count": 0,
}
_BINDING_FIELDS = {
    "source_sha256",
    "session_id",
    "origin_launch_id",
    "collection_launch_id",
    "header_sha256",
    "prerequisites_sha256",
    "operator_id",
}
_FIXED_FILES = tuple(
    sorted(
        set(
            (
                "software/config/physical_onboarding_policy.json",
                *policy_module._EXPECTED_CONTROLLED_SOURCES,
            )
        )
    )
)
_RC03_ROOT = "active-project/RoCell_v0_3"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_LIMITATIONS = (
    "ACTUAL_CONTROLLED_FILES_AND_HOST_PACKAGE_METADATA_ONLY",
    "WORKSPACE_FINGERPRINT_BEFORE_AFTER_NOT_PERSISTENT_EXECUTION_AUTHORITY",
    "NO_ISOLATION_MEASUREMENT_OR_HZ_012_QUALIFICATION_EVIDENCE",
    "NO_RECEIVED_HARDWARE_DRIVER_OR_STATIC_CAMERA_RELEASE_QUALIFICATION",
    "OPERATOR_LABELS_DO_NOT_AUTHENTICATE_INDEPENDENT_PEOPLE",
)


class WorkspaceSourceEvidenceError(ValueError):
    def __init__(
        self,
        code: str = "WORKSPACE_SOURCE_EVIDENCE_INVALID",
        *,
        receipt: WorkspaceSourceReceipt | None = None,
    ) -> None:
        self.code = code
        # Complete verified evidence may survive a late Stop/source/guard failure
        # as historical diagnostics, never as a current successful publication.
        self.receipt = receipt
        super().__init__(code)


def _require(value: bool, code: str = "WORKSPACE_SOURCE_EVIDENCE_INVALID") -> None:
    if not value:
        raise WorkspaceSourceEvidenceError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha(value: Any) -> str:
    _require(type(value) is str and _SHA.fullmatch(value) is not None)
    return str(value)


def _label(value: Any) -> str:
    _require(
        type(value) is str
        and bool(value)
        and value.strip() == value
        and len(value.encode("utf-8")) <= 128
        and all(ord(c) >= 32 and ord(c) != 127 for c in value)
    )
    return str(value)


def _identifier(value: Any) -> str:
    _label(value)
    _require(_ID.fullmatch(value) is not None)
    return str(value)


def _exact(value: Any, fields: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == fields)
    return value


def _same(value: Any, expected: Any) -> None:
    _require(_canonical(value) == _canonical(expected))


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        _require(key not in result, "DUPLICATE_FIELD")
        result[key] = value
    return result


def _parse(payload: bytes) -> dict[str, Any]:
    _require(
        type(payload) is bytes and 0 < len(payload) <= MAX_EVIDENCE_BYTES,
        "EVIDENCE_BYTE_LIMIT",
    )
    try:
        value = json.loads(payload, object_pairs_hook=_pairs)
        nodes = 0

        def node(item: Any, depth: int) -> None:
            nonlocal nodes
            nodes += 1
            _require(depth <= 12 and nodes <= 20_000, "EVIDENCE_SHAPE_LIMIT")
            if item is None or type(item) is bool:
                return
            if type(item) is int:
                _require(-(2**63) <= item <= 2**63 - 1)
            elif type(item) is str:
                _require(len(item.encode("utf-8")) <= 64 * 1024)
            elif type(item) is list:
                _require(len(item) <= 128)
                for child in item:
                    node(child, depth + 1)
            elif type(item) is dict:
                _require(len(item) <= 128)
                for key, child in item.items():
                    node(key, depth + 1)
                    node(child, depth + 1)
            else:
                raise WorkspaceSourceEvidenceError()

        node(value, 0)
        _require(
            type(value) is dict and _canonical(value) == payload,
            "CANONICAL_BYTES_REQUIRED",
        )
        return value
    except WorkspaceSourceEvidenceError:
        raise
    except (ValueError, TypeError, RecursionError, UnicodeError) as error:
        raise WorkspaceSourceEvidenceError() from error


def _binding(value: Any) -> dict[str, Any]:
    result = _exact(value, _BINDING_FIELDS)
    for key, field in result.items():
        if key.endswith("sha256"):
            _sha(field)
        elif key == "operator_id":
            _label(field)
        else:
            _identifier(field)
    return result


def _relative(value: Any) -> str:
    _require(
        type(value) is str
        and 0 < len(value) <= 512
        and "\\" not in value
        and ":" not in value
    )
    path = PurePosixPath(value)
    _require(
        not path.is_absolute()
        and str(path) == value
        and all(part not in {".", ".."} for part in path.parts)
    )
    return value


def _build(value: Any) -> BuildSnapshot:
    _exact(
        value,
        {
            "manifest_id",
            "manifest_sha256",
            "design_revision",
            "active_build_id",
            "source_hashes",
            "selected_routes",
            "gate_statuses",
            "hard_blockers",
            "physical_release_status",
            "tag_coordinate_source",
            "camera_exact_model",
            "camera_state",
            "safe_to_power_robot",
            "contact_enabled",
            "integrity_verified",
        },
    )
    _sha(value["manifest_sha256"])
    for path, digest in value["source_hashes"].items():
        _relative(path)
        _sha(digest)
    _require(1 <= len(value["source_hashes"]) <= 64)
    _require(all(type(v) is bool for v in value["selected_routes"].values()))
    _require(all(type(v) is str and v for v in value["gate_statuses"].values()))
    result = BuildSnapshot(**{**value, "hard_blockers": tuple(value["hard_blockers"])})
    _same(value, result.to_dict())
    return result


def _host(value: Any, build: BuildSnapshot) -> host_module.PhysicalHostReadinessReport:
    _exact(
        value,
        {
            "schema",
            "platform",
            "workspace",
            "build",
            "runtime_fail_closed",
            "launcher_present",
            "environment",
            "dependencies",
            "readiness",
            "blockers",
            "authority",
            "report_sha256",
        },
    )
    platform = _exact(
        value["platform"], {"system", "release", "python_version", "python_64_bit"}
    )
    built = _exact(
        value["build"],
        {
            "active_build_id",
            "manifest_id",
            "snapshot_sha256",
            "static_camera_plan_selected",
            "static_camera_freeze_promoted",
        },
    )
    env = _exact(
        value["environment"],
        {
            "bootstrap_script_present",
            "workspace_venv_present",
            "running_from_workspace_venv",
            "workspace_venv_integrity_ready",
            "workspace_venv_pyvenv_cfg_sha256",
            "workspace_interpreter_path",
            "resolved_interpreter_path",
            "workspace_interpreter_sha256",
            "python_prefix_matches_workspace_venv",
            "python_base_prefix_distinct",
            "interpreter_identity_valid",
            "runtime_module_origins",
            "runtime_origins_match_workspace",
            "device_access_environment_ready",
        },
    )
    readiness = _exact(
        value["readiness"],
        {
            "base_software_ready",
            "camera_diagnostics_dependencies_ready",
            "arm_diagnostics_dependencies_ready",
            "development_dependencies_ready",
        },
    )
    _require(type(platform["python_64_bit"]) is bool)
    _require(
        all(
            type(built[k]) is bool
            for k in ("static_camera_plan_selected", "static_camera_freeze_promoted")
        )
    )
    _require(
        all(type(value[k]) is bool for k in ("runtime_fail_closed", "launcher_present"))
    )
    _require(all(type(v) is bool for v in readiness.values()))
    non_bool_environment = {
        "workspace_venv_pyvenv_cfg_sha256",
        "workspace_interpreter_path",
        "resolved_interpreter_path",
        "workspace_interpreter_sha256",
        "runtime_module_origins",
    }
    _require(
        all(type(v) is bool for k, v in env.items() if k not in non_bool_environment)
    )
    dependencies = tuple(
        host_module.HostDependency(**row) for row in value["dependencies"]
    )
    _require(
        tuple(row.import_name for row in dependencies)
        == tuple(host_module._DEPENDENCY_VERSION_POLICIES)
    )
    _require(
        all(
            row.version_specifier
            == host_module._DEPENDENCY_VERSION_POLICIES[row.import_name]
            for row in dependencies
        )
    )
    origins = tuple(
        host_module.RuntimeModuleOrigin(**row) for row in env["runtime_module_origins"]
    )
    _require(
        tuple(row.import_name for row in origins)
        == tuple(host_module._RUNTIME_MODULE_PATHS)
    )
    result = host_module.PhysicalHostReadinessReport(
        platform_system=platform["system"],
        platform_release=platform["release"],
        python_version=platform["python_version"],
        python_64_bit=platform["python_64_bit"],
        workspace=value["workspace"],
        active_build_id=built["active_build_id"],
        manifest_id=built["manifest_id"],
        build_snapshot_sha256=built["snapshot_sha256"],
        static_camera_plan_selected=built["static_camera_plan_selected"],
        static_camera_freeze_promoted=built["static_camera_freeze_promoted"],
        runtime_fail_closed=value["runtime_fail_closed"],
        launcher_present=value["launcher_present"],
        dependencies=dependencies,
        blockers=tuple(value["blockers"]),
        runtime_module_origins=origins,
        **readiness,
        **{k: v for k, v in env.items() if k != "runtime_module_origins"},
    )
    _same(value, result.to_dict())
    _same(
        (built["active_build_id"], built["manifest_id"], built["snapshot_sha256"]),
        (build.active_build_id, build.manifest_id, build.snapshot_hash),
    )
    # Independently recalculate retained aggregate arithmetic without find_spec,
    # filesystem access, package imports, or replaying the host assessor.
    deps = {row.import_name: row for row in dependencies}
    base = (
        Version(result.python_version) >= Version("3.10")
        and result.python_64_bit
        and result.platform_system in host_module._SUPPORTED_HOSTS
        and result.runtime_fail_closed
        and result.launcher_present
        and result.bootstrap_script_present
        and result.static_camera_plan_selected
        and result.runtime_origins_match_workspace
        and deps["packaging"].version_policy_satisfied
        and deps["PIL"].version_policy_satisfied
    )
    device = (
        result.workspace_venv_present
        and result.running_from_workspace_venv
        and result.runtime_origins_match_workspace
        and all(
            deps[name].origin_within_workspace_venv
            and deps[name].version_policy_satisfied
            for name in host_module._DEVICE_DEPENDENCY_NAMES
        )
    )
    expected = {
        "base_software_ready": base,
        "camera_diagnostics_dependencies_ready": base
        and device
        and deps["numpy"].version_policy_satisfied
        and deps["cv2"].version_policy_satisfied,
        "arm_diagnostics_dependencies_ready": base
        and device
        and deps["serial"].version_policy_satisfied,
        "development_dependencies_ready": base
        and device
        and deps["cv2"].version_policy_satisfied
        and deps["serial"].version_policy_satisfied
        and deps["pytest"].version_policy_satisfied
        and deps["pytest"].origin_within_workspace_venv,
    }
    _same(readiness, expected)
    _same(result.device_access_environment_ready, device)
    _same(result.running_from_workspace_venv, result.interpreter_identity_valid)
    _same(result.workspace_venv_present, result.workspace_venv_integrity_ready)
    _same(
        result.static_camera_freeze_promoted,
        build.camera_exact_model is not None
        and build.camera_state == "QUALIFIED"
        and "FIXED_CAMERA_FALLBACK_ARCHITECTURE_NOT_RELEASED"
        not in build.hard_blockers,
    )
    _require(type(value["blockers"]) is list and len(value["blockers"]) <= 64)
    return result


def _source_rows(value: Any, build: BuildSnapshot) -> dict[str, dict[str, Any]]:
    _require(type(value) is list and 1 <= len(value) <= MAX_SOURCE_FILES)
    paths = []
    total = 0
    for row in value:
        _exact(row, {"relative_path", "bytes", "sha256"})
        paths.append(_relative(row["relative_path"]))
        _require(
            type(row["bytes"]) is int and 0 < row["bytes"] <= MAX_SOURCE_FILE_BYTES
        )
        total += row["bytes"]
        _sha(row["sha256"])
    expected = sorted(
        set((*_FIXED_FILES, *(_RC03_ROOT + "/" + p for p in build.source_hashes)))
    )
    _same(paths, expected)
    _require(total <= MAX_SOURCE_TOTAL_BYTES)
    rows = {row["relative_path"]: row for row in value}
    _same(rows["software/config/system_manifest.json"]["sha256"], build.manifest_sha256)
    for relative, digest in build.source_hashes.items():
        _same(rows[_RC03_ROOT + "/" + relative]["sha256"], digest)
    return rows


def _foundation(value: Any, rows: dict[str, dict[str, Any]]) -> None:
    _exact(
        value,
        {
            "foundation_id",
            "source_sha256",
            "runtime_activation",
            "zero_physical_authority",
            "contracts",
            "open_implementation_gates",
        },
    )
    _same(value["foundation_id"], foundation_module.PHYSICAL_ONBOARDING_FOUNDATION_ID)
    _same(
        value["source_sha256"],
        rows["software/config/physical_onboarding_foundation.json"]["sha256"],
    )
    _same(value["runtime_activation"], False)
    _same(value["zero_physical_authority"], True)
    _same(
        value["open_implementation_gates"], list(foundation_module._EXPECTED_OPEN_GATES)
    )
    expected = [
        {"id": name, "path": path, "sha256": rows[path]["sha256"]}
        for name, path in foundation_module._EXPECTED_CONTRACTS
    ]
    _same(value["contracts"], expected)


def _checks(host: host_module.PhysicalHostReadinessReport) -> list[dict[str, Any]]:
    return [
        {"check_id": name, "passed": passed}
        for name, passed in zip(
            CHECK_IDS,
            (
                True,
                True,
                True,
                host.runtime_fail_closed,
                host.launcher_present and host.bootstrap_script_present,
                host.base_software_ready,
                host.static_camera_plan_selected,
            ),
        )
    ]


def _validate_receipt(payload: bytes) -> dict[str, Any]:
    try:
        data = _parse(payload)
        _exact(
            data,
            {
                "schema",
                "status",
                "stage",
                "binding",
                "collection",
                "source_files",
                "build_snapshot",
                "foundation",
                "host_readiness",
                "workspace_requirements",
                "software_checks",
                "effects",
                "limitations",
                *set(_FLAGS),
            },
        )
        _same(data["schema"], RECEIPT_SCHEMA)
        _same(data["status"], "FILE_FACTS_COLLECTED")
        _same(data["stage"], "workspace_sources")
        binding = _binding(data["binding"])
        _same({k: data[k] for k in _FLAGS}, _FLAGS)
        _same(data["effects"], _EFFECTS)
        _same(data["limitations"], list(_LIMITATIONS))
        collection = _exact(
            data["collection"],
            {
                "started_monotonic_ns",
                "finished_monotonic_ns",
                "recorded_at_ns",
                "before_source_sha256",
                "after_source_sha256",
                "before_files_sha256",
                "after_files_sha256",
                "consistency_scope",
            },
        )
        for key in ("started_monotonic_ns", "finished_monotonic_ns", "recorded_at_ns"):
            _require(type(collection[key]) is int and 0 < collection[key] <= 2**63 - 1)
        _require(
            0
            <= collection["finished_monotonic_ns"] - collection["started_monotonic_ns"]
            < MAX_COLLECTION_DURATION_NS
        )
        _same(collection["before_source_sha256"], binding["source_sha256"])
        _same(collection["after_source_sha256"], binding["source_sha256"])
        _same(
            collection["before_files_sha256"], _hash(_canonical(data["source_files"]))
        )
        _same(collection["after_files_sha256"], collection["before_files_sha256"])
        _same(
            collection["consistency_scope"],
            "BOUNDED_FILE_OBSERVATION_NOT_PERSISTENT_EXECUTION_AUTHORITY",
        )
        build = _build(data["build_snapshot"])
        rows = _source_rows(data["source_files"], build)
        _foundation(data["foundation"], rows)
        host = _host(data["host_readiness"], build)
        _same(data["software_checks"], _checks(host))
        requirement = _exact(
            data["workspace_requirements"],
            {
                "stage",
                "status",
                "required_effect_classes",
                "actuator_power_requirement",
                "owned_artifacts",
                "hazard_ids",
                "intake_rows",
                "required_records",
            },
        )
        _require(
            type(requirement) is dict
            and requirement["stage"] == "workspace_sources"
            and requirement["status"] == "REQUIREMENTS_ONLY"
            and requirement["actuator_power_requirement"] == "DISCONNECTED_REQUIRED"
            and requirement["hazard_ids"] == ["HZ-012"]
        )
        _same(requirement["required_effect_classes"], ["NO_DEVICE_IO"])
        _same(requirement["intake_rows"], [])
        _same(
            requirement["required_records"],
            [
                "ACTUAL_CONTROLLED_SOURCE_EVIDENCE",
                "REVIEWED_ACTUATOR_ISOLATION_OBSERVATION",
                "HZ_012_OWNERSHIP_QUALIFICATION_EVIDENCE",
            ],
        )
        return data
    except WorkspaceSourceEvidenceError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OverflowError,
        RecursionError,
    ) as error:
        raise WorkspaceSourceEvidenceError() from error


def _assessment_document(receipt: WorkspaceSourceReceipt) -> dict[str, Any]:
    data = receipt.to_dict()
    missing = list(MISSING_REQUIREMENTS)
    if not all(row["passed"] for row in data["software_checks"]):
        missing.append("SOFTWARE_PREREQUISITES_NOT_READY")
    return {
        "schema": ASSESSMENT_SCHEMA,
        "status": "ASSESSED",
        "verdict": "BLOCKED",
        "stage": "workspace_sources",
        "binding": data["binding"],
        "receipt_sha256": receipt.sha256,
        "software_checks": data["software_checks"],
        "missing_requirements": missing,
        "effects": _EFFECTS,
        "meaning": "Software facts do not establish disconnected actuator power, HZ-012 qualification or physical release.",
        **_FLAGS,
    }


def _validate_assessment(payload: bytes) -> dict[str, Any]:
    data = _parse(payload)
    _exact(
        data,
        {
            "schema",
            "status",
            "verdict",
            "stage",
            "binding",
            "receipt_sha256",
            "software_checks",
            "missing_requirements",
            "effects",
            "meaning",
            *set(_FLAGS),
        },
    )
    _binding(data["binding"])
    _sha(data["receipt_sha256"])
    _same(
        (data["schema"], data["status"], data["verdict"], data["stage"]),
        (ASSESSMENT_SCHEMA, "ASSESSED", "BLOCKED", "workspace_sources"),
    )
    _same(data["effects"], _EFFECTS)
    _same({k: data[k] for k in _FLAGS}, _FLAGS)
    checks = data["software_checks"]
    _require(type(checks) is list and len(checks) == len(CHECK_IDS))
    for row, check_id in zip(checks, CHECK_IDS):
        _exact(row, {"check_id", "passed"})
        _require(row["check_id"] == check_id and type(row["passed"]) is bool)
    _require(all(row["passed"] for row in checks[:3]))
    _same(
        data["missing_requirements"],
        [*MISSING_REQUIREMENTS]
        + (
            []
            if all(row["passed"] for row in checks)
            else ["SOFTWARE_PREREQUISITES_NOT_READY"]
        ),
    )
    _same(
        data["meaning"],
        "Software facts do not establish disconnected actuator power, HZ-012 qualification or physical release.",
    )
    return data


def _validate_review(payload: bytes) -> dict[str, Any]:
    data = _parse(payload)
    _exact(
        data,
        {
            "schema",
            "status",
            "verdict",
            "stage",
            "binding",
            "receipt_sha256",
            "assessment_sha256",
            "reviewer_id",
            "review_launch_id",
            "distinct_operator_labels",
            "authenticated_independent_people",
            "effects",
            *set(_FLAGS),
        },
    )
    binding = _binding(data["binding"])
    for key in ("receipt_sha256", "assessment_sha256"):
        _sha(data[key])
    _same(
        (data["schema"], data["status"], data["verdict"], data["stage"]),
        (REVIEW_SCHEMA, "ACKNOWLEDGED_BLOCKED", "BLOCKED", "workspace_sources"),
    )
    _label(data["reviewer_id"])
    _identifier(data["review_launch_id"])
    _require(
        data["reviewer_id"].casefold() != binding["operator_id"].casefold(),
        "DISTINCT_REVIEWER_REQUIRED",
    )
    _same(data["distinct_operator_labels"], True)
    _same(data["authenticated_independent_people"], False)
    _same(data["effects"], _EFFECTS)
    _same({k: data[k] for k in _FLAGS}, _FLAGS)
    return data


@dataclass(frozen=True, slots=True)
class WorkspaceSourceReceipt:
    payload: bytes

    def __post_init__(self) -> None:
        _validate_receipt(self.payload)

    @property
    def sha256(self) -> str:
        return _hash(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _validate_receipt(self.payload)

    def safe_summary(self) -> dict[str, Any]:
        data = self.to_dict()
        return _summary(
            {
                "schema": "rocell.workspace_source_receipt_summary.v1",
                "status": data["status"],
                "binding": data["binding"],
                "receipt_sha256": self.sha256,
                "software_checks": data["software_checks"],
                "source_file_count": len(data["source_files"]),
                "foundation_contract_count": len(data["foundation"]["contracts"]),
                "host_blocker_count": len(data["host_readiness"]["blockers"]),
                **_FLAGS,
            }
        )


@dataclass(frozen=True, slots=True)
class WorkspaceSourceAssessment:
    payload: bytes

    def __post_init__(self) -> None:
        _validate_assessment(self.payload)

    @property
    def sha256(self) -> str:
        return _hash(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _validate_assessment(self.payload)

    def safe_summary(self) -> dict[str, Any]:
        data = self.to_dict()
        return _summary(
            {
                "schema": "rocell.workspace_source_assessment_summary.v1",
                **{
                    k: data[k]
                    for k in (
                        "status",
                        "verdict",
                        "binding",
                        "receipt_sha256",
                        "software_checks",
                        "missing_requirements",
                    )
                },
                "assessment_sha256": self.sha256,
                **_FLAGS,
            }
        )


@dataclass(frozen=True, slots=True)
class WorkspaceSourceReview:
    payload: bytes

    def __post_init__(self) -> None:
        _validate_review(self.payload)

    @property
    def sha256(self) -> str:
        return _hash(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _validate_review(self.payload)

    def safe_summary(self) -> dict[str, Any]:
        data = self.to_dict()
        return _summary(
            {
                "schema": "rocell.workspace_source_review_summary.v1",
                **{
                    k: data[k]
                    for k in (
                        "status",
                        "verdict",
                        "binding",
                        "receipt_sha256",
                        "assessment_sha256",
                        "reviewer_id",
                        "review_launch_id",
                        "distinct_operator_labels",
                        "authenticated_independent_people",
                    )
                },
                "review_sha256": self.sha256,
                **_FLAGS,
            }
        )


def _summary(value: dict[str, Any]) -> dict[str, Any]:
    _require(len(_canonical(value)) <= MAX_SUMMARY_BYTES)
    return json.loads(_canonical(value))


def _payload(value: Any, exact_type: type) -> bytes:
    if type(value) is exact_type:
        return getattr(value, "payload")
    if type(value) is bytes:
        return value
    _require(type(value) is dict)
    # Bound containers/text BEFORE encoding an externally supplied mapping.
    # A self-hash or already-decoded dict is not a size/recursion guarantee.
    nodes, text_bytes = 0, 0

    def bound(item: Any, depth: int) -> None:
        nonlocal nodes, text_bytes
        nodes += 1
        _require(nodes <= 20_000 and depth <= 12, "EVIDENCE_SHAPE_LIMIT")
        if item is None or type(item) is bool:
            return
        if type(item) is int:
            _require(-(2**63) <= item <= 2**63 - 1)
        elif type(item) is str:
            length = len(item.encode("utf-8"))
            text_bytes += length
            _require(
                length <= 64 * 1024 and text_bytes <= MAX_EVIDENCE_BYTES,
                "EVIDENCE_BYTE_LIMIT",
            )
        elif type(item) is list:
            _require(len(item) <= 128)
            for child in item:
                bound(child, depth + 1)
        elif type(item) is dict:
            _require(len(item) <= 128 and all(type(k) is str for k in item))
            for key, child in item.items():
                bound(key, depth + 1)
                bound(child, depth + 1)
        else:
            raise WorkspaceSourceEvidenceError()

    try:
        bound(value, 0)
        result = _canonical(value)
    except (ValueError, TypeError, RecursionError, UnicodeError) as error:
        raise WorkspaceSourceEvidenceError() from error
    _require(len(result) <= MAX_EVIDENCE_BYTES, "EVIDENCE_BYTE_LIMIT")
    return result


def verify_workspace_source_receipt(
    value: Any,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    expected_source_sha256: str,
    expected_session_id: str,
    expected_origin_launch_id: str,
    expected_header_sha256: str,
    expected_receipt_sha256: str,
) -> WorkspaceSourceReceipt:
    _require(type(prerequisites) is PhysicalCameraPrerequisites)
    original = verify_physical_camera_prerequisites(
        prerequisites.payload,
        expected_source_sha256=expected_source_sha256,
        expected_session_id=expected_session_id,
        expected_launch_session_id=expected_origin_launch_id,
        expected_evidence_sha256=prerequisites.evidence_sha256,
    )
    result = WorkspaceSourceReceipt(_payload(value, WorkspaceSourceReceipt))
    _require(result.sha256 == _sha(expected_receipt_sha256), "RECEIPT_HASH_MISMATCH")
    data, prerequisite = result.to_dict(), original.to_dict()
    expected = {
        "source_sha256": _sha(expected_source_sha256),
        "session_id": _identifier(expected_session_id),
        "origin_launch_id": _identifier(expected_origin_launch_id),
        "header_sha256": _sha(expected_header_sha256),
        "prerequisites_sha256": original.evidence_sha256,
    }
    _same({k: data["binding"][k] for k in expected}, expected)
    _same(data["workspace_requirements"], prerequisite["requirements"]["stages"][0])
    rows = {row["relative_path"]: row for row in data["source_files"]}
    for source in prerequisite["source_files"]:
        _same(rows[source["relative_path"]]["sha256"], source["sha256"])
        _same(rows[source["relative_path"]]["bytes"], source["bytes"])
    return result


def assess_workspace_source_receipt(
    receipt: WorkspaceSourceReceipt,
) -> WorkspaceSourceAssessment:
    _require(type(receipt) is WorkspaceSourceReceipt)
    return WorkspaceSourceAssessment(_canonical(_assessment_document(receipt)))


def verify_workspace_source_assessment(
    value: Any, *, receipt: WorkspaceSourceReceipt, expected_assessment_sha256: str
) -> WorkspaceSourceAssessment:
    _require(type(receipt) is WorkspaceSourceReceipt)
    result = WorkspaceSourceAssessment(_payload(value, WorkspaceSourceAssessment))
    _require(
        result.sha256 == _sha(expected_assessment_sha256), "ASSESSMENT_HASH_MISMATCH"
    )
    _same(result.to_dict(), _assessment_document(receipt))
    return result


def review_workspace_source_assessment(
    receipt: WorkspaceSourceReceipt,
    assessment: WorkspaceSourceAssessment,
    *,
    reviewer_id: str,
    review_launch_id: str,
) -> WorkspaceSourceReview:
    _require(
        type(receipt) is WorkspaceSourceReceipt
        and type(assessment) is WorkspaceSourceAssessment
    )
    verified = verify_workspace_source_assessment(
        assessment, receipt=receipt, expected_assessment_sha256=assessment.sha256
    )
    return WorkspaceSourceReview(
        _canonical(
            {
                "schema": REVIEW_SCHEMA,
                "status": "ACKNOWLEDGED_BLOCKED",
                "verdict": "BLOCKED",
                "stage": "workspace_sources",
                "binding": receipt.to_dict()["binding"],
                "receipt_sha256": receipt.sha256,
                "assessment_sha256": verified.sha256,
                "reviewer_id": _label(reviewer_id),
                "review_launch_id": _identifier(review_launch_id),
                "distinct_operator_labels": True,
                "authenticated_independent_people": False,
                "effects": _EFFECTS,
                **_FLAGS,
            }
        )
    )


def verify_workspace_source_review(
    value: Any,
    *,
    receipt: WorkspaceSourceReceipt,
    assessment: WorkspaceSourceAssessment,
    expected_review_sha256: str,
) -> WorkspaceSourceReview:
    result = WorkspaceSourceReview(_payload(value, WorkspaceSourceReview))
    _require(result.sha256 == _sha(expected_review_sha256), "REVIEW_HASH_MISMATCH")
    data = result.to_dict()
    expected = review_workspace_source_assessment(
        receipt,
        assessment,
        reviewer_id=data["reviewer_id"],
        review_launch_id=data["review_launch_id"],
    )
    _same(data, expected.to_dict())
    return result


def _roster(root: Path) -> tuple[str, ...]:
    raw = read_bounded_regular_file(
        _checked(root / "software/config/system_manifest.json"),
        maximum_bytes=256 * 1024,
    )
    manifest = json.loads(raw, object_pairs_hook=_pairs)
    _require(manifest["rc03"]["root"] == _RC03_ROOT, "CONTROLLED_ROOT_CHANGED")
    sources = manifest["rc03"]["source_snapshot"]
    _require(type(sources) is list and 1 <= len(sources) <= 64)
    paths = []
    for row in sources:
        _exact(row, {"path", "sha256"})
        paths.append(_RC03_ROOT + "/" + _relative(row["path"]))
        _sha(row["sha256"])
    _require(len(set(paths)) == len(paths))
    result = tuple(sorted(set((*_FIXED_FILES, *paths))))
    _require(len(result) <= MAX_SOURCE_FILES)
    return result


@contextmanager
def _pins(
    root: Path,
    roster: tuple[str, ...],
    check: Callable[[], None],
    *,
    allow_directory_write_sharing: bool = False,
) -> Iterator[None]:
    """Regular disk-file sharing pins only; no device/helper handles or calls."""
    with ExitStack() as stack:
        for parent in sorted({(root / relative).parent for relative in roster}):
            check()
            stack.enter_context(
                _directory_guard(
                    parent,
                    allow_directory_write_sharing=allow_directory_write_sharing,
                )
            )
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
        for relative in roster:
            check()
            path = _checked(root / relative)
            size = path.stat().st_size
            total += size
            _require(
                0 < size <= MAX_SOURCE_FILE_BYTES and total <= MAX_SOURCE_TOTAL_BYTES,
                "SOURCE_BYTE_LIMIT",
            )
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
    root: Path, roster: tuple[str, ...], check: Callable[[], None]
) -> list[dict[str, Any]]:
    rows, total = [], 0
    for relative in roster:
        check()
        raw = read_bounded_regular_file(
            _checked(root / relative),
            maximum_bytes=min(MAX_SOURCE_FILE_BYTES, MAX_SOURCE_TOTAL_BYTES - total),
        )
        check()
        _require(bool(raw), "EMPTY_SOURCE")
        total += len(raw)
        rows.append(
            {"relative_path": relative, "bytes": len(raw), "sha256": _hash(raw)}
        )
    return rows


def collect_workspace_source_receipt(
    workspace: Path,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    source_sha256: str,
    session_id: str,
    origin_launch_id: str,
    collection_launch_id: str,
    header_sha256: str,
    operator_id: str,
    cancellation: Event,
    progress: Callable[[str], None] | None = None,
) -> WorkspaceSourceReceipt:
    """Explicit bounded file collection; no durable write or stage mutation."""
    _require(
        type(prerequisites) is PhysicalCameraPrerequisites
        and type(cancellation) is Event
    )
    _require(progress is None or callable(progress))
    binding = _binding(
        {
            "source_sha256": source_sha256,
            "session_id": session_id,
            "origin_launch_id": origin_launch_id,
            "collection_launch_id": collection_launch_id,
            "header_sha256": header_sha256,
            "prerequisites_sha256": prerequisites.evidence_sha256,
            "operator_id": operator_id,
        }
    )
    original = verify_physical_camera_prerequisites(
        prerequisites.payload,
        expected_source_sha256=source_sha256,
        expected_session_id=session_id,
        expected_launch_session_id=origin_launch_id,
        expected_evidence_sha256=prerequisites.evidence_sha256,
    )
    start = time.monotonic_ns()
    last = start
    result: WorkspaceSourceReceipt | None = None

    def check() -> None:
        nonlocal last
        _require(not cancellation.is_set(), "CANCELLED")
        now = time.monotonic_ns()
        _require(
            type(now) is int
            and 0 < start <= last <= now < start + MAX_COLLECTION_DURATION_NS,
            "TIMED_OUT",
        )
        last = now

    def notify(message: str) -> None:
        check()
        if progress is not None:
            try:
                progress(message)
            except Exception as error:
                raise WorkspaceSourceEvidenceError("PROGRESS_FAILED") from error
        check()

    try:
        check()
        root = _checked(Path(workspace), directory=True)
        notify("Checking current controlled workspace source binding.")
        before = source_fingerprint(root)
        check()
        _require(before == source_sha256, "SOURCE_CHANGED")
        roster = _roster(root)
        with _pins(root, roster, check):
            _same(roster, _roster(root))
            rows = _snapshot(root, roster, check)
            notify("Validating build sources and the zero-authority foundation.")
            build = import_build_snapshot(root)
            check()
            foundation = foundation_module.load_physical_onboarding_foundation(root)
            check()
            policy_module.load_physical_onboarding_policy(root)
            check()
            notify("Reading host software/package metadata without device imports.")
            # platform.release() on a cold Windows Python can launch `ver`.
            # Supply actual non-device OS facts directly, keeping this collector
            # file/software-metadata only even before platform caches are warm.
            if os.name == "nt":
                version = sys.getwindowsversion()
                host_system, host_release = (
                    "Windows",
                    f"{version.major}.{version.minor}.{version.build}",
                )
            else:
                uname = getattr(os, "uname")()
                host_system, host_release = uname.sysname, uname.release
            host = host_module.assess_physical_host_readiness(
                root, build, platform_system=host_system, platform_release=host_release
            )
            check()
            _same(rows, _snapshot(root, roster, check))
            _same(roster, _roster(root))
            after = source_fingerprint(root)
            check()
            _require(after == before, "SOURCE_CHANGED")
            data = {
                "schema": RECEIPT_SCHEMA,
                "status": "FILE_FACTS_COLLECTED",
                "stage": "workspace_sources",
                "binding": binding,
                "collection": {
                    "started_monotonic_ns": start,
                    "finished_monotonic_ns": last,
                    "recorded_at_ns": time.time_ns(),
                    "before_source_sha256": before,
                    "after_source_sha256": after,
                    "before_files_sha256": _hash(_canonical(rows)),
                    "after_files_sha256": _hash(_canonical(rows)),
                    "consistency_scope": "BOUNDED_FILE_OBSERVATION_NOT_PERSISTENT_EXECUTION_AUTHORITY",
                },
                "source_files": rows,
                "build_snapshot": build.to_dict(),
                "foundation": {
                    "foundation_id": foundation.foundation_id,
                    "source_sha256": foundation.source_sha256,
                    "runtime_activation": foundation.runtime_activation,
                    "zero_physical_authority": foundation.zero_physical_authority,
                    "contracts": [
                        {"id": v.id, "path": v.path, "sha256": v.sha256}
                        for v in foundation.contracts
                    ],
                    "open_implementation_gates": list(
                        foundation.open_implementation_gates
                    ),
                },
                "host_readiness": host.to_dict(),
                "workspace_requirements": original.to_dict()["requirements"]["stages"][
                    0
                ],
                "software_checks": _checks(host),
                "effects": _EFFECTS,
                "limitations": list(_LIMITATIONS),
                **_FLAGS,
            }
            result = WorkspaceSourceReceipt(_canonical(data))
            result = verify_workspace_source_receipt(
                result,
                prerequisites=original,
                expected_source_sha256=source_sha256,
                expected_session_id=session_id,
                expected_origin_launch_id=origin_launch_id,
                expected_header_sha256=header_sha256,
                expected_receipt_sha256=result.sha256,
            )
            check()
        notify("File facts collected; physical prerequisites remain unverified.")
        return result
    except WorkspaceSourceEvidenceError as error:
        raise WorkspaceSourceEvidenceError(error.code, receipt=result) from error
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RuntimeError,
        OverflowError,
        RecursionError,
    ) as error:
        raise WorkspaceSourceEvidenceError(
            "COLLECTION_SOURCE_INVALID", receipt=result
        ) from error
