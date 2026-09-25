"""Rebuild matched speed comparisons from original portable exports only."""
import math

from .base_compensation_comparison import read_base_experiment_export
from rocell.safety.positional_campaign_authority import (
    BASE_SPEED_SCHEMA, BASE_CORRECTION_SCHEMA, DECREASING_BASE_CORRECTION_SCHEMA,
)


def compare_base_speeds(*, candidate, reference, direction):
    """One speed-10 observation versus one matched speed-20 corrected trial.

    Both use the same raw target. Misses are retained; safety/transport faults
    are rejected by the original-export reader. No model fitting or progression.
    """
    if direction not in ('INCREASING','DECREASING'):
        raise ValueError('Known comparison direction required')
    a=read_base_experiment_export(candidate,expected_schema=BASE_SPEED_SCHEMA)
    b=read_base_experiment_export(reference,expected_schema=(
        DECREASING_BASE_CORRECTION_SCHEMA if direction=='DECREASING' else BASE_CORRECTION_SCHEMA))
    if (a['campaign_id']==b['campaign_id'] or a['report_sha256']==b['report_sha256']
            or a['speed']!=10 or b['speed']!=20 or a['acceleration']!=1 or b['acceleration']!=1
            or any(a[k]!=b[k] for k in ('context','model_sha256','command_rad','desired_rad'))
            or a['direction']!=direction or b['direction']!=direction
            or any(abs(x-y)>math.radians(.01) for x,y in zip(a['start_joints_rad'],b['start_joints_rad']))):
        raise ValueError('Distinct, same-route and same-context speed observations required')
    return dict(schema='rocell.base_speed_pair.v1',direction=direction,candidate=a,reference=b,
        absolute_error_reduction_rad=abs(b['error_rad'])-abs(a['error_rad']),
        candidate_improved_reported_endpoint=abs(a['error_rad'])<abs(b['error_rad']),
        physical_accuracy_verified=False,physical_speed_verified=False,
        speed_specific_model_validated=False,motion_authorized=False)
