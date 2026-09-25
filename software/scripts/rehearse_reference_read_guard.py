"""Reproduce/fix a pinned library read-validation defect using in-memory transport.

Compiles vendor protocol code with a fake transport, never Arduino startup code.
The candidate edit exists only in a temporary build directory. No device access.
"""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export

URL='https://files.waveshare.com/upload/5/5a/SERVO_DRIVER_WITH_ESP32.zip'
SHA='b8b377642b3eb45610226fdf96fbc61d7c012a512bdd7f8c904a9c1ac88328af'


def main():
    compiler=shutil.which('clang++')
    if not compiler:raise RuntimeError('Host compiler required')
    workspace=Path(__file__).resolve().parents[1]
    with urllib.request.urlopen(URL,timeout=20) as response:
        archive=response.read(16_000_001)
    if hashlib.sha256(archive).hexdigest()!=SHA:raise ValueError('Unreviewed archive bytes')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        members={name:z.read('SCServo/'+name) for name in ('SCS.cpp','SCS.h','INST.h')}
    source=members['SCS.cpp'].decode('utf-8-sig').replace('\r\r\n','\n').replace('\r\n','\n')
    anchor='\tint Size = readSCS(nData, nLen);'
    if source.count(anchor)!=1:raise ValueError('Patch anchor is not unique')
    guard='\tif(bBuf[0]!=ID || bBuf[1]!=(unsigned int)nLen+2){ return 0; }\n'
    candidate=source.replace(anchor,guard+anchor)
    results={}
    with tempfile.TemporaryDirectory(prefix='rocell-reference-read-') as temporary:
        root=Path(temporary)
        for name in ('SCS.h','INST.h'):(root/name).write_bytes(members[name])
        for variant,text in (('original',source),('candidate',candidate)):
            cpp=root/(variant+'.cpp');cpp.write_text(text,encoding='utf-8')
            executable=root/(variant+'.exe')
            command=[compiler,'-std=c++11','-I',str(root),str(cpp),
                str(workspace/'firmware/diagnostics/test_reference_read.cpp'),'-o',str(executable)]
            if variant=='candidate':command.append('-DROCELL_VALIDATE_RESPONSE')
            subprocess.run(command,check=True,capture_output=True,text=True,timeout=60)
            run=subprocess.run([str(executable)],check=True,capture_output=True,text=True,timeout=10)
            results[variant]=json.loads(run.stdout)
    report=dict(schema='rocell.reference_read_guard_rehearsal.v1',source_url=URL,
        archive_sha256=SHA,member_sha256={k:hashlib.sha256(v).hexdigest() for k,v in members.items()},
        candidate_normalized_source_sha256=hashlib.sha256(candidate.encode()).hexdigest(),
        harness_sha256=hashlib.sha256((workspace/'firmware/diagnostics/test_reference_read.cpp').read_bytes()).hexdigest(),
        adapter_sha256=hashlib.sha256((workspace/'firmware/diagnostics/reference_read_adapter.h').read_bytes()).hexdigest(),
        inserted_guard=guard.strip(),results=results,transport='IN_MEMORY_ONLY',
        installed_library_verified=False,installed_cause_proven=False,
        firmware_deployed=False,motion_commands=0)
    exporter=WizardDiagnosticExporter(workspace/'runs/wizard-exports');exporter.prepare(create=True)
    receipt=exporter.export({'mode':'reference-protocol-rehearsal'},[],
        attachments={'reference-read-guard.json':canonical(report)})
    if not verify_export(Path(receipt['path']))['valid']:raise ValueError('Export failed verification')
    print(json.dumps(dict(export=receipt['path'],verified=True,report=report)))


if __name__=='__main__':main()
