"""Offline import of exported local-step movement records, never a device client.

Reuses the original independent event validator. Post-fault settling is deliberately
not folded into arrival: the movement deadline remains a failed test.
"""
import argparse
import hashlib
import json
from pathlib import Path

from .first_motion_contract import canonical
from .local_shoulder_step_review import LocalStepReview
from .physical_settling_review import review_settling
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def _attachment(bundle, name):
    checked = verify_export(bundle)
    if not checked['valid']:
        raise ValueError('Invalid source bundle: ' + bundle.name)
    entry = next((f for f in checked['files'] if f['name'] == name), None)
    if entry is None:
        raise ValueError('Missing source attachment: ' + name)
    payload = (bundle / name).read_bytes()
    if len(payload) != entry['bytes'] or hashlib.sha256(payload).hexdigest() != entry['sha256']:
        raise ValueError('Source changed after verification')
    return payload, dict(bundle=bundle.name, manifest_sha256=checked['manifest_sha256'])


def import_local_step(source):
    """Validate accepted movement records within the source export directory.

    Manifest hashes establish saved-file integrity, not device authentication.
    Unknown deployment details stay unknown; this never queries current firmware.
    """
    source = Path(source).resolve()
    raw, identity = _attachment(source, 'attachment-local-step-run.json')
    report = decode_diagnostic_json(raw, maximum=len(raw))
    if (not isinstance(report, dict) or report.get('schema') != 'rocell.local_step_run.v1'
            or report.get('origin') != 'DEVICE_CAPTURE'
            or report.get('state') not in ('STOPPED', 'LOCAL_STEP_OBSERVED')):
        raise ValueError('Unsupported physical local-step report')
    records = report.get('records')
    if not isinstance(records, list) or not 6 <= len(records) <= 64:
        raise ValueError('Insufficient or unbounded movement evidence')
    review = LocalStepReview(report['boot_id'], report['command_id'])
    sources = [identity]
    docs = []
    seen = set()
    for index, reference in enumerate(records):
        path = Path(reference).resolve()
        # Saved paths are data, not authority to traverse arbitrary directories.
        if path.parent != source.parent or path in seen:
            raise ValueError('Record must be a unique sibling export')
        seen.add(path)
        event, evidence = _attachment(path, 'attachment-shoulder-event.txt')
        if index == 3:
            plan = review.authorize(review.finished)
            if report.get('plan') != plan:
                raise ValueError('Saved plan differs from reconstructed plan')
        docs.append(review.accept(event))
        sources.append(evidence)
    if report['state'] == 'LOCAL_STEP_OBSERVED' and review.arrivals < 3:
        raise ValueError('Successful outcome lacks verified arrival')
    plan = review.plan
    final = docs[-1]
    settling = None
    if 'settling' in report:
        capture = report['settling']
        if (report['state'] != 'STOPPED' or not isinstance(capture, dict)
                or capture.get('parent_motion_state') != 'FAULT'
                or capture.get('physical_accuracy_verified') is not False
                or not isinstance(capture.get('records'), list)
                or not 1 <= len(capture['records']) <= 12):
            raise ValueError('Unsupported post-fault evidence')
        raw_settling = []
        for reference in [capture['original_export'], *capture['records']]:
            path = Path(reference).resolve()
            if path.parent != source.parent or path in seen:
                raise ValueError('Settling record must be a unique sibling export')
            seen.add(path)
            event, evidence = _attachment(path, 'attachment-shoulder-event.txt')
            raw_settling.append(event)
            sources.append(evidence)
        settling = review_settling(raw_settling[0], raw_settling[1:],
                                  last_movement=final, movement_count=review.count,
                                  claimed_state=capture['state'])
    rows = []
    for offset, servo in enumerate((12, 13), 1):
        position = final['joints'][offset][1]
        accepted = final['joints'][offset][2]
        rows.append(dict(servo_id=servo, start_counts=plan['positions'][offset],
                         prior_goal_counts=plan['goals'][offset],
                         requested_counts=plan['targets'][offset-1],
                         accepted_counts=accepted, measured_counts=position,
                         endpoint_error_counts=position-accepted,
                         measured_change_counts=position-plan['positions'][offset]))
    return dict(schema='rocell.physical_local_step_review.v1', basis='DEVICE_CAPTURE',
                boot_id=report['boot_id'], command_id=report['command_id'],
                original_state=report['state'], controller_reason=report.get('controller_reason'),
                speed=plan['speed'], acceleration=plan['acceleration'],
                endpoint_basis='LAST_ACCEPTED_MOVEMENT_SAMPLE_NOT_POSTFAULT_SETTLING',
                elapsed_after_send_us=final['scan_finished_us']-review.sent,
                accepted_records=review.count, endpoints=rows, sources=sources, settling=settling,
                transmission='SENT_UNACKNOWLEDGED', target_readback_verified=True,
                physical_accuracy_verified=False, movement_authorized=False,
                firmware_identity='NOT_INDEPENDENTLY_VERIFIED_BY_THIS_IMPORTER',
                limitations=['Historical encoder observations, not current pose or stylus accuracy.',
                             'Post-fault settling does not turn the movement deadline failure into a pass.',
                             'Single trial; repeatability and compensation are not established.',
                             'Bundle integrity is not authenticated device provenance.'])


def render_review(summary):
    lines = ['# Physical local-step evidence review', '',
             'Historical device capture — no new movement was performed.', '',
             f"Original outcome: **{summary['original_state']}**; controller reason: {summary['controller_reason']}.", '',
             'Endpoint: last accepted movement sample, not the later post-fault settling pose.', '',
             '| Servo | Start | Prior goal | Requested | Accepted | Measured | Error | Change |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in summary['endpoints']:
        lines.append('| ' + ' | '.join(str(row[k]) for k in (
            'servo_id', 'start_counts', 'prior_goal_counts', 'requested_counts',
            'accepted_counts', 'measured_counts', 'endpoint_error_counts',
            'measured_change_counts')) + ' |')
    lines += ['', 'All values above are encoder counts, not millimetres.', '',
              f"Validated movement records: {summary['accepted_records']}."]
    settling = summary.get('settling')
    if settling is not None:
        lines += ['', '## Separate post-fault settling', '',
                  f"State: {settling['state']}; validated samples: {settling['validated_records']}.", '',
                  f"Final shoulder errors: {settling['endpoint_error_counts']} counts.", '',
                  f"Additional change after movement: {settling['change_from_movement_counts']} counts.", '',
                  'The original movement outcome remains unchanged.']
    lines += ['', '## Limitations', '']
    lines += ['- ' + value for value in summary['limitations']]
    return '\n'.join(lines) + '\n'


def review_physical_export(source, destination):
    summary = import_local_step(source)
    exporter = WizardDiagnosticExporter(Path(destination).resolve())
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'physical-local-step-review'}, [], attachments={
        'physical-review.json': canonical(summary),
        'physical-review.md': render_review(summary).encode('utf-8')})
    if not verify_export(Path(saved['path']))['valid']:
        raise OSError('Review export verification failed')
    return saved['path']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--exports', required=True, type=Path)
    args = parser.parse_args()
    print(review_physical_export(args.source, args.exports))


if __name__ == '__main__':
    main()
