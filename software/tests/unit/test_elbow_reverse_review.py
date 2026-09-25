from pathlib import Path
import pytest
from rocell.geometry import UrdfModel
from rocell.application.product_ghost_export_review import _read
from rocell.application.elbow_reverse_review import review_reverse_identification


@pytest.fixture
def evidence():
    software=Path(__file__).resolve().parents[2]
    root=software/'runs/wizard-exports'
    report,_=_read(root,'wizard-20260917T213018314567Z-ebaacbf5eb60410ba58e880c6809b165',
        'attachment-all-joint-trial.json')
    passive,_=_read(root,'wizard-20260917T213104814701Z-86eef1254d414e90bcb09785af62cc32',
        'attachment-result-f22e6df632804f2c90c96587126fef60.json')
    model=UrdfModel.from_file(software/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    return report,passive['steps'][0]['report'],model


def test_retained_reverse_evidence_is_not_global_compensation(evidence):
    result=review_reverse_identification(*evidence)
    assert result['trial']['elbow']['predicted_count_change']==-10
    assert result['trial']['elbow']['reported_count_change']==0
    assert result['maximum_passive_joint_change_rad']==0
    assert result['passive_samples']==113
    assert result['historical_offset_scenario']['envelope']['status']=='SAMPLED_MODEL_BOUND_EXCEEDED'
    assert not result['motion_authorized'] and not result['physical_cause_established']


@pytest.mark.parametrize('change',['receipt','row','timestamp','followup','motion'])
def test_corrupt_or_unrelated_evidence_rejected(evidence,change):
    report,passive,model=evidence
    if change=='receipt':report['receipt']['payload_sha256']='0'*64
    if change=='row':report['transaction']['rows'][0]['reported_joints_rad'][2]+=.1
    if change=='timestamp':report['transaction']['rows'][0]['observed_s']+=.001
    if change=='followup':passive['samples'].reverse()
    if change=='motion':passive['motion_commands']=1
    with pytest.raises(ValueError):review_reverse_identification(report,passive,model)
