"""Recover a compact summary from an intact wizard export, without hardware I/O."""
import argparse
import base64
import json
from pathlib import Path

from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def recover(source):
    source = Path(source).resolve()
    if not verify_export(source)['valid']:
        raise ValueError('Source export integrity check failed')
    logs = json.loads((source / 'attachment-powered-feedback-native-logs.json').read_text())
    native = json.loads(b''.join(base64.b64decode(c, validate=True)
                                for c in logs['stdout_base64_chunks']))
    observation = native['child_result']['observation']
    capture, lifecycle = observation['capture'], observation['lifecycle']
    return dict(
        schema='rocell.recovered_usb_capture_summary.v1', source_export=str(source),
        source_integrity_verified=True, status=observation['status'],
        pose_sample_count=capture['pose_sample_count'],
        latest_pose_record=capture['latest_pose_record'],
        confirmed_write_bytes=lifecycle['confirmed_write_bytes'],
        cleanup_confirmed=lifecycle['cleanup_confirmed'],
        pending_io_unresolved=lifecycle['pending_io_unresolved'],
        acquisition_started_monotonic_ns=observation['acquisition_started_monotonic_ns'],
        observation_finished_monotonic_ns=observation['observation_finished_monotonic_ns'],
        sample_freshness_verified=capture['sample_freshness_verified'],
        query_response_verified=capture['query_response_verified'],
        http_bracketing_evidence_recovered=False, motion_authorized=False,
        limitation='Recovery does not reconstruct lost HTTP probes or prove physical endpoint accuracy.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_export', type=Path)
    args = parser.parse_args()
    summary = recover(args.source_export)
    destination = Path(__file__).resolve().parents[1] / 'runs/wizard-exports'
    exporter = WizardDiagnosticExporter(destination.resolve())
    exporter.prepare(create=True)
    receipt = exporter.export({'mode': 'offline-evidence-recovery'}, [], attachments={
        'recovered-usb-capture.json': json.dumps(summary, allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:
        raise RuntimeError('Recovered export verification failed')
    print(json.dumps({'export': receipt['path'], 'samples': summary['pose_sample_count'],
                      'confirmed_write_bytes': summary['confirmed_write_bytes']}))


if __name__ == '__main__':
    main()
