from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from rocell.application import SimulationContextError, load_simulation_context
from rocell.rc03.integrity import sha256_file


WORKSPACE = Path(__file__).resolve().parents[3]
SOFTWARE_BUNDLE_SOURCES = (
    "software/config/simulation_bundle_lock.json",
    "software/config/simulation_hardware_profile.json",
    "software/config/nominal_target_profiles.json",
    "software/config/arm_frame_contract.json",
    "software/config/camera_manifest.json",
    "software/config/virtual_commissioning_profile.json",
    "software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf",
)


def _write_json(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _alternate_workspace(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "workspace"
    rc03 = root / "active-project/RoCell_v0_3"
    sources: dict[str, dict[str, object]] = {
        "config/measurement_record.json": {
            "design_revision": "RC03-INT-R1",
            "selected_routes": {
                "keyboard_rod_route": True,
                "phone_stylus_route": True,
                "camera_mast_optional": False,
            },
            "gates": {"physical": {"status": "NOT_TESTED"}},
        },
        "fiducials/apriltag_map.json": {
            "design_revision": "RC03-INT-R1",
            "coordinate_source": "nominal_layout",
        },
        "BUILD_BY_STEP/ACTIVE_BUILD.json": {"active_build_id": "ALT-BUILD"},
    }
    for relative, document in sources.items():
        _write_json(rc03 / relative, document)
    source_snapshot = [
        {"path": relative, "sha256": sha256_file(rc03 / relative)}
        for relative in sources
    ]
    manifest: dict[str, object] = {
        "manifest_id": "ALTERNATE-SAME-REVISION-FREEZE",
        "status": "FROZEN_TEST",
        "rc03": {
            "root": "active-project/RoCell_v0_3",
            "design_revision": "RC03-INT-R1",
            "physical_release_status": "UNRELEASED",
            "active_build_id": "ALT-BUILD",
            "source_snapshot": source_snapshot,
        },
        "mission_routes": {
            "keyboard_rod_route": {"selected": True},
            "phone_stylus_route": {"selected": True},
            "camera_mast_optional": {"selected": False},
        },
        "hardware": {
            "robot": {"model": "Waveshare RoArm-M3 Pro"},
            "camera": {"exact_model": None, "state": "OPEN_BLOCKING"},
        },
        "fiducials": {"coordinate_source": "nominal_layout"},
        "current_build_state": {
            "safe_to_power_robot": False,
            "contact_enabled": False,
        },
        "hard_blockers": ["PHYSICAL_RELEASE_UNRELEASED"],
    }
    manifest_path = root / "software/config/system_manifest.json"
    _write_json(manifest_path, manifest)
    for relative in SOFTWARE_BUNDLE_SOURCES:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE / relative, destination)
    return root, manifest_path


def _coherent_frozen_copy(tmp_path: Path) -> tuple[Path, Path]:
    """Copy current RC03 bytes and refresh only the temporary manifest pins."""

    root = tmp_path / "coherent-workspace"
    manifest = json.loads(
        (WORKSPACE / "software/config/system_manifest.json").read_text(encoding="utf-8")
    )
    rc03_relative = manifest["rc03"]["root"]
    for entry in manifest["rc03"]["source_snapshot"]:
        relative = entry["path"]
        source = WORKSPACE / rc03_relative / relative
        destination = root / rc03_relative / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        entry["sha256"] = sha256_file(destination)
    for relative in SOFTWARE_BUNDLE_SOURCES:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE / relative, destination)
    manifest_path = root / "software/config/system_manifest.json"
    _write_json(manifest_path, manifest)
    return root, manifest_path


def test_context_is_bound_to_verified_simulation_bundle(tmp_path: Path) -> None:
    workspace, manifest_path = _coherent_frozen_copy(tmp_path)
    context = load_simulation_context(
        workspace,
        manifest_path,
    )

    assert context.bundle_lock.system_manifest_id == context.snapshot.manifest_id
    assert context.bundle_lock.design_revision == context.snapshot.design_revision
    assert context.bundle_lock.artifact("simulation_hardware_profile").sha256 == (
        context.hardware_profile.source_profile_sha256
    )
    assert context.bundle_lock.artifact("nominal_target_profiles").sha256 == (
        context.targets.content_sha256
    )
    assert context.bundle_lock.artifact("local_roarm_urdf").sha256 == (
        context.scenario.model_sha256
    )


def test_same_revision_custom_manifest_cannot_mix_with_default_simulation_freeze(
    tmp_path: Path,
) -> None:
    workspace, manifest_path = _alternate_workspace(tmp_path)

    with pytest.raises(SimulationContextError, match="does not reference"):
        load_simulation_context(workspace, manifest_path)


def test_manifest_outside_workspace_is_rejected_before_import(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(SimulationContextError, match="beneath the workspace"):
        load_simulation_context(workspace, outside)
