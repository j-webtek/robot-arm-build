"""Read-only r89 live-launch preflight; never starts or moves the arm."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
from pathlib import Path
import re

from rocell.application.product_ghost_export_review import _read
from rocell.application.reviewed_hover_release_identity import verify_release_pair
from rocell.application.reviewed_hover_live_host import R89_APP_SHA, R89_RELEASE_SHA
from rocell.application.servo_diagnostic_http import DiagnosticHTTPReader
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


RELEASE_EXPORT = "wizard-20260925T034728622941Z-f15a2f14fa5847df8340a884d9d53856"
COMPILE_EXPORT = "wizard-20260925T034619289604Z-68658f0139aa430793f4b8ba5c5345b4"
STARTUP_EXPORT = "wizard-20260925T112402757756Z-e4fb5e9ddb13490f910e12b31c1a0e45"


def local_install_review(root: Path) -> dict:
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    release, _ = _read(exports, RELEASE_EXPORT,
                       "attachment-r89-reviewed-hover-release-review.json")
    compiled, _ = _read(exports, COMPILE_EXPORT, "attachment-compile-review.json")
    app = (root / ".firmware-tools/build-configured-diagnostic-candidate-r89--default-4mb-no-psram"
           / "RoArm-M3_example.ino.bin").read_bytes()
    if hashlib.sha256(app).hexdigest() != R89_APP_SHA:
        raise ValueError("Pinned r89 image differs")
    source_bytes = {name: (root / name).read_bytes() for name in release["source_hashes"]}
    checked = verify_release_pair(release, compile_report=compiled,
                                  source_bytes=source_bytes, app_image=app)
    if checked["release_sha256"] != R89_RELEASE_SHA:
        raise ValueError("Reviewed release differs")
    journal = (root / "private-backups/controller-20260918-session1"
               / "app-r89-attempt2-deployment-events.jsonl")
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    if ([row.get("stage") for row in rows] != [
            "RESERVED", "IDENTITY_AND_PREWRITE_VERIFIED", "WRITE_ATTEMPT_STARTED",
            "FLASH_VERIFIED", "ONE_STARTUP_ATTEMPT", "STARTUP_RESET_SENT"] or
            rows[0].get("app_sha256") != R89_APP_SHA or
            rows[3].get("app_sha256") != R89_APP_SHA or
            rows[3].get("protected_regions_unchanged") is not True or
            rows[1].get("mac") != "fc:e8:c0:f8:d5:38"):
        raise ValueError("Installed r89 journal differs")
    startup, _ = _read(exports, STARTUP_EXPORT,
                       "attachment-r89-read-only-startup-review.json")
    if startup.get("status") != "READ_ONLY_STARTUP_VERIFIED_FROM_CAPTURE":
        raise ValueError("r89 startup review differs")
    return dict(app_sha256=R89_APP_SHA, release_sha256=R89_RELEASE_SHA,
                installed_journal_sha256=hashlib.sha256(journal.read_bytes()).hexdigest(),
                previous_boot_id=startup["boot_id"])


def assess_boot(exports: Path, boot: str, previous_boot: str) -> dict:
    if type(boot) is not str or not re.fullmatch(r"[0-9a-f]{32}", boot) or boot == "0" * 32:
        raise ValueError("Invalid current boot ID")
    claims = [name for name in (
        f"pose-observation-{boot}.json",
        f"reviewed-hover-live-{boot}.json",
        f"r89-read-only-status-{boot}.json",
    ) if (Path(exports) / name).exists()]
    reasons = []
    if boot == previous_boot:
        reasons.append("PREVIOUSLY_OBSERVED_BOOT")
    if claims:
        reasons.append("BOOT_ALREADY_CLAIMED_OR_SIGNED_SEQUENCE_USED")
    return dict(boot_id=boot, claim_files=claims, software_preflight_ready=not reasons,
                reasons=reasons, physical_clearance_verified=False,
                source_pose_verified=False, motion_authorized=False)


def current_capabilities(address: str) -> dict:
    address = DiagnosticHTTPReader(address, 80).address
    connection = http.client.HTTPConnection(address, 80, timeout=3)
    try:
        connection.request("GET", "/rocell/reviewed-hover/capabilities",
                           headers={"Accept-Encoding": "identity"})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("Capabilities unavailable")
        raw = response.read(513)
    finally:
        connection.close()
    if len(raw) > 512:
        raise ValueError("Capabilities exceed bound")
    caps = json.loads(raw)
    if (type(caps) is not dict or set(caps) != {"schema", "boot_id",
            "live_release_available", "motion_authorized", "maximum_legs",
            "stamped_release_sha256"} or
            caps["schema"] != "rocell.reviewed_hover_capabilities.v1" or
            caps["live_release_available"] is not True or
            caps["motion_authorized"] is not False or
            caps["maximum_legs"] != 16 or
            caps["stamped_release_sha256"] != R89_RELEASE_SHA):
        raise ValueError("Controller release/capabilities differ")
    return caps


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--local-only", action="store_true")
    mode.add_argument("--read-current-boot", action="store_true")
    parser.add_argument("--address", default="192.168.0.225")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    installation = local_install_review(root)
    if args.local_only:
        print(json.dumps(dict(status="R89_LOCAL_INSTALL_REVIEW_VERIFIED",
                              installation=installation, hardware_access=False)))
        return
    caps = current_capabilities(args.address)
    exports = root / "runs/wizard-exports"
    report = dict(schema="rocell.r89_live_preflight.v1", installation=installation,
                  capabilities=caps,
                  **assess_boot(exports, caps["boot_id"], installation["previous_boot_id"]))
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r89-live-preflight"}, [],
                            attachments={"r89-live-preflight.json":
                                         json.dumps(report, sort_keys=True).encode()})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Preflight export verification failed")
    print(json.dumps(dict(report=report, export=saved["path"])))


if __name__ == "__main__":
    main()
