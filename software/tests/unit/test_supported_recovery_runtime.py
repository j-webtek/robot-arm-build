"""Real HMAC/native runtime with a scripted bus; never connects to hardware."""
import hashlib
import copy
import hmac
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_start_authorization import DOMAIN
from rocell.application.supported_recovery_review import assess_recovery, export_recovery, replay_recovery
from rocell.application.supported_recovery_start import freeze_recovery_plan, sign_recovery


def test_recovery_native_admission_and_retained_records(tmp_path):
    compiler = shutil.which('clang++')
    if sys.platform != 'win32' or not compiler:
        pytest.skip('Windows native crypto/compiler required')
    root = Path(__file__).resolve().parents[2]
    exe = tmp_path / 'recovery.exe'
    built = subprocess.run([compiler, '-std=c++17',
        '-I' + str(root / '.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root / 'firmware/diagnostics/test_supported_recovery_runtime.cpp'),
        '-lbcrypt', '-o', str(exe)], capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    hold = dict(acceleration=1, age_us=250000, baseline_gap_us=100000,
        deadline_us=2000000, drift=2,
        joints=[[p-8, p+8] for p in (2048,2390,1727,2723,2041,2042,2051)],
        maximum_gap_us=500000, pair_us=10000, permit_explicit_enable=0,
        scan_us=100000, schema='rocell.hold_policy.v1', servo_id=14,
        settle_us=100000, speed=20)
    policy = dict(hold_policy=hold, initial_residual_counts=5,
                  schema='rocell.supported_recovery_policy.v1')
    plan = dict(boot_id='11'*16, command_id='reviewed-recovery', origin='DEVICE_CAPTURE',
        policy_sha256=hashlib.sha256(canonical(policy)).hexdigest(),
        schema='rocell.supported_recovery_plan.v1')
    cases = [plan, dict(plan, schema='rocell.hold_plan.v1'),
             dict(plan, command_id='other'), dict(plan, boot_id='33'*16),
             dict(plan, policy_sha256=hashlib.sha256(canonical(hold)).hexdigest()),
             dict(plan, origin='SIMULATION')]
    for i, candidate in enumerate(cases + [plan]):
        payload = canonical(candidate)
        body = DOMAIN + bytes.fromhex('11'*16) + bytes.fromhex('22'*32)
        body += struct.pack('>QQH', 1000, 10001000, len(payload)) + payload
        signature = hmac.digest(b'k'*32, body, 'sha256')
        if i == 0:
            frozen = freeze_recovery_plan(policy, boot_id=plan['boot_id'], command_id=plan['command_id'])
            assert frozen.encoded == payload
            assert sign_recovery(frozen, dict(schema='rocell.start_challenge.v1',
                boot_id='11'*16, nonce='22'*32, issued_us=1000, expires_us=10001000),
                b'k'*32, approved_policy=policy) == body + signature
        if i == len(cases):
            signature = bytes([signature[0]^1]) + signature[1:]
        path = tmp_path / f'token-{i}.bin'
        path.write_bytes(body + signature)
        result = subprocess.run([str(exe), str(path), '1' if i == 0 else '0'],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        if i != 0:
            assert not result.stdout
            continue
        records = [json.loads(line) for line in result.stdout.splitlines()]
        assert len(records) == 8
        for record in records:
            assert record['schema'].startswith('rocell.supported_recovery_')
            assert record['plan_sha256'] == hashlib.sha256(payload).hexdigest()
            assert record['policy_sha256'] == plan['policy_sha256']
            assert record['boot_id'] == plan['boot_id']
            assert record['command_id'] == plan['command_id']
        assert records[0]['policy'] == policy
        assert records[-1]['state'] == 'CAPTURED'
        assert records[-1]['action_count'] == 1
        assert records[-1]['whole_arm_ready'] is False
        assessed = assess_recovery(records, expected_plan=plan, expected_policy=policy, origin='SIMULATION')
        assert assessed['category'] == 'SIMULATED_RECOVERY_VERIFIED'
        assert assessed['endpoint']['previous_goal'] == 2728
        assert assessed['endpoint']['requested_hold_target'] == 2723
        assert assessed['endpoint']['encoded_command_target'] == 2723
        assert assessed['endpoint']['settled_error_counts'] == 0
        assert assessed['progression_authority'] is False
        assert assessed['provenance_verified'] is False
        exported = export_recovery(tmp_path / 'exports', records,
            expected_plan=plan, expected_policy=policy, origin='SIMULATION')
        assert replay_recovery(exported['path']) == assessed
        reported = assess_recovery(records, expected_plan=plan, expected_policy=policy, origin='DEVICE_CAPTURE')
        assert reported['category'] == 'CONTROLLER_REPORTED_RECOVERY_VERIFIED'
        assert reported['provenance_verified'] is False
        for fault in range(13):
            bad = copy.deepcopy(records)
            if fault == 0: bad[0]['schema'] = 'rocell.hold_authorization.v1'
            if fault == 1: bad[2]['boot_id'] = '33'*16
            if fault == 2: bad[4]['payload_hex'] = '01a80a00001400'  # old goal, not fresh position
            if fault == 3: bad[4]['library_return'] = 0
            if fault == 4: bad[1]['reads'][6][3][-1] = 'a90a'  # six-count residual
            if fault == 5: bad[3]['reads'][6][3][-1] = 'a70a'  # changed prewrite goal
            if fault == 6: bad[6]['reads'][7][3][-1] = 'a60a' + '00'*13  # three-count arrival error
            if fault == 7: bad[6]['reads'][21][3][-1] = '00'  # torque loss
            if fault == 8: bad[6]['reads'][0][3][4] = 1  # device error
            if fault == 9: bad[3], bad[4] = bad[4], bad[3]  # record reordering
            if fault == 10: bad[-1]['snapshot_count'] = True
            if fault == 11: bad.pop(5)
            if fault == 12: bad[-1]['state'] = 'FAULT'
            failure = assess_recovery(bad, expected_plan=plan, expected_policy=policy, origin='SIMULATION')
            assert failure['category'] == 'INCONCLUSIVE', fault
            assert 'endpoint' not in failure
            if fault == 3:
                failed_export = export_recovery(tmp_path / 'exports', bad,
                    expected_plan=plan, expected_policy=policy, origin='SIMULATION')
                assert replay_recovery(failed_export['path']) == failure
        altered = Path(exported['path']) / 'attachment-recovery-assessment.json'
        altered.write_text('{}', encoding='utf-8')
        with pytest.raises(ValueError): replay_recovery(exported['path'])
