"""Closed registration for the one-query powered engineering worker."""

import hashlib
from pathlib import Path
import sys

from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.powered_arm_feedback_contract import PoweredFeedbackIntent

PAYLOAD_SCHEMA = "rocell.powered_feedback_native_handoff.v1"
REQUEST_SCHEMA = "rocell.owned_powered_feedback_native_request.v1"
RESULT_SCHEMA = "rocell.owned_powered_feedback_native_result.v1"
WORKER_ID = "physical-powered-feedback"


def require(value, code):
    if not value:
        raise ValueError(code)


def validate_payload(value):
    from .owned_worker_process import _path, _hash

    require(
        type(value) is dict
        and set(value)
        == {"schema", "root", "intent", "consumption_sha256", "registration"},
        "POWERED_NATIVE_HANDOFF_FIELDS",
    )
    require(
        value["schema"] == PAYLOAD_SCHEMA
        and type(value["root"]) is str
        and type(value["registration"]) is dict,
        "POWERED_NATIVE_HANDOFF_DOMAIN",
    )
    _path(Path(value["root"]))
    _hash(value["consumption_sha256"])
    intent = PoweredFeedbackIntent(_canonical(value["intent"]))
    require(
        intent.to_dict()["mode"] == "physical",
        "POWERED_NATIVE_PHYSICAL_INTENT_REQUIRED",
    )
    require(
        hashlib.sha256(_canonical(value["registration"])).hexdigest()
        == intent.to_dict()["references"]["runtime_sha256"],
        "POWERED_NATIVE_RUNTIME_HASH",
    )
    return intent


def validate_registration(registration, outer):
    from .owned_worker_process import (
        WorkerProcessRegistration,
        OwnedWorkerRequest,
        WorkerProcessBudget,
        decode_owned_json,
        owned_registration_document,
    )
    from .powered_feedback_native_package import CHILD, expected_archive
    from .owned_arm_feedback_package import _read, MAX_FILE_BYTES

    require(
        type(registration) is WorkerProcessRegistration
        and type(outer) is OwnedWorkerRequest,
        "POWERED_NATIVE_EXACT_TYPES",
    )
    registration.__post_init__()
    outer.__post_init__()
    payload = decode_owned_json(outer.payload_json, maximum=60 * 1024)
    intent = validate_payload(payload)
    body = intent.to_dict()
    require(
        registration.worker_id == WORKER_ID
        and registration.composition == "PHYSICAL_UNQUALIFIED"
        and registration.request_schema == REQUEST_SCHEMA
        and registration.result_schema == RESULT_SCHEMA,
        "POWERED_NATIVE_REGISTRATION_DOMAIN",
    )
    require(
        registration.executable.path
        == Path(getattr(sys, "_base_executable", sys.executable)),
        "POWERED_NATIVE_FIXED_INTERPRETER",
    )
    pins = registration.package_files
    require(
        len(pins) == 2
        and pins[0].path == CHILD
        and pins[1].path
        == registration.working_directory / "powered-feedback-native.zip"
        and registration.argv
        == ("-I", "-S", str(CHILD), str(pins[1].path), pins[1].sha256, "observe"),
        "POWERED_NATIVE_FIXED_COMMAND",
    )
    require(
        pins[0].sha256 == hashlib.sha256(_read(CHILD, MAX_FILE_BYTES)).hexdigest()
        and pins[1].sha256 == hashlib.sha256(expected_archive()).hexdigest(),
        "POWERED_NATIVE_CURRENT_SOURCE",
    )
    require(
        registration.budget
        == WorkerProcessBudget(
            run_timeout_ms=20000,
            cleanup_timeout_ms=2000,
            stdin_bytes=65536,
            stdout_bytes=256 * 1024,
            stderr_bytes=8192,
            process_count=1,
        ),
        "POWERED_NATIVE_FIXED_BUDGET",
    )
    require(
        _canonical(payload["registration"])
        == _canonical(owned_registration_document(registration)),
        "POWERED_NATIVE_RUNTIME_BINDING",
    )
    require(
        body["attempt_id"] == outer.attempt_id
        and body["session_id"] == outer.session_id
        and body["references"]["source_sha256"] == outer.source_sha256
        and body["parent_deadline_monotonic_ns"] == outer.expires_at_ns
        and intent.request_sha256 == outer.operation_sha256
        and body["references"]["native_identity_original_sha256"]
        == outer.selected_identity_sha256,
        "POWERED_NATIVE_REQUEST_BINDING",
    )
    require(
        registration.working_directory
        == Path(payload["root"]) / (outer.attempt_id + "-powered-native-child"),
        "POWERED_NATIVE_ASSIGNED_DIRECTORY",
    )
    return payload
