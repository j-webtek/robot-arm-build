"""Offline plan checks and actual pinned Waveshare conversion, never hardware."""
import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from rocell.application.startup_first_trial import build_first_trial
from rocell.application.startup_command_contract import validate_startup_plan

ROOT = Path(__file__).resolve().parents[2]
BOOT = '11' * 16


def configuration():
    return json.loads((ROOT / 'docs/startup-r6-policy-draft.json').read_bytes())


def test_bounded_plan_and_exact_policy():
    config = configuration()
    plan = build_first_trial(config, boot_id=BOOT, command_id='offline-first-trial')
    doc = validate_startup_plan(plan, BOOT, config['startup_policy'])
    assert doc['origin'] == 'SIMULATION'
    assert doc['command']['wire_count'] == doc['command']['desired_count'] == 2727
    assert doc['baseline_policy']['maximum_delta_counts'] == 8
    assert doc['schedule']['sample_count'] == 6
    assert doc['schedule']['sample_interval_us'] == 500000
    assert doc['policy']['settle_us'] == 1000000
    bad = copy.deepcopy(config)
    bad['startup_policy']['drift_tolerance'] = 16
    with pytest.raises(ValueError): build_first_trial(bad, boot_id=BOOT, command_id='bad')


@pytest.mark.parametrize('target', [True, 0, 2658, 2787, 3072, 2727.0])
def test_reject_invalid_or_outside_conversion_bounds(target):
    with pytest.raises(ValueError):
        build_first_trial(configuration(), boot_id=BOOT, command_id='bad', target_count=target)


def test_actual_pinned_conversion_roundtrip(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler: pytest.skip('Native compiler required')
    tools = ROOT / '.firmware-tools'
    reference = tools / 'reference/RoArm-M3_example/RoArm-M3_module.h'
    raw = reference.read_bytes()
    manifest = json.loads((tools / 'reference-build-inputs.json').read_bytes())
    assert hashlib.sha256(raw).hexdigest() == manifest['files'][str(reference.relative_to(tools))]
    source = raw.decode('utf-8-sig').replace('\r\r\n', '\n').replace('\r\n', '\n')
    bodies = []
    for signature in ('double calculatePosByRad(', 'int RoArmM3_elbowJointCtrlRad('):
        start = source.index(signature)
        bodies.append(source[start:source.index('\n}', start)+2])
    config = configuration()
    doc = validate_startup_plan(build_first_trial(config, boot_id=BOOT, command_id='convert'),
        BOOT, config['startup_policy'])
    # Compile extracted pinned function bodies, with a bus that aborts on writes.
    cpp = '''#define _USE_MATH_DEFINES
#include <cmath>
#include <cassert>
#include <algorithm>
using byte=unsigned char; using u16=unsigned short; using u8=unsigned char; using s16=short;
const int ARM_SERVO_POS_RANGE=4096, ELBOW_SERVO_ID=14; int goalPos[7]={};
template<class A,class B> A constrain(A x,B low,B high){return std::min<A>(std::max<A>(x,low),high);}
struct Bus { void WritePosEx(int,int,int,int){assert(false);} } st;
'''+ '\n'.join(bodies) + '\nint main(){assert(RoArmM3_elbowJointCtrlRad(0,' + repr(doc['command']['wire_rad']) + ',20,1)==2727);}\n'
    path = tmp_path / 'conversion.cpp'
    path.write_text(cpp)
    exe = tmp_path / 'conversion.exe'
    subprocess.run([compiler, '-std=c++14', str(path), '-o', str(exe)], check=True,
                   capture_output=True, timeout=30)
    subprocess.run([str(exe)], check=True, capture_output=True, timeout=5)
