"""Exact parent registration checks for the fixed passive native child.

Validation does not dispatch or release native access. The owned supervisor also
requires retained consumed originals before starting this child. Callers cannot
supply an alternate child or archive; serial loading remains separately held.
"""

import hashlib
from pathlib import Path
import re
import sys

from rocell.application.arm_bench_qualification_contract import (
    PassiveBenchRequest,
    _canonical,
)

PAYLOAD_SCHEMA = "rocell.passive_native_child_handoff.v1"
REQUEST_SCHEMA = "rocell.owned_passive_native_request.v1"
RESULT_SCHEMA = "rocell.owned_passive_native_result.v1"
WORKER_ID = "physical-passive-arm"


def _require(value, message):
    if not value:
        raise ValueError(message)


def validate_payload(value):
    from .owned_worker_process import _path, _hash

    _require(
        type(value) is dict
        and set(value)
        == {
            "schema",
            "root",
            "request",
            "setup_operation_id",
            "consumption_sha256",
            "registration",
        },
        "PASSIVE_NATIVE_HANDOFF_FIELDS",
    )
    _require(value["schema"] == PAYLOAD_SCHEMA, "PASSIVE_NATIVE_HANDOFF_SCHEMA")
    _require(type(value["root"]) is str, "PASSIVE_NATIVE_JOURNAL_ROOT")
    _path(Path(value["root"]))
    _hash(value["consumption_sha256"])
    _require(
        type(value["setup_operation_id"]) is str
        and re.fullmatch(r"operation-[a-f0-9]{32}", value["setup_operation_id"])
        is not None,
        "PASSIVE_NATIVE_SETUP_OPERATION",
    )
    _require(
        type(value["registration"]) is dict, "PASSIVE_NATIVE_REGISTRATION_REQUIRED"
    )
    request = PassiveBenchRequest(_canonical(value["request"]))
    _require(
        request.to_dict()["mode"] == "physical",
        "PASSIVE_NATIVE_PHYSICAL_REQUEST_REQUIRED",
    )
    return request


def validate_registration(registration, outer):
    from .owned_worker_process import (
        WorkerProcessRegistration,
        OwnedWorkerRequest,
        WorkerProcessBudget,
        decode_owned_json,
        owned_registration_document,
    )
    from .passive_native_package import CHILD, expected_archive
    from .owned_arm_feedback_package import _read, MAX_FILE_BYTES
    from rocell.application.passive_arm_attempt_store import (
        MAX_STDOUT_BYTES,
        MAX_STDERR_BYTES,
    )

    _require(
        type(registration) is WorkerProcessRegistration
        and type(outer) is OwnedWorkerRequest,
        "PASSIVE_NATIVE_EXACT_TYPES",
    )
    registration.__post_init__()
    outer.__post_init__()
    payload = decode_owned_json(outer.payload_json, maximum=60 * 1024)
    request = validate_payload(payload)
    body = request.to_dict()
    _require(
        registration.worker_id == WORKER_ID
        and registration.composition == "PHYSICAL_UNQUALIFIED"
        and registration.request_schema == REQUEST_SCHEMA
        and registration.result_schema == RESULT_SCHEMA,
        "PASSIVE_NATIVE_REGISTRATION_IDENTITY",
    )
    _require(
        registration.executable.path
        == Path(getattr(sys, "_base_executable", sys.executable)),
        "PASSIVE_NATIVE_FIXED_INTERPRETER",
    )
    pins = registration.package_files
    _require(
        len(pins) == 2
        and pins[0].path == CHILD
        and pins[1].path == registration.working_directory / "passive-native.zip"
        and registration.argv
        == ("-I", "-S", str(CHILD), str(pins[1].path), pins[1].sha256, "observe"),
        "PASSIVE_NATIVE_FIXED_COMMAND",
    )
    _require(
        pins[0].sha256 == hashlib.sha256(_read(CHILD, MAX_FILE_BYTES)).hexdigest()
        and pins[1].sha256 == hashlib.sha256(expected_archive()).hexdigest(),
        "PASSIVE_NATIVE_CURRENT_SOURCE_REQUIRED",
    )
    expected_budget = WorkerProcessBudget(
        run_timeout_ms=20_000,
        cleanup_timeout_ms=2000,
        stdin_bytes=65536,
        stdout_bytes=MAX_STDOUT_BYTES,
        stderr_bytes=MAX_STDERR_BYTES,
        process_count=1,
    )
    _require(
        registration.budget == expected_budget, "PASSIVE_NATIVE_EXACT_PROCESS_BUDGET"
    )
    runtime = owned_registration_document(registration)
    runtime_sha = hashlib.sha256(_canonical(runtime)).hexdigest()
    _require(
        _canonical(payload["registration"]) == _canonical(runtime)
        and body["references"]["runtime_sha256"] == runtime_sha,
        "PASSIVE_NATIVE_RUNTIME_BINDING",
    )
    _require(
        body["attempt_id"] == outer.attempt_id
        and body["launch_id"] == outer.session_id
        and body["references"]["source_sha256"] == outer.source_sha256
        and body["parent_deadline_monotonic_ns"] == outer.expires_at_ns
        and request.request_sha256 == outer.operation_sha256
        and body["references"]["native_metadata_review_sha256"]
        == outer.selected_identity_sha256,
        "PASSIVE_NATIVE_REQUEST_BINDING",
    )
    # The child working directory is private to this service attempt and sits
    # beside journal originals, not inside a user-selectable alternate root.
    _require(
        registration.working_directory
        == Path(payload["root"]) / (outer.attempt_id + "-native-child"),
        "PASSIVE_NATIVE_ASSIGNED_DIRECTORY",
    )
    return payload
