"""Cross-layer proof for a synthetic epoch and the model-to-arm preview path.

This module deliberately accepts only the transport-free preview receipt.  A
successful rehearsal means that one exact model batch retained its identities
through a sealed trajectory and Waveshare encoding while the unchanged
configuration-epoch assessment continued to block production use.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from rocell.models import ModelMotionBatchV2

from .controller_configuration_epoch_intake_v1 import (
    ControllerConfigurationEpochIntakeReportV1,
    ControllerConfigurationEpochIntakeV1,
    assess_controller_configuration_epoch_intake_v1,
)
from .r97_independent_review_decision_v1 import (
    R97IndependentReviewDecisionV1,
    assess_r97_independent_review_decision_v1,
)
from .trajectory_execution_envelope_v2 import TrajectoryExecutionEnvelopeV2
from .zero_write_waveshare_adapter_v1 import (
    WaveshareT102EncodingProfileV1,
    ZeroWriteWavesharePreviewReceiptV1,
)

SCHEMA = "rocell.synthetic_epoch_model_arm_rehearsal.v1"
EXPECTED_EPOCH_BLOCKERS = (
    "FIRMWARE_REVIEW_DECISION_BLOCKED",
    "COMPONENT_NOT_PHYSICAL_ORIGINAL",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SyntheticEpochModelArmRehearsalError(ValueError):
    """The supplied synthetic lineage is incomplete or crossed."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SyntheticEpochModelArmRehearsalError(
            "rehearsal report is not canonical JSON") from exc


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise SyntheticEpochModelArmRehearsalError(
            f"{label} must be a SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class SyntheticEpochModelArmRehearsalReportV1:
    review_decision_sha256: str
    review_report_sha256: str
    configuration_epoch_sha256: str
    configuration_epoch_report_sha256: str
    batch_sha256: str
    proposal_v2_sha256: str
    envelope_v2_sha256: str
    encoding_profile_sha256: str
    preview_receipt_sha256: str
    command_count: int
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise SyntheticEpochModelArmRehearsalError(
                "unsupported synthetic epoch model-arm rehearsal schema")
        for field in (
            "review_decision_sha256", "review_report_sha256",
            "configuration_epoch_sha256",
            "configuration_epoch_report_sha256", "batch_sha256",
            "proposal_v2_sha256", "envelope_v2_sha256",
            "encoding_profile_sha256", "preview_receipt_sha256",
        ):
            _digest(getattr(self, field), field)
        if (
            isinstance(self.command_count, bool)
            or not isinstance(self.command_count, int)
            or self.command_count < 1
        ):
            raise SyntheticEpochModelArmRehearsalError(
                "command_count must be a positive integer")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": "ZERO_WRITE_LINEAGE_PROVEN_PRODUCTION_BLOCKED",
            "review_decision_sha256": self.review_decision_sha256,
            "review_report_sha256": self.review_report_sha256,
            "configuration_epoch_sha256": self.configuration_epoch_sha256,
            "configuration_epoch_report_sha256": (
                self.configuration_epoch_report_sha256),
            "configuration_epoch_blockers": list(EXPECTED_EPOCH_BLOCKERS),
            "batch_sha256": self.batch_sha256,
            "proposal_v2_sha256": self.proposal_v2_sha256,
            "envelope_v2_sha256": self.envelope_v2_sha256,
            "encoding_profile_sha256": self.encoding_profile_sha256,
            "preview_receipt_sha256": self.preview_receipt_sha256,
            "command_count": self.command_count,
            "production_dispatch_allowed": False,
            "transport_opened": False,
            "transport_write_count": 0,
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


def assess_synthetic_epoch_model_arm_rehearsal_v1(
    *,
    review_decision: R97IndependentReviewDecisionV1,
    configuration_epoch: ControllerConfigurationEpochIntakeV1,
    configuration_epoch_report: ControllerConfigurationEpochIntakeReportV1,
    batch: ModelMotionBatchV2,
    envelope: TrajectoryExecutionEnvelopeV2,
    encoding_profile: WaveshareT102EncodingProfileV1,
    preview_receipt: ZeroWriteWavesharePreviewReceiptV1,
) -> SyntheticEpochModelArmRehearsalReportV1:
    """Verify the exact offline lineage without creating execution authority."""

    expected_types = (
        (review_decision, R97IndependentReviewDecisionV1, "review_decision"),
        (configuration_epoch, ControllerConfigurationEpochIntakeV1,
         "configuration_epoch"),
        (configuration_epoch_report,
         ControllerConfigurationEpochIntakeReportV1,
         "configuration_epoch_report"),
        (batch, ModelMotionBatchV2, "batch"),
        (envelope, TrajectoryExecutionEnvelopeV2, "envelope"),
        (encoding_profile, WaveshareT102EncodingProfileV1, "encoding_profile"),
        (preview_receipt, ZeroWriteWavesharePreviewReceiptV1,
         "preview_receipt"),
    )
    for value, expected, label in expected_types:
        if not isinstance(value, expected):
            raise TypeError(f"{label} must be {expected.__name__}")

    review_report = assess_r97_independent_review_decision_v1(review_decision)
    if (
        review_report.status != "SYNTHETIC_REHEARSAL_ACCEPTED"
        or review_report.blockers != ("SYNTHETIC_EVIDENCE_NOT_INDEPENDENT",)
    ):
        raise SyntheticEpochModelArmRehearsalError(
            "review decision is not the bounded synthetic rehearsal case")

    recomputed_epoch_report = assess_controller_configuration_epoch_intake_v1(
        configuration_epoch,
        evaluated_monotonic_ns=(
            configuration_epoch_report.evaluated_monotonic_ns),
        firmware_review_decision=review_decision,
    )
    if recomputed_epoch_report != configuration_epoch_report:
        raise SyntheticEpochModelArmRehearsalError(
            "configuration epoch report does not match a fresh assessment")
    if (
        configuration_epoch_report.status != "BLOCKED"
        or configuration_epoch_report.blockers != EXPECTED_EPOCH_BLOCKERS
    ):
        raise SyntheticEpochModelArmRehearsalError(
            "synthetic configuration epoch did not retain production blockers")

    inner = envelope.measured_envelope
    if envelope.batch_sha256 != batch.batch_sha256:
        raise SyntheticEpochModelArmRehearsalError(
            "trajectory envelope binds a different model batch")
    if (
        envelope.action_index >= len(batch.proposals)
        or envelope.proposal_v2_sha256
        != batch.proposals[envelope.action_index].proposal_sha256
    ):
        raise SyntheticEpochModelArmRehearsalError(
            "trajectory envelope binds a different model proposal")
    epoch_sha256 = configuration_epoch.configuration_epoch_sha256
    if (
        inner.configuration_epoch_sha256 != epoch_sha256
        or encoding_profile.configuration_epoch_sha256 != epoch_sha256
    ):
        raise SyntheticEpochModelArmRehearsalError(
            "trajectory or encoding profile binds a different configuration epoch")

    receipt = preview_receipt.to_dict()
    if (
        preview_receipt.envelope_v2_sha256 != envelope.envelope_v2_sha256
        or preview_receipt.measured_envelope_sha256 != inner.envelope_sha256
        or preview_receipt.encoding_profile_sha256
        != encoding_profile.profile_sha256
        or preview_receipt.controller_session_id != inner.controller_session_id
    ):
        raise SyntheticEpochModelArmRehearsalError(
            "zero-write receipt lineage differs from its sealed inputs")
    if (
        receipt["status"] != "ZERO_WRITE_ENCODING_ONLY"
        or receipt["command_count"] < 1
        or receipt["transport_opened"] is not False
        or receipt["transport_write_count"] != 0
        or receipt["submitted_bytes"] != []
        or receipt["automatic_retry"] is not False
        or receipt["hardware_access"] is not False
        or receipt["physical_authority"] is not False
    ):
        raise SyntheticEpochModelArmRehearsalError(
            "preview receipt crossed the zero-write boundary")

    return SyntheticEpochModelArmRehearsalReportV1(
        review_decision_sha256=review_decision.decision_sha256,
        review_report_sha256=review_report.report_sha256,
        configuration_epoch_sha256=epoch_sha256,
        configuration_epoch_report_sha256=(
            configuration_epoch_report.report_sha256),
        batch_sha256=batch.batch_sha256,
        proposal_v2_sha256=envelope.proposal_v2_sha256,
        envelope_v2_sha256=envelope.envelope_v2_sha256,
        encoding_profile_sha256=encoding_profile.profile_sha256,
        preview_receipt_sha256=preview_receipt.receipt_sha256,
        command_count=len(preview_receipt.commands),
    )


__all__ = [
    "EXPECTED_EPOCH_BLOCKERS", "SCHEMA",
    "SyntheticEpochModelArmRehearsalError",
    "SyntheticEpochModelArmRehearsalReportV1",
    "assess_synthetic_epoch_model_arm_rehearsal_v1",
]
