"""Stage exact measured T1 -> P1 candidate from pinned r62 source, offline."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


R62_COMPILE='wizard-20260923T004133494491Z-9f85eff5009a41c5bf3b93353ed08145'
T1_RESULT='wizard-20260923T013000217507Z-65942c5e2f9b42f4b683f0fbf0a32455'
OVERLAY=('characterization_board_services.h','characterization_composition.h',
         'large_pose_relief_policy.h','large_pose_relief_owner.h',
         'large_pose_relief_routes.h')


def stage(root):
    root=Path(root).resolve();exports=root/'runs/wizard-exports'
    compiled,compile_receipt=_read(exports,R62_COMPILE,'attachment-compile-review.json')
    result,result_receipt=_read(exports,T1_RESULT,'attachment-large-pose-lift-assessment.json')
    if (result['status']!='T1_JOINT_ENDPOINT_MEASURED' or
            result['boot']!='8b2dccefc3394fd2827130e5994efb08' or
            result['position_delta_counts']!=[0,-58,59,0,61,0,0]):
        raise ValueError('Pinned T1 endpoint differs')
    prefix='.firmware-tools/configured-diagnostic-candidate-r62/RoArm-M3_example/'
    source=root/prefix
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    expected={Path(path).name:digest for path,digest in compiled['source_hashes'].items()
              if path.replace('\\','/').startswith(prefix)}
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    if (compiled['status']!='COMPILED' or
            compiled['target']!='configured-diagnostic-candidate-r62' or
            set(files)!=set(expected) or
            any(sha(raw)!=expected[name] for name,raw in files.items())):
        raise ValueError('Pinned r62 source differs')
    changed={}
    for name in OVERLAY:
        old=files.get(name)
        new=(root/'firmware/diagnostics'/name).read_bytes()
        files[name]=new
        changed[name]={'before':sha(old) if old is not None else None,'after':sha(new)}
    board='characterization_smoke_board.h'
    old=files[board]
    needle=b'CharacterizationPattern::VisibleIntervalCampaign,false,false,false,true'
    replacement=b'CharacterizationPattern::VisibleIntervalCampaign,false,false,false,false,true'
    if old.count(needle)!=1:
        raise ValueError('Expected exact r62 route selector')
    files[board]=old.replace(needle,replacement)
    changed[board]={'before':sha(old),'after':sha(files[board])}
    target=root/'.firmware-tools/configured-diagnostic-candidate-r63/RoArm-M3_example'
    target.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():
        with (target/name).open('xb') as stream:stream.write(raw)
        if (target/name).read_bytes()!=raw:raise ValueError('Staged readback differs')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r63-large-pose-relief-stage'},[],attachments={
        'r63-large-pose-relief-stage.json':canonical({
            'schema':'rocell.r63_large_pose_relief_stage.v1','revision':63,
            'predecessor_revision':62,'predecessor_compile_receipt':compile_receipt,
            'source_result_export_id':T1_RESULT,'source_result_receipt':result_receipt,
            'changed_files':changed,'selector_body':'P1',
            'source_goals':[2047,2348,1766,2907,1654,2040,2047],
            'source_positions':[2047,2357,1759,2904,1652,2041,2047],
            'targets':{'14':2842,'15':1719},'maximum_writes':1,
            'retry_allowed':False,'return_allowed':False,'hardware_access':False,
            'uploaded':False,'settings_changed':False,'deployable':False})})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Stage export invalid')
    return saved['path']


if __name__=='__main__':
    print(stage(Path(__file__).resolve().parents[1]))
