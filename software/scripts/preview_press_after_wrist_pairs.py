"""Offline typing-relevant joint demands from the verified repeated wrist pair."""
import json
import math
from pathlib import Path
from rocell.geometry import UrdfModel
from rocell.application.product_ghost_export_review import _read
from rocell.application.identification_endpoint import verified_identification_endpoint
from rocell.application.local_tip_cycle import preview_local_tip_cycle
from rocell.application.asynchronous_response_review import review_response_envelope
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    source='wizard-20260917T211014935627Z-2274705df5384aa79452b858c4f7ddb7'
    report,digest=_read(root,source,'attachment-all-joint-trial.json')
    model=UrdfModel.from_file(Path(__file__).resolve().parents[1]/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    endpoint=verified_identification_endpoint(report,model);start=endpoint['joints_rad']
    cycle=preview_local_tip_cycle(model,start)
    if cycle['status']!='LOCAL_TIP_REFERENCE_PASS_NOT_EXECUTABLE':raise ValueError('Local press IK failed')
    target=cycle['waypoints'][4]['joints_rad']
    isolated=list(start);isolated[2]=target[2]
    result=dict(source_export=source,source_sha256=digest,endpoint=endpoint,cycle=cycle,
        desired_joint_changes_deg=[math.degrees(b-a) for a,b in zip(start,target)],
        isolated_elbow_target_rad=target[2],
        isolated_elbow_preview=review_response_envelope(model,start,isolated,extra_steps=1),
        coordinated_preview=review_response_envelope(model,start,target,extra_steps=1),
        motion_authorized=False,compensation_applied=False,
        limitation='Geometric demand only; wrist evidence does not qualify elbow response or coordinated dynamics.')
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-press-demand-after-wrist-pairs'},[],attachments={
        'press-demands.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']))['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],review={k:v for k,v in result.items() if k!='cycle'})))


if __name__=='__main__':main()
