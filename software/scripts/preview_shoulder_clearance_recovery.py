"""Export a source-bound offline recovery preview; never contact hardware."""
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from rocell.kinematics.shoulder_clearance_recovery import preview_recovery


def main():
    exports = Path(__file__).resolve().parents[1] / 'runs/wizard-exports'
    source = 'wizard-20260919T203825127176Z-0533f1bb58ca40d3b5371679adc34cd4'
    report, receipt = _read(exports, source, 'attachment-shoulder-run.json')
    event_dir = Path(report['records'][-1]).resolve()
    if event_dir.parent != exports:
        raise ValueError('Record outside workspace exports')
    event, event_receipt = _read(exports, event_dir.name, 'attachment-shoulder-event.txt')
    if event['boot_id'] != report['boot_id'] or event['event'] != 'SHOULDER_STEP_SAMPLE':
        raise ValueError('Unexpected source event')
    result = preview_recovery([row[1] for row in event['joints']],
                              [row[2] for row in event['joints']])
    result.update(source_run_receipt=receipt, source_event_receipt=event_receipt,
                  input_is_historical=True)
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({'mode':'offline-shoulder-clearance-preview'}, [],
        attachments={'recovery-preview.json':canonical(result)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Invalid preview export')
    print(canonical(dict(export_path=saved['path'], preview=result)).decode())


if __name__ == '__main__': main()
