from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest

import rocell.application.bootstrap as bootstrap_module
from rocell.application.bootstrap import (
    BOOTSTRAP_SCHEMA,
    BootstrapConfigurationError,
    bootstrap_virtual_workcell,
    revalidate_virtual_workcell,
)
from rocell.application.context import load_simulation_context


WORKSPACE = Path(__file__).resolve().parents[3]


def _write_json(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _copy_virtual_workspace(tmp_path: Path, name: str = "workspace") -> Path:
    """Copy only the exact startup sources required by the virtual bootstrap."""

    root = tmp_path / name
    config = root / "software/config"
    config.mkdir(parents=True)
    for relative in (
        "software/config/runtime.json",
        "software/config/system_manifest.json",
        "software/config/simulation_bundle_lock.json",
        "software/config/gate_projection.json",
        "software/config/arm_connection.json",
        "software/calibrations/registry.json",
    ):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE / relative, destination)

    manifest = json.loads(
        (WORKSPACE / "software/config/system_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    rc03_relative = manifest["rc03"]["root"]
    for entry in manifest["rc03"]["source_snapshot"]:
        relative = entry["path"]
        destination = root / rc03_relative / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE / rc03_relative / relative, destination)

    bundle = json.loads(
        (WORKSPACE / "software/config/simulation_bundle_lock.json").read_text(
            encoding="utf-8"
        )
    )
    for artifact in bundle["artifacts"].values():
        relative = artifact["path"]
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE / relative, destination)

    source_registry = WORKSPACE / "software/calibrations"
    destination_registry = root / "software/calibrations"
    destination_registry.mkdir(parents=True, exist_ok=True)
    if (source_registry / "index.json").is_file():
        shutil.copyfile(
            source_registry / "index.json", destination_registry / "index.json"
        )
    if (source_registry / "artifacts").is_dir():
        shutil.copytree(
            source_registry / "artifacts",
            destination_registry / "artifacts",
        )
    (root / "software/runs").mkdir(parents=True)
    return root


def test_checked_in_bootstrap_is_deterministic_ready_and_zero_authority() -> None:
    first = bootstrap_virtual_workcell(WORKSPACE)
    second = bootstrap_virtual_workcell(WORKSPACE)

    assert first.to_dict() == second.to_dict()
    assert first.bootstrap_hash == second.bootstrap_hash
    assert first.simulation_ready is True
    assert first.status == "READY_SIMULATION_ONLY_WITH_DECLARED_GAPS"
    document = first.to_dict()
    assert document["schema"] == BOOTSTRAP_SCHEMA
    assert document["authority"] == {
        "simulation_only": True,
        "execution_authorized": False,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "can_release_physical_gates": False,
        "safe_to_power_robot_conferred": False,
        "contact_enabled_conferred": False,
    }
    assert document["synthetic_overview"]["visible_tag_count"] == 6
    assert document["synthetic_overview"]["tag_count"] == 6
    assert document["arm_connection"]["commissioned"] is False
    assert document["collision_readiness"]["diagnostic_ready"] is False
    assert set(document["gate_projection"]["allowed"]) == {
        "digital_plan",
        "simulated_dry_run",
        "camera_capture",
        "arm_feedback",
        "empty_cell_motion",
        "keyboard_contact",
        "phone_contact",
    }
    checks = {item["id"]: item for item in document["checks"]}
    assert checks["runtime_policy"]["status"] == "PASS"
    assert checks["synthetic_overview"]["status"] == "PASS"
    assert checks["physical_calibration"]["status"] == "DECLARED_GAP"
    assert checks["collision_geometry"]["status"] == "DECLARED_GAP"


def test_bootstrap_hash_is_independent_of_absolute_workspace_path(
    tmp_path: Path,
) -> None:
    first_root = _copy_virtual_workspace(tmp_path, "first")
    second_root = _copy_virtual_workspace(tmp_path, "second")

    first = bootstrap_virtual_workcell(first_root)
    second = bootstrap_virtual_workcell(second_root)

    assert first.bootstrap_hash == second.bootstrap_hash
    assert first.to_dict() == second.to_dict()


@pytest.mark.parametrize(
    ("field_path", "value", "message"),
    (
        (("live_hardware_enabled",), True, "disable live hardware"),
        (("contact_enabled",), True, "disable contact"),
        (
            ("policy", "automatic_motion_retry"),
            True,
            "automatic_motion_retry",
        ),
    ),
)
def test_bootstrap_rejects_weakened_runtime_policy(
    tmp_path: Path,
    field_path: tuple[str, ...],
    value: object,
    message: str,
) -> None:
    root = _copy_virtual_workspace(tmp_path)
    path = root / "software/config/runtime.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    target = document
    for key in field_path[:-1]:
        target = target[key]
    target[field_path[-1]] = value
    _write_json(path, document)

    with pytest.raises(BootstrapConfigurationError, match=message):
        bootstrap_virtual_workcell(root)


def test_bootstrap_rejects_runtime_path_escape_before_source_loading(
    tmp_path: Path,
) -> None:
    root = _copy_virtual_workspace(tmp_path)
    path = root / "software/config/runtime.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["camera_manifest"] = "../outside-camera.json"
    _write_json(path, document)

    with pytest.raises(BootstrapConfigurationError, match="escapes the workspace"):
        bootstrap_virtual_workcell(root)


def test_bootstrap_rejects_gate_projection_capability_drift(tmp_path: Path) -> None:
    root = _copy_virtual_workspace(tmp_path)
    path = root / "software/config/gate_projection.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["capabilities"]["simulated_dry_run"]["allowed"] = False
    _write_json(path, document)

    with pytest.raises(BootstrapConfigurationError, match="simulated_dry_run.*disagrees"):
        bootstrap_virtual_workcell(root)


def test_bootstrap_rejects_calibration_manifest_inventory_drift(
    tmp_path: Path,
) -> None:
    root = _copy_virtual_workspace(tmp_path)
    path = root / "software/calibrations/registry.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["artifacts"] = {"camera_intrinsics": "a" * 64}
    document["status"] = "PHYSICAL_EVIDENCE_PRESENT"
    _write_json(path, document)

    with pytest.raises(BootstrapConfigurationError, match="registry index"):
        bootstrap_virtual_workcell(root)


def test_bootstrap_rejects_scene_hash_not_bound_to_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _copy_virtual_workspace(tmp_path)
    context = load_simulation_context(
        root,
        root / "software/config/system_manifest.json",
    )
    changed_hashes = dict(context.scene.source_hashes)
    changed_hashes["config/workcell_layout.json"] = "f" * 64
    changed_scene = replace(context.scene, source_hashes=changed_hashes)
    changed_context = replace(context, scene=changed_scene)
    monkeypatch.setattr(
        bootstrap_module,
        "load_simulation_context",
        lambda _workspace, _manifest: changed_context,
    )

    with pytest.raises(BootstrapConfigurationError, match="Scene bytes differ"):
        bootstrap_virtual_workcell(root)


def test_revalidation_detects_valid_but_changed_startup_source(tmp_path: Path) -> None:
    root = _copy_virtual_workspace(tmp_path)
    bootstrap = bootstrap_virtual_workcell(root)
    path = root / "software/config/gate_projection.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["capabilities"]["digital_plan"]["reason"] += " (edited)"
    _write_json(path, document)

    with pytest.raises(BootstrapConfigurationError, match="differs from freshly"):
        revalidate_virtual_workcell(bootstrap)


def test_runtime_json_rejects_duplicate_and_nonfinite_fields(tmp_path: Path) -> None:
    root = _copy_virtual_workspace(tmp_path)
    path = root / "software/config/runtime.json"
    original = path.read_text(encoding="utf-8")
    path.write_text(
        original.replace(
            '"schema_version": 1,',
            '"schema_version": 1, "schema_version": 1,',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(BootstrapConfigurationError, match="Duplicate"):
        bootstrap_virtual_workcell(root)

    path.write_text(original.replace('"schema_version": 1', '"schema_version": NaN', 1))
    with pytest.raises(BootstrapConfigurationError, match="Nonfinite"):
        bootstrap_virtual_workcell(root)

