"""Offline chronological response-model comparison; no deployable correction."""
import json
import math
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.coordinated_trace_review import review_coordinated_trace
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export

SOURCES=(
    'wizard-20260917T182619277841Z-90592a21fcd14c78be0a319d0bdc6038',
    'wizard-20260917T183047269334Z-94f355c5112a48cfae9ac624121a1637',
    'wizard-20260917T201014338834Z-fe2b6eb0afe14b93901dfbaedc4e1ccf',
    'wizard-20260917T201423927986Z-2d8334fcc06a430eb158652560d12a63',
)


def compare_response(rows):
    """Fit only older pair; score newer pair without refitting or inverse commands."""
    if len(rows)!=4:raise ValueError('Two training and two held-out records required')
    output=[]
    for joint in ('elbow','wrist_pitch'):
        points=[(r[joint]['requested_delta_deg'],r[joint]['reported_delta_deg']) for r in rows]
        if any(not math.isfinite(v) for p in points for v in p):raise ValueError('Finite response data required')
        (x0,y0),(x1,y1)=points[:2]
        if abs(x1-x0)<360/4096:raise ValueError('Insufficient command separation')
        slope=(y1-y0)/(x1-x0);intercept=y0-slope*x0
        bias=((y0-x0)+(y1-x1))/2
        scores=[]
        for index,(x,y) in enumerate(points[2:],2):
            scores.append(dict(source=rows[index]['source'],command_delta_deg=x,observed_delta_deg=y,
                additive_prediction_deg=x+bias,affine_prediction_deg=slope*x+intercept,
                additive_error_deg=x+bias-y,affine_error_deg=slope*x+intercept-y,
                inside_training_command_range=min(x0,x1)<=x<=max(x0,x1)))
        output.append(dict(joint=joint,slope=slope,intercept_deg=intercept,bias_deg=bias,
            held_out=scores,additive_max_error_deg=max(abs(s['additive_error_deg']) for s in scores),
            affine_max_error_deg=max(abs(s['affine_error_deg']) for s in scores)))
    return output


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve();rows=[]
    for source in SOURCES:
        report,digest=_read(root,source,'attachment-cartesian-trial.json')
        run=report['run'];tx=run['transaction'];review=review_coordinated_trace(report)
        if run.get('error') is not None or run.get('acknowledgment_received') is not True or review['feedback_failures']:
            raise ValueError('Uncertain source cannot enter comparison')
        if tx['command'].get('T')!=104 or tx['command'].get('spd')!=.05:
            raise ValueError('Comparable coordinated command family required')
        row=dict(source=source,sha256=digest,start_joints_rad=tx['baseline_joints'],
            endpoint_status=report['status'],desired_endpoint_result=tx.get('desired_endpoint_result'))
        for index,name in ((2,'elbow'),(3,'wrist_pitch')):
            j=review['joints'][index]
            if (j['unchanged_tail_s'] or 0)<1 or j['requested_delta_deg']*j['reported_delta_deg']<=0:
                raise ValueError('Settled same-direction response required')
            row[name]={k:j[k] for k in ('requested_delta_deg','reported_delta_deg','residual_deg')}
        rows.append(row)
    comparisons=compare_response(rows)
    result=dict(schema='rocell.coordinated_response_comparison.v1',rows=rows,comparisons=comparisons,
        training_sources=list(SOURCES[:2]),held_out_sources=list(SOURCES[2:]),
        motion_authorized=False,compensation_deployed=False,physical_accuracy_verified=False,
        limitations=['Four observations only; differing starting postures and prior motion histories confound command-size effects.',
            'Predicts reported response to recorded commands; does not prove accuracy of unexecuted inverse corrections.',
            'Two-point affine training fit is exact by construction, not validation.',
            'No extrapolated command or reverse-direction model is authorized.'])
    lines=['# Coordinated response comparison','',
        'Offline chronological split: fit older two trials, score newer two. No hardware access or correction deployment.','',
        '| Joint | Offset max prediction error (deg) | Affine max prediction error (deg) |',
        '|---|---:|---:|']
    for c in comparisons:lines.append(f"| {c['joint']} | {c['additive_max_error_deg']:.6f} | {c['affine_max_error_deg']:.6f} |")
    lines+=['','These are reported-angle prediction errors, not measured tip errors or corrected-motion outcomes.','',*result['limitations']]
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-response-comparison'},[],attachments={
        'response-comparison.json':json.dumps(result,allow_nan=False).encode(),
        'response-comparison.md':'\n'.join(lines).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],comparisons=comparisons)))


if __name__=='__main__':main()
