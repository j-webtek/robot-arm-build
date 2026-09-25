"""Bounded request/result association for supervised powered feedback."""

import base64
import hashlib

from .powered_feedback_native_registration import (
    REQUEST_SCHEMA,
    RESULT_SCHEMA,
    WORKER_ID,
    validate_payload,
    require,
)
from .owned_worker_process import decode_owned_json
from rocell.application.arm_bench_qualification_contract import _canonical


def decode_request(raw):
    wire = decode_owned_json(raw, maximum=65536)
    require(
        type(wire) is dict
        and set(wire)
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
        "POWERED_NATIVE_WIRE_FIELDS",
    )
    require(
        wire["schema"] == REQUEST_SCHEMA and wire["worker_id"] == WORKER_ID,
        "POWERED_NATIVE_WIRE_DOMAIN",
    )
    require(
        hashlib.sha256(
            _canonical({k: v for k, v in wire.items() if k != "request_sha256"})
        ).hexdigest()
        == wire["request_sha256"],
        "POWERED_NATIVE_WIRE_HASH",
    )
    intent = validate_payload(wire["payload"])
    body = intent.to_dict()
    require(
        wire["attempt_id"] == body["attempt_id"]
        and wire["session_id"] == body["session_id"]
        and wire["source_sha256"] == body["references"]["source_sha256"]
        and wire["selected_identity_sha256"]
        == body["references"]["native_identity_original_sha256"]
        and wire["operation_sha256"] == intent.request_sha256
        and wire["registration_sha256"] == body["references"]["runtime_sha256"],
        "POWERED_NATIVE_WIRE_BINDING",
    )
    for key in ("expires_at_monotonic_ns", "parent_deadline_monotonic_ns"):
        require(
            type(wire[key]) is int
            and wire[key] == body["parent_deadline_monotonic_ns"],
            "POWERED_NATIVE_WIRE_DEADLINE",
        )
    return wire


def encode_result(child, wire):
    result = {
        "schema": RESULT_SCHEMA,
        "attempt_id": wire["attempt_id"],
        "request_sha256": wire["request_sha256"],
        "child_result": child,
        "physical_authority": False,
        "connected": False,
    }
    validate_result(result, wire=wire)
    return _canonical(result)


def validate_result(value, *, wire):
    from .owned_worker_process import _hash
    from rocell.arm.feedback_wire import validate_feedback_response_line

    wire = decode_request(_canonical(wire))
    require(
        type(value) is dict
        and set(value)
        == {
            "schema",
            "attempt_id",
            "request_sha256",
            "child_result",
            "physical_authority",
            "connected",
        },
        "POWERED_NATIVE_RESULT_FIELDS",
    )
    require(
        value["schema"] == RESULT_SCHEMA
        and value["attempt_id"] == wire["attempt_id"]
        and value["request_sha256"] == wire["request_sha256"]
        and value["physical_authority"] is False
        and value["connected"] is False,
        "POWERED_NATIVE_RESULT_BINDING",
    )
    child = value["child_result"]
    require(
        type(child) is dict
        and set(child)
        == {
            "schema",
            "claim_sha256",
            "observation",
            "fresh_snapshot",
            "physical_authority",
            "connected",
        }
        and child["schema"] == "rocell.powered_feedback_native_child_result.v1"
        and child["physical_authority"] is False
        and child["connected"] is False,
        "POWERED_NATIVE_CHILD_FIELDS",
    )
    _hash(child["claim_sha256"])
    from rocell.application.wizard_native_arm_metadata import decode_controller_snapshot

    decode_controller_snapshot(child["fresh_snapshot"], "physical")
    obs = child["observation"]
    from rocell.application.powered_arm_feedback_contract import TELEMETRY_PURPOSE
    if wire["payload"]["intent"]["purpose"] == TELEMETRY_PURPOSE:
        from .powered_telemetry_wire import validate_observation
        return validate_observation(obs, wire=wire)
    require(
        type(obs) is dict
        and obs.get("schema") == "rocell.powered_feedback_observation.v1"
        and obs.get("request_sha256") == wire["operation_sha256"]
        and obs.get("origin") == "PHYSICAL_OBSERVATION"
        and obs.get("physical_authority") is False
        and obs.get("connected") is False
        and obs.get("motion_authorized") is False
        and obs.get("status") in {"FEEDBACK_OBSERVED_CLOSED", "FAILED"},
        "POWERED_NATIVE_OBSERVATION",
    )
    lifecycle = obs["lifecycle"]
    require(
        lifecycle.get("composition") == "WINDOWS_POWERED_FEEDBACK_ENGINEERING"
        and lifecycle.get("physical_authority") is False
        and lifecycle.get("arm_connected") is False,
        "POWERED_NATIVE_LIFECYCLE",
    )
    require(
        type(lifecycle["confirmed_write_bytes"]) is int
        and 0 <= lifecycle["confirmed_write_bytes"] <= 10,
        "POWERED_NATIVE_WRITE_BOUND",
    )
    buffers = {}
    for name in ("startup", "response", "late_cleanup_input"):
        blob = obs[name]
        require(
            type(blob) is dict
            and set(blob) == {"bytes", "sha256", "base64"}
            and type(blob["base64"]) is str,
            "POWERED_NATIVE_BUFFER_FIELDS",
        )
        raw = base64.b64decode(blob["base64"], validate=True)
        require(
            type(blob["bytes"]) is int
            and blob["bytes"] == len(raw) <= 65537
            and hashlib.sha256(raw).hexdigest() == blob["sha256"],
            "POWERED_NATIVE_BUFFER_HASH",
        )
        buffers[name] = raw
    if obs["status"] == "FEEDBACK_OBSERVED_CLOSED":
        feedback = validate_feedback_response_line(
            buffers["response"], max_line_bytes=65536
        )
        require(
            _canonical(feedback) == _canonical(obs["feedback"])
            and {"x", "y", "z", "tit", "b", "s", "e", "t", "r", "g", "v"}.issubset(
                feedback
            )
            and not buffers["startup"]
            and not buffers["late_cleanup_input"]
            and obs["errors"] == []
            and lifecycle["cleanup_confirmed"] is True
            and lifecycle["confirmed_write_bytes"] == 10,
            "POWERED_NATIVE_SUCCESS_REQUIREMENTS",
        )
    return obs
