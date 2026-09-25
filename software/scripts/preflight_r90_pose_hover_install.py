"""Read-only r90 app-only installation preflight; never opens a serial port."""

import argparse
import hashlib
import json
from pathlib import Path

if __package__:
    from .deploy_reviewed_hover_r89 import BACKUP_SHA, FS_SHA
    from .preflight_r89_live_campaign import current_capabilities, local_install_review
    from .review_r90_pose_hover_candidate import review
else:
    from deploy_reviewed_hover_r89 import BACKUP_SHA, FS_SHA
    from preflight_r89_live_campaign import current_capabilities, local_install_review
    from review_r90_pose_hover_candidate import review
from rocell.application.product_ghost_export_review import _read
from rocell.providers.windows.diagnostic_image_store import load_image
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


COMPILE = "wizard-20260925T115330774418Z-399cdfe58f7441d3af02d1584ceddfe1"
REVIEW = "wizard-20260925T115402595189Z-52243d92ed6a4a9fb9d235b5236d2bf6"


def preflight(root: Path, address: str | None = None) -> dict:
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    reviewed, _ = _read(exports, REVIEW, "attachment-r90-pose-hover-candidate-review.json")
    if reviewed != review(root, COMPILE):
        raise ValueError("r90 independent candidate review differs")
    installed = local_install_review(root)
    build = root / ".firmware-tools/build-configured-diagnostic-candidate-r90--default-4mb-no-psram"
    app = (build / "RoArm-M3_example.ino.bin").read_bytes()
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    if (sha(app) != reviewed["app_sha256"] or not 0 < len(app) <= 0x140000
            or reviewed["predecessor_app_sha256"] != installed["app_sha256"]):
        raise ValueError("r90 app/predecessor or slot differs")
    private = root / "private-backups/controller-20260918-session1"
    backup_a = (private / "flash-pair-a.bin").read_bytes()
    backup_b = (private / "flash-pair-b.bin").read_bytes()
    if (len(backup_a) != 0x400000 or sha(backup_a) != BACKUP_SHA
            or backup_b != backup_a):
        raise ValueError("Full flash backups differ")
    filesystem = load_image(private / "observed-pose-plus10-candidate.dpapi")
    if len(filesystem) != 0x160000 or sha(filesystem) != FS_SHA:
        raise ValueError("Protected filesystem/settings snapshot differs")
    journal = private / "app-r90-deployment-events.jsonl"
    if journal.exists():
        raise ValueError("r90 installation already attempted; no automatic retry")
    report = dict(schema="rocell.r90_app_only_preflight.v1",
                  status="LOCAL_PREFLIGHT_VERIFIED", app_sha256=sha(app),
                  release_sha256=reviewed["release_sha256"],
                  predecessor_app_sha256=installed["app_sha256"],
                  app_offset=0x10000, app_bytes=len(app), app_slot_bytes=0x140000,
                  protected_regions=[[0, 0x10000], [0x150000, 0x2b0000]],
                  original_full_backup_verified=True,
                  protected_filesystem_snapshot_verified=True,
                  installation_journal_absent=True, current_device_verified=False,
                  hardware_access=False, firmware_uploaded=False,
                  movement_command_sent=False, deployment_authorized=False)
    if address is not None:
        caps = current_capabilities(address)
        if caps["stamped_release_sha256"] != installed["release_sha256"]:
            raise ValueError("Connected controller is not verified r89 release")
        report["current_device_verified"] = True
        report["current_boot_id"] = caps["boot_id"]
        report["hardware_access"] = "public_capabilities_get_only"
        report["status"] = "READ_ONLY_DEVICE_PREFLIGHT_VERIFIED"
    return report


def main() -> None:
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
    saved = exporter.export({"mode": "r90-app-only-preflight"}, [],
                            attachments={"r90-app-only-preflight.json":
                                         json.dumps(report, sort_keys=True).encode()})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r90 preflight export invalid")
    print(json.dumps(dict(report=report, export=saved["path"])))


if __name__ == "__main__":
    main()
