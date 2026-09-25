"""Compare verified capture exports offline; never connect or command hardware."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

from rocell.application.feedback_channel_comparison import compare_feedback_channels
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def compare(source):
    source = Path(source).resolve()
    if not verify_export(source)['valid']:
        raise ValueError('Wrapper integrity failure')
    record = json.loads((source / 'attachment-usb-http-capture.json').read_text())
    native = Path(record['wizard_export']).resolve()
    if not verify_export(native)['valid']:
        raise ValueError('Native export integrity failure')
    logs = json.loads((native / 'attachment-powered-feedback-native-logs.json').read_text())
    observation = json.loads(b''.join(base64.b64decode(c, validate=True)
        for c in logs['stdout_base64_chunks']))['child_result']['observation']
    capture = observation['capture']
    raw = base64.b64decode(capture['raw']['base64'], validate=True)
    if hashlib.sha256(raw).hexdigest() != capture['raw']['sha256']:
        raise ValueError('Serial bytes changed')
    pose = capture['latest_pose_record']
    packet = raw[pose['start']:pose['end']]
    windows = [w for w in observation['read_windows']
               if w[0] < pose['end'] and w[1] > pose['start']]
    if not windows:
        raise ValueError('No acquisition windows for pose')
    serial = dict(channel='SERIAL', started_ns=windows[0][2], finished_ns=windows[-1][3],
                  response_base64=base64.b64encode(packet).decode(),
                  response_sha256=hashlib.sha256(packet).hexdigest())
    comparisons = {}
    for name in ('http_before', 'http_after'):
        http = record[name]
        if 'host_monotonic_started_ns' not in http:
            comparisons[name] = dict(status='COMMON_CLOCK_BRACKET_MISSING')
            continue
        comparisons[name] = compare_feedback_channels(dict(channel='HTTP',
            started_ns=http['host_monotonic_started_ns'],
            finished_ns=http['host_monotonic_finished_ns'],
            response_base64=http['response_base64'], response_sha256=http['response_sha256']), serial)
    return dict(schema='rocell.usb_http_export_comparison.v1',
        source_export=str(source), native_export=str(native), comparisons=comparisons,
        serial_byte_range=[pose['start'], pose['end']],
        serial_pose_samples=capture['pose_sample_count'], motion_authorized=False,
        encoder_freshness_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    args = parser.parse_args()
    result = compare(args.export)
    exporter = WizardDiagnosticExporter((Path(__file__).resolve().parents[1] / 'runs/wizard-exports').resolve())
    exporter.prepare(create=True)
    receipt = exporter.export({'mode': 'offline-feedback-comparison'}, [], attachments={
        'usb-http-comparison.json': json.dumps(result, allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:
        raise RuntimeError('Comparison export failed verification')
    print(json.dumps(dict(export=receipt['path'], comparisons=result['comparisons'])))


if __name__ == '__main__':
    main()
