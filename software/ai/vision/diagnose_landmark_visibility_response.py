"""Paired synthetic occlusion response; no new training or runtime authority."""
import hashlib,json
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1]

def summarize(cases):
    groups={}
    for row in cases:groups.setdefault(row['seed'],{})[row['condition']]=row
    rows=[]
    for seed,g in sorted(groups.items()):
        a,b=g['standard'],g['full'];k=seed%4
        if a['visibility_targets'][k]!=1 or b['visibility_targets'][k]!=0:continue
        # Only compare untouched corners whose geometric labels remain clear.
        peers=[j for j in range(4) if j!=k and a['visibility_targets'][j]==b['visibility_targets'][j]==1]
        if not peers:continue
        drop=[x-y for x,y in zip(a['visibility_probabilities'],b['visibility_probabilities'])]
        peer=float(np.mean([drop[j] for j in peers]))
        rows.append(dict(seed=seed,corner=k,target_drop=drop[k],peer_drop=peer,selectivity=drop[k]-peer,
                         threshold_crossed=a['visibility_probabilities'][k]>=.5>b['visibility_probabilities'][k]))
    return dict(pairs=len(rows),target_drop_mean=float(np.mean([r['target_drop'] for r in rows])),
                peer_drop_mean=float(np.mean([r['peer_drop'] for r in rows])),
                selectivity_mean=float(np.mean([r['selectivity'] for r in rows])),
                positive_selectivity=sum(r['selectivity']>0 for r in rows),
                threshold_crossings=sum(r['threshold_crossed'] for r in rows),rows=rows)

def main():
    plan_path=AI/'vision/landmark_visibility_response_plan.json';plan=json.loads(plan_path.read_text())
    results={}
    for name,item in plan['inputs'].items():
        path=AI/item['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
        results[name]=summarize(json.loads(path.read_text())['cases'])
    report=dict(plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),results=results,
                hardware_writes=0,physical_movements=0,qualification_installed=False,
                limitations=plan['limitations'])
    out=AI/'eval/landmark_visibility_response.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:{a:b for a,b in v.items() if a!='rows'} for k,v in results.items()},indent=2))
if __name__=='__main__':main()
