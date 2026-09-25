"""Export the next fixed validation plan from verified physical evidence."""
import json
from pathlib import Path
from compare_ab_pilot import load_trial
from rocell.application.product_ghost_export_review import _read
from rocell.application.next_compensation_validation import draft
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1];exports=(root/'runs/wizard-exports').resolve()
    control_id='wizard-20260920T183801352365Z-150c883b704449b581992fc4a59618c2'
    candidate_id='wizard-20260920T185928036920Z-212a0ec7b32949d5ac9117297277feb2'
    _,control_sha,control_model=load_trial(exports,control_id,'control')
    candidate,candidate_sha,candidate_model=load_trial(exports,candidate_id,'compensated')
    if control_model!=candidate_model:raise ValueError('Pilot models differ')
    raw,_=_read(exports,Path(candidate['source_result']).name,'attachment-characterization-result.json')
    last=raw['observations'][-1]['joints']
    plan=draft(frozen=candidate_model,bounds=raw['bounds'],
        installed_goals=[last[i]['goal'] for i in (1,2)],
        installed_positions=[last[i]['position'] for i in (1,2)])
    plan.update(source_control=dict(export_id=control_id,sha256=control_sha),
                source_candidate=dict(export_id=candidate_id,sha256=candidate_sha))
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'next-compensation-validation-plan'},[],attachments={
        'next-validation-plan.json':json.dumps(plan,indent=2).encode()})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Plan export failed')
    print(json.dumps(dict(export_path=saved['path'],maximum_total_writes=10,
        reverse_candidate=plan['reverse_candidate']['manifest']['goals'][-1],
        reverse_control=plan['reverse_control']['manifest']['goals'][-1],
        hardware_access=False)))


if __name__=='__main__':main()
