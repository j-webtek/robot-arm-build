"""Exact staged r7 filesystem provisioning; local preflight is hardware-free."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from deploy_reviewed_diagnostic_app import provisioned_filesystem, R7_HASH, R6_FS_HASH
from provision_startup_r6 import check_private_acl
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.native_provisioning_validator import NativeProvisioningValidator
from rocell.application.hold_provisioning_run import run_hold_provisioning
from rocell.providers.windows.diagnostic_image_store import load_image, save_image

CANDIDATE = '0bdfc4d3f300e811e03332a6a86df20e47c3d42c95282e9ddd2f00c211044e9b'
POLICY = 'f9663167513aadeb5666713c808128ddd834be5843e6570d22359338f93dc9e1'
VALIDATOR = '5bb34a17fa28066e2142f410d265c1739e60afa522e947a8a306692d771d1628'
STAGING_EXPORT = 'wizard-20260918T192754597401Z-66ce7c2b5fa041509937d7c61b69134f'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def preflight(root):
    private = root/'private-backups/controller-20260918-session1'
    check_private_acl(private)
    for name in ('hold-r7-provisioning-events.jsonl', 'hold-r7-candidate.dpapi', 'hold-r7-prewrite-source.dpapi'):
        if (private/name).exists():
            raise ValueError('Hold provisioning already reserved; no automatic resume')
    review, _ = _read(root/'runs/wizard-exports', STAGING_EXPORT, 'attachment-hold-staging-review.json')
    required = dict(schema='rocell.offline_hold_provisioning_image.v1',
        candidate_sha256=CANDIDATE, policy_sha256=POLICY, source_sha256=R6_FS_HASH,
        installed_application_sha256=R7_HASH, validator_sha256=VALIDATOR,
        remount_verified=True, device_modified=False, physical_authority='NONE',
        provisioning_authorized=False, startup_authorized=False, motion_authorized=False)
    if any(canonical(review.get(k)) != canonical(v) for k, v in required.items()):
        raise ValueError('Staged review differs from exact candidate')
    policy = canonical(json.loads((root/'docs/hold-r7-policy-draft.json').read_bytes()))
    if digest(policy) != POLICY:
        raise ValueError('Reviewed hold policy changed')
    candidate = load_image(private/'hold-r7-reviewed-candidate.dpapi')
    if len(candidate) != 0x160000 or digest(candidate) != CANDIDATE:
        raise ValueError('Private candidate mismatch')
    source = provisioned_filesystem(root, private)
    validator = NativeProvisioningValidator(root/'.firmware-tools/hold-r7-validator-imc7cqjb/validate.exe', VALIDATOR)
    if not validator(policy):
        raise ValueError('Retained r7 parser rejected policy')
    return private, source, candidate, policy, validator


def read_hold_key(candidate, littlefs):
    if littlefs.__version__ != '0.19.0':
        raise ValueError('Unreviewed LittleFS implementation')
    fs = littlefs.LittleFS(context=littlefs.UserContext(buffer=bytearray(candidate)),
        mount=False, block_size=4096, block_count=352, read_size=256, prog_size=256)
    fs.mount()  # Never format or repair.
    try:
        with fs.open('/rocell-hold.key', 'rb') as stream:
            key = stream.read(33)
        if len(key) != 32:
            raise ValueError('Staged hold key length mismatch')
        return key
    finally:
        fs.unmount()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight-only', action='store_true')
    modes.add_argument('--authorized-provision-and-startup', action='store_true')
    parser.add_argument('--candidate-sha256')
    args = parser.parse_args()
    if (args.authorized_provision_and_startup and args.candidate_sha256 != CANDIDATE or
            args.preflight_only and args.candidate_sha256 is not None):
        parser.error('Provisioning requires exactly the separately approved candidate digest')
    root = Path(__file__).resolve().parents[1]
    private, source, candidate, policy, validator = preflight(root)
    if args.preflight_only:
        print(json.dumps(dict(status='LOCAL_PREFLIGHT_VERIFIED', candidate_sha256=CANDIDATE,
            source_sha256=digest(source), policy_sha256=POLICY, app_sha256=R7_HASH,
            hardware_access=False, journal_reserved=False, key_created=False,
            provisioning_authorized=False)))
        return
    sys.path.insert(0, str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    key = read_hold_key(candidate, littlefs)
    # Device imports/opening are reachable only after explicit execution choice.
    sys.path.insert(0, str(root/'.firmware-tools/esptool-api-4.6'))
    import esptool
    from esptool import cmds, loader
    import serial
    if not Path(esptool.__file__).resolve().is_relative_to((root/'.firmware-tools/esptool-api-4.6').resolve()):
        raise ValueError('Unexpected esptool import location')
    from rocell.providers.windows.startup_provisioning_device import StartupProvisioningDevice
    device = StartupProvisioningDevice(esptool=esptool, cmds=cmds, loader=loader, serial=serial)
    result = run_hold_provisioning(source=source, source_sha256=digest(source),
        candidate=candidate, candidate_sha256=CANDIDATE, policy=policy, key=key,
        littlefs=littlefs, validate_policy=validator, private_root=private,
        export_root=root/'runs/wizard-exports', device=device, save_private_image=save_image,
        startup_authorized=True)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
