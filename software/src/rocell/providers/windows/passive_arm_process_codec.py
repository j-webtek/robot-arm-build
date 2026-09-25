"""Exact membership for one incapable passive-arm IPC fixture; no live release."""

import hashlib
from pathlib import Path
import sys

from rocell.application.arm_bench_qualification_contract import (
    PassiveBenchRequest,
    _canonical,
)
from rocell.application.arm_bench_qualification_result import PassiveBenchResult


PAYLOAD_SCHEMA = "rocell.owned_passive_arm_fixture_payload.v1"
REQUEST_SCHEMA = "rocell.owned_passive_arm_fixture_request.v1"
RESULT_SCHEMA = "rocell.owned_passive_arm_fixture_result.v1"
FIXTURE_PATH = Path(__file__).with_name("_passive_arm_process_fixture.py")
SCENARIOS = frozenset(
    {
        "nominal",
        "open-failed",
        "cleanup-unknown",
        "malformed",
        "wrong-binding",
        "stall",
        "lifecycle-nominal",
        "lifecycle-open-failed",
        "lifecycle-cleanup-unknown",
    }
)


def require(condition, code):
    if not condition:
        raise ValueError(code)


def validate_payload(value):
    require(
        type(value) is dict
        and set(value) == {"schema", "scenario", "request", "selected_identity_sha256"},
        "PASSIVE_FIXTURE_PAYLOAD_FIELDS",
    )
    require(
        value["schema"] == PAYLOAD_SCHEMA
        and type(value["scenario"]) is str
        and value["scenario"] in SCENARIOS,
        "PASSIVE_FIXTURE_SCENARIO",
    )
    request = PassiveBenchRequest(_canonical(value["request"]))
    require(request.to_dict()["mode"] == "rehearsal", "PASSIVE_PHYSICAL_DISPATCH_HELD")
    from .owned_worker_process import _hash

    _hash(value["selected_identity_sha256"])
    return request


def validate_registration(registration, outer):
    from .owned_worker_process import decode_owned_json, owned_registration_document

    payload = decode_owned_json(outer.payload_json, maximum=60 * 1024)
    request = validate_payload(payload)
    body = request.to_dict()
    require(
        registration.worker_id == "incapable-passive-arm"
        and registration.composition == "INCAPABLE_PROCESS_FIXTURE"
        and registration.request_schema == REQUEST_SCHEMA
        and registration.result_schema == RESULT_SCHEMA,
        "PASSIVE_FIXTURE_REGISTRATION",
    )
    require(
        registration.executable.path
        == Path(getattr(sys, "_base_executable", sys.executable)),
        "PASSIVE_FIXTURE_FIXED_INTERPRETER",
    )
    if payload["scenario"].startswith("lifecycle-"):
        from .passive_arm_lifecycle_package import (
            validate_registration as validate_package,
        )

        validate_package(registration, payload["scenario"])
    else:
        require(
            registration.argv == ("-I", "-S", str(FIXTURE_PATH), payload["scenario"])
            and len(registration.package_files) == 1
            and registration.package_files[0].path == FIXTURE_PATH,
            "PASSIVE_FIXTURE_FIXED_COMMAND",
        )
    runtime_digest = hashlib.sha256(
        _canonical(owned_registration_document(registration))
    ).hexdigest()
    require(
        body["references"]["runtime_sha256"] == runtime_digest,
        "PASSIVE_FIXTURE_RUNTIME_BINDING",
    )
    require(
        body["attempt_id"] == outer.attempt_id
        and body["launch_id"] == outer.session_id
        and body["references"]["source_sha256"] == outer.source_sha256
        and body["parent_deadline_monotonic_ns"] == outer.expires_at_ns
        and request.request_sha256 == outer.operation_sha256
        and payload["selected_identity_sha256"] == outer.selected_identity_sha256,
        "PASSIVE_FIXTURE_REQUEST_BINDING",
    )
    budget = registration.budget
    require(
        budget.process_count == 1
        and budget.run_timeout_ms <= 10_000
        and budget.cleanup_timeout_ms <= 2000
        and budget.stdout_bytes == 128 * 1024
        and budget.stderr_bytes <= 8192,
        "PASSIVE_FIXTURE_PROCESS_BUDGET",
    )
    return payload


def validate_result(value, *, payload, request_sha256, attempt_id):
    request = validate_payload(payload)
    extra = {"lifecycle"} if payload["scenario"].startswith("lifecycle-") else set()
    require(
        type(value) is dict
        and set(value)
        == extra
        | {
            "schema",
            "request_sha256",
            "attempt_id",
            "physical_authority",
            "scenario",
            "passive_result",
        },
        "PASSIVE_FIXTURE_RESULT_FIELDS",
    )
    if extra:
        lifecycle = value["lifecycle"]
        require(
            type(lifecycle) is dict
            and lifecycle.get("schema") == "rocell.nonpurging_serial_lifecycle.v1"
            and lifecycle.get("composition") == "HARDWARE_INCAPABLE_REHEARSAL"
            and lifecycle.get("physical_authority") is False
            and lifecycle.get("arm_connected") is False,
            "PASSIVE_LIFECYCLE_RESULT_REQUIRED",
        )
    require(
        value["schema"] == RESULT_SCHEMA
        and value["request_sha256"] == request_sha256
        and value["attempt_id"] == attempt_id
        and value["physical_authority"] is False
        and value["scenario"] == payload["scenario"],
        "PASSIVE_FIXTURE_RESULT_BINDING",
    )
    return PassiveBenchResult(_canonical(value["passive_result"]), request)
