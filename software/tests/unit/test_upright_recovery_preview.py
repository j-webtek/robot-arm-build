import pytest
from rocell.kinematics.upright_recovery_preview import compare_orders


def test_recorded_pose_ordering_and_limits():
    result=compare_orders([2047,2455,1659,2906,1589,2040,2047])
    assert result['shoulder_pair_residual_counts']==20
    assert len(result['orders'])==6
    for row in result['orders']:
        if row['order'][0]=='shoulder':
            assert row['first_sample_delta_z_mm']>0
            assert row['minimum_sampled_delta_z_mm']==0
        else:assert row['minimum_sampled_delta_z_mm']<0
    assert result['target_reference_angles_deg'][1:]==[0,90,0]
    assert result['target_reference_endpoint'][2]==pytest.approx(223.13)
    assert not result['motion_authorized'] and not result['physical_clearance_verified']
    assert not result['dynamics_simulated']


@pytest.mark.parametrize('positions',[[0]*6,[0]*8,[False]*7,[-1]*7,[4096]*7])
def test_invalid_counts(positions):
    with pytest.raises(ValueError):compare_orders(positions)
