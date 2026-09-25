"""Review the verified r74 endpoint against a local virtual A-B-A row, offline."""
import argparse
import hashlib
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.local_p4_ghost_preview import EXPECTED_SOURCE, preview_local_p4_ghost
from rocell.application.p4_midpoint_scoring import score_exported_campaign
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R74_SUMMARY = "wizard-20260924T194534566569Z-9bccccf548084617b78cd5290a1482ef"
R74_BOOT = "05b842d721c1ec3519d8a7bc7909b061"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-export", default=R74_SUMMARY)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    exports = root / "runs/wizard-exports"
    saved, _ = _read(exports, args.summary_export, "attachment-r74-p4-midpoint-summary.json")
    if (saved.get("source_kind") != "controller_feedback" or
            saved.get("result") != "LOCAL_SCREEN_PASS" or
            saved.get("verified_legs") != 16):
        raise ValueError("Verified physical r74 midpoint source required")
    reviewed = score_exported_campaign(exports, saved["source_exports"], boot=R74_BOOT)
    if canonical(saved) != canonical(reviewed):
        raise ValueError("Saved score differs from independently replayed records")
    last, _ = _read(exports, saved["source_exports"][-1],
                    "attachment-p4-midpoint-assessment.json")
    if (last["leg"] != 16 or last["status"] != "LEG_ENDPOINT_VERIFIED" or
            tuple(last["final_positions"]) != EXPECTED_SOURCE):
        raise ValueError("Unexpected P4 source endpoint")
    report = preview_local_p4_ghost(last["final_positions"],
                                    root / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf")
    report["source_campaign_export"] = args.summary_export
    report["source_last_leg_export"] = saved["source_exports"][-1]
    report["source_boot"] = R74_BOOT
    report.pop("report_sha256")
    report["report_sha256"] = hashlib.sha256(canonical(report)).hexdigest()
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    receipt = exporter.export({"mode": "offline-local-p4-ghost-preview"}, [],
                              attachments={"local-p4-ghost-preview.json": canonical(report)})
    if not verify_export(Path(receipt["path"]))["valid"]:
        raise ValueError("Preview export invalid")
    print(json.dumps({"status": report["status"], "legs": len(report["legs"]),
                      "source_export": args.summary_export, "export": receipt["path"],
                      "hardware_access": False, "motion_authorized": False}))


if __name__ == "__main__":
    main()
