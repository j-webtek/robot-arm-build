"""Stage r73 fixed comparison candidate from verified r72 sources, offline."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.p4_correction_comparison import review_comparison
from rocell.application.p4_endpoint_prediction import TEST, load_session
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

R72_COMPILE='wizard-20260924T184102787182Z-e6daa16054ff4961875b00e4ea99ee77'
R72_APP_SHA='e8d27dc8085d4e21ae6450be4eff0c41eb46a39962ba2d47baf084b01ee3afe9'


def specialize(files, root):
    files=dict(files)
    files['large_pose_relief_routes.h']=(
        b'#pragma once\n#include "p4_correction_routes.h"\nnamespace rocell_diag { '
        b'template<class C,class S,class K,class W> using LargePoseReliefRoutes='
        b'P4CorrectionRoutes<C,S,K,W>; }\n')
    old=b'target!=1915&&target!=1947&&target!=1980'
    if files['characterization_board_services.h'].count(old)!=1:
        raise ValueError('Unexpected r72 board adapter')
    files['characterization_board_services.h']=files['characterization_board_services.h'].replace(
        old,b'target!=1944&&target!=1947&&target!=1980')
    for name in ('p4_correction_policy.h','p4_correction_owner.h','p4_correction_routes.h'):
        files[name]=(root/'firmware/diagnostics'/name).read_bytes()
    return files


def stage(root):
    root=Path(root).resolve();exports=root/'runs/wizard-exports'
    compiled,compile_digest=_read(exports,R72_COMPILE,'attachment-compile-review.json')
    source=root/'.firmware-tools/configured-diagnostic-candidate-r72/RoArm-M3_example'
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    prefix='.firmware-tools/configured-diagnostic-candidate-r72/RoArm-M3_example/'
    expected={Path(p).name:h for p,h in compiled['source_hashes'].items()
              if p.replace('\\','/').startswith(prefix)}
    if (compiled['status']!='COMPILED' or compiled['target']!='configured-diagnostic-candidate-r72'
        or set(files)!=set(expected) or any(sha(v)!=expected[k] for k,v in files.items())):
        raise ValueError('Pinned r72 source differs')
    image=(root/'.firmware-tools/build-configured-diagnostic-candidate-r72--default-4mb-no-psram/RoArm-M3_example.ino.bin').read_bytes()
    if sha(image)!=R72_APP_SHA:raise ValueError('Pinned r72 binary differs')
    last=load_session(exports,TEST)[-1]
    review=review_comparison(root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    if (tuple(last['final_positions'])!=tuple(review['source_positions']) or
        tuple(last['final_goals'])!=tuple(review['source_goals'])):
        raise ValueError('Retained r72 source differs')
    candidate=specialize(files,root)
    target=root/'.firmware-tools/configured-diagnostic-candidate-r73/RoArm-M3_example'
    target.mkdir(parents=True,exist_ok=True)
    existing={p.name:p.read_bytes() for p in target.iterdir() if p.is_file()}
    if existing and existing!=candidate:raise ValueError('Existing stage differs; no overwrite')
    for name,data in candidate.items():
        if not (target/name).exists():
            with (target/name).open('xb') as stream:stream.write(data)
        if (target/name).read_bytes()!=data:raise ValueError('Staged readback differs')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r73-p4-correction-stage'},[],attachments={
        'r73-p4-correction-stage.json':canonical(dict(predecessor_revision=72,
            predecessor_compile_export=R72_COMPILE,predecessor_compile_digest=compile_digest,
            source_export=TEST,comparison_review=review,selector='P4C16',record_bytes=1130,
            changed_files={k:dict(before=sha(files[k]) if k in files else None,after=sha(v))
                for k,v in candidate.items() if v!=files.get(k)},
            hardware_access=False,uploaded=False,deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid stage export')
    return saved['path']


if __name__=='__main__':print(stage(Path(__file__).resolve().parents[1]))
