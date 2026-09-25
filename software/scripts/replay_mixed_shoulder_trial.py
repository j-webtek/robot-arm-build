"""Replay verified historical capture and synthetic outcomes; no device access."""
import argparse
import base64
from dataclasses import replace
import json
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.hold_record_replay import _snapshot
from rocell.application.mixed_shoulder_trial import MixedShoulderTrial
from rocell.application.pose_observation_export import replay_pose_observation
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture_export')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]/'runs/wizard-exports'
    replay=replay_pose_observation(root,args.capture_export)
    if replay['assessment']['category']!='STABLE_SAMPLED_POSE':
        raise ValueError('Stable validated historical capture required')
    bundle,_=_read(root,args.capture_export,'attachment-pose-raw.json')
    records=[json.loads(base64.b64decode(r['raw_base64'])) for r in bundle['responses']]
    first,last=_snapshot(records[0]),_snapshot(records[2])
    cases=[]
    for torque in (0,1):
        trial=MixedShoulderTrial(first)
        command=trial.propose(last,now_us=last.finished_us+1)
        scans=[]
        for i in range(3):
            joints=list(last.joints)
            j=command['servo_id']-11
            joints[j]=replace(joints[j],goal=command['target'],torque=torque)
            start=last.finished_us+100000*(i+1)
            scans.append(replace(last,started_us=start,finished_us=start+10000,joints=tuple(joints)))
        cases.append(dict(origin='SIMULATION',assumed_selected_torque=torque,
                          result=trial.assess(scans,delivery_confirmed=True)))
    report=dict(schema='rocell.mixed_shoulder_replay.v1',source_export=args.capture_export,
        source_sha256=replay['raw_bundle_sha256'],source_origin=bundle['origin'],
        historical_replay=True,live_freshness_established=False,hardware_access=False,
        progression_authority=False,proposal=command,synthetic_cases=cases)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-mixed-shoulder-replay'},[],
        attachments={'mixed-shoulder-replay.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid replay export')
    print(json.dumps(dict(export_path=saved['path'],**report)))


if __name__=='__main__':main()
