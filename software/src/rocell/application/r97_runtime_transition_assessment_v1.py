"""Zero-I/O reconciliation of installed-surface evidence with r97 readiness."""

from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import json
from typing import Any

from .r97_independent_review_decision_v1 import (
    R97_APP_SHA256,
    R97_REVIEW_MANIFEST_SHA256,
    R97_REVIEW_PACKET_SHA256,
)


SCHEMA = "rocell.r97_runtime_transition_assessment.v1"
ARM064_RECEIPT_SHA256 = (
    "8bf9d1d5fc3f523918953633ef24b51bcf59c44b8d6df8e7fc7fbd8426c3c1d1"
)
ARM064_RESPONSE_SHA256 = (
    "148028ad79af17d51f9c75cdd7f49e04bc274fa5830e58aae4568006921c4a53"
)
EXPECTED_FAULT = b"FAULT:NOT_READY\r\n"
BLOCKERS = (
    "INSTALLED_RUNTIME_NOT_ATTESTED_AS_R97",
    "ACTIVE_FEEDBACK_SURFACE_REJECTED",
    "R97_INDEPENDENT_REVIEW_DECISION_MISSING",
    "MEASURED_CONFIGURATION_EPOCH_MISSING",
    "R97_CONFIGURATION_EPOCH_NULL",
)


class R97RuntimeTransitionAssessmentError(ValueError):
    """Retained evidence is malformed or differs from the frozen transition."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class R97RuntimeTransitionAssessmentV1:
    arm064_receipt_sha256: str
    arm064_response_sha256: str
    blockers: tuple[str, ...]

    @property
    def status(self) -> str:
        return "BLOCKED"

    def to_dict(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "schema": SCHEMA,
            "status": self.status,
            "installed_surface_assessment": "DIAGNOSTIC_SURFACE_CONSISTENT_NOT_ATTESTED",
            "arm064_receipt_sha256": self.arm064_receipt_sha256,
            "arm064_response_sha256": self.arm064_response_sha256,
            "r97_review_packet_sha256": R97_REVIEW_PACKET_SHA256,
            "r97_review_manifest_sha256": R97_REVIEW_MANIFEST_SHA256,
            "r97_app_sha256": R97_APP_SHA256,
            "blockers": list(self.blockers),
            "next_dependency": (
                "EXTERNAL_R97_REVIEW_AND_EIGHT_COMPONENT_MEASURED_EPOCH"
            ),
            "installation_intake_ready": False,
            "installation_authorized": False,
            "controller_start_authorized": False,
            "transport_authorized": False,
            "execution_authorized": False,
            "hardware_access": False,
            "physical_authority": False,
        }
        document["assessment_sha256"] = hashlib.sha256(_canonical(document)).hexdigest()
        return document


def assess_r97_runtime_transition_v1(
    arm064_receipt_bytes: bytes,
) -> R97RuntimeTransitionAssessmentV1:
    """Bind ARM-064 and report exactly why an r97 transition is not ready."""

    receipt_sha = hashlib.sha256(arm064_receipt_bytes).hexdigest()
    if receipt_sha != ARM064_RECEIPT_SHA256:
        raise R97RuntimeTransitionAssessmentError("ARM-064 receipt digest differs")
    try:
        receipt = json.loads(arm064_receipt_bytes.decode("utf-8"))
        raw = base64.b64decode(receipt["response_base64"], validate=True)
    except (UnicodeError, json.JSONDecodeError, KeyError, ValueError) as exc:
        raise R97RuntimeTransitionAssessmentError("ARM-064 receipt is malformed") from exc
    if (
        receipt.get("status") != "ACTIVE_FEEDBACK_FAILED_TERMINAL"
        or raw != EXPECTED_FAULT
        or hashlib.sha256(raw).hexdigest() != ARM064_RESPONSE_SHA256
        or receipt.get("response_sha256") != ARM064_RESPONSE_SHA256
        or receipt.get("movement_commands") != 0
        or receipt.get("torque_commands") != 0
        or receipt.get("retry_count") != 0
        or receipt.get("close_confirmed") is not True
    ):
        raise R97RuntimeTransitionAssessmentError("ARM-064 terminal facts differ")

    return R97RuntimeTransitionAssessmentV1(
        arm064_receipt_sha256=receipt_sha,
        arm064_response_sha256=ARM064_RESPONSE_SHA256,
        blockers=BLOCKERS,
    )


__all__ = [
    "ARM064_RECEIPT_SHA256", "ARM064_RESPONSE_SHA256", "BLOCKERS", "SCHEMA",
    "R97RuntimeTransitionAssessmentError", "R97RuntimeTransitionAssessmentV1",
    "assess_r97_runtime_transition_v1",
]
