"""Offline reference-profile traces with independently timed register reads.

Projection reuses endpoint rules, not acquisition timestamps: original pairs and
their raw bytes remain in the decoded trace/export. Neither profile selection nor
a passing synthetic endpoint proves installed firmware compatibility.
"""
from .servo_acquisition_pair import assess_acquisition_pair
from .servo_diagnostic_contract import _assess_trace, _integer


def assess_trace_v2(trace):
    command=trace['command'];dispatch=trace['dispatch'];policy=trace['policy']
    maximum=_integer(policy['maximum_pair_us'],1)
    previous=dispatch['device_us'];sequence=-1;projected=[]
    for pair in trace['samples']:
        result=assess_acquisition_pair(pair,boot_id=command['boot_id'],
            command_id=command['command_id'],servo_id=command['servo_id'],
            dispatch_us=dispatch['device_us'],previous_sequence=sequence,
            previous_finished_us=previous,maximum_pair_us=maximum)
        target=result['decoded']['target'];position=result['decoded']['feedback']['position']
        projected.append(dict(boot_id=command['boot_id'],command_id=command['command_id'],
            servo_id=command['servo_id'],sequence=result['last_sequence'],
            read_started_us=min(pair['target']['read_started_us'],pair['feedback']['read_started_us']),
            read_finished_us=pair['feedback']['read_finished_us'],
            position_read_status=position['read_status'],position_count=position['decoded_value'],
            target_read_status=target['read_status'],target_count=target['raw_unsigned']))
        previous=result['last_finished_us'];sequence=result['last_sequence']
    projected_trace=dict(trace,schema='rocell.servo_diagnostic_trace.v1',samples=projected,
        policy={key:policy[key] for key in ('tolerance_counts','settle_us','maximum_gap_us')})
    result=_assess_trace(projected_trace,signed_positions=True)
    result.update(source_schema=trace['schema'],acquisitions_simultaneous=False,
        installed_compatibility_verified=False)
    return result
