"""Immutable build state and conservative capability projection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping


class Capability(str, Enum):
    DIGITAL_PLAN = "digital_plan"
    SIMULATED_DRY_RUN = "simulated_dry_run"
    CAMERA_CAPTURE = "camera_capture"
    ARM_FEEDBACK = "arm_feedback"
    EMPTY_CELL_MOTION = "empty_cell_motion"
    KEYBOARD_CONTACT = "keyboard_contact"
    PHONE_CONTACT = "phone_contact"


CAMERA_QUALIFIED_STATES = frozenset({"QUALIFIED"})


def _frozen_mapping(values: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True, slots=True)
class BuildSnapshot:
    manifest_id: str
    manifest_sha256: str
    design_revision: str
    active_build_id: str | None
    source_hashes: Mapping[str, str]
    selected_routes: Mapping[str, bool]
    gate_statuses: Mapping[str, str]
    hard_blockers: tuple[str, ...]
    physical_release_status: str
    tag_coordinate_source: str
    camera_exact_model: str | None
    camera_state: str
    safe_to_power_robot: bool
    contact_enabled: bool
    integrity_verified: bool = True

    def __post_init__(self) -> None:
        for name in ("manifest_id", "manifest_sha256", "design_revision"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if self.active_build_id is not None and (
            not isinstance(self.active_build_id, str) or not self.active_build_id.strip()
        ):
            raise ValueError("active_build_id must be null or a non-empty string")
        object.__setattr__(self, "source_hashes", _frozen_mapping(self.source_hashes))
        object.__setattr__(self, "selected_routes", _frozen_mapping(self.selected_routes))
        object.__setattr__(self, "gate_statuses", _frozen_mapping(self.gate_statuses))
        blockers = tuple(dict.fromkeys(self.hard_blockers))
        if any(not isinstance(blocker, str) or not blocker for blocker in blockers):
            raise ValueError("hard_blockers must contain non-empty strings")
        object.__setattr__(self, "hard_blockers", blockers)
        if not isinstance(self.camera_state, str) or not self.camera_state.strip():
            raise ValueError("camera_state must be a non-empty string")
        object.__setattr__(self, "camera_state", self.camera_state.strip())
        if self.camera_exact_model is not None and (
            not isinstance(self.camera_exact_model, str) or not self.camera_exact_model.strip()
        ):
            raise ValueError("camera_exact_model must be null or a non-empty string")
        if self.camera_exact_model is not None:
            object.__setattr__(self, "camera_exact_model", self.camera_exact_model.strip())
        if not isinstance(self.safe_to_power_robot, bool):
            raise TypeError("safe_to_power_robot must be bool")
        if not isinstance(self.contact_enabled, bool):
            raise TypeError("contact_enabled must be bool")
        if self.integrity_verified is not True:
            raise ValueError("A BuildSnapshot cannot represent unverified source data")

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "manifest_sha256": self.manifest_sha256,
            "design_revision": self.design_revision,
            "active_build_id": self.active_build_id,
            "source_hashes": dict(sorted(self.source_hashes.items())),
            "selected_routes": dict(sorted(self.selected_routes.items())),
            "gate_statuses": dict(sorted(self.gate_statuses.items())),
            "hard_blockers": list(self.hard_blockers),
            "physical_release_status": self.physical_release_status,
            "tag_coordinate_source": self.tag_coordinate_source,
            "camera_exact_model": self.camera_exact_model,
            "camera_state": self.camera_state,
            "safe_to_power_robot": self.safe_to_power_robot,
            "contact_enabled": self.contact_enabled,
            "integrity_verified": True,
        }

    @property
    def snapshot_hash(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class CapabilityAssessment:
    capability: Capability
    allowed: bool
    reasons: tuple[str, ...]
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(dict.fromkeys(self.reasons)))
        if self.allowed and self.reasons:
            raise ValueError("An allowed capability cannot retain blocking reasons")
        if not self.allowed and not self.reasons:
            raise ValueError("A denied capability must explain why")


def _camera_is_qualified(state: str) -> bool:
    """Fail closed: only an exact, controlled qualification state enables capture."""

    return state.strip().upper() in CAMERA_QUALIFIED_STATES


def assess_capability(snapshot: BuildSnapshot, capability: Capability) -> CapabilityAssessment:
    if not isinstance(capability, Capability):
        capability = Capability(capability)
    reasons: list[str] = []

    if capability in (Capability.DIGITAL_PLAN, Capability.SIMULATED_DRY_RUN):
        return CapabilityAssessment(capability, True, (), snapshot.snapshot_hash)

    if snapshot.active_build_id is None:
        reasons.append("ACTIVE_BUILD_ID_NULL")

    if capability is Capability.CAMERA_CAPTURE:
        if snapshot.camera_exact_model is None:
            reasons.append("EXACT_CAMERA_IDENTITY_MISSING")
        if not _camera_is_qualified(snapshot.camera_state):
            reasons.append("CAMERA_NOT_QUALIFIED")

    if capability in (
        Capability.ARM_FEEDBACK,
        Capability.EMPTY_CELL_MOTION,
        Capability.KEYBOARD_CONTACT,
        Capability.PHONE_CONTACT,
    ) and not snapshot.safe_to_power_robot:
        reasons.append("ROBOT_POWER_NOT_RELEASED")

    if capability in (
        Capability.EMPTY_CELL_MOTION,
        Capability.KEYBOARD_CONTACT,
        Capability.PHONE_CONTACT,
    ):
        if snapshot.physical_release_status.upper() not in {"PASS", "RELEASED"}:
            reasons.append("PHYSICAL_RELEASE_UNRELEASED")
        incomplete = tuple(
            gate_id for gate_id, status in snapshot.gate_statuses.items() if status != "PASS"
        )
        if not snapshot.gate_statuses:
            reasons.append("PHYSICAL_GATES_MISSING")
        elif incomplete:
            reasons.append("PHYSICAL_GATES_INCOMPLETE")

    if capability in (Capability.KEYBOARD_CONTACT, Capability.PHONE_CONTACT):
        if not snapshot.contact_enabled:
            reasons.append("CONTACT_DISABLED")
        route = (
            "keyboard_rod_route"
            if capability is Capability.KEYBOARD_CONTACT
            else "phone_stylus_route"
        )
        if snapshot.selected_routes.get(route) is not True:
            reasons.append(f"REQUIRED_ROUTE_NOT_SELECTED:{route}")
        if snapshot.tag_coordinate_source != "measured_installation":
            reasons.append("MEASURED_TAG_MAP_MISSING")

    # Preserve current controlled blockers in the explanation for any motion or
    # contact attempt.  Feedback/camera probes use their narrower gates above.
    if capability in (
        Capability.EMPTY_CELL_MOTION,
        Capability.KEYBOARD_CONTACT,
        Capability.PHONE_CONTACT,
    ):
        reasons.extend(snapshot.hard_blockers)

    return CapabilityAssessment(
        capability=capability,
        allowed=not reasons,
        reasons=tuple(reasons),
        snapshot_hash=snapshot.snapshot_hash,
    )


def project_capabilities(snapshot: BuildSnapshot) -> Mapping[Capability, CapabilityAssessment]:
    return MappingProxyType(
        {capability: assess_capability(snapshot, capability) for capability in Capability}
    )
