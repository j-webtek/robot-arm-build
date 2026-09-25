"""Closed owned-process wire binding for the passive native child.

This codec verifies association and bounded structure, not runtime authenticity,
electrical isolation or device authority. Original/claim verification and pinned
process supervision remain mandatory in the physical composition.
"""

import hashlib

from .passive_native_registration import (
    REQUEST_SCHEMA,
    RESULT_SCHEMA,
    WORKER_ID,
    validate_payload,
    _require,
)
from .owned_worker_process import decode_owned_json
from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.arm_bench_qualification_result import PassiveBenchResult


def decode_request(raw):
    value = decode_owned_json(raw, maximum=65536)
    _require(
        set(value)
        == {
            "schema",
            "worker_id",
            "attempt_id",
            "session_id",
            "source_sha256",
            "operation_sha256",
            "selected_identity_sha256",
            "expires_at_monotonic_ns",
            "parent_deadline_monotonic_ns",
            "payload",
            "registration_sha256",
            "request_sha256",
        },
        "PASSIVE_NATIVE_WIRE_FIELDS",
    )
    _require(
        value["schema"] == REQUEST_SCHEMA and value["worker_id"] == WORKER_ID,
        "PASSIVE_NATIVE_WIRE_PROTOCOL",
    )
    core = {key: item for key, item in value.items() if key != "request_sha256"}
    _require(
        hashlib.sha256(_canonical(core)).hexdigest() == value["request_sha256"],
        "PASSIVE_NATIVE_WIRE_HASH",
    )
    request = validate_payload(value["payload"])
    body = request.to_dict()
    runtime_sha = hashlib.sha256(
        _canonical(value["payload"]["registration"])
    ).hexdigest()
    _require(
        value["registration_sha256"]
        == runtime_sha
        == body["references"]["runtime_sha256"],
        "PASSIVE_NATIVE_WIRE_RUNTIME",
    )
    _require(
        value["attempt_id"] == body["attempt_id"]
        and value["session_id"] == body["launch_id"]
        and value["source_sha256"] == body["references"]["source_sha256"]
        and value["selected_identity_sha256"]
        == body["references"]["native_metadata_review_sha256"]
        and value["operation_sha256"] == request.request_sha256,
        "PASSIVE_NATIVE_WIRE_REQUEST_BINDING",
    )
    for field in ("expires_at_monotonic_ns", "parent_deadline_monotonic_ns"):
        _require(
            type(value[field]) is int
            and value[field] == body["parent_deadline_monotonic_ns"],
            "PASSIVE_NATIVE_WIRE_DEADLINE",
        )
    return value


def encode_result(child_result, wire):
    result = {
        "schema": RESULT_SCHEMA,
        "request_sha256": wire["request_sha256"],
        "attempt_id": wire["attempt_id"],
        "child_result": child_result,
        "physical_authority": False,
        "connected": False,
    }
    validate_result(result, wire=wire)
    return _canonical(result)


def validate_result(value, *, wire):
    from rocell.application.wizard_native_arm_metadata import (
        summarize_native_arm_metadata,
    )

    # Revalidate the supplied envelope too; callers cannot change the expected
    # request after decoding and then validate a result against new expectations.
    checked = decode_request(_canonical(wire))
    request = validate_payload(checked["payload"])
    _require(
        type(value) is dict
        and set(value)
        == {
            "schema",
            "request_sha256",
            "attempt_id",
            "child_result",
            "physical_authority",
            "connected",
        },
        "PASSIVE_NATIVE_RESULT_FIELDS",
    )
    _require(
        value["schema"] == RESULT_SCHEMA
        and value["request_sha256"] == checked["request_sha256"]
        and value["attempt_id"] == checked["attempt_id"]
        and value["physical_authority"] is False
        and value["connected"] is False,
        "PASSIVE_NATIVE_RESULT_BINDING",
    )
    child = value["child_result"]
    _require(
        type(child) is dict
        and set(child)
        == {"schema", "claim_sha256", "observation", "physical_authority", "connected"}
        and child["schema"] == "rocell.passive_native_child_result.v1"
        and child["physical_authority"] is False
        and child["connected"] is False,
        "PASSIVE_NATIVE_CHILD_RESULT",
    )
    from .owned_worker_process import _hash

    _hash(child["claim_sha256"])
    observation = child["observation"]
    _require(
        type(observation) is dict
        and set(observation)
        == {
            "result",
            "summary",
            "lifecycle",
            "provenance",
            "physical_authority",
            "connected",
            "identity_recheck",
        }
        and observation["provenance"]
        == "NATIVE_LIFECYCLE_RESULT_NOT_COMMISSIONING_ACCEPTANCE"
        and observation["physical_authority"] is False
        and observation["connected"] is False,
        "PASSIVE_NATIVE_OBSERVATION_RESULT",
    )
    parsed = PassiveBenchResult(_canonical(observation["result"]), request)
    _require(
        _canonical(parsed.summary()) == _canonical(observation["summary"]),
        "PASSIVE_NATIVE_RESULT_SUMMARY",
    )
    lifecycle = observation["lifecycle"]
    _require(
        type(lifecycle) is dict
        and lifecycle.get("schema") == "rocell.nonpurging_serial_lifecycle.v1"
        and lifecycle.get("composition")
        in {
            "WINDOWS_NONPURGING_SERIAL_PHYSICAL_HELD",
            "WINDOWS_PASSIVE_SERIAL_ENGINEERING",
        }
        and lifecycle.get("physical_authority") is False
        and lifecycle.get("arm_connected") is False,
        "PASSIVE_NATIVE_LIFECYCLE_ORIGIN",
    )
    recheck = observation["identity_recheck"]
    _require(
        type(recheck) is dict
        and recheck.get("schema") == "rocell.passive_arm_identity_recheck.v1"
        and recheck.get("status") == "METADATA_RECHECK_MATCHED"
        and recheck.get("mode") == "physical"
        and recheck.get("blockers") == []
        and recheck.get("physical_authority") is False
        and recheck.get("connected") is False,
        "PASSIVE_NATIVE_RECHECK_RESULT",
    )
    fresh = summarize_native_arm_metadata(recheck["fresh_report"])
    _require(
        fresh["status"] == "METADATA_CORRELATED"
        and fresh["binding"]["mode"] == "physical"
        and fresh["binding"]["session_id"] == checked["session_id"]
        and fresh["binding"]["source_sha256"] == checked["source_sha256"]
        and fresh["binding"]["operation_id"] == checked["attempt_id"],
        "PASSIVE_NATIVE_RECHECK_BINDING",
    )
    return parsed
