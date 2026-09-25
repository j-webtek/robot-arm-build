"""The post-loading B cycle is an offline, source-bound candidate only."""
from pathlib import Path

from rocell.application.ghost_typing_resume_preview import (
    B_CLEAR, B_DOWN, B_HOVER, SOURCE_GOALS, preview, review_source,
)

ROOT = Path(__file__).resolve().parents[2]


def test_verified_close_source_and_gripper_goal_are_preserved():
    assert len(review_source(ROOT / "runs/wizard-exports")) == 64
    assert SOURCE_GOALS[6] == B_CLEAR[6] == B_HOVER[6] == B_DOWN[6] == 1897


def test_five_leg_sweep_is_nonexecuting_and_unqualified():
    report = preview(ROOT / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf",
                     ROOT / "runs/wizard-exports")
    assert report["status"] == "OFFLINE_B_CYCLE_SWEEP_PASS_NOT_EXECUTABLE"
    assert len(report["legs"]) == 5
    assert [row["phase"] for row in report["legs"]] == [
        "B_CLEAR", "B_HOVER", "B_VIRTUAL_DOWN", "B_RETRACT", "B_CLEAR_FINAL"]
    assert all(row["goals"][6] == 1897 for row in report["legs"])
    assert not report["hardware_access"]
    assert not report["motion_authorized"]
    assert not report["stylus_retention_verified"]
    assert not report["physical_clearance_verified"]
