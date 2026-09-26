"""Post-hoc retained calibration diagnosis; no evaluation scoring or new gate."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
from PIL import Image,ImageDraw,ImageEnhance
from vision.synthetic_keyboard import render,catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize
from vision.evaluate_pose_challenge import _alter


def run():
    path=AI/'eval/stable_errors_v0.manifest.json';m=json.loads(path.read_text())
    for f,h in m['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('frozen source changed')
    # Source contains evaluation evidence; only fitting_cases is selected for analysis.
    cases=json.loads((ROOT/m['source']).read_text())['fitting_cases']
    low=[c for c in cases if c['bin']==0];bad=[c for c in low if c['maximum_error_mm']>3]
    catalog=catalog_for_workspace(ROOT);details=[]
    for c in bad:
        pred,truth=c['predicted_pose'],c['truth_pose']
        details.append(dict(seed=c['seed'],condition=c['condition'],maximum_error_mm=c['maximum_error_mm'],
            disagreement_mm=c['disagreement_mm'],center_error_mm=math.dist(pred[:2],truth[:2]),
            yaw_error_degrees=abs(math.degrees(pred[2]-truth[2])),truth_pose=truth,predicted_pose=pred))
    # One representative per seed avoids spending the montage on correlated views.
    selected=[];seen=set()
    for c in sorted(details,key=lambda c:(-c['maximum_error_mm'],c['seed'],c['condition'])):
        if c['seed'] not in seen:selected.append(c);seen.add(c['seed'])
        if len(selected)==12:break
    out=AI/'results/stable_errors_v0';out.mkdir(parents=True,exist_ok=True)
    sheet=Image.new('RGB',(960,math.ceil(len(selected)/3)*250),'white');draw=ImageDraw.Draw(sheet)
    for i,c in enumerate(selected):
        image,_=render(c['seed'],catalog,domain='appearance_shift' if c['condition']=='appearance_shift' else 'standard')
        if c['condition']=='challenge':image=_alter(image,c['seed'])
        image=image.resize((128,96))
        if c['condition'] in m['brightness_factors']:image=ImageEnhance.Brightness(image).enhance(m['brightness_factors'][c['condition']])
        image,_=normalize(image)
        c['normalized_pixels_sha256']=hashlib.sha256(image.tobytes()).hexdigest()
        x=(i%3)*320;y=(i//3)*250
        draw.text((x+5,y+4),f"{c['seed']} {c['condition']}",fill='black')
        draw.text((x+5,y+18),f"max {c['maximum_error_mm']:.2f} / shift {c['center_error_mm']:.2f} mm",fill='black')
        draw.text((x+5,y+32),f"yaw {c['yaw_error_degrees']:.2f} deg / disagreement {c['disagreement_mm']:.2f}",fill='black')
        sheet.paste(image.resize((256,192)),(x+5,y+50))
    sheet.save(out/'stable_errors.png')
    summaries={}
    for condition in m['conditions']:
        rows=[r for r in low if r['condition']==condition];fail=[r for r in details if r['condition']==condition]
        summaries[condition]=dict(low_disagreement_images=len(rows),above_3mm=len(fail),fraction=len(fail)/len(rows) if rows else None,
            center_mean_mm=float(np.mean([r['center_error_mm'] for r in fail])) if fail else None,
            yaw_mean_degrees=float(np.mean([r['yaw_error_degrees'] for r in fail])) if fail else None)
    report=dict(scope='POST_HOC_CALIBRATION_DIAGNOSTIC',manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        calibration_images=len(cases),low_disagreement_images=len(low),above_3mm_images=len(bad),above_3mm_seed_groups=len({r['seed'] for r in bad}),
        summaries=summaries,details=details,selected_images=selected,contact_sheet_sha256=hashlib.sha256((out/'stable_errors.png').read_bytes()).hexdigest(),
        hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Retained24M calibration only; source container also includes25M records but no evaluation metrics are read or used',
                    'Selection uses known synthetic error for diagnosis only; not an inference-time gate',
                    'Qualitative image associations do not establish causes or real arm/camera behavior'])
    (AI/'eval/stable_errors_v0_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('low_disagreement_images','above_3mm_images','above_3mm_seed_groups','summaries')},indent=2))


if __name__=='__main__':run()
