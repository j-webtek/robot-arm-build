"""Native stored-evidence matching and real HMAC, with synthetic bus and key."""
import hmac
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_start_authorization import DOMAIN
from rocell.application.held_evidence_digest import held_evidence_digest


def test_stored_return_admission(tmp_path):
    compiler = shutil.which('clang++')
    if sys.platform != 'win32' or not compiler:
        pytest.skip('Windows native crypto/compiler required')
    root = Path(__file__).resolve().parents[2]
    exe = tmp_path/'stored-return.exe'
    build = subprocess.run([compiler, '-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_held_stored_return_admission.cpp'),
        '-lbcrypt', '-o', str(exe)], capture_output=True, text=True, timeout=60)
    assert build.returncode == 0, build.stderr
    dump = subprocess.run([str(exe), 'dump'], capture_output=True, timeout=20)
    assert dump.returncode == 0, dump.stderr
    rows = [(k.decode(), raw) for k, raw in
            (line.split(b'\t', 1) for line in dump.stdout.splitlines())]
    assert len(rows) == 7
    plan = dict(schema='rocell.held_return_authorization.v1', boot_id='11'*16,
                session_sha256='a'*64, forward_plan_sha256='b'*64,
                evidence_sha256=held_evidence_digest(rows), export_sha256='d'*64,
                return_target_count=2902, origin='DEVICE_CAPTURE')
    for case in range(16):
        changed = dict(plan)
        if case == 8:
            changed['evidence_sha256'] = '0'*64
        if case == 10:
            changed['return_target_count'] = 2908
        if case == 12:
            changed['session_sha256'] = 'e'*64
        if case == 13:
            changed['forward_plan_sha256'] = 'e'*64
        payload = canonical(changed)
        body = (DOMAIN + bytes.fromhex('11'*16) + bytes.fromhex('22'*32) +
                struct.pack('>QQH', 1000, 1001 if case == 11 else 10001000, len(payload)) + payload)
        signature = hmac.digest(b'k'*32, body, 'sha256')
        if case == 9:
            signature = bytes([signature[0]^1]) + signature[1:]
        token = tmp_path/f'token-{case}.bin'
        token.write_bytes(body+signature)
        mutation = case-1 if 1 <= case <= 7 else -1
        if case == 14:
            mutation = -2  # Changed neighbor after signed admission.
        if case == 15:
            mutation = -3  # Return evidence store fails before any return write.
        run = subprocess.run([str(exe), str(token), str(int(case in (0,14,15))), str(mutation)],
                             capture_output=True, text=True, timeout=20)
        assert run.returncode == 0, run.stderr
