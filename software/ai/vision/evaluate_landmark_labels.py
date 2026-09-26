"""Audit exact pixel preservation and geometric landmark-label population."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
from vision.synthetic_keyboard import render,catalog_for_workspace
from vision.landmark_renderer import render_landmarks
from vision.landmark_model import KeyboardLandmarkNet


def run():
    path=AI/'eval/landmark_labels_v0.manifest.json';m=json.loads(path.read_text())
    for f,h in m['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('frozen source changed')
    catalog=catalog_for_workspace(ROOT);cases=[]
    for seed in range(15000000,15000200):
        for domain in ('standard','appearance_shift'):
            original,pose=render(seed,catalog,domain=domain)
            image,label,mask=render_landmarks(seed,catalog,domain=domain)
            equal=image.tobytes()==original.tobytes() and list(pose)==label['pose']
            cases.append(dict(seed=seed,domain=domain,pixels_and_pose_equal=equal,
                image_sha256=hashlib.sha256(image.tobytes()).hexdigest(),mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest(),label=label))
    landmarks=[p for c in cases for p in c['label']['landmarks']]
    report=dict(manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),scope='SYNTHETIC_LABEL_FOUNDATION',
        cases=cases,images=len(cases),pixel_mismatches=sum(not c['pixels_and_pose_equal'] for c in cases),
        landmarks=len(landmarks),fully_unoccluded=sum(p['unoccluded_fraction']==1 for p in landmarks),
        partially_occluded=sum(0<p['unoccluded_fraction']<1 for p in landmarks),fully_occluded=sum(p['unoccluded_fraction']==0 for p in landmarks),
        parameter_count=sum(p.numel() for p in KeyboardLandmarkNet().parameters()),model_trained=False,
        hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Known renderer geometry, not measured physical corners; foreground-mask visibility only',
                    'No photograph/challenge masks or calibrated visibility confidence; duplicated renderer pinned by hashes',
                    'Architecture untrained; no localization accuracy, latency or generalization claim'])
    (AI/'eval/landmark_labels_v0_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))


if __name__=='__main__':run()
