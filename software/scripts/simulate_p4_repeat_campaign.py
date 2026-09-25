"""Compile the native test owner and export twelve explicitly simulated legs.

No serial port, network client, startup or firmware installation is used.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from rocell.application.p4_repeat_campaign import P4RepeatHost


def main():
    root=Path(__file__).resolve().parents[1]
    compiler=shutil.which('clang++')
    if not compiler:raise ValueError('Native compiler unavailable')
    with tempfile.TemporaryDirectory(prefix='p4-repeat-simulation-') as folder:
        executable=Path(folder)/'owner.exe'
        subprocess.run([compiler,'-std=c++17','-I'+str(root/'firmware/diagnostics'),
            '-I'+str(root/'.firmware-tools/configured-diagnostic-candidate-r71/RoArm-M3_example'),
            str(root/'firmware/diagnostics/test_p4_repeat_owner.cpp'),'-o',str(executable)],
            check=True,capture_output=True,timeout=30)
        native=subprocess.run([str(executable),'success'],check=True,capture_output=True,text=True,timeout=10)
    records=[bytes.fromhex(line) for line in native.stdout.splitlines()]
    if len(records)!=12:raise ValueError('Incomplete native simulation')
    leg=1;ready=False
    def transport(method,path,body=b''):
        nonlocal leg,ready
        action=path.rsplit('/',1)[-1]
        if action=='start' and method=='POST' and body==b'P4R12':return b'CAPTURING_START'
        if action=='status' and not ready:return f'AWAITING_EXPORT|{leg}'.encode()
        if action=='record' and not ready:return records[leg-1].hex().encode()
        if action=='receipt' and not ready:
            if body!=f'{leg}:{hashlib.sha256(records[leg-1]).hexdigest()}'.encode():
                raise ValueError('Receipt differs')
            ready=True
            return b'COMPLETE' if leg==12 else f'READY|{leg+1}'.encode()
        if action=='next' and ready and leg<12 and body==str(leg+1).encode():
            ready=False;leg+=1;return b'CAPTURING_START'
        raise ValueError('Unexpected simulated transport operation')
    result=P4RepeatHost(transport,boot='ab'*16,export_root=root/'runs/wizard-exports',
        source_kind='simulation').run_once()
    print(json.dumps(dict(status=result['status'],source_kind='simulation',hardware_access=False,
        exports=result['exports'],legs=len(result['rows']))))


if __name__=='__main__':main()
