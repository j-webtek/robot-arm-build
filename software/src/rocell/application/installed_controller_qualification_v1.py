"""Fail-closed binding of reviewed installed-controller evidence to S4 profiles.

This module does not collect evidence, open a transport, or authorize motion.
It only verifies that an already reviewed physical evidence record is current
and exactly matches the zero-write encoding profile that would later be used by
a separately authorized sole writer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any

from rocell.kinematics import ARM_JOINT_NAMES

from .zero_write_waveshare_adapter_v1 import WaveshareT102EncodingProfileV1


EVIDENCE_SCHEMA = "rocell.installed_controller_qualification_evidence.v1"
REPORT_SCHEMA = "rocell.installed_controller_qualification_report.v1"
EXPECTED_T102_FIELDS = (
    "base", "shoulder", "elbow", "wrist", "roll", "hand",
)
EXPECTED_T1051_FIELDS = ("b", "s", "e", "t", "r", "g")
EXPECTED_ARM_JOINT_ORDER = ARM_JOINT_NAMES
BLOCKER_CODES = (
    "MISSING_REVIEWED_EVIDENCE", "EVIDENCE_NOT_PHYSICAL_ORIGINAL",
    "INDEPENDENT_REVIEW_INCOMPLETE", "EVALUATION_PREDATES_CAPTURE",
    "EVIDENCE_STALE", "CONTROLLER_SESSION_MISMATCH",
    "CONFIGURATION_EPOCH_MISMATCH", "JOINT_MAPPING_HASH_MISMATCH",
    "PROTOCOL_SOURCE_HASH_MISMATCH", "T102_COMMAND_FIELDS_MISMATCH",
    "T1051_FEEDBACK_FIELDS_MISMATCH", "ARM_JOINT_ORDER_MISMATCH",
    "FIXED_GRIPPER_FIELD_MISMATCH",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class InstalledControllerQualificationError(ValueError):
    """Qualification evidence or an assessment input is malformed."""


class EvidenceOrigin(str, Enum):
    PHYSICAL_RETAINED_ORIGINALS = "PHYSICAL_RETAINED_ORIGINALS"
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"


class ReviewDisposition(str, Enum):
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
        raise InstalledControllerQualificationError(
            "qualification value is not canonical JSON") from exc


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise InstalledControllerQualificationError(
            f"{label} must be a SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise InstalledControllerQualificationError(
            f"{label} must be a bounded identifier")
    return value


def _positive_ns(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InstalledControllerQualificationError(
            f"{label} must be positive nanoseconds")
    return value


def _field_tuple(value: object, label: str, maximum: int) -> tuple[str, ...]:
    if (
        not isinstance(value, tuple) or not 1 <= len(value) <= maximum
        or any(not isinstance(item, str) or not item for item in value)
        or len(set(value)) != len(value)
    ):
        raise InstalledControllerQualificationError(
            f"{label} must be a unique bounded tuple of fields")
    return value


@dataclass(frozen=True, slots=True)
class InstalledControllerQualificationEvidenceV1:
    qualification_id: str
    controller_binding_sha256: str
    installed_firmware_evidence_sha256: str
    qualified_protocol_source_sha256: str
    controller_joint_mapping_evidence_sha256: str
    controller_joint_mapping_sha256: str
    feedback_protocol_evidence_sha256: str
    startup_behavior_evidence_sha256: str
    configuration_epoch_sha256: str
    controller_session_id: str
    captured_monotonic_ns: int
    valid_until_monotonic_ns: int
    t102_command_fields: tuple[str, ...]
    t1051_feedback_fields: tuple[str, ...]
    arm_joint_order: tuple[str, ...]
    fixed_gripper_field: str
    evidence_origin: EvidenceOrigin
    review_disposition: ReviewDisposition
    schema: str = EVIDENCE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != EVIDENCE_SCHEMA:
            raise InstalledControllerQualificationError(
                "unsupported qualification evidence schema")
        _identifier(self.qualification_id, "qualification_id")
        _identifier(self.controller_session_id, "controller_session_id")
        for name in (
            "controller_binding_sha256",
            "installed_firmware_evidence_sha256",
            "qualified_protocol_source_sha256",
            "controller_joint_mapping_evidence_sha256",
            "controller_joint_mapping_sha256",
            "feedback_protocol_evidence_sha256",
            "startup_behavior_evidence_sha256",
            "configuration_epoch_sha256",
        ):
            _digest(getattr(self, name), name)
        captured = _positive_ns(self.captured_monotonic_ns, "captured_monotonic_ns")
        valid_until = _positive_ns(
            self.valid_until_monotonic_ns, "valid_until_monotonic_ns")
        if valid_until <= captured:
            raise InstalledControllerQualificationError(
                "qualification expiry must follow capture")
        object.__setattr__(self, "t102_command_fields", _field_tuple(
            self.t102_command_fields, "t102_command_fields", 16))
        object.__setattr__(self, "t1051_feedback_fields", _field_tuple(
            self.t1051_feedback_fields, "t1051_feedback_fields", 16))
        object.__setattr__(self, "arm_joint_order", _field_tuple(
            self.arm_joint_order, "arm_joint_order", 16))
        if not isinstance(self.fixed_gripper_field, str) or not self.fixed_gripper_field:
            raise InstalledControllerQualificationError(
                "fixed_gripper_field must be nonempty text")
        if not isinstance(self.evidence_origin, EvidenceOrigin):
            raise InstalledControllerQualificationError(
                "evidence_origin must be typed")
        if not isinstance(self.review_disposition, ReviewDisposition):
            raise InstalledControllerQualificationError(
                "review_disposition must be typed")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "qualification_id": self.qualification_id,
            "controller_binding_sha256": self.controller_binding_sha256,
            "installed_firmware_evidence_sha256": (
                self.installed_firmware_evidence_sha256),
            "qualified_protocol_source_sha256": (
                self.qualified_protocol_source_sha256),
            "controller_joint_mapping_evidence_sha256": (
                self.controller_joint_mapping_evidence_sha256),
            "controller_joint_mapping_sha256": (
                self.controller_joint_mapping_sha256),
            "feedback_protocol_evidence_sha256": (
                self.feedback_protocol_evidence_sha256),
            "startup_behavior_evidence_sha256": (
                self.startup_behavior_evidence_sha256),
            "configuration_epoch_sha256": self.configuration_epoch_sha256,
            "controller_session_id": self.controller_session_id,
            "captured_monotonic_ns": self.captured_monotonic_ns,
            "valid_until_monotonic_ns": self.valid_until_monotonic_ns,
            "t102_command_fields": list(self.t102_command_fields),
            "t1051_feedback_fields": list(self.t1051_feedback_fields),
            "arm_joint_order": list(self.arm_joint_order),
            "fixed_gripper_field": self.fixed_gripper_field,
            "evidence_origin": self.evidence_origin.value,
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
class InstalledControllerQualificationReportV1:
    encoding_profile_sha256: str
    qualification_evidence_sha256: str | None
    evaluated_monotonic_ns: int
    blockers: tuple[str, ...]
    schema: str = REPORT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REPORT_SCHEMA:
            raise InstalledControllerQualificationError(
                "unsupported qualification report schema")
        _digest(self.encoding_profile_sha256, "encoding_profile_sha256")
        if self.qualification_evidence_sha256 is not None:
            _digest(
                self.qualification_evidence_sha256,
                "qualification_evidence_sha256")
        _positive_ns(self.evaluated_monotonic_ns, "evaluated_monotonic_ns")
        if (
            not isinstance(self.blockers, tuple)
            or len(set(self.blockers)) != len(self.blockers)
            or any(item not in BLOCKER_CODES for item in self.blockers)
        ):
            raise InstalledControllerQualificationError(
                "qualification blockers are invalid")

    @property
    def status(self) -> str:
        return (
            "READY_FOR_ZERO_WRITE_PROFILE_BINDING"
            if not self.blockers else "BLOCKED")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "encoding_profile_sha256": self.encoding_profile_sha256,
            "qualification_evidence_sha256": self.qualification_evidence_sha256,
            "evaluated_monotonic_ns": self.evaluated_monotonic_ns,
            "blockers": list(self.blockers),
            "profile_binding_ready": not self.blockers,
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


def assess_installed_controller_qualification_v1(
    profile: WaveshareT102EncodingProfileV1,
    evidence: InstalledControllerQualificationEvidenceV1 | None,
    *,
    evaluated_monotonic_ns: int,
) -> InstalledControllerQualificationReportV1:
    """Bind reviewed evidence to a profile; never produce execution authority."""

    if not isinstance(profile, WaveshareT102EncodingProfileV1):
        raise TypeError("profile must be a WaveshareT102EncodingProfileV1")
    now = _positive_ns(evaluated_monotonic_ns, "evaluated_monotonic_ns")
    blockers: list[str] = []
    if evidence is None:
        blockers.append("MISSING_REVIEWED_EVIDENCE")
        evidence_hash = None
    elif not isinstance(evidence, InstalledControllerQualificationEvidenceV1):
        raise TypeError(
            "evidence must be InstalledControllerQualificationEvidenceV1 or None")
    else:
        evidence_hash = evidence.evidence_sha256
        checks = (
            (evidence.evidence_origin is not EvidenceOrigin.PHYSICAL_RETAINED_ORIGINALS,
             "EVIDENCE_NOT_PHYSICAL_ORIGINAL"),
            (evidence.review_disposition is not ReviewDisposition.INDEPENDENTLY_APPROVED,
             "INDEPENDENT_REVIEW_INCOMPLETE"),
            (now < evidence.captured_monotonic_ns, "EVALUATION_PREDATES_CAPTURE"),
            (now > evidence.valid_until_monotonic_ns, "EVIDENCE_STALE"),
            (profile.controller_session_id != evidence.controller_session_id,
             "CONTROLLER_SESSION_MISMATCH"),
            (profile.configuration_epoch_sha256 != evidence.configuration_epoch_sha256,
             "CONFIGURATION_EPOCH_MISMATCH"),
            (profile.controller_joint_mapping_sha256
             != evidence.controller_joint_mapping_sha256,
             "JOINT_MAPPING_HASH_MISMATCH"),
            (profile.vendor_source_sha256
             != evidence.qualified_protocol_source_sha256,
             "PROTOCOL_SOURCE_HASH_MISMATCH"),
            (evidence.t102_command_fields != EXPECTED_T102_FIELDS,
             "T102_COMMAND_FIELDS_MISMATCH"),
            (evidence.t1051_feedback_fields != EXPECTED_T1051_FIELDS,
             "T1051_FEEDBACK_FIELDS_MISMATCH"),
            (evidence.arm_joint_order != EXPECTED_ARM_JOINT_ORDER,
             "ARM_JOINT_ORDER_MISMATCH"),
            (evidence.fixed_gripper_field != "hand",
             "FIXED_GRIPPER_FIELD_MISMATCH"),
        )
        blockers.extend(code for failed, code in checks if failed)
    return InstalledControllerQualificationReportV1(
        encoding_profile_sha256=profile.profile_sha256,
        qualification_evidence_sha256=evidence_hash,
        evaluated_monotonic_ns=now,
        blockers=tuple(blockers),
    )


__all__ = [
    "BLOCKER_CODES", "EVIDENCE_SCHEMA", "REPORT_SCHEMA", "EXPECTED_ARM_JOINT_ORDER",
    "EXPECTED_T102_FIELDS", "EXPECTED_T1051_FIELDS", "EvidenceOrigin",
    "InstalledControllerQualificationError",
    "InstalledControllerQualificationEvidenceV1",
    "InstalledControllerQualificationReportV1", "ReviewDisposition",
    "assess_installed_controller_qualification_v1",
]
