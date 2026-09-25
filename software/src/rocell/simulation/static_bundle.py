"""Closed static-primary simulation inputs, separate from historical v1 locks."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from rocell.calibration.static_phase1_requirements import STATIC_OVERHEAD_PHASE1_GRAPH
from rocell.typing.static_development_profiles import (
    static_development_keyboard_profile,
    static_development_phone_profile,
    static_semantic_profile_binding,
)
from ._validation import (
    SimulationSourceError,
    load_json_object,
    sha256_file,
    source_path,
)
from .bundle import SimulationBundleArtifact


STATIC_BUNDLE_PATH = "software/config/static_simulation_bundle_lock.json"
STATIC_BUNDLE_SCHEMA = "rocell.static_simulation_bundle_lock.v1"
STATIC_BUNDLE_ID = "ROCELL-STATIC-B0477-SIM-BUNDLE-001"
STATIC_ARTIFACT_PATHS: Mapping[str, str] = MappingProxyType(
    {
        "system_manifest": "software/config/system_manifest.json",
        "robot_numerical_seed": "software/config/simulation_hardware_profile.json",
        "static_targets": "software/config/static_nominal_target_profiles.json",
        "legacy_geometry_seed": "software/config/nominal_target_profiles.json",
        "architecture": "software/config/camera_architecture_plan.json",
        "purchased_camera": "software/config/camera_profiles/arducam_b0477_imx283_16mm.json",
        "support_design": "hardware/static_overhead_camera/config/support_design.json",
        "kinematic_model": "software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf",
        "arm_frame_contract": "software/config/arm_frame_contract.json",
    }
)
ROBOT_NUMERICAL_SEED_SHA256 = (
    "b79ca2653fe0c95ecd328412a44b160d2d0beae1a0dc5c3e2fd09bb94a487990"
)


def static_semantic_bindings() -> dict:
    return {
        "keyboard": static_semantic_profile_binding(
            static_development_keyboard_profile()
        ),
        "phone": static_semantic_profile_binding(static_development_phone_profile()),
    }


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class StaticSimulationBundle:
    """Verified file references; never accepted without context revalidation."""

    source_path: Path
    source_sha256: str
    artifacts: Mapping[str, SimulationBundleArtifact]
    graph_hash: str
    semantic_bindings_sha256: str

    def __post_init__(self):
        object.__setattr__(self, "artifacts", MappingProxyType(dict(self.artifacts)))

    @property
    def physical_authority(self) -> bool:
        return False


def load_static_simulation_bundle(workspace: Path) -> StaticSimulationBundle:
    """Validate exact source roster and semantics; never rewrite a stale lock."""
    root = Path(workspace).resolve(strict=True)
    path = source_path(root, STATIC_BUNDLE_PATH)
    if (
        path != root / STATIC_BUNDLE_PATH
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > 128 * 1024
    ):
        raise SimulationSourceError("Static bundle is missing, unsafe or oversized")
    before = sha256_file(path)
    document = load_json_object(path)
    expected = dict(
        schema=STATIC_BUNDLE_SCHEMA,
        bundle_id=STATIC_BUNDLE_ID,
        simulation_only=True,
        physical_authority=False,
        physical_freeze_promoted=False,
        geometry_scope="UNCHANGED_FROZEN_ROBOT_AND_NOMINAL_WORKCELL_GEOMETRY",
        optical_scope="EXISTING_B0477_SYNTHETIC_PROXY_NOT_INSTALLED_CALIBRATION",
        graph_id=STATIC_OVERHEAD_PHASE1_GRAPH.graph_id,
        graph_sha256=STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash,
        semantic_bindings=static_semantic_bindings(),
        artifacts=document.get("artifacts"),
    )
    if _canonical(document) != _canonical(expected):
        raise SimulationSourceError(
            "Static bundle schema/architecture/semantic contract differs"
        )
    raw = document.get("artifacts")
    if type(raw) is not dict or set(raw) != set(STATIC_ARTIFACT_PATHS):
        raise SimulationSourceError("Static bundle artifact roster is not exact")
    artifacts = {}
    for identifier, relative in STATIC_ARTIFACT_PATHS.items():
        row = raw[identifier]
        if (
            type(row) is not dict
            or set(row) != {"path", "sha256"}
            or row["path"] != relative
        ):
            raise SimulationSourceError("Static bundle artifact path/fields differ")
        selected = source_path(root, relative)
        if (
            selected != root / relative
            or selected.is_symlink()
            or not selected.is_file()
        ):
            raise SimulationSourceError(
                "Static bundle artifact is redirected or unavailable"
            )
        actual = sha256_file(selected)
        if row["sha256"] != actual:
            raise SimulationSourceError(
                "Static bundle artifact bytes changed: " + identifier
            )
        artifacts[identifier] = SimulationBundleArtifact(
            identifier, relative, selected, actual
        )
    if artifacts["robot_numerical_seed"].sha256 != ROBOT_NUMERICAL_SEED_SHA256:
        raise SimulationSourceError(
            "Static robot geometry differs from its frozen numerical seed"
        )
    if sha256_file(path) != before:
        raise SimulationSourceError("Static bundle changed while loading")
    return StaticSimulationBundle(
        path,
        before,
        artifacts,
        STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash,
        hashlib.sha256(_canonical(expected["semantic_bindings"])).hexdigest(),
    )
