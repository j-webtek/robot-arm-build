"""Reproduce a matched base experiment pair from portable originals only.

No device access or model fitting. Missed but clean controls remain observations;
invalid captures cannot be turned into favorable endpoint comparisons.
"""
import base64
import hashlib
import math

from .first_motion_contract import canonical
from .physical_onboarding_durability import safe_root, contained_path, read_bounded_regular_file
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .positional_campaign_native_export import verify_native_retained_export, LIMITS
from .positional_campaign_capture import validate_campaign_capture
from rocell.providers.windows.positional_campaign_native_protocol import decode_request
from rocell.safety.positional_campaign_authority import (
    BASE_CORRECTION_SCHEMA, BASE_CONTROL_SCHEMA, BASE_EXPERIMENT_SCHEMAS,
    DECREASING_BASE_CORRECTION_SCHEMA, DECREASING_BASE_CONTROL_SCHEMA, PositionalCampaignIntent, BASE_SPEED_SCHEMA,
)
from rocell.arm.campaign_stream_sync import campaign_window


def read_base_experiment_export(selection, *, expected_schema):
    if type(selection) is not dict or set(selection)!={'directory','report_name','report_sha256'}:
        raise ValueError('Exact pinned experiment export required')
    if expected_schema not in (*BASE_EXPERIMENT_SCHEMAS,BASE_SPEED_SCHEMA):
        raise ValueError('Known experiment role required')
    verified=verify_native_retained_export(selection['directory'],selection['report_name'])
    if (not verified['valid'] or not verified['reconstruction_consistent']
            or verified['report_sha256']!=selection['report_sha256']):
        raise ValueError('Changed or unreconstructed experiment export')
    root=safe_root(selection['directory'])
    def read(name,maximum):
        return read_bounded_regular_file(contained_path(root,name,label='base pair original'),maximum_bytes=maximum)
    report_raw=read(selection['report_name'],65536)
    if hashlib.sha256(report_raw).hexdigest()!=selection['report_sha256']:
        raise ValueError('Report changed during comparison')
    report=decode_diagnostic_json(report_raw,maximum=65536)
    def original(name):
        ref=report['originals'][name]
        wrapper=decode_diagnostic_json(read(ref['file'],4*1024*1024),maximum=4*1024*1024)
        raw=base64.b64decode(wrapper['base64'],validate=True)
        if (len(raw)!=ref['bytes'] or len(raw)!=wrapper['bytes'] or len(raw)>LIMITS[name]
                or hashlib.sha256(raw).hexdigest()!=ref['sha256']):
            raise ValueError('Experiment original changed during comparison')
        return raw
    body=decode_request(original('request'))['payload']['campaign_intent']
    if body['schema']!=expected_schema:
        raise ValueError('Experiment role differs; positioning is not pair evidence')
    request=PositionalCampaignIntent(canonical(body))
    trial=decode_diagnostic_json(original('trial'),maximum=LIMITS['trial'])
    leg=trial['legs'][0]
    endpoint=leg['verification']['endpoint']
    if (trial['errors'] or not trial['cleanup']['all_handles_closed']
            or trial['cleanup']['pending_io_count'] or not trial['cleanup']['within_budget']
            or leg['write']['uncertain'] or endpoint['other_joint_changed'] or endpoint['joint_excursion']
            or endpoint['status'] not in ('NO_RESPONSE','TARGET_MISSED','REPORTED_SETTLED')):
        raise ValueError('Faulted or drifting trial cannot support a matched comparison')
    captured={}
    for phase in ('baseline','post'):
        cap=leg[phase]
        raw=validate_campaign_capture(request,cap,phase=phase,
            command_completed_ns=leg['write']['finished_ns'] if phase=='post' else None)
        rows,issues,_=campaign_window(body,phase,raw,cap['read_windows'],cap['started_ns'],cap['finished_ns'],maximum_bytes=98304)
        if issues or len(rows)<20:
            raise ValueError('Clean complete experiment capture required')
        captured[phase]=rows
    before,after=captured['baseline'],captured['post']
    tail=[row for row in after if after[-1][0]-row[1]<=400_000_000]
    if (tail[-1][0]-tail[0][1]<200_000_000
            or max(row[2][0] for row in tail)-min(row[2][0] for row in tail)>math.radians(.1)):
        raise ValueError('Stable final endpoint tail required')
    from .base_reported_timing import summarize_reported_base_timing
    timing=summarize_reported_base_timing(after,start_rad=before[-1][2][0],
        desired_rad=body['legs'][0]['target_rad'],write_finished_ns=leg['write']['finished_ns'])
    proposal=body['base_speed']['proposal'] if body['schema']==BASE_SPEED_SCHEMA else body['base_experiment']
    return dict(campaign_id=body['campaign_id'],report_sha256=selection['report_sha256'],
        experiment_kind=endpoint['correction']['experiment_kind'],
        start_joints_rad=list(before[-1][2]),final_joints_rad=list(after[-1][2]),
        desired_rad=body['legs'][0]['target_rad'],command_rad=body['legs'][0]['command']['rad'],
        error_rad=endpoint['final_error_rad'],status=endpoint['status'],
        experiment_screen_passed=endpoint['correction']['experiment_screen_passed'],
        context=proposal['context_references'],
        model_sha256=proposal['model_sha256'],
        speed=body['legs'][0]['command']['spd'],acceleration=body['legs'][0]['command']['acc'],
        direction=proposal['direction'],
        selected_sample_age_ns=leg['write']['started_ns']-before[-1][1],
        maximum_other_joint_drift_rad=[max(abs(row[2][j]-before[-1][2][j]) for row in after) for j in range(1,6)],
        maximum_base_displacement_rad=max(abs(row[2][0]-before[-1][2][0]) for row in after),
        post_sample_count=len(after),post_duration_ns=leg['post']['finished_ns']-leg['post']['started_ns'],
        reported_timing=timing)


def compare_base_compensation_pair(*, corrected, control, direction='INCREASING'):
    """One predeclared candidate versus one control, never a global validation."""
    if direction not in ('INCREASING','DECREASING'):
        raise ValueError('Known comparison direction required')
    a=read_base_experiment_export(corrected,expected_schema=DECREASING_BASE_CORRECTION_SCHEMA if direction=='DECREASING' else BASE_CORRECTION_SCHEMA)
    b=read_base_experiment_export(control,expected_schema=DECREASING_BASE_CONTROL_SCHEMA if direction=='DECREASING' else BASE_CONTROL_SCHEMA)
    if (a['campaign_id']==b['campaign_id'] or a['report_sha256']==b['report_sha256']
            or a['context']!=b['context'] or a['model_sha256']!=b['model_sha256']
            or a['desired_rad']!=b['desired_rad']
            or any(abs(x-y)>math.radians(.01) for x,y in zip(a['start_joints_rad'],b['start_joints_rad']))):
        raise ValueError('Distinct campaigns with matched six-joint starts and context required')
    corrected_error,control_error=abs(a['error_rad']),abs(b['error_rad'])
    improvement=control_error-corrected_error
    return dict(schema='rocell.base_compensation_pair_comparison.v1',corrected=a,control=b,
        matched_start_tolerance_deg=.01,absolute_error_improvement_deg=math.degrees(improvement),
        relative_error_reduction_percent=100*improvement/control_error if control_error else None,
        local_pair_supports_candidate=bool(a['experiment_screen_passed'] and improvement>0),
        model_retrained=False,pair_count=1,repeated_validation_complete=False,
        physical_accuracy_verified=False,device_sample_freshness_verified=False,motion_authorized=False)


def summarize_base_compensation_repeats(pairs, *, direction='INCREASING'):
    """Reverify finite, distinct matched pairs; summarize without fitting a model.

    A zero reported span is limited by encoder quantization and sample coverage.
    It must not be promoted to zero physical error or proof against order effects.
    """
    from statistics import mean
    if direction not in ('INCREASING','DECREASING'):
        raise ValueError('Known repeat direction required')
    if type(pairs) is not list or not 2<=len(pairs)<=8:
        raise ValueError('Two through eight pinned pair selections required')
    results=[];seen_ids=set();seen_hashes=set()
    for pair in pairs:
        if type(pair) is not dict or set(pair)!={'corrected','control'}:
            raise ValueError('Exact correction/control pair selection required')
        result=compare_base_compensation_pair(**pair,direction=direction)
        for role in ('corrected','control'):
            row=result[role]
            if row['campaign_id'] in seen_ids or row['report_sha256'] in seen_hashes:
                raise ValueError('Repeated campaigns cannot count as independent repeats')
            seen_ids.add(row['campaign_id']);seen_hashes.add(row['report_sha256'])
            if results:
                reference=results[0]['corrected']
                if (row['context']!=reference['context'] or row['model_sha256']!=reference['model_sha256']
                        or row['desired_rad']!=reference['desired_rad']
                        or any(abs(x-y)>math.radians(.01) for x,y in zip(row['start_joints_rad'],reference['start_joints_rad']))):
                    raise ValueError('Repeat context, model, endpoint or starting pose differs')
        results.append(result)
    statistics={}
    for role in ('corrected','control'):
        rows=[r[role] for r in results]
        errors=[abs(r['error_rad']) for r in rows]
        endpoints=[r['final_joints_rad'][0] for r in rows]
        statistics[role]=dict(trial_count=len(rows),
            mean_absolute_error_deg=math.degrees(mean(errors)),
            maximum_absolute_error_deg=math.degrees(max(errors)),
            reported_endpoint_span_deg=math.degrees(max(endpoints)-min(endpoints)))
    return dict(schema='rocell.base_compensation_repeats.v1',pair_count=len(results),
        pairs=results,statistics=statistics,
        all_pairs_support_candidate=all(r['local_pair_supports_candidate'] for r in results),
        model_retrained=False,generalized_compensation_validated=False,
        physical_accuracy_verified=False,device_sample_freshness_verified=False,motion_authorized=False)
