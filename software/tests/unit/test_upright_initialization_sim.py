import pytest
from rocell.application.upright_initialization_sim import rehearse, FAULTS


def sample(fault='NONE'):
    return rehearse([2047,2455,1659,2906,1589,2040,2047],
        [0,0,0,2907,0,0,0],[0,0,0,1,0,0,0],fault=fault)


def test_all_targets_preloaded_before_any_enable():
    report=sample();actions=report['actions']
    assert report['status']=='MODEL_COMPLETED'
    assert [a['kind'] for a in actions[:6]]==['PRELOAD']*6
    assert actions[6]['servo_ids']==[12,13]
    for action in actions[:6]:
        index=action['servo_ids'][0]-11
        assert int.from_bytes(bytes.fromhex(action['payload_hex'])[1:3],'little')==report['initial']['positions'][index]
    assert report['final']['goals'][3]==2907  # Enabled elbow untouched.
    assert report['final']['torques']==[1]*7
    assert report['shoulder_pair_residual_counts']==20  # Never force mirrored counts.
    assert not report['whole_arm_ready'] and not report['motion_authorized']


@pytest.mark.parametrize('fault',FAULTS[1:])
def test_faults_stop_without_rollback_or_retry(fault):
    report=sample(fault)
    assert report['status']=='STOPPED'
    assert len(report['actions'])<=11
    assert all(a['kind'] in ('PRELOAD','ABSTRACT_GROUP_ENABLE') for a in report['actions'])
    if fault.startswith('PRELOAD_'):assert len(report['actions'])==1
    if fault=='DRIFT_BEFORE_ENABLE':assert len(report['actions'])==6
    if fault in ('PARTIAL_SHOULDER_ENABLE','ENABLE_ACK_LOST','NEIGHBOR_DRIFT'):
        assert len(report['actions'])==7
    if fault=='PARTIAL_SHOULDER_ENABLE':assert report['final']['torques'][1:3]==[1,0]


def test_enabled_error_rejected_before_model():
    with pytest.raises(ValueError):rehearse([100]*7,[0]*7,[1]*7)
