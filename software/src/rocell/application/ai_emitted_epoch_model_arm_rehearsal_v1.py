"""Bind actual AI-emitter bytes to arm admission and a synthetic preview.

The measured planner result and the synthetic encoding rehearsal are kept as
separate facts.  The former must remain calibration-blocked; the latter proves
only that downstream identity plumbing and protocol encoding agree.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping

from rocell.models import decode_model_motion_batch_v2_json

from .synthetic_epoch_model_arm_rehearsal_v1 import (
    SyntheticEpochModelArmRehearsalReportV1,
)

SCHEMA = "rocell.ai_emitted_epoch_model_arm_rehearsal.v1"
PLANNER_BLOCKED_STATUS = "BLOCKED_CALIBRATION_MISSING_OR_STALE"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class AIEmittedEpochModelArmRehearsalError(ValueError):
    """AI bytes or arm reports do not form one zero-authority lineage."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AIEmittedEpochModelArmRehearsalError(
            "value is not canonical JSON") from exc


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise AIEmittedEpochModelArmRehearsalError(
            f"{label} must be a SHA-256 digest")
    return value


def _report_hash(
    report: Mapping[str, Any], field: str, label: str,
) -> str:
    if not isinstance(report, Mapping):
        raise TypeError(f"{label} must be a mapping")
    claimed = _digest(report.get(field), field)
    unsigned = {key: value for key, value in report.items() if key != field}
    if hashlib.sha256(_canonical(unsigned)).hexdigest() != claimed:
        raise AIEmittedEpochModelArmRehearsalError(
            f"{label} content hash is invalid")
    return claimed


def _zero_authority(report: Mapping[str, Any], label: str) -> None:
    if (
        report.get("controller_commands") != []
        or report.get("hardware_access") is not False
        or report.get("physical_authority") is not False
    ):
        raise AIEmittedEpochModelArmRehearsalError(
            f"{label} crossed the zero-authority boundary")


@dataclass(frozen=True, slots=True)
class AIEmittedEpochModelArmRehearsalReportV1:
    batch_payload_sha256: str
    batch_sha256: str
    intent_plan_sha256: str
    ingress_sha256: str
    preplanner_gate_sha256: str
    planner_gate_v2_sha256: str
    synthetic_rehearsal_report_sha256: str
    configuration_epoch_sha256: str
    preview_receipt_sha256: str
    command_count: int
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise AIEmittedEpochModelArmRehearsalError(
                "unsupported AI-emitted model-arm rehearsal schema")
        for field in (
            "batch_payload_sha256", "batch_sha256", "intent_plan_sha256",
            "ingress_sha256", "preplanner_gate_sha256",
            "planner_gate_v2_sha256", "synthetic_rehearsal_report_sha256",
            "configuration_epoch_sha256", "preview_receipt_sha256",
        ):
            _digest(getattr(self, field), field)
        if (
            isinstance(self.command_count, bool)
            or not isinstance(self.command_count, int)
            or self.command_count < 1
        ):
            raise AIEmittedEpochModelArmRehearsalError(
                "command_count must be a positive integer")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": (
                "AI_BYTES_ADMITTED_PLANNER_BLOCKED_SYNTHETIC_PREVIEW_ONLY"),
            "batch_payload_sha256": self.batch_payload_sha256,
            "batch_sha256": self.batch_sha256,
            "intent_plan_sha256": self.intent_plan_sha256,
            "ingress_sha256": self.ingress_sha256,
            "preplanner_gate_sha256": self.preplanner_gate_sha256,
            "planner_gate_v2_sha256": self.planner_gate_v2_sha256,
            "measured_planner_status": PLANNER_BLOCKED_STATUS,
            "measured_planner_next_stage": "COMMISSION_REQUIRED_CALIBRATIONS",
            "synthetic_rehearsal_report_sha256": (
                self.synthetic_rehearsal_report_sha256),
            "configuration_epoch_sha256": self.configuration_epoch_sha256,
            "preview_receipt_sha256": self.preview_receipt_sha256,
            "command_count": self.command_count,
            "actual_ai_emitter_bytes_admitted": True,
            "synthetic_downstream_preview": True,
            "production_dispatch_allowed": False,
            "installation_authorized": False,
            "controller_start_authorized": False,
            "execution_authorized": False,
            "automatic_retry": False,
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def report_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "report_sha256": self.report_sha256}


def assess_ai_emitted_epoch_model_arm_rehearsal_v1(
    *,
    batch_payload: bytes,
    ingress_report: Mapping[str, Any],
    preplanner_report: Mapping[str, Any],
    planner_report: Mapping[str, Any],
    synthetic_rehearsal_report: SyntheticEpochModelArmRehearsalReportV1,
) -> AIEmittedEpochModelArmRehearsalReportV1:
    """Verify actual emitter bytes through real arm gates and synthetic preview."""

    if not isinstance(batch_payload, bytes):
        raise TypeError("batch_payload must be bytes")
    if not isinstance(
        synthetic_rehearsal_report, SyntheticEpochModelArmRehearsalReportV1
    ):
        raise TypeError(
            "synthetic_rehearsal_report must be "
            "SyntheticEpochModelArmRehearsalReportV1")
    batch = decode_model_motion_batch_v2_json(batch_payload)
    if batch_payload != _canonical(batch.to_dict()):
        raise AIEmittedEpochModelArmRehearsalError(
            "AI batch payload is valid but not canonical emitter bytes")

    ingress_sha256 = _report_hash(
        ingress_report, "ingress_sha256", "ingress report")
    preplanner_sha256 = _report_hash(
        preplanner_report, "preplanner_gate_sha256", "preplanner report")
    planner_sha256 = _report_hash(
        planner_report, "planner_gate_v2_sha256", "planner report")
    for report, label in (
        (ingress_report, "ingress report"),
        (preplanner_report, "preplanner report"),
        (planner_report, "planner report"),
    ):
        _zero_authority(report, label)
        if report.get("batch_sha256") != batch.batch_sha256:
            raise AIEmittedEpochModelArmRehearsalError(
                f"{label} binds a different model batch")

    if ingress_report.get("status") != (
        "ACCEPTED_V2_FOR_FRESH_SEQUENTIAL_PLANNER_GATES"
    ):
        raise AIEmittedEpochModelArmRehearsalError("AI bytes were not admitted")
    if (
        preplanner_report.get("status") != "FRESH_FOR_DETERMINISTIC_PLANNING"
        or preplanner_report.get("ingress_sha256") != ingress_sha256
    ):
        raise AIEmittedEpochModelArmRehearsalError(
            "preplanner did not preserve fresh ingress lineage")
    if (
        planner_report.get("status") != PLANNER_BLOCKED_STATUS
        or planner_report.get("next_required_stage")
        != "COMMISSION_REQUIRED_CALIBRATIONS"
        or planner_report.get("ingress_sha256") != ingress_sha256
        or planner_report.get("preplanner_gate_sha256") != preplanner_sha256
        or planner_report.get("action_index") != 0
        or planner_report.get("proposal_sha256")
        != batch.proposals[0].proposal_sha256
    ):
        raise AIEmittedEpochModelArmRehearsalError(
            "measured planner result or lineage differs from the expected blocker")

    downstream = synthetic_rehearsal_report.to_dict()
    if (
        downstream["status"]
        != "ZERO_WRITE_LINEAGE_PROVEN_PRODUCTION_BLOCKED"
        or downstream["batch_sha256"] != batch.batch_sha256
        or downstream["proposal_v2_sha256"]
        != batch.proposals[0].proposal_sha256
        or downstream["production_dispatch_allowed"] is not False
        or downstream["transport_write_count"] != 0
        or downstream["hardware_access"] is not False
        or downstream["physical_authority"] is not False
    ):
        raise AIEmittedEpochModelArmRehearsalError(
            "synthetic preview does not preserve the admitted AI batch")

    return AIEmittedEpochModelArmRehearsalReportV1(
        batch_payload_sha256=hashlib.sha256(batch_payload).hexdigest(),
        batch_sha256=batch.batch_sha256,
        intent_plan_sha256=batch.intent_plan_sha256,
        ingress_sha256=ingress_sha256,
        preplanner_gate_sha256=preplanner_sha256,
        planner_gate_v2_sha256=planner_sha256,
        synthetic_rehearsal_report_sha256=(
            synthetic_rehearsal_report.report_sha256),
        configuration_epoch_sha256=(
            synthetic_rehearsal_report.configuration_epoch_sha256),
        preview_receipt_sha256=(
            synthetic_rehearsal_report.preview_receipt_sha256),
        command_count=synthetic_rehearsal_report.command_count,
    )


__all__ = [
    "PLANNER_BLOCKED_STATUS", "SCHEMA",
    "AIEmittedEpochModelArmRehearsalError",
    "AIEmittedEpochModelArmRehearsalReportV1",
    "assess_ai_emitted_epoch_model_arm_rehearsal_v1",
]
