from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil

import pytest

from rocell.simulation import (
    SimulationBundleError,
    SimulationSourceError,
    load_simulation_bundle_lock,
    load_simulation_scenario,
)
from rocell.simulation._validation import load_json_object


WORKSPACE = Path(__file__).resolve().parents[3]
LOCK_RELATIVE = Path("software/config/simulation_bundle_lock.json")
ARTIFACT_RELATIVES = (
    Path("software/config/simulation_hardware_profile.json"),
    Path("software/config/nominal_target_profiles.json"),
    Path("software/config/arm_frame_contract.json"),
    Path("software/config/camera_manifest.json"),
    Path("software/config/virtual_commissioning_profile.json"),
    Path("software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle_workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    for relative in (LOCK_RELATIVE, *ARTIFACT_RELATIVES):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE / relative, destination)
    return root


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_json(path: Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _relock_artifact(root: Path, artifact_id: str, artifact_path: Path) -> None:
    """Update only a temporary test lock after an intentional artifact mutation."""

    lock_path = root / LOCK_RELATIVE
    lock = _read_json(lock_path)
    artifacts = lock["artifacts"]
    assert isinstance(artifacts, dict)
    artifact = artifacts[artifact_id]
    assert isinstance(artifact, dict)
    artifact["sha256"] = _sha256(artifact_path)
    _write_json(lock_path, lock)


def test_controlled_simulation_bundle_verifies_exact_six_artifacts() -> None:
    bundle = load_simulation_bundle_lock(WORKSPACE)
    manifest = _read_json(WORKSPACE / "software/config/system_manifest.json")
    manifest_id = manifest["manifest_id"]
    assert isinstance(manifest_id, str)
    freeze_number = manifest_id.rsplit("-", maxsplit=1)[-1]

    assert bundle.system_manifest_id == manifest_id
    assert bundle.design_revision == "RC03-INT-R1"
    assert re.fullmatch(
        rf"ROCELL-SIM-BUNDLE-{re.escape(bundle.design_revision)}-FREEZE-"
        rf"{re.escape(freeze_number)}-[0-9]{{3}}",
        bundle.bundle_id,
    ) is not None
    assert set(bundle.artifacts) == {
        "simulation_hardware_profile",
        "nominal_target_profiles",
        "arm_frame_contract",
        "camera_manifest",
        "virtual_commissioning_profile",
        "local_roarm_urdf",
    }
    assert all(
        artifact.sha256 == _sha256(artifact.path)
        for artifact in bundle.artifacts.values()
    )
    assert bundle.simulation_only is True
    assert bundle.can_release_physical_gates is False
    assert bundle.to_dict()["authority"] == {
        "simulation_only": True,
        "can_release_physical_gates": False,
        "hardware_io_allowed": False,
        "hardware_commands_generated": 0,
    }


def test_bundle_rejects_artifact_byte_drift(tmp_path: Path) -> None:
    root = _bundle_workspace(tmp_path)
    targets_path = root / "software/config/nominal_target_profiles.json"
    targets_path.write_bytes(targets_path.read_bytes() + b"\n")

    with pytest.raises(SimulationBundleError, match="hash mismatch"):
        load_simulation_bundle_lock(root)


def test_bundle_rejects_internally_inconsistent_relocked_profile(tmp_path: Path) -> None:
    root = _bundle_workspace(tmp_path)
    profile_path = root / "software/config/simulation_hardware_profile.json"
    profile = _read_json(profile_path)
    robot = profile["robot"]
    assert isinstance(robot, dict)
    official_model = robot["official_model"]
    assert isinstance(official_model, dict)
    official_model["local_kinematic_projection_sha256"] = "0" * 64
    _write_json(profile_path, profile)

    lock_path = root / LOCK_RELATIVE
    lock = _read_json(lock_path)
    artifacts = lock["artifacts"]
    assert isinstance(artifacts, dict)
    locked_profile = artifacts["simulation_hardware_profile"]
    assert isinstance(locked_profile, dict)
    locked_profile["sha256"] = _sha256(profile_path)
    _write_json(lock_path, lock)

    with pytest.raises(SimulationBundleError, match="model digest differs"):
        load_simulation_bundle_lock(root)


def test_bundle_rejects_missing_or_extra_artifact_entries(tmp_path: Path) -> None:
    root = _bundle_workspace(tmp_path)
    lock_path = root / LOCK_RELATIVE
    lock = _read_json(lock_path)
    artifacts = lock["artifacts"]
    assert isinstance(artifacts, dict)
    del artifacts["arm_frame_contract"]
    artifacts["unexpected"] = {
        "path": "software/config/camera_manifest.json",
        "sha256": _sha256(root / "software/config/camera_manifest.json"),
    }
    _write_json(lock_path, lock)

    with pytest.raises(SimulationBundleError, match="artifact set mismatch"):
        load_simulation_bundle_lock(root)


def test_bundle_rejects_boolean_schema_version(tmp_path: Path) -> None:
    root = _bundle_workspace(tmp_path)
    lock_path = root / LOCK_RELATIVE
    lock = _read_json(lock_path)
    lock["schema_version"] = True
    _write_json(lock_path, lock)

    with pytest.raises(SimulationBundleError, match="schema_version"):
        load_simulation_bundle_lock(root)


def test_bundle_rejects_relocked_target_workcell_crosslink_drift(tmp_path: Path) -> None:
    root = _bundle_workspace(tmp_path)
    target_path = root / "software/config/nominal_target_profiles.json"
    targets = _read_json(target_path)
    binding = targets["binding"]
    assert isinstance(binding, dict)
    binding["workcell_layout"] = "active-project/other/config/workcell_layout.json"
    _write_json(target_path, targets)
    _relock_artifact(root, "nominal_target_profiles", target_path)

    with pytest.raises(SimulationBundleError, match="different workcell layouts"):
        load_simulation_bundle_lock(root)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("schema", "not.a.frame.contract", "schema, identity, state"),
        ("status", "PHYSICAL_RELEASED", "schema, identity, state"),
    ),
)
def test_bundle_rejects_relocked_frame_contract_authority_drift(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    root = _bundle_workspace(tmp_path)
    frame_path = root / "software/config/arm_frame_contract.json"
    frame = _read_json(frame_path)
    frame[field] = value
    _write_json(frame_path, frame)
    _relock_artifact(root, "arm_frame_contract", frame_path)

    with pytest.raises(SimulationBundleError, match=message):
        load_simulation_bundle_lock(root)


def test_bundle_rejects_relocked_frame_provenance_drift(tmp_path: Path) -> None:
    root = _bundle_workspace(tmp_path)
    frame_path = root / "software/config/arm_frame_contract.json"
    frame = _read_json(frame_path)
    pins = frame["pinned_sources"]
    assert isinstance(pins, dict)
    pins["python_sdk_commit"] = "0" * 40
    _write_json(frame_path, frame)
    _relock_artifact(root, "arm_frame_contract", frame_path)

    with pytest.raises(SimulationBundleError, match="provenance pins"):
        load_simulation_bundle_lock(root)


def test_bundle_rejects_relocked_nested_frame_semantic_drift(tmp_path: Path) -> None:
    root = _bundle_workspace(tmp_path)
    frame_path = root / "software/config/arm_frame_contract.json"
    frame = _read_json(frame_path)
    motion = frame["motion_t104"]
    assert isinstance(motion, dict)
    motion["cartesian_frame"] = "Wv"
    _write_json(frame_path, frame)
    _relock_artifact(root, "arm_frame_contract", frame_path)

    with pytest.raises(SimulationBundleError, match="semantic contract changed"):
        load_simulation_bundle_lock(root)


def test_bundle_rejects_relocked_camera_mechanical_mismatch(tmp_path: Path) -> None:
    root = _bundle_workspace(tmp_path)
    camera_path = root / "software/config/camera_manifest.json"
    camera = _read_json(camera_path)
    primary = camera["primary"]
    assert isinstance(primary, dict)
    candidate = primary["selected_candidate"]
    assert isinstance(candidate, dict)
    candidate["camera_hole_center_spacing_mm"] = [20.0, 13.5]
    _write_json(camera_path, camera)
    _relock_artifact(root, "camera_manifest", camera_path)

    with pytest.raises(SimulationBundleError, match="mechanics differ"):
        load_simulation_bundle_lock(root)


def test_bundle_rejects_relocked_virtual_profile_authority_drift(
    tmp_path: Path,
) -> None:
    root = _bundle_workspace(tmp_path)
    profile_path = root / "software/config/virtual_commissioning_profile.json"
    profile = _read_json(profile_path)
    authority = profile["authority"]
    assert isinstance(authority, dict)
    authority["live_hardware_access_allowed"] = True
    _write_json(profile_path, profile)
    _relock_artifact(root, "virtual_commissioning_profile", profile_path)

    with pytest.raises(SimulationBundleError, match="identity, binding, or authority"):
        load_simulation_bundle_lock(root)


def test_scenario_rejects_fixed_gripper_outside_controller_intersection(
    tmp_path: Path,
) -> None:
    root = _bundle_workspace(tmp_path)
    profile_path = root / "software/config/simulation_hardware_profile.json"
    profile = _read_json(profile_path)
    robot = profile["robot"]
    assert isinstance(robot, dict)
    bridge = robot["controller_model_bridge"]
    assert isinstance(bridge, dict)
    intersection = bridge["provisional_simulation_joint_intersection_rad"]
    assert isinstance(intersection, dict)
    intersection["gripper_model"] = [0.5, 1.5]
    _write_json(profile_path, profile)

    with pytest.raises(SimulationSourceError, match="Fixed gripper position leaves"):
        load_simulation_scenario(root)


def test_scenario_rejects_gripper_intersection_outside_pinned_urdf(
    tmp_path: Path,
) -> None:
    root = _bundle_workspace(tmp_path)
    profile_path = root / "software/config/simulation_hardware_profile.json"
    profile = _read_json(profile_path)
    robot = profile["robot"]
    assert isinstance(robot, dict)
    bridge = robot["controller_model_bridge"]
    assert isinstance(bridge, dict)
    intersection = bridge["provisional_simulation_joint_intersection_rad"]
    assert isinstance(intersection, dict)
    intersection["gripper_model"] = [-100.0, 100.0]
    _write_json(profile_path, profile)

    with pytest.raises(SimulationSourceError, match="leaves the pinned URDF"):
        load_simulation_scenario(root)


def test_scenario_rejects_reordered_joint_contract(tmp_path: Path) -> None:
    root = _bundle_workspace(tmp_path)
    profile_path = root / "software/config/simulation_hardware_profile.json"
    profile = _read_json(profile_path)
    robot = profile["robot"]
    assert isinstance(robot, dict)
    joint_order = robot["joint_order"]
    assert isinstance(joint_order, list)
    joint_order[0], joint_order[5] = joint_order[5], joint_order[0]
    _write_json(profile_path, profile)

    with pytest.raises(SimulationSourceError, match="joint_order changed"):
        load_simulation_scenario(root)


@pytest.mark.parametrize("constant", ("NaN", "Infinity", "-Infinity"))
def test_simulation_json_loader_rejects_nonfinite_constants(
    tmp_path: Path,
    constant: str,
) -> None:
    source = tmp_path / "nonfinite.json"
    source.write_text('{"value": ' + constant + '}\n', encoding="utf-8")

    with pytest.raises(SimulationSourceError, match="Nonfinite JSON constant"):
        load_json_object(source)
