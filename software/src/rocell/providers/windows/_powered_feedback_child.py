"""Isolated powered-feedback worker bootstrap; no live mode is implemented.

No application bootstrap, site packages or current-directory imports are used.
The archive must match its supplied digest. Source-pinned parent registration
and supervision remain required before this can be a live worker composition.
"""

import hashlib
from pathlib import Path
import sys
from threading import Event


def main():
    if not sys.flags.isolated or not sys.flags.no_site or len(sys.argv) != 4:
        return 2
    path = Path(sys.argv[1])
    if not path.is_absolute() or path.name != "powered-feedback.zip":
        return 3
    # Reject live dispatch before importing any archive code or reading stdin.
    if sys.argv[3] not in {"check-imports", "rehearse", "supervised-rehearse"}:
        return 5
    with path.open("rb") as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != sys.argv[2]:
        return 4
    # These modes must never load a native DLL or spawn another process.
    # Exact incapable provider checks remain the actual rehearsal I/O boundary.
    import ctypes
    import subprocess

    def forbidden(*args, **kwargs):
        raise RuntimeError("POWERED_REHEARSAL_HOST_ACCESS_FORBIDDEN")

    ctypes.WinDLL = forbidden
    subprocess.Popen = forbidden
    # Install guards before archive imports as well as before scenario execution.
    sys.path.insert(0, str(path))
    from rocell.application.arm_bench_qualification_contract import _canonical
    from rocell.application.powered_feedback_child_claim import claim_for_child
    from rocell.application.wizard_powered_feedback_rehearsal import run_rehearsal
    from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json

    if sys.argv[3] == "check-imports":
        result = {
            "status": "IMPORTS_OK_NOT_HARDWARE_TESTED",
            "physical_authority": False,
            "connected": False,
            "native_dispatch_available": False,
        }
    elif sys.argv[3] == "supervised-rehearse":
        import base64
        import time
        from rocell.providers.windows.powered_feedback_process_codec import (
            decode_request,
            validate_result,
            RESULT_SCHEMA,
        )

        wire = decode_request(sys.stdin.buffer.read(65537))
        if time.monotonic_ns() >= wire["parent_deadline_monotonic_ns"]:
            raise ValueError("Powered rehearsal deadline expired")
        completion, original = run_rehearsal(
            **{key: value for key, value in wire["payload"].items() if key != "schema"},
            cancellation=Event(),
        )
        result = {
            "schema": RESULT_SCHEMA,
            "request_sha256": wire["request_sha256"],
            "attempt_id": wire["attempt_id"],
            "completion": completion,
            "original_base64": base64.b64encode(original).decode("ascii"),
            "physical_authority": False,
            "connected": False,
        }
        validate_result(
            result,
            payload=wire["payload"],
            request_sha256=wire["request_sha256"],
            attempt_id=wire["attempt_id"],
        )
    else:
        value = decode_diagnostic_json(sys.stdin.buffer.read(4097), maximum=4096)
        if type(value) is not dict or set(value) != {
            "session_id",
            "operation_id",
            "source_sha256",
            "scenario",
        }:
            raise ValueError("Exact powered rehearsal handoff required")
        completion, original = run_rehearsal(**value, cancellation=Event())
        import base64

        result = {
            "schema": "rocell.powered_feedback_child_rehearsal.v1",
            "completion": completion,
            "original_base64": base64.b64encode(original).decode("ascii"),
            "physical_authority": False,
            "connected": False,
        }
    sys.stdout.buffer.write(_canonical(result))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
