"""Finite offline feasibility scan; no candidate admission or model refitting."""
import itertools
import json
import math
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.coordinated_affine_trial import supported_inverse
from rocell.application.asynchronous_response_review import review_response_envelope
from rocell.application.wrist_tip_review import modeled_tip
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export
from rocell.geometry import UrdfModel


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    analysis_id='wizard-20260917T201603834704Z-6d84f5b22d7d46829d1471bf7867c04c'
    observed_id='wizard-20260917T202055447509Z-0997b263015e431e838d73b237b36d0e'
    analysis,ah=_read(root,analysis_id,'attachment-response-comparison.json')
    observed,oh=_read(root,observed_id,'attachment-result-7bb883a53a7a4724907c9a004304378e.json')
    samples=observed['steps'][0]['report']['samples'];last=samples[-1]
    q=[last['joints_rad'][k] for k in ('b','s','e','t','r','g')]
    model=UrdfModel.from_file(Path(__file__).resolve().parents[1]/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    origin=modeled_tip(model,q);rows=[]
    for fractions in itertools.product((.1,.3,.5,.7,.9),repeat=2):
        desired=list(q);wire=list(q)
        for c,index,f in zip(analysis['comparisons'],(2,3),fractions):
            bounds=sorted(r[c['joint']]['reported_delta_deg'] for r in analysis['rows'][:2])
            delta=bounds[0]+f*(bounds[1]-bounds[0])
            wire_delta=supported_inverse(c,analysis['rows'][:2],delta)
            desired[index]+=math.radians(delta);wire[index]+=math.radians(wire_delta)
        tip=modeled_tip(model,desired);delta=[b-a for a,b in zip(origin,tip)]
        stress=review_response_envelope(model,q,desired,extra_steps=1)
        lateral=math.hypot(*delta[:2]);vertical=abs(delta[2]+2)
        rows.append(dict(response_fractions=list(fractions),desired_joints_rad=desired,wire_joints_rad=wire,
            predicted_tip_delta_mm=delta,lateral_drift_mm=lateral,vertical_press_error_mm=vertical,
            asynchronous_max_displacement_mm=stress['maximum_sampled_tip_displacement_mm'],
            sampled_stress_pass=stress['status']=='NO_SAMPLED_EXCEEDANCE',
            vertical_geometry_pass=lateral<=.05 and vertical<=.02))
    feasible=[r for r in rows if r['sampled_stress_pass']]
    result=dict(schema='rocell.coordinated_domain_scan.v1',analysis_export=analysis_id,analysis_sha256=ah,
        posture_export=observed_id,posture_sha256=oh,baseline_joints_rad=q,rows=rows,
        sampled_count=len(rows),sampled_stress_pass_count=len(feasible),
        sampled_vertical_pass_count=sum(r['sampled_stress_pass'] and r['vertical_geometry_pass'] for r in rows),
        best_sampled_press_error_mm=min(math.hypot(r['lateral_drift_mm'],r['vertical_press_error_mm']) for r in rows),
        motion_authorized=False,model_validated=False,
        limitations=['Finite sampled search does not prove continuous infeasibility.',
            'This model failed its prospective test; predicted geometry is not validated actual motion.',
            'Passing the one-step stress scenario is not a verified actuator-error or clearance bound.'])
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-domain-feasibility'},[],attachments={
        'domain-scan.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],summary={k:v for k,v in result.items() if k!='rows'})))


if __name__=='__main__':main()
