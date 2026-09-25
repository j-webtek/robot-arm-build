"""Strict design catalog layered over the canonical fifteen onboarding stages.

This additive catalog binds only the canonical stage names and order from
``physical_onboarding.STAGE_ORDER``; it does not claim that the v1 human-facing
stage definitions describe the future v2 runtime.  It adds the implementation
metadata that coordinator needs: the ordered set of required effect classes,
power requirement, progressive intake ownership, deferred acceptance, output
artifacts, and hazard banners.  It is runtime-inactive and cannot create a
session, issue a permit, call a provider, or change the legacy v1 journal.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from rocell.application.physical_onboarding import (
    STAGE_ORDER,
    PhysicalOnboardingStage,
)
from rocell.safety.effects import EffectClass


PHYSICAL_ONBOARDING_STAGE_CATALOG_SCHEMA = "rocell.physical_onboarding_stage_catalog.v2"
DEFAULT_PHYSICAL_ONBOARDING_STAGE_CATALOG = Path(
    "software/config/physical_onboarding_stage_catalog.json"
)
MAX_PHYSICAL_ONBOARDING_STAGE_CATALOG_BYTES = 512 * 1024
CANONICAL_STAGE_ORDER_SHA256 = hashlib.sha256(
    json.dumps(
        [stage.value for stage in STAGE_ORDER],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
).hexdigest()

_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,95}\Z")
_HAZARD_ID = re.compile(r"HZ-[0-9]{3}\Z")
_INTAKE_ID = re.compile(r"INT-[0-9]{3}\Z")
_EXPECTED_STAGE_STATES = (
    "PENDING",
    "WAITING_OPERATOR",
    "REVIEW_PENDING",
    "PASS",
    "BLOCKED",
    "INVALIDATED",
    "COMPLETE_DIAGNOSTIC",
    "INCIDENT_HOLD",
    "SIDE_EFFECT_UNCERTAIN",
)
_EXPECTED_ATTEMPT_STATES = (
    "INTENT_DURABLE",
    "ABORTED_PRE_EFFECT",
    "EFFECT_ARMED",
    "EFFECT_OBSERVED",
    "CLEANUP_CONFIRMED",
    "SEALED_KNOWN",
    "SEALED_UNCERTAIN",
)
_EXPECTED_QUARANTINE_ACTIONS = (
    "READ_ONLY_VERIFY",
    "SAFING_NOTE",
    "INCIDENT_EVIDENCE",
    "EXPORT",
)
_EXPECTED_INTAKE_BY_STAGE: Mapping[PhysicalOnboardingStage, tuple[str, ...]] = {
    PhysicalOnboardingStage.WORKSPACE_SOURCES: (),
    PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT: (),
    PhysicalOnboardingStage.CAMERA_RECEIPT: (
        "INT-001",
        "INT-002",
        "INT-003",
        "INT-004",
        "INT-005",
        "INT-006",
        "INT-007",
        "INT-008",
        "INT-009",
        "INT-017",
        "INT-019",
        "INT-020",
        "INT-021",
        "INT-022",
        "INT-023",
        "INT-024",
    ),
    PhysicalOnboardingStage.CAMERA_IDENTITY: ("INT-018",),
    PhysicalOnboardingStage.CAMERA_MODE_CONTROLS: ("INT-028", "INT-029"),
    PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS: (),
    PhysicalOnboardingStage.OPTICS_INTRINSICS: ("INT-025", "INT-026", "INT-027"),
    PhysicalOnboardingStage.STATIC_REGISTRATION: tuple(
        [f"INT-{number:03d}" for number in range(30, 44)]
        + [f"INT-{number:03d}" for number in range(46, 49)]
        + [f"INT-{number:03d}" for number in range(50, 54)]
    ),
    PhysicalOnboardingStage.ARM_IDENTITY: ("INT-010",),
    PhysicalOnboardingStage.POWER_SAFETY: tuple(
        [f"INT-{number:03d}" for number in range(12, 17)] + ["INT-044", "INT-045"]
    ),
    PhysicalOnboardingStage.POWER_ON_OBSERVATION: (),
    PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION: ("INT-011",),
    PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION: ("INT-049",),
    PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE: ("INT-054",),
    PhysicalOnboardingStage.PHYSICAL_HANDOFF: (),
}
_EXPECTED_EFFECTS_BY_STAGE: Mapping[
    PhysicalOnboardingStage, tuple[EffectClass, ...]
] = {
    PhysicalOnboardingStage.WORKSPACE_SOURCES: (EffectClass.NO_DEVICE_IO,),
    PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT: (EffectClass.NO_DEVICE_IO,),
    PhysicalOnboardingStage.CAMERA_RECEIPT: (EffectClass.NO_DEVICE_IO,),
    PhysicalOnboardingStage.CAMERA_IDENTITY: (EffectClass.READ_ONLY_OS_INVENTORY,),
    PhysicalOnboardingStage.CAMERA_MODE_CONTROLS: (
        EffectClass.BOUNDED_CAMERA_CAMPAIGN,
    ),
    PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS: (
        EffectClass.BOUNDED_CAMERA_CAMPAIGN,
    ),
    PhysicalOnboardingStage.OPTICS_INTRINSICS: (EffectClass.BOUNDED_CAMERA_CAMPAIGN,),
    PhysicalOnboardingStage.STATIC_REGISTRATION: (EffectClass.BOUNDED_CAMERA_CAMPAIGN,),
    PhysicalOnboardingStage.ARM_IDENTITY: (EffectClass.READ_ONLY_OS_INVENTORY,),
    PhysicalOnboardingStage.POWER_SAFETY: (EffectClass.MANUAL_ENERGY_CHANGE,),
    PhysicalOnboardingStage.POWER_ON_OBSERVATION: (
        EffectClass.MANUAL_ENERGY_CHANGE,
        EffectClass.MANUAL_POSSIBLE_MOTION,
    ),
    PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION: (
        EffectClass.MANUAL_ENERGY_CHANGE,
        EffectClass.SERIAL_OPEN_OR_WRITE,
    ),
    PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION: (
        EffectClass.MANUAL_ENERGY_CHANGE,
        EffectClass.NONCONTACT_ARM_MOTION_EXTERNAL,
    ),
    PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE: (
        EffectClass.MANUAL_ENERGY_CHANGE,
        EffectClass.NONCONTACT_ARM_MOTION_EXTERNAL,
    ),
    PhysicalOnboardingStage.PHYSICAL_HANDOFF: (EffectClass.NO_DEVICE_IO,),
}
_EXPECTED_HAZARDS_BY_STAGE: Mapping[PhysicalOnboardingStage, tuple[str, ...]] = {
    PhysicalOnboardingStage.WORKSPACE_SOURCES: ("HZ-012",),
    PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT: ("HZ-007", "HZ-010"),
    PhysicalOnboardingStage.CAMERA_RECEIPT: ("HZ-007", "HZ-008", "HZ-009"),
    PhysicalOnboardingStage.CAMERA_IDENTITY: ("HZ-009",),
    PhysicalOnboardingStage.CAMERA_MODE_CONTROLS: (
        "HZ-009",
        "HZ-011",
        "HZ-015",
    ),
    PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS: (
        "HZ-009",
        "HZ-011",
        "HZ-015",
    ),
    PhysicalOnboardingStage.OPTICS_INTRINSICS: (
        "HZ-007",
        "HZ-010",
        "HZ-011",
        "HZ-015",
    ),
    PhysicalOnboardingStage.STATIC_REGISTRATION: (
        "HZ-007",
        "HZ-008",
        "HZ-010",
        "HZ-011",
        "HZ-015",
    ),
    PhysicalOnboardingStage.ARM_IDENTITY: ("HZ-006", "HZ-009"),
    PhysicalOnboardingStage.POWER_SAFETY: (
        "HZ-001",
        "HZ-002",
        "HZ-003",
        "HZ-004",
        "HZ-005",
        "HZ-007",
        "HZ-008",
        "HZ-012",
        "HZ-013",
        "HZ-016",
    ),
    PhysicalOnboardingStage.POWER_ON_OBSERVATION: (
        "HZ-001",
        "HZ-002",
        "HZ-003",
        "HZ-004",
        "HZ-005",
        "HZ-012",
        "HZ-016",
    ),
    PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION: (
        "HZ-001",
        "HZ-002",
        "HZ-003",
        "HZ-004",
        "HZ-006",
        "HZ-009",
        "HZ-011",
        "HZ-012",
        "HZ-016",
    ),
    PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION: (
        "HZ-001",
        "HZ-002",
        "HZ-003",
        "HZ-004",
        "HZ-008",
        "HZ-010",
        "HZ-011",
        "HZ-013",
        "HZ-014",
        "HZ-016",
    ),
    PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE: (
        "HZ-001",
        "HZ-002",
        "HZ-003",
        "HZ-004",
        "HZ-007",
        "HZ-008",
        "HZ-010",
        "HZ-011",
        "HZ-014",
        "HZ-016",
    ),
    PhysicalOnboardingStage.PHYSICAL_HANDOFF: ("HZ-010", "HZ-014", "HZ-016"),
}
_EXPECTED_BUNDLE_COMPONENTS_BY_STAGE: Mapping[
    PhysicalOnboardingStage, tuple[str, ...]
] = {
    PhysicalOnboardingStage.WORKSPACE_SOURCES: (
        "controlled_source_binding",
        "provider_implementation_hashes",
        "runner_implementation_hashes",
    ),
    PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT: (),
    PhysicalOnboardingStage.CAMERA_RECEIPT: (
        "camera_receipt",
        "passive_workcell_receipt",
    ),
    PhysicalOnboardingStage.CAMERA_IDENTITY: ("camera_identity",),
    PhysicalOnboardingStage.CAMERA_MODE_CONTROLS: ("camera_mode_controls",),
    PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS: ("camera_frame_freshness",),
    PhysicalOnboardingStage.OPTICS_INTRINSICS: (),
    PhysicalOnboardingStage.STATIC_REGISTRATION: (
        "installed_camera_intrinsics",
        "measured_tag_map",
        "static_camera_to_board_transform",
        "installed_optical_stability",
        "passive_visibility_atlas",
        "dataset_partition_manifests",
    ),
    PhysicalOnboardingStage.ARM_IDENTITY: ("exact_arm_physical_identity",),
    PhysicalOnboardingStage.POWER_SAFETY: ("power_safety_review",),
    PhysicalOnboardingStage.POWER_ON_OBSERVATION: (
        "first_power_observation",
        "startup_sweep_evidence",
    ),
    PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION: (
        "feedback_only_exchange",
        "qualified_controller_identity",
    ),
    PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION: (
        "bootstrap_phase_receipt",
        "reference_characterization_phase_receipt",
        "arm_to_board_transform",
        "controller_model_correlation",
        "free_state_tool_tcp",
        "keyboard_target_map",
        "phone_target_map",
        "outcome_observer_candidates",
    ),
    PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE: (
        "noncontact_qualification_phase_receipt",
        "untouched_final_acceptance_phase_receipt",
        "noncontact_acceptance_report",
        "arm_induced_visibility_atlas",
        "collision_configuration",
        "accuracy_budget_assessment",
    ),
    PhysicalOnboardingStage.PHYSICAL_HANDOFF: (
        "configuration_epoch_vector",
        "global_attempt_ledger_head",
        "global_quarantine_ledger_head",
        "reviewer_decisions",
        "open_blockers",
    ),
}
EXPECTED_BUNDLE_COMPONENT_ORDER = tuple(
    component
    for stage in STAGE_ORDER
    for component in _EXPECTED_BUNDLE_COMPONENTS_BY_STAGE[stage]
)
if len(EXPECTED_BUNDLE_COMPONENT_ORDER) != 39 or len(
    set(EXPECTED_BUNDLE_COMPONENT_ORDER)
) != len(EXPECTED_BUNDLE_COMPONENT_ORDER):
    raise RuntimeError("bundle-component producer contract must cover 39 unique items")

_INT_005_OBSERVATION_REQUIREMENT = "MEASUREMENT_AND_EVIDENCE_REQUIRED"
_INT_005_ACCEPTANCE_PREREQUISITES = ("TARGET_ACCURACY_BUDGET_CLOSED",)


class PhysicalOnboardingStageCatalogError(ValueError):
    """The additive catalog is malformed, stale, or unsafe."""


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PhysicalOnboardingStageCatalogError(
                f"duplicate stage-catalog field {key!r}"
            )
        result[key] = value
    return result


def _reject_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise PhysicalOnboardingStageCatalogError(f"nonfinite value {value!r}")
    raise PhysicalOnboardingStageCatalogError("stage catalog must not contain floats")


def _reject_constant(value: str) -> None:
    raise PhysicalOnboardingStageCatalogError(f"nonfinite constant {value!r}")


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PhysicalOnboardingStageCatalogError(f"{label} must be an object")
    return value


def _exact_fields(
    value: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise PhysicalOnboardingStageCatalogError(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise PhysicalOnboardingStageCatalogError(f"{label} is not a valid identifier")
    return value


def _unique_identifiers(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise PhysicalOnboardingStageCatalogError(f"{label} must be a non-empty list")
    result = tuple(_identifier(item, f"{label} item") for item in value)
    if len(result) != len(set(result)):
        raise PhysicalOnboardingStageCatalogError(f"{label} contains duplicates")
    return result


def _resolve_catalog(workspace: Path, selected: Path) -> Path:
    root = Path(os.path.abspath(workspace))
    candidate = selected if selected.is_absolute() else root / selected
    for label, path in (("workspace", root), ("stage catalog", candidate)):
        cursor = path
        while True:
            if os.path.lexists(cursor) and cursor.is_symlink():
                raise PhysicalOnboardingStageCatalogError(f"{label} contains a symlink")
            if cursor.parent == cursor:
                break
            cursor = cursor.parent
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise PhysicalOnboardingStageCatalogError(
            "stage catalog must be a file beneath the workspace"
        ) from exc
    if not resolved.is_file():
        raise PhysicalOnboardingStageCatalogError(
            "stage catalog must be a regular file"
        )
    return resolved


@dataclass(frozen=True, slots=True)
class StageImplementationContract:
    stage: PhysicalOnboardingStage
    required_effect_classes: tuple[EffectClass, ...]
    actuator_power_requirement: str
    intake_record_ids: tuple[str, ...]
    owned_artifacts: tuple[str, ...]
    produced_bundle_components: tuple[str, ...]
    hazard_banner_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeferredIntakeAcceptance:
    """A receipt observation whose limit closes only at a later stage."""

    record_id: str
    observation_owner_stage: PhysicalOnboardingStage
    observation_requirement: str
    observation_acceptance_allowed: bool
    acceptance_owner_stage: PhysicalOnboardingStage
    acceptance_prerequisites: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PhysicalOnboardingStageCatalog:
    source_path: Path
    source_sha256: str
    catalog_id: str
    canonical_stage_order_sha256: str
    stages: tuple[StageImplementationContract, ...]
    post_diagnostic_intake_record_ids: tuple[str, ...]
    deferred_acceptance: tuple[DeferredIntakeAcceptance, ...]

    @property
    def by_stage(self) -> Mapping[PhysicalOnboardingStage, StageImplementationContract]:
        return MappingProxyType({item.stage: item for item in self.stages})

    @property
    def deferred_acceptance_by_record_id(
        self,
    ) -> Mapping[str, DeferredIntakeAcceptance]:
        return MappingProxyType(
            {item.record_id: item for item in self.deferred_acceptance}
        )

    @property
    def produced_bundle_components(self) -> tuple[str, ...]:
        return tuple(
            component
            for stage in self.stages
            for component in stage.produced_bundle_components
        )

    @property
    def bundle_component_producers(
        self,
    ) -> Mapping[str, PhysicalOnboardingStage]:
        return MappingProxyType(
            {
                component: stage.stage
                for stage in self.stages
                for component in stage.produced_bundle_components
            }
        )

    @property
    def zero_physical_authority(self) -> bool:
        return True


def load_physical_onboarding_stage_catalog(
    workspace: Path,
    catalog_path: Path | None = None,
) -> PhysicalOnboardingStageCatalog:
    """Validate metadata against the canonical stage names and order."""

    selected = (
        DEFAULT_PHYSICAL_ONBOARDING_STAGE_CATALOG
        if catalog_path is None
        else catalog_path
    )
    resolved = _resolve_catalog(Path(workspace), Path(selected))
    try:
        payload = resolved.read_bytes()
    except OSError as exc:
        raise PhysicalOnboardingStageCatalogError(
            "could not read stage catalog"
        ) from exc
    if not payload or len(payload) > MAX_PHYSICAL_ONBOARDING_STAGE_CATALOG_BYTES:
        raise PhysicalOnboardingStageCatalogError("stage catalog size is invalid")
    try:
        parsed = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PhysicalOnboardingStageCatalogError(
            "stage catalog must be strict UTF-8 JSON"
        ) from exc
    root = _mapping(parsed, "stage catalog")
    _exact_fields(
        root,
        frozenset(
            {
                "schema",
                "catalog_id",
                "revision",
                "status",
                "runtime_activation",
                "canonical_stage_order_source",
                "canonical_stage_order_sha256",
                "duplicate_stage_catalog_allowed",
                "v1_session_policy_after_v2_activation",
                "new_effectful_session_schema",
                "post_diagnostic_intake_record_ids",
                "deferred_acceptance",
                "effect_composition_policy",
                "state_model",
                "stages",
            }
        ),
        "stage catalog",
    )
    expected_scalars = {
        "schema": PHYSICAL_ONBOARDING_STAGE_CATALOG_SCHEMA,
        "catalog_id": "ROCELL-PHYSICAL-ONBOARDING-STAGES-001",
        "revision": 3,
        "status": "DESIGN_REVIEWED_RUNTIME_MIGRATION_PENDING",
        "runtime_activation": False,
        "canonical_stage_order_source": (
            "rocell.application.physical_onboarding.STAGE_ORDER"
        ),
        "canonical_stage_order_sha256": CANONICAL_STAGE_ORDER_SHA256,
        "duplicate_stage_catalog_allowed": False,
        "v1_session_policy_after_v2_activation": "READ_ONLY_VERIFY_EXPORT_ONLY",
        "new_effectful_session_schema": "rocell.physical_onboarding_header.v2",
    }
    for field, expected in expected_scalars.items():
        if type(root[field]) is not type(expected) or root[field] != expected:
            raise PhysicalOnboardingStageCatalogError(
                f"stage catalog {field} differs from the reviewed contract"
            )
    post_diagnostic = root["post_diagnostic_intake_record_ids"]
    if post_diagnostic != ["INT-055"]:
        raise PhysicalOnboardingStageCatalogError(
            "INT-055 must remain post-diagnostic promotion evidence"
        )

    raw_deferred = root["deferred_acceptance"]
    if type(raw_deferred) is not list or len(raw_deferred) != 1:
        raise PhysicalOnboardingStageCatalogError(
            "deferred_acceptance must contain exactly the INT-005 split"
        )
    deferred_document = _mapping(raw_deferred[0], "deferred_acceptance[0]")
    _exact_fields(
        deferred_document,
        frozenset(
            {
                "record_id",
                "observation_owner_stage",
                "observation_requirement",
                "observation_acceptance_allowed",
                "acceptance_owner_stage",
                "acceptance_prerequisites",
            }
        ),
        "deferred_acceptance[0]",
    )
    try:
        observation_owner_stage = PhysicalOnboardingStage(
            deferred_document["observation_owner_stage"]
        )
        acceptance_owner_stage = PhysicalOnboardingStage(
            deferred_document["acceptance_owner_stage"]
        )
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingStageCatalogError(
            "deferred acceptance references an unknown stage"
        ) from exc
    acceptance_prerequisites = deferred_document["acceptance_prerequisites"]
    if (
        deferred_document["record_id"] != "INT-005"
        or observation_owner_stage is not PhysicalOnboardingStage.CAMERA_RECEIPT
        or deferred_document["observation_requirement"]
        != _INT_005_OBSERVATION_REQUIREMENT
        or deferred_document["observation_acceptance_allowed"] is not False
        or acceptance_owner_stage is not PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE
        or type(acceptance_prerequisites) is not list
        or tuple(acceptance_prerequisites) != _INT_005_ACCEPTANCE_PREREQUISITES
    ):
        raise PhysicalOnboardingStageCatalogError(
            "INT-005 observation/acceptance ownership differs from the reviewed split"
        )
    deferred_acceptance = (
        DeferredIntakeAcceptance(
            record_id="INT-005",
            observation_owner_stage=observation_owner_stage,
            observation_requirement=_INT_005_OBSERVATION_REQUIREMENT,
            observation_acceptance_allowed=False,
            acceptance_owner_stage=acceptance_owner_stage,
            acceptance_prerequisites=_INT_005_ACCEPTANCE_PREREQUISITES,
        ),
    )

    effect_composition = _mapping(
        root["effect_composition_policy"], "effect_composition_policy"
    )
    expected_effect_composition = {
        "required_effect_classes_are_complete_ordered_domains": True,
        "one_permit_has_exactly_one_primary_effect_class": True,
        "separable_external_effects_require_predecessor_linked_attempts": True,
        "causally_inseparable_effects_are_facets_of_one_attempt": True,
        "effect_facets_do_not_authorize_a_second_dispatch_or_retry": True,
        "effect_class_count_does_not_imply_operation_count": True,
    }
    if dict(effect_composition) != expected_effect_composition:
        raise PhysicalOnboardingStageCatalogError(
            "effect composition policy differs from the reviewed contract"
        )

    state_model = _mapping(root["state_model"], "state_model")
    _exact_fields(
        state_model,
        frozenset(
            {
                "stage_review_states",
                "attempt_states",
                "attempt_records_are_append_only",
                "automatic_attempt_replay_allowed",
                "global_quarantine_latches",
                "quarantine_allows_only",
            }
        ),
        "state_model",
    )
    if tuple(state_model["stage_review_states"]) != _EXPECTED_STAGE_STATES:
        raise PhysicalOnboardingStageCatalogError("stage review state model changed")
    if tuple(state_model["attempt_states"]) != _EXPECTED_ATTEMPT_STATES:
        raise PhysicalOnboardingStageCatalogError("attempt state model changed")
    if (
        state_model["attempt_records_are_append_only"] is not True
        or state_model["automatic_attempt_replay_allowed"] is not False
        or state_model["global_quarantine_latches"]
        != ["INCIDENT_HOLD", "SIDE_EFFECT_UNCERTAIN"]
        or tuple(state_model["quarantine_allows_only"]) != _EXPECTED_QUARANTINE_ACTIONS
    ):
        raise PhysicalOnboardingStageCatalogError("quarantine or replay policy changed")

    raw_stages = root["stages"]
    if not isinstance(raw_stages, list):
        raise PhysicalOnboardingStageCatalogError("stages must be a list")
    stages: list[StageImplementationContract] = []
    all_intake: list[str] = []
    for index, raw_stage in enumerate(raw_stages):
        entry = _mapping(raw_stage, f"stages[{index}]")
        _exact_fields(
            entry,
            frozenset(
                {
                    "stage",
                    "required_effect_classes",
                    "actuator_power_requirement",
                    "intake_record_ids",
                    "owned_artifacts",
                    "produced_bundle_components",
                    "hazard_banner_ids",
                }
            ),
            f"stages[{index}]",
        )
        try:
            stage = PhysicalOnboardingStage(entry["stage"])
        except (TypeError, ValueError) as exc:
            raise PhysicalOnboardingStageCatalogError(
                "stage catalog contains an unknown stage"
            ) from exc
        raw_effect_classes = entry["required_effect_classes"]
        if type(raw_effect_classes) is not list or not raw_effect_classes:
            raise PhysicalOnboardingStageCatalogError(
                "required_effect_classes must be a non-empty array"
            )
        try:
            effect_classes = tuple(
                EffectClass(effect_class) for effect_class in raw_effect_classes
            )
        except (TypeError, ValueError) as exc:
            raise PhysicalOnboardingStageCatalogError(
                "stage catalog contains an unknown effect class"
            ) from exc
        if len(effect_classes) != len(set(effect_classes)):
            raise PhysicalOnboardingStageCatalogError(
                "required effect classes must not repeat"
            )
        if effect_classes != _EXPECTED_EFFECTS_BY_STAGE[stage]:
            raise PhysicalOnboardingStageCatalogError(
                f"required effect classes changed for stage {stage.value}"
            )
        power = entry["actuator_power_requirement"]
        if not isinstance(power, str) or not power or power != power.strip():
            raise PhysicalOnboardingStageCatalogError(
                "actuator power requirement is invalid"
            )
        raw_intake = entry["intake_record_ids"]
        if not isinstance(raw_intake, list):
            raise PhysicalOnboardingStageCatalogError(
                "intake_record_ids must be a list"
            )
        intake = tuple(raw_intake)
        if intake != _EXPECTED_INTAKE_BY_STAGE[stage]:
            raise PhysicalOnboardingStageCatalogError(
                f"progressive intake ownership changed for stage {stage.value}"
            )
        if any(
            not isinstance(item, str) or _INTAKE_ID.fullmatch(item) is None
            for item in intake
        ):
            raise PhysicalOnboardingStageCatalogError("invalid intake record ID")
        artifacts = _unique_identifiers(
            entry["owned_artifacts"], f"stages[{index}].owned_artifacts"
        )
        raw_bundle_components = entry["produced_bundle_components"]
        if type(raw_bundle_components) is not list:
            raise PhysicalOnboardingStageCatalogError(
                "produced_bundle_components must be an array"
            )
        bundle_components = tuple(
            _identifier(
                component,
                f"stages[{index}].produced_bundle_components item",
            )
            for component in raw_bundle_components
        )
        if len(bundle_components) != len(set(bundle_components)):
            raise PhysicalOnboardingStageCatalogError(
                "produced bundle components must not repeat within a stage"
            )
        if bundle_components != _EXPECTED_BUNDLE_COMPONENTS_BY_STAGE[stage]:
            raise PhysicalOnboardingStageCatalogError(
                f"bundle-component production changed for stage {stage.value}"
            )
        raw_hazards = entry["hazard_banner_ids"]
        if not isinstance(raw_hazards, list) or not raw_hazards:
            raise PhysicalOnboardingStageCatalogError(
                "each stage needs a hazard banner"
            )
        hazards = tuple(raw_hazards)
        if len(hazards) != len(set(hazards)) or any(
            not isinstance(item, str) or _HAZARD_ID.fullmatch(item) is None
            for item in hazards
        ):
            raise PhysicalOnboardingStageCatalogError("hazard banner IDs are invalid")
        if hazards != _EXPECTED_HAZARDS_BY_STAGE[stage]:
            raise PhysicalOnboardingStageCatalogError(
                f"hazard banner coverage changed for stage {stage.value}"
            )
        all_intake.extend(intake)
        stages.append(
            StageImplementationContract(
                stage=stage,
                required_effect_classes=effect_classes,
                actuator_power_requirement=power,
                intake_record_ids=intake,
                owned_artifacts=artifacts,
                produced_bundle_components=bundle_components,
                hazard_banner_ids=hazards,
            )
        )
    if tuple(item.stage for item in stages) != STAGE_ORDER:
        raise PhysicalOnboardingStageCatalogError(
            "stage order differs from canonical order"
        )
    complete_intake = tuple(all_intake) + tuple(post_diagnostic)
    if len(complete_intake) != 55 or set(complete_intake) != {
        f"INT-{number:03d}" for number in range(1, 56)
    }:
        raise PhysicalOnboardingStageCatalogError(
            "progressive intake ownership must cover INT-001 through INT-055 exactly once"
        )
    if len(complete_intake) != len(set(complete_intake)):
        raise PhysicalOnboardingStageCatalogError(
            "progressive intake ownership overlaps"
        )

    by_stage = {item.stage: item for item in stages}
    produced_bundle_components = tuple(
        component for item in stages for component in item.produced_bundle_components
    )
    if produced_bundle_components != EXPECTED_BUNDLE_COMPONENT_ORDER or len(
        set(produced_bundle_components)
    ) != len(produced_bundle_components):
        raise PhysicalOnboardingStageCatalogError(
            "bundle components must have one exact producer across all stages"
        )
    for item in deferred_acceptance:
        if (
            item.record_id
            not in by_stage[item.observation_owner_stage].intake_record_ids
        ):
            raise PhysicalOnboardingStageCatalogError(
                "deferred acceptance record is not owned by its observation stage"
            )
        if STAGE_ORDER.index(item.acceptance_owner_stage) <= STAGE_ORDER.index(
            item.observation_owner_stage
        ):
            raise PhysicalOnboardingStageCatalogError(
                "deferred acceptance must close after its observation stage"
            )
    if (
        "installed_camera_intrinsics"
        in by_stage[PhysicalOnboardingStage.OPTICS_INTRINSICS].owned_artifacts
        or "installed_camera_intrinsics"
        not in by_stage[PhysicalOnboardingStage.STATIC_REGISTRATION].owned_artifacts
        or "arm_to_board_transform"
        in by_stage[PhysicalOnboardingStage.STATIC_REGISTRATION].owned_artifacts
        or "arm_to_board_transform"
        not in by_stage[
            PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION
        ].owned_artifacts
    ):
        raise PhysicalOnboardingStageCatalogError(
            "camera, board, arm, and TCP calibration ownership is inconsistent"
        )
    arm_identity_stage = by_stage[PhysicalOnboardingStage.ARM_IDENTITY]
    feedback_stage = by_stage[PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION]
    if (
        "controller_inventory_candidate" not in arm_identity_stage.owned_artifacts
        or "qualified_controller_identity" in arm_identity_stage.owned_artifacts
        or "qualified_controller_identity"
        in arm_identity_stage.produced_bundle_components
        or "qualified_controller_identity" not in feedback_stage.owned_artifacts
        or feedback_stage.produced_bundle_components[-1]
        != "qualified_controller_identity"
    ):
        raise PhysicalOnboardingStageCatalogError(
            "controller identity candidate/promotion ownership is inconsistent"
        )
    if (
        by_stage[PhysicalOnboardingStage.STATIC_REGISTRATION].actuator_power_requirement
        != "DISCONNECTED_REQUIRED"
        or by_stage[
            PhysicalOnboardingStage.POWER_ON_OBSERVATION
        ].actuator_power_requirement
        != "FRESH_MANUAL_PERMIT_END_DISCONNECTED"
        or by_stage[
            PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION
        ].actuator_power_requirement
        != "FRESH_MANUAL_PERMIT_END_DISCONNECTED"
        or by_stage[
            PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION
        ].actuator_power_requirement
        != "EXTERNAL_NONCONTACT_PERMIT_END_DISCONNECTED"
        or by_stage[
            PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE
        ].actuator_power_requirement
        != "EXTERNAL_NONCONTACT_PERMIT_END_DISCONNECTED"
    ):
        raise PhysicalOnboardingStageCatalogError(
            "critical actuator-power sequence changed"
        )

    return PhysicalOnboardingStageCatalog(
        source_path=resolved,
        source_sha256=hashlib.sha256(payload).hexdigest(),
        catalog_id=root["catalog_id"],
        canonical_stage_order_sha256=root["canonical_stage_order_sha256"],
        stages=tuple(stages),
        post_diagnostic_intake_record_ids=tuple(post_diagnostic),
        deferred_acceptance=deferred_acceptance,
    )


__all__ = [
    "CANONICAL_STAGE_ORDER_SHA256",
    "EXPECTED_BUNDLE_COMPONENT_ORDER",
    "PHYSICAL_ONBOARDING_STAGE_CATALOG_SCHEMA",
    "DEFAULT_PHYSICAL_ONBOARDING_STAGE_CATALOG",
    "MAX_PHYSICAL_ONBOARDING_STAGE_CATALOG_BYTES",
    "DeferredIntakeAcceptance",
    "PhysicalOnboardingStageCatalog",
    "PhysicalOnboardingStageCatalogError",
    "StageImplementationContract",
    "load_physical_onboarding_stage_catalog",
]
