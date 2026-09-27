"""Owner acceptance of the exact internal ARM-054 AI technical review.

This is an explicit governance override, not a rewritten external-review
claim.  It allows the project owner to accept one hash-bound AI review as the
review prerequisite for a later read-only endpoint-qualification intake while
retaining the provenance caveat and every hardware authorization as false.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from .native_t102_adapter_review_decision_v1 import (
    ADAPTER_SOURCE_SHA256,
    CANDIDATE_COMMIT,
    EXPECTED_CHECKS,
    MANIFEST_SHA256,
    PACKET_SHA256,
)


SCHEMA = "rocell.native_t102_owner_ai_review_acceptance.v1"
REVIEW_SCHEMA = "rocell.internal_ai_technical_review.v1"
ACCEPTED_TECHNICAL_DISPOSITION = "PASS_OFFLINE_REVIEW_SCOPE"
REQUIRED_GOVERNANCE_CAVEAT = "BLOCKED_EXTERNAL_INDEPENDENCE_REQUIRED"
AI_REVIEW_ID = "arm054-ai-review-65749a9f-20260927"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,191}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class NativeT102OwnerAIReviewAcceptanceError(ValueError):
    """The owner acceptance or its bound AI review is invalid."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise NativeT102OwnerAIReviewAcceptanceError(
            "value is not canonical JSON") from exc


def _strict_object(raw: bytes) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not 2 <= len(raw) <= 131072:
        raise NativeT102OwnerAIReviewAcceptanceError(
            "AI review must be bounded bytes")

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise NativeT102OwnerAIReviewAcceptanceError(
                    f"duplicate AI review field: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeT102OwnerAIReviewAcceptanceError(
            "AI review must be UTF-8 JSON") from exc
    if type(value) is not dict:
        raise NativeT102OwnerAIReviewAcceptanceError(
            "AI review must be a JSON object")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise NativeT102OwnerAIReviewAcceptanceError(
            f"{label} must be a bounded identifier")
    return value


def _utc(value: object) -> str:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise NativeT102OwnerAIReviewAcceptanceError(
            "accepted_utc must be whole-second UTC")
    return value


@dataclass(frozen=True, slots=True)
class NativeT102OwnerAIReviewAcceptanceV1:
    acceptance_id: str
    owner_id: str
    accepted_utc: str
    source_review_file_sha256: str
    source_review_content_sha256: str
    source_review_id: str
    reviewed_packet_sha256: str
    reviewed_manifest_sha256: str
    reviewed_candidate_commit: str
    reviewed_adapter_source_sha256: str
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise NativeT102OwnerAIReviewAcceptanceError(
                "unsupported owner acceptance schema")
        _identifier(self.acceptance_id, "acceptance_id")
        _identifier(self.owner_id, "owner_id")
        _identifier(self.source_review_id, "source_review_id")
        _utc(self.accepted_utc)
        for name in (
            "source_review_file_sha256", "source_review_content_sha256",
            "reviewed_packet_sha256", "reviewed_manifest_sha256",
            "reviewed_adapter_source_sha256",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA.fullmatch(value) is None:
                raise NativeT102OwnerAIReviewAcceptanceError(
                    f"{name} must be a SHA-256 digest")
        if not isinstance(self.reviewed_candidate_commit, str) \
                or not re.fullmatch(r"[0-9a-f]{40}", self.reviewed_candidate_commit):
            raise NativeT102OwnerAIReviewAcceptanceError(
                "reviewed_candidate_commit must be a full git object ID")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": "OWNER_ACCEPTED_AI_REVIEW_WITH_CAVEAT",
            "acceptance_id": self.acceptance_id,
            "owner_id": self.owner_id,
            "accepted_utc": self.accepted_utc,
            "source_review_file_sha256": self.source_review_file_sha256,
            "source_review_content_sha256": self.source_review_content_sha256,
            "source_review_id": self.source_review_id,
            "reviewed_packet_sha256": self.reviewed_packet_sha256,
            "reviewed_manifest_sha256": self.reviewed_manifest_sha256,
            "reviewed_candidate_commit": self.reviewed_candidate_commit,
            "reviewed_adapter_source_sha256": (
                self.reviewed_adapter_source_sha256),
            "technical_disposition": ACCEPTED_TECHNICAL_DISPOSITION,
            "provenance_caveat": REQUIRED_GOVERNANCE_CAVEAT,
            "human_review_claimed": False,
            "external_independence_claimed": False,
            "owner_governance_override": True,
            "ready_for_read_only_endpoint_qualification_intake": True,
            "endpoint_open_authorized": False,
            "controller_start_authorized": False,
            "transport_write_authorized": False,
            "execution_authorized": False,
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def acceptance_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(),
                "acceptance_sha256": self.acceptance_sha256}


def accept_native_t102_internal_ai_review_v1(
    review_bytes: bytes, *, acceptance_id: str, owner_id: str,
    accepted_utc: str,
) -> NativeT102OwnerAIReviewAcceptanceV1:
    """Bind and accept the exact passing AI review without claiming a human."""

    review = _strict_object(review_bytes)
    review_file_sha256 = hashlib.sha256(review_bytes).hexdigest()
    review_content_sha256 = hashlib.sha256(_canonical(review)).hexdigest()
    required_fields = {
        "schema", "review_id", "reviewer_id", "review_kind",
        "evidence_origin", "review_completed_utc", "reviewed_packet_sha256",
        "reviewed_manifest_sha256", "reviewed_candidate_commit",
        "reviewed_adapter_source_sha256", "technical_disposition",
        "governance_disposition", "reviewer_independence_asserted",
        "reviewer_participated_in_implementation_chain",
        "qualifies_as_external_independent_review",
        "ready_for_read_only_endpoint_qualification_intake",
        "endpoint_open_authorized", "controller_start_authorized",
        "execution_authorized", "hardware_access", "physical_authority",
        "checks", "test_runs", "open_technical_findings", "limitations",
    }
    if set(review) != required_fields:
        raise NativeT102OwnerAIReviewAcceptanceError(
            "AI review fields differ from the closed review contract")
    expected_scalars = {
        "schema": REVIEW_SCHEMA,
        "review_id": AI_REVIEW_ID,
        "reviewer_id": "openai-codex-primary-agent",
        "review_kind": "INTERNAL_AI_TECHNICAL_REVIEW",
        "evidence_origin": "SYNTHETIC_TEST_ONLY",
        "review_completed_utc": "2026-09-27T11:52:55Z",
        "reviewed_packet_sha256": PACKET_SHA256,
        "reviewed_manifest_sha256": MANIFEST_SHA256,
        "reviewed_candidate_commit": CANDIDATE_COMMIT,
        "reviewed_adapter_source_sha256": ADAPTER_SOURCE_SHA256,
        "technical_disposition": ACCEPTED_TECHNICAL_DISPOSITION,
        "governance_disposition": REQUIRED_GOVERNANCE_CAVEAT,
        "reviewer_independence_asserted": False,
        "reviewer_participated_in_implementation_chain": True,
        "qualifies_as_external_independent_review": False,
        "ready_for_read_only_endpoint_qualification_intake": False,
        "endpoint_open_authorized": False,
        "controller_start_authorized": False,
        "execution_authorized": False,
        "hardware_access": False,
        "physical_authority": False,
    }
    if any(review.get(key) != value for key, value in expected_scalars.items()):
        raise NativeT102OwnerAIReviewAcceptanceError(
            "AI review identity, disposition, provenance, or authority differs")
    checks = review.get("checks")
    if not isinstance(checks, list) or [item.get("check_id") for item in checks
                                       if type(item) is dict] != list(EXPECTED_CHECKS) \
            or len(checks) != len(EXPECTED_CHECKS) \
            or any(type(item) is not dict
                   or set(item) != {"check_id", "passed"}
                   or item["passed"] is not True for item in checks):
        raise NativeT102OwnerAIReviewAcceptanceError(
            "AI review checklist is incomplete or failed")
    if review.get("open_technical_findings") != []:
        raise NativeT102OwnerAIReviewAcceptanceError(
            "AI review contains open technical findings")
    review_id = review.get("review_id")
    _identifier(review_id, "review_id")
    return NativeT102OwnerAIReviewAcceptanceV1(
        acceptance_id=acceptance_id,
        owner_id=owner_id,
        accepted_utc=accepted_utc,
        source_review_file_sha256=review_file_sha256,
        source_review_content_sha256=review_content_sha256,
        source_review_id=review_id,
        reviewed_packet_sha256=PACKET_SHA256,
        reviewed_manifest_sha256=MANIFEST_SHA256,
        reviewed_candidate_commit=CANDIDATE_COMMIT,
        reviewed_adapter_source_sha256=ADAPTER_SOURCE_SHA256,
    )


__all__ = [
    "ACCEPTED_TECHNICAL_DISPOSITION", "AI_REVIEW_ID",
    "REQUIRED_GOVERNANCE_CAVEAT",
    "REVIEW_SCHEMA", "SCHEMA", "NativeT102OwnerAIReviewAcceptanceError",
    "NativeT102OwnerAIReviewAcceptanceV1",
    "accept_native_t102_internal_ai_review_v1",
]
