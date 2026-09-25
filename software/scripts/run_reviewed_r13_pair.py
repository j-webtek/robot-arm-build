"""Finite r13 elbow pair from retained installation/hold evidence; no reset.

The live flag represents the operator's bounded-test authorization, not software
proof of physical clearance. Native prewrite scans enforce current joint state.
No firmware, filesystem or servo configuration is changed by this launcher.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from provision_startup_r6 import check_private_acl
from provision_hold_r7 import read_hold_key
from rocell.application.first_motion_contract import canonical
from rocell.application.r10_provisioned_evidence import review_provisioned_r10, CANDIDATE
from rocell.application.held_pair_preparation import replay_held_pair_preparation
from rocell.application.held_pair_trial import run_admitted_pair
from rocell.application.hold_transport_export import capture_hold_transport
from rocell.application.hold_transport_snapshot import HoldHTTPReader
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from rocell.providers.windows.diagnostic_image_store import load_image

PREPARATION = 'wizard-20260919T035918294015Z-ca28470911a0407289605b59a400cbe6'
PREPARATION_SHA = 'b6a24a109938953e39a1161a75bf43ba7d71139f1b56834ef48e08706f30ec20'


def preflight(root):
    evidence = review_provisioned_r10(root, revision=13)
    source = replay_held_pair_preparation(root/'runs/wizard-exports', PREPARATION)
    prep = source['preparation']; plan = prep['pair_plan']
    if (source['preparation_sha256'] != PREPARATION_SHA or
            plan['boot_id'] != evidence['expected_boot'] or
            plan['forward_command_id'] != 'r10-elbow-forward' or
            plan['return_command_id'] != 'r10-elbow-return' or
            plan['offset_counts'] != 6 or plan['tolerance_counts'] != 2 or
            prep['historical_anchor'] != 2901):
        raise ValueError('Exact reviewed pair preparation required')
    policy_document = dict(schema='rocell.controller_hold.v1',
        command_id='r7-supported-hold-20260918', start_port=8081,
        hold_policy=prep['policy'])
    if hashlib.sha256(canonical(policy_document)).hexdigest() != evidence['hold_policy_sha256']:
        raise ValueError('Pair policy differs from installed hold settings')
    claim = 'held-pair-trial-' + hashlib.sha256(plan['boot_id'].encode('ascii')).hexdigest() + '.json'
    if (root/'runs/wizard-exports'/claim).exists():
        raise ValueError('Pair attempt consumed; no retry or recovery')
    private = root/'private-backups/controller-20260918-session1'
    check_private_acl(private)
    image = load_image(private/'pair-r10-settings-candidate.dpapi')
    if len(image) != 0x160000 or hashlib.sha256(image).hexdigest() != CANDIDATE:
        raise ValueError('Retained private settings image differs')
    return evidence, image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight-only', action='store_true')
    modes.add_argument('--authorized-powered-pair', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    evidence, image = preflight(root)
    if args.preflight_only:
        print(json.dumps(dict(status='LOCAL_R13_PAIR_PREFLIGHT_VERIFIED',
            expected_boot=evidence['expected_boot'], preparation_id=PREPARATION,
            targets=[2907,2901], hardware_access=False, key_extracted=False)))
        return
    exports = root/'runs/wizard-exports'
    current = capture_hold_transport(exports, HoldHTTPReader(evidence['address']),
        expected_boot=evidence['expected_boot'])
    status = current['summary'].get('status', {})
    if (current['summary']['category'] != 'TRANSPORT_CAPTURED' or
            status.get('state') != 'CAPTURED' or status.get('storage_fault') is not False):
        raise ValueError('Same-boot completed hold required; no pair command sent')
    # Save the actual basis for admission, not invented measurements or an
    # assertion that retained flash receipts prove current physical accuracy.
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    admission = exporter.export({'mode':'reviewed-r13-pair-admission'}, [], attachments={
        'pair-admission-basis.json':canonical(dict(installation_and_settings=evidence,
            current_hold_export=Path(current['export_path']).name,
            preparation_id=PREPARATION, preparation_sha256=PREPARATION_SHA,
            authorization_basis='USER_STANDING_BOUNDED_MOTION_TEST_AUTHORIZATION',
            clearance_basis='USER_STANDING_SECURED_CLEAR_POWERED_CONFIRMATION',
            physical_clearance_measured=False, retry_allowed=False))})
    if not verify_export(Path(admission['path']))['valid']:
        raise ValueError('Admission export failed')
    sys.path.insert(0, str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to(root/'.firmware-tools/littlefs-review'):
        raise ValueError('Unexpected LittleFS implementation')
    key = read_hold_key(image, littlefs)
    result = run_admitted_pair(exports, PREPARATION, address=evidence['address'], key=key, approved=True)
    print(json.dumps(dict(admission_export=admission['path'], **result)))


if __name__ == '__main__':
    main()
