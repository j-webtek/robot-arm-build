"""Add only r10 pair settings, verify preservation, then perform one startup.

Default preflight never opens hardware. Live execution requires the explicit flag;
the durable provisioning journal prevents a second attempt or automatic recovery.
Secret-bearing filesystem images remain in memory or current-user DPAPI storage.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from deploy_reviewed_diagnostic_app import supported_pose_filesystem, SUPPORTED_FS_HASH
from provision_startup_r6 import check_private_acl
from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_installation_evidence import review_pair_installation
from rocell.application.held_pair_settings import encode_pair_settings
from rocell.application.native_provisioning_validator import NativeProvisioningValidator
from rocell.application.diagnostic_provisioning_image import stage_pair_settings_image
from rocell.application.pair_settings_provisioning import run_pair_settings_provisioning
from rocell.providers.windows.diagnostic_image_store import save_image


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight-only', action='store_true')
    modes.add_argument('--authorized-filesystem-and-startup', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    private = root/'private-backups/controller-20260918-session1'
    check_private_acl(private)
    if any((private/('pair-r10-settings'+suffix)).exists() for suffix in
           ('-provisioning-events.jsonl', '-candidate.dpapi', '-prewrite-source.dpapi')):
        raise ValueError('Provisioning already reserved; no automatic resume')
    review_pair_installation(root)
    source = supported_pose_filesystem(root, private)
    hold = canonical(json.loads((root/'docs/hold-r7-supported-pose-draft.json').read_bytes()))
    if digest(hold) != '2ab588877107ebbc067607c29003fb317867123780e40c8e9d41011907d312d1':
        raise ValueError('Retained hold policy changed')
    settings = encode_pair_settings(forward_command_id='r10-elbow-forward',
        return_command_id='r10-elbow-return', offset_counts=6, tolerance_counts=2)
    # Compile the deployed candidate's parsers, not mutable development headers.
    sketch = root/'.firmware-tools/configured-diagnostic-candidate-r10/RoArm-M3_example'
    build = Path(tempfile.mkdtemp(prefix='pair-r10-provision-validators-', dir=root/'.firmware-tools'))
    def validator(name, adapter):
        exe = build/(name+'.exe')
        subprocess.run(['clang++', '-std=c++17', '-I'+str(sketch),
            '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
            str(root/adapter), '-o', str(exe)], check=True, capture_output=True, timeout=60)
        return NativeProvisioningValidator(exe, digest(exe.read_bytes()))
    pair_validator = validator('pair', 'firmware/validators/validate_pair_provisioning.cpp')
    hold_validator = validator('hold', 'firmware/diagnostics/validate_hold_provisioning.cpp')
    sys.path.insert(0, str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root/'.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected LittleFS implementation')
    candidate, review = stage_pair_settings_image(source, SUPPORTED_FS_HASH, settings, hold,
        littlefs=littlefs, validate_settings=pair_validator, validate_hold_policy=hold_validator)
    print(json.dumps(dict(status='PRESERVING_CANDIDATE_VERIFIED', **review)), flush=True)
    if args.preflight_only:
        return
    sys.path.insert(0, str(root/'.firmware-tools/esptool-api-4.6'))
    import esptool
    from esptool import cmds, loader
    import serial
    if not Path(esptool.__file__).resolve().is_relative_to((root/'.firmware-tools/esptool-api-4.6').resolve()):
        raise ValueError('Unexpected esptool implementation')
    from rocell.providers.windows.startup_provisioning_device import StartupProvisioningDevice
    device = StartupProvisioningDevice(esptool=esptool, cmds=cmds, loader=loader, serial=serial)
    result = run_pair_settings_provisioning(source=source, source_sha256=SUPPORTED_FS_HASH,
        candidate=candidate, candidate_sha256=digest(candidate), settings=settings,
        expected_hold_policy=hold, littlefs=littlefs, validate_settings=pair_validator,
        validate_hold_policy=hold_validator, private_root=private, export_root=root/'runs/wizard-exports',
        device=device, save_private_image=save_image, startup_authorized=True)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
