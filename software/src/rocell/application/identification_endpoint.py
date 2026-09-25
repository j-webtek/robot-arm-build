"""Reconstruct a settled desired endpoint from an already verified export."""
import math
from .controller_route_preview import _baseline
from .wrist_tip_review import modeled_tip
from rocell.safety.wifi_all_joint_reservation import verify_sample


def verified_identification_endpoint(report,model):
    tx=report['transaction'];rows=tx.get('rows',[])
    if (tx.get('state')!='REPORTED_SETTLED_PENDING_EXPORT' or not rows
            or report.get('acknowledgment_received') is not True):
        raise ValueError('Retained completed identification required')
    desired=tx['desired_joints_rad'];desired_tip=modeled_tip(model,desired)
    previous=tx['dispatch_s'];validated=[]
    for row in rows:
        raw=row['raw_feedback'];verify_sample(raw)
        _,q,consistent=_baseline(raw)
        now=row['observed_s']
        if (not consistent or q!=row['reported_joints_rad']
                or now!=raw['response_finished_monotonic_s']
                or not previous<now<=tx['dispatch_s']+10):
            raise ValueError('Consistent ordered observed endpoint required')
        validated.append((now,q));previous=now
    final=validated[-1][1];begin=validated[-1][0];last=begin
    for now,q in reversed(validated):
        if (last-now>1 or math.dist(modeled_tip(model,q),desired_tip)>.5
                or max(abs(a-b) for a,b in zip(q,desired))>.004
                or max(abs(a-b) for a,b in zip(q,final))>2*math.pi/4096+1e-8):break
        begin=now;last=now
    if validated[-1][0]-begin<2:
        raise ValueError('Two-second independently reconstructed endpoint tail required')
    return dict(joints_rad=list(final),stable_tail_s=validated[-1][0]-begin,
        modeled_desired_tip_error_mm=math.dist(modeled_tip(model,final),desired_tip),
        physical_accuracy_verified=False)
