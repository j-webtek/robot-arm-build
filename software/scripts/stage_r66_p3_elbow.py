"""Stage an exact single-servo P3E elbow candidate from pinned r65, offline."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.p3_extension_review import review_p3_extension
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

COMPILE='wizard-20260923T195319510419Z-f65208d64d6c478ca3fc038249eee01f'
SOURCE='wizard-20260923T201517566882Z-2a37583111464777b465b59ccec7b9f0'

def specialize(files):
    files=dict(files)
    changes={
        'large_pose_relief_policy.h':[
            ('P2L -> P2 wrist-only','P2 -> P3E elbow-only'),
            ('source_goals[7]={2047,2283,1831,2842,1719,2040,2047}','source_goals[7]={2047,2283,1831,2842,1785,2040,2047}'),
            ('source_positions[7]={2047,2291,1825,2844,1720,2041,2047}','source_positions[7]={2047,2291,1825,2844,1784,2041,2047}'),
            ('target_goals[7]={2047,2283,1831,2842,1785,2040,2047}','target_goals[7]={2047,2283,1831,2777,1785,2040,2047}'),
            ('selected[1]={4}','selected[1]={3}'),('joint==4','joint==3')],
        'large_pose_relief_owner.h':[
            ('P2L -> P2 wrist adjustment','P2 -> P3E elbow extension'),
            ('LARGE_POSE_P2_INTENT','LARGE_POSE_P3E_INTENT'),
            ('LARGE_POSE_P2_RECORDED','LARGE_POSE_P3E_RECORDED'),
            ('write(uint8_t(15),uint16_t(1785)','write(uint8_t(14),uint16_t(2777)'),
            ('RCP2WRST01','RCP3ELBW01'),('put(1785,2)','put(2777,2)')],
        'large_pose_relief_routes.h':[
            ('P2L -> P2 route','P2 -> P3E route'),('body "P2"','body "P3E"'),
            ('body!="P2"','body!="P3E"'),('LARGE_POSE_P2_RECORDED','LARGE_POSE_P3E_RECORDED')],
        'characterization_board_services.h':[
            ('servo!=15||target!=1785','servo!=14||target!=2777')]
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
    if not verify_export(source)['valid']:raise ValueError('Invalid P2 export')
    raw=bytes.fromhex((source/'attachment-large-pose-relief.hex.txt').read_text())
    path_review=review_p3_extension(raw,expected_boot='ce3a5f51d59110826b67e3bf48d1f260',
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    prefix='.firmware-tools/configured-diagnostic-candidate-r65/RoArm-M3_example/'
    files={p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    sha=lambda data:hashlib.sha256(data).hexdigest()
    expected={Path(p).name:h for p,h in compiled['source_hashes'].items()
              if p.replace('\\','/').startswith(prefix)}
    if (compiled['status']!='COMPILED' or compiled['target']!='configured-diagnostic-candidate-r65'
        or set(files)!=set(expected) or any(sha(v)!=expected[k] for k,v in files.items())):
        raise ValueError('Pinned r65 source differs')
    candidate=specialize(files)
    target=root/'.firmware-tools/configured-diagnostic-candidate-r66/RoArm-M3_example'
    target.mkdir(parents=True,exist_ok=False)
    for name,data in candidate.items():
        with (target/name).open('xb') as stream:stream.write(data)
        if (target/name).read_bytes()!=data:raise ValueError('Staged readback differs')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r66-p3-elbow-stage'},[],attachments={
        'r66-p3-elbow-stage.json':canonical(dict(revision=66,predecessor_compile_receipt=receipt,
            source_export=SOURCE,path_review=path_review,selector='P3E',record_bytes=1129,
            changed_files={k:dict(before=sha(files[k]),after=sha(v)) for k,v in candidate.items() if v!=files[k]},
            hardware_access=False,uploaded=False,deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid stage export')
    return saved['path']

if __name__=='__main__':print(stage(Path(__file__).resolve().parents[1]))
