"""Two-file replacement on synthetic LittleFS only; no private backup access."""
import hashlib
import pytest
from test_diagnostic_provisioning_image import library, image
from test_observed_pose_candidate import inputs
from rocell.application.observed_pose_candidate import draft_settings
from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_settings import encode_pair_settings
from rocell.application.diagnostic_provisioning_image import (
    stage_hold_image, stage_pair_settings_image, replace_observed_pose_image)


def fixture(library):
    previous, assessment = inputs()
    old_hold = canonical(previous)
    old_pair = encode_pair_settings(forward_command_id='r10-elbow-forward',
        return_command_id='r10-elbow-return', offset_counts=-6)
    hold, pair = map(canonical, draft_settings(previous, assessment))
    source = image(library)
    # Permissive validators only seed this synthetic image. Native parser
    # compatibility of the exact candidate is covered by separate native tests.
    source, _ = stage_hold_image(source, hashlib.sha256(source).hexdigest(), old_hold,
        b'H'*32, littlefs=library, validate_policy=lambda _: True)
    source, _ = stage_pair_settings_image(source, hashlib.sha256(source).hexdigest(),
        old_pair, old_hold, littlefs=library, validate_settings=lambda _: True,
        validate_hold_policy=lambda _: True)
    args = dict(expected_sha256=hashlib.sha256(source).hexdigest(), previous_hold=old_hold,
        previous_pair=old_pair, hold=hold, pair=pair, littlefs=library,
        validate_hold=lambda raw: raw in (old_hold, hold),
        validate_pair=lambda raw: raw in (old_pair, pair))
    return source, args


def test_only_two_reviewed_files_change(library, monkeypatch):
    source, args = fixture(library)
    writes = []; original = library.LittleFS.open
    def tracked(self, path, mode='r', *a, **kw):
        if mode in ('wb', 'xb'): writes.append(path)
        return original(self, path, mode, *a, **kw)
    monkeypatch.setattr(library.LittleFS, 'open', tracked)
    candidate, report = replace_observed_pose_image(source, **args)
    assert writes == ['/rocell-hold.json', '/rocell-pair.json']
    assert candidate != source and len(candidate) == len(source)
    assert report['unrelated_entries_preserved'] and report['existing_key_preserved']
    assert not report['device_modified'] and report['physical_authority'] == 'NONE'
    assert hashlib.sha256(source).hexdigest() == args['expected_sha256']


@pytest.mark.parametrize('fault', ['source', 'hold', 'pair', 'native', 'second_write'])
def test_failure_returns_no_partial_candidate(library, monkeypatch, fault):
    source, args = fixture(library)
    if fault == 'source': args['expected_sha256'] = '0'*64
    if fault in ('hold', 'pair'): args[fault] += b' '
    if fault == 'native': args['validate_pair'] = lambda _: False
    if fault == 'second_write':
        original = library.LittleFS.open
        def fail(self, path, mode='r', *a, **kw):
            if path == '/rocell-pair.json' and mode == 'wb': raise OSError('Synthetic full disk')
            return original(self, path, mode, *a, **kw)
        monkeypatch.setattr(library.LittleFS, 'open', fail)
    digest = hashlib.sha256(source).hexdigest()
    with pytest.raises((ValueError, OSError)):
        replace_observed_pose_image(source, **args)
    assert hashlib.sha256(source).hexdigest() == digest
