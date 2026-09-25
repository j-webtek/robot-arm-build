"""Real offline filesystem tests; synthetic keys/policy, no hardware access."""
import hashlib
from pathlib import Path
import sys

import pytest

from rocell.application.diagnostic_provisioning_image import stage_image


@pytest.fixture
def library():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] /
                           '.firmware-tools/littlefs-review'))
    import littlefs
    return littlefs


def image(library, existing=False):
    context = library.UserContext(buffsize=352 * 4096)
    fs = library.LittleFS(context=context, mount=False, block_size=4096,
                          block_count=352, read_size=256, prog_size=256)
    fs.format()  # Synthetic test image ONLY; production staging never formats.
    fs.mount()
    fs.mkdir('/nested')
    with fs.open('/nested/preserved', 'wb') as stream:
        stream.write(b'unchanged content')
    if existing:
        with fs.open('/rocell-diagnostics.key', 'wb') as stream:
            stream.write(b'preserve me')
    fs.unmount()
    return bytes(context.buffer)


def stage(source, library, **overrides):
    args = dict(expected_sha256=hashlib.sha256(source).hexdigest(), policy=b'{}',
                key=b'K' * 32, littlefs=library, validate_policy=lambda data: True)
    args.update(overrides)
    return stage_image(source, **args)


def test_remount_and_preservation(library):
    source = image(library)
    candidate, report = stage(source, library)
    assert candidate != source and len(candidate) == len(source)
    assert report['existing_entries_preserved'] == 2
    assert report['remount_verified'] and not report['device_modified']
    assert 'key' not in report and b'unchanged content' in source


@pytest.mark.parametrize('overrides', [
    {'expected_sha256': '0' * 64}, {'policy': b''}, {'policy': b'x' * 4097},
    {'key': b'x'}, {'key': bytes(32)}, {'key': bytes(range(32))},
    {'validate_policy': lambda data: False},
])
def test_reject_inputs(library, overrides):
    with pytest.raises(ValueError):
        stage(image(library), library, **overrides)


def test_no_overwrite(library):
    with pytest.raises(ValueError, match='already exist'):
        stage(image(library, existing=True), library)


def test_corrupt_filesystem_is_not_formatted(library):
    with pytest.raises(Exception):
        stage(bytes(352 * 4096), library)


def test_write_failure_returns_no_candidate(library, monkeypatch):
    source = image(library)
    original = library.LittleFS.open

    def failing_open(self, path, mode='r', *args, **kwargs):
        if mode == 'xb':
            raise OSError('Synthetic filesystem full')
        return original(self, path, mode, *args, **kwargs)

    monkeypatch.setattr(library.LittleFS, 'open', failing_open)
    with pytest.raises(OSError, match='filesystem full'):
        stage(source, library)
    assert hashlib.sha256(source).hexdigest() == hashlib.sha256(image(library)).hexdigest()
