"""Stage an exact single-servo P4E elbow candidate from pinned r69, offline."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.p4_extension_review import review_p4_extension
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

COMPILE='wizard-20260924T095347591688Z-949670757f6f46a6a8afa540063e58db'
SOURCE='wizard-20260924T100122313690Z-ba8afa38d92b436c8f137dae16978a84'

def specialize(files):
    files=dict(files)
    changes={
        'large_pose_relief_policy.h':[
            ('T4L -> T4 wrist-only','T4 -> P4E elbow-only'),
            ('source_goals[7]={2047,2217,1897,2777,1850,2040,2047}','source_goals[7]={2047,2217,1897,2777,1915,2040,2047}'),
            ('source_positions[7]={2047,2225,1890,2780,1850,2041,2047}','source_positions[7]={2047,2225,1890,2780,1912,2041,2047}'),
            ('target_goals[7]={2047,2217,1897,2777,1915,2040,2047}','target_goals[7]={2047,2217,1897,2711,1915,2040,2047}'),
            ('selected[1]={4}','selected[1]={3}'),('joint==4','joint==3')],
        'large_pose_relief_owner.h':[
            ('T4L -> T4 wrist adjustment','T4 -> P4E elbow extension'),
            ('LARGE_POSE_T4_INTENT','LARGE_POSE_P4E_INTENT'),
            ('LARGE_POSE_T4_RECORDED','LARGE_POSE_P4E_RECORDED'),
            ('write(uint8_t(15),uint16_t(1915)','write(uint8_t(14),uint16_t(2711)'),
            ('RCT4WRST01','RCP4ELBW01'),('put(1915,2)','put(2711,2)')],
        'large_pose_relief_routes.h':[
            ('T4L -> T4 route','T4 -> P4E route'),('body "T4"','body "P4E"'),
            ('body!="T4"','body!="P4E"'),('LARGE_POSE_T4_RECORDED','LARGE_POSE_P4E_RECORDED')],
        'characterization_board_services.h':[
            ('servo!=15||target!=1915','servo!=14||target!=2711')]
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
    if not verify_export(source)['valid']:raise ValueError('Invalid T4 export')
    raw=bytes.fromhex((source/'attachment-large-pose-relief.hex.txt').read_text())
    path_review=review_p4_extension(raw,expected_boot='4ea6cf4781ec4a1ff14ebbe6a45bf2bc',
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    prefix='.firmware-tools/configured-diagnostic-candidate-r69/RoArm-M3_example/'
    files={p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    sha=lambda data:hashlib.sha256(data).hexdigest()
    expected={Path(p).name:h for p,h in compiled['source_hashes'].items()
              if p.replace('\\','/').startswith(prefix)}
    if (compiled['status']!='COMPILED' or compiled['target']!='configured-diagnostic-candidate-r69'
        or set(files)!=set(expected) or any(sha(v)!=expected[k] for k,v in files.items())):
        raise ValueError('Pinned r69 source differs')
    candidate=specialize(files)
    target=root/'.firmware-tools/configured-diagnostic-candidate-r70/RoArm-M3_example'
    target.mkdir(parents=True,exist_ok=False)
    for name,data in candidate.items():
        with (target/name).open('xb') as stream:stream.write(data)
        if (target/name).read_bytes()!=data:raise ValueError('Staged readback differs')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r70-p4-elbow-stage'},[],attachments={
        'r70-p4-elbow-stage.json':canonical(dict(revision=70,predecessor_compile_receipt=receipt,
            source_export=SOURCE,path_review=path_review,selector='P4E',record_bytes=1129,
            changed_files={k:dict(before=sha(files[k]),after=sha(v)) for k,v in candidate.items() if v!=files[k]},
            hardware_access=False,uploaded=False,deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid stage export')
    return saved['path']

if __name__=='__main__':print(stage(Path(__file__).resolve().parents[1]))
