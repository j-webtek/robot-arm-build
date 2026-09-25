import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_transport_snapshot import collect_snapshot,STATUS,RECORD
from rocell.application.servo_diagnostic_simulation import simulate_trace,simulate_write_evidence


def fixture():
    trace=simulate_trace('paired_arrival')
    identity={k:trace['command'][k] for k in ('boot_id','command_id','servo_id')}
    bodies=[identity,{},trace['dispatch'],simulate_write_evidence('paired_arrival'),trace['samples'][0]]
    status=dict(schema='rocell.diagnostic_transport.v1',state='CAPTURED',reason='NONE',records=5,
                storage_fault=False,start_supported=False,durable_export_verified=False)
    responses={STATUS:status}
    for i,body in enumerate(bodies):
        responses[RECORD+str(i)]=dict(schema='rocell.diagnostic_record.v1',index=i,
                                    kind=('converted','hook','dispatch','write','pair')[i],record=body)
    return responses


def reader(responses,calls):
    def get(path,*,maximum_bytes,timeout_seconds):
        calls.append(path)
        assert maximum_bytes in (512,2304) and timeout_seconds==3.0
        return canonical(responses[path])
    return get


def test_terminal_snapshot_is_readonly_and_not_authority():
    calls=[];result=collect_snapshot(reader(fixture(),calls))
    assert len(calls)==7 and calls[0]==calls[-1]==STATUS
    assert len(result['responses'])==7
    assert not result['provenance_verified'] and not result['progression_authority']
    assert not result['endpoint_assessed']


@pytest.mark.parametrize('fault',['active','overflow','order','identity','changed','missing'])
def test_rejects_inconsistent_collection_without_retry(fault):
    responses=fixture();calls=[]
    if fault=='active':responses[STATUS]['state']='SAMPLING'
    if fault=='overflow':responses[STATUS]['records']=17
    if fault=='order':responses[RECORD+'2']['index']=1
    if fault=='identity':responses[RECORD+'4']['record']['feedback']['boot_id']='other'
    get=reader(responses,calls)
    def altered(path,**kwargs):
        if fault=='missing' and path==RECORD+'2':raise ValueError('Missing response')
        if fault=='changed' and path==STATUS and calls:
            responses[STATUS]['state']='FAULT'
        return get(path,**kwargs)
    with pytest.raises(ValueError):collect_snapshot(altered)
    assert calls.count(RECORD+'2')<=1


def test_empty_idle_is_not_an_endpoint():
    responses=fixture();responses[STATUS].update(state='IDLE',records=0)
    assert collect_snapshot(reader(responses,[]))['records']==[]


@pytest.mark.parametrize('replacement',[None,'record','status'])
def test_v2_boot_identity_prevents_same_count_reboot_mix(replacement):
    responses=fixture();instance='0123456789abcdef'*2
    responses[STATUS].update(schema='rocell.diagnostic_transport.v2',instance_id=instance)
    for index in range(5):
        responses[RECORD+str(index)].update(schema='rocell.diagnostic_record.v2',instance_id=instance)
    calls=[];get=reader(responses,calls)
    def changed(path,**kwargs):
        if replacement=='record' and path==RECORD+'3':responses[path]['instance_id']='f'*32
        if replacement=='status' and path==STATUS and calls:responses[path]['instance_id']='f'*32
        return get(path,**kwargs)
    if replacement:
        with pytest.raises(ValueError):collect_snapshot(changed)
    else:assert collect_snapshot(changed)['instance_identity_bound']


@pytest.mark.parametrize('instance',[None,True,'','z'*32,'a'*31,'a'*33])
def test_v2_rejects_malformed_instance_before_record_requests(instance):
    responses=fixture()
    responses[STATUS].update(schema='rocell.diagnostic_transport.v2',instance_id=instance)
    calls=[]
    with pytest.raises(ValueError):collect_snapshot(reader(responses,calls))
    assert calls==[STATUS]
