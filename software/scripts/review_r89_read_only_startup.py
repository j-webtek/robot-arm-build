"""Review the captured r89 NEW|1 startup response offline; never access hardware."""

import hashlib
import json
from pathlib import Path

from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


CAPTURE = "wizard-20260925T112230268400Z-d2cc89a69c314fe880f1d17d5eb271a1"
APP_SHA = "89c0d91334ab4362d392a3e3e66433c216d7e1740842dbba1b87881b722236b0"
RELEASE_SHA = "653729599a9ba29baed5095b3ed156810b38396065a0b6a3a06fe6c7dd74ab1a"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    exports = root / "runs/wizard-exports"
    captured, _ = _read(exports, CAPTURE, "attachment-r89-read-only-startup.json")
    if (captured.get("schema") != "rocell.r89_read_only_startup.v1"
            or captured.get("status") != "READ_ONLY_STARTUP_FAILED"
            or captured.get("error") != "Reviewed-hover owner is not unused"
            or captured.get("authenticated_status") != "NEW|1"
            or captured.get("app_sha256") != APP_SHA
            or captured.get("release_sha256") != RELEASE_SHA
            or captured.get("motion_request_sent") is not False
            or captured.get("reservation_request_sent") is not False):
        raise ValueError("Captured startup report differs")
    owner = (root / "firmware/diagnostics/reviewed_hover_owner.h").read_text()
    route = (root / "firmware/diagnostics/reviewed_hover_routes.h").read_text()
    if ("unsigned leg()const{return leg_+1;}" not in owner
            or "unsigned leg_=0" not in owner
            or 'const char* reason_="NEW"' not in owner
            or 'owner_.reason(),owner_.leg()' not in route):
        raise ValueError("One-based idle status implementation differs")
    journal = root / "private-backups/controller-20260918-session1/app-r89-attempt2-deployment-events.jsonl"
    raw = journal.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    if ([row.get("stage") for row in rows] != ["RESERVED", "IDENTITY_AND_PREWRITE_VERIFIED",
            "WRITE_ATTEMPT_STARTED", "FLASH_VERIFIED", "ONE_STARTUP_ATTEMPT",
            "STARTUP_RESET_SENT"] or rows[3].get("app_sha256") != APP_SHA
            or rows[3].get("protected_regions_unchanged") is not True):
        raise ValueError("Verified installation journal differs")
    report = dict(schema="rocell.r89_read_only_startup_review.v1",
                  status="READ_ONLY_STARTUP_VERIFIED_FROM_CAPTURE",
                  captured_export=CAPTURE,
                  installation_journal_sha256=hashlib.sha256(raw).hexdigest(),
                  boot_id=captured["boot_id"],
                  authenticated_status="NEW|1",
                  rationale="Owner leg() is one-based; New state has leg_=0 and reason_=NEW",
                  no_additional_hardware_access=True,
                  motion_request_sent=False,
                  reservation_request_sent=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r89-read-only-startup-review"}, [],
                            attachments={"r89-read-only-startup-review.json":
                                         json.dumps(report, sort_keys=True).encode()})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Review export verification failed")
    print(saved["path"])


if __name__ == "__main__":
    main()
