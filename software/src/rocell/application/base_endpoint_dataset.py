"""Read-only base characterization from pinned portable originals.

No transport, review signing, compensation or native admission. Target misses
and subthreshold responses remain observations, never promoted to arrivals.
"""
import base64
import hashlib
import math
from statistics import mean
from .first_motion_contract import canonical
from .physical_onboarding_durability import safe_root, contained_path, read_bounded_regular_file
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .positional_campaign_native_export import verify_native_retained_export, LIMITS
from .positional_campaign_capture import validate_campaign_capture
from rocell.providers.windows.positional_campaign_native_protocol import decode_request
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent, BASE_SCHEMAS, BASE_EXPERIMENT_SCHEMAS, BASE_SPEED_SCHEMA
from rocell.arm.campaign_stream_sync import campaign_window

CONTEXT_KEYS=('native_controller_review_sha256','protocol_review_sha256','workcell_sha256','tool_payload_sha256')


def build_base_dataset(exports):
    """Reverify original exports; summary files may select but cannot supply data."""
    if type(exports) is not list or not 1<=len(exports)<=64:
        raise ValueError('One through 64 original export selections required')
    rows=[];seen=set()
    for selection in exports:
        if type(selection) is not dict or set(selection)!={'directory','report_name','report_sha256'}:
            raise ValueError('Exact pinned export selection required')
        v=verify_native_retained_export(selection['directory'],selection['report_name'])
        if (not v['valid'] or not v['reconstruction_consistent']
                or v['report_sha256']!=selection['report_sha256'] or v['report_sha256'] in seen):
            raise ValueError('Changed, duplicate or unreconstructed export')
        seen.add(v['report_sha256'])
        root=safe_root(selection['directory'])
        raw=read_bounded_regular_file(contained_path(root,selection['report_name'],label='base dataset report'),maximum_bytes=65536)
        if hashlib.sha256(raw).hexdigest()!=v['report_sha256']:
            raise ValueError('Report changed during dataset extraction')
        report=decode_diagnostic_json(raw,maximum=65536)
        def original(name):
            ref=report['originals'][name]
            wrapper=decode_diagnostic_json(read_bounded_regular_file(
                contained_path(root,ref['file'],label='base dataset original'),maximum_bytes=4*1024*1024),maximum=4*1024*1024)
            data=base64.b64decode(wrapper['base64'],validate=True)
            if (len(data)!=ref['bytes'] or len(data)!=wrapper['bytes'] or len(data)>LIMITS[name]
                    or hashlib.sha256(data).hexdigest()!=ref['sha256']):
                raise ValueError('Original changed during extraction')
            return data
        body=decode_request(original('request'))['payload']['campaign_intent']
        request=PositionalCampaignIntent(canonical(body))
        if body['schema'] not in BASE_SCHEMAS or body['schema'] in (*BASE_EXPERIMENT_SCHEMAS,BASE_SPEED_SCHEMA) or len(body['legs'])!=1:
            raise ValueError('Single base campaign required')
        trial=decode_diagnostic_json(original('trial'),maximum=LIMITS['trial'])
        leg=trial['legs'][0];endpoint=v['endpoint_diagnostics'][0]
        parsed={}
        for phase in ('baseline','post'):
            cap=leg[phase]
            data=validate_campaign_capture(request,cap,phase=phase,
                command_completed_ns=leg['write']['finished_ns'] if phase=='post' else None)
            values,issues,_=campaign_window(body,phase,data,cap['read_windows'],cap['started_ns'],cap['finished_ns'],maximum_bytes=98304)
            if issues:raise ValueError('Invalid dataset capture')
            parsed[phase]=values
        before,after=parsed['baseline'],parsed['post']
        monitor=leg['verification']['endpoint']
        if monitor['status'] not in ('NO_RESPONSE','TARGET_MISSED','REPORTED_SETTLED'):
            raise ValueError('Unexpected or drifting endpoint cannot characterize mapping')
        tail=[r for r in after if after[-1][0]-r[1]<=400_000_000]
        if (tail[-1][0]-tail[0][1]<200_000_000
                or max(r[2][0] for r in tail)-min(r[2][0] for r in tail)>math.radians(.1)):
            raise ValueError('Insufficient stable final tail')
        command=body['legs'][0]['command']
        if command['rad']!=endpoint['target_rad']:
            raise ValueError('Only uncorrected observations may train this dataset')
        rows.append(dict(campaign_id=body['campaign_id'],report_sha256=v['report_sha256'],
            capture_profile=body['schema'],context={k:body['references'][k] for k in CONTEXT_KEYS},
            start_joints_rad=list(before[-1][2]),final_joints_rad=list(after[-1][2]),
            target_rad=endpoint['target_rad'],command_rad=command['rad'],spd=command['spd'],acc=command['acc'],
            direction=endpoint['direction'],status=endpoint['status'],endpoint_verified=endpoint['reported_endpoint_verified'],
            post_sample_count=len(after),stable_tail_span_ns=tail[-1][0]-tail[0][1]))
    return dict(schema='rocell.base_endpoint_dataset.v1',rows=rows,
        basis='REVERIFIED_ORIGINAL_CONTROLLER_REPORTS',physical_accuracy_verified=False,
        device_sample_freshness_verified=False,motion_authorized=False)


def fit_local_base_lines(dataset):
    """Two-anchor linear hypotheses per direction; no validation claims.

    Average repeated captures within their exact target group before fitting.
    Repeats cannot become held-out target validation. The returned start ranges
    and domain restrict later predictions; baseline-profile changes are exposed.
    """
    rows=dataset['rows'];contexts={canonical(r['context']) for r in rows}
    if len(contexts)!=1:raise ValueError('Mixed experiment contexts')
    if any(r['spd']!=20 or r['acc']!=1 for r in rows):raise ValueError('Mixed speed context')
    if any(max(r['start_joints_rad'][i] for r in rows)-min(r['start_joints_rad'][i] for r in rows)>math.radians(.5) for i in range(1,6)):
        raise ValueError('Other-joint pose context differs')
    models=[]
    for direction in ('INCREASING','DECREASING'):
        selected=[r for r in rows if r['direction']==direction]
        targets=sorted({r['command_rad'] for r in selected})
        if len(targets)!=2:raise ValueError('Exactly two distinct anchors per direction required')
        anchors=[]
        for target in targets:
            group=[r for r in selected if r['command_rad']==target]
            if len(group)<2:raise ValueError('Two repeats per anchor required')
            if len({r['campaign_id'] for r in group})!=len(group):raise ValueError('Duplicate campaign')
            anchors.append(dict(command_rad=target,mean_final_rad=mean(r['final_joints_rad'][0] for r in group),
                campaign_ids=[r['campaign_id'] for r in group],repeat_count=len(group)))
        a,b=anchors;slope=(b['mean_final_rad']-a['mean_final_rad'])/(b['command_rad']-a['command_rad'])
        if not 0<slope<=2:raise ValueError('Nonmonotonic or extreme local hypothesis')
        models.append(dict(direction=direction,anchors=anchors,slope=slope,
            intercept_rad=a['mean_final_rad']-slope*a['command_rad'],
            observed_start_range_rad=[min(r['start_joints_rad'][0] for r in selected),max(r['start_joints_rad'][0] for r in selected)],
            capture_profiles=sorted({r['capture_profile'] for r in selected})))
    return dict(schema='rocell.base_local_line_hypotheses.v1',dataset_sha256=hashlib.sha256(canonical(dataset)).hexdigest(),
        models=models,context=rows[0]['context'],other_joint_reference_rad=rows[0]['start_joints_rad'],
        validation_unit='UNSEEN_TARGET_GROUP',held_out_target_count=0,validated=False,
        compensation_enabled=False,motion_authorized=False)


def predict_unseen_base_target(model, *, target_rad, start_joints_rad):
    """Freeze an interpolation prediction, not an inverse or dispatch permit."""
    if (type(start_joints_rad) is not list or len(start_joints_rad)!=6
            or any(type(v) not in (float,int) or not math.isfinite(v) for v in [target_rad,*start_joints_rad])):
        raise ValueError('Finite target and six-joint start required')
    direction='INCREASING' if target_rad>start_joints_rad[0] else 'DECREASING'
    m=next(m for m in model['models'] if m['direction']==direction)
    low,high=[a['command_rad'] for a in m['anchors']]
    if not low<target_rad<high:raise ValueError('Strictly unseen interpolated target required')
    if not m['observed_start_range_rad'][0]<=start_joints_rad[0]<=m['observed_start_range_rad'][1]:
        raise ValueError('Starting angle outside observed model domain')
    if any(abs(start_joints_rad[i]-model['other_joint_reference_rad'][i])>math.radians(.5) for i in range(1,6)):
        raise ValueError('Other-joint pose outside model context')
    predicted=m['slope']*target_rad+m['intercept_rad']
    if (predicted-start_joints_rad[0])*(target_rad-start_joints_rad[0])<=0:
        raise ValueError('Prediction conflicts with approach direction')
    distance=min(abs(a['command_rad']-target_rad) for a in m['anchors'])
    # Midpoint ties are resolved before measurement, toward the lower command.
    nearest=min((a for a in m['anchors'] if abs(abs(a['command_rad']-target_rad)-distance)<=1e-12),
        key=lambda a:a['command_rad'])
    return dict(schema='rocell.base_held_out_prediction.v1',model_sha256=hashlib.sha256(canonical(model)).hexdigest(),
        direction=direction,target_rad=target_rad,start_joints_rad=start_joints_rad,
        predicted_final_rad=predicted,nearest_anchor_final_rad=nearest['mean_final_rad'],
        nearest_anchor_command_rad=nearest['command_rad'],nearest_anchor_tie_rule='LOWER_COMMAND_WITHIN_1E-12_RAD',
        prediction_tolerance_deg=.25,
        validation_completed=False,compensation_applied=False,motion_authorized=False)
