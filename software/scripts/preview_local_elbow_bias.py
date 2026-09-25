"""Freeze a local increasing-elbow bias candidate; no controller access."""
import json
from pathlib import Path
from rocell.geometry import UrdfModel
from rocell.application.product_ghost_export_review import _read
from rocell.application.wrist_command_comparison import summarize_joint_trial
from rocell.application.local_elbow_bias_candidate import build_candidate
from rocell.safety.wifi_all_joint_reservation import verify_sample
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    ids=['wizard-20260917T211417782591Z-7a6acfc727ba4e6395a14ae328c02760',
         'wizard-20260917T211830530621Z-37561f57a5134b439898e3cc7fcc7bbb']
    trials=[];sources=[]
    for source in ids:
        report,digest=_read(root,source,'attachment-all-joint-trial.json');tx=report['transaction']
        if not report['acknowledgment_received'] or tx['reason']!='FEEDBACK_OR_COMPLETION_WINDOW_EXHAUSTED':
            raise ValueError('Clean endpoint-failure identification record required')
        rows=tx['rows']
        for row in rows:verify_sample(row['raw_feedback'])
        tail=[]
        for row in reversed(rows):
            if row['reported_joints_rad']!=rows[-1]['reported_joints_rad']:break
            tail.append(row)
        if len(tail)<3 or tail[0]['observed_s']-tail[-1]['observed_s']<2:
            raise ValueError('Stable identification response required')
        trials.append(summarize_joint_trial(report,joint=3));sources.append(dict(export=source,sha256=digest))
    model=UrdfModel.from_file(Path(__file__).resolve().parents[1]/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    result=dict(candidate=build_candidate(model,trials),sources=sources,
        limitation='Two local samples support a hypothesis only; held-out validation required. Not a global elbow model.')
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-local-elbow-bias'},[],attachments={
        'local-elbow-bias.json':json.dumps(result,allow_nan=False).encode()})
    if not verify_export(Path(receipt['path']))['valid']:raise ValueError('Invalid export')
    print(json.dumps(dict(export=receipt['path'],review=result)))


if __name__=='__main__':main()
