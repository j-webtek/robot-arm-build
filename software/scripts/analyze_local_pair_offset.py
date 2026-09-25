"""Reproduce r29-trained/r31-evaluated local offset analysis; no hardware I/O."""
import json
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.local_pair_offset import LocalPairOffset
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root=Path(__file__).resolve().parents[1]/'runs/wizard-exports'
    training_id='wizard-20260919T212458408646Z-f7e6a7fbf4e942208ea216666ddf55f0'
    evaluation_id='wizard-20260919T234006065057Z-53ea59edfe2d4b20bfc7d3eaae25253e'
    training,training_hash=_read(root,training_id,'attachment-settled-recovery-analysis.json')
    run,run_hash=_read(root,evaluation_id,'attachment-local-step-run.json')
    if (training['schema']!='rocell.r29_settled_recovery_analysis.v1' or
            run['state']!='STOPPED' or run['settling']['state']!='SETTLED' or
            run['settling']['parent_motion_state']!='FAULT'):
        raise ValueError('Unexpected evidence outcomes')
    # Bind derived r29 training analysis to its retained source receipts.
    for ident,name,digest in (
        (training['run_export'],'attachment-shoulder-run.json',training['run_receipt']),
        (training['settled_assessment_export'],'attachment-pose-assessment.json',training['settled_receipt'])):
        _,observed=_read(root,ident,name)
        if observed!=digest:raise ValueError('Training source receipt differs')
    paths=[*run['records'],*run['raw_exports'],run['settling']['original_export'],
           *run['settling']['records'],*run['settling']['raw_exports']]
    for value in paths:
        path=Path(value).resolve()
        if path.parent!=root or not verify_export(path)['valid']:raise ValueError('Invalid source export')
    samples=[]
    for value in run['settling']['raw_exports']:
        raw=(Path(value)/'attachment-settling-record.txt').read_bytes()
        sample=json.loads(raw)
        if sample['boot_id']!=run['boot_id'] or sample['event']!='FAULT_SETTLING_SAMPLE':
            raise ValueError('Settling identity differs')
        samples.append(sample)
    if len(samples)<3:raise ValueError('Missing settling evidence')
    final=samples[-1]['joints']
    trained=training['joints'][1:3]
    if [j['servo_id'] for j in trained]!=[12,13]:raise ValueError('Shoulder identity')
    model=LocalPairOffset(training_id,tuple(j['commanded_goal'] for j in trained),
                         tuple(j['settled_sampled_position'] for j in trained))
    actual=[final[i][1] for i in (1,2)];goals=[final[i][2] for i in (1,2)]
    if goals!=run['plan']['targets']:raise ValueError('Readback goals differ from plan')
    evaluation=model.evaluate(evidence_id=evaluation_id,goals=goals,actual=actual)
    preview=model.propose(current_positions=actual,current_goals=goals,
                          desired=[actual[0]-14,actual[1]+14])
    report=dict(schema='rocell.local_pair_offset_analysis.v1',training_export=training_id,
        training_sha256=training_hash,evaluation_export=evaluation_id,evaluation_sha256=run_hash,
        frozen_offset=list(model.offset),evaluation=evaluation,historical_preview=preview,
        model='position = goal + constant local residual; constrained coupled-sum projection',
        training_trials=1,evaluation_trials=1,retrospective_model_selection=True,
        prospective_validation=False,hardware_access=False,movement_authorized=False,
        limitation='One later-trial retrospective check, same direction and nearby pose; not global accuracy or live admission.')
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-local-pair-offset'},[],
        attachments={'local-pair-offset-analysis.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Analysis export failed')
    print(canonical(dict(export_path=saved['path'],**report)).decode())


if __name__=='__main__':main()
