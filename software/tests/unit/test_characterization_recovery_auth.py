import hashlib
import hmac
import pytest
from rocell.application.characterization_recovery_auth import RecoveryRead

KEY=bytes(range(32))
BOOT='11'*16


@pytest.mark.parametrize('case', ['valid','tampered','wrong_boot','wrong_nonce','status','replay'])
def test_response_binding_and_one_shot(case):
    read=RecoveryRead(key=KEY,boot=BOOT)
    request=bytes.fromhex(read.request_body().decode())
    expected=hmac.digest(KEY,b'RCCRECOVERYREQUEST01\0'+bytes.fromhex(BOOT)+request[:32],'sha256')
    assert request[32:]==expected
    boot=bytes.fromhex('22'*16 if case=='wrong_boot' else BOOT)
    nonce=b'x'*32 if case=='wrong_nonce' else request[:32]
    status=409 if case=='status' else 200
    body=b'{}'
    signature=hmac.digest(KEY,b'RCCRECOVERYRESPONSE01\0'+boot+nonce+
        status.to_bytes(2,'big')+hashlib.sha256(body).digest(),'sha256').hex()
    if case in ('valid','replay'):
        assert read.verify(status=status,body=body,signature=signature)==body
    else:
        with pytest.raises(ValueError):
            read.verify(status=status,body=b'[]' if case=='tampered' else body,signature=signature)
    with pytest.raises(ValueError):
        read.verify(status=status,body=body,signature=signature)
    with pytest.raises(ValueError):
        read.request_body()
