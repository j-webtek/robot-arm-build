"""Approved offline r7 staging only. No serial/network/flash/reset operations."""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile

from deploy_reviewed_diagnostic_app import provisioned_filesystem, R7_HASH
from provision_startup_r6 import check_private_acl
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.native_provisioning_validator import NativeProvisioningValidator
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.diagnostic_provisioning_image import stage_hold_image
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from rocell.providers.windows.diagnostic_image_store import save_image

POLICY_HASH = 'f9663167513aadeb5666713c808128ddd834be5843e6570d22359338f93dc9e1'
COMPILE_EXPORT = 'wizard-20260918T174440380311Z-592ae9d2f2484a13b103cc8e8b954407'
INSTALL_EXPORT = 'wizard-20260918T191322958288Z-a8f1786858e441619438af6e01245a46'
STAGED = 'hold-r7-reviewed-candidate.dpapi'
ATTEMPT = 'hold-r7-private-staging.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorized-stage-private', action='store_true', required=True)
    parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    private = root/'private-backups/controller-20260918-session1'
    exports = root/'runs/wizard-exports'
    check_private_acl(private)
    for name in (STAGED, ATTEMPT, 'hold-r7-candidate.dpapi', 'hold-r7-provisioning-events.jsonl'):
        if (private/name).exists():
            raise ValueError('Hold staging/provisioning already reserved; no regeneration')
    installed, _ = _read(exports, INSTALL_EXPORT, 'attachment-installation-health.json')
    if (installed.get('app_sha256') != R7_HASH or installed.get('flash_readback_verified') is not True
            or installed.get('protected_regions_unchanged') is not True):
        raise ValueError('Installed r7 evidence differs')
    compile_review, _ = _read(exports, COMPILE_EXPORT, 'attachment-compile-review.json')
    prefix = '.firmware-tools/configured-diagnostic-candidate-r7/RoArm-M3_example/'
    sources = {name: value for name, value in compile_review['source_hashes'].items()
               if name.replace('\\', '/').startswith(prefix)}
    if not sources or compile_review['artifact_hashes']['RoArm-M3_example.ino.bin'] != R7_HASH:
        raise ValueError('Missing reviewed candidate sources')
    for name, expected in sources.items():
        if digest((root/name).read_bytes()) != expected:
            raise ValueError('Reviewed candidate source changed')
    policy = canonical(json.loads((root/'docs/hold-r7-policy-draft.json').read_bytes()))
    if len(policy) != 456 or digest(policy) != POLICY_HASH:
        raise ValueError('Reviewed hold policy changed')
    source = provisioned_filesystem(root, private)
    compiler = shutil.which('clang++')
    if not compiler:
        raise ValueError('Native parser compiler unavailable')
    build = Path(tempfile.mkdtemp(prefix='hold-r7-validator-', dir=root/'.firmware-tools'))
    executable = build/'validate.exe'
    validator_source = root/'firmware/diagnostics/validate_hold_provisioning.cpp'
    result = subprocess.run([compiler, '-std=c++17', '-I'+str(root/prefix),
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(validator_source), '-o', str(executable)], capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError('Offline validator compilation failed')
    validator_hash = digest(executable.read_bytes())
    validator = NativeProvisioningValidator(executable, validator_hash)
    if not validator(policy):
        raise ValueError('Installed parser rejected hold policy')
    sys.path.insert(0, str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    reservation = dict(schema='rocell.hold_private_staging.v1', policy_sha256=POLICY_HASH,
        source_sha256=digest(source), validator_sha256=validator_hash,
        state='CONSUMED_BEFORE_KEY_GENERATION', hardware_access=False)
    publish_reservation_bytes(private, ATTEMPT, canonical(reservation), maximum_bytes=2048)
    key = secrets.token_bytes(32)
    candidate, review = stage_hold_image(source, digest(source), policy, key,
        littlefs=littlefs, validate_policy=validator)
    saved = save_image(private, STAGED, candidate)
    if saved['image_sha256'] != review['candidate_sha256']:
        raise ValueError('Private staging readback differs')
    review.update(validator_sha256=validator_hash,
        validator_source_sha256=digest(validator_source.read_bytes()),
        validator_path=str(executable.relative_to(root)),
        installed_application_sha256=R7_HASH, provisioning_authorized=False,
        startup_authorized=False, motion_authorized=False)
    exported = exporter.export({'mode':'offline-hold-staging'}, [], attachments={
        'hold-staging-review.json':canonical(review), 'hold-policy.json':policy})
    if not verify_export(Path(exported['path']))['valid']:
        raise ValueError('Staging export verification failed; do not regenerate')
    print(json.dumps(dict(status='PRIVATELY_STAGED_NOT_PROVISIONED',
        candidate_sha256=review['candidate_sha256'], policy_sha256=POLICY_HASH,
        validator_sha256=validator_hash, validator_path=review['validator_path'],
        existing_entries_preserved=review['existing_entries_preserved'],
        export_id=Path(exported['path']).name, export_verified=True, hardware_access=False)))


if __name__ == '__main__':
    main()
