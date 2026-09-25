"""Wire association checks with a held physical-shaped observation fixture."""

from copy import deepcopy
import hashlib
import json

import pytest

from rocell.providers.windows import passive_native_wire as codec
from rocell.providers.windows.passive_native_registration import (
    REQUEST_SCHEMA,
    WORKER_ID,
)
from rocell.application.arm_bench_qualification_contract import (
    PassiveBenchRequest,
    _canonical,
)
from rocell.providers.windows.passive_serial_observation import observe_physical
from test_passive_physical_observation import inputs
from test_wizard_native_arm_metadata import no_host_access


def envelope(payload):
    request = PassiveBenchRequest(_canonical(payload["request"]))
    body = request.to_dict()
    core = dict(
        schema=REQUEST_SCHEMA,
        worker_id=WORKER_ID,
        attempt_id=body["attempt_id"],
        session_id=body["launch_id"],
        source_sha256=body["references"]["source_sha256"],
        operation_sha256=request.request_sha256,
        selected_identity_sha256=body["references"]["native_metadata_review_sha256"],
        expires_at_monotonic_ns=body["parent_deadline_monotonic_ns"],
        parent_deadline_monotonic_ns=body["parent_deadline_monotonic_ns"],
        payload=payload,
        registration_sha256=hashlib.sha256(
            _canonical(payload["registration"])
        ).hexdigest(),
    )
    return {**core, "request_sha256": hashlib.sha256(_canonical(core)).hexdigest()}


def fixture():
    request, binding, api, cancel, values = inputs()
    body = request.to_dict()
    runtime = {"fixture": "NOT A REGISTERED NATIVE RUNTIME"}
    body["references"]["runtime_sha256"] = hashlib.sha256(
        _canonical(runtime)
    ).hexdigest()
    request = PassiveBenchRequest(_canonical(body))
    payload = dict(
        schema="rocell.passive_native_child_handoff.v1",
        root="C:/fixture-root",
        request=request.to_dict(),
        setup_operation_id="operation-" + "a" * 32,
        consumption_sha256="c" * 64,
        registration=runtime,
    )
    wire = envelope(payload)
    values["metadata_operation_id"] = body["attempt_id"]
    observation = observe_physical(request, binding, api, cancel, **values)
    child = dict(
        schema="rocell.passive_native_child_result.v1",
        claim_sha256="e" * 64,
        observation=observation,
        physical_authority=False,
        connected=False,
    )
    return wire, child


def test_roundtrip_retains_held_native_result_not_connected():
    wire, child = fixture()
    decoded = codec.decode_request(_canonical(wire) + b"\n")
    result = json.loads(codec.encode_result(child, decoded))
    parsed = codec.validate_result(result, wire=decoded)
    assert parsed.to_dict()["open_state"] == "FAILED"
    assert parsed.summary()["connected"] is False


@pytest.mark.parametrize(
    "field",
    [
        "attempt_id",
        "session_id",
        "source_sha256",
        "operation_sha256",
        "selected_identity_sha256",
        "registration_sha256",
    ],
)
def test_rehashed_outer_mismatch_still_rejected(field):
    wire, _ = fixture()
    wire[field] = "f" * 64
    wire["request_sha256"] = hashlib.sha256(
        _canonical({k: v for k, v in wire.items() if k != "request_sha256"})
    ).hexdigest()
    with pytest.raises(ValueError):
        codec.decode_request(_canonical(wire))


def test_shortened_or_extended_deadline_rejected():
    wire, _ = fixture()
    wire["parent_deadline_monotonic_ns"] -= 1
    wire["request_sha256"] = hashlib.sha256(
        _canonical({k: v for k, v in wire.items() if k != "request_sha256"})
    ).hexdigest()
    with pytest.raises(ValueError, match="DEADLINE"):
        codec.decode_request(_canonical(wire))


@pytest.mark.parametrize(
    "field,value",
    [
        ("attempt_id", "other-attempt"),
        ("request_sha256", "f" * 64),
        ("physical_authority", True),
        ("connected", True),
    ],
)
def test_result_cannot_be_rebound_or_promoted(field, value):
    wire, child = fixture()
    result = json.loads(codec.encode_result(child, wire))
    result[field] = value
    with pytest.raises(ValueError):
        codec.validate_result(result, wire=wire)


def test_changed_summary_does_not_hide_failure():
    wire, child = fixture()
    child["observation"]["summary"]["status"] = "OBSERVED_CLOSED"
    with pytest.raises(ValueError, match="SUMMARY"):
        codec.encode_result(child, wire)


def test_synthetic_lifecycle_cannot_be_promoted():
    wire, child = fixture()
    child["observation"]["lifecycle"]["composition"] = "HARDWARE_INCAPABLE_REHEARSAL"
    with pytest.raises(ValueError, match="LIFECYCLE_ORIGIN"):
        codec.encode_result(child, wire)
