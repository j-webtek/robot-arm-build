import hashlib,json,math,sys
from pathlib import Path
import torch
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
from vision.landmark_model import KeyboardLandmarkNet,heatmap_coordinates


def test_label_geometry_and_frozen_parity():
    path=AI/'eval/landmark_labels_v0.manifest.json';m=json.loads(path.read_text())
    r=json.loads((AI/'eval/landmark_labels_v0_report.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==r['manifest_sha256']
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['cases'])==400 and r['pixel_mismatches']==0
    for c in r['cases']:
        label=c['label'];points=label['landmarks'];pose=label['pose']
        assert [p['corner_index'] for p in points]==[0,1,2,3]
        assert abs(sum(p['x_px'] for p in points)/4-pose[0]*256/610)<1e-10
        assert abs(sum(p['y_px'] for p in points)/4-pose[1]*192/457)<1e-10
        assert all(0<=p['unoccluded_fraction']<=p['in_frame_fraction']<=1 for p in points)
    assert r['fully_unoccluded']+r['partially_occluded']+r['fully_occluded']==1600
    assert not r['model_trained'] and not r['qualification_installed']


def test_model_shapes_and_coordinate_gradients():
    torch.set_num_threads(2);model=KeyboardLandmarkNet()
    out=model(torch.zeros(2,3,192,256))
    assert out['heatmap_logits'].shape==(2,4,48,64)
    assert out['visibility_logits'].shape==(2,4)
    coords=heatmap_coordinates(out['heatmap_logits'])
    assert coords.shape==(2,4,2) and torch.isfinite(coords).all()
    (coords.square().mean()+out['visibility_logits'].square().mean()).backward()
    assert model.heatmaps.weight.grad is not None
    assert torch.isfinite(model.heatmaps.weight.grad).all()
    uniform=heatmap_coordinates(torch.zeros(1,4,48,64))
    assert torch.allclose(uniform,torch.tensor([126.,94.]).expand(1,4,2))
    peaked=torch.full((1,4,48,64),-100.)
    peaked[:,:,10,20]=100
    assert torch.allclose(heatmap_coordinates(peaked),torch.tensor([80.,40.]).expand(1,4,2))
