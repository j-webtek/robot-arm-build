"""Reconstruct observational references from fixed retained originals and source."""
import hashlib
from pathlib import Path

from rocell.safety.observational_review_authority import ObservationalIntent
from .wizard_diagnostic_coordinator import source_fingerprint, decode_diagnostic_json
from .physical_onboarding_durability import safe_root, contained_path, read_bounded_regular_file

ORIGINAL_FILES = {'runtime_sha256': 'runtime.original.json',
    'protocol_review_sha256': 'protocol.original.json',
    'native_controller_review_sha256': 'controller.original.json'}


class ObservationalReferenceReader:
    """No geometry measurements, caller paths or digests-as-originals accepted.

    This full source check belongs before capture. The short owned trial must
    use its pinned package/originals rather than repeat slow source traversal
    between baseline acquisition and command submission.
    """
    def __init__(self, request, *, workspace, root):
        if type(request) is not ObservationalIntent:
            raise ValueError('Exact observational intent required')
        self._request = request
        self._workspace = safe_root(Path(workspace))
        self._directory = contained_path(safe_root(root),
            request.to_dict()['attempt_id']+'-observational-native-child', label='observational originals')

    def original(self, reference):
        if reference not in ORIGINAL_FILES:
            raise ValueError('Unknown observational reference')
        path = contained_path(safe_root(self._directory), ORIGINAL_FILES[reference], label='observational original')
        raw = read_bounded_regular_file(path, maximum_bytes=128*1024)
        value = decode_diagnostic_json(raw, maximum=128*1024)
        if type(value) is not dict or not value:
            raise ValueError('Structured reference original required')
        if hashlib.sha256(raw).hexdigest() != self._request.to_dict()['references'][reference]:
            raise ValueError('Observational reference original changed')
        return raw

    def __call__(self):
        refs = {'source_sha256': source_fingerprint(self._workspace)}
        for name in ORIGINAL_FILES:
            refs[name] = hashlib.sha256(self.original(name)).hexdigest()
        if refs != self._request.to_dict()['references']:
            raise ValueError('Observational source or reference mismatch')
        return tuple(sorted(refs.items()))


class FrozenObservationalReferences:
    """Verified immutable execution inputs, not a fresh-workspace assertion.

    Freeze only after the parent/child package checks. Current USB metadata,
    signed review expiry and baseline recency remain independently checked.
    """
    def __init__(self, reader):
        if type(reader) is not ObservationalReferenceReader:
            raise ValueError('Original reconstruction reader required')
        references = reader()
        originals = tuple((name, reader.original(name)) for name in sorted(ORIGINAL_FILES))
        if reader() != references:
            raise ValueError('Observational references changed during freezing')
        self._references, self._originals = references, originals

    def __call__(self):
        return self._references

    def original(self, name):
        return dict(self._originals)[name]
