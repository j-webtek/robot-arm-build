from pathlib import Path

from rocell.application.local_air_typing_recipe import plan_air_typing


MODEL = Path(__file__).resolve().parents[2] / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf"


def test_larger_aba_recipe_is_finite_and_offline():
    plan = plan_air_typing(MODEL)
    assert plan == plan_air_typing(MODEL)
    assert plan["status"] == "OFFLINE_RECIPE_PASS_NOT_EXECUTABLE"
    assert len(plan["legs"]) == 17
    assert [row["name"] for row in plan["legs"][:4]] == [
        "LIFT_10", "LIFT_20", "LIFT_30", "A_TRAVEL"]
    assert [row["name"] for row in plan["legs"][-3:]] == [
        "A_RETURN_HOVER", "A_RETURN_PRESS", "A_RETURN_RETRACT"]
    assert max(abs(v) for row in plan["legs"] for v in row["goal_delta_counts"]) <= 80
    assert all(row["minimum_nonadjacent_proxy_distance_mm"] > 30 for row in plan["legs"])
    assert plan["hardware_access"] is False
    assert plan["motion_authorized"] is False
    assert plan["board_registered"] is False
    assert plan["installed_tool_offset_applied"] is False
