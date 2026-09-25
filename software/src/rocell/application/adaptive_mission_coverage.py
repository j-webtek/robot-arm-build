"""Bounded full-catalog coverage through the adaptive arm-camera pipeline.

The existing mission-route screen proves independent trajectory feasibility for
all locked targets.  This module deliberately asks a stronger, separate
software-only question: can each target complete one fresh arm-camera
observation, achieved-FK contact projection, independent device outcome, and
return-to-park cycle?  Each route remains independent so a failure cannot hide
later catalog entries.

The report is compact and hash-bound.  Child reports are committed by digest
rather than embedded, and every authority field remains false/zero.  Nothing in
this module imports a camera or serial adapter or can satisfy a physical gate.
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

from rocell.models.actions import PressKey, TapPhoneTarget
from rocell.simulation.virtual_profile import (
    VirtualCommissioningProfile,
    VirtualProfileContext,
    load_virtual_commissioning_profile,
)
from rocell.typing import compile_development_text

from .adaptive_virtual_session import (
    AdaptiveVirtualSessionPolicy,
    AdaptiveVirtualSessionReport,
    run_adaptive_virtual_session,
    synthetic_wide_fov_adaptive_session_policy,
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
    MissionSemanticRoute,
    mission_semantic_routes,
)
from .virtual_arm_camera import make_hidden_virtual_board_truth
from .virtual_session import VirtualSessionScenarioBinding


ADAPTIVE_MISSION_COVERAGE_SCHEMA = "rocell.adaptive_mission_coverage.v1"
MAX_ADAPTIVE_COVERAGE_CHUNK_SIZE = 15
MAX_ADAPTIVE_COVERAGE_EXECUTIONS_PER_ROUTE = 128
MAX_ADAPTIVE_COVERAGE_EXECUTIONS = (
    EXPECTED_MISSION_TARGET_COUNT * MAX_ADAPTIVE_COVERAGE_EXECUTIONS_PER_ROUTE
)
MAX_ADAPTIVE_COVERAGE_CAPTURES = EXPECTED_MISSION_TARGET_COUNT * 2
MAX_ADAPTIVE_COVERAGE_CONTACTS = EXPECTED_MISSION_TARGET_COUNT
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DECISION_STATUSES = frozenset({"NO_CHANGE", "APPLY", "REJECT"})


class AdaptiveMissionCoverageError(ValueError):
    """The complete adaptive target catalog could not be proven coherently."""


def _full_catalog_session_policy() -> AdaptiveVirtualSessionPolicy:
    """Use the bounded envelope measured across all 75 synthetic views.

    Integer-pixel tag corners at the two most oblique phone viewpoints produce
    up to 2.21 mm apparent translation and 0.42 degrees apparent tilt on
    nominal truth.  A small explicit margin prevents those renderer artifacts
    from becoming false Z corrections; independent truth-derived contact is
    still required for every route.  These are not physical tolerances.
    """

    return synthetic_wide_fov_adaptive_session_policy(
        translation_deadband_mm=2.5,
        angular_deadband_rad=math.radians(0.5),
        maximum_inlier_reprojection_rmse_px=5.0,
        maximum_execution_waypoints=(
            MAX_ADAPTIVE_COVERAGE_EXECUTIONS_PER_ROUTE
        ),
    )


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


def _digest(value: str, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise AdaptiveMissionCoverageError(f"{label} must be a lowercase SHA-256")
    return value


def _bounded_text(value: object, label: str, *, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise AdaptiveMissionCoverageError(f"{label} is invalid")
    return value


def _authority() -> dict[str, object]:
    return {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "execution_authorized": False,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "can_release_physical_gates": False,
        "physical_release_effect": "NONE",
    }


def _freeze_json(value: object, label: str) -> object:
    """Detach a JSON tree so a returned report cannot be mutated by aliases."""

    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise AdaptiveMissionCoverageError(f"{label} keys must be strings")
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
    raise AdaptiveMissionCoverageError(
        f"{label} must contain finite JSON-compatible values"
    )


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(child) for child in value]
    return value


def _physical_target_ids(plan: object) -> tuple[str, ...]:
    actions = getattr(plan, "actions", ())
    return tuple(
        action.key_id if isinstance(action, PressKey) else action.target_id
        for action in actions
        if isinstance(action, (PressKey, TapPhoneTarget))
    )


def _zero_authority(document: object) -> bool:
    """Reject positive hardware authority anywhere in a child document."""

    if isinstance(document, Mapping):
        for key, value in document.items():
            if key in {
                "hardware_accessed",
                "execution_authorized",
                "live_motion_authorized",
                "physical_contact_authorized",
                "can_release_physical_gates",
                "hardware_command_emitted",
            } and value is not False:
                return False
            if key == "hardware_commands_generated" and value != 0:
                return False
            if not _zero_authority(value):
                return False
        return True
    if isinstance(document, (tuple, list)):
        return all(_zero_authority(item) for item in document)
    return True


@dataclass(frozen=True, slots=True)
class AdaptiveMissionCoveragePolicy:
    """Fixed resource policy for 75 independent nominal adaptive sessions."""

    orchestration_chunk_size: int = 5
    maximum_total_executions: int = MAX_ADAPTIVE_COVERAGE_EXECUTIONS
    maximum_total_captures: int = MAX_ADAPTIVE_COVERAGE_CAPTURES
    maximum_total_contacts: int = MAX_ADAPTIVE_COVERAGE_CONTACTS
    session_policy: AdaptiveVirtualSessionPolicy = field(
        default_factory=_full_catalog_session_policy
    )

    def __post_init__(self) -> None:
        if not isinstance(self.session_policy, AdaptiveVirtualSessionPolicy):
            raise TypeError("session_policy must be AdaptiveVirtualSessionPolicy")
        for name, lower, upper in (
            ("orchestration_chunk_size", 1, MAX_ADAPTIVE_COVERAGE_CHUNK_SIZE),
            ("maximum_total_executions", 1, MAX_ADAPTIVE_COVERAGE_EXECUTIONS),
            ("maximum_total_captures", 1, MAX_ADAPTIVE_COVERAGE_CAPTURES),
            ("maximum_total_contacts", 1, MAX_ADAPTIVE_COVERAGE_CONTACTS),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not lower <= value <= upper
            ):
                raise AdaptiveMissionCoverageError(
                    f"{name} must be an integer in [{lower}, {upper}]"
                )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.adaptive_mission_coverage_policy.v1",
            "orchestration_chunk_size": self.orchestration_chunk_size,
            "maximum_total_executions": self.maximum_total_executions,
            "maximum_total_captures": self.maximum_total_captures,
            "maximum_total_contacts": self.maximum_total_contacts,
            "session_policy": {
                **self.session_policy.to_dict(),
                "policy_sha256": self.session_policy.policy_hash,
                "physical_tolerance_claimed": False,
            },
            "route_truth": {
                "translation_Wv_mm": [0.0, 0.0, 0.0],
                "yaw_board_rad": 0.0,
                "classification": "SYNTHETIC_NOMINAL_ONLY",
                "serialized_to_child": False,
            },
            "authority": _authority(),
        }

    @property
    def policy_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class AdaptiveTargetEvidence:
    """Compact outcome for one independently executed catalog target."""

    ordinal: int
    device: str
    target_id: str
    requested_text_sha256: str
    child_report_sha256: str
    child_status: str
    decision_statuses: tuple[str, ...]
    execution_count: int
    capture_count: int
    correction_installation_count: int
    contact_count: int
    accepted_contact_count: int
    observed_contact_targets: tuple[str, ...]
    pipeline_completed: bool
    outcome_verified: bool
    ended_at_park: bool
    arm_closed: bool
    authority_verified: bool
    fault_reason: str | None

    def __post_init__(self) -> None:
        if (
            isinstance(self.ordinal, bool)
            or not isinstance(self.ordinal, int)
            or not 0 <= self.ordinal < EXPECTED_MISSION_TARGET_COUNT
        ):
            raise AdaptiveMissionCoverageError("route ordinal is invalid")
        if self.device not in {"keyboard", "phone"}:
            raise AdaptiveMissionCoverageError("route device is invalid")
        _bounded_text(self.target_id, "route target_id", maximum=128)
        _digest(self.requested_text_sha256, "requested text hash")
        _digest(self.child_report_sha256, "child report hash")
        _bounded_text(self.child_status, "child status", maximum=128)
        if (
            not isinstance(self.decision_statuses, tuple)
            or len(self.decision_statuses) > 2
            or any(status not in _DECISION_STATUSES for status in self.decision_statuses)
        ):
            raise AdaptiveMissionCoverageError(
                "decision_statuses must be a bounded immutable status tuple"
            )
        if (
            not isinstance(self.observed_contact_targets, tuple)
            or any(
                not isinstance(target, str)
                or not target
                or target.strip() != target
                or len(target) > 128
                for target in self.observed_contact_targets
            )
        ):
            raise AdaptiveMissionCoverageError(
                "observed_contact_targets must be a bounded immutable ID tuple"
            )
        for name, value, maximum in (
            (
                "execution_count",
                self.execution_count,
                MAX_ADAPTIVE_COVERAGE_EXECUTIONS_PER_ROUTE,
            ),
            ("capture_count", self.capture_count, 2),
            ("correction_installation_count", self.correction_installation_count, 1),
            ("contact_count", self.contact_count, 1),
            ("accepted_contact_count", self.accepted_contact_count, 1),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value <= maximum
            ):
                raise AdaptiveMissionCoverageError(
                    f"{name} must be an integer in [0, {maximum}]"
                )
        for name in (
            "pipeline_completed",
            "outcome_verified",
            "ended_at_park",
            "arm_closed",
            "authority_verified",
        ):
            if not isinstance(getattr(self, name), bool):
                raise AdaptiveMissionCoverageError(f"{name} must be boolean")
        if self.accepted_contact_count > self.contact_count:
            raise AdaptiveMissionCoverageError(
                "accepted contact count cannot exceed contact count"
            )
        if len(self.observed_contact_targets) != self.contact_count:
            raise AdaptiveMissionCoverageError(
                "observed contact IDs must match the contact count"
            )
        if self.correction_installation_count > self.capture_count:
            raise AdaptiveMissionCoverageError(
                "correction installations cannot exceed camera captures"
            )
        if self.fault_reason is not None:
            _bounded_text(self.fault_reason, "fault_reason", maximum=256)
        if self.pipeline_completed and self.fault_reason is not None:
            raise AdaptiveMissionCoverageError(
                "a completed route cannot retain a fault reason"
            )

    @property
    def expected_contact_target(self) -> str:
        """Return the action-layer namespace for this raw catalog target."""

        return f"{self.device}:{self.target_id}"

    @property
    def vision_converged(self) -> bool:
        """Require one of the only two safe terminal correction sequences."""

        return (
            self.decision_statuses == ("NO_CHANGE",)
            and self.capture_count == 1
            and self.correction_installation_count == 0
        ) or (
            self.decision_statuses == ("APPLY", "NO_CHANGE")
            and self.capture_count == 2
            and self.correction_installation_count == 1
        )

    @property
    def accepted(self) -> bool:
        return (
            self.pipeline_completed
            and self.outcome_verified
            and self.ended_at_park
            and self.arm_closed
            and self.authority_verified
            and self.fault_reason is None
            and self.capture_count >= 1
            and self.contact_count == 1
            and self.accepted_contact_count == 1
            and self.observed_contact_targets == (self.expected_contact_target,)
            and self.vision_converged
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "device": self.device,
            "target_id": self.target_id,
            "expected_contact_target": self.expected_contact_target,
            "requested_text": {
                "sha256": self.requested_text_sha256,
                "normalized_codepoint_length": 1,
                "plaintext_serialized": False,
            },
            "child_report_sha256": self.child_report_sha256,
            "child_status": self.child_status,
            "decision_statuses": list(self.decision_statuses),
            "execution_count": self.execution_count,
            "capture_count": self.capture_count,
            "correction_installation_count": self.correction_installation_count,
            "contact_count": self.contact_count,
            "accepted_contact_count": self.accepted_contact_count,
            "observed_contact_targets": list(self.observed_contact_targets),
            "pipeline_completed": self.pipeline_completed,
            "outcome_verified": self.outcome_verified,
            "ended_at_park": self.ended_at_park,
            "arm_closed": self.arm_closed,
            "authority_verified": self.authority_verified,
            "fault_reason": self.fault_reason,
            "vision_converged": self.vision_converged,
            "accepted": self.accepted,
            "authority": _authority(),
        }


@dataclass(frozen=True, slots=True)
class AdaptiveMissionCoverageChunk:
    chunk_id: str
    chunk_index: int
    routes: tuple[AdaptiveTargetEvidence, ...]

    def __post_init__(self) -> None:
        _bounded_text(self.chunk_id, "chunk_id", maximum=128)
        if (
            isinstance(self.chunk_index, bool)
            or not isinstance(self.chunk_index, int)
            or self.chunk_index < 0
        ):
            raise AdaptiveMissionCoverageError("chunk_index is invalid")
        if not isinstance(self.routes, tuple) or not self.routes:
            raise AdaptiveMissionCoverageError("chunk routes must be a non-empty tuple")
        if len(self.routes) > MAX_ADAPTIVE_COVERAGE_CHUNK_SIZE:
            raise AdaptiveMissionCoverageError("chunk route count exceeded hard cap")
        if any(not isinstance(route, AdaptiveTargetEvidence) for route in self.routes):
            raise AdaptiveMissionCoverageError(
                "chunk routes must contain AdaptiveTargetEvidence values"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "route_count": len(self.routes),
            "routes": [route.to_dict() for route in self.routes],
        }


@dataclass(frozen=True, slots=True)
class AdaptiveMissionCoverageReport:
    """Complete 75-target adaptive-camera coverage evidence."""

    source: Mapping[str, object]
    policy: AdaptiveMissionCoveragePolicy
    keyboard_target_ids: tuple[str, ...]
    phone_target_ids: tuple[str, ...]
    chunks: tuple[AdaptiveMissionCoverageChunk, ...]
    final_revalidation_passed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.policy, AdaptiveMissionCoveragePolicy):
            raise TypeError("policy must be AdaptiveMissionCoveragePolicy")
        if not isinstance(self.final_revalidation_passed, bool):
            raise AdaptiveMissionCoverageError(
                "final_revalidation_passed must be boolean"
            )
        if not isinstance(self.source, Mapping):
            raise AdaptiveMissionCoverageError("source must be a mapping")
        frozen_source = _freeze_json(self.source, "source")
        if not isinstance(frozen_source, Mapping):  # Defensive for type narrowing.
            raise AdaptiveMissionCoverageError("source must be a mapping")
        object.__setattr__(self, "source", frozen_source)
        for name, values, expected in (
            ("keyboard_target_ids", self.keyboard_target_ids, EXPECTED_KEYBOARD_TARGET_COUNT),
            ("phone_target_ids", self.phone_target_ids, EXPECTED_PHONE_TARGET_COUNT),
        ):
            if (
                not isinstance(values, tuple)
                or len(values) != expected
                or len(set(values)) != expected
                or any(
                    not isinstance(value, str)
                    or not value
                    or value.strip() != value
                    or len(value) > 128
                    for value in values
                )
            ):
                raise AdaptiveMissionCoverageError(
                    f"{name} must contain exactly {expected} unique target IDs"
                )
        if (
            not isinstance(self.chunks, tuple)
            or not self.chunks
            or len(self.chunks) > EXPECTED_MISSION_TARGET_COUNT
            or any(not isinstance(chunk, AdaptiveMissionCoverageChunk) for chunk in self.chunks)
        ):
            raise AdaptiveMissionCoverageError("chunks are invalid or unbounded")
        if tuple(chunk.chunk_index for chunk in self.chunks) != tuple(
            range(len(self.chunks))
        ):
            raise AdaptiveMissionCoverageError("chunk indexes must be contiguous")
        if len({chunk.chunk_id for chunk in self.chunks}) != len(self.chunks):
            raise AdaptiveMissionCoverageError("chunk IDs must be unique")
        if any(
            len(chunk.routes) > self.policy.orchestration_chunk_size
            for chunk in self.chunks
        ):
            raise AdaptiveMissionCoverageError(
                "chunk route count exceeds the selected policy"
            )
        if not _zero_authority(self.source):
            raise AdaptiveMissionCoverageError("source document carries authority")
        self._validate_resources()

    @property
    def routes(self) -> tuple[AdaptiveTargetEvidence, ...]:
        return tuple(route for chunk in self.chunks for route in chunk.routes)

    @property
    def complete_catalog_evidence(self) -> bool:
        routes = self.routes
        keyboard = tuple(route.target_id for route in routes if route.device == "keyboard")
        phone = tuple(route.target_id for route in routes if route.device == "phone")
        return (
            len(routes) == EXPECTED_MISSION_TARGET_COUNT
            and tuple(route.ordinal for route in routes)
            == tuple(range(EXPECTED_MISSION_TARGET_COUNT))
            and keyboard == self.keyboard_target_ids
            and phone == self.phone_target_ids
            and len(set((route.device, route.target_id) for route in routes))
            == EXPECTED_MISSION_TARGET_COUNT
        )

    @property
    def all_routes_accepted(self) -> bool:
        return (
            self.final_revalidation_passed
            and self.complete_catalog_evidence
            and all(route.accepted for route in self.routes)
        )

    @property
    def status(self) -> str:
        if not self.complete_catalog_evidence:
            return "ADAPTIVE_MISSION_COVERAGE_INCOMPLETE_FAIL_CLOSED"
        if self.all_routes_accepted:
            return "ADAPTIVE_MISSION_COVERAGE_PASS_WITH_PHYSICAL_HOLDS"
        return "ADAPTIVE_MISSION_COVERAGE_GAPS_REPORTED"

    @property
    def resource_usage(self) -> dict[str, int]:
        return {
            "route_count": len(self.routes),
            "execution_count": sum(route.execution_count for route in self.routes),
            "capture_count": sum(route.capture_count for route in self.routes),
            "correction_installation_count": sum(
                route.correction_installation_count for route in self.routes
            ),
            "contact_count": sum(route.contact_count for route in self.routes),
        }

    def _validate_resources(self) -> None:
        usage = self.resource_usage
        if usage["route_count"] > EXPECTED_MISSION_TARGET_COUNT:
            raise AdaptiveMissionCoverageError("route count exceeded hard cap")
        if usage["execution_count"] > self.policy.maximum_total_executions:
            raise AdaptiveMissionCoverageError("execution count exceeded policy cap")
        if usage["capture_count"] > self.policy.maximum_total_captures:
            raise AdaptiveMissionCoverageError("capture count exceeded policy cap")
        if usage["contact_count"] > self.policy.maximum_total_contacts:
            raise AdaptiveMissionCoverageError("contact count exceeded policy cap")

    def _without_hash(self) -> dict[str, object]:
        return {
            "schema": ADAPTIVE_MISSION_COVERAGE_SCHEMA,
            "status": self.status,
            "source": _thaw_json(self.source),
            "policy": {**self.policy.to_dict(), "policy_sha256": self.policy.policy_hash},
            "catalog": {
                "expected_route_count": EXPECTED_MISSION_TARGET_COUNT,
                "keyboard_target_ids": list(self.keyboard_target_ids),
                "phone_target_ids": list(self.phone_target_ids),
                "complete_catalog_evidence": self.complete_catalog_evidence,
            },
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "summary": {
                **self.resource_usage,
                "accepted_route_count": sum(route.accepted for route in self.routes),
                "rejected_route_count": sum(not route.accepted for route in self.routes),
                "all_routes_accepted": self.all_routes_accepted,
                "final_revalidation_passed": self.final_revalidation_passed,
                "physical_ready": False,
            },
            "physical_holds": [
                "CAMERA_INTRINSICS_MOUNT_AND_TIMING_UNMEASURED",
                "CONTROLLER_TRACKING_AND_FRAME_CORRELATION_UNCOMMISSIONED",
                "FULL_BODY_COLLISION_AND_CABLE_GEOMETRY_INCOMPLETE",
                "PHYSICAL_DEVICE_TOOL_AND_CONTACT_EVIDENCE_MISSING",
            ],
            "authority": _authority(),
        }

    @property
    def report_hash(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, object]:
        return {**self._without_hash(), "report_sha256": self.report_hash}


def _scenario(profile: VirtualCommissioningProfile) -> VirtualSessionScenarioBinding:
    park = profile.park_point_board
    return VirtualSessionScenarioBinding(
        scenario_id=profile.profile_id,
        scenario_hash=profile.source_sha256,
        park_point_board_mm=(park.x, park.y, park.z),
    )


def _source_document(
    bootstrap: VirtualWorkcellBootstrap,
    profile: VirtualCommissioningProfile,
) -> dict[str, object]:
    snapshot = bootstrap.context.snapshot
    return {
        "bootstrap_sha256": bootstrap.bootstrap_hash,
        "manifest_id": snapshot.manifest_id,
        "manifest_sha256": snapshot.manifest_sha256,
        "snapshot_sha256": snapshot.snapshot_hash,
        "active_build_id": snapshot.active_build_id,
        "simulation_bundle_id": bootstrap.context.bundle_lock.bundle_id,
        "simulation_bundle_sha256": bootstrap.context.bundle_lock.source_lock_sha256,
        "virtual_profile_id": profile.profile_id,
        "virtual_profile_sha256": profile.source_sha256,
        "virtual_profile_classification": profile.status,
        "physical_ready": False,
        "authority": _authority(),
    }


def _evidence_from_report(
    ordinal: int,
    request: MissionSemanticRoute,
    report: AdaptiveVirtualSessionReport,
) -> AdaptiveTargetEvidence:
    document = report.to_dict()
    decisions = tuple(
        attempt.decision.status.value
        for attempt in report.vision_attempts
        if attempt.decision is not None
    )
    contacts = tuple(attempt.semantic_target for attempt in report.contact_attempts)
    return AdaptiveTargetEvidence(
        ordinal=ordinal,
        device=request.device,
        target_id=request.target_id,
        requested_text_sha256=hashlib.sha256(
            request.semantic_character.encode("utf-8")
        ).hexdigest(),
        child_report_sha256=report.report_hash,
        child_status=report.status,
        decision_statuses=decisions,
        execution_count=len(report.executions),
        capture_count=len(report.vision_attempts),
        correction_installation_count=len(report.correction_installations),
        contact_count=len(report.contact_attempts),
        accepted_contact_count=sum(item.accepted for item in report.contact_attempts),
        observed_contact_targets=contacts,
        pipeline_completed=report.pipeline_completed,
        outcome_verified=report.outcome_verified,
        ended_at_park=report.ended_at_park,
        arm_closed=report.arm_document.get("lifecycle") == "CLOSED",
        authority_verified=_zero_authority(document),
        fault_reason=report.fault_reason,
    )


def _run_adaptive_mission_coverage_with_runners(
    workspace: Path,
    *,
    policy: AdaptiveMissionCoveragePolicy,
    runtime_path: Path | None = None,
    bootstrap_runner: Callable[..., VirtualWorkcellBootstrap] | None = None,
    profile_loader: Callable[..., VirtualCommissioningProfile] | None = None,
    session_runner: Callable[..., AdaptiveVirtualSessionReport] | None = None,
    revalidator: Callable[[VirtualWorkcellBootstrap], None] | None = None,
) -> AdaptiveMissionCoverageReport:
    """Internal injection seam for exhaustive orchestration tests."""

    if not isinstance(policy, AdaptiveMissionCoveragePolicy):
        raise TypeError("policy must be AdaptiveMissionCoveragePolicy")
    root = Path(workspace).resolve()
    bootstrap_fn = bootstrap_runner or bootstrap_virtual_workcell
    profile_fn = profile_loader or load_virtual_commissioning_profile
    session_fn = session_runner or run_adaptive_virtual_session
    revalidate_fn = revalidator or revalidate_virtual_workcell
    bootstrap = bootstrap_fn(root, runtime_path)
    profile = profile_fn(cast(VirtualProfileContext, bootstrap.context))
    scenario = _scenario(profile)
    requests = mission_semantic_routes(bootstrap.context)
    if len(requests) != EXPECTED_MISSION_TARGET_COUNT:
        raise AdaptiveMissionCoverageError("adaptive coverage requires exactly 75 routes")

    chunks: list[AdaptiveMissionCoverageChunk] = []
    total_executions = 0
    total_captures = 0
    total_contacts = 0
    for chunk_index, offset in enumerate(
        range(0, len(requests), policy.orchestration_chunk_size)
    ):
        chunk_routes: list[AdaptiveTargetEvidence] = []
        for ordinal, request in enumerate(
            requests[offset : offset + policy.orchestration_chunk_size],
            start=offset,
        ):
            plan = compile_development_text(request.device, request.semantic_character)
            if _physical_target_ids(plan) != (request.target_id,):
                raise AdaptiveMissionCoverageError(
                    f"semantic route drifted for {request.device}:{request.target_id}"
                )
            truth = make_hidden_virtual_board_truth(profile.study_input)
            session_report = session_fn(
                bootstrap,
                plan,
                request.semantic_character,
                profile.study_input,
                scenario,
                truth=truth,
                policy=policy.session_policy,
            )
            try:
                evidence = _evidence_from_report(ordinal, request, session_report)
            except AdaptiveMissionCoverageError as exc:
                raise AdaptiveMissionCoverageError(
                    "adaptive evidence invalid for "
                    f"{request.device}:{request.target_id}: {exc}"
                ) from exc
            chunk_routes.append(evidence)
            total_executions += evidence.execution_count
            total_captures += evidence.capture_count
            total_contacts += evidence.contact_count
            # Stop before starting another expensive route if a hard aggregate
            # cap has already been crossed.
            if total_executions > policy.maximum_total_executions:
                raise AdaptiveMissionCoverageError("execution count exceeded policy cap")
            if total_captures > policy.maximum_total_captures:
                raise AdaptiveMissionCoverageError("capture count exceeded policy cap")
            if total_contacts > policy.maximum_total_contacts:
                raise AdaptiveMissionCoverageError("contact count exceeded policy cap")
        chunks.append(
            AdaptiveMissionCoverageChunk(
                chunk_id=f"adaptive-catalog-{chunk_index:02d}",
                chunk_index=chunk_index,
                routes=tuple(chunk_routes),
            )
        )

    revalidate_fn(bootstrap)
    coverage_report = AdaptiveMissionCoverageReport(
        source=_source_document(bootstrap, profile),
        policy=policy,
        keyboard_target_ids=tuple(sorted(bootstrap.context.targets.keyboard_targets)),
        phone_target_ids=tuple(sorted(bootstrap.context.targets.phone_targets)),
        chunks=tuple(chunks),
        final_revalidation_passed=True,
    )
    if not coverage_report.complete_catalog_evidence:
        raise AdaptiveMissionCoverageError(
            "complete 46-key + 29-phone adaptive evidence was not produced"
        )
    return coverage_report


def run_adaptive_mission_coverage(
    workspace: Path,
    *,
    policy: AdaptiveMissionCoveragePolicy | None = None,
    runtime_path: Path | None = None,
) -> AdaptiveMissionCoverageReport:
    """Run all 75 targets through independent nominal arm-camera sessions."""

    selected = policy or AdaptiveMissionCoveragePolicy()
    if not isinstance(selected, AdaptiveMissionCoveragePolicy):
        raise TypeError("policy must be AdaptiveMissionCoveragePolicy")
    return _run_adaptive_mission_coverage_with_runners(
        workspace,
        policy=selected,
        runtime_path=runtime_path,
    )


__all__ = [
    "ADAPTIVE_MISSION_COVERAGE_SCHEMA",
    "AdaptiveMissionCoverageChunk",
    "AdaptiveMissionCoverageError",
    "AdaptiveMissionCoveragePolicy",
    "AdaptiveMissionCoverageReport",
    "AdaptiveTargetEvidence",
    "run_adaptive_mission_coverage",
]
