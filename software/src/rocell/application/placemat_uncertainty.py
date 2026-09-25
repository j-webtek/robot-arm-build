"""Deterministic, zero-authority RC03 placemat geometry sensitivity study.

The nominal target catalog is useful for software integration, but its device
poses and target centres are not measurements.  This module makes that gap
explicit: it displaces the nominal board registration, device placements,
local target maps, and TCP by bounded *assumed* amounts and reports where the
unchanged nominal command point would land.

These bounds are sensitivity-study inputs.  They are not manufacturing
tolerances, calibration acceptance limits, safety margins, or evidence that
the physical cell may move.  The service only reads and revalidates controlled
files; it has no camera, controller, transport, or actuator dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
from itertools import product
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

from rocell.targets import TargetRegion
from rocell.vision import DEFAULT_B0477_CAMERA_PROFILE, load_camera_profile
from rocell.workcell import (
    DEFAULT_STATIC_CAMERA_SUPPORT_DESIGN,
    load_static_camera_support_design,
)

from .context import SimulationContext, revalidate_simulation_context


PLACEMAT_UNCERTAINTY_SCHEMA = "rocell.placemat_geometry_sensitivity.v1"
PLACEMAT_UNCERTAINTY_STATUS = "UNMEASURED_SENSITIVITY_DIAGNOSTIC_ONLY"
PLACEMAT_UNCERTAINTY_GENERATOR = "signed-oat-plus-device-corners-v1"

EXPECTED_KEYBOARD_TARGETS = 46
EXPECTED_PHONE_TARGETS = 29
MAX_TARGETS = 128
MAX_CASES = 96
MAX_OBSERVATIONS = 10_000
MAX_ABSOLUTE_XY_BOUND_MM = 25.0
MAX_ABSOLUTE_Z_BOUND_MM = 10.0
MAX_ABSOLUTE_YAW_BOUND_DEG = 5.0
MAX_IMPLEMENTATION_BYTES = 512 * 1024

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,95}$")
_EPSILON_MM = 1e-9


class PlacematUncertaintyError(ValueError):
    """The requested sensitivity study cannot be represented safely."""


def _finite_nonnegative(value: object, label: str, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlacematUncertaintyError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise PlacematUncertaintyError(f"{label} must be a finite number")
    if result < 0.0:
        raise PlacematUncertaintyError(f"{label} cannot be negative")
    if result > maximum:
        raise PlacematUncertaintyError(
            f"{label} exceeds the hard sensitivity-study bound {maximum}"
        )
    return result


def _finite_signed(value: object, label: str, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlacematUncertaintyError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or abs(result) > maximum:
        raise PlacematUncertaintyError(f"{label} is outside the hard work bound")
    return result


def _quantize(value: float) -> float:
    """Canonicalize geometry floats before hashing or serialization."""

    result = round(float(value), 9)
    return 0.0 if result == 0.0 else result


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


def _require_digest(value: str, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise PlacematUncertaintyError(f"{label} must be a lowercase SHA-256")
    return value


def _regular_file_sha256(path: Path, label: str) -> str:
    """Hash one regular non-link file through a bounded read."""

    if path.is_symlink() or not path.is_file():
        raise PlacematUncertaintyError(f"{label} must be a regular non-link file")
    digest = hashlib.sha256()
    byte_count = 0
    try:
        with path.open("rb") as handle:
            while block := handle.read(64 * 1024):
                byte_count += len(block)
                if byte_count > MAX_IMPLEMENTATION_BYTES:
                    raise PlacematUncertaintyError(
                        f"{label} exceeds the bounded source size"
                    )
                digest.update(block)
    except OSError as exc:
        raise PlacematUncertaintyError(f"could not read {label}") from exc
    return digest.hexdigest()


def _authority() -> dict[str, object]:
    return {
        "simulation_only": True,
        "hardware_accessed": False,
        "camera_frames_requested": 0,
        "hardware_commands_generated": 0,
        "arm_motion_commands": 0,
        "contact_commands": 0,
        "execution_authorized": False,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "physical_calibration_authority": False,
        "physical_release_effect": "NONE",
        "can_release_physical_gates": False,
    }


@dataclass(frozen=True, slots=True)
class RigidPoseSensitivityBounds:
    """Unsigned bounds for one assumed planar pose plus height perturbation."""

    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0
    yaw_deg: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "x_mm",
            _finite_nonnegative(
                self.x_mm, "rigid pose x_mm", MAX_ABSOLUTE_XY_BOUND_MM
            ),
        )
        object.__setattr__(
            self,
            "y_mm",
            _finite_nonnegative(
                self.y_mm, "rigid pose y_mm", MAX_ABSOLUTE_XY_BOUND_MM
            ),
        )
        object.__setattr__(
            self,
            "z_mm",
            _finite_nonnegative(
                self.z_mm, "rigid pose z_mm", MAX_ABSOLUTE_Z_BOUND_MM
            ),
        )
        object.__setattr__(
            self,
            "yaw_deg",
            _finite_nonnegative(
                self.yaw_deg,
                "rigid pose yaw_deg",
                MAX_ABSOLUTE_YAW_BOUND_DEG,
            ),
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "z_mm": self.z_mm,
            "yaw_deg": self.yaw_deg,
        }


@dataclass(frozen=True, slots=True)
class CartesianSensitivityBounds:
    """Unsigned assumed offsets for a target map or TCP."""

    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "x_mm",
            _finite_nonnegative(
                self.x_mm, "cartesian x_mm", MAX_ABSOLUTE_XY_BOUND_MM
            ),
        )
        object.__setattr__(
            self,
            "y_mm",
            _finite_nonnegative(
                self.y_mm, "cartesian y_mm", MAX_ABSOLUTE_XY_BOUND_MM
            ),
        )
        object.__setattr__(
            self,
            "z_mm",
            _finite_nonnegative(
                self.z_mm, "cartesian z_mm", MAX_ABSOLUTE_Z_BOUND_MM
            ),
        )

    def to_dict(self) -> dict[str, float]:
        return {"x_mm": self.x_mm, "y_mm": self.y_mm, "z_mm": self.z_mm}


@dataclass(frozen=True, slots=True)
class PlacematUncertaintyBounds:
    """Assumed study envelope; deliberately unrelated to physical acceptance."""

    board_registration: RigidPoseSensitivityBounds = field(
        default_factory=lambda: RigidPoseSensitivityBounds(1.0, 1.0, 0.5, 0.2)
    )
    keyboard_placement: RigidPoseSensitivityBounds = field(
        default_factory=lambda: RigidPoseSensitivityBounds(1.0, 1.0, 0.5, 0.2)
    )
    phone_placement: RigidPoseSensitivityBounds = field(
        default_factory=lambda: RigidPoseSensitivityBounds(1.0, 1.0, 0.5, 0.2)
    )
    keyboard_target_map: CartesianSensitivityBounds = field(
        default_factory=lambda: CartesianSensitivityBounds(0.5, 0.5, 0.5)
    )
    phone_target_map: CartesianSensitivityBounds = field(
        default_factory=lambda: CartesianSensitivityBounds(0.5, 0.5, 0.5)
    )
    tcp: CartesianSensitivityBounds = field(
        default_factory=lambda: CartesianSensitivityBounds(0.75, 0.75, 0.75)
    )

    def __post_init__(self) -> None:
        expected = (
            ("board_registration", RigidPoseSensitivityBounds),
            ("keyboard_placement", RigidPoseSensitivityBounds),
            ("phone_placement", RigidPoseSensitivityBounds),
            ("keyboard_target_map", CartesianSensitivityBounds),
            ("phone_target_map", CartesianSensitivityBounds),
            ("tcp", CartesianSensitivityBounds),
        )
        for name, expected_type in expected:
            if not isinstance(getattr(self, name), expected_type):
                raise PlacematUncertaintyError(
                    f"{name} must be {expected_type.__name__}"
                )

    @classmethod
    def zero(cls) -> "PlacematUncertaintyBounds":
        """Return a nominal-only study useful for integration verification."""

        return cls(
            board_registration=RigidPoseSensitivityBounds(),
            keyboard_placement=RigidPoseSensitivityBounds(),
            phone_placement=RigidPoseSensitivityBounds(),
            keyboard_target_map=CartesianSensitivityBounds(),
            phone_target_map=CartesianSensitivityBounds(),
            tcp=CartesianSensitivityBounds(),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "input_semantics": (
                "ASSUMED_UNMEASURED_SENSITIVITY_BOUNDS_NOT_TOLERANCES_OR_"
                "ACCEPTANCE_LIMITS"
            ),
            "board_registration": self.board_registration.to_dict(),
            "keyboard_placement": self.keyboard_placement.to_dict(),
            "phone_placement": self.phone_placement.to_dict(),
            "keyboard_target_map": self.keyboard_target_map.to_dict(),
            "phone_target_map": self.phone_target_map.to_dict(),
            "tcp": self.tcp.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class RigidPoseDelta:
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0
    yaw_deg: float = 0.0

    def __post_init__(self) -> None:
        for name, maximum in (
            ("x_mm", MAX_ABSOLUTE_XY_BOUND_MM),
            ("y_mm", MAX_ABSOLUTE_XY_BOUND_MM),
            ("z_mm", MAX_ABSOLUTE_Z_BOUND_MM),
            ("yaw_deg", MAX_ABSOLUTE_YAW_BOUND_DEG),
        ):
            object.__setattr__(
                self, name, _quantize(_finite_signed(getattr(self, name), name, maximum))
            )

    def to_dict(self) -> dict[str, float]:
        return {
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "z_mm": self.z_mm,
            "yaw_deg": self.yaw_deg,
        }


@dataclass(frozen=True, slots=True)
class CartesianDelta:
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0

    def __post_init__(self) -> None:
        for name, maximum in (
            ("x_mm", MAX_ABSOLUTE_XY_BOUND_MM),
            ("y_mm", MAX_ABSOLUTE_XY_BOUND_MM),
            ("z_mm", MAX_ABSOLUTE_Z_BOUND_MM),
        ):
            object.__setattr__(
                self, name, _quantize(_finite_signed(getattr(self, name), name, maximum))
            )

    def to_dict(self) -> dict[str, float]:
        return {"x_mm": self.x_mm, "y_mm": self.y_mm, "z_mm": self.z_mm}


@dataclass(frozen=True, slots=True)
class PlacematUncertaintyCase:
    case_id: str
    board_registration: RigidPoseDelta = field(default_factory=RigidPoseDelta)
    keyboard_placement: RigidPoseDelta = field(default_factory=RigidPoseDelta)
    phone_placement: RigidPoseDelta = field(default_factory=RigidPoseDelta)
    keyboard_target_map: CartesianDelta = field(default_factory=CartesianDelta)
    phone_target_map: CartesianDelta = field(default_factory=CartesianDelta)
    tcp: CartesianDelta = field(default_factory=CartesianDelta)

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or _CASE_ID.fullmatch(self.case_id) is None:
            raise PlacematUncertaintyError("case_id is invalid")
        for name, expected in (
            ("board_registration", RigidPoseDelta),
            ("keyboard_placement", RigidPoseDelta),
            ("phone_placement", RigidPoseDelta),
            ("keyboard_target_map", CartesianDelta),
            ("phone_target_map", CartesianDelta),
            ("tcp", CartesianDelta),
        ):
            if not isinstance(getattr(self, name), expected):
                raise PlacematUncertaintyError(f"case {name} has the wrong type")

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "board_registration": self.board_registration.to_dict(),
            "keyboard_placement": self.keyboard_placement.to_dict(),
            "phone_placement": self.phone_placement.to_dict(),
            "keyboard_target_map": self.keyboard_target_map.to_dict(),
            "phone_target_map": self.phone_target_map.to_dict(),
            "tcp": self.tcp.to_dict(),
        }


class GeometryClassification(str, Enum):
    """Diagnostic landing classification; none of these releases hardware."""

    INSIDE_INTENDED_SAFE_REGION = "INSIDE_INTENDED_SAFE_REGION"
    OUTSIDE_INTENDED_SAFE_REGION = "OUTSIDE_INTENDED_SAFE_REGION"
    ADJACENT_OR_AMBIGUOUS_TARGET = "ADJACENT_OR_AMBIGUOUS_TARGET"
    DEVICE_BOUNDARY_EXCEEDED = "DEVICE_BOUNDARY_EXCEEDED"
    BOARD_BOUNDARY_EXCEEDED = "BOARD_BOUNDARY_EXCEEDED"


_CLASSIFICATION_ORDER = {
    value: index
    for index, value in enumerate(
        (
            GeometryClassification.BOARD_BOUNDARY_EXCEEDED,
            GeometryClassification.DEVICE_BOUNDARY_EXCEEDED,
            GeometryClassification.ADJACENT_OR_AMBIGUOUS_TARGET,
            GeometryClassification.OUTSIDE_INTENDED_SAFE_REGION,
            GeometryClassification.INSIDE_INTENDED_SAFE_REGION,
        )
    )
}


@dataclass(frozen=True, slots=True)
class TargetCaseOutcome:
    case_id: str
    classification: GeometryClassification
    intended_safe_region_xy_margin_mm: float
    error_target_x_mm: float
    error_target_y_mm: float
    absolute_z_error_mm: float
    adjacent_target_ids: tuple[str, ...]
    board_boundary_exceeded: bool
    device_boundary_exceeded: bool

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or _CASE_ID.fullmatch(self.case_id) is None:
            raise PlacematUncertaintyError("outcome case_id is invalid")
        if not isinstance(self.classification, GeometryClassification):
            raise PlacematUncertaintyError("outcome classification is invalid")
        for name in (
            "intended_safe_region_xy_margin_mm",
            "error_target_x_mm",
            "error_target_y_mm",
            "absolute_z_error_mm",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise PlacematUncertaintyError(f"outcome {name} must be numeric")
            value = float(value)
            if not math.isfinite(value):
                raise PlacematUncertaintyError(f"outcome {name} must be finite")
            object.__setattr__(self, name, _quantize(value))
        if self.absolute_z_error_mm < 0.0:
            raise PlacematUncertaintyError("absolute_z_error_mm cannot be negative")
        adjacent = tuple(self.adjacent_target_ids)
        if (
            adjacent != tuple(sorted(adjacent))
            or len(adjacent) != len(set(adjacent))
            or any(not isinstance(value, str) or not value for value in adjacent)
        ):
            raise PlacematUncertaintyError("adjacent target ids are not canonical")
        object.__setattr__(self, "adjacent_target_ids", adjacent)
        for name in ("board_boundary_exceeded", "device_boundary_exceeded"):
            if not isinstance(getattr(self, name), bool):
                raise PlacematUncertaintyError(f"{name} must be boolean")

    @property
    def inside_intended_safe_region(self) -> bool:
        return self.intended_safe_region_xy_margin_mm >= -_EPSILON_MM

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "classification": self.classification.value,
            "inside_intended_safe_region": self.inside_intended_safe_region,
            "intended_safe_region_xy_margin_mm": (
                self.intended_safe_region_xy_margin_mm
            ),
            "error_in_perturbed_target_frame_xy_mm": [
                self.error_target_x_mm,
                self.error_target_y_mm,
            ],
            "absolute_z_error_mm": self.absolute_z_error_mm,
            "adjacent_target_ids": list(self.adjacent_target_ids),
            "board_boundary_exceeded": self.board_boundary_exceeded,
            "device_boundary_exceeded": self.device_boundary_exceeded,
            "physical_acceptance_interpretation": "NONE",
        }


@dataclass(frozen=True, slots=True)
class TargetSensitivitySummary:
    device: str
    target_id: str
    nominal_half_extent_x_mm: float
    nominal_half_extent_y_mm: float
    outcomes: tuple[TargetCaseOutcome, ...]

    def __post_init__(self) -> None:
        if self.device not in {"keyboard", "phone"}:
            raise PlacematUncertaintyError("summary device is invalid")
        if not self.target_id:
            raise PlacematUncertaintyError("summary target_id is empty")
        for name in ("nominal_half_extent_x_mm", "nominal_half_extent_y_mm"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) <= 0.0
            ):
                raise PlacematUncertaintyError(f"summary {name} must be positive")
            object.__setattr__(self, name, _quantize(float(value)))
        outcomes = tuple(self.outcomes)
        if not outcomes or any(
            not isinstance(outcome, TargetCaseOutcome) for outcome in outcomes
        ):
            raise PlacematUncertaintyError("summary requires case outcomes")
        object.__setattr__(self, "outcomes", outcomes)
        if len({outcome.case_id for outcome in outcomes}) != len(outcomes):
            raise PlacematUncertaintyError("summary case ids are not unique")

    @property
    def worst_xy_margin_mm(self) -> float:
        return min(outcome.intended_safe_region_xy_margin_mm for outcome in self.outcomes)

    @property
    def worst_xy_case_id(self) -> str:
        return min(
            self.outcomes,
            key=lambda outcome: (
                outcome.intended_safe_region_xy_margin_mm,
                outcome.case_id,
            ),
        ).case_id

    @property
    def maximum_absolute_z_error_mm(self) -> float:
        return max(outcome.absolute_z_error_mm for outcome in self.outcomes)

    @property
    def worst_z_case_id(self) -> str:
        return min(
            self.outcomes,
            key=lambda outcome: (-outcome.absolute_z_error_mm, outcome.case_id),
        ).case_id

    @property
    def sensitivity_gap_observed(self) -> bool:
        return any(
            outcome.classification
            is not GeometryClassification.INSIDE_INTENDED_SAFE_REGION
            for outcome in self.outcomes
        )

    @property
    def observed_classifications(self) -> tuple[GeometryClassification, ...]:
        return tuple(
            sorted(
                {outcome.classification for outcome in self.outcomes},
                key=_CLASSIFICATION_ORDER.__getitem__,
            )
        )

    def to_dict(self) -> dict[str, object]:
        counts = {
            classification.value: sum(
                outcome.classification is classification for outcome in self.outcomes
            )
            for classification in GeometryClassification
        }
        return {
            "device": self.device,
            "target_id": self.target_id,
            "nominal_safe_half_extent_xy_mm": [
                self.nominal_half_extent_x_mm,
                self.nominal_half_extent_y_mm,
            ],
            "worst_intended_safe_region_xy_margin_mm": self.worst_xy_margin_mm,
            "worst_xy_case_id": self.worst_xy_case_id,
            "maximum_absolute_z_error_mm": self.maximum_absolute_z_error_mm,
            "worst_z_case_id": self.worst_z_case_id,
            "sensitivity_gap_observed": self.sensitivity_gap_observed,
            "observed_classifications": [
                value.value for value in self.observed_classifications
            ],
            "classification_counts": counts,
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
        }


@dataclass(frozen=True, slots=True)
class PlacematUncertaintySourceBinding:
    design_revision: str
    snapshot_sha256: str
    system_manifest_sha256: str
    simulation_bundle_id: str
    simulation_bundle_sha256: str
    simulation_hardware_profile_sha256: str
    nominal_target_profile_sha256: str
    alignment_report_sha256: str
    scene_source_hashes: tuple[tuple[str, str], ...]
    static_support_design_id: str
    static_support_sha256: str
    b0477_profile_id: str
    b0477_profile_file_sha256: str
    b0477_profile_canonical_sha256: str
    camera_architecture_plan_sha256: str
    implementation_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "snapshot_sha256",
            "system_manifest_sha256",
            "simulation_bundle_sha256",
            "simulation_hardware_profile_sha256",
            "nominal_target_profile_sha256",
            "alignment_report_sha256",
            "static_support_sha256",
            "b0477_profile_file_sha256",
            "b0477_profile_canonical_sha256",
            "camera_architecture_plan_sha256",
            "implementation_sha256",
        ):
            _require_digest(getattr(self, name), name)
        if not self.design_revision or not self.simulation_bundle_id:
            raise PlacematUncertaintyError("source identity is incomplete")
        if self.scene_source_hashes != tuple(sorted(self.scene_source_hashes)):
            raise PlacematUncertaintyError("scene source hashes are not canonical")
        for name, digest in self.scene_source_hashes:
            if not name:
                raise PlacematUncertaintyError("scene source name is empty")
            _require_digest(digest, f"scene source {name}")

    def to_dict(self) -> dict[str, object]:
        return {
            "design_revision": self.design_revision,
            "snapshot_sha256": self.snapshot_sha256,
            "system_manifest_sha256": self.system_manifest_sha256,
            "simulation_bundle_id": self.simulation_bundle_id,
            "simulation_bundle_sha256": self.simulation_bundle_sha256,
            "simulation_hardware_profile_sha256": (
                self.simulation_hardware_profile_sha256
            ),
            "canonical_profile_camera_boundary": {
                "state": "LEGACY_EYE_ON_ARM_RETAINED_UNDER_ALIGNMENT_HOLD",
                "role_in_this_study": "ROBOT_AND_NOMINAL_RC03_CONTEXT_ONLY",
                "reinterpreted_as_b0477_static": False,
                "superseding_controlled_freeze_required": True,
            },
            "nominal_target_profile_sha256": self.nominal_target_profile_sha256,
            "alignment_report_sha256": self.alignment_report_sha256,
            "scene_source_hashes": dict(self.scene_source_hashes),
            "selected_static_camera": {
                "architecture": "STATIC_OVERHEAD_EYE_TO_HAND",
                "support_design_id": self.static_support_design_id,
                "support_design_sha256": self.static_support_sha256,
                "purchased_profile_id": self.b0477_profile_id,
                "purchased_profile_file_sha256": self.b0477_profile_file_sha256,
                "purchased_profile_canonical_sha256": (
                    self.b0477_profile_canonical_sha256
                ),
                "camera_architecture_plan_sha256": (
                    self.camera_architecture_plan_sha256
                ),
                "physical_identity_verified": False,
                "physical_installation_verified": False,
            },
            "implementation": {
                "id": "rocell.application.placemat_uncertainty.v1",
                "module_sha256": self.implementation_sha256,
            },
        }


@dataclass(frozen=True, slots=True)
class PlacematUncertaintyReport:
    source_binding: PlacematUncertaintySourceBinding
    bounds: PlacematUncertaintyBounds
    cases: tuple[PlacematUncertaintyCase, ...]
    targets: tuple[TargetSensitivitySummary, ...]
    schema: str = PLACEMAT_UNCERTAINTY_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != PLACEMAT_UNCERTAINTY_SCHEMA:
            raise PlacematUncertaintyError("unsupported report schema")
        if not isinstance(self.source_binding, PlacematUncertaintySourceBinding):
            raise PlacematUncertaintyError("report source binding is invalid")
        if not isinstance(self.bounds, PlacematUncertaintyBounds):
            raise PlacematUncertaintyError("report bounds are invalid")
        if any(not isinstance(case, PlacematUncertaintyCase) for case in self.cases):
            raise PlacematUncertaintyError("report contains an invalid case")
        if any(not isinstance(target, TargetSensitivitySummary) for target in self.targets):
            raise PlacematUncertaintyError("report contains an invalid target summary")
        if not 1 <= len(self.cases) <= MAX_CASES:
            raise PlacematUncertaintyError("case count is outside the work limit")
        if not 1 <= len(self.targets) <= MAX_TARGETS:
            raise PlacematUncertaintyError("target count is outside the work limit")
        if len(self.cases) * len(self.targets) > MAX_OBSERVATIONS:
            raise PlacematUncertaintyError("observation count exceeds the work limit")
        case_ids = tuple(case.case_id for case in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise PlacematUncertaintyError("report case ids are not unique")
        target_keys = tuple((target.device, target.target_id) for target in self.targets)
        if len(target_keys) != len(set(target_keys)):
            raise PlacematUncertaintyError("report target keys are not unique")
        if any(
            tuple(outcome.case_id for outcome in target.outcomes) != case_ids
            for target in self.targets
        ):
            raise PlacematUncertaintyError("target outcomes do not cover the case matrix")

    @property
    def keyboard_target_count(self) -> int:
        return sum(target.device == "keyboard" for target in self.targets)

    @property
    def phone_target_count(self) -> int:
        return sum(target.device == "phone" for target in self.targets)

    @property
    def sensitivity_gap_count(self) -> int:
        return sum(target.sensitivity_gap_observed for target in self.targets)

    @property
    def status(self) -> str:
        if self.sensitivity_gap_count:
            return "SENSITIVITY_GAPS_OBSERVED_NO_PHYSICAL_CONCLUSION"
        return "NO_GAPS_IN_SAMPLED_ASSUMPTIONS_NO_PHYSICAL_CONCLUSION"

    def _without_hash(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "status": self.status,
            "evidence_state": PLACEMAT_UNCERTAINTY_STATUS,
            "generator": PLACEMAT_UNCERTAINTY_GENERATOR,
            "authority": _authority(),
            "interpretation": {
                "bounds_are": "ASSUMED_UNMEASURED_SENSITIVITY_INPUTS",
                "bounds_are_not": [
                    "HARDWARE_TOLERANCES",
                    "CALIBRATION_ACCEPTANCE_LIMITS",
                    "SAFETY_LIMITS",
                    "PHYSICAL_RELEASE_EVIDENCE",
                ],
                "nominal_command_model": (
                    "The software commands the nominal target centre; assumed physical "
                    "geometry and the actual TCP are displaced around it."
                ),
                "board_yaw_pivot": "NOMINAL_BOARD_XY_CENTRE",
                "device_yaw_pivot": "NOMINAL_DEVICE_FRONT_LEFT_ORIGIN",
                "z_result": (
                    "Absolute separation between assumed target plane and assumed "
                    "actual TCP contact point; not a contact-depth criterion."
                ),
            },
            "source_binding": self.source_binding.to_dict(),
            "bounds": self.bounds.to_dict(),
            "counts": {
                "cases": len(self.cases),
                "targets": len(self.targets),
                "keyboard_targets": self.keyboard_target_count,
                "phone_targets": self.phone_target_count,
                "observations": len(self.cases) * len(self.targets),
                "targets_with_sensitivity_gap": self.sensitivity_gap_count,
            },
            "cases": [case.to_dict() for case in self.cases],
            "targets": [target.to_dict() for target in self.targets],
        }

    @property
    def report_sha256(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, object]:
        return {**self._without_hash(), "report_sha256": self.report_sha256}


def _case_payload_key(case: PlacematUncertaintyCase) -> str:
    document = case.to_dict()
    document.pop("case_id")
    return _stable_hash(document)


def _with_rigid_delta(
    case: PlacematUncertaintyCase,
    field_name: str,
    delta: RigidPoseDelta,
) -> PlacematUncertaintyCase:
    """Replace one rigid-pose field without losing static type information."""

    if field_name == "board_registration":
        return replace(case, board_registration=delta)
    if field_name == "keyboard_placement":
        return replace(case, keyboard_placement=delta)
    if field_name == "phone_placement":
        return replace(case, phone_placement=delta)
    raise PlacematUncertaintyError(f"unsupported rigid-pose field {field_name!r}")


def _with_cartesian_delta(
    case: PlacematUncertaintyCase,
    field_name: str,
    delta: CartesianDelta,
) -> PlacematUncertaintyCase:
    """Replace one Cartesian field without dynamic dataclass keyword typing."""

    if field_name == "keyboard_target_map":
        return replace(case, keyboard_target_map=delta)
    if field_name == "phone_target_map":
        return replace(case, phone_target_map=delta)
    if field_name == "tcp":
        return replace(case, tcp=delta)
    raise PlacematUncertaintyError(f"unsupported Cartesian field {field_name!r}")


def _generate_cases(bounds: PlacematUncertaintyBounds) -> tuple[PlacematUncertaintyCase, ...]:
    nominal = PlacematUncertaintyCase("nominal")
    cases: list[PlacematUncertaintyCase] = [nominal]

    rigid_axes = (
        ("board", "board_registration", bounds.board_registration),
        ("keyboard-placement", "keyboard_placement", bounds.keyboard_placement),
        ("phone-placement", "phone_placement", bounds.phone_placement),
    )
    cartesian_axes = (
        ("keyboard-target-map", "keyboard_target_map", bounds.keyboard_target_map),
        ("phone-target-map", "phone_target_map", bounds.phone_target_map),
        ("tcp", "tcp", bounds.tcp),
    )
    for label, field_name, rigid_source in rigid_axes:
        for axis in ("x_mm", "y_mm", "z_mm", "yaw_deg"):
            magnitude = getattr(rigid_source, axis)
            if magnitude == 0.0:
                continue
            for suffix, sign in (("neg", -1.0), ("pos", 1.0)):
                rigid_delta = replace(
                    RigidPoseDelta(), **{axis: sign * magnitude}
                )
                named_case = replace(
                    nominal,
                    case_id=f"{label}-{axis.removesuffix('_mm').removesuffix('_deg')}-{suffix}",
                )
                cases.append(_with_rigid_delta(named_case, field_name, rigid_delta))
    for label, field_name, cartesian_source in cartesian_axes:
        for axis in ("x_mm", "y_mm", "z_mm"):
            magnitude = getattr(cartesian_source, axis)
            if magnitude == 0.0:
                continue
            for suffix, sign in (("neg", -1.0), ("pos", 1.0)):
                cartesian_delta = replace(
                    CartesianDelta(), **{axis: sign * magnitude}
                )
                named_case = replace(
                    nominal,
                    case_id=f"{label}-{axis.removesuffix('_mm')}-{suffix}",
                )
                cases.append(
                    _with_cartesian_delta(named_case, field_name, cartesian_delta)
                )

    # Eight signed XYZ corners per device combine all error sources and put the
    # TCP on the opposing sign.  This is a compact deterministic stress screen,
    # not a probability distribution or physical worst-case proof.
    for device in ("keyboard", "phone"):
        placement_bounds = getattr(bounds, f"{device}_placement")
        target_bounds = getattr(bounds, f"{device}_target_map")
        active = any(
            value != 0.0
            for value in (
                *bounds.board_registration.to_dict().values(),
                *placement_bounds.to_dict().values(),
                *target_bounds.to_dict().values(),
                *bounds.tcp.to_dict().values(),
            )
        )
        if not active:
            continue
        for sx, sy, sz in product((-1.0, 1.0), repeat=3):
            board = RigidPoseDelta(
                sx * bounds.board_registration.x_mm,
                sy * bounds.board_registration.y_mm,
                sz * bounds.board_registration.z_mm,
                sx * bounds.board_registration.yaw_deg,
            )
            placement = RigidPoseDelta(
                sx * placement_bounds.x_mm,
                sy * placement_bounds.y_mm,
                sz * placement_bounds.z_mm,
                sy * placement_bounds.yaw_deg,
            )
            target_map = CartesianDelta(
                sx * target_bounds.x_mm,
                sy * target_bounds.y_mm,
                sz * target_bounds.z_mm,
            )
            tcp = CartesianDelta(
                -sx * bounds.tcp.x_mm,
                -sy * bounds.tcp.y_mm,
                -sz * bounds.tcp.z_mm,
            )
            sign_name = "".join("p" if sign > 0.0 else "n" for sign in (sx, sy, sz))
            named_case = replace(
                nominal,
                case_id=f"{device}-corner-{sign_name}",
                board_registration=board,
                tcp=tcp,
            )
            named_case = _with_rigid_delta(
                named_case, f"{device}_placement", placement
            )
            cases.append(
                _with_cartesian_delta(
                    named_case, f"{device}_target_map", target_map
                )
            )

    # Zero-valued axes can make distinct case labels encode identical geometry.
    # Retain only the first canonical payload so reports never inflate evidence
    # with duplicate samples.
    unique: list[PlacematUncertaintyCase] = []
    seen: set[str] = set()
    for case in cases:
        key = _case_payload_key(case)
        if key in seen:
            continue
        seen.add(key)
        unique.append(case)
    if len(unique) > MAX_CASES:
        raise PlacematUncertaintyError("generated case count exceeds the work limit")
    return tuple(unique)


def _rotate(x_mm: float, y_mm: float, yaw_rad: float) -> tuple[float, float]:
    cosine = math.cos(yaw_rad)
    sine = math.sin(yaw_rad)
    return cosine * x_mm - sine * y_mm, sine * x_mm + cosine * y_mm


def _point_inside(
    x_mm: float,
    y_mm: float,
    bounds: tuple[float, float, float, float],
) -> bool:
    return (
        bounds[0] - _EPSILON_MM <= x_mm <= bounds[2] + _EPSILON_MM
        and bounds[1] - _EPSILON_MM <= y_mm <= bounds[3] + _EPSILON_MM
    )


@dataclass(frozen=True, slots=True)
class _PerturbedTarget:
    center_x_mm: float
    center_y_mm: float
    center_z_mm: float
    yaw_rad: float
    region_leaves_device: bool
    region_leaves_board: bool


def _inverse_board_xy(
    x_mm: float,
    y_mm: float,
    case: PlacematUncertaintyCase,
    board_center: tuple[float, float],
) -> tuple[float, float]:
    shifted_x = x_mm - board_center[0] - case.board_registration.x_mm
    shifted_y = y_mm - board_center[1] - case.board_registration.y_mm
    local_x, local_y = _rotate(
        shifted_x,
        shifted_y,
        -math.radians(case.board_registration.yaw_deg),
    )
    return local_x + board_center[0], local_y + board_center[1]


def _perturbed_target(
    target: TargetRegion,
    case: PlacematUncertaintyCase,
    device_bounds: tuple[float, float, float, float],
    board_bounds: tuple[float, float, float, float],
    board_center: tuple[float, float],
) -> _PerturbedTarget:
    placement = getattr(case, f"{target.device}_placement")
    target_map = getattr(case, f"{target.device}_target_map")
    origin_x, origin_y = device_bounds[0], device_bounds[1]
    width = device_bounds[2] - device_bounds[0]
    depth = device_bounds[3] - device_bounds[1]
    nominal_local_x = target.center.x - origin_x
    nominal_local_y = target.center.y - origin_y
    device_yaw = math.radians(placement.yaw_deg)
    local_center_x = nominal_local_x + target_map.x_mm
    local_center_y = nominal_local_y + target_map.y_mm
    rotated_x, rotated_y = _rotate(local_center_x, local_center_y, device_yaw)
    preboard_x = origin_x + placement.x_mm + rotated_x
    preboard_y = origin_y + placement.y_mm + rotated_y

    board_yaw = math.radians(case.board_registration.yaw_deg)
    rotated_board_x, rotated_board_y = _rotate(
        preboard_x - board_center[0],
        preboard_y - board_center[1],
        board_yaw,
    )
    center_x = board_center[0] + case.board_registration.x_mm + rotated_board_x
    center_y = board_center[1] + case.board_registration.y_mm + rotated_board_y

    region_leaves_device = not (
        0.0 <= local_center_x - target.half_extent_x_mm
        and local_center_x + target.half_extent_x_mm <= width
        and 0.0 <= local_center_y - target.half_extent_y_mm
        and local_center_y + target.half_extent_y_mm <= depth
    )
    preboard_corners: list[tuple[float, float]] = []
    total_local_yaw = device_yaw
    for dx, dy in product(
        (-target.half_extent_x_mm, target.half_extent_x_mm),
        (-target.half_extent_y_mm, target.half_extent_y_mm),
    ):
        corner_dx, corner_dy = _rotate(dx, dy, total_local_yaw)
        preboard_corners.append((preboard_x + corner_dx, preboard_y + corner_dy))
    region_leaves_board = any(
        not _point_inside(x_mm, y_mm, board_bounds)
        for x_mm, y_mm in preboard_corners
    )
    # A displaced or rotated device envelope leaving the physical placemat is
    # also a board-boundary result for every target on that device.
    for local_x, local_y in product((0.0, width), (0.0, depth)):
        corner_x, corner_y = _rotate(local_x, local_y, device_yaw)
        if not _point_inside(
            origin_x + placement.x_mm + corner_x,
            origin_y + placement.y_mm + corner_y,
            board_bounds,
        ):
            region_leaves_board = True
            break
    return _PerturbedTarget(
        center_x_mm=center_x,
        center_y_mm=center_y,
        center_z_mm=(
            target.center.z
            + case.board_registration.z_mm
            + placement.z_mm
            + target_map.z_mm
        ),
        yaw_rad=board_yaw + device_yaw,
        region_leaves_device=region_leaves_device,
        region_leaves_board=region_leaves_board,
    )


def _outcome(
    target: TargetRegion,
    case: PlacematUncertaintyCase,
    geometry: Mapping[str, _PerturbedTarget],
    target_regions: Mapping[str, TargetRegion],
    device_bounds: tuple[float, float, float, float],
    board_bounds: tuple[float, float, float, float],
    board_center: tuple[float, float],
) -> TargetCaseOutcome:
    actual = geometry[target.target_id]
    achieved_x = target.center.x + case.tcp.x_mm
    achieved_y = target.center.y + case.tcp.y_mm
    achieved_z = target.center.z + case.tcp.z_mm
    error_x, error_y = _rotate(
        achieved_x - actual.center_x_mm,
        achieved_y - actual.center_y_mm,
        -actual.yaw_rad,
    )
    margin = min(
        target.half_extent_x_mm - abs(error_x),
        target.half_extent_y_mm - abs(error_y),
    )

    preboard_x, preboard_y = _inverse_board_xy(
        achieved_x, achieved_y, case, board_center
    )
    board_boundary = actual.region_leaves_board or not _point_inside(
        preboard_x, preboard_y, board_bounds
    )

    placement = getattr(case, f"{target.device}_placement")
    device_local_x, device_local_y = _rotate(
        preboard_x - device_bounds[0] - placement.x_mm,
        preboard_y - device_bounds[1] - placement.y_mm,
        -math.radians(placement.yaw_deg),
    )
    device_boundary = actual.region_leaves_device or not (
        -_EPSILON_MM
        <= device_local_x
        <= device_bounds[2] - device_bounds[0] + _EPSILON_MM
        and -_EPSILON_MM
        <= device_local_y
        <= device_bounds[3] - device_bounds[1] + _EPSILON_MM
    )

    adjacent: list[str] = []
    for other_id, other in geometry.items():
        if other_id == target.target_id:
            continue
        other_target_error_x, other_target_error_y = _rotate(
            achieved_x - other.center_x_mm,
            achieved_y - other.center_y_mm,
            -other.yaw_rad,
        )
        other_region = target_regions[other_id]
        if (
            abs(other_target_error_x)
            <= other_region.half_extent_x_mm + _EPSILON_MM
            and abs(other_target_error_y)
            <= other_region.half_extent_y_mm + _EPSILON_MM
        ):
            adjacent.append(other_id)

    if board_boundary:
        classification = GeometryClassification.BOARD_BOUNDARY_EXCEEDED
    elif device_boundary:
        classification = GeometryClassification.DEVICE_BOUNDARY_EXCEEDED
    elif adjacent:
        classification = GeometryClassification.ADJACENT_OR_AMBIGUOUS_TARGET
    elif margin < -_EPSILON_MM:
        classification = GeometryClassification.OUTSIDE_INTENDED_SAFE_REGION
    else:
        classification = GeometryClassification.INSIDE_INTENDED_SAFE_REGION
    return TargetCaseOutcome(
        case_id=case.case_id,
        classification=classification,
        intended_safe_region_xy_margin_mm=_quantize(margin),
        error_target_x_mm=_quantize(error_x),
        error_target_y_mm=_quantize(error_y),
        absolute_z_error_mm=_quantize(abs(achieved_z - actual.center_z_mm)),
        adjacent_target_ids=tuple(sorted(adjacent)),
        board_boundary_exceeded=board_boundary,
        device_boundary_exceeded=device_boundary,
    )


def _summaries(
    context: SimulationContext,
    cases: tuple[PlacematUncertaintyCase, ...],
) -> tuple[TargetSensitivitySummary, ...]:
    board = context.scene.board
    board_bounds = (
        board.minimum.x,
        board.minimum.y,
        board.maximum.x,
        board.maximum.y,
    )
    board_center = (
        (board.minimum.x + board.maximum.x) / 2.0,
        (board.minimum.y + board.maximum.y) / 2.0,
    )
    target_groups = (
        ("keyboard", context.targets.keyboard_targets),
        ("phone", context.targets.phone_targets),
    )
    summaries: list[TargetSensitivitySummary] = []
    for device, targets in target_groups:
        envelope = context.scene.devices[device].envelope
        device_bounds = (
            envelope.minimum.x,
            envelope.minimum.y,
            envelope.maximum.x,
            envelope.maximum.y,
        )
        outcomes_by_target: dict[str, list[TargetCaseOutcome]] = {
            target_id: [] for target_id in sorted(targets)
        }
        for case in cases:
            geometry = {
                target_id: _perturbed_target(
                    target,
                    case,
                    device_bounds,
                    board_bounds,
                    board_center,
                )
                for target_id, target in sorted(targets.items())
            }
            for target_id, target in sorted(targets.items()):
                outcomes_by_target[target_id].append(
                    _outcome(
                        target,
                        case,
                        geometry,
                        targets,
                        device_bounds,
                        board_bounds,
                        board_center,
                    )
                )
        summaries.extend(
            TargetSensitivitySummary(
                device=device,
                target_id=target_id,
                nominal_half_extent_x_mm=target.half_extent_x_mm,
                nominal_half_extent_y_mm=target.half_extent_y_mm,
                outcomes=tuple(outcomes_by_target[target_id]),
            )
            for target_id, target in sorted(targets.items())
        )
    return tuple(summaries)


def _contained_path(root: Path, selected: Path | None, default: Path, label: str) -> Path:
    candidate = default if selected is None else Path(selected)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PlacematUncertaintyError(f"{label} escapes the workspace") from exc
    if not resolved.is_file():
        raise PlacematUncertaintyError(f"{label} is not a file: {resolved}")
    return resolved


def _source_binding(
    context: SimulationContext,
    *,
    support_path: Path | None,
    camera_profile_path: Path | None,
) -> PlacematUncertaintySourceBinding:
    root = context.workspace.resolve()
    selected_support = _contained_path(
        root,
        support_path,
        DEFAULT_STATIC_CAMERA_SUPPORT_DESIGN,
        "static support design",
    )
    selected_profile = _contained_path(
        root,
        camera_profile_path,
        Path(DEFAULT_B0477_CAMERA_PROFILE),
        "purchased B0477 profile",
    )
    support = load_static_camera_support_design(root, selected_support)
    profile = load_camera_profile(selected_profile)

    scene_board = context.scene.board
    scene_size = (
        scene_board.maximum.x - scene_board.minimum.x,
        scene_board.maximum.y - scene_board.minimum.y,
        scene_board.maximum.z - scene_board.minimum.z,
    )
    layout_hash = context.scene.source_hashes.get("config/workcell_layout.json")
    mismatches: list[str] = []
    if support.board_size_mm != scene_size:
        mismatches.append("static support and RC03 scene board dimensions differ")
    if support.source_sha256.get("workcell_layout") != layout_hash:
        mismatches.append("static support and RC03 scene use different layout bytes")
    if support.source_sha256.get("purchased_camera_profile") != profile.source_file_sha256:
        mismatches.append("static support and purchased B0477 profile bytes differ")
    if (support.camera_model, support.sensor) != (
        f"{profile.manufacturer} {profile.model}",
        profile.sensor,
    ):
        mismatches.append("static support and purchased camera identity differ")
    matching_mode = profile.published_mode("USB_3_2_GEN_1", *support.native_mode[:2])
    if matching_mode is None or (
        matching_mode.maximum_fps,
        matching_mode.pixel_format,
    ) != (support.native_mode[2], support.native_mode[3]):
        mismatches.append("static support and purchased native UVC mode differ")
    if any(profile.authority.values()):
        mismatches.append("purchased camera profile unexpectedly grants authority")
    if mismatches:
        raise PlacematUncertaintyError("; ".join(mismatches))

    # Re-read both strict sources so a file change during calculation cannot be
    # hidden behind the first validated object.
    final_support = load_static_camera_support_design(root, selected_support)
    final_profile = load_camera_profile(selected_profile)
    if final_support != support or final_profile != profile:
        raise PlacematUncertaintyError("static camera sources changed while loading")
    return PlacematUncertaintySourceBinding(
        design_revision=context.snapshot.design_revision,
        snapshot_sha256=context.snapshot.snapshot_hash,
        system_manifest_sha256=context.snapshot.manifest_sha256,
        simulation_bundle_id=context.bundle_lock.bundle_id,
        simulation_bundle_sha256=context.bundle_lock.source_lock_sha256,
        simulation_hardware_profile_sha256=(
            context.hardware_profile.source_profile_sha256
        ),
        nominal_target_profile_sha256=context.targets.content_sha256,
        alignment_report_sha256=context.alignment.report_hash,
        scene_source_hashes=tuple(sorted(context.scene.source_hashes.items())),
        static_support_design_id=support.design_id,
        static_support_sha256=support.content_sha256,
        b0477_profile_id=profile.profile_id,
        b0477_profile_file_sha256=profile.source_file_sha256,
        b0477_profile_canonical_sha256=profile.canonical_sha256,
        camera_architecture_plan_sha256=support.source_sha256[
            "camera_architecture_plan"
        ],
        implementation_sha256=_regular_file_sha256(
            Path(__file__).resolve(), "placemat uncertainty implementation"
        ),
    )


def run_placemat_uncertainty_simulation(
    context: SimulationContext,
    bounds: PlacematUncertaintyBounds | None = None,
    *,
    support_path: Path | None = None,
    camera_profile_path: Path | None = None,
) -> PlacematUncertaintyReport:
    """Run the bounded sensitivity matrix without accessing any hardware."""

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    selected_bounds = PlacematUncertaintyBounds() if bounds is None else bounds
    if not isinstance(selected_bounds, PlacematUncertaintyBounds):
        raise TypeError("bounds must be PlacematUncertaintyBounds")
    revalidate_simulation_context(context)
    if not context.alignment.all_checks_pass:
        raise PlacematUncertaintyError("nominal placemat alignment did not pass")
    counts = (
        len(context.targets.keyboard_targets),
        len(context.targets.phone_targets),
    )
    if counts != (EXPECTED_KEYBOARD_TARGETS, EXPECTED_PHONE_TARGETS):
        raise PlacematUncertaintyError(
            "current RC03 target coverage must remain exactly 46 keyboard and 29 phone targets"
        )
    if sum(counts) > MAX_TARGETS:
        raise PlacematUncertaintyError("target count exceeds the work limit")

    binding = _source_binding(
        context,
        support_path=support_path,
        camera_profile_path=camera_profile_path,
    )
    cases = _generate_cases(selected_bounds)
    if len(cases) * sum(counts) > MAX_OBSERVATIONS:
        raise PlacematUncertaintyError("case matrix exceeds the work limit")
    targets = _summaries(context, cases)

    # Reconstruct every RC03 input after computation.  A caller-modified frozen
    # copy or source-file change therefore cannot inherit the original hashes.
    revalidate_simulation_context(context)
    final_binding = _source_binding(
        context,
        support_path=support_path,
        camera_profile_path=camera_profile_path,
    )
    if final_binding != binding:
        raise PlacematUncertaintyError("source bindings changed during the study")
    return PlacematUncertaintyReport(
        source_binding=binding,
        bounds=selected_bounds,
        cases=cases,
        targets=targets,
    )


__all__ = [
    "CartesianSensitivityBounds",
    "EXPECTED_KEYBOARD_TARGETS",
    "EXPECTED_PHONE_TARGETS",
    "GeometryClassification",
    "MAX_ABSOLUTE_XY_BOUND_MM",
    "MAX_ABSOLUTE_YAW_BOUND_DEG",
    "MAX_ABSOLUTE_Z_BOUND_MM",
    "PLACEMAT_UNCERTAINTY_GENERATOR",
    "PLACEMAT_UNCERTAINTY_SCHEMA",
    "PLACEMAT_UNCERTAINTY_STATUS",
    "PlacematUncertaintyBounds",
    "PlacematUncertaintyCase",
    "PlacematUncertaintyError",
    "PlacematUncertaintyReport",
    "PlacematUncertaintySourceBinding",
    "RigidPoseSensitivityBounds",
    "TargetCaseOutcome",
    "TargetSensitivitySummary",
    "run_placemat_uncertainty_simulation",
]
