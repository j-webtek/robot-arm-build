"""Export the offline P4 wrist reverse/repeat campaign review."""
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.p4_repeat_campaign_review import review_p4_repeat_campaign
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

SOURCE = 'wizard-20260924T182321443347Z-87b68bc4624a4e1b80c6fb0af4027e5e'


def main():
    root = Path(__file__).resolve().parents[1]
    exports = root/'runs/wizard-exports'
    source, _ = _read(exports, SOURCE, 'attachment-large-pose-relief-assessment.json')
    if not verify_export(exports/SOURCE)['valid']:
        raise ValueError('Source export invalid')
    raw = bytes.fromhex((exports/SOURCE/'attachment-large-pose-relief.hex.txt').read_text('ascii'))
    review = review_p4_repeat_campaign(raw, expected_boot=source['boot'],
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    if canonical(source) != canonical(review['source_assessment']):
        raise ValueError('Source assessment differs from independent replay')
    review['source_export_id'] = SOURCE
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode':'p4-repeat-campaign-offline-review'}, [], attachments={
        'p4-repeat-campaign-review.json':canonical(review)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Review export invalid')
    print(saved['path'])
    print(canonical(review).decode())


if __name__ == '__main__':
    main()
