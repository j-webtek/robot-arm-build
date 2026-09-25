"""Offline compiled r63 T1-to-P1 app review; never opens controller."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


COMPILE='wizard-20260923T015145565967Z-a39d76aa5967494f9e831e9fee455f48'
STAGE='wizard-20260923T014941177721Z-df983f2919674966aa33f9e94ed2b904'
APP_SHA='cbca0f164c49f480c282fe2ed435616a50a767db50b1048b24b7abb40e55604b'
R62_SHA='ee259799cb6b74b80cc4a45e16934ac6476b81d7a4536cc31406fffb766fd6e4'
CHANGED={'characterization_board_services.h','characterization_composition.h',
         'characterization_smoke_board.h','large_pose_relief_policy.h',
         'large_pose_relief_owner.h','large_pose_relief_routes.h'}


def review(root):
    root=Path(root).resolve();exports=root/'runs/wizard-exports'
    compiled,compile_digest=_read(exports,COMPILE,'attachment-compile-review.json')
    staged,stage_digest=_read(exports,STAGE,'attachment-r63-large-pose-relief-stage.json')
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    old=root/'.firmware-tools/configured-diagnostic-candidate-r62/RoArm-M3_example'
    new=root/'.firmware-tools/configured-diagnostic-candidate-r63/RoArm-M3_example'
    old_files={p.name:p.read_bytes() for p in old.iterdir() if p.is_file()}
    new_files={p.name:p.read_bytes() for p in new.iterdir() if p.is_file()}
    changed={name for name in old_files if old_files[name]!=new_files.get(name)}
    changed|=set(new_files)-set(old_files)
    if (compiled['status']!='COMPILED' or
            compiled['target']!='configured-diagnostic-candidate-r63' or
            compiled['build_profile']!='default-4mb-no-psram' or
            set(staged['changed_files'])!=CHANGED or changed!=CHANGED or
            staged['targets']!={'14':2842,'15':1719} or
            staged['source_positions']!=[2047,2357,1759,2904,1652,2041,2047] or
            staged['maximum_writes']!=1 or staged['retry_allowed'] or staged['return_allowed']):
        raise ValueError('Pinned r63 review evidence differs')
    prefix='.firmware-tools/configured-diagnostic-candidate-r63/RoArm-M3_example/'
    sources={name.replace('\\','/'):digest for name,digest in compiled['source_hashes'].items()}
    if any(sources.get(prefix+name)!=sha(raw) for name,raw in new_files.items()):
        raise ValueError('Compiled r63 source changed')
    board=new_files['characterization_smoke_board.h']
    owner=new_files['large_pose_relief_owner.h']
    services=new_files['characterization_board_services.h']
    if (board.count(b'VisibleIntervalCampaign,false,false,false,false,true')!=1 or
            owner.count(b'write(uint8_t(14),uint8_t(15),uint16_t(2842)')!=1 or
            services.count(b'st.SyncWritePosEx(ids,2,targets,speeds,acc); // One broadcast; no retry.')!=1):
        raise ValueError('r63 exact route/target binding differs')
    image=(root/'.firmware-tools/build-configured-diagnostic-candidate-r63--default-4mb-no-psram/'
           'RoArm-M3_example.ino.bin').read_bytes()
    identities=(b'/rocell/large-pose-relief/start',b'/rocell/large-pose-relief/receipt',
                b'RCRELIEF01',b'LARGE_POSE_P1_RECORDED')
    if sha(image)!=APP_SHA or len(image)!=1200704 or not all(x in image for x in identities):
        raise ValueError('Compiled r63 application differs')
    for suffix,expected in (
        ('bootloader.bin','b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7'),
        ('partitions.bin','148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1')):
        if compiled['artifact_hashes']['RoArm-M3_example.ino.'+suffix]!=expected:
            raise ValueError('Boot or partition artifact changed')
    report={
        'schema':'rocell.r63_large_pose_relief_review.v1',
        'target':'configured-diagnostic-candidate-r63',
        'app_sha256':APP_SHA,'app_bytes':len(image),'app_offset':0x10000,
        'app_slot_bytes':0x140000,'app_headroom_bytes':0x140000-len(image),
        'predecessor_sha256':R62_SHA,'compile_export_id':COMPILE,
        'compile_report_sha256':compile_digest,'stage_export_id':STAGE,
        'stage_report_sha256':stage_digest,'changed_files':sorted(CHANGED),
        'source_pose':'T1','target_pose':'P1',
        'source_positions':[2047,2357,1759,2904,1652,2041,2047],
        'synchronized_servo_ids':[14,15],'targets':[2842,1719],
        'maximum_writes':1,'retry_allowed':False,'return_allowed':False,
        'requires_fresh_three_sample_source':True,
        'requires_fresh_three_sample_endpoint':True,
        'requires_durable_export_receipt':True,'settings_preserved_by_design':True,
        'hardware_access':False,'firmware_uploaded':False,'deployment_authorized':False}
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r63-large-pose-relief-review'},[],attachments={
        'r63-large-pose-relief-review.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Review export invalid')
    return saved['path'],report


if __name__=='__main__':
    print(review(Path(__file__).resolve().parents[1])[0])
