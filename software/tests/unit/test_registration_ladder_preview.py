"""The r96 candidate is one model-only high-clear base leg."""
from pathlib import Path

from rocell.application.registration_ladder_preview import preview


ROOT = Path(__file__).resolve().parents[2]


def test_one_leg_registration_candidate_is_bounded_and_non_authoritative():
    result = preview(ROOT / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf")
    assert result["selected_joints"] == [0]
    assert result["base_step_counts"] == 60
    assert 16 < result["pinned_firmware_reference_displacement_mm"] < 19
    assert result["maximum_writes"] == 1
    assert not result["gripper_writes"]
    assert not result["return_movement"]
    assert not result["board_to_controller_verified"]
    assert not result["motion_authorized"]
