"""End-to-end keyboard/Android mission through only zero-hardware components.

This is the highest-fidelity executable path available before the RoArm and
B0477 arrive.  It performs real application initialization and plan/geometry
compilation, then joins the accepted dense route to synthetic pixel evidence,
full endpoint/midpoint collision queries, authorization-v2, crash-safe contact
journals, the non-wire T104 runtime, geometry-resolved virtual contacts, and an
independent output observer.

Nothing in this module opens a camera, serial port, socket, or physical device.
The collision geometry adapter is explicitly an isolated software-binding
fixture, and calibration artifacts remain ``NOMINAL_ONLY``.  The final report
therefore proves software integration and fail-closed sequencing—not physical
readiness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Sequence, cast

from rocell.motion import MotionPhase
from rocell.simulation.b0477_replay_camera import (
    B0477ReplayCameraPort,
    B0477ReplayCaptureError,
    B0477ReplayFaultInjection,
    B0477ReplayFaultReceipt,
)
from rocell.safety.authorization_v2 import (
    SimulationCommandReceipt,
    canonical_record_sha256,
    issue_ordered_simulation_permit,
)
from rocell.safety.synthetic_authorization import (
    SYNTHETIC_INTERLOCK_MAX_AGE_S,
    SYNTHETIC_ISSUANCE_MONOTONIC,
    SYNTHETIC_PERMIT_TTL_S,
    SyntheticInterlockContinuity,
)
from rocell.simulation.static_mission_fixture import (
    build_isolated_static_mission_fixture,
)
from rocell.simulation.t104_runtime import (
    InMemoryT104Runtime,
    T104FaultInjection,
    T104RuntimeStateReceipt,
    T104TraceReceipt,
)
from rocell.simulation.virtual_outcome import VirtualTextOutcomeObserver
from rocell.simulation.virtual_profile import (
    VirtualProfileContext,
    load_virtual_commissioning_profile,
)
from rocell.simulation.virtual_workcell import (
    ContactEvent,
    VirtualAndroid,
    VirtualKeyboard,
)
from rocell.typing.development_profiles import compile_development_text
from rocell.typing.unicode_support import normalize_line_endings

from .b0477_mission_observations import (
    rehearse_b0477_mission_observations,
)
from .bootstrap import bootstrap_virtual_workcell
from .dense_route_schedule import build_dense_route_schedule
from .mission_journal import (
    ActionOccurrence,
    ActionJournalState,
    MISSION_JOURNAL_HEADER_SCHEMA,
    MISSION_JOURNAL_HIGH_WATER_SCHEMA,
    MissionJournalEvent,
    MissionJournalSnapshot,
    ZeroAuthorityMissionJournal,
)
from .multi_action_mission_v2 import (
    DeviceSafetyContext,
    MissionV2CommandBinding,
    MultiActionMissionSpecV2,
    assemble_zero_hardware_mission_v2,
)
from .semantic_step_schedule import (
    ContactSemanticStep,
    PhoneStateObservationStep,
    build_semantic_step_schedule,
)
from .trajectory_simulation import (
    TrajectorySimulationPolicy,
    run_trajectory_simulation,
)
from .virtual_session import (
    VIRTUAL_CONTACT_DWELL_TICKS,
    build_virtual_device_model,
)


INTEGRATED_ZERO_HARDWARE_REPORT_SCHEMA = (
    "rocell.integrated_zero_hardware_mission_report.v1"
)
INTEGRATED_COMMAND_RECEIPT_SCHEMA = (
    "rocell.integrated_zero_hardware_command_receipt.v1"
)
INTEGRATED_CONTACT_RECEIPT_SCHEMA = (
    "rocell.integrated_zero_hardware_contact_receipt.v1"
)
INTEGRATED_FAULT_RECEIPT_SCHEMA = (
    "rocell.integrated_zero_hardware_fault_receipt.v1"
)
INTEGRATED_STATE_OBSERVATION_SCHEMA = (
    "rocell.integrated_zero_hardware_state_observation.v1"
)
INTEGRATED_JOURNAL_SET_SCHEMA = "rocell.integrated_mission_journal_set.v1"
INTEGRATED_JOURNAL_SET_FILENAME = "mission-v2.json"
MAX_INTEGRATED_REPORT_BYTES = 64 * 1024 * 1024
MAX_INTEGRATED_TEXT_LENGTH = 1024
_ZERO_SHA256 = "0" * 64
_T104_FAULT_KINDS = frozenset(
    {"STALL", "RESET", "DISCONNECT", "TIMEOUT", "NONSETTLE"}
)
_CAMERA_FAULT_KINDS = frozenset(
    {"CAPTURE_FAILURE", "TIMEOUT", "STALE_FRAME"}
)
_FAULT_SOURCE_RUNTIME = "InMemoryT104Runtime"
_FAULT_SOURCE_OBSERVATION_BOUNDARY = "SettledHoverObservationBoundary"
_FAULT_SOURCE_COORDINATOR = "IntegratedZeroHardwareMissionCoordinator"
_OBSERVATION_BOUNDARY_STAGE = "SETTLED_HOVER_OBSERVATION"
_OBSERVATION_BOUNDARY_FAULT_KIND = "OBSERVATION_BOUNDARY_FAILURE"
_COORDINATOR_FAULT_KIND = "COORDINATOR_FAILURE"
_COORDINATOR_FAULT_STAGES = frozenset(
    {
        "SEMANTIC_OBSERVATION",
        "CONTACT_JOURNAL_BOUNDARY",
        "PRE_COMMAND_FAILURE",
        "CONTACT_POST_COMMAND",
        "RETRACTION_COMMIT",
        "MISSION_FINALIZATION",
    }
)
_COMPLETE_STATUS = "ZERO_HARDWARE_MISSION_V2_COMPLETE_WITH_PHYSICAL_HOLDS"
_FAULTED_STATUS = "ZERO_HARDWARE_MISSION_V2_FAULTED_CLOSED"


class IntegratedZeroHardwareMissionError(RuntimeError):
    """The end-to-end rehearsal could not produce trustworthy evidence."""


class _MissionAbort(RuntimeError):
    pass


def _canonical_bytes(value: object, maximum: int = MAX_INTEGRATED_REPORT_BYTES) -> bytes:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise IntegratedZeroHardwareMissionError(
            "integrated evidence is not canonical JSON"
        ) from exc
    if len(encoded) > maximum:
        raise IntegratedZeroHardwareMissionError(
            "integrated evidence exceeds its byte limit"
        )
    return encoded


def _hash(value: object, maximum: int = MAX_INTEGRATED_REPORT_BYTES) -> str:
    return hashlib.sha256(_canonical_bytes(value, maximum)).hexdigest()


def _digest(value: object, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise IntegratedZeroHardwareMissionError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _ordinal(value: object, label: str, *, maximum: int = 65_535) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise IntegratedZeroHardwareMissionError(
            f"{label} must be a bounded nonnegative integer"
        )
    return value


def _bounded_text(value: object, label: str) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= MAX_INTEGRATED_TEXT_LENGTH
        or value != value.strip()
        or "\r" in value
        or "\n" in value
    ):
        raise IntegratedZeroHardwareMissionError(
            f"{label} must be bounded, trimmed single-line text"
        )
    return value


def _authority() -> dict[str, object]:
    return {
        "simulation_only": True,
        "physical_authority": "ZERO",
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "wire_messages_generated": 0,
        "power_authorized": False,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "can_release_physical_gates": False,
        "physical_release_effect": "NONE",
    }


def _journal_id_for_occurrence_hash(occurrence_sha256: str) -> str:
    return f"journal-{occurrence_sha256[:24]}"


def _journal_set_document(assembly: MultiActionMissionSpecV2) -> dict[str, object]:
    """Bind a durable journal directory to one exact immutable assembly."""

    core: dict[str, object] = {
        "schema": INTEGRATED_JOURNAL_SET_SCHEMA,
        **_authority(),
        "assembly_sha256": assembly.assembly_sha256,
        "mission_id": assembly.mission_id,
        "bootstrap_sha256": assembly.bootstrap.bootstrap_hash,
        "source_action_plan_sha256": assembly.plan.plan_hash,
        "requested_text_sha256": assembly.plan.requested_text_sha256,
        "requested_text_length": len(assembly.normalized_text),
        "semantic_schedule_sha256": assembly.semantic_schedule.canonical_sha256,
        "trajectory_report_sha256": assembly.trajectory.report_hash,
        "dense_route_schedule_sha256": assembly.dense_route.canonical_sha256,
        "camera_observation_set_sha256": (
            assembly.camera_observations.canonical_sha256
        ),
        "collision_report_sha256": assembly.collision_fixture.report.report_hash,
        "authorization_bundle_sha256": assembly.authorization.bundle_sha256,
        "command_count": assembly.command_count,
        "contact_count": assembly.contact_count,
        "occurrence_sha256s": [
            item.occurrence_hash for item in assembly.occurrences
        ],
        "journal_ids": [
            _journal_id_for_occurrence_hash(item.occurrence_hash)
            for item in assembly.occurrences
        ],
        "automatic_contact_retry_permitted": False,
    }
    return {**core, "manifest_sha256": _hash(core, 256 * 1024)}


def _write_journal_set_manifest(
    root: Path,
    assembly: MultiActionMissionSpecV2,
) -> None:
    destination = root / INTEGRATED_JOURNAL_SET_FILENAME
    payload = _canonical_bytes(_journal_set_document(assembly), 256 * 1024)
    try:
        with destination.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise IntegratedZeroHardwareMissionError(
            "could not publish the integrated journal-set manifest"
        ) from exc


def _verify_journal_set_manifest(
    root: Path,
    assembly: MultiActionMissionSpecV2,
) -> None:
    source = root / INTEGRATED_JOURNAL_SET_FILENAME
    if source.is_symlink() or not source.is_file():
        raise IntegratedZeroHardwareMissionError(
            "integrated journal-set manifest is unavailable"
        )
    expected = _canonical_bytes(_journal_set_document(assembly), 256 * 1024)
    try:
        with source.open("rb") as stream:
            received = stream.read(256 * 1024 + 1)
    except OSError as exc:
        raise IntegratedZeroHardwareMissionError(
            "could not read the integrated journal-set manifest"
        ) from exc
    if received != expected:
        raise IntegratedZeroHardwareMissionError(
            "integrated journal-set manifest differs from the exact assembly"
        )


def _verify_journal_set_directory(
    root: Path,
    assembly: MultiActionMissionSpecV2,
) -> tuple[str, ...]:
    """Require the exact manifest plus one real directory per occurrence."""

    if root.is_symlink() or not root.is_dir():
        raise IntegratedZeroHardwareMissionError("journal root is unavailable")
    expected_journal_ids = tuple(
        _journal_id_for_occurrence_hash(item.occurrence_hash)
        for item in assembly.occurrences
    )
    expected_entries = {INTEGRATED_JOURNAL_SET_FILENAME, *expected_journal_ids}
    entries = tuple(root.iterdir())
    if any(item.is_symlink() for item in entries) or {
        item.name for item in entries
    } != expected_entries:
        raise IntegratedZeroHardwareMissionError(
            "journal directory entries do not exactly cover this assembly"
        )
    for journal_id in expected_journal_ids:
        if not (root / journal_id).is_dir():
            raise IntegratedZeroHardwareMissionError(
                "journal directory entries do not exactly cover this assembly"
            )
    _verify_journal_set_manifest(root, assembly)
    return expected_journal_ids


@dataclass(frozen=True, slots=True)
class IntegratedStateObservationReceipt:
    semantic_step_ordinal: int
    required_state: str
    observed_state: str
    device_state_before_sha256: str
    passed: bool
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(self, "_sealed_sha256", _hash(self._document(), 64 * 1024))

    @property
    def receipt_sha256(self) -> str:
        self.validate()
        return self._sealed_sha256

    def _validate_unsealed(self) -> None:
        _ordinal(self.semantic_step_ordinal, "semantic_step_ordinal", maximum=511)
        required = _bounded_text(self.required_state, "required_state")
        observed = _bounded_text(self.observed_state, "observed_state")
        _digest(self.device_state_before_sha256, "device_state_before_sha256")
        if type(self.passed) is not bool:
            raise TypeError("passed must be bool")
        if self.passed is not (required == observed):
            raise IntegratedZeroHardwareMissionError(
                "state-observation pass flag differs from the observed state"
            )

    def _document(self) -> dict[str, object]:
        return {
            "schema": INTEGRATED_STATE_OBSERVATION_SCHEMA,
            **_authority(),
            "semantic_step_ordinal": self.semantic_step_ordinal,
            "required_state": self.required_state,
            "observed_state": self.observed_state,
            "device_state_before_sha256": self.device_state_before_sha256,
            "passed": self.passed,
            "arm_command_generated": False,
            "contact_occurrence_created": False,
            "journal_created": False,
        }

    def validate(self) -> None:
        self._validate_unsealed()
        if _hash(self._document(), 64 * 1024) != self._sealed_sha256:
            raise IntegratedZeroHardwareMissionError(
                "state-observation receipt changed after construction"
            )

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return self._document()


@dataclass(frozen=True, slots=True)
class IntegratedCommandReceipt:
    semantic_step_ordinal: int
    contact_occurrence_ordinal: int
    route_waypoint_ordinal: int
    authorization_command_ordinal: int
    phase: MotionPhase
    mission_tail: bool
    action_occurrence_sha256: str
    non_wire_t104_command_sha256: str
    authorization_receipt: SimulationCommandReceipt = field(compare=False)
    t104_trace_receipt: T104TraceReceipt = field(compare=False)
    collision_binding_sha256: str
    camera_observation_sha256: str
    success: bool
    fault_kind: str | None
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(
            self,
            "_sealed_sha256",
            _hash(self._document(), 256 * 1024),
        )

    @property
    def receipt_sha256(self) -> str:
        self.validate()
        return self._sealed_sha256

    @property
    def authorization_receipt_sha256(self) -> str:
        return _authorization_receipt_hash(self.authorization_receipt)

    @property
    def t104_trace_receipt_sha256(self) -> str:
        return self.t104_trace_receipt.canonical_sha256

    def _validate_unsealed(self) -> None:
        _ordinal(self.semantic_step_ordinal, "semantic_step_ordinal", maximum=511)
        _ordinal(
            self.contact_occurrence_ordinal,
            "contact_occurrence_ordinal",
            maximum=511,
        )
        route = _ordinal(self.route_waypoint_ordinal, "route_waypoint_ordinal")
        authorization = _ordinal(
            self.authorization_command_ordinal,
            "authorization_command_ordinal",
        )
        if route == 0 or authorization != route - 1:
            raise IntegratedZeroHardwareMissionError(
                "command receipt route/authorization ordinals differ"
            )
        if type(self.phase) is not MotionPhase:
            raise TypeError("phase must be exactly MotionPhase")
        if type(self.mission_tail) is not bool or type(self.success) is not bool:
            raise TypeError("mission_tail and success must be bool")
        if self.mission_tail and self.phase not in {
            MotionPhase.TRANSIT,
            MotionPhase.PARK,
        }:
            raise IntegratedZeroHardwareMissionError(
                "mission-tail receipt has an unsupported phase"
            )
        for name in (
            "action_occurrence_sha256",
            "non_wire_t104_command_sha256",
            "collision_binding_sha256",
            "camera_observation_sha256",
        ):
            _digest(getattr(self, name), name)
        if type(self.authorization_receipt) is not SimulationCommandReceipt:
            raise TypeError(
                "authorization_receipt must be exactly SimulationCommandReceipt"
            )
        self.authorization_receipt.to_dict()
        if (
            self.authorization_receipt.ordinal != authorization
            or self.authorization_receipt.action_occurrence_id
            != self.action_occurrence_sha256
        ):
            raise IntegratedZeroHardwareMissionError(
                "authorization receipt differs from the integrated command"
            )
        if type(self.t104_trace_receipt) is not T104TraceReceipt:
            raise TypeError("t104_trace_receipt must be exactly T104TraceReceipt")
        self.t104_trace_receipt.__post_init__()
        if (
            self.t104_trace_receipt.sequence_ordinal != authorization
            or self.t104_trace_receipt.command_sha256
            != self.non_wire_t104_command_sha256
            or self.t104_trace_receipt.success is not self.success
            or self.t104_trace_receipt.fault_kind != self.fault_kind
        ):
            raise IntegratedZeroHardwareMissionError(
                "T104 trace receipt differs from the integrated command"
            )
        if self.fault_kind is not None and self.fault_kind not in _T104_FAULT_KINDS:
            raise IntegratedZeroHardwareMissionError(
                "command receipt fault_kind is not recognized"
            )
        if self.success is not (self.fault_kind is None):
            raise IntegratedZeroHardwareMissionError(
                "command receipt success differs from fault_kind"
            )

    def _document(self) -> dict[str, object]:
        return {
            "schema": INTEGRATED_COMMAND_RECEIPT_SCHEMA,
            **_authority(),
            "semantic_step_ordinal": self.semantic_step_ordinal,
            "contact_occurrence_ordinal": self.contact_occurrence_ordinal,
            "route_waypoint_ordinal": self.route_waypoint_ordinal,
            "authorization_command_ordinal": self.authorization_command_ordinal,
            "phase": self.phase.value,
            "mission_tail": self.mission_tail,
            "action_occurrence_sha256": self.action_occurrence_sha256,
            "non_wire_t104_command_sha256": self.non_wire_t104_command_sha256,
            "authorization_receipt": self.authorization_receipt.to_dict(),
            "authorization_receipt_sha256": self.authorization_receipt_sha256,
            "t104_trace_receipt": self.t104_trace_receipt.to_dict(),
            "t104_trace_receipt_sha256": self.t104_trace_receipt_sha256,
            "collision_binding_sha256": self.collision_binding_sha256,
            "camera_observation_sha256": self.camera_observation_sha256,
            "success": self.success,
            "fault_kind": self.fault_kind,
        }

    def validate(self) -> None:
        self._validate_unsealed()
        if _hash(self._document(), 256 * 1024) != self._sealed_sha256:
            raise IntegratedZeroHardwareMissionError(
                "command receipt changed after construction"
            )

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return self._document()


@dataclass(frozen=True, slots=True)
class IntegratedContactReceipt:
    semantic_step_ordinal: int
    contact_occurrence_ordinal: int
    target_id: str
    action_occurrence_sha256: str
    contact_event_sha256: str
    contact_result_sha256: str
    resolved_target_id: str | None
    observer_snapshot_sha256: str
    journal_snapshot_sha256: str
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(self, "_sealed_sha256", _hash(self._document(), 64 * 1024))

    @property
    def receipt_sha256(self) -> str:
        self.validate()
        return self._sealed_sha256

    def _validate_unsealed(self) -> None:
        _ordinal(self.semantic_step_ordinal, "semantic_step_ordinal", maximum=511)
        _ordinal(
            self.contact_occurrence_ordinal,
            "contact_occurrence_ordinal",
            maximum=511,
        )
        target = _bounded_text(self.target_id, "target_id")
        for name in (
            "action_occurrence_sha256",
            "contact_event_sha256",
            "contact_result_sha256",
            "observer_snapshot_sha256",
            "journal_snapshot_sha256",
        ):
            _digest(getattr(self, name), name)
        if type(self.resolved_target_id) is not str or not self.resolved_target_id.endswith(
            f":{target}"
        ):
            raise IntegratedZeroHardwareMissionError(
                "contact receipt did not resolve its intended semantic target"
            )

    def _document(self) -> dict[str, object]:
        return {
            "schema": INTEGRATED_CONTACT_RECEIPT_SCHEMA,
            **_authority(),
            "semantic_step_ordinal": self.semantic_step_ordinal,
            "contact_occurrence_ordinal": self.contact_occurrence_ordinal,
            "target_id": self.target_id,
            "action_occurrence_sha256": self.action_occurrence_sha256,
            "contact_event_sha256": self.contact_event_sha256,
            "contact_result_sha256": self.contact_result_sha256,
            "resolved_target_id": self.resolved_target_id,
            "observer_snapshot_sha256": self.observer_snapshot_sha256,
            "journal_snapshot_sha256": self.journal_snapshot_sha256,
            "plaintext_output_serialized": False,
        }

    def validate(self) -> None:
        self._validate_unsealed()
        if _hash(self._document(), 64 * 1024) != self._sealed_sha256:
            raise IntegratedZeroHardwareMissionError(
                "contact receipt changed after construction"
            )

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return self._document()


def _coordinator_fault_source_sha256(
    *,
    assembly_sha256: str,
    stage: str,
    fault_kind: str,
    semantic_step_ordinal: int | None,
    contact_occurrence_ordinal: int | None,
    authorization_command_ordinal: int | None,
    command_receipt_count: int,
    camera_observation_count: int,
    state_observation_count: int,
    contact_receipt_count: int,
) -> str:
    """Hash a coordinator failure's exact durable/in-memory execution prefix."""

    return _hash(
        {
            "schema": "rocell.integrated_execution_prefix_fault.v1",
            "assembly_sha256": assembly_sha256,
            "source_class": _FAULT_SOURCE_COORDINATOR,
            "stage": stage,
            "fault_kind": fault_kind,
            "semantic_step_ordinal": semantic_step_ordinal,
            "contact_occurrence_ordinal": contact_occurrence_ordinal,
            "authorization_command_ordinal": authorization_command_ordinal,
            "command_receipt_count": command_receipt_count,
            "camera_observation_count": camera_observation_count,
            "state_observation_count": state_observation_count,
            "contact_receipt_count": contact_receipt_count,
            **_authority(),
        },
        64 * 1024,
    )


def _observation_boundary_fault_source_sha256(
    *,
    assembly_sha256: str,
    semantic_step_ordinal: int,
    contact_occurrence_ordinal: int,
    authorization_command_ordinal: int,
    command_receipt_count: int,
    camera_observation_count: int,
    state_observation_count: int,
    contact_receipt_count: int,
) -> str:
    """Bind a coarse observation-boundary failure to its exact run prefix.

    The boundary intentionally includes both the coordinator's settled-hover
    association checks and the replay-camera call.  Unless the camera adapter
    returns its own sealed ``B0477ReplayFaultReceipt``, the available evidence
    cannot distinguish those two locations more precisely.
    """

    return _hash(
        {
            "schema": "rocell.integrated_observation_boundary_fault.v1",
            "assembly_sha256": assembly_sha256,
            "source_class": _FAULT_SOURCE_OBSERVATION_BOUNDARY,
            "stage": _OBSERVATION_BOUNDARY_STAGE,
            "fault_kind": _OBSERVATION_BOUNDARY_FAULT_KIND,
            "semantic_step_ordinal": semantic_step_ordinal,
            "contact_occurrence_ordinal": contact_occurrence_ordinal,
            "authorization_command_ordinal": authorization_command_ordinal,
            "command_receipt_count": command_receipt_count,
            "camera_observation_count": camera_observation_count,
            "state_observation_count": state_observation_count,
            "contact_receipt_count": contact_receipt_count,
            **_authority(),
        },
        64 * 1024,
    )


@dataclass(frozen=True, slots=True)
class IntegratedFaultReceipt:
    """Sealed, machine-verifiable cause record for a failed V2 mission.

    Human-readable ``fault_detail`` remains useful for diagnostics, but it is
    intentionally not causal evidence.  Typed camera faults retain the camera
    port's full settled-hover receipt; other failures near that call retain a
    deliberately coarse observation-boundary prefix; controller faults bind
    the failed T104 trace; coordinator faults bind a coarse execution stage.
    """

    assembly_sha256: str
    source_class: str
    stage: str
    fault_kind: str
    semantic_step_ordinal: int | None
    contact_occurrence_ordinal: int | None
    authorization_command_ordinal: int | None
    command_receipt_count: int
    camera_observation_count: int
    state_observation_count: int
    contact_receipt_count: int
    source_evidence_sha256: str
    camera_fault_receipt: B0477ReplayFaultReceipt | None = None
    schema: str = INTEGRATED_FAULT_RECEIPT_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(
            self,
            "_sealed_sha256",
            _hash(self._document(), 256 * 1024),
        )

    @property
    def receipt_sha256(self) -> str:
        self.validate()
        return self._sealed_sha256

    def _validate_unsealed(self) -> None:
        if self.schema != INTEGRATED_FAULT_RECEIPT_SCHEMA:
            raise IntegratedZeroHardwareMissionError(
                "unsupported integrated fault receipt schema"
            )
        _digest(self.assembly_sha256, "fault assembly_sha256")
        _bounded_text(self.source_class, "fault source_class")
        _bounded_text(self.stage, "fault stage")
        _bounded_text(self.fault_kind, "fault kind")
        _digest(self.source_evidence_sha256, "fault source_evidence_sha256")
        for name in (
            "semantic_step_ordinal",
            "contact_occurrence_ordinal",
            "authorization_command_ordinal",
        ):
            value = getattr(self, name)
            if value is not None:
                _ordinal(value, name, maximum=65_535)
        for name, maximum in (
            ("command_receipt_count", 4096),
            ("camera_observation_count", 512),
            ("state_observation_count", 512),
            ("contact_receipt_count", 512),
        ):
            _ordinal(getattr(self, name), name, maximum=maximum)
        if self.contact_receipt_count > self.camera_observation_count:
            raise IntegratedZeroHardwareMissionError(
                "fault receipt has more contacts than camera observations"
            )

        if self.source_class == _FAULT_SOURCE_OBSERVATION_BOUNDARY:
            if (
                self.stage != _OBSERVATION_BOUNDARY_STAGE
                or self.fault_kind != _OBSERVATION_BOUNDARY_FAULT_KIND
                or self.semantic_step_ordinal is None
                or self.contact_occurrence_ordinal is None
                or self.authorization_command_ordinal is None
            ):
                raise IntegratedZeroHardwareMissionError(
                    "observation-boundary fault has inconsistent source metadata"
                )
            expected_source = _observation_boundary_fault_source_sha256(
                assembly_sha256=self.assembly_sha256,
                semantic_step_ordinal=self.semantic_step_ordinal,
                contact_occurrence_ordinal=self.contact_occurrence_ordinal,
                authorization_command_ordinal=(
                    self.authorization_command_ordinal
                ),
                command_receipt_count=self.command_receipt_count,
                camera_observation_count=self.camera_observation_count,
                state_observation_count=self.state_observation_count,
                contact_receipt_count=self.contact_receipt_count,
            )
            if self.source_evidence_sha256 != expected_source:
                raise IntegratedZeroHardwareMissionError(
                    "observation-boundary source differs from its prefix"
                )
            camera = self.camera_fault_receipt
            if camera is not None:
                if type(camera) is not B0477ReplayFaultReceipt:
                    raise TypeError(
                        "camera fault diagnostic must be exactly "
                        "B0477ReplayFaultReceipt"
                    )
                camera.validate()
                if (
                    camera.fault_kind.value not in _CAMERA_FAULT_KINDS
                    or self.semantic_step_ordinal
                    != camera.semantic_step_ordinal
                    or self.contact_occurrence_ordinal
                    != camera.contact_occurrence_ordinal
                    or self.authorization_command_ordinal
                    != camera.authorization_command_ordinal
                ):
                    raise IntegratedZeroHardwareMissionError(
                        "camera fault diagnostic differs from its observation boundary"
                    )
        elif self.source_class == _FAULT_SOURCE_RUNTIME:
            if (
                self.stage != "COMMAND_EXECUTION"
                or self.fault_kind not in _T104_FAULT_KINDS
                or self.camera_fault_receipt is not None
                or self.semantic_step_ordinal is None
                or self.contact_occurrence_ordinal is None
                or self.authorization_command_ordinal is None
            ):
                raise IntegratedZeroHardwareMissionError(
                    "controller fault receipt has inconsistent source metadata"
                )
        elif self.source_class == _FAULT_SOURCE_COORDINATOR:
            if (
                self.stage not in _COORDINATOR_FAULT_STAGES
                or self.fault_kind != _COORDINATOR_FAULT_KIND
                or self.camera_fault_receipt is not None
            ):
                raise IntegratedZeroHardwareMissionError(
                    "coordinator fault receipt has inconsistent source metadata"
                )
            expected_source = _coordinator_fault_source_sha256(
                assembly_sha256=self.assembly_sha256,
                stage=self.stage,
                fault_kind=self.fault_kind,
                semantic_step_ordinal=self.semantic_step_ordinal,
                contact_occurrence_ordinal=self.contact_occurrence_ordinal,
                authorization_command_ordinal=self.authorization_command_ordinal,
                command_receipt_count=self.command_receipt_count,
                camera_observation_count=self.camera_observation_count,
                state_observation_count=self.state_observation_count,
                contact_receipt_count=self.contact_receipt_count,
            )
            if self.source_evidence_sha256 != expected_source:
                raise IntegratedZeroHardwareMissionError(
                    "coordinator fault source evidence differs from its prefix"
                )
        else:
            raise IntegratedZeroHardwareMissionError(
                "integrated fault source class is not recognized"
            )

    def _document(self) -> dict[str, object]:
        camera = self.camera_fault_receipt
        return {
            "schema": self.schema,
            **_authority(),
            "assembly_sha256": self.assembly_sha256,
            "source_class": self.source_class,
            "stage": self.stage,
            "fault_kind": self.fault_kind,
            "semantic_step_ordinal": self.semantic_step_ordinal,
            "contact_occurrence_ordinal": self.contact_occurrence_ordinal,
            "authorization_command_ordinal": self.authorization_command_ordinal,
            "command_receipt_count": self.command_receipt_count,
            "camera_observation_count": self.camera_observation_count,
            "state_observation_count": self.state_observation_count,
            "contact_receipt_count": self.contact_receipt_count,
            "source_evidence_sha256": self.source_evidence_sha256,
            "camera_fault_receipt": None if camera is None else camera.to_dict(),
            "camera_fault_receipt_sha256": (
                None if camera is None else camera.canonical_sha256
            ),
            # Simulation receipts have no secret authenticity anchor.  The
            # nested camera detail can aid deterministic diagnosis but cannot
            # prove, after persistence, that the adapter rather than an
            # adjacent association check raised.  Causality therefore remains
            # the coarse source/stage/kind above.
            "camera_fault_receipt_is_causal_evidence": False,
            "camera_fault_receipt_role": "UNAUTHENTICATED_DIAGNOSTIC_ONLY",
        }

    def validate(self) -> None:
        self._validate_unsealed()
        if _hash(self._document(), 256 * 1024) != self._sealed_sha256:
            raise IntegratedZeroHardwareMissionError(
                "integrated fault receipt changed after construction"
            )

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {**self._document(), "receipt_sha256": self._sealed_sha256}


_JOURNAL_TRANSITIONS = {
    ActionJournalState.INTENT_COMMITTED: frozenset(
        {ActionJournalState.PRE_CONTACT, ActionJournalState.FAULTED}
    ),
    ActionJournalState.PRE_CONTACT: frozenset(
        {ActionJournalState.CONTACT_MAY_HAVE_OCCURRED, ActionJournalState.FAULTED}
    ),
    ActionJournalState.CONTACT_MAY_HAVE_OCCURRED: frozenset(
        {ActionJournalState.OUTCOME_CONFIRMED, ActionJournalState.OUTCOME_UNCERTAIN}
    ),
    ActionJournalState.OUTCOME_CONFIRMED: frozenset(
        {ActionJournalState.RETRACTED, ActionJournalState.FAULTED}
    ),
    ActionJournalState.RETRACTED: frozenset(
        {ActionJournalState.PARKED, ActionJournalState.FAULTED}
    ),
    ActionJournalState.PARKED: frozenset(),
    ActionJournalState.FAULTED: frozenset(),
    ActionJournalState.OUTCOME_UNCERTAIN: frozenset(),
}
_COMPLETE_JOURNAL_STATES = (
    ActionJournalState.INTENT_COMMITTED,
    ActionJournalState.PRE_CONTACT,
    ActionJournalState.CONTACT_MAY_HAVE_OCCURRED,
    ActionJournalState.OUTCOME_CONFIRMED,
    ActionJournalState.RETRACTED,
    ActionJournalState.PARKED,
)
_INTEGRATED_JOURNAL_DETAIL_CODES = {
    ActionJournalState.INTENT_COMMITTED: "ACTION_INTENT_COMMITTED",
    ActionJournalState.PRE_CONTACT: "PRE_CONTACT_EVIDENCE_COMMITTED",
    ActionJournalState.CONTACT_MAY_HAVE_OCCURRED: (
        "CONTACT_BOUNDARY_COMMITTED_BEFORE_SUBMISSION"
    ),
    ActionJournalState.OUTCOME_CONFIRMED: "INDEPENDENT_OUTCOME_CONFIRMED",
    ActionJournalState.RETRACTED: "RETRACTION_CONFIRMED",
    ActionJournalState.PARKED: "PARK_CONFIRMED",
    ActionJournalState.FAULTED: "INTEGRATED_MISSION_ABORTED",
    ActionJournalState.OUTCOME_UNCERTAIN: (
        "INTEGRATED_CONTACT_OUTCOME_UNCERTAIN"
    ),
}


def _validate_journal_snapshot(snapshot: MissionJournalSnapshot) -> None:
    """Recompute the complete in-memory journal chain carried by a report."""

    if type(snapshot) is not MissionJournalSnapshot:
        raise TypeError("journal snapshots must contain MissionJournalSnapshot")
    if type(snapshot.occurrence) is not ActionOccurrence:
        raise TypeError("journal snapshot occurrence must be ActionOccurrence")
    snapshot.occurrence.__post_init__()
    _ordinal(snapshot.created_at_ns, "journal created_at_ns", maximum=2**63 - 1)
    if snapshot.created_at_ns == 0:
        raise IntegratedZeroHardwareMissionError("journal created_at_ns must be positive")
    _digest(snapshot.header_sha256, "journal header_sha256")
    _digest(snapshot.high_water_sha256, "journal high_water_sha256")
    expected_journal_id = _journal_id_for_occurrence_hash(
        snapshot.occurrence.occurrence_hash
    )
    if snapshot.journal_id != expected_journal_id:
        raise IntegratedZeroHardwareMissionError(
            "journal snapshot id differs from its occurrence"
        )
    events = snapshot.events
    if type(events) is not tuple or not 1 <= len(events) <= 32:
        raise IntegratedZeroHardwareMissionError(
            "journal snapshot needs a bounded immutable event chain"
        )
    if any(type(item) is not MissionJournalEvent for item in events):
        raise TypeError("journal events must be exactly MissionJournalEvent")
    previous_hash = _ZERO_SHA256
    previous_time = snapshot.created_at_ns - 1
    previous_state: ActionJournalState | None = None
    for sequence, event in enumerate(events):
        event.__post_init__()
        if (
            event.sequence != sequence
            or event.journal_id != snapshot.journal_id
            or event.occurrence_id != snapshot.occurrence.occurrence_id
            or event.previous_event_sha256 != previous_hash
            or event.event_time_ns <= previous_time
        ):
            raise IntegratedZeroHardwareMissionError(
                "journal snapshot event chain is inconsistent"
            )
        if event.detail_code != _INTEGRATED_JOURNAL_DETAIL_CODES[event.state]:
            raise IntegratedZeroHardwareMissionError(
                "journal event detail code differs from integrated runtime semantics"
            )
        if sequence == 0:
            if (
                event.state is not ActionJournalState.INTENT_COMMITTED
                or event.evidence_sha256 != snapshot.occurrence.action_sha256
                or event.event_time_ns != snapshot.created_at_ns
            ):
                raise IntegratedZeroHardwareMissionError(
                    "journal snapshot does not start with bound intent"
                )
        elif previous_state is None or event.state not in _JOURNAL_TRANSITIONS[
            previous_state
        ]:
            raise IntegratedZeroHardwareMissionError(
                "journal snapshot contains an invalid state transition"
            )
        previous_hash = event.event_sha256
        previous_time = event.event_time_ns
        previous_state = event.state

    header_core = {
        "schema": MISSION_JOURNAL_HEADER_SCHEMA,
        "journal_id": snapshot.journal_id,
        "occurrence": snapshot.occurrence.to_dict(),
        "occurrence_sha256": snapshot.occurrence.occurrence_hash,
        "created_at_ns": snapshot.created_at_ns,
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "physical_release_effect": "NONE",
    }
    if snapshot.header_sha256 != _hash(header_core, 64 * 1024):
        raise IntegratedZeroHardwareMissionError(
            "journal snapshot header hash is inconsistent"
        )
    contact = next(
        (
            event
            for event in events
            if event.state is ActionJournalState.CONTACT_MAY_HAVE_OCCURRED
        ),
        None,
    )
    high_water_core = {
        "schema": MISSION_JOURNAL_HIGH_WATER_SCHEMA,
        "journal_id": snapshot.journal_id,
        "occurrence_id": snapshot.occurrence.occurrence_id,
        "header_sha256": snapshot.header_sha256,
        "committed_sequence": events[-1].sequence,
        "committed_event_sha256": events[-1].event_sha256,
        "committed_state": events[-1].state.value,
        "committed_event_time_ns": events[-1].event_time_ns,
        "event_count": len(events),
        "contact_boundary_ever_committed": contact is not None,
        "contact_boundary_sequence": None if contact is None else contact.sequence,
        "contact_boundary_event_sha256": (
            None if contact is None else contact.event_sha256
        ),
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "physical_release_effect": "NONE",
    }
    if snapshot.high_water_sha256 != _hash(high_water_core, 64 * 1024):
        raise IntegratedZeroHardwareMissionError(
            "journal snapshot high-water hash is inconsistent"
        )


@dataclass(frozen=True, slots=True)
class PreparedZeroHardwareMissionV2:
    assembly: MultiActionMissionSpecV2
    journals: tuple[ZeroAuthorityMissionJournal, ...]

    def __post_init__(self) -> None:
        if type(self.assembly) is not MultiActionMissionSpecV2:
            raise TypeError("assembly must be exactly MultiActionMissionSpecV2")
        self.assembly.validate()
        if type(self.journals) is not tuple:
            raise TypeError("journals must be an immutable tuple")
        journals = self.journals
        if len(journals) != self.assembly.contact_count or any(
            type(item) is not ZeroAuthorityMissionJournal for item in journals
        ):
            raise IntegratedZeroHardwareMissionError(
                "prepared journals do not cover every physical occurrence"
            )
        snapshots = tuple(item.snapshot() for item in journals)
        if tuple(item.occurrence for item in snapshots) != self.assembly.occurrences:
            raise IntegratedZeroHardwareMissionError(
                "prepared journal occurrences differ from the assembly"
            )
        maximum_event_time = max(
            event.event_time_ns
            for snapshot in snapshots
            for event in snapshot.events
        )
        if maximum_event_time > (2**63 - 1) - 10_000 - (
            8 * self.assembly.contact_count
        ):
            raise IntegratedZeroHardwareMissionError(
                "prepared journals lack timestamp headroom for safe fault closure"
            )
        roots = {item.directory.parent.resolve() for item in journals}
        if len(roots) != 1:
            raise IntegratedZeroHardwareMissionError(
                "prepared journals do not share one assembly-bound root"
            )
        _verify_journal_set_directory(next(iter(roots)), self.assembly)


@dataclass(frozen=True, slots=True)
class IntegratedZeroHardwareMissionReport:
    status: str
    assembly_sha256: str
    command_receipts: tuple[IntegratedCommandReceipt, ...]
    camera_observation_sha256s: tuple[str, ...]
    state_observation_receipts: tuple[IntegratedStateObservationReceipt, ...]
    contact_receipts: tuple[IntegratedContactReceipt, ...]
    runtime_final_state: T104RuntimeStateReceipt
    journal_snapshots: tuple[MissionJournalSnapshot, ...]
    expected_output_sha256: str
    expected_output_length: int
    observed_output_sha256: str
    observed_output_length: int
    outcome_matches: bool
    fault_receipt: IntegratedFaultReceipt | None
    fault_detail: str | None
    schema: str = INTEGRATED_ZERO_HARDWARE_REPORT_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(self, "_sealed_sha256", _hash(self._document()))

    @property
    def completed(self) -> bool:
        return self.status == _COMPLETE_STATUS

    @property
    def report_sha256(self) -> str:
        self.validate()
        return self._sealed_sha256

    def _completion_evidence_passes(self) -> bool:
        return (
            self.fault_receipt is None
            and self.fault_detail is None
            and self.outcome_matches
            and bool(self.command_receipts)
            and bool(self.contact_receipts)
            and all(item.success for item in self.command_receipts)
            and all(item.passed for item in self.state_observation_receipts)
            and self.runtime_final_state.terminal
            and self.runtime_final_state.connected
            and self.runtime_final_state.fault_latched is None
            and self.runtime_final_state.attempted_command_count
            == len(self.command_receipts)
            and self.runtime_final_state.completed_command_count
            == len(self.command_receipts)
            and len(self.camera_observation_sha256s) == len(self.contact_receipts)
            and len(self.contact_receipts) == len(self.journal_snapshots)
            and all(
                tuple(event.state for event in snapshot.events)
                == _COMPLETE_JOURNAL_STATES
                for snapshot in self.journal_snapshots
            )
        )

    def _validate_unsealed(self) -> None:
        if self.schema != INTEGRATED_ZERO_HARDWARE_REPORT_SCHEMA:
            raise IntegratedZeroHardwareMissionError(
                "unsupported integrated mission report schema"
            )
        if self.status not in {_COMPLETE_STATUS, _FAULTED_STATUS}:
            raise IntegratedZeroHardwareMissionError(
                "integrated mission report status is not recognized"
            )
        _digest(self.assembly_sha256, "assembly_sha256")
        for name in ("expected_output_sha256", "observed_output_sha256"):
            _digest(getattr(self, name), name)
        expected_length = _ordinal(
            self.expected_output_length,
            "expected_output_length",
            maximum=65_535,
        )
        observed_length = _ordinal(
            self.observed_output_length,
            "observed_output_length",
            maximum=65_535,
        )
        if type(self.outcome_matches) is not bool:
            raise TypeError("outcome_matches must be bool")
        exact_outcome = (
            self.expected_output_sha256 == self.observed_output_sha256
            and expected_length == observed_length
        )
        if self.outcome_matches is not exact_outcome:
            raise IntegratedZeroHardwareMissionError(
                "outcome_matches differs from the redacted output evidence"
            )

        commands = self.command_receipts
        if type(commands) is not tuple or len(commands) > 4096:
            raise IntegratedZeroHardwareMissionError(
                "command receipts must be a bounded immutable tuple"
            )
        if any(type(item) is not IntegratedCommandReceipt for item in commands):
            raise TypeError("command receipts contain the wrong type")
        for item in commands:
            item.validate()
        if tuple(item.authorization_command_ordinal for item in commands) != tuple(
            range(len(commands))
        ) or tuple(item.route_waypoint_ordinal for item in commands) != tuple(
            range(1, len(commands) + 1)
        ):
            raise IntegratedZeroHardwareMissionError(
                "command receipt ordinals are not a dense route prefix"
            )
        failed = tuple(index for index, item in enumerate(commands) if not item.success)
        if failed and failed != (len(commands) - 1,):
            raise IntegratedZeroHardwareMissionError(
                "only the final attempted command may be faulted"
            )
        contact_groups: list[int] = []
        for item in commands:
            if not contact_groups or contact_groups[-1] != item.contact_occurrence_ordinal:
                if item.contact_occurrence_ordinal in contact_groups:
                    raise IntegratedZeroHardwareMissionError(
                        "command receipt contact groups are not contiguous"
                    )
                contact_groups.append(item.contact_occurrence_ordinal)
        if contact_groups and contact_groups != list(range(len(contact_groups))):
            raise IntegratedZeroHardwareMissionError(
                "command receipt contact groups are not dense"
            )
        tails = tuple(index for index, item in enumerate(commands) if item.mission_tail)
        if tails and tails != tuple(range(tails[0], len(commands))):
            raise IntegratedZeroHardwareMissionError(
                "mission-tail command receipts are not a final suffix"
            )
        for previous, current in zip(commands, commands[1:]):
            if (
                current.t104_trace_receipt.state_before
                != previous.t104_trace_receipt.state_after
                or current.authorization_receipt.permit_id
                != previous.authorization_receipt.permit_id
                or current.authorization_receipt.context_sha256
                != previous.authorization_receipt.context_sha256
                or current.authorization_receipt.consumed_at_monotonic
                <= previous.authorization_receipt.consumed_at_monotonic
            ):
                raise IntegratedZeroHardwareMissionError(
                    "integrated command receipts are not one continuous run"
                )

        camera = self.camera_observation_sha256s
        if type(camera) is not tuple or len(camera) > 512:
            raise IntegratedZeroHardwareMissionError(
                "camera receipts must be a bounded immutable tuple"
            )
        for index, value in enumerate(camera):
            _digest(value, f"camera_observation_sha256s[{index}]")
        if len(set(camera)) != len(camera):
            raise IntegratedZeroHardwareMissionError(
                "an integrated camera observation was reused"
            )
        command_camera_order: list[str] = []
        for item in commands:
            if item.camera_observation_sha256 not in command_camera_order:
                command_camera_order.append(item.camera_observation_sha256)
        if tuple(command_camera_order[: len(camera)]) != camera:
            raise IntegratedZeroHardwareMissionError(
                "camera receipts are not an ordered command-observation prefix"
            )

        states = self.state_observation_receipts
        if type(states) is not tuple or len(states) > 512:
            raise IntegratedZeroHardwareMissionError(
                "state receipts must be a bounded immutable tuple"
            )
        if any(type(item) is not IntegratedStateObservationReceipt for item in states):
            raise TypeError("state receipts contain the wrong type")
        for state_receipt in states:
            state_receipt.validate()
        if any(
            right.semantic_step_ordinal <= left.semantic_step_ordinal
            for left, right in zip(states, states[1:])
        ):
            raise IntegratedZeroHardwareMissionError(
                "state-observation semantic ordinals must increase"
            )

        contacts = self.contact_receipts
        if type(contacts) is not tuple or len(contacts) > 512:
            raise IntegratedZeroHardwareMissionError(
                "contact receipts must be a bounded immutable tuple"
            )
        if any(type(item) is not IntegratedContactReceipt for item in contacts):
            raise TypeError("contact receipts contain the wrong type")
        for contact_receipt in contacts:
            contact_receipt.validate()
        if tuple(item.contact_occurrence_ordinal for item in contacts) != tuple(
            range(len(contacts))
        ) or any(
            right.semantic_step_ordinal <= left.semantic_step_ordinal
            for left, right in zip(contacts, contacts[1:])
        ):
            raise IntegratedZeroHardwareMissionError(
                "contact receipt ordinals are not an ordered dense prefix"
            )
        if len(contacts) > len(camera):
            raise IntegratedZeroHardwareMissionError(
                "a contact receipt exists without a prior camera receipt"
            )

        if type(self.runtime_final_state) is not T104RuntimeStateReceipt:
            raise TypeError("runtime_final_state must be T104RuntimeStateReceipt")
        runtime = T104RuntimeStateReceipt.from_dict(
            self.runtime_final_state.to_dict()
        )
        if runtime != self.runtime_final_state:
            raise IntegratedZeroHardwareMissionError(
                "runtime final state is not canonical"
            )
        if (
            runtime.attempted_command_count != len(commands)
            or runtime.completed_command_count
            != sum(item.success for item in commands)
            or runtime.next_sequence_ordinal != runtime.completed_command_count
        ):
            raise IntegratedZeroHardwareMissionError(
                "runtime counters differ from command receipts"
            )
        if commands and runtime != commands[-1].t104_trace_receipt.state_after:
            raise IntegratedZeroHardwareMissionError(
                "runtime final state differs from the final retained T104 trace"
            )
        if runtime.fault_latched is None:
            if failed:
                raise IntegratedZeroHardwareMissionError(
                    "failed command receipt has no runtime fault"
                )
        elif not failed or commands[-1].fault_kind != runtime.fault_latched:
            raise IntegratedZeroHardwareMissionError(
                "runtime fault differs from the final command receipt"
            )

        fault = self.fault_receipt
        if fault is not None:
            if type(fault) is not IntegratedFaultReceipt:
                raise TypeError("fault_receipt must be IntegratedFaultReceipt or None")
            fault.validate()
            if (
                fault.assembly_sha256 != self.assembly_sha256
                or fault.command_receipt_count != len(commands)
                or fault.camera_observation_count != len(camera)
                or fault.state_observation_count != len(states)
                or fault.contact_receipt_count != len(contacts)
            ):
                raise IntegratedZeroHardwareMissionError(
                    "fault receipt differs from the report execution prefix"
                )

        journals = self.journal_snapshots
        if type(journals) is not tuple or not 1 <= len(journals) <= 512:
            raise IntegratedZeroHardwareMissionError(
                "journal snapshots must be a bounded non-empty immutable tuple"
            )
        for snapshot in journals:
            _validate_journal_snapshot(snapshot)
        if tuple(item.occurrence.action_ordinal for item in journals) != tuple(
            range(len(journals))
        ) or len({item.journal_id for item in journals}) != len(journals):
            raise IntegratedZeroHardwareMissionError(
                "journal snapshot occurrences are not dense and unique"
            )
        for contact, snapshot in zip(contacts, journals):
            outcome_indexes = tuple(
                index
                for index, event in enumerate(snapshot.events)
                if event.state is ActionJournalState.OUTCOME_CONFIRMED
            )
            if len(outcome_indexes) != 1:
                raise IntegratedZeroHardwareMissionError(
                    "contact receipt journal has no unique confirmed-outcome prefix"
                )
            outcome_events = snapshot.events[: outcome_indexes[0] + 1]
            boundary = next(
                event
                for event in outcome_events
                if event.state is ActionJournalState.CONTACT_MAY_HAVE_OCCURRED
            )
            outcome_tail = outcome_events[-1]
            outcome_high_water_core = {
                "schema": MISSION_JOURNAL_HIGH_WATER_SCHEMA,
                "journal_id": snapshot.journal_id,
                "occurrence_id": snapshot.occurrence.occurrence_id,
                "header_sha256": snapshot.header_sha256,
                "committed_sequence": outcome_tail.sequence,
                "committed_event_sha256": outcome_tail.event_sha256,
                "committed_state": outcome_tail.state.value,
                "committed_event_time_ns": outcome_tail.event_time_ns,
                "event_count": len(outcome_events),
                "contact_boundary_ever_committed": True,
                "contact_boundary_sequence": boundary.sequence,
                "contact_boundary_event_sha256": boundary.event_sha256,
                "simulation_only": True,
                "hardware_accessed": False,
                "hardware_commands_generated": 0,
                "physical_release_effect": "NONE",
            }
            historical_outcome_snapshot = MissionJournalSnapshot(
                journal_id=snapshot.journal_id,
                occurrence=snapshot.occurrence,
                created_at_ns=snapshot.created_at_ns,
                header_sha256=snapshot.header_sha256,
                high_water_sha256=_hash(outcome_high_water_core, 64 * 1024),
                events=outcome_events,
            )
            expected_outcome_sha256 = _hash(
                {
                    "occurrence_sha256": contact.action_occurrence_sha256,
                    "contact_result_sha256": contact.contact_result_sha256,
                    "observer_snapshot_sha256": contact.observer_snapshot_sha256,
                    "resolved_target_id": contact.resolved_target_id,
                },
                128 * 1024,
            )
            if (
                contact.action_occurrence_sha256
                != snapshot.occurrence.occurrence_hash
                or contact.journal_snapshot_sha256
                != historical_outcome_snapshot.snapshot_hash
                or outcome_tail.evidence_sha256 != expected_outcome_sha256
            ):
                raise IntegratedZeroHardwareMissionError(
                    "contact receipt differs from its journal snapshot"
                )

        completion = self._completion_evidence_passes()
        if self.status != (_COMPLETE_STATUS if completion else _FAULTED_STATUS):
            raise IntegratedZeroHardwareMissionError(
                "report status differs from independently derived completion evidence"
            )
        if completion:
            if self.fault_receipt is not None or self.fault_detail is not None:
                raise IntegratedZeroHardwareMissionError(
                    "complete report cannot contain fault evidence"
                )
        else:
            if self.fault_receipt is None:
                raise IntegratedZeroHardwareMissionError(
                    "faulted report requires a structured fault receipt"
                )
            _bounded_text(self.fault_detail, "fault_detail")

    def _document(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            **_authority(),
            "status": self.status,
            "completed": self.completed,
            "assembly_sha256": self.assembly_sha256,
            "execution": {
                "command_count": len(self.command_receipts),
                "command_receipts": [
                    item.to_dict() for item in self.command_receipts
                ],
                "command_receipt_hashes": [
                    item.receipt_sha256 for item in self.command_receipts
                ],
                "camera_observation_count": len(self.camera_observation_sha256s),
                "camera_observation_sha256s": list(
                    self.camera_observation_sha256s
                ),
                "state_observation_count": len(self.state_observation_receipts),
                "state_observation_receipts": [
                    item.to_dict() for item in self.state_observation_receipts
                ],
                "state_observation_receipt_hashes": [
                    item.receipt_sha256
                    for item in self.state_observation_receipts
                ],
                "contact_count": len(self.contact_receipts),
                "contact_receipts": [
                    item.to_dict() for item in self.contact_receipts
                ],
                "contact_receipt_hashes": [
                    item.receipt_sha256 for item in self.contact_receipts
                ],
            },
            "controller_final_state": self.runtime_final_state.to_dict(),
            "journals": [
                {
                    **item.to_dict(),
                    "events": [event.to_dict() for event in item.events],
                }
                for item in self.journal_snapshots
            ],
            "outcome": {
                "expected_sha256": self.expected_output_sha256,
                "expected_length": self.expected_output_length,
                "observed_sha256": self.observed_output_sha256,
                "observed_length": self.observed_output_length,
                "matches": self.outcome_matches,
                "raw_plaintext_field_serialized": False,
                "semantic_target_metadata_serialized": True,
                "semantic_target_metadata_may_reconstruct_text": True,
                "observer_input_contract": "CONTACT_RESULT_ONLY",
            },
            "fault_receipt": (
                None if self.fault_receipt is None else self.fault_receipt.to_dict()
            ),
            "fault_receipt_sha256": (
                None
                if self.fault_receipt is None
                else self.fault_receipt.receipt_sha256
            ),
            "fault_detail": self.fault_detail,
            "fault_detail_is_descriptive_only": True,
            "physical_readiness": {
                "ready": False,
                "reason": (
                    "software integration passed" if self.completed else "rehearsal faulted"
                ),
                "measured_collision_clearance": False,
                "measured_calibration": False,
                "received_hardware_verified": False,
            },
        }

    def validate(self) -> None:
        self._validate_unsealed()
        if _hash(self._document()) != self._sealed_sha256:
            raise IntegratedZeroHardwareMissionError(
                "integrated mission report changed after construction"
            )

    def assert_matches_assembly(self, assembly: MultiActionMissionSpecV2) -> None:
        """Bind report receipts back to the exact immutable mission assembly."""

        self.validate()
        if type(assembly) is not MultiActionMissionSpecV2:
            raise TypeError("assembly must be exactly MultiActionMissionSpecV2")
        assembly.validate()
        if self.assembly_sha256 != assembly.assembly_sha256:
            raise IntegratedZeroHardwareMissionError(
                "integrated report belongs to another assembly"
            )
        if (
            self.expected_output_sha256 != assembly.plan.requested_text_sha256
            or self.expected_output_length != len(assembly.normalized_text)
            or self.runtime_final_state.session_id
            != assembly.dense_route.controller_session_id
            or self.runtime_final_state.config_sha256
            != assembly.dense_route.runtime_config.canonical_sha256
            or len(self.command_receipts) > assembly.command_count
        ):
            raise IntegratedZeroHardwareMissionError(
                "integrated report source/runtime identity differs from assembly"
            )
        for receipt, binding in zip(
            self.command_receipts,
            assembly.command_bindings,
        ):
            if (
                receipt.semantic_step_ordinal
                != binding.dense.semantic_step_ordinal
                or receipt.contact_occurrence_ordinal
                != binding.dense.contact_occurrence_ordinal
                or receipt.route_waypoint_ordinal
                != binding.dense.route_waypoint_ordinal
                or receipt.authorization_command_ordinal
                != binding.dense.authorization_command_ordinal
                or receipt.phase is not binding.dense.phase
                or receipt.mission_tail is not binding.dense.mission_tail
                or receipt.action_occurrence_sha256
                != binding.action_occurrence_sha256
                or receipt.non_wire_t104_command_sha256
                != binding.dense.command_sha256
                or receipt.authorization_receipt.context_sha256
                != assembly.authorization.evidence.context_sha256
                or receipt.authorization_receipt.command_sha256
                != binding.simulation_command.command_sha256
                or receipt.t104_trace_receipt.session_id
                != assembly.dense_route.controller_session_id
                or receipt.t104_trace_receipt.config_sha256
                != assembly.dense_route.runtime_config.canonical_sha256
                or receipt.t104_trace_receipt.schedule_sha256
                != assembly.dense_route.runtime_config.schedule_sha256
                or receipt.t104_trace_receipt.route_sha256
                != assembly.trajectory.report_hash
                or receipt.t104_trace_receipt.joint_result_sha256
                != binding.dense.joint_result_sha256
                or receipt.collision_binding_sha256
                != binding.collision.content_hash
                or receipt.camera_observation_sha256
                != binding.camera_observation_sha256
            ):
                raise IntegratedZeroHardwareMissionError(
                    "integrated command receipt differs from assembly command"
                )
        replay_runtime = InMemoryT104Runtime(assembly.dense_route.runtime_config)
        replay_permit = issue_ordered_simulation_permit(
            assembly.authorization.evidence,
            ttl_s=SYNTHETIC_PERMIT_TTL_S,
            now_monotonic=SYNTHETIC_ISSUANCE_MONOTONIC,
            interlock_max_age_s=SYNTHETIC_INTERLOCK_MAX_AGE_S,
        )
        replay_continuity = SyntheticInterlockContinuity(assembly.authorization)
        replayed_authorizations: list[SimulationCommandReceipt] = []
        replayed_traces: list[T104TraceReceipt] = []
        for binding in assembly.command_bindings[: len(self.command_receipts)]:
            sample = replay_continuity.next_sample()
            replayed_authorizations.append(
                replay_permit.consume_next(
                    ordinal=binding.dense.authorization_command_ordinal,
                    action_occurrence_id=binding.action_occurrence_sha256,
                    command=binding.simulation_command,
                    continuity=sample.continuity,
                    now_monotonic=sample.now_monotonic,
                )
            )
            replayed_trace = replay_runtime.execute(binding.dense.command)
            replayed_traces.append(replayed_trace)
            if not replayed_trace.success:
                break
        if (
            tuple(replayed_authorizations)
            != tuple(item.authorization_receipt for item in self.command_receipts)
            or tuple(replayed_traces)
            != tuple(item.t104_trace_receipt for item in self.command_receipts)
            or replay_runtime.state_receipt() != self.runtime_final_state
        ):
            raise IntegratedZeroHardwareMissionError(
                "retained authorization/T104 receipts differ from deterministic replay"
            )
        expected_camera = tuple(
            item.observation_sha256
            for item in assembly.camera_observations.observations[
                : len(self.camera_observation_sha256s)
            ]
        )
        if self.camera_observation_sha256s != expected_camera:
            raise IntegratedZeroHardwareMissionError(
                "integrated camera receipts differ from assembly observations"
            )
        successful_authorization_ordinals = {
            item.authorization_command_ordinal
            for item in self.command_receipts
            if item.success
        }
        for route_slice in assembly.dense_route.contact_slices[
            : len(self.camera_observation_sha256s)
        ]:
            if (
                route_slice.final_hover_route_waypoint_ordinal - 1
                not in successful_authorization_ordinals
            ):
                raise IntegratedZeroHardwareMissionError(
                    "camera receipt precedes its successful final-hover command"
                )
        for contact_receipt in self.contact_receipts:
            route_slice = assembly.dense_route.contact_slices[
                contact_receipt.contact_occurrence_ordinal
            ]
            if (
                route_slice.contact_route_waypoint_ordinal - 1
                not in successful_authorization_ordinals
            ):
                raise IntegratedZeroHardwareMissionError(
                    "contact receipt precedes its successful contact command"
                )
        replay_device, replay_physical_count = build_virtual_device_model(
            assembly.bootstrap,
            assembly.plan,
            assembly.normalized_text,
        )
        if replay_physical_count != assembly.contact_count:
            raise IntegratedZeroHardwareMissionError(
                "virtual contact replay count differs from assembly"
            )
        replay_observer = VirtualTextOutcomeObserver(
            observer_id=f"{assembly.mission_id}-independent-outcome"
        )
        final_round = assembly.trajectory.final_round
        if final_round is None:
            raise IntegratedZeroHardwareMissionError(
                "assembly accepted trajectory has no final round"
            )
        trajectory_results = {
            item.waypoint_sequence: item for item in final_round.joint_results
        }
        contact_receipts_by_ordinal = {
            item.contact_occurrence_ordinal: item for item in self.contact_receipts
        }
        state_receipts_by_semantic = {
            item.semantic_step_ordinal: item
            for item in self.state_observation_receipts
        }

        # A state observation is an execution prerequisite, not merely another
        # optional receipt stream.  Require every earlier observation-only
        # semantic step before accepting *any* motion, camera, or contact
        # evidence for a later contact.  This explicit prefix check prevents a
        # forged report from deleting a phone-state check while retaining the
        # already executed motion that depended on it.
        observation_steps = tuple(
            item
            for item in assembly.semantic_schedule.steps
            if type(item) is PhoneStateObservationStep
        )

        def assert_observation_prerequisites(
            semantic_step_ordinal: int,
            evidence_label: str,
            *,
            include_later_observations: bool = False,
        ) -> None:
            required = tuple(
                item
                for item in observation_steps
                if include_later_observations
                or item.semantic_step_ordinal < semantic_step_ordinal
            )
            if any(
                (
                    receipt := state_receipts_by_semantic.get(
                        item.semantic_step_ordinal
                    )
                )
                is None
                or not receipt.passed
                for item in required
            ):
                raise IntegratedZeroHardwareMissionError(
                    f"{evidence_label} exists without every preceding "
                    "phone-state observation"
                )

        for command_receipt in self.command_receipts:
            assert_observation_prerequisites(
                command_receipt.semantic_step_ordinal,
                "motion command receipt",
                include_later_observations=command_receipt.mission_tail,
            )
        for contact_receipt in self.contact_receipts:
            assert_observation_prerequisites(
                contact_receipt.semantic_step_ordinal,
                "contact receipt",
            )
        for camera_index in range(len(self.camera_observation_sha256s)):
            camera_expectation = assembly.camera_observations.observations[
                camera_index
            ]
            assert_observation_prerequisites(
                camera_expectation.semantic_step_ordinal,
                "camera observation receipt",
            )

        execution_gap_seen = False
        replayed_contact_count = 0
        replayed_state_count = 0
        last_replayed_contact_ordinal: int | None = None
        for semantic_step in assembly.semantic_schedule.steps:
            if type(semantic_step) is PhoneStateObservationStep:
                state_receipt = state_receipts_by_semantic.get(
                    semantic_step.semantic_step_ordinal
                )
                if state_receipt is None:
                    execution_gap_seen = True
                    continue
                if execution_gap_seen or type(replay_device) is not VirtualAndroid:
                    raise IntegratedZeroHardwareMissionError(
                        "state-observation receipts are not a semantic execution prefix"
                    )
                if last_replayed_contact_ordinal is not None:
                    prior_slice = assembly.dense_route.contact_slices[
                        last_replayed_contact_ordinal
                    ]
                    prior_retract_ordinal = (
                        prior_slice.final_retract_route_waypoint_ordinal - 1
                    )
                    prior_retract = next(
                        (
                            item
                            for item in self.command_receipts
                            if item.authorization_command_ordinal
                            == prior_retract_ordinal
                        ),
                        None,
                    )
                    if (
                        prior_retract is None
                        or not prior_retract.success
                        or ActionJournalState.RETRACTED
                        not in tuple(
                            event.state
                            for event in self.journal_snapshots[
                                last_replayed_contact_ordinal
                            ].events
                        )
                    ):
                        raise IntegratedZeroHardwareMissionError(
                            "post-contact state observation precedes durable retraction"
                        )
                observed_state = replay_device.ui_state
                observed_state_hash = replay_device.state_hash
                observed_pass = replay_device.verify_ui_state(semantic_step.state_id)
                if (
                    state_receipt.required_state != semantic_step.state_id
                    or state_receipt.observed_state != observed_state
                    or state_receipt.device_state_before_sha256
                    != observed_state_hash
                    or state_receipt.passed is not observed_pass
                ):
                    raise IntegratedZeroHardwareMissionError(
                        "integrated state receipt differs from chronological device truth"
                    )
                replayed_state_count += 1
                continue

            if type(semantic_step) is not ContactSemanticStep:
                raise IntegratedZeroHardwareMissionError(
                    "semantic replay encountered an unsupported step type"
                )
            contact_ordinal = semantic_step.contact_occurrence_ordinal
            chronological_contact_receipt = contact_receipts_by_ordinal.get(
                contact_ordinal
            )
            if chronological_contact_receipt is None:
                execution_gap_seen = True
                continue
            if execution_gap_seen:
                raise IntegratedZeroHardwareMissionError(
                    "contact receipts are not a semantic execution prefix"
                )
            occurrence = assembly.occurrences[contact_ordinal]
            route_slice = assembly.dense_route.contact_slices[contact_ordinal]
            result = trajectory_results[route_slice.contact_route_waypoint_ordinal]
            replay_event = ContactEvent(
                action_index=semantic_step.semantic_step_ordinal,
                achieved_board_xyz_mm=result.achieved_tip_position_board_mm,
                achieved_contact_normal_board=(
                    -result.achieved_hand_tcp_z_axis_board[0],
                    -result.achieved_hand_tcp_z_axis_board[1],
                    -result.achieved_hand_tcp_z_axis_board[2],
                ),
                dwell_ticks=VIRTUAL_CONTACT_DWELL_TICKS,
                activation_count=1,
            )
            replay_result = replay_device.apply_contact(replay_event)
            replay_snapshot = replay_observer.consume(replay_result)
            if (
                chronological_contact_receipt.semantic_step_ordinal
                != semantic_step.semantic_step_ordinal
                or chronological_contact_receipt.contact_occurrence_ordinal
                != contact_ordinal
                or chronological_contact_receipt.target_id != semantic_step.target_id
                or chronological_contact_receipt.resolved_target_id
                != f"{assembly.plan.device.value}:{semantic_step.target_id}"
                or chronological_contact_receipt.action_occurrence_sha256
                != occurrence.occurrence_hash
                or chronological_contact_receipt.contact_event_sha256
                != replay_event.event_hash
                or chronological_contact_receipt.contact_result_sha256
                != replay_result.result_hash
                or chronological_contact_receipt.observer_snapshot_sha256
                != replay_snapshot.snapshot_hash
            ):
                raise IntegratedZeroHardwareMissionError(
                    "integrated contact receipt differs from assembly occurrence"
                )
            replayed_contact_count += 1
            last_replayed_contact_ordinal = contact_ordinal
        if (
            replayed_contact_count != len(self.contact_receipts)
            or replayed_state_count != len(self.state_observation_receipts)
        ):
            raise IntegratedZeroHardwareMissionError(
                "semantic replay did not consume every state/contact receipt"
            )
        if (
            self.observed_output_sha256 != replay_observer.output_sha256
            or self.observed_output_length != replay_observer.output_length
        ):
            raise IntegratedZeroHardwareMissionError(
                "integrated output evidence differs from independent contact replay"
            )
        if tuple(item.occurrence for item in self.journal_snapshots) != assembly.occurrences:
            raise IntegratedZeroHardwareMissionError(
                "integrated journal snapshots differ from assembly occurrences"
            )
        for contact_ordinal, route_slice in enumerate(
            assembly.dense_route.contact_slices
        ):
            owned_receipts = tuple(
                item
                for item in self.command_receipts
                if item.contact_occurrence_ordinal == contact_ordinal
            )
            journal_states = tuple(
                item.state for item in self.journal_snapshots[contact_ordinal].events
            )
            camera_recorded = contact_ordinal < len(
                self.camera_observation_sha256s
            )
            contact_recorded = contact_ordinal < len(self.contact_receipts)
            if any(
                item.phase
                in {MotionPhase.APPROACH, MotionPhase.CONTACT, MotionPhase.RETRACT}
                for item in owned_receipts
            ) and not camera_recorded:
                raise IntegratedZeroHardwareMissionError(
                    "approach-or-later command has no prior camera receipt"
                )
            contact_authorization = route_slice.contact_route_waypoint_ordinal - 1
            contact_command = next(
                (
                    item
                    for item in owned_receipts
                    if item.authorization_command_ordinal == contact_authorization
                ),
                None,
            )
            durable_pre_contact = ActionJournalState.PRE_CONTACT in journal_states
            durable_contact_boundary = (
                ActionJournalState.CONTACT_MAY_HAVE_OCCURRED in journal_states
            )
            if durable_pre_contact or durable_contact_boundary:
                successful_before_contact = tuple(
                    item.authorization_command_ordinal
                    for item in self.command_receipts
                    if item.success
                    and item.authorization_command_ordinal < contact_authorization
                )
                if (
                    not camera_recorded
                    or successful_before_contact
                    != tuple(range(contact_authorization))
                ):
                    raise IntegratedZeroHardwareMissionError(
                        "durable contact frontier leads its successful command/camera prefix"
                    )
            if contact_command is not None and not {
                ActionJournalState.PRE_CONTACT,
                ActionJournalState.CONTACT_MAY_HAVE_OCCURRED,
            }.issubset(journal_states):
                raise IntegratedZeroHardwareMissionError(
                    "contact attempt lacks its durable contact-boundary journal states"
                )
            outcome_confirmed = ActionJournalState.OUTCOME_CONFIRMED in journal_states
            if outcome_confirmed is not contact_recorded:
                raise IntegratedZeroHardwareMissionError(
                    "durable confirmed outcome differs from contact receipt coverage"
                )
            if contact_recorded:
                if (
                    contact_command is None
                    or not contact_command.success
                    or ActionJournalState.OUTCOME_CONFIRMED not in journal_states
                ):
                    raise IntegratedZeroHardwareMissionError(
                        "contact receipt lacks successful contact/outcome evidence"
                    )
            elif contact_command is not None and (
                self.journal_snapshots[contact_ordinal].current_state
                is not ActionJournalState.OUTCOME_UNCERTAIN
            ):
                raise IntegratedZeroHardwareMissionError(
                    "unconfirmed contact attempt is not durably outcome-uncertain"
                )
            retract_receipts = tuple(
                item for item in owned_receipts if item.phase is MotionPhase.RETRACT
            )
            if retract_receipts and not contact_recorded:
                raise IntegratedZeroHardwareMissionError(
                    "retract command exists without a confirmed contact outcome"
                )
            final_retract_authorization = (
                route_slice.final_retract_route_waypoint_ordinal - 1
            )
            final_retract = next(
                (
                    item
                    for item in retract_receipts
                    if item.authorization_command_ordinal
                    == final_retract_authorization
                ),
                None,
            )
            retained_fault = self.fault_receipt
            exact_retraction_commit_fault = bool(
                retained_fault is not None
                and retained_fault.source_class == _FAULT_SOURCE_COORDINATOR
                and retained_fault.stage == "RETRACTION_COMMIT"
                and retained_fault.fault_kind == _COORDINATOR_FAULT_KIND
                and retained_fault.semantic_step_ordinal
                == route_slice.semantic_step_ordinal
                and retained_fault.contact_occurrence_ordinal == contact_ordinal
                and retained_fault.authorization_command_ordinal
                == final_retract_authorization
            )
            if final_retract is not None and final_retract.success and (
                ActionJournalState.RETRACTED not in journal_states
            ) and not exact_retraction_commit_fault:
                raise IntegratedZeroHardwareMissionError(
                    "successful final retract lacks durable retracted state"
                )
            if any(item.mission_tail for item in owned_receipts) and (
                ActionJournalState.RETRACTED not in journal_states
            ):
                raise IntegratedZeroHardwareMissionError(
                    "mission-tail command precedes durable final retraction"
                )
            if contact_ordinal + 1 < assembly.contact_count and any(
                item.contact_occurrence_ordinal == contact_ordinal + 1
                for item in self.command_receipts
            ) and ActionJournalState.RETRACTED not in journal_states:
                raise IntegratedZeroHardwareMissionError(
                    "next contact command group precedes prior durable retraction"
                )

        terminal_event_times = tuple(
            item.events[-1].event_time_ns for item in self.journal_snapshots
        )
        if any(
            right <= left
            for left, right in zip(terminal_event_times, terminal_event_times[1:])
        ):
            raise IntegratedZeroHardwareMissionError(
                "journal terminal events do not follow contact-occurrence order"
            )
        maximum_intent_time = max(
            item.events[0].event_time_ns for item in self.journal_snapshots
        )
        if any(
            event.event_time_ns <= maximum_intent_time
            for snapshot in self.journal_snapshots
            for event in snapshot.events[1:]
        ):
            raise IntegratedZeroHardwareMissionError(
                "journal lifecycle event predates completion of intent setup"
            )
        for left, right in zip(
            self.journal_snapshots,
            self.journal_snapshots[1:],
        ):
            left_retract = next(
                (
                    event
                    for event in left.events
                    if event.state is ActionJournalState.RETRACTED
                ),
                None,
            )
            right_pre_contact = next(
                (
                    event
                    for event in right.events
                    if event.state is ActionJournalState.PRE_CONTACT
                ),
                None,
            )
            if (
                right_pre_contact is not None
                and (
                    left_retract is None
                    or right_pre_contact.event_time_ns <= left_retract.event_time_ns
                )
            ):
                raise IntegratedZeroHardwareMissionError(
                    "journal contact lifecycles are not chronologically serialized"
                )
        command_receipts_by_authorization = {
            item.authorization_command_ordinal: item
            for item in self.command_receipts
        }
        bindings_by_authorization = {
            item.dense.authorization_command_ordinal: item
            for item in assembly.command_bindings
        }

        # A precommitted camera fault is part of the immutable program.  A
        # report may stop before reaching it for an independent earlier fault,
        # but it may never contain evidence that crossed the scheduled capture
        # boundary.  Enforce this globally instead of only when the final
        # receipt happens to look like a camera fault.
        scheduled_camera_fault = assembly.camera_fault_injection
        if scheduled_camera_fault is not None:
            scheduled_contact = (
                scheduled_camera_fault.contact_occurrence_ordinal
            )
            scheduled_slice = assembly.dense_route.contact_slices[
                scheduled_contact
            ]
            maximum_command_count = (
                scheduled_slice.final_hover_route_waypoint_ordinal
            )
            if (
                len(self.command_receipts) > maximum_command_count
                or len(self.camera_observation_sha256s) > scheduled_contact
                or len(self.contact_receipts) > scheduled_contact
            ):
                raise IntegratedZeroHardwareMissionError(
                    "execution evidence crossed the precommitted camera-fault boundary"
                )

        # Derive the component that could have failed from the immutable
        # execution frontier.  A failed final T104 receipt is necessarily a
        # controller fault.  A successful final-HOVER prefix with the next
        # observation still absent is necessarily the replay-camera capture
        # boundary in this coordinator.  This prevents a caller from relabeling
        # the cause merely by replacing human-readable fault text.
        fault = self.fault_receipt
        if fault is not None:
            final_command = (
                None if not self.command_receipts else self.command_receipts[-1]
            )
            runtime_fault_frontier = (
                final_command is not None and not final_command.success
            )
            camera_fault_frontier = False
            next_camera_observation = None
            if len(self.camera_observation_sha256s) < assembly.contact_count:
                next_camera_observation = assembly.camera_observations.observations[
                    len(self.camera_observation_sha256s)
                ]
                camera_fault_frontier = bool(
                    final_command is not None
                    and final_command.success
                    and final_command.phase is MotionPhase.HOVER
                    and final_command.authorization_command_ordinal
                    == next_camera_observation.authorization_command_ordinal
                    and final_command.route_waypoint_ordinal
                    == next_camera_observation.route_waypoint_ordinal
                    and len(self.contact_receipts)
                    == next_camera_observation.contact_occurrence_ordinal
                )

            if runtime_fault_frontier:
                if (
                    fault.source_class != _FAULT_SOURCE_RUNTIME
                    or final_command is None
                    or fault.source_evidence_sha256
                    != final_command.t104_trace_receipt_sha256
                    or fault.fault_kind != final_command.fault_kind
                    or fault.semantic_step_ordinal
                    != final_command.semantic_step_ordinal
                    or fault.contact_occurrence_ordinal
                    != final_command.contact_occurrence_ordinal
                    or fault.authorization_command_ordinal
                    != final_command.authorization_command_ordinal
                ):
                    raise IntegratedZeroHardwareMissionError(
                        "structured controller fault differs from the failed trace"
                    )
            elif camera_fault_frontier:
                camera_source = fault.camera_fault_receipt
                expected_fault_injection = assembly.camera_fault_injection
                if (
                    next_camera_observation is None
                    or fault.semantic_step_ordinal
                    != next_camera_observation.semantic_step_ordinal
                    or fault.contact_occurrence_ordinal
                    != next_camera_observation.contact_occurrence_ordinal
                    or fault.authorization_command_ordinal
                    != next_camera_observation.authorization_command_ordinal
                ):
                    raise IntegratedZeroHardwareMissionError(
                        "structured camera fault differs from the capture frontier"
                    )
                scheduled_here = bool(
                    expected_fault_injection is not None
                    and expected_fault_injection.contact_occurrence_ordinal
                    == next_camera_observation.contact_occurrence_ordinal
                )
                expected_boundary_source = (
                    _observation_boundary_fault_source_sha256(
                        assembly_sha256=assembly.assembly_sha256,
                        semantic_step_ordinal=(
                            next_camera_observation.semantic_step_ordinal
                        ),
                        contact_occurrence_ordinal=(
                            next_camera_observation.contact_occurrence_ordinal
                        ),
                        authorization_command_ordinal=(
                            next_camera_observation.authorization_command_ordinal
                        ),
                        command_receipt_count=len(self.command_receipts),
                        camera_observation_count=len(
                            self.camera_observation_sha256s
                        ),
                        state_observation_count=len(
                            self.state_observation_receipts
                        ),
                        contact_receipt_count=len(self.contact_receipts),
                    )
                )
                if not (
                    fault.source_class == _FAULT_SOURCE_OBSERVATION_BOUNDARY
                    and fault.stage == _OBSERVATION_BOUNDARY_STAGE
                    and fault.fault_kind == _OBSERVATION_BOUNDARY_FAULT_KIND
                    and fault.source_evidence_sha256
                    == expected_boundary_source
                ):
                    raise IntegratedZeroHardwareMissionError(
                        "observation-boundary fault differs from its call frontier"
                    )
                if camera_source is not None and not (
                    scheduled_here
                    and expected_fault_injection is not None
                    and type(camera_source) is B0477ReplayFaultReceipt
                    and camera_source.fault_kind
                    is expected_fault_injection.fault_kind
                    and camera_source.observation_set_sha256
                    == assembly.camera_observations.canonical_sha256
                    and camera_source.fault_injection_sha256
                    == expected_fault_injection.canonical_sha256
                    and camera_source.expected_observation_sha256
                    == next_camera_observation.observation_sha256
                    and camera_source.semantic_step_ordinal
                    == next_camera_observation.semantic_step_ordinal
                    and camera_source.contact_occurrence_ordinal
                    == next_camera_observation.contact_occurrence_ordinal
                    and camera_source.target_id
                    == next_camera_observation.target_id
                    and camera_source.route_waypoint_ordinal
                    == next_camera_observation.route_waypoint_ordinal
                    and camera_source.authorization_command_ordinal
                    == next_camera_observation.authorization_command_ordinal
                    and camera_source.settled_controller_pose_sha256
                    == next_camera_observation.expected_settled_controller_pose_sha256
                ):
                    raise IntegratedZeroHardwareMissionError(
                        "camera fault diagnostic differs from the precommitted schedule"
                    )
            elif fault.source_class != _FAULT_SOURCE_COORDINATOR:
                raise IntegratedZeroHardwareMissionError(
                    "structured fault source differs from the execution frontier"
                )
            else:
                stage = fault.stage
                actual_ordinals = (
                    fault.semantic_step_ordinal,
                    fault.contact_occurrence_ordinal,
                    fault.authorization_command_ordinal,
                )
                if stage in {
                    "CONTACT_JOURNAL_BOUNDARY",
                    "PRE_COMMAND_FAILURE",
                }:
                    if len(self.command_receipts) >= assembly.command_count:
                        raise IntegratedZeroHardwareMissionError(
                            "coordinator pre-command stage has no next command"
                        )
                    next_binding = assembly.command_bindings[
                        len(self.command_receipts)
                    ].dense
                    expected_ordinals = (
                        next_binding.semantic_step_ordinal,
                        next_binding.contact_occurrence_ordinal,
                        next_binding.authorization_command_ordinal,
                    )
                    if actual_ordinals != expected_ordinals:
                        raise IntegratedZeroHardwareMissionError(
                            "coordinator pre-command fault ordinals differ from the frontier"
                        )
                    assert_observation_prerequisites(
                        next_binding.semantic_step_ordinal,
                        "coordinator pre-command fault",
                        include_later_observations=next_binding.mission_tail,
                    )
                    if (
                        stage == "CONTACT_JOURNAL_BOUNDARY"
                        and next_binding.phase is not MotionPhase.CONTACT
                    ):
                        raise IntegratedZeroHardwareMissionError(
                            "contact-journal fault is not at a contact command"
                        )
                    current_journal_states = tuple(
                        event.state
                        for event in self.journal_snapshots[
                            next_binding.contact_occurrence_ordinal
                        ].events
                    )
                    boundary_committed = (
                        ActionJournalState.CONTACT_MAY_HAVE_OCCURRED
                        in current_journal_states
                    )
                    if stage == "CONTACT_JOURNAL_BOUNDARY" and boundary_committed:
                        raise IntegratedZeroHardwareMissionError(
                            "contact-journal fault follows a completed boundary"
                        )
                    if (
                        stage == "PRE_COMMAND_FAILURE"
                        and next_binding.phase is MotionPhase.CONTACT
                        and not boundary_committed
                    ):
                        raise IntegratedZeroHardwareMissionError(
                            "contact command failure precedes its durable boundary"
                        )
                    contact_ordinal = next_binding.contact_occurrence_ordinal
                    current_states = tuple(
                        event.state
                        for event in self.journal_snapshots[contact_ordinal].events
                    )
                    camera_recorded = contact_ordinal < len(
                        self.camera_observation_sha256s
                    )
                    current_contact_receipt = contact_receipts_by_ordinal.get(
                        contact_ordinal
                    )
                    if (
                        stage == "PRE_COMMAND_FAILURE"
                        and next_binding.phase
                        in {
                            MotionPhase.APPROACH,
                            MotionPhase.CONTACT,
                            MotionPhase.RETRACT,
                        }
                        and not camera_recorded
                    ):
                        raise IntegratedZeroHardwareMissionError(
                            "coordinator command frontier crosses an unobserved approach"
                        )
                    if (
                        stage == "PRE_COMMAND_FAILURE"
                        and next_binding.phase is MotionPhase.RETRACT
                    ):
                        route_slice = assembly.dense_route.contact_slices[
                            contact_ordinal
                        ]
                        contact_command = command_receipts_by_authorization.get(
                            route_slice.contact_route_waypoint_ordinal - 1
                        )
                        if (
                            current_contact_receipt is None
                            or contact_command is None
                            or not contact_command.success
                            or ActionJournalState.OUTCOME_CONFIRMED
                            not in current_states
                        ):
                            raise IntegratedZeroHardwareMissionError(
                                "retract command frontier precedes a confirmed contact outcome"
                            )
                    if (
                        stage == "PRE_COMMAND_FAILURE"
                        and contact_ordinal > 0
                        and next_binding.authorization_command_ordinal
                        == assembly.dense_route.contact_slices[
                            contact_ordinal
                        ].first_authorization_command_ordinal
                    ):
                        prior_states = tuple(
                            event.state
                            for event in self.journal_snapshots[
                                contact_ordinal - 1
                            ].events
                        )
                        if ActionJournalState.RETRACTED not in prior_states:
                            raise IntegratedZeroHardwareMissionError(
                                "next contact command group precedes durable prior retraction"
                            )
                    if (
                        stage == "PRE_COMMAND_FAILURE"
                        and next_binding.mission_tail
                        and ActionJournalState.RETRACTED not in current_states
                    ):
                        raise IntegratedZeroHardwareMissionError(
                            "mission-tail command precedes durable final retraction"
                        )
                elif stage in {
                    "CONTACT_POST_COMMAND",
                    "RETRACTION_COMMIT",
                }:
                    if not self.command_receipts:
                        raise IntegratedZeroHardwareMissionError(
                            "coordinator post-command stage has no prior command"
                        )
                    prior = self.command_receipts[-1]
                    expected_ordinals = (
                        prior.semantic_step_ordinal,
                        prior.contact_occurrence_ordinal,
                        prior.authorization_command_ordinal,
                    )
                    if actual_ordinals != expected_ordinals:
                        raise IntegratedZeroHardwareMissionError(
                            "coordinator post-command fault ordinals differ from the frontier"
                        )
                    expected_phase = (
                        MotionPhase.RETRACT
                        if stage == "RETRACTION_COMMIT"
                        else MotionPhase.CONTACT
                    )
                    if prior.phase is not expected_phase:
                        raise IntegratedZeroHardwareMissionError(
                            "coordinator post-command stage differs from command phase"
                        )
                    if stage == "CONTACT_POST_COMMAND":
                        prior_contact_states = tuple(
                            event.state
                            for event in self.journal_snapshots[
                                prior.contact_occurrence_ordinal
                            ].events
                        )
                        if (
                            prior.contact_occurrence_ordinal
                            in contact_receipts_by_ordinal
                            or ActionJournalState.OUTCOME_CONFIRMED
                            in prior_contact_states
                        ):
                            raise IntegratedZeroHardwareMissionError(
                                "contact-post-command fault follows a confirmed outcome"
                            )
                    else:
                        route_slice = assembly.dense_route.contact_slices[
                            prior.contact_occurrence_ordinal
                        ]
                        final_retract_authorization = (
                            route_slice.final_retract_route_waypoint_ordinal - 1
                        )
                        retract_states = tuple(
                            event.state
                            for event in self.journal_snapshots[
                                prior.contact_occurrence_ordinal
                            ].events
                        )
                        if (
                            prior.authorization_command_ordinal
                            != final_retract_authorization
                            or not assembly.command_bindings[
                                prior.authorization_command_ordinal
                            ].dense.phase_endpoint
                            or prior.contact_occurrence_ordinal
                            not in contact_receipts_by_ordinal
                            or ActionJournalState.OUTCOME_CONFIRMED
                            not in retract_states
                            or ActionJournalState.RETRACTED in retract_states
                        ):
                            raise IntegratedZeroHardwareMissionError(
                                "retraction-commit fault differs from the exact unpublished endpoint"
                            )
                elif stage == "SEMANTIC_OBSERVATION":
                    if (
                        fault.contact_occurrence_ordinal is not None
                        or fault.authorization_command_ordinal is not None
                    ):
                        raise IntegratedZeroHardwareMissionError(
                            "semantic-observation fault has motion/contact ordinals"
                        )
                    fault_semantic = fault.semantic_step_ordinal
                    target_observation = next(
                        (
                            item
                            for item in assembly.semantic_schedule.steps
                            if type(item) is PhoneStateObservationStep
                            and item.semantic_step_ordinal == fault_semantic
                        ),
                        None,
                    )
                    if target_observation is None:
                        raise IntegratedZeroHardwareMissionError(
                            "semantic-observation fault does not identify an observation"
                        )
                    for prior_step in assembly.semantic_schedule.steps:
                        if (
                            prior_step.semantic_step_ordinal
                            >= target_observation.semantic_step_ordinal
                        ):
                            break
                        if type(prior_step) is PhoneStateObservationStep:
                            prior_state = state_receipts_by_semantic.get(
                                prior_step.semantic_step_ordinal
                            )
                            if prior_state is None or not prior_state.passed:
                                raise IntegratedZeroHardwareMissionError(
                                    "semantic-observation fault skips a prior state observation"
                                )
                            continue
                        if type(prior_step) is not ContactSemanticStep:
                            raise IntegratedZeroHardwareMissionError(
                                "semantic-observation frontier has an unsupported prior step"
                            )
                        prior_contact = contact_receipts_by_ordinal.get(
                            prior_step.contact_occurrence_ordinal
                        )
                        prior_slice = assembly.dense_route.contact_slices[
                            prior_step.contact_occurrence_ordinal
                        ]
                        prior_retract = command_receipts_by_authorization.get(
                            prior_slice.final_retract_route_waypoint_ordinal - 1
                        )
                        prior_journal_states = tuple(
                            item.state
                            for item in self.journal_snapshots[
                                prior_step.contact_occurrence_ordinal
                            ].events
                        )
                        if (
                            prior_contact is None
                            or prior_retract is None
                            or not prior_retract.success
                            or ActionJournalState.RETRACTED
                            not in prior_journal_states
                        ):
                            raise IntegratedZeroHardwareMissionError(
                                "semantic-observation fault skips an unfinished contact"
                            )
                    target_receipt = state_receipts_by_semantic.get(
                        target_observation.semantic_step_ordinal
                    )
                    allowed_state_semantics = {
                        item.semantic_step_ordinal
                        for item in assembly.semantic_schedule.steps
                        if type(item) is PhoneStateObservationStep
                        and item.semantic_step_ordinal
                        < target_observation.semantic_step_ordinal
                    }
                    if target_receipt is not None:
                        if target_receipt.passed:
                            raise IntegratedZeroHardwareMissionError(
                                "semantic-observation fault follows a passing target observation"
                            )
                        allowed_state_semantics.add(
                            target_observation.semantic_step_ordinal
                        )
                    if set(state_receipts_by_semantic) != allowed_state_semantics:
                        raise IntegratedZeroHardwareMissionError(
                            "semantic-observation receipts differ from the exact semantic frontier"
                        )
                elif stage == "MISSION_FINALIZATION":
                    if (
                        actual_ordinals != (None, None, None)
                        or len(self.command_receipts) != assembly.command_count
                    ):
                        raise IntegratedZeroHardwareMissionError(
                            "mission-finalization fault differs from the terminal prefix"
                        )
                    assert_observation_prerequisites(
                        len(assembly.semantic_schedule.steps),
                        "mission-finalization fault",
                        include_later_observations=True,
                    )
                else:
                    raise IntegratedZeroHardwareMissionError(
                        "coordinator fault stage is not valid at this frontier"
                    )

        fault_evidence_sha256 = (
            None
            if fault is None
            else fault.receipt_sha256
        )
        final_trace_sha256 = (
            None
            if not self.command_receipts
            else self.command_receipts[-1].t104_trace_receipt_sha256
        )
        for contact_ordinal, journal_snapshot in enumerate(self.journal_snapshots):
            route_slice = assembly.dense_route.contact_slices[contact_ordinal]
            contact_authorization = route_slice.contact_route_waypoint_ordinal - 1
            contact_binding = bindings_by_authorization[contact_authorization]
            expected_pre_contact = contact_binding.simulation_command.constraint_set_sha256
            expected_contact_boundary = _hash(
                {
                    "authorization_command_sha256": (
                        contact_binding.simulation_command.command_sha256
                    ),
                    "non_wire_t104_command_sha256": (
                        contact_binding.dense.command_sha256
                    ),
                },
                64 * 1024,
            )
            retract_authorization = (
                route_slice.final_retract_route_waypoint_ordinal - 1
            )
            retract_receipt = command_receipts_by_authorization.get(
                retract_authorization
            )
            for event in journal_snapshot.events:
                expected_evidence: str | None = None
                if event.state is ActionJournalState.PRE_CONTACT:
                    expected_evidence = expected_pre_contact
                elif event.state is ActionJournalState.CONTACT_MAY_HAVE_OCCURRED:
                    expected_evidence = expected_contact_boundary
                elif event.state is ActionJournalState.RETRACTED:
                    if retract_receipt is None or not retract_receipt.success:
                        raise IntegratedZeroHardwareMissionError(
                            "retracted journal has no successful retract trace"
                        )
                    expected_evidence = retract_receipt.t104_trace_receipt_sha256
                elif event.state is ActionJournalState.PARKED:
                    if final_trace_sha256 is None:
                        raise IntegratedZeroHardwareMissionError(
                            "parked journal has no final controller trace"
                        )
                    expected_evidence = final_trace_sha256
                elif event.state in {
                    ActionJournalState.FAULTED,
                    ActionJournalState.OUTCOME_UNCERTAIN,
                }:
                    if fault_evidence_sha256 is None:
                        raise IntegratedZeroHardwareMissionError(
                            "faulted journal has no mission fault evidence"
                        )
                    expected_evidence = fault_evidence_sha256
                if (
                    expected_evidence is not None
                    and event.evidence_sha256 != expected_evidence
                ):
                    raise IntegratedZeroHardwareMissionError(
                        "journal transition evidence differs from mission execution"
                    )
        expected_runtime_pose = (
            assembly.dense_route.initial_controller_pose
            if not self.command_receipts
            else self.command_receipts[-1].t104_trace_receipt.state_after.current_pose
        )
        if self.runtime_final_state.current_pose != expected_runtime_pose:
            raise IntegratedZeroHardwareMissionError(
                "integrated runtime pose differs from the executed assembly prefix"
            )
        if self.completed and (
            len(self.command_receipts) != assembly.command_count
            or len(self.camera_observation_sha256s) != assembly.contact_count
            or len(self.contact_receipts) != assembly.contact_count
            or len(self.state_observation_receipts)
            != assembly.observation_only_step_count
        ):
            raise IntegratedZeroHardwareMissionError(
                "complete report does not cover the entire assembly"
            )
        if self.completed and assembly.camera_fault_injection is not None:
            raise IntegratedZeroHardwareMissionError(
                "complete report contradicts its precommitted camera fault schedule"
            )
        if any(
            snapshot.current_state is ActionJournalState.PARKED
            for snapshot in self.journal_snapshots
        ) and not (
            self.completed
            and len(self.command_receipts) == assembly.command_count
            and self.runtime_final_state.terminal
            and self.runtime_final_state.fault_latched is None
            and all(
                snapshot.current_state is ActionJournalState.PARKED
                for snapshot in self.journal_snapshots
            )
        ):
            raise IntegratedZeroHardwareMissionError(
                "PARKED journals require one fully completed terminal mission"
            )

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {**self._document(), "report_sha256": self._sealed_sha256}


def _trajectory_policy(park_xy: tuple[float, float]) -> TrajectorySimulationPolicy:
    return TrajectorySimulationPolicy(
        maximum_cartesian_step_mm=30.0,
        maximum_joint_step_rad=0.35,
        minimum_normalized_arm_joint_margin=0.01,
        maximum_refinement_rounds=2,
        maximum_waypoints_per_round=256,
        maximum_total_ik_solves=512,
        maximum_route_targets=8,
        park_xy_board_mm=park_xy,
    )


def assemble_default_zero_hardware_mission_v2(
    workspace_root: Path,
    device: str,
    requested_text: str,
    *,
    mission_id: str | None = None,
    controller_session_id: str | None = None,
    camera_starting_sequence: int = 1,
    t104_fault_injections: Sequence[T104FaultInjection] = (),
    camera_fault_injection: B0477ReplayFaultInjection | None = None,
) -> MultiActionMissionSpecV2:
    """Build every synthetic component for one bounded default mission."""

    workspace = Path(workspace_root).resolve()
    normalized = normalize_line_endings(requested_text)
    plan = compile_development_text(device, normalized)
    bootstrap = bootstrap_virtual_workcell(workspace)
    profile = load_virtual_commissioning_profile(
        cast(VirtualProfileContext, bootstrap.context)
    )
    selected_mission = (
        f"{device}-mission-{plan.plan_hash[:16]}"
        if mission_id is None
        else mission_id
    )
    selected_session = (
        f"{device}-t104-{plan.plan_hash[:16]}"
        if controller_session_id is None
        else controller_session_id
    )
    semantic = build_semantic_step_schedule(plan)
    park = profile.park_point_board
    trajectory = run_trajectory_simulation(
        bootstrap.context,
        plan,
        profile.study_input,
        _trajectory_policy((park.x, park.y)),
    )
    dense = build_dense_route_schedule(
        mission_id=selected_mission,
        controller_session_id=selected_session,
        semantic_schedule=semantic,
        trajectory=trajectory,
        fault_injections=t104_fault_injections,
    )
    observations = rehearse_b0477_mission_observations(
        workspace,
        semantic_schedule=semantic,
        dense_route_schedule=dense,
        starting_sequence=camera_starting_sequence,
    )
    collision = build_isolated_static_mission_fixture(workspace, trajectory)
    virtual_device, physical_count = build_virtual_device_model(
        bootstrap,
        plan,
        normalized,
    )
    if physical_count != semantic.contact_count:
        raise IntegratedZeroHardwareMissionError(
            "virtual device contact count differs from semantic schedule"
        )
    return assemble_zero_hardware_mission_v2(
        mission_id=selected_mission,
        bootstrap=bootstrap,
        plan=plan,
        normalized_text=normalized,
        semantic_schedule=semantic,
        trajectory=trajectory,
        dense_route=dense,
        camera_observations=observations,
        collision_fixture=collision,
        virtual_device=virtual_device,
        camera_fault_injection=camera_fault_injection,
    )


def prepare_zero_hardware_mission_v2(
    assembly: MultiActionMissionSpecV2,
    journal_root: Path,
    *,
    created_at_ns: int = 1_000_000,
) -> PreparedZeroHardwareMissionV2:
    """Create an individually atomic write-ahead journal for every contact.

    Publishing each journal is atomic, while publishing the complete set is
    intentionally fail-closed rather than transactional: an interrupted setup
    leaves an incomplete set that :func:`open_zero_hardware_mission_v2` rejects.
    """

    if type(assembly) is not MultiActionMissionSpecV2:
        raise TypeError("assembly must be exactly MultiActionMissionSpecV2")
    assembly.validate()
    if (
        type(created_at_ns) is not int
        or created_at_ns <= 0
        or created_at_ns
        > (2**63 - 1) - 10_000 - (8 * assembly.contact_count)
    ):
        raise IntegratedZeroHardwareMissionError(
            "created_at_ns lacks bounded headroom for the complete journal lifecycle"
        )
    root = Path(journal_root)
    if not root.exists():
        root.mkdir(parents=True, exist_ok=False)
    if root.is_symlink() or not root.is_dir():
        raise IntegratedZeroHardwareMissionError(
            "journal_root must be a real directory"
        )
    root = root.resolve()
    if any(root.iterdir()):
        raise IntegratedZeroHardwareMissionError(
            "new integrated journal_root must be empty"
        )
    _write_journal_set_manifest(root, assembly)
    journals = tuple(
        ZeroAuthorityMissionJournal.create(
            root,
            occurrence,
            created_at_ns=created_at_ns + index,
        )
        for index, occurrence in enumerate(assembly.occurrences)
    )
    return PreparedZeroHardwareMissionV2(assembly, journals)


def open_zero_hardware_mission_v2(
    assembly: MultiActionMissionSpecV2,
    journal_root: Path,
) -> PreparedZeroHardwareMissionV2:
    """Reconstruct exact journals without allowing automatic contact retry."""

    if type(assembly) is not MultiActionMissionSpecV2:
        raise TypeError("assembly must be exactly MultiActionMissionSpecV2")
    assembly.validate()
    selected_root = Path(journal_root)
    if selected_root.is_symlink():
        raise IntegratedZeroHardwareMissionError("journal root is unavailable")
    root = selected_root.resolve()
    if not root.is_dir():
        raise IntegratedZeroHardwareMissionError("journal root is unavailable")
    expected_journal_ids = _verify_journal_set_directory(root, assembly)
    opened: dict[str, ZeroAuthorityMissionJournal] = {}
    for journal_id in expected_journal_ids:
        child = root / journal_id
        journal = ZeroAuthorityMissionJournal.open(child)
        occurrence_id = journal.snapshot().occurrence.occurrence_id
        if occurrence_id in opened:
            raise IntegratedZeroHardwareMissionError("duplicate occurrence journal")
        opened[occurrence_id] = journal
    expected_ids = tuple(item.occurrence_id for item in assembly.occurrences)
    if set(opened) != set(expected_ids):
        raise IntegratedZeroHardwareMissionError(
            "journal directory does not exactly cover this assembly"
        )
    return PreparedZeroHardwareMissionV2(
        assembly,
        tuple(opened[value] for value in expected_ids),
    )


def _authorization_receipt_hash(receipt: SimulationCommandReceipt) -> str:
    return canonical_record_sha256(receipt.to_dict())


def _safe_fault_detail(exc: BaseException) -> str:
    try:
        class_name = type(exc).__name__
        if type(class_name) is not str or not class_name:
            class_name = "UNIDENTIFIED_EXCEPTION"
    except BaseException:
        # Exception classes can have hostile/broken metaclasses.  Diagnostic
        # rendering must never run ahead of durable journal terminalization.
        class_name = "UNIDENTIFIED_EXCEPTION"
    try:
        rendered = str(exc)
    except BaseException:
        rendered = "UNPRINTABLE_EXCEPTION_DETAIL"
    try:
        message = " ".join(rendered.split())[:256]
    except BaseException:
        message = "UNPRINTABLE_EXCEPTION_DETAIL"
    try:
        return f"{class_name}:{message or 'NO_DETAIL'}"
    except BaseException:
        return "UNIDENTIFIED_EXCEPTION:UNPRINTABLE_EXCEPTION_DETAIL"


def run_zero_hardware_mission_v2(
    prepared: PreparedZeroHardwareMissionV2,
) -> IntegratedZeroHardwareMissionReport:
    """Run the exact dense schedule and return redacted, zero-authority evidence."""

    if type(prepared) is not PreparedZeroHardwareMissionV2:
        raise TypeError("prepared must be exactly PreparedZeroHardwareMissionV2")
    prepared.__post_init__()
    assembly = prepared.assembly
    initial_snapshots = tuple(journal.snapshot() for journal in prepared.journals)
    unsafe_restart = tuple(
        snapshot
        for snapshot in initial_snapshots
        if snapshot.current_state is not ActionJournalState.INTENT_COMMITTED
    )
    if unsafe_restart:
        dispositions = ",".join(
            snapshot.recovery_disposition.value for snapshot in unsafe_restart
        )
        raise IntegratedZeroHardwareMissionError(
            "automatic integrated restart is refused; inspect journals: "
            + dispositions
        )

    device, physical_count = build_virtual_device_model(
        assembly.bootstrap,
        assembly.plan,
        assembly.normalized_text,
    )
    if physical_count != assembly.contact_count:
        raise IntegratedZeroHardwareMissionError("runtime virtual device count drifted")
    current_safety = DeviceSafetyContext.from_device(
        device,
        source_device=assembly.plan.device,
        profile_id=assembly.plan.profile_id,
    )
    if current_safety != assembly.device_safety_context:
        raise IntegratedZeroHardwareMissionError("runtime device safety context drifted")

    observer = VirtualTextOutcomeObserver(
        observer_id=f"{assembly.mission_id}-independent-outcome"
    )
    runtime = InMemoryT104Runtime(assembly.dense_route.runtime_config)
    camera_port = B0477ReplayCameraPort(
        assembly.camera_observations,
        fault_injection=assembly.camera_fault_injection,
    )
    permit = issue_ordered_simulation_permit(
        assembly.authorization.evidence,
        ttl_s=SYNTHETIC_PERMIT_TTL_S,
        now_monotonic=SYNTHETIC_ISSUANCE_MONOTONIC,
        interlock_max_age_s=SYNTHETIC_INTERLOCK_MAX_AGE_S,
    )
    continuity = SyntheticInterlockContinuity(assembly.authorization)
    command_receipts: list[IntegratedCommandReceipt] = []
    camera_receipts: list[str] = []
    state_receipts: list[IntegratedStateObservationReceipt] = []
    contact_receipts: list[IntegratedContactReceipt] = []
    event_time = max(item.events[-1].event_time_ns for item in initial_snapshots) + 1000
    fault_receipt: IntegratedFaultReceipt | None = None
    fault_detail: str | None = None
    active_stage = "MISSION_FINALIZATION"
    active_semantic_step_ordinal: int | None = None
    active_contact_occurrence_ordinal: int | None = None
    active_authorization_command_ordinal: int | None = None
    semantic_cursor = 0
    final_round = assembly.trajectory.final_round
    if final_round is None:
        raise IntegratedZeroHardwareMissionError("accepted final trajectory vanished")
    result_by_route = {
        item.waypoint_sequence: item for item in final_round.joint_results
    }

    def next_event_time() -> int:
        nonlocal event_time
        event_time += 1
        return event_time

    def verify_observations_until_contact(expected_semantic: int | None) -> None:
        nonlocal active_authorization_command_ordinal
        nonlocal active_contact_occurrence_ordinal
        nonlocal active_semantic_step_ordinal
        nonlocal active_stage
        nonlocal semantic_cursor
        while semantic_cursor < len(assembly.semantic_schedule.steps):
            step = assembly.semantic_schedule.steps[semantic_cursor]
            if type(step) is ContactSemanticStep:
                if expected_semantic is None or step.semantic_step_ordinal != expected_semantic:
                    break
                return
            if type(step) is not PhoneStateObservationStep or type(device) is not VirtualAndroid:
                raise _MissionAbort("semantic observation has no Android observer")
            active_stage = "SEMANTIC_OBSERVATION"
            active_semantic_step_ordinal = step.semantic_step_ordinal
            active_contact_occurrence_ordinal = None
            active_authorization_command_ordinal = None
            observed = device.ui_state
            receipt = IntegratedStateObservationReceipt(
                semantic_step_ordinal=step.semantic_step_ordinal,
                required_state=step.state_id,
                observed_state=observed,
                device_state_before_sha256=device.state_hash,
                passed=device.verify_ui_state(step.state_id),
            )
            state_receipts.append(receipt)
            if not receipt.passed:
                raise _MissionAbort(
                    f"phone state verification failed at semantic {semantic_cursor}"
                )
            semantic_cursor += 1

    def execute_command(binding: MissionV2CommandBinding) -> T104TraceReceipt:
        nonlocal active_authorization_command_ordinal
        nonlocal active_contact_occurrence_ordinal
        nonlocal active_semantic_step_ordinal
        nonlocal active_stage
        active_semantic_step_ordinal = binding.dense.semantic_step_ordinal
        active_contact_occurrence_ordinal = (
            binding.dense.contact_occurrence_ordinal
        )
        active_authorization_command_ordinal = (
            binding.dense.authorization_command_ordinal
        )
        # Until a standalone attempt receipt exists, authorization and a
        # raised-without-trace runtime call share one honest coarse stage.
        active_stage = "PRE_COMMAND_FAILURE"
        current = DeviceSafetyContext.from_device(
            device,
            source_device=assembly.plan.device,
            profile_id=assembly.plan.profile_id,
        )
        if current != assembly.device_safety_context:
            raise _MissionAbort("device safety context changed during permit")
        sample = continuity.next_sample()
        if sample.command_ordinal != binding.dense.authorization_command_ordinal:
            raise _MissionAbort("continuity ordinal differs from dense command")
        authorization_receipt = permit.consume_next(
            ordinal=binding.dense.authorization_command_ordinal,
            action_occurrence_id=binding.action_occurrence_sha256,
            command=binding.simulation_command,
            continuity=sample.continuity,
            now_monotonic=sample.now_monotonic,
        )
        trace = runtime.execute(binding.dense.command)
        command_receipts.append(
            IntegratedCommandReceipt(
                semantic_step_ordinal=binding.dense.semantic_step_ordinal,
                contact_occurrence_ordinal=(
                    binding.dense.contact_occurrence_ordinal
                ),
                route_waypoint_ordinal=binding.dense.route_waypoint_ordinal,
                authorization_command_ordinal=(
                    binding.dense.authorization_command_ordinal
                ),
                phase=binding.dense.phase,
                mission_tail=binding.dense.mission_tail,
                action_occurrence_sha256=binding.action_occurrence_sha256,
                non_wire_t104_command_sha256=binding.dense.command_sha256,
                authorization_receipt=authorization_receipt,
                t104_trace_receipt=trace,
                collision_binding_sha256=binding.collision.content_hash,
                camera_observation_sha256=binding.camera_observation_sha256,
                success=trace.success,
                fault_kind=trace.fault_kind,
            )
        )
        if not trace.success:
            raise _MissionAbort(f"T104 emulator fault {trace.fault_kind}")
        return trace

    try:
        for slice_ in assembly.dense_route.contact_slices:
            verify_observations_until_contact(slice_.semantic_step_ordinal)
            step = assembly.semantic_schedule.steps[semantic_cursor]
            if (
                type(step) is not ContactSemanticStep
                or step.contact_occurrence_ordinal
                != slice_.contact_occurrence_ordinal
            ):
                raise _MissionAbort("semantic/contact schedule join changed")
            journal = prepared.journals[slice_.contact_occurrence_ordinal]
            expected_camera = assembly.camera_observations.observations[
                slice_.contact_occurrence_ordinal
            ]
            if (
                expected_camera.semantic_step_ordinal != slice_.semantic_step_ordinal
                or expected_camera.contact_occurrence_ordinal
                != slice_.contact_occurrence_ordinal
                or expected_camera.target_id != slice_.target_id
                or expected_camera.route_waypoint_ordinal
                != slice_.final_hover_route_waypoint_ordinal
            ):
                raise _MissionAbort(
                    "B0477 observation differs from its semantic contact slice"
                )
            owned = tuple(
                item
                for item in assembly.command_bindings
                if item.dense.contact_occurrence_ordinal
                == slice_.contact_occurrence_ordinal
            )
            contact_motion = tuple(item for item in owned if not item.dense.mission_tail)
            mission_tail = tuple(item for item in owned if item.dense.mission_tail)
            camera_used = False
            contact_confirmed = False
            retracted = False
            for binding in contact_motion:
                if binding.dense.phase is MotionPhase.APPROACH and not camera_used:
                    raise _MissionAbort("approach attempted before final-hover observation")
                if binding.dense.phase is MotionPhase.CONTACT:
                    if not (binding.dense.phase_endpoint and camera_used):
                        raise _MissionAbort("contact is not the observed final endpoint")
                    active_semantic_step_ordinal = (
                        binding.dense.semantic_step_ordinal
                    )
                    active_contact_occurrence_ordinal = (
                        binding.dense.contact_occurrence_ordinal
                    )
                    active_authorization_command_ordinal = (
                        binding.dense.authorization_command_ordinal
                    )
                    active_stage = "CONTACT_JOURNAL_BOUNDARY"
                    journal.commit_pre_contact(
                        event_time_ns=next_event_time(),
                        route_sha256=binding.simulation_command.constraint_set_sha256,
                    )
                    journal.commit_contact_boundary(
                        event_time_ns=next_event_time(),
                        command_sha256=_hash(
                            {
                                "authorization_command_sha256": (
                                    binding.simulation_command.command_sha256
                                ),
                                "non_wire_t104_command_sha256": (
                                    binding.dense.command_sha256
                                ),
                            },
                            64 * 1024,
                        ),
                    )
                trace = execute_command(binding)
                if (
                    binding.dense.phase is MotionPhase.HOVER
                    and binding.dense.phase_endpoint
                ):
                    # The next two operations form one honestly coarse
                    # observation boundary unless the camera adapter emits its
                    # own sealed typed fault: first associate the settled hover
                    # feedback, then ask the camera port for the bound frame.
                    active_stage = _OBSERVATION_BOUNDARY_STAGE
                    if (
                        binding.dense.route_waypoint_ordinal
                        != expected_camera.route_waypoint_ordinal
                        or trace.feedback[-1].observed_pose_sha256
                        != expected_camera.expected_settled_controller_pose_sha256
                        or not trace.feedback[-1].settled
                    ):
                        raise _MissionAbort("B0477 hover pose/feedback association failed")
                    active_stage = "CAPTURE_AFTER_SETTLE"
                    captured_camera = camera_port.capture_after_settle(
                        semantic_step_ordinal=step.semantic_step_ordinal,
                        contact_occurrence_ordinal=(
                            slice_.contact_occurrence_ordinal
                        ),
                        target_id=step.target_id,
                        final_hover_route_waypoint_ordinal=(
                            binding.dense.route_waypoint_ordinal
                        ),
                        authorization_command_ordinal=(
                            binding.dense.authorization_command_ordinal
                        ),
                        just_settled_controller_pose_sha256=(
                            trace.feedback[-1].observed_pose_sha256
                        ),
                    )
                    if (
                        captured_camera.observation_sha256
                        != binding.camera_observation_sha256
                    ):
                        raise _MissionAbort(
                            "B0477 replay yielded the wrong bound observation"
                        )
                    camera_receipts.append(captured_camera.observation_sha256)
                    camera_used = True
                if binding.dense.phase is MotionPhase.CONTACT:
                    active_stage = "CONTACT_POST_COMMAND"
                    result = result_by_route[binding.dense.route_waypoint_ordinal]
                    event = ContactEvent(
                        action_index=step.semantic_step_ordinal,
                        achieved_board_xyz_mm=result.achieved_tip_position_board_mm,
                        achieved_contact_normal_board=(
                            -result.achieved_hand_tcp_z_axis_board[0],
                            -result.achieved_hand_tcp_z_axis_board[1],
                            -result.achieved_hand_tcp_z_axis_board[2],
                        ),
                        dwell_ticks=VIRTUAL_CONTACT_DWELL_TICKS,
                        activation_count=1,
                    )
                    contact_result = device.apply_contact(event)
                    observer_snapshot = observer.consume(contact_result)
                    expected_region = f"{assembly.plan.device.value}:{step.target_id}"
                    if (
                        not contact_result.accepted
                        or contact_result.resolved_target_id != expected_region
                    ):
                        raise _MissionAbort("virtual contact did not resolve intended target")
                    outcome_sha = _hash(
                        {
                            "occurrence_sha256": (
                                assembly.occurrences[
                                    slice_.contact_occurrence_ordinal
                                ].occurrence_hash
                            ),
                            "contact_result_sha256": contact_result.result_hash,
                            "observer_snapshot_sha256": observer_snapshot.snapshot_hash,
                            "resolved_target_id": contact_result.resolved_target_id,
                        },
                        128 * 1024,
                    )
                    snapshot = journal.confirm_outcome(
                        event_time_ns=next_event_time(),
                        outcome_sha256=outcome_sha,
                    )
                    contact_receipts.append(
                        IntegratedContactReceipt(
                            semantic_step_ordinal=step.semantic_step_ordinal,
                            contact_occurrence_ordinal=(
                                slice_.contact_occurrence_ordinal
                            ),
                            target_id=step.target_id,
                            action_occurrence_sha256=(
                                assembly.occurrences[
                                    slice_.contact_occurrence_ordinal
                                ].occurrence_hash
                            ),
                            contact_event_sha256=event.event_hash,
                            contact_result_sha256=contact_result.result_hash,
                            resolved_target_id=contact_result.resolved_target_id,
                            observer_snapshot_sha256=observer_snapshot.snapshot_hash,
                            journal_snapshot_sha256=snapshot.snapshot_hash,
                        )
                    )
                    contact_confirmed = True
                if (
                    binding.dense.phase is MotionPhase.RETRACT
                    and binding.dense.phase_endpoint
                ):
                    if not contact_confirmed:
                        raise _MissionAbort("retract endpoint preceded confirmed contact")
                    active_stage = "RETRACTION_COMMIT"
                    journal.confirm_retracted(
                        event_time_ns=next_event_time(),
                        feedback_sha256=trace.canonical_sha256,
                    )
                    retracted = True
            if not (camera_used and contact_confirmed and retracted):
                raise _MissionAbort("contact slice did not complete observe/contact/retract")
            semantic_cursor += 1
            # A post-contact VerifyPhoneState is evaluated from device truth
            # before another contact—or the final mission tail—may execute.
            verify_observations_until_contact(
                (
                    assembly.dense_route.contact_slices[
                        slice_.contact_occurrence_ordinal + 1
                    ].semantic_step_ordinal
                    if slice_.contact_occurrence_ordinal + 1
                    < len(assembly.dense_route.contact_slices)
                    else None
                )
            )
            for binding in mission_tail:
                execute_command(binding)

        verify_observations_until_contact(None)
        active_stage = "MISSION_FINALIZATION"
        active_semantic_step_ordinal = None
        active_contact_occurrence_ordinal = None
        active_authorization_command_ordinal = None
        if semantic_cursor != len(assembly.semantic_schedule.steps):
            raise _MissionAbort("not every semantic step was consumed")
        if (
            not permit.complete
            or continuity.remaining_samples != 0
            or not camera_port.complete
            or camera_port.remaining != 0
        ):
            raise _MissionAbort("authorization/continuity schedule is incomplete")
        final_state = runtime.state_receipt()
        if not (
            final_state.terminal
            and final_state.completed_command_count == assembly.command_count
        ):
            raise _MissionAbort("T104 emulator did not reach terminal park schedule")
        final_trace_hash = command_receipts[-1].t104_trace_receipt_sha256
        for journal in prepared.journals:
            journal.confirm_parked(
                event_time_ns=next_event_time(),
                feedback_sha256=final_trace_hash,
            )
        matches = observer.output_matches(
            assembly.plan.requested_text_sha256,
            len(assembly.normalized_text),
        )
        if not matches:
            raise _MissionAbort("independent final output does not match requested text")
    # Once execution begins, every ordinary software failure must first close
    # the durable journals.  Restricting this to today's known exception types
    # would turn a future adapter bug into an unsafe automatic-retry window.
    except Exception as exc:
        fault_detail = _safe_fault_detail(exc)
        try:
            if type(exc) is B0477ReplayCaptureError:
                camera_exception = cast(B0477ReplayCaptureError, exc)
                camera_fault = camera_exception.receipt
                port_fault = camera_port.fault_receipt
                if (
                    port_fault is None
                    or port_fault.canonical_sha256
                    != camera_fault.canonical_sha256
                ):
                    raise IntegratedZeroHardwareMissionError(
                        "camera exception differs from the replay port fault latch"
                    )
                boundary_source = _observation_boundary_fault_source_sha256(
                    assembly_sha256=assembly.assembly_sha256,
                    semantic_step_ordinal=camera_fault.semantic_step_ordinal,
                    contact_occurrence_ordinal=(
                        camera_fault.contact_occurrence_ordinal
                    ),
                    authorization_command_ordinal=(
                        camera_fault.authorization_command_ordinal
                    ),
                    command_receipt_count=len(command_receipts),
                    camera_observation_count=len(camera_receipts),
                    state_observation_count=len(state_receipts),
                    contact_receipt_count=len(contact_receipts),
                )
                fault_receipt = IntegratedFaultReceipt(
                    assembly_sha256=assembly.assembly_sha256,
                    source_class=_FAULT_SOURCE_OBSERVATION_BOUNDARY,
                    stage=_OBSERVATION_BOUNDARY_STAGE,
                    fault_kind=_OBSERVATION_BOUNDARY_FAULT_KIND,
                    semantic_step_ordinal=camera_fault.semantic_step_ordinal,
                    contact_occurrence_ordinal=(
                        camera_fault.contact_occurrence_ordinal
                    ),
                    authorization_command_ordinal=(
                        camera_fault.authorization_command_ordinal
                    ),
                    command_receipt_count=len(command_receipts),
                    camera_observation_count=len(camera_receipts),
                    state_observation_count=len(state_receipts),
                    contact_receipt_count=len(contact_receipts),
                    source_evidence_sha256=boundary_source,
                    # This preserves useful deterministic adapter detail but
                    # does not elevate an unauthenticated in-process receipt
                    # into a stronger persisted causal claim.
                    camera_fault_receipt=camera_fault,
                )
            elif command_receipts and not command_receipts[-1].success:
                failed_command = command_receipts[-1]
                if failed_command.fault_kind is None:
                    raise IntegratedZeroHardwareMissionError(
                        "failed controller receipt lost its fault kind"
                    )
                fault_receipt = IntegratedFaultReceipt(
                    assembly_sha256=assembly.assembly_sha256,
                    source_class=_FAULT_SOURCE_RUNTIME,
                    stage="COMMAND_EXECUTION",
                    fault_kind=failed_command.fault_kind,
                    semantic_step_ordinal=failed_command.semantic_step_ordinal,
                    contact_occurrence_ordinal=(
                        failed_command.contact_occurrence_ordinal
                    ),
                    authorization_command_ordinal=(
                        failed_command.authorization_command_ordinal
                    ),
                    command_receipt_count=len(command_receipts),
                    camera_observation_count=len(camera_receipts),
                    state_observation_count=len(state_receipts),
                    contact_receipt_count=len(contact_receipts),
                    source_evidence_sha256=(
                        failed_command.t104_trace_receipt_sha256
                    ),
                )
            elif (
                active_stage
                in {_OBSERVATION_BOUNDARY_STAGE, "CAPTURE_AFTER_SETTLE"}
                and active_semantic_step_ordinal is not None
                and active_contact_occurrence_ordinal is not None
                and active_authorization_command_ordinal is not None
            ):
                observation_boundary_source = (
                    _observation_boundary_fault_source_sha256(
                        assembly_sha256=assembly.assembly_sha256,
                        semantic_step_ordinal=active_semantic_step_ordinal,
                        contact_occurrence_ordinal=(
                            active_contact_occurrence_ordinal
                        ),
                        authorization_command_ordinal=(
                            active_authorization_command_ordinal
                        ),
                        command_receipt_count=len(command_receipts),
                        camera_observation_count=len(camera_receipts),
                        state_observation_count=len(state_receipts),
                        contact_receipt_count=len(contact_receipts),
                    )
                )
                fault_receipt = IntegratedFaultReceipt(
                    assembly_sha256=assembly.assembly_sha256,
                    source_class=_FAULT_SOURCE_OBSERVATION_BOUNDARY,
                    stage=_OBSERVATION_BOUNDARY_STAGE,
                    fault_kind=_OBSERVATION_BOUNDARY_FAULT_KIND,
                    semantic_step_ordinal=active_semantic_step_ordinal,
                    contact_occurrence_ordinal=(
                        active_contact_occurrence_ordinal
                    ),
                    authorization_command_ordinal=(
                        active_authorization_command_ordinal
                    ),
                    command_receipt_count=len(command_receipts),
                    camera_observation_count=len(camera_receipts),
                    state_observation_count=len(state_receipts),
                    contact_receipt_count=len(contact_receipts),
                    source_evidence_sha256=observation_boundary_source,
                )
            else:
                raise IntegratedZeroHardwareMissionError(
                    "fall back to coordinator fault attribution"
                )
        except BaseException:
            # Fault attribution must never precede durable terminalization.  If
            # a malformed adapter exception cannot produce its specialized
            # receipt, preserve the coarsest representable prefix receipt,
            # close every journal below, and reject irreconcilable provenance
            # only after automatic retry has been disabled.
            try:
                if (
                    active_stage
                    in {_OBSERVATION_BOUNDARY_STAGE, "CAPTURE_AFTER_SETTLE"}
                    and active_semantic_step_ordinal is not None
                    and active_contact_occurrence_ordinal is not None
                    and active_authorization_command_ordinal is not None
                ):
                    boundary_source = _observation_boundary_fault_source_sha256(
                        assembly_sha256=assembly.assembly_sha256,
                        semantic_step_ordinal=active_semantic_step_ordinal,
                        contact_occurrence_ordinal=(
                            active_contact_occurrence_ordinal
                        ),
                        authorization_command_ordinal=(
                            active_authorization_command_ordinal
                        ),
                        command_receipt_count=len(command_receipts),
                        camera_observation_count=len(camera_receipts),
                        state_observation_count=len(state_receipts),
                        contact_receipt_count=len(contact_receipts),
                    )
                    fault_receipt = IntegratedFaultReceipt(
                        assembly_sha256=assembly.assembly_sha256,
                        source_class=_FAULT_SOURCE_OBSERVATION_BOUNDARY,
                        stage=_OBSERVATION_BOUNDARY_STAGE,
                        fault_kind=_OBSERVATION_BOUNDARY_FAULT_KIND,
                        semantic_step_ordinal=active_semantic_step_ordinal,
                        contact_occurrence_ordinal=(
                            active_contact_occurrence_ordinal
                        ),
                        authorization_command_ordinal=(
                            active_authorization_command_ordinal
                        ),
                        command_receipt_count=len(command_receipts),
                        camera_observation_count=len(camera_receipts),
                        state_observation_count=len(state_receipts),
                        contact_receipt_count=len(contact_receipts),
                        source_evidence_sha256=boundary_source,
                    )
                else:
                    coordinator_source = _coordinator_fault_source_sha256(
                        assembly_sha256=assembly.assembly_sha256,
                        stage=active_stage,
                        fault_kind=_COORDINATOR_FAULT_KIND,
                        semantic_step_ordinal=active_semantic_step_ordinal,
                        contact_occurrence_ordinal=(
                            active_contact_occurrence_ordinal
                        ),
                        authorization_command_ordinal=(
                            active_authorization_command_ordinal
                        ),
                        command_receipt_count=len(command_receipts),
                        camera_observation_count=len(camera_receipts),
                        state_observation_count=len(state_receipts),
                        contact_receipt_count=len(contact_receipts),
                    )
                    fault_receipt = IntegratedFaultReceipt(
                        assembly_sha256=assembly.assembly_sha256,
                        source_class=_FAULT_SOURCE_COORDINATOR,
                        stage=active_stage,
                        fault_kind=_COORDINATOR_FAULT_KIND,
                        semantic_step_ordinal=active_semantic_step_ordinal,
                        contact_occurrence_ordinal=(
                            active_contact_occurrence_ordinal
                        ),
                        authorization_command_ordinal=(
                            active_authorization_command_ordinal
                        ),
                        command_receipt_count=len(command_receipts),
                        camera_observation_count=len(camera_receipts),
                        state_observation_count=len(state_receipts),
                        contact_receipt_count=len(contact_receipts),
                        source_evidence_sha256=coordinator_source,
                    )
            except BaseException:
                # Even evidence-construction failures cannot bypass durable
                # journal closure.  The emergency hash below closes every
                # journal; the caller then receives a hard error, not a report.
                fault_receipt = None
        fault_hash = (
            fault_receipt.receipt_sha256
            if fault_receipt is not None
            else _hash(
                {
                    "schema": "rocell.integrated_emergency_fault_closure.v1",
                    "assembly_sha256": assembly.assembly_sha256,
                    "stage": active_stage,
                    "command_receipt_count": len(command_receipts),
                    "camera_observation_count": len(camera_receipts),
                    "contact_receipt_count": len(contact_receipts),
                    **_authority(),
                },
                64 * 1024,
            )
        )
        closure_errors: list[str] = []
        for journal in prepared.journals:
            try:
                snapshot = journal.snapshot()
                if (
                    snapshot.current_state
                    is ActionJournalState.CONTACT_MAY_HAVE_OCCURRED
                ):
                    journal.mark_outcome_uncertain(
                        event_time_ns=next_event_time(),
                        detail_code="INTEGRATED_CONTACT_OUTCOME_UNCERTAIN",
                        evidence_sha256=fault_hash,
                    )
                elif snapshot.current_state in {
                    ActionJournalState.INTENT_COMMITTED,
                    ActionJournalState.PRE_CONTACT,
                    ActionJournalState.OUTCOME_CONFIRMED,
                    ActionJournalState.RETRACTED,
                }:
                    journal.mark_faulted(
                        event_time_ns=next_event_time(),
                        detail_code="INTEGRATED_MISSION_ABORTED",
                        evidence_sha256=fault_hash,
                    )
            except BaseException as closure_exc:
                closure_errors.append(_safe_fault_detail(closure_exc))
        if closure_errors:
            raise IntegratedZeroHardwareMissionError(
                "one or more mission journals could not be terminalized: "
                + ";".join(closure_errors)[:512]
            ) from exc
        if fault_receipt is None:
            raise IntegratedZeroHardwareMissionError(
                "fault receipt construction failed after journals were terminalized"
            ) from exc

    final_state = runtime.state_receipt()
    journal_snapshots = tuple(journal.snapshot() for journal in prepared.journals)
    outcome_matches = observer.output_matches(
        assembly.plan.requested_text_sha256,
        len(assembly.normalized_text),
    )
    complete = (
        fault_receipt is None
        and fault_detail is None
        and outcome_matches
        and len(command_receipts) == assembly.command_count
        and len(camera_receipts) == assembly.contact_count
        and len(contact_receipts) == assembly.contact_count
        and all(
            snapshot.current_state is ActionJournalState.PARKED
            for snapshot in journal_snapshots
        )
    )
    report = IntegratedZeroHardwareMissionReport(
        status=(
            "ZERO_HARDWARE_MISSION_V2_COMPLETE_WITH_PHYSICAL_HOLDS"
            if complete
            else "ZERO_HARDWARE_MISSION_V2_FAULTED_CLOSED"
        ),
        assembly_sha256=assembly.assembly_sha256,
        command_receipts=tuple(command_receipts),
        camera_observation_sha256s=tuple(camera_receipts),
        state_observation_receipts=tuple(state_receipts),
        contact_receipts=tuple(contact_receipts),
        runtime_final_state=final_state,
        journal_snapshots=journal_snapshots,
        expected_output_sha256=assembly.plan.requested_text_sha256,
        expected_output_length=len(assembly.normalized_text),
        observed_output_sha256=observer.output_sha256,
        observed_output_length=observer.output_length,
        outcome_matches=outcome_matches,
        fault_receipt=fault_receipt,
        fault_detail=fault_detail,
    )
    report.assert_matches_assembly(assembly)
    return report


def run_default_zero_hardware_mission_v2(
    workspace_root: Path,
    device: str,
    requested_text: str,
    journal_root: Path,
    **assembly_options: Any,
) -> IntegratedZeroHardwareMissionReport:
    """Convenience entry point: assemble, journal, and execute one rehearsal."""

    assembly = assemble_default_zero_hardware_mission_v2(
        workspace_root,
        device,
        requested_text,
        **assembly_options,
    )
    prepared = prepare_zero_hardware_mission_v2(assembly, journal_root)
    return run_zero_hardware_mission_v2(prepared)


__all__ = [
    "INTEGRATED_COMMAND_RECEIPT_SCHEMA",
    "INTEGRATED_CONTACT_RECEIPT_SCHEMA",
    "INTEGRATED_FAULT_RECEIPT_SCHEMA",
    "INTEGRATED_JOURNAL_SET_FILENAME",
    "INTEGRATED_JOURNAL_SET_SCHEMA",
    "INTEGRATED_STATE_OBSERVATION_SCHEMA",
    "INTEGRATED_ZERO_HARDWARE_REPORT_SCHEMA",
    "IntegratedCommandReceipt",
    "IntegratedContactReceipt",
    "IntegratedFaultReceipt",
    "IntegratedStateObservationReceipt",
    "IntegratedZeroHardwareMissionError",
    "IntegratedZeroHardwareMissionReport",
    "PreparedZeroHardwareMissionV2",
    "assemble_default_zero_hardware_mission_v2",
    "open_zero_hardware_mission_v2",
    "prepare_zero_hardware_mission_v2",
    "run_default_zero_hardware_mission_v2",
    "run_zero_hardware_mission_v2",
]
