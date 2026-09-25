"""Offline/read-only r91 installation preflight. Never flashes, resets, or moves."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.reviewed_hover_recovery_live_host import (
    R91_APP_SHA, R91_RELEASE_SHA,
)
from rocell.application.reviewed_hover_live_host import R90_APP_SHA, R90_RELEASE_SHA
from rocell.application.wizard_diagnostic_export import (
    WizardDiagnosticExporter, verify_export,
)
from rocell.providers.windows.diagnostic_image_store import load_image

if __package__:
    from .review_r91_hover_recovery_candidate import review
    from .run_r90_pose_observation import get
else:
    from review_r91_hover_recovery_candidate import review
    from run_r90_pose_observation import get


REVIEW_EXPORT = "wizard-20260925T132443178692Z-90971789a3914b20852c44a0f0f1920c"
BACKUP_SHA = "d9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9"
FILESYSTEM_SHA = "45320bab56ec1d8e889078a50e2aa0ef79d4d65c59e5dcb89c7a7880f08e7267"


def preflight(root: Path, address: str | None = None) -> dict:
    root = Path(root).resolve()
    reviewed = review(root)
    saved, _ = _read(root / "runs/wizard-exports", REVIEW_EXPORT,
                     "attachment-r91-hover-recovery-candidate-review.json")
    if (saved != reviewed or reviewed["app_sha256"] != R91_APP_SHA or
            reviewed["release_sha256"] != R91_RELEASE_SHA or
            reviewed["predecessor_app_sha256"] != R90_APP_SHA):
        raise ValueError("r91 reviewed image or release differs")
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    private = root / "private-backups/controller-20260918-session1"
    journal = private / "app-r90-deployment-events.jsonl"
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    if ([row.get("stage") for row in rows] != [
            "RESERVED", "IDENTITY_AND_PREWRITE_VERIFIED", "WRITE_ATTEMPT_STARTED",
            "FLASH_VERIFIED", "ONE_STARTUP_ATTEMPT", "STARTUP_RESET_SENT"] or
            rows[0].get("app_sha256") != R90_APP_SHA or
            rows[0].get("release_sha256") != R90_RELEASE_SHA or
            rows[0].get("offset") != 0x10000 or
            rows[1].get("mac") != "fc:e8:c0:f8:d5:38" or
            rows[3].get("app_sha256") != R90_APP_SHA or
            rows[3].get("protected_regions_unchanged") is not True or
            (private / "app-r91-deployment-events.jsonl").exists()):
        raise ValueError("r90 installed journal or r91 attempt state differs")
    backup_a = (private / "flash-pair-a.bin").read_bytes()
    backup_b = (private / "flash-pair-b.bin").read_bytes()
    filesystem = load_image(private / "observed-pose-plus10-candidate.dpapi")
    if (len(backup_a) != 0x400000 or sha(backup_a) != BACKUP_SHA or
            backup_b != backup_a or len(filesystem) != 0x160000 or
            sha(filesystem) != FILESYSTEM_SHA):
        raise ValueError("Protected full-flash/filesystem backup differs")
    report = dict(schema="rocell.r91_hover_recovery_install_preflight.v1",
                  status="LOCAL_EVIDENCE_VERIFIED_NOT_AUTHORIZED",
                  app_sha256=R91_APP_SHA, release_sha256=R91_RELEASE_SHA,
                  predecessor_app_sha256=R90_APP_SHA,
                  predecessor_release_sha256=R90_RELEASE_SHA,
                  app_offset=0x10000, app_bytes=reviewed["app_bytes"],
                  app_slot_bytes=0x140000,
                  protected_regions=[[0, 0x10000], [0x150000, 0x2b0000]],
                  original_full_backup_verified=True,
                  protected_filesystem_snapshot_verified=True,
                  predecessor_install_journal_verified=True,
                  predecessor_live_readback_verified_now=False,
                  current_device_checked=False, boot_id=None,
                  current_boot_consumed=None, hardware_access=False,
                  firmware_uploaded=False, startup_performed=False,
                  movement_command_sent=False, deployment_authorized=False,
                  torque_loss_support_verified=False,
                  source_pose_after_startup_verified=False)
    if address is not None:
        status, raw = get(address, "/rocell/reviewed-hover/capabilities", 512)
        if status != 200:
            raise ValueError("Current r90 capabilities unavailable")
        caps = json.loads(raw)
        boot = caps.get("boot_id") if type(caps) is dict else None
        if (type(caps) is not dict or set(caps) != {
                "schema", "boot_id", "live_release_available", "motion_authorized",
                "maximum_legs", "stamped_release_sha256"} or
                caps["schema"] != "rocell.reviewed_hover_capabilities.v1" or
                caps["stamped_release_sha256"] != R90_RELEASE_SHA or
                caps["live_release_available"] is not True or
                caps["motion_authorized"] is not False or
                caps["maximum_legs"] != 16 or type(boot) is not str or
                not re.fullmatch(r"[0-9a-f]{32}", boot) or boot == "0" * 32):
            raise ValueError("Current r90 release/boot differs")
        exports = root / "runs/wizard-exports"
        report.update(status="READ_ONLY_DEVICE_IDENTITY_VERIFIED_NOT_AUTHORIZED",
                      current_device_checked=True, boot_id=boot,
                      current_boot_consumed=(exports / f"reviewed-hover-live-{boot}.json").exists(),
                      hardware_access="public_capabilities_get_only")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--local-only", action="store_true")
    mode.add_argument("--read-current-device", action="store_true")
    parser.add_argument("--address", default="192.168.0.225")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = preflight(root, args.address if args.read_current_device else None)
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r91-hover-recovery-install-preflight"}, [],
        attachments={"r91-hover-recovery-install-preflight.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r91 install preflight export invalid")
    print(json.dumps(dict(report=report, export=saved["path"])))
