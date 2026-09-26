"""Dual-lineage wrapper for a controller-independent v2 trajectory envelope."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from rocell.models import ModelMotionBatchV2, ModelMotionProposalV2

from .trajectory_execution_envelope import TrajectoryExecutionEnvelope

SCHEMA = "rocell.trajectory_execution_envelope.v2"


class TrajectoryExecutionEnvelopeV2Error(ValueError):
    """A sealed measured trajectory does not preserve both v2 lineages."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise TrajectoryExecutionEnvelopeV2Error(
            f"{label} must be a SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise TrajectoryExecutionEnvelopeV2Error(
            f"{label} must be a SHA-256 digest") from exc
    return value


def _require_report_hash(report: Mapping[str, Any]) -> str:
    claimed = _digest(report.get("planner_gate_v2_sha256"),
                      "planner_gate_v2_sha256")
    unsigned = {
        key: value for key, value in report.items()
        if key != "planner_gate_v2_sha256"
    }
    if hashlib.sha256(_canonical(unsigned)).hexdigest() != claimed:
        raise TrajectoryExecutionEnvelopeV2Error(
            "v2 planner report content hash is invalid")
    return claimed


@dataclass(frozen=True, slots=True)
class TrajectoryExecutionEnvelopeV2:
    batch_sha256: str
    action_index: int
    proposal_v2_sha256: str
    planner_gate_v2_sha256: str
    derived_v1_surrogate_sha256: str
    measured_planner_gate_sha256: str
    measured_envelope: TrajectoryExecutionEnvelope
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise TrajectoryExecutionEnvelopeV2Error("unsupported v2 envelope schema")
        for field in (
            "batch_sha256", "proposal_v2_sha256", "planner_gate_v2_sha256",
            "derived_v1_surrogate_sha256", "measured_planner_gate_sha256",
        ):
            _digest(getattr(self, field), field)
        if isinstance(self.action_index, bool) or not isinstance(
            self.action_index, int) or self.action_index < 0:
            raise TrajectoryExecutionEnvelopeV2Error(
                "action_index must be nonnegative")
        if not isinstance(self.measured_envelope, TrajectoryExecutionEnvelope):
            raise TypeError("measured_envelope must be a TrajectoryExecutionEnvelope")
        inner = self.measured_envelope
        if (
            inner.batch_sha256 != self.batch_sha256
            or inner.action_index != self.action_index
            or inner.proposal_sha256 != self.derived_v1_surrogate_sha256
            or inner.planner_gate_sha256 != self.measured_planner_gate_sha256
        ):
            raise TrajectoryExecutionEnvelopeV2Error(
                "measured envelope differs from its v2 lineage bindings")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "batch_sha256": self.batch_sha256,
            "action_index": self.action_index,
            "proposal_v2_sha256": self.proposal_v2_sha256,
            "planner_gate_v2_sha256": self.planner_gate_v2_sha256,
            "derived_v1_surrogate_sha256": self.derived_v1_surrogate_sha256,
            "measured_planner_gate_sha256": self.measured_planner_gate_sha256,
            "measured_envelope": self.measured_envelope.to_dict(),
            "wire_commands": [],
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def envelope_v2_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.unsigned_dict(),
            "envelope_v2_sha256": self.envelope_v2_sha256,
        }


def bind_trajectory_execution_envelope_v2(
    batch: ModelMotionBatchV2,
    proposal: ModelMotionProposalV2,
    planner_report: Mapping[str, Any],
    measured_envelope: TrajectoryExecutionEnvelope,
) -> TrajectoryExecutionEnvelopeV2:
    """Seal original v2 and measured-surrogate identities without authority."""
    if not isinstance(batch, ModelMotionBatchV2):
        raise TypeError("batch must be a ModelMotionBatchV2")
    if not isinstance(proposal, ModelMotionProposalV2):
        raise TypeError("proposal must be a ModelMotionProposalV2")
    if not isinstance(planner_report, Mapping):
        raise TypeError("planner_report must be a mapping")
    if proposal.action_index >= len(batch.proposals) or (
        batch.proposals[proposal.action_index] != proposal
    ):
        raise TrajectoryExecutionEnvelopeV2Error(
            "proposal is not the indexed batch action")
    planner_sha256 = _require_report_hash(planner_report)
    if (
        planner_report.get("batch_sha256") != batch.batch_sha256
        or planner_report.get("action_index") != proposal.action_index
        or planner_report.get("proposal_sha256") != proposal.proposal_sha256
    ):
        raise TrajectoryExecutionEnvelopeV2Error(
            "planner report binds a different v2 action")
    if (
        planner_report.get("controller_commands") != []
        or planner_report.get("hardware_access") is not False
        or planner_report.get("physical_authority") is not False
    ):
        raise TrajectoryExecutionEnvelopeV2Error(
            "planner report violates zero authority")
    measured_report = planner_report.get("measured_planner_gate")
    if (
        planner_report.get("status")
        != "READY_FOR_SINGLE_ACTION_EXECUTION_ADMISSION"
        or not isinstance(measured_report, Mapping)
        or measured_report.get("status")
        != "READY_FOR_SINGLE_ACTION_EXECUTION_ADMISSION"
    ):
        raise TrajectoryExecutionEnvelopeV2Error(
            "both planner layers must be ready before envelope binding")
    return TrajectoryExecutionEnvelopeV2(
        batch_sha256=batch.batch_sha256,
        action_index=proposal.action_index,
        proposal_v2_sha256=proposal.proposal_sha256,
        planner_gate_v2_sha256=planner_sha256,
        derived_v1_surrogate_sha256=_digest(
            planner_report.get("derived_v1_surrogate_sha256"),
            "derived_v1_surrogate_sha256"),
        measured_planner_gate_sha256=_digest(
            planner_report.get("measured_planner_gate_sha256"),
            "measured_planner_gate_sha256"),
        measured_envelope=measured_envelope,
    )


__all__ = [
    "SCHEMA",
    "TrajectoryExecutionEnvelopeV2",
    "TrajectoryExecutionEnvelopeV2Error",
    "bind_trajectory_execution_envelope_v2",
]
