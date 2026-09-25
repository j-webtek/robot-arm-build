"""Offline interpretation of retained r13 feedback; no device access or tuning."""
import base64
import hashlib
import json
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_observed_forward import replay_observed_pair_forward
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

SOURCE = 'wizard-20260919T040312216715Z-0275b1d6e250462abc207ceedd218a9a'


def signed_magnitude(value, bit):
    return -(value & ~(1 << bit)) if value & (1 << bit) else value


def analyze_forward(root, source, *, leg='forward'):
    """Replay one recorded forward trial before decoding its diagnostic samples."""
    root = Path(root).resolve()
    exports = root/'runs/wizard-exports'
    if leg == 'forward':
        replay = replay_observed_pair_forward(exports, source)
        assessment = replay['assessment']
    elif leg == 'return':
        from rocell.application.held_pair_observed_return import replay_observed_pair_return
        replay = replay_observed_pair_return(exports, source)
        assessment = replay['review']['reverse']
    else:
        raise ValueError('Explicit forward or return leg required')
    bundle, digest = _read(exports, source, f'attachment-observed-pair-{leg}.json')
    samples = []; action = None
    for response in bundle['responses']:
        envelope = json.loads(base64.b64decode(response['raw_base64']))
        if 'raw_json' not in envelope:
            continue
        record = json.loads(envelope['raw_json'])
        if record['schema'] == 'rocell.hold_action.v1':
            action = record
        for servo, address, width, read in record.get('reads', []):
            if (servo, address, width) != (14, 56, 15):
                continue
            raw = bytes.fromhex(read[6])
            word = lambda offset: int.from_bytes(raw[offset:offset+2], 'little')
            samples.append(dict(snapshot_index=record['snapshot_index'], start_us=read[1],
                finish_us=read[2], position_counts=word(0),
                speed_library_units=signed_magnitude(word(2), 15),
                load_library_units=signed_magnitude(word(4), 10),
                voltage_raw=raw[6], temperature_raw=raw[7], moving_raw=raw[10],
                current_library_units=signed_magnitude(word(13), 15)))
    if action is None or len(samples) != assessment['snapshot_count']:
        raise ValueError('Complete correlated sample sequence required')
    for sample in samples:
        sample['after_ack_us'] = sample['start_us'] - action['finished_us']
    library = root/'.firmware-tools/user/libraries/SCServo/SMS_STS.cpp'
    result = dict(schema='rocell.r13_tracking_review.v1', source_export=source,
        source_sha256=digest, replay_verified=replay['replay_verified'],
        assessment=assessment, action=action, samples=samples, leg=leg,
        decoder_reference_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
        decoder_basis='Pinned SMS_STS.cpp sign-magnitude ReadSpeed/ReadLoad/ReadCurrent',
        units_calibrated=False, deadband_registers_observed=False,
        cause_established=False, compensation_recommended=False, hardware_access=False)
    if leg == 'return':
        result['paired_forward_assessment'] = replay['review']['forward']
    return result


def main():
    root = Path(__file__).resolve().parents[1]
    exports = root/'runs/wizard-exports'
    report = analyze_forward(root, SOURCE)
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({'mode':'offline-r13-tracking-review'}, [], attachments={
        'tracking-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Tracking export failed')
    print(json.dumps(dict(export_path=saved['path'], samples=report['samples'])))


if __name__ == '__main__':
    main()
