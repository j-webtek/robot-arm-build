"""Fail-closed intake for the camera/support/optics epoch component.

The repository baseline may describe a purchased camera and a digital support
prototype, but those are not received-unit evidence.  This module keeps that
distinction explicit and can assemble the shared epoch component only after all
four retained-original bindings have current owner-AI reviews.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import csv
import hashlib
import io
import json
from pathlib import Path
import re
from typing import Any

from .controller_configuration_epoch_intake_v1 import ConfigurationEpochComponent
from .installed_controller_qualification_v1 import EvidenceOrigin
from .owner_governed_configuration_epoch_v1 import (
    ComponentBindingEvidenceV1,
    ComponentInstallationState,
    OwnerAIReviewDisposition,
    OwnerGovernedConfigurationComponentV1,
)


INTAKE_SCHEMA = "rocell.camera_support_optics_epoch_intake.v1"
REPORT_SCHEMA = "rocell.camera_support_optics_epoch_assessment.v1"
SOURCE_BASELINE_COMMIT = "c9f7ab03d7ee2fab477828f4f4ef5566ddd46052"
SOURCE_BASELINE_TREE = "608a18b3de2a04c347af6ce235aa900c3bf3ba39"
REQUIRED_BINDINGS = (
    "camera_receipt", "camera_identity", "camera_mode_controls",
    "support_witnesses",
)
CONTROLLED_SOURCES = (
    "config/camera_profiles/arducam_b0477_imx283_16mm.json",
    "config/physical_onboarding_policy.json",
    "config/configuration_epochs.json",
    "../hardware/static_overhead_camera/config/support_design.json",
    "../hardware/static_overhead_camera/hardware_intake_template.csv",
)
BASELINE_FACT_IDS = (
    "camera_profile_record_state", "received_unit_confirmed",
    "persistent_usb_identity_sha256", "commissioned_mode",
    "camera_controls_snapshot_sha256", "support_state",
    "unresolved_hardware_intake_rows",
)
BLOCKER_CODES = (
    "RETAINED_ORIGINAL_MISSING", "EVALUATION_PREDATES_MEASUREMENT",
    "EVIDENCE_STALE", "NOT_PHYSICAL_RETAINED_ORIGINAL",
    "OWNER_AI_REVIEW_INCOMPLETE",
)
_SHA = re.compile(r"^[0-9a-f]{64}$")


class CameraSupportOpticsEpochError(ValueError):
    """Camera/support evidence is malformed or cannot satisfy the epoch."""


class BindingReviewDisposition(str, Enum):
    OWNER_AI_ACCEPTED = "OWNER_AI_ACCEPTED"
    UNREVIEWED = "UNREVIEWED"
    REJECTED = "REJECTED"


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CameraSupportOpticsEpochError(
            "camera/support value is not canonical JSON") from exc


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise CameraSupportOpticsEpochError(f"{label} must be a SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class CameraSupportBindingV1:
    binding_id: str
    evidence_sha256: str
    owner_ai_review_sha256: str
    measured_monotonic_ns: int
    valid_until_monotonic_ns: int
    evidence_origin: EvidenceOrigin
    review_disposition: BindingReviewDisposition

    def __post_init__(self) -> None:
        if self.binding_id not in REQUIRED_BINDINGS:
            raise CameraSupportOpticsEpochError("unknown camera/support binding")
        _digest(self.evidence_sha256, "evidence_sha256")
        _digest(self.owner_ai_review_sha256, "owner_ai_review_sha256")
        if (
            isinstance(self.measured_monotonic_ns, bool)
            or not isinstance(self.measured_monotonic_ns, int)
            or self.measured_monotonic_ns <= 0
            or isinstance(self.valid_until_monotonic_ns, bool)
            or not isinstance(self.valid_until_monotonic_ns, int)
            or self.valid_until_monotonic_ns <= self.measured_monotonic_ns
        ):
            raise CameraSupportOpticsEpochError("binding validity window is invalid")
        if not isinstance(self.evidence_origin, EvidenceOrigin):
            raise CameraSupportOpticsEpochError("evidence_origin must be typed")
        if not isinstance(self.review_disposition, BindingReviewDisposition):
            raise CameraSupportOpticsEpochError("review_disposition must be typed")

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "evidence_sha256": self.evidence_sha256,
            "owner_ai_review_sha256": self.owner_ai_review_sha256,
            "measured_monotonic_ns": self.measured_monotonic_ns,
            "valid_until_monotonic_ns": self.valid_until_monotonic_ns,
            "evidence_origin": self.evidence_origin.value,
            "review_disposition": self.review_disposition.value,
        }


@dataclass(frozen=True, slots=True)
class CameraSupportOpticsEpochIntakeV1:
    source_hashes: tuple[tuple[str, str], ...]
    baseline_facts: tuple[tuple[str, object], ...]
    bindings: tuple[CameraSupportBindingV1, ...] = ()
    schema: str = INTAKE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != INTAKE_SCHEMA:
            raise CameraSupportOpticsEpochError("unsupported intake schema")
        if tuple(path for path, _ in self.source_hashes) != CONTROLLED_SOURCES:
            raise CameraSupportOpticsEpochError("controlled source set differs")
        for path, digest in self.source_hashes:
            if not path:
                raise CameraSupportOpticsEpochError("source path is empty")
            _digest(digest, f"source {path}")
        if tuple(name for name, _ in self.baseline_facts) != BASELINE_FACT_IDS:
            raise CameraSupportOpticsEpochError("baseline fact set differs")
        _canonical({name: value for name, value in self.baseline_facts})
        actual = tuple(item.binding_id for item in self.bindings)
        if len(actual) != len(set(actual)) or actual != tuple(
            item for item in REQUIRED_BINDINGS if item in actual
        ):
            raise CameraSupportOpticsEpochError(
                "bindings must be a unique canonical subset")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "intake_id": "arm-070-camera-support-optics",
            "component_id": "camera_support_optics",
            "source_baseline_commit": SOURCE_BASELINE_COMMIT,
            "source_baseline_tree": SOURCE_BASELINE_TREE,
            "controlled_sources": [
                {"path": path, "sha256": digest}
                for path, digest in self.source_hashes
            ],
            "baseline_facts": {name: value for name, value in self.baseline_facts},
            "bindings": [item.to_dict() for item in self.bindings],
            "design_or_catalog_evidence_is_not_physical_original": True,
            "hardware_access": False,
            "camera_open_authorized": False,
            "installation_authorized": False,
            "controller_start_authorized": False,
            "transport_authorized": False,
            "execution_authorized": False,
            "physical_authority": False,
        }

    @property
    def intake_sha256(self) -> str:
        return _hash(_canonical(self.unsigned_dict()))

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "intake_sha256": self.intake_sha256}


@dataclass(frozen=True, slots=True)
class CameraSupportOpticsEpochAssessmentV1:
    intake_sha256: str
    evaluated_monotonic_ns: int
    binding_statuses: tuple[tuple[str, str, tuple[str, ...]], ...]
    schema: str = REPORT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REPORT_SCHEMA:
            raise CameraSupportOpticsEpochError("unsupported assessment schema")
        _digest(self.intake_sha256, "intake_sha256")
        if (
            isinstance(self.evaluated_monotonic_ns, bool)
            or not isinstance(self.evaluated_monotonic_ns, int)
            or self.evaluated_monotonic_ns <= 0
        ):
            raise CameraSupportOpticsEpochError("evaluation time must be positive")
        if tuple(item[0] for item in self.binding_statuses) != REQUIRED_BINDINGS:
            raise CameraSupportOpticsEpochError("assessment binding order differs")
        for _, status, blockers in self.binding_statuses:
            if status not in {"MISSING", "BLOCKED", "READY"}:
                raise CameraSupportOpticsEpochError("unknown binding status")
            if (
                not isinstance(blockers, tuple)
                or len(blockers) != len(set(blockers))
                or any(item not in BLOCKER_CODES for item in blockers)
            ):
                raise CameraSupportOpticsEpochError("invalid binding blockers")
            if ((status == "READY") != (not blockers)):
                raise CameraSupportOpticsEpochError("binding status contradicts blockers")
            if status == "MISSING" and blockers != ("RETAINED_ORIGINAL_MISSING",):
                raise CameraSupportOpticsEpochError("missing binding blockers differ")

    @property
    def ready(self) -> bool:
        return all(status == "READY" for _, status, _ in self.binding_statuses)

    def unsigned_dict(self) -> dict[str, Any]:
        missing = [name for name, status, _ in self.binding_statuses
                   if status == "MISSING"]
        blocked = [name for name, status, _ in self.binding_statuses
                   if status == "BLOCKED"]
        return {
            "schema": self.schema,
            "status": "READY_FOR_COMPONENT_ADMISSION" if self.ready else "BLOCKED",
            "intake_sha256": self.intake_sha256,
            "evaluated_monotonic_ns": self.evaluated_monotonic_ns,
            "binding_assessments": [
                {"binding_id": name, "status": status, "blockers": list(blockers)}
                for name, status, blockers in self.binding_statuses
            ],
            "missing_binding_ids": missing,
            "blocked_binding_ids": blocked,
            "component_admission_ready": self.ready,
            "epoch_advanced": False,
            "hardware_access": False,
            "camera_open_authorized": False,
            "installation_authorized": False,
            "controller_start_authorized": False,
            "transport_authorized": False,
            "execution_authorized": False,
            "physical_authority": False,
        }

    @property
    def assessment_sha256(self) -> str:
        return _hash(_canonical(self.unsigned_dict()))

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "assessment_sha256": self.assessment_sha256}


def build_camera_support_optics_epoch_intake_v1(
    repository_root: Path, *,
    bindings: tuple[CameraSupportBindingV1, ...] = (),
) -> CameraSupportOpticsEpochIntakeV1:
    root = Path(repository_root).resolve()
    software = root / "software"
    data = {}
    source_hashes = []
    for relative in CONTROLLED_SOURCES:
        path = (software / relative).resolve()
        raw = path.read_bytes()
        source_hashes.append((relative, _hash(raw)))
        data[relative] = raw
    profile = json.loads(data[CONTROLLED_SOURCES[0]])
    support = json.loads(data[CONTROLLED_SOURCES[3]])
    intake_rows = tuple(csv.DictReader(io.StringIO(
        data[CONTROLLED_SOURCES[4]].decode("utf-8-sig"))))
    unresolved = sum(
        row["status"] not in {"PASS", "RECORDED", "MEASURED"}
        for row in intake_rows
    )
    facts = (
        ("camera_profile_record_state", profile["record_state"]),
        ("received_unit_confirmed", profile["physical_observation"]["received"]),
        ("persistent_usb_identity_sha256",
         profile["usb_observation"]["descriptor_snapshot_sha256"]),
        ("commissioned_mode", profile["commissioning"]["commissioned_mode"]),
        ("camera_controls_snapshot_sha256",
         profile["commissioning"]["camera_controls_snapshot_sha256"]),
        ("support_state", support["state"]),
        ("unresolved_hardware_intake_rows", unresolved),
    )
    return CameraSupportOpticsEpochIntakeV1(
        source_hashes=tuple(source_hashes), baseline_facts=facts,
        bindings=bindings)


def assess_camera_support_optics_epoch_intake_v1(
    intake: CameraSupportOpticsEpochIntakeV1, *, evaluated_monotonic_ns: int,
) -> CameraSupportOpticsEpochAssessmentV1:
    if not isinstance(intake, CameraSupportOpticsEpochIntakeV1):
        raise TypeError("intake must be CameraSupportOpticsEpochIntakeV1")
    now = evaluated_monotonic_ns
    by_id = {item.binding_id: item for item in intake.bindings}
    statuses = []
    for binding_id in REQUIRED_BINDINGS:
        binding = by_id.get(binding_id)
        blockers = []
        if binding is None:
            status = "MISSING"
            blockers.append("RETAINED_ORIGINAL_MISSING")
        else:
            if now < binding.measured_monotonic_ns:
                blockers.append("EVALUATION_PREDATES_MEASUREMENT")
            if now > binding.valid_until_monotonic_ns:
                blockers.append("EVIDENCE_STALE")
            if binding.evidence_origin is not EvidenceOrigin.PHYSICAL_RETAINED_ORIGINALS:
                blockers.append("NOT_PHYSICAL_RETAINED_ORIGINAL")
            if binding.review_disposition is not BindingReviewDisposition.OWNER_AI_ACCEPTED:
                blockers.append("OWNER_AI_REVIEW_INCOMPLETE")
            status = "BLOCKED" if blockers else "READY"
        statuses.append((binding_id, status, tuple(blockers)))
    return CameraSupportOpticsEpochAssessmentV1(
        intake_sha256=intake.intake_sha256,
        evaluated_monotonic_ns=now,
        binding_statuses=tuple(statuses),
    )


def camera_support_optics_epoch_component_v1(
    intake: CameraSupportOpticsEpochIntakeV1,
    assessment: CameraSupportOpticsEpochAssessmentV1,
) -> OwnerGovernedConfigurationComponentV1:
    if assessment.intake_sha256 != intake.intake_sha256:
        raise CameraSupportOpticsEpochError("assessment crosses intake lineage")
    expected = assess_camera_support_optics_epoch_intake_v1(
        intake, evaluated_monotonic_ns=assessment.evaluated_monotonic_ns)
    if assessment != expected:
        raise CameraSupportOpticsEpochError("assessment differs from fresh evaluation")
    if not assessment.ready:
        raise CameraSupportOpticsEpochError("camera/support intake is not ready")
    return OwnerGovernedConfigurationComponentV1(
        component=ConfigurationEpochComponent.CAMERA_SUPPORT_OPTICS,
        installation_state=ComponentInstallationState.INSTALLED,
        evidence_bundle_sha256=intake.intake_sha256,
        binding_evidence=tuple(ComponentBindingEvidenceV1(
            binding_id=item.binding_id,
            evidence_sha256=item.evidence_sha256,
        ) for item in intake.bindings),
        owner_ai_review_sha256=assessment.assessment_sha256,
        measured_monotonic_ns=max(
            item.measured_monotonic_ns for item in intake.bindings),
        valid_until_monotonic_ns=min(
            item.valid_until_monotonic_ns for item in intake.bindings),
        evidence_origin=EvidenceOrigin.PHYSICAL_RETAINED_ORIGINALS,
        review_disposition=OwnerAIReviewDisposition.OWNER_AI_ACCEPTED,
    )


__all__ = [
    "BASELINE_FACT_IDS", "BLOCKER_CODES", "CONTROLLED_SOURCES", "INTAKE_SCHEMA",
    "REPORT_SCHEMA", "REQUIRED_BINDINGS",
    "BindingReviewDisposition", "CameraSupportBindingV1",
    "CameraSupportOpticsEpochAssessmentV1", "CameraSupportOpticsEpochError",
    "CameraSupportOpticsEpochIntakeV1",
    "assess_camera_support_optics_epoch_intake_v1",
    "build_camera_support_optics_epoch_intake_v1",
    "camera_support_optics_epoch_component_v1",
]
