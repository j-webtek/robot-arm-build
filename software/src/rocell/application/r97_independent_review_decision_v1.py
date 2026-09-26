"""Closed, content-addressed decision format for an external r97 reviewer.

This validates the structure and internal binding of a supplied review.  It
cannot prove who operated the reviewer identity or manufacture independence;
identity authentication and custody remain external evidence requirements.
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
from .r97_independent_review_packet import STATUS as PACKET_STATUS


DECISION_SCHEMA = "rocell.r97_independent_review_decision.v1"
REPORT_SCHEMA = "rocell.r97_independent_review_decision_report.v1"
R97_REVIEW_PACKET_SHA256 = (
    "987cbe86d98440734d8336c704f1ecd89692675a9cb1620cb674e4132957b416"
)
R97_REVIEW_MANIFEST_SHA256 = (
    "e7c67071d0485b016cf44e0158fddb92edc0373e1e73532a3b1847f976d5117e"
)
R97_APP_SHA256 = "7d2e47d40141e95b611fcf37ca38d495fcf3da4dc3051f128bbae95e10840d1d"
BLOCKER_CODES = (
    "DECISION_NOT_APPROVED",
    "PACKET_IDENTITY_MISMATCH",
    "MANIFEST_IDENTITY_MISMATCH",
    "APP_IDENTITY_MISMATCH",
    "INDEPENDENCE_NOT_ASSERTED",
    "IMPLEMENTATION_AUTHOR_CONFLICT",
    "CHECKLIST_INCOMPLETE",
    "APPROVAL_HAS_OPEN_FINDINGS",
)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,191}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class R97IndependentReviewDecisionError(ValueError):
    """The external review decision is malformed or internally inconsistent."""


class R97ReviewCheck(str, Enum):
    CLOSED_MEMBER_MANIFEST = "closed_member_manifest"
    MEMBER_HASHES = "member_hashes"
    SOURCE_INSPECTION = "source_inspection"
    REPRODUCIBLE_BUILD = "reproducible_build"
    SOURCE_IMAGE_LINKAGE = "source_image_linkage"
    SAFE_IDLE_STARTUP = "safe_idle_startup"
    SINGLE_GROUP_WRITE = "single_group_write"
    NO_RETRY_OR_REPLAY = "no_retry_or_replay"
    TERMINAL_LOCK_FAILURES = "terminal_lock_failures"
    RUNTIME_ATTESTATION = "runtime_attestation"
    NULL_EPOCH_BLOCKER = "null_epoch_blocker"


EXPECTED_CHECKS = tuple(item.value for item in R97ReviewCheck)


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise R97IndependentReviewDecisionError(
            "review decision is not canonical JSON") from exc


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise R97IndependentReviewDecisionError(
            f"{label} must be a SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise R97IndependentReviewDecisionError(
            f"{label} must be a bounded identifier")
    return value


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise R97IndependentReviewDecisionError(
            f"{label} must be whole-second UTC")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError as exc:
        raise R97IndependentReviewDecisionError(
            f"{label} must be valid UTC") from exc
    return parsed


@dataclass(frozen=True, slots=True)
class R97ReviewCheckResultV1:
    check: R97ReviewCheck
    passed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.check, R97ReviewCheck) or type(self.passed) is not bool:
            raise R97IndependentReviewDecisionError(
                "review check must use the closed typed result")

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check.value, "passed": self.passed}


@dataclass(frozen=True, slots=True)
class R97IndependentReviewDecisionV1:
    decision_id: str
    reviewer_id: str
    reviewer_affiliation: str
    reviewer_attestation_sha256: str
    review_started_utc: str
    review_completed_utc: str
    reviewed_packet_sha256: str
    reviewed_manifest_sha256: str
    reviewed_app_sha256: str
    reviewer_independence_asserted: bool
    reviewer_was_implementation_author: bool
    checks: tuple[R97ReviewCheckResultV1, ...]
    findings: tuple[str, ...]
    disposition: ReviewDisposition
    schema: str = DECISION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != DECISION_SCHEMA:
            raise R97IndependentReviewDecisionError(
                "unsupported r97 review decision schema")
        _identifier(self.decision_id, "decision_id")
        _identifier(self.reviewer_id, "reviewer_id")
        _identifier(self.reviewer_affiliation, "reviewer_affiliation")
        _digest(self.reviewer_attestation_sha256, "reviewer_attestation_sha256")
        started = _utc(self.review_started_utc, "review_started_utc")
        completed = _utc(self.review_completed_utc, "review_completed_utc")
        if completed < started:
            raise R97IndependentReviewDecisionError(
                "review completion must not predate review start")
        for name in (
            "reviewed_packet_sha256", "reviewed_manifest_sha256",
            "reviewed_app_sha256",
        ):
            _digest(getattr(self, name), name)
        if (
            type(self.reviewer_independence_asserted) is not bool
            or type(self.reviewer_was_implementation_author) is not bool
        ):
            raise R97IndependentReviewDecisionError(
                "reviewer independence fields must be booleans")
        if (
            not isinstance(self.checks, tuple)
            or any(type(item) is not R97ReviewCheckResultV1 for item in self.checks)
            or tuple(item.check.value for item in self.checks) != EXPECTED_CHECKS
        ):
            raise R97IndependentReviewDecisionError(
                "review checks must contain the closed checklist in order")
        if (
            not isinstance(self.findings, tuple)
            or len(self.findings) > 32
            or any(not isinstance(item, str) or not item.strip()
                   or item != item.strip() or len(item) > 512
                   for item in self.findings)
        ):
            raise R97IndependentReviewDecisionError(
                "findings must be bounded trimmed text")
        if len(set(self.findings)) != len(self.findings):
            raise R97IndependentReviewDecisionError("findings must be unique")
        if self.disposition not in {
            ReviewDisposition.INDEPENDENTLY_APPROVED,
            ReviewDisposition.REJECTED,
        }:
            raise R97IndependentReviewDecisionError(
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
            "reviewed_packet_sha256": self.reviewed_packet_sha256,
            "reviewed_manifest_sha256": self.reviewed_manifest_sha256,
            "reviewed_app_sha256": self.reviewed_app_sha256,
            "reviewed_packet_status": PACKET_STATUS,
            "reviewer_independence_asserted": self.reviewer_independence_asserted,
            "reviewer_was_implementation_author": (
                self.reviewer_was_implementation_author),
            "checks": [item.to_dict() for item in self.checks],
            "findings": list(self.findings),
            "disposition": self.disposition.value,
            "installation_authorized": False,
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
class R97IndependentReviewDecisionReportV1:
    decision_sha256: str
    blockers: tuple[str, ...]
    schema: str = REPORT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REPORT_SCHEMA:
            raise R97IndependentReviewDecisionError(
                "unsupported r97 review decision report schema")
        _digest(self.decision_sha256, "decision_sha256")
        if (
            not isinstance(self.blockers, tuple)
            or len(self.blockers) != len(set(self.blockers))
            or any(item not in BLOCKER_CODES for item in self.blockers)
        ):
            raise R97IndependentReviewDecisionError(
                "review decision blockers are invalid")

    @property
    def status(self) -> str:
        return "INDEPENDENT_REVIEW_ACCEPTED" if not self.blockers else "BLOCKED"

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "decision_sha256": self.decision_sha256,
            "blockers": list(self.blockers),
            "ready_for_epoch_intake": not self.blockers,
            "installation_authorized": False,
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


def assess_r97_independent_review_decision_v1(
    decision: R97IndependentReviewDecisionV1,
    *,
    expected_packet_sha256: str = R97_REVIEW_PACKET_SHA256,
    expected_manifest_sha256: str = R97_REVIEW_MANIFEST_SHA256,
    expected_app_sha256: str = R97_APP_SHA256,
) -> R97IndependentReviewDecisionReportV1:
    """Validate a supplied external decision; never create or sign one."""

    if not isinstance(decision, R97IndependentReviewDecisionV1):
        raise TypeError("decision must be R97IndependentReviewDecisionV1")
    for value, label in (
        (expected_packet_sha256, "expected_packet_sha256"),
        (expected_manifest_sha256, "expected_manifest_sha256"),
        (expected_app_sha256, "expected_app_sha256"),
    ):
        _digest(value, label)
    checks = (
        (decision.disposition is not ReviewDisposition.INDEPENDENTLY_APPROVED,
         "DECISION_NOT_APPROVED"),
        (decision.reviewed_packet_sha256 != expected_packet_sha256,
         "PACKET_IDENTITY_MISMATCH"),
        (decision.reviewed_manifest_sha256 != expected_manifest_sha256,
         "MANIFEST_IDENTITY_MISMATCH"),
        (decision.reviewed_app_sha256 != expected_app_sha256,
         "APP_IDENTITY_MISMATCH"),
        (decision.reviewer_independence_asserted is not True,
         "INDEPENDENCE_NOT_ASSERTED"),
        (decision.reviewer_was_implementation_author is not False,
         "IMPLEMENTATION_AUTHOR_CONFLICT"),
        (not all(item.passed for item in decision.checks),
         "CHECKLIST_INCOMPLETE"),
        (bool(decision.findings), "APPROVAL_HAS_OPEN_FINDINGS"),
    )
    blockers = tuple(code for failed, code in checks if failed)
    return R97IndependentReviewDecisionReportV1(
        decision_sha256=decision.decision_sha256,
        blockers=blockers,
    )


__all__ = [
    "BLOCKER_CODES", "DECISION_SCHEMA", "EXPECTED_CHECKS", "REPORT_SCHEMA",
    "R97_APP_SHA256", "R97_REVIEW_MANIFEST_SHA256", "R97_REVIEW_PACKET_SHA256",
    "R97IndependentReviewDecisionError", "R97IndependentReviewDecisionReportV1",
    "R97IndependentReviewDecisionV1", "R97ReviewCheck", "R97ReviewCheckResultV1",
    "assess_r97_independent_review_decision_v1",
]
