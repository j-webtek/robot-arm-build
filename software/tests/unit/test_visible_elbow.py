import math
import pytest
from test_wifi_cartesian import setup


def test_visible_lift_is_single_send_with_distinct_scope(tmp_path):
    reservation,run,sent,_,_,baseline=setup(tmp_path,elbow_only=True,elbow_degrees=5)
    assert reservation.command()['rad']==baseline['joints_rad']['e']-math.radians(5)
    result=run()
    assert result['status']=='REPORTED_ENDPOINT_VERIFIED'
    assert result['transaction']['policy']['scope']=='ELBOW_ONLY_MINUS_5_DEGREES'
    assert len(sent)==1
    assert run()['status']=='ATTEMPT_ALREADY_USED'
    assert len(sent)==1


def test_nonresponse_does_not_retry_visible_lift(tmp_path):
    _,run,sent,_,_,_=setup(tmp_path,mode='unchanged',elbow_only=True,elbow_degrees=5)
    assert run()['status']=='COMPLETION_DEADLINE_EXCEEDED'
    assert len(sent)==1


def test_reverse_probe_stays_local_and_one_send(tmp_path):
    reservation,run,sent,_,_,baseline=setup(tmp_path,elbow_only=True,elbow_degrees=-3)
    assert reservation.command()['rad']==baseline['joints_rad']['e']+math.radians(3)
    assert run()['status']=='REPORTED_ENDPOINT_VERIFIED'
    assert len(sent)==1
    assert run()['status']=='ATTEMPT_ALREADY_USED'


def test_reverse_probe_rejects_start_outside_reviewed_interval(tmp_path):
    from rocell.application.controller_route_preview import preview_elbow_isolation
    _,_,_,_,_,baseline=setup(tmp_path,elbow_only=True)
    assert preview_elbow_isolation(baseline,elbow_degrees=-3)['status']=='REVERSE_PROBE_OUTSIDE_REVIEWED_INTERVAL'


# Internal mode 3 now names the fixed v3 candidate, not a relative 3-degree move.
@pytest.mark.parametrize('degrees',[True,0,4,10,90,5.0])
def test_arbitrary_expansion_rejected(tmp_path,degrees):
    with pytest.raises(ValueError): setup(tmp_path,elbow_only=True,elbow_degrees=degrees)
