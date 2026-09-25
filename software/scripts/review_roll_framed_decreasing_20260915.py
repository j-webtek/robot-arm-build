"""Pinned live v21 comparison against the historical held v20; no hardware I/O."""
import base64
import json
import math
from pathlib import Path
import runpy
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from rocell.providers.windows.positional_campaign_native_protocol import decode_request

CID='campaign-aba218bc89224e91a0c3a830d56d0f39'
SHA='b7944c052b571dc65cc84544ead6d83b3afdb7fb50c885aa7949a1a286480a8e'


def require(condition,message):
    if not condition:
        raise ValueError(message)


def review():
    root=Path(__file__).resolve().parents[1]/'runs'/'wizard-exports'
    historical=runpy.run_path(str(Path(__file__).with_name('review_roll_cross_window_20260915.py')))['review']()
    def original(cid,name):
        wrapper=json.loads((root/cid/(cid+'-parent-'+name+'.original.json')).read_bytes())
        return base64.b64decode(wrapper['base64'],validate=True)
    verified=verify_native_retained_export(root/CID,CID+'-parent-report.json')
    require(verified['valid'] and verified['reconstruction_consistent'] and
            verified['endpoint_completion_consistent'] and verified['report_sha256']==SHA,
            'Pinned completed export required')
    current=decode_request(original(CID,'request'))['payload']['campaign_intent']
    prior=decode_request(original(historical['campaign_id'],'request'))['payload']['campaign_intent']
    require(current['start_joints_rad']==prior['start_joints_rad'] and
            current['legs'][0]['command']==prior['legs'][0]['command'],'Geometry changed')
    trial=json.loads(original(CID,'trial')); e=verified['endpoint_diagnostics'][0]
    require(trial['native_submission_attempts']==1 and len(trial['legs'])==1,'One write required')
    require(e['persistence']['status']=='REPORTED_ENDPOINT_PERSISTENT','Persistence failed')
    require(e['cross_window_framing']['status']=='CROSSING_FRAME_EXCLUDED','Expected split frame')
    return dict(schema='rocell.roll_framed_decreasing_review.v1',campaign_id=CID,
        verification=verified,write=trial['legs'][0]['write'],cleanup=trial['cleanup'],
        historical_replay=historical,geometry_matches=True,
        reference_matches={k:current['references'][k]==prior['references'][k] for k in current['references']},
        schema_matches=current['schema']==prior['schema'],
        target_deg=math.degrees(e['target_rad']),final_deg=math.degrees(e['final_rad']),
        signed_error_deg=math.degrees(e['signed_error_rad']),
        reported_travel_deg=math.degrees(e['final_rad']-e['start_rad']),
        difference_from_historical_final_deg=math.degrees(e['final_rad']-historical['persistence']['final_rad']),
        compensation_applied=False,physical_accuracy_verified=False,motion_authorized=False)


if __name__=='__main__':
    print(json.dumps(review(),indent=2))
