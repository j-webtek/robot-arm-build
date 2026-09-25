"""Export the fixed larger A-B-A air-typing hypothesis; no hardware access."""
import hashlib
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.local_air_typing_recipe import (
    SOURCE_GOALS, SOURCE_POSITIONS, plan_air_typing,
)
from rocell.application.p4_midpoint_scoring import score_exported_campaign
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


SUMMARY = "wizard-20260924T194534566569Z-9bccccf548084617b78cd5290a1482ef"
BOOT = "05b842d721c1ec3519d8a7bc7909b061"


def main():
    root = Path(__file__).resolve().parents[1]
    exports = root / "runs/wizard-exports"
    saved, _ = _read(exports, SUMMARY, "attachment-r74-p4-midpoint-summary.json")
    replayed = score_exported_campaign(exports, saved["source_exports"], boot=BOOT)
    if canonical(replayed) != canonical(saved) or saved["result"] != "LOCAL_SCREEN_PASS":
        raise ValueError("r74 source score differs from raw export replay")
    last, _ = _read(exports, saved["source_exports"][-1],
                    "attachment-p4-midpoint-assessment.json")
    if (tuple(last["final_positions"]) != SOURCE_POSITIONS or
            tuple(last["final_goals"]) != SOURCE_GOALS or last["leg"] != 16):
        raise ValueError("r74 source endpoint differs")
    report = plan_air_typing(root / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf")
    report.pop("report_sha256")
    report["source_campaign_export"] = SUMMARY
    report["source_last_leg_export"] = saved["source_exports"][-1]
    report["source_boot"] = BOOT
    report["report_sha256"] = hashlib.sha256(canonical(report)).hexdigest()
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    receipt = exporter.export({"mode": "offline-local-air-typing-recipe"}, [],
                              attachments={"local-air-typing-recipe.json": canonical(report)})
    if not verify_export(Path(receipt["path"]))["valid"]:
        raise ValueError("Recipe export invalid")
    print(json.dumps({"status": report["status"], "legs": len(report["legs"]),
                      "maximum_step_counts": max(max(abs(v) for v in row["goal_delta_counts"])
                                                 for row in report["legs"]),
                      "export": receipt["path"], "hardware_access": False,
                      "motion_authorized": False}))


if __name__ == "__main__":
    main()
