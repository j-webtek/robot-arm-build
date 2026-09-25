"""Offline decision replay, not a plant model, motion permit, or live sender."""
import math

from .discrete_transaction import DiscreteTransaction


def assess_correction(record, *, band_deg=0.05):
    """Evaluate a direct-to-desired correction against the real transaction guard.

    The band is an illustrative analysis parameter, not a changed live tolerance.
    Historical reported endpoints are inputs; a future response is never invented.
    Failed/partial trials cannot become correction candidates through this path.
    """
    if type(band_deg) not in (int, float) or not math.isfinite(band_deg) or band_deg <= 0:
        raise ValueError('Positive finite analysis band required')
    result = dict(simulation_only=True, motion_authorized=False,
                  plant_response_predicted=False, band_deg=band_deg)
    if record.get('full_validation_success') is not True:
        return dict(result, decision='STOP_INCOMPLETE_OR_UNVERIFIED')
    actual = record['final_deg']
    desired = record['desired_endpoint_deg']
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (actual, desired)):
        raise ValueError('Finite reported and desired angles required')
    error = actual-desired
    result['error_deg'] = error
    if abs(error) <= band_deg:
        return dict(result, decision='ACCEPT_REPORTED_ENDPOINT')
    baseline = list(record['baseline_rad'])
    # Validated holds have unchanged other joints. Replace roll with the actual
    # settled reading; the original pre-move roll is not the correction baseline.
    baseline[4] = math.radians(actual)
    try:
        DiscreteTransaction(baseline=baseline, baseline_finished_ns=1,
                            target=math.radians(desired),
                            completion_budget_ns=10_000_000_000)
    except ValueError:
        return dict(result, decision='STOP_DIRECT_CORRECTION_OUTSIDE_ENVELOPE')
    return dict(result, decision='DIRECT_CORRECTION_GEOMETRY_ELIGIBLE_ONLY',
                fresh_baseline_required=True, outcome_unknown=True)
