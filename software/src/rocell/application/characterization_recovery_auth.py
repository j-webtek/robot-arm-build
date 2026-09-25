"""One-shot offline recovery authenticator. No socket, retry or motion access.

Transport must impose a total deadline and reject duplicate authentication headers.
Nonce binds this read, not physical pose freshness or permission to resume.
"""
import hashlib
import hmac
import secrets
from .servo_start_authorization import _hex, _key


class RecoveryRead:
    def __init__(self, *, key, boot):
        _key(key)
        self._key = key
        self._boot = _hex(boot, 16)
        self._nonce = secrets.token_bytes(32)
        self._used = False

    def request_body(self):
        if self._used:
            raise ValueError('Recovery read already consumed')
        message = b'RCCRECOVERYREQUEST01\0'+self._boot+self._nonce
        return (self._nonce+hmac.digest(self._key, message, 'sha256')).hex().encode()

    def verify(self, *, status, body, signature):
        if self._used:
            raise ValueError('Recovery read already consumed')
        self._used = True  # All failures consume this attempt; no verification retries.
        if type(status) is not int or not 100 <= status <= 599 or type(body) is not bytes or len(body)>639:
            raise ValueError('Invalid recovery response')
        message = (b'RCCRECOVERYRESPONSE01\0'+self._boot+self._nonce
                   +status.to_bytes(2, 'big')+hashlib.sha256(body).digest())
        if not hmac.compare_digest(_hex(signature, 32), hmac.digest(self._key, message, 'sha256')):
            raise ValueError('Recovery authentication failed')
        if status != 200:
            raise ValueError('Recovery snapshot unavailable')
        return body
