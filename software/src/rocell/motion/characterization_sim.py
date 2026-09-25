"""Deterministic campaign sequencing rehearsal; never opens a transport.

Linear endpoint interpolation is synthetic, not a prediction of RoArm dynamics
or IK. Speed coefficients are recorded but intentionally do not set travel time.
This first simulator exercises finite sequencing and fail-closed advancement;
link/cable clearance and observed settling require separate evidence.
"""

from .characterization_plan import AXES, FrozenCampaign, _number
from .characterization_wire_sim import analyze_synthetic_trial

FAULTS = frozenset({"NONE", "NO_RESPONSE", "STALE", "DISCONNECT", "CANCELLED",
                    "OVERSHOOT", "DRIFT", "DROPOUT", "MALFORMED"})


def simulate_campaign(plan: FrozenCampaign, *, travel_s: float, sample_period_s: float,
                      faults: dict | None = None, blocked_trial_ids: tuple = ()) -> dict:
    """Run an explicitly parameterized model, stopping at its first failed trial.

    Each synthetic sample has a model timestamp, not a host or device timestamp.
    Limits bound both numerical work and returned data before generation begins.
    Unknown fault IDs are errors rather than silently unused test inputs.
    """
    if type(plan) is not FrozenCampaign:
        raise ValueError("Expected a validated frozen campaign")
    travel = _number(travel_s, "travel_s", positive=True)
    period = _number(sample_period_s, "sample_period_s", positive=True)
    data = plan.to_dict()
    if faults is None:
        faults = {}
    if type(faults) is not dict:
        raise ValueError("Expected a bounded trial fault mapping")
    ids = {t['trial_id'] for t in data['trials']}
    if type(blocked_trial_ids) is not tuple or any(type(v) is not str or v not in ids for v in blocked_trial_ids):
        raise ValueError("Invalid nominal geometry blocker IDs")
    if any(key not in ids or type(value) is not str or value not in FAULTS for key,value in faults.items()):
        raise ValueError("Unknown trial or fault")
    # Include both t=0 and the exact terminal time; all rows across the campaign
    # remain bounded even if a caller supplies a tiny sample period.
    total_timeout = sum(t['timeout_s'] for t in data['trials'])
    if period < total_timeout/10000:
        raise ValueError("Synthetic sample budget exceeds 10000")
    counts = [int(t['timeout_s']/period)+2 for t in data['trials']]
    if sum(counts) > 10000:
        raise ValueError("Synthetic sample budget exceeds 10000")
    results, stop_index = [], None
    for index, trial in enumerate(data['trials']):
        if trial['trial_id'] in blocked_trial_ids:
            results.append({'trial_id':trial['trial_id'],'status':'NOMINAL_GEOMETRY_BLOCKED',
                            'fault':'NONE','spd_coefficient':trial['spd'],'samples':[],
                            'wire_evidence':None,'observed_settling_verified':False})
            stop_index=index
            break
        fault = faults.get(trial['trial_id'], 'NONE')
        rows = []
        required = travel + trial['dwell_s']
        terminal = min(required, trial['timeout_s'])
        if fault in {'CANCELLED', 'DISCONNECT'}:
            terminal = 0.0
            status = fault
        elif fault in {'NO_RESPONSE', 'STALE'}:
            terminal = trial['timeout_s']
            status = 'TIMEOUT'
        elif period > trial['stop']['max_read_gap_s']:
            terminal = min(period, trial['timeout_s'])
            status = 'GAP_POLICY_FAILED'
        elif required > trial['timeout_s']:
            status = 'TIMEOUT'
        else:
            status = 'MODEL_COMPLETED'
        # Integer indexing avoids cumulative floating-point drift. Always emit
        # the exact terminal sample once, but never manufacture a device reply.
        times = [n*period for n in range(int(terminal/period)+1) if n*period < terminal]
        times.append(terminal)
        if fault not in {'NO_RESPONSE', 'DISCONNECT', 'CANCELLED'}:
            for elapsed in times:
                fraction = 0.0 if fault == 'STALE' else min(elapsed/travel, 1.0)
                if fault == 'OVERSHOOT' and travel <= elapsed < travel+2*period:
                    fraction = 1.2
                if fault == 'DRIFT' and elapsed >= travel:
                    fraction = 1.0 + .5*(elapsed-travel)/trial['dwell_s']
                pose = {a: trial['start'][a] + fraction*(trial['target'][a]-trial['start'][a]) for a in AXES}
                rows.append({'model_elapsed_s':elapsed, 'pose':pose})
        if fault == 'DROPOUT' and rows:
            middle = len(rows)//2
            rows = rows[:middle] + rows[middle+3:]
        try:
            evidence = analyze_synthetic_trial(plan, trial['trial_id'], rows,
                malformed_index=len(rows)//2 if fault == 'MALFORMED' and rows else None)
        except ValueError:
            # No truncated "success": the entire trial must fit the bounded
            # capture/analysis model before any subsequent trial is rehearsed.
            evidence = None
            status = 'SYNTHETIC_CAPTURE_LIMIT'
        if status == 'MODEL_COMPLETED' and evidence['analysis']['status'] != 'OBSERVED_SETTLING':
            status = 'MODEL_ANALYSIS_FAILED'
        results.append({'trial_id':trial['trial_id'], 'status':status, 'fault':fault,
                        'spd_coefficient':trial['spd'], 'samples':rows,
                        'wire_evidence':evidence,
                        'observed_settling_verified':False})
        if status != 'MODEL_COMPLETED':
            stop_index = index
            break
    return {
        'schema':'rocell.characterization_simulation.v1', 'basis':'SYNTHETIC_LINEAR_ENDPOINT_MODEL',
        'plan_sha256':plan.sha256, 'travel_s':travel, 'sample_period_s':period,
        'speed_controls_model_duration':False, 'trial_results':results,
        'skipped_trial_ids':[t['trial_id'] for t in data['trials'][stop_index+1:]] if stop_index is not None else [],
        'status':'MODEL_COMPLETED' if stop_index is None else 'STOPPED',
        'checks':{'planning_envelope':'VALIDATED_BY_PLAN', 'ik':'UNKNOWN',
                  'full_link_collision':'UNKNOWN', 'cable_clearance':'UNKNOWN',
                  'physical_dynamics':'UNKNOWN'},
        'device_opens':0, 'command_writes':0, 'motion_authorized':False, 'physical_ready':False,
    }
