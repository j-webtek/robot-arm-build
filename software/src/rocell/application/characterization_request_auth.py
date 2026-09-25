"""Offline request signing; no HTTP client, key provisioning or retry loop."""
import hashlib
import hmac
from .servo_start_authorization import _hex, _key


def sign_request(*, key, boot, sequence, method, path, body=b''):
    _key(key);boot_bytes=_hex(boot,16)
    if type(sequence) is not int or not 0<=sequence<4096 or method not in ('GET','POST'):
        raise ValueError('Invalid request sequence or method')
    if type(path) is not str or not path.isascii() or '\0' in path or not 1<=len(path)<=128:
        raise ValueError('Invalid exact path')
    if type(body) is not bytes or len(body)>1024:raise ValueError('Invalid request body')
    message=(b'RCCREQUEST01\0'+boot_bytes+sequence.to_bytes(4,'big')
             +bytes([method=='POST',len(path)])+path.encode('ascii')+hashlib.sha256(body).digest())
    return hmac.digest(key,message,'sha256')


def verify_response(*, key, boot, sequence, status, body, signature):
    """Verify exact response bytes before JSON/hex decoding. Caller tracks outstanding request."""
    _key(key);boot_bytes=_hex(boot,16)
    if (type(sequence) is not int or not 0<=sequence<4096 or type(status) is not int
            or not 100<=status<=599 or type(body) is not bytes or len(body)>4095
            or type(signature) is not bytes or len(signature)!=32):
        raise ValueError('Invalid response framing')
    message=(b'RCCRESPONSE01\0'+boot_bytes+sequence.to_bytes(4,'big')
             +status.to_bytes(2,'big')+hashlib.sha256(body).digest())
    if not hmac.compare_digest(signature,hmac.digest(key,message,'sha256')):
        raise ValueError('Response authentication failed')
    return body
