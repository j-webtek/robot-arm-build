from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable

import pytest

from rocell.application.physical_onboarding import (
    STAGE_ORDER,
    PhysicalOnboardingStage,
)
from rocell.application.physical_onboarding_stage_catalog import (
    CANONICAL_STAGE_ORDER_SHA256,
    EXPECTED_BUNDLE_COMPONENT_ORDER,
    PhysicalOnboardingStageCatalogError,
    load_physical_onboarding_stage_catalog,
)
from rocell.safety.effects import EffectClass


WORKSPACE = Path(__file__).resolve().parents[3]
CATALOG_PATH = WORKSPACE / "software/config/physical_onboarding_stage_catalog.json"


def _document() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _temporary_catalog(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> Path:
    document = copy.deepcopy(_document())
    mutate(document)
    path = tmp_path / "physical_onboarding_stage_catalog.json"
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path


def _stage(document: dict[str, Any], stage: str) -> dict[str, Any]:
    return next(item for item in document["stages"] if item["stage"] == stage)


def test_loads_additive_catalog_against_canonical_stage_plan() -> None:
    before = CATALOG_PATH.read_bytes()

    catalog = load_physical_onboarding_stage_catalog(WORKSPACE)

    assert CATALOG_PATH.read_bytes() == before
    assert catalog.zero_physical_authority
    assert catalog.canonical_stage_order_sha256 == CANONICAL_STAGE_ORDER_SHA256
    assert tuple(item.stage for item in catalog.stages) == STAGE_ORDER
    assert catalog.post_diagnostic_intake_record_ids == ("INT-055",)
    assert catalog.by_stage[
        PhysicalOnboardingStage.CAMERA_MODE_CONTROLS
    ].required_effect_classes == (EffectClass.BOUNDED_CAMERA_CAMPAIGN,)


def test_repeated_energization_stages_declare_ordered_compound_effects() -> None:
    catalog = load_physical_onboarding_stage_catalog(WORKSPACE)

    assert catalog.by_stage[
        PhysicalOnboardingStage.POWER_ON_OBSERVATION
    ].required_effect_classes == (
        EffectClass.MANUAL_ENERGY_CHANGE,
        EffectClass.MANUAL_POSSIBLE_MOTION,
    )
    assert catalog.by_stage[
        PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION
    ].required_effect_classes == (
        EffectClass.MANUAL_ENERGY_CHANGE,
        EffectClass.SERIAL_OPEN_OR_WRITE,
    )
    for stage in (
        PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION,
        PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE,
    ):
        assert catalog.by_stage[stage].required_effect_classes == (
            EffectClass.MANUAL_ENERGY_CHANGE,
            EffectClass.NONCONTACT_ARM_MOTION_EXTERNAL,
        )


def test_compound_effects_are_domains_not_duplicate_dispatches() -> None:
    document = _document()

    assert document["effect_composition_policy"] == {
        "required_effect_classes_are_complete_ordered_domains": True,
        "one_permit_has_exactly_one_primary_effect_class": True,
        "separable_external_effects_require_predecessor_linked_attempts": True,
        "causally_inseparable_effects_are_facets_of_one_attempt": True,
        "effect_facets_do_not_authorize_a_second_dispatch_or_retry": True,
        "effect_class_count_does_not_imply_operation_count": True,
    }


def test_repeated_energization_stages_have_required_hazard_banners() -> None:
    catalog = load_physical_onboarding_stage_catalog(WORKSPACE)

    stage_12_hazards = set(
        catalog.by_stage[
            PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION
        ].hazard_banner_ids
    )
    assert {"HZ-002", "HZ-003", "HZ-004"} <= stage_12_hazards
    for stage in (
        PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION,
        PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE,
    ):
        assert "HZ-001" in catalog.by_stage[stage].hazard_banner_ids
        assert "HZ-004" in catalog.by_stage[stage].hazard_banner_ids


def test_int_005_observation_and_acceptance_are_separate() -> None:
    catalog = load_physical_onboarding_stage_catalog(WORKSPACE)
    split = catalog.deferred_acceptance_by_record_id["INT-005"]

    assert split.observation_owner_stage is PhysicalOnboardingStage.CAMERA_RECEIPT
    assert split.observation_requirement == "MEASUREMENT_AND_EVIDENCE_REQUIRED"
    assert split.observation_acceptance_allowed is False
    assert split.acceptance_owner_stage is PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE
    assert split.acceptance_prerequisites == ("TARGET_ACCURACY_BUDGET_CLOSED",)
    assert (
        "INT-005"
        in catalog.by_stage[PhysicalOnboardingStage.CAMERA_RECEIPT].intake_record_ids
    )


def test_every_commissioning_bundle_component_has_one_exact_producer() -> None:
    catalog = load_physical_onboarding_stage_catalog(WORKSPACE)

    assert catalog.produced_bundle_components == EXPECTED_BUNDLE_COMPONENT_ORDER
    assert len(catalog.produced_bundle_components) == 39
    assert len(set(catalog.produced_bundle_components)) == 39
    assert catalog.bundle_component_producers["accuracy_budget_assessment"] is (
        PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE
    )
    assert catalog.bundle_component_producers["qualified_controller_identity"] is (
        PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION
    )
    assert catalog.bundle_component_producers["configuration_epoch_vector"] is (
        PhysicalOnboardingStage.PHYSICAL_HANDOFF
    )


def test_progressive_intake_covers_all_rows_exactly_once() -> None:
    catalog = load_physical_onboarding_stage_catalog(WORKSPACE)

    owned = [
        record_id for stage in catalog.stages for record_id in stage.intake_record_ids
    ] + list(catalog.post_diagnostic_intake_record_ids)

    assert len(owned) == 55
    assert len(set(owned)) == 55
    assert set(owned) == {f"INT-{number:03d}" for number in range(1, 56)}
    assert "INT-055" not in {
        record_id for stage in catalog.stages for record_id in stage.intake_record_ids
    }


def test_calibration_ownership_is_not_conflated() -> None:
    catalog = load_physical_onboarding_stage_catalog(WORKSPACE)

    stage_7 = catalog.by_stage[PhysicalOnboardingStage.OPTICS_INTRINSICS]
    stage_8 = catalog.by_stage[PhysicalOnboardingStage.STATIC_REGISTRATION]
    stage_13 = catalog.by_stage[PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION]

    assert "physical_capture_plan" in stage_7.owned_artifacts
    assert "installed_camera_intrinsics" not in stage_7.owned_artifacts
    assert "installed_camera_intrinsics" in stage_8.owned_artifacts
    assert "static_camera_to_board_transform" in stage_8.owned_artifacts
    assert "arm_to_board_transform" not in stage_8.owned_artifacts
    assert "arm_to_board_transform" in stage_13.owned_artifacts


def test_every_energization_stage_requires_a_final_disconnected_state() -> None:
    catalog = load_physical_onboarding_stage_catalog(WORKSPACE)

    assert (
        catalog.by_stage[
            PhysicalOnboardingStage.POWER_ON_OBSERVATION
        ].actuator_power_requirement
        == "FRESH_MANUAL_PERMIT_END_DISCONNECTED"
    )
    assert (
        catalog.by_stage[
            PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION
        ].actuator_power_requirement
        == "FRESH_MANUAL_PERMIT_END_DISCONNECTED"
    )
    for stage in (
        PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION,
        PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE,
    ):
        assert (
            catalog.by_stage[stage].actuator_power_requirement
            == "EXTERNAL_NONCONTACT_PERMIT_END_DISCONNECTED"
        )


def test_controller_identity_is_candidate_at_stage_9_and_promoted_at_stage_12() -> None:
    catalog = load_physical_onboarding_stage_catalog(WORKSPACE)
    stage_9 = catalog.by_stage[PhysicalOnboardingStage.ARM_IDENTITY]
    stage_12 = catalog.by_stage[PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION]

    assert "controller_inventory_candidate" in stage_9.owned_artifacts
    assert "qualified_controller_identity" not in stage_9.owned_artifacts
    assert "qualified_controller_identity" not in stage_9.produced_bundle_components
    assert "qualified_controller_identity" in stage_12.owned_artifacts
    assert stage_12.produced_bundle_components[-1] == "qualified_controller_identity"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("runtime_activation", True),
        ("duplicate_stage_catalog_allowed", True),
        ("canonical_stage_order_sha256", "0" * 64),
        ("new_effectful_session_schema", "rocell.physical_onboarding_header.v1"),
    ],
)
def test_rejects_activation_or_catalog_drift(
    tmp_path: Path, field: str, value: object
) -> None:
    path = _temporary_catalog(
        tmp_path, lambda document: document.update({field: value})
    )
    with pytest.raises(PhysicalOnboardingStageCatalogError, match=field):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_effect_class_omission(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        _stage(document, "feedback_only_connection")["required_effect_classes"] = [
            "SERIAL_OPEN_OR_WRITE"
        ]

    path = _temporary_catalog(tmp_path, mutate)
    with pytest.raises(
        PhysicalOnboardingStageCatalogError,
        match="required effect classes changed",
    ):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_effect_class_reordering(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        _stage(document, "feedback_only_connection")[
            "required_effect_classes"
        ].reverse()

    path = _temporary_catalog(tmp_path, mutate)
    with pytest.raises(
        PhysicalOnboardingStageCatalogError,
        match="required effect classes changed",
    ):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_effect_composition_that_can_duplicate_dispatch(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["effect_composition_policy"][
            "effect_facets_do_not_authorize_a_second_dispatch_or_retry"
        ] = False

    path = _temporary_catalog(tmp_path, mutate)
    with pytest.raises(
        PhysicalOnboardingStageCatalogError,
        match="effect composition policy",
    ):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_missing_repeated_energization_hazard(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        _stage(document, "feedback_only_connection")["hazard_banner_ids"].remove(
            "HZ-004"
        )

    path = _temporary_catalog(tmp_path, mutate)
    with pytest.raises(
        PhysicalOnboardingStageCatalogError,
        match="hazard banner coverage changed",
    ):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_early_int_005_acceptance(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["deferred_acceptance"][0]["observation_acceptance_allowed"] = True

    path = _temporary_catalog(tmp_path, mutate)
    with pytest.raises(
        PhysicalOnboardingStageCatalogError,
        match="INT-005 observation/acceptance ownership",
    ):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_missing_bundle_component_producer(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        _stage(document, "noncontact_acceptance")["produced_bundle_components"].remove(
            "accuracy_budget_assessment"
        )

    path = _temporary_catalog(tmp_path, mutate)
    with pytest.raises(
        PhysicalOnboardingStageCatalogError,
        match="bundle-component production changed",
    ):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_duplicate_bundle_component_producer(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        _stage(document, "physical_handoff")["produced_bundle_components"].append(
            "controlled_source_binding"
        )

    path = _temporary_catalog(tmp_path, mutate)
    with pytest.raises(
        PhysicalOnboardingStageCatalogError,
        match="bundle-component production changed",
    ):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_stage_8_power_weakening(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        _stage(document, "static_registration")[
            "actuator_power_requirement"
        ] = "PREFERABLY_DISCONNECTED"

    path = _temporary_catalog(tmp_path, mutate)
    with pytest.raises(
        PhysicalOnboardingStageCatalogError, match="critical actuator-power"
    ):
        load_physical_onboarding_stage_catalog(tmp_path, path)


@pytest.mark.parametrize(
    "stage",
    ["reference_frame_calibration", "noncontact_acceptance"],
)
def test_rejects_later_motion_stage_without_final_disconnection(
    tmp_path: Path, stage: str
) -> None:
    def mutate(document: dict[str, Any]) -> None:
        _stage(document, stage)[
            "actuator_power_requirement"
        ] = "EXTERNAL_NONCONTACT_PERMIT_REQUIRED"

    path = _temporary_catalog(tmp_path, mutate)
    with pytest.raises(
        PhysicalOnboardingStageCatalogError, match="critical actuator-power"
    ):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_premature_controller_identity_qualification(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        stage_9 = _stage(document, "arm_identity")
        stage_12 = _stage(document, "feedback_only_connection")
        stage_9["produced_bundle_components"].append("qualified_controller_identity")
        stage_12["produced_bundle_components"].remove("qualified_controller_identity")

    path = _temporary_catalog(tmp_path, mutate)
    with pytest.raises(
        PhysicalOnboardingStageCatalogError,
        match="bundle-component production changed|candidate/promotion",
    ):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_intake_overlap_or_early_promotion_row(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        _stage(document, "physical_handoff")["intake_record_ids"] = ["INT-055"]
        document["post_diagnostic_intake_record_ids"] = []

    path = _temporary_catalog(tmp_path, mutate)
    with pytest.raises(PhysicalOnboardingStageCatalogError, match="INT-055"):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_missing_progressive_intake_row(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        _stage(document, "camera_receipt")["intake_record_ids"].remove("INT-001")

    path = _temporary_catalog(tmp_path, mutate)
    with pytest.raises(PhysicalOnboardingStageCatalogError, match="ownership changed"):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_unknown_or_missing_stage(tmp_path: Path) -> None:
    path = _temporary_catalog(tmp_path, lambda document: document["stages"].pop())
    with pytest.raises(PhysicalOnboardingStageCatalogError, match="stage order"):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_weakened_global_quarantine(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["state_model"]["global_quarantine_latches"].remove(
            "SIDE_EFFECT_UNCERTAIN"
        )

    path = _temporary_catalog(tmp_path, mutate)
    with pytest.raises(PhysicalOnboardingStageCatalogError, match="quarantine"):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_unknown_root_field(tmp_path: Path) -> None:
    path = _temporary_catalog(
        tmp_path,
        lambda document: document.update({"unversioned_extension": True}),
    )
    with pytest.raises(PhysicalOnboardingStageCatalogError, match="fields differ"):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_duplicate_json_field(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text(
        CATALOG_PATH.read_text(encoding="utf-8").replace(
            '"runtime_activation": false,',
            '"runtime_activation": false,\n  "runtime_activation": false,',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(PhysicalOnboardingStageCatalogError, match="duplicate"):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_float_anywhere(tmp_path: Path) -> None:
    path = tmp_path / "float.json"
    path.write_text(
        CATALOG_PATH.read_text(encoding="utf-8").replace(
            '"revision": 3,', '"revision": 3.0,', 1
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        PhysicalOnboardingStageCatalogError, match="must not contain floats"
    ):
        load_physical_onboarding_stage_catalog(tmp_path, path)


def test_rejects_catalog_outside_workspace(tmp_path: Path) -> None:
    with pytest.raises(
        PhysicalOnboardingStageCatalogError, match="beneath the workspace"
    ):
        load_physical_onboarding_stage_catalog(tmp_path, CATALOG_PATH)
