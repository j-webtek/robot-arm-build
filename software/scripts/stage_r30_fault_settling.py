"""Freeze the reviewed r29 baseline plus fault-settling integration, offline only.

Retains the old motion window; this is NOT a new motion admission for the current
pose. Creates a new directory exclusively and never replaces an earlier stage.
"""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root=Path(__file__).resolve().parents[1]
    exports=root/'runs/wizard-exports'
    prefix='.firmware-tools/configured-diagnostic-candidate-r29/RoArm-M3_example/'
    source=root/prefix
    target=root/'.firmware-tools/configured-diagnostic-candidate-r30/RoArm-M3_example'
    report,receipt=_read(exports,'wizard-20260919T211604203264Z-471612255f894a76877c46d285a3a416',
                         'attachment-compile-review.json')
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    expected={Path(p).name:h for p,h in report['source_hashes'].items()
              if p.replace('\\','/').startswith(prefix)}
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    if (report['status']!='COMPILED' or set(files)!=set(expected)
            or any(sha(raw)!=expected[name] for name,raw in files.items())):
        raise ValueError('Pinned r29 source differs')
    changes={}
    for name in ('shoulder_preload_candidate.h','shoulder_hold_event_json.h',
                 'shoulder_session_owner.h','shoulder_board_session.h',
                 'shoulder_fault_settling_capture.h','shoulder_fault_settling_session.h',
                 'shoulder_fault_settling_routes.h'):
        raw=(root/'firmware/diagnostics'/name).read_bytes()
        if name=='shoulder_board_session.h':
            raw=b'#define ROCELL_STABLE_CLEARANCE_RECOVERY 1\n#define ROCELL_FAULT_SETTLING_CAPTURE 1\n'+raw
        before=files.get(name)
        if before==raw:raise ValueError('Expected integration change missing')
        changes[name]=dict(before=sha(before) if before is not None else None,after=sha(raw))
        files[name]=raw
    target.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():
        with (target/name).open('xb') as stream:stream.write(raw)
        if (target/name).read_bytes()!=raw:raise ValueError('Stage readback differs')
    evidence=dict(schema='rocell.fault_settling_stage.v1',revision=30,
        predecessor_compile_receipt=receipt,changed_files=changes,
        original_motion_contract_unchanged=True,current_pose_motion_released=False,
        settling_command_prefix='settle-',maximum_settling_scans=12,
        settling_deadline_us=8_000_000,minimum_scan_spacing_us=500_000,
        original_fault_export_required=True,parent_fault_remains_latched=True,
        additional_target_writes=0,explicit_torque_commands=0,
        hardware_access=False,uploaded=False,live_release_binding=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r30-fault-settling-stage'},[],
                         attachments={'fault-settling-stage.json':canonical(evidence)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid stage export')
    print(saved['path'])


if __name__=='__main__':main()
