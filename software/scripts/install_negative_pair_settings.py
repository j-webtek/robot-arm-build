"""One approved r16 filesystem direction replacement and startup; no movement."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from stage_negative_pair_settings import digest, PROPOSED, DESTINATION
from provision_startup_r6 import check_private_acl
from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_installation_evidence import review_pair_installation
from rocell.application.held_pair_settings import encode_pair_settings
from rocell.application.r10_provisioned_evidence import CANDIDATE, POLICY, SETTINGS
from rocell.application.product_ghost_export_review import _read
from rocell.application.native_provisioning_validator import NativeProvisioningValidator
from rocell.application.startup_provisioning_run import _run_provisioning
from rocell.providers.windows.diagnostic_image_store import load_image, save_image

STAGE='wizard-20260919T120836418654Z-a650a5a7eb314cc9b756964c18b236ce'
IMAGE='d1c041bcb4e90082685babc16698bcef3c639d87464932d6534d8056b71ce3aa'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorized-direction-install-and-startup',action='store_true',required=True)
    parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    private=root/'private-backups/controller-20260918-session1'
    check_private_acl(private)
    if (private/'pair-negative6-provisioning-events.jsonl').exists():
        raise ValueError('Installation already consumed; no retry')
    installation=review_pair_installation(root,revision=16)
    report,_=_read(root/'runs/wizard-exports',STAGE,'attachment-negative-pair-staging.json')
    if (canonical(report['installation'])!=canonical(installation) or
        report['review']['candidate_sha256']!=IMAGE or report['settings_sha256']!=PROPOSED):
        raise ValueError('Staged candidate receipt changed')
    source=load_image(private/'pair-r10-settings-candidate.dpapi')
    candidate=load_image(private/DESTINATION)
    if digest(source)!=CANDIDATE or digest(candidate)!=IMAGE: raise ValueError('Private image mismatch')
    hold=canonical(json.loads((root/'docs/hold-r7-supported-pose-draft.json').read_bytes()))
    previous=encode_pair_settings(forward_command_id='r10-elbow-forward',return_command_id='r10-elbow-return')
    settings=encode_pair_settings(forward_command_id='r10-elbow-forward',return_command_id='r10-elbow-return',offset_counts=-6)
    if (digest(hold),digest(previous),digest(settings))!=(POLICY,SETTINGS,PROPOSED):
        raise ValueError('Public settings identity mismatch')
    sketch=root/'.firmware-tools/configured-diagnostic-candidate-r16/RoArm-M3_example'
    build=Path(tempfile.mkdtemp(prefix='negative-install-validators-',dir=root/'.firmware-tools'))
    def validator(name,adapter):
        exe=build/(name+'.exe')
        subprocess.run(['clang++','-std=c++17','-I'+str(sketch),
            '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),str(root/adapter),
            '-o',str(exe)],check=True,capture_output=True,timeout=60)
        return NativeProvisioningValidator(exe,digest(exe.read_bytes()))
    pv=validator('pair','firmware/validators/validate_pair_provisioning.cpp')
    hv=validator('hold','firmware/diagnostics/validate_hold_provisioning.cpp')
    sys.path.insert(0,str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    sys.path.insert(0,str(root/'.firmware-tools/esptool-api-4.6'))
    import esptool
    from esptool import cmds,loader
    import serial
    from serial.tools.list_ports import comports
    if not Path(littlefs.__file__).resolve().is_relative_to((root/'.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected filesystem dependency')
    if not Path(esptool.__file__).resolve().is_relative_to((root/'.firmware-tools/esptool-api-4.6').resolve()):
        raise ValueError('Unexpected deployment dependency')
    ports=[p for p in comports() if p.device=='COM7' and p.vid==0x10c4 and p.pid==0xea60
           and p.serial_number=='52E4E1E8337FEF119E92181CEDD322A4']
    if len(ports)!=1: raise ValueError('Expected USB adapter not identified')
    from rocell.providers.windows.startup_provisioning_device import StartupProvisioningDevice
    device=StartupProvisioningDevice(esptool=esptool,cmds=cmds,loader=loader,serial=serial)
    result=_run_provisioning('negative-pair',source=source,source_sha256=CANDIDATE,
        candidate=candidate,candidate_sha256=IMAGE,policy=settings,key=None,
        previous_policy=dict(settings=previous,hold=hold),littlefs=littlefs,
        validate_policy=pv,validate_existing_policy=hv,private_root=private,
        export_root=root/'runs/wizard-exports',device=device,save_private_image=save_image,
        startup_authorized=True)
    print(json.dumps(result))


if __name__=='__main__': main()
