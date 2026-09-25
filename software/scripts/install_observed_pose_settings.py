"""Receipt-bound r21 filesystem-only install and one startup; no movement."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from stage_observed_pose_settings import digest, SOURCE_SHA, DESTINATION
from provision_startup_r6 import check_private_acl
from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_installation_evidence import review_pair_installation
from rocell.application.held_pair_settings import encode_pair_settings
from rocell.application.observed_pose_candidate import replay_candidate
from rocell.application.observed_pose_provisioning import ObservedPoseJournal
from rocell.application.product_ghost_export_review import _read
from rocell.application.native_provisioning_validator import NativeProvisioningValidator
from rocell.application.diagnostic_provisioning_image import replace_observed_pose_image
from rocell.application.startup_provisioning_run import _run_provisioning
from rocell.providers.windows.diagnostic_image_store import load_image, save_image


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-export', required=True)
    parser.add_argument('--candidate-sha256', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only', action='store_true')
    mode.add_argument('--authorized-filesystem-install-and-startup', action='store_true')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    installation = review_pair_installation(root, revision=21)
    report, _ = _read(root/'runs/wizard-exports', args.stage_export, 'attachment-observed-pose-staging.json')
    public = replay_candidate(root, report['public_candidate_export'])
    if (report['schema'] != 'rocell.observed_pose_private_stage.v1' or
            canonical(report['installation']) != canonical(installation) or
            report['public_candidate_sha256'] != public['candidate_report_sha256'] or
            report['review']['candidate_sha256'] != args.candidate_sha256 or
            report['review']['source_sha256'] != SOURCE_SHA):
        raise ValueError('Reviewed staging/application/candidate linkage required')
    private = root/'private-backups/controller-20260918-session1'
    check_private_acl(private)
    if (private/ObservedPoseJournal.NAME).exists():
        raise ValueError('Installation consumed; no automatic retry')
    source = load_image(private/'pair-negative6-candidate.dpapi')
    candidate = load_image(private/DESTINATION)
    if digest(source) != SOURCE_SHA or digest(candidate) != args.candidate_sha256:
        raise ValueError('Private image identity mismatch')
    sketch = root/'.firmware-tools/configured-diagnostic-candidate-r21/RoArm-M3_example'
    pins = {'controller_hold_config.h':'fa6aab90805c54f719be1cdfc8553584afe2a886d51065d772bea8ee3f1917dd',
            'controller_pair_config.h':'5f20891b2ae10090af19ce785273313a6f297c98d976edece741537284f874aa'}
    if any(digest((sketch/name).read_bytes())!=value for name,value in pins.items()):
        raise ValueError('Reviewed native parser changed')
    build = Path(tempfile.mkdtemp(prefix='observed-install-validators-', dir=root/'.firmware-tools'))
    def validator(name, adapter):
        exe = build/(name+'.exe')
        subprocess.run(['clang++','-std=c++17','-I'+str(sketch),
            '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),str(root/adapter),
            '-o',str(exe)], check=True, capture_output=True, timeout=60)
        return NativeProvisioningValidator(exe, digest(exe.read_bytes()))
    hv = validator('hold', 'firmware/diagnostics/validate_hold_provisioning.cpp')
    pv = validator('pair', 'firmware/validators/validate_pair_provisioning.cpp')
    old_hold = canonical(json.loads((root/'docs/hold-r7-supported-pose-draft.json').read_bytes()))
    old_pair = encode_pair_settings(forward_command_id='r10-elbow-forward',
        return_command_id='r10-elbow-return',offset_counts=-6)
    hold = canonical(public['report']['hold_settings']); pair = canonical(public['report']['pair_settings'])
    sys.path.insert(0, str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root/'.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected filesystem dependency')
    rebuilt, review = replace_observed_pose_image(source, SOURCE_SHA, old_hold, old_pair, hold, pair,
        littlefs=littlefs, validate_hold=hv, validate_pair=pv)
    if rebuilt != candidate or canonical(review) != canonical(report['review']):
        raise ValueError('Staged candidate does not reproduce exactly')
    if args.preflight_only:
        print(json.dumps(dict(status='LOCAL_OBSERVED_POSE_PREFLIGHT_VERIFIED',
            candidate_sha256=digest(candidate),hardware_access=False,attempt_reserved=False)))
        return
    # Hardware libraries are intentionally imported only after explicit execution
    # mode and all local checks. The adapter itself disables write retries.
    sys.path.insert(0, str(root/'.firmware-tools/esptool-api-4.6'))
    import esptool
    from esptool import cmds, loader
    import serial
    from serial.tools.list_ports import comports
    if not Path(esptool.__file__).resolve().is_relative_to((root/'.firmware-tools/esptool-api-4.6').resolve()):
        raise ValueError('Unexpected deployment dependency')
    matches = [p for p in comports() if p.device=='COM7' and p.vid==0x10c4 and p.pid==0xea60
        and p.serial_number=='52E4E1E8337FEF119E92181CEDD322A4']
    if len(matches)!=1: raise ValueError('Expected USB adapter not identified')
    from rocell.providers.windows.startup_provisioning_device import StartupProvisioningDevice
    device = StartupProvisioningDevice(esptool=esptool,cmds=cmds,loader=loader,serial=serial)
    result = _run_provisioning('observed-pose', source=source,source_sha256=SOURCE_SHA,
        candidate=candidate,candidate_sha256=args.candidate_sha256,
        policy=dict(hold=hold,pair=pair),key=None,previous_policy=dict(hold=old_hold,pair=old_pair),
        littlefs=littlefs,validate_policy=pv,validate_existing_policy=hv,private_root=private,
        export_root=root/'runs/wizard-exports',device=device,save_private_image=save_image,
        startup_authorized=True)
    print(json.dumps(result))


if __name__ == '__main__': main()
