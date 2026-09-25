"""One authenticated preparation/capture, never start/receipt or movement."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_challenge import decode_challenge
from rocell.application.characterization_reference import export_reference
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def load_reviewed_key(root):
    """Load the reviewed private key in memory without hardware access."""
    from provision_startup_r6 import check_private_acl
    from provision_hold_r7 import read_hold_key
    from rocell.providers.windows.diagnostic_image_store import load_image
    private=root/'private-backups/controller-20260918-session1'
    check_private_acl(private)
    image=load_image(private/'observed-pose-plus10-candidate.dpapi')
    if len(image)!=0x160000 or hashlib.sha256(image).hexdigest()!='45320bab56ec1d8e889078a50e2aa0ef79d4d65c59e5dcb89c7a7880f08e7267':
        raise ValueError('Key-source identity mismatch')
    sys.path.insert(0,str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to(root/'.firmware-tools/littlefs-review'):
        raise ValueError('Unexpected filesystem reader')
    return read_hold_key(image,littlefs)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export',required=True)
    parser.add_argument('--revision',type=int,choices=(33,34,48,49,50,51,52),default=33)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    binding=review_recovery_startup(root,args.startup_export,revision=args.revision)
    boot=binding['expected_boot']; exports=root/'runs/wizard-exports'
    key=load_reviewed_key(root)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    # Reserve once, before network I/O. A later process must not reset sequence.
    with (exports/(f'r{args.revision}-capture-'+boot+'.json')).open('x') as stream:
        json.dump(dict(boot=boot,startup_export=args.startup_export,scope='prepare-only'),stream)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    client=CharacterizationHTTP(binding['address'],key=key,boot=boot)
    report=dict(boot=boot,status='INCONCLUSIVE',responses=[],motion_authorized=False,
                target_commands_sent=False,raw_joint_positions_exported=False,
                starting_gate_passed=False,retry=False)
    prefix='/rocell/characterization/'
    def request(method,suffix):
        raw=client(method,prefix+suffix)
        report['responses'].append(dict(method=method,path=prefix+suffix,raw_hex=raw.hex()))
        return raw
    try:
        initial=json.loads(request('GET','status'))
        if initial.get('state')!='NEW' or initial.get('writes_attempted')!=0:
            raise ValueError('Campaign already used or unexpected state')
        request('POST','prepare')  # Read-only servo acquisition; sticky reservation.
        for _ in range(12):
            state=json.loads(request('GET','status'))
            if state.get('writes_attempted')!=0:raise ValueError('Unexpected write count')
            if state.get('state')=='FAULT':
                report['status']='PREPARATION_FAULT';break
            if state.get('state')=='AWAITING_AUTHORIZATION':
                raw=bytes.fromhex(request('GET','challenge').decode())
                report['challenge']=decode_challenge(raw,expected_boot=boot)
                expected_legs=11 if args.revision==51 else 12 if args.revision in (48,49,50,52) else 1
                if len(report['challenge']['manifest']['goals'])!=expected_legs:
                    raise ValueError('Unexpected fixed plan length')
                if args.revision in (34,48,49,50,51,52):
                    # Historical measured samples, authenticated and bound to this
                    # challenge; never substitute commanded goals for positions.
                    reference=bytes.fromhex(request('GET','reference').decode('ascii'))
                    report['reference_export']=export_reference(
                        exports,reference,expected_sha256=report['challenge']['reference'])
                    report['raw_joint_positions_exported']=True
                    if args.revision in (48,49,50,51,52):
                        from rocell.application.characterization_reference import decode_reference
                        if args.revision==48:
                            from rocell.application.local_pair_mapping_batch import plan_mapping_batch
                            expected_plan=plan_mapping_batch()
                            expected_goals=[2386,1728];expected_positions=[2391,1724]
                        elif args.revision==49:
                            from rocell.application.separated_pair_mapping_batch import plan_separated_mapping_batch
                            expected_plan=plan_separated_mapping_batch()
                            expected_goals=[2381,1733];expected_positions=[2387,1728]
                        elif args.revision==50:
                            from rocell.application.fine_pair_lookup_validation import plan_fine_lookup_validation
                            expected_plan=plan_fine_lookup_validation()
                            expected_goals=[2387,1727];expected_positions=[2389,1726]
                        elif args.revision==51:
                            from rocell.application.local_interval_campaign import plan_local_interval_campaign
                            expected_plan=plan_local_interval_campaign()
                            expected_goals=[2389,1725];expected_positions=[2391,1724]
                        else:
                            from rocell.application.ghost_pair_transition_campaign import plan_ghost_pair_transition_campaign
                            expected_plan=plan_ghost_pair_transition_campaign()
                            expected_goals=[2389,1725];expected_positions=[2391,1724]
                        decoded=decode_reference(reference,
                            expected_sha256=report['challenge']['reference'])
                        joints=decoded['poses'][-1]['joints']
                        if report['challenge']['manifest']['goals']!=expected_plan['manifest']['goals']:
                            raise ValueError('Mapping manifest differs')
                        if ([joints[i]['goal'] for i in (1,2)]!=expected_goals or
                            any(abs(value-expected)>1 for value,expected in zip(
                                [joints[i]['position'] for i in (1,2)],expected_positions))):
                            raise ValueError('Mapping starting gate differs')
                        report['starting_gate_passed']=True
                report['status']='READ_ONLY_CAPTURE_PREPARED';break
            time.sleep(0.15)
        else:raise ValueError('Bounded preparation polling exhausted')
    except Exception as error:
        report.update(error_type=type(error).__name__,error_message=str(error),
                      uncertainty=client.session.uncertainty)
    saved=exporter.export({'mode':f'r{args.revision}-campaign-read-only'},[],attachments={
        f'r{args.revision}-campaign-observation.json':json.dumps(report,indent=2).encode()})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Export invalid')
    print(json.dumps(dict(export_path=saved['path'],status=report['status'],
        error_type=report.get('error_type'),target_commands_sent=False,
        raw_joint_positions_exported=report['raw_joint_positions_exported'])))


if __name__=='__main__':main()
