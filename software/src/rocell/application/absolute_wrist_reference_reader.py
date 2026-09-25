"""Reconstruct absolute-worker references from retained original bytes."""
import hashlib
from pathlib import Path

from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from .wizard_diagnostic_coordinator import source_fingerprint, decode_diagnostic_json
from .physical_onboarding_durability import safe_root, contained_path, read_bounded_regular_file

ORIGINAL_FILES = {'runtime_sha256': 'runtime.original.json',
    'protocol_review_sha256': 'protocol.original.json',
    'native_controller_review_sha256': 'controller.original.json'}


class AbsoluteWristReferenceReader:
    def __init__(self, request, *, workspace, root):
        if type(request) is not AbsoluteWristIntent:
            raise ValueError('Exact absolute intent required')
        self._request = request
        self._workspace = safe_root(Path(workspace))
        self._directory = contained_path(safe_root(root), request.to_dict()['attempt_id']+
            '-absolute-wrist-native-child', label='absolute worker originals')

    def original(self, reference):
        if reference not in ORIGINAL_FILES:
            raise ValueError('Unknown absolute worker reference')
        raw = read_bounded_regular_file(contained_path(safe_root(self._directory),
            ORIGINAL_FILES[reference], label='absolute original'), maximum_bytes=128*1024)
        value = decode_diagnostic_json(raw, maximum=128*1024)
        if type(value) is not dict or not value:
            raise ValueError('Structured original required')
        if hashlib.sha256(raw).hexdigest() != self._request.to_dict()['references'][reference]:
            raise ValueError('Absolute reference original changed')
        return raw

    def __call__(self):
        refs = {'source_sha256': source_fingerprint(self._workspace)}
        for name in ORIGINAL_FILES:
            refs[name] = hashlib.sha256(self.original(name)).hexdigest()
        if refs != self._request.to_dict()['references']:
            raise ValueError('Absolute source/reference mismatch')
        return tuple(sorted(refs.items()))


class FrozenAbsoluteWristReferences:
    """Freeze only after package/source verification, not as current USB proof."""
    def __init__(self, reader):
        if type(reader) is not AbsoluteWristReferenceReader:
            raise ValueError('Exact original reader required')
        refs = reader()
        originals = tuple((name, reader.original(name)) for name in sorted(ORIGINAL_FILES))
        if reader() != refs:
            raise ValueError('Absolute references changed during freeze')
        self._references, self._originals = refs, originals

    def __call__(self):
        return self._references

    def original(self, name):
        return dict(self._originals)[name]
