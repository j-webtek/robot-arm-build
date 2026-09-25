"""Run a finite camera-free ghost regression suite and export all evidence.

No native providers are imported. A suite pass means the synthetic cases behaved
as expected, including stopping on faults; it never means the arm is qualified.
"""
import argparse
import json
from pathlib import Path
from rocell.application.ghost_endpoint_rehearsal import rehearse_ghost_endpoints
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


CASES=('NONE','DELAYED_ARRIVAL','BASELINE_MISMATCH','SHORT_WRITE','UNCHANGED',
       'CANCEL_AFTER_WRITE','CLEANUP_PENDING','MISSING_FEEDBACK','POSITION_BIAS')


def evaluate(report):
    """Check progression and write count, not just the top-level status label."""
    success=report['fault'] in ('NONE','DELAYED_ARRIVAL')
    expected_count=len(report['plan']['trials']) if success else 2
    rows=report['trial_results']
    checks=dict(
        outcome=report['status']==('SIMULATED_SEQUENCE_COMPLETE' if success else 'SIMULATED_SEQUENCE_STOPPED'),
        trial_count=len(rows)==expected_count,
        skipped=report['skipped_trial_ids']==[t['trial_id'] for t in report['plan']['trials'][expected_count:]],
        prior_legs_verified=all(r['trial']['status']=='OBSERVED_ENDPOINT_DWELL' for r in rows[:1]),
        all_successful=not success or all(r['trial']['status']=='OBSERVED_ENDPOINT_DWELL' for r in rows),
        failed_leg=success or (len(rows)==2 and rows[-1]['trial']['status']!='OBSERVED_ENDPOINT_DWELL'),
        one_write_or_prewrite_rejection=all(len(r['simulated_wire_writes'])==(
            0 if r['fault']=='BASELINE_MISMATCH' else 1) for r in rows),
        no_hardware=report['native_device_opens']==0 and report['physical_motion_commands']==0
            and report['physical_authority'] is False)
    return dict(passed=all(checks.values()),checks=checks)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--export-dir',type=Path)
    args=parser.parse_args()
    root=args.workspace.resolve(strict=True)
    exporter=WizardDiagnosticExporter((args.export_dir or root/'software/runs/wizard-exports').resolve())
    exporter.prepare(create=True)
    attachments={}; summaries=[]
    for fault in CASES:
        report=rehearse_ghost_endpoints(root,'aba',fault=fault,fault_trial=2)
        verdict=evaluate(report)
        case_export=exporter.export(dict(mode='offline-ghost-simulation',case=fault),[],attachments={
            'ghost-case.json':json.dumps(report,allow_nan=False).encode()})
        case_path=Path(case_export['path']).resolve()
        if not verify_export(case_path)['valid']:
            raise ValueError('Ghost case export verification failed')
        summaries.append(dict(case=fault,status=report['status'],attempted=len(report['trial_results']),
            skipped=len(report['skipped_trial_ids']),plan_sha256=report['plan_sha256'],
            case_export=case_path.name,**verdict))
    passed=all(s['passed'] for s in summaries)
    summary=dict(schema='rocell.ghost_suite.v1',status='SIMULATION_SUITE_PASS' if passed else 'SIMULATION_SUITE_FAIL',
        text='aba',fault_trial=2,cases=summaries,physical_qualification=False,
        camera_required=False,hardware_access=False)
    attachments['ghost-suite.json']=json.dumps(summary,indent=2,allow_nan=False).encode()
    lines=['# Ghost keyboard regression suite','',summary['status'],'',
        'Synthetic A–B–A endpoints only. No arm or camera access. Not physical qualification.','',
        '| Case | Attempted | Skipped | Expected behavior verified |','| --- | ---: | ---: | --- |']
    lines += [f"| {s['case']} | {s['attempted']} | {s['skipped']} | {s['passed']} |" for s in summaries]
    lines += ['', '## Case exports', '']
    lines += [f"- {s['case']}: `{s['case_export']}`" for s in summaries]
    lines += ['', 'Faults are injected at the second nonzero-motion trial. Raw per-leg requests,',
        'synthetic feedback and verdicts are in each sibling case export (attachment-ghost-case.json).',
        'Attempt IDs vary between runs; compare plan hashes and case outcomes, not byte-identical archives.',
        'Live elbow response, route clearance, tool/board calibration and actual input remain unverified.']
    attachments['ghost-summary.md']='\n'.join(lines).encode()
    receipt=exporter.export(dict(mode='offline-ghost-simulation',status=summary['status']),[],attachments=attachments)
    verified=verify_export(Path(receipt['path']).resolve())['valid']
    print(json.dumps(dict(status=summary['status'],cases=len(summaries),export=receipt['path'],export_valid=verified)))
    return 0 if passed and verified else 1


if __name__=='__main__':
    raise SystemExit(main())
