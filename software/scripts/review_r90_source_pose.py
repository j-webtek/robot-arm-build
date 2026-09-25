"""Replay the r90 device pose and compare it to the reviewed A_CLEAR source."""

import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.ghost_key_multitarget_recipe import SOURCE_GOALS, SOURCE_POSITIONS
from rocell.application.pose_observation_export import replay_pose_observation
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


STARTUP = "wizard-20260925T120548177570Z-2509b8e33ac84d08a1f942fd1b6f5ac0"
CAPTURE = "wizard-20260925T120550111405Z-39d8a760eafe4ae5a01fa0832819d337"
ASSESSMENT = "wizard-20260925T120550061669Z-9ac8186080ac4fd3906eb16aa21b1c18"


def review(root: Path) -> dict:
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    startup, _ = _read(exports, STARTUP, "attachment-r90-pose-startup-preflight.json")
    capture, _ = _read(exports, CAPTURE, "attachment-pose-capture.json")
    replay = replay_pose_observation(exports, ASSESSMENT)
    assessed = replay["assessment"]
    if (startup.get("status") != "ROUTE_PRESENT_NO_RECORD"
            or capture.get("category") != "STABLE_SAMPLED_POSE"
            or capture.get("subject", {}).get("expected_boot") != startup.get("boot_id")
            or capture.get("subject", {}).get("expected_id") != "r90-pose-1"
            or capture.get("assessment_export_id") != ASSESSMENT
            or capture.get("retry_allowed") is not False
            or len(capture.get("responses", [])) != 5
            or assessed.get("category") != "STABLE_SAMPLED_POSE"
            or assessed.get("origin") != "DEVICE_CAPTURE"
            or assessed.get("physical_tip_accuracy_verified") is not False
            or replay.get("replay_verified") is not True):
        raise ValueError("Pinned r90 pose evidence differs")
    joints = assessed["joints"]
    if len(joints) != 7:
        raise ValueError("Seven servo observations required")
    rows = []
    for index, joint in enumerate(joints):
        expected_goal = SOURCE_GOALS[index]
        expected_position = SOURCE_POSITIONS[index]
        if (joint.get("servo_id") != 11 + index
                or joint.get("last_goal") != expected_goal
                or abs(joint.get("last_position", -10000) - expected_position) > 3
                or joint.get("position_span") != 0
                or joint.get("controls_unchanged") is not True
                or joint.get("torque") != 1):
            raise ValueError(f"Joint {11 + index} differs from reviewed A_CLEAR source")
        rows.append(dict(servo_id=11 + index, goal=joint["last_goal"],
                         position=joint["last_position"],
                         source_position_delta=joint["last_position"] - expected_position))
    return dict(schema="rocell.r90_source_pose_review.v1",
                status="A_CLEAR_JOINT_SOURCE_WINDOW_VERIFIED",
                boot_id=startup["boot_id"], joints=rows,
                position_tolerance_counts=3, stable_snapshot_count=3,
                pose_boot_claimed=True, same_boot_movement_allowed=False,
                physical_clearance_verified=False,
                physical_tip_accuracy_verified=False,
                progression_authority=False, movement_command_sent=False)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = review(root)
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r90-source-pose-review"}, [],
                            attachments={"r90-source-pose-review.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r90 source pose review export invalid")
    print(json.dumps(dict(report=report, export=saved["path"])))


if __name__ == "__main__":
    main()
