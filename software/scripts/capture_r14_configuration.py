"""Receipt-bound read-only r14 configuration capture; never installs or moves."""
import argparse
import json
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_installation_evidence import review_pair_installation
from rocell.application.held_pair_capabilities import read_pair_capabilities
from rocell.application.product_ghost_export_review import _read
from rocell.application.elbow_configuration_capture import capture_configuration
from rocell.application.servo_start_authorization import _hex


def review_startup(root, export_id, revision=14):
    if revision == 16:
        from rocell.application.supported_recovery_installation import review_recovery_startup
        binding=review_recovery_startup(root,export_id)
        return binding['address'],binding['expected_boot']
    if revision != 14: raise ValueError('Reviewed diagnostic revision required')
    installation=review_pair_installation(root,revision=14)
    exports=root/'runs/wizard-exports'
    startup,_=_read(exports,export_id,'attachment-r14-startup-observation.json')
    if (startup.get('schema')!='rocell.r14_startup_observation.v1' or
            startup.get('status')!='IDLE_AND_PAIR_PROTOCOL_OBSERVED' or
            startup.get('address')!='192.168.0.225' or
            any(startup.get(field) is not False for field in
                ('challenge_requested','servo_commands_sent','provisioning_performed','reset_performed','retry_allowed'))):
        raise ValueError('Reviewed r14 startup required')
    retained,_=_read(exports,startup['installation_export_id'],'attachment-held-pair-installation-evidence.json')
    if canonical(retained)!=canonical(installation):raise ValueError('Startup installation linkage differs')
    boot=startup['hold_status']['instance_id'];_hex(boot,16)
    if startup['capability_observation']['capabilities']['boot_id']!=boot:
        raise ValueError('Startup boot mismatch')
    return startup['address'],boot


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export',required=True)
    parser.add_argument('--revision',type=int,choices=(14,16),default=14)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight-only',action='store_true')
    modes.add_argument('--capture',action='store_true')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    address,boot=review_startup(root,args.startup_export,args.revision)
    if args.preflight_only:
        print(json.dumps(dict(status=f'LOCAL_R{args.revision}_CAPTURE_PREFLIGHT_VERIFIED',expected_boot=boot,
            hardware_access=False,configuration_changes_authorized=False)))
        return
    # Fresh read-only boot identity check before the one-shot acquisition POST.
    read_pair_capabilities(address=address,expected_boot=boot)
    print(json.dumps(capture_configuration(root/'runs/wizard-exports',address=address,expected_boot=boot)))


if __name__=='__main__':main()
