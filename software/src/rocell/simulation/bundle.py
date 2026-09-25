"""Versioned hash lock for the complete software simulation bundle.

The system manifest freezes the controlled RC03 hardware-build sources.  This
companion lock covers the software-side scenario inputs that are intentionally
outside that RC03 snapshot.  Loading is read-only and can never affect a
physical release gate.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping

from ._validation import (
    SimulationSourceError,
    identifier,
    load_json_object,
    mapping,
    sha256_file,
    source_path,
)


SIMULATION_BUNDLE_SCHEMA = "rocell.simulation_bundle_lock.v1"
SIMULATION_BUNDLE_STATUS = "SIMULATION_ONLY_LOCKED_PHYSICAL_AUTHORITY_NONE"
DEFAULT_SIMULATION_BUNDLE_LOCK = "software/config/simulation_bundle_lock.json"

_EXPECTED_ARTIFACT_PATHS: Mapping[str, str] = MappingProxyType(
    {
        "simulation_hardware_profile": (
            "software/config/simulation_hardware_profile.json"
        ),
        "nominal_target_profiles": "software/config/nominal_target_profiles.json",
        "arm_frame_contract": "software/config/arm_frame_contract.json",
        "camera_manifest": "software/config/camera_manifest.json",
        "virtual_commissioning_profile": (
            "software/config/virtual_commissioning_profile.json"
        ),
        "local_roarm_urdf": (
            "software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf"
        ),
    }
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ARM_FRAME_SEMANTIC_KEYS = (
    "frames",
    "frame_separation",
    "camera_installation",
    "controller_model_correlation",
    "feedback_t1051",
    "motion_t104",
    "required_before_motion",
)
_ARM_FRAME_SEMANTICS_SHA256 = (
    "75081de17e33ae1d120772e7249b9d813bd9ea58aeedae79991a62bc499da741"
)


class SimulationBundleError(SimulationSourceError):
    """The simulation lock or one of its immutable artifacts is invalid."""


@dataclass(frozen=True, slots=True)
class SimulationBundleArtifact:
    """One workspace-contained artifact verified against its locked digest."""

    artifact_id: str
    relative_path: str
    path: Path
    sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "artifact_id",
            identifier(self.artifact_id, "simulation bundle artifact id"),
        )
        object.__setattr__(
            self,
            "relative_path",
            identifier(self.relative_path, "simulation bundle artifact path"),
        )
        digest = identifier(self.sha256, "simulation bundle artifact sha256").lower()
        if _SHA256_PATTERN.fullmatch(digest) is None:
            raise SimulationBundleError("Simulation bundle artifact SHA-256 is invalid")
        object.__setattr__(self, "sha256", digest)
        object.__setattr__(self, "path", Path(self.path).resolve())

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.relative_path,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class SimulationBundleLock:
    """Verified software-side simulation inputs with permanently zero authority."""

    bundle_id: str
    system_manifest_id: str
    design_revision: str
    source_lock_path: Path
    source_lock_sha256: str
    artifacts: Mapping[str, SimulationBundleArtifact]
    schema: str = SIMULATION_BUNDLE_SCHEMA
    status: str = SIMULATION_BUNDLE_STATUS

    def __post_init__(self) -> None:
        for field_name in ("bundle_id", "system_manifest_id", "design_revision"):
            object.__setattr__(
                self,
                field_name,
                identifier(getattr(self, field_name), field_name),
            )
        if self.schema != SIMULATION_BUNDLE_SCHEMA:
            raise SimulationBundleError("Simulation bundle schema changed after loading")
        if self.status != SIMULATION_BUNDLE_STATUS:
            raise SimulationBundleError("Simulation bundle status changed after loading")
        lock_digest = identifier(
            self.source_lock_sha256,
            "simulation bundle lock sha256",
        ).lower()
        if _SHA256_PATTERN.fullmatch(lock_digest) is None:
            raise SimulationBundleError("Simulation bundle lock SHA-256 is invalid")
        object.__setattr__(self, "source_lock_sha256", lock_digest)
        object.__setattr__(self, "source_lock_path", Path(self.source_lock_path).resolve())
        artifacts = dict(self.artifacts)
        if set(artifacts) != set(_EXPECTED_ARTIFACT_PATHS):
            raise SimulationBundleError("Simulation bundle artifact set is not exact")
        if any(key != artifact.artifact_id for key, artifact in artifacts.items()):
            raise SimulationBundleError("Simulation bundle artifact IDs are inconsistent")
        object.__setattr__(self, "artifacts", MappingProxyType(artifacts))

    @property
    def simulation_only(self) -> bool:
        return True

    @property
    def can_release_physical_gates(self) -> bool:
        return False

    def artifact(self, artifact_id: str) -> SimulationBundleArtifact:
        try:
            return self.artifacts[artifact_id]
        except KeyError as exc:
            raise SimulationBundleError(
                f"Unknown simulation bundle artifact {artifact_id!r}"
            ) from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "bundle_id": self.bundle_id,
            "status": self.status,
            "simulation_only": True,
            "physical_release_effect": "NONE",
            "system_manifest_id": self.system_manifest_id,
            "design_revision": self.design_revision,
            "source_lock_sha256": self.source_lock_sha256,
            "artifacts": {
                artifact_id: self.artifacts[artifact_id].to_dict()
                for artifact_id in sorted(self.artifacts)
            },
            "authority": {
                "simulation_only": True,
                "can_release_physical_gates": False,
                "hardware_io_allowed": False,
                "hardware_commands_generated": 0,
            },
        }


def _require_sha256(value: object, name: str) -> str:
    digest = identifier(value, name).lower()
    if _SHA256_PATTERN.fullmatch(digest) is None:
        raise SimulationBundleError(f"{name} must be a lowercase SHA-256 digest")
    return digest


def _validate_internal_bindings(
    lock: SimulationBundleLock,
) -> None:
    """Cross-check redundant pins so a self-inconsistent lock fails closed."""

    profile_artifact = lock.artifact("simulation_hardware_profile")
    target_artifact = lock.artifact("nominal_target_profiles")
    frame_artifact = lock.artifact("arm_frame_contract")
    camera_artifact = lock.artifact("camera_manifest")
    virtual_profile_artifact = lock.artifact("virtual_commissioning_profile")
    model_artifact = lock.artifact("local_roarm_urdf")

    profile = load_json_object(profile_artifact.path)
    profile_binding = mapping(profile.get("binding"), "simulation profile binding")
    if profile_binding.get("system_manifest_id") != lock.system_manifest_id:
        raise SimulationBundleError(
            "Simulation profile and bundle lock reference different system manifests"
        )
    if profile_binding.get("design_revision") != lock.design_revision:
        raise SimulationBundleError(
            "Simulation profile and bundle lock use different design revisions"
        )
    if profile_binding.get("nominal_target_profiles") != target_artifact.relative_path:
        raise SimulationBundleError(
            "Simulation profile target-map path differs from the bundle lock"
        )
    robot = mapping(profile.get("robot"), "simulation profile robot")
    official_model = mapping(robot.get("official_model"), "simulation profile model")
    if official_model.get("local_kinematic_projection") != model_artifact.relative_path:
        raise SimulationBundleError(
            "Simulation profile model path differs from the bundle lock"
        )
    if official_model.get("local_kinematic_projection_sha256") != model_artifact.sha256:
        raise SimulationBundleError(
            "Simulation profile model digest differs from the bundle lock"
        )

    targets = load_json_object(target_artifact.path)
    target_binding = mapping(targets.get("binding"), "nominal target binding")
    if target_binding.get("design_revision") != lock.design_revision:
        raise SimulationBundleError(
            "Nominal target map and bundle lock use different design revisions"
        )
    if target_binding.get("workcell_layout") != profile_binding.get("workcell_layout"):
        raise SimulationBundleError(
            "Nominal target map and simulation profile use different workcell layouts"
        )

    frame_contract = load_json_object(frame_artifact.path)
    if (
        frame_contract.get("schema") != "rocell.arm_frame_contract.v2"
        or frame_contract.get("schema_version") != 2
        or frame_contract.get("contract_id")
        != "ROCELL-ROARM-M3-PRO-FRAMES-DRAFT-002"
        or frame_contract.get("status") != "OPEN_BLOCKING_NOT_COMMISSIONED"
        or frame_contract.get("physical_release_effect") != "NONE"
        or frame_contract.get("length_unit") != "mm"
        or frame_contract.get("angle_unit") != "rad"
    ):
        raise SimulationBundleError(
            "Arm frame contract schema, identity, state, authority, or units changed"
        )
    # These sections jointly define the prohibited aliases, camera frames,
    # controller boundary, feedback interpretation, and prerequisites.  Pin
    # their canonical content so a coordinated artifact re-lock cannot weaken
    # the safety meaning while retaining the same top-level v2 label.
    frame_semantics = {
        key: frame_contract.get(key) for key in _ARM_FRAME_SEMANTIC_KEYS
    }
    frame_semantics_sha256 = hashlib.sha256(
        json.dumps(
            frame_semantics,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if frame_semantics_sha256 != _ARM_FRAME_SEMANTICS_SHA256:
        raise SimulationBundleError("Arm frame semantic contract changed")
    frame_identity = mapping(
        frame_contract.get("hardware_identity"),
        "frame contract hardware identity",
    )
    expected_frame_identity = {
        "manufacturer": robot.get("manufacturer"),
        "model": robot.get("model"),
        "controller": robot.get("controller"),
        "dof_contract": robot.get("dof_contract"),
    }
    if dict(frame_identity) != expected_frame_identity:
        raise SimulationBundleError(
            "Arm frame contract hardware identity differs from the simulation profile"
        )
    frame_pins = mapping(frame_contract.get("pinned_sources"), "frame contract pins")
    controller_sources = mapping(
        robot.get("official_controller_sources"),
        "simulation profile controller sources",
    )
    python_sdk = mapping(controller_sources.get("python_sdk"), "Python SDK source")
    firmware_archive = mapping(
        controller_sources.get("firmware_archive"),
        "firmware archive source",
    )
    expected_frame_pins = {
        "vendor_urdf_repository_commit": official_model.get("commit"),
        "local_kinematic_projection": model_artifact.relative_path,
        "local_kinematic_projection_sha256": model_artifact.sha256,
        "python_sdk_commit": python_sdk.get("commit"),
        "firmware_archive_sha256": firmware_archive.get("sha256"),
    }
    if dict(frame_pins) != expected_frame_pins:
        raise SimulationBundleError(
            "Arm frame contract provenance pins differ from the locked simulation profile"
        )

    camera = load_json_object(camera_artifact.path)
    if camera.get("system_freeze_id") != lock.system_manifest_id:
        raise SimulationBundleError(
            "Camera manifest and bundle lock reference different system manifests"
        )
    camera_primary = mapping(camera.get("primary"), "camera manifest primary")
    camera_candidate = mapping(
        camera_primary.get("selected_candidate"),
        "camera manifest selected candidate",
    )
    camera_holder = mapping(camera.get("holder"), "camera manifest holder")
    profile_camera = mapping(profile.get("camera"), "simulation profile camera")
    profile_carrier = mapping(profile_camera.get("carrier"), "simulation profile carrier")
    frame_camera = mapping(
        frame_contract.get("camera_installation"),
        "frame contract camera installation",
    )
    expected_hole_spacing = [21.0, 13.5]
    expected_module_size = [25.0, 24.0]
    camera_mechanics_ok = (
        camera.get("architecture") == "eye_on_moving_upper_arm"
        and camera_primary.get("backend") == "usb_opencv"
        and camera_candidate.get("model") == "IMX335 5MP USB Camera (B)"
        and camera_candidate.get("sku") == "26719"
        and camera_candidate.get("module_size_mm") == expected_module_size
        and camera_candidate.get("camera_hole_center_spacing_mm")
        == expected_hole_spacing
        and camera_holder.get("camera_hole_center_spacing_mm") == expected_hole_spacing
        and camera_holder.get("installed_rail_position_mm") is None
        and camera_holder.get("physical_part_revision") is None
        and profile_camera.get("module_size_mm") == expected_module_size
        and profile_camera.get("holder_hole_centres_mm") == expected_hole_spacing
        and profile_carrier.get("mount_pattern_mm") == expected_hole_spacing
        and profile_carrier.get("vendor_carrier_link") == "link2"
        and profile_carrier.get("carrier_frame") == "E"
        and profile_carrier.get("link2_T_holder") is None
        and profile_carrier.get("holder_T_C_optical") is None
        and frame_camera.get("carrier_link") == "link2"
        and frame_camera.get("carrier_frame") == "E"
        and frame_camera.get("link2_T_holder") is None
        and frame_camera.get("holder_T_C_arm") is None
    )
    if not camera_mechanics_ok:
        raise SimulationBundleError(
            "Camera manifest, simulation profile, and frame contract mechanics differ"
        )

    virtual_profile = load_json_object(virtual_profile_artifact.path)
    virtual_binding = mapping(
        virtual_profile.get("binding"),
        "virtual commissioning profile binding",
    )
    virtual_authority = mapping(
        virtual_profile.get("authority"),
        "virtual commissioning profile authority",
    )
    virtual_schema_version = virtual_profile.get("schema_version")
    if (
        virtual_profile.get("schema")
        != "rocell.virtual_commissioning_profile.v1"
        or isinstance(virtual_schema_version, bool)
        or virtual_schema_version != 1
        or virtual_profile.get("profile_id")
        != "ROCELL-VIRTUAL-COMMISSIONING-RANK1-001"
        or virtual_profile.get("status") != "UNMEASURED_SENSITIVITY_OVERLAY"
        or virtual_profile.get("simulation_only") is not True
        or virtual_profile.get("physical_release_effect") != "NONE"
        or virtual_binding.get("system_manifest_id") != lock.system_manifest_id
        or virtual_binding.get("design_revision") != lock.design_revision
        or virtual_binding.get("simulation_bundle_id") != lock.bundle_id
        or dict(virtual_authority)
        != {
            "simulation_only": True,
            "physical_release_effect": "NONE",
            "live_hardware_access_allowed": False,
            "hardware_commands_generated": 0,
            "can_promote_calibrations": False,
        }
    ):
        raise SimulationBundleError(
            "Virtual commissioning profile identity, binding, or authority changed"
        )


def load_simulation_bundle_lock(
    workspace: Path,
    *,
    lock_path: Path | None = None,
) -> SimulationBundleLock:
    """Load and verify the exact versioned simulation artifact bundle."""

    root = Path(workspace).resolve()
    selected = (
        Path(lock_path).resolve()
        if lock_path is not None
        else source_path(root, DEFAULT_SIMULATION_BUNDLE_LOCK)
    )
    try:
        selected.relative_to(root)
    except ValueError as exc:
        raise SimulationBundleError(
            "Simulation bundle lock must be beneath the workspace"
        ) from exc

    document = load_json_object(selected)
    if document.get("schema") != SIMULATION_BUNDLE_SCHEMA:
        raise SimulationBundleError("Unsupported simulation bundle lock schema")
    schema_version = document.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != 1:
        raise SimulationBundleError("Unsupported simulation bundle lock schema_version")
    if document.get("status") != SIMULATION_BUNDLE_STATUS:
        raise SimulationBundleError("Simulation bundle lock is not in its locked state")
    if document.get("simulation_only") is not True:
        raise SimulationBundleError("Simulation bundle lock must remain simulation-only")
    if document.get("physical_release_effect") != "NONE":
        raise SimulationBundleError(
            "Simulation bundle lock cannot affect physical release"
        )

    raw_artifacts = mapping(document.get("artifacts"), "simulation bundle artifacts")
    if set(raw_artifacts) != set(_EXPECTED_ARTIFACT_PATHS):
        missing = sorted(set(_EXPECTED_ARTIFACT_PATHS) - set(raw_artifacts))
        extra = sorted(set(raw_artifacts) - set(_EXPECTED_ARTIFACT_PATHS))
        raise SimulationBundleError(
            f"Simulation bundle artifact set mismatch; missing={missing}, extra={extra}"
        )

    artifacts: dict[str, SimulationBundleArtifact] = {}
    seen_paths: set[Path] = set()
    for artifact_id, expected_relative in _EXPECTED_ARTIFACT_PATHS.items():
        raw_artifact = mapping(
            raw_artifacts[artifact_id],
            f"simulation bundle artifact {artifact_id}",
        )
        if set(raw_artifact) != {"path", "sha256"}:
            raise SimulationBundleError(
                f"Simulation bundle artifact {artifact_id!r} must contain only path and sha256"
            )
        relative = identifier(raw_artifact.get("path"), f"{artifact_id} path")
        if relative != expected_relative:
            raise SimulationBundleError(
                f"Simulation bundle artifact {artifact_id!r} path changed"
            )
        path = source_path(root, relative)
        if path in seen_paths:
            raise SimulationBundleError("Simulation bundle artifact paths must be unique")
        seen_paths.add(path)
        expected_digest = _require_sha256(
            raw_artifact.get("sha256"),
            f"{artifact_id} sha256",
        )
        if not path.is_file():
            raise SimulationBundleError(
                f"Simulation bundle artifact is missing: {relative}"
            )
        actual_digest = sha256_file(path)
        if actual_digest != expected_digest:
            raise SimulationBundleError(
                f"Simulation bundle hash mismatch for {relative}: "
                f"expected {expected_digest}, got {actual_digest}"
            )
        artifacts[artifact_id] = SimulationBundleArtifact(
            artifact_id,
            relative,
            path,
            expected_digest,
        )

    lock = SimulationBundleLock(
        bundle_id=identifier(document.get("bundle_id"), "simulation bundle id"),
        system_manifest_id=identifier(
            document.get("system_manifest_id"),
            "simulation bundle system manifest id",
        ),
        design_revision=identifier(
            document.get("design_revision"),
            "simulation bundle design revision",
        ),
        source_lock_path=selected,
        source_lock_sha256=sha256_file(selected),
        artifacts=artifacts,
    )
    _validate_internal_bindings(lock)
    return lock
