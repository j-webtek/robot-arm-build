"""Replay retained P1 evidence and export the offline P2 timing-order review."""
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.p2_path_review import review_p2_path
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

SOURCE = 'wizard-20260923T024713112793Z-299f2bdab3454e0fb68cc1cdc7cd44f0'
BOOT = 'f7b522422be6edcb9ab740a776e32ae5'


def main():
    root = Path(__file__).resolve().parents[1]
    exports = root/'runs/wizard-exports'
    source = exports/SOURCE
    if not verify_export(source)['valid']:
        raise ValueError('P1 export failed verification')
    raw = bytes.fromhex((source/'attachment-large-pose-relief.hex.txt').read_text())
    review = review_p2_path(raw, expected_boot=BOOT,
                           model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    review['source_export_id'] = SOURCE
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'offline-p2-path-review'}, [], attachments={
        'p2-path-review.json': canonical(review)})
    if not verify_export(Path(saved['path']).resolve())['valid']:
        raise ValueError('Review export failed verification')
    print(saved['path'])


if __name__ == '__main__':
    main()
