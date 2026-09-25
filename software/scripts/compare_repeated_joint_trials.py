"""Offline comparison of same-command trials; does not authorize another move."""
import argparse
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('first');parser.add_argument('second')
    args=parser.parse_args()
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    sources=[];transactions=[]
    for export_id in (args.first,args.second):
        report,digest=_read(root,export_id,'attachment-cartesian-trial.json')
        run=report['run'];tx=run['transaction']
        if run.get('error') is not None or not run.get('acknowledgment_received') or not tx['rows']:
            raise ValueError('Clean retained command/feedback run required')
        sources.append(dict(export=export_id,attachment_sha256=digest,status=report['status'],
            samples=len(tx['rows']),wire_result=tx['result'],desired_result=tx['desired_endpoint_result']))
        transactions.append(tx)
    a,b=transactions
    same_command=a['command']==b['command']
    same_start=a['baseline_joints']==b['baseline_joints']
    same_candidate=a['local_candidate']==b['local_candidate']
    differences=[y-x for x,y in zip(a['rows'][-1][3],b['rows'][-1][3])]
    result=dict(schema='rocell.repeated_joint_trial_comparison.v1',sources=sources,
        same_command=same_command,same_reported_start=same_start,same_candidate=same_candidate,
        comparable=same_command and same_start and same_candidate,
        second_minus_first_final_joints_rad=differences,
        reported_endpoint_equal=all(abs(v)<=1e-8 for v in differences),
        sample_size=2,physical_repeatability_verified=False,motion_authorized=False)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-repeat-comparison'},[],attachments={
        'repeat-comparison.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:
        raise RuntimeError('Comparison export verification failed')
    print(json.dumps(dict(export=receipt['path'],comparable=result['comparable'],
        reported_endpoint_equal=result['reported_endpoint_equal'],
        final_differences_rad=differences,
        desired_results=[s['desired_result'] for s in sources])))


if __name__=='__main__':main()
