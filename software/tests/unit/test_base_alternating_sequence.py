"""Real admission/collector and portable math with incapable stream callbacks."""
from copy import deepcopy
import hashlib
import json
from threading import Event
import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.base_alternating_sequence import _assemble_template
from rocell.application.positional_owned_campaign import run_owned_positional_campaign
from rocell.application.endpoint_owned_trial import EndpointCleanupResult
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent,require_correction_start
from test_base_compensation_campaign import experiment_body,proposal
from test_positional_campaign_admission import setup
from test_model_corrected_native_campaign import install


def sequence_body():
    source=experiment_body()
    down_start=list(source['start_joints_rad']);down_start[0]=.018407769
    b=_assemble_template(source,source['base_experiment'],
        proposal(down_start,source['references'],'DECREASING')).to_dict()
    b.update(issued_ns=1_000_000_000,deadline_ns=61_000_000_000)
    return b


def exercise_sequence(tmp_path,monkeypatch,*,fault=None,fault_leg=1):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',sequence_body)
    admission,reader,clock=setup(tmp_path)
    admission.claim_open()
    event=Event();counts=dict(write=0,close=0,commands=[])
    pose=list(reader.request.to_dict()['start_joints_rad'])
    transition=dict(start=pose[0],target=pose[0],written_ns=None)
    def read(size,timeout):
        clock[0]+=min(50,timeout)*1_000_000
        # Exercise a finite motion interval, not an instantaneous encoder jump.
        if transition['written_ns'] is not None:
            fraction=min(1.,(clock[0]-transition['written_ns'])/500_000_000)
            pose[0]=transition['start']+(transition['target']-transition['start'])*fraction
        if counts['write']==fault_leg and fault=='malformed':return b'bad\n'
        if counts['write']==fault_leg and fault=='late_read':clock[0]+=300_000_000
        fields=dict(T=1051,x=0,y=0,z=0,tit=0,**dict(zip(('b','s','e','t','r','g'),pose)))
        raw=canonical(fields)+b'\n'
        assert len(raw)<=size
        return raw
    def write(payload):
        counts['write']+=1;counts['commands'].append(json.loads(payload))
        active=counts['write']==fault_leg
        transition.update(start=pose[0],target=pose[0],written_ns=clock[0])
        if not (active and fault=='no_response'):
            transition['target']=.018407769 if counts['write']%2 else .007669904
        if active and fault=='other_joint':pose[2]+=.02
        if active and fault=='cancel':event.set()
        if active and fault=='short_write':return len(payload)-1
        return len(payload)
    def close(timeout):
        counts['close']+=1
        return EndpointCleanupResult(True,0)
    result=run_owned_positional_campaign(reader.request,admission,read_once=read,
        write_once=write,close_once=close,cancellation=event,basis='SYNTHETIC_WIRE_REHEARSAL',
        clock_ns=lambda:clock[0],idle_wait=lambda s:clock.__setitem__(0,clock[0]+round(s*1e9)))
    return result,counts,reader.request


def test_four_legs_one_claimed_connection_with_original_reconstruction(tmp_path,monkeypatch):
    result,counts,_=exercise_sequence(tmp_path,monkeypatch)
    assert result['status']=='SIMULATION_COMPLETE',result
    assert counts['write']==4 and counts['close']==1
    assert result['reconstruction']['legs_verified']==4
    assert not result['physical_write_count'] and not result['native_execution_released']
    assert [c['rad'] for c in counts['commands']]==[.04076651868282478,-.011952475158143525]*2


@pytest.mark.parametrize('leg',[1,2,3,4])
@pytest.mark.parametrize('fault',['no_response','other_joint','short_write','malformed','late_read','cancel'])
def test_fault_on_any_leg_withholds_every_later_write(tmp_path,monkeypatch,leg,fault):
    result,counts,_=exercise_sequence(tmp_path,monkeypatch,fault=fault,fault_leg=leg)
    assert result['status']!='SIMULATION_COMPLETE'
    assert counts['write']==leg and counts['close']==1
    assert len(result['skipped_leg_ids'])==4-leg
    assert not result['physical_write_count']


@pytest.mark.parametrize('fault',['extra','speed','direction','nominal','start','deadline','budget','model'])
def test_sequence_is_not_an_arbitrary_list_or_new_model(fault):
    b=sequence_body()
    if fault=='extra':b['legs'].append(deepcopy(b['legs'][-1]))
    if fault=='speed':b['legs'][2]['command']['spd']=30
    if fault=='direction':b['legs'][1]['command']['rad']=.04076651868282478
    if fault=='nominal':b['legs'][2]['target_rad']=.02
    if fault=='start':b['start_joints_rad'][0]=.01
    if fault=='deadline':b['deadline_ns']+=1
    if fault=='budget':b['limits']['maximum_writes']=5
    if fault=='model':
        b['base_sequence']['decreasing']['model_sha256']='e'*64
        b['references']['configuration_sha256']=hashlib.sha256(canonical(b['base_sequence'])).hexdigest()
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(b))


def test_next_leg_uses_its_direction_and_all_six_handoff_coordinates():
    b=sequence_body();s=list(b['start_joints_rad']);s[0]=.018407769
    require_correction_start(b,s,b['legs'][1])
    with pytest.raises(ValueError):require_correction_start(b,s,b['legs'][0])
    for i in range(6):
        changed=list(s);changed[i]+=.001
        with pytest.raises(ValueError):require_correction_start(b,changed,b['legs'][1])


def test_v14_cannot_open_native_api_without_exact_native_composition():
    from rocell.providers.windows.positional_campaign_serial_api import WindowsPositionalCampaignSerialApi
    with pytest.raises(ValueError,match='composition required'):
        WindowsPositionalCampaignSerialApi.from_campaign_claim(
            PositionalCampaignIntent(canonical(sequence_body())),None,None,
            port_name='COM7',connection_id='unused',cancellation=Event())


def test_changed_original_result_cannot_claim_success(tmp_path,monkeypatch):
    from rocell.application.positional_campaign_reconstruction import verify_completed_owned_campaign
    result,_,request=exercise_sequence(tmp_path,monkeypatch)
    altered=deepcopy(result)
    altered['legs'][2]['verification']['endpoint']['final_error_rad']=0
    with pytest.raises(ValueError):verify_completed_owned_campaign(request,altered)


@pytest.mark.parametrize('index',[0,1,2,3])
def test_no_nominal_endpoint_can_replace_observed_handoff(index):
    b=sequence_body();leg=b['legs'][index]
    s=list(b['start_joints_rad']);s[0]=.4*3.141592653589793/180 if index%2==0 else 3.141592653589793/180
    with pytest.raises(ValueError):require_correction_start(b,s,leg)
