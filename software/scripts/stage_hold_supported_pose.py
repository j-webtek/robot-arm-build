"""Approved offline policy replacement only; no controller or network access."""
import argparse
import json
from pathlib import Path
import sys

from provision_hold_r7 import CANDIDATE, POLICY, VALIDATOR, digest
from deploy_reviewed_diagnostic_app import R7_HASH
from provision_startup_r6 import check_private_acl
from run_hold_r7 import INSTALL, PROVISION, require_fields
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.native_provisioning_validator import NativeProvisioningValidator
from rocell.application.diagnostic_provisioning_image import replace_hold_policy_image
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from rocell.providers.windows.diagnostic_image_store import load_image, save_image

NEW_POLICY = '2ab588877107ebbc067607c29003fb317867123780e40c8e9d41011907d312d1'
ATTEMPT = 'hold-r7-supported-pose-staging.json'
STAGED = 'hold-r7-supported-pose-candidate.dpapi'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorized-offline-private-staging', action='store_true', required=True)
    parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    private = root/'private-backups/controller-20260918-session1'
    exports = root/'runs/wizard-exports'
    check_private_acl(private)
    if any((private/name).exists() for name in (ATTEMPT, STAGED)):
        raise ValueError('Replacement staging already reserved; no automatic retry')
    installed, _ = _read(exports, INSTALL, 'attachment-installation-health.json')
    require_fields(installed, dict(app_sha256=R7_HASH, flash_readback_verified=True,
                                   protected_regions_unchanged=True))
    provision, provision_digest = _read(exports, PROVISION, 'attachment-provisioning-run.json')
    require_fields(provision, dict(candidate_sha256=CANDIDATE, status='FLASH_READBACK_VERIFIED',
                                   protected_regions_unchanged=True, recovery_preserved=True))
    source = load_image(private/'hold-r7-candidate.dpapi')
    if len(source) != 0x160000 or digest(source) != CANDIDATE:
        raise ValueError('Retained provisioned image mismatch')
    prior = canonical(json.loads((root/'docs/hold-r7-policy-draft.json').read_bytes()))
    policy = canonical(json.loads((root/'docs/hold-r7-supported-pose-draft.json').read_bytes()))
    if digest(prior) != POLICY or digest(policy) != NEW_POLICY:
        raise ValueError('Approved policy identity mismatch')
    validator = NativeProvisioningValidator(root/'.firmware-tools/hold-r7-validator-imc7cqjb/validate.exe', VALIDATOR)
    if not validator(prior) or not validator(policy):
        raise ValueError('Installed parser rejected configuration')
    sys.path.insert(0, str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root/'.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected LittleFS import location')
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    publish_reservation_bytes(private, ATTEMPT, canonical(dict(
        schema='rocell.hold_replacement_staging_claim.v1', source_sha256=CANDIDATE,
        previous_policy_sha256=POLICY, policy_sha256=NEW_POLICY,
        state='CONSUMED_BEFORE_PRIVATE_STAGING', hardware_access=False)), maximum_bytes=2048)
    candidate, review = replace_hold_policy_image(source, CANDIDATE, prior, policy,
                                                  littlefs=littlefs, validate_policy=validator)
    saved = save_image(private, STAGED, candidate)
    if saved['image_sha256'] != review['candidate_sha256']:
        raise ValueError('Private candidate readback mismatch')
    review.update(previous_policy_sha256=POLICY, validator_sha256=VALIDATOR,
        installed_application_sha256=R7_HASH, source_provisioning_export_id=PROVISION,
        source_provisioning_sha256=provision_digest, existing_key_preserved=True,
        key_generated=False, provisioning_authorized=False, startup_authorized=False,
        motion_authorized=False, private_filename=STAGED)
    exported = exporter.export({'mode':'offline-hold-policy-replacement'}, [], attachments={
        'hold-replacement-review.json':canonical(review), 'hold-policy.json':policy})
    if not verify_export(Path(exported['path']))['valid']:
        raise ValueError('Replacement export verification failed; do not retry')
    print(json.dumps(dict(status='PRIVATELY_STAGED_NOT_PROVISIONED',
        candidate_sha256=review['candidate_sha256'], policy_sha256=NEW_POLICY,
        existing_entries_preserved=review['existing_entries_preserved'],
        existing_key_preserved=True, export_id=Path(exported['path']).name,
        export_verified=True, hardware_access=False)))


if __name__ == '__main__':
    main()
