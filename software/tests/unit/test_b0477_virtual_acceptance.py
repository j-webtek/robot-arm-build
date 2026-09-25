from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
from typing import Iterator

import pytest

from rocell.application.b0477_static_vision import (
    B0477StaticVisionError,
    B0477StaticVisionMode,
    B0477StaticVisionReport,
    run_b0477_static_vision_rehearsal,
)
from rocell.application.b0477_virtual_acceptance import (
    B0477_VIRTUAL_ACCEPTANCE_SCHEMA,
    B0477VirtualAcceptanceError,
    B0477VirtualAcceptanceReport,
    run_b0477_bound_virtual_acceptance,
)


WORKSPACE = Path(__file__).resolve().parents[3]
SEQUENCE = 93


def _nested_values(value: object) -> Iterator[object]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _nested_values(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _nested_values(child)


def _replace_source_hash(
    report: B0477StaticVisionReport, key: str, digest: str
) -> B0477StaticVisionReport:
    sources = dict(report.source_hashes)
    sources[key] = digest
    return replace(report, source_hashes=tuple(sorted(sources.items())))


@pytest.fixture(scope="module")
def b0477_pair() -> tuple[B0477StaticVisionReport, B0477StaticVisionReport]:
    pytest.importorskip("PIL")
    normal = run_b0477_static_vision_rehearsal(WORKSPACE, sequence=SEQUENCE)
    tag_loss = run_b0477_static_vision_rehearsal(
        WORKSPACE,
        sequence=SEQUENCE,
        mode=B0477StaticVisionMode.TAG_LOSS,
    )
    return normal, tag_loss


@pytest.fixture(scope="module")
def acceptance(
    b0477_pair: tuple[B0477StaticVisionReport, B0477StaticVisionReport],
) -> B0477VirtualAcceptanceReport:
    normal, tag_loss = b0477_pair
    return run_b0477_bound_virtual_acceptance(
        WORKSPACE,
        registration_sequence=SEQUENCE,
        normal_vision_report=normal,
        tag_loss_vision_report=tag_loss,
    )


def test_representative_missions_pass_with_exact_execution_counts(
    acceptance: B0477VirtualAcceptanceReport,
) -> None:
    assert acceptance.schema == B0477_VIRTUAL_ACCEPTANCE_SCHEMA
    assert acceptance.status == (
        "B0477_BOUND_VIRTUAL_ACCEPTANCE_PASSED_WITH_PHYSICAL_HOLDS"
    )
    assert acceptance.passed
    assert acceptance.stack.passed
    assert acceptance.stack.vision_reports_consumed == 2

    keyboard = acceptance.keyboard
    assert keyboard.passed
    assert keyboard.device == "keyboard"
    assert keyboard.semantic_action_count == 4
    assert keyboard.physical_target_count == 4
    assert keyboard.final_waypoint_count == 48
    assert keyboard.virtual_command_count == 48
    assert keyboard.event_count == 61
    assert keyboard.attempted_contact_count == 4
    assert keyboard.accepted_contact_count == 4

    phone = acceptance.phone
    assert phone.passed
    assert phone.device == "phone"
    # The leading phone-state verification is semantic but non-contact.
    assert phone.semantic_action_count == 6
    assert phone.physical_target_count == 5
    assert phone.final_waypoint_count == 61
    assert phone.virtual_command_count == 61
    assert phone.event_count == 77
    assert phone.attempted_contact_count == 5
    assert phone.accepted_contact_count == 5

    assert acceptance.observation_count == 9
    assert acceptance.final_waypoint_count == 109
    assert acceptance.virtual_contact_count == 9


def test_every_mission_observation_is_hash_bound_to_the_selected_b0477(
    acceptance: B0477VirtualAcceptanceReport,
) -> None:
    camera = acceptance.camera
    assert camera.profile_id == "arducam-b0477-imx283-16mm-purchased-001"
    assert camera.support_design_id == "ROCELL-STATIC-CAMERA-SUPPORT-CANDIDATE-001"
    assert camera.optical_frame == "C_overhead_optical"
    assert camera.camera_axis_xy_board_mm == (305.0, 228.5)
    assert camera.entrance_pupil_z_board_mm == 1000.0
    assert camera.native_mode == (5472, 3648, 9.0, "YUY2")
    assert camera.proxy_resolution_px == (2736, 1824)
    assert camera.registration_sequence == SEQUENCE
    assert (
        camera.profile_source_file_sha256
        == camera.support_profile_source_sha256
        == camera.intrinsics_profile_source_sha256
    )

    components = dict(camera.component_hashes)
    optical_sources = dict(camera.optical_source_hashes)
    assert components["intrinsics_fixture_canonical"] == (
        camera.intrinsics_canonical_sha256
    )
    assert components["intrinsics_fixture_file"] == (
        camera.intrinsics_source_file_sha256
    )
    assert components["intrinsics_integrity"] == camera.intrinsics_integrity_sha256
    assert components["normal_vision_report"] == (
        camera.normal_registration_report_sha256
    )
    assert components["tag_loss_vision_report"] == camera.tag_loss_report_sha256
    assert optical_sources["camera_profile_file"] == (camera.profile_source_file_sha256)
    assert optical_sources["support_design"] == camera.support_design_sha256
    assert optical_sources["nominal_intrinsics"] == camera.proxy_intrinsics_sha256

    observations = (
        *acceptance.keyboard.observation_bindings,
        *acceptance.phone.observation_bindings,
    )
    assert len({item.occurrence_attempt_sha256 for item in observations}) == 9
    assert all(
        item.profile_id == camera.profile_id
        and item.camera_evidence_sha256 == camera.content_sha256
        and item.support_pose_sha256 == camera.support_pose_sha256
        and item.intrinsics_artifact_sha256 == camera.intrinsics_canonical_sha256
        and item.registration_report_sha256 == camera.normal_registration_report_sha256
        and item.registration_jpeg_sha256 == camera.normal_registration_jpeg_sha256
        for item in observations
    )


def test_report_is_redacted_canonical_and_does_not_accept_legacy_camera_identity(
    acceptance: B0477VirtualAcceptanceReport,
) -> None:
    document = acceptance.to_dict()
    serialized = json.dumps(document, sort_keys=True, separators=(",", ":"))
    assert "imx335" not in serialized.casefold()
    assert '"plaintext_serialized":false' in serialized
    assert document["evidence_scope"] == {
        "b0477_registration_is_acceptance_preflight": True,
        "b0477_frame_reused_across_both_missions_and_action_bindings": True,
        "per_action_b0477_pixels_rendered": False,
        "historical_session_camera_identity_accepted_as_b0477": False,
        "intrinsics_rehearsal_applied_as_physical_calibration": False,
        "registration_report_trust_scope": (
            "DIRECT_IN_PROCESS_TYPED_VALUE_NOT_EXTERNAL_AUTHENTICATION"
        ),
        "virtual_model_complete": False,
    }
    without_hash = dict(document)
    without_hash.pop("report_hash")
    expected = hashlib.sha256(
        json.dumps(
            without_hash,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    assert acceptance.report_hash == expected
    assert document["report_hash"] == expected


def test_all_serialized_authority_blocks_remain_zero(
    acceptance: B0477VirtualAcceptanceReport,
) -> None:
    assert acceptance.zero_physical_authority
    document = acceptance.to_dict()
    authorities = [
        value
        for value in _nested_values(document)
        if isinstance(value, dict)
        and value.get("simulation_only") is True
        and "hardware_accessed" in value
    ]
    assert authorities
    for authority in authorities:
        assert authority["hardware_accessed"] is False
        assert authority["physical_camera_accessed"] is False
        assert authority["hardware_commands_generated"] == 0
        assert authority["physical_arm_motion_commands"] == 0
        assert authority["physical_contact_commands"] == 0
        assert authority["live_capture_authority"] is False
        assert authority["physical_calibration_authority"] is False
        assert authority["robot_motion_authority"] is False
        assert authority["contact_authority"] is False
        assert authority["physical_release_effect"] == "NONE"


def test_precomputed_registration_pair_is_strict_and_fails_closed(
    b0477_pair: tuple[B0477StaticVisionReport, B0477StaticVisionReport],
) -> None:
    normal, tag_loss = b0477_pair
    with pytest.raises(B0477VirtualAcceptanceError, match="supplied together"):
        run_b0477_bound_virtual_acceptance(
            WORKSPACE,
            registration_sequence=SEQUENCE,
            normal_vision_report=normal,
        )
    with pytest.raises(B0477VirtualAcceptanceError, match="sequences differ"):
        run_b0477_bound_virtual_acceptance(
            WORKSPACE,
            registration_sequence=SEQUENCE + 1,
            normal_vision_report=normal,
            tag_loss_vision_report=tag_loss,
        )
    # A report whose payload passes but whose status claims rejection is now
    # stopped at the report boundary, before it can reach stack acceptance.
    with pytest.raises(B0477StaticVisionError, match="complete synthetic acceptance"):
        replace(
            normal,
            status="REJECTED",
            detail_code="B0477_STATIC_PIXEL_POSE_QUALITY_REJECTED",
        )


def test_precomputed_pair_cannot_smuggle_a_different_static_support_pose(
    b0477_pair: tuple[B0477StaticVisionReport, B0477StaticVisionReport],
) -> None:
    normal, tag_loss = b0477_pair
    changed_transform = list(normal.nominal_projection.camera_T_board_row_major)
    changed_transform[3] += 1.0
    changed_projection = replace(
        normal.nominal_projection,
        camera_T_board_row_major=tuple(changed_transform),
    )
    changed_normal = replace(normal, nominal_projection=changed_projection)
    with pytest.raises(B0477VirtualAcceptanceError, match="static support pose"):
        run_b0477_bound_virtual_acceptance(
            WORKSPACE,
            registration_sequence=SEQUENCE,
            normal_vision_report=changed_normal,
            tag_loss_vision_report=tag_loss,
        )


def test_precomputed_pair_reconstructs_projection_and_optical_processor_hashes(
    b0477_pair: tuple[B0477StaticVisionReport, B0477StaticVisionReport],
) -> None:
    normal, tag_loss = b0477_pair
    changed_matrix = list(normal.nominal_projection.intrinsics_row_major)
    changed_matrix[0] += 1.0
    with pytest.raises(B0477StaticVisionError, match="aspect-consistent"):
        replace(
            normal.nominal_projection,
            intrinsics_row_major=tuple(changed_matrix),
        )

    changed_normal = _replace_source_hash(normal, "nominal_intrinsics", "0" * 64)
    changed_tag_loss = _replace_source_hash(tag_loss, "nominal_intrinsics", "0" * 64)
    with pytest.raises(B0477VirtualAcceptanceError, match="do not reconstruct"):
        run_b0477_bound_virtual_acceptance(
            WORKSPACE,
            registration_sequence=SEQUENCE,
            normal_vision_report=changed_normal,
            tag_loss_vision_report=changed_tag_loss,
        )

    changed_normal = _replace_source_hash(
        normal, "synthetic_undistortion_map", "0" * 64
    )
    changed_tag_loss = _replace_source_hash(
        tag_loss, "synthetic_undistortion_map", "0" * 64
    )
    with pytest.raises(B0477VirtualAcceptanceError, match="do not reconstruct"):
        run_b0477_bound_virtual_acceptance(
            WORKSPACE,
            registration_sequence=SEQUENCE,
            normal_vision_report=changed_normal,
            tag_loss_vision_report=changed_tag_loss,
        )


def test_precomputed_pair_enforces_exact_source_hash_shape(
    b0477_pair: tuple[B0477StaticVisionReport, B0477StaticVisionReport],
) -> None:
    normal, tag_loss = b0477_pair
    changed = _replace_source_hash(normal, "unexpected_source", "0" * 64)
    with pytest.raises(B0477VirtualAcceptanceError, match="exact contract"):
        run_b0477_bound_virtual_acceptance(
            WORKSPACE,
            registration_sequence=SEQUENCE,
            normal_vision_report=changed,
            tag_loss_vision_report=tag_loss,
        )


def test_precomputed_pair_revalidates_support_and_scene_source_files(
    b0477_pair: tuple[B0477StaticVisionReport, B0477StaticVisionReport],
) -> None:
    normal, tag_loss = b0477_pair
    changed_normal = _replace_source_hash(
        normal, "support_source:workcell_layout", "0" * 64
    )
    changed_tag_loss = _replace_source_hash(
        tag_loss, "support_source:workcell_layout", "0" * 64
    )
    with pytest.raises(B0477VirtualAcceptanceError, match="current files"):
        run_b0477_bound_virtual_acceptance(
            WORKSPACE,
            registration_sequence=SEQUENCE,
            normal_vision_report=changed_normal,
            tag_loss_vision_report=changed_tag_loss,
        )


def test_top_level_report_revalidates_every_nested_camera_link(
    acceptance: B0477VirtualAcceptanceReport,
) -> None:
    first = acceptance.keyboard.observation_bindings[0]
    changed = replace(first, support_pose_sha256="0" * 64)
    changed_keyboard = replace(
        acceptance.keyboard,
        observation_bindings=(
            changed,
            *acceptance.keyboard.observation_bindings[1:],
        ),
    )
    with pytest.raises(B0477VirtualAcceptanceError, match="accepted B0477 context"):
        replace(acceptance, keyboard=changed_keyboard)


def test_completed_mission_cannot_pass_with_zeroed_counts(
    acceptance: B0477VirtualAcceptanceReport,
) -> None:
    with pytest.raises(B0477VirtualAcceptanceError, match="counts or terminal"):
        replace(
            acceptance.keyboard,
            requested_text_length=0,
            semantic_action_count=0,
            final_waypoint_count=0,
            virtual_command_count=0,
            event_count=0,
        )


def test_supported_phone_post_tap_verification_shape_is_accepted(
    b0477_pair: tuple[B0477StaticVisionReport, B0477StaticVisionReport],
) -> None:
    normal, tag_loss = b0477_pair
    report = run_b0477_bound_virtual_acceptance(
        WORKSPACE,
        keyboard_text="a",
        phone_text="a\n",
        registration_sequence=SEQUENCE,
        normal_vision_report=normal,
        tag_loss_vision_report=tag_loss,
    )
    assert report.passed
    assert report.phone.requested_text_length == 2
    assert report.phone.physical_target_count == 2
    assert report.phone.semantic_action_count == 4
    assert tuple(item.action_index for item in report.phone.observation_bindings) == (
        1,
        2,
    )


def test_evidence_values_are_immutable_and_wrong_profile_cannot_be_relabelled(
    acceptance: B0477VirtualAcceptanceReport,
) -> None:
    binding = acceptance.keyboard.observation_bindings[0]
    with pytest.raises(FrozenInstanceError):
        binding.target_id = "keyboard:Q"  # type: ignore[misc]
    with pytest.raises(B0477VirtualAcceptanceError, match="purchased B0477"):
        replace(binding, profile_id="legacy-overview-camera")
    with pytest.raises(B0477VirtualAcceptanceError, match="component hashes"):
        replace(acceptance.camera, profile_canonical_sha256="0" * 64)
    changed_transform = list(acceptance.camera.camera_T_board_row_major)
    changed_transform[3] += 1.0
    with pytest.raises(B0477VirtualAcceptanceError, match="support axis and height"):
        replace(
            acceptance.camera,
            camera_T_board_row_major=tuple(changed_transform),
        )
    with pytest.raises(B0477VirtualAcceptanceError, match="native mode types"):
        replace(
            acceptance.camera,
            native_mode=(5472.0, 3648.0, 9.0, "YUY2"),  # type: ignore[arg-type]
        )
    with pytest.raises(B0477VirtualAcceptanceError, match="registration_report_count"):
        replace(acceptance, b0477_registration_report_count=2.0)  # type: ignore[arg-type]


@pytest.mark.parametrize("sequence", [True, -1, 1_000_000_001])
def test_registration_sequence_is_bounded_before_any_session_runs(
    sequence: object,
) -> None:
    with pytest.raises(B0477VirtualAcceptanceError, match="registration_sequence"):
        run_b0477_bound_virtual_acceptance(
            WORKSPACE,
            registration_sequence=sequence,  # type: ignore[arg-type]
        )
