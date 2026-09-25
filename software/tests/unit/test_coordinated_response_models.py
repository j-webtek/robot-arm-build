import pytest
from test_coordinated_candidate import source
from rocell.kinematics.firmware_reference import forward
from rocell.application.coordinated_response_models import compare_response_models,screen_hybrid_approach


def traces():
    reports=[]
    for i in range(3):
        r=source();t=r['run']['transaction'];shift=i*10_000_000_000
        t['dispatch_started_ns']+=shift
        for index,sign in ((2,1),(3,-1)):
            delta=sign*(.01+.005*i)
            t['expected_joints'][index]=t['baseline_joints'][index]+delta
            for row in t['rows']:row[3][index]=t['baseline_joints'][index]+.6*delta
        for row in t['rows']:
            row[0]+=shift;row[1]+=shift;row[2]=list(forward(*row[3][:4]))
        reports.append(r)
    return reports


def test_gain_recovered_without_last_sample_fitting():
    r=compare_response_models(traces())
    assert not r['holdout_used_for_fitting'] and r['new_independent_validation_required']
    for j in r['joints']:
        gain=j['evaluations'][1]
        assert gain['slope']==pytest.approx(.6)
        assert abs(gain['holdout_error_deg'])<1e-10
        assert not gain['enabled_for_motion']


def test_changed_holdout_does_not_change_fitted_parameters():
    reports=traces();before=compare_response_models(reports)
    for row in reports[-1]['run']['transaction']['rows']:
        row[3][3]-=.001;row[2]=list(forward(*row[3][:4]))
    after=compare_response_models(reports)
    for a,b in zip(before['joints'],after['joints']):
        assert [(v['slope'],v['intercept_rad']) for v in a['evaluations']]==[(v['slope'],v['intercept_rad']) for v in b['evaluations']]


def test_out_of_order_traces_rejected():
    with pytest.raises(ValueError):compare_response_models(traces()[::-1])


def test_hybrid_grid_preserves_training_ranges_and_no_authority():
    r=screen_hybrid_approach(traces())
    assert r['sampled_count']==2010
    assert not r['motion_authorized'] and not r['full_path_screened']
    for point in r['feasible']:
        for value,(lo,hi) in zip((point['wire_elbow_delta_rad'],point['wire_wrist_delta_rad']),r['training_command_ranges_rad']):
            assert lo<=value<=hi
