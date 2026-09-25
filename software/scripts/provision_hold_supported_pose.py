"""Exact supported-pose filesystem replacement; never issues servo commands."""
import argparse
import json
from pathlib import Path
import sys

from stage_hold_supported_pose import NEW_POLICY, STAGED
from provision_hold_r7 import CANDIDATE as SOURCE, POLICY, VALIDATOR, digest
from provision_startup_r6 import check_private_acl
from run_hold_r7 import require_fields
from deploy_reviewed_diagnostic_app import R7_HASH
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.native_provisioning_validator import NativeProvisioningValidator
from rocell.application.hold_provisioning_run import run_hold_policy_replacement
from rocell.providers.windows.diagnostic_image_store import load_image, save_image

CANDIDATE = '4524696545583513b283348789b2e1f92ed37e178efcb10edf32dcbd639ec4bf'
REVIEW = 'wizard-20260918T210720842126Z-374c9d9e3cfb41128c743accf9220ffc'
PREFIX = 'hold-r7-supported-replacement'


def preflight(root):
    private = root/'private-backups/controller-20260918-session1'
    check_private_acl(private)
    if any((private/(PREFIX+suffix)).exists() for suffix in
           ('-provisioning-events.jsonl', '-candidate.dpapi', '-prewrite-source.dpapi')):
        raise ValueError('Replacement already reserved; no automatic resume')
    review, _ = _read(root/'runs/wizard-exports', REVIEW, 'attachment-hold-replacement-review.json')
    require_fields(review, dict(schema='rocell.offline_hold_policy_replacement.v1',
        source_sha256=SOURCE, candidate_sha256=CANDIDATE, policy_sha256=NEW_POLICY,
        previous_policy_sha256=POLICY, validator_sha256=VALIDATOR,
        installed_application_sha256=R7_HASH, existing_key_preserved=True,
        remount_verified=True, key_generated=False, device_modified=False,
        provisioning_authorized=False, startup_authorized=False, motion_authorized=False))
    source = load_image(private/'hold-r7-candidate.dpapi')
    candidate = load_image(private/STAGED)
    if any(len(data) != 0x160000 or digest(data) != expected for data, expected in
           ((source, SOURCE), (candidate, CANDIDATE))):
        raise ValueError('Private image identity mismatch')
    prior = canonical(json.loads((root/'docs/hold-r7-policy-draft.json').read_bytes()))
    policy = canonical(json.loads((root/'docs/hold-r7-supported-pose-draft.json').read_bytes()))
    if digest(prior) != POLICY or digest(policy) != NEW_POLICY:
        raise ValueError('Reviewed policies changed')
    validator = NativeProvisioningValidator(root/'.firmware-tools/hold-r7-validator-imc7cqjb/validate.exe', VALIDATOR)
    if not validator(prior) or not validator(policy):
        raise ValueError('Installed parser rejected configuration')
    return private, source, candidate, prior, policy, validator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight-only', action='store_true')
    modes.add_argument('--authorized-filesystem-and-startup', action='store_true')
    parser.add_argument('--candidate-sha256')
    args = parser.parse_args()
    if (args.authorized_filesystem_and_startup and args.candidate_sha256 != CANDIDATE or
            args.preflight_only and args.candidate_sha256 is not None):
        parser.error('Live mode requires the exact separately approved candidate')
    root = Path(__file__).resolve().parents[1]
    private, source, candidate, prior, policy, validator = preflight(root)
    if args.preflight_only:
        print(json.dumps(dict(status='LOCAL_REPLACEMENT_PREFLIGHT_VERIFIED',
            candidate_sha256=CANDIDATE, hardware_access=False, journal_reserved=False)))
        return
    sys.path.insert(0, str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root/'.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected LittleFS implementation')
    sys.path.insert(0, str(root/'.firmware-tools/esptool-api-4.6'))
    import esptool
    from esptool import cmds, loader
    import serial
    if not Path(esptool.__file__).resolve().is_relative_to((root/'.firmware-tools/esptool-api-4.6').resolve()):
        raise ValueError('Unexpected esptool implementation')
    from rocell.providers.windows.startup_provisioning_device import StartupProvisioningDevice
    device = StartupProvisioningDevice(esptool=esptool, cmds=cmds, loader=loader, serial=serial)
    result = run_hold_policy_replacement(source=source, source_sha256=SOURCE,
        candidate=candidate, candidate_sha256=CANDIDATE, previous_policy=prior, policy=policy,
        littlefs=littlefs, validate_policy=validator, private_root=private,
        export_root=root/'runs/wizard-exports', device=device, save_private_image=save_image,
        startup_authorized=True)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
