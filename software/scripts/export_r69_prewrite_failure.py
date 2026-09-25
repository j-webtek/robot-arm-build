"""Export the failed r69 connection journal without opening any device."""
import hashlib
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.t4_wrist_release import APP_SHA, APP_BYTES
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root = Path(__file__).resolve().parents[1]
    journal = root/'private-backups/controller-20260918-session1/app-r69-deployment-events.jsonl'
    raw = journal.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    if (len(rows) != 2 or rows[0] != dict(stage='RESERVED', app_sha256=APP_SHA,
            offset=65536, bytes=APP_BYTES) or rows[1].get('stage') != 'STOPPED' or
            rows[1].get('error_type') != 'FatalError' or rows[1].get('retry') is not False or
            'getting no sync reply' not in rows[1].get('error','')):
        raise ValueError('Unexpected failure journal; do not classify as prewrite')
    report = dict(schema='rocell.r69_prewrite_failure.v1',
        journal_sha256=hashlib.sha256(raw).hexdigest(),
        status='DOWNLOAD_MODE_DETECTED_NO_SYNC', app_write_attempted=False,
        startup_reset_sent=False, movement_command_sent=False,
        current_controller_state='unknown; may remain in ROM download mode',
        retry_attempted=False, failed_journal_preserved=True)
    exporter = WizardDiagnosticExporter(root/'runs/wizard-exports')
    exporter.prepare(create=True)
    saved = exporter.export({'mode':'r69-prewrite-failure'}, [], attachments={
        'r69-prewrite-failure.json':canonical(report), 'r69-failed-journal.jsonl':raw})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Failure export verification failed')
    print(saved['path'])


if __name__ == '__main__':
    main()
