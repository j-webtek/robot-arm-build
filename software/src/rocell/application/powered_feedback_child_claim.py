"""Original-byte verification and exclusive powered worker claim, without I/O.

This is a lifecycle prerequisite, not firmware/runtime approval or native entry.
Only independently reviewed source-pinned worker composition may eventually
consume these live objects. Disk inspection cannot recreate a live claim.
"""

import base64
from dataclasses import dataclass
import hashlib
from threading import Lock

from .arm_bench_qualification_contract import _canonical
from .physical_onboarding_durability import read_bounded_regular_file
from .powered_arm_feedback_contract import PoweredFeedbackIntent, REFERENCE_NAMES
from .powered_arm_feedback_preparation import (
    PreparedPoweredFeedback,
    prepare_powered_feedback,
)
from .powered_feedback_attempt_store import MAX_RECORD_BYTES, attempt_path, _publish
from .wizard_diagnostic_coordinator import decode_diagnostic_json


def _read(root, attempt_id, stage):
    raw = read_bounded_regular_file(
        attempt_path(root, attempt_id, stage), maximum_bytes=MAX_RECORD_BYTES
    )
    record = decode_diagnostic_json(raw, maximum=MAX_RECORD_BYTES)
    if (
        type(record) is not dict
        or set(record)
        != {
            "schema",
            "attempt_id",
            "stage",
            "body",
            "replay_allowed",
            "physical_authority",
        }
        or record["schema"] != "rocell.powered_feedback_attempt_journal.v1"
        or record["attempt_id"] != attempt_id
        or record["stage"] != stage
        or record["replay_allowed"] is not False
        or record["physical_authority"] is not False
        or type(record["body"]) is not dict
        or _canonical(record) != raw
    ):
        raise ValueError("Exact canonical powered journal record required")
    return record["body"], hashlib.sha256(raw).hexdigest()


def verify_consumed_attempt(
    *,
    root,
    intent,
    expected_consumption_sha256,
    runtime_original,
    current_source_sha256,
    now_monotonic_ns
):
    """Rebuild consumed originals; hash equality is association, not approval."""
    if (
        type(intent) is not PoweredFeedbackIntent
        or intent.to_dict()["mode"] != "physical"
    ):
        raise ValueError("Exact physical powered intent required")
    intent.require_time_available(now_monotonic_ns)
    body = intent.to_dict()
    attempt_id = body["attempt_id"]
    for stage in ("claimed", "outcome"):
        try:
            attempt_path(root, attempt_id, stage).lstat()
        except FileNotFoundError:
            pass
        else:
            raise ValueError("Powered attempt already claimed or completed")
    prepared, prepared_sha = _read(root, attempt_id, "prepared")
    consumed, consumed_sha = _read(root, attempt_id, "consumed")
    if consumed_sha != expected_consumption_sha256:
        raise ValueError("Powered consumption digest mismatch")
    if (
        set(consumed)
        != {
            "prepared_sha256",
            "request_sha256",
            "consumed_monotonic_ns",
            "dispatch_may_have_started",
        }
        or consumed["prepared_sha256"] != prepared_sha
        or consumed["request_sha256"] != intent.request_sha256
        or consumed["dispatch_may_have_started"] is not True
        or type(consumed["consumed_monotonic_ns"]) is not int
        or not body["startup_recorded_monotonic_ns"]
        <= consumed["consumed_monotonic_ns"]
        <= now_monotonic_ns
    ):
        raise ValueError("Powered consumption chain mismatch")
    if (
        set(prepared)
        != {
            "intent",
            "startup_operation_id",
            "originals_base64",
            "references_authenticated_by_journal",
        }
        or prepared["references_authenticated_by_journal"] is not False
        or _canonical(prepared["intent"]) != intent.payload
    ):
        raise ValueError("Prepared powered intent mismatch")
    encoded = prepared["originals_base64"]
    if (
        type(encoded) is not dict
        or set(encoded)
        != (REFERENCE_NAMES - {"source_sha256"}) | {"generic_review_original"}
        or any(type(value) is not str for value in encoded.values())
    ):
        raise ValueError("Exact powered original collection required")
    originals = {
        name: base64.b64decode(value, validate=True) for name, value in encoded.items()
    }
    if (
        type(runtime_original) is not bytes
        or originals["runtime_sha256"] != runtime_original
    ):
        raise ValueError("Powered child runtime original mismatch")
    rebuilt = prepare_powered_feedback(
        intent=intent,
        root=root,
        startup_operation_id=prepared["startup_operation_id"],
        current_source_sha256=current_source_sha256,
        native_original=originals["native_identity_original_sha256"],
        generic_review=decode_diagnostic_json(
            originals["generic_review_original"], maximum=262144
        ),
        runtime_original=runtime_original,
        serial_profile_original=originals["serial_profile_sha256"],
        protocol_review_original=originals["protocol_review_sha256"],
        firmware_review_original=originals["firmware_compatibility_review_sha256"],
        now_monotonic_ns=now_monotonic_ns,
    )
    if dict(rebuilt.originals) != originals:
        raise ValueError("Child powered originals differ from retained bytes")
    return rebuilt


@dataclass(frozen=True, slots=True)
class ClaimedPoweredFeedback:
    prepared: PreparedPoweredFeedback
    claim_sha256: str


_LIVE_CLAIMS = {}
_LIVE_LOCK = Lock()


def claim_for_child(**kwargs):
    """The final-name reservation is the one-winner boundary between workers."""
    prepared = verify_consumed_attempt(**kwargs)
    body = prepared.intent.to_dict()
    digest = _publish(
        kwargs["root"],
        body["attempt_id"],
        "claimed",
        {
            "consumption_sha256": kwargs["expected_consumption_sha256"],
            "request_sha256": prepared.intent.request_sha256,
            "runtime_sha256": body["references"]["runtime_sha256"],
            "claimed_monotonic_ns": kwargs["now_monotonic_ns"],
            "native_access_granted": False,
        },
    )
    claim = ClaimedPoweredFeedback(prepared, digest)
    with _LIVE_LOCK:
        _LIVE_CLAIMS[digest] = claim
    return claim


def consume_live_claim(claim, intent):
    """Burn before later admission; copied receipts never substitute for the object."""
    with _LIVE_LOCK:
        if (
            type(claim) is not ClaimedPoweredFeedback
            or _LIVE_CLAIMS.get(claim.claim_sha256) is not claim
        ):
            raise ValueError("Live unconsumed powered child claim required")
        del _LIVE_CLAIMS[claim.claim_sha256]
    if (
        type(intent) is not PoweredFeedbackIntent
        or intent.payload != claim.prepared.intent.payload
    ):
        raise ValueError("Powered native intent differs from live claim")
