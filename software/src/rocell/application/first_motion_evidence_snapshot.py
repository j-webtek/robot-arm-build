"""Bounded frozen evidence bytes, not proof of parent pinning or motion approval.

The parent must pin this document for execution and bind its digest to the fixed
worker registration. Decoding alone does not permit cached live-state checks.
"""

import base64
import hashlib
from pathlib import Path
from .arm_bench_qualification_contract import _canonical
from .first_motion_contract import FirstMotionRequest
from .first_motion_reference_reader import FirstMotionReferenceReader, ORIGINAL_REFERENCES
from .endpoint_reference_reader import MAX_ORIGINAL_BYTES
from .physical_onboarding_durability import contained_path, safe_root, read_bounded_regular_file, publish_bytes, PublicationMode
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.rc03.importer import import_build_snapshot

SCHEMA = 'rocell.first_motion_evidence_snapshot.v1'
FILENAME = 'first_motion-evidence.json'
MAX_BYTES = 2*1024*1024


class FrozenFirstMotionReferences:
    """Validated immutable execution bytes; never a current-workspace assertion.

    Parent pinning is a separate mandatory launch condition. Physical metadata,
    review expiry and baseline freshness must not be supplied by this object.
    """

    def __init__(self,raw,request):
        originals = decode_snapshot(raw,request)
        self._originals = tuple(sorted(originals.items()))
        self._references = tuple(sorted(request.to_dict()['references'].items()))
        self.snapshot_sha256 = hashlib.sha256(raw).hexdigest()

    def __call__(self):
        return self._references

    def original(self,name):
        return dict(self._originals)[name]


def decode_snapshot(raw,request):
    if type(request) is not FirstMotionRequest or type(raw) is not bytes or not 0<len(raw)<=MAX_BYTES:
        raise ValueError('Bounded snapshot and exact first_motion request required')
    value = decode_diagnostic_json(raw,maximum=MAX_BYTES)
    expected = {'schema','request','request_sha256','build_snapshot','originals','physical_authority'}
    if (type(value) is not dict or set(value)!=expected or _canonical(value)!=raw
            or value['schema']!=SCHEMA or value['physical_authority'] is not False
            or value['request_sha256']!=request.request_sha256
            or _canonical(value['request'])!=request.canonical_bytes):
        raise ValueError('Frozen first_motion snapshot context mismatch')
    refs = request.to_dict()['references']
    build = value['build_snapshot']
    if type(build) is not dict or hashlib.sha256(_canonical(build)).hexdigest()!=refs['build_snapshot_sha256']:
        raise ValueError('Frozen build snapshot changed')
    encoded = value['originals']
    if type(encoded) is not dict or set(encoded)!=ORIGINAL_REFERENCES:
        raise ValueError('All frozen reference originals required')
    originals = {}
    for name,text in encoded.items():
        if type(text) is not str or len(text)>((MAX_ORIGINAL_BYTES+2)//3)*4:
            raise ValueError('Frozen original exceeds budget')
        original = base64.b64decode(text,validate=True)
        if not 0<len(original)<=MAX_ORIGINAL_BYTES or hashlib.sha256(original).hexdigest()!=refs[name]:
            raise ValueError('Frozen reference original changed')
        document = decode_diagnostic_json(original,maximum=MAX_ORIGINAL_BYTES)
        if type(document) is not dict or not document:
            raise ValueError('Structured frozen reference required')
        originals[name]=original
    return originals


def prepare_snapshot(workspace,request,*,reference_root,directory):
    """Verify current inputs and publish immutable snapshot before parent pinning."""
    reader = FirstMotionReferenceReader(request,workspace=workspace,reference_root=reference_root)
    reader()
    root = safe_root(Path(reference_root))
    originals = {}
    for name in sorted(ORIGINAL_REFERENCES):
        filename = request.to_dict()['attempt_id']+'-'+name+'.original.json'
        raw = read_bounded_regular_file(contained_path(root,filename,label='snapshot original'),
                                       maximum_bytes=MAX_ORIGINAL_BYTES)
        originals[name]=base64.b64encode(raw).decode('ascii')
    raw = _canonical({'schema':SCHEMA,'request':request.to_dict(),'request_sha256':request.request_sha256,
        'build_snapshot':import_build_snapshot(workspace).to_dict(),'originals':originals,'physical_authority':False})
    decode_snapshot(raw,request)
    reader()  # Detect observed edits during assembly; this is not an atomic lock.
    path = publish_bytes(Path(directory),FILENAME,raw,mode=PublicationMode.IMMUTABLE,maximum_bytes=MAX_BYTES)
    if read_bounded_regular_file(path,maximum_bytes=MAX_BYTES)!=raw:
        raise ValueError('Frozen snapshot publication changed')
    return path
