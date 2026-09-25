from pathlib import Path
import subprocess
import shutil
import pytest
from rocell.application.characterization_request_auth import sign_request, verify_response


def test_host_native_request_binding(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    source=Path(__file__).resolve().parents[2]/'firmware/diagnostics/test_characterization_request_auth.cpp'
    binary=tmp_path/'auth.exe'
    build=subprocess.run([compiler,'-std=c++17',str(source),'-lbcrypt','-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert build.returncode==0,build.stderr
    signature=sign_request(key=bytes(range(32)),boot='11'*16,sequence=0,method='GET',path='/rocell/characterization/status')
    path=tmp_path/'signature.bin';path.write_bytes(signature)
    response=tmp_path/'response.bin'
    run=subprocess.run([str(binary),str(path),str(response)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    args=dict(key=bytes(range(32)),boot='11'*16,sequence=0,status=200,body=b'{}',signature=response.read_bytes())
    assert verify_response(**args)==b'{}'
    for changed in ({'boot':'22'*16},{'sequence':1},{'status':409},{'body':b'{ }'}):
        with pytest.raises(ValueError):verify_response(**(args|changed))
