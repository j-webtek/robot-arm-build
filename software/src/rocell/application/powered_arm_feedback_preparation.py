"""Associate exact powered-feedback originals without granting dispatch.

This is the file/evidence join preceding runtime and firmware-review admission.
It cannot authenticate an arbitrary supplied review or executable by its hash.
All byte originals are retained in an immutable tuple for later journal/child
validation; the startup timestamp is never renewed during preparation.
"""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from .arm_bench_qualification_contract import _canonical
from .powered_arm_feedback_contract import PoweredFeedbackIntent, REFERENCE_NAMES
from .physical_onboarding_durability import contained_path, read_bounded_regular_file
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from . import wizard_native_arm_metadata as metadata


@dataclass(frozen=True, slots=True)
class PreparedPoweredFeedback:
    intent: PoweredFeedbackIntent
    originals: tuple[tuple[str, bytes], ...]

    def summary(self):
        return {
            "status": "POWERED_ORIGINALS_ASSOCIATED_NOT_AUTHENTICATED",
            "request_sha256": self.intent.request_sha256,
            "original_sha256": {
                name: hashlib.sha256(raw).hexdigest() for name, raw in self.originals
            },
            "firmware_review_authenticated": False,
            "runtime_qualified": False,
            "physical_dispatch_available": False,
            "physical_authority": False,
        }


def prepare_powered_feedback(
    *,
    intent,
    root,
    startup_operation_id,
    current_source_sha256,
    native_original,
    generic_review,
    runtime_original,
    serial_profile_original,
    protocol_review_original,
    firmware_review_original,
    now_monotonic_ns
):
    """Reopen the fixed startup file and bind all originals to the exact intent."""
    if type(intent) is not PoweredFeedbackIntent:
        raise ValueError("Exact powered-feedback intent required")
    intent.require_time_available(now_monotonic_ns)
    body = intent.to_dict()
    if current_source_sha256 != body["references"]["source_sha256"]:
        raise ValueError("Current source differs from powered-feedback intent")
    if (
        type(startup_operation_id) is not str
        or re.fullmatch(r"operation-[a-f0-9]{32}", startup_operation_id) is None
    ):
        raise ValueError("Exact powered startup operation ID required")
    startup_raw = read_bounded_regular_file(
        contained_path(
            Path(root),
            startup_operation_id + "-powered-startup-original.json",
            label="powered startup",
        ),
        maximum_bytes=32768,
    )
    originals = {
        "powered_startup_original_sha256": startup_raw,
        "native_identity_original_sha256": native_original,
        "runtime_sha256": runtime_original,
        "serial_profile_sha256": serial_profile_original,
        "protocol_review_sha256": protocol_review_original,
        "firmware_compatibility_review_sha256": firmware_review_original,
    }
    assert set(originals) == REFERENCE_NAMES - {"source_sha256"}
    for name, raw in originals.items():
        maximum = (
            metadata.MAX_REPORT_BYTES
            if name == "native_identity_original_sha256"
            else 65536
        )
        if type(raw) is not bytes or not 0 < len(raw) <= maximum:
            raise ValueError("Bounded nonempty byte originals required: " + name)
        if hashlib.sha256(raw).hexdigest() != body["references"][name]:
            raise ValueError("Powered original hash mismatch: " + name)
    startup = decode_diagnostic_json(startup_raw, maximum=32768)
    if type(startup) is not dict or _canonical(startup) != startup_raw:
        raise ValueError("Canonical powered startup original required")
    fixed = {
        "schema": "rocell.powered_arm_startup_original.v1",
        "session_id": body["session_id"],
        "operation_id": startup_operation_id,
        "source_sha256": current_source_sha256,
        "recorded_monotonic_ns": body["startup_recorded_monotonic_ns"],
        "evidence_kind": "OPERATOR_REPORT_NOT_SENSOR_MEASUREMENT",
        "supply_voltage_measurement": None,
        "installed_firmware_identity": "UNKNOWN",
        "controller_identity_verified": False,
        "canonical_power_stage_accepted": False,
        "usb_only_policy_applicable": False,
        "feedback_authorized": False,
        "motion_authorized": False,
        "physical_authority": False,
    }
    if set(startup) != set(fixed) | {"operator_id", "reported"} or any(
        _canonical(startup[key]) != _canonical(value) for key, value in fixed.items()
    ):
        raise ValueError("Powered startup context or evidence basis mismatch")
    if (
        type(startup["operator_id"]) is not str
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", startup["operator_id"])
        is None
    ):
        raise ValueError("Recorded operator ID invalid")
    reported = startup["reported"]
    if (
        type(reported) is not dict
        or set(reported)
        != {
            "external_adapter_on",
            "usb_connected",
            "secured_and_clear",
            "stationary",
            "startup_motion",
        }
        or any(
            reported[key] is not True
            for key in (
                "external_adapter_on",
                "usb_connected",
                "secured_and_clear",
                "stationary",
            )
        )
        or type(reported["startup_motion"]) is not str
        or reported["startup_motion"] not in {"observed", "not_observed", "unknown"}
    ):
        raise ValueError("Explicit powered startup reports required")
    native = decode_diagnostic_json(native_original, maximum=metadata.MAX_REPORT_BYTES)
    rebuilt = metadata.correlate_native_arm_metadata(
        native["snapshot"],
        generic_review,
        mode=body["mode"],
        session_id=body["session_id"],
        source_sha256=current_source_sha256,
        operation_id=native["binding"]["operation_id"],
    )
    if (
        _canonical(rebuilt) != native_original
        or rebuilt["status"] != "METADATA_CORRELATED"
    ):
        raise ValueError("Powered feedback identity originals do not correlate")
    from .powered_feedback_firmware_review import validate_review

    validate_review(
        firmware_review_original,
        session_id=body["session_id"],
        source_sha256=current_source_sha256,
        protocol_review_original=protocol_review_original,
    )

    # The native report binds this full review by hash but contains only its
    # compact acknowledgement. Retain full bytes for child-side reconstruction,
    # rather than later borrowing a mutable/current UI selection.
    originals["generic_review_original"] = _canonical(generic_review)
    return PreparedPoweredFeedback(intent, tuple(sorted(originals.items())))
