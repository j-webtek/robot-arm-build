import copy
import json
from pathlib import Path
import pytest
import shutil
import subprocess
import sys
from rocell.application.first_motion_contract import canonical
from rocell.application.observed_pose_candidate import draft_settings


def inputs():
    root = Path(__file__).resolve().parents[2]
    previous = json.loads((root/'docs/hold-r7-supported-pose-draft.json').read_bytes())
    positions = [2047, 2487, 1629, 2899, 2035, 2041, 2054]
    assessment = dict(origin='DEVICE_CAPTURE', category='STABLE_SAMPLED_POSE', joints=[
        dict(servo_id=11+i, last_position=p, position_span=0,
             controls_unchanged=True, torque=1 if i==3 else 0)
        for i,p in enumerate(positions)])
    return previous, assessment


def test_narrow_candidate_preserves_predecessor_and_motion_limits():
    previous, assessment = inputs(); original = copy.deepcopy(previous)
    hold, pair = draft_settings(previous, assessment)
    assert previous == original
    assert hold['hold_policy']['joints'] == [[2045,2049],[2485,2489],[1627,1631],
        [2893,2909],[2033,2037],[2039,2043],[2052,2056]]
    expected = copy.deepcopy(original['hold_policy'])
    expected['joints'] = hold['hold_policy']['joints']
    expected['permit_explicit_enable'] = 0
    assert hold['hold_policy'] == expected
    assert pair['offset_counts'] == 10 and pair['tolerance_counts'] == 2
    assert hold['command_id'] != original['command_id']


@pytest.mark.parametrize('fault', ['policy','simulation','unstable','anchor','torque','neighbor','order'])
def test_candidate_denies_incompatible_evidence(fault):
    previous, assessment = inputs()
    if fault=='policy': previous['hold_policy']['speed'] = 21
    if fault=='simulation': assessment['origin'] = 'SIMULATION'
    if fault=='unstable': assessment['category'] = 'POSE_NOT_STABLE'
    if fault=='anchor': assessment['joints'][3]['last_position'] = 2900
    if fault=='torque': assessment['joints'][3]['torque'] = 0
    if fault=='neighbor': assessment['joints'][0]['torque'] = 1
    if fault=='order': assessment['joints'].reverse()
    with pytest.raises(ValueError): draft_settings(previous, assessment)


@pytest.mark.parametrize('adapter,part', [
    ('firmware/diagnostics/validate_hold_provisioning.cpp', 0),
    ('firmware/validators/validate_pair_provisioning.cpp', 1)])
def test_r20_native_parser_accepts_draft(tmp_path, adapter, part):
    compiler = shutil.which('clang++')
    if not compiler: pytest.skip('Native compiler required')
    root = Path(__file__).resolve().parents[2]
    sketch = root/'.firmware-tools/configured-diagnostic-candidate-r20/RoArm-M3_example'
    exe = tmp_path/'validator.exe'
    built = subprocess.run([compiler, '-std=c++17', '-I'+str(sketch),
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/adapter), '-o', str(exe)], capture_output=True, timeout=60)
    assert built.returncode == 0, built.stderr
    settings = draft_settings(*inputs())[part]
    checked = subprocess.run([str(exe)], input=canonical(settings), capture_output=True, timeout=10)
    assert checked.returncode == 0, checked.stderr
    assert b'ACCEPTED' in checked.stdout


def test_native_observed_pose_movement(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler: pytest.skip('Native compiler required')
    root = Path(__file__).resolve().parents[2]
    exe = tmp_path/'observed-movement.exe'
    built = subprocess.run([compiler, '-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_observed_pose_movement.cpp'), '-o', str(exe)],
        capture_output=True, timeout=60)
    assert built.returncode == 0, built.stderr
    path = tmp_path/'hold.json'
    path.write_bytes(canonical(draft_settings(*inputs())[0]))
    checked = subprocess.run([str(exe), str(path)], capture_output=True, timeout=10)
    assert checked.returncode == 0, checked.stderr
    assert b'OBSERVED_POSE_CORE_SCENARIOS_PASSED' in checked.stdout


def test_public_replay_rejects_changed_report(monkeypatch, tmp_path):
    from rocell.application import observed_pose_candidate as module
    expected = dict(source_export='pose', motion_authorized=False)
    monkeypatch.setattr(module, '_build_report', lambda *args: expected)
    monkeypatch.setattr(module, '_read', lambda *args: (dict(expected), 'a'*64))
    assert module.replay_candidate(tmp_path, 'candidate')['replay_verified']
    monkeypatch.setattr(module, '_read', lambda *args:
        (dict(expected, motion_authorized=True), 'b'*64))
    with pytest.raises(ValueError, match='does not reproduce'):
        module.replay_candidate(tmp_path, 'candidate')


def test_private_staging_requires_explicit_mode():
    root = Path(__file__).resolve().parents[2]
    checked = subprocess.run([sys.executable, str(root/'scripts/stage_observed_pose_settings.py'),
        '--candidate-export', 'absent'], capture_output=True, text=True, timeout=10)
    assert checked.returncode == 2
    assert '--authorized-offline-private-staging' in checked.stderr


def test_r20_recovery_rejects_proposed_registration(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler: pytest.skip('Native compiler required')
    root = Path(__file__).resolve().parents[2]
    sketch = root/'.firmware-tools/configured-diagnostic-candidate-r20/RoArm-M3_example'
    exe = tmp_path/'recovery-compatibility.exe'
    built = subprocess.run([compiler, '-std=c++17', '-I'+str(sketch),
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_observed_pose_recovery_compatibility.cpp'),
        '-o', str(exe)], capture_output=True, timeout=60)
    assert built.returncode == 0, built.stderr
    previous, assessment = inputs()
    old_path, new_path = tmp_path/'old.json', tmp_path/'new.json'
    old_path.write_bytes(canonical(previous))
    new_path.write_bytes(canonical(draft_settings(previous, assessment)[0]))
    checked = subprocess.run([str(exe), str(old_path), str(new_path)],
        capture_output=True, timeout=10)
    assert checked.returncode == 0, checked.stderr


def test_new_recovery_board_profile_and_legacy(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler: pytest.skip('Native compiler required')
    root = Path(__file__).resolve().parents[2]
    exe = tmp_path/'observed-recovery-board.exe'
    built = subprocess.run([compiler, '-std=c++17', '-DROCELL_OBSERVED_POSE_RECOVERY',
        '-DROCELL_SIX_COUNT_RECOVERY',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_recovery_board_prepare.cpp'), '-o', str(exe)],
        capture_output=True, timeout=60)
    assert built.returncode == 0, built.stderr
    previous, assessment = inputs()
    for name, settings in [('legacy', previous), ('observed', draft_settings(previous, assessment)[0])]:
        path = tmp_path/(name+'.json'); path.write_bytes(canonical(settings))
        for fault in range(14):
            checked = subprocess.run([str(exe), str(path), str(fault)], capture_output=True, timeout=10)
            assert checked.returncode == 0, (name, fault, checked.stderr)
