"""Read-only pinned comparison; no serial access, fitting or motion authority."""
import base64
import json
import math
from pathlib import Path

from rocell.application.positional_campaign_native_export import verify_native_retained_export
from rocell.application.positional_campaign_capture import validate_campaign_capture
from rocell.application.first_motion_contract import canonical
from rocell.providers.windows.positional_campaign_native_protocol import decode_request
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
from rocell.arm.campaign_stream_sync import campaign_window

PINS=(
    ('campaign-2f1f627662f740948dca6f70b3145105','f601f654983cc11fc8c85b6447b3564a8b81332399668bdd01a9f2cb412a91ec'),
    ('campaign-83563fca6ffc425ab12d94061c3c7bb0','dd29aad9a417490e5c277246e3824b0bdaa1ec8443d9b0b6f0bc3a08d202585f'),
    ('campaign-e621169d1a9147158c32c043e17022f8','262df257dd73f9e0f79d3fb825d6a885fea3053ae2d6fd89a21220cdc3b28017'),
)


def require(condition,message):
    if not condition:
        raise ValueError(message)


def read_trial(cid,digest):
    root=Path(__file__).resolve().parents[1]/'runs'/'wizard-exports'/cid
    v=verify_native_retained_export(root,cid+'-parent-report.json')
    require(v['valid'] and v['reconstruction_consistent'] and v['endpoint_completion_consistent']
            and v['report_sha256']==digest,'Pinned completed export required')
    def original(name):
        return base64.b64decode(json.loads((root/(cid+'-parent-'+name+'.original.json')).read_bytes())['base64'],validate=True)
    b=decode_request(original('request'))['payload']['campaign_intent']
    request=PositionalCampaignIntent(canonical(b))
    trial=json.loads(original('trial'));leg=trial['legs'][0]
    require(len(trial['legs'])==1 and trial['native_submission_attempts']==1,'One submission required')
    require(not leg['write']['uncertain'] and trial['cleanup']['all_handles_closed']
            and trial['cleanup']['within_budget'] and trial['cleanup']['pending_io_count']==0,'Write/cleanup failed')
    poses={}
    for phase in ('baseline','post'):
        c=leg[phase]
        raw=validate_campaign_capture(request,c,phase=phase,
            command_completed_ns=leg['write']['finished_ns'] if phase=='post' else None)
        rows,issues,_=campaign_window(b,phase,raw,c['read_windows'],c['started_ns'],c['finished_ns'],
            maximum_bytes=b['limits']['maximum_raw_bytes_per_leg'])
        require(rows and not issues,'Invalid capture')
        poses[phase]=rows[-1][2]
    e=v['endpoint_diagnostics'][0]
    require(e['persistence']['status']=='REPORTED_ENDPOINT_PERSISTENT','Persistence failed')
    return dict(campaign_id=cid,report_sha256=digest,schema=b['schema'],
        start=poses['baseline'],final=poses['post'],command=b['legs'][0]['command'],
        references=b['references'],endpoint=e,write=leg['write'],cleanup=trial['cleanup'])


def review():
    old,up,down=[read_trial(*pin) for pin in PINS]
    require(old['start']==down['start'] and old['command']==down['command']
            and old['schema']==down['schema'],'Decreasing geometry mismatch')
    require(up['final']==down['start'],'Reported handoff mismatch')
    reference_matches={key:old['references'][key]==down['references'][key] for key in old['references']}
    for key in ('configuration_sha256','native_controller_review_sha256','protocol_review_sha256',
                'workcell_sha256','tool_payload_sha256','bounded_motion_risk_sha256'):
        require(reference_matches[key],'Experimental context differs: '+key)
    return dict(schema='rocell.roll_return_pair_review.v1',trials=[old,up,down],
        decreasing_reference_matches=reference_matches,
        same_source_and_runtime=all(reference_matches[k] for k in ('source_sha256','runtime_sha256')),
        decreasing_endpoint_difference_deg=math.degrees(down['final'][4]-old['final'][4]),
        recent_pair_signed_errors_deg=[math.degrees(t['endpoint']['signed_error_rad']) for t in (up,down)],
        recent_pair_reported_travel_deg=[math.degrees(t['final'][4]-t['start'][4]) for t in (up,down)],
        recent_pair_return_difference_rad=[a-b for a,b in zip(down['final'],up['start'])],
        fitted_compensation=False,physical_accuracy_verified=False,motion_authorized=False)


if __name__=='__main__':
    print(json.dumps(review(),indent=2))
