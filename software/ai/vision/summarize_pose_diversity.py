"""Aggregate all preregistered anchor runs without seed selection."""
import hashlib,json
from pathlib import Path
import numpy as np
AI=Path(__file__).resolve().parents[1]


def summarize(reports):
    summary={}
    for arm in ['baseline','control','occlusion']:
        summary[arm]={}
        for c in ['standard','appearance_shift','partial','full']:
            summary[arm][c]={}
            for metric in ['mean_mm','tail','yaw_p95']:
                values=[r['results'][arm]['summaries'][c][metric] for r in reports]
                summary[arm][c][metric]=dict(values=values,mean=float(np.mean(values)),minimum=min(values),maximum=max(values))
    return summary


def run():
    paths=[AI/f'eval/pose_diversity_{s}_report.json' for s in (260926,260927,260928)]
    reports=[json.loads(p.read_text()) for p in paths]
    summary=summarize(reports)
    result=dict(seeds=[260926,260927,260928],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},summaries=summary,
        full_passes=[r['passed'] for r in reports],baseline_passes=[all(all(v.values()) if isinstance(v,dict) else v for v in r['checks']['baseline'].values()) for r in reports],
        hardware_writes=0,physical_movements=0,qualification_installed=False,limitations=['Three training seeds on the same reused development images; no independent data replication','Range is descriptive,not a confidence interval; no winning seed selected'])
    output=AI/'eval/pose_diversity_v0_report.json'
    if output.exists():raise FileExistsError(output)
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(full_passes=result['full_passes'],baseline_passes=result['baseline_passes'],tail_totals={a:[sum(r['results'][a]['summaries'][c]['tail'] for c in r['results'][a]['summaries']) for r in reports] for a in summary},appearance_means={a:summary[a]['appearance_shift']['mean_mm'] for a in summary}),indent=2))
if __name__=='__main__':run()
