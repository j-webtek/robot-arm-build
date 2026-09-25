"""Virtual clock and fake legs only; no hardware sender is imported."""
import math
import pytest
from rocell.arm.comparison_session import ComparisonSession, CommandSpacingSession, PairedSpacingSession, LEGS, LOOKUP_HASH, JOINTS


def harness(*,fault=None,session_type=ComparisonSession):
    timer=[100.];calls=[];events=[];saved={}
    def execute(action):
        i=len(calls);calls.append(action)
        timer[0]+=.1 if fault!='dispatch_late' or i!=1 else 3
        dispatch=timer[0];timer[0]+=36
        _,command,desired=session_type.PLAN[i]
        saved[str(i)]=dict(dispatch_s=dispatch,baseline=[0]*6,
            last_hold=dict(response_finished_monotonic_s=timer[0],joints_rad=dict.fromkeys(JOINTS,0)),
            summary=dict(export_id=str(i),manifest_file_sha256='hash'+str(i),
                command=dict(T=101,joint=5,spd=20,acc=1,rad=math.radians(command)),
                desired_endpoint_deg=desired,command_attempts=1,full_validation_success=fault!='endpoint',
                candidate=dict(candidate_sha256=LOOKUP_HASH) if action=='lookup' else None))
        if action.startswith('sweep_'):
            saved[str(i)]['summary']['characterization']=dict(protocol='LOCAL_COMMAND_SPACING_V1',
                command_deg=command,desired_endpoint_deg=desired,held_out=False,model_updated=False)
            if fault=='characterization':saved[str(i)]['summary']['characterization']['held_out']=True
        if fault=='execute':raise RuntimeError('secret')
        return str(i)
    def review(path):
        if fault=='review':raise ValueError('secret')
        timer[0]+=25 if fault=='slow_review' else 1
        r=saved[path]
        if fault=='incomplete_hold':
            r['summary'].update(full_validation_success=False,failure_code='HOLD_INCOMPLETE',endpoint_replayed=True)
        if fault=='command':r['summary']['command']['spd']=99
        if fault=='baseline' and path=='1':r['baseline'][0]=1
        return r
    def publish(event):
        if fault=='publish' and event['event']=='LEG_INTENT':raise OSError('secret')
        if fault=='final_publish' and event['event']=='FINISHED':raise OSError('secret')
        if fault=='slow_intent' and event['event']=='LEG_INTENT' and event['index']==1:timer[0]+=3
        events.append(event)
    session=session_type()
    def run():
        return session.run(execute_leg=execute,review_leg=review,publish=publish,
            clock=lambda:timer[0],wait=lambda n:timer.__setitem__(0,timer[0]+n),
            cancelled=lambda:fault=='cancel')
    return run,calls,events


def test_two_blocks_are_finite_linked_and_single_use():
    run,calls,events=harness();r=run()
    assert r['status']=='COMPLETED' and r['reviewed_legs']==8
    assert calls==[v[0] for v in LEGS]
    verified=[e for e in events if e['event']=='LEG_VERIFIED']
    assert all(e['measured_interval_s']==pytest.approx(20.1) for e in verified[1:])
    assert verified[1]['predecessor']['manifest_file_sha256']=='hash0'
    with pytest.raises(ValueError):run()
    assert len(calls)==8


@pytest.mark.parametrize('fault,count',[('publish',0),('cancel',0),('execute',1),
    ('review',1),('endpoint',1),('command',1),('slow_review',1),('dispatch_late',2),('baseline',2)])
def test_faults_stop_without_retry_or_return(fault,count):
    run,calls,_=harness(fault=fault);r=run()
    assert r['status']=='STOPPED' and len(calls)==count
    assert not r['automatic_retry_allowed'] and not r['automatic_return_allowed']
    assert 'secret' not in str(r)


def test_slow_intent_publication_does_not_dispatch_after_window():
    run,calls,_=harness(fault='slow_intent');r=run()
    assert len(calls)==1 and r['reason']=='PRE_DISPATCH_WINDOW_MISSED'


def test_final_storage_failure_does_not_report_completion():
    run,calls,_=harness(fault='final_publish');r=run()
    assert len(calls)==8 and r['reason']=='FINAL_PUBLICATION_FAILED'
    assert r['status']=='STOPPED'


def test_sweep_exactly_twelve_legs_with_characterization_not_validation():
    run,calls,events=harness(session_type=CommandSpacingSession)
    r=run()
    assert r['status']=='COMPLETED' and len(calls)==12
    assert calls==[v[0] for v in CommandSpacingSession.PLAN]
    assert calls[1::2]==['sweep_low','sweep_center','sweep_high','sweep_high','sweep_center','sweep_low']


def test_sweep_rejects_wrong_evidence_classification():
    run,calls,_=harness(session_type=CommandSpacingSession,fault='characterization')
    r=run()
    assert len(calls)==2 and r['reason']=='CHARACTERIZATION_MISMATCH'


def test_incomplete_hold_gets_specific_failure_event_without_next_move():
    run,calls,events=harness(fault='incomplete_hold');r=run()
    assert r['reason']=='HOLD_INCOMPLETE' and len(calls)==1
    failures=[e for e in events if e['event']=='LEG_REVIEW_FAILED']
    assert len(failures)==1 and failures[0]['endpoint_replayed']


def test_paired_spacing_is_finite_abba():
    run,calls,_=harness(session_type=PairedSpacingSession)
    assert run()['status']=='COMPLETED'
    assert len(calls)==8
    assert calls[::2]==['high']*4
    assert calls[1::2]==['sweep_center','sweep_high','sweep_high','sweep_center']
    with pytest.raises(ValueError):run()


@pytest.mark.parametrize('fault', ['incomplete_hold','endpoint','baseline','characterization'])
def test_paired_spacing_stops_on_failure(fault):
    run,calls,_=harness(session_type=PairedSpacingSession,fault=fault)
    assert run()['status']=='STOPPED'
    assert len(calls)<=2
