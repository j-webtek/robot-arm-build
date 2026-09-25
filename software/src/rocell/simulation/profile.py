"""Simulation-only hardware identity bound to the controlled software manifests.

This model deliberately has no physical-release capability.  It records the
user-authorized assumption that the expected hardware is healthy enough to
model while preserving the actual build's independent acceptance state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from ._validation import (
    SimulationSourceError,
    identifier,
    load_json_object,
    mapping,
    sha256_file,
    source_path,
)


class SimulationProfileStatus(str, Enum):
    ASSUMED_GOOD_FOR_SIMULATION_ONLY = "ASSUMED_GOOD_FOR_SIMULATION_ONLY"


@dataclass(frozen=True, slots=True)
class SimulatedArmIdentity:
    manufacturer: str
    model: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "manufacturer", identifier(self.manufacturer, "arm manufacturer"))
        object.__setattr__(self, "model", identifier(self.model, "arm model"))


@dataclass(frozen=True, slots=True)
class SimulatedCameraIdentity:
    manufacturer: str
    model: str
    sku: str
    interface: str
    sensor: str

    def __post_init__(self) -> None:
        for field_name in ("manufacturer", "model", "sku", "interface", "sensor"):
            object.__setattr__(
                self,
                field_name,
                identifier(getattr(self, field_name), f"camera {field_name}"),
            )


@dataclass(frozen=True, slots=True)
class SimulationHardwareProfile:
    """Hash-bound identities and assumptions with permanently absent authority."""

    profile_id: str
    design_revision: str
    source_profile_sha256: str
    source_freeze_id: str
    source_manifest_sha256: str
    source_camera_binding_id: str
    source_camera_manifest_sha256: str
    source_manifest_status: str
    source_physical_release_status: str
    arm: SimulatedArmIdentity
    camera: SimulatedCameraIdentity
    assumptions: tuple[str, ...]
    status: SimulationProfileStatus = field(
        default=SimulationProfileStatus.ASSUMED_GOOD_FOR_SIMULATION_ONLY,
        init=False,
    )

    def __post_init__(self) -> None:
        for field_name in (
            "profile_id",
            "design_revision",
            "source_freeze_id",
            "source_camera_binding_id",
            "source_manifest_status",
            "source_physical_release_status",
        ):
            object.__setattr__(
                self,
                field_name,
                identifier(getattr(self, field_name), field_name),
            )
        for field_name in (
            "source_profile_sha256",
            "source_manifest_sha256",
            "source_camera_manifest_sha256",
        ):
            value = identifier(getattr(self, field_name), field_name).lower()
            if re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise SimulationSourceError(f"{field_name} must be a SHA-256 hex digest")
            object.__setattr__(self, field_name, value)
        if not isinstance(self.arm, SimulatedArmIdentity):
            raise TypeError("arm must be SimulatedArmIdentity")
        if not isinstance(self.camera, SimulatedCameraIdentity):
            raise TypeError("camera must be SimulatedCameraIdentity")
        assumptions = tuple(identifier(value, "simulation assumption") for value in self.assumptions)
        if not assumptions:
            raise SimulationSourceError("At least one simulation assumption is required")
        object.__setattr__(self, "assumptions", assumptions)

    @property
    def simulation_only(self) -> bool:
        return True

    @property
    def hardware_io_allowed(self) -> bool:
        return False

    @property
    def can_release_physical_gates(self) -> bool:
        return False

    @property
    def physical_pass(self) -> bool:
        return False

    @property
    def safe_to_power_robot(self) -> bool:
        return False

    @property
    def contact_enabled(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.simulation_hardware_profile.v1",
            "profile_id": self.profile_id,
            "status": self.status.value,
            "sources": {
                "design_revision": self.design_revision,
                "simulation_profile_sha256": self.source_profile_sha256,
                "freeze_id": self.source_freeze_id,
                "system_manifest_sha256": self.source_manifest_sha256,
                "camera_binding_id": self.source_camera_binding_id,
                "camera_manifest_sha256": self.source_camera_manifest_sha256,
                "system_manifest_status": self.source_manifest_status,
                "physical_release_status": self.source_physical_release_status,
            },
            "arm": {
                "manufacturer": self.arm.manufacturer,
                "model": self.arm.model,
            },
            "camera": {
                "manufacturer": self.camera.manufacturer,
                "model": self.camera.model,
                "sku": self.camera.sku,
                "interface": self.camera.interface,
                "sensor": self.camera.sensor,
            },
            "assumptions": list(self.assumptions),
            "authority": {
                "simulation_only": True,
                "hardware_io_allowed": False,
                "can_release_physical_gates": False,
                "physical_pass": False,
                "safe_to_power_robot": False,
                "contact_enabled": False,
            },
        }

    @property
    def profile_hash(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def load_simulation_hardware_profile(
    workspace: Path,
    *,
    profile_path: Path | None = None,
    system_manifest_path: Path | None = None,
    camera_manifest_path: Path | None = None,
) -> SimulationHardwareProfile:
    """Bind the expected Pro arm/camera to manifests without inheriting authority."""

    workspace = workspace.resolve()
    selected_profile_path = (
        profile_path.resolve()
        if profile_path is not None
        else source_path(workspace, "software/config/simulation_hardware_profile.json")
    )
    system_path = (
        system_manifest_path.resolve()
        if system_manifest_path is not None
        else source_path(workspace, "software/config/system_manifest.json")
    )
    camera_path = (
        camera_manifest_path.resolve()
        if camera_manifest_path is not None
        else source_path(workspace, "software/config/camera_manifest.json")
    )
    for path, name in (
        (selected_profile_path, "simulation profile"),
        (system_path, "system manifest"),
        (camera_path, "camera manifest"),
    ):
        try:
            path.relative_to(workspace)
        except ValueError as exc:
            raise SimulationSourceError(f"{name} must be beneath the workspace") from exc

    profile = load_json_object(selected_profile_path)
    if profile.get("schema") != "rocell.simulation_hardware_profile.v1":
        raise SimulationSourceError("Unsupported simulation hardware profile schema")
    if profile.get("status") != SimulationProfileStatus.ASSUMED_GOOD_FOR_SIMULATION_ONLY.value:
        raise SimulationSourceError("Hardware profile is not explicitly simulation-only")
    if profile.get("simulation_only") is not True:
        raise SimulationSourceError("Hardware profile must set simulation_only true")
    if profile.get("physical_release_effect") != "NONE":
        raise SimulationSourceError("Hardware profile must have no physical release effect")
    if profile.get("live_hardware_access_allowed") is not False:
        raise SimulationSourceError("Hardware profile must prohibit live hardware access")

    system = load_json_object(system_path)
    camera_binding = load_json_object(camera_path)
    freeze_id = identifier(system.get("manifest_id"), "system manifest id")
    binding = mapping(profile.get("binding"), "profile.binding")
    if binding.get("system_manifest_id") != freeze_id:
        raise SimulationSourceError("Simulation profile does not reference the selected system freeze")
    if camera_binding.get("system_freeze_id") != freeze_id:
        raise SimulationSourceError("Camera binding does not reference the selected system freeze")

    hardware = mapping(system.get("hardware"), "system.hardware")
    robot = mapping(hardware.get("robot"), "system.hardware.robot")
    system_arm_model = identifier(robot.get("model"), "robot model")
    if system_arm_model != "Waveshare RoArm-M3 Pro":
        raise SimulationSourceError(
            f"Simulation profile requires Waveshare RoArm-M3 Pro, found {system_arm_model!r}"
        )
    profile_robot = mapping(profile.get("robot"), "profile.robot")
    profile_arm_manufacturer = identifier(
        profile_robot.get("manufacturer"), "profile robot manufacturer"
    )
    profile_arm_model = identifier(profile_robot.get("model"), "profile robot model")
    if (profile_arm_manufacturer, profile_arm_model) != ("Waveshare", "RoArm-M3-Pro"):
        raise SimulationSourceError("Simulation profile robot identity is not RoArm-M3-Pro")
    design_revision = identifier(binding.get("design_revision"), "binding design revision")

    purchased = mapping(camera_binding.get("purchased_product"), "camera.purchased_product")
    if (
        camera_binding.get("schema_version") != 1
        or camera_binding.get("manifest_id") != "ROCELL-CAMERA-BINDING-001"
        or camera_binding.get("status")
        != "STANDALONE_HOLDER_FROZEN_USB_CAMERA_CANDIDATE_SELECTED_PHYSICAL_IDENTITY_BLOCKED"
        or camera_binding.get("architecture") != "eye_on_moving_upper_arm"
    ):
        raise SimulationSourceError("Camera binding schema, identity, state, or architecture changed")
    if purchased.get("selected_variant") != "RoArm-M3-Pro":
        raise SimulationSourceError("Camera binding is not for the RoArm-M3-Pro variant")
    if purchased.get("camera_holder_included") is not True or purchased.get("camera_included") is not False:
        raise SimulationSourceError("Camera binding changed the standalone package contents")
    primary = mapping(camera_binding.get("primary"), "camera.primary")
    if primary.get("backend") != "usb_opencv":
        raise SimulationSourceError("Selected camera binding must use the USB/OpenCV backend")
    selected = mapping(primary.get("selected_candidate"), "camera.primary.selected_candidate")
    expected_binding = {
        "manufacturer": "Waveshare",
        "model": "IMX335 5MP USB Camera (B)",
        "sku": "26719",
        "interface": "USB 2.0",
        "sensor": "IMX335",
    }
    for key, expected_value in expected_binding.items():
        if selected.get(key) != expected_value:
            raise SimulationSourceError(
                f"Expected camera candidate {key}={expected_value!r}, found {selected.get(key)!r}"
            )
    expected_module_size = [25.0, 24.0]
    expected_hole_spacing = [21.0, 13.5]
    if selected.get("module_size_mm") != expected_module_size:
        raise SimulationSourceError("Selected camera module envelope changed")
    if selected.get("camera_hole_center_spacing_mm") != expected_hole_spacing:
        raise SimulationSourceError("Selected camera mounting-hole spacing changed")
    holder_binding = mapping(camera_binding.get("holder"), "camera.holder")
    if (
        holder_binding.get("identity") != "Waveshare bundled RoArm camera holder"
        or holder_binding.get("camera_hole_center_spacing_mm") != expected_hole_spacing
        or holder_binding.get("carrier") != "moving upper-arm twin 1020 rail structure"
        or holder_binding.get("installed_rail_position_mm") is not None
        or holder_binding.get("physical_part_revision") is not None
    ):
        raise SimulationSourceError("Bundled camera-holder identity, geometry, or open state changed")
    optional_backends = mapping(camera_binding.get("optional_backends"), "camera.optional_backends")
    esp_backend = mapping(optional_backends.get("esp_http_mjpeg"), "camera ESP backend")
    if esp_backend.get("selected") is not False:
        raise SimulationSourceError("Optional ESP camera backend became selected")

    profile_camera = mapping(profile.get("camera"), "profile.camera")
    expected_profile_camera = {
        "manufacturer": "Waveshare",
        "expected_model": "IMX335 5MP USB Camera (B)",
        "sku": "26719",
        "interface": "USB 2.0",
        "sensor": "Sony IMX335",
    }
    for key, expected_value in expected_profile_camera.items():
        if profile_camera.get(key) != expected_value:
            raise SimulationSourceError(
                f"Simulation profile camera {key} must be {expected_value!r}"
            )
    if profile_camera.get("module_size_mm") != expected_module_size:
        raise SimulationSourceError("Profile and camera binding module envelopes differ")
    if profile_camera.get("holder_hole_centres_mm") != expected_hole_spacing:
        raise SimulationSourceError("Profile and camera binding holder-hole spacing differ")

    rc03 = mapping(system.get("rc03"), "system.rc03")
    if rc03.get("design_revision") != design_revision:
        raise SimulationSourceError("Simulation profile and RC03 design revisions disagree")
    for binding_key in ("workcell_layout", "apriltag_map", "nominal_target_profiles"):
        relative = identifier(binding.get(binding_key), f"binding.{binding_key}")
        path = source_path(workspace, relative)
        if not path.is_file():
            raise SimulationSourceError(f"Simulation profile binding is missing: {relative}")

    official_model = mapping(profile_robot.get("official_model"), "profile.robot.official_model")
    model_relative = identifier(
        official_model.get("local_kinematic_projection"),
        "official_model.local_kinematic_projection",
    )
    model_path = source_path(workspace, model_relative)
    expected_model_hash = identifier(
        official_model.get("local_kinematic_projection_sha256"),
        "official_model.local_kinematic_projection_sha256",
    ).lower()
    if sha256_file(model_path) != expected_model_hash:
        raise SimulationSourceError("Pinned local RoArm kinematic projection hash mismatch")

    controller_sources = mapping(
        profile_robot.get("official_controller_sources"),
        "profile.robot.official_controller_sources",
    )
    python_sdk = mapping(controller_sources.get("python_sdk"), "controller sources python SDK")
    firmware_archive = mapping(
        controller_sources.get("firmware_archive"),
        "controller sources firmware archive",
    )
    if python_sdk.get("commit") != "d9893632aa7f5a9cb283136ab024faf3143ea7db":
        raise SimulationSourceError("Official RoArm SDK source pin changed")
    if firmware_archive.get("sha256") != (
        "a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57"
    ):
        raise SimulationSourceError("Official RoArm firmware source pin changed")

    frame_contract = mapping(profile_robot.get("frame_contract"), "profile.robot.frame_contract")
    expected_frame_contract = {
        "urdf_root": "world",
        "urdf_base": "base_link",
        "urdf_tip": "hand_tcp",
        "controller_cartesian_frame": "R_ctrl",
        "controller_frame_equivalence": "NOT_ASSUMED",
    }
    for key, expected_value in expected_frame_contract.items():
        if frame_contract.get(key) != expected_value:
            raise SimulationSourceError(
                f"Simulation frame contract {key} must be {expected_value!r}"
            )
    controller_bridge = mapping(
        profile_robot.get("controller_model_bridge"),
        "profile.robot.controller_model_bridge",
    )
    if "not a released live-safe joint envelope" not in identifier(
        controller_bridge.get("authority"), "controller bridge authority"
    ):
        raise SimulationSourceError(
            "Controller/model bridge must deny a released live-safe joint envelope"
        )

    if profile_camera.get("selection_state") != (
        "WAVESHARE_COMPATIBLE_SELECTED_CANDIDATE_NOT_EXPLICITLY_NAMED_BY_ARM_PRODUCT_PAGE"
    ):
        raise SimulationSourceError("Camera selection must remain an explicit compatible candidate")
    carrier = mapping(profile_camera.get("carrier"), "profile.camera.carrier")
    if (
        carrier.get("architecture") != "eye_on_arm"
        or carrier.get("holder") != "bundled Waveshare camera holder"
        or carrier.get("mount_pattern_mm") != expected_hole_spacing
        or carrier.get("carrier_frame") != "E"
        or carrier.get("vendor_carrier_link") != "link2"
        or carrier.get("optical_frame") != "C_arm"
    ):
        raise SimulationSourceError("Camera carrier E must remain installation-specific on link2")
    if carrier.get("link2_T_holder") is not None or carrier.get("holder_T_C_optical") is not None:
        raise SimulationSourceError(
            "Unmeasured camera installation transforms must remain null in the nominal profile"
        )

    defaults = mapping(profile.get("simulation_defaults"), "profile.simulation_defaults")
    if defaults.get("hardware_commands_generated") != 0:
        raise SimulationSourceError("Simulation profile must generate zero hardware commands")
    boundary = mapping(profile.get("assumption_boundary"), "profile.assumption_boundary")
    assumed = boundary.get("assumed_good_in_simulation")
    not_proven = boundary.get("not_assumed_or_proven")
    if not isinstance(assumed, list) or not assumed or not isinstance(not_proven, list) or not not_proven:
        raise SimulationSourceError("Simulation assumption boundary must list assumed and unproven items")
    assumptions = tuple(
        [f"ASSUMED_GOOD: {identifier(value, 'assumed-good item')}" for value in assumed]
        + [f"NOT_PROVEN: {identifier(value, 'unproven item')}" for value in not_proven]
        + [identifier(boundary.get("rule"), "assumption boundary rule")]
    )
    return SimulationHardwareProfile(
        profile_id=identifier(profile.get("profile_id"), "simulation profile id"),
        design_revision=design_revision,
        source_profile_sha256=sha256_file(selected_profile_path),
        source_freeze_id=freeze_id,
        source_manifest_sha256=sha256_file(system_path),
        source_camera_binding_id=identifier(
            camera_binding.get("manifest_id"), "camera manifest id"
        ),
        source_camera_manifest_sha256=sha256_file(camera_path),
        source_manifest_status=identifier(system.get("status"), "system manifest status"),
        source_physical_release_status=identifier(
            rc03.get("physical_release_status"), "physical release status"
        ),
        arm=SimulatedArmIdentity(profile_arm_manufacturer, profile_arm_model),
        camera=SimulatedCameraIdentity(
            manufacturer=expected_profile_camera["manufacturer"],
            model=expected_profile_camera["expected_model"],
            sku=expected_profile_camera["sku"],
            interface=expected_profile_camera["interface"],
            sensor=expected_profile_camera["sensor"],
        ),
        assumptions=assumptions,
    )
