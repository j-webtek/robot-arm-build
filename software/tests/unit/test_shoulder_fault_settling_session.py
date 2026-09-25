import json
from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.shoulder_export_receipt import export_and_sign
from rocell.application.shoulder_fault_settling_export import FaultSettlingExport


BOOT = '11' * 16
KEY = bytes(range(32))


def original():
    return json.dumps(dict(schema='rocell.shoulder_hold_event.v1', boot_id=BOOT,
        command_id='receipt-test', sequence=0, event='STATE_MISMATCH',
        scan_started_us=1, scan_finished_us=2)).encode()


@pytest.fixture(scope='module')
def settling_bridge(tmp_path_factory):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    binary = tmp_path_factory.mktemp('settling-bridge') / 'bridge.exe'
    built = subprocess.run([compiler, '-std=c++17',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_shoulder_fault_settling_session.cpp'),
        '-lbcrypt', '-o', str(binary)], capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stderr
    return binary


@pytest.mark.parametrize('mode', ['success', 'bad_original', 'bad_sample', 'replay_original'])
def test_authenticated_native_capture_exports(tmp_path, settling_bridge, mode):
    raw = original()
    initial = export_and_sign(tmp_path/'exports', raw, key=KEY, boot=BOOT,
                              command='receipt-test', sequence=0)['receipt']
    process = subprocess.Popen([str(settling_bridge)], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    reviewer = FaultSettlingExport(raw, boot=BOOT, parent_command='receipt-test')
    try:
        sent = initial if mode != 'bad_original' else initial[:-1]+bytes([initial[-1]^1])
        process.stdin.write(raw.decode()+'\n'+sent.hex()+'\n'); process.stdin.flush()
        terminal = None
        for _ in range(13):
            line = process.stdout.readline()
            assert line, process.stderr.read()
            doc = json.loads(line)
            if doc.get('terminal'):
                terminal = doc
                break
            exported = reviewer.export(tmp_path/'exports', line.rstrip().encode(), key=KEY)
            receipt = exported['receipt']
            if mode == 'bad_sample':
                receipt = receipt[:-1]+bytes([receipt[-1]^1])
            if mode == 'replay_original':
                receipt = initial
            process.stdin.write(receipt.hex()+'\n'); process.stdin.flush()
        assert terminal and terminal['settled'] == (mode == 'success')
        assert terminal['reads'] == (0 if mode == 'bad_original' else 28*terminal['count'])
        assert process.wait(timeout=5) == 0, process.stderr.read()
    finally:
        if process.poll() is None:
            process.kill(); process.wait(timeout=5)


def sample():
    import hashlib
    return dict(schema='rocell.shoulder_hold_event.v1', boot_id=BOOT,
        command_id='settle-receipt-test', sequence=0, event='FAULT_SETTLING_SAMPLE',
        parent_command_id='receipt-test', original_fault_sha256=hashlib.sha256(original()).hexdigest(),
        parent_fault_latched=True, movement_authorized=False, physical_accuracy_verified=False,
        scan_started_us=1000, scan_finished_us=2000,
        joints=[[sid, 2429, 2419, 1, (2429).to_bytes(2,'little').hex()+'00'*13]
                for sid in range(11,18)])


@pytest.mark.parametrize('field,value', [('original_fault_sha256','00'*32),
    ('parent_command_id','other'), ('boot_id','22'*16), ('sequence',1),
    ('scan_started_us',1), ('scan_finished_us',900000), ('movement_authorized',True),
    ('parent_fault_latched',False), ('joints',[])])
def test_malformed_evidence_never_gets_receipt(tmp_path, field, value):
    review = FaultSettlingExport(original(), boot=BOOT, parent_command='receipt-test')
    doc = sample(); doc[field] = value
    with pytest.raises(ValueError):
        review.export(tmp_path, json.dumps(doc).encode(), key=KEY)
    assert review.failed
    with pytest.raises(ValueError):
        review.export(tmp_path, json.dumps(sample()).encode(), key=KEY)
