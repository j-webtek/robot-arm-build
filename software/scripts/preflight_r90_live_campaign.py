"""Read-only r90 live-campaign preflight; never starts or moves the arm."""

import argparse
import hashlib
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.reviewed_hover_live_host import R90_APP_SHA, R90_RELEASE_SHA
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

if __package__:
    from .preflight_r89_live_campaign import assess_boot
    from .review_r90_pose_hover_candidate import review as review_candidate
    from .review_r90_source_pose import review as review_source_pose
    from .run_r90_pose_observation import get
else:
    from preflight_r89_live_campaign import assess_boot
    from review_r90_pose_hover_candidate import review as review_candidate
    from review_r90_source_pose import review as review_source_pose
    from run_r90_pose_observation import get


COMPILE = "wizard-20260925T115330774418Z-399cdfe58f7441d3af02d1584ceddfe1"
SOURCE_EXPORT = "wizard-20260925T120659583576Z-07fd100e64354ea597d0773dfceac3d3"


def preflight(root: Path, address: str) -> dict:
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    candidate = review_candidate(root, COMPILE)
    if candidate["app_sha256"] != R90_APP_SHA or candidate["release_sha256"] != R90_RELEASE_SHA:
        raise ValueError("r90 reviewed release differs")
    source, _ = _read(exports, SOURCE_EXPORT, "attachment-r90-source-pose-review.json")
    if source != review_source_pose(root):
        raise ValueError("r90 source pose evidence differs")
    journal = (root / "private-backups/controller-20260918-session1"
               / "app-r90-deployment-events.jsonl")
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    if ([row.get("stage") for row in rows] != [
            "RESERVED", "IDENTITY_AND_PREWRITE_VERIFIED", "WRITE_ATTEMPT_STARTED",
            "FLASH_VERIFIED", "ONE_STARTUP_ATTEMPT", "STARTUP_RESET_SENT"]
            or rows[3].get("app_sha256") != R90_APP_SHA
            or rows[3].get("protected_regions_unchanged") is not True):
        raise ValueError("r90 installed journal differs")
    status, raw = get(address, "/rocell/reviewed-hover/capabilities", 512)
    if status != 200:
        raise ValueError("r90 capabilities unavailable")
    caps = json.loads(raw)
    if (caps.get("schema") != "rocell.reviewed_hover_capabilities.v1"
            or caps.get("stamped_release_sha256") != R90_RELEASE_SHA
            or caps.get("live_release_available") is not True
            or caps.get("motion_authorized") is not False
            or caps.get("maximum_legs") != 16):
        raise ValueError("r90 live release/capabilities differ")
    boot = assess_boot(exports, caps.get("boot_id"), source["boot_id"])
    return dict(**boot, schema="rocell.r90_live_preflight.v1",
                installation_journal_sha256=hashlib.sha256(journal.read_bytes()).hexdigest(),
                app_sha256=R90_APP_SHA, release_sha256=R90_RELEASE_SHA,
                capabilities=caps, source_pose_export_id=SOURCE_EXPORT,
                last_source_pose_verified=True,
                current_boot_source_pose_verified=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", default="192.168.0.225")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = preflight(root, args.address)
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r90-live-preflight"}, [],
                            attachments={"r90-live-preflight.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r90 live preflight export invalid")
    print(json.dumps(dict(report=report, export=saved["path"])))


if __name__ == "__main__":
    main()
