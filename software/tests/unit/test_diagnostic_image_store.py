import json
import os

import pytest

from rocell.providers.windows import diagnostic_image_store as store


@pytest.fixture
def simulated_crypto(monkeypatch):
    # Shape/ordering tests only. Not a substitute for the native DPAPI test below.
    monkeypatch.setattr(store, '_crypt', lambda raw, decrypt: raw[::-1])


def test_roundtrip_and_no_overwrite(tmp_path, simulated_crypto):
    image = b'Z' * store.IMAGE_SIZE
    report = store.save_image(tmp_path, 'candidate.dpapi', image)
    assert not report['device_modified']
    assert store.load_image(report['path']) == image
    with pytest.raises(Exception):
        store.save_image(tmp_path, 'candidate.dpapi', b'Y' * store.IMAGE_SIZE)
    assert store.load_image(report['path']) == image


@pytest.mark.parametrize('change', ['reorder', 'truncate', 'mix'])
def test_chunk_binding(simulated_crypto, change):
    document = json.loads(store.protect_image(b'Z' * store.IMAGE_SIZE))
    if change == 'reorder':
        document['chunks'][0], document['chunks'][1] = document['chunks'][1], document['chunks'][0]
    elif change == 'truncate':
        document['chunks'].pop()
    else:
        other = json.loads(store.protect_image(b'Y' * store.IMAGE_SIZE))
        document['chunks'][1] = other['chunks'][1]
    with pytest.raises(ValueError):
        store.unprotect_image(json.dumps(document).encode())


def test_invalid_input_and_path(tmp_path):
    with pytest.raises(ValueError):
        store.protect_image(b'short')
    with pytest.raises(ValueError):
        store.save_image(tmp_path, '../escape.dpapi', b'Z' * store.IMAGE_SIZE)


@pytest.mark.skipif(os.name != 'nt', reason='Windows current-user DPAPI required')
def test_native_dpapi_roundtrip_and_ciphertext_tamper(tmp_path):
    image = bytes(range(256)) * (store.IMAGE_SIZE // 256)
    report = store.save_image(tmp_path, 'synthetic.dpapi', image)
    assert store.load_image(report['path']) == image
    document = json.loads((tmp_path / 'synthetic.dpapi').read_bytes())
    import base64
    chunk = bytearray(base64.b64decode(document['chunks'][0]))
    chunk[-1] ^= 1
    document['chunks'][0] = base64.b64encode(chunk).decode()
    with pytest.raises(Exception):
        store.unprotect_image(json.dumps(document).encode())
