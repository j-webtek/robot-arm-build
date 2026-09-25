from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from rocell.application import load_simulation_context
from rocell.geometry import RigidTransform, Vec3
import rocell.simulation as simulation
from rocell.simulation import virtual_profile, virtual_workcell
from rocell.simulation.virtual_profile import (
    MAX_VIRTUAL_COMMISSIONING_PROFILE_BYTES,
    VIRTUAL_COMMISSIONING_PROFILE_STATUS,
    VirtualCommissioningProfileError,
    load_virtual_commissioning_profile,
    validate_virtual_commissioning_profile,
)


WORKSPACE = Path(__file__).resolve().parents[3]
PROFILE_PATH = WORKSPACE / "software/config/virtual_commissioning_profile.json"
MANIFEST_PATH = WORKSPACE / "software/config/system_manifest.json"


def test_virtual_modules_have_complete_package_import_surface() -> None:
    public_names = tuple(virtual_profile.__all__) + tuple(virtual_workcell.__all__)

    assert len(public_names) == len(set(public_names))
    assert len(simulation.__all__) == len(set(simulation.__all__))
    assert set(public_names) <= set(simulation.__all__)
    for module in (virtual_profile, virtual_workcell):
        for name in module.__all__:
            assert getattr(simulation, name) is getattr(module, name)


class _TestBundle:
    def __init__(self, bundle_id: str, path: Path, digest: str) -> None:
        self.bundle_id = bundle_id
        self._artifact = SimpleNamespace(path=path.resolve(), sha256=digest)

    def artifact(self, artifact_id: str) -> Any:
        if artifact_id != "virtual_commissioning_profile":
            raise KeyError(artifact_id)
        return self._artifact


def _canonical_context() -> Any:
    return load_simulation_context(WORKSPACE, MANIFEST_PATH)


def _write_document(path: Path, document: dict[str, Any]) -> str:
    payload = (json.dumps(document, indent=2, allow_nan=False) + "\n").encode("utf-8")
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _context_for_source(canonical: Any, path: Path, digest: str) -> Any:
    return SimpleNamespace(
        snapshot=canonical.snapshot,
        bundle_lock=_TestBundle(canonical.bundle_lock.bundle_id, path, digest),
        scenario=canonical.scenario,
        scene=canonical.scene,
    )


def _document() -> dict[str, Any]:
    value = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_locked_rank1_profile_reconstructs_exact_study_and_park() -> None:
    context = _canonical_context()
    profile = load_virtual_commissioning_profile(context)

    assert profile.status == VIRTUAL_COMMISSIONING_PROFILE_STATUS
    assert profile.simulation_only is True
    assert profile.physical_release_effect == "NONE"
    assert profile.can_authorize_hardware is False
    assert profile.study_input.study_input_id == "reach-944d7463f4c67905"
    assert profile.study_input.rear_clamp_contact_x_board_mm == 385.0
    assert profile.study_input.rear_edge_to_base_axis_y_mm == 75.0
    assert profile.study_input.base_yaw_board_rad == pytest.approx(
        -1.832595714594046,
        abs=1e-15,
    )
    assert profile.study_input.keyboard_tool_length_mm == 120.0
    assert profile.study_input.phone_tool_length_mm == 100.0
    assert (
        profile.park_point_board.x,
        profile.park_point_board.y,
        profile.park_point_board.z,
    ) == (290.0, 10.0, 70.0)
    assert profile.source_path == PROFILE_PATH.resolve()
    assert profile.source_sha256 == hashlib.sha256(PROFILE_PATH.read_bytes()).hexdigest()


def test_profile_rejects_unknown_fields_and_authority_drift(tmp_path: Path) -> None:
    canonical = _canonical_context()
    for name, mutate, message in (
        (
            "unknown",
            lambda value: value.__setitem__("unexpected", True),
            "fields differ",
        ),
        (
            "authority",
            lambda value: value["authority"].__setitem__(
                "live_hardware_access_allowed", True
            ),
            "zero authority",
        ),
        (
            "source",
            lambda value: value["selection"].__setitem__(
                "source_layout_report_hash", "0" * 64
            ),
            "source report identities",
        ),
    ):
        document = _document()
        mutate(document)
        path = tmp_path / f"{name}.json"
        digest = _write_document(path, document)
        context = _context_for_source(canonical, path, digest)
        with pytest.raises(VirtualCommissioningProfileError, match=message):
            load_virtual_commissioning_profile(context)


def test_profile_rejects_duplicate_keys_and_oversized_source(tmp_path: Path) -> None:
    canonical = _canonical_context()
    original = PROFILE_PATH.read_bytes()
    duplicate = original.replace(
        b'{\n  "schema":',
        b'{\n  "schema": "rocell.virtual_commissioning_profile.v1",\n  "schema":',
        1,
    )
    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_bytes(duplicate)
    duplicate_context = _context_for_source(
        canonical,
        duplicate_path,
        hashlib.sha256(duplicate).hexdigest(),
    )
    with pytest.raises(VirtualCommissioningProfileError, match="Duplicate JSON key"):
        load_virtual_commissioning_profile(duplicate_context)

    oversized = b"{" + b" " * MAX_VIRTUAL_COMMISSIONING_PROFILE_BYTES + b"}"
    oversized_path = tmp_path / "oversized.json"
    oversized_path.write_bytes(oversized)
    oversized_context = _context_for_source(
        canonical,
        oversized_path,
        hashlib.sha256(oversized).hexdigest(),
    )
    with pytest.raises(VirtualCommissioningProfileError, match="byte limit"):
        load_virtual_commissioning_profile(oversized_context)


def test_profile_rejects_content_id_and_urdf_transform_invariant_drift(
    tmp_path: Path,
) -> None:
    canonical = _canonical_context()

    changed_tool = _document()
    changed_tool["study_input"]["route_tool_lengths_mm"]["keyboard"] = 100.0
    tool_path = tmp_path / "changed-tool.json"
    tool_digest = _write_document(tool_path, changed_tool)
    with pytest.raises(VirtualCommissioningProfileError, match="content-derived identity"):
        load_virtual_commissioning_profile(
            _context_for_source(canonical, tool_path, tool_digest)
        )

    changed_transform = _document()
    changed_transform["study_input"]["derived_solver_transform"]["matrix_row_major"][11] = 1.0
    transform_path = tmp_path / "changed-transform.json"
    transform_digest = _write_document(transform_path, changed_transform)
    with pytest.raises(
        VirtualCommissioningProfileError,
        match=r"B_T_Ru \* inverse\(Wv_T_Ru\)",
    ):
        load_virtual_commissioning_profile(
            _context_for_source(canonical, transform_path, transform_digest)
        )


def test_typed_profile_revalidation_rejects_replaced_transform() -> None:
    context = _canonical_context()
    profile = load_virtual_commissioning_profile(context)
    study = profile.study_input
    invalid_solver_transform = RigidTransform(
        "board",
        "world",
        study.board_T_vendor_world.rotation,
        study.board_T_vendor_world.translation_mm + Vec3(0.0, 0.0, 1.0),
    )
    replaced_study = replace(
        study,
        board_T_vendor_world=invalid_solver_transform,
    )
    replaced_profile = replace(profile, study_input=replaced_study)

    with pytest.raises(
        VirtualCommissioningProfileError,
        match=r"B_T_Wv does not equal B_T_Ru",
    ):
        validate_virtual_commissioning_profile(replaced_profile, context)
