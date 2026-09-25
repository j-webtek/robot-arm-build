"""Replay selected saved roll campaigns and hypothetical correction decisions.

No hardware access, model fitting, transport creation or admission consumption.
Optional output is a new exclusive diagnostic JSON file, never an overwrite.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

from review_wifi_roll_export import review
from rocell.arm.endpoint_correction_simulation import assess_correction


def completed_journal(exports, session, *, expected_legs, expected_final_hash):
    """Verify the frozen journal and return ordered references, not motion authority."""
    header=(exports/f'comparison-{session}-header.json').read_bytes()
    if json.loads(header).get('session_id') != session:
        raise ValueError('Journal header identity mismatch')
    previous=hashlib.sha256(header).hexdigest(); events=[]; legs=[]
    for path in sorted(exports.glob(f'comparison-{session}-[0-9]*.json')):
        raw=path.read_bytes(); row=json.loads(raw); event=row['event']
        if (row['sequence']!=len(events) or row['previous_sha256']!=previous
                or event.get('session_id')!=session):
            raise ValueError('Journal chain or identity mismatch')
        previous=hashlib.sha256(raw).hexdigest(); events.append(event)
        if event['event']=='LEG_VERIFIED':
            if event['index']!=len(legs):raise ValueError('Journal leg order mismatch')
            legs.append(event)
    if (previous!=expected_final_hash or not events or events[-1].get('event')!='FINISHED'
            or events[-1].get('status')!='COMPLETED' or len(legs)!=expected_legs
            or events[-1].get('reviewed_legs')!=expected_legs
            or len({leg['export_id'] for leg in legs})!=expected_legs):
        raise ValueError('Incomplete or changed frozen journal')
    return legs


def direction_summary(records):
    """Descriptive groups only: varying roll baselines remain explicit confounders."""
    groups = defaultdict(list)
    for row in records:
        if not row['full_validation_success']:
            continue
        baseline=row['baseline_rad']; command=row['command']
        direction='ascending' if command['rad']>baseline[4] else 'descending' if command['rad']<baseline[4] else 'unchanged'
        key=json.dumps([command,row['desired_endpoint_deg'],direction,
                        baseline[:4]+baseline[5:]],sort_keys=True)
        groups[key].append(row)
    result=[]
    for key,rows in groups.items():
        command,desired,direction,other_joints=json.loads(key)
        angles=[r['final_deg'] for r in rows]
        result.append(dict(command_deg=math.degrees(command['rad']),desired_deg=desired,
            direction=direction,speed=command['spd'],acceleration=command['acc'],
            other_joint_baseline_rad=other_joints,count=len(rows),
            reported_endpoint_min_deg=min(angles),reported_endpoint_max_deg=max(angles),
            reported_endpoint_span_deg=max(angles)-min(angles),
            maximum_absolute_desired_error_deg=max(abs(x-desired) for x in angles),
            in_illustrative_005_band=sum(abs(x-desired)<=.05 for x in angles),
            starting_roll_deg=sorted(set(math.degrees(r['baseline_rad'][4]) for r in rows)),
            session_ids=sorted(set(r.get('session_id') or 'UNKNOWN' for r in rows)),
            exports=[r['export_id'] for r in rows]))
    return result


def collect(root, *, include_recent=False, include_balanced=False):
    """Explicit evidence cohorts, deduplicated by export ID (not endpoint value)."""
    docs = root/'software/docs'
    mapping = json.loads((docs/'ROLL_LOCAL_MAPPING_EVIDENCE.json').read_bytes())
    sweep = json.loads((docs/'LOCAL_COMMAND_SWEEP_EVIDENCE.json').read_bytes())
    cohorts = defaultdict(set)
    for key in ('held_out_lookup', 'uncorrected_controls'):
        for export in mapping[key]['exports']:
            cohorts[export].add(key)
    for item in mapping['interruption_history']:
        cohorts[item['export']].add('interruption')
    for key in ('probes', 'separate_followups'):
        for item in sweep[key]:
            cohorts[item['export_id']].add(key)
    exports = root/'software/runs/wizard-exports'
    balanced_refs={}
    if include_balanced:
        include_recent=True
        session='86b99f6aa91c4e0b800ad17ac13945b9'
        for leg in completed_journal(exports,session,expected_legs=8,
                expected_final_hash='edb6dc46db55beeef5daa7274e9a4b47dc72421ffbbafec4824d1a5c3ade1646'):
            cohorts[leg['export_id']].add('balanced_direction_block')
            balanced_refs[leg['export_id']]=dict(comparison_session_id=session,
                leg_index=leg['index'],manifest_file_sha256=leg['manifest_file_sha256'],
                predecessor=leg.get('predecessor'),measured_interval_s=leg.get('measured_interval_s'))
    if include_recent:
        reverse=json.loads((docs/'ROLL_REVERSE_ORDER_EVIDENCE.json').read_bytes())
        for row in reverse['legs']:
            cohorts[row['export']].add('reverse_order_'+row['role'])
        for export,label in (
            ('wizard-20260917T023026790706Z-152ba4ea102e4a7097c1cee0eb2ae37a','earlier_ascending_control'),
            ('wizard-20260917T114034463638Z-2ca2721b65cf49bab117051e31e8c561','first_micro_positioning'),
            ('wizard-20260917T114136387057Z-8814afa2619443058843275609f6cd3a','first_micro_predecessor')):
            cohorts[export].add(label)
    session = 'f779bddc786f4828945dee5aa264609b'
    previous = hashlib.sha256((exports/f'comparison-{session}-header.json').read_bytes()).hexdigest()
    events = []
    for path in sorted(exports.glob(f'comparison-{session}-[0-9]*.json')):
        raw = path.read_bytes()
        row = json.loads(raw)
        if row['sequence'] != len(events) or row['previous_sha256'] != previous:
            raise ValueError('Session journal chain mismatch')
        previous = hashlib.sha256(raw).hexdigest()
        events.append(row['event'])
        if row['event']['event'] == 'LEG_VERIFIED':
            cohorts[row['event']['export_id']].add('paired_session')
    if not events or events[-1].get('status') != 'COMPLETED':
        raise ValueError('Expected completed paired session')
    records = []
    for export, names in sorted(cohorts.items()):
        evidence = review(exports/export)
        record = {key: evidence.get(key) for key in (
            'export_id', 'manifest_file_sha256', 'baseline_rad', 'command',
            'desired_endpoint_deg', 'final_deg', 'full_validation_success',
            'failure_code', 'transaction_state')}
        record['cohorts'] = sorted(names)
        if export in balanced_refs:
            ref=balanced_refs[export]
            if evidence['manifest_file_sha256']!=ref['manifest_file_sha256']:
                raise ValueError('Balanced journal/export manifest mismatch')
            record['comparison_provenance']=ref
        manifest=json.loads((exports/export/'manifest.json').read_bytes())
        record['session_id']=manifest.get('provenance',{}).get('session_id')
        record['hypothetical_correction'] = assess_correction(evidence)
        records.append(record)
    groups = defaultdict(list)
    for record in records:
        if record['full_validation_success']:
            # Keep target, full baseline, speed and acceleration in the grouping.
            command = record['command']
            key = json.dumps([command, record['desired_endpoint_deg'], record['baseline_rad']], sort_keys=True)
            groups[key].append(record)
    summaries = []
    for key, group in groups.items():
        angles = [r['final_deg'] for r in group]
        summaries.append(dict(command_target_baseline=json.loads(key), count=len(group),
                              endpoint_min_deg=min(angles), endpoint_max_deg=max(angles),
                              endpoint_span_deg=max(angles)-min(angles),
                              exports=[r['export_id'] for r in group]))
    return dict(schema='rocell.cross_session_roll_replay.v1',
                scope='SELECTED_DOCUMENTED_COHORTS_NOT_ALL_HISTORY',
                records=records, matched_groups=summaries,
                direction_groups=direction_summary(records),
                includes_recent=include_recent,
                includes_balanced=include_balanced,
                grouping_limitations='Direction groups retain other-joint baseline and command/target/speed/acceleration, but not identical starting roll or hidden history. Session IDs describe exports, not independent mechanical trials.',
                decisions=dict(Counter(r['hypothetical_correction']['decision'] for r in records)),
                model_fitted=False, motion_authorized=False, physical_accuracy_verified=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--include-recent', action='store_true', help='Include reverse-order controls and first micro-workflow legs')
    parser.add_argument('--include-balanced', action='store_true', help='Include complete frozen eight-leg direction block and recent cohorts')
    args = parser.parse_args()
    result = collect(Path(__file__).resolve().parents[2],include_recent=args.include_recent,include_balanced=args.include_balanced)
    if args.output:
        with args.output.open('x', encoding='utf-8') as output:
            json.dump(result, output, indent=2)
            output.write('\n')
    print(json.dumps(dict(records=len(result['records']), decisions=result['decisions'],
                          groups=len(result['matched_groups'])), indent=2))
