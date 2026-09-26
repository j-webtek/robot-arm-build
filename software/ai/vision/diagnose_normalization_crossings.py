"""Post-hoc crossing diagnosis on retained development evidence; no new rule."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
from PIL import Image,ImageDraw
from vision.synthetic_keyboard import render,catalog_for_workspace
from vision.evaluate_lighting_normalization import normalize


def transition(before,after):
    return ('new_failure' if after>3 else 'stable_pass') if before<=3 else ('persistent_failure' if after>3 else 'recovered')


def run():
    path=AI/'eval/normalization_crossings_v0.manifest.json';m=json.loads(path.read_text())
    for f,h in m['file_sha256'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=h:raise ValueError('frozen input changed')
    source=json.loads((ROOT/m['scorecard']).read_text());summary={};details=[]
    catalog=catalog_for_workspace(ROOT)
    for condition in source['summaries']:
        rows=[c for c in source['cases'] if c['condition']==condition]
        groups={k:[] for k in ('stable_pass','new_failure','persistent_failure','recovered')}
        for c in rows:
            label=transition(c['arms']['control']['maximum_mm'],c['arms']['normalized']['maximum_mm'])
            groups[label].append(c)
            if condition=='appearance_shift' and label!='stable_pass':
                image,_=render(c['seed'],catalog,domain=condition);image=image.resize((128,96));fixed,gain=normalize(image)
                assert abs(gain-c['gain'])<1e-12
                pixels=np.asarray(image,dtype=np.float32);post=np.asarray(fixed,dtype=np.float32)
                details.append(dict(seed=c['seed'],transition=label,gain=gain,arms=c['arms'],
                    input_sha256=hashlib.sha256(image.tobytes()).hexdigest(),normalized_sha256=hashlib.sha256(fixed.tobytes()).hexdigest(),
                    input_mean=float(pixels.mean()),output_mean=float(post.mean()),
                    input_saturated_fraction=float(np.mean(pixels>=255)),output_saturated_fraction=float(np.mean(post>=255))))
        summary[condition]={label:dict(count=len(cases),seeds=[c['seed'] for c in cases],
            gain_min=min((c['gain'] for c in cases),default=None),gain_max=max((c['gain'] for c in cases),default=None)) for label,cases in groups.items()}
    output=AI/'results/normalization_crossings_v0';output.mkdir(parents=True,exist_ok=True)
    sheet=Image.new('RGB',(700,max(1,len(details))*235),'white');draw=ImageDraw.Draw(sheet)
    for i,c in enumerate(details):
        image,_=render(c['seed'],catalog,domain='appearance_shift');image=image.resize((128,96));fixed,_=normalize(image)
        y=i*235
        draw.text((8,y+4),f"Seed {c['seed']} | {c['transition']} | gain {c['gain']:.3f}",fill='black')
        for x,arm,pic in [(8,'control',image),(350,'normalized',fixed)]:
            sheet.paste(pic.resize((256,192)),(x,y+38))
            draw.text((x,y+20),f"{arm}: max {c['arms'][arm]['maximum_mm']:.3f} mm",fill='black')
    sheet.save(output/'appearance_crossings.png')
    report=dict(scope='POST_HOC_DEVELOPMENT_DIAGNOSTIC',manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        transitions=summary,appearance_details=details,contact_sheet_sha256=hashlib.sha256((output/'appearance_crossings.png').read_bytes()).hexdigest(),
        hardware_writes=0,physical_movements=0,qualification_installed=False,
        limitations=['Post-hoc grouping by known synthetic error is diagnostic only, never an inference-time gate',
                    'Threshold3mm is inherited from prior study; no new thresholds or parameters selected',
                    'Images show synthetic input appearance, not true camera failures; associations do not prove cause'])
    (AI/'eval/normalization_crossings_v0_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(transitions={k:{t:v['count'] for t,v in g.items()} for k,g in summary.items()},details=details),indent=2))


if __name__=='__main__':run()
