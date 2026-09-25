"""Read-only preflight, then optionally run the one-use r91 noncontact cycle.

The catch must be outside the swept path and the board/cables clear before
--authorized-a-cycle is supplied. The controller independently samples its
source pose before any servo write. Do not use the pose-capture route on the
movement boot: it exclusively reserves that boot. This launcher never retries.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re

from observe_r33_campaign import load_reviewed_key
from run_r90_pose_observation import get
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.reviewed_hover_recovery_live_host import (
    R91_APP_SHA, R91_RELEASE_SHA, ReviewedHoverRecoveryLiveHost,
)
from rocell.application.wizard_diagnostic_export import (
    WizardDiagnosticExporter, verify_export,
)


BOOT = "2adaa8657729046162db3a8c403a9654"
POSE_EXPORT = "wizard-20260925T134630545997Z-385394bdb89646b7b5d116a842cd1d84"
CAPTURE_EXPORT = "wizard-20260925T134630624259Z-8b0d17ae6d4e4ef68015679330075518"
GOALS = [2047, 2093, 2021, 2618, 2197, 2040, 2047]
JOURNAL_STAGES = ["RESERVED", "IDENTITY_AND_PREWRITE_VERIFIED",
                  "WRITE_ATTEMPT_STARTED", "FLASH_VERIFIED",
                  "ONE_STARTUP_ATTEMPT", "STARTUP_RESET_SENT"]


def preflight(root: Path, address: str) -> dict:
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    journal = (root / "private-backups/controller-20260918-session1"
               / "app-r91-deployment-events.jsonl")
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    if ([row.get("stage") for row in rows] != JOURNAL_STAGES or
            rows[0].get("app_sha256") != R91_APP_SHA or
            rows[0].get("release_sha256") != R91_RELEASE_SHA or
            rows[0].get("offset") != 0x10000 or
            rows[1].get("mac") != "fc:e8:c0:f8:d5:38" or
            rows[3].get("app_sha256") != R91_APP_SHA or
            rows[3].get("protected_regions_unchanged") is not True or
            rows[5].get("application_health_verified") is not False):
        raise ValueError("Exact one-use r91 installation journal required")
    assessed, _ = _read(exports, POSE_EXPORT, "attachment-pose-assessment.json")
    capture, _ = _read(exports, CAPTURE_EXPORT, "attachment-pose-capture.json")
    if type(assessed) is not dict or type(capture) is not dict:
        raise ValueError("Post-install pose evidence must be objects")
    joints = assessed.get("joints")
    if (assessed.get("category") != "STABLE_SAMPLED_POSE" or
            assessed.get("origin") != "DEVICE_CAPTURE" or
            assessed.get("physical_tip_accuracy_verified") is not False or
            type(joints) is not list or len(joints) != 7 or
            capture.get("category") != "STABLE_SAMPLED_POSE" or
            capture.get("subject") != dict(expected_boot=BOOT,
                                            expected_id="r91-postinstall-1") or
            capture.get("assessment_export_id") != POSE_EXPORT or
            len(capture.get("responses", [])) != 5):
        raise ValueError("Post-install pose evidence differs")
    for index, joint in enumerate(joints):
        if (joint.get("servo_id") != 11 + index or
                joint.get("last_goal") != GOALS[index] or
                type(joint.get("last_position")) is not int or
                abs(joint["last_position"] - GOALS[index]) > 12 or
                joint.get("torque") != 1 or
                joint.get("controls_unchanged") is not True or
                joint.get("position_span") != 0):
            raise ValueError("Post-install joint/source evidence differs")
    status, raw = get(address, "/rocell/recovery-hover/capabilities", 512)
    if status != 200:
        raise ValueError("r91 capabilities unavailable")
    caps = json.loads(raw)
    if (type(caps) is not dict or set(caps) != {
            "schema", "boot_id", "live_release_available", "motion_authorized",
            "maximum_legs", "stamped_release_sha256"} or
            caps["schema"] != "rocell.reviewed_hover_recovery_capabilities.v1" or
            type(caps["boot_id"]) is not str or
            re.fullmatch(r"[0-9a-f]{32}", caps["boot_id"]) is None or
            caps["boot_id"] == "0" * 32 or
            caps["stamped_release_sha256"] != R91_RELEASE_SHA or
            caps["live_release_available"] is not True or
            caps["motion_authorized"] is not False or
            caps["maximum_legs"] != 5):
        raise ValueError("Current r91 boot/release differs")
    boot = caps["boot_id"]
    if boot == BOOT or (exports / f"pose-observation-{boot}.json").exists():
        raise ValueError("Movement boot already reserved by pose observation")
    if (exports / f"recovery-hover-live-{boot}.json").exists():
        raise ValueError("This r91 boot is already claimed")
    return dict(schema="rocell.r91_recovery_live_preflight.v1",
                status="READY_FOR_PHYSICAL_CLEARANCE_CONFIRMATION",
                boot_id=boot, release_sha256=R91_RELEASE_SHA,
                app_sha256=R91_APP_SHA,
                install_journal_sha256=hashlib.sha256(journal.read_bytes()).hexdigest(),
                pose_export_id=POSE_EXPORT, capture_export_id=CAPTURE_EXPORT,
                prior_pose_stable=True, current_source_recheck_required=True,
                physical_clearance_verified=False, movement_command_sent=False)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", default="192.168.0.225")
    parser.add_argument("--authorized-a-cycle", action="store_true")
    parser.add_argument("--catch-outside-swept-path", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    report = preflight(root, args.address)
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r91-recovery-live-preflight"}, [],
                            attachments={"r91-recovery-live-preflight.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r91 live preflight export invalid")
    if not args.authorized_a_cycle:
        print(json.dumps(dict(report=report, export=saved["path"],
                              status="PREFLIGHT_ONLY_NO_MOVEMENT")))
        return
    if not args.catch_outside_swept_path:
        raise ValueError("Physical catch/path clearance confirmation required")
    key = load_reviewed_key(root)
    client = CharacterizationHTTP(args.address, key=key, boot=report["boot_id"],
        recovery_hover_live_release_sha256=R91_RELEASE_SHA)
    host = ReviewedHoverRecoveryLiveHost(client, boot=report["boot_id"],
        export_root=root / "runs/wizard-exports",
        authorize_noncontact_motion=True)
    print(json.dumps(host.run_once()))


if __name__ == "__main__":
    main()
