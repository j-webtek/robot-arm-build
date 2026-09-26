"""Bind collision qualification and phase-local contact to a no-write envelope.

This boundary deliberately cannot create controller commands or physical
authority.  It proves only that one already-sealed action has conservative
non-contact sweep evidence and, for a contact proposal, one narrowly scoped
CONTACT-phase allowance.  Contact allowances never modify global exclusions.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from rocell.models import Interaction, ModelMotionProposalV2, ProposalDevice
from rocell.motion import MotionPhase
from rocell.simulation.collision import (
    CollisionBodyRole,
    CollisionExclusionEvidenceState,
    CollisionExclusionScope,
)

from .installed_collision_geometry import InstalledCollisionGeometryProfile
from .trajectory_execution_envelope_v2 import TrajectoryExecutionEnvelopeV2

SCHEMA = "rocell.phase_local_contact_envelope_gate.v1"


class PhaseLocalContactEnvelopeGateError(ValueError):
    """Collision or contact evidence is malformed, crossed, or insufficient."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PhaseLocalContactEnvelopeGateError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _verified_report_hash(
    report: Mapping[str, Any], field: str, label: str
) -> str:
    claimed = _digest(report.get(field), field)
    unsigned = {key: value for key, value in report.items() if key != field}
    if _sha256(unsigned) != claimed:
        raise PhaseLocalContactEnvelopeGateError(f"{label} content hash is invalid")
    return claimed


def _body_id(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PhaseLocalContactEnvelopeGateError(
            f"{label} must be nonempty unpadded text"
        )
    return value


@dataclass(frozen=True, slots=True)
class PhaseLocalContactAllowance:
    """One exact tool/target allowance valid only at a CONTACT waypoint."""

    policy_id: str
    target_id: str
    tool_body_id: str
    target_body_id: str
    engineering_evidence_sha256: str
    source_reference: str
    phase: MotionPhase = MotionPhase.CONTACT
    maximum_contact_waypoints: int = 1

    def __post_init__(self) -> None:
        _body_id(self.policy_id, "policy_id")
        _body_id(self.target_id, "target_id")
        _body_id(self.tool_body_id, "tool_body_id")
        _body_id(self.target_body_id, "target_body_id")
        _body_id(self.source_reference, "source_reference")
        _digest(self.engineering_evidence_sha256, "engineering_evidence_sha256")
        if self.tool_body_id == self.target_body_id:
            raise PhaseLocalContactEnvelopeGateError(
                "contact allowance must name two different bodies"
            )
        if self.phase is not MotionPhase.CONTACT:
            raise PhaseLocalContactEnvelopeGateError(
                "contact allowance phase must be CONTACT"
            )
        if self.maximum_contact_waypoints != 1:
            raise PhaseLocalContactEnvelopeGateError(
                "v1 permits exactly one CONTACT waypoint"
            )

    @property
    def content_sha256(self) -> str:
        return _sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "target_id": self.target_id,
            "body_pair": sorted((self.tool_body_id, self.target_body_id)),
            "phase": self.phase.value,
            "maximum_contact_waypoints": self.maximum_contact_waypoints,
            "engineering_evidence_sha256": self.engineering_evidence_sha256,
            "source_reference": self.source_reference,
            "global_exclusion": False,
            "contact_authority": False,
        }


def _validate_profile(
    profile: InstalledCollisionGeometryProfile,
    allowance: PhaseLocalContactAllowance | None,
    proposal: ModelMotionProposalV2,
) -> None:
    if not isinstance(profile, InstalledCollisionGeometryProfile):
        raise TypeError("installed_profile must be InstalledCollisionGeometryProfile")
    if any(
        item.scope is not CollisionExclusionScope.ENGINEERING_GLOBAL
        or item.evidence_state
        is not CollisionExclusionEvidenceState.ACCEPTED_ENGINEERING
        for item in profile.contract.pair_exclusions
    ):
        raise PhaseLocalContactEnvelopeGateError(
            "all global pair exclusions require accepted engineering evidence"
        )
    if allowance is None:
        return
    bodies = {item.body_id: item for item in profile.contract.bodies}
    try:
        tool = bodies[allowance.tool_body_id]
        target = bodies[allowance.target_body_id]
    except KeyError as exc:
        raise PhaseLocalContactEnvelopeGateError(
            "contact allowance body is absent from installed collision profile"
        ) from exc
    if tool.role is not CollisionBodyRole.TOOL:
        raise PhaseLocalContactEnvelopeGateError(
            "contact allowance tool body must have TOOL role"
        )
    if target.role is not CollisionBodyRole.STATIC_ENVIRONMENT:
        raise PhaseLocalContactEnvelopeGateError(
            "contact allowance target body must have STATIC_ENVIRONMENT role"
        )
    expected_target = {
        ProposalDevice.KEYBOARD: "workcell:keyboard",
        ProposalDevice.PHONE: "workcell:phone",
    }[proposal.device]
    if allowance.target_body_id != expected_target:
        raise PhaseLocalContactEnvelopeGateError(
            "contact allowance target body differs from proposal device"
        )


def bind_phase_local_contact_envelope_gate(
    proposal: ModelMotionProposalV2,
    installed_profile: InstalledCollisionGeometryProfile,
    trajectory_screening: Mapping[str, Any],
    conservative_sweep_report: Mapping[str, Any],
    envelope: TrajectoryExecutionEnvelopeV2,
    *,
    contact_allowance: PhaseLocalContactAllowance | None = None,
) -> dict[str, Any]:
    """Return a sealed, zero-authority collision-policy binding for one action."""

    if not isinstance(proposal, ModelMotionProposalV2):
        raise TypeError("proposal must be a ModelMotionProposalV2")
    if not isinstance(trajectory_screening, Mapping):
        raise TypeError("trajectory_screening must be a mapping")
    if not isinstance(conservative_sweep_report, Mapping):
        raise TypeError("conservative_sweep_report must be a mapping")
    if not isinstance(envelope, TrajectoryExecutionEnvelopeV2):
        raise TypeError("envelope must be a TrajectoryExecutionEnvelopeV2")
    if contact_allowance is not None and not isinstance(
        contact_allowance, PhaseLocalContactAllowance
    ):
        raise TypeError("contact_allowance must be a PhaseLocalContactAllowance")

    trajectory_sha256 = _verified_report_hash(
        trajectory_screening,
        "trajectory_screening_sha256",
        "trajectory screening",
    )
    sweep_sha256 = _verified_report_hash(
        conservative_sweep_report,
        "conservative_sweep_qualification_sha256",
        "conservative sweep report",
    )
    if (
        envelope.action_index != proposal.action_index
        or envelope.proposal_v2_sha256 != proposal.proposal_sha256
        or envelope.measured_envelope.trajectory_screening_sha256
        != trajectory_sha256
    ):
        raise PhaseLocalContactEnvelopeGateError(
            "trajectory envelope differs from proposal or screening lineage"
        )
    if (
        conservative_sweep_report.get("trajectory_screening_sha256")
        != trajectory_sha256
        or conservative_sweep_report.get("installed_collision_profile_sha256")
        != installed_profile.content_sha256
    ):
        raise PhaseLocalContactEnvelopeGateError(
            "conservative sweep differs from trajectory or installed profile lineage"
        )
    if (
        conservative_sweep_report.get("all_conservative_segment_sweeps_clear")
        is not True
        or conservative_sweep_report.get(
            "all_pair_exclusions_physically_accepted"
        )
        is not True
        or conservative_sweep_report.get(
            "continuous_collision_proven_for_bound_geometry"
        )
        is not True
    ):
        raise PhaseLocalContactEnvelopeGateError(
            "conservative continuous collision qualification is incomplete"
        )

    _validate_profile(installed_profile, contact_allowance, proposal)
    waypoints = trajectory_screening.get("waypoints")
    if not isinstance(waypoints, list):
        raise PhaseLocalContactEnvelopeGateError(
            "trajectory screening waypoints must be an array"
        )
    contact_waypoints = [
        item for item in waypoints
        if isinstance(item, Mapping) and item.get("phase") == MotionPhase.CONTACT.value
    ]
    if proposal.interaction is Interaction.CONTACT:
        if contact_allowance is None:
            raise PhaseLocalContactEnvelopeGateError(
                "CONTACT proposal requires a phase-local contact allowance"
            )
        if contact_allowance.target_id != proposal.target_id:
            raise PhaseLocalContactEnvelopeGateError(
                "contact allowance target differs from proposal target"
            )
        if len(contact_waypoints) != contact_allowance.maximum_contact_waypoints:
            raise PhaseLocalContactEnvelopeGateError(
                "CONTACT waypoint count differs from contact allowance"
            )
        for item in contact_waypoints:
            semantic_target = item.get("semantic_target")
            if semantic_target is not None and semantic_target != proposal.target_id:
                raise PhaseLocalContactEnvelopeGateError(
                    "CONTACT waypoint semantic target differs from proposal"
                )
    elif contact_allowance is not None or contact_waypoints:
        raise PhaseLocalContactEnvelopeGateError(
            "HOVER proposal cannot carry contact allowance or CONTACT waypoint"
        )

    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "COLLISION_POLICY_BOUND_NO_WRITE_ENVELOPE",
        "action_index": proposal.action_index,
        "proposal_v2_sha256": proposal.proposal_sha256,
        "target_id": proposal.target_id,
        "interaction": proposal.interaction.value,
        "trajectory_screening_sha256": trajectory_sha256,
        "conservative_sweep_qualification_sha256": sweep_sha256,
        "installed_collision_profile_sha256": installed_profile.content_sha256,
        "trajectory_execution_envelope_v2_sha256": envelope.envelope_v2_sha256,
        "global_pair_exclusions_accepted_engineering": True,
        "phase_local_contact_allowance": (
            None if contact_allowance is None else contact_allowance.to_dict()
        ),
        "phase_local_contact_allowance_sha256": (
            None if contact_allowance is None else contact_allowance.content_sha256
        ),
        "continuous_collision_proven_for_bound_geometry": True,
        "installed_physical_qualification_required": True,
        "controller_commands": [],
        "wire_commands": [],
        "hardware_access": False,
        "physical_authority": False,
        "contact_authority": False,
    }
    return {**report, "contact_envelope_gate_sha256": _sha256(report)}


__all__ = [
    "SCHEMA",
    "PhaseLocalContactAllowance",
    "PhaseLocalContactEnvelopeGateError",
    "bind_phase_local_contact_envelope_gate",
]
