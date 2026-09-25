from pathlib import Path

from rocell.application.large_pose_ladder import plan_large_pose_ladder


MODEL = Path(__file__).resolve().parents[1] / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf"


def test_large_pose_ladder_lifts_then_relieves_elbow_with_bounded_steps():
    plan = plan_large_pose_ladder(MODEL)
    by_name = {pose["name"]: pose for pose in plan["poses"]}
    assert plan["release_sequence"] == ["P0", "T1", "P1", "P2", "P3", "T4", "P4"]
    assert plan["first_physical_candidate"] == "T1"
    assert by_name["T1"]["relative_tcp_height_gain_mm"] > 10
    assert by_name["P1"]["elbow_limit_margin_rad"] > by_name["P0"]["elbow_limit_margin_rad"]
    assert by_name["P4"]["relative_tcp_height_gain_mm"] > 35
    assert by_name["P4"]["hand_tcp_world_mm"][0] > by_name["P0"]["hand_tcp_world_mm"][0] + 20
    assert all(row["maximum_joint_delta_rad"] <= 0.1000001 for row in plan["transitions"])
    assert all(row["minimum_hand_tcp_world_z_mm"] > 5 for row in plan["transitions"])
    assert all(row["proxy_capsule_clearance_mm_at_15mm_radius"] > 20
               for row in plan["transitions"])
    assert plan["physical_clearance_verified"] is plan["movement_authorized"] is False


def test_pose_commands_preserve_shoulder_pair_sum_and_wire_range():
    plan = plan_large_pose_ladder(MODEL)
    for pose in plan["poses"]:
        goals = pose["command_goals"]
        assert goals[1] + goals[2] == 4114
        assert all(0 <= value <= 4095 for value in goals)
