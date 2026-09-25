"""Explicitly authorized offline private staging only; never install or restart."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from provision_startup_r6 import check_private_acl
from rocell.application.observed_pose_candidate import replay_candidate
from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_installation_evidence import review_pair_installation
from rocell.application.held_pair_settings import encode_pair_settings
from rocell.application.native_provisioning_validator import NativeProvisioningValidator
from rocell.application.diagnostic_provisioning_image import replace_observed_pose_image
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter
from rocell.application.product_ghost_export_review import _read
from rocell.providers.windows.diagnostic_image_store import load_image, save_image

SOURCE_SHA = 'd1c041bcb4e90082685babc16698bcef3c639d87464932d6534d8056b71ce3aa'
DESTINATION = 'observed-pose-plus10-candidate.dpapi'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorized-offline-private-staging', action='store_true', required=True)
    parser.add_argument('--candidate-export', required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    replay = replay_candidate(root, args.candidate_export)
    public = replay['report']
    installation = review_pair_installation(root, revision=21)
    private = root/'private-backups/controller-20260918-session1'
    check_private_acl(private)
    if (private/DESTINATION).exists():
        raise ValueError('Candidate exists; never overwrite or silently restage')
    sketch = root/'.firmware-tools/configured-diagnostic-candidate-r21/RoArm-M3_example'
    pins = {'controller_hold_config.h': 'fa6aab90805c54f719be1cdfc8553584afe2a886d51065d772bea8ee3f1917dd',
            'controller_pair_config.h': '5f20891b2ae10090af19ce785273313a6f297c98d976eDEce741537284f874aa'.lower()}
    for name, expected in pins.items():
        if digest((sketch/name).read_bytes()) != expected:
            raise ValueError('Reviewed r21 parser changed')
    build = Path(tempfile.mkdtemp(prefix='observed-pose-validators-', dir=root/'.firmware-tools'))
    def validator(name, source):
        exe = build/(name+'.exe')
        subprocess.run(['clang++', '-std=c++17', '-I'+str(sketch),
            '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
            str(root/source), '-o', str(exe)], check=True, capture_output=True, timeout=60)
        return NativeProvisioningValidator(exe, digest(exe.read_bytes()))
    hold_validator = validator('hold', 'firmware/diagnostics/validate_hold_provisioning.cpp')
    pair_validator = validator('pair', 'firmware/validators/validate_pair_provisioning.cpp')
    sys.path.insert(0, str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root/'.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected filesystem implementation')
    old_hold = canonical(json.loads((root/'docs/hold-r7-supported-pose-draft.json').read_bytes()))
    old_pair = encode_pair_settings(forward_command_id='r10-elbow-forward',
        return_command_id='r10-elbow-return', offset_counts=-6)
    source = load_image(private/'pair-negative6-candidate.dpapi')
    candidate, review = replace_observed_pose_image(source, SOURCE_SHA, old_hold, old_pair,
        canonical(public['hold_settings']), canonical(public['pair_settings']),
        littlefs=littlefs, validate_hold=hold_validator, validate_pair=pair_validator)
    stored = save_image(private, DESTINATION, candidate)
    report = dict(schema='rocell.observed_pose_private_stage.v1', review=review, storage=stored,
        public_candidate_export=args.candidate_export,
        public_candidate_sha256=replay['candidate_report_sha256'], installation=installation,
        hardware_access=False, installation_authorized=False, startup_authorized=False,
        motion_authorized=False)
    exports = root/'runs/wizard-exports'; exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'offline-observed-pose-staging'}, [], attachments={
        'observed-pose-staging.json': canonical(report)})
    retained, _ = _read(exports, Path(saved['path']).name, 'attachment-observed-pose-staging.json')
    if canonical(retained) != canonical(report):
        raise ValueError('Staging export changed; retain candidate and stop')
    print(json.dumps(dict(export_path=saved['path'], **report)))


if __name__ == '__main__':
    main()
