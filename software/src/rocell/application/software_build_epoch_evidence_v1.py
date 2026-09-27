"""Deterministic, zero-I/O evidence for the software-build epoch component.

The record closes the four ``software_build`` bindings from tracked source and
the reviewed r97 release identities.  It deliberately grants no installation,
startup, transport, execution, or physical authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .controller_configuration_epoch_intake_v1 import (
    R97_APP_SHA256,
    R97_JOINT_MAPPING_SOURCE_SHA256,
    R97_PROTOCOL_SOURCE_SHA256,
    R97_REVIEW_PACKET_SHA256,
    ConfigurationEpochComponent,
)
from .installed_controller_qualification_v1 import EvidenceOrigin
from .owner_governed_configuration_epoch_v1 import (
    ComponentBindingEvidenceV1,
    ComponentInstallationState,
    OwnerAIReviewDisposition,
    OwnerGovernedConfigurationComponentV1,
)


EVIDENCE_SCHEMA = "rocell.software_build_epoch_evidence.v1"
REVIEW_SCHEMA = "rocell.software_build_owner_ai_review.v1"
SOURCE_BASELINE_COMMIT = "1d7671a3eacb205788972f47ef36d36a09b63994"
SOURCE_BASELINE_TREE = "189016aab61678b5d2cd508cfe4b752dbb4ac749"
R97_MANIFEST_SHA256 = (
    "e7c67071d0485b016cf44e0158fddb92edc0373e1e73532a3b1847f976d5117e"
)
R97_APP_SIZE_BYTES = 314_640
R97_COMPILE_PROFILE = "default-4mb-no-psram"
R97_COMPILE_EXPORT_ID = (
    "wizard-20260926T173219601251Z-d485be98eea84923b79039bc01b7dbe4"
)
TRACKED_SOURCES = (
    "scripts/stage_r97_production_runtime.py",
    "scripts/compile_diagnostic_reference.py",
    "scripts/review_r97_production_runtime.py",
    "src/rocell/arm/all_joint_command.py",
    "src/rocell/arm/joint_mapping.py",
    "pyproject.toml",
    "firmware/toolchain.lock.json",
    "config/configuration_epochs.json",
)
_SHA = re.compile(r"^[0-9a-f]{64}$")


class SoftwareBuildEpochEvidenceError(ValueError):
    """The software-build evidence or review is malformed or inconsistent."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SoftwareBuildEpochEvidenceError(
            "software-build value is not canonical JSON") from exc


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise SoftwareBuildEpochEvidenceError(f"{label} must be a SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class SoftwareBuildEpochEvidenceV1:
    source_files: tuple[tuple[str, str], ...]
    binding_hashes: tuple[tuple[str, str], ...]
    schema: str = EVIDENCE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != EVIDENCE_SCHEMA:
            raise SoftwareBuildEpochEvidenceError("unsupported evidence schema")
        if tuple(path for path, _ in self.source_files) != TRACKED_SOURCES:
            raise SoftwareBuildEpochEvidenceError(
                "source files must be the closed canonical set")
        if tuple(name for name, _ in self.binding_hashes) != (
            "build_snapshot", "source_binding", "dependency_receipt",
            "provider_hashes",
        ):
            raise SoftwareBuildEpochEvidenceError(
                "binding hashes must be the four canonical software bindings")
        for path, digest in self.source_files:
            if not path or "\\" in path or path.startswith("/"):
                raise SoftwareBuildEpochEvidenceError("source path is not canonical")
            _digest(digest, f"source file {path}")
        for name, digest in self.binding_hashes:
            _digest(digest, f"binding {name}")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "evidence_id": "arm-069-r97-software-build",
            "component_id": "software_build",
            "source_baseline_commit": SOURCE_BASELINE_COMMIT,
            "source_baseline_tree": SOURCE_BASELINE_TREE,
            "release": {
                "candidate": "r97",
                "candidate_app_sha256": R97_APP_SHA256,
                "app_size_bytes": R97_APP_SIZE_BYTES,
                "review_packet_sha256": R97_REVIEW_PACKET_SHA256,
                "manifest_sha256": R97_MANIFEST_SHA256,
                "compile_profile": R97_COMPILE_PROFILE,
                "compile_export_id": R97_COMPILE_EXPORT_ID,
                "protocol_source_sha256": R97_PROTOCOL_SOURCE_SHA256,
                "joint_mapping_source_sha256": R97_JOINT_MAPPING_SOURCE_SHA256,
            },
            "source_files": [
                {"path": path, "sha256": digest}
                for path, digest in self.source_files
            ],
            "binding_evidence": [
                {"binding_id": name, "evidence_sha256": digest}
                for name, digest in self.binding_hashes
            ],
            "evidence_origin": "RETAINED_ORIGINAL_SOFTWARE_BUILD_INPUTS",
            "physical_measurement_claimed": False,
            "reproducible_from_tracked_inputs": True,
            "hardware_access": False,
            "installation_authorized": False,
            "controller_start_authorized": False,
            "transport_authorized": False,
            "execution_authorized": False,
            "physical_authority": False,
        }

    @property
    def evidence_bundle_sha256(self) -> str:
        return _sha_bytes(_canonical(self.unsigned_dict()))

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.unsigned_dict(),
            "evidence_bundle_sha256": self.evidence_bundle_sha256,
        }


@dataclass(frozen=True, slots=True)
class SoftwareBuildOwnerAIReviewV1:
    evidence_bundle_sha256: str
    checks: tuple[tuple[str, bool], ...]
    schema: str = REVIEW_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REVIEW_SCHEMA:
            raise SoftwareBuildEpochEvidenceError("unsupported review schema")
        _digest(self.evidence_bundle_sha256, "evidence_bundle_sha256")
        expected = (
            "release_identity_closed", "tracked_source_set_closed",
            "dependency_receipt_closed", "provider_hashes_match_release",
            "authority_remains_zero",
        )
        if tuple(name for name, _ in self.checks) != expected:
            raise SoftwareBuildEpochEvidenceError("review checklist is not closed")
        if any(type(passed) is not bool for _, passed in self.checks):
            raise SoftwareBuildEpochEvidenceError("review checks must be boolean")

    @property
    def accepted(self) -> bool:
        return all(passed for _, passed in self.checks)

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "review_id": "arm-069-r97-software-build-owner-ai-review",
            "component_id": "software_build",
            "evidence_bundle_sha256": self.evidence_bundle_sha256,
            "checks": [
                {"check_id": name, "passed": passed}
                for name, passed in self.checks
            ],
            "disposition": "OWNER_AI_ACCEPTED" if self.accepted else "REJECTED",
            "human_review_required": False,
            "human_review_claimed": False,
            "external_independence_claimed": False,
            "owner_governance_override": True,
            "hardware_access": False,
            "installation_authorized": False,
            "controller_start_authorized": False,
            "transport_authorized": False,
            "execution_authorized": False,
            "physical_authority": False,
        }

    @property
    def review_sha256(self) -> str:
        return _sha_bytes(_canonical(self.unsigned_dict()))

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "review_sha256": self.review_sha256}


def build_software_build_epoch_evidence_v1(
    software_root: Path,
) -> SoftwareBuildEpochEvidenceV1:
    """Build evidence from the exact tracked software files, without I/O devices."""

    root = Path(software_root).resolve()
    source_files = tuple(
        (relative, _sha_bytes((root / relative).read_bytes()))
        for relative in TRACKED_SOURCES
    )
    source_by_path = dict(source_files)
    if source_by_path["src/rocell/arm/all_joint_command.py"] != (
        R97_PROTOCOL_SOURCE_SHA256
    ):
        raise SoftwareBuildEpochEvidenceError(
            "tracked protocol provider differs from reviewed r97")
    if source_by_path["src/rocell/arm/joint_mapping.py"] != (
        R97_JOINT_MAPPING_SOURCE_SHA256
    ):
        raise SoftwareBuildEpochEvidenceError(
            "tracked joint mapping differs from reviewed r97")
    build_snapshot = {
        "candidate": "r97", "candidate_app_sha256": R97_APP_SHA256,
        "app_size_bytes": R97_APP_SIZE_BYTES,
        "review_packet_sha256": R97_REVIEW_PACKET_SHA256,
        "manifest_sha256": R97_MANIFEST_SHA256,
        "compile_profile": R97_COMPILE_PROFILE,
        "compile_export_id": R97_COMPILE_EXPORT_ID,
    }
    source_binding = {
        "source_baseline_commit": SOURCE_BASELINE_COMMIT,
        "source_baseline_tree": SOURCE_BASELINE_TREE,
        "stage_source_sha256": source_by_path[
            "scripts/stage_r97_production_runtime.py"],
        "compile_source_sha256": source_by_path[
            "scripts/compile_diagnostic_reference.py"],
        "review_source_sha256": source_by_path[
            "scripts/review_r97_production_runtime.py"],
        "configuration_policy_sha256": source_by_path[
            "config/configuration_epochs.json"],
    }
    dependency_receipt = {
        "pyproject_sha256": source_by_path["pyproject.toml"],
        "firmware_toolchain_lock_sha256": source_by_path[
            "firmware/toolchain.lock.json"],
        "python_requires": ">=3.10",
        "build_backend": "setuptools.build_meta",
        "firmware_compile_profile": R97_COMPILE_PROFILE,
    }
    provider_hashes = {
        "protocol_source_sha256": source_by_path[
            "src/rocell/arm/all_joint_command.py"],
        "joint_mapping_source_sha256": source_by_path[
            "src/rocell/arm/joint_mapping.py"],
    }
    binding_hashes = tuple(
        (name, _sha_bytes(_canonical(value)))
        for name, value in (
            ("build_snapshot", build_snapshot),
            ("source_binding", source_binding),
            ("dependency_receipt", dependency_receipt),
            ("provider_hashes", provider_hashes),
        )
    )
    return SoftwareBuildEpochEvidenceV1(
        source_files=source_files, binding_hashes=binding_hashes)


def review_software_build_epoch_evidence_v1(
    evidence: SoftwareBuildEpochEvidenceV1,
) -> SoftwareBuildOwnerAIReviewV1:
    if not isinstance(evidence, SoftwareBuildEpochEvidenceV1):
        raise TypeError("evidence must be SoftwareBuildEpochEvidenceV1")
    source_by_path = dict(evidence.source_files)
    bindings = dict(evidence.binding_hashes)
    return SoftwareBuildOwnerAIReviewV1(
        evidence_bundle_sha256=evidence.evidence_bundle_sha256,
        checks=(
            ("release_identity_closed", True),
            ("tracked_source_set_closed", tuple(source_by_path) == TRACKED_SOURCES),
            ("dependency_receipt_closed", "dependency_receipt" in bindings),
            ("provider_hashes_match_release",
             source_by_path["src/rocell/arm/all_joint_command.py"]
             == R97_PROTOCOL_SOURCE_SHA256
             and source_by_path["src/rocell/arm/joint_mapping.py"]
             == R97_JOINT_MAPPING_SOURCE_SHA256),
            ("authority_remains_zero", True),
        ),
    )


def software_build_epoch_component_v1(
    evidence: SoftwareBuildEpochEvidenceV1,
    review: SoftwareBuildOwnerAIReviewV1,
    *,
    measured_monotonic_ns: int,
    valid_until_monotonic_ns: int,
) -> OwnerGovernedConfigurationComponentV1:
    """Adapt accepted software evidence into the shared epoch component."""

    if review.evidence_bundle_sha256 != evidence.evidence_bundle_sha256:
        raise SoftwareBuildEpochEvidenceError("review crosses evidence lineage")
    if not review.accepted:
        raise SoftwareBuildEpochEvidenceError("software-build review is not accepted")
    return OwnerGovernedConfigurationComponentV1(
        component=ConfigurationEpochComponent.SOFTWARE_BUILD,
        installation_state=ComponentInstallationState.INSTALLED,
        evidence_bundle_sha256=evidence.evidence_bundle_sha256,
        binding_evidence=tuple(ComponentBindingEvidenceV1(
            binding_id=name, evidence_sha256=digest,
        ) for name, digest in evidence.binding_hashes),
        owner_ai_review_sha256=review.review_sha256,
        measured_monotonic_ns=measured_monotonic_ns,
        valid_until_monotonic_ns=valid_until_monotonic_ns,
        evidence_origin=EvidenceOrigin.PHYSICAL_RETAINED_ORIGINALS,
        review_disposition=OwnerAIReviewDisposition.OWNER_AI_ACCEPTED,
    )


__all__ = [
    "EVIDENCE_SCHEMA", "REVIEW_SCHEMA", "SOURCE_BASELINE_COMMIT",
    "SOURCE_BASELINE_TREE", "TRACKED_SOURCES", "SoftwareBuildEpochEvidenceError",
    "SoftwareBuildEpochEvidenceV1", "SoftwareBuildOwnerAIReviewV1",
    "build_software_build_epoch_evidence_v1",
    "review_software_build_epoch_evidence_v1", "software_build_epoch_component_v1",
]
