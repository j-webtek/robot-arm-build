"""Stage r74 fixed midpoint candidate from verified r73 sources, offline."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.p4_midpoint_comparison import review_comparison
from rocell.application.p4_correction_scoring import score_exported_campaign
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

R73_COMPILE='wizard-20260924T192012116855Z-79eccb30246b41a9a6bfb7c2d150a932'
R73_APP_SHA='ec2b9f63e6c2157185584f596a7a04551c995bed9de811d9bcd94b7bc3c2373a'
R73_SUMMARY='wizard-20260924T193000463098Z-0dd40c9e0c784847bda008593634ad38'
R73_BOOT='3b61679887bee5e72bc70ca6ffdf7344'


def specialize(files, root):
    files=dict(files)
    files['large_pose_relief_routes.h']=(
        b'#pragma once\n#include "p4_midpoint_routes.h"\nnamespace rocell_diag { '
        b'template<class C,class S,class K,class W> using LargePoseReliefRoutes='
        b'P4MidpointRoutes<C,S,K,W>; }\n')
    old=b'target!=1944&&target!=1947&&target!=1980'
    if files['characterization_board_services.h'].count(old)!=1:
        raise ValueError('Unexpected r73 board adapter')
    files['characterization_board_services.h']=files['characterization_board_services.h'].replace(
        old,b'target!=1944&&target!=1945&&target!=1980')
    for name in ('p4_midpoint_policy.h','p4_midpoint_owner.h','p4_midpoint_routes.h'):
        files[name]=(root/'firmware/diagnostics'/name).read_bytes()
    return files


def stage(root):
    root=Path(root).resolve();exports=root/'runs/wizard-exports'
    compiled,compile_digest=_read(exports,R73_COMPILE,'attachment-compile-review.json')
    source=root/'.firmware-tools/configured-diagnostic-candidate-r73/RoArm-M3_example'
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    prefix='.firmware-tools/configured-diagnostic-candidate-r73/RoArm-M3_example/'
    expected={Path(p).name:h for p,h in compiled['source_hashes'].items()
              if p.replace('\\','/').startswith(prefix)}
    if (compiled['status']!='COMPILED' or compiled['target']!='configured-diagnostic-candidate-r73'
        or set(files)!=set(expected) or any(sha(v)!=expected[k] for k,v in files.items())):
        raise ValueError('Pinned r73 source differs')
    image=(root/'.firmware-tools/build-configured-diagnostic-candidate-r73--default-4mb-no-psram/RoArm-M3_example.ino.bin').read_bytes()
    if sha(image)!=R73_APP_SHA:raise ValueError('Pinned r73 binary differs')
    summary,_=_read(exports,R73_SUMMARY,'attachment-r73-p4-correction-summary.json')
    replay=score_exported_campaign(exports,summary['source_exports'],boot=R73_BOOT)
    if (canonical(replay)!=canonical(summary) and
        {k:v for k,v in replay.items() if k!='limitation'}!={k:v for k,v in summary.items() if k!='limitation'}):
        raise ValueError('Retained r73 summary differs from raw replay')
    last,_=_read(exports,summary['source_exports'][-1],'attachment-p4-correction-assessment.json')
    review=review_comparison(root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    if (tuple(last['final_positions'])!=tuple(review['source_positions']) or
        tuple(last['final_goals'])!=tuple(review['source_goals'])):
        raise ValueError('Retained r73 source differs')
    candidate=specialize(files,root)
    target=root/'.firmware-tools/configured-diagnostic-candidate-r74/RoArm-M3_example'
    target.mkdir(parents=True,exist_ok=True)
    existing={p.name:p.read_bytes() for p in target.iterdir() if p.is_file()}
    if existing and existing!=candidate:raise ValueError('Existing stage differs; no overwrite')
    for name,data in candidate.items():
        if not (target/name).exists():
            with (target/name).open('xb') as stream:stream.write(data)
        if (target/name).read_bytes()!=data:raise ValueError('Staged readback differs')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r74-p4-midpoint-stage'},[],attachments={
        'r74-p4-midpoint-stage.json':canonical(dict(predecessor_revision=73,
            predecessor_compile_export=R73_COMPILE,predecessor_compile_digest=compile_digest,
            source_export=R73_SUMMARY,comparison_review=review,selector='P4M16',record_bytes=1130,
            changed_files={k:dict(before=sha(files[k]) if k in files else None,after=sha(v))
                for k,v in candidate.items() if v!=files.get(k)},
            hardware_access=False,uploaded=False,deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid stage export')
    return saved['path']


if __name__=='__main__':print(stage(Path(__file__).resolve().parents[1]))
