"""Offline comparison of retained pre/post-r19 snapshots. No hardware access."""
import base64
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.hold_record_replay import _snapshot
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root=Path(__file__).resolve().parents[1]/'runs/wizard-exports'
    sources=[
        ('forward','wizard-20260919T122458244741Z-9b5a28f3770a4b8593c0ef6851b12cf7','attachment-observed-pair-forward.json'),
        ('return','wizard-20260919T122507135457Z-e2d89bf807aa4c6ea4836a10a05db5e7','attachment-observed-pair-return.json'),
        ('recovery','wizard-20260919T133346177163Z-d82078c8739845daa3260dac030ae548','attachment-six_count_recovery-transport.json')]
    history=[]
    for label,ident,name in sources:
        value,digest=_read(root,ident,name)
        records=[]
        if label=='recovery':
            records=value['summary']['records']
        else:
            for response in value['responses']:
                raw=base64.b64decode(response['raw_base64'],validate=True)
                if hashlib.sha256(raw).hexdigest()!=response['sha256']:
                    raise ValueError('Response hash changed')
                envelope=json.loads(raw)
                if 'raw_json' in envelope: records.append(json.loads(envelope['raw_json']))
        scans=[]
        for record in records:
            if not record['schema'].endswith('_snapshot.v1'): continue
            fields={k:v for k,v in record.items() if k not in ('plan_sha256','policy_sha256')}
            scan=_snapshot(fields)
            scans.append(dict(boot=record['boot_id'],index=record['snapshot_index'],
                joints=[asdict(j) for j in scan.joints]))
        if not scans: raise ValueError('No validated snapshots')
        joints=[]
        for index in range(7):
            rows=[s['joints'][index] for s in scans]
            joints.append(dict(servo_id=index+11,first=rows[0],last=rows[-1],
                minimum_position=min(r['position'] for r in rows),
                maximum_position=max(r['position'] for r in rows)))
        history.append(dict(label=label,export_id=ident,source_sha256=digest,
            boot=scans[0]['boot'],snapshot_count=len(scans),joints=joints))
    earlier=history[1]['joints'];latest=history[2]['joints']
    shoulder=dict(servo_ids=[12,13],
        earlier_positions=[earlier[i]['last']['position'] for i in (1,2)],
        latest_positions=[latest[i]['last']['position'] for i in (1,2)],
        deltas=[latest[i]['last']['position']-earlier[i]['last']['position'] for i in (1,2)])
    shoulder['earlier_sum']=sum(shoulder['earlier_positions'])
    shoulder['latest_sum']=sum(shoulder['latest_positions'])
    report=dict(schema='rocell.recovery_pose_history.v1',history=history,shoulder_comparison=shoulder,
        hardware_access=False,motion_authorized=False,cause_established=False,
        observation_gap_unmeasured=True)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-recovery-pose-history'},[],
        attachments={'pose-history.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']: raise ValueError('Export verification failed')
    print(json.dumps(dict(export_path=saved['path'],**report)))


if __name__=='__main__': main()
