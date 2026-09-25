"""Bounded, hash-bound qualification campaigns for the virtual workcell.

This module turns the existing simulation services into one repeatable
pre-hardware diagnostic.  It deliberately does not introduce another arm,
camera, contact, or trajectory model: every case crosses the same public
application boundaries used by the individual simulation commands.

There are two locked profiles. ``quick`` exercises corrected keyboard and
phone contact plus an independent determinism repeat. ``standard`` adds
nominal and fail-closed adaptive cases, representative legacy runtime faults,
and all 75 independent catalog routes.  A passing campaign means that the
selected software assertions behaved as expected.  It never means that the
workcell is physically ready or that motion/contact is authorized.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Callable, Mapping, cast

from rocell.geometry import Vec3
from rocell.simulation.virtual_profile import (
    VirtualCommissioningProfile,
    VirtualProfileContext,
    load_virtual_commissioning_profile,
)
from rocell.simulation.virtual_workcell import (
    VirtualFaultKind,
    VirtualFaultScript,
    VirtualFaultTrigger,
)
from rocell.typing import compile_development_text

from .adaptive_virtual_session import (
    AdaptiveVirtualSessionReport,
    run_adaptive_virtual_session,
)
from .bootstrap import (
    VirtualWorkcellBootstrap,
    bootstrap_virtual_workcell,
    revalidate_virtual_workcell,
)
from .mission_route_coverage import (
    EXPECTED_KEYBOARD_TARGET_COUNT,
    EXPECTED_MISSION_TARGET_COUNT,
    EXPECTED_PHONE_TARGET_COUNT,
    MissionRouteCoveragePolicy,
    MissionRouteCoverageReport,
    run_mission_route_coverage,
)
from .virtual_arm_camera import make_hidden_virtual_board_truth
from .virtual_session import (
    VirtualSessionReport,
    VirtualSessionScenarioBinding,
    run_virtual_session,
)


PREHARDWARE_QUALIFICATION_SCHEMA = "rocell.prehardware_qualification.v1"
PREHARDWARE_QUALIFICATION_CATALOG = "ROCELL_LOCKED_QUALIFICATION_CASES_V1"
PREHARDWARE_QUALIFICATION_PROFILES = ("quick", "standard")

MAX_QUALIFICATION_CASES = 24
MAX_QUALIFICATION_SESSION_RUNS = 24
MAX_QUALIFICATION_VIRTUAL_COMMANDS = 8_192
MAX_QUALIFICATION_CAMERA_CAPTURES = 256
MAX_QUALIFICATION_LEGACY_EVENTS = 16_384

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_CASE_CATEGORIES = {
    "STARTUP",
    "ADAPTIVE_SESSION",
    "DETERMINISM_REPLAY",
    "LEGACY_FAULT_SESSION",
    "MISSION_ROUTE_COVERAGE",
}
_EXPECTED_OUTCOMES = {
    "SIMULATION_READY",
    "COMPLETE",
    "FAIL_STOP",
    "IDENTICAL",
    "COMPLETE_CATALOG",
}
_SOURCE_KEYS = {
    "bootstrap_sha256",
    "manifest_id",
    "manifest_sha256",
    "snapshot_sha256",
    "design_revision",
    "active_build_id",
    "simulation_bundle_id",
    "simulation_bundle_lock_sha256",
    "alignment_status",
    "alignment_report_sha256",
    "virtual_profile_id",
    "virtual_profile_sha256",
    "virtual_profile_classification",
    "virtual_profile_simulation_only",
    "virtual_profile_physical_release_effect",
    "study_input_id",
    "park_probe_id",
    "historical_layout_report_sha256",
    "historical_mission_coverage_sha256",
}
_SOURCE_DIGEST_KEYS = {
    "bootstrap_sha256",
    "manifest_sha256",
    "snapshot_sha256",
    "simulation_bundle_lock_sha256",
    "alignment_report_sha256",
    "virtual_profile_sha256",
    "historical_layout_report_sha256",
    "historical_mission_coverage_sha256",
}
_COVERAGE_SUMMARY_KEYS = {
    "evaluated",
    "state",
    "complete_catalog_evidence",
    "expected_route_count",
    "expected_keyboard_route_count",
    "expected_phone_route_count",
    "route_count",
    "accepted_route_count",
    "rejected_route_count",
    "keyboard",
    "phone",
    "all_routes_accepted",
    "coverage_report_sha256",
    "selected_profile_source_coverage_sha256",
    "reason",
}


class PrehardwareQualificationError(ValueError):
    """A qualification definition or orchestration contract is invalid."""


def _stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PrehardwareQualificationError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _finite(value: object, label: str, *, bound: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PrehardwareQualificationError(f"{label} must be a finite number")
    parsed = float(value)
    if not math.isfinite(parsed) or abs(parsed) > bound:
        raise PrehardwareQualificationError(
            f"{label} must be finite and within +/-{bound}"
        )
    return parsed


def _freeze_json(value: object, label: str) -> object:
    """Detach and recursively freeze one finite JSON-compatible value."""

    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise PrehardwareQualificationError(f"{label} keys must be text")
            frozen[key] = _freeze_json(child, f"{label}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (tuple, list)):
        return tuple(
            _freeze_json(child, f"{label}[{index}]")
            for index, child in enumerate(value)
        )
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise PrehardwareQualificationError(
        f"{label} must contain only finite JSON-compatible values"
    )


def _freeze_document(value: Mapping[str, object], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    frozen = _freeze_json(value, label)
    assert isinstance(frozen, Mapping)
    return cast(Mapping[str, object], frozen)


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(child) for child in value]
    return value


def _text_commitment(value: str) -> dict[str, object]:
    encoded = value.encode("utf-8")
    return {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "normalized_codepoint_length": len(value),
        "plaintext_serialized": False,
    }


def _contains_only_zero_authority_values(value: object) -> bool:
    """Reject any nested field that claims I/O, command, or release authority."""

    false_fields = {
        "execution_authorized",
        "hardware_accessed",
        "hardware_access_allowed",
        "live_hardware_access_allowed",
        "live_motion_authorized",
        "physical_camera_accessed",
        "physical_contact_authorized",
        "contact_authorized",
        "can_release_physical_gates",
    }

    def visit(node: object) -> bool:
        if isinstance(node, Mapping):
            for key, child in node.items():
                if key == "simulation_only" and child is not True:
                    return False
                if key in false_fields and child is not False:
                    return False
                if key == "hardware_commands_generated" and child != 0:
                    return False
                if key == "physical_release_effect" and child != "NONE":
                    return False
                if not visit(child):
                    return False
        elif isinstance(node, (tuple, list)):
            return all(visit(child) for child in node)
        return True

    return visit(value)


def _zero_authority(mapping: Mapping[str, object]) -> bool:
    """Check nested authority values and require an explicit simulation flag."""

    simulation_flags_seen = 0

    def count(value: object) -> None:
        nonlocal simulation_flags_seen
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key == "simulation_only" and child is True:
                    simulation_flags_seen += 1
                count(child)
        elif isinstance(value, (tuple, list)):
            for child in value:
                count(child)

    count(mapping)
    return (
        simulation_flags_seen > 0
        and _contains_only_zero_authority_values(mapping)
    )


@dataclass(frozen=True, slots=True)
class QualificationCaseSpec:
    """One immutable case from the built-in v1 qualification catalog."""

    case_id: str
    category: str
    expected_outcome: str
    profiles: tuple[str, ...]
    device: str | None = None
    requested_text: str | None = field(default=None, repr=False)
    truth_translation_Wv_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    truth_yaw_board_deg: float = 0.0
    fault_kind: VirtualFaultKind | None = None
    fault_component: str | None = None
    fault_operation: str | None = None
    expected_fault_reason: str | None = None
    expected_correction_count: int | None = None
    maximum_contact_attempts: int | None = None
    reference_case_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or _CASE_ID.fullmatch(self.case_id) is None:
            raise PrehardwareQualificationError("case_id is invalid")
        if self.category not in _CASE_CATEGORIES:
            raise PrehardwareQualificationError(
                f"case {self.case_id} has an unsupported category"
            )
        if self.expected_outcome not in _EXPECTED_OUTCOMES:
            raise PrehardwareQualificationError(
                f"case {self.case_id} has an unsupported expected outcome"
            )
        profiles = tuple(self.profiles)
        if (
            not profiles
            or len(profiles) != len(set(profiles))
            or any(item not in PREHARDWARE_QUALIFICATION_PROFILES for item in profiles)
        ):
            raise PrehardwareQualificationError(
                f"case {self.case_id} has invalid profile membership"
            )
        object.__setattr__(self, "profiles", profiles)

        raw_translation = tuple(self.truth_translation_Wv_mm)
        if len(raw_translation) != 3:
            raise PrehardwareQualificationError(
                f"case {self.case_id} truth translation must have three values"
            )
        translation = tuple(
            _finite(value, f"case {self.case_id} truth translation", bound=100.0)
            for value in raw_translation
        )
        object.__setattr__(self, "truth_translation_Wv_mm", translation)
        object.__setattr__(
            self,
            "truth_yaw_board_deg",
            _finite(
                self.truth_yaw_board_deg,
                f"case {self.case_id} truth yaw",
                bound=30.0,
            ),
        )
        if self.expected_correction_count is not None and (
            isinstance(self.expected_correction_count, bool)
            or not isinstance(self.expected_correction_count, int)
            or not 0 <= self.expected_correction_count <= 1
        ):
            raise PrehardwareQualificationError(
                f"case {self.case_id} expected correction count is invalid"
            )
        if self.maximum_contact_attempts is not None and (
            isinstance(self.maximum_contact_attempts, bool)
            or not isinstance(self.maximum_contact_attempts, int)
            or not 0 <= self.maximum_contact_attempts <= 4
        ):
            raise PrehardwareQualificationError(
                f"case {self.case_id} maximum contact attempts is invalid"
            )

        is_session = self.category in {
            "ADAPTIVE_SESSION",
            "LEGACY_FAULT_SESSION",
        }
        if is_session:
            if self.device not in {"keyboard", "phone"}:
                raise PrehardwareQualificationError(
                    f"case {self.case_id} requires a supported device"
                )
            if not isinstance(self.requested_text, str) or len(self.requested_text) != 1:
                raise PrehardwareQualificationError(
                    f"case {self.case_id} requires exactly one requested character"
                )
        elif self.device is not None or self.requested_text is not None:
            raise PrehardwareQualificationError(
                f"case {self.case_id} cannot carry session text/device fields"
            )

        if self.category == "STARTUP":
            if self.expected_outcome != "SIMULATION_READY":
                raise PrehardwareQualificationError("startup must expect simulation ready")
        elif self.category == "ADAPTIVE_SESSION":
            if self.expected_outcome not in {"COMPLETE", "FAIL_STOP"}:
                raise PrehardwareQualificationError(
                    "adaptive cases must expect COMPLETE or FAIL_STOP"
                )
            if any(
                value is not None
                for value in (
                    self.fault_kind,
                    self.fault_component,
                    self.fault_operation,
                    self.reference_case_id,
                )
            ):
                raise PrehardwareQualificationError(
                    "adaptive cases cannot carry legacy fault/reference selectors"
                )
        elif self.category == "LEGACY_FAULT_SESSION":
            if (
                self.expected_outcome != "FAIL_STOP"
                or not isinstance(self.fault_kind, VirtualFaultKind)
                or not self.fault_component
                or not self.fault_operation
                or not self.expected_fault_reason
            ):
                raise PrehardwareQualificationError(
                    "legacy fault cases require one exact expected fault"
                )
            if (
                self.truth_translation_Wv_mm != (0.0, 0.0, 0.0)
                or self.truth_yaw_board_deg != 0.0
                or self.expected_correction_count is not None
                or self.reference_case_id is not None
            ):
                raise PrehardwareQualificationError(
                    "legacy fault cases cannot carry adaptive controls"
                )
        elif self.category == "DETERMINISM_REPLAY":
            if (
                self.expected_outcome != "IDENTICAL"
                or not self.reference_case_id
                or _CASE_ID.fullmatch(self.reference_case_id) is None
            ):
                raise PrehardwareQualificationError(
                    "determinism cases require one valid reference case"
                )
        elif self.category == "MISSION_ROUTE_COVERAGE":
            if self.expected_outcome != "COMPLETE_CATALOG":
                raise PrehardwareQualificationError(
                    "mission coverage must expect complete catalog evidence"
                )

        if (
            self.expected_outcome == "FAIL_STOP"
            and not self.expected_fault_reason
        ):
            raise PrehardwareQualificationError(
                f"case {self.case_id} must name its expected fail-stop reason"
            )
        if (
            self.expected_outcome != "FAIL_STOP"
            and self.expected_fault_reason is not None
        ):
            raise PrehardwareQualificationError(
                f"case {self.case_id} cannot expect a fault reason"
            )

    def _private_input_commitment(self) -> str:
        return _stable_hash(
            {
                "device": self.device,
                "requested_text": self.requested_text,
                "truth_translation_Wv_mm": list(self.truth_translation_Wv_mm),
                "truth_yaw_board_deg": self.truth_yaw_board_deg,
                "fault_kind": None if self.fault_kind is None else self.fault_kind.value,
                "fault_component": self.fault_component,
                "fault_operation": self.fault_operation,
                "reference_case_id": self.reference_case_id,
            }
        )

    @property
    def requested_text_sha256(self) -> str | None:
        if self.requested_text is None:
            return None
        return hashlib.sha256(self.requested_text.encode("utf-8")).hexdigest()

    @property
    def truth_yaw_board_rad(self) -> float:
        return math.radians(self.truth_yaw_board_deg)

    @property
    def expected_pipeline_completed(self) -> bool | None:
        if self.expected_outcome == "COMPLETE":
            return True
        if self.expected_outcome == "FAIL_STOP":
            return False
        return None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "case_id": self.case_id,
            "category": self.category,
            "expected_outcome": self.expected_outcome,
            "profiles": list(self.profiles),
            "case_input_commitment_sha256": self._private_input_commitment(),
            "expected_fault_reason": self.expected_fault_reason,
            "expected_correction_count": self.expected_correction_count,
            "maximum_contact_attempts": self.maximum_contact_attempts,
        }
        if self.requested_text is not None:
            result["requested_text"] = _text_commitment(self.requested_text)
        if self.category == "ADAPTIVE_SESSION":
            result["synthetic_truth_injection"] = {
                "scope": "HIDDEN_VIRTUAL_PLANT_SIMULATION_ONLY",
                "transform_serialized": False,
                "processor_received_transform": False,
            }
        if self.category == "LEGACY_FAULT_SESSION":
            result["fault"] = {
                "kind": cast(VirtualFaultKind, self.fault_kind).value,
                "component": self.fault_component,
                "operation": self.fault_operation,
            }
        if self.reference_case_id is not None:
            result["reference_case_id"] = self.reference_case_id
        result["case_spec_sha256"] = _stable_hash(result)
        return result

    @property
    def spec_hash(self) -> str:
        return cast(str, self.to_dict()["case_spec_sha256"])


@dataclass(frozen=True, slots=True)
class QualificationCaseResult:
    """Compact evidence for one case; the source report is retained by hash."""

    spec: QualificationCaseSpec
    observed_status: str
    passed: bool
    source_report_sha256: str
    authority_verified: bool
    metrics: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.spec, QualificationCaseSpec):
            raise TypeError("spec must be QualificationCaseSpec")
        if not isinstance(self.observed_status, str) or not self.observed_status:
            raise PrehardwareQualificationError("observed_status must be non-empty")
        if not isinstance(self.passed, bool) or not isinstance(
            self.authority_verified, bool
        ):
            raise PrehardwareQualificationError(
                "case pass and authority results must be boolean"
            )
        _digest(self.source_report_sha256, "case source report sha256")
        object.__setattr__(
            self,
            "metrics",
            _freeze_document(self.metrics, f"case {self.spec.case_id} metrics"),
        )
        if (
            self.metrics.get("hardware_commands_generated") != 0
            or not _contains_only_zero_authority_values(self.metrics)
        ):
            raise PrehardwareQualificationError(
                "case metrics must retain zero authority and zero hardware commands"
            )
        if self.passed and not self.authority_verified:
            raise PrehardwareQualificationError(
                "a case cannot pass without verified zero authority"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "case": self.spec.to_dict(),
            "observed_status": self.observed_status,
            "passed": self.passed,
            "source_report_sha256": self.source_report_sha256,
            "authority_verified": self.authority_verified,
            "metrics": _thaw_json(self.metrics),
        }

    @property
    def result_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class PrehardwareQualificationPolicy:
    """Hard resource limits and profile selection for a v1 campaign."""

    profile: str = "standard"
    maximum_cases: int = MAX_QUALIFICATION_CASES
    maximum_session_runs: int = MAX_QUALIFICATION_SESSION_RUNS
    maximum_total_virtual_commands: int = MAX_QUALIFICATION_VIRTUAL_COMMANDS
    maximum_total_camera_captures: int = MAX_QUALIFICATION_CAMERA_CAPTURES
    maximum_total_legacy_events: int = MAX_QUALIFICATION_LEGACY_EVENTS
    route_policy: MissionRouteCoveragePolicy = field(
        default_factory=MissionRouteCoveragePolicy
    )

    def __post_init__(self) -> None:
        if self.profile not in PREHARDWARE_QUALIFICATION_PROFILES:
            raise PrehardwareQualificationError(
                f"profile must be one of {PREHARDWARE_QUALIFICATION_PROFILES}"
            )
        for name, hard_cap in (
            ("maximum_cases", MAX_QUALIFICATION_CASES),
            ("maximum_session_runs", MAX_QUALIFICATION_SESSION_RUNS),
            (
                "maximum_total_virtual_commands",
                MAX_QUALIFICATION_VIRTUAL_COMMANDS,
            ),
            (
                "maximum_total_camera_captures",
                MAX_QUALIFICATION_CAMERA_CAPTURES,
            ),
            ("maximum_total_legacy_events", MAX_QUALIFICATION_LEGACY_EVENTS),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= hard_cap
            ):
                raise PrehardwareQualificationError(
                    f"{name} must be an integer in [1, {hard_cap}]"
                )
        if not isinstance(self.route_policy, MissionRouteCoveragePolicy):
            raise TypeError("route_policy must be MissionRouteCoveragePolicy")
        selected = self.selected_cases
        if len(selected) > self.maximum_cases:
            raise PrehardwareQualificationError(
                "selected qualification profile exceeds maximum_cases"
            )
        session_runs = sum(
            case.category in {"ADAPTIVE_SESSION", "LEGACY_FAULT_SESSION"}
            for case in selected
        ) + sum(case.category == "DETERMINISM_REPLAY" for case in selected)
        if session_runs > self.maximum_session_runs:
            raise PrehardwareQualificationError(
                "selected qualification profile exceeds maximum_session_runs"
            )

    @property
    def selected_cases(self) -> tuple[QualificationCaseSpec, ...]:
        return default_qualification_case_specs(self.profile)

    @property
    def case_specs(self) -> tuple[QualificationCaseSpec, ...]:
        """Compatibility name emphasizing that these are definitions."""

        return self.selected_cases

    @property
    def includes_full_catalog_coverage(self) -> bool:
        return any(
            case.category == "MISSION_ROUTE_COVERAGE"
            for case in self.selected_cases
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.prehardware_qualification_policy.v1",
            "catalog_id": PREHARDWARE_QUALIFICATION_CATALOG,
            "profile": self.profile,
            "maximum_cases": self.maximum_cases,
            "maximum_session_runs": self.maximum_session_runs,
            "maximum_total_virtual_commands": self.maximum_total_virtual_commands,
            "maximum_total_camera_captures": self.maximum_total_camera_captures,
            "maximum_total_legacy_events": self.maximum_total_legacy_events,
            "includes_full_catalog_coverage": self.includes_full_catalog_coverage,
            "route_policy": {
                **self.route_policy.to_dict(),
                "policy_sha256": self.route_policy.policy_hash,
            },
            "selected_cases": [case.to_dict() for case in self.selected_cases],
            "selected_case_count": len(self.selected_cases),
            "wall_clock_time_is_evidence": False,
        }

    @property
    def policy_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class PrehardwareQualificationReport:
    """Aggregate diagnostic with simulation and physical readiness separated."""

    policy: PrehardwareQualificationPolicy
    source: Mapping[str, object]
    cases: tuple[QualificationCaseResult, ...]
    coverage_summary: Mapping[str, object]
    resource_usage: Mapping[str, object]
    physical_holds: tuple[str, ...]
    final_revalidation_passed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.policy, PrehardwareQualificationPolicy):
            raise TypeError("policy must be PrehardwareQualificationPolicy")
        cases = tuple(self.cases)
        if (
            not cases
            or len(cases) > self.policy.maximum_cases
            or tuple(item.spec for item in cases) != self.policy.selected_cases
        ):
            raise PrehardwareQualificationError(
                "qualification results do not match the selected ordered catalog"
            )
        if len({item.spec.case_id for item in cases}) != len(cases):
            raise PrehardwareQualificationError("qualification case ids are not unique")
        object.__setattr__(self, "cases", cases)
        if not isinstance(self.source, Mapping) or set(self.source) != _SOURCE_KEYS:
            raise PrehardwareQualificationError(
                "qualification source fields differ from the v1 contract"
            )
        for key in _SOURCE_DIGEST_KEYS:
            _digest(self.source[key], f"qualification source {key}")
        for key in _SOURCE_KEYS - _SOURCE_DIGEST_KEYS - {
            "virtual_profile_simulation_only",
        }:
            value = self.source[key]
            if not isinstance(value, str) or not value:
                raise PrehardwareQualificationError(
                    f"qualification source {key} must be non-empty text"
                )
        if (
            self.source["virtual_profile_classification"]
            != "UNMEASURED_SENSITIVITY_OVERLAY"
            or self.source["virtual_profile_simulation_only"] is not True
            or self.source["virtual_profile_physical_release_effect"] != "NONE"
        ):
            raise PrehardwareQualificationError(
                "qualification source virtual profile gained physical authority"
            )
        object.__setattr__(
            self, "source", _freeze_document(self.source, "qualification source")
        )
        if (
            not isinstance(self.coverage_summary, Mapping)
            or set(self.coverage_summary) != _COVERAGE_SUMMARY_KEYS
        ):
            raise PrehardwareQualificationError(
                "coverage summary fields differ from the v1 contract"
            )
        if (
            self.coverage_summary["expected_route_count"]
            != EXPECTED_MISSION_TARGET_COUNT
            or self.coverage_summary["expected_keyboard_route_count"]
            != EXPECTED_KEYBOARD_TARGET_COUNT
            or self.coverage_summary["expected_phone_route_count"]
            != EXPECTED_PHONE_TARGET_COUNT
            or self.coverage_summary["selected_profile_source_coverage_sha256"]
            != self.source["historical_mission_coverage_sha256"]
        ):
            raise PrehardwareQualificationError(
                "coverage summary catalog/profile provenance is invalid"
            )
        coverage_cases = tuple(
            item
            for item in cases
            if item.spec.category == "MISSION_ROUTE_COVERAGE"
        )
        if self.policy.includes_full_catalog_coverage:
            if len(coverage_cases) != 1:
                raise PrehardwareQualificationError(
                    "standard profile must contain exactly one coverage result"
                )
            coverage_case = coverage_cases[0]
            route_count = coverage_case.metrics.get("route_count")
            accepted_count = coverage_case.metrics.get("accepted_route_count")
            all_accepted = coverage_case.metrics.get("all_routes_accepted")
            complete = coverage_case.metrics.get("complete_catalog_evidence")
            expected_state = (
                "ALL_ROUTES_ACCEPTED"
                if complete is True and all_accepted is True
                else "ROUTE_GAPS_REPORTED"
                if complete is True
                else "CATALOG_INCOMPLETE"
            )
            if (
                self.coverage_summary["evaluated"] is not True
                or self.coverage_summary["state"] != expected_state
                or self.coverage_summary["complete_catalog_evidence"] is not complete
                or self.coverage_summary["route_count"] != route_count
                or self.coverage_summary["accepted_route_count"] != accepted_count
                or self.coverage_summary["all_routes_accepted"] is not all_accepted
                or self.coverage_summary["coverage_report_sha256"]
                != coverage_case.source_report_sha256
            ):
                raise PrehardwareQualificationError(
                    "coverage summary differs from its coverage case"
                )
        elif (
            coverage_cases
            or self.coverage_summary["evaluated"] is not False
            or self.coverage_summary["state"] != "NOT_RUN"
            or self.coverage_summary["complete_catalog_evidence"] is not False
            or self.coverage_summary["route_count"] != 0
            or self.coverage_summary["accepted_route_count"] is not None
            or self.coverage_summary["rejected_route_count"] is not None
            or self.coverage_summary["all_routes_accepted"] is not False
            or self.coverage_summary["coverage_report_sha256"] is not None
        ):
            raise PrehardwareQualificationError(
                "quick profile coverage summary cannot claim fresh route evidence"
            )
        object.__setattr__(
            self,
            "coverage_summary",
            _freeze_document(self.coverage_summary, "coverage summary"),
        )
        expected_usage = _resource_usage(cases)
        if (
            not isinstance(self.resource_usage, Mapping)
            or dict(self.resource_usage) != expected_usage
            or not _contains_only_zero_authority_values(self.resource_usage)
        ):
            raise PrehardwareQualificationError(
                "resource usage differs from the case-derived totals"
            )
        object.__setattr__(
            self,
            "resource_usage",
            _freeze_document(self.resource_usage, "resource usage"),
        )
        holds = tuple(self.physical_holds)
        if not holds or any(not isinstance(item, str) or not item for item in holds):
            raise PrehardwareQualificationError("physical holds must be non-empty")
        object.__setattr__(self, "physical_holds", holds)
        if not isinstance(self.final_revalidation_passed, bool):
            raise PrehardwareQualificationError(
                "final_revalidation_passed must be boolean"
            )

    @property
    def campaign_passed(self) -> bool:
        return self.final_revalidation_passed and all(
            case.passed for case in self.cases
        )

    @property
    def profile(self) -> str:
        return self.policy.profile

    @property
    def case_results(self) -> tuple[QualificationCaseResult, ...]:
        return self.cases

    @property
    def diagnostic_pass(self) -> bool:
        """Alias that explicitly describes what ``campaign_passed`` means."""

        return self.campaign_passed

    @property
    def coverage_evaluated(self) -> bool:
        return self.coverage_summary.get("evaluated") is True

    @property
    def all_mission_routes_accepted(self) -> bool:
        return (
            self.coverage_evaluated
            and self.coverage_summary.get("all_routes_accepted") is True
        )

    @property
    def physical_ready(self) -> bool:
        # This schema is simulation-only by construction.  Physical readiness
        # belongs to later measured calibration and release evidence.
        return False

    @property
    def coverage_state(self) -> str:
        value = self.coverage_summary.get("state")
        return value if isinstance(value, str) else "INCOMPLETE"

    @property
    def status(self) -> str:
        if not self.campaign_passed:
            return "PREHARDWARE_QUALIFICATION_FAILED"
        if not self.coverage_evaluated:
            return (
                "PREHARDWARE_QUALIFICATION_PASS_WITH_UNEVALUATED_"
                "CATALOG_AND_PHYSICAL_HOLDS"
            )
        if not self.all_mission_routes_accepted:
            return (
                "PREHARDWARE_QUALIFICATION_PASS_WITH_KNOWN_ROUTE_"
                "GAPS_AND_PHYSICAL_HOLDS"
            )
        return "PREHARDWARE_QUALIFICATION_PASS_WITH_PHYSICAL_HOLDS"

    def _without_hash(self) -> dict[str, object]:
        passed_count = sum(case.passed for case in self.cases)
        return {
            "schema": PREHARDWARE_QUALIFICATION_SCHEMA,
            "status": self.status,
            "profile": self.profile,
            "campaign_passed": self.campaign_passed,
            "diagnostic_pass": self.diagnostic_pass,
            "physical_ready": self.physical_ready,
            "coverage_evaluated": self.coverage_evaluated,
            "coverage_state": self.coverage_state,
            "all_mission_routes_accepted": self.all_mission_routes_accepted,
            "source": _thaw_json(self.source),
            "policy": {
                **self.policy.to_dict(),
                "policy_sha256": self.policy.policy_hash,
            },
            "case_summary": {
                "selected": len(self.cases),
                "passed": passed_count,
                "failed": len(self.cases) - passed_count,
                "expected_fail_stop_cases": sum(
                    item.spec.expected_outcome == "FAIL_STOP" for item in self.cases
                ),
            },
            "cases": [
                {**case.to_dict(), "case_result_sha256": case.result_hash}
                for case in self.cases
            ],
            "coverage_summary": _thaw_json(self.coverage_summary),
            "resource_usage": _thaw_json(self.resource_usage),
            "final_source_revalidation_passed": self.final_revalidation_passed,
            "physical_holds": list(self.physical_holds),
            "limitations": [
                "Synthetic camera, pose, contact, and device models are not measured physical evidence.",
                "Catalog routes are independent park-to-target-to-park diagnostics, not an arbitrary typing-sequence proof.",
                "Full robot, holder, camera, cable, tool, and environment collision coverage remains incomplete.",
                "Controller correlation, dynamics, payload, force, timing, and physical outcome sensing remain uncommissioned.",
                "Passing this campaign cannot release power, motion, contact, calibration, or hardware transport gates.",
            ],
            "evidence_recording": {
                "recorded": False,
                "replay_supported": False,
                "reason": "QUALIFICATION_EVIDENCE_PACKAGE_SCHEMA_NOT_IMPLEMENTED",
            },
            "authority": {
                "simulation_only": True,
                "execution_authorized": False,
                "hardware_accessed": False,
                "hardware_commands_generated": 0,
                "live_motion_authorized": False,
                "physical_contact_authorized": False,
                "physical_release_effect": "NONE",
                "can_release_physical_gates": False,
            },
        }

    @property
    def report_hash(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, object]:
        return {**self._without_hash(), "report_sha256": self.report_hash}


def default_qualification_case_specs(
    profile: str = "standard",
) -> tuple[QualificationCaseSpec, ...]:
    """Return the ordered built-in case catalog subset for ``profile``."""

    if profile not in PREHARDWARE_QUALIFICATION_PROFILES:
        raise PrehardwareQualificationError(
            f"profile must be one of {PREHARDWARE_QUALIFICATION_PROFILES}"
        )
    both = ("quick", "standard")
    standard = ("standard",)
    cases = (
        QualificationCaseSpec(
            "startup.integrity",
            "STARTUP",
            "SIMULATION_READY",
            both,
        ),
        QualificationCaseSpec(
            "adaptive.keyboard.nominal",
            "ADAPTIVE_SESSION",
            "COMPLETE",
            standard,
            device="keyboard",
            requested_text="a",
            expected_correction_count=0,
        ),
        QualificationCaseSpec(
            "adaptive.phone.nominal",
            "ADAPTIVE_SESSION",
            "COMPLETE",
            standard,
            device="phone",
            requested_text="a",
            expected_correction_count=0,
        ),
        QualificationCaseSpec(
            "adaptive.keyboard.offset_x_plus_12mm",
            "ADAPTIVE_SESSION",
            "COMPLETE",
            both,
            device="keyboard",
            requested_text="a",
            truth_translation_Wv_mm=(12.0, 0.0, 0.0),
            expected_correction_count=1,
        ),
        QualificationCaseSpec(
            "adaptive.phone.offset_x_plus_8mm",
            "ADAPTIVE_SESSION",
            "COMPLETE",
            both,
            device="phone",
            requested_text="a",
            truth_translation_Wv_mm=(8.0, 0.0, 0.0),
            expected_correction_count=1,
        ),
        QualificationCaseSpec(
            "adaptive.keyboard.offset_x_plus_16mm_rejected",
            "ADAPTIVE_SESSION",
            "FAIL_STOP",
            standard,
            device="keyboard",
            requested_text="a",
            truth_translation_Wv_mm=(16.0, 0.0, 0.0),
            expected_fault_reason=(
                "BOARD_POSE_CORRECTION_REJECTED:"
                "TRANSLATION_DELTA_LIMIT_EXCEEDED"
            ),
            expected_correction_count=0,
            maximum_contact_attempts=0,
        ),
        QualificationCaseSpec(
            "fault.arm_connect.keyboard",
            "LEGACY_FAULT_SESSION",
            "FAIL_STOP",
            standard,
            device="keyboard",
            requested_text="a",
            fault_kind=VirtualFaultKind.ARM_CONNECT_FAILURE,
            fault_component="arm",
            fault_operation="connect",
            expected_fault_reason=VirtualFaultKind.ARM_CONNECT_FAILURE.value,
        ),
        QualificationCaseSpec(
            "fault.arm_reference.keyboard",
            "LEGACY_FAULT_SESSION",
            "FAIL_STOP",
            standard,
            device="keyboard",
            requested_text="a",
            fault_kind=VirtualFaultKind.ARM_REFERENCE_FAILURE,
            fault_component="arm",
            fault_operation="reference",
            expected_fault_reason=VirtualFaultKind.ARM_REFERENCE_FAILURE.value,
        ),
        QualificationCaseSpec(
            "fault.arm_stall.keyboard",
            "LEGACY_FAULT_SESSION",
            "FAIL_STOP",
            standard,
            device="keyboard",
            requested_text="a",
            fault_kind=VirtualFaultKind.ARM_STALL,
            fault_component="arm",
            fault_operation="execute_waypoint",
            expected_fault_reason=VirtualFaultKind.ARM_STALL.value,
        ),
        QualificationCaseSpec(
            "fault.camera_unavailable.keyboard",
            "LEGACY_FAULT_SESSION",
            "FAIL_STOP",
            standard,
            device="keyboard",
            requested_text="a",
            fault_kind=VirtualFaultKind.CAMERA_UNAVAILABLE,
            fault_component="camera",
            fault_operation="observe",
            expected_fault_reason=VirtualFaultKind.CAMERA_UNAVAILABLE.value,
        ),
        QualificationCaseSpec(
            "fault.camera_tag_loss.keyboard",
            "LEGACY_FAULT_SESSION",
            "FAIL_STOP",
            both,
            device="keyboard",
            requested_text="a",
            fault_kind=VirtualFaultKind.CAMERA_TAG_LOSS,
            fault_component="camera",
            fault_operation="observe",
            expected_fault_reason=VirtualFaultKind.CAMERA_TAG_LOSS.value,
        ),
        QualificationCaseSpec(
            "fault.contact_missed.keyboard",
            "LEGACY_FAULT_SESSION",
            "FAIL_STOP",
            standard,
            device="keyboard",
            requested_text="a",
            fault_kind=VirtualFaultKind.KEYBOARD_MISSED_CONTACT,
            fault_component="keyboard",
            fault_operation="contact",
            expected_fault_reason=VirtualFaultKind.KEYBOARD_MISSED_CONTACT.value,
        ),
        QualificationCaseSpec(
            "fault.keyboard_double",
            "LEGACY_FAULT_SESSION",
            "FAIL_STOP",
            standard,
            device="keyboard",
            requested_text="a",
            fault_kind=VirtualFaultKind.KEYBOARD_DOUBLE_CONTACT,
            fault_component="keyboard",
            fault_operation="contact",
            expected_fault_reason=VirtualFaultKind.KEYBOARD_DOUBLE_CONTACT.value,
        ),
        QualificationCaseSpec(
            "fault.phone_wrong_ui",
            "LEGACY_FAULT_SESSION",
            "FAIL_STOP",
            standard,
            device="phone",
            requested_text="a",
            fault_kind=VirtualFaultKind.ANDROID_WRONG_UI_STATE,
            fault_component="android",
            fault_operation="verify_state",
            expected_fault_reason="ANDROID_UI_STATE_REJECTED",
        ),
        QualificationCaseSpec(
            "fault.focus_lost.phone",
            "LEGACY_FAULT_SESSION",
            "FAIL_STOP",
            standard,
            device="phone",
            requested_text="a",
            fault_kind=VirtualFaultKind.DEVICE_FOCUS_LOST,
            fault_component="android",
            fault_operation="contact",
            expected_fault_reason=VirtualFaultKind.DEVICE_FOCUS_LOST.value,
        ),
        QualificationCaseSpec(
            "determinism.keyboard.offset_x_plus_12mm",
            "DETERMINISM_REPLAY",
            "IDENTICAL",
            both,
            reference_case_id="adaptive.keyboard.offset_x_plus_12mm",
        ),
        QualificationCaseSpec(
            "coverage.locked_catalog",
            "MISSION_ROUTE_COVERAGE",
            "COMPLETE_CATALOG",
            standard,
        ),
    )
    selected = tuple(case for case in cases if profile in case.profiles)
    if (
        not selected
        or len(selected) > MAX_QUALIFICATION_CASES
        or len({case.case_id for case in selected}) != len(selected)
    ):
        raise PrehardwareQualificationError(
            "built-in qualification case catalog is invalid"
        )
    return selected


def _scenario(profile: VirtualCommissioningProfile) -> VirtualSessionScenarioBinding:
    park = profile.park_point_board
    return VirtualSessionScenarioBinding(
        scenario_id=profile.profile_id,
        scenario_hash=profile.source_sha256,
        park_point_board_mm=(park.x, park.y, park.z),
    )


def _adaptive_case_result(
    spec: QualificationCaseSpec,
    bootstrap: VirtualWorkcellBootstrap,
    profile: VirtualCommissioningProfile,
    scenario: VirtualSessionScenarioBinding,
    adaptive_runner: Callable[..., AdaptiveVirtualSessionReport],
) -> tuple[QualificationCaseResult, AdaptiveVirtualSessionReport]:
    assert spec.device is not None and spec.requested_text is not None
    plan = compile_development_text(spec.device, spec.requested_text)
    truth = make_hidden_virtual_board_truth(
        profile.study_input,
        translation_Wv_mm=Vec3(*spec.truth_translation_Wv_mm),
        yaw_board_rad=math.radians(spec.truth_yaw_board_deg),
    )
    report = adaptive_runner(
        bootstrap,
        plan,
        spec.requested_text,
        profile.study_input,
        scenario,
        truth=truth,
    )
    document = report.to_dict()
    authority_verified = _zero_authority(document)
    correction_count = len(report.correction_installations)
    contact_count = len(report.contact_attempts)
    decision_statuses = tuple(
        attempt.decision.status.value
        for attempt in report.vision_attempts
        if attempt.decision is not None
    )
    lifecycle_closed = report.arm_document.get("lifecycle") == "CLOSED"
    expectation = (
        report.pipeline_completed
        and report.fault_reason is None
        if spec.expected_outcome == "COMPLETE"
        else (
            not report.pipeline_completed
            and report.fault_reason == spec.expected_fault_reason
        )
    )
    expectation = expectation and lifecycle_closed
    if spec.expected_correction_count is not None:
        expectation = expectation and correction_count == spec.expected_correction_count
        if spec.expected_outcome == "COMPLETE":
            expected_decisions = (
                ("NO_CHANGE",)
                if spec.expected_correction_count == 0
                else ("APPLY", "NO_CHANGE")
            )
            expectation = expectation and decision_statuses == expected_decisions
        elif spec.expected_fault_reason and "CORRECTION_REJECTED" in (
            spec.expected_fault_reason
        ):
            expectation = expectation and decision_statuses == ("REJECT",)
    if spec.maximum_contact_attempts is not None:
        expectation = expectation and contact_count <= spec.maximum_contact_attempts
    passed = bool(expectation and authority_verified)
    return (
        QualificationCaseResult(
            spec=spec,
            observed_status=report.status,
            passed=passed,
            source_report_sha256=report.report_hash,
            authority_verified=authority_verified,
            metrics={
                "pipeline_completed": report.pipeline_completed,
                "fault_reason": report.fault_reason,
                "outcome_verified": report.outcome_verified,
                "ended_at_park": report.ended_at_park,
                "closed_after_execution": lifecycle_closed,
                "virtual_commands_executed": len(report.executions),
                "camera_capture_count": len(report.vision_attempts),
                "correction_installation_count": correction_count,
                "correction_decision_statuses": list(decision_statuses),
                "contact_attempt_count": contact_count,
                "phone_verification_count": len(report.phone_verifications),
                "camera_path": "ACHIEVED_JOINT_DEPENDENT_ARM_CAMERA",
                "hardware_commands_generated": 0,
            },
        ),
        report,
    )


def _legacy_fault_case_result(
    spec: QualificationCaseSpec,
    bootstrap: VirtualWorkcellBootstrap,
    profile: VirtualCommissioningProfile,
    scenario: VirtualSessionScenarioBinding,
    virtual_runner: Callable[..., VirtualSessionReport],
) -> QualificationCaseResult:
    assert spec.device is not None and spec.requested_text is not None
    assert spec.fault_kind is not None
    assert spec.fault_component is not None and spec.fault_operation is not None
    trigger = VirtualFaultTrigger(
        trigger_id=f"qualification-{spec.case_id}",
        kind=spec.fault_kind,
        component=spec.fault_component,
        operation=spec.fault_operation,
    )
    script = VirtualFaultScript(
        script_id=f"qualification-{spec.case_id}",
        triggers=(trigger,),
    )
    plan = compile_development_text(spec.device, spec.requested_text)
    report = virtual_runner(
        bootstrap,
        plan,
        spec.requested_text,
        profile.study_input,
        scenario,
        fault_script=script,
    )
    document = report.to_dict()
    authority_verified = _zero_authority(document)
    trigger_consumed = report.final_fault_script.consumed_trigger_ids == frozenset(
        {trigger.trigger_id}
    )
    lifecycle_closed = (
        report.lifecycle_history[-1].value == "CLOSED"
        and report.arm_document.get("lifecycle") == "CLOSED"
    )
    passed = bool(
        not report.pipeline_completed
        and report.fault_reason == spec.expected_fault_reason
        and trigger_consumed
        and lifecycle_closed
        and authority_verified
    )
    return QualificationCaseResult(
        spec=spec,
        observed_status=report.status,
        passed=passed,
        source_report_sha256=report.report_hash,
        authority_verified=authority_verified,
        metrics={
            "pipeline_completed": report.pipeline_completed,
            "fault_reason": report.fault_reason,
            "fault_trigger_consumed": trigger_consumed,
            "closed_after_fail_stop": lifecycle_closed,
            "outcome_verified": report.outcome_verified,
            "ended_at_park": report.ended_at_park,
            "virtual_commands_executed": report.ledger.virtual_commands_executed,
            "legacy_event_count": len(report.ledger.events),
            "camera_path": "LEGACY_FIXED_OVERVIEW_PIXEL_SERVICE",
            "hardware_commands_generated": 0,
        },
    )


def _coverage_case_result(
    spec: QualificationCaseSpec,
    bootstrap: VirtualWorkcellBootstrap,
    profile: VirtualCommissioningProfile,
    policy: PrehardwareQualificationPolicy,
    route_runner: Callable[..., MissionRouteCoverageReport],
) -> tuple[QualificationCaseResult, dict[str, object]]:
    park = profile.park_point_board
    report = route_runner(
        bootstrap.context,
        profile.study_input,
        (park.x, park.y),
        policy.route_policy,
    )
    document = report.to_dict()
    authority_verified = _zero_authority(document)
    accepted = sum(route.accepted for route in report.routes)
    passed = bool(
        report.complete_catalog_evidence
        and report.all_routes_accepted
        and authority_verified
    )
    keyboard = cast(Mapping[str, object], document["device_summary"])["keyboard"]
    phone = cast(Mapping[str, object], document["device_summary"])["phone"]
    summary: dict[str, object] = {
        "evaluated": True,
        "state": (
            "ALL_ROUTES_ACCEPTED"
            if report.complete_catalog_evidence and report.all_routes_accepted
            else "ROUTE_GAPS_REPORTED"
            if report.complete_catalog_evidence
            else "CATALOG_INCOMPLETE"
        ),
        "complete_catalog_evidence": report.complete_catalog_evidence,
        "expected_route_count": EXPECTED_MISSION_TARGET_COUNT,
        "expected_keyboard_route_count": EXPECTED_KEYBOARD_TARGET_COUNT,
        "expected_phone_route_count": EXPECTED_PHONE_TARGET_COUNT,
        "route_count": len(report.routes),
        "accepted_route_count": accepted,
        "rejected_route_count": len(report.routes) - accepted,
        "keyboard": keyboard,
        "phone": phone,
        "all_routes_accepted": report.all_routes_accepted,
        "coverage_report_sha256": report.report_hash,
        "selected_profile_source_coverage_sha256": (
            profile.source_mission_route_coverage_hash
        ),
        "reason": None,
    }
    return (
        QualificationCaseResult(
            spec=spec,
            observed_status=report.status,
            passed=passed,
            source_report_sha256=report.report_hash,
            authority_verified=authority_verified,
            metrics={
                "complete_catalog_evidence": report.complete_catalog_evidence,
                "route_count": len(report.routes),
                "accepted_route_count": accepted,
                "all_routes_accepted": report.all_routes_accepted,
                "total_waypoint_records": report.total_waypoint_records,
                "total_ik_solves": report.total_ik_solves,
                "total_task_jacobian_fk_evaluations": (
                    report.total_task_jacobian_fk_evaluations
                ),
                "hardware_commands_generated": 0,
            },
        ),
        summary,
    )


def _startup_case_result(
    spec: QualificationCaseSpec,
    bootstrap: VirtualWorkcellBootstrap,
) -> QualificationCaseResult:
    document = bootstrap.to_dict()
    authority_verified = _zero_authority(document)
    passed = bool(bootstrap.simulation_ready and authority_verified)
    return QualificationCaseResult(
        spec=spec,
        observed_status=bootstrap.status,
        passed=passed,
        source_report_sha256=bootstrap.bootstrap_hash,
        authority_verified=authority_verified,
        metrics={
            "simulation_ready": bootstrap.simulation_ready,
            "bootstrap_check_count": len(bootstrap.checks),
            "declared_gap_count": sum(
                check.status == "DECLARED_GAP" for check in bootstrap.checks
            ),
            "collision_diagnostic_ready": (
                bootstrap.collision_readiness.geometry_audit.diagnostic_ready
            ),
            "hardware_commands_generated": 0,
        },
    )


def _resource_usage(cases: tuple[QualificationCaseResult, ...]) -> dict[str, object]:
    def metric_sum(key: str) -> int:
        total = 0
        for result in cases:
            value = result.metrics.get(key, 0)
            if isinstance(value, int) and not isinstance(value, bool):
                total += value
        return total

    return {
        "case_count": len(cases),
        "session_run_count": sum(
            result.spec.category
            in {"ADAPTIVE_SESSION", "LEGACY_FAULT_SESSION", "DETERMINISM_REPLAY"}
            for result in cases
        ),
        "virtual_commands_executed": metric_sum("virtual_commands_executed"),
        "camera_capture_count": metric_sum("camera_capture_count"),
        "correction_installation_count": metric_sum(
            "correction_installation_count"
        ),
        "contact_attempt_count": metric_sum("contact_attempt_count"),
        "legacy_event_count": metric_sum("legacy_event_count"),
        "mission_route_count": metric_sum("route_count"),
        "mission_total_waypoint_records": metric_sum("total_waypoint_records"),
        "mission_total_ik_solves": metric_sum("total_ik_solves"),
        "mission_total_task_jacobian_fk_evaluations": metric_sum(
            "total_task_jacobian_fk_evaluations"
        ),
        "wall_clock_time_recorded": False,
        "hardware_commands_generated": 0,
    }


def _validate_actual_resources(
    usage: Mapping[str, object], policy: PrehardwareQualificationPolicy
) -> None:
    checks = (
        ("case_count", policy.maximum_cases),
        ("session_run_count", policy.maximum_session_runs),
        ("virtual_commands_executed", policy.maximum_total_virtual_commands),
        ("camera_capture_count", policy.maximum_total_camera_captures),
        ("legacy_event_count", policy.maximum_total_legacy_events),
    )
    for name, limit in checks:
        value = usage.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value > limit:
            raise PrehardwareQualificationError(
                f"qualification resource {name} exceeded its policy limit"
            )


def _source_document(
    bootstrap: VirtualWorkcellBootstrap,
    profile: VirtualCommissioningProfile,
) -> dict[str, object]:
    snapshot = bootstrap.context.snapshot
    bundle = bootstrap.context.bundle_lock
    return {
        "bootstrap_sha256": bootstrap.bootstrap_hash,
        "manifest_id": snapshot.manifest_id,
        "manifest_sha256": snapshot.manifest_sha256,
        "snapshot_sha256": snapshot.snapshot_hash,
        "design_revision": snapshot.design_revision,
        "active_build_id": snapshot.active_build_id,
        "simulation_bundle_id": bundle.bundle_id,
        "simulation_bundle_lock_sha256": bundle.source_lock_sha256,
        "alignment_status": bootstrap.context.alignment.status,
        "alignment_report_sha256": bootstrap.context.alignment.report_hash,
        "virtual_profile_id": profile.profile_id,
        "virtual_profile_sha256": profile.source_sha256,
        "virtual_profile_classification": profile.status,
        "virtual_profile_simulation_only": profile.simulation_only,
        "virtual_profile_physical_release_effect": profile.physical_release_effect,
        "study_input_id": profile.study_input.study_input_id,
        "park_probe_id": profile.park_probe_id,
        "historical_layout_report_sha256": profile.source_layout_report_hash,
        "historical_mission_coverage_sha256": (
            profile.source_mission_route_coverage_hash
        ),
    }


def _physical_holds(bootstrap: VirtualWorkcellBootstrap) -> tuple[str, ...]:
    holds = [
        "PHYSICAL_POWER_MOTION_AND_CONTACT_RELEASE_NOT_CONFERRED",
        "SYNTHETIC_CAMERA_INTRINSICS_AND_MOUNT_EXTRINSIC_UNMEASURED",
        "CONTROLLER_CORRELATION_DYNAMICS_FORCE_AND_TIMING_UNCOMMISSIONED",
    ]
    if bootstrap.calibration_inventory.missing_requirement_ids:
        holds.append("PHYSICAL_CALIBRATION_REGISTRY_INCOMPLETE")
    if not bootstrap.collision_readiness.geometry_audit.diagnostic_ready:
        holds.append("FULL_BODY_COLLISION_MODEL_INCOMPLETE")
    holds.extend(
        f"SNAPSHOT_BLOCKER:{blocker}"
        for blocker in bootstrap.context.snapshot.hard_blockers
    )
    return tuple(dict.fromkeys(holds))


def _run_prehardware_qualification_with_runners(
    workspace: Path,
    *,
    policy: PrehardwareQualificationPolicy,
    runtime_path: Path | None = None,
    bootstrap_runner: Callable[..., VirtualWorkcellBootstrap] | None = None,
    profile_loader: Callable[..., VirtualCommissioningProfile] | None = None,
    adaptive_runner: Callable[..., AdaptiveVirtualSessionReport] | None = None,
    virtual_runner: Callable[..., VirtualSessionReport] | None = None,
    route_runner: Callable[..., MissionRouteCoverageReport] | None = None,
    revalidator: Callable[[VirtualWorkcellBootstrap], None] | None = None,
) -> PrehardwareQualificationReport:
    """Internal injection seam used to exhaustively test orchestration."""

    if not isinstance(policy, PrehardwareQualificationPolicy):
        raise TypeError("policy must be PrehardwareQualificationPolicy")
    root = Path(workspace).resolve()
    bootstrap_fn = bootstrap_runner or bootstrap_virtual_workcell
    profile_fn = profile_loader or load_virtual_commissioning_profile
    adaptive_fn = adaptive_runner or run_adaptive_virtual_session
    virtual_fn = virtual_runner or run_virtual_session
    route_fn = route_runner or run_mission_route_coverage
    revalidate_fn = revalidator or revalidate_virtual_workcell

    bootstrap = bootstrap_fn(root, runtime_path)
    profile = profile_fn(cast(VirtualProfileContext, bootstrap.context))
    scenario = _scenario(profile)
    results: list[QualificationCaseResult] = []
    adaptive_reports: dict[str, AdaptiveVirtualSessionReport] = {}
    coverage_summary: dict[str, object] = {
        "evaluated": False,
        "state": "NOT_RUN",
        "complete_catalog_evidence": False,
        "expected_route_count": EXPECTED_MISSION_TARGET_COUNT,
        "expected_keyboard_route_count": EXPECTED_KEYBOARD_TARGET_COUNT,
        "expected_phone_route_count": EXPECTED_PHONE_TARGET_COUNT,
        "route_count": 0,
        "accepted_route_count": None,
        "rejected_route_count": None,
        "keyboard": None,
        "phone": None,
        "all_routes_accepted": False,
        "coverage_report_sha256": None,
        "selected_profile_source_coverage_sha256": (
            profile.source_mission_route_coverage_hash
        ),
        "reason": "QUICK_PROFILE_DOES_NOT_RECOMPUTE_MULTI_MINUTE_75_ROUTE_SCREEN",
    }

    specs_by_id = {case.case_id: case for case in policy.selected_cases}
    for spec in policy.selected_cases:
        if spec.category == "STARTUP":
            result = _startup_case_result(spec, bootstrap)
        elif spec.category == "ADAPTIVE_SESSION":
            result, adaptive_report = _adaptive_case_result(
                spec,
                bootstrap,
                profile,
                scenario,
                adaptive_fn,
            )
            adaptive_reports[spec.case_id] = adaptive_report
        elif spec.category == "DETERMINISM_REPLAY":
            assert spec.reference_case_id is not None
            reference_spec = specs_by_id.get(spec.reference_case_id)
            reference_report = adaptive_reports.get(spec.reference_case_id)
            if reference_spec is None or reference_report is None:
                raise PrehardwareQualificationError(
                    f"determinism reference {spec.reference_case_id!r} was not run"
                )
            replay_case_result, replay_report = _adaptive_case_result(
                reference_spec,
                bootstrap,
                profile,
                scenario,
                adaptive_fn,
            )
            identical = (
                replay_report.report_hash == reference_report.report_hash
                and replay_report.to_dict() == reference_report.to_dict()
            )
            authority_verified = _zero_authority(replay_report.to_dict())
            result = QualificationCaseResult(
                spec=spec,
                observed_status=(
                    "DETERMINISTIC_REPLAY_IDENTICAL"
                    if identical
                    else "DETERMINISTIC_REPLAY_MISMATCH"
                ),
                passed=bool(
                    identical
                    and replay_case_result.passed
                    and authority_verified
                ),
                source_report_sha256=replay_report.report_hash,
                authority_verified=authority_verified,
                metrics={
                    "reference_case_id": spec.reference_case_id,
                    "reference_report_sha256": reference_report.report_hash,
                    "replay_report_sha256": replay_report.report_hash,
                    "byte_canonical_report_hash_identical": identical,
                    "full_child_document_identical": identical,
                    "virtual_commands_executed": len(replay_report.executions),
                    "camera_capture_count": len(replay_report.vision_attempts),
                    "correction_installation_count": len(
                        replay_report.correction_installations
                    ),
                    "contact_attempt_count": len(replay_report.contact_attempts),
                    "camera_path": "ACHIEVED_JOINT_DEPENDENT_ARM_CAMERA",
                    "hardware_commands_generated": 0,
                },
            )
        elif spec.category == "LEGACY_FAULT_SESSION":
            result = _legacy_fault_case_result(
                spec,
                bootstrap,
                profile,
                scenario,
                virtual_fn,
            )
        elif spec.category == "MISSION_ROUTE_COVERAGE":
            result, coverage_summary = _coverage_case_result(
                spec,
                bootstrap,
                profile,
                policy,
                route_fn,
            )
        else:  # Defensive even though QualificationCaseSpec rejects this.
            raise PrehardwareQualificationError(
                f"unsupported qualification category {spec.category!r}"
            )
        results.append(result)
        # Enforce aggregate caps after every case so an over-budget campaign
        # stops immediately rather than completing more expensive work first.
        _validate_actual_resources(_resource_usage(tuple(results)), policy)

    result_tuple = tuple(results)
    usage = _resource_usage(result_tuple)
    _validate_actual_resources(usage, policy)
    revalidate_fn(bootstrap)
    return PrehardwareQualificationReport(
        policy=policy,
        source=_source_document(bootstrap, profile),
        cases=result_tuple,
        coverage_summary=coverage_summary,
        resource_usage=usage,
        physical_holds=_physical_holds(bootstrap),
        final_revalidation_passed=True,
    )


def run_prehardware_qualification(
    workspace: Path,
    *,
    policy: PrehardwareQualificationPolicy | None = None,
    runtime_path: Path | None = None,
) -> PrehardwareQualificationReport:
    """Run one locked software-only qualification campaign.

    ``standard`` deliberately includes the complete 75-route diagnostic and
    can take several minutes.  Choose ``PrehardwareQualificationPolicy(
    profile="quick")`` for the bounded correction/determinism smoke campaign.
    """

    selected = policy or PrehardwareQualificationPolicy()
    if not isinstance(selected, PrehardwareQualificationPolicy):
        raise TypeError("policy must be PrehardwareQualificationPolicy")
    return _run_prehardware_qualification_with_runners(
        workspace,
        policy=selected,
        runtime_path=runtime_path,
    )


__all__ = [
    "MAX_QUALIFICATION_CAMERA_CAPTURES",
    "MAX_QUALIFICATION_CASES",
    "MAX_QUALIFICATION_LEGACY_EVENTS",
    "MAX_QUALIFICATION_SESSION_RUNS",
    "MAX_QUALIFICATION_VIRTUAL_COMMANDS",
    "PREHARDWARE_QUALIFICATION_CATALOG",
    "PREHARDWARE_QUALIFICATION_PROFILES",
    "PREHARDWARE_QUALIFICATION_SCHEMA",
    "PrehardwareQualificationError",
    "PrehardwareQualificationPolicy",
    "PrehardwareQualificationReport",
    "QualificationCaseResult",
    "QualificationCaseSpec",
    "default_qualification_case_specs",
    "run_prehardware_qualification",
]
