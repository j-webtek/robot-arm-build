from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from rocell.application.collision_readiness import assess_current_collision_readiness
from rocell.application.context import load_simulation_context
from rocell.application.installed_collision_geometry import (
    InstalledCollisionGeometryError,
    load_installed_collision_geometry_for_context,
    load_installed_collision_geometry_profile,
)
from rocell.simulation.collision import CollisionBindingMode


WORKSPACE = Path(__file__).resolve().parents[3]
MANIFEST = WORKSPACE / "software/config/system_manifest.json"
SOURCE_HASH = "a" * 64


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _fixture() -> tuple[Any, dict[str, Any]]:
    context = load_simulation_context(WORKSPACE, MANIFEST)
    readiness = assess_current_collision_readiness(context)
    bodies = []
    for requirement in readiness.contract.requirements:
        primitives = []
        if requirement.binding_mode is not CollisionBindingMode.CONFIGURATION_SAMPLED:
            primitives = [
                {
                    "kind": "sphere",
                    # Negative local coordinates are intentional: link-frame geometry
                    # must not be restricted to the positive octant.
                    "center_mm": [-1.0, 0.0, 1.0],
                    "radius_mm": 1.0,
                }
            ]
        bodies.append(
            {
                "body_id": requirement.body_id,
                "parent_frame": requirement.parent_frame,
                "role": requirement.role.value,
                "binding_mode": requirement.binding_mode.value,
                "evidence_state": "ACCEPTED_MEASURED",
                "source_reference": "unit-test metrology fixture",
                "primitives": primitives,
            }
        )
    document: dict[str, Any] = {
        "schema": "rocell.installed_collision_geometry_profile.v1",
        "profile_id": "installed-collision-unit-test-v1",
        "manifest_id": readiness.manifest_id,
        "manifest_sha256": readiness.manifest_sha256,
        "active_build_id": readiness.active_build_id,
        "build_snapshot_sha256": readiness.build_snapshot_hash,
        "robot_model_sha256": readiness.urdf_sha256,
        "base_contract_sha256": readiness.contract.content_hash,
        "source_bindings": {"metrology_fixture": SOURCE_HASH},
        "bodies": bodies,
        "pair_exclusions": [],
        "clearance_policy": {
            "minimum_separation_mm": 2.0,
            "geometry_uncertainty_mm_per_body": 0.5,
            "pose_uncertainty_mm_per_body": 0.5,
            "evidence_state": "ACCEPTED_MEASURED",
            "source_reference": "unit-test clearance fixture",
        },
    }
    document["content_sha256"] = hashlib.sha256(_canonical(document)).hexdigest()
    return readiness, document


def _write(tmp_path: Path, document: dict[str, Any]) -> tuple[Path, str]:
    payload = _canonical(document)
    path = tmp_path / "installed_collision_geometry.json"
    path.write_bytes(payload)
    return path, hashlib.sha256(payload).hexdigest()


def _load(tmp_path: Path, document: dict[str, Any]):
    readiness, _ = _fixture()
    path, file_hash = _write(tmp_path, document)
    return load_installed_collision_geometry_profile(
        path,
        file_hash,
        base_contract=readiness.contract,
        expected_manifest_id=readiness.manifest_id,
        expected_manifest_sha256=readiness.manifest_sha256,
        expected_active_build_id=readiness.active_build_id,
        expected_build_snapshot_sha256=readiness.build_snapshot_hash,
        expected_robot_model_sha256=readiness.urdf_sha256,
        expected_source_bindings={"metrology_fixture": SOURCE_HASH},
    )


def test_loads_exact_hash_bound_measured_profile_without_conferring_authority(
    tmp_path: Path,
) -> None:
    readiness, document = _fixture()
    path, file_hash = _write(tmp_path, document)

    context = load_simulation_context(WORKSPACE, MANIFEST)
    profile = load_installed_collision_geometry_for_context(
        path,
        file_hash,
        context=context,
        expected_source_bindings={"metrology_fixture": SOURCE_HASH},
    )

    audit = profile.to_dict()["geometry_audit"]
    assert audit["diagnostic_ready"] is True
    assert audit["physical_geometry_complete"] is False
    assert audit["configuration_sampled_body_ids"] == [
        "attachment:moving_camera_cable"
    ]
    assert profile.contract.bodies_by_id["robot:base_link"].primitives[0].center_mm.x == -1.0
    assert profile.to_dict()["hardware_commands_generated"] == 0
    assert profile.to_dict()["physical_authority"] is False


def test_rejects_wrong_file_hash_before_decoding(tmp_path: Path) -> None:
    readiness, document = _fixture()
    path, _ = _write(tmp_path, document)
    with pytest.raises(InstalledCollisionGeometryError, match="file hash mismatch"):
        load_installed_collision_geometry_profile(
            path,
            "0" * 64,
            base_contract=readiness.contract,
            expected_manifest_id=readiness.manifest_id,
            expected_manifest_sha256=readiness.manifest_sha256,
            expected_active_build_id=readiness.active_build_id,
            expected_build_snapshot_sha256=readiness.build_snapshot_hash,
            expected_robot_model_sha256=readiness.urdf_sha256,
            expected_source_bindings={"metrology_fixture": SOURCE_HASH},
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda document: document["bodies"].pop(), "body coverage is incomplete"),
        (
            lambda document: document["bodies"][0].update(
                evidence_state="SYNTHETIC_TEST_ONLY"
            ),
            "must use ACCEPTED_MEASURED",
        ),
        (
            lambda document: next(
                body
                for body in document["bodies"]
                if body["binding_mode"] == "CONFIGURATION_SAMPLED"
            )["primitives"].append(
                {"kind": "sphere", "center_mm": [0, 0, 0], "radius_mm": 1}
            ),
            "must provide geometry per pose",
        ),
    ],
)
def test_rejects_incomplete_or_misrepresented_geometry(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    _, document = _fixture()
    mutation(document)
    document["content_sha256"] = hashlib.sha256(
        _canonical({key: value for key, value in document.items() if key != "content_sha256"})
    ).hexdigest()
    with pytest.raises(InstalledCollisionGeometryError, match=message):
        _load(tmp_path, document)


def test_rejects_content_tamper_even_when_caller_rehashes_file(tmp_path: Path) -> None:
    readiness, document = _fixture()
    document["clearance_policy"]["minimum_separation_mm"] = 9.0
    path, file_hash = _write(tmp_path, document)

    with pytest.raises(InstalledCollisionGeometryError, match="content hash mismatch"):
        load_installed_collision_geometry_profile(
            path,
            file_hash,
            base_contract=readiness.contract,
            expected_manifest_id=readiness.manifest_id,
            expected_manifest_sha256=readiness.manifest_sha256,
            expected_active_build_id=readiness.active_build_id,
            expected_build_snapshot_sha256=readiness.build_snapshot_hash,
            expected_robot_model_sha256=readiness.urdf_sha256,
            expected_source_bindings={"metrology_fixture": SOURCE_HASH},
        )


def test_rejects_unexpected_measurement_source_hash(tmp_path: Path) -> None:
    readiness, document = _fixture()
    path, file_hash = _write(tmp_path, document)
    with pytest.raises(InstalledCollisionGeometryError, match="source binding hashes"):
        load_installed_collision_geometry_profile(
            path,
            file_hash,
            base_contract=readiness.contract,
            expected_manifest_id=readiness.manifest_id,
            expected_manifest_sha256=readiness.manifest_sha256,
            expected_active_build_id=readiness.active_build_id,
            expected_build_snapshot_sha256=readiness.build_snapshot_hash,
            expected_robot_model_sha256=readiness.urdf_sha256,
            expected_source_bindings={"metrology_fixture": "b" * 64},
        )
