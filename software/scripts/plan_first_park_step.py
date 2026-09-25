"""Replay two exports and draft the first bounded rise; never open hardware."""

import argparse
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.park_step_plan import plan_first_park_step
from rocell.application.pose_observation_export import replay_pose_observation
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-export-id', required=True)
    parser.add_argument('--pose-export-id', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / 'runs/wizard-exports'
    reference, reference_hash = _read(root, args.reference_export_id,
                                      'attachment-standard-start-reference.json')
    raw, _ = _read(root, args.pose_export_id, 'attachment-pose-raw.json')
    replay = replay_pose_observation(root, args.pose_export_id)
    if replay['replay_verified'] is not True:
        raise ValueError('Pose source did not replay')
    boot = raw['subject']['expected_boot']
    plan = plan_first_park_step(reference, replay['assessment'],
                                observation_boot=boot,
                                observation_export_id=args.pose_export_id)
    plan['reference_export_id'] = args.reference_export_id
    plan['reference_attachment_sha256'] = reference_hash
    plan['observation_bundle_sha256'] = replay['raw_bundle_sha256']
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'offline-first-park-step-plan'}, [], attachments={
        'first-park-step-plan.json': canonical(plan)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Plan export failed verification')
    print(json.dumps(dict(export_path=saved['path'], target_goals=plan['target_goals'],
                          movement_authorized=False, hardware_access=False)))


if __name__ == '__main__':
    main()
