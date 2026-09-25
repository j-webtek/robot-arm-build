"""Read-only pinned verification of the first v21 live run and prior geometry."""
import base64
import json
import math
from pathlib import Path

from rocell.application.positional_campaign_native_export import verify_native_retained_export
from rocell.providers.windows.positional_campaign_native_protocol import decode_request

PINS=(
    ('campaign-8e69010a84ae4ad2b8775c6cf1fd9df9','0c6a85363feff26896b40f96dc9f2a9302d78ebccd3837eb1e877c0254923402'),
    ('campaign-8162e80bb7d446f1b7a994d4e1ce65c3','53a8b1ccde41dae37ef556879d40c43b46f8f6ac1382f3313ee8e4935423e2f0'),
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
                and v['report_sha256']==digest,'Pinned complete export required')
        def original(name):
            return base64.b64decode(json.loads((root/(cid+'-parent-'+name+'.original.json')).read_bytes())['base64'],validate=True)
        body=decode_request(original('request'))['payload']['campaign_intent']
        trial=json.loads(original('trial'))
        require(len(trial['legs'])==1 and trial['native_submission_attempts']==1,'Unexpected submission count')
        e=v['endpoint_diagnostics'][0]
        require(e['persistence']['status']=='REPORTED_ENDPOINT_PERSISTENT','Persistence did not pass')
        rows.append(dict(campaign_id=cid,verification=v,schema=body['schema'],
            staged_start=body['start_joints_rad'],write=trial['legs'][0]['write'],cleanup=trial['cleanup']))
    previous,current=rows
    a,b=[r['verification']['endpoint_diagnostics'][0] for r in rows]
    require(previous['staged_start']==current['staged_start'] and a['start_rad']==b['start_rad']
            and a['command']==b['command'],'Geometry differs')
    require(current['schema']=='rocell.attended_positional_intent.v21','Expected framed profile')
    proof=b['cross_window_framing']
    require(proof['status']=='CROSSING_FRAME_EXCLUDED' and proof['byte_continuity_consistent']
            and not proof['crossing_frame_counted_as_post'],'Split handling not demonstrated')
    return dict(schema='rocell.roll_framed_live_review.v1',trials=rows,
        geometry_matches=True,schema_matches=previous['schema']==current['schema'],
        reference_matches={k:previous['verification']['configuration_references'][k]==value
            for k,value in current['verification']['configuration_references'].items()},
        reported_endpoint_difference_deg=math.degrees(b['final_rad']-a['final_rad']),
        target_deg=math.degrees(b['target_rad']),final_deg=math.degrees(b['final_rad']),
        signed_error_deg=math.degrees(b['signed_error_rad']),
        reported_travel_deg=math.degrees(b['final_rad']-b['start_rad']),
        compensation_applied=False,physical_accuracy_verified=False,motion_authorized=False)


if __name__=='__main__':
    print(json.dumps(review(),indent=2))
