"""Offline comparison of immutable leg-8 and post-fault pose exports; no device access."""
import json
from pathlib import Path

from rocell.application.air_typing_campaign import TARGETS
from rocell.application.air_typing_r76_endpoint_rule import endpoint_joint_verified
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


LEG8 = "wizard-20260924T203329563829Z-01ca5eeb36ca45878d02ab7671643d36"
POSE = "wizard-20260924T221646916450Z-89afb8ef3c6041cdafa23e899c271bf3"
FAULT = "wizard-20260924T203339762923Z-c480bd69c444485fab0514416b8d5801"
STATUS = "wizard-20260924T203544393845Z-e1c183d31bd343c98202384153bcb3f9"


def review(root: Path) -> dict:
    exports = root / "runs/wizard-exports"
    for name in (LEG8, POSE, FAULT, STATUS):
        if not verify_export(exports / name)["valid"]:
            raise ValueError(f"Invalid source export: {name}")
    leg8 = json.loads((exports / LEG8 / "attachment-air-typing-assessment.json").read_text())
    pose = json.loads((exports / POSE / "attachment-pose-assessment.json").read_text())
    fault = json.loads((exports / FAULT / "attachment-air-typing-fault.json").read_text())
    if (leg8["leg"] != 8 or leg8["status"] != "LEG_ENDPOINT_VERIFIED"
            or pose["category"] != "STABLE_SAMPLED_POSE"
            or pose["origin"] != "DEVICE_CAPTURE"
            or fault["leg"] != 9 or fault["completed_legs"] != 8):
        raise ValueError("Source observations do not describe the expected stop")
    target = TARGETS[8]
    goals = [joint["last_goal"] for joint in pose["joints"]]
    positions = [joint["last_position"] for joint in pose["joints"]]
    if goals != list(target):
        raise ValueError("Captured goals do not match leg-nine targets")
    if not all(joint["position_span"] == 0 and joint["torque"] == 1
               and joint["controls_unchanged"] for joint in pose["joints"]):
        raise ValueError("Captured pose not stable and torque-on")
    joints = []
    for i in range(7):
        previous_goal = leg8["final_goals"][i]
        previous_position = leg8["final_positions"][i]
        command = target[i] - previous_goal
        travel = positions[i] - previous_position
        old_gate = (abs(command) < 4 or travel * (1 if command > 0 else -1) >= 2)
        new_gate = (endpoint_joint_verified(initial_goal=previous_goal,
                    initial_position=previous_position, target_goal=target[i],
                    final_position=positions[i]) if command else None)
        joints.append(dict(servo_id=11+i, previous_goal=previous_goal,
            previous_position=previous_position, target_goal=target[i],
            captured_position=positions[i], command_counts=command,
            observed_travel_counts=travel, target_error_counts=positions[i]-target[i],
            old_minimum_travel_gate=old_gate if command else None,
            proposed_r76_joint_gate=new_gate))
    return dict(schema="rocell.r75_leg9_offline_review.v1",
        source_exports=dict(leg8=LEG8, pose=POSE, fault=FAULT, status=STATUS),
        conclusion="POST_RESET_GOALS_MATCH_LEG9_AND_STABLE_POSITIONS_ARE_WITHIN_12_COUNTS",
        old_rule_rejects_servo_ids=[j["servo_id"] for j in joints if j["old_minimum_travel_gate"] is False],
        proposed_rule_all_selected_pass=all(j["proposed_r76_joint_gate"] is True
                                        for j in joints if j["command_counts"]),
        joints=joints,
        caveat="Post-reset capture is not a sample from the 10-second deadline; other transient causes cannot be excluded.",
        hardware_access=False, movement_sent=False,
        deployment_authorized=False, continuation_authorized=False)


def main():
    root = Path(__file__).resolve().parents[1]
    result = review(root)
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r75-leg9-offline-review"}, [], attachments={
        "r75-leg9-offline-review.json": canonical(result)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Review export invalid")
    print(json.dumps(dict(export_path=saved["path"], conclusion=result["conclusion"],
                          old_rule_rejects_servo_ids=result["old_rule_rejects_servo_ids"])))


if __name__ == "__main__":
    main()
