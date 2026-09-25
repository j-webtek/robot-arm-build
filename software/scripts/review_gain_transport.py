"""Offline review of saved gain responses; never retries device communication."""
import argparse
import base64
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.elbow_gain_review import assess_gain
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def review(report):
    if report.get('schema') != 'rocell.gain_capture_transport.v1':
        raise ValueError('Gain transport report required')
    responses = report['responses']
    if not 1 <= len(responses) <= 2:
        raise ValueError('No captured gain response or unexpected response count')
    raw = []
    assessments = []
    for row, method in zip(responses, ('POST', 'GET')):
        if set(row) != {'method', 'raw_base64'} or row['method'] != method:
            raise ValueError('Unexpected response identity')
        data = base64.b64decode(row['raw_base64'], validate=True)
        if not 0 < len(data) <= 4095 or base64.b64encode(data).decode() != row['raw_base64']:
            raise ValueError('Invalid response encoding/budget')
        assessments.append(assess_gain(decode_diagnostic_json(data, maximum=4095), **report['subject']))
        raw.append(data)
    retained = len(raw) == 2 and raw[0] == raw[1]
    return dict(schema='rocell.saved_gain_transport_review.v1',
                post_assessment=assessments[0], retained_copy_verified=retained,
                capture_workflow_complete=retained and 'error_type' not in report
                    and report['category']=='CONTROLLER_REPORTED_GAINS',
                source_transport_category=report['category'],
                hardware_access=False, retry_performed=False,
                motion_authorized=False, gain_changes_authorized=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export_id')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]/'runs/wizard-exports'
    document, digest = _read(root, args.export_id, 'attachment-gain-transport.json')
    assessment = review(document)
    assessment.update(source_export_id=args.export_id, source_sha256=digest)
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved = exporter.export({'mode':'saved-gain-transport-review'}, [],
        attachments={'saved-gain-review.json':canonical(assessment)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Offline review export failed')
    retained, _ = _read(root, Path(saved['path']).name, 'attachment-saved-gain-review.json')
    if canonical(retained) != canonical(assessment):
        raise ValueError('Offline review changed')
    print(canonical(dict(export_path=saved['path'], **assessment)).decode())


if __name__ == '__main__':
    main()
