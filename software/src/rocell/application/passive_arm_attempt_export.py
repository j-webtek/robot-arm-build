"""Read-only, exact-byte diagnostic collection; never resume an attempt.

Malformed or partially published records are evidence too. Keep their bytes
without parsing or treating them as authorization. File reads are bounded and
reject links; missing/unreadable stages are explicit, never inferred success.
"""

import base64
import hashlib

from .passive_arm_attempt_store import _path, MAX_BYTES
from .physical_onboarding_durability import read_bounded_regular_file


def collect_attempt(root, attempt_id):
    stages = {}
    for stage in ("prepared", "consumed", "claimed", "outcome"):
        path = _path(root, attempt_id, stage)
        try:
            path.lstat()
        except FileNotFoundError:
            stages[stage] = {"status": "MISSING"}
            continue
        try:
            raw = read_bounded_regular_file(path, maximum_bytes=MAX_BYTES)
        except Exception as error:
            stages[stage] = {"status": "READ_FAILED", "error": type(error).__name__}
            continue
        stages[stage] = {
            "status": "BYTES_COLLECTED_NOT_VALIDATED",
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "base64_chunks": [
                base64.b64encode(raw[start : start + 32768]).decode("ascii")
                for start in range(0, len(raw), 32768)
            ],
        }
    return {
        "schema": "rocell.passive_arm_attempt_files_export.v1",
        "attempt_id": attempt_id,
        "stages": stages,
        "physical_authority": False,
        "replay_allowed": False,
        "authenticated": False,
        "atomic_snapshot": False,
        "meaning": "Diagnostic file reads only; missing or malformed records do not permit replay or prove device cleanup.",
        "privacy": "Exact original bytes, not text-redacted. Review before sharing.",
    }
