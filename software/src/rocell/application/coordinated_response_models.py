"""Offline chronological holdout comparison; no model is enabled for motion.

Changed posture and movement size are confounded. These small fits are hypotheses,
not a claim that an actuator's physical gain or backlash has been identified.
"""
import math
from .coordinated_trace_review import review_coordinated_trace
from .ghost_first_step import ANCHOR
from rocell.kinematics.firmware_reference import forward,inverse


def compare_response_models(reports):
    if not 3<=len(reports)<=8:
        raise ValueError('Three to eight chronological traces required')
    reviews=[review_coordinated_trace(r) for r in reports]
    txs=[r['run']['transaction'] for r in reports]
    times=[t['dispatch_started_ns'] for t in txs]
    if any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('Distinct chronological dispatches required')
    if any(t['command'].get('T')!=104 or t['command'].get('spd')!=.05 for t in txs):
        raise ValueError('Same coordinated command type and speed required')
    models=[]
    for index,name in ((2,'elbow'),(3,'wrist_pitch')):
        x=[t['expected_joints'][index]-t['baseline_joints'][index] for t in txs]
        y=[t['rows'][-1][3][index]-t['baseline_joints'][index] for t in txs]
        if any(a*x[0]<=0 or b*x[0]<=0 for a,b in zip(x,y)):
            raise ValueError('Same nonzero requested/reported direction required')
        if any((r['joints'][index]['unchanged_tail_s'] or 0)<1 for r in reviews):
            raise ValueError('Settled retained reports required')
        train_x=x[:-1];train_y=y[:-1];n=len(train_x)
        mean_x=sum(train_x)/n;mean_y=sum(train_y)/n
        variance=sum((a-mean_x)**2 for a in train_x)
        if variance<1e-12:raise ValueError('Distinct training movements required')
        gain=sum(a*b for a,b in zip(train_x,train_y))/sum(a*a for a in train_x)
        slope=sum((a-mean_x)*(b-mean_y) for a,b in zip(train_x,train_y))/variance
        candidates=(('ADDITIVE_BIAS',1.,sum(b-a for a,b in zip(train_x,train_y))/n),
                    ('PROPORTIONAL_GAIN',gain,0.),('AFFINE_DELTA',slope,mean_y-slope*mean_x))
        evaluations=[]
        for kind,m,b in candidates:
            predicted=m*x[-1]+b
            evaluations.append(dict(model=kind,slope=m,intercept_rad=b,
                predicted_holdout_delta_rad=predicted,observed_holdout_delta_rad=y[-1],
                holdout_error_deg=math.degrees(predicted-y[-1]),
                positive_gain=m>0,enabled_for_motion=False))
        models.append(dict(joint=name,training_count=n,holdout_index=len(reports)-1,
            requested_deltas_rad=x,reported_deltas_rad=y,evaluations=evaluations,
            lowest_holdout_error_model=min(evaluations,key=lambda r:abs(r['holdout_error_deg']))['model']))
    return dict(schema='rocell.coordinated_response_models.v1',status='OFFLINE_HYPOTHESIS_COMPARISON',
        joints=models,source_outcomes=[dict(status=r['status'],runner_error=r['run'].get('error'),
            feedback_failures=v['feedback_failures']) for r,v in zip(reports,reviews)],
        holdout_used_for_fitting=False,model_selection_uses_holdout=True,
        new_independent_validation_required=True,motion_authorized=False,physical_accuracy_verified=False,
        limitation='Tiny changed-posture sample; model selection on this holdout is exploratory, not independent qualification.')


def screen_hybrid_approach(reports):
    """Sample approach lengths/pitches; no feasible grid point is not a proof
    that every possible path is infeasible. Never extend the training range.
    """
    comparison=compare_response_models(reports)
    e=next(v for v in comparison['joints'][0]['evaluations'] if v['model']=='AFFINE_DELTA')
    w=next(v for v in comparison['joints'][1]['evaluations'] if v['model']=='PROPORTIONAL_GAIN')
    if e['slope']<=0 or w['slope']<=0:raise ValueError('Positive inverse gain required')
    start=reports[-1]['run']['transaction']['rows'][-1][3]
    pose=forward(*start[:4]);distance=math.dist(pose[:3],ANCHOR[:3])
    if not 150<=distance<=220:raise ValueError('Outside reviewed approach neighborhood')
    ranges=[(min(j['requested_deltas_rad'][:-1]),max(j['requested_deltas_rad'][:-1]))
            for j in comparison['joints']]
    feasible=[];counts=dict(elbow_outside_training=0,wrist_outside_training=0,joint_envelope=0,ik_unavailable=0)
    attempted=0
    for length in range(1,11):
        xyz=[a+(b-a)*length/distance for a,b in zip(pose[:3],ANCHOR[:3])]
        for offset in range(-100,101):
            attempted+=1
            try:desired=inverse(*xyz,pose[3]+offset*.0002)
            except ValueError:
                counts['ik_unavailable']+=1;continue
            elbow=(desired[2]-start[2]-e['intercept_rad'])/e['slope']
            wrist=(desired[3]-start[3])/w['slope']
            bad_e=not ranges[0][0]<=elbow<=ranges[0][1]
            bad_w=not ranges[1][0]<=wrist<=ranges[1][1]
            counts['elbow_outside_training']+=int(bad_e)
            counts['wrist_outside_training']+=int(bad_w)
            envelope=max(abs(desired[0]-start[0]),abs(desired[1]-start[1]),abs(elbow),abs(wrist))>math.radians(3)
            counts['joint_envelope']+=int(envelope)
            if not (bad_e or bad_w or envelope):
                feasible.append(dict(translation_mm=length,pitch_change_rad=offset*.0002,
                    desired_joints_rad=list(desired),wire_elbow_delta_rad=elbow,wire_wrist_delta_rad=wrist))
    return dict(schema='rocell.hybrid_approach_screen.v1',
        status='FEASIBLE_GRID_POINTS_REQUIRE_PATH_REVIEW' if feasible else 'NO_IN_RANGE_GRID_POINT',
        sampled_count=attempted,feasible=feasible,rejection_counts=counts,
        starting_joints_rad=start,training_command_ranges_rad=ranges,
        elbow_model=e,wrist_model=w,model_comparison=comparison,
        motion_authorized=False,full_path_screened=False,physical_accuracy_verified=False,
        limitation='Finite grid only; counts overlap. No extrapolation, live command or clearance claim.')
