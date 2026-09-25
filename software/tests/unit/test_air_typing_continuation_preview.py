from pathlib import Path

from rocell.application.air_typing_campaign import TARGETS
from rocell.application.air_typing_continuation_preview import preview


MODEL = Path(__file__).resolve().parents[2] / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf"


def test_continuation_begins_at_captured_leg_nine_pose_and_is_inert():
    result = preview(MODEL)
    assert result["status"] == "OFFLINE_CONTINUATION_SWEEP_PASS_NOT_EXECUTABLE"
    assert result["source_goals"] == list(TARGETS[8])
    assert [row["original_leg"] for row in result["legs"]] == list(range(10, 18))
    assert [row["goals"] for row in result["legs"]] == [list(row) for row in TARGETS[9:]]
    assert all(row["maximum_goal_step_counts"] <= 80 for row in result["legs"])
    assert result["hardware_access"] is False
    assert result["motion_authorized"] is False
