"""Offline campaign review using the existing classifier and export format.

This module deliberately has no device adapter. Counts are encoder evidence,
not millimetres or independently measured tip accuracy. No fitted correction
is applied to the coupled shoulder pair.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import fields
import json
from pathlib import Path
from statistics import mean

from .compensated_shoulder_contract import Pose
from .first_motion_contract import canonical
from .shoulder_characterization import assess_leg
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def summarize_campaign(report: dict) -> dict:
    """Reassess raw synthetic observations; never trust stored pass labels.

    Deliberately accepts only the current simulation schema. A live importer
    must preserve freshness and delivery evidence before sharing this path.
    """
    if (report.get('schema') != 'rocell.shoulder_characterization_sim.v1'
            or report.get('basis') != 'SYNTHETIC_ONLY'
            or report.get('physical_packets') != 0
            or report.get('movement_authorized') is not False):
        raise ValueError('Expected an explicitly synthetic campaign')
    legs = report.get('legs')
    if not isinstance(legs, list) or not 1 <= len(legs) <= 12:
        raise ValueError('Expected one to twelve campaign legs')
    groups = defaultdict(list)
    excluded = []
    pose_fields = {field.name for field in fields(Pose)}
    stopped = False
    for index, leg in enumerate(legs, 1):
        if leg.get('leg_id') != index:
            raise ValueError('Noncontiguous campaign legs')
        if stopped:
            raise ValueError('Evidence contains progression after an excluded leg')
        # Incomplete and stopped legs remain visible, not silently fitted away.
        if not leg.get('result_export') or leg.get('assessment', {}).get('status') == 'STOP':
            excluded.append({'leg_id': index, 'reason': 'INCOMPLETE_OR_STOPPED'})
            stopped = True
            continue
        try:
            before = Pose(**{key: leg['baseline'][key] for key in pose_fields})
            samples = [Pose(**{key: sample[key] for key in pose_fields})
                       for sample in leg['samples']]
            goals = leg['command']['command_goals']
            assessed = assess_leg(before, goals, samples, bounds=report['bounds'],
                                  delivery_confirmed=True, export_verified=True)
        except (KeyError, TypeError) as error:
            raise ValueError('Malformed raw campaign observations') from error
        if assessed['status'] == 'STOP':
            raise ValueError('Stored successful leg fails raw reassessment')
        for pair_index, servo_id in enumerate((12, 13)):
            direction = 1 if assessed['goal_delta'][pair_index] > 0 else -1
            command = leg['command']
            key = (servo_id, goals[pair_index], direction,
                   command['speed'], command['acceleration'])
            groups[key].append((index, assessed['endpoint_error'][pair_index]))
    rows = []
    for (servo_id, target, direction, speed, acceleration), values in sorted(groups.items()):
        errors = [value for _, value in values]
        rows.append(dict(servo_id=servo_id, target_counts=target,
                         approach_direction=direction, speed=speed, acceleration=acceleration,
                         leg_ids=[leg for leg, _ in values], samples=len(errors),
                         mean_error_counts=mean(errors),
                         max_absolute_error_counts=max(map(abs, errors)),
                         endpoint_range_counts=max(errors)-min(errors)))
    return dict(schema='rocell.characterization_batch_review.v1', basis='SYNTHETIC_ONLY',
                campaign_state=report['state'], grouped_endpoints=rows, excluded_legs=excluded,
                physical_packets=0, movement_authorized=False, compensation_applied=False,
                limitations=[
                    'Synthetic results do not qualify hardware or stylus accuracy.',
                    'Range is repeatability at one target, direction, speed and acceleration.',
                    'No causal direction claim without matched opposite-direction targets.',
                    'No compensation fit or independent paired-servo corrections.'])


def review_export(source: Path, destination: Path) -> dict:
    """Verify the source bundle, summarize it, and publish a verified new bundle."""
    source = Path(source).resolve()
    verified = verify_export(source)
    if not verified['valid']:
        raise ValueError('Source export failed integrity verification')
    name = 'attachment-campaign-result.json'
    entry = next((item for item in verified['files'] if item['name'] == name), None)
    if entry is None:
        raise ValueError('Source is not a campaign-result export')
    payload = (source / name).read_bytes()
    # Bind the actual bytes used for analysis, not just an earlier verification.
    import hashlib
    if len(payload) != entry['bytes'] or hashlib.sha256(payload).hexdigest() != entry['sha256']:
        raise ValueError('Campaign changed after verification')
    summary = summarize_campaign(json.loads(payload))
    summary['source_manifest_sha256'] = verified['manifest_sha256']
    exporter = WizardDiagnosticExporter(Path(destination).resolve())
    exporter.prepare(create=True)
    from .characterization_report import render_batch_review
    saved = exporter.export({'mode': 'characterization-batch-review'}, [],
                            attachments={'batch-review.json': canonical(summary),
                                         'batch-review.md': render_batch_review(summary).encode('utf-8')})
    if not verify_export(Path(saved['path']))['valid']:
        raise OSError('Review export failed integrity verification')
    return {'summary': summary, 'export_path': saved['path']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--simulate', action='store_true', help='Run existing 12-leg synthetic campaign')
    mode.add_argument('--source', type=Path, help='Existing verified simulation campaign-result bundle')
    parser.add_argument('--exports', required=True, type=Path)
    parser.add_argument('--pattern', choices=('legacy', 'matched'), default='legacy',
                        help='Offline simulation pattern; does not enable controller support')
    args = parser.parse_args(argv)
    source = args.source
    if args.simulate:
        # Reviewing an existing export must not depend on loading a simulator.
        from .shoulder_characterization_sim import run_characterization_sim
        source = Path(run_characterization_sim(args.exports, pattern=args.pattern)['export_path'])
    print(json.dumps(review_export(source, args.exports), indent=2))


if __name__ == '__main__':
    main()
