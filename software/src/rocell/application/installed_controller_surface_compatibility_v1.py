"""Fail-closed compatibility check for an installed controller command surface.

The check is pure and grants no authority.  It prevents a finite diagnostic app
from being mistaken for the generic Waveshare T=102/T=105/T=1051 runtime needed
by the zero-write profile and a future sole writer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any

from .installed_controller_passive_evidence_v1 import (
    InstalledControllerPassiveEvidenceV1,
)


EVIDENCE_SCHEMA = "rocell.installed_controller_surface_evidence.v1"
REPORT_SCHEMA = "rocell.installed_controller_surface_compatibility_report.v1"
BLOCKER_CODES = (
    "APP_HASH_MISMATCH",
    "RUNTIME_APP_HASH_NOT_ATTESTED",
    "GENERIC_COMMAND_DISPATCH_ABSENT",
    "T102_COMMAND_UNAVAILABLE",
    "T105_FEEDBACK_REQUEST_UNAVAILABLE",
    "T1051_FEEDBACK_RESPONSE_UNAVAILABLE",
    "INDEPENDENT_REVIEW_INCOMPLETE",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class InstalledControllerSurfaceCompatibilityError(ValueError):
    """Command-surface evidence or assessment input is malformed."""


class SurfaceReviewDisposition(str, Enum):
    INDEPENDENTLY_APPROVED = "INDEPENDENTLY_APPROVED"
    UNREVIEWED = "UNREVIEWED"
    REJECTED = "REJECTED"


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise InstalledControllerSurfaceCompatibilityError(
            "surface value is not canonical JSON") from exc


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise InstalledControllerSurfaceCompatibilityError(
            f"{label} must be a SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class InstalledControllerSurfaceEvidenceV1:
    surface_id: str
    reviewed_app_sha256: str
    linked_image_review_sha256: str
    generic_command_dispatch_present: bool
    t102_command_supported: bool
    t105_feedback_request_supported: bool
    t1051_feedback_response_supported: bool
    runtime_app_hash_attested: bool
    review_disposition: SurfaceReviewDisposition
    schema: str = EVIDENCE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != EVIDENCE_SCHEMA:
            raise InstalledControllerSurfaceCompatibilityError(
                "unsupported command-surface evidence schema")
        if not isinstance(self.surface_id, str) or _IDENTIFIER.fullmatch(self.surface_id) is None:
            raise InstalledControllerSurfaceCompatibilityError("surface_id is invalid")
        _digest(self.reviewed_app_sha256, "reviewed_app_sha256")
        _digest(self.linked_image_review_sha256, "linked_image_review_sha256")
        for name in (
            "generic_command_dispatch_present", "t102_command_supported",
            "t105_feedback_request_supported", "t1051_feedback_response_supported",
            "runtime_app_hash_attested",
        ):
            if not isinstance(getattr(self, name), bool):
                raise InstalledControllerSurfaceCompatibilityError(
                    f"{name} must be boolean")
        if not isinstance(self.review_disposition, SurfaceReviewDisposition):
            raise InstalledControllerSurfaceCompatibilityError(
                "review_disposition must be typed")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "surface_id": self.surface_id,
            "reviewed_app_sha256": self.reviewed_app_sha256,
            "linked_image_review_sha256": self.linked_image_review_sha256,
            "generic_command_dispatch_present": self.generic_command_dispatch_present,
            "t102_command_supported": self.t102_command_supported,
            "t105_feedback_request_supported": self.t105_feedback_request_supported,
            "t1051_feedback_response_supported": self.t1051_feedback_response_supported,
            "runtime_app_hash_attested": self.runtime_app_hash_attested,
            "review_disposition": self.review_disposition.value,
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def evidence_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "evidence_sha256": self.evidence_sha256}


@dataclass(frozen=True, slots=True)
class InstalledControllerSurfaceCompatibilityReportV1:
    passive_evidence_sha256: str
    surface_evidence_sha256: str
    controller_session_id: str
    blockers: tuple[str, ...]
    schema: str = REPORT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REPORT_SCHEMA:
            raise InstalledControllerSurfaceCompatibilityError(
                "unsupported compatibility report schema")
        _digest(self.passive_evidence_sha256, "passive_evidence_sha256")
        _digest(self.surface_evidence_sha256, "surface_evidence_sha256")
        if not isinstance(self.controller_session_id, str) or not self.controller_session_id:
            raise InstalledControllerSurfaceCompatibilityError(
                "controller_session_id is required")
        if (
            not isinstance(self.blockers, tuple)
            or len(set(self.blockers)) != len(self.blockers)
            or any(item not in BLOCKER_CODES for item in self.blockers)
        ):
            raise InstalledControllerSurfaceCompatibilityError(
                "compatibility blockers are invalid")

    @property
    def status(self) -> str:
        return "COMPATIBLE_FOR_ZERO_WRITE_BINDING" if not self.blockers else "BLOCKED"

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "passive_evidence_sha256": self.passive_evidence_sha256,
            "surface_evidence_sha256": self.surface_evidence_sha256,
            "controller_session_id": self.controller_session_id,
            "blockers": list(self.blockers),
            "profile_binding_compatible": not self.blockers,
            "execution_authorized": False,
            "transport_authorized": False,
            "hardware_commands_generated": 0,
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def report_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "report_sha256": self.report_sha256}


def assess_installed_controller_surface_compatibility_v1(
    passive: InstalledControllerPassiveEvidenceV1,
    surface: InstalledControllerSurfaceEvidenceV1,
) -> InstalledControllerSurfaceCompatibilityReportV1:
    """Require the exact installed candidate to expose every needed protocol path."""

    if not isinstance(passive, InstalledControllerPassiveEvidenceV1):
        raise TypeError("passive must be InstalledControllerPassiveEvidenceV1")
    if not isinstance(surface, InstalledControllerSurfaceEvidenceV1):
        raise TypeError("surface must be InstalledControllerSurfaceEvidenceV1")
    blockers: list[str] = []
    checks = (
        (passive.installed_app_sha256 != surface.reviewed_app_sha256,
         "APP_HASH_MISMATCH"),
        (not surface.runtime_app_hash_attested, "RUNTIME_APP_HASH_NOT_ATTESTED"),
        (not surface.generic_command_dispatch_present,
         "GENERIC_COMMAND_DISPATCH_ABSENT"),
        (not surface.t102_command_supported, "T102_COMMAND_UNAVAILABLE"),
        (not surface.t105_feedback_request_supported,
         "T105_FEEDBACK_REQUEST_UNAVAILABLE"),
        (not surface.t1051_feedback_response_supported,
         "T1051_FEEDBACK_RESPONSE_UNAVAILABLE"),
        (surface.review_disposition is not SurfaceReviewDisposition.INDEPENDENTLY_APPROVED,
         "INDEPENDENT_REVIEW_INCOMPLETE"),
    )
    blockers.extend(code for failed, code in checks if failed)
    return InstalledControllerSurfaceCompatibilityReportV1(
        passive_evidence_sha256=passive.evidence_sha256,
        surface_evidence_sha256=surface.evidence_sha256,
        controller_session_id=passive.controller_session_id,
        blockers=tuple(blockers),
    )


__all__ = [
    "BLOCKER_CODES", "EVIDENCE_SCHEMA", "REPORT_SCHEMA",
    "InstalledControllerSurfaceCompatibilityError",
    "InstalledControllerSurfaceCompatibilityReportV1",
    "InstalledControllerSurfaceEvidenceV1", "SurfaceReviewDisposition",
    "assess_installed_controller_surface_compatibility_v1",
]
