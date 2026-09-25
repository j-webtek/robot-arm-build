"""Load one coherent, hash-linked simulation context.

All source paths are resolved once from the caller-selected manifest and the
frozen simulation profile.  This prevents a custom snapshot from being mixed
with the default workcell, camera binding, or target map.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rocell.rc03 import (
    BuildImportError,
    BuildIntegrityError,
    BuildSnapshot,
    import_build_snapshot,
)
from rocell.simulation import (
    NominalWorkcellScene,
    SimulationBundleLock,
    SimulationHardwareProfile,
    SimulationScenario,
    load_rc03_nominal_scene,
    load_simulation_bundle_lock,
    load_simulation_hardware_profile,
    load_simulation_scenario,
)
from rocell.simulation._validation import (
    identifier,
    load_json_object,
    mapping,
    sha256_file,
    source_path,
)
from rocell.targets import NominalTargetCatalog, load_nominal_target_catalog
from rocell.workcell import PlacematAlignmentReport, validate_placemat_alignment


class SimulationContextError(ValueError):
    """The selected sources do not describe the same immutable workcell."""


@dataclass(frozen=True, slots=True)
class SimulationContext:
    """Verified input bundle shared by all stages of one simulation run."""

    workspace: Path
    manifest_path: Path
    rc03_root: Path
    snapshot: BuildSnapshot
    bundle_lock: SimulationBundleLock
    hardware_profile: SimulationHardwareProfile
    scenario: SimulationScenario
    scene: NominalWorkcellScene
    targets: NominalTargetCatalog
    alignment: PlacematAlignmentReport


def revalidate_simulation_context(context: SimulationContext) -> None:
    """Fail closed if an in-memory context differs from its locked sources.

    ``frozen=True`` prevents direct assignment, but it does not prevent a caller
    from creating a modified copy with :func:`dataclasses.replace`.  Application
    services call this boundary guard before trusting any geometry or evidence.
    The guard reconstructs the complete context through the same source loader
    used at startup, then compares every field.  This validates the RC03
    snapshot as well as reloading the bundle, scenario, scene, targets, and
    alignment instead of trusting hashes stored in caller-provided dataclasses.
    """

    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")

    root = Path(context.workspace).resolve()
    selected_manifest = Path(context.manifest_path).resolve()
    try:
        selected_manifest.relative_to(root)
    except ValueError as exc:
        raise SimulationContextError(
            "Simulation manifest must be beneath the workspace"
        ) from exc

    try:
        verified = load_simulation_context(root, selected_manifest)
    except (OSError, TypeError, ValueError) as exc:
        raise SimulationContextError(
            f"Could not revalidate locked simulation sources: {exc}"
        ) from exc

    mismatches: list[str] = []
    if context.workspace != verified.workspace:
        mismatches.append("workspace differs from the canonical source context")
    if context.manifest_path != verified.manifest_path:
        mismatches.append("manifest_path differs from the canonical source context")
    if context.rc03_root != verified.rc03_root:
        mismatches.append("rc03_root differs from the locked scenario")
    if context.snapshot != verified.snapshot:
        mismatches.append("snapshot differs from the verified build import")
    if context.bundle_lock != verified.bundle_lock:
        mismatches.append("bundle_lock differs from the canonical lock")
    if context.hardware_profile != verified.hardware_profile:
        mismatches.append("hardware_profile differs from its locked source")
    if context.scenario != verified.scenario:
        mismatches.append("scenario differs from its locked source")
    if context.scene != verified.scene:
        mismatches.append("scene differs from its locked sources")
    if context.targets != verified.targets:
        mismatches.append("targets differ from their locked source")
    if context.alignment != verified.alignment:
        mismatches.append("alignment differs from a fresh locked-source validation")

    if mismatches:
        raise SimulationContextError(
            "Simulation context coherence check failed: " + "; ".join(mismatches)
        )


def load_simulation_context(
    workspace: Path,
    manifest_path: Path,
) -> SimulationContext:
    """Import and cross-check one frozen context without touching hardware."""

    root = Path(workspace).resolve()
    selected_manifest = Path(manifest_path).resolve()
    try:
        selected_manifest.relative_to(root)
    except ValueError as exc:
        raise SimulationContextError("Simulation manifest must be beneath the workspace") from exc

    try:
        snapshot = import_build_snapshot(root, selected_manifest)
        manifest = load_json_object(selected_manifest)
        manifest_rc03 = mapping(manifest.get("rc03"), "system manifest rc03")
        rc03_root = source_path(
            root,
            identifier(manifest_rc03.get("root"), "system manifest rc03 root"),
        )
        bundle = load_simulation_bundle_lock(
            root,
            lock_path=selected_manifest.parent / "simulation_bundle_lock.json",
        )
        locked_profile = bundle.artifact("simulation_hardware_profile")
        locked_camera = bundle.artifact("camera_manifest")
        locked_targets = bundle.artifact("nominal_target_profiles")
        locked_model = bundle.artifact("local_roarm_urdf")
        profile = load_simulation_hardware_profile(
            root,
            profile_path=locked_profile.path,
            system_manifest_path=selected_manifest,
            camera_manifest_path=locked_camera.path,
        )
        scenario = load_simulation_scenario(root, profile_path=locked_profile.path)
        scenario_rc03_root = scenario.workcell_layout_path.parents[1]
        if scenario_rc03_root != rc03_root:
            raise SimulationContextError(
                "Selected manifest RC03 root differs from the simulation-profile workcell root"
            )
        scene = load_rc03_nominal_scene(
            rc03_root,
            assumed_tag_plane_z_mm=scenario.assumed_tag_plane_z_mm,
            station_proxy_height_mm=scenario.station_proxy_height_mm,
        )
        if scenario.apriltag_map_path != rc03_root / "fiducials/apriltag_map.json":
            raise SimulationContextError(
                "Simulation-profile AprilTag path differs from the selected RC03 map"
            )
        if scenario.target_profile_path != locked_targets.path:
            raise SimulationContextError(
                "Simulation scenario target profile differs from the bundle lock"
            )
        if scenario.model_path != locked_model.path:
            raise SimulationContextError(
                "Simulation scenario model differs from the bundle lock"
            )
        targets = load_nominal_target_catalog(root, locked_targets.path)
    except SimulationContextError:
        raise
    except (
        BuildImportError,
        BuildIntegrityError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        raise SimulationContextError(f"Could not load coherent simulation sources: {exc}") from exc

    manifest_hash = sha256_file(selected_manifest)
    mismatches: list[str] = []
    if profile.source_freeze_id != snapshot.manifest_id:
        mismatches.append("snapshot manifest ID differs from hardware profile freeze ID")
    if bundle.system_manifest_id != snapshot.manifest_id:
        mismatches.append("snapshot manifest ID differs from simulation bundle lock")
    if bundle.design_revision != snapshot.design_revision:
        mismatches.append("snapshot design revision differs from simulation bundle lock")
    if profile.source_manifest_sha256 != manifest_hash:
        mismatches.append("hardware profile did not bind the selected manifest bytes")
    if snapshot.manifest_sha256 != manifest_hash:
        mismatches.append("snapshot manifest hash differs from the selected manifest bytes")
    if profile.source_profile_sha256 != scenario.source_profile_sha256:
        mismatches.append("identity and numerical projections used different profile bytes")
    if profile.source_profile_sha256 != bundle.artifact(
        "simulation_hardware_profile"
    ).sha256:
        mismatches.append("hardware profile bytes differ from the simulation bundle lock")
    if profile.source_camera_manifest_sha256 != bundle.artifact("camera_manifest").sha256:
        mismatches.append("camera manifest bytes differ from the simulation bundle lock")
    if targets.content_sha256 != bundle.artifact("nominal_target_profiles").sha256:
        mismatches.append("nominal target bytes differ from the simulation bundle lock")
    if scenario.model_sha256 != bundle.artifact("local_roarm_urdf").sha256:
        mismatches.append("URDF bytes differ from the simulation bundle lock")
    if snapshot.design_revision != profile.design_revision:
        mismatches.append("snapshot and simulation profile use different design revisions")
    if mismatches:
        raise SimulationContextError("; ".join(mismatches))

    alignment = validate_placemat_alignment(profile, scenario, scene, targets)
    return SimulationContext(
        workspace=root,
        manifest_path=selected_manifest,
        rc03_root=rc03_root,
        snapshot=snapshot,
        bundle_lock=bundle,
        hardware_profile=profile,
        scenario=scenario,
        scene=scene,
        targets=targets,
        alignment=alignment,
    )
