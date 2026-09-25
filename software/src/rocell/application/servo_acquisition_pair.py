"""Validate separately timed reference goal/feedback reads, without native I/O.

This is a producer-contract building block, not an endpoint verdict or proof of
installed compatibility. The caller retains command/dispatch and raw envelope.
"""
from .servo_diagnostic_contract import _identifier,_integer
from .servo_register_reference import PROFILE_ID,decode_register,decode_feedback_block


def assess_acquisition_pair(pair,*,boot_id,command_id,servo_id,dispatch_us,
                            previous_sequence,previous_finished_us,maximum_pair_us):
    _identifier(boot_id);_identifier(command_id);_integer(servo_id,1,253)
    _integer(dispatch_us);_integer(previous_sequence,-1);_integer(previous_finished_us)
    _integer(maximum_pair_us,1)
    if type(pair) is not dict or set(pair)!={'schema','profile_id','byte_order','target','feedback'}:
        raise ValueError('Exact acquisition-pair fields required')
    if pair['schema']!='rocell.servo_acquisition_pair.v1' or pair['profile_id']!=PROFILE_ID:
        raise ValueError('Reviewed reference profile required')
    order=pair['byte_order']
    if order not in ('little','big'):raise ValueError('Explicit byte order required')
    decoded={};intervals=[]
    for name,address,width in (('target',42,2),('feedback',56,15)):
        record=pair[name]
        expected={'boot_id','command_id','servo_id','sequence','read_started_us',
                  'read_finished_us','address','width','status','device_error','raw_hex'}
        if type(record) is not dict or set(record)!=expected:
            raise ValueError('Exact acquisition record required')
        _integer(record['servo_id'],1,253)
        _integer(record['address'],0,255);_integer(record['width'],1,255)
        if (record['boot_id']!=boot_id or record['command_id']!=command_id
                or record['servo_id']!=servo_id or record['address']!=address
                or record['width']!=width):
            raise ValueError('Acquisition identity or register mismatch')
        sequence=_integer(record['sequence'])
        begin=_integer(record['read_started_us']);end=_integer(record['read_finished_us'])
        # Sequence establishes acquisition order; adjacent integer-microsecond
        # boundaries may be equal. The command boundary remains strictly earlier.
        if begin<=dispatch_us or begin<previous_finished_us or end<begin or sequence<=previous_sequence:
            raise ValueError('Acquisition predates command or prior sample')
        status=record['status'];raw=None;error=record['device_error']
        if status not in ('SUCCEEDED','FAILED','UNSUPPORTED'):
            raise ValueError('Explicit read status required')
        if error is not None:_integer(error,0,255)
        if status=='SUCCEEDED':
            if error!=0 or type(error) is not int:raise ValueError('Successful read requires zero device error')
            encoded=record['raw_hex']
            if type(encoded) is not str or len(encoded)!=width*2:
                raise ValueError('Exact raw-byte width required')
            try:raw=bytes.fromhex(encoded)
            except ValueError:raise ValueError('Invalid raw bytes') from None
            if len(raw)!=width:raise ValueError('Incomplete raw bytes')
        elif record['raw_hex'] is not None:
            raise ValueError('Failed read must not supply cached bytes')
        if name=='target':
            decoded[name]=decode_register('goal_position',int.from_bytes(raw,order) if raw is not None else None,read_status=status)
        else:decoded[name]=decode_feedback_block(raw,read_status=status,byte_order=order)
        intervals.append((begin,end,sequence,name))
    intervals.sort()
    first,last=intervals
    if last[0]<first[1] or last[2]<=first[2]:
        raise ValueError('Single-owner reads must be ordered and nonoverlapping')
    duration=last[1]-first[0]
    if duration>maximum_pair_us:raise ValueError('Target/position correlation window exceeded')
    complete=pair['target']['status']==pair['feedback']['status']=='SUCCEEDED'
    return dict(schema='rocell.servo_acquisition_pair_assessment.v1',
        status='REFERENCE_READ_PAIR_COMPLETE' if complete else 'READ_PAIR_INCOMPLETE',
        decoded=decoded,read_order=[entry[3] for entry in intervals],
        pair_span_us=duration,last_sequence=last[2],last_finished_us=last[1],
        simultaneous=False,installed_compatibility_verified=False,
        provenance_verified=False,progression_authority=False)
