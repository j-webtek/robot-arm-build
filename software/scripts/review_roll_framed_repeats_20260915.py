"""Verify all four v21 originals; compare repetition without granting motion."""
import base64
import json
import math
from pathlib import Path
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from rocell.providers.windows.positional_campaign_native_protocol import decode_request

PINS=(
    ('campaign-8162e80bb7d446f1b7a994d4e1ce65c3','53a8b1ccde41dae37ef556879d40c43b46f8f6ac1382f3313ee8e4935423e2f0'),
    ('campaign-aba218bc89224e91a0c3a830d56d0f39','b7944c052b571dc65cc84544ead6d83b3afdb7fb50c885aa7949a1a286480a8e'),
    ('campaign-ace739d6a5d3488e950f0c01ba28e354','99656b9153743d82ad154809d12f2e42962fa701b167d4ce626a488847f9d186'),
    ('campaign-503fa3f0796a441d9866bfa614ea9a59','596f7a796a9685f09a65750e19ff3564ca6ad235bb4cdc5621ba36bc4d7a812a'),
)


def require(condition,message):
    if not condition:
        raise ValueError(message)


def review():
    rows=[]
    for cid,digest in PINS:
        root=Path(__file__).resolve().parents[1]/'runs'/'wizard-exports'/cid
        v=verify_native_retained_export(root,cid+'-parent-report.json')
        require(v['valid'] and v['reconstruction_consistent'] and v['endpoint_completion_consistent']
                and v['report_sha256']==digest,'Pinned completed export required')
        def original(name):
            return base64.b64decode(json.loads((root/(cid+'-parent-'+name+'.original.json')).read_bytes())['base64'],validate=True)
        body=decode_request(original('request'))['payload']['campaign_intent']
        trial=json.loads(original('trial'));e=v['endpoint_diagnostics'][0]
        require(body['schema']=='rocell.attended_positional_intent.v21','Expected v21')
        require(trial['native_submission_attempts']==1 and len(trial['legs'])==1,'One write required')
        require(e['persistence']['status']=='REPORTED_ENDPOINT_PERSISTENT','Persistence failed')
        rows.append(dict(campaign_id=cid,verification=v,staged_start=body['start_joints_rad'],
            write=trial['legs'][0]['write'],cleanup=trial['cleanup']))
    pairs=[]
    for a,b in ((rows[0],rows[2]),(rows[1],rows[3])):
        av,bv=a['verification'],b['verification']
        ae,be=av['endpoint_diagnostics'][0],bv['endpoint_diagnostics'][0]
        require(a['staged_start']==b['staged_start'] and ae['start_rad']==be['start_rad']
                and ae['command']==be['command'],'Pair geometry changed')
        matches={k:av['configuration_references'][k]==value for k,value in bv['configuration_references'].items()}
        require(all(value for k,value in matches.items() if k not in ('runtime_sha256','owned_baseline_sha256')),
                'Context mismatch')
        pairs.append(dict(direction=ae['direction'],sample_count=2,reference_matches=matches,
            campaigns=[a['campaign_id'],b['campaign_id']],
            final_rad=[e['final_rad'] for e in (ae,be)],
            signed_errors_deg=[math.degrees(e['signed_error_rad']) for e in (ae,be)],
            endpoint_spread_deg=abs(math.degrees(be['final_rad']-ae['final_rad']))))
    final=rows[-1]['verification']['endpoint_diagnostics'][0]['final_rad']
    return dict(schema='rocell.roll_framed_repeat_screen.v1',trials=rows,pairs=pairs,
        final_reported_roll_rad=final,
        next_fixed_start_matches=abs(final-.004601942)<=math.radians(.01),
        continuation='STOPPED_AFTER_FINITE_PAIR_AND_UNMATCHED_NEXT_ANCHOR',
        historical_faults_superseded=False,compensation_applied=False,
        physical_accuracy_verified=False,motion_authorized=False)


if __name__=='__main__':
    print(json.dumps(review(),indent=2))
