from test_wifi_cartesian import setup
import pytest
from rocell.application.elbow_local_candidate import candidate_record


def test_candidate_is_frozen_local_and_single_send(tmp_path):
    reservation,run,sent,_,_,_=setup(tmp_path,elbow_only=True,elbow_degrees=1)
    candidate=candidate_record()
    assert reservation.command()['rad']==candidate['command_rad']
    assert candidate['desired_rad']!=candidate['command_rad']
    result=run()
    assert result['status']=='REPORTED_ENDPOINT_VERIFIED'
    assert result['transaction']['desired_endpoint_result']['status']=='DESIRED_ENDPOINT_NOT_VERIFIED'
    assert len(sent)==1 and run()['status']=='ATTEMPT_ALREADY_USED'


def test_desired_success_does_not_relabel_wire_failure(tmp_path):
    _,run,sent,_,_,_=setup(tmp_path,mode='desired_candidate',elbow_only=True,elbow_degrees=1)
    result=run()
    assert result['status']=='COMPLETION_DEADLINE_EXCEEDED'
    assert not result['transaction']['result']['endpoint_verified']
    desired=result['transaction']['desired_endpoint_result']
    assert desired['status']=='DESIRED_REPORTED_ENDPOINT_VERIFIED'
    assert not desired['physical_accuracy_verified'] and len(sent)==1


def test_wrong_start_rejected(tmp_path):
    from rocell.application.controller_route_preview import preview_elbow_isolation
    _,_,_,_,_,baseline=setup(tmp_path)
    assert preview_elbow_isolation(baseline,elbow_degrees=1)['status']=='CANDIDATE_START_OUTSIDE_LOCAL_RANGE'


def test_extended_identity_preserves_original():
    original=candidate_record(); extended=candidate_record(extended_start=True)
    assert original['candidate_sha256']=='94285286e6a0d95735bf75ced9a8ab1337129ed6a54b35495ad58f6dc3d7df3f'
    assert extended['parent_candidate_sha256']==original['candidate_sha256']
    assert extended['candidate_sha256']!=original['candidate_sha256']
    for key in ('command_rad','desired_rad','spd','acc','training_residual_rad'):
        assert extended[key]==original[key]


def test_extended_transaction_keeps_two_verdicts(tmp_path):
    _,run,sent,_,_,_=setup(tmp_path,mode='desired_candidate',elbow_only=True,elbow_degrees=-1)
    result=run(); transaction=result['transaction']
    assert len(sent)==1 and result['status']=='COMPLETION_DEADLINE_EXCEEDED'
    assert transaction['local_candidate']['schema']=='rocell.elbow_local_candidate.v2'
    assert transaction['desired_endpoint_result']['status']=='DESIRED_REPORTED_ENDPOINT_VERIFIED'


def test_nearby_target_scores_its_own_target(tmp_path):
    import pytest
    from rocell.application.elbow_local_candidate import evaluate_desired_endpoint
    _,run,sent,_,_,_=setup(tmp_path,mode='desired_candidate',elbow_only=True,elbow_degrees=3)
    result=run(); transaction=result['transaction']
    candidate=transaction['local_candidate']
    assert candidate['desired_rad']==pytest.approx(candidate_record()['desired_rad']-.01)
    assert candidate['desired_rad']-candidate['command_rad']==pytest.approx(candidate['training_residual_rad'])
    assert len(sent)==1 and result['status']=='COMPLETION_DEADLINE_EXCEEDED'
    assert transaction['desired_endpoint_result']['status']=='DESIRED_REPORTED_ENDPOINT_VERIFIED'
    assert evaluate_desired_endpoint(transaction['baseline_joints'],transaction['rows'])['status']=='DESIRED_ENDPOINT_NOT_VERIFIED'


def test_descending_candidate_has_separate_fit_and_verdict(tmp_path):
    import pytest
    candidate=candidate_record(descending=True)
    assert candidate['approach']=='DECREASING_ELBOW_RAD'
    assert candidate['command_rad']==pytest.approx(1.4826170384002835)
    assert candidate['training_residual_rad']!=candidate_record()['training_residual_rad']
    _,run,sent,_,_,_=setup(tmp_path,mode='desired_candidate',elbow_only=True,elbow_degrees=-4)
    result=run()
    assert len(sent)==1 and result['status']=='COMPLETION_DEADLINE_EXCEEDED'
    assert result['transaction']['desired_endpoint_result']['status']=='DESIRED_REPORTED_ENDPOINT_VERIFIED'
    assert result['transaction']['policy']['position_tolerance_mm']==.5


@pytest.mark.parametrize('mode',[-4,-5])
def test_descending_boundaries_and_path(tmp_path,mode):
    import math
    from rocell.application.controller_route_preview import preview_elbow_isolation
    from rocell.kinematics.firmware_reference import forward
    _,_,_,_,_,baseline=setup(tmp_path,elbow_only=True,elbow_degrees=mode)
    for elbow in (1.549999,1.550,1.552388557,1.555,1.560,1.565,1.565001):
        baseline['joints_rad']['e']=elbow
        pose=forward(*(baseline['joints_rad'][key] for key in ('b','s','e','t')))
        baseline['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),pose))
        preview=preview_elbow_isolation(baseline,elbow_degrees=mode)
        if 1.550<=elbow<=1.565:
            assert preview['status']=='PREVIEW_ONLY_NOT_EXECUTABLE'
            assert all(math.dist(pose[:3],s['xyz_pitch'][:3])<=28 for s in preview['samples'])
            assert all(s['joints_rad'][2]<=elbow for s in preview['samples'])
        else:
            assert preview['status']=='CANDIDATE_START_OUTSIDE_LOCAL_RANGE'


def test_revised_descending_is_frozen_separately(tmp_path):
    original=candidate_record(descending=True)
    revised=candidate_record(descending_revised=True)
    assert original['candidate_sha256']=='8dcb1cb97bf2538f1c2fcfb25288eea558ed6a5ee4d01d9b775386185acf52ae'
    assert revised['parent_candidate_sha256']==original['candidate_sha256']
    assert revised['training_residual_rad']==pytest.approx(.0486063650997165)
    _,run,sent,_,_,_=setup(tmp_path,mode='desired_candidate',elbow_only=True,elbow_degrees=-5)
    result=run()
    assert len(sent)==1 and result['status']=='COMPLETION_DEADLINE_EXCEEDED'
    assert result['transaction']['desired_endpoint_result']['status']=='DESIRED_REPORTED_ENDPOINT_VERIFIED'
    assert result['transaction']['policy']['position_tolerance_mm']==.5


def test_extended_range_screening(tmp_path):
    import math
    from rocell.application.controller_route_preview import preview_elbow_isolation
    from rocell.kinematics.firmware_reference import forward
    _,_,_,_,_,baseline=setup(tmp_path,elbow_only=True,elbow_degrees=-1)
    for elbow in (1.519999,1.520,1.523242922,1.525,1.530,1.535,1.540,1.540001):
        baseline['joints_rad']['e']=elbow
        pose=forward(*(baseline['joints_rad'][key] for key in ('b','s','e','t')))
        baseline['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),pose))
        preview=preview_elbow_isolation(baseline,elbow_degrees=-1)
        if 1.520<=elbow<=1.540:
            assert preview['status']=='PREVIEW_ONLY_NOT_EXECUTABLE'
            assert len(preview['samples'])==41
            assert all(math.dist(pose[:3],sample['xyz_pitch'][:3])<=12 for sample in preview['samples'])
        else:
            assert preview['status']=='CANDIDATE_START_OUTSIDE_LOCAL_RANGE'


def test_mapping_sample_fixed_start_and_one_send(tmp_path):
    from rocell.application.controller_route_preview import preview_elbow_isolation
    from rocell.kinematics.firmware_reference import forward
    _,run,sent,_,_,baseline=setup(tmp_path,elbow_only=True,elbow_degrees=-6)
    result=run()
    assert len(sent)==1 and result['status']=='REPORTED_ENDPOINT_VERIFIED'
    assert result['transaction']['local_candidate']['purpose']=='FIXED_START_IDENTIFICATION_NOT_FITTED_CORRECTION'
    assert result['transaction']['desired_endpoint_result']['status']=='DESIRED_ENDPOINT_NOT_VERIFIED'
    assert run()['status']=='ATTEMPT_ALREADY_USED'
    for delta in (-.001,.001):
        baseline['joints_rad']['e']=1.552388557+delta
        pose=forward(*(baseline['joints_rad'][key] for key in ('b','s','e','t')))
        baseline['controller_cartesian']['values']=dict(zip(('x','y','z','tit'),pose))
        assert preview_elbow_isolation(baseline,elbow_degrees=-6)['status']=='CANDIDATE_START_OUTSIDE_LOCAL_RANGE'
