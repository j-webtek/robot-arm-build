"""Compare command-space hypotheses using explicitly synthetic response models.

No live imports, requests, firmware settings or admissions. Degrees throughout.
These models are stress cases, not fitted explanations of the physical arm.
"""
import math

STRATEGIES=('toward_desired_setpoint','previous_setpoint_plus_error')
MODELS=('fixed_offset','quantized_offset','deadband','changing_offset')


def run(strategy, model):
    if strategy not in STRATEGIES or model not in MODELS:
        raise ValueError('Enumerated strategy and synthetic model required')
    # Seed matches one observed pair, but its subsequent behavior is hypothetical.
    command=.95
    reported=1.40625
    desired=1.25
    offset=reported-command
    rows=[]
    total=0.
    reason='ATTEMPT_LIMIT'
    for index in range(3):
        error=desired-reported
        if abs(error)<=.05:
            reason='IN_BAND';break
        proposed=desired if strategy=='toward_desired_setpoint' else command+error
        delta=max(-.10,min(.10,proposed-command))
        if abs(delta)<1e-12:
            reason='NO_COMMAND_CHANGE';break
        if total+abs(delta)>.30+1e-12 or abs(command+delta)>3:
            reason='COMMAND_LIMIT';break
        previous_command=command
        previous_reported=reported
        command+=delta
        total+=abs(delta)
        predicted=command+offset
        if model=='quantized_offset':
            predicted=round(predicted/(360/4096))*(360/4096)
        elif model=='deadband' and abs(command-previous_command)<.11:
            predicted=previous_reported
        elif model=='changing_offset':
            predicted+=(-.18 if index%2==0 else .18)
        reported=predicted
        rows.append(dict(index=index,previous_command_deg=previous_command,
                         previous_reported_deg=previous_reported,
                         command_deg=command,command_delta_deg=delta,
                         synthetic_reported_deg=reported,error_deg=reported-desired))
        if abs(reported-previous_reported)>.25 or abs(reported)>3:
            reason='EXCURSION';break
        if abs(reported-desired)<=.05:
            reason='IN_BAND';break
        if (desired-previous_reported)*(desired-reported)<0:
            reason='OVERSHOOT';break
        if abs(reported-desired)>=abs(previous_reported-desired)-.01:
            reason='NO_USEFUL_PROGRESS';break
    return dict(strategy=strategy,model=model,reason=reason,attempts=rows,
                cumulative_command_change_deg=total,final_error_deg=reported-desired,
                simulation_only=True,model_fitted=False,motion_authorized=False,
                physical_response_predicted=False)


def compare():
    return [run(strategy,model) for model in MODELS for strategy in STRATEGIES]
