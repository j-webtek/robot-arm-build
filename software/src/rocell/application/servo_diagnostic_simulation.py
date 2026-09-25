"""Deterministic hypothetical traces; never imports a hardware adapter.

Counts/mapping are synthetic. Scenarios exercise evidence interpretation, not
the physical dynamics or configuration of the installed RoArm.
"""
import hashlib
from .first_motion_contract import canonical

SCENARIOS=('arrival','bus_failure','wrong_target','failed_read','no_readback',
           'stationary','delayed_arrival','reboot','stale_sequence',
           'paired_arrival','paired_negative_position','paired_stale_read','paired_failed_read')


def simulate_write_evidence(scenario):
    """Explicit synthetic ACK fixture, never inferred for real device data."""
    dispatch = simulate_trace(scenario)['dispatch']
    return dict(schema='rocell.servo_write_evidence.v1',
        **{key: dispatch[key] for key in
           ('boot_id','command_id','servo_id','device_us','bus_write_status')},
        library_return=0 if scenario=='bus_failure' else 1,
        device_error=-1 if scenario=='bus_failure' else 0, ack_policy='ENABLED')


def simulate_trace(scenario):
    if scenario not in SCENARIOS:raise ValueError('Named simulation scenario required')
    if scenario.startswith('paired_'):return _paired_trace(scenario)
    payload=dict(T=101,joint=3,rad=1.7,spd=20,acc=1)
    command=dict(boot_id='simulation-boot',command_id='simulation-command',servo_id=3,joint=3,
        conversion_version='synthetic-not-installed',angle_units='rad',position_units='count',
        desired_rad=1.7,wire_rad=1.7,desired_count=2100,wire_count=2100,
        payload=payload,payload_sha256=hashlib.sha256(canonical(payload)).hexdigest())
    dispatch=dict(boot_id=command['boot_id'],command_id=command['command_id'],servo_id=3,
        wire_count=2100,speed=20,acceleration=1,device_us=1000,
        bus_write_status='FAILED' if scenario=='bus_failure' else 'SUCCEEDED')
    samples=[]
    for i in range(6):
        position=2120 if scenario=='stationary' or scenario=='delayed_arrival' and i<2 else 2100
        sample=dict(boot_id=command['boot_id'],command_id=command['command_id'],servo_id=3,
            sequence=i,read_started_us=1100+i*1000000,read_finished_us=1200+i*1000000,
            position_read_status='SUCCEEDED',position_count=position,
            target_read_status='SUCCEEDED',target_count=2110 if scenario=='wrong_target' else 2100)
        if scenario=='failed_read':sample.update(position_read_status='FAILED',position_count=None)
        if scenario=='no_readback':sample.update(target_read_status='UNSUPPORTED',target_count=None)
        if scenario=='reboot' and i==3:sample['boot_id']='different-boot'
        if scenario=='stale_sequence' and i==3:sample['sequence']=0
        samples.append(sample)
    return dict(schema='rocell.servo_diagnostic_trace.v1',origin='SIMULATION',
        command=command,dispatch=dispatch,samples=samples,
        policy=dict(tolerance_counts=1,settle_us=2000000,maximum_gap_us=1100000))


def _paired_trace(scenario):
    from .servo_register_reference import PROFILE_ID
    trace=simulate_trace('arrival')
    trace['schema']='rocell.servo_diagnostic_trace.v2'
    trace['policy']['maximum_pair_us']=1000
    pairs=[]
    for i,sample in enumerate(trace['samples']):
        begin=sample['read_started_us']
        def record(address,width,sequence,start,raw):
            return dict(boot_id=sample['boot_id'],command_id=sample['command_id'],servo_id=3,
                sequence=sequence,read_started_us=start,read_finished_us=start+100,
                address=address,width=width,status='SUCCEEDED',device_error=0,raw_hex=raw.hex())
        # Signed-magnitude -1 is a successful measurement, not the API's read-failure sentinel.
        position=0x8001 if scenario=='paired_negative_position' else 2100
        pair=dict(schema='rocell.servo_acquisition_pair.v1',profile_id=PROFILE_ID,byte_order='little',
            target=record(42,2,2*i,begin,(2100).to_bytes(2,'little')),
            feedback=record(56,15,2*i+1,begin+200,position.to_bytes(2,'little')+bytes(13)))
        if scenario=='paired_stale_read' and i==3:pair['feedback']['sequence']=0
        if scenario=='paired_failed_read':
            pair['feedback'].update(status='FAILED',device_error=None,raw_hex=None)
        pairs.append(pair)
    trace['samples']=pairs
    return trace
