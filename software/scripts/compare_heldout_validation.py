"""Compare the verified held-out candidate/control pair without hardware access."""
import argparse
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


FIXED={
    'heldout_candidate':[[2377,1737],[2388,1726]],
    'heldout_control':[[2377,1737],[2389,1725]],
}
DESIRED=[2390,1725]


def _source(exports,path,attachment):
    selected=Path(path)
    if selected.parent.resolve()!=exports.resolve():raise ValueError('Source outside assigned export folder')
    return _read(exports,selected.name,attachment)[0]


def load_trial(exports,audit_id,variant):
    audit,digest=_read(exports,audit_id,'attachment-next-validation-terminal-review.json')
    if (variant not in FIXED or audit.get('variant')!=variant or
        audit.get('terminal_measurement_usable') is not True or
        audit.get('desired')!=DESIRED or audit.get('general_compensation_validated') is not False):
        raise ValueError('Usable held-out terminal audit required')
    run=_source(exports,audit['source_run'],'attachment-smoke-run.json')
    record=_source(exports,audit['source_result'],'attachment-characterization-result.json')
    expected=FIXED[variant]
    if (run.get('status')!='COMPLETE' or run.get('challenge',{}).get('manifest',{}).get('goals')!=expected or
        len(run.get('legs',[]))!=2 or record.get('leg')!=1 or record.get('goals')!=expected or
        run['legs'][1].get('export_path')!=audit['source_result']):
        raise ValueError('Fixed held-out trial identity differs')
    for index,leg in enumerate(run['legs']):
        retained=_source(exports,leg['export_path'],'attachment-characterization-result.json')
        if (leg.get('leg')!=index or retained.get('leg')!=index or retained.get('goals')!=expected or
            leg.get('assessment',{}).get('continuation_eligible') is not True):
            raise ValueError('Held-out leg evidence differs')
    before=[record['baseline']['joints'][i]['position'] for i in (1,2)]
    actual=[record['observations'][-1]['joints'][i]['position'] for i in (1,2)]
    if before!=audit['before'] or actual!=audit['actual']:
        raise ValueError('Audit and raw held-out endpoint differ')
    prediction=_source(exports,run['baseline_review']['prediction_export'],
                       'attachment-next-validation-predictions.json')
    if (prediction.get('variant')!=variant or prediction.get('targets')!=expected or
        prediction.get('desired')!=DESIRED or prediction.get('campaign')!=run['challenge']['campaign'] or
        prediction.get('reference_sha256')!=run['challenge']['reference']):
        raise ValueError('Held-out frozen prediction provenance differs')
    return audit,digest,prediction['frozen_models']


def compare(exports,candidate_id,control_id):
    candidate,candidate_hash,candidate_model=load_trial(exports,candidate_id,'heldout_candidate')
    control,control_hash,control_model=load_trial(exports,control_id,'heldout_control')
    if candidate_model!=control_model:raise ValueError('Frozen model differs between held-out trials')
    starts_match=all(abs(a-b)<=1 for a,b in zip(candidate['before'],control['before']))
    candidate_error=[a-d for a,d in zip(candidate['actual'],DESIRED)]
    control_error=[a-d for a,d in zip(control['actual'],DESIRED)]
    metrics=lambda error:dict(max_abs=max(map(abs,error)),l1=sum(map(abs,error)),
                              squared=sum(value*value for value in error))
    cm,um=metrics(candidate_error),metrics(control_error)
    result=dict(schema='rocell.heldout_candidate_control_comparison.v1',
        candidate_export=candidate_id,control_export=control_id,
        candidate_audit_sha256=candidate_hash,control_audit_sha256=control_hash,
        candidate_before=candidate['before'],control_before=control['before'],
        starts_match_within_one_count=starts_match,desired=DESIRED,
        candidate_actual=candidate['actual'],control_actual=control['actual'],
        candidate_error=candidate_error,control_error=control_error,
        candidate_metrics=cm,control_metrics=um,
        candidate_improves_max_abs_error=cm['max_abs']<um['max_abs'],
        candidate_ties_all_primary_metrics=cm==um,model_sha256=candidate_model['sha256'],
        model_refitted=False,comparison_eligible=starts_match,
        general_compensation_validated=False,hardware_access=False,movement_authorized=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'heldout-candidate-control-comparison'},[],
        attachments={'heldout-comparison.json':canonical(result)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Held-out comparison export failed')
    return saved['path']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-audit',required=True);parser.add_argument('--control-audit',required=True)
    args=parser.parse_args()
    print(compare(Path(__file__).resolve().parents[1]/'runs/wizard-exports',
                  args.candidate_audit,args.control_audit))
