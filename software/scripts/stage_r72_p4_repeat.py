"""Stage a finite twelve-leg wrist candidate from pinned r71, offline."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.p4_repeat_campaign_review import review_p4_repeat_campaign
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

COMPILE='wizard-20260924T181633213678Z-41dc084be42d4fdc933239d4546d97ac'
SOURCE='wizard-20260924T182321443347Z-87b68bc4624a4e1b80c6fb0af4027e5e'

def specialize(files, root):
    files=dict(files)
    # Reuse the existing exclusive, authenticated composition slot, replacing
    # the former one-shot routes rather than enabling both movement paths.
    files['large_pose_relief_routes.h']=b'#pragma once\n#include "p4_repeat_routes.h"\nnamespace rocell_diag { template<class C,class S,class K,class W> using LargePoseReliefRoutes=P4RepeatRoutes<C,S,K,W>; }\n'
    old=b'servo!=15||target!=1980'
    if files['characterization_board_services.h'].count(old)!=1:
        raise ValueError('Unexpected board adapter')
    files['characterization_board_services.h']=files['characterization_board_services.h'].replace(
        old,b'servo!=15||(target!=1915&&target!=1947&&target!=1980)')
    for name in ('p4_repeat_policy.h','p4_repeat_owner.h','p4_repeat_routes.h'):
        files[name]=(root/'firmware/diagnostics'/name).read_bytes()
    return files


def stage(root):
    root=Path(root).resolve();exports=root/'runs/wizard-exports'
    compiled,receipt=_read(exports,COMPILE,'attachment-compile-review.json')
    source=exports/SOURCE
    if not verify_export(source)['valid']:raise ValueError('Invalid P4E export')
    raw=bytes.fromhex((source/'attachment-large-pose-relief.hex.txt').read_text())
    path_review=review_p4_repeat_campaign(raw,expected_boot='3ce87bcbe82e9ccdc6f8b46854e095b3',
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    prefix='.firmware-tools/configured-diagnostic-candidate-r71/RoArm-M3_example/'
    files={p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    sha=lambda data:hashlib.sha256(data).hexdigest()
    expected={Path(p).name:h for p,h in compiled['source_hashes'].items()
              if p.replace('\\','/').startswith(prefix)}
    if (compiled['status']!='COMPILED' or compiled['target']!='configured-diagnostic-candidate-r71'
        or set(files)!=set(expected) or any(sha(v)!=expected[k] for k,v in files.items())):
        raise ValueError('Pinned r71 source differs')
    candidate=specialize(files,root)
    target=root/'.firmware-tools/configured-diagnostic-candidate-r72/RoArm-M3_example'
    target.mkdir(parents=True,exist_ok=True)
    existing={p.name:p.read_bytes() for p in target.iterdir() if p.is_file()}
    if existing and existing!=candidate:raise ValueError('Existing stage differs; no overwrite')
    for name,data in candidate.items():
        if not (target/name).exists():
            with (target/name).open('xb') as stream:stream.write(data)
        if (target/name).read_bytes()!=data:raise ValueError('Staged readback differs')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r72-p4-repeat-stage'},[],attachments={
        'r72-p4-repeat-stage.json':canonical(dict(revision=71,predecessor_compile_receipt=receipt,
            source_export=SOURCE,path_review=path_review,selector='P4R12',record_bytes=1130,
            changed_files={k:dict(before=sha(files[k]) if k in files else None,after=sha(v)) for k,v in candidate.items() if v!=files.get(k)},
            hardware_access=False,uploaded=False,deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid stage export')
    return saved['path']

if __name__=='__main__':print(stage(Path(__file__).resolve().parents[1]))
