"""Cross-check the complete synthetic B0477 static-camera stack.

This module is the hardware-free seam between five independently strict
contracts:

* the purchase-time B0477 profile;
* the static overhead support screening design;
* the deterministic commissioning rehearsal;
* the deterministic UVC inventory rehearsal; and
* the synthetic intrinsics rehearsal.

Each source is useful by itself, but that is not enough: a calibration for one
synthetic identity must never be combined with settings or geometry from
another.  The assessor below therefore revalidates every source and then binds
their identities, digests, native mode, persistent selector, and capture
settings.  Optional, already-computed normal and tag-loss pixel reports can be
checked without rendering another image.

The result is diagnostic evidence only.  Neither loading nor assessment opens
a camera, imports a hardware backend, sends a robot command, or grants any
physical, motion, or contact authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping

from rocell.application.b0477_static_vision import (
    B0477StaticVisionMode,
    B0477StaticVisionReport,
)
from rocell.calibration.static_camera_intrinsics import (
    StaticCameraIntrinsicsError,
    StaticCameraIntrinsicsRehearsal,
    assess_static_camera_intrinsics_rehearsal,
    load_static_camera_intrinsics_rehearsal,
)
from rocell.vision.camera_commissioning import (
    CameraCommissioningRehearsalError,
    SyntheticCameraCommissioningRehearsal,
    assess_camera_commissioning_rehearsal,
    load_camera_commissioning_rehearsal,
)
from rocell.vision.camera_profile import PurchasedCameraProfile, load_camera_profile
from rocell.vision.uvc_inventory import (
    UvcCaptureControl,
    UvcDevice,
    UvcInventory,
    UvcInventoryError,
    assess_uvc_inventory,
    parse_uvc_inventory_json,
)
from rocell.workcell.static_camera_support import (
    StaticCameraSupportDesign,
    load_static_camera_support_design,
)


B0477_STACK_COHERENCE_SCHEMA = "rocell.b0477_static_stack_coherence.v1"

DEFAULT_B0477_PROFILE_PATH = Path(
    "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
)
DEFAULT_B0477_SUPPORT_PATH = Path(
    "hardware/static_overhead_camera/config/support_design.json"
)
DEFAULT_B0477_COMMISSIONING_FIXTURE_PATH = Path(
    "software/tests/fixtures/camera/b0477_nominal_rehearsal.json"
)
DEFAULT_B0477_UVC_FIXTURE_PATH = Path(
    "software/tests/fixtures/camera/b0477_nominal_uvc_inventory.json"
)
DEFAULT_B0477_INTRINSICS_FIXTURE_PATH = Path(
    "software/tests/fixtures/camera/b0477_synthetic_intrinsics_rehearsal.json"
)

_TARGET_PROFILE_ID = "arducam-b0477-imx283-16mm-purchased-001"
_TARGET_MODE = (5472, 3648, 9.0, "YUY2")
_TARGET_MODE_WITH_BUS = (*_TARGET_MODE, "USB_3_2_GEN_1")
_EXPECTED_TAG_IDS = tuple(range(6))
_POSE_FIT_TAG_IDS = (0, 1, 2, 3)
_HELD_OUT_STATION_TAG_IDS = (4, 5)
_TAG_LOSS_VISIBLE_IDS = (4, 5)
_CHECK_ID = re.compile(r"^[a-z][a-z0-9_]{0,95}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class B0477StackCoherenceError(ValueError):
    """A stack input cannot be loaded or represented safely."""


def _canonical_hash(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive boundary
        raise B0477StackCoherenceError("stack report is not canonicalizable") from exc
    return hashlib.sha256(encoded).hexdigest()


def _validate_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise B0477StackCoherenceError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _resolve_contained_file(
    workspace_root: Path,
    selected: Path | None,
    default_path: Path,
    label: str,
) -> Path:
    candidate = default_path if selected is None else selected
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise B0477StackCoherenceError(f"{label} escapes the workspace") from exc
    if not resolved.is_file():
        raise B0477StackCoherenceError(f"{label} is not a file: {resolved}")
    return resolved


@dataclass(frozen=True, slots=True)
class B0477StackCheck:
    """One deterministic cross-component coherence gate."""

    check_id: str
    passed: bool
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.check_id, str) or _CHECK_ID.fullmatch(self.check_id) is None:
            raise B0477StackCoherenceError("stack check_id is invalid")
        if not isinstance(self.passed, bool):
            raise B0477StackCoherenceError("stack check passed must be boolean")
        if (
            not isinstance(self.message, str)
            or not self.message
            or len(self.message.encode("utf-8")) > 2_048
        ):
            raise B0477StackCoherenceError("stack check message is invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class B0477StackCoherenceReport:
    """Deterministic diagnostic result with permanently zero authority."""

    profile_id: str
    support_design_id: str
    component_hashes: tuple[tuple[str, str], ...]
    checks: tuple[B0477StackCheck, ...]
    vision_evidence_state: str
    vision_reports_consumed: int
    schema: str = B0477_STACK_COHERENCE_SCHEMA
    simulation_only: bool = field(init=False, default=True)
    commissioned: bool = field(init=False, default=False)
    hardware_accessed: bool = field(init=False, default=False)
    camera_frames_requested: int = field(init=False, default=0)
    arm_motion_commands: int = field(init=False, default=0)
    contact_commands: int = field(init=False, default=0)
    hardware_presence_authority: bool = field(init=False, default=False)
    live_capture_authority: bool = field(init=False, default=False)
    physical_calibration_authority: bool = field(init=False, default=False)
    physical_static_extrinsic_authority: bool = field(init=False, default=False)
    robot_motion_authority: bool = field(init=False, default=False)
    contact_authority: bool = field(init=False, default=False)
    physical_release_effect: str = field(init=False, default="NONE")

    def __post_init__(self) -> None:
        if self.schema != B0477_STACK_COHERENCE_SCHEMA:
            raise B0477StackCoherenceError("unsupported stack coherence schema")
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise B0477StackCoherenceError("profile_id must be non-empty text")
        if not isinstance(self.support_design_id, str) or not self.support_design_id:
            raise B0477StackCoherenceError("support_design_id must be non-empty text")
        if (
            not isinstance(self.component_hashes, tuple)
            or not self.component_hashes
            or self.component_hashes != tuple(sorted(self.component_hashes))
            or len({name for name, _ in self.component_hashes})
            != len(self.component_hashes)
        ):
            raise B0477StackCoherenceError(
                "component_hashes must be a non-empty canonical tuple"
            )
        for name, digest in self.component_hashes:
            if not isinstance(name, str) or _CHECK_ID.fullmatch(name) is None:
                raise B0477StackCoherenceError("component hash name is invalid")
            _validate_digest(digest, f"component hash {name}")
        if not isinstance(self.checks, tuple) or not self.checks:
            raise B0477StackCoherenceError("checks must be a non-empty tuple")
        if any(not isinstance(check, B0477StackCheck) for check in self.checks):
            raise B0477StackCoherenceError("checks contains an invalid item")
        ids = tuple(check.check_id for check in self.checks)
        if len(ids) != len(set(ids)):
            raise B0477StackCoherenceError("stack check ids must be unique")
        if self.vision_evidence_state not in {
            "NOT_SUPPLIED_OPTIONAL",
            "INCOMPLETE_PAIR_BLOCKED",
            "PRECOMPUTED_PAIR_SUPPLIED",
        }:
            raise B0477StackCoherenceError("vision evidence state is invalid")
        if self.vision_reports_consumed not in (0, 1, 2):
            raise B0477StackCoherenceError("vision report count is invalid")
        expected_count = {
            "NOT_SUPPLIED_OPTIONAL": 0,
            "INCOMPLETE_PAIR_BLOCKED": 1,
            "PRECOMPUTED_PAIR_SUPPLIED": 2,
        }[self.vision_evidence_state]
        if self.vision_reports_consumed != expected_count:
            raise B0477StackCoherenceError(
                "vision evidence state disagrees with report count"
            )

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def status(self) -> str:
        return (
            "SYNTHETIC_B0477_STACK_COHERENT"
            if self.passed
            else "SYNTHETIC_B0477_STACK_BLOCKED"
        )

    @property
    def canonical_sha256(self) -> str:
        return _canonical_hash(self.to_dict())

    def checks_by_id(self) -> Mapping[str, B0477StackCheck]:
        return MappingProxyType({check.check_id: check for check in self.checks})

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "status": self.status,
            "passed": self.passed,
            "profile_id": self.profile_id,
            "support_design_id": self.support_design_id,
            "component_hashes": dict(self.component_hashes),
            "checks": [check.to_dict() for check in self.checks],
            "vision_evidence": {
                "state": self.vision_evidence_state,
                "reports_consumed": self.vision_reports_consumed,
                "required_for_core_stack_coherence": False,
            },
            "execution": {
                "simulation_only": self.simulation_only,
                "hardware_accessed": self.hardware_accessed,
                "camera_frames_requested": self.camera_frames_requested,
                "arm_motion_commands": self.arm_motion_commands,
                "contact_commands": self.contact_commands,
            },
            "authority": {
                "commissioned": self.commissioned,
                "hardware_presence_authority": self.hardware_presence_authority,
                "live_capture_authority": self.live_capture_authority,
                "physical_calibration_authority": self.physical_calibration_authority,
                "physical_static_extrinsic_authority": (
                    self.physical_static_extrinsic_authority
                ),
                "robot_motion_authority": self.robot_motion_authority,
                "contact_authority": self.contact_authority,
                "physical_release_effect": self.physical_release_effect,
            },
        }


def _selected_uvc_devices(inventory: UvcInventory) -> tuple[UvcDevice, ...]:
    selected: list[UvcDevice] = []
    for snapshot in inventory.reopen_snapshots:
        matches = tuple(
            device
            for device in snapshot.devices
            if device.identity.persistent_path == inventory.selector_value
        )
        if len(matches) != 1:
            return ()
        selected.append(matches[0])
    return tuple(selected)


def _controls_by_id(controls: tuple[UvcCaptureControl, ...]) -> Mapping[str, UvcCaptureControl]:
    return MappingProxyType({control.control_id: control for control in controls})


def _intrinsics_settings_hash(intrinsics: StaticCameraIntrinsicsRehearsal) -> str:
    """Recompute the intrinsics artifact's complete camera-settings binding."""

    return _canonical_hash(
        {
            "persistent_camera_identity_sha256": (
                intrinsics.persistent_camera_identity_sha256
            ),
            "mode": intrinsics.mode.to_dict(),
            "focus_lock_evidence_sha256": intrinsics.focus_lock_evidence_sha256,
            "aperture_lock_evidence_sha256": intrinsics.aperture_lock_evidence_sha256,
            "controls_snapshot_sha256": intrinsics.controls_snapshot_sha256,
        }
    )


def _vision_pair_ok(
    normal: B0477StaticVisionReport,
    tag_loss: B0477StaticVisionReport,
    *,
    profile: PurchasedCameraProfile,
    support: StaticCameraSupportDesign,
) -> bool:
    expected_sources = {
        "camera_profile_canonical": profile.canonical_sha256,
        "camera_profile_file": profile.source_file_sha256,
        "support_design": support.content_sha256,
    }

    def sources_match(report: B0477StaticVisionReport) -> bool:
        sources = dict(report.source_hashes)
        return all(sources.get(key) == value for key, value in expected_sources.items())

    zero_authority = all(
        report.authority.simulation_only
        and not report.authority.physical_camera_accessed
        and not report.authority.hardware_presence_authority
        and not report.authority.live_capture_authority
        and not report.authority.physical_calibration_authority
        and not report.authority.physical_static_extrinsic_authority
        and not report.authority.robot_motion_authority
        and not report.authority.contact_authority
        and report.authority.hardware_commands_generated == 0
        for report in (normal, tag_loss)
    )
    shared = all(
        report.profile_id == profile.profile_id
        and report.support_design_id == support.design_id
        and sources_match(report)
        for report in (normal, tag_loss)
    )
    normal_ok = (
        normal.mode is B0477StaticVisionMode.NORMAL
        and normal.status == "PASS"
        and normal.detail_code == "B0477_STATIC_PIXEL_POSE_ACCEPTED"
        and normal.visible_tag_ids == _EXPECTED_TAG_IDS
        and normal.detected_tag_ids == _EXPECTED_TAG_IDS
        and normal.inlier_tag_ids == _POSE_FIT_TAG_IDS
        and normal.pose_comparison.estimate_available
        and tuple(
            item.tag_id for item in normal.held_out_station_residuals
        )
        == _HELD_OUT_STATION_TAG_IDS
        and normal.held_out_station_checks_passed
    )
    loss_ok = (
        tag_loss.mode is B0477StaticVisionMode.TAG_LOSS
        and tag_loss.status == "REJECTED"
        and tag_loss.detail_code == "B0477_STATIC_TAG_LOSS_NATURALLY_REJECTED"
        and tag_loss.visible_tag_ids == _TAG_LOSS_VISIBLE_IDS
        and tag_loss.detected_tag_ids == _TAG_LOSS_VISIBLE_IDS
        and tag_loss.inlier_tag_ids == ()
        and not tag_loss.pose_comparison.estimate_available
        and tag_loss.held_out_station_residuals == ()
        and not tag_loss.held_out_station_checks_passed
    )
    return normal.sequence == tag_loss.sequence and shared and normal_ok and loss_ok and zero_authority


def assess_b0477_stack_coherence(
    profile: PurchasedCameraProfile,
    support: StaticCameraSupportDesign,
    commissioning: SyntheticCameraCommissioningRehearsal,
    uvc_inventory: UvcInventory,
    intrinsics: StaticCameraIntrinsicsRehearsal,
    *,
    normal_vision_report: B0477StaticVisionReport | None = None,
    tag_loss_vision_report: B0477StaticVisionReport | None = None,
) -> B0477StackCoherenceReport:
    """Assess already-validated components without reading files or hardware."""

    expected_types = (
        (profile, PurchasedCameraProfile, "profile"),
        (support, StaticCameraSupportDesign, "support"),
        (
            commissioning,
            SyntheticCameraCommissioningRehearsal,
            "commissioning",
        ),
        (uvc_inventory, UvcInventory, "uvc_inventory"),
        (intrinsics, StaticCameraIntrinsicsRehearsal, "intrinsics"),
    )
    for value, expected, label in expected_types:
        if not isinstance(value, expected):
            raise TypeError(f"{label} must be {expected.__name__}")
    for report, label in (
        (normal_vision_report, "normal_vision_report"),
        (tag_loss_vision_report, "tag_loss_vision_report"),
    ):
        if report is not None and not isinstance(report, B0477StaticVisionReport):
            raise TypeError(f"{label} must be B0477StaticVisionReport or None")

    try:
        commissioning_assessment = assess_camera_commissioning_rehearsal(
            commissioning, purchased_profile=profile
        )
        commissioning_assessment_ok = commissioning_assessment.passed
    except CameraCommissioningRehearsalError:
        commissioning_assessment = None
        commissioning_assessment_ok = False
    try:
        intrinsics_assessment = assess_static_camera_intrinsics_rehearsal(
            intrinsics, purchased_profile=profile
        )
        intrinsics_assessment_ok = intrinsics_assessment.structural_gates_passed
    except StaticCameraIntrinsicsError:
        intrinsics_assessment = None
        intrinsics_assessment_ok = False
    try:
        uvc_assessment = assess_uvc_inventory(profile, uvc_inventory)
        uvc_assessment_ok = uvc_assessment.passed
    except UvcInventoryError:
        uvc_assessment = None
        uvc_assessment_ok = False

    selected_uvc = _selected_uvc_devices(uvc_inventory)
    expected_profile_mode = profile.published_mode("USB_3_2_GEN_1", 5472, 3648)
    profile_mode_ok = expected_profile_mode is not None and (
        expected_profile_mode.width_px,
        expected_profile_mode.height_px,
        expected_profile_mode.maximum_fps,
        expected_profile_mode.pixel_format,
    ) == _TARGET_MODE
    commissioning_mode_ok = all(
        (
            snapshot.mode.width_px,
            snapshot.mode.height_px,
            snapshot.mode.fps,
            snapshot.mode.fourcc,
            snapshot.negotiated_bus,
        )
        == _TARGET_MODE_WITH_BUS
        for snapshot in commissioning.camera.reopen_snapshots
    )
    uvc_mode_ok = bool(selected_uvc) and all(
        (
            snapshot.selected_mode.width_px,
            snapshot.selected_mode.height_px,
            snapshot.selected_mode.fps,
            snapshot.selected_mode.fourcc,
            snapshot.selected_mode.host_bus,
        )
        == _TARGET_MODE_WITH_BUS
        and snapshot.negotiated_bus == "USB_3_2_GEN_1"
        and any(
            (
                mode.width_px,
                mode.height_px,
                mode.fps,
                mode.fourcc,
                mode.host_bus,
            )
            == _TARGET_MODE_WITH_BUS
            for mode in device.modes
        )
        for snapshot, device in zip(uvc_inventory.reopen_snapshots, selected_uvc)
    )
    intrinsics_mode_ok = (
        intrinsics.mode.width_px,
        intrinsics.mode.height_px,
        intrinsics.mode.fps,
        intrinsics.mode.pixel_format,
    ) == _TARGET_MODE

    profile_ids_ok = (
        profile.profile_id
        == commissioning.target_profile_id
        == uvc_inventory.profile_id
        == intrinsics.profile_id
        == _TARGET_PROFILE_ID
    )
    profile_hashes_ok = (
        support.source_sha256.get("purchased_camera_profile")
        == profile.source_file_sha256
        and uvc_inventory.profile_sha256 == profile.canonical_sha256
        and intrinsics.profile_source_file_sha256 == profile.source_file_sha256
    )
    identity_ok = (
        (profile.manufacturer, profile.model, profile.sensor, profile.lens_mount)
        == ("Arducam", "B0477", "Sony IMX283", "C-mount")
        and profile.focal_length_mm == 16.0
        and (support.camera_model, support.sensor)
        == ("Arducam B0477", "Sony IMX283")
        and (
            commissioning.target_manufacturer,
            commissioning.target_model,
            commissioning.target_sensor,
        )
        == ("Arducam", "B0477", "Sony IMX283")
        and bool(selected_uvc)
        and all(
            device.identity.manufacturer.casefold() == "arducam"
            and "b0477" in device.identity.product.casefold()
            for device in selected_uvc
        )
    )
    support_geometry_ok = (
        support.state == "SCREENING_CANDIDATE_PHYSICAL_QUALIFICATION_OPEN"
        and support.camera_axis_xy_mm == (305.0, 228.5)
        and support.nominal_entrance_pupil_z_mm == 1000.0
        and support.native_mode == _TARGET_MODE
        and support.field_of_view_deg == (49.0, 38.0, 60.0)
        and support.metrics.minimum_height_view_margin_width_mm > 0.0
        and support.metrics.minimum_height_view_margin_depth_mm > 0.0
    )

    uvc_identity_hashes = {
        device.identity.canonical_sha256 for device in selected_uvc
    }
    persistent_identity_ok = (
        len(selected_uvc) == len(uvc_inventory.reopen_snapshots)
        and commissioning.camera.persistent_device_id == uvc_inventory.selector_value
        and all(
            snapshot.persistent_device_id == uvc_inventory.selector_value
            for snapshot in commissioning.camera.reopen_snapshots
        )
        and len(uvc_identity_hashes) == 1
        and intrinsics.persistent_camera_identity_sha256 in uvc_identity_hashes
    )

    commissioning_controls = commissioning.camera.reopen_snapshots[0].controls
    uvc_settings_hashes = {
        snapshot.settings_sha256 for snapshot in uvc_inventory.reopen_snapshots
    }
    controls_semantics_ok = bool(selected_uvc) and all(
        (
            (controls := _controls_by_id(snapshot.controls)).get("exposure")
            is not None
            and controls["exposure"].mode == "manual"
            and controls["exposure"].value == commissioning_controls.exposure_us
            and controls["exposure"].unit == "microseconds"
            and controls.get("white_balance") is not None
            and controls["white_balance"].mode == "manual"
            and controls["white_balance"].value
            == commissioning_controls.white_balance_kelvin
            and controls["white_balance"].unit == "kelvin"
            and controls.get("gain") is not None
            and controls["gain"].mode == "manual"
            and controls["gain"].value == commissioning_controls.gain_observed
            and controls["gain"].unit == "relative"
        )
        for snapshot in uvc_inventory.reopen_snapshots
    )
    settings_binding_ok = (
        len(uvc_settings_hashes) == 1
        and intrinsics.controls_snapshot_sha256 in uvc_settings_hashes
        and intrinsics.settings_binding_sha256 == _intrinsics_settings_hash(intrinsics)
    )

    zero_authority_ok = (
        profile.record_state == "PURCHASED_PENDING_RECEIPT"
        and not profile.live_ready
        and not any(profile.authority.values())
        and not commissioning.commissioned
        and not commissioning.hardware_accessed
        and commissioning.camera_frames_requested == 0
        and commissioning.arm_commands == 0
        and commissioning.physical_release_effect == "NONE"
        and not uvc_inventory.hardware_accessed
        and not uvc_inventory.commissioned
        and not uvc_inventory.live_capture_authority
        and not uvc_inventory.robot_motion_authority
        and not uvc_inventory.contact_authority
        and not intrinsics.physical_calibration_valid
        and not intrinsics.commissioned
        and not intrinsics.robot_motion_authority
        and not intrinsics.contact_authority
    )

    checks = [
        B0477StackCheck(
            "component_structural_assessments",
            commissioning_assessment_ok and uvc_assessment_ok and intrinsics_assessment_ok,
            "commissioning, UVC, and intrinsics component assessors all pass synthetically",
        ),
        B0477StackCheck(
            "selected_camera_identity",
            identity_ok,
            "all components identify the purchased Arducam B0477 / IMX283 / 16 mm C-mount combination",
        ),
        B0477StackCheck(
            "profile_id_binding",
            profile_ids_ok,
            "every synthetic component binds the exact purchased profile id",
        ),
        B0477StackCheck(
            "profile_digest_binding",
            profile_hashes_ok,
            "support and intrinsics bind profile source bytes while UVC binds canonical profile meaning",
        ),
        B0477StackCheck(
            "native_precision_mode",
            profile_mode_ok
            and support.native_mode == _TARGET_MODE
            and commissioning_mode_ok
            and uvc_mode_ok
            and intrinsics_mode_ok,
            "every component selects 5472x3648 at 9 fps YUY2 over USB 3.2 Gen 1 where bus is represented",
        ),
        B0477StackCheck(
            "support_geometry_binding",
            support_geometry_ok,
            "support retains the centered 1000 mm static geometry and positive minimum-height view margin",
        ),
        B0477StackCheck(
            "synthetic_persistent_identity",
            persistent_identity_ok,
            "commissioning path, UVC selector/identity, and intrinsics identity digest describe one synthetic camera",
        ),
        B0477StackCheck(
            "synthetic_capture_settings",
            controls_semantics_ok and settings_binding_ok,
            "manual exposure, white balance, gain, reopen settings, and intrinsics settings evidence remain linked",
        ),
        B0477StackCheck(
            "zero_physical_authority",
            zero_authority_ok,
            "all components remain hardware-free and grant no capture, calibration, motion, or contact authority",
        ),
    ]

    vision_count = int(normal_vision_report is not None) + int(
        tag_loss_vision_report is not None
    )
    if vision_count == 0:
        vision_state = "NOT_SUPPLIED_OPTIONAL"
    elif vision_count == 1:
        vision_state = "INCOMPLETE_PAIR_BLOCKED"
        checks.append(
            B0477StackCheck(
                "precomputed_vision_pair",
                False,
                "precomputed vision evidence must contain both normal and tag-loss reports",
            )
        )
    else:
        vision_state = "PRECOMPUTED_PAIR_SUPPLIED"
        assert normal_vision_report is not None
        assert tag_loss_vision_report is not None
        checks.append(
            B0477StackCheck(
                "precomputed_vision_pair",
                _vision_pair_ok(
                    normal_vision_report,
                    tag_loss_vision_report,
                    profile=profile,
                    support=support,
                ),
                "normal pixels fit T0-T3 and independently check K0/P0 while tag-loss pixels reject naturally under the same source bindings",
            )
        )

    component_hash_values: dict[str, str] = {
        "camera_profile_canonical": profile.canonical_sha256,
        "camera_profile_file": profile.source_file_sha256,
        "commissioning_fixture_canonical": commissioning.canonical_sha256,
        "commissioning_fixture_file": commissioning.source_file_sha256,
        "intrinsics_fixture_canonical": intrinsics.canonical_sha256,
        "intrinsics_fixture_file": intrinsics.source_file_sha256,
        "intrinsics_integrity": intrinsics.integrity_sha256,
        "static_support_file": support.content_sha256,
        "uvc_inventory_canonical": uvc_inventory.canonical_sha256,
    }
    if uvc_inventory.source_file_sha256 is not None:
        component_hash_values["uvc_inventory_file"] = uvc_inventory.source_file_sha256
    if commissioning_assessment is not None:
        component_hash_values["commissioning_assessment"] = (
            commissioning_assessment.canonical_sha256
        )
    if uvc_assessment is not None:
        component_hash_values["uvc_assessment"] = uvc_assessment.canonical_sha256
    if intrinsics_assessment is not None:
        component_hash_values["intrinsics_assessment"] = (
            intrinsics_assessment.canonical_sha256
        )
    if normal_vision_report is not None:
        component_hash_values["normal_vision_report"] = (
            normal_vision_report.content_sha256
        )
    if tag_loss_vision_report is not None:
        component_hash_values["tag_loss_vision_report"] = (
            tag_loss_vision_report.content_sha256
        )

    return B0477StackCoherenceReport(
        profile_id=profile.profile_id,
        support_design_id=support.design_id,
        component_hashes=tuple(sorted(component_hash_values.items())),
        checks=tuple(checks),
        vision_evidence_state=vision_state,
        vision_reports_consumed=vision_count,
    )


def load_and_assess_b0477_stack_coherence(
    workspace_root: Path | str,
    *,
    camera_profile_path: Path | None = None,
    support_design_path: Path | None = None,
    commissioning_fixture_path: Path | None = None,
    uvc_inventory_fixture_path: Path | None = None,
    intrinsics_fixture_path: Path | None = None,
    normal_vision_report: B0477StaticVisionReport | None = None,
    tag_loss_vision_report: B0477StaticVisionReport | None = None,
) -> B0477StackCoherenceReport:
    """Load contained workspace artifacts and assess their shared contract.

    All paths, including symlink targets, must remain below ``workspace_root``.
    The function reads only bounded JSON evidence; it has no live provider and
    cannot enumerate, open, or capture from a camera.
    """

    root = Path(workspace_root).resolve()
    if not root.is_dir():
        raise B0477StackCoherenceError(
            "workspace_root must be an existing directory"
        )
    profile_path = _resolve_contained_file(
        root,
        camera_profile_path,
        DEFAULT_B0477_PROFILE_PATH,
        "camera profile path",
    )
    support_path = _resolve_contained_file(
        root,
        support_design_path,
        DEFAULT_B0477_SUPPORT_PATH,
        "support design path",
    )
    commissioning_path = _resolve_contained_file(
        root,
        commissioning_fixture_path,
        DEFAULT_B0477_COMMISSIONING_FIXTURE_PATH,
        "commissioning fixture path",
    )
    uvc_path = _resolve_contained_file(
        root,
        uvc_inventory_fixture_path,
        DEFAULT_B0477_UVC_FIXTURE_PATH,
        "UVC inventory fixture path",
    )
    intrinsics_path = _resolve_contained_file(
        root,
        intrinsics_fixture_path,
        DEFAULT_B0477_INTRINSICS_FIXTURE_PATH,
        "intrinsics fixture path",
    )

    profile = load_camera_profile(profile_path)
    support = load_static_camera_support_design(root, support_path)
    commissioning = load_camera_commissioning_rehearsal(
        commissioning_path, fixture_root=root
    )
    try:
        uvc_payload = uvc_path.read_bytes()
    except OSError as exc:  # pragma: no cover - is_file was already checked
        raise B0477StackCoherenceError(
            f"cannot read UVC inventory fixture {uvc_path}: {exc}"
        ) from exc
    uvc_inventory = parse_uvc_inventory_json(uvc_payload)
    intrinsics = load_static_camera_intrinsics_rehearsal(
        intrinsics_path, fixture_root=root
    )
    return assess_b0477_stack_coherence(
        profile,
        support,
        commissioning,
        uvc_inventory,
        intrinsics,
        normal_vision_report=normal_vision_report,
        tag_loss_vision_report=tag_loss_vision_report,
    )


__all__ = [
    "B0477_STACK_COHERENCE_SCHEMA",
    "DEFAULT_B0477_COMMISSIONING_FIXTURE_PATH",
    "DEFAULT_B0477_INTRINSICS_FIXTURE_PATH",
    "DEFAULT_B0477_PROFILE_PATH",
    "DEFAULT_B0477_SUPPORT_PATH",
    "DEFAULT_B0477_UVC_FIXTURE_PATH",
    "B0477StackCheck",
    "B0477StackCoherenceError",
    "B0477StackCoherenceReport",
    "assess_b0477_stack_coherence",
    "load_and_assess_b0477_stack_coherence",
]
