"""Stage an exact single-servo P2 wrist candidate from pinned r64, offline."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.p2_wrist_review import review_p2_wrist
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

COMPILE='wizard-20260923T094333014308Z-df5a0efd5a874f0ab2de6dd4da1bc575'
SOURCE='wizard-20260923T194529289849Z-76fd6c1bf73a4a6eacf42e7510b2072d'

def specialize(files):
    files=dict(files)
    def change(name, old, new, count=1):
        old,new=old.encode(),new.encode()
        if files[name].count(old)!=count:raise ValueError('Unexpected source: '+name)
        files[name]=files[name].replace(old,new)
    policy='large_pose_relief_policy.h'
    change(policy,'P1 -> P2L shoulder-lift','P2L -> P2 wrist-only')
    change(policy,'source_goals[7]={2047,2348,1766,2842,1719,2040,2047}',
                  'source_goals[7]={2047,2283,1831,2842,1719,2040,2047}')
    change(policy,'source_positions[7]={2047,2356,1759,2844,1720,2041,2047}',
                  'source_positions[7]={2047,2291,1825,2844,1720,2041,2047}')
    change(policy,'target_goals[7]={2047,2283,1831,2842,1719,2040,2047}',
                  'target_goals[7]={2047,2283,1831,2842,1785,2040,2047}')
    change(policy,'selected[2]={1,2}','selected[1]={4}')
    change(policy,'joint==1||joint==2','joint==4')
    owner='large_pose_relief_owner.h'
    change(owner,'P1 -> P2L lift','P2L -> P2 wrist adjustment')
    change(owner,'LARGE_POSE_P2L_INTENT','LARGE_POSE_P2_INTENT')
    change(owner,'LARGE_POSE_P2L_RECORDED','LARGE_POSE_P2_RECORDED')
    change(owner,'write(uint8_t(12),uint8_t(13),uint16_t(2283),\n                uint16_t(1831),uint16_t(20),uint8_t(1))',
                 'write(uint8_t(15),uint16_t(1785),uint16_t(20),uint8_t(1))')
    change(owner,'10+16+4+8+1+7*(16+7*20)','10+16+2+8+1+7*(16+7*20)')
    change(owner,'RCP2LIFT01','RCP2WRST01')
    change(owner,'put(2283,2);put(1831,2)','put(1785,2)')
    routes='large_pose_relief_routes.h'
    change(routes,'P1 -> P2L route','P2L -> P2 route')
    change(routes,'body "P2L"','body "P2"')
    change(routes,'body!="P2L"','body!="P2"')
    change(routes,'LARGE_POSE_P2L_RECORDED','LARGE_POSE_P2_RECORDED')
    change(routes,'uint8_t a,uint8_t b,uint16_t x,uint16_t y,','uint8_t a,uint16_t x,')
    change(routes,'large_pose_relief_write(a,b,x,y,speed,acc)','large_pose_relief_write(a,x,speed,acc)')
    change(routes,'record_[1131]','record_[1129]')
    change(routes,'hex_[2263]','hex_[2259]')
    services='characterization_board_services.h'
    start=files[services].index(b'  bool large_pose_relief_write(')
    end=files[services].index(b'  bool large_pose_relief_evidence(',start)
    old=files[services][start:end].decode()
    new='''  bool large_pose_relief_write(uint8_t servo,uint16_t target,
                               uint16_t speed,uint8_t acceleration){
    if(!owned()||!healthy()||servo!=15||target!=1785||
       speed!=20||acceleration!=1||st.End!=0)return false;
    uint8_t ids[1]={servo},acc[1]={acceleration};
    int16_t targets[1]={int16_t(target)};
    uint16_t speeds[1]={speed};
    st.SyncWritePosEx(ids,1,targets,speeds,acc); // One broadcast; no retry.
    return st.Error==0;
  }
'''
    change(services,old,new)
    return files

def stage(root):
    root=Path(root).resolve();exports=root/'runs/wizard-exports'
    compiled,receipt=_read(exports,COMPILE,'attachment-compile-review.json')
    source=exports/SOURCE
    if not verify_export(source)['valid']:raise ValueError('Invalid P2L export')
    raw=bytes.fromhex((source/'attachment-large-pose-relief.hex.txt').read_text())
    path_review=review_p2_wrist(raw,expected_boot='6d2f06e84d08620829bd579b7f337c8b',
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    prefix='.firmware-tools/configured-diagnostic-candidate-r64/RoArm-M3_example/'
    files={p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    sha=lambda data:hashlib.sha256(data).hexdigest()
    expected={Path(p).name:h for p,h in compiled['source_hashes'].items()
              if p.replace('\\','/').startswith(prefix)}
    if (compiled['status']!='COMPILED' or compiled['target']!='configured-diagnostic-candidate-r64'
        or set(files)!=set(expected) or any(sha(v)!=expected[k] for k,v in files.items())):
        raise ValueError('Pinned r64 source differs')
    candidate=specialize(files)
    target=root/'.firmware-tools/configured-diagnostic-candidate-r65/RoArm-M3_example'
    target.mkdir(parents=True,exist_ok=False)
    for name,data in candidate.items():
        with (target/name).open('xb') as stream:stream.write(data)
        if (target/name).read_bytes()!=data:raise ValueError('Staged readback differs')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r65-p2-wrist-stage'},[],attachments={
        'r65-p2-wrist-stage.json':canonical(dict(revision=65,predecessor_compile_receipt=receipt,
            source_export=SOURCE,path_review=path_review,selector='P2',record_bytes=1129,
            changed_files={k:dict(before=sha(files[k]),after=sha(v)) for k,v in candidate.items() if v!=files[k]},
            hardware_access=False,uploaded=False,deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid stage export')
    return saved['path']

if __name__=='__main__':print(stage(Path(__file__).resolve().parents[1]))
