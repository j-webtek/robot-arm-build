"""Freeze r28 plus three-snapshot recovery baseline; never access hardware."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    prefix='.firmware-tools/configured-diagnostic-candidate-r28/RoArm-M3_example/'
    source=root/prefix;target=root/'.firmware-tools/configured-diagnostic-candidate-r29/RoArm-M3_example'
    report,receipt=_read(exports,'wizard-20260919T205553183262Z-0cd25b4f86a44fcc85b252c2dec155de','attachment-compile-review.json')
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    expected={Path(p).name:h for p,h in report['source_hashes'].items() if p.replace('\\','/').startswith(prefix)}
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    if report['status']!='COMPILED' or set(files)!=set(expected) or any(sha(raw)!=expected[n] for n,raw in files.items()):
        raise ValueError('Pinned r28 source differs')
    changes={}
    for name in ('shoulder_preload_session.h','shoulder_authorized_start.h','shoulder_board_session.h','shoulder_hold_event_json.h'):
        raw=(root/'firmware/diagnostics'/name).read_bytes()
        if name=='shoulder_board_session.h':raw=b'#define ROCELL_STABLE_CLEARANCE_RECOVERY 1\n'+raw
        if raw==files[name]:raise ValueError('Expected integration change missing')
        changes[name]=dict(before=sha(files[name]),after=sha(raw));files[name]=raw
    target.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():
        with (target/name).open('xb') as stream:stream.write(raw)
        if (target/name).read_bytes()!=raw:raise ValueError('Stage readback differs')
    evidence=dict(schema='rocell.stable_clearance_stage.v1',revision=29,predecessor_compile_receipt=receipt,
        changed_files=changes,command_id='shoulder-stable-clearance24-v1',scope='STABLE_CLEARANCE_RECOVERY',
        baseline_samples=3,baseline_spacing_us=100000,baseline_position_variation_counts=1,
        nonselected_start_goal_error_limit=5,nonselected_drift_limit=2,selected_arrival_error_limit=2,
        maximum_target_packets=1,targets=[2419,1695],maximum_actual_travel_counts=32,
        explicit_torque_commands=0,return_or_retry=False,hardware_access=False,uploaded=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r29-stable-clearance-stage'},[],attachments={'stable-clearance-stage.json':canonical(evidence)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid stage export')
    print(saved['path'])


if __name__=='__main__':main()
