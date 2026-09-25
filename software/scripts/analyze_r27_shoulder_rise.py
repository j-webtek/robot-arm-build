"""Replay the retained r27 trial and export its endpoint shortfall, offline only.

No controller connection, authorization receipt, firmware or settings write.
Counts describe servo encoders, not independently measured tool-tip accuracy.
"""
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.shoulder_rise_review import ShoulderRiseReview
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    exports = Path(__file__).resolve().parents[1] / 'runs/wizard-exports'
    run_id = 'wizard-20260919T203825127176Z-0533f1bb58ca40d3b5371679adc34cd4'
    status_id = 'wizard-20260919T203853177393Z-9558379d4ab34ad8a3e4eec1b34302d5'
    run, _ = _read(exports, run_id, 'attachment-shoulder-run.json')
    status_path = exports / status_id
    if not verify_export(status_path)['valid']:
        raise ValueError('Invalid retained status export')
    status = json.loads((status_path / 'attachment-shoulder-status.txt').read_bytes())
    review = ShoulderRiseReview(run['boot_id'], run['command_id'])
    records = []
    for record_path in run['records']:
        path = Path(record_path).resolve()
        if path.parent != exports or not verify_export(path)['valid']:
            raise ValueError('Invalid or out-of-workspace event export')
        records.append(review.accept((path / 'attachment-shoulder-event.txt').read_bytes()))
    if (len(records) != 14 or status['boot_id'] != run['boot_id']
            or status['reason'] != 'RISE_OBSERVATION_DEADLINE'
            or status['preload_writes'] != 1 or status['enable_delivery'] != 'NOT_ATTEMPTED'):
        raise ValueError('Unexpected retained trial identity or outcome')
    samples = records[3:]
    joints = []
    for i in (1, 2):
        start = records[0]['joints'][i][1]
        target = review.targets[i-1]
        positions = [sample['joints'][i][1] for sample in samples]
        joints.append(dict(servo_id=11+i, start=start, target=target,
            final_sampled_position=positions[-1], requested_delta=target-start,
            observed_delta=positions[-1]-start, signed_position_error=positions[-1]-target,
            post_command_positions=positions, plateau_in_all_samples=len(set(positions)) == 1))
    report = dict(schema='rocell.r27_endpoint_analysis.v1', run_export=run_id,
        status_export=status_id, boot_id=run['boot_id'], records_replayed=len(records),
        sample_count=len(samples), joints=joints,
        first_sample_after_command_us=samples[0]['scan_finished_us']-review.sent,
        last_sample_after_command_us=samples[-1]['scan_finished_us']-review.sent,
        consecutive_verified_arrivals=review.arrivals, controller_reason=status['reason'],
        outcome='CORRECT_DIRECTION_PARTIAL_TRAVEL_NOT_VERIFIED_ARRIVAL',
        hardware_access=False, compensation_applied=False, physical_accuracy_verified=False,
        limitation='Last sampled positions are historical, not a fresh current-pose query.')
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'offline-r27-endpoint-analysis'}, [],
                            attachments={'endpoint-analysis.json': canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Analysis export verification failed')
    print(json.dumps(dict(export_path=saved['path'], **report)))


if __name__ == '__main__':
    main()
