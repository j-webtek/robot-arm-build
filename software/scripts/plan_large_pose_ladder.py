"""Export the offline RoArm P0-P4 large-pose ladder; never contacts hardware."""
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.large_pose_ladder import plan_large_pose_ladder
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root = Path(__file__).resolve().parents[1]
    exports = (root / "runs/wizard-exports").resolve()
    plan = plan_large_pose_ladder(root / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf")
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({"mode": "large-pose-ladder-planning"}, [], attachments={
        "large-pose-ladder.json": canonical(plan)})
    if not verify_export(Path(saved["path"]).resolve())["valid"]:
        raise ValueError("Large pose ladder export invalid")
    print(json.dumps({"export_path": saved["path"], "first_candidate": "T1",
                      "poses": [{"name": p["name"], "tcp": p["hand_tcp_world_mm"],
                                 "height_gain": p["relative_tcp_height_gain_mm"],
                                 "elbow_margin_deg": p["elbow_limit_margin_rad"]*180/3.141592653589793}
                                for p in plan["poses"]],
                      "movement_authorized": False}))


if __name__ == "__main__": main()
