"""Bind one fresh static-B0477 rehearsal to every physical contact hover.

The overhead camera is static, so its board pose is independent of arm angle.
The arm still has to reach and settle at the final HOVER waypoint before a
frame is useful: that makes the observation's target association, achieved
controller pose, and route ordinal part of the evidence.  This module records
that association without claiming a physical capture or measured calibration.

``rehearse_b0477_mission_observations`` generates fresh synthetic pixel reports
for hardware-free testing.  ``bind_b0477_mission_observations`` is the narrower
adapter that will later accept independently recorded report objects while
retaining the same ordering and hash checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
from typing import Sequence

from rocell.motion import MotionPhase
from rocell.simulation.t104_runtime import controller_pose_sha256

from .b0477_static_vision import (
    B0477StaticVisionMode,
    B0477StaticVisionReport,
    MAX_B0477_REHEARSAL_SEQUENCE,
    run_b0477_static_vision_rehearsal,
)
from .dense_route_schedule import DenseRouteSchedule
from .semantic_step_schedule import SemanticStepSchedule


B0477_MISSION_OBSERVATION_SCHEMA = (
    "rocell.zero_authority.b0477_mission_observation.v1"
)
B0477_MISSION_OBSERVATION_SET_SCHEMA = (
    "rocell.zero_authority.b0477_mission_observation_set.v1"
)
MAX_MISSION_OBSERVATIONS = 512
MAX_OBSERVATION_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_OBSERVATION_SET_BYTES = 64 * 1024 * 1024

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_PER_CAPTURE_DERIVED_SOURCE_KEYS = frozenset(
    {
        "detected_batch",
        "fit_detection_batch",
        "pose_observation",
        "raw_detected_batch",
        "rectified_detection_batch",
    }
)


class B0477MissionObservationError(ValueError):
    """A camera report is stale, rejected, or bound to the wrong mission row."""


def _canonical_bytes(value: object, maximum: int) -> bytes:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise B0477MissionObservationError("value is not canonical JSON") from exc
    if len(encoded) > maximum:
        raise B0477MissionObservationError("observation evidence exceeds its byte limit")
    return encoded


def _hash(value: object, maximum: int) -> str:
    return hashlib.sha256(_canonical_bytes(value, maximum)).hexdigest()


def _digest(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise B0477MissionObservationError(
            f"{label} must be an exact lowercase SHA-256 digest"
        )
    return value


def _identifier(value: object, label: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise B0477MissionObservationError(f"{label} must be a bounded identifier")
    return value


def _ordinal(value: object, label: str, *, maximum: int = 65_536) -> int:
    if isinstance(value, bool) or type(value) is not int or not 0 <= value < maximum:
        raise B0477MissionObservationError(
            f"{label} must be a bounded nonnegative integer"
        )
    return value


def _authority() -> dict[str, object]:
    return {
        "simulation_only": True,
        "synthetic_pixels": True,
        "physical_camera_accessed": False,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "live_capture_authority": False,
        "physical_calibration_authority": False,
        "robot_motion_authority": False,
        "contact_authority": False,
        "physical_release_effect": "NONE",
    }


@dataclass(frozen=True, slots=True)
class B0477MissionObservation:
    """One accepted synthetic frame tied to the final hover for one contact."""

    source_plan_sha256: str
    semantic_schedule_sha256: str
    dense_route_schedule_sha256: str
    trajectory_report_sha256: str
    semantic_step_ordinal: int
    contact_occurrence_ordinal: int
    target_id: str
    route_waypoint_ordinal: int
    authorization_command_ordinal: int
    expected_settled_controller_pose_sha256: str
    report: B0477StaticVisionReport
    observation_id: str
    schema: str = B0477_MISSION_OBSERVATION_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(
            self,
            "_sealed_sha256",
            _hash(self._document(), MAX_OBSERVATION_DOCUMENT_BYTES),
        )

    @property
    def camera_sequence(self) -> int:
        return self.report.sequence

    @property
    def report_sha256(self) -> str:
        return self.report.content_sha256

    @property
    def observation_sha256(self) -> str:
        self.validate()
        return self._sealed_sha256

    @property
    def expected_observation_id(self) -> str:
        core = {
            "source_plan_sha256": self.source_plan_sha256,
            "contact_occurrence_ordinal": self.contact_occurrence_ordinal,
            "target_id": self.target_id,
            "route_waypoint_ordinal": self.route_waypoint_ordinal,
            "report_sha256": self.report.content_sha256,
        }
        return f"b0477-observation-{_hash(core, 64 * 1024)[:24]}"

    def _validate_unsealed(self) -> None:
        if self.schema != B0477_MISSION_OBSERVATION_SCHEMA:
            raise B0477MissionObservationError("unsupported mission observation schema")
        for name in (
            "source_plan_sha256",
            "semantic_schedule_sha256",
            "dense_route_schedule_sha256",
            "trajectory_report_sha256",
            "expected_settled_controller_pose_sha256",
        ):
            _digest(getattr(self, name), name)
        _ordinal(self.semantic_step_ordinal, "semantic_step_ordinal", maximum=512)
        _ordinal(
            self.contact_occurrence_ordinal,
            "contact_occurrence_ordinal",
            maximum=MAX_MISSION_OBSERVATIONS,
        )
        route = _ordinal(self.route_waypoint_ordinal, "route_waypoint_ordinal")
        authorization = _ordinal(
            self.authorization_command_ordinal,
            "authorization_command_ordinal",
        )
        if route == 0 or authorization != route - 1:
            raise B0477MissionObservationError(
                "camera authorization ordinal must bind the final-hover route ordinal"
            )
        _identifier(self.target_id, "target_id")
        _identifier(self.observation_id, "observation_id")
        if type(self.report) is not B0477StaticVisionReport:
            raise TypeError("report must be exactly B0477StaticVisionReport")
        # Re-run the report's structural validation and policy, including its
        # six-tag pixel-derived pose and held-out K0/P0 station checks.
        self.report.__post_init__()
        if (
            self.report.mode is not B0477StaticVisionMode.NORMAL
            or self.report.status != "PASS"
            or not self.report.passes_nominal_policy
        ):
            raise B0477MissionObservationError(
                "mission observation needs a passing NORMAL B0477 rehearsal"
            )
        if self.observation_id != self.expected_observation_id:
            raise B0477MissionObservationError(
                "observation_id does not bind target, hover, and report"
            )

    def _document(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            **_authority(),
            "observation_id": self.observation_id,
            "source_plan_sha256": self.source_plan_sha256,
            "semantic_schedule_sha256": self.semantic_schedule_sha256,
            "dense_route_schedule_sha256": self.dense_route_schedule_sha256,
            "trajectory_report_sha256": self.trajectory_report_sha256,
            "semantic_step_ordinal": self.semantic_step_ordinal,
            "contact_occurrence_ordinal": self.contact_occurrence_ordinal,
            "target_id": self.target_id,
            "capture_boundary": "AFTER_FINAL_HOVER_SETTLED_BEFORE_APPROACH",
            "route_waypoint_ordinal": self.route_waypoint_ordinal,
            "authorization_command_ordinal": self.authorization_command_ordinal,
            "expected_settled_controller_pose_sha256": (
                self.expected_settled_controller_pose_sha256
            ),
            "camera_sequence": self.report.sequence,
            "b0477_report_sha256": self.report.content_sha256,
            "b0477_report": self.report.to_dict(),
        }

    def validate(self) -> None:
        self._validate_unsealed()
        if _hash(self._document(), MAX_OBSERVATION_DOCUMENT_BYTES) != self._sealed_sha256:
            raise B0477MissionObservationError("mission observation changed after construction")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return self._document()


@dataclass(frozen=True, slots=True)
class B0477MissionObservationSet:
    """Complete, contact-ordered observation set for one dense mission."""

    source_plan_sha256: str
    semantic_schedule_sha256: str
    dense_route_schedule_sha256: str
    trajectory_report_sha256: str
    observations: tuple[B0477MissionObservation, ...]
    schema: str = B0477_MISSION_OBSERVATION_SET_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(
            self,
            "_sealed_sha256",
            _hash(self._document(), MAX_OBSERVATION_SET_BYTES),
        )

    @property
    def observation_count(self) -> int:
        return len(self.observations)

    @property
    def canonical_sha256(self) -> str:
        self.validate()
        return self._sealed_sha256

    def _validate_unsealed(self) -> None:
        if self.schema != B0477_MISSION_OBSERVATION_SET_SCHEMA:
            raise B0477MissionObservationError("unsupported observation-set schema")
        for name in (
            "source_plan_sha256",
            "semantic_schedule_sha256",
            "dense_route_schedule_sha256",
            "trajectory_report_sha256",
        ):
            _digest(getattr(self, name), name)
        if type(self.observations) is not tuple:
            raise TypeError("observations must be an immutable tuple")
        observations = self.observations
        if not 1 <= len(observations) <= MAX_MISSION_OBSERVATIONS:
            raise B0477MissionObservationError(
                "observation count is outside the contact bound"
            )
        if any(type(item) is not B0477MissionObservation for item in observations):
            raise TypeError("observations must contain B0477MissionObservation")
        for item in observations:
            item.validate()
            if (
                item.source_plan_sha256 != self.source_plan_sha256
                or item.semantic_schedule_sha256 != self.semantic_schedule_sha256
                or item.dense_route_schedule_sha256 != self.dense_route_schedule_sha256
                or item.trajectory_report_sha256 != self.trajectory_report_sha256
            ):
                raise B0477MissionObservationError(
                    "observation source hashes differ from the aggregate"
                )
        if tuple(item.contact_occurrence_ordinal for item in observations) != tuple(
            range(len(observations))
        ):
            raise B0477MissionObservationError(
                "observations must use dense contact-occurrence order"
            )
        sequences = tuple(item.camera_sequence for item in observations)
        if any(right <= left for left, right in zip(sequences, sequences[1:])):
            raise B0477MissionObservationError(
                "camera sequences must increase strictly for fresh observations"
            )
        report_hashes = tuple(item.report_sha256 for item in observations)
        if len(set(report_hashes)) != len(report_hashes):
            raise B0477MissionObservationError("a B0477 report was replayed")
        # Detection/pose record hashes correctly change with the fresh frame
        # sequence.  Everything that defines the camera, optics, detector,
        # rectifier, renderer, tag map, scene, and support must stay identical.
        source_sets = tuple(
            tuple(
                pair
                for pair in item.report.source_hashes
                if pair[0] not in _PER_CAPTURE_DERIVED_SOURCE_KEYS
            )
            for item in observations
        )
        if any(value != source_sets[0] for value in source_sets[1:]):
            raise B0477MissionObservationError("B0477 source identity drifted mid-mission")
        identities = tuple(
            (item.report.profile_id, item.report.support_design_id)
            for item in observations
        )
        if any(value != identities[0] for value in identities[1:]):
            raise B0477MissionObservationError("B0477 profile/support identity drifted")

    def _document(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            **_authority(),
            "source_plan_sha256": self.source_plan_sha256,
            "semantic_schedule_sha256": self.semantic_schedule_sha256,
            "dense_route_schedule_sha256": self.dense_route_schedule_sha256,
            "trajectory_report_sha256": self.trajectory_report_sha256,
            "freshness_contract": "STRICTLY_INCREASING_UNIQUE_REPORTS_ONE_PER_CONTACT",
            "observations": [item.to_dict() for item in self.observations],
        }

    def validate(self) -> None:
        self._validate_unsealed()
        if _hash(self._document(), MAX_OBSERVATION_SET_BYTES) != self._sealed_sha256:
            raise B0477MissionObservationError("observation set changed after construction")

    def assert_matches_schedules(
        self,
        semantic_schedule: SemanticStepSchedule,
        dense_route_schedule: DenseRouteSchedule,
    ) -> None:
        """Prove every observation belongs to its exact semantic/route slice."""

        self.validate()
        if type(semantic_schedule) is not SemanticStepSchedule:
            raise TypeError("semantic_schedule must be exactly SemanticStepSchedule")
        semantic_schedule.validate()
        if type(dense_route_schedule) is not DenseRouteSchedule:
            raise TypeError("dense_route_schedule must be exactly DenseRouteSchedule")
        dense_route_schedule.validate()
        if (
            self.source_plan_sha256 != semantic_schedule.source_plan_sha256
            or self.semantic_schedule_sha256 != semantic_schedule.canonical_sha256
            or self.source_plan_sha256 != dense_route_schedule.source_plan_sha256
            or self.dense_route_schedule_sha256
            != dense_route_schedule.canonical_sha256
            or self.trajectory_report_sha256
            != dense_route_schedule.trajectory_report_sha256
        ):
            raise B0477MissionObservationError(
                "observation set source hashes differ from the selected schedules"
            )
        slices = dense_route_schedule.contact_slices
        if len(self.observations) != len(slices):
            raise B0477MissionObservationError(
                "observation count differs from dense contact slices"
            )
        by_route = {
            item.route_waypoint_ordinal: item
            for item in dense_route_schedule.commands
        }
        for observation, slice_ in zip(self.observations, slices):
            hover = by_route.get(slice_.final_hover_route_waypoint_ordinal)
            if hover is None:
                raise B0477MissionObservationError(
                    "contact slice final hover is absent from the dense route"
                )
            if (
                observation.semantic_step_ordinal
                != slice_.semantic_step_ordinal
                or observation.contact_occurrence_ordinal
                != slice_.contact_occurrence_ordinal
                or observation.target_id != slice_.target_id
                or observation.route_waypoint_ordinal
                != slice_.final_hover_route_waypoint_ordinal
                or observation.authorization_command_ordinal
                != hover.authorization_command_ordinal
                or hover.phase is not MotionPhase.HOVER
                or not hover.phase_endpoint
                or hover.mission_tail
                or observation.expected_settled_controller_pose_sha256
                != controller_pose_sha256(hover.command.target.pose)
            ):
                raise B0477MissionObservationError(
                    "camera observation differs from its exact contact/final-hover slice"
                )

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return self._document()


def bind_b0477_mission_observations(
    *,
    semantic_schedule: SemanticStepSchedule,
    dense_route_schedule: DenseRouteSchedule,
    reports: Sequence[B0477StaticVisionReport],
) -> B0477MissionObservationSet:
    """Bind existing reports to exact final-hover rows in contact order."""

    if type(semantic_schedule) is not SemanticStepSchedule:
        raise TypeError("semantic_schedule must be exactly SemanticStepSchedule")
    semantic_schedule.validate()
    if type(dense_route_schedule) is not DenseRouteSchedule:
        raise TypeError("dense_route_schedule must be exactly DenseRouteSchedule")
    dense_route_schedule.validate()
    if semantic_schedule.source_plan_sha256 != dense_route_schedule.source_plan_sha256:
        raise B0477MissionObservationError("semantic and dense route plans differ")
    if semantic_schedule.canonical_sha256 != dense_route_schedule.semantic_schedule_sha256:
        raise B0477MissionObservationError("semantic schedule hash differs from route")
    if isinstance(reports, (str, bytes)) or not isinstance(reports, Sequence):
        raise TypeError("reports must be a sequence")
    if len(reports) != len(dense_route_schedule.contact_slices):
        raise B0477MissionObservationError("exactly one report is required per contact")
    by_route = {
        item.route_waypoint_ordinal: item for item in dense_route_schedule.commands
    }
    observations: list[B0477MissionObservation] = []
    for slice_, report in zip(dense_route_schedule.contact_slices, reports):
        if type(report) is not B0477StaticVisionReport:
            raise TypeError("reports must contain B0477StaticVisionReport")
        hover = by_route[slice_.final_hover_route_waypoint_ordinal]
        if not (
            hover.phase is MotionPhase.HOVER
            and hover.phase_endpoint
            and not hover.mission_tail
            and hover.contact_occurrence_ordinal == slice_.contact_occurrence_ordinal
        ):
            raise B0477MissionObservationError("contact slice does not select a final hover")
        observation_id = "b0477-observation-" + _hash(
            {
                "source_plan_sha256": semantic_schedule.source_plan_sha256,
                "contact_occurrence_ordinal": slice_.contact_occurrence_ordinal,
                "target_id": slice_.target_id,
                "route_waypoint_ordinal": hover.route_waypoint_ordinal,
                "report_sha256": report.content_sha256,
            },
            64 * 1024,
        )[:24]
        observations.append(
            B0477MissionObservation(
                source_plan_sha256=semantic_schedule.source_plan_sha256,
                semantic_schedule_sha256=semantic_schedule.canonical_sha256,
                dense_route_schedule_sha256=dense_route_schedule.canonical_sha256,
                trajectory_report_sha256=dense_route_schedule.trajectory_report_sha256,
                semantic_step_ordinal=slice_.semantic_step_ordinal,
                contact_occurrence_ordinal=slice_.contact_occurrence_ordinal,
                target_id=slice_.target_id,
                route_waypoint_ordinal=hover.route_waypoint_ordinal,
                authorization_command_ordinal=hover.authorization_command_ordinal,
                expected_settled_controller_pose_sha256=(
                    controller_pose_sha256(hover.command.target.pose)
                ),
                report=report,
                observation_id=observation_id,
            )
        )
    result = B0477MissionObservationSet(
        source_plan_sha256=semantic_schedule.source_plan_sha256,
        semantic_schedule_sha256=semantic_schedule.canonical_sha256,
        dense_route_schedule_sha256=dense_route_schedule.canonical_sha256,
        trajectory_report_sha256=dense_route_schedule.trajectory_report_sha256,
        observations=tuple(observations),
    )
    result.assert_matches_schedules(semantic_schedule, dense_route_schedule)
    return result


def rehearse_b0477_mission_observations(
    workspace_root: Path,
    *,
    semantic_schedule: SemanticStepSchedule,
    dense_route_schedule: DenseRouteSchedule,
    starting_sequence: int = 1,
) -> B0477MissionObservationSet:
    """Generate one new NORMAL synthetic pixel report per physical contact."""

    start = _ordinal(
        starting_sequence,
        "starting_sequence",
        maximum=MAX_B0477_REHEARSAL_SEQUENCE,
    )
    contact_count = len(dense_route_schedule.contact_slices)
    if start > MAX_B0477_REHEARSAL_SEQUENCE - (contact_count - 1):
        raise B0477MissionObservationError(
            "starting_sequence lacks headroom for every mission observation"
        )
    reports = tuple(
        run_b0477_static_vision_rehearsal(
            Path(workspace_root),
            sequence=start + offset,
            mode=B0477StaticVisionMode.NORMAL,
        )
        for offset in range(contact_count)
    )
    return bind_b0477_mission_observations(
        semantic_schedule=semantic_schedule,
        dense_route_schedule=dense_route_schedule,
        reports=reports,
    )


__all__ = [
    "B0477_MISSION_OBSERVATION_SCHEMA",
    "B0477_MISSION_OBSERVATION_SET_SCHEMA",
    "B0477MissionObservation",
    "B0477MissionObservationError",
    "B0477MissionObservationSet",
    "bind_b0477_mission_observations",
    "rehearse_b0477_mission_observations",
]
