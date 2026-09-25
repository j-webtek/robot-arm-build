"""Bounded, hypothesis-only layout search before physical metrology.

This service explores a deliberately small placement/tool envelope around the
hash-bound RC03 simulation inputs.  It does not modify the canonical workcell.
Every result is a diagnostic overlay and carries zero hardware authority.

The search is staged so that the expensive 46-key + 29-phone catalog is run
only for candidates that first pass the Freeze-005 selected park probe,
spatial sentinels, and
the named phone ``key_a`` contact/approach regressions.  A candidate promoted
by this module is merely eligible for the separate full-route simulator; it is
not claimed to have a continuous, collision-free, or executable route.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import product
import json
import math
from pathlib import Path
from typing import Any, Callable, Iterable

from rocell import __version__
from rocell.geometry import Point3Mm, RigidTransform, Rotation3, UrdfModel, Vec3
from rocell.kinematics import BoardToolTipTarget, IkOptions, RoArmM3NumericalIk
from rocell.models.units import finite_real
from rocell.motion import GeometricDryRunEngine
from rocell.targets import TargetRegion

from ._pinned_model import (
    MAX_PINNED_URDF_BYTES,
    PinnedModelLoadError,
    load_pinned_urdf,
)
from .context import SimulationContext, revalidate_simulation_context
from .park_optimizer import ParkOptimizationReport, run_park_optimization
from .reach_optimizer import (
    ContactPoseResult,
    FullContactEvaluation,
    ParkEvaluation,
    PoseFeasibility,
    ReachStudyInput,
)
from .trajectory_simulation import _hash_file_bounded, _implementation_hashes


_FULL_KEYBOARD_TARGET_COUNT = 46
_FULL_PHONE_TARGET_COUNT = 29
_FULL_TARGET_COUNT = 75
_MAX_COARSE_HYPOTHESES = 243
_MAX_REFINEMENT_ANCHORS = 6
_MAX_REFINEMENT_HYPOTHESES = 66
_MAX_FULL_CATALOG_CANDIDATES = 8
_MAX_LAYOUT_IK_SOLVES = 4_096
_MAX_PARK_OPTIMIZER_IK_SOLVES = 192
_MAX_TOTAL_SERVICE_IK_SOLVES = (
    _MAX_LAYOUT_IK_SOLVES + _MAX_PARK_OPTIMIZER_IK_SOLVES
)
_MAX_CANONICAL_IK_ATTEMPTS = 8
_MAX_CANONICAL_IK_ITERATIONS = 200
_MAX_COARSE_IK_ATTEMPTS = 2
_MAX_COARSE_IK_ITERATIONS = 18
_MAX_REAR_EDGE_OFFSET_MM = 100.0
_MAX_YAW_SENSITIVITY_DELTA_RAD = math.radians(15.0)
_MAX_TOOL_LENGTH_MM = 150.0
_CANONICAL_IK_SOLVER = RoArmM3NumericalIk
_CANONICAL_PARK_OPTIMIZER = run_park_optimization


class PrehardwareLayoutStudyError(ValueError):
    """A layout hypothesis or bounded-search contract is invalid."""


def _stable_hash(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_axis(values: Iterable[object], label: str) -> tuple[float, ...]:
    result = tuple(sorted({finite_real(value, name=label) for value in values}))
    if not result:
        raise PrehardwareLayoutStudyError(f"{label} cannot be empty")
    return result


@dataclass(frozen=True, slots=True)
class LayoutAxisValueEvidence:
    """Field-level provenance for one search value, never physical approval."""

    value: float
    classification: str
    source_id: str
    derivation: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", finite_real(self.value, name="axis value"))
        allowed = {
            "EXACT_LAYOUT_DERIVED",
            "CANONICAL_PROFILE_DERIVED",
            "MIDPOINT_SEARCH_DERIVED",
            "VIRTUAL_SENSITIVITY_SOURCE",
            "SENSITIVITY_ONLY_BOUND",
            "SENSITIVITY_INTERPOLATION",
        }
        if self.classification not in allowed:
            raise PrehardwareLayoutStudyError(
                f"unsupported axis evidence classification {self.classification!r}"
            )
        for name in ("source_id", "derivation"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise PrehardwareLayoutStudyError(f"{name} must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "classification": self.classification,
            "source_id": self.source_id,
            "derivation": self.derivation,
            "physical_measurement": False,
            "mechanically_allowed": False,
        }


@dataclass(frozen=True, slots=True)
class LayoutSearchAxis:
    """One bounded coarse-search axis with evidence for every listed value."""

    field_name: str
    unit: str
    value_evidence: tuple[LayoutAxisValueEvidence, ...]
    envelope_classification: str

    def __post_init__(self) -> None:
        if not isinstance(self.field_name, str) or not self.field_name:
            raise PrehardwareLayoutStudyError("axis field_name must be non-empty")
        if self.unit not in {"mm", "rad"}:
            raise PrehardwareLayoutStudyError("axis unit must be mm or rad")
        evidence = tuple(self.value_evidence)
        if not evidence or len(evidence) > 3:
            raise PrehardwareLayoutStudyError(
                "each coarse axis must contain between one and three values"
            )
        values = tuple(row.value for row in evidence)
        if values != tuple(sorted(set(values))):
            raise PrehardwareLayoutStudyError(
                f"{self.field_name} evidence values must be unique and sorted"
            )
        if self.envelope_classification not in {
            "EXACT_LAYOUT_ENVELOPE_NOT_PHYSICAL_MEASUREMENT",
            "SENSITIVITY_ONLY_NOT_MECHANICAL_ALLOWANCE",
            "VIRTUAL_SENSITIVITY_NOT_MEASURED_TCP",
        }:
            raise PrehardwareLayoutStudyError(
                f"unsupported envelope classification for {self.field_name}"
            )
        object.__setattr__(self, "value_evidence", evidence)

    @property
    def values(self) -> tuple[float, ...]:
        return tuple(row.value for row in self.value_evidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "unit": self.unit,
            "search_values": [row.to_dict() for row in self.value_evidence],
            "search_envelope": [self.values[0], self.values[-1]],
            "envelope_classification": self.envelope_classification,
            "physical_measurement": False,
            "physical_release_effect": "NONE",
        }


@dataclass(frozen=True, slots=True)
class PrehardwareLayoutStudyPolicy:
    """Staged axes, margin gate, and hard resource ceilings."""

    rear_clamp_contact_x: LayoutSearchAxis
    rear_edge_to_base_axis_y: LayoutSearchAxis
    base_yaw_board: LayoutSearchAxis
    keyboard_tool_length: LayoutSearchAxis
    phone_tool_length: LayoutSearchAxis
    refinement_anchor_count: int = 6
    full_catalog_candidate_count: int = 8
    spatial_sentinels_per_device: int = 3
    minimum_normalized_arm_joint_margin: float = 0.01
    maximum_layout_ik_solves: int = _MAX_LAYOUT_IK_SOLVES

    def __post_init__(self) -> None:
        expected = (
            (self.rear_clamp_contact_x, "rear_clamp_contact_x_board_mm", "mm"),
            (
                self.rear_edge_to_base_axis_y,
                "rear_edge_to_base_axis_y_mm",
                "mm",
            ),
            (self.base_yaw_board, "base_yaw_board_rad", "rad"),
            (self.keyboard_tool_length, "keyboard_tool_length_mm", "mm"),
            (self.phone_tool_length, "phone_tool_length_mm", "mm"),
        )
        for axis, name, unit in expected:
            if not isinstance(axis, LayoutSearchAxis):
                raise TypeError(f"{name} must be a LayoutSearchAxis")
            if (axis.field_name, axis.unit) != (name, unit):
                raise PrehardwareLayoutStudyError(
                    f"axis must identify {name} in {unit}"
                )
        rear_values = self.rear_edge_to_base_axis_y.values
        if any(not 0.0 <= value <= _MAX_REAR_EDGE_OFFSET_MM for value in rear_values):
            raise PrehardwareLayoutStudyError(
                "rear-edge Y sensitivity must remain in [0, 100] mm"
            )
        if any(
            not 0.0 <= value <= _MAX_TOOL_LENGTH_MM
            for value in (
                *self.keyboard_tool_length.values,
                *self.phone_tool_length.values,
            )
        ):
            raise PrehardwareLayoutStudyError(
                "tool sensitivity lengths must remain in [0, 150] mm"
            )
        count = math.prod(len(axis.values) for axis, _, _ in expected)
        if count > _MAX_COARSE_HYPOTHESES:
            raise PrehardwareLayoutStudyError(
                f"coarse grid has {count} hypotheses; maximum is "
                f"{_MAX_COARSE_HYPOTHESES}"
            )
        for name, value, lower, upper in (
            (
                "refinement_anchor_count",
                self.refinement_anchor_count,
                1,
                _MAX_REFINEMENT_ANCHORS,
            ),
            (
                "full_catalog_candidate_count",
                self.full_catalog_candidate_count,
                1,
                _MAX_FULL_CATALOG_CANDIDATES,
            ),
            (
                "spatial_sentinels_per_device",
                self.spatial_sentinels_per_device,
                1,
                8,
            ),
            (
                "maximum_layout_ik_solves",
                self.maximum_layout_ik_solves,
                1,
                _MAX_LAYOUT_IK_SOLVES,
            ),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
                raise PrehardwareLayoutStudyError(
                    f"{name} must be an integer in [{lower}, {upper}]"
                )
        margin = finite_real(
            self.minimum_normalized_arm_joint_margin,
            name="minimum_normalized_arm_joint_margin",
        )
        if not 0.0 < margin < 0.5:
            raise PrehardwareLayoutStudyError(
                "minimum_normalized_arm_joint_margin must be in (0, 0.5)"
            )
        object.__setattr__(self, "minimum_normalized_arm_joint_margin", margin)

    @property
    def coarse_hypothesis_count(self) -> int:
        return math.prod(
            len(axis.values)
            for axis in (
                self.rear_clamp_contact_x,
                self.rear_edge_to_base_axis_y,
                self.base_yaw_board,
                self.keyboard_tool_length,
                self.phone_tool_length,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": "RC03_PREHARDWARE_STAGED_LAYOUT_SENSITIVITY_V1",
            "axes": {
                axis.field_name: axis.to_dict()
                for axis in (
                    self.rear_clamp_contact_x,
                    self.rear_edge_to_base_axis_y,
                    self.base_yaw_board,
                    self.keyboard_tool_length,
                    self.phone_tool_length,
                )
            },
            "fixed_hypotheses": {
                "clamp_to_base_axis_x_mm": {
                    "value": 0.0,
                    "classification": "SENSITIVITY_ONLY_UNMEASURED_FIXED_VALUE",
                },
                "base_roll_rad": 0.0,
                "base_pitch_rad": 0.0,
                "base_link_z": "canonical pinned-profile projection",
                "physical_measurement": False,
            },
            "coarse_hypothesis_count": self.coarse_hypothesis_count,
            "refinement": {
                "method": (
                    "one-axis-at-a-time midpoints of the actual adjacent "
                    "coarse intervals"
                ),
                "anchor_count": self.refinement_anchor_count,
                "maximum_hypotheses": _MAX_REFINEMENT_HYPOTHESES,
            },
            "full_catalog_candidate_count": self.full_catalog_candidate_count,
            "spatial_sentinels_per_device": self.spatial_sentinels_per_device,
            "minimum_normalized_arm_joint_margin": (
                self.minimum_normalized_arm_joint_margin
            ),
            "margin_scope": {
                "gated_joints": "five IK arm joints",
                "fixed_gripper_excluded": True,
                "strictly_positive": True,
            },
            "maximum_layout_ik_solves": self.maximum_layout_ik_solves,
            "hard_implementation_caps": {
                "coarse_hypotheses": _MAX_COARSE_HYPOTHESES,
                "refinement_anchors": _MAX_REFINEMENT_ANCHORS,
                "refinement_hypotheses": _MAX_REFINEMENT_HYPOTHESES,
                "full_catalog_candidates": _MAX_FULL_CATALOG_CANDIDATES,
                "layout_ik_solves": _MAX_LAYOUT_IK_SOLVES,
                "park_optimizer_ik_solves": _MAX_PARK_OPTIMIZER_IK_SOLVES,
                "total_service_ik_solves": _MAX_TOTAL_SERVICE_IK_SOLVES,
                "canonical_ik_attempts": _MAX_CANONICAL_IK_ATTEMPTS,
                "canonical_ik_iterations_per_attempt": (
                    _MAX_CANONICAL_IK_ITERATIONS
                ),
                "coarse_ik_attempts": _MAX_COARSE_IK_ATTEMPTS,
                "coarse_ik_iterations_per_attempt": _MAX_COARSE_IK_ITERATIONS,
                "captured_urdf_bytes": MAX_PINNED_URDF_BYTES,
            },
        }

    @property
    def policy_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class LayoutHypothesis:
    """One immutable placement/tool overlay and its field-level evidence."""

    stage: str
    anchor_study_input_id: str | None
    study_input: ReachStudyInput
    field_evidence: tuple[tuple[str, LayoutAxisValueEvidence], ...]

    def __post_init__(self) -> None:
        if self.stage not in {"COARSE", "REFINEMENT"}:
            raise PrehardwareLayoutStudyError("hypothesis stage is invalid")
        expected_fields = {
            "rear_clamp_contact_x_board_mm",
            "rear_edge_to_base_axis_y_mm",
            "base_yaw_board_rad",
            "keyboard_tool_length_mm",
            "phone_tool_length_mm",
        }
        if {name for name, _ in self.field_evidence} != expected_fields:
            raise PrehardwareLayoutStudyError(
                "hypothesis must carry evidence for every searched field"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "anchor_study_input_id": self.anchor_study_input_id,
            "study_input": self.study_input.to_dict(),
            "field_evidence": {
                name: evidence.to_dict() for name, evidence in self.field_evidence
            },
            "hypothesis_only": True,
            "canonical_context_modified": False,
        }


@dataclass(frozen=True, slots=True)
class LayoutNamedPoseResult:
    role: str
    device: str
    target_id: str
    phase: str
    point_board: Point3Mm
    feasibility: PoseFeasibility

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "device": self.device,
            "target_id": self.target_id,
            "phase": self.phase,
            "point_board_mm": [
                self.point_board.x,
                self.point_board.y,
                self.point_board.z,
            ],
            **self.feasibility.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class LayoutRegressionScreen:
    hypothesis: LayoutHypothesis
    selected_park_probe: ParkEvaluation
    named_poses: tuple[LayoutNamedPoseResult, ...]
    required_named_pose_count: int
    skipped_named_pose_roles: tuple[str, ...]
    ranking_key: tuple[Any, ...]
    ik_solve_count: int

    @property
    def accepted_named_pose_count(self) -> int:
        return sum(row.feasibility.accepted for row in self.named_poses)

    @property
    def regression_passed(self) -> bool:
        return (
            self.selected_park_probe.all_routes_accepted
            and bool(self.named_poses)
            and not self.skipped_named_pose_roles
            and len(self.named_poses) == self.required_named_pose_count
            and self.accepted_named_pose_count == self.required_named_pose_count
        )

    @property
    def minimum_normalized_arm_joint_margin(self) -> float | None:
        values = tuple(
            value
            for value in (
                self.selected_park_probe.minimum_normalized_arm_margin,
                *(
                    row.feasibility.minimum_normalized_arm_joint_margin
                    for row in self.named_poses
                    if row.feasibility.accepted
                ),
            )
            if value is not None
        )
        return min(values) if values else None

    def named(self, role: str) -> LayoutNamedPoseResult:
        matches = tuple(row for row in self.named_poses if row.role == role)
        if len(matches) != 1:
            raise PrehardwareLayoutStudyError(
                f"regression screen does not contain exactly one {role!r}"
            )
        return matches[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis": self.hypothesis.to_dict(),
            "regression_passed": self.regression_passed,
            "accepted_named_pose_count": self.accepted_named_pose_count,
            "named_pose_count": len(self.named_poses),
            "required_named_pose_count": self.required_named_pose_count,
            "skipped_named_pose_roles": list(self.skipped_named_pose_roles),
            "fail_fast_staging": (
                "park and phone key_a contact/approach first; spatial "
                "sentinels only when those primary regressions pass"
            ),
            "minimum_normalized_arm_joint_margin": (
                self.minimum_normalized_arm_joint_margin
            ),
            "selected_park_probe": self.selected_park_probe.to_dict(),
            "named_poses": [row.to_dict() for row in self.named_poses],
            "phone_key_a_regressions": {
                "contact": self.named("PHONE_KEY_A_CONTACT").to_dict(),
                "approach": self.named("PHONE_KEY_A_APPROACH").to_dict(),
            },
            "ranking_key": list(self.ranking_key),
            "ik_solve_count": self.ik_solve_count,
            "eligible_for_full_catalog_screen": self.regression_passed,
        }


@dataclass(frozen=True, slots=True)
class LayoutFullCatalogScreen:
    hypothesis: LayoutHypothesis
    contacts: FullContactEvaluation
    selected_park_probe: ParkEvaluation
    phone_key_a_approach: PoseFeasibility
    ik_solve_count: int

    @property
    def phone_key_a_contact(self) -> ContactPoseResult:
        matches = tuple(
            row
            for row in self.contacts.outcomes
            if row.device == "phone" and row.target_id == "key_a"
        )
        if len(matches) != 1:
            raise PrehardwareLayoutStudyError(
                "full catalog does not contain exactly one phone key_a"
            )
        return matches[0]

    @property
    def eligible_for_full_route_screen(self) -> bool:
        return (
            self.contacts.all_contacts_accepted
            and self.selected_park_probe.all_routes_accepted
            and self.phone_key_a_contact.feasibility.accepted
            and self.phone_key_a_approach.accepted
        )

    @property
    def minimum_normalized_arm_joint_margin(self) -> float | None:
        values = tuple(
            value
            for value in (
                self.contacts.minimum_normalized_arm_margin,
                self.selected_park_probe.minimum_normalized_arm_margin,
                self.phone_key_a_approach.minimum_normalized_arm_joint_margin,
            )
            if value is not None
        )
        return min(values) if values else None

    @property
    def rejection_reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if not self.selected_park_probe.all_routes_accepted:
            reasons.append("SELECTED_PARK_PROBE_BOTH_ROUTE_TOOLS_NOT_ACCEPTED")
        if not self.contacts.all_contacts_accepted:
            reasons.append("FULL_46_KEYBOARD_PLUS_29_PHONE_CONTACTS_NOT_ACCEPTED")
        if not self.phone_key_a_contact.feasibility.accepted:
            reasons.append("PHONE_KEY_A_CONTACT_REGRESSION_FAILED")
        if not self.phone_key_a_approach.accepted:
            reasons.append("PHONE_KEY_A_APPROACH_MARGIN_REGRESSION_FAILED")
        return tuple(reasons)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis": self.hypothesis.to_dict(),
            "coverage": self.contacts.to_dict(),
            "selected_park_probe": self.selected_park_probe.to_dict(),
            "named_regressions": {
                "phone_key_a_contact": self.phone_key_a_contact.to_dict(),
                "phone_key_a_approach": self.phone_key_a_approach.to_dict(),
            },
            "minimum_normalized_arm_joint_margin": (
                self.minimum_normalized_arm_joint_margin
            ),
            "eligible_for_full_route_screen": self.eligible_for_full_route_screen,
            "rejection_reasons": list(self.rejection_reasons),
            "ik_solve_count": self.ik_solve_count,
            "route_screen_executed": False,
            "execution_authorized": False,
        }


@dataclass(frozen=True, slots=True)
class LayoutCandidatePromotion:
    rank: int
    full_catalog_screen: LayoutFullCatalogScreen

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise PrehardwareLayoutStudyError("promotion rank must be positive")
        if not self.full_catalog_screen.eligible_for_full_route_screen:
            raise PrehardwareLayoutStudyError(
                "only candidates eligible for full-route screening may be promoted"
            )

    @property
    def study_input(self) -> ReachStudyInput:
        return self.full_catalog_screen.hypothesis.study_input

    def to_dict(self) -> dict[str, Any]:
        park = self.full_catalog_screen.selected_park_probe
        return {
            "rank": self.rank,
            "study_input_id": self.study_input.study_input_id,
            "eligible_for_full_route_screen": True,
            "selected_park_probe": {
                "park_id": park.park_id,
                "point_board_mm": [
                    park.point_board.x,
                    park.point_board.y,
                    park.point_board.z,
                ],
            },
            "full_route_screen_executed": False,
            "physical_motion_authorized": False,
            "full_catalog_screen": self.full_catalog_screen.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PrehardwareLayoutStudyReport:
    source_provenance: tuple[tuple[str, Any], ...]
    policy: PrehardwareLayoutStudyPolicy
    freeze005_park_source_report_hash: str
    selected_park_probe_id: str
    selected_park_probe_point_board: Point3Mm
    coarse_screens: tuple[LayoutRegressionScreen, ...]
    refinement_screens: tuple[LayoutRegressionScreen, ...]
    full_catalog_screens: tuple[LayoutFullCatalogScreen, ...]
    promoted_candidates: tuple[LayoutCandidatePromotion, ...]
    planned_layout_ik_solve_upper_bound: int
    actual_layout_ik_solve_count: int
    park_optimizer_actual_ik_solve_count: int

    @property
    def ranked_regression_passes(self) -> tuple[LayoutRegressionScreen, ...]:
        """Return every regression pass in the exact shortlist ranking order."""

        return tuple(
            sorted(
                (
                    row
                    for row in (*self.coarse_screens, *self.refinement_screens)
                    if row.regression_passed
                ),
                key=lambda row: row.ranking_key,
            )
        )

    @property
    def full_catalog_shortlist_candidate_ids(self) -> tuple[str, ...]:
        return tuple(
            row.hypothesis.study_input.study_input_id
            for row in self.full_catalog_screens
        )

    @property
    def omitted_regression_pass_candidate_ids(self) -> tuple[str, ...]:
        screened = set(self.full_catalog_shortlist_candidate_ids)
        return tuple(
            row.hypothesis.study_input.study_input_id
            for row in self.ranked_regression_passes
            if row.hypothesis.study_input.study_input_id not in screened
        )

    @property
    def status(self) -> str:
        if self.promoted_candidates:
            return (
                "CANDIDATES_ELIGIBLE_WITHIN_SCREENED_FULL_CATALOG_SHORTLIST"
            )
        return "NO_CANDIDATE_FOUND_WITHIN_SCREENED_FULL_CATALOG_SHORTLIST"

    @property
    def best_candidate(self) -> LayoutCandidatePromotion | None:
        return self.promoted_candidates[0] if self.promoted_candidates else None

    def to_dict(self) -> dict[str, Any]:
        provenance = dict(self.source_provenance)
        for name in ("coarse_ik_options", "canonical_ik_options"):
            if name in provenance:
                provenance[name] = dict(provenance[name])
        return {
            "schema": "rocell.prehardware_layout_study.v1",
            "status": self.status,
            "scope": "HYPOTHESIS_ONLY_STAGED_INDEPENDENT_POSE_IK",
            "simulation_only": True,
            "execution_authorized": False,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "physical_release_effect": "NONE",
            "canonical_context_modified": False,
            "source_provenance": provenance,
            "policy": {**self.policy.to_dict(), "policy_hash": self.policy.policy_hash},
            "transform_contract": {
                "physical_hypothesis": "B_T_Ru (Ru = URDF base_link)",
                "solver_transform": "B_T_Wv",
                "derivation": "B_T_Wv = B_T_Ru * inverse(Wv_T_Ru)",
                "runtime_invariant": "B_T_Wv * Wv_T_Ru == B_T_Ru",
                "verified_for_every_generated_hypothesis": True,
            },
            "selected_park_probe_binding": {
                "source_freeze005_park_report_hash": (
                    self.freeze005_park_source_report_hash
                ),
                "park_probe_id": self.selected_park_probe_id,
                "point_board_mm": [
                    self.selected_park_probe_point_board.x,
                    self.selected_park_probe_point_board.y,
                    self.selected_park_probe_point_board.z,
                ],
                "per_hypothesis_probe_set_size": 1,
                "selection_algorithm": (
                    "reuse the one Freeze-005 selected coordinate as a fixed "
                    "probe, then independently re-screen it for both route "
                    "tool hypotheses; no per-layout park optimization is claimed"
                ),
                "per_hypothesis_ranking_performed": False,
                "re_screened_for_every_layout_and_route_tool": True,
            },
            "search": {
                "coarse_hypothesis_count": len(self.coarse_screens),
                "refinement_hypothesis_count": len(self.refinement_screens),
                "regression_pass_count": sum(
                    row.regression_passed
                    for row in (*self.coarse_screens, *self.refinement_screens)
                ),
                "full_catalog_candidate_count": len(self.full_catalog_screens),
                "full_catalog_shortlist": {
                    "ranking_basis": "ascending regression ranking_key",
                    "policy_top_n": self.policy.full_catalog_candidate_count,
                    "total_regression_pass_candidates": len(
                        self.ranked_regression_passes
                    ),
                    "screened_candidate_count": len(
                        self.full_catalog_shortlist_candidate_ids
                    ),
                    "screened_candidate_ids_in_rank_order": list(
                        self.full_catalog_shortlist_candidate_ids
                    ),
                    "omitted_candidate_count": len(
                        self.omitted_regression_pass_candidate_ids
                    ),
                    "omitted_candidate_ids_in_rank_order": list(
                        self.omitted_regression_pass_candidate_ids
                    ),
                    "truncated": bool(
                        self.omitted_regression_pass_candidate_ids
                    ),
                    "status_scope": (
                        "status and promotions apply only to the screened "
                        "full-catalog shortlist; omitted regression-pass "
                        "candidates have no full-catalog result"
                    ),
                },
                "full_catalog_required_coverage": {
                    "keyboard": _FULL_KEYBOARD_TARGET_COUNT,
                    "phone": _FULL_PHONE_TARGET_COUNT,
                    "total": _FULL_TARGET_COUNT,
                },
                "planned_layout_ik_solve_upper_bound": (
                    self.planned_layout_ik_solve_upper_bound
                ),
                "actual_layout_ik_solve_count": self.actual_layout_ik_solve_count,
                "park_optimizer_actual_ik_solve_count": (
                    self.park_optimizer_actual_ik_solve_count
                ),
                "actual_total_service_ik_solve_count": (
                    self.actual_layout_ik_solve_count
                    + self.park_optimizer_actual_ik_solve_count
                ),
                "layout_ik_solve_cap": self.policy.maximum_layout_ik_solves,
                "total_service_ik_solve_cap": _MAX_TOTAL_SERVICE_IK_SOLVES,
                "cap_enforced_before_each_layout_solve": True,
                "coarse_screens": [row.to_dict() for row in self.coarse_screens],
                "refinement_screens": [
                    row.to_dict() for row in self.refinement_screens
                ],
                "full_catalog_screens": [
                    row.to_dict() for row in self.full_catalog_screens
                ],
            },
            "promoted_candidates": [row.to_dict() for row in self.promoted_candidates],
            "best_candidate": (
                None if self.best_candidate is None else self.best_candidate.to_dict()
            ),
            "promotion_contract": {
                "name": "eligible_for_full_route_screen",
                "requires": [
                    "Freeze-005 selected park probe accepted by both route tool hypotheses",
                    "all 46 keyboard contact poses accepted",
                    "all 29 phone contact poses accepted",
                    "phone key_a contact accepted",
                    "phone key_a approach accepted at the positive margin gate",
                ],
                "does_not_claim": [
                    "full-route success",
                    "branch continuity",
                    "collision clearance",
                    "physical reachability",
                    "motion or contact authority",
                ],
            },
            "unsupported_diagnostics": [
                "complete route interpolation and sequential branch continuity",
                "robot-link, self, holder, camera, tool-volume, and cable collision",
                "physical six-dimensional singularity/manipulability",
                "payload, dynamics, force, compliance, and cable load",
                "measured board-to-base, route TCP, and controller-frame correlation",
                "vision correction and observed keyboard/Android outcome",
            ],
            "limitations": [
                "Clamp-axis X offset remains fixed at an unmeasured zero hypothesis.",
                "Rear-edge Y, yaw deltas, and route tool lengths are sensitivity values, not measured installation facts.",
                "Yaw sensitivity bounds are not a statement of mechanical allowance.",
                "Only regression-pass candidates receive the complete 75-contact screen.",
                "Status and promotion conclusions are limited to the ranked top-N full-catalog shortlist; every disclosed omitted regression-pass candidate remains unevaluated by the full catalog.",
                "The 2-attempt/18-iteration regression solver can false-reject a hypothesis that a larger search might solve; this bounded staged screen is not exhaustive proof of absence.",
                "Every result is independent-pose IK; promoted candidates still require the separate full-route simulator.",
                "No result authorizes physical motion or contact.",
            ],
        }

    @property
    def report_hash(self) -> str:
        return _stable_hash(self.to_dict())


def _axis(
    field_name: str,
    unit: str,
    rows: Iterable[LayoutAxisValueEvidence],
    envelope_classification: str,
) -> LayoutSearchAxis:
    return LayoutSearchAxis(
        field_name,
        unit,
        tuple(sorted(rows, key=lambda row: row.value)),
        envelope_classification,
    )


def default_prehardware_layout_study_policy(
    context: SimulationContext,
) -> PrehardwareLayoutStudyPolicy:
    """Derive the default 243-point sensitivity grid from locked sources."""

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    clamp_lower, clamp_upper = context.scene.arm_clamp_rear_edge_x_range_mm
    clamp_midpoint = (clamp_lower + clamp_upper) / 2.0
    nominal_yaw = math.atan2(
        context.scenario.board_T_world.rotation.matrix[3],
        context.scenario.board_T_world.rotation.matrix[0],
    )
    tool_lengths = tuple(
        sorted(
            {
                -case.hand_tcp_to_tip_z_mm
                for case in context.scenario.tool_cases
                if case.hand_tcp_to_tip_z_mm < 0.0
            }
        )
    )
    if tool_lengths != (80.0, 100.0, 120.0):
        raise PrehardwareLayoutStudyError(
            "locked virtual tool sensitivity cases must be exactly 80, 100, and 120 mm"
        )
    layout_source = "RC03 config/workcell_layout.json#arm_clamp_zone"
    rear_zero_source = (
        "RC03 config/robot_reach_screening.json#"
        "screening_assumption.board_frame_base_axis_xy_mm"
    )
    rear_hundred_source = (
        "RC03 config/robot_reach_screening.json#"
        "sensitivity_case.assumed_base_axis_xy_mm"
    )
    rear_midpoint_source = (
        "derived midpoint of robot_reach_screening screening_assumption "
        "and sensitivity_case"
    )
    profile_source = "software/config/simulation_hardware_profile.json#virtual_tool_sensitivity_cases"
    clamp_axis = _axis(
        "rear_clamp_contact_x_board_mm",
        "mm",
        (
            LayoutAxisValueEvidence(
                clamp_lower,
                "EXACT_LAYOUT_DERIVED",
                layout_source,
                "lower endpoint of the locked rear-edge clamp contact zone",
            ),
            LayoutAxisValueEvidence(
                clamp_midpoint,
                "MIDPOINT_SEARCH_DERIVED",
                layout_source,
                "arithmetic midpoint of the locked clamp-zone endpoints",
            ),
            LayoutAxisValueEvidence(
                clamp_upper,
                "EXACT_LAYOUT_DERIVED",
                layout_source,
                "upper endpoint of the locked rear-edge clamp contact zone",
            ),
        ),
        "EXACT_LAYOUT_ENVELOPE_NOT_PHYSICAL_MEASUREMENT",
    )
    rear_axis = _axis(
        "rear_edge_to_base_axis_y_mm",
        "mm",
        (
            LayoutAxisValueEvidence(
                0.0,
                "SENSITIVITY_ONLY_BOUND",
                rear_zero_source,
                "locked screening baseline places the assumed axis on the board rear edge",
            ),
            LayoutAxisValueEvidence(
                50.0,
                "MIDPOINT_SEARCH_DERIVED",
                rear_midpoint_source,
                "arithmetic midpoint of the 0..100 mm screening sensitivity envelope",
            ),
            LayoutAxisValueEvidence(
                100.0,
                "SENSITIVITY_ONLY_BOUND",
                rear_hundred_source,
                "locked screening sensitivity case places the assumed axis 100 mm behind the board",
            ),
        ),
        "SENSITIVITY_ONLY_NOT_MECHANICAL_ALLOWANCE",
    )
    yaw_axis = _axis(
        "base_yaw_board_rad",
        "rad",
        tuple(
            LayoutAxisValueEvidence(
                nominal_yaw + delta,
                (
                    "CANONICAL_PROFILE_DERIVED"
                    if delta == 0.0
                    else "SENSITIVITY_ONLY_BOUND"
                ),
                (
                    "software/config/simulation_hardware_profile.json#"
                    "nominal_board_T_robot_world"
                    if delta == 0.0
                    else "software/src/rocell/application/reach_optimizer.py#_study_inputs(+/-15deg-sensitivity-guard)"
                ),
                (
                    "yaw of the locked nominal transform"
                    if delta == 0.0
                    else f"nominal yaw plus a {math.degrees(delta):g} degree sensitivity delta; not a mechanical allowance"
                ),
            )
            for delta in (
                -_MAX_YAW_SENSITIVITY_DELTA_RAD,
                0.0,
                _MAX_YAW_SENSITIVITY_DELTA_RAD,
            )
        ),
        "SENSITIVITY_ONLY_NOT_MECHANICAL_ALLOWANCE",
    )

    def tool_axis(field_name: str) -> LayoutSearchAxis:
        return _axis(
            field_name,
            "mm",
            tuple(
                LayoutAxisValueEvidence(
                    length,
                    "VIRTUAL_SENSITIVITY_SOURCE",
                    profile_source,
                    "magnitude of a locked virtual hand_tcp-to-tip -Z sensitivity case; not a measured route TCP",
                )
                for length in tool_lengths
            ),
            "VIRTUAL_SENSITIVITY_NOT_MEASURED_TCP",
        )

    return PrehardwareLayoutStudyPolicy(
        rear_clamp_contact_x=clamp_axis,
        rear_edge_to_base_axis_y=rear_axis,
        base_yaw_board=yaw_axis,
        keyboard_tool_length=tool_axis("keyboard_tool_length_mm"),
        phone_tool_length=tool_axis("phone_tool_length_mm"),
    )


def _target_catalog(context: SimulationContext) -> tuple[TargetRegion, ...]:
    targets = tuple(
        sorted(
            (
                *context.targets.keyboard_targets.values(),
                *context.targets.phone_targets.values(),
            ),
            key=lambda row: (row.device, row.target_id),
        )
    )
    keyboard_count = sum(row.device == "keyboard" for row in targets)
    phone_count = sum(row.device == "phone" for row in targets)
    if (
        len(targets) != _FULL_TARGET_COUNT
        or keyboard_count != _FULL_KEYBOARD_TARGET_COUNT
        or phone_count != _FULL_PHONE_TARGET_COUNT
    ):
        raise PrehardwareLayoutStudyError(
            "layout study requires the locked 46-key + 29-phone target catalog"
        )
    return targets


def _spatial_sentinels(
    targets: tuple[TargetRegion, ...], per_device: int
) -> tuple[TargetRegion, ...]:
    selected_all: list[TargetRegion] = []
    for device in ("keyboard", "phone"):
        available = tuple(row for row in targets if row.device == device)
        selected = [
            min(
                available,
                key=lambda row: (row.center.x, row.center.y, row.target_id),
            )
        ]
        while len(selected) < min(per_device, len(available)):
            remaining = tuple(row for row in available if row not in selected)
            selected.append(
                max(
                    remaining,
                    key=lambda row: (
                        min(
                            (row.center.x - prior.center.x) ** 2
                            + (row.center.y - prior.center.y) ** 2
                            for prior in selected
                        ),
                        -row.center.x,
                        -row.center.y,
                        row.target_id,
                    ),
                )
            )
        selected_all.extend(selected)
    return tuple(
        sorted(selected_all, key=lambda row: (row.device, row.target_id))
    )


def _contact_point(context: SimulationContext, target: TargetRegion) -> Point3Mm:
    return Point3Mm(
        "board",
        target.center.x,
        target.center.y,
        target.center.z - context.scenario.path_policy.contact_overtravel_mm,
    )


def _approach_point(context: SimulationContext, target: TargetRegion) -> Point3Mm:
    contact = _contact_point(context, target)
    return Point3Mm(
        "board",
        contact.x,
        contact.y,
        contact.z + context.scenario.path_policy.approach_height_mm,
    )


def _evidence_for_value(
    axis: LayoutSearchAxis, value: float
) -> LayoutAxisValueEvidence:
    matches = tuple(row for row in axis.value_evidence if row.value == value)
    if len(matches) != 1:
        raise PrehardwareLayoutStudyError(
            f"coarse value {value} is absent from {axis.field_name} evidence"
        )
    return matches[0]


def _study_input(
    *,
    context: SimulationContext,
    vendor_world_T_base_link: RigidTransform,
    clamp_x: float,
    rear_y: float,
    yaw: float,
    keyboard_tool: float,
    phone_tool: float,
) -> ReachStudyInput:
    board_T_base_link = RigidTransform(
        "board",
        "base_link",
        Rotation3.from_rpy(0.0, 0.0, yaw),
        Vec3(
            clamp_x,
            context.scene.board.maximum.y + rear_y,
            context.scenario.board_T_world.compose(
                vendor_world_T_base_link
            ).translation_mm.z,
        ),
    )
    board_T_vendor_world = board_T_base_link.compose(
        vendor_world_T_base_link.inverse()
    )
    recomposed = board_T_vendor_world.compose(vendor_world_T_base_link)
    expected_matrix = board_T_base_link.to_transform().matrix
    recomposed_matrix = recomposed.to_transform().matrix
    if any(
        not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-9)
        for actual, expected in zip(recomposed_matrix, expected_matrix)
    ):
        raise PrehardwareLayoutStudyError(
            "layout transform invariant failed: B_T_Wv * Wv_T_Ru != B_T_Ru"
        )
    return ReachStudyInput(
        rear_clamp_contact_x_board_mm=clamp_x,
        clamp_to_base_axis_x_mm=0.0,
        base_axis_x_board_mm=clamp_x,
        rear_edge_to_base_axis_y_mm=rear_y,
        base_link_z_board_mm=board_T_base_link.translation_mm.z,
        base_yaw_board_rad=yaw,
        keyboard_tool_length_mm=keyboard_tool,
        phone_tool_length_mm=phone_tool,
        board_T_base_link=board_T_base_link,
        board_T_vendor_world=board_T_vendor_world,
    )


def _coarse_hypotheses(
    context: SimulationContext,
    policy: PrehardwareLayoutStudyPolicy,
    vendor_world_T_base_link: RigidTransform,
) -> tuple[LayoutHypothesis, ...]:
    result: list[LayoutHypothesis] = []
    axes = (
        policy.rear_clamp_contact_x,
        policy.rear_edge_to_base_axis_y,
        policy.base_yaw_board,
        policy.keyboard_tool_length,
        policy.phone_tool_length,
    )
    for values in product(*(axis.values for axis in axes)):
        study = _study_input(
            context=context,
            vendor_world_T_base_link=vendor_world_T_base_link,
            clamp_x=values[0],
            rear_y=values[1],
            yaw=values[2],
            keyboard_tool=values[3],
            phone_tool=values[4],
        )
        result.append(
            LayoutHypothesis(
                "COARSE",
                None,
                study,
                tuple(
                    (axis.field_name, _evidence_for_value(axis, value))
                    for axis, value in zip(axes, values)
                ),
            )
        )
    return tuple(sorted(result, key=lambda row: row.study_input.study_input_id))


def _refinement_value_evidence(
    field_name: str,
    value: float,
    axis: LayoutSearchAxis,
) -> LayoutAxisValueEvidence:
    if any(row.value == value for row in axis.value_evidence):
        return _evidence_for_value(axis, value)
    classification = (
        "MIDPOINT_SEARCH_DERIVED"
        if field_name == "rear_clamp_contact_x_board_mm"
        else "SENSITIVITY_INTERPOLATION"
    )
    return LayoutAxisValueEvidence(
        value,
        classification,
        f"refinement:{axis.field_name}",
        "midpoint of the actual adjacent coarse interval for one-axis refinement",
    )


def _adjacent_interval_midpoints(
    axis: LayoutSearchAxis, anchor_value: float
) -> tuple[float, ...]:
    """Return midpoints of the actual coarse intervals beside an anchor.

    Refinement anchors always originate in the coarse Cartesian grid.  Looking
    up their exact axis value avoids the incorrect assumption that custom axes
    are uniformly spaced.
    """

    try:
        index = axis.values.index(anchor_value)
    except ValueError as exc:
        raise PrehardwareLayoutStudyError(
            f"refinement anchor value {anchor_value} is absent from "
            f"{axis.field_name}"
        ) from exc
    result: list[float] = []
    if index > 0:
        result.append((axis.values[index - 1] + anchor_value) / 2.0)
    if index + 1 < len(axis.values):
        result.append((anchor_value + axis.values[index + 1]) / 2.0)
    return tuple(result)


def _refinement_hypotheses(
    context: SimulationContext,
    policy: PrehardwareLayoutStudyPolicy,
    vendor_world_T_base_link: RigidTransform,
    anchors: tuple[LayoutRegressionScreen, ...],
    existing_ids: set[str],
) -> tuple[LayoutHypothesis, ...]:
    axes = (
        policy.rear_clamp_contact_x,
        policy.rear_edge_to_base_axis_y,
        policy.base_yaw_board,
        policy.keyboard_tool_length,
        policy.phone_tool_length,
    )
    rows: list[LayoutHypothesis] = []
    seen = set(existing_ids)
    for anchor in anchors:
        study = anchor.hypothesis.study_input
        base_values = (
            study.rear_clamp_contact_x_board_mm,
            study.rear_edge_to_base_axis_y_mm,
            study.base_yaw_board_rad,
            study.keyboard_tool_length_mm,
            study.phone_tool_length_mm,
        )
        for axis_index, axis in enumerate(axes):
            for midpoint in _adjacent_interval_midpoints(
                axis, base_values[axis_index]
            ):
                values = list(base_values)
                candidate_value = round(midpoint, 12)
                values[axis_index] = candidate_value
                refined_study = _study_input(
                    context=context,
                    vendor_world_T_base_link=vendor_world_T_base_link,
                    clamp_x=values[0],
                    rear_y=values[1],
                    yaw=values[2],
                    keyboard_tool=values[3],
                    phone_tool=values[4],
                )
                if refined_study.study_input_id in seen:
                    continue
                seen.add(refined_study.study_input_id)
                evidence = tuple(
                    (
                        selected_axis.field_name,
                        _refinement_value_evidence(
                            selected_axis.field_name,
                            value,
                            selected_axis,
                        ),
                    )
                    for selected_axis, value in zip(axes, values)
                )
                rows.append(
                    LayoutHypothesis(
                        "REFINEMENT",
                        study.study_input_id,
                        refined_study,
                        evidence,
                    )
                )
    if len(rows) > _MAX_REFINEMENT_HYPOTHESES:
        raise PrehardwareLayoutStudyError(
            "refinement generation exceeded its hard hypothesis cap"
        )
    return tuple(sorted(rows, key=lambda row: row.study_input.study_input_id))


class _SolveBudget:
    def __init__(self, maximum: int) -> None:
        self.maximum = maximum
        self.actual = 0

    def consume(self) -> None:
        if self.actual >= self.maximum:
            raise PrehardwareLayoutStudyError(
                "maximum_layout_ik_solves exhausted before the next solve"
            )
        self.actual += 1


class _CandidateEvaluator:
    def __init__(
        self,
        context: SimulationContext,
        model: UrdfModel,
        study: ReachStudyInput,
        options: IkOptions,
        minimum_margin: float,
        solver_class: type[Any],
        budget: _SolveBudget,
    ) -> None:
        self.context = context
        self.study = study
        self._model = model
        self._options = options
        self._minimum_margin = minimum_margin
        self._solver_class = solver_class
        self._budget = budget
        self._solvers: dict[float, Any] = {}
        self._cache: dict[tuple[float, float, float, float], PoseFeasibility] = {}

    @property
    def solve_count(self) -> int:
        return len(self._cache)

    def _solver(self, tool_length_mm: float) -> Any:
        if tool_length_mm not in self._solvers:
            scenario = self.context.scenario
            self._solvers[tool_length_mm] = self._solver_class(
                model=self._model,
                board_T_world=self.study.board_T_vendor_world,
                hand_tcp_to_tip_z_mm=-tool_length_mm,
                fixed_gripper_position=scenario.fixed_gripper_position,
                ready_arm_joint_positions=scenario.ready_arm_joint_positions_rad,
                gripper_bounds_rad=scenario.controller_gripper_intersection_rad,
                options=self._options,
                joint_bounds_rad=scenario.controller_joint_intersection_rad,
            )
        return self._solvers[tool_length_mm]

    def screen(self, tool_length_mm: float, point: Point3Mm) -> PoseFeasibility:
        key = (tool_length_mm, point.x, point.y, point.z)
        if key in self._cache:
            return self._cache[key]
        self._budget.consume()
        solved = self._solver(tool_length_mm).solve(BoardToolTipTarget(point))
        bounds = self.context.scenario.controller_joint_intersection_rad
        solution = {
            item.name: item.position.value
            for item in solved.solution_arm_joint_positions
        }
        controller_ok = solved.converged and set(solution) == set(bounds) and all(
            lower <= solution[name] <= upper
            for name, (lower, upper) in bounds.items()
        )
        raw_margin = None
        normalized_margin = None
        if controller_ok:
            raw_margin = min(
                min(value - bounds[name][0], bounds[name][1] - value)
                for name, value in solution.items()
            )
            normalized_margin = min(
                min(value - bounds[name][0], bounds[name][1] - value)
                / (bounds[name][1] - bounds[name][0])
                for name, value in solution.items()
            )
        margin_ok = (
            controller_ok
            and normalized_margin is not None
            and normalized_margin >= self._minimum_margin
        )
        result = PoseFeasibility(
            status=(
                solved.status.value
                if margin_ok or not solved.converged
                else "MINIMUM_NORMALIZED_ARM_JOINT_MARGIN_REJECTED"
                if controller_ok
                else "INTERNAL_CONTROLLER_INTERSECTION_REJECTED"
            ),
            accepted=bool(margin_ok),
            position_error_mm=solved.residual.position_error_mm,
            alignment_error_rad=solved.residual.alignment_error_rad,
            minimum_arm_joint_margin_rad=raw_margin,
            minimum_normalized_arm_joint_margin=normalized_margin,
            attempt_count=len(solved.attempts),
            selected_attempt_index=solved.selected_attempt_index,
            solution_arm_joint_positions_rad=tuple(solution.items()),
        )
        self._cache[key] = result
        return result


def _tool_length(study: ReachStudyInput, device: str) -> float:
    return (
        study.keyboard_tool_length_mm
        if device == "keyboard"
        else study.phone_tool_length_mm
    )


def _park_evaluation(
    evaluator: _CandidateEvaluator,
    park_probe_id: str,
    park_point: Point3Mm,
) -> ParkEvaluation:
    return ParkEvaluation(
        park_probe_id,
        park_point,
        True,
        evaluator.screen(evaluator.study.keyboard_tool_length_mm, park_point),
        evaluator.screen(evaluator.study.phone_tool_length_mm, park_point),
    )


def _deviation(
    context: SimulationContext, study: ReachStudyInput
) -> float:
    nominal_yaw = math.atan2(
        context.scenario.board_T_world.rotation.matrix[3],
        context.scenario.board_T_world.rotation.matrix[0],
    )
    nominal_tool = -context.scenario.hand_tcp_to_tip_z_mm
    return (
        abs(study.rear_clamp_contact_x_board_mm - context.scenario.board_T_world.translation_mm.x)
        / 160.0
        + abs(study.rear_edge_to_base_axis_y_mm) / 100.0
        + abs(study.base_yaw_board_rad - nominal_yaw) / math.radians(30.0)
        + abs(study.keyboard_tool_length_mm - nominal_tool) / 40.0
        + abs(study.phone_tool_length_mm - nominal_tool) / 40.0
    )


def _regression_screen(
    context: SimulationContext,
    hypothesis: LayoutHypothesis,
    model: UrdfModel,
    options: IkOptions,
    policy: PrehardwareLayoutStudyPolicy,
    park_probe_id: str,
    park_point: Point3Mm,
    sentinels: tuple[TargetRegion, ...],
    phone_key_a: TargetRegion,
    solver_class: type[Any],
    budget: _SolveBudget,
) -> LayoutRegressionScreen:
    evaluator = _CandidateEvaluator(
        context,
        model,
        hypothesis.study_input,
        options,
        policy.minimum_normalized_arm_joint_margin,
        solver_class,
        budget,
    )
    park = _park_evaluation(evaluator, park_probe_id, park_point)
    named: list[LayoutNamedPoseResult] = []
    key_contact = _contact_point(context, phone_key_a)
    key_approach = _approach_point(context, phone_key_a)
    named.extend(
        (
            LayoutNamedPoseResult(
                "PHONE_KEY_A_CONTACT",
                "phone",
                "key_a",
                "CONTACT",
                key_contact,
                evaluator.screen(
                    hypothesis.study_input.phone_tool_length_mm, key_contact
                ),
            ),
            LayoutNamedPoseResult(
                "PHONE_KEY_A_APPROACH",
                "phone",
                "key_a",
                "APPROACH",
                key_approach,
                evaluator.screen(
                    hypothesis.study_input.phone_tool_length_mm, key_approach
                ),
            ),
        )
    )
    primary_passed = park.all_routes_accepted and all(
        row.feasibility.accepted for row in named
    )
    skipped_roles: tuple[str, ...] = ()
    if primary_passed:
        for target in sentinels:
            point = _contact_point(context, target)
            named.append(
                LayoutNamedPoseResult(
                    f"{target.device.upper()}_SPATIAL_SENTINEL_{target.target_id}",
                    target.device,
                    target.target_id,
                    "CONTACT",
                    point,
                    evaluator.screen(
                        _tool_length(hypothesis.study_input, target.device), point
                    ),
                )
            )
    else:
        skipped_roles = tuple(
            f"{target.device.upper()}_SPATIAL_SENTINEL_{target.target_id}"
            for target in sentinels
        )
    required_named_pose_count = len(sentinels) + 2
    provisional = LayoutRegressionScreen(
        hypothesis,
        park,
        tuple(named),
        required_named_pose_count,
        skipped_roles,
        (),
        evaluator.solve_count,
    )
    device_accepted = {
        device: sum(
            row.feasibility.accepted
            for row in named
            if row.device == device and "SPATIAL_SENTINEL" in row.role
        )
        for device in ("keyboard", "phone")
    }
    ranking_key = (
        0 if provisional.regression_passed else 1,
        -park.accepted_route_count,
        -sum(
            provisional.named(role).feasibility.accepted
            for role in ("PHONE_KEY_A_CONTACT", "PHONE_KEY_A_APPROACH")
        ),
        -min(device_accepted.values()),
        -provisional.accepted_named_pose_count,
        -(
            provisional.minimum_normalized_arm_joint_margin
            if provisional.minimum_normalized_arm_joint_margin is not None
            else -1.0
        ),
        _deviation(context, hypothesis.study_input),
        hypothesis.study_input.study_input_id,
    )
    return LayoutRegressionScreen(
        hypothesis,
        park,
        tuple(named),
        required_named_pose_count,
        skipped_roles,
        ranking_key,
        evaluator.solve_count,
    )


def _full_catalog_screen(
    context: SimulationContext,
    hypothesis: LayoutHypothesis,
    model: UrdfModel,
    options: IkOptions,
    policy: PrehardwareLayoutStudyPolicy,
    park_probe_id: str,
    park_point: Point3Mm,
    targets: tuple[TargetRegion, ...],
    phone_key_a: TargetRegion,
    solver_class: type[Any],
    budget: _SolveBudget,
) -> LayoutFullCatalogScreen:
    evaluator = _CandidateEvaluator(
        context,
        model,
        hypothesis.study_input,
        options,
        policy.minimum_normalized_arm_joint_margin,
        solver_class,
        budget,
    )
    outcomes = tuple(
        ContactPoseResult(
            target.device,
            target.target_id,
            _contact_point(context, target),
            evaluator.screen(
                _tool_length(hypothesis.study_input, target.device),
                _contact_point(context, target),
            ),
        )
        for target in targets
    )
    contacts = FullContactEvaluation(
        hypothesis.study_input, outcomes, evaluator.solve_count
    )
    park = _park_evaluation(evaluator, park_probe_id, park_point)
    approach = evaluator.screen(
        hypothesis.study_input.phone_tool_length_mm,
        _approach_point(context, phone_key_a),
    )
    return LayoutFullCatalogScreen(
        hypothesis,
        contacts,
        park,
        approach,
        evaluator.solve_count,
    )


def _planned_solve_upper_bound(
    policy: PrehardwareLayoutStudyPolicy,
    refinement_count: int,
) -> int:
    # Per regression screen: six spatial sentinels, key_a contact/approach,
    # and two park route tools. Identical target/tool points may be cached, so
    # this is intentionally an upper bound.
    regression_poses = 2 * policy.spatial_sentinels_per_device + 4
    full_poses = _FULL_TARGET_COUNT + 3
    return (
        (policy.coarse_hypothesis_count + refinement_count) * regression_poses
        + policy.full_catalog_candidate_count * full_poses
    )


def _ik_options_dict(options: IkOptions) -> dict[str, int | float]:
    """Serialize every numerical control that can affect an IK result."""

    return {
        name: getattr(options, name)
        for name in (
            "max_attempts",
            "max_iterations_per_attempt",
            "position_tolerance_mm",
            "alignment_tolerance_rad",
            "orientation_weight_mm_per_rad",
            "finite_difference_step_rad",
            "initial_damping",
            "minimum_damping",
            "maximum_damping",
            "max_joint_step_rad",
            "line_search_steps",
        )
    }


def _implementation_provenance(
    solver_class: type[Any], solver_mode: str
) -> tuple[tuple[str, str], ...]:
    hashes = dict(
        _implementation_hashes(
            solver_class,
            GeometricDryRunEngine,
            solver_mode=solver_mode,
        )
    )
    module_hash, _ = _hash_file_bounded(Path(__file__).resolve(), 5_000_000)
    reach_policy_hash, _ = _hash_file_bounded(
        Path(__file__).with_name("reach_optimizer.py").resolve(), 5_000_000
    )
    result = {
        "prehardware_layout_study_module_sha256": module_hash,
        "reach_optimizer_policy_module_sha256": reach_policy_hash,
        "ik_module_sha256": hashes["ik_module_sha256"],
        "active_ik_solver_source_sha256": hashes[
            "active_ik_solver_source_sha256"
        ],
        "rocell_source_tree_sha256": hashes["rocell_source_tree_sha256"],
        "ik_solver_identity": hashes["ik_solver_identity"],
        "solver_mode": solver_mode,
    }
    result["prehardware_layout_implementation_bundle_sha256"] = _stable_hash(
        result
    )
    return tuple(sorted(result.items()))


def _run_prehardware_layout_study_with_solver(
    context: SimulationContext,
    policy: PrehardwareLayoutStudyPolicy | None,
    *,
    solver_class: type[Any],
    solver_mode: str,
    park_optimizer: Callable[[SimulationContext], ParkOptimizationReport],
) -> PrehardwareLayoutStudyReport:
    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    revalidate_simulation_context(context)
    if not context.alignment.all_checks_pass:
        raise PrehardwareLayoutStudyError("canonical placemat alignment must pass")
    selected_policy = policy or default_prehardware_layout_study_policy(context)
    if not isinstance(selected_policy, PrehardwareLayoutStudyPolicy):
        raise TypeError("policy must be a PrehardwareLayoutStudyPolicy")
    scenario = context.scenario
    if (
        scenario.ik_policy.max_attempts > _MAX_CANONICAL_IK_ATTEMPTS
        or scenario.ik_policy.max_iterations_per_attempt
        > _MAX_CANONICAL_IK_ITERATIONS
    ):
        raise PrehardwareLayoutStudyError(
            "canonical IK effort exceeds layout-study caps"
        )
    clamp_lower, clamp_upper = context.scene.arm_clamp_rear_edge_x_range_mm
    if any(
        not clamp_lower <= value <= clamp_upper
        for value in selected_policy.rear_clamp_contact_x.values
    ):
        raise PrehardwareLayoutStudyError(
            "clamp X search leaves the locked RC03 rear-edge zone"
        )
    nominal_yaw = math.atan2(
        scenario.board_T_world.rotation.matrix[3],
        scenario.board_T_world.rotation.matrix[0],
    )
    if any(
        abs(value - nominal_yaw) > _MAX_YAW_SENSITIVITY_DELTA_RAD + 1e-12
        for value in selected_policy.base_yaw_board.values
    ):
        raise PrehardwareLayoutStudyError(
            "yaw leaves the +/-15 degree sensitivity-only envelope"
        )
    try:
        loaded_model = load_pinned_urdf(
            scenario.model_path,
            scenario.model_sha256,
        )
    except PinnedModelLoadError as exc:
        raise PrehardwareLayoutStudyError(
            f"pinned URDF capture failed: {exc}"
        ) from exc
    model = loaded_model.model
    fixed = model.joint("world_to_base_link")
    if (
        fixed.joint_type != "fixed"
        or fixed.parent_link != "world"
        or fixed.child_link != "base_link"
    ):
        raise PrehardwareLayoutStudyError(
            "pinned URDF lost Wv_T_Ru fixed-joint contract"
        )
    vendor_world_T_base_link = fixed.transform_at(None)
    if not math.isclose(
        vendor_world_T_base_link.translation_mm.z, 70.1, abs_tol=1e-9
    ):
        raise PrehardwareLayoutStudyError(
            "pinned Wv_T_Ru Z offset is not 70.1 mm"
        )
    park_report = park_optimizer(context)
    park_candidate = park_report.best_candidate
    if (
        park_candidate is None
        or not park_candidate.all_routes_accepted
        or park_report.actual_ik_solve_count > _MAX_PARK_OPTIMIZER_IK_SOLVES
    ):
        raise PrehardwareLayoutStudyError(
            "Freeze-005 park source did not provide a bounded both-route candidate"
        )
    park_point = park_candidate.geometry.point_board
    park_probe_id = f"freeze005-selected:{park_candidate.geometry.candidate_id}"
    targets = _target_catalog(context)
    phone_key_a_matches = tuple(
        row
        for row in targets
        if row.device == "phone" and row.target_id == "key_a"
    )
    if len(phone_key_a_matches) != 1:
        raise PrehardwareLayoutStudyError(
            "locked target catalog must contain exactly one phone key_a"
        )
    phone_key_a = phone_key_a_matches[0]
    sentinels = _spatial_sentinels(
        targets, selected_policy.spatial_sentinels_per_device
    )
    coarse_options = IkOptions(
        max_attempts=_MAX_COARSE_IK_ATTEMPTS,
        max_iterations_per_attempt=min(
            _MAX_COARSE_IK_ITERATIONS,
            scenario.ik_policy.max_iterations_per_attempt,
        ),
    )
    canonical_options = IkOptions(
        max_attempts=scenario.ik_policy.max_attempts,
        max_iterations_per_attempt=scenario.ik_policy.max_iterations_per_attempt,
    )
    budget = _SolveBudget(selected_policy.maximum_layout_ik_solves)
    coarse_hypotheses = _coarse_hypotheses(
        context, selected_policy, vendor_world_T_base_link
    )
    coarse_screens = tuple(
        _regression_screen(
            context,
            hypothesis,
            model,
            coarse_options,
            selected_policy,
            park_probe_id,
            park_point,
            sentinels,
            phone_key_a,
            solver_class,
            budget,
        )
        for hypothesis in coarse_hypotheses
    )
    anchors = tuple(sorted(coarse_screens, key=lambda row: row.ranking_key))[
        : selected_policy.refinement_anchor_count
    ]
    refinement_hypotheses = _refinement_hypotheses(
        context,
        selected_policy,
        vendor_world_T_base_link,
        anchors,
        {row.study_input.study_input_id for row in coarse_hypotheses},
    )
    planned_upper = _planned_solve_upper_bound(
        selected_policy, len(refinement_hypotheses)
    )
    if planned_upper > selected_policy.maximum_layout_ik_solves:
        raise PrehardwareLayoutStudyError(
            f"planned layout IK upper bound {planned_upper} exceeds policy cap "
            f"{selected_policy.maximum_layout_ik_solves}"
        )
    refinement_screens = tuple(
        _regression_screen(
            context,
            hypothesis,
            model,
            coarse_options,
            selected_policy,
            park_probe_id,
            park_point,
            sentinels,
            phone_key_a,
            solver_class,
            budget,
        )
        for hypothesis in refinement_hypotheses
    )
    all_regression = tuple(
        sorted(
            (*coarse_screens, *refinement_screens),
            key=lambda row: row.ranking_key,
        )
    )
    full_shortlist = tuple(
        row for row in all_regression if row.regression_passed
    )[: selected_policy.full_catalog_candidate_count]
    full_screens = tuple(
        _full_catalog_screen(
            context,
            row.hypothesis,
            model,
            canonical_options,
            selected_policy,
            park_probe_id,
            park_point,
            targets,
            phone_key_a,
            solver_class,
            budget,
        )
        for row in full_shortlist
    )
    eligible = tuple(
        sorted(
            (row for row in full_screens if row.eligible_for_full_route_screen),
            key=lambda row: (
                -(
                    row.minimum_normalized_arm_joint_margin
                    if row.minimum_normalized_arm_joint_margin is not None
                    else -1.0
                ),
                _deviation(context, row.hypothesis.study_input),
                row.hypothesis.study_input.study_input_id,
            ),
        )
    )
    promotions = tuple(
        LayoutCandidatePromotion(rank, row)
        for rank, row in enumerate(eligible, start=1)
    )
    implementation = _implementation_provenance(solver_class, solver_mode)
    source_hashes = context.snapshot.source_hashes
    provenance: tuple[tuple[str, Any], ...] = (
        ("snapshot_hash", context.snapshot.snapshot_hash),
        ("manifest_id", context.snapshot.manifest_id),
        ("manifest_sha256", context.snapshot.manifest_sha256),
        ("simulation_bundle_id", context.bundle_lock.bundle_id),
        ("simulation_bundle_sha256", context.bundle_lock.source_lock_sha256),
        ("scenario_profile_sha256", scenario.source_profile_sha256),
        ("target_profile_sha256", context.targets.content_sha256),
        ("model_sha256", scenario.model_sha256),
        ("captured_model_sha256", loaded_model.sha256),
        ("captured_model_byte_count", loaded_model.byte_count),
        ("captured_model_maximum_bytes", MAX_PINNED_URDF_BYTES),
        ("captured_model_matches_pinned_sha256", True),
        ("alignment_report_hash", context.alignment.report_hash),
        (
            "rc03_workcell_layout_sha256",
            source_hashes.get("config/workcell_layout.json"),
        ),
        (
            "rc03_robot_reach_screening_sha256",
            source_hashes.get("config/robot_reach_screening.json"),
        ),
        ("freeze005_park_source_report_sha256", park_report.report_hash),
        ("rocell_runtime_version", __version__),
        (
            "ik_solver_algorithm_version",
            (
                "DETERMINISTIC_BOUNDED_DLS_V1"
                if solver_class is _CANONICAL_IK_SOLVER
                and solver_mode == "CANONICAL_IN_PACKAGE_IMPLEMENTATION"
                else "EXPLICIT_TEST_DOUBLE"
            ),
        ),
        ("coarse_ik_options", tuple(sorted(_ik_options_dict(coarse_options).items()))),
        (
            "canonical_ik_options",
            tuple(sorted(_ik_options_dict(canonical_options).items())),
        ),
        *implementation,
    )
    return PrehardwareLayoutStudyReport(
        provenance,
        selected_policy,
        park_report.report_hash,
        park_probe_id,
        park_point,
        coarse_screens,
        refinement_screens,
        full_screens,
        promotions,
        planned_upper,
        budget.actual,
        park_report.actual_ik_solve_count,
    )


def run_prehardware_layout_study(
    context: SimulationContext,
    policy: PrehardwareLayoutStudyPolicy | None = None,
) -> PrehardwareLayoutStudyReport:
    """Run the canonical bounded layout sensitivity study without hardware."""

    return _run_prehardware_layout_study_with_solver(
        context,
        policy,
        solver_class=_CANONICAL_IK_SOLVER,
        solver_mode="CANONICAL_IN_PACKAGE_IMPLEMENTATION",
        park_optimizer=_CANONICAL_PARK_OPTIMIZER,
    )


__all__ = [
    "LayoutAxisValueEvidence",
    "LayoutCandidatePromotion",
    "LayoutFullCatalogScreen",
    "LayoutHypothesis",
    "LayoutNamedPoseResult",
    "LayoutRegressionScreen",
    "LayoutSearchAxis",
    "PrehardwareLayoutStudyError",
    "PrehardwareLayoutStudyPolicy",
    "PrehardwareLayoutStudyReport",
    "default_prehardware_layout_study_policy",
    "run_prehardware_layout_study",
]
