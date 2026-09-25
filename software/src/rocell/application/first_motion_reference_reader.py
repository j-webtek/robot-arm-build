"""Reconstruct commissioning references from current workspace and originals.

Uses fixed attempt-relative filenames, not arbitrary browser paths or claimed
hash callbacks. Integrity is not semantic approval: the measurement selection
reader and authenticated engineering/operator reviews are still required.
"""
from .first_motion_contract import FirstMotionRequest, REFERENCES
from .endpoint_reference_reader import EndpointReferenceReader

ORIGINAL_REFERENCES = REFERENCES - {'source_sha256','build_snapshot_sha256'}


class FirstMotionReferenceReader(EndpointReferenceReader):
    _original_references = ORIGINAL_REFERENCES

    @staticmethod
    def _accept_request(request):
        return type(request) is FirstMotionRequest
