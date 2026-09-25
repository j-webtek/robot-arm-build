import hashlib
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_diagnostic_contract import assess_trace


@pytest.fixture
def trace():
    payload=dict(T=101,joint=3,rad=1.7,spd=20,acc=1)
    return dict(schema='rocell.servo_diagnostic_trace.v1',origin='SIMULATION',
        command=dict(boot_id='boot1',command_id='move1',servo_id=3,joint=3,
            conversion_version='synthetic-v1',angle_units='rad',position_units='count',
            desired_rad=1.7,wire_rad=1.7,desired_count=2100,wire_count=2100,
            payload=payload,payload_sha256=hashlib.sha256(canonical(payload)).hexdigest()),
        dispatch=dict(boot_id='boot1',command_id='move1',servo_id=3,wire_count=2100,
            speed=20,acceleration=1,device_us=100,bus_write_status='SUCCEEDED'),
        policy=dict(tolerance_counts=1,settle_us=200,maximum_gap_us=150),
        samples=[dict(boot_id='boot1',command_id='move1',servo_id=3,sequence=i,
            read_started_us=110+i*100,read_finished_us=120+i*100,
            position_read_status='SUCCEEDED',position_count=2100,
            target_read_status='SUCCEEDED',target_count=2100) for i in range(3)])


def test_settled_synthetic_trace_grants_no_hardware_authority(trace):
    r=assess_trace(trace)
    assert r['category']=='DIAGNOSTIC_ENDPOINT_CRITERIA_MET'
    assert not r['progression_authority'] and not r['physical_accuracy_verified']
    assert not r['provenance_verified']


def test_successful_write_is_not_accepted_target(trace):
    for s in trace['samples']:s.update(target_read_status='UNSUPPORTED',target_count=None)
    r=assess_trace(trace)
    assert not r['matching_target_readback_observed']
    assert 'TARGET_READBACK_UNAVAILABLE' in r['issues']


def test_fresh_nonarrival_is_not_stale_acquisition(trace):
    for s in trace['samples']:s['position_count']=2120
    r=assess_trace(trace)
    assert r['fresh_position_samples']==3
    assert r['category']=='FRESH_POSITION_NOT_SETTLED_AT_DESIRED_TARGET'


@pytest.mark.parametrize('fault',['boot','command','servo','sequence','time','hash','speed','nan','cached','boolean'])
def test_invalid_contract_rejected(trace,fault):
    s=trace['samples'][-1]
    if fault=='boot':s['boot_id']='reboot'
    if fault=='command':s['command_id']='other'
    if fault=='servo':s['servo_id']=4
    if fault=='sequence':s['sequence']=0
    if fault=='time':s['read_started_us']=100
    if fault=='hash':trace['command']['payload_sha256']='0'*64
    if fault=='speed':trace['dispatch']['speed']=40
    if fault=='nan':trace['command']['desired_rad']=float('nan')
    if fault=='cached':s['position_read_status']='FAILED'
    if fault=='boolean':s['position_count']=True
    with pytest.raises(ValueError):assess_trace(trace)


def test_bus_failure_cannot_pass_on_matching_positions(trace):
    trace['dispatch']['bus_write_status']='FAILED'
    assert assess_trace(trace)['category']=='BUS_DISPATCH_NOT_VERIFIED'


def test_wrong_readback_cannot_pass_on_matching_positions(trace):
    trace['samples'][0]['target_count']=2110
    assert 'TARGET_READBACK_MISMATCH' in assess_trace(trace)['issues']


def test_missing_position_and_gap_block_completion(trace):
    trace['samples'][0].update(position_read_status='FAILED',position_count=None)
    trace['policy']['maximum_gap_us']=50
    r=assess_trace(trace)
    assert set(r['issues'])=={'POSITION_ACQUISITION_UNAVAILABLE','ACQUISITION_GAP'}


def test_single_endpoint_sample_is_not_settled(trace):
    trace['samples']=trace['samples'][-1:]
    trace['policy']['maximum_gap_us']=500
    assert assess_trace(trace)['category']=='FRESH_POSITION_NOT_SETTLED_AT_DESIRED_TARGET'
