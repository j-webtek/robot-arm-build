"""Retain raw pose records and reproduce assessments without controller access."""
import base64
import hashlib
from pathlib import Path

from .first_motion_contract import canonical
from .pose_observation_review import assess_pose_observation
from .product_ghost_export_review import _read
from .servo_diagnostic_contract import _identifier
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter


def _assess(bundle):
    if (set(bundle)!={'schema','subject','origin','responses'} or
            bundle['schema']!='rocell.pose_observation_raw.v1' or
            bundle['origin'] not in ('SIMULATION','DEVICE_CAPTURE')):
        raise ValueError('Unsupported pose evidence bundle')
    subject=bundle['subject']
    if set(subject)!={'expected_boot','expected_id'}: raise ValueError('Invalid subject')
    for value in subject.values(): _identifier(value)
    if type(bundle['responses']) is not list or len(bundle['responses'])>4:
        raise ValueError('Pose response budget')
    records=[]
    for i,row in enumerate(bundle['responses']):
        if set(row)!={'index','raw_base64','sha256'} or type(row['index']) is not int or row['index']!=i:
            raise ValueError('Response index mismatch')
        if type(row['raw_base64']) is not str or len(row['raw_base64'])>5464:
            raise ValueError('Response byte budget')
        raw=base64.b64decode(row['raw_base64'],validate=True)
        if base64.b64encode(raw).decode()!=row['raw_base64'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:
            raise ValueError('Response bytes changed')
        try:
            records.append(decode_diagnostic_json(raw,maximum=4095))
        except (ValueError,UnicodeError):
            # Retain malformed device bytes too; they must never become a
            # successful observation, but are valuable diagnostic evidence.
            records.append({})
    return dict(assess_pose_observation(records,**subject),origin=bundle['origin'])


def export_pose_observation(root, raw_records, *, expected_boot, expected_id, origin):
    if type(raw_records) is not list or len(raw_records)>4 or any(type(r) is not bytes or len(r)>4095 for r in raw_records):
        raise ValueError('Bounded raw records required')
    bundle=dict(schema='rocell.pose_observation_raw.v1',origin=origin,
        subject=dict(expected_boot=expected_boot,expected_id=expected_id),
        responses=[dict(index=i,raw_base64=base64.b64encode(raw).decode(),
            sha256=hashlib.sha256(raw).hexdigest()) for i,raw in enumerate(raw_records)])
    assessment=_assess(bundle)
    exporter=WizardDiagnosticExporter(Path(root));exporter.prepare(create=True)
    saved=exporter.export({'mode':'pose-observation'},[],attachments={
        'pose-raw.json':canonical(bundle),'pose-assessment.json':canonical(assessment)})
    replay=replay_pose_observation(root,Path(saved['path']).name)
    return dict(export_path=saved['path'],**replay)


def replay_pose_observation(root, export_id):
    bundle,digest=_read(Path(root),export_id,'attachment-pose-raw.json')
    assessment,_=_read(Path(root),export_id,'attachment-pose-assessment.json')
    rebuilt=_assess(bundle)
    if canonical(rebuilt)!=canonical(assessment): raise ValueError('Pose assessment does not replay')
    return dict(assessment=rebuilt,raw_bundle_sha256=digest,replay_verified=True,
                progression_authority=False)
