"""Reconstruct original response bodies before offline micro endpoint evaluation."""
from rocell.arm.micro_endpoint import verify_micro_endpoint
from rocell.providers.windows.arm_wifi_observation import review_observation

JOINTS=('b','s','e','t','r','g')


def review_micro_feedback(samples, *, baseline, dispatch_ns, receipt_ns, evaluated_ns,
                          cancelled=False):
    """Any failed sample invalidates arrival; corrupted originals raise.

    Baseline and dispatch/receipt bounds must be supplied by a future bound
    transaction, not guessed from response bodies or receipt contents.
    """
    successful=[s for s in samples if s.get('status')=='SUCCEEDED']
    if successful:
        review_observation(dict(schema='rocell.arm_wifi_observation.v4',samples=successful))
    rows=[[round(s['request_started_monotonic_s']*1e9),round(s['response_finished_monotonic_s']*1e9),
           [s['joints_rad'][j] for j in JOINTS]] for s in successful]
    return verify_micro_endpoint(rows,baseline=baseline,dispatch_ns=dispatch_ns,
        receipt_ns=receipt_ns,evaluated_ns=evaluated_ns,
        transport_clean=len(successful)==len(samples),cancelled=cancelled)
