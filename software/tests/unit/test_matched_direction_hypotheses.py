import pytest
from rocell.application.shoulder_characterization_sim import run_characterization_sim


def test_constant_bias_can_reverse_despite_target_below_measured(tmp_path):
    r=run_characterization_sim(tmp_path,pattern='matched',residual=(10,-7))['report']
    assert r['state']=='COMPLETED' and r['physical_packets']==0
    reversal=r['legs'][1]
    assert reversal['target_minus_measured']==[-2,-1]
    assert reversal['assessment']['actual_delta']==[8,-8]
    assert all(x['assessment']['endpoint_error']==[10,-7] for x in r['legs'])


def test_direction_dependent_model_is_not_constant_compensation(tmp_path):
    r=run_characterization_sim(tmp_path,pattern='matched',residual=(10,-7),
                               reverse_residual=(6,-4))['report']
    assert r['state']=='COMPLETED'
    middle=[x for x in r['legs'] if x['command']['command_goals']==[2397,1717]]
    assert {tuple(x['assessment']['endpoint_error']) for x in middle}=={(10,-7),(6,-4)}
    assert len(middle)==6


@pytest.mark.parametrize('fault',['NO_RESPONSE','REVERSE','UNSETTLED','NEIGHBOR','DELIVERY','EXPORT'])
def test_failed_reverse_stops_following_legs(tmp_path,fault):
    r=run_characterization_sim(tmp_path,pattern='matched',residual=(10,-7),
                               fault=fault,fault_leg=2)['report']
    assert r['state']=='STOPPED' and len(r['legs'])==2
    assert r['physical_packets']==0 and not r['movement_authorized']
