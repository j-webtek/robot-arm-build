"""Reconstruct endpoint reference digests from current source and fixed originals.

Integrity is not approval: semantic engineering/operator review remains required.
No caller-supplied digest callback or arbitrary path appears in this reader.
"""

import hashlib
from pathlib import Path
from .endpoint_trial_contract import EndpointTrialRequest, REFERENCE_NAMES
from .wizard_diagnostic_coordinator import source_fingerprint, decode_diagnostic_json
from .physical_onboarding_durability import safe_root, contained_path, read_bounded_regular_file
from rocell.rc03.importer import import_build_snapshot

ORIGINAL_REFERENCES = REFERENCE_NAMES-{'source_sha256','build_snapshot_sha256'}
MAX_ORIGINAL_BYTES = 128*1024


class EndpointReferenceReader:
    """Read all eight retained originals afresh on every explicit invocation."""

    _original_references = ORIGINAL_REFERENCES

    @staticmethod
    def _accept_request(request):
        return type(request) is EndpointTrialRequest

    def __init__(self,request,*,workspace,reference_root):
        if not self._accept_request(request):
            raise ValueError('Exact endpoint request required')
        self._request = request
        self._workspace = safe_root(Path(workspace))
        self._root = safe_root(Path(reference_root))

    def __call__(self):
        body = self._request.to_dict()
        observed = {'source_sha256':source_fingerprint(self._workspace),
                    'build_snapshot_sha256':import_build_snapshot(self._workspace).snapshot_hash}
        for name in sorted(self._original_references):
            filename = body['attempt_id']+'-'+name+'.original.json'
            path = contained_path(self._root,filename,label='endpoint reference original')
            raw = read_bounded_regular_file(path,maximum_bytes=MAX_ORIGINAL_BYTES)
            # These are original structured receipts/configuration records, not
            # files containing only a claimed hash or a path to another file.
            value = decode_diagnostic_json(raw,maximum=MAX_ORIGINAL_BYTES)
            if type(value) is not dict or not value:
                raise ValueError('Structured endpoint reference original required')
            observed[name] = hashlib.sha256(raw).hexdigest()
        if observed!=body['references']:
            raise ValueError('Current endpoint source/build/reference bytes changed')
        return tuple(sorted(observed.items()))
