"""Collect verified elbow evidence offline; no device access or outbound upload."""
import json
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.joint_response_diagnosis import diagnose_joint_response
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export

SOURCES=(
    'wizard-20260917T184148463017Z-fc3474830b1d4836b6df550bad581717',
    'wizard-20260917T193314387752Z-d975fcaf16c34888a2ab6f69bce92c81',
    'wizard-20260917T193723231482Z-4f2c92274eb740ea8b8007d588c8a64b',
    'wizard-20260917T194218360472Z-ab9990310e9141fe8cdef162b3bac6d0')


def main():
    root=(Path(__file__).resolve().parents[1]/'runs/wizard-exports').resolve()
    rows=[];attachments={}
    for index,source in enumerate(SOURCES):
        report,digest=_read(root,source,'attachment-cartesian-trial.json')
        tx=report['run']['transaction'];diagnosis=diagnose_joint_response(report)
        rows.append(dict(source_export=source,source_attachment_sha256=digest,
            command=tx['command'],baseline=tx['baseline_joints'],final=tx['rows'][-1][3],
            diagnosis=diagnosis))
        # Retain complete originals, separately, instead of one deeply nested blob.
        attachments[f'trial-{index+1}.json']=json.dumps(report,allow_nan=False).encode()
    summary=dict(schema='rocell.elbow_diagnostic_bundle.v1',trials=rows,
        motion_authorized=False,physical_cause_identified=False,
        next_dependency='Independent observation or verified per-servo acquisition/status evidence',
        no_response_must_not_train_inverse_map=True)
    attachments['elbow-diagnosis.json']=json.dumps(summary,allow_nan=False).encode()
    lines=['# Elbow diagnostic bundle','',
        'Read-only evidence assembly. No movement, settings change, or support upload performed.','',
        '| Trial | Speed | Requested delta (rad) | Reported delta (rad) | Classification |',
        '| --- | ---: | ---: | ---: | --- |']
    for index,row in enumerate(rows):
        d=row['diagnosis']
        lines.append(f"| {index+1} | {row['command']['spd']} | {d['requested_delta_rad']:.9f} | {d['reported_final_delta_rad']:.9f} | {d['classification']} |")
    lines.extend(['','Original source hashes are in elbow-diagnosis.json; full retained reports are in trial-N.json.',
        'Matching or changing telemetry is not independent proof of encoder freshness or physical accuracy.',
        'Do not replay these commands or infer a safe return from this bundle.'])
    attachments['elbow-summary.md']='\n'.join(lines).encode()
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-elbow-diagnosis'},[],attachments=attachments)
    if not verify_export(Path(receipt['path']).resolve())['valid']:raise RuntimeError('Bundle verification failed')
    print(json.dumps(dict(export=receipt['path'],classifications=[r['diagnosis']['classification'] for r in rows])))


if __name__=='__main__':main()
