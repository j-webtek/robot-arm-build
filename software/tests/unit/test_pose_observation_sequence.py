"""Compile acquisition-only core with a write-disabled synthetic bus."""
from pathlib import Path
import shutil
import subprocess
import json
import copy
import pytest
from rocell.application.pose_observation_review import assess_pose_observation
from rocell.application.pose_observation_export import export_pose_observation,replay_pose_observation


def test_native_observation_sequence(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler: pytest.skip('Native compiler required')
    root=Path(__file__).resolve().parents[2]
    exe=tmp_path/'pose-observation.exe'
    build=subprocess.run([compiler,'-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_pose_observation_sequence.cpp'),'-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    records=[json.loads(line) for line in run.stdout.splitlines()]
    saved=export_pose_observation(tmp_path/'exports',[line.encode() for line in run.stdout.splitlines()],
        expected_boot='test-boot',expected_id='test-pose',origin='SIMULATION')
    assert saved['assessment']['category']=='STABLE_SAMPLED_POSE'
    assert replay_pose_observation(tmp_path/'exports',Path(saved['export_path']).name)['replay_verified']
    from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter
    from rocell.application.first_motion_contract import canonical
    source=Path(saved['export_path'])
    bundle=json.loads((source/'attachment-pose-raw.json').read_bytes())
    forged=copy.deepcopy(saved['assessment']);forged['category']='POSE_NOT_STABLE'
    exporter=WizardDiagnosticExporter(tmp_path/'exports')
    exporter.prepare(create=True)
    altered=exporter.export({'mode':'test'},[],attachments={
        'pose-raw.json':canonical(bundle),'pose-assessment.json':canonical(forged)})
    with pytest.raises(ValueError,match='does not replay'):
        replay_pose_observation(tmp_path/'exports',Path(altered['path']).name)
    def assess(rows):
        return assess_pose_observation(rows,expected_boot='test-boot',expected_id='test-pose')
    assert assess(records)['category']=='STABLE_SAMPLED_POSE'
    assert assess(records)['progression_authority'] is False
    for fault in ('boot','missing','index','read','terminal','time','drift'):
        changed=copy.deepcopy(records)
        if fault=='boot': changed[1]['boot_id']='other'
        if fault=='missing': changed.pop(1)
        if fault=='index': changed[1]['snapshot_index']=False
        if fault=='read': changed[1]['reads'][0][3][5]=False
        if fault=='terminal': changed[-1]['action_count']=1
        if fault=='time': changed[1]=copy.deepcopy(changed[0]);changed[1]['snapshot_index']=1
        if fault=='drift':
            raw=changed[1]['reads'][1][3][6]
            changed[1]['reads'][1][3][6]='0308'+raw[4:]
        expected='POSE_NOT_STABLE' if fault=='drift' else 'INCONCLUSIVE'
        assert assess(changed)['category']==expected,fault


@pytest.mark.parametrize('source', ['test_pose_observation_owner.cpp','test_pose_observation_routes.cpp',
                                  'test_pose_enabled_board.cpp'])
def test_native_exclusive_observation_owner(tmp_path, source):
    compiler=shutil.which('clang++')
    if not compiler: pytest.skip('Native compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'pose-owner.exe'
    build=subprocess.run([compiler,'-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics'/source),'-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
