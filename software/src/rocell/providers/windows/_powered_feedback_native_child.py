"""Fixed isolated one-query child. Import checks never claim or access devices."""

import hashlib
import json
from pathlib import Path
import sys
import time
from threading import Event


def observe(payload):
    from rocell.providers.windows.powered_feedback_native_registration import (
        validate_payload,
    )
    from rocell.application.powered_feedback_child_claim import claim_for_child
    from rocell.application.arm_bench_qualification_contract import _canonical
    from rocell.application.passive_arm_identity import PassiveControllerSelection
    from rocell.providers.windows.powered_feedback_binding import PoweredFeedbackBinding
    from rocell.providers.windows.powered_feedback_serial_api import (
        WindowsPoweredFeedbackSerialApi,
    )
    from rocell.providers.windows.powered_feedback_observation import observe_physical
    from rocell.providers.windows.controller_metadata import (
        WindowsControllerMetadataAcquirer,
    )

    intent = validate_payload(payload)
    body = intent.to_dict()
    root = Path(payload["root"])
    claim = claim_for_child(
        root=root,
        intent=intent,
        expected_consumption_sha256=payload["consumption_sha256"],
        runtime_original=_canonical(payload["registration"]),
        current_source_sha256=body["references"]["source_sha256"],
        now_monotonic_ns=time.monotonic_ns(),
    )
    originals = dict(claim.prepared.originals)
    binding = PoweredFeedbackBinding(
        PassiveControllerSelection(originals["native_identity_original_sha256"]), intent
    )
    cancel = Event()
    now = time.monotonic_ns()
    deadline = min(
        now + 9_000_000_000, body["parent_deadline_monotonic_ns"] - 7_000_000_000
    )
    if deadline <= now:
        raise ValueError("Powered metadata/cleanup lifetime unavailable")
    snapshot = WindowsControllerMetadataAcquirer(
        deadline_ns=deadline, cancellation=cancel
    )()
    fresh = json.loads(snapshot.payload())
    api = WindowsPoweredFeedbackSerialApi.from_live_claim(
        root=root,
        claim=claim,
        binding=binding,
        fresh_snapshot=fresh,
        collection_not_before_ns=now,
        metadata_operation_id=body["attempt_id"],
        current_source_sha256=body["references"]["source_sha256"],
    )
    from rocell.application.powered_arm_feedback_contract import TELEMETRY_PURPOSE
    if body["purpose"] == TELEMETRY_PURPOSE:
        from rocell.providers.windows.powered_telemetry_observation import (
            observe_physical as observe_telemetry,
        )
        observation = observe_telemetry(binding, api, cancel)
    else:
        observation = observe_physical(binding, api, cancel)
    return {
        "schema": "rocell.powered_feedback_native_child_result.v1",
        "claim_sha256": claim.claim_sha256,
        "observation": observation,
        "fresh_snapshot": fresh,
        "physical_authority": False,
        "connected": False,
    }


def main():
    if not sys.flags.isolated or not sys.flags.no_site or len(sys.argv) != 4:
        return 2
    path = Path(sys.argv[1])
    if not path.is_absolute() or path.name != "powered-feedback-native.zip":
        return 3
    if sys.argv[3] not in {"check-imports", "observe"}:
        return 5
    with path.open("rb") as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != sys.argv[2]:
        return 4
    if sys.argv[3] == "check-imports":
        import ctypes
        import subprocess

        def forbidden(*args, **kwargs):
            raise RuntimeError("POWERED_IMPORT_CHECK_HOST_ACCESS_FORBIDDEN")

        ctypes.WinDLL = forbidden
        subprocess.Popen = forbidden
    sys.path.insert(0, str(path))
    from rocell.application.arm_bench_qualification_contract import _canonical
    from rocell.providers.windows.powered_feedback_native_wire import (
        decode_request,
        encode_result,
    )
    from rocell.providers.windows.controller_metadata import (
        WindowsControllerMetadataAcquirer,
    )
    from rocell.providers.windows.powered_feedback_serial_api import (
        WindowsPoweredFeedbackSerialApi,
    )

    if sys.argv[3] == "check-imports":
        # Exercise telemetry's lazy branch while native/process calls remain
        # forbidden, so archive dependency omissions fail before any live run.
        from rocell.providers.windows.powered_telemetry_observation import (
            observe_physical as telemetry_import_check,
        )
        from rocell.providers.windows.powered_telemetry_wire import (
            validate_observation as telemetry_wire_import_check,
        )
        result = _canonical(
            {
                "status": "IMPORTS_OK_NOT_HARDWARE_TESTED",
                "native": WindowsPoweredFeedbackSerialApi("COM4096").status(),
                "physical_authority": False,
                "connected": False,
            }
        )
    else:
        wire = decode_request(sys.stdin.buffer.read(65537))
        result = encode_result(observe(wire["payload"]), wire)
    sys.stdout.buffer.write(result)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
