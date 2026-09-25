from __future__ import annotations

from pathlib import Path

import pytest

from rocell.application.model_motion_bridge import (
    ModelMotionBridgeError,
    compile_mapping,
    compile_model_motion_proposal,
)
from rocell.models import ModelMotionProposal, MotionProposalError, Point3Mm
from rocell.targets import load_nominal_target_catalog


@pytest.fixture
def workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def proposal(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "rocell.model_motion_proposal.v1",
        "proposal_id": "proposal-h-001",
        "device": "keyboard",
        "target_id": "H",
        "coordinate_frame": "keyboard_local",
        "target_mm": {"x": 131.55, "y": 69.0, "z": 0.0},
        "interaction": "HOVER",
        "approach_clearance_mm": 25.0,
        "speed_class": "SLOW",
        "confidence": 0.98,
        "source": {
            "model_id": "candidate-model-v1",
            "frame_id": "frame-001",
            "image_sha256": "a" * 64,
        },
    }
    value.update(overrides)
    return value


def test_keyboard_local_coordinate_compiles_to_nominal_board_candidate(
    workspace_root: Path,
) -> None:
    report = compile_mapping(proposal(), workspace=workspace_root)

    assert report["status"] == "ACCEPTED_OFFLINE_NOMINAL_REQUIRES_CALIBRATED_PLANNER"
    assert report["proposal_id"] == "proposal-h-001"
    assert report["proposed_surface_target_board_mm"] == {
        "frame": "board",
        "x": pytest.approx(216.55),
        "y": pytest.approx(154.0),
        "z": pytest.approx(21.0),
    }
    assert report["requested_waypoints"] == [
        {
            "phase": "HOVER_DESTINATION",
            "point_mm": {
                "frame": "board",
                "x": pytest.approx(216.55),
                "y": pytest.approx(154.0),
                "z": pytest.approx(46.0),
            },
        }
    ]
    assert report["controller_commands"] == []
    assert report["hardware_commands_generated"] == 0
    assert report["physical_authority"] is False


def test_contact_candidate_preserves_approach_contact_retract_order(
    workspace_root: Path,
) -> None:
    value = proposal(
        device="phone",
        target_id="key_h",
        coordinate_frame="phone_screen_local",
        target_mm={"x": 46.5, "y": 42.0, "z": 0.0},
        interaction="CONTACT",
    )
    report = compile_mapping(value, workspace=workspace_root)

    assert [row["phase"] for row in report["requested_waypoints"]] == [
        "APPROACH",
        "CONTACT_CANDIDATE",
        "RETRACT",
    ]
    assert report["proposed_surface_target_board_mm"]["x"] == pytest.approx(545.7)
    assert report["proposed_surface_target_board_mm"]["y"] == pytest.approx(126.2)
    assert report["proposed_surface_target_board_mm"]["z"] == pytest.approx(11.9)


def test_board_coordinate_is_accepted_when_inside_named_safe_region(
    workspace_root: Path,
) -> None:
    value = proposal(
        coordinate_frame="board",
        target_mm={"x": 217.0, "y": 154.5, "z": 21.0},
    )
    report = compile_mapping(value, workspace=workspace_root)
    assert report["nominal_delta_mm"] == {
        "x": pytest.approx(0.45),
        "y": pytest.approx(0.5),
        "z": pytest.approx(0.0),
    }


def test_coordinate_outside_named_region_is_rejected(workspace_root: Path) -> None:
    value = proposal(target_mm={"x": 160.0, "y": 69.0, "z": 0.0})
    with pytest.raises(ModelMotionBridgeError, match="outside"):
        compile_mapping(value, workspace=workspace_root)


def test_wrong_surface_plane_is_rejected(workspace_root: Path) -> None:
    value = proposal(target_mm={"x": 131.55, "y": 69.0, "z": 5.0})
    with pytest.raises(ModelMotionBridgeError, match="surface plane"):
        compile_mapping(value, workspace=workspace_root)


def test_low_confidence_is_rejected(workspace_root: Path) -> None:
    value = proposal(confidence=0.5)
    with pytest.raises(ModelMotionBridgeError, match="below"):
        compile_mapping(value, workspace=workspace_root)


def test_device_frame_mismatch_is_rejected() -> None:
    value = proposal(device="phone")
    with pytest.raises(MotionProposalError, match="incompatible"):
        ModelMotionProposal.from_mapping(value)


def test_extra_wire_command_field_is_rejected() -> None:
    value = proposal(controller_command={"T": 102})
    with pytest.raises(MotionProposalError, match="exactly"):
        ModelMotionProposal.from_mapping(value)


def test_catalog_local_projection_is_explicitly_nominal(workspace_root: Path) -> None:
    catalog = load_nominal_target_catalog(workspace_root)
    board = catalog.local_to_board(
        Point3Mm("keyboard_local", 36.3, 69.0, 0.0),
        device="keyboard",
    )
    assert board == Point3Mm("board", 121.3, 154.0, 21.0)
    assert catalog.simulation_only is True


def test_candidate_hash_is_deterministic(workspace_root: Path) -> None:
    parsed = ModelMotionProposal.from_mapping(proposal())
    catalog = load_nominal_target_catalog(workspace_root)
    first = compile_model_motion_proposal(parsed, catalog)
    second = compile_model_motion_proposal(parsed, catalog)
    assert first == second
    assert len(first["candidate_sha256"]) == 64
