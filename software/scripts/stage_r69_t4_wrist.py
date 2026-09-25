"""Stage an exact single-servo T4 wrist candidate from pinned r67, offline."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.t4_wrist_review import review_t4_wrist
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

COMPILE='wizard-20260923T232929118798Z-82280e00a0e24d50b7031e7ac31f016d'
SOURCE='wizard-20260924T094712566120Z-c199a22385e441c0b96efde228b164e1'

def specialize(files):
    files=dict(files)
    changes={
        'large_pose_relief_policy.h':[
            ('P3E -> P3 wrist-only','T4L -> T4 wrist-only'),
            ('source_goals[7]={2047,2283,1831,2777,1785,2040,2047}','source_goals[7]={2047,2217,1897,2777,1850,2040,2047}'),
            ('source_positions[7]={2047,2291,1825,2780,1784,2041,2047}','source_positions[7]={2047,2225,1890,2780,1850,2041,2047}'),
            ('target_goals[7]={2047,2283,1831,2777,1850,2040,2047}','target_goals[7]={2047,2217,1897,2777,1915,2040,2047}')],
        'large_pose_relief_owner.h':[
            ('P3E -> P3 wrist adjustment','T4L -> T4 wrist adjustment'),
            ('LARGE_POSE_P3_INTENT','LARGE_POSE_T4_INTENT'),
            ('LARGE_POSE_P3_RECORDED','LARGE_POSE_T4_RECORDED'),
            ('uint16_t(1850)','uint16_t(1915)'),
            ('RCP3WRST01','RCT4WRST01'),('put(1850,2)','put(1915,2)')],
        'large_pose_relief_routes.h':[
            ('P3E -> P3 route','T4L -> T4 route'),('body "P3"','body "T4"'),
            ('body!="P3"','body!="T4"'),('LARGE_POSE_P3_RECORDED','LARGE_POSE_T4_RECORDED')],
        'characterization_board_services.h':[
            ('servo!=15||target!=1850','servo!=15||target!=1915')]
    }
    for name,replacements in changes.items():
        for old,new in replacements:
            old,new=old.encode(),new.encode()
            if files[name].count(old)!=1:raise ValueError('Unexpected source: '+name)
            files[name]=files[name].replace(old,new)
    return files

def stage(root):
    root=Path(root).resolve();exports=root/'runs/wizard-exports'
    compiled,receipt=_read(exports,COMPILE,'attachment-compile-review.json')
    source=exports/SOURCE
    if not verify_export(source)['valid']:raise ValueError('Invalid T4L export')
    raw=bytes.fromhex((source/'attachment-large-pose-relief.hex.txt').read_text())
    path_review=review_t4_wrist(raw,expected_boot='3393ba5a435af3044f3b554f5622f2fa',
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    prefix='.firmware-tools/configured-diagnostic-candidate-r67/RoArm-M3_example/'
    files={p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    sha=lambda data:hashlib.sha256(data).hexdigest()
    expected={Path(p).name:h for p,h in compiled['source_hashes'].items()
              if p.replace('\\','/').startswith(prefix)}
    if (compiled['status']!='COMPILED' or compiled['target']!='configured-diagnostic-candidate-r67'
        or set(files)!=set(expected) or any(sha(v)!=expected[k] for k,v in files.items())):
        raise ValueError('Pinned r67 source differs')
    candidate=specialize(files)
    target=root/'.firmware-tools/configured-diagnostic-candidate-r69/RoArm-M3_example'
    target.mkdir(parents=True,exist_ok=False)
    for name,data in candidate.items():
        with (target/name).open('xb') as stream:stream.write(data)
        if (target/name).read_bytes()!=data:raise ValueError('Staged readback differs')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r69-t4-wrist-stage'},[],attachments={
        'r69-t4-wrist-stage.json':canonical(dict(revision=69,predecessor_compile_receipt=receipt,
            source_export=SOURCE,path_review=path_review,selector='T4',record_bytes=1129,
            changed_files={k:dict(before=sha(files[k]),after=sha(v)) for k,v in candidate.items() if v!=files[k]},
            hardware_access=False,uploaded=False,deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid stage export')
    return saved['path']

if __name__=='__main__':print(stage(Path(__file__).resolve().parents[1]))
