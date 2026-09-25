import subprocess
import pytest
from test_characterization_board_services import binary
from rocell.application.characterization_challenge import decode_challenge
from rocell.application.characterization_admission import sign_campaign


@pytest.fixture
def raw(binary,tmp_path):
    path=tmp_path/'challenge.bin'
    run=subprocess.run([str(binary),'success',str(path)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    return path.read_bytes()


def test_native_publication_to_host_signer(raw):
    decoded=decode_challenge(raw,expected_boot='11'*16)
    assert len(decoded['manifest']['goals'])==12
    assert decoded['manifest']['goals'][0]==[2397,1717]
    token=sign_campaign(decoded['manifest'],decoded['challenge'],bytes(range(32)),
                        campaign=decoded['campaign'],reference=decoded['reference'])
    assert 0<len(token)<=512


@pytest.mark.parametrize('case',['boot','truncated','trailing','magic'])
def test_invalid_publication(raw,case):
    boot='22'*16 if case=='boot' else '11'*16
    if case=='truncated':raw=raw[:-1]
    if case=='trailing':raw+=b'\0'
    if case=='magic':raw=b'X'+raw[1:]
    with pytest.raises(ValueError):decode_challenge(raw,expected_boot=boot)
