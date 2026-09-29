"""Real-file static context joins with unchanged digital geometry and no IO owners."""

from dataclasses import fields, replace
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess

import pytest

from rocell.application import context as legacy
from rocell.application import static_simulation_context as module
from rocell.calibration.static_phase1_requirements import STATIC_OVERHEAD_PHASE1_GRAPH
from rocell.simulation._validation import SimulationSourceError
from rocell.simulation.scenario import load_simulation_scenario
from rocell.simulation.static_bundle import (
    STATIC_ARTIFACT_PATHS,
    STATIC_BUNDLE_ID,
    STATIC_BUNDLE_PATH,
    load_static_simulation_bundle,
)


WORKSPACE = Path(__file__).resolve().parents[3]
RECONCILIATION_PATH = (
    "software/ai/eval/static_simulation_bundle_002_reconciliation.json"
)


@pytest.fixture(autouse=True)
def no_process_or_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail(
            "Static context loading must not start a process or network connection"
        )

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)


@pytest.fixture
def workspace(tmp_path):
    manifest = json.loads(
        (WORKSPACE / STATIC_ARTIFACT_PATHS["system_manifest"]).read_text("utf-8")
    )
    support = json.loads(
        (WORKSPACE / STATIC_ARTIFACT_PATHS["support_design"]).read_text("utf-8")
    )
    paths = set(STATIC_ARTIFACT_PATHS.values()) | {STATIC_BUNDLE_PATH}
    paths.update(
        manifest["rc03"]["root"] + "/" + row["path"]
        for row in manifest["rc03"]["source_snapshot"]
    )
    paths.update(row["path"] for row in support["source_locks"].values())
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE / relative, target)
    return tmp_path


def test_static_route_preserves_all_robot_numerics_and_uses_existing_optics(workspace):
    context = module.load_static_simulation_context(workspace)
    original = load_simulation_scenario(workspace)
    changed_fields = {
        "source_profile_path",
        "source_profile_sha256",
        "target_profile_path",
        "overview",
    }
    for field in fields(original):
        if field.name not in changed_fields:
            assert getattr(original, field.name) == getattr(
                context.scenario, field.name
            ), field.name
    assert context.scenario.overview.camera == context.optical_contract.capture_camera()
    assert (
        context.scenario.overview.camera_T_board.matrix
        == context.nominal_projection.camera_T_board_row_major
    )
    assert context.scenario.overview.camera.optical_frame == "C_overhead_optical"
    assert context.scenario.overview.scenario_is_arm_mounted_camera is False
    assert (
        context.nominal_projection.entrance_pupil_z_board_mm == 1000.0
    )  # Existing nominal screening input, not installed measurement.
    assert context.scenario.source_profile_path == context.bundle.source_path
    assert context.scenario.source_profile_sha256 == context.bundle.source_sha256
    assert context.physical_authority is False
    assert context.bundle.physical_authority is False
    assert (
        len(context.targets.keyboard_targets),
        len(context.targets.phone_targets),
    ) == (46, 29)
    module.revalidate_static_simulation_context(context)


def test_static_bundle_002_retains_auditable_reconciliation_boundary():
    lock_path = WORKSPACE / STATIC_BUNDLE_PATH
    lock = json.loads(lock_path.read_text("utf-8"))
    record = json.loads((WORKSPACE / RECONCILIATION_PATH).read_text("utf-8"))

    assert STATIC_BUNDLE_ID == lock["bundle_id"] == record["active_boundary"][
        "bundle_id"
    ]
    assert hashlib.sha256(lock_path.read_bytes()).hexdigest() == record[
        "active_boundary"
    ]["lock_sha256"]
    manifest_path = WORKSPACE / lock["artifacts"]["system_manifest"]["path"]
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert manifest_sha256 == lock["artifacts"]["system_manifest"]["sha256"]
    assert manifest_sha256 == record["active_boundary"]["system_manifest_sha256"]
    assert record["unchanged_bundle_artifacts"] == {
        key: row["sha256"]
        for key, row in lock["artifacts"].items()
        if key not in record["bundle_artifact_delta"]
    }
    assert [row["json_path"] for row in record["manifest_delta_from_prior_boundary"]] == [
        "freeze_date",
        "manifest_id",
        "rc03.source_snapshot[14].sha256",
        "rc03.source_snapshot[15].sha256",
    ]
    assert record["classification"] == {
        "manifest_change": "FREEZE_IDENTITY_AND_STEP_00_PACKAGE_PROVENANCE_ONLY",
        "simulation_hardware_profile_change": "SYSTEM_MANIFEST_ID_BINDING_ONLY",
        "robot_numerical_geometry_changed": False,
        "target_catalog_changed": False,
        "camera_or_optical_contract_changed": False,
        "support_design_changed": False,
        "kinematic_model_changed": False,
        "arm_frame_contract_changed": False,
        "semantic_bindings_changed": False,
    }
    assert record["authority"] == {
        "simulation_only": True,
        "physical_authority": False,
        "physical_freeze_promoted": False,
        "model_promotion": False,
        "hardware_writes": 0,
        "physical_movements": 0,
    }


def test_static_graph_hashes_use_static_semantics_and_exact_context_roster(workspace):
    context = module.load_static_simulation_context(workspace)
    hashes = module.static_simulation_context_hashes(context)
    assert set(hashes) == set(STATIC_OVERHEAD_PHASE1_GRAPH.required_context_hash_ids)
    assert hashes["target_catalog"] == context.targets.content_sha256
    assert (
        hashes["keyboard_semantic_profile"]
        == context.targets.keyboard_semantic_profile_sha256
    )
    assert (
        hashes["phone_semantic_profile"]
        == context.targets.phone_semantic_profile_sha256
    )
    with pytest.raises(TypeError):
        hashes["system_manifest"] = "1" * 64


def test_static_loader_does_not_call_legacy_context_loader(workspace, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Static loading cannot relabel a legacy context")

    monkeypatch.setattr(legacy, "load_simulation_context", forbidden)
    context = module.load_static_simulation_context(workspace)
    with pytest.raises(TypeError):
        legacy.revalidate_simulation_context(context)


def test_graph_rehearsal_uses_static_context_and_does_not_install_artifacts(
    workspace, monkeypatch
):
    from rocell.application.static_phase1_calibration import (
        run_static_context_calibration_rehearsal,
    )
    from rocell.calibration import CalibrationRegistry

    def no_install(*args, **kwargs):
        pytest.fail("Rehearsal must not install nominal artifacts")

    monkeypatch.setattr(CalibrationRegistry, "install", no_install)
    context = module.load_static_simulation_context(workspace)
    result = run_static_context_calibration_rehearsal(context)
    assert result["bundle_sha256"] == context.bundle.source_sha256
    assert result["target_catalog_sha256"] == context.targets.content_sha256
    assert (
        result["physical_authority"]
        is result["installed_calibration_accepted"]
        is False
    )
    assert result["hardware_commands_generated"] == 0
    assert not (workspace / "software/calibrations").exists()
    assert result["rehearsal"]["synthetic_rehearsal"]["simulation_graph_verified"] is True
    assert result["rehearsal"]["physical_registry"]["blocked"] is True
    assert result["rehearsal"]["physical_registry"]["written"] is False


@pytest.mark.parametrize(
    "field",
    [
        "workspace",
        "manifest_path",
        "snapshot",
        "bundle",
        "scenario",
        "scene",
        "targets",
        "optical_contract",
        "nominal_projection",
    ],
)
def test_changed_context_field_is_rejected(workspace, field):
    context = module.load_static_simulation_context(workspace)
    replacement = workspace.parent if field == "workspace" else None
    with pytest.raises((TypeError, ValueError, OSError)):
        module.revalidate_static_simulation_context(
            replace(context, **{field: replacement})
        )


@pytest.mark.parametrize("source", list(STATIC_ARTIFACT_PATHS))
def test_drift_of_each_bound_file_rejects_revalidation(workspace, source):
    context = module.load_static_simulation_context(workspace)
    path = workspace / STATIC_ARTIFACT_PATHS[source]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(SimulationSourceError):
        module.revalidate_static_simulation_context(context)


@pytest.mark.parametrize(
    "fault",
    ["unknown-artifact", "path", "hash", "authority", "graph", "semantics", "missing"],
)
def test_static_lock_does_not_accept_mixed_or_changed_contract(workspace, fault):
    path = workspace / STATIC_BUNDLE_PATH
    data = json.loads(path.read_text("utf-8"))
    if fault == "unknown-artifact":
        data["artifacts"]["extra"] = data["artifacts"]["static_targets"]
    elif fault == "path":
        data["artifacts"]["static_targets"]["path"] = STATIC_ARTIFACT_PATHS[
            "legacy_geometry_seed"
        ]
    elif fault == "hash":
        data["artifacts"]["static_targets"]["sha256"] = "1" * 64
    elif fault == "authority":
        data["physical_authority"] = True
    elif fault == "graph":
        data["graph_sha256"] = "1" * 64
    elif fault == "semantics":
        data["semantic_bindings"]["keyboard"][
            "profile_id"
        ] = "development/keyboard-us-lowercase-semantic-v1"
    else:
        del data["artifacts"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SimulationSourceError):
        load_static_simulation_bundle(workspace)


def test_rehashed_changed_robot_seed_is_not_a_geometry_migration(workspace):
    seed_path = workspace / STATIC_ARTIFACT_PATHS["robot_numerical_seed"]
    seed_path.write_bytes(seed_path.read_bytes() + b" ")
    path = workspace / STATIC_BUNDLE_PATH
    data = json.loads(path.read_text("utf-8"))
    data["artifacts"]["robot_numerical_seed"]["sha256"] = hashlib.sha256(
        seed_path.read_bytes()
    ).hexdigest()
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SimulationSourceError, match="frozen numerical seed"):
        load_static_simulation_bundle(workspace)


@pytest.mark.parametrize(
    "relative",
    [
        STATIC_ARTIFACT_PATHS["kinematic_model"],
        "active-project/RoCell_v0_3/config/workcell_layout.json",
    ],
)
def test_late_direct_or_indirect_source_change_is_rejected(
    workspace, monkeypatch, relative
):
    actual = module.load_static_nominal_target_catalog

    def read_then_change(root):
        value = actual(root)
        path = root / relative
        path.write_bytes(path.read_bytes() + b" ")
        return value

    monkeypatch.setattr(module, "load_static_nominal_target_catalog", read_then_change)
    with pytest.raises((ValueError, RuntimeError)):
        module.load_static_simulation_context(workspace)
