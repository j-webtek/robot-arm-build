"""Fixed isolated passive child entry with live-claim-only native admission.

The import check is device-incapable. The registered observation consumes its
live claim after fresh metadata; ordinary API construction remains held.
"""

import base64
import hashlib
import json
from pathlib import Path
import sys
from threading import Event
import time


def observe(value):
    from rocell.application.arm_bench_qualification_contract import (
        PassiveBenchRequest,
        _canonical,
    )
    from rocell.application.passive_arm_child_claim import claim_for_child
    from rocell.application.passive_arm_attempt_store import inspect_attempt
    from rocell.application.passive_arm_identity import PassiveControllerSelection
    from rocell.application.physical_onboarding_durability import (
        contained_path,
        read_bounded_regular_file,
    )
    from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
    from rocell.providers.windows.passive_serial_binding import PassiveSerialBinding
    from rocell.providers.windows.passive_serial_api import WindowsPassiveSerialApi
    from rocell.providers.windows.passive_serial_observation import observe_physical
    from rocell.providers.windows.controller_metadata import (
        WindowsControllerMetadataAcquirer,
    )

    if (
        type(value) is not dict
        or set(value)
        != {
            "schema",
            "root",
            "request",
            "setup_operation_id",
            "consumption_sha256",
            "registration",
        }
        or value["schema"] != "rocell.passive_native_child_handoff.v1"
    ):
        raise ValueError("Exact passive child handoff required")
    root = Path(value["root"])
    if not root.is_absolute():
        raise ValueError("Absolute assigned journal directory required")
    request = PassiveBenchRequest(_canonical(value["request"]))
    body = request.to_dict()
    # The exclusive claim precedes enumeration as well as serial access.
    claim = claim_for_child(
        root=root,
        request=request,
        expected_consumption_sha256=value["consumption_sha256"],
        registration=value["registration"],
        now_monotonic_ns=time.monotonic_ns(),
    )
    retained = inspect_attempt(root, body["attempt_id"])["records"]["prepared"]["body"]
    originals = retained["originals_base64"]
    native_raw = base64.b64decode(
        originals["native_metadata_review_sha256"], validate=True
    )
    attestation = decode_diagnostic_json(
        base64.b64decode(originals["operator_attestation_sha256"], validate=True),
        maximum=32768,
    )
    import re

    setup_id = value["setup_operation_id"]
    if (
        type(setup_id) is not str
        or re.fullmatch(r"operation-[a-f0-9]{32}", setup_id) is None
    ):
        raise ValueError("Exact setup operation required")
    path = contained_path(
        root, setup_id + "-passive-setup-original.json", label="child setup original"
    )
    setup_raw = read_bounded_regular_file(path, maximum_bytes=1024 * 1024)
    if hashlib.sha256(setup_raw).hexdigest() != attestation["setup_sha256"]:
        raise ValueError("Child setup original changed")
    setup = decode_diagnostic_json(setup_raw, maximum=1024 * 1024)
    if (
        setup["session_id"] != body["launch_id"]
        or setup["source_sha256"] != body["references"]["source_sha256"]
    ):
        raise ValueError("Child setup context mismatch")
    binding = PassiveSerialBinding(PassiveControllerSelection(native_raw))
    cancel = Event()
    now = time.monotonic_ns()
    # Reserve the observation/cleanup lifetime when bounding metadata acquisition.
    metadata_deadline = min(
        now + 9_000_000_000, body["parent_deadline_monotonic_ns"] - 7_000_000_000
    )
    if metadata_deadline <= now:
        raise ValueError("Insufficient metadata and cleanup lifetime")
    fresh = WindowsControllerMetadataAcquirer(
        deadline_ns=metadata_deadline, cancellation=cancel
    )()
    fresh_snapshot = json.loads(fresh.payload())
    api = WindowsPassiveSerialApi.from_live_claim(
        root=root,
        claim=claim,
        request=request,
        binding=binding,
        fresh_snapshot=fresh_snapshot,
        generic_review=setup["generic_review"],
        collection_not_before_ns=now,
        metadata_operation_id=body["attempt_id"],
    )
    result = observe_physical(
        request,
        binding,
        api,
        cancel,
        fresh_snapshot=fresh_snapshot,
        generic_review=setup["generic_review"],
        collection_not_before_ns=now,
        metadata_operation_id=body["attempt_id"],
    )
    return {
        "schema": "rocell.passive_native_child_result.v1",
        "claim_sha256": claim.claim_sha256,
        "observation": result,
        "physical_authority": False,
        "connected": False,
    }


def main():
    if len(sys.argv) != 4:
        return 2
    path = Path(sys.argv[1])
    if not path.is_absolute() or path.name != "passive-native.zip":
        return 3
    with path.open("rb") as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != sys.argv[2]:
        return 4
    sys.path.insert(0, str(path))
    from rocell.application.arm_bench_qualification_contract import _canonical
    from rocell.application.passive_arm_child_claim import claim_for_child
    from rocell.providers.windows.passive_serial_observation import observe_physical
    from rocell.providers.windows.controller_metadata import (
        WindowsControllerMetadataAcquirer,
    )
    from rocell.providers.windows.passive_serial_api import WindowsPassiveSerialApi

    if sys.argv[3] == "check-imports":
        result = {
            "status": "IMPORTS_OK_NOT_HARDWARE_TESTED",
            "physical_authority": False,
            "connected": False,
            "native": WindowsPassiveSerialApi("COM4096").status(),
        }
    elif sys.argv[3] == "observe":
        from rocell.providers.windows.passive_native_wire import (
            decode_request,
            encode_result,
        )

        wire = decode_request(sys.stdin.buffer.read(65537))
        result = observe(wire["payload"])
        sys.stdout.buffer.write(encode_result(result, wire))
        sys.stdout.buffer.flush()
        return 0
    else:
        return 5
    sys.stdout.buffer.write(_canonical(result))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
