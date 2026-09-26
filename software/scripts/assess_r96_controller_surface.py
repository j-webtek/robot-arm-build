"""Assess retained r96 evidence against the production protocol surface.

This is an offline-only tool. It reads retained files, performs linked-image
source inspection, and writes a zero-authority compatibility report. It has no
network, serial, controller, firmware, or motion code path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from review_r96_registration_ladder import review
from rocell.application.installed_controller_passive_evidence_v1 import (
    InstalledControllerPassiveEvidenceV1,
    canonical_json,
)
from rocell.application.installed_controller_surface_compatibility_v1 import (
    InstalledControllerSurfaceEvidenceV1,
    SurfaceReviewDisposition,
    assess_installed_controller_surface_compatibility_v1,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--passive-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _load_passive(path: Path) -> InstalledControllerPassiveEvidenceV1:
    document = json.loads(path.read_text(encoding="utf-8"))
    originals = document["retained_originals"]
    usb = document["usb_identity"]
    passive = InstalledControllerPassiveEvidenceV1(
        capture_id=document["capture_id"],
        captured_at_utc=document["captured_at_utc"],
        controller_session_id=document["controller_session_id"],
        usb_port=usb["port"],
        usb_pnp_instance_id=usb["pnp_instance_id"],
        installed_app_sha256=originals["installed_app_sha256"],
        installed_app_bytes_sha256=originals["installed_app_bytes_sha256"],
        deployment_journal_sha256=originals["deployment_journal_sha256"],
        final_export_manifest_sha256=originals["final_export_manifest_sha256"],
        final_feedback_attachment_sha256=(
            originals["final_feedback_attachment_sha256"]),
        live_capabilities=document["live_capabilities"],
        live_capabilities_sha256=document["live_capabilities_sha256"],
    )
    if passive.to_dict() != document:
        raise ValueError("passive evidence is not the canonical retained record")
    return passive


def main() -> int:
    args = _arguments()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("compatibility output already exists")
    passive = _load_passive(args.passive_evidence.resolve())
    root = Path(__file__).resolve().parents[1]
    linked_review = review(root)
    linked_review_sha = hashlib.sha256(canonical_json(linked_review)).hexdigest()
    surface = InstalledControllerSurfaceEvidenceV1(
        surface_id="r96-registration-ladder",
        reviewed_app_sha256=linked_review["app_sha256"],
        linked_image_review_sha256=linked_review_sha,
        generic_command_dispatch_present=linked_review["generic_motion_parser"],
        t102_command_supported=False,
        t105_feedback_request_supported=False,
        t1051_feedback_response_supported=False,
        runtime_app_hash_attested=False,
        review_disposition=SurfaceReviewDisposition.UNREVIEWED,
    )
    report = assess_installed_controller_surface_compatibility_v1(
        passive, surface)
    document = {
        "surface_evidence": surface.to_dict(),
        "compatibility_report": report.to_dict(),
        "linked_image_review": linked_review,
        "offline_only": True,
        "network_access": False,
        "serial_port_opened": False,
        "controller_restarted": False,
        "hardware_writes": 0,
        "movement_commands": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json(document) + b"\n")
    print(json.dumps({
        "output": str(output),
        "status": report.status,
        "blockers": list(report.blockers),
        "report_sha256": report.report_sha256,
        "surface_evidence_sha256": surface.evidence_sha256,
        "hardware_writes": 0,
        "movement_commands": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
