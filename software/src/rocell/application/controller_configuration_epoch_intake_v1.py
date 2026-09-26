"""Zero-I/O intake for a measured, independently reviewed controller epoch.

The epoch hashes release identity and eight measured workcell components.  The
candidate app digest remains a separate field, avoiding a self-referential
firmware hash when a later build embeds the resulting epoch digest.  A passing
assessment means only that an epoch-bound build may be proposed; it never
authorizes installation, startup, transport, torque, or motion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any

from .installed_controller_qualification_v1 import EvidenceOrigin, ReviewDisposition
from .r97_independent_review_decision_v1 import (
    R97IndependentReviewDecisionV1,
    assess_r97_independent_review_decision_v1,
)


INTAKE_SCHEMA = "rocell.controller_configuration_epoch_intake.v1"
REPORT_SCHEMA = "rocell.controller_configuration_epoch_intake_report.v1"
EXPECTED_COMPONENT_IDS = (
    "software_build",
    "camera_support_optics",
    "board_tags_bench",
    "arm_controller_tool",
    "power_system",
    "keyboard_station",
    "phone_station",
    "empty_cell_safety",
)
BLOCKER_CODES = (
    "FIRMWARE_REVIEW_DECISION_MISSING",
    "FIRMWARE_REVIEW_DECISION_MISMATCH",
    "FIRMWARE_REVIEW_DECISION_BLOCKED",
    "FIRMWARE_INDEPENDENT_REVIEW_INCOMPLETE",
    "REVIEW_PACKET_MISMATCH",
    "CANDIDATE_APP_MISMATCH",
    "PROTOCOL_SOURCE_MISMATCH",
    "JOINT_MAPPING_SOURCE_MISMATCH",
    "EVALUATION_PREDATES_MEASUREMENT",
    "MEASUREMENT_STALE",
    "COMPONENT_NOT_PHYSICAL_ORIGINAL",
    "COMPONENT_INDEPENDENT_REVIEW_INCOMPLETE",
)
R97_REVIEW_PACKET_SHA256 = (
    "987cbe86d98440734d8336c704f1ecd89692675a9cb1620cb674e4132957b416"
)
R97_APP_SHA256 = "7d2e47d40141e95b611fcf37ca38d495fcf3da4dc3051f128bbae95e10840d1d"
R97_PROTOCOL_SOURCE_SHA256 = (
    "3647f6575de09a521503d02d192a8c5396ff5537015f946ef5d571c3f4a9a933"
)
R97_JOINT_MAPPING_SOURCE_SHA256 = (
    "b99bd3590c1cd4855535863a9d19a873bb2643be24403f9760f376150a71483f"
)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ControllerConfigurationEpochIntakeError(ValueError):
    """The supplied epoch evidence is malformed or exceeds this contract."""


class ConfigurationEpochComponent(str, Enum):
    SOFTWARE_BUILD = "software_build"
    CAMERA_SUPPORT_OPTICS = "camera_support_optics"
    BOARD_TAGS_BENCH = "board_tags_bench"
    ARM_CONTROLLER_TOOL = "arm_controller_tool"
    POWER_SYSTEM = "power_system"
    KEYBOARD_STATION = "keyboard_station"
    PHONE_STATION = "phone_station"
    EMPTY_CELL_SAFETY = "empty_cell_safety"


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ControllerConfigurationEpochIntakeError(
            "configuration epoch value is not canonical JSON") from exc


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise ControllerConfigurationEpochIntakeError(
            f"{label} must be a SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ControllerConfigurationEpochIntakeError(
            f"{label} must be a bounded identifier")
    return value


def _positive_ns(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ControllerConfigurationEpochIntakeError(
            f"{label} must be positive nanoseconds")
    return value


@dataclass(frozen=True, slots=True)
class MeasuredConfigurationComponentV1:
    component: ConfigurationEpochComponent
    evidence_sha256: str
    independent_review_sha256: str
    measured_monotonic_ns: int
    valid_until_monotonic_ns: int
    evidence_origin: EvidenceOrigin
    review_disposition: ReviewDisposition

    def __post_init__(self) -> None:
        if not isinstance(self.component, ConfigurationEpochComponent):
            raise ControllerConfigurationEpochIntakeError(
                "component must be a closed configuration component")
        _digest(self.evidence_sha256, "evidence_sha256")
        _digest(self.independent_review_sha256, "independent_review_sha256")
        measured = _positive_ns(
            self.measured_monotonic_ns, "measured_monotonic_ns")
        valid_until = _positive_ns(
            self.valid_until_monotonic_ns, "valid_until_monotonic_ns")
        if valid_until <= measured:
            raise ControllerConfigurationEpochIntakeError(
                "component expiry must follow measurement")
        if not isinstance(self.evidence_origin, EvidenceOrigin):
            raise ControllerConfigurationEpochIntakeError(
                "evidence_origin must be typed")
        if not isinstance(self.review_disposition, ReviewDisposition):
            raise ControllerConfigurationEpochIntakeError(
                "review_disposition must be typed")

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component.value,
            "evidence_sha256": self.evidence_sha256,
            "independent_review_sha256": self.independent_review_sha256,
            "measured_monotonic_ns": self.measured_monotonic_ns,
            "valid_until_monotonic_ns": self.valid_until_monotonic_ns,
            "evidence_origin": self.evidence_origin.value,
            "review_disposition": self.review_disposition.value,
        }


@dataclass(frozen=True, slots=True)
class ControllerConfigurationEpochIntakeV1:
    epoch_id: str
    predecessor_configuration_epoch_sha256: str | None
    r97_review_packet_sha256: str
    firmware_independent_review_sha256: str
    firmware_review_disposition: ReviewDisposition
    candidate_app_sha256: str
    protocol_source_sha256: str
    joint_mapping_source_sha256: str
    components: tuple[MeasuredConfigurationComponentV1, ...]
    schema: str = INTAKE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != INTAKE_SCHEMA:
            raise ControllerConfigurationEpochIntakeError(
                "unsupported configuration epoch intake schema")
        _identifier(self.epoch_id, "epoch_id")
        if self.predecessor_configuration_epoch_sha256 is not None:
            _digest(
                self.predecessor_configuration_epoch_sha256,
                "predecessor_configuration_epoch_sha256",
            )
        for name in (
            "r97_review_packet_sha256",
            "firmware_independent_review_sha256",
            "candidate_app_sha256",
            "protocol_source_sha256",
            "joint_mapping_source_sha256",
        ):
            _digest(getattr(self, name), name)
        if not isinstance(self.firmware_review_disposition, ReviewDisposition):
            raise ControllerConfigurationEpochIntakeError(
                "firmware_review_disposition must be typed")
        if (
            not isinstance(self.components, tuple)
            or any(type(item) is not MeasuredConfigurationComponentV1
                   for item in self.components)
            or tuple(item.component.value for item in self.components)
            != EXPECTED_COMPONENT_IDS
        ):
            raise ControllerConfigurationEpochIntakeError(
                "components must contain the eight closed components in order")
        for item in self.components:
            item.__post_init__()

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "epoch_id": self.epoch_id,
            "predecessor_configuration_epoch_sha256": (
                self.predecessor_configuration_epoch_sha256),
            "r97_review_packet_sha256": self.r97_review_packet_sha256,
            "firmware_independent_review_sha256": (
                self.firmware_independent_review_sha256),
            "firmware_review_disposition": self.firmware_review_disposition.value,
            "candidate_app_sha256": self.candidate_app_sha256,
            "protocol_source_sha256": self.protocol_source_sha256,
            "joint_mapping_source_sha256": self.joint_mapping_source_sha256,
            "components": [item.to_dict() for item in self.components],
            "epoch_scope": "RELEASE_IDENTITY_PLUS_MEASURED_WORKCELL",
            "app_digest_separate_to_avoid_self_reference": True,
            "hardware_access": False,
            "installation_authorized": False,
            "controller_start_authorized": False,
            "execution_authorized": False,
            "physical_authority": False,
        }

    @property
    def configuration_epoch_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.unsigned_dict(),
            "configuration_epoch_sha256": self.configuration_epoch_sha256,
        }


@dataclass(frozen=True, slots=True)
class ControllerConfigurationEpochIntakeReportV1:
    configuration_epoch_sha256: str
    evaluated_monotonic_ns: int
    blockers: tuple[str, ...]
    schema: str = REPORT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REPORT_SCHEMA:
            raise ControllerConfigurationEpochIntakeError(
                "unsupported configuration epoch report schema")
        _digest(self.configuration_epoch_sha256, "configuration_epoch_sha256")
        _positive_ns(self.evaluated_monotonic_ns, "evaluated_monotonic_ns")
        if (
            not isinstance(self.blockers, tuple)
            or len(self.blockers) != len(set(self.blockers))
            or any(item not in BLOCKER_CODES for item in self.blockers)
        ):
            raise ControllerConfigurationEpochIntakeError(
                "configuration epoch blockers are invalid")

    @property
    def status(self) -> str:
        return "READY_FOR_EPOCH_BOUND_BUILD_PROPOSAL" if not self.blockers else "BLOCKED"

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "configuration_epoch_sha256": self.configuration_epoch_sha256,
            "evaluated_monotonic_ns": self.evaluated_monotonic_ns,
            "blockers": list(self.blockers),
            "epoch_bound_build_proposal_ready": not self.blockers,
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


def assess_controller_configuration_epoch_intake_v1(
    intake: ControllerConfigurationEpochIntakeV1,
    *,
    evaluated_monotonic_ns: int,
    firmware_review_decision: R97IndependentReviewDecisionV1 | None = None,
    expected_review_packet_sha256: str = R97_REVIEW_PACKET_SHA256,
    expected_app_sha256: str = R97_APP_SHA256,
    expected_protocol_source_sha256: str = R97_PROTOCOL_SOURCE_SHA256,
    expected_joint_mapping_source_sha256: str = R97_JOINT_MAPPING_SOURCE_SHA256,
) -> ControllerConfigurationEpochIntakeReportV1:
    """Assess supplied originals; a pass permits only a later build proposal."""

    if not isinstance(intake, ControllerConfigurationEpochIntakeV1):
        raise TypeError("intake must be ControllerConfigurationEpochIntakeV1")
    now = _positive_ns(evaluated_monotonic_ns, "evaluated_monotonic_ns")
    for value, label in (
        (expected_review_packet_sha256, "expected_review_packet_sha256"),
        (expected_app_sha256, "expected_app_sha256"),
        (expected_protocol_source_sha256, "expected_protocol_source_sha256"),
        (expected_joint_mapping_source_sha256,
         "expected_joint_mapping_source_sha256"),
    ):
        _digest(value, label)
    blockers: list[str] = []
    if firmware_review_decision is None:
        blockers.append("FIRMWARE_REVIEW_DECISION_MISSING")
    else:
        if not isinstance(
            firmware_review_decision, R97IndependentReviewDecisionV1
        ):
            raise TypeError(
                "firmware_review_decision must be "
                "R97IndependentReviewDecisionV1 or None")
        review_report = assess_r97_independent_review_decision_v1(
            firmware_review_decision,
            expected_packet_sha256=expected_review_packet_sha256,
            expected_app_sha256=expected_app_sha256,
        )
        if (
            intake.firmware_independent_review_sha256
            != firmware_review_decision.decision_sha256
            or intake.firmware_review_disposition
            is not firmware_review_decision.disposition
        ):
            blockers.append("FIRMWARE_REVIEW_DECISION_MISMATCH")
        if review_report.blockers:
            blockers.append("FIRMWARE_REVIEW_DECISION_BLOCKED")
    checks = (
        (intake.firmware_review_disposition
         is not ReviewDisposition.INDEPENDENTLY_APPROVED,
         "FIRMWARE_INDEPENDENT_REVIEW_INCOMPLETE"),
        (intake.r97_review_packet_sha256 != expected_review_packet_sha256,
         "REVIEW_PACKET_MISMATCH"),
        (intake.candidate_app_sha256 != expected_app_sha256,
         "CANDIDATE_APP_MISMATCH"),
        (intake.protocol_source_sha256 != expected_protocol_source_sha256,
         "PROTOCOL_SOURCE_MISMATCH"),
        (intake.joint_mapping_source_sha256
         != expected_joint_mapping_source_sha256,
         "JOINT_MAPPING_SOURCE_MISMATCH"),
    )
    blockers.extend(code for failed, code in checks if failed)
    for item in intake.components:
        if now < item.measured_monotonic_ns:
            blockers.append("EVALUATION_PREDATES_MEASUREMENT")
        if now > item.valid_until_monotonic_ns:
            blockers.append("MEASUREMENT_STALE")
        if item.evidence_origin is not EvidenceOrigin.PHYSICAL_RETAINED_ORIGINALS:
            blockers.append("COMPONENT_NOT_PHYSICAL_ORIGINAL")
        if item.review_disposition is not ReviewDisposition.INDEPENDENTLY_APPROVED:
            blockers.append("COMPONENT_INDEPENDENT_REVIEW_INCOMPLETE")
    return ControllerConfigurationEpochIntakeReportV1(
        configuration_epoch_sha256=intake.configuration_epoch_sha256,
        evaluated_monotonic_ns=now,
        blockers=tuple(code for code in BLOCKER_CODES if code in blockers),
    )


__all__ = [
    "BLOCKER_CODES", "EXPECTED_COMPONENT_IDS", "INTAKE_SCHEMA", "REPORT_SCHEMA",
    "R97_APP_SHA256", "R97_JOINT_MAPPING_SOURCE_SHA256",
    "R97_PROTOCOL_SOURCE_SHA256", "R97_REVIEW_PACKET_SHA256",
    "ConfigurationEpochComponent", "ControllerConfigurationEpochIntakeError",
    "ControllerConfigurationEpochIntakeReportV1",
    "ControllerConfigurationEpochIntakeV1", "MeasuredConfigurationComponentV1",
    "assess_controller_configuration_epoch_intake_v1",
]
