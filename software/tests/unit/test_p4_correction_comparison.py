from collections import Counter
from pathlib import Path
import pytest
from rocell.application.p4_correction_comparison import review_comparison, ORDER

MODEL = Path(__file__).resolve().parents[2]/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf'

@pytest.fixture(scope='module')
def review():
    return review_comparison(MODEL)

def test_balanced_route_and_same_anchor(review):
    rows = review['legs']
    assert len(rows)==16
    assert Counter(ORDER)=={'baseline':4, 'candidate':4}
    assert sum(i for i,v in enumerate(ORDER,1) if v=='baseline')==18
    assert sum(i for i,v in enumerate(ORDER,1) if v=='candidate')==18
    for comparison, anchor in zip(rows[::2],rows[1::2]):
        assert comparison['preceding_command_goal']==1980
        assert comparison['direction']==-1
        assert comparison['desired_endpoint']==1947
        assert comparison['transmitted_goal']==(1947 if comparison['condition']=='baseline' else 1944)
        assert comparison['required_goal_readback']==comparison['transmitted_goal']
        assert anchor['transmitted_goal']==1980
        assert anchor['direction']==1
    assert max(abs(r['command_delta_counts']) for r in rows)==36

def test_envelope_and_no_hardware_claim(review):
    assert review['wrist_sweep_counts']==[1888,2039]
    assert review['sweep_samples']==303
    assert review['minimum_model_tcp_z_mm']>0
    assert review['minimum_model_capsule_clearance_mm']>0
    for field in ('hardware_access','movement_authorized','physical_clearance_verified',
                  'compensation_applied','native_comparison_implemented'):
        assert review[field] is False

def test_frozen_success_criteria(review):
    assert review['acceptance']['candidate_max_absolute_desired_error_counts']==1
    assert review['acceptance']['minimum_mae_improvement_counts']==2
    assert review['acceptance']['require_all_16_legs_verified_and_exported']

def test_changed_model_rejected(tmp_path):
    path=tmp_path/'model.urdf'
    path.write_text('different')
    with pytest.raises(ValueError,match='Reviewed kinematic model'):
        review_comparison(path)
