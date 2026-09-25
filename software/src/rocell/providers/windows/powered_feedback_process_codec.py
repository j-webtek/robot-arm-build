"""Closed supervised powered rehearsal protocol. No physical composition."""

import base64
import hashlib
from pathlib import Path
import re
import sys

from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.wizard_powered_feedback_rehearsal import ACTION, SCENARIOS

PAYLOAD_SCHEMA = "rocell.owned_powered_feedback_rehearsal_payload.v1"
REQUEST_SCHEMA = "rocell.owned_powered_feedback_rehearsal_request.v1"
RESULT_SCHEMA = "rocell.owned_powered_feedback_rehearsal_result.v1"
WORKER_ID = "incapable-powered-feedback"
IDENTITY = hashlib.sha256(b"SYNTHETIC-POWERED-FEEDBACK-NOT-A-DEVICE").hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def validate_payload(value):
    require(
        type(value) is dict
        and set(value)
        == {"schema", "session_id", "operation_id", "source_sha256", "scenario"},
        "POWERED_PAYLOAD_FIELDS",
    )
    require(
        value["schema"] == PAYLOAD_SCHEMA
        and type(value["scenario"]) is str
        and value["scenario"] in SCENARIOS,
        "POWERED_PAYLOAD_SCENARIO",
    )
    for name, pattern in (
        ("session_id", r"wizard-[a-f0-9]{32}"),
        ("operation_id", r"operation-[a-f0-9]{32}"),
        ("source_sha256", r"[a-f0-9]{64}"),
    ):
        require(
            type(value[name]) is str and re.fullmatch(pattern, value[name]) is not None,
            "POWERED_PAYLOAD_CONTEXT",
        )
    return value


def validate_registration(reg, outer):
    from .owned_worker_process import decode_owned_json, WorkerProcessBudget
    from .powered_feedback_package import CHILD, expected_archive
    from .owned_arm_feedback_package import _read, MAX_FILE_BYTES

    value = validate_payload(decode_owned_json(outer.payload_json, maximum=4096))
    require(
        reg.worker_id == WORKER_ID
        and reg.composition == "INCAPABLE_PROCESS_FIXTURE"
        and reg.request_schema == REQUEST_SCHEMA
        and reg.result_schema == RESULT_SCHEMA,
        "POWERED_REGISTRATION_DOMAIN",
    )
    require(
        reg.executable.path == Path(getattr(sys, "_base_executable", sys.executable)),
        "POWERED_FIXED_INTERPRETER",
    )
    require(len(reg.package_files) == 2, "POWERED_FIXED_PACKAGE")
    child, archive = reg.package_files
    require(
        child.path == CHILD
        and child.sha256 == hashlib.sha256(_read(CHILD, MAX_FILE_BYTES)).hexdigest()
        and archive.path == reg.working_directory / "powered-feedback.zip"
        and archive.sha256 == hashlib.sha256(expected_archive()).hexdigest(),
        "POWERED_PACKAGE_SOURCE_MISMATCH",
    )
    require(
        reg.working_directory.name == outer.attempt_id + "-powered-feedback-child"
        and reg.argv
        == (
            "-I",
            "-S",
            str(CHILD),
            str(archive.path),
            archive.sha256,
            "supervised-rehearse",
        ),
        "POWERED_FIXED_COMMAND",
    )
    require(
        reg.budget
        == WorkerProcessBudget(
            run_timeout_ms=8000,
            cleanup_timeout_ms=2000,
            stdout_bytes=256 * 1024,
            stderr_bytes=8192,
            process_count=1,
        ),
        "POWERED_FIXED_BUDGET",
    )
    require(
        outer.session_id == value["session_id"]
        and outer.attempt_id == value["operation_id"]
        and outer.source_sha256 == value["source_sha256"]
        and outer.operation_sha256 == hashlib.sha256(_canonical(value)).hexdigest()
        and outer.selected_identity_sha256 == IDENTITY,
        "POWERED_REQUEST_CONTEXT",
    )
    return value


def decode_request(raw):
    from .owned_worker_process import decode_owned_json

    value = decode_owned_json(raw, maximum=65536)
    require(
        type(value) is dict
        and set(value)
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
        "POWERED_WIRE_FIELDS",
    )
    require(
        value["schema"] == REQUEST_SCHEMA and value["worker_id"] == WORKER_ID,
        "POWERED_WIRE_DOMAIN",
    )
    require(
        hashlib.sha256(
            _canonical({k: v for k, v in value.items() if k != "request_sha256"})
        ).hexdigest()
        == value["request_sha256"],
        "POWERED_WIRE_HASH",
    )
    payload = validate_payload(value["payload"])
    require(
        value["attempt_id"] == payload["operation_id"]
        and value["session_id"] == payload["session_id"]
        and value["source_sha256"] == payload["source_sha256"]
        and value["selected_identity_sha256"] == IDENTITY
        and value["operation_sha256"]
        == hashlib.sha256(_canonical(payload)).hexdigest(),
        "POWERED_WIRE_CONTEXT",
    )
    require(
        type(value["registration_sha256"]) is str
        and re.fullmatch(r"[a-f0-9]{64}", value["registration_sha256"]),
        "POWERED_WIRE_REGISTRATION",
    )
    require(
        type(value["expires_at_monotonic_ns"]) is int
        and type(value["parent_deadline_monotonic_ns"]) is int
        and 0
        < value["expires_at_monotonic_ns"]
        == value["parent_deadline_monotonic_ns"]
        < 2**63,
        "POWERED_WIRE_DEADLINE",
    )
    return value


def validate_result(value, *, payload, request_sha256, attempt_id):
    from .owned_worker_process import decode_owned_json

    validate_payload(payload)
    require(
        type(value) is dict
        and set(value)
        == {
            "schema",
            "request_sha256",
            "attempt_id",
            "completion",
            "original_base64",
            "physical_authority",
            "connected",
        },
        "POWERED_RESULT_FIELDS",
    )
    require(
        value["schema"] == RESULT_SCHEMA
        and value["request_sha256"] == request_sha256
        and value["attempt_id"] == attempt_id == payload["operation_id"]
        and value["physical_authority"] is False
        and value["connected"] is False,
        "POWERED_RESULT_CONTEXT",
    )
    require(type(value["original_base64"]) is str, "POWERED_RESULT_ORIGINAL")
    raw = base64.b64decode(value["original_base64"], validate=True)
    original = decode_owned_json(raw, maximum=128 * 1024)
    require(
        original["schema"] == "rocell.wizard_powered_feedback_rehearsal_original.v1"
        and original["origin"] == "SYNTHETIC_REHEARSAL"
        and original["physical_authority"] is False
        and original["session_id"] == payload["session_id"]
        and original["operation_id"] == attempt_id
        and original["source_sha256"] == payload["source_sha256"]
        and original["scenario"] == payload["scenario"],
        "POWERED_ORIGINAL_CONTEXT",
    )
    completion = value["completion"]
    require(
        type(completion) is dict
        and completion.get("schema") == "rocell.wizard_worker_result.v1"
        and completion.get("action_id") == ACTION
        and completion.get("physical_authority") is False
        and completion.get("status") in {"SUCCEEDED", "FAILED", "CANCELLED"},
        "POWERED_COMPLETION",
    )
    for name in (
        "device_open_count",
        "serial_write_count",
        "power_event_count",
        "motion_command_count",
        "contact_command_count",
    ):
        require(
            type(completion.get(name)) is int and completion[name] == 0,
            "POWERED_PHYSICAL_EFFECT_CLAIM",
        )
    report = completion["steps"][0]["report"]
    observation = original["observation"]
    require(observation["origin"] == "SYNTHETIC_REHEARSAL"
            and observation["motion_authorized"] is False
            and observation["lifecycle"]["composition"] == "HARDWARE_INCAPABLE_REHEARSAL"
            and observation["lifecycle"]["physical_authority"] is False
            and observation["lifecycle"]["arm_connected"] is False, "POWERED_OBSERVATION_ORIGIN")
    if observation["status"] == "FEEDBACK_OBSERVED_CLOSED":
        require(observation["feedback"] is not None and observation["errors"] == []
                and observation["lifecycle"]["cleanup_confirmed"] is True, "POWERED_SUCCESS_WITHOUT_CLEANUP")
    require(
        report["original_sha256"] == hashlib.sha256(raw).hexdigest()
        and report["status"] == observation["status"]
        and report["simulated_write_bytes"]
        == observation["lifecycle"]["confirmed_write_bytes"]
        and report["cleanup_confirmed"] is observation["lifecycle"]["cleanup_confirmed"]
        and report["errors"] == observation["errors"]
        and report["origin"] == "SYNTHETIC_REHEARSAL"
        and report["connected"] is False
        and observation["physical_authority"] is False
        and observation["connected"] is False,
        "POWERED_OBSERVATION_BINDING",
    )
    require(
        (completion["status"] == "SUCCEEDED")
        == (observation["status"] == "FEEDBACK_OBSERVED_CLOSED"),
        "POWERED_STATUS_MISMATCH",
    )
    return raw
