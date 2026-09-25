"""Immutable commissioning diagnostic originals, even for malformed child output.

This is retention only, not result validation or a supervisor receipt. It cannot
launch hardware, replay a command, qualify motion or authenticate process exit.
The production parent must separately bind these originals to its owned worker.
"""
import base64
import hashlib
from pathlib import Path

from .first_motion_contract import FirstMotionRequest, canonical
from .physical_onboarding_durability import (
    safe_root, publish_bytes, PublicationMode, read_bounded_regular_file,
)

MAX_STDOUT_BYTES = 256*1024
MAX_STDERR_BYTES = 8192
MAX_STORED_BYTES = 360*1024


def retain_first_motion_result(root, request, *, stdout, stderr):
    """Retain bounded bytes without parsing, trusting or repairing child claims.

    Parent-owned root only. An interrupted publication may leave partial evidence;
    preserve it and do not republish or relaunch using the same attempt ID.
    Deadlines are intentionally not revalidated here: failure evidence remains
    retainable after an attempt expires or its source changes.
    """
    if type(request) is not FirstMotionRequest:
        raise ValueError('Exact commissioning request required')
    for raw, limit in ((stdout,MAX_STDOUT_BYTES),(stderr,MAX_STDERR_BYTES)):
        if type(raw) is not bytes or len(raw)>limit:
            raise ValueError('Commissioning diagnostic stream exceeds retention budget')
    root = safe_root(Path(root))
    prefix = request.to_dict()['attempt_id']+'-first-motion-result-'
    originals = {}
    for name, raw in (('request',request.canonical_bytes),('stdout',stdout),('stderr',stderr)):
        stored = canonical({'schema':'rocell.first_motion_diagnostic_original.v1',
            'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
            'base64':base64.b64encode(raw).decode('ascii')})
        filename = prefix+name+'.json'
        path = publish_bytes(root,filename,stored,mode=PublicationMode.IMMUTABLE,
                             maximum_bytes=MAX_STORED_BYTES)
        if read_bounded_regular_file(path,maximum_bytes=MAX_STORED_BYTES)!=stored:
            raise ValueError('Commissioning diagnostic original readback failed')
        originals[name] = dict(file=filename,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                               stored_sha256=hashlib.sha256(stored).hexdigest())
    report = dict(schema='rocell.first_motion_diagnostics_retained.v1',
        request_sha256=request.request_sha256,status='ORIGINALS_RETAINED_NOT_VALIDATED',
        originals=originals,child_result_validated=False,owned_process_receipt_verified=False,
        physical_movement_verified=False,physical_stop_verified=False,
        campaign_advance_allowed=False,replay_allowed=False)
    stored_report = canonical(report)
    path = publish_bytes(root,prefix+'report.json',stored_report,
                         mode=PublicationMode.IMMUTABLE,maximum_bytes=8192)
    if read_bounded_regular_file(path,maximum_bytes=8192)!=stored_report:
        raise ValueError('Commissioning diagnostic report readback failed')
    return path,report
