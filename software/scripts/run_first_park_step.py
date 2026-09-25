"""One authenticated r55 first rise using a prior-boot REFERENCE_A checkpoint.

No automatic return, retry, second step, torque change or physical park claim.
The controller independently captures and gates the fresh current pose before
its only possible write. Same-boot pose capture owns the diagnostic bus and
therefore cannot be followed by a park step on that boot.
"""

import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.park_step_host import ParkStepHost
from rocell.application.park_step_plan import plan_first_park_step
from rocell.application.physical_onboarding_durability import read_bounded_regular_file
from rocell.application.pose_observation_export import replay_pose_observation
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


REFERENCE = 'wizard-20260921T223040009414Z-19964cdec96940a3a6e08e9715fd7856'


def preflight(root, startup_export, pose_export):
    root = Path(root).resolve()
    binding = review_recovery_startup(root, startup_export, revision=55)
    exports = root/'runs/wizard-exports'
    boot = binding['expected_boot']
    claim = exports/f'r55-park-step-{boot}.json'
    if claim.exists():
        raise ValueError('Park-step attempt already claimed on boot')
    if (exports/f'pose-observation-{boot}.json').exists():
        raise ValueError('Current boot already reserved by pose capture; fresh startup required')
    if (exports/f'r55-auth-gate-used-{boot}.json').exists():
        raise ValueError('Authenticated gate sequence used by prior probe; fresh startup required')
    reference, reference_digest = _read(exports, REFERENCE,
                                        'attachment-standard-start-reference.json')
    raw, _ = _read(exports, pose_export, 'attachment-pose-raw.json')
    source_boot = raw['subject']['expected_boot']
    if source_boot == boot:
        raise ValueError('Same-boot pose capture owns the bus; use a fresh startup without pose capture')
    observation = replay_pose_observation(exports, pose_export)
    if observation['replay_verified'] is not True:
        raise ValueError('Pose export did not replay')
    plan = plan_first_park_step(reference, observation['assessment'],
                                observation_boot=source_boot, observation_export_id=pose_export)
    plan['reference_export_id'] = REFERENCE
    plan['reference_attachment_sha256'] = reference_digest
    plan['observation_bundle_sha256'] = observation['raw_bundle_sha256']
    claim_path = exports/f'pose-observation-{source_boot}.json'
    if not claim_path.exists():
        raise ValueError('One-use source-boot pose capture claim required')
    pose_claim = json.loads(read_bounded_regular_file(claim_path, maximum_bytes=2048))
    if canonical(pose_claim) != canonical(dict(
            expected_boot=source_boot, expected_id=raw['subject']['expected_id'],
            retry_allowed=False)):
        raise ValueError('Pose capture claim differs')
    if ((exports/f'r54-reanchor-{boot}.json').exists() or
            (exports/f'r53-capture-{boot}.json').exists() or
            any(exports.glob(f'r53-session-*-capture-{boot}.json'))):
        raise ValueError('Boot already claimed by another motion route')
    return binding, exports, claim, plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export', required=True)
    parser.add_argument('--pose-export', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only', action='store_true')
    mode.add_argument('--authorized-once', action='store_true')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    binding, exports, claim, plan = preflight(root, args.startup_export, args.pose_export)
    if args.preflight_only:
        print(json.dumps(dict(status='R55_FIRST_STEP_BINDING_VERIFIED',
                              boot=binding['expected_boot'], target_goals=plan['target_goals'],
                              hardware_access=False, movement_authorized=False)))
        return
    key = load_reviewed_key(root)
    WizardDiagnosticExporter(exports).prepare(create=True)
    # Reserve before the first network command. Uncertain delivery can never
    # be retried on this boot by invoking the CLI again.
    with claim.open('x', encoding='utf-8') as stream:
        json.dump(dict(boot=binding['expected_boot'], startup_export=args.startup_export,
                       pose_export=args.pose_export, reference_export=REFERENCE,
                       target_goals=plan['target_goals'], scope='one-first-park-step'), stream)
        stream.flush()
        os.fsync(stream.fileno())
    client = CharacterizationHTTP(binding['address'], key=key,
                                  boot=binding['expected_boot'])
    host = ParkStepHost(client, export_root=exports,
                        boot=binding['expected_boot'], plan=plan)
    result = host.run_once()
    print(json.dumps(dict(status='FIRST_STEP_RECORDED', export=result['export'],
                          assessment=result['assessment'], physical_rise_proven=False,
                          continuation_authorized=False)))


if __name__ == '__main__':
    main()
