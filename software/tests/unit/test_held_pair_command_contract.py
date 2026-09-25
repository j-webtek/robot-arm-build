"""Cross-language initial pair authorization, synthetic key; no hardware."""
import hashlib
import hmac
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_command_contract import freeze_held_pair_plan, sign_held_pair
from rocell.application.servo_start_authorization import DOMAIN, _challenge_bytes


def inputs():
    root = Path(__file__).resolve().parents[2]
    policy = json.loads((root/'docs/hold-r7-supported-pose-draft.json').read_bytes())['hold_policy']
    policy['joints'] = [[p-8,p+8] for p in (2048,2390,1727,2723,2041,2042,2051)]
    policy['permit_explicit_enable'] = 0
    challenge = dict(schema='rocell.start_challenge.v1', boot_id='11'*16,
                     nonce='22'*32, issued_us=1000, expires_us=10001000)
    return root, policy, challenge


@pytest.mark.parametrize('offset,tolerance', [(0,2),(4,2),(17,2),(-17,2),(6,3),(True,0)])
def test_invalid_pair_geometry(offset, tolerance):
    _, policy, _ = inputs()
    with pytest.raises(ValueError):
        freeze_held_pair_plan(policy, boot_id='11'*16, hold_plan_sha256='a'*64,
            forward_command_id='forward', return_command_id='return',
            offset_counts=offset, tolerance_counts=tolerance)


def test_native_pair_plan_admission(tmp_path):
    compiler = shutil.which('clang++')
    if sys.platform != 'win32' or not compiler:
        pytest.skip('Windows crypto/compiler required')
    root, policy, challenge = inputs()
    exe = tmp_path/'pair-admission.exe'
    build = subprocess.run([compiler, '-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_held_pair_plan_admission.cpp'), '-lbcrypt', '-o', str(exe)],
        capture_output=True, text=True, timeout=60)
    assert build.returncode == 0, build.stderr
    plan = freeze_held_pair_plan(policy, boot_id='11'*16, hold_plan_sha256='a'*64,
                                forward_command_id='forward', return_command_id='return')
    signed = sign_held_pair(plan, challenge, b'k'*32, approved_policy=policy,
                            expected_hold_plan_sha256='a'*64)
    with pytest.raises(ValueError):
        sign_held_pair(plan, challenge, b'k'*32, approved_policy=policy,
                       expected_hold_plan_sha256='b'*64)
    payload = json.loads(plan.encoded)
    cases = [signed]
    for field, value in [('offset_counts',-6), ('tolerance_counts',1),
                         ('hold_plan_sha256','b'*64), ('policy_sha256','b'*64),
                         ('forward_command_id','other'), ('return_command_id','other'),
                         ('boot_id','33'*16), ('origin','SIMULATION'), ('extra',True)]:
        altered = canonical(dict(payload, **{field:value}))
        body = DOMAIN + _challenge_bytes(challenge) + struct.pack('>H',len(altered)) + altered
        cases.append(body+hmac.digest(b'k'*32,body,'sha256'))
    cases.append(signed[:-1]+bytes([signed[-1]^1]))
    for i, token in enumerate(cases):
        path = tmp_path/f'token-{i}.bin'
        path.write_bytes(token)
        run = subprocess.run([str(exe),str(path),str(int(i==0))],
                             capture_output=True,text=True,timeout=20)
        assert run.returncode == 0, run.stderr
        if i==0:
            assert run.stdout.strip() == hashlib.sha256(plan.encoded).hexdigest()
