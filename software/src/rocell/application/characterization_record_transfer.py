"""Bounded offline record assembly for future authenticated transport adapters.

Existing HTTP paths limit responses to 4095 bytes; campaign records can exceed
that. Each chunk must come from the same authenticated record snapshot.
"""
import hashlib
from .servo_start_authorization import _hex


class RecordTransfer:
    def __init__(self, *, boot, campaign, leg, size, sha256):
        _hex(boot,16); _hex(campaign,32); _hex(sha256,32)
        if type(leg) is not int or not 0 <= leg < 12 or type(size) is not int or not 0 < size <= 11000:
            raise ValueError('Invalid record limits')
        self._identity=(boot,campaign,leg)
        self._size,self._digest=size,sha256
        self._data=bytearray();self._terminal=False

    def append(self, *, boot, campaign, leg, offset, data):
        if self._terminal: raise ValueError('Transfer already terminal')
        if ((boot,campaign,leg)!=self._identity or type(leg) is not int
                or type(offset) is not int or offset!=len(self._data)
                or type(data) is not bytes or not 0<len(data)<=1024
                or len(self._data)+len(data)>self._size):
            self._terminal=True
            raise ValueError('Chunk identity, order or size mismatch')
        self._data.extend(data)

    def finish(self):
        if self._terminal: raise ValueError('Transfer already terminal')
        self._terminal=True
        if len(self._data)!=self._size or hashlib.sha256(self._data).hexdigest()!=self._digest:
            raise ValueError('Incomplete or altered record')
        return bytes(self._data)
