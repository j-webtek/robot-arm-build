"""Replay nine retained ladder transitions and export an offline comparison.

No hardware access. This is one forward traversal, not a repeatability study.
"""
import hashlib
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.large_pose_relief_record import (
    assess_large_pose_relief_record, decode_large_pose_relief_record,
)
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

SOURCES = (
    ('P1', 'wizard-20260923T024713112793Z-299f2bdab3454e0fb68cc1cdc7cd44f0'),
    ('P2L', 'wizard-20260923T194529289849Z-76fd6c1bf73a4a6eacf42e7510b2072d'),
    ('P2', 'wizard-20260923T201517566882Z-2a37583111464777b465b59ccec7b9f0'),
    ('P3E', 'wizard-20260923T220934352526Z-00cc861d428f4b168b5c1ead42c5de8e'),
    ('P3', 'wizard-20260924T000623600641Z-c2103044389a40f4a53461447c9b9ea8'),
    ('T4L', 'wizard-20260924T094712566120Z-c199a22385e441c0b96efde228b164e1'),
    ('T4', 'wizard-20260924T100122313690Z-ba8afa38d92b436c8f137dae16978a84'),
    ('P4E', 'wizard-20260924T101235379282Z-701e8f9afca3454682c92dafbb258f43'),
    ('P4', 'wizard-20260924T182321443347Z-87b68bc4624a4e1b80c6fb0af4027e5e'),
)


def summarize(root):
    exports = Path(root).resolve() / 'runs/wizard-exports'
    rows = []
    previous = None
    for profile, export_id in SOURCES:
        saved, digest = _read(exports, export_id, 'attachment-large-pose-relief-assessment.json')
        folder = exports / export_id
        if not verify_export(folder)['valid']:
            raise ValueError('Invalid source export: ' + export_id)
        raw = bytes.fromhex((folder/'attachment-large-pose-relief.hex.txt').read_text('ascii'))
        assessment = assess_large_pose_relief_record(raw, expected_boot=saved['boot'], profile=profile)
        if canonical(assessment) != canonical(saved):
            raise ValueError('Source assessment differs from replay')
        record = decode_large_pose_relief_record(raw, profile=profile)
        start = [j['position'] for j in record['start'][-1]['joints']]
        final = [j['position'] for j in record['endpoint'][-1]['joints']]
        selected = [i-11 for i in assessment['synchronized_servo_ids']]
        rows.append(dict(profile=profile, source_export=export_id,
            assessment_sha256=digest, record_sha256=hashlib.sha256(raw).hexdigest(),
            selected_servo_ids=assessment['synchronized_servo_ids'],
            selected_movement_counts=[assessment['position_delta_counts'][i] for i in selected],
            selected_endpoint_error_counts=[assessment['endpoint_error_counts'][i] for i in selected],
            maximum_passive_drift_counts=max(abs(assessment['position_delta_counts'][i])
                for i in range(7) if i not in selected),
            previous_endpoint_to_start_delta_counts=None if previous is None else
                [start[i]-previous[i] for i in range(7)],
            final_positions=final,
            final_goals=[j['goal'] for j in record['endpoint'][-1]['joints']],
            final_capture_after_dispatch_ms=(record['endpoint'][-1]['finished_us']-record['sent_us'])/1000))
        previous = final
    errors = [abs(e) for row in rows for e in row['selected_endpoint_error_counts']]
    report = dict(schema='rocell.p1_to_p4_retained_ladder_summary.v1', rows=rows,
        transitions=len(rows), maximum_selected_endpoint_error_counts=max(errors),
        mean_absolute_selected_endpoint_error_counts=sum(errors)/len(errors),
        maximum_passive_drift_counts=max(r['maximum_passive_drift_counts'] for r in rows),
        hardware_access=False, movement_authorized=False, compensation_applied=False,
        limitations=['One retained forward traversal; not repeated or reverse validation',
                     'Initial P0-to-T1 transition excluded from this comparison',
                     'Joint feedback is not external tool-tip or Cartesian measurement',
                     'Capture latency includes settling and sampling, not pure motion time',
                     'No proof of board clearance, contact accuracy or general compensation'])
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode':'p1-to-p4-offline-summary'}, [], attachments={
        'p1-to-p4-summary.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Summary export invalid')
    return dict(export=saved['path'], **report)


if __name__ == '__main__':
    print(json.dumps(summarize(Path(__file__).resolve().parents[1])))
