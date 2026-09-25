"""Consolidate a completed or stopped r48 run from verified exports; offline only."""
import argparse
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.local_pair_mapping_batch import plan_mapping_batch
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def summarize(root: Path, run_export: str):
    exports=root/'runs/wizard-exports'
    report,_=_read(exports,run_export,'attachment-smoke-run.json')
    if report.get('challenge',{}).get('manifest',{}).get('goals')!=plan_mapping_batch()['manifest']['goals']:
        raise ValueError('Exact r48 mapping manifest required')
    rows=list(report.get('mapping_rows',[]))
    terminal=report.get('failed_leg_export')
    if terminal is not None:
        record,_=_read(Path(terminal['export_path']).parent,Path(terminal['export_path']).name,
                       'attachment-characterization-result.json')
        baseline=record['baseline']['joints'];endpoint=record['observations'][-1]['joints']
        target=record['goals'][record['leg']]
        baseline_goals=[baseline[index]['goal'] for index in (1,2)]
        actual=[endpoint[index]['position'] for index in (1,2)]
        rows.append(dict(leg=record['leg'],source_export=terminal['export_path'],target=target,
            approach_direction=1 if target[0]>baseline_goals[0] else -1,
            command_delta=[target[i]-baseline_goals[i] for i in range(2)],
            baseline_goals=baseline_goals,
            baseline_positions=[baseline[index]['position'] for index in (1,2)],actual=actual,
            target_residual=[actual[i]-target[i] for i in range(2)],
            assessment=dict(status=record['outcome'],continuation_eligible=False,
                            reason=report['fault_export']['reason'])))
    if not rows or [row['leg'] for row in rows]!=list(range(len(rows))):
        raise ValueError('Contiguous mapping evidence required')
    document=dict(schema='rocell.local_pair_mapping_result.v1',source_run=run_export,
        plan_sha256=plan_mapping_batch()['plan_sha256'],status=report['status'],rows=rows,
        accepted_legs=len(report.get('legs',[])),writes_attempted=len(rows),
        stop_reason=report.get('fault_export',{}).get('reason'),
        observed_primary_range=[min(row['actual'][0] for row in rows),
                                max(row['actual'][0] for row in rows)],
        consecutive_small_response_stop=(report.get('fault_export',{}).get('reason')=='NO_CLEAR_RESPONSE'
            and len(rows)>=2 and all(max(abs(v) for v in row['command_delta'])>0 for row in rows[-2:])),
        model_fitted=False,compensation_promoted=False,general_compensation_validated=False,
        continuation_authorized=False,hardware_access=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'local-pair-mapping-partial-review'},[],attachments={
        'local-pair-mapping-result.json':canonical(document)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Summary export invalid')
    return saved['path'],document


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_export');args=parser.parse_args()
    path,document=summarize(Path(__file__).resolve().parents[1],args.run_export)
    print(json.dumps(dict(export_path=path,status=document['status'],
                          writes=document['writes_attempted'],stop_reason=document['stop_reason'])))


if __name__=='__main__':main()
