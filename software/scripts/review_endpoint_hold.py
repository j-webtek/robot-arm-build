"""Export a verified-source endpoint hold review without accessing hardware."""
import argparse
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.endpoint_hold_review import review_endpoint_hold
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('trial');p.add_argument('observation');p.add_argument('attachment')
    args=p.parse_args();root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    trial,trial_hash=_read(root,args.trial,'attachment-cartesian-trial.json')
    observed,observation_hash=_read(root,args.observation,args.attachment)
    reports=[s['report'] for s in observed['steps'] if s.get('name')=='read_only_wifi_feedback']
    if len(reports)!=1:raise ValueError('Exactly one feedback observation required')
    result=review_endpoint_hold(trial,reports[0])
    result.update(trial_export=args.trial,trial_sha256=trial_hash,
        observation_export=args.observation,observation_sha256=observation_hash)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-endpoint-hold-review'},[],attachments={
        'endpoint-hold.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid review export')
    print(json.dumps(dict(export=receipt['path'],review=result)))


if __name__=='__main__':main()
