"""Compare nearby traces without conflating changed posture with repeatability."""
import math
from .coordinated_trace_review import review_coordinated_trace


def compare_coordinated_residuals(reports):
    if len(reports)!=2:raise ValueError('Exactly two bounded comparison traces required')
    reviews=[review_coordinated_trace(r) for r in reports]
    txs=[r['run']['transaction'] for r in reports]
    if any(t['command'].get('T')!=104 for t in txs):
        raise ValueError('Coordinated commands required')
    same_start=all(abs(a-b)<=1e-8 for a,b in zip(txs[0]['baseline_joints'],txs[1]['baseline_joints']))
    rows=[]
    for i,name in enumerate(('base','shoulder','elbow','wrist_pitch','wrist_roll','gripper')):
        residuals=[t['rows'][-1][3][i]-t['expected_joints'][i] for t in txs]
        rows.append(dict(joint=name,wire_residuals_rad=residuals,
            residual_change_rad=residuals[1]-residuals[0],
            residual_change_deg=math.degrees(residuals[1]-residuals[0]),
            requested_deltas_deg=[r['joints'][i]['requested_delta_deg'] for r in reviews],
            reported_deltas_deg=[r['joints'][i]['reported_delta_deg'] for r in reviews]))
    return dict(schema='rocell.coordinated_residual_comparison.v1',
        status='DESCRIPTIVE_COMPARISON_ONLY',same_start=same_start,
        same_command=txs[0]['command']==txs[1]['command'],joints=rows,
        source_outcomes=[dict(status=r['status'],runner_error=r['run'].get('error'),
            feedback_failures=review['feedback_failures'],
            desired_endpoint_result=t.get('desired_endpoint_result')) for r,review,t in zip(reports,reviews,txs)],
        repeatability_established=False,correction_qualified=False,motion_authorized=False,
        physical_accuracy_verified=False,
        limitation='Two changed operating points cannot identify posture, delta, load or timing effects independently.')
