from pathlib import Path
import shutil
import subprocess
import hashlib
import pytest
from rocell.application.characterization_admission import sign_campaign, encode_manifest


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    compiler = shutil.which('clang++')
    if not compiler: pytest.skip('Native compiler unavailable')
    root = Path(__file__).resolve().parents[2]
    target = tmp_path_factory.mktemp('campaign-admission')/'admission.exe'
    run = subprocess.run([compiler, '-std=c++17', str(root/'firmware/diagnostics/test_characterization_admission.cpp'),
                          '-lbcrypt', '-o', str(target)], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    return target


def inputs():
    return ({'goals': [[2397,1717],[2405,1709]], 'bounds': [[0,4095] for _ in range(7)], 'maximum_us':60000000},
            dict(schema='rocell.start_challenge.v1', boot_id='11'*16, nonce='22'*32, issued_us=1000, expires_us=11000))


@pytest.mark.parametrize('case', ['valid','tamper','campaign','reference','manifest','boot','nonce','expired','early','trailing'])
def test_host_signed_native_admission(binary, tmp_path, case):
    manifest, challenge = inputs(); campaign='33'*32; reference='44'*32
    if case=='campaign': campaign='55'*32
    if case=='reference': reference='55'*32
    if case=='manifest': manifest['maximum_us']=50000000
    if case=='boot': challenge['boot_id']='55'*16
    if case=='nonce': challenge['nonce']='55'*32
    key=bytes(range(32))
    token=sign_campaign(manifest,challenge,key,campaign=campaign,reference=reference)
    if case=='tamper': token=token[:-1]+bytes([token[-1]^1])
    if case=='trailing': token+=b'\0'
    path=tmp_path/'token.bin';path.write_bytes(token)
    now=11000 if case=='expired' else 999 if case=='early' else 1001
    run=subprocess.run([str(binary),str(path),str(now),'yes' if case=='valid' else 'no'],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    size=int(run.stdout.strip().split('session_bytes=')[1])
    assert size < 32768  # Host ABI regression budget, not ESP32 heap validation.


@pytest.mark.parametrize('bad', [True, 0, 60000001])
def test_invalid_budget_rejected(bad):
    manifest,_=inputs();manifest['maximum_us']=bad
    with pytest.raises(ValueError): encode_manifest(manifest,campaign='33'*32,reference='44'*32)


@pytest.mark.parametrize('mode', ['complete', 'wrong-campaign', 'replay', 'missing'])
def test_unified_native_session(binary, tmp_path, mode):
    manifest, challenge = inputs()
    token = sign_campaign(manifest, challenge, bytes(range(32)), campaign='33'*32, reference='44'*32)
    path = tmp_path/'token.bin';path.write_bytes(token)
    run = subprocess.run([str(binary), str(path), '1001', 'yes', mode], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr


def test_native_record_to_host_assembler(binary, tmp_path):
    from rocell.application.characterization_record_transfer import RecordTransfer
    from rocell.application.characterization_result_codec import decode_result
    manifest, challenge = inputs()
    token=sign_campaign(manifest,challenge,bytes(range(32)),campaign='33'*32,reference='44'*32)
    source=tmp_path/'token.bin';source.write_bytes(token)
    artifact=tmp_path/'record.bin'
    run=subprocess.run([str(binary),str(source),'1001','yes','complete',str(artifact)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    raw=artifact.read_bytes()
    transfer=RecordTransfer(boot='11'*16,campaign='33'*32,leg=0,size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    for offset in range(0,len(raw),128):
        transfer.append(boot='11'*16,campaign='33'*32,leg=0,offset=offset,data=raw[offset:offset+128])
    result=decode_result(transfer.finish())
    assert result['goals']==manifest['goals'] and result['outcome']=='SETTLED_MISS'
