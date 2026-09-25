"""Offline pinned-firmware FK/IK check for the proposed 2 mm bench endpoint.

No serial, native provider, motion permit or board-coordinate transform exists
here. The reference equations predict geometry, not physical motion or timing.
Constants/functions transcribe RoArm-M3_config.h:101-177 and
RoArm-M3_module.h:531-555,595-619,694-731 from the pinned official archive.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from rocell.kinematics.firmware_reference import forward, inverse, REFERENCE_SHA256, REFERENCE_URL


def review(document):
    """Inspect 41 geometric samples, not timed servo or full-link simulation."""
    ranges = document['observed_axis_ranges']
    required = ('x', 'y', 'z', 'tit', 'b', 's', 'e', 't')
    for key in required:
        pair = ranges[key]
        if (type(pair) is not list or len(pair) != 2 or pair[0] != pair[1]
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       or abs(v)>1e6 for v in pair)):
            raise ValueError('Finite constant captured axes required')
    observed = tuple(ranges[k][0] for k in ('x', 'y', 'z', 'tit'))
    joints = tuple(ranges[k][0] for k in ('b', 's', 'e', 't'))
    modeled = forward(*joints)
    samples = []
    for index in range(41):
        # Geometric subdivisions only: no timing or physical speed inference.
        target = (*observed[:2], observed[2]+2*index/40, observed[3])
        result = inverse(*target)
        recovered = forward(*result)
        samples.append({'fraction': index/40, 'joints_rad': result,
                        'roundtrip_position_error_mm': math.dist(target[:3], recovered[:3])})
    return {'schema': 'rocell.bench_reference_kinematics_review.v1',
            'reference_url': REFERENCE_URL, 'reference_archive_sha256': REFERENCE_SHA256,
            'source_outcome_sha256': document['source_outcome_sha256'],
            'basis': 'PINNED_REFERENCE_MODEL_NOT_INSTALLED_BINARY',
            'observed_pose': observed, 'reference_fk': modeled,
            'fk_position_residual_mm': math.dist(observed[:3], modeled[:3]),
            'fk_pitch_residual_rad': abs(observed[3]-modeled[3]),
            'target_joint_change_deg': [math.degrees(b-a) for a,b in zip(joints,samples[-1]['joints_rad'])],
            'max_sampled_joint_change_deg': [max(abs(math.degrees(s['joints_rad'][i]-joints[i])) for s in samples) for i in range(4)],
            'samples': samples, 'full_link_and_cable_clearance_verified': False,
            'device_sample_freshness_verified': False, 'installed_binary_verified': False,
            'physical_accuracy_verified': False, 'motion_authorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.baseline_review.read_bytes()
    if len(raw)>128*1024:
        raise ValueError('Baseline review exceeds input budget')
    report = review(json.loads(raw))
    report['baseline_review_sha256'] = hashlib.sha256(raw).hexdigest()
    encoded = json.dumps(report, sort_keys=True, indent=2, allow_nan=False)+'\n'
    # Exclusive publication preserves any earlier report. This is no approval.
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(encoded)
    print(json.dumps({k:v for k,v in report.items() if k!='samples'}))


if __name__ == '__main__':
    main()
