"""Export the exact r89 pre-write connection failure without opening the arm."""

import hashlib
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


APP_SHA = "89c0d91334ab4362d392a3e3e66433c216d7e1740842dbba1b87881b722236b0"
RELEASE_SHA = "653729599a9ba29baed5095b3ed156810b38396065a0b6a3a06fe6c7dd74ab1a"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    journal = root / "private-backups/controller-20260918-session1/app-r89-deployment-events.jsonl"
    raw = journal.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    expected = dict(stage="RESERVED", app_sha256=APP_SHA, offset=65536,
                    bytes=1061360, release_sha256=RELEASE_SHA)
    if (len(rows) != 2 or rows[0] != expected or rows[1].get("stage") != "STOPPED"
            or rows[1].get("error_type") != "FatalError"
            or rows[1].get("retry") is not False
            or "getting no sync reply" not in rows[1].get("error", "")):
        raise ValueError("Unexpected journal; cannot classify as pre-write failure")
    report = dict(
        schema="rocell.r89_prewrite_failure.v1",
        journal_sha256=hashlib.sha256(raw).hexdigest(),
        status="DOWNLOAD_MODE_DETECTED_NO_SYNC",
        app_write_attempted=False,
        startup_reset_sent=False,
        movement_command_sent=False,
        retry_attempted=False,
        current_controller_state="unknown; may remain in ROM download mode",
        failed_journal_preserved=True,
    )
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r89-prewrite-failure"}, [], attachments={
        "r89-prewrite-failure.json": canonical(report),
        "r89-failed-journal.jsonl": raw,
    })
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Failure export verification failed")
    print(saved["path"])


if __name__ == "__main__":
    main()
