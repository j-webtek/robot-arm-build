import hashlib
import pytest
from rocell.application.characterization_reference import decode_reference


def reference():
    raw=bytearray()
    for index in range(3):
        start=100000+index*200000
        raw.extend(start.to_bytes(8,'big'));raw.extend((start+10000).to_bytes(8,'big'))
        for _ in range(7):
            raw.extend((2047).to_bytes(2,'big')*2+b'\x01')
            raw.extend((2047).to_bytes(2,'little')+bytes(13))
    return raw


@pytest.mark.parametrize('fault',[None,'length','digest','raw','moving','torque','unstable','time'])
def test_reference_validation(fault):
    raw=reference()
    if fault=='length':raw.pop()
    if fault=='raw':raw[21]^=1
    if fault=='moving':raw[23]=1
    if fault=='torque':raw[20]=0
    if fault=='unstable':raw[174]=0 # Second pose goal differs.
    if fault=='time':raw[156:164]=(1).to_bytes(8,'big')
    digest='00'*32 if fault=='digest' else hashlib.sha256(raw).hexdigest()
    if fault:
        with pytest.raises(ValueError):decode_reference(bytes(raw),expected_sha256=digest)
    else:
        assert len(decode_reference(bytes(raw),expected_sha256=digest)['poses'])==3
