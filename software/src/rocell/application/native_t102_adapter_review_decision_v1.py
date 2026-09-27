"""Closed intake for an externally supplied ARM-054 adapter review decision.

The format binds one exact ARM-055 packet and validates its internal claims.
It cannot authenticate a reviewer or manufacture independence.  Even an
accepted decision grants no endpoint, controller, execution, or physical
authority; it is only eligible for a later read-only qualification intake.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from typing import Any

from .installed_controller_qualification_v1 import ReviewDisposition
from .native_t102_adapter_review_packet_v1 import STATUS as PACKET_STATUS


DECISION_SCHEMA = "rocell.native_t102_adapter_review_decision.v1"
REPORT_SCHEMA = "rocell.native_t102_adapter_review_decision_report.v1"
PACKET_SHA256 = "65749a9f122fd4f685375652b6e52a101038a88b0fed1c1b921aea6c4b059f0d"
MANIFEST_SHA256 = "0aff3af9a167e82b792fd55ff6bdd544c6ee2b961109c1dac6d7cb34c17bba4b"
CANDIDATE_COMMIT = "9bd17ac21d7fd00d18f3dd4378b9bea529b5b681"
ADAPTER_SOURCE_SHA256 = (
    "29cf25dd80c7560fb1613710fcef273466aba970b5b9333df3ed7bf9acbfafea"
)
BLOCKER_CODES = (
    "SYNTHETIC_EVIDENCE_NOT_INDEPENDENT",
    "DECISION_NOT_APPROVED",
    "PACKET_IDENTITY_MISMATCH",
    "MANIFEST_IDENTITY_MISMATCH",
    "CANDIDATE_COMMIT_MISMATCH",
    "ADAPTER_SOURCE_IDENTITY_MISMATCH",
    "INDEPENDENCE_NOT_ASSERTED",
    "IMPLEMENTATION_AUTHOR_CONFLICT",
    "CHECKLIST_INCOMPLETE",
    "APPROVAL_HAS_OPEN_FINDINGS",
    "ASSESSMENT_PREDATES_REVIEW",
    "DECISION_EXPIRED",
)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,191}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class NativeT102AdapterReviewDecisionError(ValueError):
    """The supplied decision is malformed or internally inconsistent."""


class NativeT102AdapterReviewCheck(str, Enum):
    CLOSED_PACKET_MEMBERSHIP = "closed_packet_membership"
    MEMBER_HASHES = "member_hashes"
    ADAPTER_SOURCE_INSPECTION = "adapter_source_inspection"
    PRE_POST_OPEN_IDENTITY = "pre_post_open_identity"
    SERIAL_SETTINGS_AND_TIMEOUTS = "serial_settings_and_timeouts"
    SINGLE_T102_WRITE = "single_t102_write"
    BOUNDED_T1021_T1051_CAPTURE = "bounded_t1021_t1051_capture"
    NO_FALLBACK_REOPEN_RETRY = "no_fallback_reopen_retry"
    ARM053_AUTHORITY_BEFORE_OPEN = "arm053_authority_before_open"
    DURABLE_NO_REPLAY_JOURNAL = "durable_no_replay_journal"
    UNQUALIFIED_FLAGS_RETAINED = "unqualified_flags_retained"


class NativeT102AdapterReviewEvidenceOrigin(str, Enum):
    EXTERNAL_INDEPENDENT = "EXTERNAL_INDEPENDENT"
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"


EXPECTED_CHECKS = tuple(item.value for item in NativeT102AdapterReviewCheck)


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise NativeT102AdapterReviewDecisionError(
            "review decision is not canonical JSON") from exc


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise NativeT102AdapterReviewDecisionError(
            f"{label} must be a SHA-256 digest")
    return value


def _commit(value: object) -> str:
    if not isinstance(value, str) or _COMMIT.fullmatch(value) is None:
        raise NativeT102AdapterReviewDecisionError(
            "reviewed_candidate_commit must be a full lowercase git object ID")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise NativeT102AdapterReviewDecisionError(
            f"{label} must be a bounded identifier")
    return value


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise NativeT102AdapterReviewDecisionError(
            f"{label} must be whole-second UTC")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError as exc:
        raise NativeT102AdapterReviewDecisionError(
            f"{label} must be valid UTC") from exc


@dataclass(frozen=True, slots=True)
class NativeT102AdapterReviewCheckResultV1:
    check: NativeT102AdapterReviewCheck
    passed: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.check, NativeT102AdapterReviewCheck)
            or type(self.passed) is not bool
        ):
            raise NativeT102AdapterReviewDecisionError(
                "review check must use the closed typed result")

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check.value, "passed": self.passed}


@dataclass(frozen=True, slots=True)
class NativeT102AdapterReviewDecisionV1:
    decision_id: str
    reviewer_id: str
    reviewer_affiliation: str
    reviewer_attestation_sha256: str
    review_started_utc: str
    review_completed_utc: str
    decision_valid_until_utc: str
    reviewed_packet_sha256: str
    reviewed_manifest_sha256: str
    reviewed_candidate_commit: str
    reviewed_adapter_source_sha256: str
    evidence_origin: NativeT102AdapterReviewEvidenceOrigin
    reviewer_independence_asserted: bool
    reviewer_was_implementation_author: bool
    checks: tuple[NativeT102AdapterReviewCheckResultV1, ...]
    findings: tuple[str, ...]
    disposition: ReviewDisposition
    schema: str = DECISION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != DECISION_SCHEMA:
            raise NativeT102AdapterReviewDecisionError(
                "unsupported adapter review decision schema")
        _identifier(self.decision_id, "decision_id")
        _identifier(self.reviewer_id, "reviewer_id")
        _identifier(self.reviewer_affiliation, "reviewer_affiliation")
        _digest(self.reviewer_attestation_sha256, "reviewer_attestation_sha256")
        started = _utc(self.review_started_utc, "review_started_utc")
        completed = _utc(self.review_completed_utc, "review_completed_utc")
        valid_until = _utc(
            self.decision_valid_until_utc, "decision_valid_until_utc")
        if completed < started:
            raise NativeT102AdapterReviewDecisionError(
                "review completion must not predate review start")
        if valid_until <= completed:
            raise NativeT102AdapterReviewDecisionError(
                "decision validity must end after review completion")
        _digest(self.reviewed_packet_sha256, "reviewed_packet_sha256")
        _digest(self.reviewed_manifest_sha256, "reviewed_manifest_sha256")
        _commit(self.reviewed_candidate_commit)
        _digest(
            self.reviewed_adapter_source_sha256,
            "reviewed_adapter_source_sha256",
        )
        if not isinstance(
            self.evidence_origin, NativeT102AdapterReviewEvidenceOrigin
        ):
            raise NativeT102AdapterReviewDecisionError(
                "evidence_origin must be a closed review origin")
        if (
            type(self.reviewer_independence_asserted) is not bool
            or type(self.reviewer_was_implementation_author) is not bool
        ):
            raise NativeT102AdapterReviewDecisionError(
                "reviewer independence fields must be booleans")
        if (
            not isinstance(self.checks, tuple)
            or any(
                type(item) is not NativeT102AdapterReviewCheckResultV1
                for item in self.checks
            )
            or tuple(item.check.value for item in self.checks) != EXPECTED_CHECKS
        ):
            raise NativeT102AdapterReviewDecisionError(
                "review checks must contain the closed checklist in order")
        if (
            not isinstance(self.findings, tuple)
            or len(self.findings) > 32
            or any(
                not isinstance(item, str)
                or not item.strip()
                or item != item.strip()
                or len(item) > 512
                for item in self.findings
            )
            or len(set(self.findings)) != len(self.findings)
        ):
            raise NativeT102AdapterReviewDecisionError(
                "findings must be unique bounded trimmed text")
        if self.disposition not in {
            ReviewDisposition.INDEPENDENTLY_APPROVED,
            ReviewDisposition.REJECTED,
        }:
            raise NativeT102AdapterReviewDecisionError(
                "review decision must approve or reject")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "decision_id": self.decision_id,
            "reviewer_id": self.reviewer_id,
            "reviewer_affiliation": self.reviewer_affiliation,
            "reviewer_attestation_sha256": self.reviewer_attestation_sha256,
            "review_started_utc": self.review_started_utc,
            "review_completed_utc": self.review_completed_utc,
            "decision_valid_until_utc": self.decision_valid_until_utc,
            "reviewed_packet_sha256": self.reviewed_packet_sha256,
            "reviewed_manifest_sha256": self.reviewed_manifest_sha256,
            "reviewed_candidate_commit": self.reviewed_candidate_commit,
            "reviewed_adapter_source_sha256": (
                self.reviewed_adapter_source_sha256),
            "evidence_origin": self.evidence_origin.value,
            "reviewed_packet_status": PACKET_STATUS,
            "reviewer_independence_asserted": (
                self.reviewer_independence_asserted),
            "reviewer_was_implementation_author": (
                self.reviewer_was_implementation_author),
            "checks": [item.to_dict() for item in self.checks],
            "findings": list(self.findings),
            "disposition": self.disposition.value,
            "endpoint_open_authorized": False,
            "controller_start_authorized": False,
            "execution_authorized": False,
            "physical_authority": False,
        }

    @property
    def decision_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "decision_sha256": self.decision_sha256}


@dataclass(frozen=True, slots=True)
class NativeT102AdapterReviewDecisionReportV1:
    decision_sha256: str
    assessment_utc: str
    blockers: tuple[str, ...]
    schema: str = REPORT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REPORT_SCHEMA:
            raise NativeT102AdapterReviewDecisionError(
                "unsupported adapter review report schema")
        _digest(self.decision_sha256, "decision_sha256")
        _utc(self.assessment_utc, "assessment_utc")
        if (
            not isinstance(self.blockers, tuple)
            or len(self.blockers) != len(set(self.blockers))
            or any(item not in BLOCKER_CODES for item in self.blockers)
        ):
            raise NativeT102AdapterReviewDecisionError(
                "review decision blockers are invalid")

    @property
    def status(self) -> str:
        if self.blockers == ("SYNTHETIC_EVIDENCE_NOT_INDEPENDENT",):
            return "SYNTHETIC_REHEARSAL_ACCEPTED"
        return "INDEPENDENT_REVIEW_ACCEPTED" if not self.blockers else "BLOCKED"

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "decision_sha256": self.decision_sha256,
            "assessment_utc": self.assessment_utc,
            "blockers": list(self.blockers),
            "ready_for_read_only_endpoint_qualification_intake": (
                not self.blockers),
            "synthetic_rehearsal_ready": (
                self.blockers == ("SYNTHETIC_EVIDENCE_NOT_INDEPENDENT",)),
            "endpoint_open_authorized": False,
            "controller_start_authorized": False,
            "execution_authorized": False,
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def report_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "report_sha256": self.report_sha256}


def assess_native_t102_adapter_review_decision_v1(
    decision: NativeT102AdapterReviewDecisionV1,
    *,
    assessment_utc: str,
    expected_packet_sha256: str = PACKET_SHA256,
    expected_manifest_sha256: str = MANIFEST_SHA256,
    expected_candidate_commit: str = CANDIDATE_COMMIT,
    expected_adapter_source_sha256: str = ADAPTER_SOURCE_SHA256,
) -> NativeT102AdapterReviewDecisionReportV1:
    """Assess a supplied decision without creating authority or signatures."""

    if not isinstance(decision, NativeT102AdapterReviewDecisionV1):
        raise TypeError("decision must be NativeT102AdapterReviewDecisionV1")
    _digest(expected_packet_sha256, "expected_packet_sha256")
    _digest(expected_manifest_sha256, "expected_manifest_sha256")
    _commit(expected_candidate_commit)
    _digest(expected_adapter_source_sha256, "expected_adapter_source_sha256")
    assessed = _utc(assessment_utc, "assessment_utc")
    completed = _utc(decision.review_completed_utc, "review_completed_utc")
    valid_until = _utc(
        decision.decision_valid_until_utc, "decision_valid_until_utc")
    checks = (
        (decision.evidence_origin is not
         NativeT102AdapterReviewEvidenceOrigin.EXTERNAL_INDEPENDENT,
         "SYNTHETIC_EVIDENCE_NOT_INDEPENDENT"),
        (decision.disposition is not ReviewDisposition.INDEPENDENTLY_APPROVED,
         "DECISION_NOT_APPROVED"),
        (decision.reviewed_packet_sha256 != expected_packet_sha256,
         "PACKET_IDENTITY_MISMATCH"),
        (decision.reviewed_manifest_sha256 != expected_manifest_sha256,
         "MANIFEST_IDENTITY_MISMATCH"),
        (decision.reviewed_candidate_commit != expected_candidate_commit,
         "CANDIDATE_COMMIT_MISMATCH"),
        (decision.reviewed_adapter_source_sha256 !=
         expected_adapter_source_sha256,
         "ADAPTER_SOURCE_IDENTITY_MISMATCH"),
        (decision.reviewer_independence_asserted is not True,
         "INDEPENDENCE_NOT_ASSERTED"),
        (decision.reviewer_was_implementation_author is not False,
         "IMPLEMENTATION_AUTHOR_CONFLICT"),
        (not all(item.passed for item in decision.checks),
         "CHECKLIST_INCOMPLETE"),
        (bool(decision.findings), "APPROVAL_HAS_OPEN_FINDINGS"),
        (assessed < completed, "ASSESSMENT_PREDATES_REVIEW"),
        (assessed >= valid_until, "DECISION_EXPIRED"),
    )
    return NativeT102AdapterReviewDecisionReportV1(
        decision_sha256=decision.decision_sha256,
        assessment_utc=assessment_utc,
        blockers=tuple(code for failed, code in checks if failed),
    )


def build_synthetic_native_t102_adapter_review_rehearsal_v1(
    *, rehearsal_id: str, review_started_utc: str,
    review_completed_utc: str, decision_valid_until_utc: str,
) -> tuple[
    NativeT102AdapterReviewDecisionV1,
    NativeT102AdapterReviewDecisionReportV1,
]:
    """Build deterministic integration evidence that cannot unlock intake."""

    _identifier(rehearsal_id, "rehearsal_id")
    attestation = hashlib.sha256(_canonical({
        "authority": "SYNTHETIC_TEST_ONLY",
        "purpose": "ARM-054 adapter review decision rehearsal",
        "rehearsal_id": rehearsal_id,
        "reviewed_packet_sha256": PACKET_SHA256,
    })).hexdigest()
    decision = NativeT102AdapterReviewDecisionV1(
        decision_id=f"{rehearsal_id}.synthetic-arm054-adapter-review",
        reviewer_id="rocell.synthetic-rehearsal",
        reviewer_affiliation="SYNTHETIC_TEST_ONLY",
        reviewer_attestation_sha256=attestation,
        review_started_utc=review_started_utc,
        review_completed_utc=review_completed_utc,
        decision_valid_until_utc=decision_valid_until_utc,
        reviewed_packet_sha256=PACKET_SHA256,
        reviewed_manifest_sha256=MANIFEST_SHA256,
        reviewed_candidate_commit=CANDIDATE_COMMIT,
        reviewed_adapter_source_sha256=ADAPTER_SOURCE_SHA256,
        evidence_origin=NativeT102AdapterReviewEvidenceOrigin.SYNTHETIC_TEST_ONLY,
        reviewer_independence_asserted=True,
        reviewer_was_implementation_author=False,
        checks=tuple(
            NativeT102AdapterReviewCheckResultV1(check=item, passed=True)
            for item in NativeT102AdapterReviewCheck
        ),
        findings=(),
        disposition=ReviewDisposition.INDEPENDENTLY_APPROVED,
    )
    report = assess_native_t102_adapter_review_decision_v1(
        decision, assessment_utc=review_completed_utc)
    if (
        report.status != "SYNTHETIC_REHEARSAL_ACCEPTED"
        or report.to_dict()[
            "ready_for_read_only_endpoint_qualification_intake"] is not False
    ):
        raise NativeT102AdapterReviewDecisionError(
            "synthetic decision escaped its non-production boundary")
    return decision, report


def parse_native_t102_adapter_review_decision_v1(
    document: dict[str, Any],
) -> NativeT102AdapterReviewDecisionV1:
    """Strictly decode a decision and verify its embedded content hash."""

    required = {
        "schema", "decision_id", "reviewer_id", "reviewer_affiliation",
        "reviewer_attestation_sha256", "review_started_utc",
        "review_completed_utc", "decision_valid_until_utc",
        "reviewed_packet_sha256", "reviewed_manifest_sha256",
        "reviewed_candidate_commit", "reviewed_adapter_source_sha256",
        "evidence_origin", "reviewed_packet_status",
        "reviewer_independence_asserted", "reviewer_was_implementation_author",
        "checks", "findings", "disposition", "endpoint_open_authorized",
        "controller_start_authorized", "execution_authorized",
        "physical_authority", "decision_sha256",
    }
    if type(document) is not dict or set(document) != required:
        raise NativeT102AdapterReviewDecisionError(
            "review decision JSON must contain exactly the closed fields")
    if document["reviewed_packet_status"] != PACKET_STATUS:
        raise NativeT102AdapterReviewDecisionError(
            "review decision packet status is invalid")
    for field in (
        "endpoint_open_authorized", "controller_start_authorized",
        "execution_authorized", "physical_authority",
    ):
        if document[field] is not False:
            raise NativeT102AdapterReviewDecisionError(
                f"review decision {field} must remain false")
    if not isinstance(document["checks"], list):
        raise NativeT102AdapterReviewDecisionError(
            "review decision checks must be a JSON array")
    if not isinstance(document["findings"], list):
        raise NativeT102AdapterReviewDecisionError(
            "review decision findings must be a JSON array")
    raw_checks = document["checks"]
    try:
        checks = tuple(
            NativeT102AdapterReviewCheckResultV1(
                check=NativeT102AdapterReviewCheck(item["check_id"]),
                passed=item["passed"],
            )
            for item in raw_checks
            if type(item) is dict and set(item) == {"check_id", "passed"}
        )
        decision = NativeT102AdapterReviewDecisionV1(
            decision_id=document["decision_id"],
            reviewer_id=document["reviewer_id"],
            reviewer_affiliation=document["reviewer_affiliation"],
            reviewer_attestation_sha256=document["reviewer_attestation_sha256"],
            review_started_utc=document["review_started_utc"],
            review_completed_utc=document["review_completed_utc"],
            decision_valid_until_utc=document["decision_valid_until_utc"],
            reviewed_packet_sha256=document["reviewed_packet_sha256"],
            reviewed_manifest_sha256=document["reviewed_manifest_sha256"],
            reviewed_candidate_commit=document["reviewed_candidate_commit"],
            reviewed_adapter_source_sha256=(
                document["reviewed_adapter_source_sha256"]),
            evidence_origin=NativeT102AdapterReviewEvidenceOrigin(
                document["evidence_origin"]),
            reviewer_independence_asserted=(
                document["reviewer_independence_asserted"]),
            reviewer_was_implementation_author=(
                document["reviewer_was_implementation_author"]),
            checks=checks,
            findings=tuple(document["findings"]),
            disposition=ReviewDisposition(document["disposition"]),
            schema=document["schema"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise NativeT102AdapterReviewDecisionError(
            "review decision JSON contains invalid typed values") from exc
    if len(checks) != len(raw_checks):
        raise NativeT102AdapterReviewDecisionError(
            "review decision checks contain unknown fields")
    _digest(document["decision_sha256"], "decision_sha256")
    if document["decision_sha256"] != decision.decision_sha256:
        raise NativeT102AdapterReviewDecisionError(
            "review decision content hash does not match")
    return decision


__all__ = [
    "ADAPTER_SOURCE_SHA256", "BLOCKER_CODES", "CANDIDATE_COMMIT",
    "DECISION_SCHEMA", "EXPECTED_CHECKS", "MANIFEST_SHA256", "PACKET_SHA256",
    "REPORT_SCHEMA", "NativeT102AdapterReviewCheck",
    "NativeT102AdapterReviewCheckResultV1", "NativeT102AdapterReviewDecisionError",
    "NativeT102AdapterReviewDecisionReportV1",
    "NativeT102AdapterReviewDecisionV1",
    "NativeT102AdapterReviewEvidenceOrigin",
    "assess_native_t102_adapter_review_decision_v1",
    "build_synthetic_native_t102_adapter_review_rehearsal_v1",
    "parse_native_t102_adapter_review_decision_v1",
]
