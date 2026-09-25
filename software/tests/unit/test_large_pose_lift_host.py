import hashlib
from pathlib import Path
import shutil
import subprocess
import pytest

from rocell.application.large_pose_lift_host import LargePoseLiftHost


@pytest.fixture(scope="module")
def raw(tmp_path_factory):
    compiler=shutil.which("clang++")
    if not compiler:pytest.skip("Native compiler unavailable")
    root=Path(__file__).resolve().parents[2]
    target=tmp_path_factory.mktemp("lift-host")/"owner.exe"
    build=subprocess.run([compiler,"-std=c++17",str(root/"firmware/diagnostics/test_large_pose_lift_owner.cpp"),"-o",str(target)],capture_output=True,text=True,timeout=30)
    assert build.returncode==0,build.stderr
    run=subprocess.run([str(target),"success"],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    return bytes.fromhex(run.stdout.strip())


def test_exports_assesses_and_receipts_once(tmp_path,raw):
    calls=[]
    def transport(method,path,body=b""):
        calls.append((method,path,body))
        return {"/rocell/large-pose-lift/start":b"CAPTURING_START",
                "/rocell/large-pose-lift/status":b"AWAITING_DURABLE_EXPORT|1",
                "/rocell/large-pose-lift/record":raw.hex().encode(),
                "/rocell/large-pose-lift/receipt":b"LARGE_POSE_T1_RECORDED"}[path]
    host=LargePoseLiftHost(transport,export_root=tmp_path,boot="ab"*16)
    result=host.run_once(pause=lambda _:None)
    assert result["assessment"]["status"]=="T1_JOINT_ENDPOINT_MEASURED"
    assert Path(result["export"]).is_dir() and result["continuation_authorized"] is False
    assert calls[0]==("POST","/rocell/large-pose-lift/start",b"T1")
    assert calls[-1][2]==hashlib.sha256(raw).hexdigest().encode()
    with pytest.raises(ValueError):host.run_once()


def test_wrong_boot_never_receipts(tmp_path,raw):
    calls=[]
    def transport(method,path,body=b""):
        calls.append(path)
        return {"/rocell/large-pose-lift/start":b"CAPTURING_START",
                "/rocell/large-pose-lift/status":b"AWAITING_DURABLE_EXPORT|1",
                "/rocell/large-pose-lift/record":raw.hex().encode()}[path]
    with pytest.raises(ValueError,match="identity mismatch"):
        LargePoseLiftHost(transport,export_root=tmp_path,boot="cd"*16).run_once(pause=lambda _:None)
    assert "/rocell/large-pose-lift/receipt" not in calls


def test_terminal_fault_exported_without_retry(tmp_path):
    calls=[]
    def transport(method,path,body=b""):
        calls.append((method,path))
        return b"CAPTURING_START" if path.endswith("/start") else b"SOURCE_POSE_REJECTED|0"
    with pytest.raises(ValueError,match="terminal fault exported"):
        LargePoseLiftHost(transport,export_root=tmp_path,boot="ab"*16).run_once(pause=lambda _:None)
    assert calls==[("POST","/rocell/large-pose-lift/start"),("GET","/rocell/large-pose-lift/status")]
