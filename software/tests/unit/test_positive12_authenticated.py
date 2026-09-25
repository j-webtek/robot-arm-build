"""Signed +12 native path with synthetic key/bus; never opens a device."""
import hashlib
import json
import shutil
import subprocess
import sys

import pytest

from test_held_pair_command_contract import inputs
from rocell.application.hold_command_contract import freeze_hold_plan, sign_hold
from rocell.application.held_pair_command_contract import freeze_held_pair_plan, sign_held_pair


def test_positive12_signed_native_forward(tmp_path):
    compiler=shutil.which('clang++')
    if sys.platform!='win32' or not compiler:
        pytest.skip('Windows native crypto/compiler required')
    root,policy,challenge=inputs()
    policy['joints'][3]=[2719,2735]  # Translated synthetic fixture, not hardware pose.
    exe=tmp_path/'positive12.exe'
    built=subprocess.run([compiler,'-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_held_pair_authenticated_runtime.cpp'),
        '-lbcrypt','-o',str(exe)],capture_output=True,text=True,timeout=60)
    assert built.returncode==0,built.stderr
    hold=freeze_hold_plan(policy,boot_id=challenge['boot_id'],command_id='verified-hold')
    hold_hash=hashlib.sha256(hold.encoded).hexdigest()
    hold_path=tmp_path/'hold.bin'
    hold_path.write_bytes(sign_hold(hold,dict(challenge,nonce='44'*32),b'k'*32,approved_policy=policy))
    for offset in (12,6):
        plan=freeze_held_pair_plan(policy,boot_id=challenge['boot_id'],hold_plan_sha256=hold_hash,
            forward_command_id='elbow-plus12-forward',return_command_id='elbow-plus12-return',
            offset_counts=offset,tolerance_counts=2)
        path=tmp_path/f'pair-{offset}.bin'
        path.write_bytes(sign_held_pair(plan,challenge,b'k'*32,approved_policy=policy,
            expected_hold_plan_sha256=hold_hash))
        result=subprocess.run([str(exe),str(path),'-','1' if offset==12 else '0','0',
            str(hold_path),'positive12'],capture_output=True,timeout=20)
        assert result.returncode==0,result.stderr
        if offset==12:
            meta=json.loads(result.stdout.splitlines()[0])
            forward=json.loads(meta['forward_plan_json'])
            assert forward['target_count']==2735
            assert meta['session_sha256']==hashlib.sha256(plan.encoded).hexdigest()
            assert json.loads(meta['transport_status_json'])['state']=='AWAITING_EXPORT'
