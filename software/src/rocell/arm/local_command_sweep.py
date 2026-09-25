"""Offline local command sweep design; no sender, reservation or motion authority.

Small command spacing is not small physical travel. Every proposed probe starts
from a separately verified high position under the existing transaction policy.
"""
import math
from .discrete_transaction import DiscreteTransaction

COMMANDS_DEG=(.85,.95,1.05,1.05,.95,.85)
DESIRED_DEG=1.25


def preflight(baseline):
    """Check all probes against an explicit hypothetical six-joint baseline.

    A successful result only describes the pure transaction constructor; the
    native sweep actions still require their own fresh baseline and reservation.
    """
    if (type(baseline) not in (list,tuple) or len(baseline)!=6 or
            any(type(v) not in (int,float) or not math.isfinite(v) for v in baseline)):
        raise ValueError('Finite six-joint baseline required')
    rows=[]
    for i,command in enumerate(COMMANDS_DEG):
        target=math.radians(command)
        descending=target<baseline[4]
        try:
            tx=DiscreteTransaction(baseline=baseline,baseline_finished_ns=1,
                target=target,desired_endpoint=math.radians(DESIRED_DEG),
                completion_budget_ns=10_000_000_000)
            compatible=True
            wire=tx.snapshot()['command']
        except ValueError:
            compatible=False;wire=None
        rows.append(dict(index=i,command_deg=command,
            command_delta_from_baseline_deg=command-math.degrees(baseline[4]),
            descending=descending,transaction_policy_compatible=compatible,
            proposed_wire_command=wire))
    return dict(schema='rocell.local_command_sweep_preflight.v1',
        desired_deg=DESIRED_DEG,probes=rows,
        all_compatible=all(r['descending'] and r['transaction_policy_compatible'] for r in rows),
        native_sweep_action_available=True,hardware_access=False,motion_authorized=False,
        fresh_hardware_baseline_verified=False)


def summarize_response(records):
    """Descriptive sweep summary, retaining failures instead of fitting offsets.

    Records must come from independently replayed endpoint/hold evidence. This
    pure helper does not establish that provenance itself. Missing or repeated
    trials cannot qualify a sweep. Joint feedback is not tip metrology.
    """
    if len(records)>len(COMMANDS_DEG):raise ValueError('At most six probe records')
    ids=[r['export_id'] for r in records]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate evidence')
    failed=[];groups={c:[] for c in sorted(set(COMMANDS_DEG))}
    for i,r in enumerate(records):
        if r['command_deg']!=COMMANDS_DEG[i]:raise ValueError('Probe order mismatch')
        if r.get('endpoint_and_hold_verified') is not True:
            failed.append(i);continue
        value=r['hold_final_deg']
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError('Finite reported endpoint required')
        groups[r['command_deg']].append(value)
    complete=len(records)==6 and not failed
    summaries=[dict(command_deg=c,count=len(v),
        observed_min_deg=min(v) if v else None,observed_max_deg=max(v) if v else None,
        observed_span_deg=max(v)-min(v) if v else None) for c,v in groups.items()]
    comparisons=[]
    if complete:
        for left,right in zip(summaries,summaries[1:]):
            comparisons.append(dict(lower_command_deg=left['command_deg'],
                upper_command_deg=right['command_deg'],
                observed_endpoint_ranges_overlap=(max(left['observed_min_deg'],right['observed_min_deg'])
                    <=min(left['observed_max_deg'],right['observed_max_deg']))))
    return dict(complete=complete,failed_probe_indices=failed,groups=summaries,
        adjacent_comparisons=comparisons,model_fitted=False,
        physical_accuracy_verified=False,motion_authorized=False,
        note='Observed ranges are not confidence intervals; overlap does not prove deadband or quantization.')
