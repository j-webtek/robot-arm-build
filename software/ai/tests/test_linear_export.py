import hashlib,json,sys
from pathlib import Path
import pytest
import torch
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path.insert(0,str(AI))
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.pose_model import KeyboardPoseNet
from evidence_artifacts import verify_frozen_artifacts


def model():
    fit=dict(mean=[0.]*512,scale=[1.]*512,weights=[[0.,0.,0.]]*512,intercept=[.01,.02,.03])
    return LinearResidualPoseNet(KeyboardPoseNet().state_dict(),fit,'a'*64,'b'*64)


def test_exact_reload_and_image_only_shape():
    m=model();x=torch.rand(2,3,96,128);n=LinearResidualPoseNet.from_export(m.export())
    with torch.no_grad():assert torch.equal(m(x),n(x))
    assert not any(p.requires_grad for p in m.parameters())
    with pytest.raises(ValueError):m(torch.rand(2,3,192,256))
    with pytest.raises(TypeError):m(x,torch.zeros(2,3))


@pytest.mark.parametrize('field',['scale','weights','preprocess','schema'])
def test_malformed_artifact_rejected(field):
    a=model().export()
    if field=='scale':a['state']['scale'][0]=0
    elif field=='weights':a['state']['weights'][0,0]=float('nan')
    else:a[field]='wrong'
    with pytest.raises(ValueError):LinearResidualPoseNet.from_export(a)


def test_frozen_export_parity_evidence():
    p=AI/'eval/linear_export_v1_plan.json';plan=json.loads(p.read_text());verify_frozen_artifacts(ROOT,plan['file_sha256'])
    r=json.loads((AI/'eval/linear_export_v1_report.json').read_text())
    assert r['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    verify_frozen_artifacts(ROOT,{r['artifact']:r['artifact_sha256']})
    prior=json.loads((AI/'eval/linear_residual_v0_report.json').read_text())
    assert r['reference_prediction_sha256']==prior['runs'][0]['splits']['development']['predictions_sha256']
    assert r['max_normalized_delta']<=1e-10 and r['roundtrip_exact'] and r['image_preprocess_exact']
    assert r['new_fits']==r['hardware_writes']==r['physical_movements']==0
