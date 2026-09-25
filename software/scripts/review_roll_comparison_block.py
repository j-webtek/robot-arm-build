"""Offline audit of an explicit high/control/high/lookup block. No hardware I/O.

Paths must be supplied in execution order. Export timestamps do not establish a
shared host boot; cross-export timing remains conditional until a session runner
records that identity. This report never authorizes the next movement.
"""
import argparse
import json
import math
from pathlib import Path

from review_wifi_roll_export import JOINTS, review

LOOKUP_HASH='822965da1d902c86993a50c8647b06e672e37323b56a211a42a1c4bc6e48a910'
EXPECTED=(('high',2.5,2.5),('control',1.25,1.25),
          ('high',2.5,2.5),('lookup',.95,1.25))


def load_leg(path):
    """Load only manifest-listed attachments after independent export replay."""
    path=Path(path).resolve()
    summary=review(path)
    manifest=json.loads((path/'manifest.json').read_bytes())
    reports=[]
    for item in manifest['files']:
        name=item['name']
        if name.startswith('attachment-result-') and name.endswith('.json'):
            reports.extend(s['report'] for s in json.loads((path/name).read_bytes()).get('steps',[])
                           if 'report' in s)
    movement=next(r for r in reports if 'outcome' in r)
    holds=[r for r in reports if 'samples' in r]
    tx=movement['outcome']['transaction']
    return dict(summary=summary,dispatch_s=tx['dispatch_started_ns']/1e9,
        baseline=tx['baseline'],last_hold=(holds[0]['samples'][-1] if len(holds)==1 else None))


def assess_block(legs):
    """Pure block audit of replayed legs; no admission, fitting or retries."""
    if len(legs)!=4:
        raise ValueError('Exactly four explicit legs required')
    identifiers=[leg['summary']['export_id'] for leg in legs]
    if len(set(identifiers))!=4:
        raise ValueError('Repeated export cannot count as an independent leg')
    failures=[];links=[]
    for i,(leg,(role,command,desired)) in enumerate(zip(legs,EXPECTED)):
        r=leg['summary'];c=r['command']
        if not r['full_validation_success']:
            failures.append(dict(leg=i,reason='ENDPOINT_OR_HOLD_NOT_VERIFIED'))
        if (c.get('T')!=101 or c.get('joint')!=5 or c.get('spd')!=20 or c.get('acc')!=1
                or not math.isclose(c.get('rad',math.nan),math.radians(command),abs_tol=1e-12)
                or not math.isclose(r['desired_endpoint_deg'],desired,abs_tol=1e-12)
                or r['command_attempts']!=1):
            failures.append(dict(leg=i,reason='COMMAND_PROTOCOL_MISMATCH'))
        candidate=r.get('candidate')
        if role=='lookup':
            if not candidate or candidate.get('candidate_sha256')!=LOOKUP_HASH:
                failures.append(dict(leg=i,reason='FROZEN_CANDIDATE_MISMATCH'))
        elif candidate is not None:
            failures.append(dict(leg=i,reason='UNEXPECTED_COMPENSATION'))
        if not math.isfinite(leg['dispatch_s']):
            raise ValueError('Finite dispatch time required')
        if i:
            previous=legs[i-1];hold=previous['last_hold']
            link=dict(previous_export_id=identifiers[i-1],next_export_id=identifiers[i],
                previous_manifest_sha256=previous['summary']['manifest_file_sha256'])
            if hold is None:
                link.update(interval_s=None,within_proposed_window=False,baseline_matches=False)
            else:
                interval=leg['dispatch_s']-hold['response_finished_monotonic_s']
                if not math.isfinite(interval) or interval<0:
                    raise ValueError('Invalid cross-export clock ordering')
                link.update(interval_s=interval,within_proposed_window=18<=interval<=22,
                    baseline_matches=leg['baseline']==[hold['joints_rad'][k] for k in JOINTS])
            if not link['baseline_matches']:
                failures.append(dict(leg=i,reason='PREDECESSOR_BASELINE_MISMATCH'))
            links.append(link)
    ready=not failures
    control=legs[1]['summary'].get('hold_assessment')
    lookup=legs[3]['summary'].get('hold_assessment')
    comparison=None
    if ready and control and lookup:
        a=control['hold_final_error_deg'];b=lookup['hold_final_error_deg']
        comparison=dict(control_error_deg=a,lookup_error_deg=b,
            absolute_error_reduction_deg=abs(a)-abs(b))
    return dict(schema='rocell.roll_comparison_block.v1',
        export_ids=identifiers,failures=failures,links=links,
        individual_legs_and_protocol_pass=ready,
        proposed_timing_window_s=[18,22],
        observed_intervals_within_window=all(link['within_proposed_window'] for link in links),
        comparison=comparison,shared_clock_epoch_verified=False,
        controlled_block_qualified=False,motion_authorized=False,
        note='Historical cross-export timing is conditional; shared clock identity is not recorded. '
             'Four paths alone cannot prove no intervening commands or identical mechanical history.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exports',nargs=4,type=Path)
    args=parser.parse_args()
    result=assess_block([load_leg(p) for p in args.exports])
    print(json.dumps(result,indent=2))
    # Inspection is useful even when a historical block cannot qualify.
    if not result['controlled_block_qualified']:
        raise SystemExit(1)


if __name__=='__main__':main()
