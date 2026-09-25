"""Local per-joint/direction compensation experiments, simulation only.

One independently named trial counts once, not once per telemetry frame.
Never pool different joints, targets, speeds, payload contexts or directions.
These inputs are not authenticated native captures and cannot admit motion.
"""
import math
from statistics import mean
from rocell.arm.joint_endpoint_verification import JOINT_KEYS, verify_reported_joint


def _number(value):
    return type(value) in (int,float) and math.isfinite(value)


def fit_synthetic_joint_bias(trials):
    """Fit on training trials; evaluate unchanged coefficients on held-out trials.

    Trial fields: id, split, joint, start_rad[6], target_rad, command_rad,
    rows[(read_start_ns,read_end_ns,joints[6])], context, spd, acc.
    Context is an exact fixture label, not a physical clearance assertion.
    """
    if type(trials) is not list or not 10<=len(trials)<=128:
        raise ValueError('Ten through 128 bounded synthetic trials required')
    fields={'id','split','joint','start_rad','target_rad','command_rad','rows','context','spd','acc'}
    groups={}; seen=set()
    for trial in trials:
        if type(trial) is not dict or set(trial)!=fields:
            raise ValueError('Exact synthetic trial fields required')
        identity=trial['id']
        if type(identity) is not str or not 1<=len(identity)<=128 or identity in seen:
            raise ValueError('Distinct bounded trial identifiers required')
        seen.add(identity)
        joint=trial['joint']; target=trial['target_rad']; start=trial['start_rad']
        if (joint not in JOINT_KEYS or trial['split'] not in ('train','validation')
                or not _number(target) or abs(target)>2*math.pi
                or not _number(trial['command_rad']) or trial['command_rad']!=target
                or type(start) not in (list,tuple) or len(start)!=6
                or any(not _number(v) or abs(v)>2*math.pi for v in start)
                or type(trial['context']) is not str or not 1<=len(trial['context'])<=128
                or type(trial['spd']) is not int or trial['spd']!=20
                or type(trial['acc']) is not int or trial['acc']!=1):
            raise ValueError('Matched uncorrected command and finite context required')
        index=JOINT_KEYS.index(joint);delta=target-start[index]
        if not math.radians(.5)<abs(delta)<=math.radians(2):
            raise ValueError('Initial synthetic move must be within two degrees')
        rows=trial['rows']
        if type(rows) is not list or not 20<=len(rows)<=512:
            raise ValueError('Bounded five-second synthetic rows required')
        endpoint=verify_reported_joint(rows,joint=joint,start=start,target=target)
        if endpoint['status'] not in ('REPORTED_SETTLED','TARGET_MISSED'):
            raise ValueError('Invalid, drifting, absent or excursion response')
        if not 4_800_000_000<=rows[-1][0]-rows[0][1]<=5_250_000_000:
            raise ValueError('Complete synthetic observation required')
        if any(b[0]-a[1]>100_000_000 for a,b in zip(rows,rows[1:])):
            raise ValueError('Synthetic read gap')
        tail=[r for r in rows if rows[-1][0]-r[1]<=400_000_000]
        if (tail[-1][0]-tail[0][1]<200_000_000
                or max(r[2][index] for r in tail)-min(r[2][index] for r in tail)>math.radians(.1)):
            raise ValueError('Unsettled final response cannot train a bias')
        direction='INCREASING' if delta>0 else 'DECREASING'
        key=(joint,direction,target,trial['context'])
        group=groups.setdefault(key,[])
        if group and any(abs(start[i]-group[0]['start'][i])>math.radians(.5) for i in range(6) if i!=index):
            raise ValueError('Other-joint pose context differs')
        group.append(dict(id=identity,split=trial['split'],start=list(start),
            error_rad=endpoint['final_error_rad']))
    models=[]
    for (joint,direction,target,context),group in sorted(groups.items()):
        train=[r for r in group if r['split']=='train']
        validation=[r for r in group if r['split']=='validation']
        if len(train)<3 or len(validation)<2:
            raise ValueError('Each joint/direction needs three training and two validation trials')
        index=JOINT_KEYS.index(joint)
        bias=mean(r['error_rad'] for r in train)
        residuals=[r['error_rad']-bias for r in validation]
        original_mae=mean(abs(r['error_rad']) for r in validation)
        corrected_mae=mean(abs(e) for e in residuals)
        starts=[r['start'][index] for r in train]
        if any(not min(starts)-math.radians(.5)<=r['start'][index]<=max(starts)+math.radians(.5) for r in validation):
            raise ValueError('Validation approach outside training neighborhood')
        eligible=(abs(bias)<=math.radians(1) and max(abs(e) for e in residuals)<=math.radians(.25)
                  and corrected_mae<original_mae)
        proposed=target-bias
        # The inverse prediction must not reverse approach or create a larger
        # than three-degree synthetic experiment (two-degree nominal + one bias).
        eligible=eligible and abs(proposed)<=2*math.pi and all(
            math.radians(.5)<abs(proposed-r['start'][index])<=math.radians(3)
            and (proposed-r['start'][index])*(target-r['start'][index])>0 for r in group)
        models.append(dict(joint=joint,direction=direction,target_rad=target,context=context,
            bias_rad=bias,proposed_command_rad=target-bias,
            train_ids=[r['id'] for r in train],validation_ids=[r['id'] for r in validation],
            uncorrected_validation_mae_rad=original_mae,prediction_mae_rad=corrected_mae,
            maximum_prediction_error_rad=max(abs(e) for e in residuals),
            offline_prediction_screen_passed=eligible))
    return dict(schema='rocell.synthetic_local_joint_bias_models.v1',models=models,
        basis='SYNTHETIC_ONLY',motion_authorized=False,compensation_enabled=False,
        physical_accuracy_verified=False,
        limitation='Local bias prediction only; adjusted commands require separate held-out response tests.')
