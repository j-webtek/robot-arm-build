import pytest
from test_wifi_cartesian import setup
from rocell.application.compensated_elbow_cycle import CompensatedElbowCycle


def adapters(tmp_path, *, fault=None):
    events=[]; reports=[]
    def leg(*,index,mode,previous_joints,cancelled):
        events.append(('run',index))
        if fault=='raise': raise RuntimeError('private')
        path=tmp_path/str(index); path.mkdir()
        _,run,_,_,_,_=setup(path,mode='desired_candidate',elbow_only=True,elbow_degrees=mode,compensated_endpoint=True)
        result=run()
        if fault=='feedback': result['error']='TRANSACTION_INTERRUPTED_OR_UNCERTAIN'
        if fault=='identity': result['transaction']['local_candidate']['desired_rad']+=.01
        report=dict(status=result['status'],run=result,receipt=dict(cleanup_confirmed=fault!='cleanup'))
        reports.append(report)
        if index: assert previous_joints==reports[0]['run']['transaction']['rows'][-1][3]
        return report
    def publish(*,index,report):
        events.append(('publish',index))
        assert report==reports[index]
        if fault=='export_raise': raise OSError('private')
        return dict(verified=fault!='export_false',export=f'leg-{index}')
    return leg,publish,events


def test_two_legs_publish_before_progress_and_never_replay(tmp_path):
    leg,publish,events=adapters(tmp_path)
    cycle=CompensatedElbowCycle()
    result=cycle.run(run_leg=leg,publish_leg=publish)
    assert result['status']=='LOCAL_CYCLE_REPORTED_ENDPOINTS_VERIFIED'
    assert events==[('run',0),('publish',0),('run',1),('publish',1)]
    assert cycle.run(run_leg=leg,publish_leg=publish)['status']=='CYCLE_ALREADY_USED'
    assert len(events)==4


@pytest.mark.parametrize('fault,expected',[
    ('raise','LEG_OUTCOME_UNCERTAIN'),('feedback','LEG_NOT_VERIFIED'),
    ('identity','LEG_NOT_VERIFIED'),('cleanup','LEG_NOT_VERIFIED'),
    ('export_raise','EXPORT_NOT_VERIFIED'),('export_false','EXPORT_NOT_VERIFIED')])
def test_any_first_leg_failure_stops_second(tmp_path,fault,expected):
    leg,publish,events=adapters(tmp_path,fault=fault)
    result=CompensatedElbowCycle().run(run_leg=leg,publish_leg=publish)
    assert result['status']==expected
    assert ('run',1) not in events
    assert 'private' not in str(result)


def test_cancel_after_publication_prevents_next_leg(tmp_path):
    leg,publish,events=adapters(tmp_path)
    result=CompensatedElbowCycle().run(run_leg=leg,publish_leg=publish,
                                    cancelled=lambda:('publish',0) in events)
    assert result['status']=='CANCELLED_BEFORE_NEXT_LEG'
    assert events==[('run',0),('publish',0)]
