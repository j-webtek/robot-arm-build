"""Reviewed r7 hold entry point. Default work requires explicit mode selection."""
import argparse
import json
from pathlib import Path
import sys

from provision_hold_r7 import CANDIDATE, POLICY, VALIDATOR, digest, read_hold_key
from deploy_reviewed_diagnostic_app import R7_HASH, R6_FS_HASH
from provision_startup_r6 import check_private_acl
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.native_provisioning_validator import NativeProvisioningValidator
from rocell.providers.windows.diagnostic_image_store import load_image

INSTALL = 'wizard-20260918T191322958288Z-a8f1786858e441619438af6e01245a46'
PROVISION = 'wizard-20260918T194438073911Z-c5027a7bed73466d8d29ff51e49b553c'
HEALTH = 'wizard-20260918T194501474566Z-ea93ab25a2a940bd8412946a9c2d432c'
BOOT = '749e200e399ad53b38f2fa35f4929ed8'
ADDRESS = '192.168.0.225'
SUPPORTED_BOOT = '35d977559eff75fd89c2f156abb5bc0c'


def selected_profile(supported_pose=False):
    if supported_pose:
        return dict(boot=SUPPORTED_BOOT,
            provision='wizard-20260918T213520824547Z-50d496655d5d4796b58d39a0a8395a1a',
            health='wizard-20260918T213547363926Z-f5e6fd8994844a3f8e4adf459e60fa35',
            candidate='4524696545583513b283348789b2e1f92ed37e178efcb10edf32dcbd639ec4bf',
            source=CANDIDATE,
            policy='2ab588877107ebbc067607c29003fb317867123780e40c8e9d41011907d312d1',
            draft='hold-r7-supported-pose-draft.json', prefix='hold-r7-supported-replacement')
    return dict(boot=BOOT, provision=PROVISION, health=HEALTH, candidate=CANDIDATE,
                source=R6_FS_HASH, policy=POLICY, draft='hold-r7-policy-draft.json', prefix='hold-r7')


def require_fields(report, expected):
    if any(canonical(report.get(k)) != canonical(v) for k, v in expected.items()):
        raise ValueError('Retained r7 evidence mismatch')


def preflight(root, *, supported_pose=False):
    """Local evidence only; does not extract a key, reserve an attempt or use I/O."""
    exports = root/'runs/wizard-exports'
    profile = selected_profile(supported_pose)
    private = root/'private-backups/controller-20260918-session1'
    check_private_acl(private)
    installed, _ = _read(exports, INSTALL, 'attachment-installation-health.json')
    require_fields(installed, dict(app_sha256=R7_HASH, flash_readback_verified=True,
                                   protected_regions_unchanged=True))
    provision, provision_digest = _read(exports, profile['provision'], 'attachment-provisioning-run.json')
    require_fields(provision, dict(schema='rocell.hold_provisioning_result.v1',
        candidate_sha256=profile['candidate'], source_sha256=profile['source'], status='FLASH_READBACK_VERIFIED',
        protected_regions_unchanged=True, recovery_preserved=True, startup_attempted=True,
        retry_allowed=False, motion_authorized=False))
    verified, _ = _read(exports, provision['verified_write_export_id'], 'attachment-provisioning-result.json')
    require_fields(verified, dict(candidate_sha256=profile['candidate'], source_sha256=profile['source'],
        status='FLASH_READBACK_VERIFIED', protected_regions_unchanged=True,
        recovery_preserved=True, startup_attempted=False))
    health, _ = _read(exports, profile['health'], 'attachment-hold-startup-health.json')
    require_fields(health, dict(schema='rocell.hold_provisioning_startup_health.v1',
        candidate_sha256=profile['candidate'], provisioning_export_id=profile['provision'],
        provisioning_sha256=provision_digest, status_response_verified=True,
        challenge_requested=False, servo_commands_sent=False))
    require_fields(health['status'], dict(instance_id=profile['boot'], state='IDLE', reason='NOT_CONFIGURED',
                                        records=0, storage_fault=False))
    if (exports/('first-hold-trial-' + profile['boot'] + '.json')).exists():
        raise ValueError('Hold boot trial already consumed')
    policy = canonical(json.loads((root/'docs'/profile['draft']).read_bytes()))
    if digest(policy) != profile['policy']:
        raise ValueError('Reviewed policy changed')
    validator = NativeProvisioningValidator(root/'.firmware-tools/hold-r7-validator-imc7cqjb/validate.exe', VALIDATOR)
    if not validator(policy):
        raise ValueError('Installed parser rejected policy')
    candidate = load_image(private/(profile['prefix']+'-candidate.dpapi'))
    source = load_image(private/(profile['prefix']+'-prewrite-source.dpapi'))
    if (len(candidate) != 0x160000 or digest(candidate) != profile['candidate'] or
            len(source) != 0x160000 or digest(source) != profile['source']):
        raise ValueError('Private candidate or recovery mismatch')
    return json.loads(policy), candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight-only', action='store_true')
    modes.add_argument('--authorized-powered-hold', action='store_true')
    parser.add_argument('--expected-boot')
    parser.add_argument('--supported-pose', action='store_true')
    args = parser.parse_args()
    profile = selected_profile(args.supported_pose)
    if (args.authorized_powered_hold and args.expected_boot != profile['boot'] or
            args.preflight_only and args.expected_boot is not None):
        parser.error('Live hold requires the separately approved exact boot')
    root = Path(__file__).resolve().parents[1]
    configuration, candidate = preflight(root, supported_pose=args.supported_pose)
    if args.preflight_only:
        print(json.dumps(dict(status='LOCAL_HOLD_PREFLIGHT_VERIFIED', hardware_access=False,
            key_extracted=False, attempt_reserved=False, motion_authorized=False,
            candidate_sha256=profile['candidate'], expected_boot=profile['boot'])))
        return
    # Extract credentials before the short-lived challenge; never print them.
    sys.path.insert(0, str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root/'.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected LittleFS import location')
    key = read_hold_key(candidate, littlefs)
    from rocell.application.hold_first_trial_run import run_first_hold
    result = run_first_hold(root/'runs/wizard-exports', configuration=configuration,
        expected_boot=profile['boot'], key=key, address=ADDRESS, authorized_powered_hold=True)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
