"""Bounded joint-space sampling between accepted trajectory waypoints.

This diagnostic boundary expands every accepted joint segment into deterministic
intermediate configurations.  FK and collision poses are then derived by the
ARM-042 adapter, so callers still cannot provide robot-link transforms.

Sampling is not a mathematical swept-volume proof.  Even a clear result retains
the conservative-envelope blocker and creates no controller commands or physical
authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from rocell.kinematics import ARM_JOINT_NAMES

from .context import SimulationContext
from .fk_collision_pose_adapter import (
    MeasuredConfigurationGeometryBinding,
    MeasuredRigidAttachmentBinding,
    derive_and_evaluate_fk_waypoint_collisions,
)
from .installed_collision_geometry import InstalledCollisionGeometryProfile
from .measured_trajectory_screening import SCHEMA as TRAJECTORY_SCREENING_SCHEMA
from rocell.calibration import PlannerCalibrationSnapshot


SCHEMA = "rocell.bounded_segment_collision_qualification.v1"
MAX_BOUNDED_SEGMENT_SAMPLES = 256


class BoundedSegmentCollisionQualificationError(ValueError):
    """Trajectory or sample evidence cannot form one bounded qualification."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _trajectory(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise BoundedSegmentCollisionQualificationError(
            "trajectory_screening must be an object"
        )
    document = dict(value)
    digest = document.pop("trajectory_screening_sha256", None)
    if document.get("schema") != TRAJECTORY_SCREENING_SCHEMA:
        raise BoundedSegmentCollisionQualificationError(
            "trajectory screening schema mismatch"
        )
    if not isinstance(digest, str) or digest != _sha256(document):
        raise BoundedSegmentCollisionQualificationError(
            "trajectory screening hash is invalid"
        )
    return dict(value)


def _joint_map(value: object, label: str) -> dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != set(ARM_JOINT_NAMES):
        raise BoundedSegmentCollisionQualificationError(
            f"{label} must exactly cover arm joints"
        )
    result: dict[str, float] = {}
    for name in ARM_JOINT_NAMES:
        raw = value[name]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise BoundedSegmentCollisionQualificationError(
                f"{label} joint {name} is not numeric"
            )
        number = float(raw)
        if not math.isfinite(number):
            raise BoundedSegmentCollisionQualificationError(
                f"{label} joint {name} is not finite"
            )
        result[name] = number
    return result


@dataclass(frozen=True, slots=True)
class BoundedSegmentSamplingPolicy:
    """Hard limits for deterministic joint interpolation."""

    maximum_joint_step_rad: float = 0.05
    maximum_samples: int = MAX_BOUNDED_SEGMENT_SAMPLES

    def __post_init__(self) -> None:
        if (
            isinstance(self.maximum_joint_step_rad, bool)
            or not isinstance(self.maximum_joint_step_rad, (int, float))
            or not math.isfinite(float(self.maximum_joint_step_rad))
            or not 0.0 < float(self.maximum_joint_step_rad) <= 0.25
        ):
            raise BoundedSegmentCollisionQualificationError(
                "maximum_joint_step_rad must be finite in (0, 0.25]"
            )
        if (
            isinstance(self.maximum_samples, bool)
            or not isinstance(self.maximum_samples, int)
            or not 2 <= self.maximum_samples <= MAX_BOUNDED_SEGMENT_SAMPLES
        ):
            raise BoundedSegmentCollisionQualificationError(
                "maximum_samples must be an integer in [2, 256]"
            )

    @property
    def content_sha256(self) -> str:
        return _sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "maximum_joint_step_rad": float(self.maximum_joint_step_rad),
            "maximum_samples": self.maximum_samples,
        }


@dataclass(frozen=True, slots=True)
class BoundedJointConfigurationSample:
    """One deterministic point on a source joint segment."""

    sample_sequence: int
    source_segment_index: int
    subdivision_index: int
    subdivision_count: int
    interpolation_ratio: float
    joint_positions_rad: Mapping[str, float]

    @property
    def sample_id(self) -> str:
        return f"segment-{self.source_segment_index:04d}-sample-{self.subdivision_index:04d}"

    @property
    def content_sha256(self) -> str:
        return _sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_sequence": self.sample_sequence,
            "sample_id": self.sample_id,
            "source_segment_index": self.source_segment_index,
            "subdivision_index": self.subdivision_index,
            "subdivision_count": self.subdivision_count,
            "interpolation_ratio": self.interpolation_ratio,
            "joint_positions_rad": {
                name: self.joint_positions_rad[name] for name in ARM_JOINT_NAMES
            },
        }


@dataclass(frozen=True, slots=True)
class MeasuredSegmentConfigurationSample:
    """Profile-bound deformable geometry for one generated joint sample."""

    sample_sequence: int
    sample_plan_sha256: str
    geometry_by_body: Mapping[str, MeasuredConfigurationGeometryBinding]

    def __post_init__(self) -> None:
        if (
            isinstance(self.sample_sequence, bool)
            or not isinstance(self.sample_sequence, int)
            or self.sample_sequence < 0
        ):
            raise BoundedSegmentCollisionQualificationError(
                "sample_sequence must be a non-negative integer"
            )
        if (
            not isinstance(self.sample_plan_sha256, str)
            or len(self.sample_plan_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.sample_plan_sha256
            )
        ):
            raise BoundedSegmentCollisionQualificationError(
                "sample_plan_sha256 must be a lowercase SHA-256 digest"
            )
        if not isinstance(self.geometry_by_body, Mapping):
            raise TypeError("geometry_by_body must be a mapping")


def build_bounded_joint_sample_plan(
    trajectory_screening: Mapping[str, Any],
    policy: BoundedSegmentSamplingPolicy | None = None,
) -> tuple[BoundedJointConfigurationSample, ...]:
    """Expand the observed start and accepted IK endpoints into bounded samples."""

    route = _trajectory(trajectory_screening)
    selected = policy or BoundedSegmentSamplingPolicy()
    if not isinstance(selected, BoundedSegmentSamplingPolicy):
        raise TypeError("policy must be BoundedSegmentSamplingPolicy")
    if not route.get("ik_all_waypoints_accepted"):
        raise BoundedSegmentCollisionQualificationError(
            "an all-accepted IK route is required"
        )
    waypoints = route.get("waypoints")
    results = route.get("joint_results")
    if (
        not isinstance(waypoints, list)
        or not isinstance(results, list)
        or not waypoints
        or len(waypoints) != len(results)
    ):
        raise BoundedSegmentCollisionQualificationError(
            "trajectory waypoint collections are incomplete"
        )
    if any(
        not isinstance(waypoint, Mapping) or waypoint.get("sequence") != index
        for index, waypoint in enumerate(waypoints)
    ):
        raise BoundedSegmentCollisionQualificationError(
            "trajectory waypoints are not canonically ordered"
        )
    previous = _joint_map(
        route.get("observed_start_joint_positions_rad"), "observed start"
    )
    return build_bounded_joint_sample_plan_from_results(
        previous,
        results,
        selected,
    )


def build_bounded_joint_sample_plan_from_results(
    start_joint_positions_rad: Mapping[str, float],
    joint_results: Sequence[Mapping[str, Any]],
    policy: BoundedSegmentSamplingPolicy | None = None,
) -> tuple[BoundedJointConfigurationSample, ...]:
    """Expand one explicitly classified start state and canonical IK results.

    This schema-neutral helper lets offline-only producers reuse the exact same
    interpolation and resource limits without claiming their start state was
    measured controller feedback.  Authority-bearing callers remain responsible
    for proving the provenance required by their own boundary.
    """

    selected = policy or BoundedSegmentSamplingPolicy()
    if not isinstance(selected, BoundedSegmentSamplingPolicy):
        raise TypeError("policy must be BoundedSegmentSamplingPolicy")
    previous = _joint_map(start_joint_positions_rad, "start state")
    try:
        iterator = iter(joint_results)
    except TypeError as exc:
        raise TypeError("joint_results must be a finite sequence") from exc
    bounded_results: list[Mapping[str, Any]] = []
    for _ in range(selected.maximum_samples + 1):
        try:
            bounded_results.append(next(iterator))
        except StopIteration:
            break
    results = tuple(bounded_results)
    if not results:
        raise BoundedSegmentCollisionQualificationError(
            "at least one accepted joint result is required"
        )
    if len(results) > selected.maximum_samples:
        raise BoundedSegmentCollisionQualificationError(
            "joint result count exceeds policy maximum"
        )
    samples: list[BoundedJointConfigurationSample] = []
    for segment_index, result in enumerate(results):
        if (
            not isinstance(result, Mapping)
            or result.get("waypoint_sequence") != segment_index
            or result.get("accepted") is not True
        ):
            raise BoundedSegmentCollisionQualificationError(
                f"segment {segment_index} endpoint is not an accepted canonical result"
            )
        endpoint = _joint_map(
            result.get("solution_arm_joint_positions_rad"),
            f"segment {segment_index} endpoint",
        )
        maximum_delta = max(
            abs(endpoint[name] - previous[name]) for name in ARM_JOINT_NAMES
        )
        subdivision_count = max(
            1, math.ceil(maximum_delta / float(selected.maximum_joint_step_rad))
        )
        first_subdivision = 0 if segment_index == 0 else 1
        for subdivision_index in range(first_subdivision, subdivision_count + 1):
            ratio = subdivision_index / subdivision_count
            joints = {
                name: previous[name] + ratio * (endpoint[name] - previous[name])
                for name in ARM_JOINT_NAMES
            }
            samples.append(
                BoundedJointConfigurationSample(
                    len(samples),
                    segment_index,
                    subdivision_index,
                    subdivision_count,
                    ratio,
                    joints,
                )
            )
            if len(samples) > selected.maximum_samples:
                raise BoundedSegmentCollisionQualificationError(
                    "bounded segment sample count exceeds policy maximum"
                )
        previous = endpoint
    return tuple(samples)


def qualify_bounded_segment_collisions(
    context: SimulationContext,
    snapshot: PlannerCalibrationSnapshot,
    installed_profile: InstalledCollisionGeometryProfile,
    trajectory_screening: Mapping[str, Any],
    attachment_bindings: Sequence[MeasuredRigidAttachmentBinding],
    configuration_samples: Sequence[MeasuredSegmentConfigurationSample],
    *,
    policy: BoundedSegmentSamplingPolicy | None = None,
) -> dict[str, Any]:
    """Evaluate FK-derived full-body geometry at every bounded segment sample."""

    selected = policy or BoundedSegmentSamplingPolicy()
    plan = build_bounded_joint_sample_plan(trajectory_screening, selected)
    try:
        supplied = tuple(configuration_samples)
    except TypeError as exc:
        raise TypeError("configuration_samples must be a finite sequence") from exc
    if len(supplied) != len(plan):
        raise BoundedSegmentCollisionQualificationError(
            "configuration geometry must cover every bounded joint sample"
        )
    geometry: list[Mapping[str, MeasuredConfigurationGeometryBinding]] = []
    for expected, evidence in zip(plan, supplied, strict=True):
        if not isinstance(evidence, MeasuredSegmentConfigurationSample):
            raise TypeError(
                "configuration_samples must contain MeasuredSegmentConfigurationSample values"
            )
        if (
            evidence.sample_sequence != expected.sample_sequence
            or evidence.sample_plan_sha256 != expected.content_sha256
        ):
            raise BoundedSegmentCollisionQualificationError(
                f"configuration sample {expected.sample_sequence} does not bind its joint sample"
            )
        geometry.append(evidence.geometry_by_body)

    source = _trajectory(trajectory_screening)
    expanded_waypoints: list[dict[str, Any]] = []
    expanded_results: list[dict[str, Any]] = []
    for item in plan:
        expanded_waypoints.append(
            {
                "sequence": item.sample_sequence,
                "sample_id": item.sample_id,
                "source_segment_index": item.source_segment_index,
                "subdivision_index": item.subdivision_index,
                "subdivision_count": item.subdivision_count,
                "interpolation_ratio": item.interpolation_ratio,
            }
        )
        expanded_results.append(
            {
                "waypoint_sequence": item.sample_sequence,
                "accepted": True,
                "solution_arm_joint_positions_rad": dict(item.joint_positions_rad),
            }
        )
    expanded = {
        "schema": TRAJECTORY_SCREENING_SCHEMA,
        "calibration_snapshot_sha256": source["calibration_snapshot_sha256"],
        "build_snapshot_sha256": source["build_snapshot_sha256"],
        "kinematic_model_sha256": source["kinematic_model_sha256"],
        "installed_collision_profile_sha256": source[
            "installed_collision_profile_sha256"
        ],
        "collision_contract_sha256": source["collision_contract_sha256"],
        "ik_all_waypoints_accepted": True,
        "waypoints": expanded_waypoints,
        "joint_results": expanded_results,
        "source_trajectory_screening_sha256": source["trajectory_screening_sha256"],
        "bounded_segment_sampling_policy_sha256": selected.content_sha256,
    }
    expanded = {
        **expanded,
        "trajectory_screening_sha256": _sha256(expanded),
    }
    fk_report = derive_and_evaluate_fk_waypoint_collisions(
        context,
        snapshot,
        installed_profile,
        expanded,
        attachment_bindings,
        tuple(geometry),
    )
    nested_status = fk_report["status"]
    if nested_status == "DISCRETE_WAYPOINTS_CLEAR_CONTINUOUS_PROOF_REQUIRED":
        status = "BOUNDED_SEGMENT_SAMPLES_CLEAR_CONSERVATIVE_SWEEP_REQUIRED"
        blockers = ["CONSERVATIVE_INTER_SAMPLE_SWEEP_PROOF_REQUIRED"]
        next_stage = "QUALIFY_CONSERVATIVE_SWEPT_VOLUME_BETWEEN_BOUNDED_SAMPLES"
    elif nested_status == "BLOCKED_COLLISION_DETECTED":
        status = "BLOCKED_COLLISION_DETECTED_AT_BOUNDED_SAMPLE"
        blockers = ["COLLISION_DETECTED_AT_BOUNDED_SEGMENT_SAMPLE"]
        next_stage = "CORRECT_ROUTE_OR_INSTALLED_GEOMETRY"
    else:
        status = "BLOCKED_INCOMPLETE_BOUNDED_SEGMENT_EVIDENCE"
        blockers = ["INCOMPLETE_BOUNDED_SEGMENT_COLLISION_EVIDENCE"]
        next_stage = "SUPPLY_COMPLETE_PROFILE_BOUND_SAMPLE_GEOMETRY"

    maximum_gap = 0.0
    for left, right in zip(plan, plan[1:]):
        maximum_gap = max(
            maximum_gap,
            max(
                abs(right.joint_positions_rad[name] - left.joint_positions_rad[name])
                for name in ARM_JOINT_NAMES
            ),
        )
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "source_trajectory_screening_sha256": source["trajectory_screening_sha256"],
        "expanded_trajectory_screening_sha256": expanded["trajectory_screening_sha256"],
        "installed_collision_profile_sha256": installed_profile.content_sha256,
        "sampling_policy": {
            **selected.to_dict(),
            "sampling_policy_sha256": selected.content_sha256,
        },
        "sample_count": len(plan),
        "maximum_observed_joint_gap_rad": maximum_gap,
        "sample_plan": [item.to_dict() for item in plan],
        "fk_collision_qualification": fk_report,
        "all_bounded_samples_collision_free": status.startswith(
            "BOUNDED_SEGMENT_SAMPLES_CLEAR"
        ),
        "continuous_collision_proven": False,
        "blockers": blockers,
        "next_required_stage": next_stage,
        "controller_commands": [],
        "hardware_commands_generated": 0,
        "hardware_access": False,
        "physical_authority": False,
    }
    return {**report, "bounded_segment_qualification_sha256": _sha256(report)}
