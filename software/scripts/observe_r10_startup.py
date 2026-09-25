"""One read-only r10 startup observation; no challenge, motion, reset or retry."""
import base64
import argparse
import hashlib
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_installation_evidence import export_pair_installation_review
from rocell.application.held_pair_capabilities import PATH, validate_pair_capabilities
from rocell.application.hold_transport_snapshot import HoldHTTPReader, STATUS
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser=argparse.ArgumentParser(description='Read-only startup observation; no movement or reset.')
    parser.add_argument('--revision',type=int,choices=(10,11,12,13,14,16,17,19,20,21,22,23,24,25,26,27,28,29,31,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,81,82,83,84),default=10)
    parser.add_argument('--observed-pose-stage-export')
    parser.add_argument('--observed-pose-installation-export')
    args=parser.parse_args();revision=args.revision
    if bool(args.observed_pose_stage_export)!=bool(args.observed_pose_installation_export):
        parser.error('Both observed-pose receipt IDs are required together')
    if args.observed_pose_stage_export and revision!=21:
        parser.error('Observed-pose settings require r21')
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    settings_binding=None
    if args.observed_pose_stage_export:
        from rocell.application.observed_pose_installation import review_observed_installation
        settings_binding=review_observed_installation(root,
            stage_export=args.observed_pose_stage_export,
            installation_export=args.observed_pose_installation_export)
    installation=export_pair_installation_review(root,exports,revision=revision)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    report=dict(schema=f'rocell.r{revision}_startup_observation.v1',address='192.168.0.225',
        installation_export_id=Path(installation['export_path']).name,
        status='INCONCLUSIVE',responses=[],challenge_requested=False,servo_commands_sent=False,
        provisioning_performed=False,reset_performed=False,retry_allowed=False)
    if settings_binding is not None:
        report['observed_pose_installation']=settings_binding
    reader=HoldHTTPReader(report['address'])
    def read(path,maximum):
        raw=reader._get(path,maximum_bytes=maximum,timeout_seconds=3)
        report['responses'].append(dict(path=path,raw_base64=base64.b64encode(raw).decode(),
            sha256=hashlib.sha256(raw).hexdigest()))
        return raw
    try:
        first=decode_diagnostic_json(read(STATUS,512),maximum=512)
        if (first.get('schema')!='rocell.hold_transport.v1' or first.get('state')!='IDLE'
                or first.get('reason')!='NOT_CONFIGURED' or first.get('records')!=0
                or first.get('storage_fault') is not False):
            raise ValueError('Unexpected startup hold status')
        report['hold_status']=first
        report['capability_observation']=validate_pair_capabilities(read(PATH,768),
            expected_boot=first['instance_id'])
        last=decode_diagnostic_json(read(STATUS,512),maximum=512)
        if first!=last:raise ValueError('Startup status changed during observation')
        report['status']='IDLE_AND_PAIR_PROTOCOL_OBSERVED'
    except Exception as error:
        report['error_type']=type(error).__name__
    saved=exporter.export({'mode':f'r{revision}-startup-observation'},[],
        attachments={f'r{revision}-startup-observation.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Startup export verification failed')
    print(json.dumps(dict(export_path=saved['path'],**report)))


if __name__=='__main__':main()
