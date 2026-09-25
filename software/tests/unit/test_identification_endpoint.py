from pathlib import Path
from copy import deepcopy
import pytest
from rocell.geometry import UrdfModel
from rocell.application.product_ghost_export_review import _read
from rocell.application.identification_endpoint import verified_identification_endpoint
from test_all_joint_native import setup


@pytest.fixture
def source(monkeypatch,tmp_path):
    run,_,_=setup(monkeypatch,tmp_path)
    result=run(True)
    path=Path(result['export']['path'])
    report,_=_read(path.parent,path.name,'attachment-all-joint-trial.json')
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/
        'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    return report,model


def test_reconstructs_from_verified_raw_samples(source):
    result=verified_identification_endpoint(*source)
    assert result['stable_tail_s']>=2
    assert result['modeled_desired_tip_error_mm']==0
    assert not result['physical_accuracy_verified']


@pytest.mark.parametrize('fault',['hash','position','timestamp','desired','short_tail'])
def test_success_label_alone_insufficient(source,fault):
    report,model=source;report=deepcopy(report);tx=report['transaction']
    if fault=='hash':tx['rows'][-1]['raw_feedback']['response_sha256']='bad'
    elif fault=='position':tx['rows'][-1]['reported_joints_rad'][3]+=.01
    elif fault=='timestamp':tx['rows'][-1]['observed_s']+=.1
    elif fault=='desired':tx['desired_joints_rad'][3]=0
    else:tx['rows']=tx['rows'][-2:]
    with pytest.raises(ValueError):verified_identification_endpoint(report,model)
