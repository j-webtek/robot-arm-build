"""Freeze a single local mirrored shoulder rise from verified r26; offline only."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    prefix='.firmware-tools/configured-diagnostic-candidate-r26/RoArm-M3_example/'
    source=root/prefix;target=root/'.firmware-tools/configured-diagnostic-candidate-r27/RoArm-M3_example'
    report,receipt=_read(exports,'wizard-20260919T200324042010Z-eb4518e4effe49daa764f35ea98090d6',
        'attachment-compile-review.json')
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    expected={Path(p).name:h for p,h in report['source_hashes'].items() if p.replace('\\','/').startswith(prefix)}
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    if report['status']!='COMPILED' or set(files)!=set(expected) or any(sha(raw)!=expected[n] for n,raw in files.items()):
        raise ValueError('Pinned r26 source differs')
    changes={}
    for name in ('shoulder_preload_session.h','shoulder_preload_candidate.h','shoulder_authorized_start.h',
                 'shoulder_board_session.h','shoulder_hold_event_json.h'):
        raw=(root/'firmware/diagnostics'/name).read_bytes()
        if name=='shoulder_board_session.h':raw=b'#define ROCELL_SHOULDER_RISE 1\n'+raw
        if raw==files[name]:raise ValueError('Expected integration change missing')
        changes[name]=dict(before=sha(files[name]),after=sha(raw));files[name]=raw
    target.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():
        with (target/name).open('xb') as stream:stream.write(raw)
        if (target/name).read_bytes()!=raw:raise ValueError('Stage readback differs')
    evidence=dict(schema='rocell.shoulder_rise_stage.v1',revision=27,
        predecessor_compile_receipt=receipt,changed_files=changes,
        command_id='shoulder-rise12-v1',scope='SHOULDER_RISE',
        maximum_target_packets=1,servo_ids=[12,13],offset_counts=[-12,12],
        speed_counts_per_second=20,acceleration=1,explicit_torque_commands=0,
        return_or_retry=False,physical_clearance_verified=False,
        hardware_access=False,uploaded=False,settings_modified=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r27-shoulder-rise-stage'},[],attachments={'shoulder-rise-stage.json':canonical(evidence)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid stage export')
    print(saved['path'])


if __name__=='__main__':main()
