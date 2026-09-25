"""Analyze verified r37 exports only. No networking, serial or movement API."""
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.matrix_model_review import compare_models
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    exports=Path(__file__).resolve().parents[1]/'runs/wizard-exports'
    source='wizard-20260920T170057808629Z-794d9f59a6c14dad9b37178148c2b70d'
    run, digest=_read(exports,source,'attachment-smoke-run.json')
    ids=[Path(r['export_path']).name for r in run['legs']]+[Path(run['failed_leg_export']['export_path']).name]
    rows=[]
    for ident in ids:
        record, sha=_read(exports,ident,'attachment-characterization-result.json')
        baseline=record['baseline']['joints']; final=record['observations'][-1]['joints']
        target=record['goals'][record['leg']]
        rows.append(dict(leg=record['leg'],target=target,
            before=[baseline[i]['position'] for i in (1,2)],actual=[final[i]['position'] for i in (1,2)],
            goal_delta=[target[j]-baseline[j+1]['goal'] for j in range(2)],
            outcome=record['outcome'],source_export=ident,source_sha256=sha))
    report=compare_models(rows)
    report.update(source_export=source,source_sha256=digest,
        caveats=['Only one complete amplitude cycle; held-out legs both have zero sampled net motion.',
                 'Model selection itself used this dataset; a new independent campaign is required.',
                 'Encoder counts are not independent Cartesian or stylus measurements.',
                 'No causal diagnosis or compensation deployment is justified by this comparison.'])
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-r37-matrix-model-review'},[],attachments={
        'matrix-model-review.json':json.dumps(report,indent=2).encode()})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Review export failed')
    print(json.dumps(dict(export_path=saved['path'],metrics=report['held_out_metrics'],
                         bands=report['bands'],held_out_clear_motion=report['held_out_contains_clear_motion'])))


if __name__=='__main__':main()
