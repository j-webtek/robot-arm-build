"""Stage public r20 source from verified r19; never touches a controller."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    source=root/'.firmware-tools/configured-diagnostic-candidate-r19/RoArm-M3_example'
    target=root/'.firmware-tools/configured-diagnostic-candidate-r20/RoArm-M3_example'
    report,receipt=_read(exports,'wizard-20260919T131705393017Z-1368c2e209a64eb98a090bbd66a78b08',
        'attachment-compile-review.json')
    if report['status']!='COMPILED' or report['target']!='configured-diagnostic-candidate-r19':
        raise ValueError('Verified predecessor required')
    sha=lambda b:hashlib.sha256(b).hexdigest()
    expected={Path(p).name:h for p,h in report['source_hashes'].items()
        if p.replace('\\','/').startswith('.firmware-tools/configured-diagnostic-candidate-r19/RoArm-M3_example/')}
    files={}
    for path in source.iterdir():
        if path.is_symlink() or not path.is_file() or path.suffix not in ('.h','.ino'):
            raise ValueError('Unexpected predecessor entry')
        raw=path.read_bytes()
        if expected.get(path.name)!=sha(raw):raise ValueError('Predecessor changed')
        files[path.name]=raw
    if set(files)!=set(expected):raise ValueError('Source inventory changed')
    original=dict(files)
    for name in ('pose_observation_sequence.h','pose_observation_json.h','pose_observation_owner.h',
        'pose_observation_routes.h','pose_observation_board.h','pose_observation_reservation.h',
        'configured_hold_routes.h','configured_pair_board_routes.h','configured_recovery_board_routes.h'):
        files[name]=(root/'firmware/diagnostics'/name).read_bytes()
    files['configured_native_owner.h']=(b'#define ROCELL_POSE_OBSERVATION 1\n'
        b'#include "pose_observation_reservation.h"\n'+files['configured_native_owner.h'])
    boot=files['diagnostic_boot.h']
    old=b'  delay(1);'
    if boot.count(old)!=1:raise ValueError('Unexpected loop wiring')
    files['diagnostic_boot.h']=boot.replace(old,b'  if(rocellDiagnosticBootReady)pollPoseObservation();\n'+old)
    changes={n:dict(before_sha256=sha(original[n]) if n in original else None,after_sha256=sha(b))
        for n,b in files.items() if original.get(n)!=b}
    target.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():
        with (target/name).open('xb') as stream:stream.write(raw)
        if (target/name).read_bytes()!=raw:raise ValueError('Staging readback differs')
    review=dict(schema='rocell.pose_candidate_stage.v1',revision=20,predecessor_compile_sha256=receipt,
        changed_files=changes,unchanged_files=len(files)-len(changes),hardware_access=False,
        firmware_uploaded=False,provisioning_performed=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r20-pose-stage'},[],attachments={'pose-stage.json':canonical(review)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Stage export failed')
    print(canonical(dict(export_path=saved['path'],**review)).decode())


if __name__=='__main__':main()
