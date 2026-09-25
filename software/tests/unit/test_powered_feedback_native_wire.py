"""Pure wire associations with synthetic originals, never native execution."""

import hashlib
import time

import pytest

from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.powered_arm_feedback_contract import PoweredFeedbackIntent
from rocell.providers.windows import powered_feedback_native_wire as wire
from rocell.providers.windows import (
    powered_feedback_native_registration as registration,
)
from test_powered_arm_feedback_contract import document


def envelope(*, telemetry=False):
    body = document()
    if telemetry:
        from rocell.application.powered_arm_feedback_contract import TELEMETRY_PURPOSE, TELEMETRY_LIMITS
        body.update(purpose=TELEMETRY_PURPOSE, limits=TELEMETRY_LIMITS)
    body["mode"] = "physical"
    runtime = {"fixture": "synthetic runtime; not registered"}
    body["references"]["runtime_sha256"] = hashlib.sha256(
        _canonical(runtime)
    ).hexdigest()
    intent = PoweredFeedbackIntent(_canonical(body))
    payload = dict(
        schema=registration.PAYLOAD_SCHEMA,
        root="C:/fixture-powered-root",
        intent=intent.to_dict(),
        consumption_sha256="e" * 64,
        registration=runtime,
    )
    result = dict(
        schema=registration.REQUEST_SCHEMA,
        worker_id=registration.WORKER_ID,
        attempt_id=body["attempt_id"],
        session_id=body["session_id"],
        source_sha256=body["references"]["source_sha256"],
        operation_sha256=intent.request_sha256,
        selected_identity_sha256=body["references"]["native_identity_original_sha256"],
        expires_at_monotonic_ns=body["parent_deadline_monotonic_ns"],
        parent_deadline_monotonic_ns=body["parent_deadline_monotonic_ns"],
        payload=payload,
        registration_sha256=body["references"]["runtime_sha256"],
    )
    result["request_sha256"] = hashlib.sha256(_canonical(result)).hexdigest()
    return result


def test_exact_envelope_roundtrip_is_association_not_permission():
    value = envelope()
    assert wire.decode_request(_canonical(value)) == value


@pytest.mark.parametrize(
    "field,value",
    [
        ("operation_sha256", "a" * 64),
        ("attempt_id", "operation-" + "f" * 32),
        ("registration_sha256", "c" * 64),
        ("selected_identity_sha256", "d" * 64),
        ("parent_deadline_monotonic_ns", True),
    ],
)
def test_rehashed_foreign_context_still_rejected(field, value):
    body = envelope()
    body[field] = value
    del body["request_sha256"]
    body["request_sha256"] = hashlib.sha256(_canonical(body)).hexdigest()
    with pytest.raises(ValueError):
        wire.decode_request(_canonical(body))
