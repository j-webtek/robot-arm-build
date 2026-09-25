"""Compare historical shoulder trials without pooling unlike evidence.

The older recovery input is a saved derived analysis, not a newly validated
same-boot settling stream. Preserve that distinction in every exported report.
"""
import argparse
import hashlib
import json
from pathlib import Path

from .first_motion_contract import canonical
from .physical_local_step_review import _attachment, import_local_step
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def compare_results(recovery, local):
    """Pure arithmetic comparison; this function alone verifies no source files."""
    if (recovery.get('schema') != 'rocell.r29_settled_recovery_analysis.v1'
            or recovery.get('diagnostic_restart_between_command_and_settled_capture') is not True
            or recovery.get('physical_accuracy_verified') is not False
            or local.get('schema') != 'rocell.physical_local_step_review.v1'
            or local.get('basis') != 'DEVICE_CAPTURE'
            or not isinstance(local.get('settling'), dict)
            or local['settling'].get('stability_verified') is not True):
        raise ValueError('Unsupported or incomplete comparison evidence')
    joints = recovery.get('joints')
    if not isinstance(joints, list) or len(joints) != 7:
        raise ValueError('Seven recovery joints required')
    for sid, joint in enumerate(joints, 11):
        names = ('initial_position', 'settled_sampled_position', 'commanded_goal',
                 'observed_delta', 'residual', 'servo_id')
        if (any(type(joint.get(name)) is not int for name in names)
                or joint['servo_id'] != sid
                or any(not 0 <= joint[name] <= 4095 for name in names[:3])
                or joint['observed_delta'] != joint['settled_sampled_position']-joint['initial_position']
                or joint['residual'] != joint['settled_sampled_position']-joint['commanded_goal']):
            raise ValueError('Inconsistent recovery arithmetic')
    rows = []
    for offset, endpoint in enumerate(local['endpoints'], 1):
        if offset > 2 or endpoint['servo_id'] != 11+offset:
            raise ValueError('Shoulder pair required')
        old = joints[offset]
        final = local['settling']['final_positions'][offset]
        rows.append(dict(servo_id=old['servo_id'],
            recovery_start=old['initial_position'], recovery_target=old['commanded_goal'],
            recovery_settled=old['settled_sampled_position'], recovery_error=old['residual'],
            local_start=endpoint['start_counts'], local_target=endpoint['accepted_counts'],
            local_movement_error=endpoint['endpoint_error_counts'], local_settled=final,
            local_settled_error=final-endpoint['accepted_counts']))
    if len(rows) != 2:
        raise ValueError('Two shoulder endpoints required')
    return dict(schema='rocell.physical_trial_comparison.v1', basis='HISTORICAL_DEVICE_EVIDENCE',
                rows=rows, pooled_statistics=False, compensation_proposed=False,
                movement_authorized=False,
                evidence_levels=dict(recovery='VERIFIED_SAVED_DERIVED_ANALYSIS',
                                     local='REVALIDATED_MOVEMENT_AND_FAULT_LINKED_SETTLING'),
                limitations=[
                    'Different targets and recorded firmware revisions; not matched repeats.',
                    'Recovery settling follows a diagnostic restart; local settling is same-boot.',
                    'Older derived analysis is not equivalent to replaying all original raw pose data.',
                    'Firmware/configuration equivalence has not been established.',
                    'Similar residuals suggest a hypothesis, not a validated correction model.',
                    'Counts are not independently measured Cartesian or stylus-tip accuracy.'])


def render_comparison(summary):
    lines = ['# Historical shoulder trial comparison', '',
             '**Unlike trials: no pooled accuracy, repeatability or compensation claim.**', '',
             'Recovery = saved r29 analysis; local = revalidated r31 movement and settling.', '',
             '| Servo | Recovery target | Recovery settled | Recovery error | Local target | Local movement error | Local settled | Local settled error |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in summary['rows']:
        lines.append('| ' + ' | '.join(str(row[key]) for key in (
            'servo_id', 'recovery_target', 'recovery_settled', 'recovery_error',
            'local_target', 'local_movement_error', 'local_settled', 'local_settled_error')) + ' |')
    lines += ['', 'Values are encoder counts. Original motion failures remain failures.', '',
              '## Limits of this comparison', '']
    lines += ['- '+value for value in summary['limitations']]
    lines += ['', '## Next useful experiment', '',
              'Matched targets, repeated from both directions under one fixed configuration, '
              'using a fresh bounded starting pose. This report does not authorize that experiment.']
    return '\n'.join(lines)+'\n'


def export_comparison(recovery_source, local_source, destination):
    recovery_source = Path(recovery_source).resolve()
    raw, identity = _attachment(recovery_source, 'attachment-settled-recovery-analysis.json')
    recovery = json.loads(raw)
    references = []
    # Check the derived report's exact input attachment digests, not just its own manifest.
    for field, receipt, filename in (
        ('run_export', 'run_receipt', 'attachment-shoulder-run.json'),
        ('settled_assessment_export', 'settled_receipt', 'attachment-pose-assessment.json')):
        name = recovery.get(field)
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError('Sibling recovery export identifier required')
        path = (recovery_source.parent / name).resolve()
        if path.parent != recovery_source.parent:
            raise ValueError('Recovery reference escaped source root')
        payload, referenced = _attachment(path, filename)
        if hashlib.sha256(payload).hexdigest() != recovery.get(receipt):
            raise ValueError('Recovery input digest differs')
        references.append(referenced)
    local = import_local_step(local_source)
    summary = compare_results(recovery, local)
    summary['sources'] = [identity, *references, *local['sources']]
    exporter = WizardDiagnosticExporter(Path(destination).resolve())
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'physical-trial-comparison'}, [], attachments={
        'trial-comparison.json': canonical(summary),
        'trial-comparison.md': render_comparison(summary).encode('utf-8')})
    if not verify_export(Path(saved['path']))['valid']:
        raise OSError('Comparison export verification failed')
    return saved['path']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recovery-source', required=True, type=Path)
    parser.add_argument('--local-source', required=True, type=Path)
    parser.add_argument('--exports', required=True, type=Path)
    args = parser.parse_args()
    print(export_comparison(args.recovery_source, args.local_source, args.exports))


if __name__ == '__main__':
    main()
