from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.characterization_request_auth import sign_request,verify_response


def test_native_web_response_to_host(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    source=Path(__file__).resolve().parents[2]/'firmware/diagnostics/test_characterization_authenticated_web.cpp'
    binary=tmp_path/'web.exe'
    build=subprocess.run([compiler,'-std=c++17',str(source),'-lbcrypt','-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert build.returncode==0,build.stderr
    key=bytes(range(32));boot='11'*16
    request=tmp_path/'request.bin';response=tmp_path/'response.txt'
    request.write_bytes(sign_request(key=key,boot=boot,sequence=0,method='GET',path='/rocell/characterization/status'))
    run=subprocess.run([str(binary),str(request),str(response)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    assert verify_response(key=key,boot=boot,sequence=0,status=200,body=b'{}',signature=bytes.fromhex(response.read_text()))==b'{}'
