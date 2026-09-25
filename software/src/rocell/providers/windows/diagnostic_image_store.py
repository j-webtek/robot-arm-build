"""Current-user encrypted storage for secret-bearing offline filesystem images.

Reuses the bounded Windows DPAPI primitive, not its bench-key file format.
Each protected chunk binds domain, full-image hash and index to reject mixing,
truncation and reordering. This cannot isolate other processes of the same user.
No plaintext files, automatic overwrite, device access or key generation.
"""
import base64
import hashlib
import json
import struct
from pathlib import Path

from rocell.application.diagnostic_provisioning_image import IMAGE_SIZE
from rocell.application.physical_onboarding_durability import (
    publish_reservation_bytes, read_bounded_regular_file,
)
from .bench_review_key import _crypt


DOMAIN = b'rocell.private-diagnostic-image.v1\0'
CHUNK = 8192
COUNT = (IMAGE_SIZE + CHUNK - 1) // CHUNK
MAX_ENVELOPE = 3 * 1024 * 1024


def protect_image(image):
    if type(image) is not bytes or len(image) != IMAGE_SIZE:
        raise ValueError('Invalid diagnostic image length')
    identity = hashlib.sha256(image).digest()
    chunks = []
    for index in range(COUNT):
        payload = DOMAIN + identity + struct.pack('>I', index) + image[index * CHUNK:(index + 1) * CHUNK]
        encrypted = _crypt(payload, decrypt=False)
        chunks.append(base64.b64encode(encrypted).decode('ascii'))
    envelope = json.dumps({'schema': 'rocell.private_diagnostic_image.v1',
                           'chunks': chunks}, separators=(',', ':')).encode('ascii')
    if len(envelope) > MAX_ENVELOPE or unprotect_image(envelope) != image:
        raise ValueError('Protected image verification failed')
    return envelope


def unprotect_image(envelope):
    if type(envelope) is not bytes or not 0 < len(envelope) <= MAX_ENVELOPE:
        raise ValueError('Invalid protected image size')
    document = json.loads(envelope)
    if (type(document) is not dict or set(document) != {'schema', 'chunks'} or
            document['schema'] != 'rocell.private_diagnostic_image.v1' or
            type(document['chunks']) is not list or len(document['chunks']) != COUNT):
        raise ValueError('Invalid protected image envelope')
    parts = []
    identity = None
    for index, encoded in enumerate(document['chunks']):
        if type(encoded) is not str or len(encoded) > 24000:
            raise ValueError('Invalid protected chunk')
        raw = _crypt(base64.b64decode(encoded, validate=True), decrypt=True)
        length = min(CHUNK, IMAGE_SIZE - index * CHUNK)
        if len(raw) != len(DOMAIN) + 36 + length or not raw.startswith(DOMAIN):
            raise ValueError('Protected chunk domain or size mismatch')
        digest = raw[len(DOMAIN):len(DOMAIN) + 32]
        if identity is None:
            identity = digest
        if digest != identity or raw[len(DOMAIN) + 32:len(DOMAIN) + 36] != struct.pack('>I', index):
            raise ValueError('Protected image chunk binding mismatch')
        parts.append(raw[len(DOMAIN) + 36:])
    image = b''.join(parts)
    if hashlib.sha256(image).digest() != identity:
        raise ValueError('Protected image digest mismatch')
    return image


def save_image(root, filename, image):
    """Exclusive, flushed encrypted publication; partial output stays reserved."""
    if not isinstance(filename, str) or Path(filename).name != filename or not filename.endswith('.dpapi'):
        raise ValueError('A simple .dpapi filename is required')
    encrypted = protect_image(image)
    path = publish_reservation_bytes(Path(root), filename, encrypted,
                                     maximum_bytes=MAX_ENVELOPE)
    if load_image(path) != image:
        raise ValueError('Published image verification failed')
    return {'path': str(path), 'image_sha256': hashlib.sha256(image).hexdigest(),
            'protection': 'WINDOWS_DPAPI_CURRENT_USER', 'device_modified': False}


def load_image(path):
    return unprotect_image(read_bounded_regular_file(Path(path), maximum_bytes=MAX_ENVELOPE))
