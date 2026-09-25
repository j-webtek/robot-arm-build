from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from rocell.application.context import SimulationContextError, load_simulation_context
from rocell.application.model_motion_planner_gate import (
    evaluate_mapping,
    evaluate_model_motion_planner_gate,
)
from rocell.models import ModelMotionProposal


WORKSPACE = Path(__file__).resolve().parents[3]
MANIFEST = WORKSPACE / "software/config/system_manifest.json"


def proposal(**changes: object) -> dict[str, object]:
    document: dict[str, object] = {
        "schema": "rocell.model_motion_proposal.v1",
        "proposal_id": "keyboard-h-hover-001",
        "device": "keyboard",
        "target_id": "H",
        "coordinate_frame": "keyboard_local",
        "target_mm": {"x": 131.55, "y": 69.0, "z": 0.0},
        "interaction": "HOVER",
        "approach_clearance_mm": 25.0,
        "speed_class": "SLOW",
        "confidence": 0.98,
        "source": {
            "frame_id": "frame-001",
            "image_sha256": "a" * 64,
            "model_id": "candidate-model-v1",
        },
    }
    document.update(changes)
    return document


@pytest.fixture(scope="module")
def context():
    return load_simulation_context(WORKSPACE, MANIFEST)


def test_current_repository_fails_closed_at_missing_calibration(context) -> None:
    report = evaluate_model_motion_planner_gate(
        ModelMotionProposal.from_mapping(proposal()), context
    )

    assert report["status"] == "BLOCKED_CALIBRATION_MISSING_OR_STALE"
    assert report["model_motion_candidate"]["target_id"] == "H"
    assert report["model_motion_candidate"]["proposed_surface_target_board_mm"] == {
        "frame": "board", "x": 216.55, "y": 154.0, "z": 21.0
    }
    assert "MISSING_CALIBRATION:arm_board" in report["blockers"]
    assert "MISSING_CALIBRATION:controller_correlation" in report["blockers"]
    assert "STRICT_CALIBRATION_SNAPSHOT_DECODER_NOT_IMPLEMENTED" in report["blockers"]
    assert report["trajectory_candidate"] is None
    assert report["ik_executed"] is False
    assert report["route_screen_executed"] is False
    assert report["controller_commands"] == []
    assert report["hardware_commands_generated"] == 0
    assert report["hardware_access"] is False
    assert report["physical_authority"] is False


def test_gate_binds_candidate_catalog_build_frames_and_epochs(context) -> None:
    report = evaluate_model_motion_planner_gate(
        ModelMotionProposal.from_mapping(proposal()), context
    )
    bindings = report["source_bindings"]
    assert bindings["target_catalog_sha256"] == context.targets.content_sha256
    assert bindings["build_snapshot_sha256"] == context.snapshot.snapshot_hash
    assert bindings["kinematic_model_sha256"] == context.scenario.model_sha256
    assert len(bindings["arm_frame_contract_sha256"]) == 64
    assert len(bindings["configuration_epoch_policy_sha256"]) == 64
    assert len(report["calibration_status_sha256"]) == 64
    assert len(report["planner_gate_sha256"]) == 64


def test_mapping_entrypoint_is_deterministic() -> None:
    first = evaluate_mapping(proposal(), workspace=WORKSPACE)
    second = evaluate_mapping(proposal(), workspace=WORKSPACE)
    assert first == second


def test_bridge_rejection_occurs_before_planner_claim(context) -> None:
    outside = proposal(target_mm={"x": 260.0, "y": 69.0, "z": 0.0})
    with pytest.raises(ValueError, match="outside the named target"):
        evaluate_model_motion_planner_gate(
            ModelMotionProposal.from_mapping(outside), context
        )


def test_tampered_context_is_revalidated(context) -> None:
    tampered = replace(context, workspace=context.workspace.parent)
    with pytest.raises(SimulationContextError):
        evaluate_model_motion_planner_gate(
            ModelMotionProposal.from_mapping(proposal()), tampered
        )
