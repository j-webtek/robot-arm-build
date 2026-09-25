from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from rocell.rc03.build_snapshot import Capability, assess_capability, project_capabilities
from rocell.rc03.importer import BuildImportError, import_build_snapshot
from rocell.rc03.integrity import BuildIntegrityError, sha256_file


def _write_json(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _workspace(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "active-project" / "RoCell_v0_3"
    files = {
        "config/measurement_record.json": {
            "design_revision": "RC03-TEST",
            "selected_routes": {
                "keyboard_rod_route": True,
                "phone_stylus_route": True,
            },
            "gates": {"physical_gate": {"status": "NOT_TESTED"}},
        },
        "fiducials/apriltag_map.json": {
            "design_revision": "RC03-TEST",
            "coordinate_source": "nominal_layout",
        },
        "BUILD_BY_STEP/ACTIVE_BUILD.json": {"active_build_id": None},
    }
    for relative, document in files.items():
        _write_json(root / relative, document)
    snapshot = [
        {"path": relative, "sha256": sha256_file(root / relative)} for relative in files
    ]
    manifest = {
        "manifest_id": "freeze-test",
        "rc03": {
            "root": "active-project/RoCell_v0_3",
            "design_revision": "RC03-TEST",
            "physical_release_status": "UNRELEASED",
            "active_build_id": None,
            "source_snapshot": snapshot,
        },
        "mission_routes": {
            "keyboard_rod_route": {"selected": True},
            "phone_stylus_route": {"selected": True},
        },
        "hardware": {
            "camera": {"exact_model": None, "state": "OPEN_BLOCKING"},
        },
        "fiducials": {"coordinate_source": "nominal_layout"},
        "current_build_state": {
            "safe_to_power_robot": False,
            "contact_enabled": False,
        },
        "hard_blockers": ["ACTIVE_BUILD_ID_NULL"],
    }
    manifest_path = tmp_path / "software" / "config" / "system_manifest.json"
    _write_json(manifest_path, manifest)
    return tmp_path, manifest_path


def test_import_build_snapshot_preserves_blocked_state(tmp_path: Path) -> None:
    workspace, manifest_path = _workspace(tmp_path)
    snapshot = import_build_snapshot(workspace, manifest_path)
    assert snapshot.integrity_verified
    assert snapshot.active_build_id is None
    assert snapshot.gate_statuses["physical_gate"] == "NOT_TESTED"
    assert assess_capability(snapshot, Capability.DIGITAL_PLAN).allowed
    assert assess_capability(snapshot, Capability.SIMULATED_DRY_RUN).allowed
    for capability in (
        Capability.CAMERA_CAPTURE,
        Capability.ARM_FEEDBACK,
        Capability.EMPTY_CELL_MOTION,
        Capability.KEYBOARD_CONTACT,
        Capability.PHONE_CONTACT,
    ):
        assert not assess_capability(snapshot, capability).allowed


def test_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    workspace, manifest_path = _workspace(tmp_path)
    measurement = workspace / "active-project" / "RoCell_v0_3" / "config" / "measurement_record.json"
    measurement.write_text("{}\n", encoding="utf-8")
    with pytest.raises(BuildIntegrityError):
        import_build_snapshot(workspace, manifest_path)


def test_route_disagreement_is_an_import_error(tmp_path: Path) -> None:
    workspace, manifest_path = _workspace(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["mission_routes"]["keyboard_rod_route"]["selected"] = False
    _write_json(manifest_path, manifest)
    with pytest.raises(BuildImportError, match="Route keyboard_rod_route"):
        import_build_snapshot(workspace, manifest_path)


def test_manifest_must_remain_beneath_selected_workspace(tmp_path: Path) -> None:
    workspace, manifest_path = _workspace(tmp_path / "outside")
    different_workspace = tmp_path / "selected-workspace"
    different_workspace.mkdir()

    with pytest.raises(BuildIntegrityError, match="manifest escapes"):
        import_build_snapshot(different_workspace, manifest_path)


@pytest.mark.parametrize("invalid", ("ONE_STRING", [""], [1], None))
def test_hard_blockers_must_be_an_array_of_nonempty_strings(
    tmp_path: Path,
    invalid: object,
) -> None:
    workspace, manifest_path = _workspace(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["hard_blockers"] = invalid
    _write_json(manifest_path, manifest)

    with pytest.raises(BuildImportError, match="hard_blockers"):
        import_build_snapshot(workspace, manifest_path)


def test_capability_projection_is_complete(blocked_snapshot: object) -> None:
    projected = project_capabilities(blocked_snapshot)  # type: ignore[arg-type]
    assert set(projected) == set(Capability)
    assert projected[Capability.DIGITAL_PLAN].allowed
    assert not projected[Capability.KEYBOARD_CONTACT].allowed


def test_released_fixture_allows_contact(released_snapshot: object) -> None:
    assessment = assess_capability(released_snapshot, Capability.KEYBOARD_CONTACT)  # type: ignore[arg-type]
    assert assessment.allowed
    assert assessment.reasons == ()


@pytest.mark.parametrize(
    "camera_state",
    ("PENDING_REVIEW", "PASS", "qualified_pending", "UNRECOGNIZED"),
)
def test_camera_capture_fails_closed_for_every_nonqualified_state(
    released_snapshot: object,
    camera_state: str,
) -> None:
    snapshot = replace(released_snapshot, camera_state=camera_state)  # type: ignore[arg-type]

    assessment = assess_capability(snapshot, Capability.CAMERA_CAPTURE)

    assert assessment.allowed is False
    assert "CAMERA_NOT_QUALIFIED" in assessment.reasons


def test_camera_state_cannot_be_empty(released_snapshot: object) -> None:
    with pytest.raises(ValueError, match="camera_state"):
        replace(released_snapshot, camera_state=" ")  # type: ignore[arg-type]
