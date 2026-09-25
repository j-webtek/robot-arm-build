from pathlib import Path
import hashlib
import pytest
from rocell.geometry import UrdfModel
from rocell.application.first_motion_contract import canonical
from rocell.application import descending_wrist_transfer as module


@pytest.fixture
def evidence(monkeypatch):
    parent=dict(training_residual_rad=.013908092779914949)
    digest=hashlib.sha256(canonical(parent)).hexdigest()
    parent['candidate_sha256']=digest;monkeypatch.setattr(module,'PARENT_HASH',digest)
    q=[.001533981,.033747577,1.762543925,-.046019424,.018407769,3.138524692]
    desired=list(q);desired[3]=-.045
    trial=dict(acknowledgment_received=True,transaction=dict(state='REPORTED_SETTLED_PENDING_EXPORT',
        compensation_applied=True,desired_joints_rad=desired,
        baseline=dict(joints_rad=dict(t=-.055223308)),
        rows=[dict(observed_s=t,reported_joints_rad=list(q)) for t in (1,2,3)]))
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/
        'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    return model,parent,trial


def test_frozen_descending_offset_is_not_refitted(evidence):
    c=module.build_descending_transfer(*evidence)
    assert c['command']['rad']==pytest.approx(-.06913140077991495)
    assert c['desired_joints_rad'][3]==-.055223308
    assert c['preview']['maximum_sampled_tip_displacement_mm']==pytest.approx(5.04136200246)
    assert not c['correction_refitted'] and not c['motion_authorized']


@pytest.mark.parametrize('fault',['parent','tail','endpoint','ack'])
def test_insufficient_source_rejected(evidence,fault):
    model,parent,trial=evidence
    if fault=='parent':parent['training_residual_rad']=.01
    elif fault=='tail':trial['transaction']['rows'].pop()
    elif fault=='endpoint':trial['transaction']['desired_joints_rad'][3]=0
    else:trial['acknowledgment_received']=False
    with pytest.raises(ValueError):module.build_descending_transfer(model,parent,trial)
