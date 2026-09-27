"""Owner governance override for the exact r97 internal AI technical review."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from .r97_independent_review_decision_v1 import (
    R97_APP_SHA256,
    R97_REVIEW_MANIFEST_SHA256,
    R97_REVIEW_PACKET_SHA256,
    R97IndependentReviewDecisionV1,
    assess_r97_independent_review_decision_v1,
)


SCHEMA = "rocell.r97_owner_ai_review_acceptance.v1"
REQUIRED_SOURCE_STATUS = "SYNTHETIC_REHEARSAL_ACCEPTED"
GOVERNANCE_CAVEAT = "OWNER_ACCEPTED_NONINDEPENDENT_AI_TECHNICAL_REVIEW"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,191}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class R97OwnerAIReviewAcceptanceError(ValueError):
    """The owner override or its exact AI review evidence is invalid."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


@dataclass(frozen=True, slots=True)
class R97OwnerAIReviewAcceptanceV1:
    acceptance_id: str
    owner_id: str
    accepted_utc: str
    source_ai_decision_sha256: str
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise R97OwnerAIReviewAcceptanceError("unsupported acceptance schema")
        for value, label in ((self.acceptance_id, "acceptance_id"),
                             (self.owner_id, "owner_id")):
            if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
                raise R97OwnerAIReviewAcceptanceError(
                    f"{label} must be a bounded identifier")
        if not isinstance(self.accepted_utc, str) or _UTC.fullmatch(self.accepted_utc) is None:
            raise R97OwnerAIReviewAcceptanceError(
                "accepted_utc must be whole-second UTC")
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_ai_decision_sha256):
            raise R97OwnerAIReviewAcceptanceError(
                "source_ai_decision_sha256 must be a SHA-256 digest")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": "OWNER_ACCEPTED_AI_REVIEW_GOVERNANCE_OVERRIDE",
            "acceptance_id": self.acceptance_id,
            "owner_id": self.owner_id,
            "accepted_utc": self.accepted_utc,
            "source_ai_decision_sha256": self.source_ai_decision_sha256,
            "source_ai_review_status": REQUIRED_SOURCE_STATUS,
            "reviewed_packet_sha256": R97_REVIEW_PACKET_SHA256,
            "reviewed_manifest_sha256": R97_REVIEW_MANIFEST_SHA256,
            "reviewed_app_sha256": R97_APP_SHA256,
            "governance_caveat": GOVERNANCE_CAVEAT,
            "human_review_required": False,
            "human_review_claimed": False,
            "external_independence_claimed": False,
            "owner_governance_override": True,
            "ready_for_owner_governed_configuration_epoch_intake": True,
            "installation_authorized": False,
            "controller_start_authorized": False,
            "transport_authorized": False,
            "execution_authorized": False,
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def acceptance_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "acceptance_sha256": self.acceptance_sha256}


def accept_r97_internal_ai_review_v1(
    decision: R97IndependentReviewDecisionV1,
    *, acceptance_id: str, owner_id: str, accepted_utc: str,
) -> R97OwnerAIReviewAcceptanceV1:
    """Accept the exact passing synthetic review without claiming independence."""

    if not isinstance(decision, R97IndependentReviewDecisionV1):
        raise TypeError("decision must be R97IndependentReviewDecisionV1")
    report = assess_r97_independent_review_decision_v1(decision)
    if (
        report.status != REQUIRED_SOURCE_STATUS
        or report.blockers != ("SYNTHETIC_EVIDENCE_NOT_INDEPENDENT",)
        or decision.reviewed_packet_sha256 != R97_REVIEW_PACKET_SHA256
        or decision.reviewed_manifest_sha256 != R97_REVIEW_MANIFEST_SHA256
        or decision.reviewed_app_sha256 != R97_APP_SHA256
    ):
        raise R97OwnerAIReviewAcceptanceError(
            "AI review is not the exact passing non-independent r97 review")
    return R97OwnerAIReviewAcceptanceV1(
        acceptance_id=acceptance_id,
        owner_id=owner_id,
        accepted_utc=accepted_utc,
        source_ai_decision_sha256=decision.decision_sha256,
    )


def parse_r97_owner_ai_review_acceptance_v1(
    document: dict[str, Any],
) -> R97OwnerAIReviewAcceptanceV1:
    required = set(R97OwnerAIReviewAcceptanceV1(
        acceptance_id="x", owner_id="x", accepted_utc="2000-01-01T00:00:00Z",
        source_ai_decision_sha256="0" * 64).to_dict())
    if type(document) is not dict or set(document) != required:
        raise R97OwnerAIReviewAcceptanceError(
            "owner acceptance must contain exactly the closed fields")
    constants = {
        "status": "OWNER_ACCEPTED_AI_REVIEW_GOVERNANCE_OVERRIDE",
        "source_ai_review_status": REQUIRED_SOURCE_STATUS,
        "reviewed_packet_sha256": R97_REVIEW_PACKET_SHA256,
        "reviewed_manifest_sha256": R97_REVIEW_MANIFEST_SHA256,
        "reviewed_app_sha256": R97_APP_SHA256,
        "governance_caveat": GOVERNANCE_CAVEAT,
        "human_review_required": False, "human_review_claimed": False,
        "external_independence_claimed": False, "owner_governance_override": True,
        "ready_for_owner_governed_configuration_epoch_intake": True,
        "installation_authorized": False, "controller_start_authorized": False,
        "transport_authorized": False, "execution_authorized": False,
        "hardware_access": False, "physical_authority": False,
    }
    if any(document.get(key) != value for key, value in constants.items()):
        raise R97OwnerAIReviewAcceptanceError(
            "owner acceptance provenance, status, or authority differs")
    parsed = R97OwnerAIReviewAcceptanceV1(
        acceptance_id=document["acceptance_id"], owner_id=document["owner_id"],
        accepted_utc=document["accepted_utc"],
        source_ai_decision_sha256=document["source_ai_decision_sha256"],
        schema=document["schema"],
    )
    if document["acceptance_sha256"] != parsed.acceptance_sha256:
        raise R97OwnerAIReviewAcceptanceError("owner acceptance hash differs")
    return parsed


__all__ = ["GOVERNANCE_CAVEAT", "REQUIRED_SOURCE_STATUS", "SCHEMA",
           "R97OwnerAIReviewAcceptanceError", "R97OwnerAIReviewAcceptanceV1",
           "accept_r97_internal_ai_review_v1",
           "parse_r97_owner_ai_review_acceptance_v1"]
