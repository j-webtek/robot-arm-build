"""Explicit static-primary task inputs, never a relabeled legacy context.

The historical manifest supplies the existing digital workcell snapshot only.
Its camera/holder capability decisions are not inherited. Static semantics,
targets, optical model and prerequisite graph are separately bound by the new
software-only bundle. No physical freeze, calibration or authority is promoted.
"""

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from rocell.calibration.static_phase1_requirements import STATIC_OVERHEAD_PHASE1_GRAPH
from rocell.rc03 import BuildSnapshot, import_build_snapshot
from rocell.simulation import NominalWorkcellScene
from rocell.simulation._validation import SimulationSourceError, load_json_object
from rocell.simulation.scenario import (
    SimulationScenario,
    SyntheticOverviewScenario,
    _scenario_from_document,
)
from rocell.simulation.static_bundle import (
    StaticSimulationBundle,
    load_static_simulation_bundle,
)
from rocell.targets.nominal import NominalTargetCatalog
from rocell.targets.static_nominal import load_static_nominal_target_catalog
from rocell.typing.static_development_profiles import (
    static_development_keyboard_profile,
    static_development_phone_profile,
)
from .b0477_optical_contract import B0477SyntheticOpticalContract
from .b0477_static_vision import B0477NominalProjection, _load_inputs, _nominal_camera


@dataclass(frozen=True, slots=True)
class StaticSimulationContext:
    workspace: Path
    manifest_path: Path
    snapshot: BuildSnapshot
    bundle: StaticSimulationBundle
    scenario: SimulationScenario
    scene: NominalWorkcellScene
    targets: NominalTargetCatalog
    optical_contract: B0477SyntheticOpticalContract
    nominal_projection: B0477NominalProjection

    @property
    def physical_authority(self) -> bool:
        return False


def load_static_simulation_context(workspace: Path) -> StaticSimulationContext:
    """Load and cross-check one closed static source route without device IO."""
    root = Path(workspace).resolve(strict=True)
    bundle = load_static_simulation_bundle(root)
    manifest_path = bundle.artifacts["system_manifest"].path
    snapshot = import_build_snapshot(root, manifest_path)
    architecture = load_json_object(bundle.artifacts["architecture"].path)
    if (
        architecture["primary"]["architecture"] != "static_overhead_eye_to_hand"
        or architecture["routes"]["camera_overhead_primary"]["selected"] is not True
        or architecture["routes"]["camera_arm_secondary"]["selected"] is not False
        or architecture["routes"]["camera_arm_secondary"]["automatic_fallback_allowed"]
        is not False
    ):
        raise SimulationSourceError(
            "Static context requires the selected primary, with no secondary fallback"
        )
    # Existing source loaders validate purchased profile/support identity, exact
    # scene hashes, board dimensions/axis and the six-tag namespace. Existing
    # synthetic optics retain their distortion and estimator-pixel-space model.
    _, profile, support, scene = _load_inputs(root, None, None)
    optical, camera, camera_T_board, _, projection = _nominal_camera(
        profile, support, scene
    )
    overview = SyntheticOverviewScenario(
        "STATIC_B0477_NOMINAL_TASK_PROXY_NOT_INSTALLED_CALIBRATION",
        camera,
        camera_T_board,
        False,
    )
    seed = load_json_object(bundle.artifacts["robot_numerical_seed"].path)
    # Extract only numerical robot/workcell inputs. In particular, do not pass
    # the old camera or holder document to the shared numerical parser. The
    # primary source identity is this bundle descriptor, which binds both the
    # frozen numerical seed and the separately loaded B0477 sources.
    numerical = {
        key: deepcopy(seed[key])
        for key in (
            "schema",
            "simulation_only",
            "live_hardware_access_allowed",
            "robot",
            "binding",
            "simulation_defaults",
        )
    }
    numerical["binding"]["nominal_target_profiles"] = bundle.artifacts[
        "static_targets"
    ].relative_path
    scenario = _scenario_from_document(
        root, bundle.source_path, numerical, overview_scenario=overview
    )
    targets = load_static_nominal_target_catalog(root)
    if (
        snapshot.manifest_sha256 != bundle.artifacts["system_manifest"].sha256
        or snapshot.manifest_id != numerical["binding"]["system_manifest_id"]
        or snapshot.design_revision != scene.design_revision
        or targets.design_revision != snapshot.design_revision
        or scenario.model_sha256 != bundle.artifacts["kinematic_model"].sha256
        or scenario.model_path != bundle.artifacts["kinematic_model"].path
        or targets.content_sha256 != bundle.artifacts["static_targets"].sha256
        or scenario.target_profile_path != targets.profile_path
        or scenario.workcell_layout_path != targets.workcell_layout_path
        or scene.source_hashes["config/workcell_layout.json"]
        != support.source_sha256["workcell_layout"]
        or scenario.assumed_tag_plane_z_mm != projection.tag_plane_z_board_mm
    ):
        raise SimulationSourceError("Static context source/geometry joins differ")
    # Re-read the entire descriptor and its artifacts after all independent
    # loaders. An old approval/dataclass is not a cache of current source state.
    if load_static_simulation_bundle(root) != bundle:
        raise SimulationSourceError("Static context sources changed while loading")
    if import_build_snapshot(root, manifest_path) != snapshot:
        raise SimulationSourceError("Static build sources changed while loading")
    if _load_inputs(root, None, None) != (root, profile, support, scene):
        raise SimulationSourceError(
            "Static camera/support/scene sources changed while loading"
        )
    return StaticSimulationContext(
        root,
        manifest_path,
        snapshot,
        bundle,
        scenario,
        scene,
        targets,
        optical,
        projection,
    )


def revalidate_static_simulation_context(context: StaticSimulationContext) -> None:
    """Reconstruct this exact route; reject changed sources or replaced fields."""
    if type(context) is not StaticSimulationContext:
        raise TypeError("An exact StaticSimulationContext is required")
    if context != load_static_simulation_context(context.workspace):
        raise SimulationSourceError(
            "Static simulation context differs from freshly loaded sources"
        )


def static_simulation_context_hashes(
    context: StaticSimulationContext,
) -> Mapping[str, str]:
    """Supply the existing graph's exact context keys after full revalidation."""
    revalidate_static_simulation_context(context)
    refs = context.bundle.artifacts
    hashes = dict(
        system_manifest=context.snapshot.manifest_sha256,
        kinematic_model=context.scenario.model_sha256,
        workcell_layout=context.scene.source_hashes["config/workcell_layout.json"],
        apriltag_map=context.scene.source_hashes["fiducials/apriltag_map.json"],
        target_catalog=context.targets.content_sha256,
        keyboard_semantic_profile=static_development_keyboard_profile().semantic_content_sha256,
        phone_semantic_profile=static_development_phone_profile().semantic_content_sha256,
        camera_architecture_plan=refs["architecture"].sha256,
        b0477_catalog_profile=refs["purchased_camera"].sha256,
        static_camera_support=refs["support_design"].sha256,
    )
    if set(hashes) != set(STATIC_OVERHEAD_PHASE1_GRAPH.required_context_hash_ids):
        raise SimulationSourceError("Static graph context dependency roster differs")
    return MappingProxyType(hashes)
