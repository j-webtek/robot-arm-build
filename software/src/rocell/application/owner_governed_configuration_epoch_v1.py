"""Zero-I/O owner-governed configuration-epoch draft and assessment.

This contract supersedes the human-review prerequisite for new owner-governed
epochs without rewriting the historical independent-review contract.  Partial
drafts are intentional: their assessment names every missing component and
binding.  A complete assessment can permit only an epoch-bound build proposal;
it never grants installation, startup, transport, execution, or physical
authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any

from .controller_configuration_epoch_intake_v1 import (
    R97_APP_SHA256,
    R97_JOINT_MAPPING_SOURCE_SHA256,
    R97_PROTOCOL_SOURCE_SHA256,
    R97_REVIEW_PACKET_SHA256,
    ConfigurationEpochComponent,
    EXPECTED_COMPONENT_IDS,
)
from .installed_controller_qualification_v1 import EvidenceOrigin
from .r97_owner_ai_review_acceptance_v1 import R97OwnerAIReviewAcceptanceV1


DRAFT_SCHEMA = "rocell.owner_governed_configuration_epoch_draft.v1"
REPORT_SCHEMA = "rocell.owner_governed_configuration_epoch_assessment.v1"
ARM067_ACCEPTANCE_SHA256 = (
    "76bac6177af918fcee476f7645df6559a960ad52e68c68875db52cdf6a091698"
)
REQUIRED_COMPONENT_BINDINGS = {
    "software_build": (
        "build_snapshot", "source_binding", "dependency_receipt",
        "provider_hashes",
    ),
    "camera_support_optics": (
        "camera_receipt", "camera_identity", "camera_mode_controls",
        "support_witnesses",
    ),
    "board_tags_bench": (
        "board_measurement", "tag_map", "bench_identity",
        "board_reseat_test",
    ),
    "arm_controller_tool": (
        "arm_identity", "controller_identity", "firmware_identity",
        "tool_identity",
    ),
    "power_system": (
        "power_topology", "cutoff_test", "containment_review",
        "discharge_test",
    ),
    "keyboard_station": (
        "keyboard_identity", "keyboard_pose", "keyboard_target_map",
    ),
    "phone_station": (
        "phone_identity", "phone_pose", "screen_homography",
        "phone_target_map", "ui_state",
    ),
    "empty_cell_safety": (
        "installed_object_inventory", "collision_geometry", "startup_sweep",
        "empty_cell_witness",
    ),
}
GLOBAL_BLOCKER_CODES = (
    "OWNER_ACCEPTANCE_MISSING",
    "OWNER_ACCEPTANCE_MISMATCH",
    "REVIEW_PACKET_MISMATCH",
    "CANDIDATE_APP_MISMATCH",
    "PROTOCOL_SOURCE_MISMATCH",
    "JOINT_MAPPING_SOURCE_MISMATCH",
    "COMPONENT_MISSING",
    "REQUIRED_BINDING_MISSING",
    "EVALUATION_PREDATES_MEASUREMENT",
    "MEASUREMENT_STALE",
    "COMPONENT_NOT_PHYSICAL_ORIGINAL",
    "COMPONENT_OWNER_AI_REVIEW_INCOMPLETE",
)
COMPONENT_BLOCKER_CODES = GLOBAL_BLOCKER_CODES[6:]
_SHA = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class OwnerGovernedConfigurationEpochError(ValueError):
    """The owner-governed epoch document is malformed or inconsistent."""


class ComponentInstallationState(str, Enum):
    INSTALLED = "INSTALLED"
    CONFIRMED_NOT_INSTALLED = "CONFIRMED_NOT_INSTALLED"


class OwnerAIReviewDisposition(str, Enum):
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
        raise OwnerGovernedConfigurationEpochError(
            "owner-governed epoch value is not canonical JSON") from exc


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise OwnerGovernedConfigurationEpochError(
            f"{label} must be a SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise OwnerGovernedConfigurationEpochError(
            f"{label} must be a bounded identifier")
    return value


def _positive_ns(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise OwnerGovernedConfigurationEpochError(
            f"{label} must be positive nanoseconds")
    return value


@dataclass(frozen=True, slots=True)
class ComponentBindingEvidenceV1:
    binding_id: str
    evidence_sha256: str

    def __post_init__(self) -> None:
        _identifier(self.binding_id, "binding_id")
        _digest(self.evidence_sha256, "binding evidence_sha256")

    def to_dict(self) -> dict[str, str]:
        return {
            "binding_id": self.binding_id,
            "evidence_sha256": self.evidence_sha256,
        }


@dataclass(frozen=True, slots=True)
class OwnerGovernedConfigurationComponentV1:
    component: ConfigurationEpochComponent
    installation_state: ComponentInstallationState
    evidence_bundle_sha256: str
    binding_evidence: tuple[ComponentBindingEvidenceV1, ...]
    owner_ai_review_sha256: str
    measured_monotonic_ns: int
    valid_until_monotonic_ns: int
    evidence_origin: EvidenceOrigin
    review_disposition: OwnerAIReviewDisposition

    def __post_init__(self) -> None:
        if not isinstance(self.component, ConfigurationEpochComponent):
            raise OwnerGovernedConfigurationEpochError(
                "component must be a closed configuration component")
        if not isinstance(self.installation_state, ComponentInstallationState):
            raise OwnerGovernedConfigurationEpochError(
                "installation_state must be typed")
        _digest(self.evidence_bundle_sha256, "evidence_bundle_sha256")
        _digest(self.owner_ai_review_sha256, "owner_ai_review_sha256")
        measured = _positive_ns(
            self.measured_monotonic_ns, "measured_monotonic_ns")
        valid_until = _positive_ns(
            self.valid_until_monotonic_ns, "valid_until_monotonic_ns")
        if valid_until <= measured:
            raise OwnerGovernedConfigurationEpochError(
                "component expiry must follow measurement")
        if not isinstance(self.evidence_origin, EvidenceOrigin):
            raise OwnerGovernedConfigurationEpochError(
                "evidence_origin must be typed")
        if not isinstance(self.review_disposition, OwnerAIReviewDisposition):
            raise OwnerGovernedConfigurationEpochError(
                "review_disposition must be typed")
        if (
            not isinstance(self.binding_evidence, tuple)
            or any(type(item) is not ComponentBindingEvidenceV1
                   for item in self.binding_evidence)
        ):
            raise OwnerGovernedConfigurationEpochError(
                "binding_evidence must be typed")
        expected = REQUIRED_COMPONENT_BINDINGS[self.component.value]
        actual = tuple(item.binding_id for item in self.binding_evidence)
        if len(actual) != len(set(actual)) or actual != tuple(
            item for item in expected if item in actual
        ):
            raise OwnerGovernedConfigurationEpochError(
                "component bindings must be a unique canonical subset")

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component.value,
            "installation_state": self.installation_state.value,
            "evidence_bundle_sha256": self.evidence_bundle_sha256,
            "binding_evidence": [item.to_dict() for item in self.binding_evidence],
            "owner_ai_review_sha256": self.owner_ai_review_sha256,
            "measured_monotonic_ns": self.measured_monotonic_ns,
            "valid_until_monotonic_ns": self.valid_until_monotonic_ns,
            "evidence_origin": self.evidence_origin.value,
            "review_disposition": self.review_disposition.value,
        }


@dataclass(frozen=True, slots=True)
class OwnerGovernedConfigurationEpochDraftV1:
    epoch_id: str
    predecessor_configuration_epoch_sha256: str | None
    owner_acceptance_sha256: str
    r97_review_packet_sha256: str
    candidate_app_sha256: str
    protocol_source_sha256: str
    joint_mapping_source_sha256: str
    components: tuple[OwnerGovernedConfigurationComponentV1, ...]
    schema: str = DRAFT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != DRAFT_SCHEMA:
            raise OwnerGovernedConfigurationEpochError(
                "unsupported owner-governed epoch draft schema")
        _identifier(self.epoch_id, "epoch_id")
        if self.predecessor_configuration_epoch_sha256 is not None:
            _digest(
                self.predecessor_configuration_epoch_sha256,
                "predecessor_configuration_epoch_sha256",
            )
        for name in (
            "owner_acceptance_sha256", "r97_review_packet_sha256",
            "candidate_app_sha256", "protocol_source_sha256",
            "joint_mapping_source_sha256",
        ):
            _digest(getattr(self, name), name)
        if (
            not isinstance(self.components, tuple)
            or any(type(item) is not OwnerGovernedConfigurationComponentV1
                   for item in self.components)
        ):
            raise OwnerGovernedConfigurationEpochError(
                "components must be typed")
        actual = tuple(item.component.value for item in self.components)
        if len(actual) != len(set(actual)) or actual != tuple(
            item for item in EXPECTED_COMPONENT_IDS if item in actual
        ):
            raise OwnerGovernedConfigurationEpochError(
                "components must be a unique canonical subset")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "epoch_id": self.epoch_id,
            "predecessor_configuration_epoch_sha256": (
                self.predecessor_configuration_epoch_sha256),
            "owner_acceptance_sha256": self.owner_acceptance_sha256,
            "r97_review_packet_sha256": self.r97_review_packet_sha256,
            "candidate_app_sha256": self.candidate_app_sha256,
            "protocol_source_sha256": self.protocol_source_sha256,
            "joint_mapping_source_sha256": self.joint_mapping_source_sha256,
            "components": [item.to_dict() for item in self.components],
            "epoch_scope": "OWNER_GOVERNED_RELEASE_PLUS_MEASURED_WORKCELL",
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
    def draft_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "draft_sha256": self.draft_sha256}


@dataclass(frozen=True, slots=True)
class ComponentAssessmentV1:
    component: ConfigurationEpochComponent
    blockers: tuple[str, ...]
    missing_binding_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.component, ConfigurationEpochComponent):
            raise OwnerGovernedConfigurationEpochError(
                "assessment component must be typed")
        if (
            not isinstance(self.blockers, tuple)
            or len(self.blockers) != len(set(self.blockers))
            or any(item not in COMPONENT_BLOCKER_CODES for item in self.blockers)
        ):
            raise OwnerGovernedConfigurationEpochError(
                "component assessment blockers are invalid")
        expected = REQUIRED_COMPONENT_BINDINGS[self.component.value]
        if self.missing_binding_ids != tuple(
            item for item in expected if item in self.missing_binding_ids
        ):
            raise OwnerGovernedConfigurationEpochError(
                "missing bindings must be a canonical subset")

    @property
    def status(self) -> str:
        if "COMPONENT_MISSING" in self.blockers:
            return "MISSING"
        return "BLOCKED" if self.blockers else "READY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component.value,
            "status": self.status,
            "blockers": list(self.blockers),
            "missing_binding_ids": list(self.missing_binding_ids),
        }


@dataclass(frozen=True, slots=True)
class OwnerGovernedConfigurationEpochAssessmentV1:
    draft_sha256: str
    evaluated_monotonic_ns: int
    blockers: tuple[str, ...]
    component_assessments: tuple[ComponentAssessmentV1, ...]
    schema: str = REPORT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REPORT_SCHEMA:
            raise OwnerGovernedConfigurationEpochError(
                "unsupported owner-governed epoch assessment schema")
        _digest(self.draft_sha256, "draft_sha256")
        _positive_ns(self.evaluated_monotonic_ns, "evaluated_monotonic_ns")
        if (
            not isinstance(self.blockers, tuple)
            or len(self.blockers) != len(set(self.blockers))
            or any(item not in GLOBAL_BLOCKER_CODES for item in self.blockers)
        ):
            raise OwnerGovernedConfigurationEpochError(
                "owner-governed epoch blockers are invalid")
        if (
            not isinstance(self.component_assessments, tuple)
            or tuple(item.component.value for item in self.component_assessments)
            != EXPECTED_COMPONENT_IDS
        ):
            raise OwnerGovernedConfigurationEpochError(
                "assessment must cover all eight components in order")

    @property
    def ready(self) -> bool:
        return not self.blockers

    def unsigned_dict(self) -> dict[str, Any]:
        missing = tuple(
            item.component.value for item in self.component_assessments
            if item.status == "MISSING"
        )
        blocked = tuple(
            item.component.value for item in self.component_assessments
            if item.status == "BLOCKED"
        )
        ready = tuple(
            item.component.value for item in self.component_assessments
            if item.status == "READY"
        )
        return {
            "schema": self.schema,
            "status": (
                "READY_FOR_EPOCH_BOUND_BUILD_PROPOSAL"
                if self.ready else "BLOCKED"),
            "draft_sha256": self.draft_sha256,
            "configuration_epoch_sha256": (
                self.draft_sha256 if self.ready else None),
            "evaluated_monotonic_ns": self.evaluated_monotonic_ns,
            "blockers": list(self.blockers),
            "component_assessments": [
                item.to_dict() for item in self.component_assessments],
            "missing_component_ids": list(missing),
            "blocked_component_ids": list(blocked),
            "ready_component_ids": list(ready),
            "epoch_bound_build_proposal_ready": self.ready,
            "human_review_required": False,
            "human_review_claimed": False,
            "external_independence_claimed": False,
            "owner_governance_override": True,
            "installation_authorized": False,
            "controller_start_authorized": False,
            "transport_authorized": False,
            "execution_authorized": False,
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def assessment_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.unsigned_dict(),
            "assessment_sha256": self.assessment_sha256,
        }


def build_owner_governed_configuration_epoch_draft_v1(
    *,
    epoch_id: str,
    owner_acceptance: R97OwnerAIReviewAcceptanceV1,
    components: tuple[OwnerGovernedConfigurationComponentV1, ...] = (),
    predecessor_configuration_epoch_sha256: str | None = None,
) -> OwnerGovernedConfigurationEpochDraftV1:
    """Build an offline draft bound to the exact ARM-067 acceptance."""

    if not isinstance(owner_acceptance, R97OwnerAIReviewAcceptanceV1):
        raise TypeError("owner_acceptance must be R97OwnerAIReviewAcceptanceV1")
    return OwnerGovernedConfigurationEpochDraftV1(
        epoch_id=epoch_id,
        predecessor_configuration_epoch_sha256=(
            predecessor_configuration_epoch_sha256),
        owner_acceptance_sha256=owner_acceptance.acceptance_sha256,
        r97_review_packet_sha256=R97_REVIEW_PACKET_SHA256,
        candidate_app_sha256=R97_APP_SHA256,
        protocol_source_sha256=R97_PROTOCOL_SOURCE_SHA256,
        joint_mapping_source_sha256=R97_JOINT_MAPPING_SOURCE_SHA256,
        components=components,
    )


def assess_owner_governed_configuration_epoch_v1(
    draft: OwnerGovernedConfigurationEpochDraftV1,
    *,
    evaluated_monotonic_ns: int,
    owner_acceptance: R97OwnerAIReviewAcceptanceV1 | None,
) -> OwnerGovernedConfigurationEpochAssessmentV1:
    """Assess completeness and freshness without performing hardware I/O."""

    if not isinstance(draft, OwnerGovernedConfigurationEpochDraftV1):
        raise TypeError(
            "draft must be OwnerGovernedConfigurationEpochDraftV1")
    now = _positive_ns(evaluated_monotonic_ns, "evaluated_monotonic_ns")
    blockers: list[str] = []
    if owner_acceptance is None:
        blockers.append("OWNER_ACCEPTANCE_MISSING")
    elif not isinstance(owner_acceptance, R97OwnerAIReviewAcceptanceV1):
        raise TypeError(
            "owner_acceptance must be R97OwnerAIReviewAcceptanceV1 or None")
    elif (
        owner_acceptance.acceptance_sha256 != draft.owner_acceptance_sha256
        or owner_acceptance.acceptance_sha256 != ARM067_ACCEPTANCE_SHA256
    ):
        blockers.append("OWNER_ACCEPTANCE_MISMATCH")
    release_checks = (
        (draft.r97_review_packet_sha256 != R97_REVIEW_PACKET_SHA256,
         "REVIEW_PACKET_MISMATCH"),
        (draft.candidate_app_sha256 != R97_APP_SHA256,
         "CANDIDATE_APP_MISMATCH"),
        (draft.protocol_source_sha256 != R97_PROTOCOL_SOURCE_SHA256,
         "PROTOCOL_SOURCE_MISMATCH"),
        (draft.joint_mapping_source_sha256
         != R97_JOINT_MAPPING_SOURCE_SHA256,
         "JOINT_MAPPING_SOURCE_MISMATCH"),
    )
    blockers.extend(code for failed, code in release_checks if failed)
    by_id = {item.component.value: item for item in draft.components}
    component_assessments: list[ComponentAssessmentV1] = []
    for component_id in EXPECTED_COMPONENT_IDS:
        component = by_id.get(component_id)
        component_blockers: list[str] = []
        if component is None:
            component_blockers.append("COMPONENT_MISSING")
            missing_bindings = REQUIRED_COMPONENT_BINDINGS[component_id]
        else:
            present = {item.binding_id for item in component.binding_evidence}
            missing_bindings = tuple(
                item for item in REQUIRED_COMPONENT_BINDINGS[component_id]
                if item not in present
            )
            if missing_bindings:
                component_blockers.append("REQUIRED_BINDING_MISSING")
            if now < component.measured_monotonic_ns:
                component_blockers.append("EVALUATION_PREDATES_MEASUREMENT")
            if now > component.valid_until_monotonic_ns:
                component_blockers.append("MEASUREMENT_STALE")
            if component.evidence_origin is not (
                EvidenceOrigin.PHYSICAL_RETAINED_ORIGINALS
            ):
                component_blockers.append("COMPONENT_NOT_PHYSICAL_ORIGINAL")
            if component.review_disposition is not (
                OwnerAIReviewDisposition.OWNER_AI_ACCEPTED
            ):
                component_blockers.append(
                    "COMPONENT_OWNER_AI_REVIEW_INCOMPLETE")
        blockers.extend(component_blockers)
        component_assessments.append(ComponentAssessmentV1(
            component=ConfigurationEpochComponent(component_id),
            blockers=tuple(component_blockers),
            missing_binding_ids=tuple(missing_bindings),
        ))
    return OwnerGovernedConfigurationEpochAssessmentV1(
        draft_sha256=draft.draft_sha256,
        evaluated_monotonic_ns=now,
        blockers=tuple(code for code in GLOBAL_BLOCKER_CODES if code in blockers),
        component_assessments=tuple(component_assessments),
    )


def parse_owner_governed_configuration_epoch_draft_v1(
    document: dict[str, Any],
) -> OwnerGovernedConfigurationEpochDraftV1:
    """Strictly parse a draft and verify its canonical digest."""

    required = set(build_owner_governed_configuration_epoch_draft_v1(
        epoch_id="x",
        owner_acceptance=R97OwnerAIReviewAcceptanceV1(
            acceptance_id="x", owner_id="x",
            accepted_utc="2000-01-01T00:00:00Z",
            source_ai_decision_sha256="0" * 64,
        ),
    ).to_dict())
    if type(document) is not dict or set(document) != required:
        raise OwnerGovernedConfigurationEpochError(
            "owner-governed epoch draft must contain exactly the closed fields")
    constants = {
        "epoch_scope": "OWNER_GOVERNED_RELEASE_PLUS_MEASURED_WORKCELL",
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
    if any(document.get(key) != value for key, value in constants.items()):
        raise OwnerGovernedConfigurationEpochError(
            "owner-governed epoch provenance or authority differs")
    raw_components = document["components"]
    if not isinstance(raw_components, list):
        raise OwnerGovernedConfigurationEpochError(
            "owner-governed epoch components must be an array")
    try:
        components = []
        for raw in raw_components:
            if type(raw) is not dict or set(raw) != {
                "component_id", "installation_state", "evidence_bundle_sha256",
                "binding_evidence", "owner_ai_review_sha256",
                "measured_monotonic_ns", "valid_until_monotonic_ns",
                "evidence_origin", "review_disposition",
            }:
                raise OwnerGovernedConfigurationEpochError(
                    "component contains unknown or missing fields")
            raw_bindings = raw["binding_evidence"]
            if not isinstance(raw_bindings, list) or any(
                type(item) is not dict or set(item) != {
                    "binding_id", "evidence_sha256"} for item in raw_bindings
            ):
                raise OwnerGovernedConfigurationEpochError(
                    "component binding evidence is invalid")
            components.append(OwnerGovernedConfigurationComponentV1(
                component=ConfigurationEpochComponent(raw["component_id"]),
                installation_state=ComponentInstallationState(
                    raw["installation_state"]),
                evidence_bundle_sha256=raw["evidence_bundle_sha256"],
                binding_evidence=tuple(ComponentBindingEvidenceV1(
                    binding_id=item["binding_id"],
                    evidence_sha256=item["evidence_sha256"],
                ) for item in raw_bindings),
                owner_ai_review_sha256=raw["owner_ai_review_sha256"],
                measured_monotonic_ns=raw["measured_monotonic_ns"],
                valid_until_monotonic_ns=raw["valid_until_monotonic_ns"],
                evidence_origin=EvidenceOrigin(raw["evidence_origin"]),
                review_disposition=OwnerAIReviewDisposition(
                    raw["review_disposition"]),
            ))
        parsed = OwnerGovernedConfigurationEpochDraftV1(
            epoch_id=document["epoch_id"],
            predecessor_configuration_epoch_sha256=(
                document["predecessor_configuration_epoch_sha256"]),
            owner_acceptance_sha256=document["owner_acceptance_sha256"],
            r97_review_packet_sha256=document["r97_review_packet_sha256"],
            candidate_app_sha256=document["candidate_app_sha256"],
            protocol_source_sha256=document["protocol_source_sha256"],
            joint_mapping_source_sha256=document["joint_mapping_source_sha256"],
            components=tuple(components),
            schema=document["schema"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, OwnerGovernedConfigurationEpochError):
            raise
        raise OwnerGovernedConfigurationEpochError(
            "owner-governed epoch draft contains invalid typed values") from exc
    _digest(document["draft_sha256"], "draft_sha256")
    if document["draft_sha256"] != parsed.draft_sha256:
        raise OwnerGovernedConfigurationEpochError(
            "owner-governed epoch draft hash differs")
    return parsed


__all__ = [
    "ARM067_ACCEPTANCE_SHA256", "COMPONENT_BLOCKER_CODES", "DRAFT_SCHEMA",
    "GLOBAL_BLOCKER_CODES", "REPORT_SCHEMA", "REQUIRED_COMPONENT_BINDINGS",
    "ComponentAssessmentV1", "ComponentBindingEvidenceV1",
    "ComponentInstallationState", "OwnerAIReviewDisposition",
    "OwnerGovernedConfigurationComponentV1",
    "OwnerGovernedConfigurationEpochAssessmentV1",
    "OwnerGovernedConfigurationEpochDraftV1",
    "OwnerGovernedConfigurationEpochError",
    "assess_owner_governed_configuration_epoch_v1",
    "build_owner_governed_configuration_epoch_draft_v1",
    "parse_owner_governed_configuration_epoch_draft_v1",
]
