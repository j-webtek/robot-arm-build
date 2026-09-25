"""The next hover study remains bounded and non-executable."""
from pathlib import Path

from rocell.application.bare_gripper_hover_preview import (
    PHASES, SOURCE_GOALS, TARGETS, preview,
)


ROOT = Path(__file__).resolve().parents[2]


def test_two_region_hover_starts_at_verified_r94_pose_and_preserves_gripper():
    result = preview(ROOT / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf",
                     ROOT / "runs/wizard-exports")
    assert len(PHASES) == len(TARGETS) == len(result["legs"]) == 5
    assert result["source_goals"] == list(SOURCE_GOALS)
    assert all(row["goals"][6] == SOURCE_GOALS[6] for row in result["legs"])
    assert all(row["maximum_goal_step_counts"] <= 60 for row in result["legs"])
    assert min(row["minimum_modeled_tcp_z_mm"] for row in result["legs"]) > 75
    assert not result["motion_authorized"]
    assert not result["key_centers_registered_to_controller"]
    assert not result["physical_clearance_verified"]
