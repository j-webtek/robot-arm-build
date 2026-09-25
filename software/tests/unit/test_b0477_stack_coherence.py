from __future__ import annotations

import builtins
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

import pytest

from rocell.application.b0477_stack_coherence import (
    B0477_STACK_COHERENCE_SCHEMA,
    DEFAULT_B0477_COMMISSIONING_FIXTURE_PATH,
    DEFAULT_B0477_INTRINSICS_FIXTURE_PATH,
    DEFAULT_B0477_PROFILE_PATH,
    DEFAULT_B0477_SUPPORT_PATH,
    DEFAULT_B0477_UVC_FIXTURE_PATH,
    B0477StackCoherenceError,
    assess_b0477_stack_coherence,
    load_and_assess_b0477_stack_coherence,
)
from rocell.application.b0477_optical_contract import (
    build_b0477_synthetic_optical_contract,
)
from rocell.application.b0477_static_vision import (
    B0477HeldOutStationResidual,
    B0477NominalProjection,
    B0477PixelStatistics,
    B0477PoseComparison,
    B0477StaticVisionMode,
    B0477StaticVisionReport,
)
from rocell.calibration.static_camera_intrinsics import (
    StaticCameraIntrinsicsRehearsal,
    StaticIntrinsicsMode,
    load_static_camera_intrinsics_rehearsal,
)
from rocell.vision.camera_commissioning import (
    SyntheticCameraCommissioningRehearsal,
    load_camera_commissioning_rehearsal,
)
from rocell.vision.camera_profile import PurchasedCameraProfile, load_camera_profile
from rocell.vision.uvc_inventory import UvcInventory, parse_uvc_inventory_json
from rocell.workcell.static_camera_support import (
    StaticCameraSupportDesign,
    load_static_camera_support_design,
)


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture
def components() -> tuple[
    PurchasedCameraProfile,
    StaticCameraSupportDesign,
    SyntheticCameraCommissioningRehearsal,
    UvcInventory,
    StaticCameraIntrinsicsRehearsal,
]:
    profile = load_camera_profile(WORKSPACE / DEFAULT_B0477_PROFILE_PATH)
    support = load_static_camera_support_design(
        WORKSPACE, WORKSPACE / DEFAULT_B0477_SUPPORT_PATH
    )
    commissioning = load_camera_commissioning_rehearsal(
        WORKSPACE / DEFAULT_B0477_COMMISSIONING_FIXTURE_PATH,
        fixture_root=WORKSPACE,
    )
    uvc = parse_uvc_inventory_json(
        (WORKSPACE / DEFAULT_B0477_UVC_FIXTURE_PATH).read_bytes()
    )
    intrinsics = load_static_camera_intrinsics_rehearsal(
        WORKSPACE / DEFAULT_B0477_INTRINSICS_FIXTURE_PATH,
        fixture_root=WORKSPACE,
    )
    return profile, support, commissioning, uvc, intrinsics


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _vision_report(
    profile: PurchasedCameraProfile,
    support: StaticCameraSupportDesign,
    mode: B0477StaticVisionMode,
) -> B0477StaticVisionReport:
    normal = mode is B0477StaticVisionMode.NORMAL
    contract = build_b0477_synthetic_optical_contract(profile, support)
    distortion = contract.distortion
    projection = B0477NominalProjection(
        optical_frame=contract.optical_frame,
        resolution_px=(2736, 1824),
        intrinsics_row_major=contract.intrinsics_row_major,
        camera_T_board_row_major=(
            1.0,
            0.0,
            0.0,
            -305.0,
            0.0,
            -1.0,
            0.0,
            228.5,
            0.0,
            0.0,
            -1.0,
            1000.0,
            0.0,
            0.0,
            0.0,
            1.0,
        ),
        camera_axis_xy_board_mm=(305.0, 228.5),
        entrance_pupil_z_board_mm=1000.0,
        tag_plane_z_board_mm=0.3,
        nominal_working_distance_mm=999.7,
        published_fov_deg=(49.0, 38.0),
        effective_rectilinear_fov_deg=(
            contract.effective_horizontal_fov_deg,
            contract.effective_vertical_fov_deg,
        ),
        distortion_coefficients=(
            distortion.k1,
            distortion.k2,
            distortion.p1,
            distortion.p2,
            distortion.k3,
        ),
        intrinsics_source_sha256=contract.intrinsics_source_sha256,
        undistortion_map_sha256=contract.undistortion_map_sha256,
        optical_contract_sha256=contract.content_sha256,
    )
    pixels = B0477PixelStatistics(
        width_px=2736,
        height_px=1824,
        pixel_count=2736 * 1824,
        jpeg_byte_count=100_000,
        jpeg_sha256=("1" if normal else "2") * 64,
        minimum_gray=0,
        maximum_gray=255,
        mean_gray=220.0,
        dark_fraction_below_128=0.02,
        accepted_tag_edge_min_px=105.0,
        accepted_tag_edge_mean_px=110.0,
        accepted_tag_edge_max_px=115.0,
    )
    pose = B0477PoseComparison(
        estimate_available=normal,
        translation_error_mm=0.5 if normal else None,
        rotation_error_deg=0.05 if normal else None,
        inlier_reprojection_rmse_px=0.8 if normal else None,
    )
    expected = tuple(range(6)) if normal else (4, 5)
    held_out = (
        (
            B0477HeldOutStationResidual("K0", 4, 0.7, 0.9),
            B0477HeldOutStationResidual("P0", 5, 0.8, 1.0),
        )
        if normal
        else ()
    )
    return B0477StaticVisionReport(
        sequence=17,
        mode=mode,
        status="PASS" if normal else "REJECTED",
        detail_code=(
            "B0477_STATIC_PIXEL_POSE_ACCEPTED"
            if normal
            else "B0477_STATIC_TAG_LOSS_NATURALLY_REJECTED"
        ),
        profile_id=profile.profile_id,
        support_design_id=support.design_id,
        source_hashes=tuple(
            sorted(
                {
                    "camera_profile_canonical": profile.canonical_sha256,
                    "camera_profile_file": profile.source_file_sha256,
                    "support_design": support.content_sha256,
                }.items()
            )
        ),
        nominal_projection=projection,
        visible_tag_ids=expected,
        detected_tag_ids=expected,
        inlier_tag_ids=(0, 1, 2, 3) if normal else (),
        pixel_statistics=pixels,
        pose_comparison=pose,
        held_out_station_residuals=held_out,
    )


def test_default_workspace_stack_is_coherent_deterministic_and_hash_bound() -> None:
    first = load_and_assess_b0477_stack_coherence(WORKSPACE)
    second = load_and_assess_b0477_stack_coherence(WORKSPACE)

    assert first == second
    assert first.schema == B0477_STACK_COHERENCE_SCHEMA
    assert first.passed
    assert first.status == "SYNTHETIC_B0477_STACK_COHERENT"
    assert all(check.passed for check in first.checks)
    assert first.vision_evidence_state == "NOT_SUPPLIED_OPTIONAL"
    assert first.vision_reports_consumed == 0
    assert first.canonical_sha256 == _canonical_hash(first.to_dict())

    hashes = dict(first.component_hashes)
    assert {
        "camera_profile_canonical",
        "camera_profile_file",
        "commissioning_fixture_canonical",
        "commissioning_fixture_file",
        "uvc_inventory_canonical",
        "uvc_inventory_file",
        "intrinsics_fixture_canonical",
        "intrinsics_fixture_file",
        "intrinsics_integrity",
        "static_support_file",
        "commissioning_assessment",
        "uvc_assessment",
        "intrinsics_assessment",
    }.issubset(hashes)
    assert all(len(value) == 64 for value in hashes.values())


def test_report_is_explicitly_zero_authority() -> None:
    document = load_and_assess_b0477_stack_coherence(WORKSPACE).to_dict()
    assert document["execution"] == {
        "simulation_only": True,
        "hardware_accessed": False,
        "camera_frames_requested": 0,
        "arm_motion_commands": 0,
        "contact_commands": 0,
    }
    assert document["authority"] == {
        "commissioned": False,
        "hardware_presence_authority": False,
        "live_capture_authority": False,
        "physical_calibration_authority": False,
        "physical_static_extrinsic_authority": False,
        "robot_motion_authority": False,
        "contact_authority": False,
        "physical_release_effect": "NONE",
    }


def test_explicit_relative_paths_produce_the_same_report() -> None:
    default = load_and_assess_b0477_stack_coherence(WORKSPACE)
    explicit = load_and_assess_b0477_stack_coherence(
        WORKSPACE,
        camera_profile_path=DEFAULT_B0477_PROFILE_PATH,
        support_design_path=DEFAULT_B0477_SUPPORT_PATH,
        commissioning_fixture_path=DEFAULT_B0477_COMMISSIONING_FIXTURE_PATH,
        uvc_inventory_fixture_path=DEFAULT_B0477_UVC_FIXTURE_PATH,
        intrinsics_fixture_path=DEFAULT_B0477_INTRINSICS_FIXTURE_PATH,
    )
    assert explicit == default


@pytest.mark.parametrize(
    "keyword",
    [
        "camera_profile_path",
        "support_design_path",
        "commissioning_fixture_path",
        "uvc_inventory_fixture_path",
        "intrinsics_fixture_path",
    ],
)
def test_every_input_path_is_workspace_contained(keyword: str) -> None:
    parameters: dict[str, Any] = {keyword: WORKSPACE.parent / "outside.json"}
    with pytest.raises(B0477StackCoherenceError, match="escapes the workspace"):
        load_and_assess_b0477_stack_coherence(
            WORKSPACE,
            **parameters,
        )


Mutation = Callable[
    [
        PurchasedCameraProfile,
        StaticCameraSupportDesign,
        SyntheticCameraCommissioningRehearsal,
        UvcInventory,
        StaticCameraIntrinsicsRehearsal,
    ],
    tuple[
        PurchasedCameraProfile,
        StaticCameraSupportDesign,
        SyntheticCameraCommissioningRehearsal,
        UvcInventory,
        StaticCameraIntrinsicsRehearsal,
    ],
]


def _wrong_profile_lock(
    profile: PurchasedCameraProfile,
    support: StaticCameraSupportDesign,
    commissioning: SyntheticCameraCommissioningRehearsal,
    uvc: UvcInventory,
    intrinsics: StaticCameraIntrinsicsRehearsal,
) -> tuple[
    PurchasedCameraProfile,
    StaticCameraSupportDesign,
    SyntheticCameraCommissioningRehearsal,
    UvcInventory,
    StaticCameraIntrinsicsRehearsal,
]:
    sources = dict(support.source_sha256)
    sources["purchased_camera_profile"] = "0" * 64
    return (
        profile,
        replace(support, source_sha256=MappingProxyType(sources)),
        commissioning,
        uvc,
        intrinsics,
    )


def _wrong_persistent_identity(
    profile: PurchasedCameraProfile,
    support: StaticCameraSupportDesign,
    commissioning: SyntheticCameraCommissioningRehearsal,
    uvc: UvcInventory,
    intrinsics: StaticCameraIntrinsicsRehearsal,
) -> tuple[
    PurchasedCameraProfile,
    StaticCameraSupportDesign,
    SyntheticCameraCommissioningRehearsal,
    UvcInventory,
    StaticCameraIntrinsicsRehearsal,
]:
    return profile, support, commissioning, uvc, replace(
        intrinsics, persistent_camera_identity_sha256="0" * 64
    )


def _wrong_settings_evidence(
    profile: PurchasedCameraProfile,
    support: StaticCameraSupportDesign,
    commissioning: SyntheticCameraCommissioningRehearsal,
    uvc: UvcInventory,
    intrinsics: StaticCameraIntrinsicsRehearsal,
) -> tuple[
    PurchasedCameraProfile,
    StaticCameraSupportDesign,
    SyntheticCameraCommissioningRehearsal,
    UvcInventory,
    StaticCameraIntrinsicsRehearsal,
]:
    return profile, support, commissioning, uvc, replace(
        intrinsics, controls_snapshot_sha256="0" * 64
    )


def _wrong_native_mode(
    profile: PurchasedCameraProfile,
    support: StaticCameraSupportDesign,
    commissioning: SyntheticCameraCommissioningRehearsal,
    uvc: UvcInventory,
    intrinsics: StaticCameraIntrinsicsRehearsal,
) -> tuple[
    PurchasedCameraProfile,
    StaticCameraSupportDesign,
    SyntheticCameraCommissioningRehearsal,
    UvcInventory,
    StaticCameraIntrinsicsRehearsal,
]:
    wrong_mode = StaticIntrinsicsMode(1280, 720, 120.0, "YUY2")
    return profile, support, commissioning, uvc, replace(intrinsics, mode=wrong_mode)


def _hardware_access_claim(
    profile: PurchasedCameraProfile,
    support: StaticCameraSupportDesign,
    commissioning: SyntheticCameraCommissioningRehearsal,
    uvc: UvcInventory,
    intrinsics: StaticCameraIntrinsicsRehearsal,
) -> tuple[
    PurchasedCameraProfile,
    StaticCameraSupportDesign,
    SyntheticCameraCommissioningRehearsal,
    UvcInventory,
    StaticCameraIntrinsicsRehearsal,
]:
    return profile, support, commissioning, replace(uvc, hardware_accessed=True), intrinsics


@pytest.mark.parametrize(
    ("mutation", "failed_check"),
    [
        (_wrong_profile_lock, "profile_digest_binding"),
        (_wrong_persistent_identity, "synthetic_persistent_identity"),
        (_wrong_settings_evidence, "synthetic_capture_settings"),
        (_wrong_native_mode, "native_precision_mode"),
        (_hardware_access_claim, "zero_physical_authority"),
    ],
)
def test_cross_component_mismatches_fail_closed(
    components: tuple[
        PurchasedCameraProfile,
        StaticCameraSupportDesign,
        SyntheticCameraCommissioningRehearsal,
        UvcInventory,
        StaticCameraIntrinsicsRehearsal,
    ],
    mutation: Mutation,
    failed_check: str,
) -> None:
    report = assess_b0477_stack_coherence(*mutation(*components))
    assert not report.passed
    assert report.status == "SYNTHETIC_B0477_STACK_BLOCKED"
    assert report.checks_by_id()[failed_check].passed is False
    assert report.robot_motion_authority is False
    assert report.contact_authority is False


def test_precomputed_normal_and_tag_loss_reports_are_checked_without_rendering(
    components: tuple[
        PurchasedCameraProfile,
        StaticCameraSupportDesign,
        SyntheticCameraCommissioningRehearsal,
        UvcInventory,
        StaticCameraIntrinsicsRehearsal,
    ],
) -> None:
    profile, support, *_ = components
    normal = _vision_report(profile, support, B0477StaticVisionMode.NORMAL)
    tag_loss = _vision_report(profile, support, B0477StaticVisionMode.TAG_LOSS)
    report = assess_b0477_stack_coherence(
        *components,
        normal_vision_report=normal,
        tag_loss_vision_report=tag_loss,
    )
    assert report.passed
    assert report.vision_evidence_state == "PRECOMPUTED_PAIR_SUPPLIED"
    assert report.vision_reports_consumed == 2
    assert report.checks_by_id()["precomputed_vision_pair"].passed
    assert dict(report.component_hashes)["normal_vision_report"] == normal.content_sha256
    assert (
        dict(report.component_hashes)["tag_loss_vision_report"]
        == tag_loss.content_sha256
    )


def test_incomplete_or_source_mismatched_vision_evidence_blocks(
    components: tuple[
        PurchasedCameraProfile,
        StaticCameraSupportDesign,
        SyntheticCameraCommissioningRehearsal,
        UvcInventory,
        StaticCameraIntrinsicsRehearsal,
    ],
) -> None:
    profile, support, *_ = components
    normal = _vision_report(profile, support, B0477StaticVisionMode.NORMAL)
    incomplete = assess_b0477_stack_coherence(
        *components, normal_vision_report=normal
    )
    assert not incomplete.passed
    assert incomplete.vision_evidence_state == "INCOMPLETE_PAIR_BLOCKED"

    tag_loss = _vision_report(profile, support, B0477StaticVisionMode.TAG_LOSS)
    altered_sources = dict(tag_loss.source_hashes)
    altered_sources["support_design"] = "0" * 64
    altered = replace(tag_loss, source_hashes=tuple(sorted(altered_sources.items())))
    mismatched = assess_b0477_stack_coherence(
        *components,
        normal_vision_report=normal,
        tag_loss_vision_report=altered,
    )
    assert not mismatched.passed
    assert not mismatched.checks_by_id()["precomputed_vision_pair"].passed


def test_loader_does_not_import_cv2_or_serial_or_request_hardware(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted: list[str] = []
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> Any:
        if name == "cv2" or name.startswith("cv2.") or name == "serial" or name.startswith("serial."):
            attempted.append(name)
            raise AssertionError(f"stack coherence attempted hardware import {name}")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.delitem(sys.modules, "cv2", raising=False)
    monkeypatch.delitem(sys.modules, "serial", raising=False)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    report = load_and_assess_b0477_stack_coherence(WORKSPACE)
    assert report.passed
    assert attempted == []
    assert report.hardware_accessed is False
    assert report.camera_frames_requested == 0
    assert report.arm_motion_commands == 0
    assert report.contact_commands == 0
