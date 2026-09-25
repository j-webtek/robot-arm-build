"""B0477-bound, zero-I/O acceptance for representative typing missions.

The mature virtual-session simulator predates the selected camera and retains
its historical fixed-overview raster internally.  Changing that simulator in
place would invalidate a large golden evidence surface.  This module instead
provides a narrow composition boundary:

* validate the purchased Arducam B0477 profile, static support candidate,
  synthetic intrinsics rehearsal, UVC rehearsal, and B0477 pixel/pose pair;
* run the existing keyboard and Android trajectory/contact/outcome sessions;
* reconstruct their typed observation ledgers; and
* bind every observation occurrence to one immutable B0477 camera-evidence
context by content hash.

The B0477 registration frame is an acceptance-run preflight observation and is
intentionally reusable across both bounded missions and their action
occurrences.  The preflight now exercises one aspect-consistent, distorted
capture-to-rectified-pixel contract, but it does not claim that a new B0477
image was rendered for every key/tap or that the separate physical-shaped
intrinsics rehearsal fixture is a measured calibration.  It proves integration
and evidence plumbing before hardware arrives; it never opens a device, emits
a Waveshare command, or grants physical authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from rocell.calibration.static_camera_intrinsics import (
    StaticCameraIntrinsicsRehearsal,
    assess_static_camera_intrinsics_rehearsal,
    load_static_camera_intrinsics_rehearsal,
)
from rocell.models.actions import Device, PressKey, TapPhoneTarget
from rocell.simulation.scene import NominalWorkcellScene, load_rc03_nominal_scene
from rocell.simulation.synthetic_raster import SyntheticRasterConfig
from rocell.vision.apriltag_codebook import DEFAULT_APRILTAG_36H11_CODEBOOK
from rocell.vision.camera_profile import PurchasedCameraProfile, load_camera_profile
from rocell.vision.detections import TagReference
from rocell.vision.pixel_detector import (
    AprilTag36h11PixelDetector,
    AprilTagPixelDetectorConfiguration,
)
from rocell.vision.planar_pose_estimator import PlanarBoardTag, PlanarBoardTagMap
from rocell.workcell.static_camera_support import (
    StaticCameraSupportDesign,
    load_static_camera_support_design,
)

from .b0477_stack_coherence import (
    DEFAULT_B0477_INTRINSICS_FIXTURE_PATH,
    DEFAULT_B0477_PROFILE_PATH,
    DEFAULT_B0477_SUPPORT_PATH,
    B0477StackCoherenceReport,
    load_and_assess_b0477_stack_coherence,
)
from .b0477_optical_contract import (
    B0477OpticalContractError,
    build_b0477_synthetic_optical_contract,
)
from .b0477_static_vision import (
    B0477_OPTICAL_FRAME,
    B0477StaticVisionMode,
    B0477StaticVisionReport,
    run_b0477_static_vision_rehearsal,
)
from .virtual_pixel_vision import (
    VirtualPixelVisionAttemptLedger,
    virtual_pixel_vision_attempt_ledger_from_dict,
)
from .virtual_session import VirtualSessionReport, run_default_virtual_session


B0477_VIRTUAL_ACCEPTANCE_SCHEMA = "rocell.b0477_virtual_acceptance.v1"
B0477_CAMERA_EVIDENCE_SCHEMA = "rocell.b0477_camera_evidence_binding.v1"
B0477_MISSION_OBSERVATION_SCHEMA = "rocell.b0477_mission_observation_binding.v1"
B0477_VIRTUAL_MISSION_SCHEMA = "rocell.b0477_virtual_mission_acceptance.v1"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED_PROFILE_ID = "arducam-b0477-imx283-16mm-purchased-001"
_EXPECTED_SUPPORT_ID = "ROCELL-STATIC-CAMERA-SUPPORT-CANDIDATE-001"
_MAX_TEXT_LENGTH = 256
_SHARED_B0477_SOURCE_KEYS = frozenset(
    {
        "camera_profile_canonical",
        "camera_profile_file",
        "detector_configuration",
        "detector_implementation",
        "optical_contract",
        "nominal_fit_tag_map",
        "nominal_held_out_station_map",
        "nominal_intrinsics",
        "nominal_tag_map",
        "renderer_source_bundle",
        "rectifier_configuration",
        "rectifier_implementation",
        "synthetic_undistortion_map",
        "scene_source:config/workcell_layout.json",
        "scene_source:fiducials/apriltag_map.json",
        "support_design",
        "support_source:camera_architecture_plan",
        "support_source:purchased_camera_profile",
        "support_source:robot_reach_screening",
        "support_source:workcell_layout",
    }
)
_NORMAL_ONLY_B0477_SOURCE_KEYS = frozenset(
    {
        "detected_batch",
        "fit_detection_batch",
        "pose_observation",
        "raw_detected_batch",
        "rectified_detection_batch",
        "renderer_config",
        "renderer_definition",
    }
)
_TAG_LOSS_ONLY_B0477_SOURCE_KEYS = frozenset(
    {
        "detected_batch",
        "fit_detection_batch",
        "raw_detected_batch",
        "rectified_detection_batch",
        "renderer_config",
        "renderer_definition",
    }
)


class B0477VirtualAcceptanceError(ValueError):
    """The bounded B0477 acceptance inputs or evidence links are invalid."""


def _stable_hash(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise B0477VirtualAcceptanceError(
            f"acceptance evidence is not canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise B0477VirtualAcceptanceError(f"{label} must be a lowercase SHA-256")
    return value


def _bounded_text(value: object, label: str, *, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise B0477VirtualAcceptanceError(
            f"{label} must be non-empty bounded trimmed text"
        )
    return value


def _count(value: object, label: str, *, maximum: int = 100_000) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= maximum
    ):
        raise B0477VirtualAcceptanceError(
            f"{label} must be an integer within [0, {maximum}]"
        )
    return value


def _finite_tuple(
    value: tuple[float, ...], label: str, *, length: int
) -> tuple[float, ...]:
    parsed = tuple(float(item) for item in value)
    if len(parsed) != length or any(not math.isfinite(item) for item in parsed):
        raise B0477VirtualAcceptanceError(
            f"{label} must contain {length} finite numbers"
        )
    return parsed


def _zero_authority() -> dict[str, object]:
    """Return a fresh JSON-safe authority object for every serialization."""

    return {
        "simulation_only": True,
        "hardware_accessed": False,
        "physical_camera_accessed": False,
        "hardware_commands_generated": 0,
        "physical_arm_motion_commands": 0,
        "physical_contact_commands": 0,
        "hardware_presence_authority": False,
        "live_capture_authority": False,
        "physical_calibration_authority": False,
        "physical_static_extrinsic_authority": False,
        "robot_motion_authority": False,
        "contact_authority": False,
        "physical_release_effect": "NONE",
    }


def _contained_file(root: Path, relative: Path, label: str) -> Path:
    selected = (root / relative).resolve()
    try:
        selected.relative_to(root)
    except ValueError as exc:
        raise B0477VirtualAcceptanceError(f"{label} escapes the workspace") from exc
    if not selected.is_file():
        raise B0477VirtualAcceptanceError(f"{label} is not a file: {selected}")
    return selected


@dataclass(frozen=True, slots=True)
class B0477CameraEvidenceBinding:
    """One content-addressed B0477 optical context shared by both missions."""

    profile_id: str
    profile_canonical_sha256: str
    profile_source_file_sha256: str
    support_design_id: str
    support_design_sha256: str
    support_profile_source_sha256: str
    optical_frame: str
    camera_axis_xy_board_mm: tuple[float, float]
    entrance_pupil_z_board_mm: float
    camera_T_board_row_major: tuple[float, ...]
    native_mode: tuple[int, int, float, str]
    published_fov_deg: tuple[float, float, float]
    proxy_resolution_px: tuple[int, int]
    proxy_intrinsics_sha256: str
    intrinsics_artifact_id: str
    intrinsics_source_file_sha256: str
    intrinsics_canonical_sha256: str
    intrinsics_integrity_sha256: str
    intrinsics_profile_source_sha256: str
    intrinsics_solution_sha256: str
    intrinsics_input_bindings_sha256: str
    intrinsics_undistortion_map_sha256: str
    normal_registration_report_sha256: str
    normal_registration_jpeg_sha256: str
    tag_loss_report_sha256: str
    tag_loss_jpeg_sha256: str
    stack_coherence_sha256: str
    component_hashes: tuple[tuple[str, str], ...]
    optical_source_hashes: tuple[tuple[str, str], ...]
    implementation_sha256: str
    registration_sequence: int
    schema: str = B0477_CAMERA_EVIDENCE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != B0477_CAMERA_EVIDENCE_SCHEMA:
            raise B0477VirtualAcceptanceError("unsupported camera-evidence schema")
        if self.profile_id != _EXPECTED_PROFILE_ID:
            raise B0477VirtualAcceptanceError("unexpected purchased camera profile")
        if self.support_design_id != _EXPECTED_SUPPORT_ID:
            raise B0477VirtualAcceptanceError("unexpected static support design")
        if self.optical_frame != B0477_OPTICAL_FRAME:
            raise B0477VirtualAcceptanceError("unexpected B0477 optical frame")
        for name in (
            "profile_canonical_sha256",
            "profile_source_file_sha256",
            "support_design_sha256",
            "support_profile_source_sha256",
            "proxy_intrinsics_sha256",
            "intrinsics_source_file_sha256",
            "intrinsics_canonical_sha256",
            "intrinsics_integrity_sha256",
            "intrinsics_profile_source_sha256",
            "intrinsics_solution_sha256",
            "intrinsics_input_bindings_sha256",
            "intrinsics_undistortion_map_sha256",
            "normal_registration_report_sha256",
            "normal_registration_jpeg_sha256",
            "tag_loss_report_sha256",
            "tag_loss_jpeg_sha256",
            "stack_coherence_sha256",
            "implementation_sha256",
        ):
            _digest(getattr(self, name), name)
        if not (
            self.profile_source_file_sha256
            == self.support_profile_source_sha256
            == self.intrinsics_profile_source_sha256
        ):
            raise B0477VirtualAcceptanceError(
                "profile, support, and intrinsics source bindings differ"
            )
        axis = _finite_tuple(
            tuple(self.camera_axis_xy_board_mm),
            "camera_axis_xy_board_mm",
            length=2,
        )
        if axis != (305.0, 228.5):
            raise B0477VirtualAcceptanceError("B0477 support is not centered on RC03")
        object.__setattr__(self, "camera_axis_xy_board_mm", axis)
        if (
            isinstance(self.entrance_pupil_z_board_mm, bool)
            or not isinstance(self.entrance_pupil_z_board_mm, (int, float))
            or not math.isfinite(float(self.entrance_pupil_z_board_mm))
            or float(self.entrance_pupil_z_board_mm) != 1000.0
        ):
            raise B0477VirtualAcceptanceError(
                "B0477 entrance-pupil height must remain the 1000 mm candidate"
            )
        object.__setattr__(
            self, "entrance_pupil_z_board_mm", float(self.entrance_pupil_z_board_mm)
        )
        transform = _finite_tuple(
            tuple(self.camera_T_board_row_major),
            "camera_T_board_row_major",
            length=16,
        )
        expected_transform = (
            1.0,
            0.0,
            0.0,
            -axis[0],
            0.0,
            -1.0,
            0.0,
            axis[1],
            0.0,
            0.0,
            -1.0,
            float(self.entrance_pupil_z_board_mm),
            0.0,
            0.0,
            0.0,
            1.0,
        )
        if transform != expected_transform:
            raise B0477VirtualAcceptanceError(
                "camera_T_board does not match the enforced support axis and height"
            )
        object.__setattr__(self, "camera_T_board_row_major", transform)
        if (
            len(self.native_mode) != 4
            or isinstance(self.native_mode[0], bool)
            or not isinstance(self.native_mode[0], int)
            or isinstance(self.native_mode[1], bool)
            or not isinstance(self.native_mode[1], int)
            or isinstance(self.native_mode[2], bool)
            or not isinstance(self.native_mode[2], (int, float))
            or not isinstance(self.native_mode[3], str)
        ):
            raise B0477VirtualAcceptanceError("B0477 native mode types are invalid")
        normalized_native_mode = (
            self.native_mode[0],
            self.native_mode[1],
            float(self.native_mode[2]),
            self.native_mode[3],
        )
        if normalized_native_mode != (5472, 3648, 9.0, "YUY2"):
            raise B0477VirtualAcceptanceError("unexpected B0477 native mode")
        object.__setattr__(self, "native_mode", normalized_native_mode)
        normalized_fov = _finite_tuple(
            tuple(self.published_fov_deg), "published_fov_deg", length=3
        )
        if normalized_fov != (49.0, 38.0, 60.0):
            raise B0477VirtualAcceptanceError("unexpected B0477 published FOV")
        object.__setattr__(self, "published_fov_deg", normalized_fov)
        if (
            len(self.proxy_resolution_px) != 2
            or isinstance(self.proxy_resolution_px[0], bool)
            or not isinstance(self.proxy_resolution_px[0], int)
            or isinstance(self.proxy_resolution_px[1], bool)
            or not isinstance(self.proxy_resolution_px[1], int)
            or self.proxy_resolution_px != (2736, 1824)
        ):
            raise B0477VirtualAcceptanceError("unexpected B0477 proxy resolution")
        _count(
            self.registration_sequence,
            "registration_sequence",
            maximum=1_000_000_000,
        )
        for name in ("component_hashes", "optical_source_hashes"):
            values = tuple(getattr(self, name))
            if (
                not values
                or values != tuple(sorted(values))
                or len({key for key, _ in values}) != len(values)
            ):
                raise B0477VirtualAcceptanceError(
                    f"{name} must be a non-empty canonical tuple"
                )
            for key, digest in values:
                _bounded_text(key, f"{name} key")
                _digest(digest, f"{name}[{key}]")
            object.__setattr__(self, name, values)
        components = dict(self.component_hashes)
        expected_components = {
            "camera_profile_canonical": self.profile_canonical_sha256,
            "camera_profile_file": self.profile_source_file_sha256,
            "intrinsics_fixture_canonical": self.intrinsics_canonical_sha256,
            "intrinsics_fixture_file": self.intrinsics_source_file_sha256,
            "intrinsics_integrity": self.intrinsics_integrity_sha256,
            "normal_vision_report": self.normal_registration_report_sha256,
            "static_support_file": self.support_design_sha256,
            "tag_loss_vision_report": self.tag_loss_report_sha256,
        }
        if any(
            components.get(key) != value for key, value in expected_components.items()
        ):
            raise B0477VirtualAcceptanceError(
                "camera fields differ from B0477 stack component hashes"
            )
        optical_sources = dict(self.optical_source_hashes)
        expected_optical_sources = {
            "camera_profile_canonical": self.profile_canonical_sha256,
            "camera_profile_file": self.profile_source_file_sha256,
            "nominal_intrinsics": self.proxy_intrinsics_sha256,
            "support_design": self.support_design_sha256,
            "support_source:purchased_camera_profile": (
                self.support_profile_source_sha256
            ),
        }
        if any(
            optical_sources.get(key) != value
            for key, value in expected_optical_sources.items()
        ):
            raise B0477VirtualAcceptanceError(
                "camera fields differ from B0477 optical source hashes"
            )

    @property
    def support_pose_sha256(self) -> str:
        return _stable_hash(
            {
                "optical_frame": self.optical_frame,
                "camera_axis_xy_board_mm": list(self.camera_axis_xy_board_mm),
                "entrance_pupil_z_board_mm": self.entrance_pupil_z_board_mm,
                "camera_T_board_row_major": list(self.camera_T_board_row_major),
            }
        )

    def _without_hash(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "camera": {
                "profile_id": self.profile_id,
                "identity": "Arducam B0477 / Sony IMX283 / nominal included 16 mm C-mount lens",
                "mounting_architecture": "STATIC_OVERHEAD_EYE_TO_HAND",
                "profile_canonical_sha256": self.profile_canonical_sha256,
                "profile_source_file_sha256": self.profile_source_file_sha256,
                "native_mode": {
                    "width_px": self.native_mode[0],
                    "height_px": self.native_mode[1],
                    "fps": self.native_mode[2],
                    "pixel_format": self.native_mode[3],
                },
                "published_fov_deg": {
                    "horizontal": self.published_fov_deg[0],
                    "vertical": self.published_fov_deg[1],
                    "diagonal": self.published_fov_deg[2],
                    "measured": False,
                },
            },
            "static_support": {
                "design_id": self.support_design_id,
                "design_sha256": self.support_design_sha256,
                "profile_source_sha256": self.support_profile_source_sha256,
                "optical_frame": self.optical_frame,
                "camera_axis_xy_board_mm": list(self.camera_axis_xy_board_mm),
                "entrance_pupil_z_board_mm": self.entrance_pupil_z_board_mm,
                "camera_T_board_row_major": list(self.camera_T_board_row_major),
                "pose_sha256": self.support_pose_sha256,
                "physical_pose_measured": False,
            },
            "intrinsics_rehearsal": {
                "artifact_id": self.intrinsics_artifact_id,
                "source_file_sha256": self.intrinsics_source_file_sha256,
                "canonical_sha256": self.intrinsics_canonical_sha256,
                "integrity_sha256": self.intrinsics_integrity_sha256,
                "profile_source_sha256": self.intrinsics_profile_source_sha256,
                "solution_sha256": self.intrinsics_solution_sha256,
                "input_bindings_sha256": self.intrinsics_input_bindings_sha256,
                "undistortion_map_sha256": self.intrinsics_undistortion_map_sha256,
                "application_to_proxy_pixels": False,
                "role": "HASH_BOUND_SYNTHETIC_REHEARSAL_NOT_PHYSICAL_CALIBRATION",
            },
            "static_registration": {
                "sequence": self.registration_sequence,
                "normal_report_sha256": self.normal_registration_report_sha256,
                "normal_jpeg_sha256": self.normal_registration_jpeg_sha256,
                "tag_loss_report_sha256": self.tag_loss_report_sha256,
                "tag_loss_jpeg_sha256": self.tag_loss_jpeg_sha256,
                "proxy_resolution_px": list(self.proxy_resolution_px),
                "proxy_intrinsics_sha256": self.proxy_intrinsics_sha256,
                "proxy_projection_source": "PUBLISHED_FOV_DERIVED_NOT_INTRINSICS_REHEARSAL_MATRIX",
                "stack_coherence_sha256": self.stack_coherence_sha256,
            },
            "component_hashes": dict(self.component_hashes),
            "optical_source_hashes": dict(self.optical_source_hashes),
            "implementation_sha256": self.implementation_sha256,
            "authority": _zero_authority(),
        }

    @property
    def content_sha256(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, object]:
        return {**self._without_hash(), "content_sha256": self.content_sha256}


@dataclass(frozen=True, slots=True)
class B0477MissionObservationBinding:
    """Post-process association from one mission occurrence to B0477 context."""

    device: str
    action_index: int
    target_id: str
    waypoint_sequence: int
    occurrence_attempt_sha256: str
    occurrence_result_sha256: str
    profile_id: str
    camera_evidence_sha256: str
    support_pose_sha256: str
    intrinsics_artifact_sha256: str
    registration_report_sha256: str
    registration_jpeg_sha256: str
    schema: str = B0477_MISSION_OBSERVATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != B0477_MISSION_OBSERVATION_SCHEMA:
            raise B0477VirtualAcceptanceError("unsupported observation-binding schema")
        if self.device not in {Device.KEYBOARD.value, Device.PHONE.value}:
            raise B0477VirtualAcceptanceError("observation device is invalid")
        _count(self.action_index, "action_index", maximum=10_000)
        _count(self.waypoint_sequence, "waypoint_sequence", maximum=1_000_000_000)
        _bounded_text(self.target_id, "target_id")
        if self.profile_id != _EXPECTED_PROFILE_ID:
            raise B0477VirtualAcceptanceError(
                "observation is not bound to the purchased B0477 profile"
            )
        for name in (
            "occurrence_attempt_sha256",
            "occurrence_result_sha256",
            "camera_evidence_sha256",
            "support_pose_sha256",
            "intrinsics_artifact_sha256",
            "registration_report_sha256",
            "registration_jpeg_sha256",
        ):
            _digest(getattr(self, name), name)

    def _without_hash(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "device": self.device,
            "action_index": self.action_index,
            "target_id": self.target_id,
            "waypoint_sequence": self.waypoint_sequence,
            "mission_occurrence": {
                "attempt_sha256": self.occurrence_attempt_sha256,
                "result_sha256": self.occurrence_result_sha256,
            },
            "b0477_camera_context": {
                "profile_id": self.profile_id,
                "camera_evidence_sha256": self.camera_evidence_sha256,
                "support_pose_sha256": self.support_pose_sha256,
                "intrinsics_artifact_sha256": self.intrinsics_artifact_sha256,
                "registration_report_sha256": self.registration_report_sha256,
                "registration_jpeg_sha256": self.registration_jpeg_sha256,
            },
            "association": {
                "timing": "AFTER_MISSION_OBSERVATION_OCCURRENCE_VALIDATION",
                "acceptance_preflight_registration_context_reused": True,
                "new_b0477_frame_per_action_claim": False,
                "physical_observation_claim": False,
            },
            "authority": _zero_authority(),
        }

    @property
    def binding_sha256(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, object]:
        return {**self._without_hash(), "binding_sha256": self.binding_sha256}


@dataclass(frozen=True, slots=True)
class B0477VirtualMissionAcceptance:
    """Compact acceptance result for one virtual keyboard or phone mission."""

    device: str
    session_report_sha256: str
    plan_sha256: str
    requested_text_sha256: str
    requested_text_length: int
    semantic_action_count: int
    physical_target_count: int
    final_waypoint_count: int
    virtual_command_count: int
    event_count: int
    attempted_contact_count: int
    accepted_contact_count: int
    observation_bindings: tuple[B0477MissionObservationBinding, ...]
    camera_evidence_sha256: str
    pipeline_completed: bool
    outcome_verified: bool
    ended_at_park: bool
    arm_closed: bool
    schema: str = B0477_VIRTUAL_MISSION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != B0477_VIRTUAL_MISSION_SCHEMA:
            raise B0477VirtualAcceptanceError("unsupported virtual-mission schema")
        if self.device not in {Device.KEYBOARD.value, Device.PHONE.value}:
            raise B0477VirtualAcceptanceError("virtual mission device is invalid")
        for name in (
            "session_report_sha256",
            "plan_sha256",
            "requested_text_sha256",
            "camera_evidence_sha256",
        ):
            _digest(getattr(self, name), name)
        for name in (
            "requested_text_length",
            "semantic_action_count",
            "physical_target_count",
            "final_waypoint_count",
            "virtual_command_count",
            "event_count",
            "attempted_contact_count",
            "accepted_contact_count",
        ):
            _count(getattr(self, name), name)
        bindings = tuple(self.observation_bindings)
        if any(
            not isinstance(item, B0477MissionObservationBinding) for item in bindings
        ):
            raise TypeError(
                "observation_bindings must contain B0477MissionObservationBinding values"
            )
        if any(
            item.device != self.device
            or item.camera_evidence_sha256 != self.camera_evidence_sha256
            for item in bindings
        ):
            raise B0477VirtualAcceptanceError(
                "mission observation bindings differ from the mission camera context"
            )
        if tuple(item.action_index for item in bindings) != tuple(
            sorted(item.action_index for item in bindings)
        ) or len({item.action_index for item in bindings}) != len(bindings):
            raise B0477VirtualAcceptanceError(
                "mission observation action indices must be ordered and unique"
            )
        object.__setattr__(self, "observation_bindings", bindings)
        for name in (
            "pipeline_completed",
            "outcome_verified",
            "ended_at_park",
            "arm_closed",
        ):
            if not isinstance(getattr(self, name), bool):
                raise B0477VirtualAcceptanceError(f"{name} must be boolean")
        if self.physical_target_count != len(bindings):
            raise B0477VirtualAcceptanceError(
                "physical target count differs from observation-binding count"
            )
        if self.virtual_command_count != self.final_waypoint_count:
            raise B0477VirtualAcceptanceError(
                "virtual command count differs from final waypoint count"
            )
        if self.pipeline_completed and not (
            self.physical_target_count > 0
            and self.requested_text_length == self.physical_target_count
            and (
                (
                    self.device == Device.KEYBOARD.value
                    and self.semantic_action_count == self.physical_target_count
                    and tuple(item.action_index for item in bindings)
                    == tuple(range(self.semantic_action_count))
                )
                or (
                    self.device == Device.PHONE.value
                    and self.semantic_action_count > self.physical_target_count
                    and bindings[0].action_index >= 1
                    and bindings[-1].action_index < self.semantic_action_count
                )
            )
            and self.final_waypoint_count > 0
            and self.event_count > self.virtual_command_count
            and self.attempted_contact_count
            == self.accepted_contact_count
            == self.physical_target_count
            and self.outcome_verified
            and self.ended_at_park
            and self.arm_closed
        ):
            raise B0477VirtualAcceptanceError(
                "completed mission counts or terminal state are incoherent"
            )
        if self.pipeline_completed and (
            tuple(item.waypoint_sequence for item in bindings)
            != tuple(sorted(item.waypoint_sequence for item in bindings))
            or len({item.waypoint_sequence for item in bindings}) != len(bindings)
            or len({item.occurrence_attempt_sha256 for item in bindings})
            != len(bindings)
            or len({item.occurrence_result_sha256 for item in bindings})
            != len(bindings)
        ):
            raise B0477VirtualAcceptanceError(
                "completed mission observation sequences and hashes must be unique"
            )

    @property
    def passed(self) -> bool:
        return (
            self.pipeline_completed
            and self.outcome_verified
            and self.ended_at_park
            and self.arm_closed
            and self.physical_target_count > 0
            and len(self.observation_bindings) == self.physical_target_count
            and self.attempted_contact_count
            == self.accepted_contact_count
            == self.physical_target_count
            and all(
                binding.camera_evidence_sha256 == self.camera_evidence_sha256
                for binding in self.observation_bindings
            )
        )

    def _without_hash(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "device": self.device,
            "passed": self.passed,
            "session_report_sha256": self.session_report_sha256,
            "plan_sha256": self.plan_sha256,
            "requested_text": {
                "sha256": self.requested_text_sha256,
                "normalized_codepoint_length": self.requested_text_length,
                "plaintext_serialized": False,
            },
            "counts": {
                "semantic_actions": self.semantic_action_count,
                "physical_targets": self.physical_target_count,
                "final_waypoints": self.final_waypoint_count,
                "virtual_commands": self.virtual_command_count,
                "events": self.event_count,
                "attempted_contacts": self.attempted_contact_count,
                "accepted_contacts": self.accepted_contact_count,
                "b0477_bound_observations": len(self.observation_bindings),
            },
            "terminal_state": {
                "pipeline_completed": self.pipeline_completed,
                "outcome_verified": self.outcome_verified,
                "ended_at_park": self.ended_at_park,
                "arm_closed": self.arm_closed,
            },
            "camera_evidence_sha256": self.camera_evidence_sha256,
            "observations": [item.to_dict() for item in self.observation_bindings],
            "authority": _zero_authority(),
        }

    @property
    def content_sha256(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, object]:
        return {**self._without_hash(), "content_sha256": self.content_sha256}


@dataclass(frozen=True, slots=True)
class B0477VirtualAcceptanceReport:
    """Immutable result for the two representative B0477-bound missions."""

    camera: B0477CameraEvidenceBinding
    stack: B0477StackCoherenceReport
    keyboard: B0477VirtualMissionAcceptance
    phone: B0477VirtualMissionAcceptance
    b0477_registration_report_count: int = 2
    schema: str = B0477_VIRTUAL_ACCEPTANCE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != B0477_VIRTUAL_ACCEPTANCE_SCHEMA:
            raise B0477VirtualAcceptanceError("unsupported acceptance schema")
        if not isinstance(self.camera, B0477CameraEvidenceBinding):
            raise TypeError("camera must be B0477CameraEvidenceBinding")
        if not isinstance(self.stack, B0477StackCoherenceReport):
            raise TypeError("stack must be B0477StackCoherenceReport")
        if not isinstance(self.keyboard, B0477VirtualMissionAcceptance):
            raise TypeError("keyboard must be B0477VirtualMissionAcceptance")
        if not isinstance(self.phone, B0477VirtualMissionAcceptance):
            raise TypeError("phone must be B0477VirtualMissionAcceptance")
        if self.keyboard.device != Device.KEYBOARD.value:
            raise B0477VirtualAcceptanceError("keyboard mission has wrong device")
        if self.phone.device != Device.PHONE.value:
            raise B0477VirtualAcceptanceError("phone mission has wrong device")
        if any(
            mission.camera_evidence_sha256 != self.camera.content_sha256
            for mission in (self.keyboard, self.phone)
        ):
            raise B0477VirtualAcceptanceError(
                "mission camera evidence differs from the acceptance camera"
            )
        for mission in (self.keyboard, self.phone):
            for binding in mission.observation_bindings:
                if not (
                    binding.profile_id == self.camera.profile_id
                    and binding.support_pose_sha256 == self.camera.support_pose_sha256
                    and binding.intrinsics_artifact_sha256
                    == self.camera.intrinsics_canonical_sha256
                    and binding.registration_report_sha256
                    == self.camera.normal_registration_report_sha256
                    and binding.registration_jpeg_sha256
                    == self.camera.normal_registration_jpeg_sha256
                ):
                    raise B0477VirtualAcceptanceError(
                        "mission observation differs from the accepted B0477 context"
                    )
        if self.camera.stack_coherence_sha256 != self.stack.canonical_sha256:
            raise B0477VirtualAcceptanceError(
                "camera binding differs from the stack coherence report"
            )
        if not (
            self.camera.profile_id == self.stack.profile_id
            and self.camera.support_design_id == self.stack.support_design_id
            and self.camera.component_hashes == self.stack.component_hashes
        ):
            raise B0477VirtualAcceptanceError(
                "camera binding fields differ from the accepted B0477 stack"
            )
        report_count = _count(
            self.b0477_registration_report_count,
            "b0477_registration_report_count",
            maximum=2,
        )
        if report_count != 2:
            raise B0477VirtualAcceptanceError(
                "acceptance requires one normal and one tag-loss B0477 report"
            )
        if not (
            self.stack.vision_evidence_state == "PRECOMPUTED_PAIR_SUPPLIED"
            and self.stack.vision_reports_consumed == report_count
        ):
            raise B0477VirtualAcceptanceError(
                "B0477 stack does not contain the required registration pair"
            )

    @property
    def observation_count(self) -> int:
        return len(self.keyboard.observation_bindings) + len(
            self.phone.observation_bindings
        )

    @property
    def final_waypoint_count(self) -> int:
        return self.keyboard.final_waypoint_count + self.phone.final_waypoint_count

    @property
    def virtual_contact_count(self) -> int:
        return self.keyboard.accepted_contact_count + self.phone.accepted_contact_count

    @property
    def zero_physical_authority(self) -> bool:
        return (
            self.stack.simulation_only
            and not self.stack.hardware_accessed
            and self.stack.camera_frames_requested == 0
            and self.stack.arm_motion_commands == 0
            and self.stack.contact_commands == 0
            and not self.stack.live_capture_authority
            and not self.stack.physical_calibration_authority
            and not self.stack.physical_static_extrinsic_authority
            and not self.stack.robot_motion_authority
            and not self.stack.contact_authority
        )

    @property
    def passed(self) -> bool:
        return (
            self.stack.passed
            and self.keyboard.passed
            and self.phone.passed
            and self.observation_count > 0
            and self.zero_physical_authority
        )

    @property
    def status(self) -> str:
        return (
            "B0477_BOUND_VIRTUAL_ACCEPTANCE_PASSED_WITH_PHYSICAL_HOLDS"
            if self.passed
            else "B0477_BOUND_VIRTUAL_ACCEPTANCE_BLOCKED"
        )

    def _without_hash(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "status": self.status,
            "passed": self.passed,
            "camera": self.camera.to_dict(),
            "stack": {
                "status": self.stack.status,
                "passed": self.stack.passed,
                "canonical_sha256": self.stack.canonical_sha256,
                "vision_reports_consumed": self.stack.vision_reports_consumed,
            },
            "missions": [self.keyboard.to_dict(), self.phone.to_dict()],
            "aggregate_counts": {
                "missions": 2,
                "b0477_registration_reports_consumed": (
                    self.b0477_registration_report_count
                ),
                "b0477_bound_observations": self.observation_count,
                "final_waypoints": self.final_waypoint_count,
                "virtual_contacts": self.virtual_contact_count,
                "physical_camera_frames": 0,
                "physical_arm_commands": 0,
                "physical_contacts": 0,
            },
            "evidence_scope": {
                "b0477_registration_is_acceptance_preflight": True,
                "b0477_frame_reused_across_both_missions_and_action_bindings": True,
                "per_action_b0477_pixels_rendered": False,
                "historical_session_camera_identity_accepted_as_b0477": False,
                "intrinsics_rehearsal_applied_as_physical_calibration": False,
                "registration_report_trust_scope": (
                    "DIRECT_IN_PROCESS_TYPED_VALUE_NOT_EXTERNAL_AUTHENTICATION"
                ),
                "virtual_model_complete": False,
            },
            "physical_holds": [
                "PURCHASED_CAMERA_RECEIPT_AND_USB_IDENTITY_NOT_VERIFIED",
                "B0477_INTRINSICS_AND_STATIC_EXTRINSIC_NOT_PHYSICALLY_COMMISSIONED",
                "SUPPORT_POSE_STIFFNESS_CLEARANCE_AND_VISIBILITY_NOT_MEASURED",
                "PER_TARGET_B0477_PIXEL_OBSERVATIONS_NOT_REHEARSED",
                "ROBOT_COLLISION_FORCE_AND_CONTACT_ACCEPTANCE_INCOMPLETE",
            ],
            "authority": _zero_authority(),
        }

    @property
    def report_hash(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, object]:
        return {**self._without_hash(), "report_hash": self.report_hash}


def _intrinsics_solution_hash(artifact: StaticCameraIntrinsicsRehearsal) -> str:
    return _stable_hash(
        {
            "distortion_model": artifact.distortion_model,
            "distortion_coefficients": list(artifact.distortion_coefficients),
            "camera_matrix_row_major": list(artifact.camera_matrix_row_major),
            "valid_pixel_roi": list(artifact.valid_pixel_roi),
            "output_crop": list(artifact.output_crop),
            "undistortion_map_sha256": artifact.undistortion_map_sha256,
        }
    )


def _expected_tag_map(
    scene: NominalWorkcellScene,
    *,
    tag_ids: tuple[int, ...],
    map_id: str,
) -> PlanarBoardTagMap:
    """Reconstruct a B0477 tag-map identity from current RC03 source files."""

    by_id = {tag.tag_id: tag for tag in scene.fiducials}
    if set(by_id) != set(range(6)):
        raise B0477VirtualAcceptanceError(
            "current RC03 scene does not contain exact tag IDs 0 through 5"
        )
    return PlanarBoardTagMap(
        map_id=map_id,
        board_frame=scene.board_frame,
        tag_plane_z_board_mm=scene.fiducials[0].center.z,
        tags=tuple(
            PlanarBoardTag(
                tag=TagReference(by_id[tag_id].family, tag_id),
                corners_board_mm=by_id[tag_id].corners(),
            )
            for tag_id in tag_ids
        ),
        source_sha256=scene.source_hashes["fiducials/apriltag_map.json"],
    )


def _build_camera_binding(
    profile: PurchasedCameraProfile,
    support: StaticCameraSupportDesign,
    intrinsics: StaticCameraIntrinsicsRehearsal,
    stack: B0477StackCoherenceReport,
    normal: B0477StaticVisionReport,
    tag_loss: B0477StaticVisionReport,
    scene: NominalWorkcellScene,
) -> B0477CameraEvidenceBinding:
    if not stack.passed:
        failed = ", ".join(check.check_id for check in stack.checks if not check.passed)
        raise B0477VirtualAcceptanceError(
            f"B0477 stack coherence is blocked: {failed or 'unknown check'}"
        )
    if normal.mode is not B0477StaticVisionMode.NORMAL or normal.status != "PASS":
        raise B0477VirtualAcceptanceError("normal B0477 registration did not pass")
    if (
        tag_loss.mode is not B0477StaticVisionMode.TAG_LOSS
        or tag_loss.status != "REJECTED"
        or tag_loss.detail_code != "B0477_STATIC_TAG_LOSS_NATURALLY_REJECTED"
    ):
        raise B0477VirtualAcceptanceError(
            "B0477 tag-loss evidence did not fail closed as expected"
        )
    projection = normal.nominal_projection
    if projection.camera_axis_xy_board_mm != support.camera_axis_xy_mm:
        raise B0477VirtualAcceptanceError("B0477 projection and support axis differ")
    if projection.entrance_pupil_z_board_mm != support.nominal_entrance_pupil_z_mm:
        raise B0477VirtualAcceptanceError("B0477 projection and support height differ")
    expected_camera_T_board = (
        1.0,
        0.0,
        0.0,
        -support.camera_axis_xy_mm[0],
        0.0,
        -1.0,
        0.0,
        support.camera_axis_xy_mm[1],
        0.0,
        0.0,
        -1.0,
        support.nominal_entrance_pupil_z_mm,
        0.0,
        0.0,
        0.0,
        1.0,
    )
    if projection.camera_T_board_row_major != expected_camera_T_board:
        raise B0477VirtualAcceptanceError(
            "B0477 camera_T_board differs from the static support pose"
        )
    if tag_loss.nominal_projection != projection:
        raise B0477VirtualAcceptanceError(
            "normal and tag-loss B0477 projections differ"
        )
    if tag_loss.pixel_statistics.jpeg_sha256 == normal.pixel_statistics.jpeg_sha256:
        raise B0477VirtualAcceptanceError(
            "normal and tag-loss B0477 evidence reused identical JPEG bytes"
        )
    normal_sources = dict(normal.source_hashes)
    tag_loss_sources = dict(tag_loss.source_hashes)
    if frozenset(normal_sources) != (
        _SHARED_B0477_SOURCE_KEYS | _NORMAL_ONLY_B0477_SOURCE_KEYS
    ) or frozenset(tag_loss_sources) != (
        _SHARED_B0477_SOURCE_KEYS | _TAG_LOSS_ONLY_B0477_SOURCE_KEYS
    ):
        raise B0477VirtualAcceptanceError(
            "B0477 report source-hash fields differ from the exact contract"
        )
    if any(
        normal_sources[key] != tag_loss_sources[key]
        for key in _SHARED_B0477_SOURCE_KEYS
    ):
        raise B0477VirtualAcceptanceError(
            "normal and tag-loss B0477 shared source hashes differ"
        )
    expected_support_sources = {
        f"support_source:{key}": value for key, value in support.source_sha256.items()
    }
    expected_scene_sources = {
        f"scene_source:{key}": value for key, value in scene.source_hashes.items()
    }
    if any(
        normal_sources.get(key) != value
        for key, value in {
            **expected_support_sources,
            **expected_scene_sources,
        }.items()
    ):
        raise B0477VirtualAcceptanceError(
            "B0477 report support or scene source hashes differ from current files"
        )

    # Reconstruct all inexpensive optical identities instead of trusting a
    # caller-supplied report's labels.  Pixel-derived batch/pose digests remain
    # content commitments made by the immutable report itself.
    proxy = profile.simulation_proxy
    try:
        expected_optical_contract = build_b0477_synthetic_optical_contract(
            profile, support
        )
    except B0477OpticalContractError as exc:
        raise B0477VirtualAcceptanceError(
            f"canonical B0477 optical contract is invalid: {exc}"
        ) from exc
    if not (
        projection.resolution_px == (proxy.width_px, proxy.height_px)
        and projection.optical_contract == expected_optical_contract
        and projection.optical_contract_sha256
        == expected_optical_contract.content_sha256
        and projection.undistortion_map_sha256
        == expected_optical_contract.undistortion_map_sha256
        and projection.published_fov_deg
        == (proxy.horizontal_fov_deg, proxy.vertical_fov_deg)
    ):
        raise B0477VirtualAcceptanceError(
            "B0477 projection differs from the canonical optical contract"
        )
    expected_proxy_intrinsics = expected_optical_contract.estimator_intrinsics()
    expected_detector = AprilTag36h11PixelDetector(
        AprilTagPixelDetectorConfiguration(
            host_clock="b0477_static_synthetic_host_monotonic",
            maximum_image_pixels=proxy.pixel_detector_maximum_image_pixels,
        ),
        DEFAULT_APRILTAG_36H11_CODEBOOK,
    )
    expected_rectifier = expected_optical_contract.rectifier_identity(
        expected_detector.detector_identity
    )
    if not (
        normal_sources["nominal_intrinsics"] == expected_proxy_intrinsics.content_hash
        and normal_sources["optical_contract"]
        == expected_optical_contract.content_sha256
        and normal_sources["synthetic_undistortion_map"]
        == expected_optical_contract.undistortion_map_sha256
        and normal_sources["detector_configuration"]
        == expected_detector.detector_identity.configuration_sha256
        and normal_sources["detector_implementation"]
        == expected_detector.detector_identity.implementation_sha256
        and normal_sources["rectifier_configuration"]
        == expected_rectifier.configuration_sha256
        and normal_sources["rectifier_implementation"]
        == expected_rectifier.implementation_sha256
    ):
        raise B0477VirtualAcceptanceError(
            "B0477 report optical processor hashes do not reconstruct"
        )
    fit_tag_map = _expected_tag_map(
        scene,
        tag_ids=(0, 1, 2, 3),
        map_id="rc03.nominal_t0_t3_fit.for_b0477_static_rehearsal",
    )
    held_out_tag_map = _expected_tag_map(
        scene,
        tag_ids=(4, 5),
        map_id="rc03.nominal_k0_p0_held_out.for_b0477_static_rehearsal",
    )
    if not (
        normal_sources["nominal_fit_tag_map"] == fit_tag_map.content_hash
        and normal_sources["nominal_tag_map"] == fit_tag_map.content_hash
        and normal_sources["nominal_held_out_station_map"]
        == held_out_tag_map.content_hash
    ):
        raise B0477VirtualAcceptanceError(
            "B0477 report tag-map hashes do not reconstruct from current RC03"
        )
    normal_renderer_config = SyntheticRasterConfig(
        renderer_id="RC03_B0477_STATIC_OVERHEAD_PROXY_V1",
        noise_amplitude_gray=1,
    )
    tag_loss_renderer_config = SyntheticRasterConfig(
        renderer_id="RC03_B0477_STATIC_OVERHEAD_PROXY_V1",
        occluded_tag_ids=(0, 1, 2, 3),
        noise_amplitude_gray=1,
    )
    if not (
        normal_sources["renderer_config"] == normal_renderer_config.config_sha256
        and tag_loss_sources["renderer_config"]
        == tag_loss_renderer_config.config_sha256
    ):
        raise B0477VirtualAcceptanceError(
            "B0477 report renderer configuration hashes do not reconstruct"
        )
    assessment = assess_static_camera_intrinsics_rehearsal(
        intrinsics, purchased_profile=profile
    )
    if not assessment.structural_gates_passed:
        raise B0477VirtualAcceptanceError(
            "synthetic static-intrinsics rehearsal is structurally blocked"
        )
    optical_sources = tuple(normal.source_hashes)
    try:
        proxy_intrinsics_hash = dict(optical_sources)["nominal_intrinsics"]
        support_profile_hash = support.source_sha256["purchased_camera_profile"]
    except KeyError as exc:
        raise B0477VirtualAcceptanceError(
            f"required B0477 source hash is absent: {exc.args[0]}"
        ) from exc
    return B0477CameraEvidenceBinding(
        profile_id=profile.profile_id,
        profile_canonical_sha256=profile.canonical_sha256,
        profile_source_file_sha256=profile.source_file_sha256,
        support_design_id=support.design_id,
        support_design_sha256=support.content_sha256,
        support_profile_source_sha256=support_profile_hash,
        optical_frame=projection.optical_frame,
        camera_axis_xy_board_mm=projection.camera_axis_xy_board_mm,
        entrance_pupil_z_board_mm=projection.entrance_pupil_z_board_mm,
        camera_T_board_row_major=projection.camera_T_board_row_major,
        native_mode=support.native_mode,
        published_fov_deg=support.field_of_view_deg,
        proxy_resolution_px=projection.resolution_px,
        proxy_intrinsics_sha256=proxy_intrinsics_hash,
        intrinsics_artifact_id=intrinsics.artifact_id,
        intrinsics_source_file_sha256=intrinsics.source_file_sha256,
        intrinsics_canonical_sha256=intrinsics.canonical_sha256,
        intrinsics_integrity_sha256=intrinsics.integrity_sha256,
        intrinsics_profile_source_sha256=intrinsics.profile_source_file_sha256,
        intrinsics_solution_sha256=_intrinsics_solution_hash(intrinsics),
        intrinsics_input_bindings_sha256=intrinsics.input_bindings_sha256,
        intrinsics_undistortion_map_sha256=intrinsics.undistortion_map_sha256,
        normal_registration_report_sha256=normal.content_sha256,
        normal_registration_jpeg_sha256=normal.pixel_statistics.jpeg_sha256,
        tag_loss_report_sha256=tag_loss.content_sha256,
        tag_loss_jpeg_sha256=tag_loss.pixel_statistics.jpeg_sha256,
        stack_coherence_sha256=stack.canonical_sha256,
        component_hashes=stack.component_hashes,
        optical_source_hashes=optical_sources,
        implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        registration_sequence=normal.sequence,
    )


def _device_count(document: Any, key: str) -> int:
    if not isinstance(document, dict):
        # VirtualSessionReport currently stores a plain dict, but retain a
        # narrow compatibility path for immutable Mapping implementations.
        try:
            value = document[key]
        except (KeyError, TypeError) as exc:
            raise B0477VirtualAcceptanceError(
                f"virtual device evidence lacks {key}"
            ) from exc
    else:
        value = document.get(key)
    return _count(value, f"virtual device {key}")


def _build_mission(
    report: VirtualSessionReport,
    camera: B0477CameraEvidenceBinding,
) -> B0477VirtualMissionAcceptance:
    if not isinstance(report, VirtualSessionReport):
        raise TypeError("report must be VirtualSessionReport")
    session_authority = report.to_dict().get("authority")
    if not isinstance(session_authority, dict) or not (
        session_authority.get("simulation_only") is True
        and session_authority.get("execution_authorized") is False
        and session_authority.get("hardware_accessed") is False
        and session_authority.get("hardware_commands_generated") == 0
        and session_authority.get("physical_release_effect") == "NONE"
        and session_authority.get("can_release_physical_gates") is False
    ):
        raise B0477VirtualAcceptanceError(
            "virtual mission no longer proves zero physical authority"
        )
    vision: VirtualPixelVisionAttemptLedger = (
        virtual_pixel_vision_attempt_ledger_from_dict(report.vision_document)
    )
    expected_physical_action_indices = tuple(
        index
        for index, action in enumerate(report.plan.actions)
        if isinstance(action, (PressKey, TapPhoneTarget))
    )
    observed_physical_action_indices = tuple(
        attempt.action_index for attempt in vision.attempts
    )
    if observed_physical_action_indices != expected_physical_action_indices:
        raise B0477VirtualAcceptanceError(
            "mission observations do not cover the plan's exact physical actions"
        )
    final = report.trajectory.final_round
    if final is None:
        raise B0477VirtualAcceptanceError("virtual mission has no final trajectory")
    device = report.plan.device.value
    bindings = tuple(
        B0477MissionObservationBinding(
            device=device,
            action_index=attempt.action_index,
            target_id=attempt.target_id,
            waypoint_sequence=attempt.waypoint_sequence,
            occurrence_attempt_sha256=attempt.attempt_hash,
            occurrence_result_sha256=attempt.result.result_hash,
            profile_id=camera.profile_id,
            camera_evidence_sha256=camera.content_sha256,
            support_pose_sha256=camera.support_pose_sha256,
            intrinsics_artifact_sha256=camera.intrinsics_canonical_sha256,
            registration_report_sha256=(camera.normal_registration_report_sha256),
            registration_jpeg_sha256=camera.normal_registration_jpeg_sha256,
        )
        for attempt in vision.attempts
    )
    return B0477VirtualMissionAcceptance(
        device=device,
        session_report_sha256=report.report_hash,
        plan_sha256=report.plan.plan_hash,
        requested_text_sha256=report.plan.requested_text_sha256,
        requested_text_length=report.requested_text_length,
        semantic_action_count=len(report.plan.actions),
        physical_target_count=len(vision.attempts),
        final_waypoint_count=len(final.waypoints),
        virtual_command_count=report.ledger.virtual_commands_executed,
        event_count=len(report.ledger.events),
        attempted_contact_count=_device_count(
            report.device_document, "attempted_contact_count"
        ),
        accepted_contact_count=_device_count(
            report.device_document, "accepted_contact_count"
        ),
        observation_bindings=bindings,
        camera_evidence_sha256=camera.content_sha256,
        pipeline_completed=report.pipeline_completed,
        outcome_verified=report.outcome_verified,
        ended_at_park=report.ended_at_park,
        arm_closed=report.arm_document.get("lifecycle") == "CLOSED",
    )


def run_b0477_bound_virtual_acceptance(
    workspace_root: Path | str,
    *,
    keyboard_text: str = "test",
    phone_text: str = "test.",
    registration_sequence: int = 0,
    normal_vision_report: B0477StaticVisionReport | None = None,
    tag_loss_vision_report: B0477StaticVisionReport | None = None,
) -> B0477VirtualAcceptanceReport:
    """Run two representative missions under a validated B0477 context.

    A caller that already ran the B0477 normal/tag-loss pair may supply both
    direct in-process typed results to avoid re-rendering.  These arguments are
    a same-process cache optimization, not an authentication mechanism for
    deserialized or externally supplied evidence.  The adapter reconstructs
    stable optical/source identities, but pixel-derived hashes are commitments
    carried by the typed reports.  Supplying only one report, a report at a
    different sequence, or a pair that fails full stack coherence is rejected.
    The function has no hardware provider and the returned authority is always
    zero regardless of success.
    """

    root = Path(workspace_root).resolve()
    if not root.is_dir():
        raise B0477VirtualAcceptanceError(
            "workspace_root must be an existing directory"
        )
    if not isinstance(keyboard_text, str) or not isinstance(phone_text, str):
        raise TypeError("keyboard_text and phone_text must be str")
    if not 0 < len(keyboard_text) <= _MAX_TEXT_LENGTH:
        raise B0477VirtualAcceptanceError("keyboard_text must be non-empty and bounded")
    if not 0 < len(phone_text) <= _MAX_TEXT_LENGTH:
        raise B0477VirtualAcceptanceError("phone_text must be non-empty and bounded")
    _count(registration_sequence, "registration_sequence", maximum=1_000_000_000)
    if (normal_vision_report is None) != (tag_loss_vision_report is None):
        raise B0477VirtualAcceptanceError(
            "normal and tag-loss B0477 reports must be supplied together"
        )
    if normal_vision_report is None:
        normal = run_b0477_static_vision_rehearsal(
            root,
            sequence=registration_sequence,
            mode=B0477StaticVisionMode.NORMAL,
        )
        tag_loss = run_b0477_static_vision_rehearsal(
            root,
            sequence=registration_sequence,
            mode=B0477StaticVisionMode.TAG_LOSS,
        )
    else:
        if not isinstance(
            normal_vision_report, B0477StaticVisionReport
        ) or not isinstance(tag_loss_vision_report, B0477StaticVisionReport):
            raise TypeError(
                "normal_vision_report and tag_loss_vision_report must be B0477 reports"
            )
        normal = normal_vision_report
        tag_loss = tag_loss_vision_report
    if (
        normal.sequence != registration_sequence
        or tag_loss.sequence != registration_sequence
    ):
        raise B0477VirtualAcceptanceError(
            "B0477 report sequences differ from registration_sequence"
        )

    profile_path = _contained_file(root, DEFAULT_B0477_PROFILE_PATH, "camera profile")
    support_path = _contained_file(root, DEFAULT_B0477_SUPPORT_PATH, "support design")
    intrinsics_path = _contained_file(
        root, DEFAULT_B0477_INTRINSICS_FIXTURE_PATH, "intrinsics rehearsal"
    )
    profile = load_camera_profile(profile_path)
    support = load_static_camera_support_design(root, support_path)
    intrinsics = load_static_camera_intrinsics_rehearsal(
        intrinsics_path, fixture_root=root
    )
    scene_root = (root / "active-project" / "RoCell_v0_3").resolve()
    try:
        scene_root.relative_to(root)
    except ValueError as exc:  # pragma: no cover - all segments are literals
        raise B0477VirtualAcceptanceError("RC03 scene root escapes workspace") from exc
    scene = load_rc03_nominal_scene(scene_root)
    stack = load_and_assess_b0477_stack_coherence(
        root,
        normal_vision_report=normal,
        tag_loss_vision_report=tag_loss,
    )
    camera = _build_camera_binding(
        profile, support, intrinsics, stack, normal, tag_loss, scene
    )

    # The mission sessions execute only in-memory virtual plants.  The camera
    # adapter is applied afterward so the historical simulator cannot silently
    # masquerade as the selected physical camera.
    keyboard_report = run_default_virtual_session(root, "keyboard", keyboard_text)
    phone_report = run_default_virtual_session(root, "phone", phone_text)
    keyboard = _build_mission(keyboard_report, camera)
    phone = _build_mission(phone_report, camera)
    return B0477VirtualAcceptanceReport(
        camera=camera,
        stack=stack,
        keyboard=keyboard,
        phone=phone,
    )


__all__ = [
    "B0477_CAMERA_EVIDENCE_SCHEMA",
    "B0477_MISSION_OBSERVATION_SCHEMA",
    "B0477_VIRTUAL_ACCEPTANCE_SCHEMA",
    "B0477_VIRTUAL_MISSION_SCHEMA",
    "B0477CameraEvidenceBinding",
    "B0477MissionObservationBinding",
    "B0477VirtualAcceptanceError",
    "B0477VirtualAcceptanceReport",
    "B0477VirtualMissionAcceptance",
    "run_b0477_bound_virtual_acceptance",
]
