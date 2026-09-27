"""Synthetic scene audit; visual figures and geometry diagnostics only."""
import hashlib,json,math,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1];sys.path[:0]=[str(AI),str(AI.parent/'src')]
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image,ImageDraw
from vision.landmark_occlusions import render_controlled
from vision.synthetic_keyboard import catalog_for_workspace
from vision.evaluate_dark_only_normalization import normalize


def run():
    p=AI/'eval/persistent_visual_v0_plan.json';plan=json.loads(p.read_text())
    for f,h in plan['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    out=AI/'eval/persistent_visual_v0_report.json'
    if out.exists():raise FileExistsError(out)
    source=json.loads((AI/'eval/persistent_pose_v0_report.json').read_text());catalog=catalog_for_workspace(ROOT);scenes={}
    for row in source['rows']:
        image,label,mask=render_controlled(row['seed'],catalog,row['condition'],'ellipse');image,_=normalize(image)
        pose=label['pose'];corners=np.array([[v['x_px'],v['y_px']] for v in label['landmarks']]);polygon=Image.new('L',(256,192));ImageDraw.Draw(polygon).polygon([tuple(v) for v in corners],fill=255)
        inside=np.asarray(polygon)>0;occluded=np.asarray(mask)>0
        expected=[]
        for x,y in [(-157.5,-73.5),(157.5,-73.5),(157.5,73.5),(-157.5,73.5)]:
            expected.append([(pose[0]+math.cos(pose[2])*x-math.sin(pose[2])*y)*256/610,(pose[1]+math.sin(pose[2])*x+math.cos(pose[2])*y)*192/457])
        info=dict(seed=row['seed'],condition=row['condition'],pose=pose,normalized_pose=[(pose[0]-235)/30,(pose[1]-154)/24,(pose[2]-math.pi)/math.radians(11)],
            corner_min_margin_px=float(min(corners[:,0].min(),corners[:,1].min(),255-corners[:,0].max(),191-corners[:,1].max())),
            foreground_fraction=float((inside&occluded).sum()/inside.sum()),unoccluded_corners=sum(v['unoccluded_fraction']>=.5 for v in label['landmarks']),label_projection_max_delta_px=float(np.abs(corners-np.array(expected)).max()),pixels_sha256=hashlib.sha256(image.tobytes()).hexdigest())
        scenes[(row['seed'],row['condition'])]=(image,info,corners)
    pairs=[]
    for row in source['rows']:
        if row['trained_failure_count']!=6:continue
        key=(row['seed'],row['condition']);a=scenes[key][1]
        candidates=[r for r in source['rows'] if r['condition']==row['condition'] and r['trained_failure_count']==0]
        nearest=min(candidates,key=lambda r:(sum((x-y)**2 for x,y in zip(a['normalized_pose'],scenes[(r['seed'],r['condition'])][1]['normalized_pose'])),r['seed']))
        b=scenes[(nearest['seed'],nearest['condition'])][1];pairs.append(dict(failure=a,success=b))
    figures=[]
    for start in range(0,len(pairs),5):
        batch=pairs[start:start+5];fig,axes=plt.subplots(len(batch),2,figsize=(9,2.6*len(batch)),squeeze=False)
        for i,pair in enumerate(batch):
            for j,kind in enumerate(['failure','success']):
                info=pair[kind];image,_,corners=scenes[(info['seed'],info['condition'])];ax=axes[i,j];ax.imshow(image);closed=np.vstack([corners,corners[0]]);ax.plot(closed[:,0],closed[:,1],color='lime',lw=.6);ax.set_title(f"{kind} {info['seed']} {info['condition']}\nmask {info['foreground_fraction']:.1%}; corners {info['unoccluded_corners']}/4",fontsize=9);ax.axis('off')
        fig.tight_layout();path=AI/f'eval/persistent_visual_v0_page_{start//5+1}.png';fig.savefig(path,dpi=110);plt.close(fig);figures.append(dict(path=str(path.relative_to(ROOT)).replace('\\','/'),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    summaries={kind:dict(count=len(pairs),cropped=sum(p[kind]['corner_min_margin_px']<0 for p in pairs),foreground_mean=float(np.mean([p[kind]['foreground_fraction'] for p in pairs])),fewer_than3_corners=sum(p[kind]['unoccluded_corners']<3 for p in pairs),pose_extreme=sum(max(abs(v) for v in p[kind]['normalized_pose'])>.9 for p in pairs),projection_max_delta_px=max(p[kind]['label_projection_max_delta_px'] for p in pairs)) for kind in ['failure','success']}
    report=dict(plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),pairs=pairs,summaries=summaries,figures=figures,hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Controls matched by normalized true pose within condition,with replacement; not randomized causal evidence','Foreground mask measures geometric overlay only,not perceptual visibility','Vector projection check cannot qualify physical labels or raster edge accuracy','Repeated synthetic development; no training or runtime exclusions'])
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summaries,indent=2))
if __name__=='__main__':run()
