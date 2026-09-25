"""Presentation of validated evidence; never infer missing stages from arrival.

Use only the final acquisition for endpoint comparisons. An earlier successful
read must not mask a failed final read. Raw health values have no calibrated units.
"""
from .servo_diagnostic_decode import decode_trace
from .servo_register_reference import decode_feedback_block,decode_register


def summarize_trace(raw):
    try:
        decoded=decode_trace(raw)
    except ValueError:
        return None
    trace=decoded['trace'];command=trace['command'];samples=trace['samples']
    position=None;target=None;position_status='UNAVAILABLE';target_status='UNAVAILABLE'
    health={}
    if samples:
        last=samples[-1]
        if trace['schema']=='rocell.servo_diagnostic_trace.v2':
            feedback=last['feedback'];goal=last['target'];order=last['byte_order']
            fields=decode_feedback_block(bytes.fromhex(feedback['raw_hex'])
                if feedback['status']=='SUCCEEDED' else None,
                read_status=feedback['status'],byte_order=order)
            position_status=feedback['status'];position=fields['position']['decoded_value']
            target_status=goal['status']
            target=decode_register('goal_position',int.from_bytes(bytes.fromhex(goal['raw_hex']),order)
                if target_status=='SUCCEEDED' else None,read_status=target_status)['raw_unsigned']
            health={name:dict(status=value['read_status'],raw_unsigned=value['raw_unsigned'],
                decoded_value=value['decoded_value'],units='RAW_REFERENCE')
                for name,value in fields.items() if name!='position'}
        else:
            position_status=last['position_read_status'];position=last['position_count']
            target_status=last['target_read_status'];target=last['target_count']
    return dict(schema='rocell.servo_diagnostic_summary.v1',origin=trace['origin'],
        source_sha256=decoded['raw_sha256'],desired_count=command['desired_count'],
        wire_count=command['wire_count'],final_target_count=target,final_position_count=position,
        position_minus_desired=position-command['desired_count'] if position is not None else None,
        position_minus_wire=position-command['wire_count'] if position is not None else None,
        position_minus_readback=position-target if position is not None and target is not None else None,
        stages=dict(controller_receipt='UNAVAILABLE',bus_dispatch=trace['dispatch']['bus_write_status'],
            target_readback=target_status,position_acquisition=position_status,
            endpoint=decoded['assessment']['category']),
        raw_health=health,torque_enable='UNAVAILABLE',operating_mode='UNAVAILABLE',
        progression_authority=False,physical_accuracy_verified=False)
