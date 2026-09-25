"""Read-only reconstruction of discovery and delayed feedback; never moves hardware."""
import base64
import hashlib
import json
import math
from pathlib import Path
import runpy


SCRIPTS = Path(__file__).resolve().parent
FOLLOWUPS = (
    ('operation-4a2e8381b6f1478f928e7b16a4fe965f',
     'a1be8befdf7f272b1479d4d219d43f627db426eb59402e40257e202dccaa07e6'),
    ('operation-6e7941fcd7a64189a8f9591af75e0b46',
     '285b5b926ce2f1b0e5c6dcba983bacf5f5daa5c9d21dbe38b3d7e68ee436a0a2'),
)


def main():
    # Reuse the original-byte verifier, not a copied display summary.
    review = runpy.run_path(str(SCRIPTS / 'review_roll_fixed_repeat_20260915.py'))
    require = review['require']
    trial = review['read_trial']('campaign-7f6aa44cee654b4c88dc7b77ca129564',
        '05c456aa946170a3a6f3d9ccb9f6ed5a06da315d45e3167dce68eb10c22a3c61')
    baseline_reader = runpy.run_path(str(SCRIPTS / 'bench_attended_campaign.py'))['retained_start']
    captures = []
    for operation, digest in FOLLOWUPS:
        path = Path('software/runs/wizard-diagnostics') / (operation + '-powered-feedback-outcome.json')
        pose, original, details = baseline_reader(path)
        require(hashlib.sha256(original).hexdigest() == digest, 'Follow-up original changed')
        envelope = json.loads(original)
        observation = json.loads(base64.b64decode(envelope['body']['stdout_base64'],
            validate=True))['child_result']['observation']
        lifecycle = observation['lifecycle']
        require(lifecycle['confirmed_write_bytes'] == 0 and
                lifecycle['actual_effect_counts']['robot_commands_sent'] == 0 and
                lifecycle['cleanup_confirmed'] and not observation['errors'],
                'Follow-up was not a clean zero-command capture')
        captures.append(dict(operation=operation, original_sha256=digest,
            final_joints_rad=pose, planning_parse=details,
            difference_from_trial_final_deg=[math.degrees(a-b) for a,b in zip(pose,trial['final'])],
            capture_start_after_write_ms=(observation['acquisition_started_monotonic_ns']-
                trial['write']['finished_ns'])/1e6,
            capture_end_after_write_ms=(observation['observation_finished_monotonic_ns']-
                trial['write']['finished_ns'])/1e6,
            confirmed_write_bytes=0, cleanup_confirmed=True))
    require(captures[0]['final_joints_rad'] == captures[1]['final_joints_rad'],
            'Follow-up endpoints no longer agree')
    require(all(captures[0]['final_joints_rad'][i] == trial['final'][i]
                for i in (0,1,2,3,5)), 'Other-joint change')
    print(json.dumps(dict(schema='rocell.roll_second_point_discovery.v1',
        trial=trial, followups=captures, motion_command_count=1,
        second_planned_command_sent=False, progression='HELD_FOR_ENDPOINT_CONTEXT_CHANGE',
        compensation_applied=False, physical_accuracy_verified=False,
        causal_explanation_verified=False, motion_authorized=False), indent=2))


if __name__ == '__main__':
    main()
