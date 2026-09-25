import hashlib
import hmac
from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application import shoulder_export_receipt as receipt
from rocell.application.first_motion_contract import canonical

def event():
    return canonical(dict(schema='rocell.shoulder_hold_event.v1',boot_id='11'*16,
                          command_id='receipt-test',sequence=0))

def test_export_before_real_native_receipt_verification(tmp_path):
    raw=event();key=bytes(range(32))
    result=receipt.export_and_sign(tmp_path/'exports',raw,key=key,boot='11'*16,command='receipt-test',sequence=0)
    token=result['receipt'];assert len(token)==124
    assert hmac.compare_digest(token[-32:],hmac.digest(key,token[:-32],'sha256'))
    assert token[60:92]==hashlib.sha256(raw).digest()
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2];binary=tmp_path/'receipt.exe'
    built=subprocess.run([compiler,'-std=c++17',str(root/'firmware/diagnostics/test_shoulder_export_receipt.cpp'),
                          '-lbcrypt','-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert built.returncode==0,built.stderr
    token_path=tmp_path/'receipt.bin';token_path.write_bytes(token)
    checked=subprocess.run([str(binary),str(token_path),str(Path(result['export_path'])/'attachment-shoulder-event.txt')],
                           capture_output=True,text=True,timeout=10)
    assert checked.returncode==0,checked.stderr

def test_failed_export_never_signs(tmp_path,monkeypatch):
    monkeypatch.setattr(receipt,'verify_export',lambda path:{'valid':False})
    monkeypatch.setattr(receipt.hmac,'digest',lambda *a:pytest.fail('must not sign'))
    with pytest.raises(ValueError,match='verification'):
        receipt.export_and_sign(tmp_path,event(),key=bytes(range(32)),boot='11'*16,command='receipt-test',sequence=0)

def test_wrong_identity_rejected_before_export(tmp_path):
    with pytest.raises(ValueError,match='identity'):
        receipt.export_and_sign(tmp_path,event(),key=bytes(range(32)),boot='22'*16,command='receipt-test',sequence=0)
    assert not list(tmp_path.iterdir())
