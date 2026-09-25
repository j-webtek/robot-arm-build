from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

import pytest

from rocell.application.context import (
    SimulationContextError,
    load_simulation_context,
)
from rocell.application.placemat_uncertainty import (
    MAX_ABSOLUTE_XY_BOUND_MM,
    CartesianSensitivityBounds,
    GeometryClassification,
    PlacematUncertaintyBounds,
    PlacematUncertaintyError,
    RigidPoseSensitivityBounds,
    run_placemat_uncertainty_simulation,
)
from rocell.vision import DEFAULT_B0477_CAMERA_PROFILE, load_camera_profile
from rocell.workcell import load_static_camera_support_design


WORKSPACE = Path(__file__).resolve().parents[3]
MANIFEST = WORKSPACE / "software/config/system_manifest.json"


@pytest.fixture(scope="module")
def context():
    return load_simulation_context(WORKSPACE, MANIFEST)


def _canonical_hash(document: object) -> str:
    return hashlib.sha256(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _assert_zero_authority(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {
                "hardware_accessed",
                "execution_authorized",
                "live_motion_authorized",
                "physical_contact_authorized",
                "physical_calibration_authority",
                "can_release_physical_gates",
                "physical_identity_verified",
                "physical_installation_verified",
            }:
                assert child is False
            if key in {
                "camera_frames_requested",
                "hardware_commands_generated",
                "arm_motion_commands",
                "contact_commands",
            }:
                assert child == 0
            if key == "physical_release_effect":
                assert child == "NONE"
            _assert_zero_authority(child)
    elif isinstance(value, list):
        for child in value:
            _assert_zero_authority(child)


def _outcome(report, device: str, target_id: str, case_id: str):
    target = next(
        row
        for row in report.targets
        if row.device == device and row.target_id == target_id
    )
    return next(row for row in target.outcomes if row.case_id == case_id)


def test_nominal_only_matrix_covers_every_target_without_claiming_acceptance(
    context,
) -> None:
    report = run_placemat_uncertainty_simulation(
        context, PlacematUncertaintyBounds.zero()
    )

    assert len(report.cases) == 1
    assert report.cases[0].case_id == "nominal"
    assert len(report.targets) == 75
    assert report.keyboard_target_count == 46
    assert report.phone_target_count == 29
    assert report.sensitivity_gap_count == 0
    assert report.status == "NO_GAPS_IN_SAMPLED_ASSUMPTIONS_NO_PHYSICAL_CONCLUSION"
    for target in report.targets:
        outcome = target.outcomes[0]
        assert outcome.classification is GeometryClassification.INSIDE_INTENDED_SAFE_REGION
        assert outcome.intended_safe_region_xy_margin_mm == pytest.approx(
            min(target.nominal_half_extent_x_mm, target.nominal_half_extent_y_mm)
        )
        assert outcome.absolute_z_error_mm == 0.0
    document = report.to_dict()
    assert document["bounds"]["input_semantics"].endswith(
        "NOT_TOLERANCES_OR_ACCEPTANCE_LIMITS"
    )
    _assert_zero_authority(document)


def test_default_signed_and_corner_campaign_is_deterministic_and_hash_sealed(
    context,
) -> None:
    first = run_placemat_uncertainty_simulation(context)
    second = run_placemat_uncertainty_simulation(context)

    assert len(first.cases) == 59
    assert first.to_dict() == second.to_dict()
    assert first.report_sha256 == second.report_sha256
    unsigned = first.to_dict()
    reported_hash = unsigned.pop("report_sha256")
    assert reported_hash == _canonical_hash(unsigned)
    assert len(reported_hash) == 64
    assert len({case.case_id for case in first.cases}) == len(first.cases)
    assert any(case.case_id == "board-x-neg" for case in first.cases)
    assert any(case.case_id == "phone-corner-ppp" for case in first.cases)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: RigidPoseSensitivityBounds(x_mm=-0.01),
        lambda: RigidPoseSensitivityBounds(yaw_deg=float("nan")),
        lambda: CartesianSensitivityBounds(z_mm=True),
    ],
)
def test_invalid_sensitivity_bounds_fail_closed(factory) -> None:
    with pytest.raises(PlacematUncertaintyError):
        factory()


def test_over_bound_sensitivity_input_is_rejected() -> None:
    with pytest.raises(PlacematUncertaintyError, match="hard sensitivity-study bound"):
        CartesianSensitivityBounds(x_mm=MAX_ABSOLUTE_XY_BOUND_MM + 0.001)


def test_service_revalidates_modified_target_objects_before_analysis(context) -> None:
    original = context.targets.keyboard_targets["A"]
    changed_targets = dict(context.targets.keyboard_targets)
    changed_targets["A"] = replace(original, half_extent_x_mm=6.5)
    changed_catalog = replace(context.targets, keyboard_targets=changed_targets)
    changed_context = replace(context, targets=changed_catalog)

    with pytest.raises(SimulationContextError, match="targets differ"):
        run_placemat_uncertainty_simulation(changed_context)


def test_default_assumptions_expose_small_phone_target_vulnerability(context) -> None:
    report = run_placemat_uncertainty_simulation(context)
    keyboard = tuple(target for target in report.targets if target.device == "keyboard")
    phone = tuple(target for target in report.targets if target.device == "phone")

    assert min(target.worst_xy_margin_mm for target in keyboard) > 0.0
    assert all(not target.sensitivity_gap_observed for target in keyboard)
    assert min(target.worst_xy_margin_mm for target in phone) < 0.0
    assert sum(target.sensitivity_gap_observed for target in phone) >= 26
    assert all(target.maximum_absolute_z_error_mm > 0.0 for target in report.targets)
    assert report.status == "SENSITIVITY_GAPS_OBSERVED_NO_PHYSICAL_CONCLUSION"


def test_signed_translation_sources_retain_expected_target_frame_signs(context) -> None:
    bounds = PlacematUncertaintyBounds(
        board_registration=RigidPoseSensitivityBounds(x_mm=1.0),
        keyboard_placement=RigidPoseSensitivityBounds(x_mm=1.25),
        phone_placement=RigidPoseSensitivityBounds(),
        keyboard_target_map=CartesianSensitivityBounds(x_mm=0.5),
        phone_target_map=CartesianSensitivityBounds(),
        tcp=CartesianSensitivityBounds(x_mm=0.75),
    )
    report = run_placemat_uncertainty_simulation(context, bounds)

    board = _outcome(report, "keyboard", "A", "board-x-pos")
    placement = _outcome(report, "keyboard", "A", "keyboard-placement-x-pos")
    target_map = _outcome(report, "keyboard", "A", "keyboard-target-map-x-pos")
    tcp = _outcome(report, "keyboard", "A", "tcp-x-pos")

    assert (board.error_target_x_mm, board.error_target_y_mm) == (-1.0, 0.0)
    assert (placement.error_target_x_mm, placement.error_target_y_mm) == (
        -1.25,
        0.0,
    )
    assert (target_map.error_target_x_mm, target_map.error_target_y_mm) == (
        -0.5,
        0.0,
    )
    assert (tcp.error_target_x_mm, tcp.error_target_y_mm) == (0.75, 0.0)


def test_board_and_device_yaw_use_the_documented_pivots(context) -> None:
    bounds = PlacematUncertaintyBounds(
        board_registration=RigidPoseSensitivityBounds(yaw_deg=1.0),
        keyboard_placement=RigidPoseSensitivityBounds(yaw_deg=1.0),
        phone_placement=RigidPoseSensitivityBounds(),
        keyboard_target_map=CartesianSensitivityBounds(),
        phone_target_map=CartesianSensitivityBounds(),
        tcp=CartesianSensitivityBounds(),
    )
    report = run_placemat_uncertainty_simulation(context, bounds)
    target = context.targets.keyboard_targets["A"]
    theta = math.radians(1.0)

    def rotate(x_mm: float, y_mm: float, angle: float) -> tuple[float, float]:
        return (
            math.cos(angle) * x_mm - math.sin(angle) * y_mm,
            math.sin(angle) * x_mm + math.cos(angle) * y_mm,
        )

    board_center = (
        (context.scene.board.minimum.x + context.scene.board.maximum.x) / 2.0,
        (context.scene.board.minimum.y + context.scene.board.maximum.y) / 2.0,
    )
    board_radius = (
        target.center.x - board_center[0],
        target.center.y - board_center[1],
    )
    inverse_board_radius = rotate(*board_radius, -theta)
    expected_board_error = (
        inverse_board_radius[0] - board_radius[0],
        inverse_board_radius[1] - board_radius[1],
    )
    board_outcome = _outcome(report, "keyboard", "A", "board-yaw-pos")
    assert board_outcome.error_target_x_mm == pytest.approx(
        expected_board_error[0], abs=1e-9
    )
    assert board_outcome.error_target_y_mm == pytest.approx(
        expected_board_error[1], abs=1e-9
    )

    device = context.scene.devices["keyboard"].envelope
    device_radius = (
        target.center.x - device.minimum.x,
        target.center.y - device.minimum.y,
    )
    inverse_device_radius = rotate(*device_radius, -theta)
    expected_device_error = (
        inverse_device_radius[0] - device_radius[0],
        inverse_device_radius[1] - device_radius[1],
    )
    device_outcome = _outcome(
        report, "keyboard", "A", "keyboard-placement-yaw-pos"
    )
    assert device_outcome.error_target_x_mm == pytest.approx(
        expected_device_error[0], abs=1e-9
    )
    assert device_outcome.error_target_y_mm == pytest.approx(
        expected_device_error[1], abs=1e-9
    )


def test_classifier_reports_adjacent_and_boundary_failures_without_authority(
    context,
) -> None:
    bounds = PlacematUncertaintyBounds(
        board_registration=RigidPoseSensitivityBounds(),
        keyboard_placement=RigidPoseSensitivityBounds(),
        phone_placement=RigidPoseSensitivityBounds(x_mm=25.0, yaw_deg=5.0),
        keyboard_target_map=CartesianSensitivityBounds(),
        phone_target_map=CartesianSensitivityBounds(x_mm=5.0),
        tcp=CartesianSensitivityBounds(),
    )
    report = run_placemat_uncertainty_simulation(context, bounds)
    observed = {
        outcome.classification
        for target in report.targets
        for outcome in target.outcomes
    }

    assert GeometryClassification.ADJACENT_OR_AMBIGUOUS_TARGET in observed
    assert GeometryClassification.DEVICE_BOUNDARY_EXCEEDED in observed
    assert GeometryClassification.BOARD_BOUNDARY_EXCEEDED in observed
    adjacent = _outcome(report, "phone", "key_a", "phone-target-map-x-neg")
    assert adjacent.classification is GeometryClassification.ADJACENT_OR_AMBIGUOUS_TARGET
    assert adjacent.adjacent_target_ids == ("key_s",)
    assert adjacent.intended_safe_region_xy_margin_mm == -2.0
    board_precedence = _outcome(report, "phone", "key_b", "phone-corner-pnn")
    assert board_precedence.classification is GeometryClassification.BOARD_BOUNDARY_EXCEEDED
    assert board_precedence.adjacent_target_ids == ("key_z",)
    _assert_zero_authority(report.to_dict())


def test_report_binds_strict_static_support_and_purchased_b0477_profile(
    context,
) -> None:
    support = load_static_camera_support_design(WORKSPACE)
    profile = load_camera_profile(WORKSPACE / DEFAULT_B0477_CAMERA_PROFILE)
    report = run_placemat_uncertainty_simulation(
        context, PlacematUncertaintyBounds.zero()
    )
    binding = report.source_binding

    assert binding.design_revision == context.snapshot.design_revision
    assert binding.nominal_target_profile_sha256 == context.targets.content_sha256
    assert binding.static_support_design_id == support.design_id
    assert binding.static_support_sha256 == support.content_sha256
    assert binding.b0477_profile_id == profile.profile_id
    assert binding.b0477_profile_file_sha256 == profile.source_file_sha256
    assert binding.b0477_profile_canonical_sha256 == profile.canonical_sha256
    assert (
        binding.camera_architecture_plan_sha256
        == support.source_sha256["camera_architecture_plan"]
    )
    assert len(binding.implementation_sha256) == 64
    selected = report.to_dict()["source_binding"]["selected_static_camera"]
    assert selected["architecture"] == "STATIC_OVERHEAD_EYE_TO_HAND"
    assert selected["physical_identity_verified"] is False
    assert selected["physical_installation_verified"] is False
    canonical = report.to_dict()["source_binding"]["canonical_profile_camera_boundary"]
    assert canonical["reinterpreted_as_b0477_static"] is False
    assert canonical["superseding_controlled_freeze_required"] is True
