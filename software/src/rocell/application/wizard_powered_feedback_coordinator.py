"""One source-pinned, owned memory-only child per wizard rehearsal operation."""

import base64
from copy import deepcopy
import hashlib
from pathlib import Path
import re
import sys
import time

from .arm_bench_qualification_contract import _canonical
from .physical_onboarding_durability import PublicationMode, publish_bytes, safe_root
from .wizard_powered_feedback_rehearsal import ACTION
from rocell.providers.windows import powered_feedback_process_codec as codec
from rocell.providers.windows.powered_feedback_package import prepare, CHILD
from rocell.providers.windows.owned_arm_feedback_package import _read
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessBudget,
    WorkerProcessRegistration,
    OwnedWorkerRequest,
    OwnedWindowsWorker,
    owned_registration_document,
)


def run_supervised_rehearsal(
    *,
    root,
    session_id,
    operation_id,
    source_sha256,
    scenario,
    cancellation,
    deadline_ns,
    recheck_source
):
    payload = codec.validate_payload(
        dict(
            schema=codec.PAYLOAD_SCHEMA,
            session_id=session_id,
            operation_id=operation_id,
            source_sha256=source_sha256,
            scenario=scenario,
        )
    )
    parent = safe_root(Path(root))
    directory = parent / (operation_id + "-powered-feedback-child")
    directory.mkdir(exist_ok=False)

    def pin(path):
        return PinnedWorkerFile(
            path, hashlib.sha256(_read(path, 64 * 1024 * 1024)).hexdigest()
        )

    archive = pin(prepare(directory))
    registration = WorkerProcessRegistration(
        codec.WORKER_ID,
        pin(Path(getattr(sys, "_base_executable", sys.executable))),
        (
            "-I",
            "-S",
            str(CHILD),
            str(archive.path),
            archive.sha256,
            "supervised-rehearse",
        ),
        (pin(CHILD), archive),
        directory,
        WorkerProcessBudget(
            run_timeout_ms=8000,
            cleanup_timeout_ms=2000,
            stdout_bytes=256 * 1024,
            stderr_bytes=8192,
            process_count=1,
        ),
        "INCAPABLE_PROCESS_FIXTURE",
        codec.REQUEST_SCHEMA,
        codec.RESULT_SCHEMA,
    )
    outer = OwnedWorkerRequest(
        operation_id,
        session_id,
        source_sha256,
        hashlib.sha256(_canonical(payload)).hexdigest(),
        codec.IDENTITY,
        deadline_ns,
        _canonical(payload),
    )

    def authorize(actual_registration, actual_request, digest):
        if actual_registration != registration or actual_request != outer:
            raise ValueError("Powered rehearsal dispatch inputs changed")
        recheck_source()
        codec.validate_registration(actual_registration, actual_request)
        if time.monotonic_ns() >= deadline_ns:
            raise ValueError("Powered rehearsal deadline expired")

    codec.validate_registration(registration, outer)
    recheck_source()
    publish_bytes(
        directory,
        "prepared-rehearsal.json",
        _canonical(
            {
                "payload": payload,
                "registration": owned_registration_document(registration),
                "physical_authority": False,
                "replay_allowed": False,
            }
        ),
        mode=PublicationMode.IMMUTABLE,
        maximum_bytes=128 * 1024,
    )
    owned = OwnedWindowsWorker(registration, authorizer=authorize).run(
        outer, cancellation=cancellation, deadline_ns=deadline_ns
    )
    process = {
        key: value for key, value in owned.to_dict().items() if key != "parsed_result"
    }
    diagnostic = _canonical(
        {
            "schema": "rocell.powered_feedback_owned_rehearsal.v1",
            "session_id": session_id,
            "operation_id": operation_id,
            "source_sha256": source_sha256,
            "registration": owned_registration_document(registration),
            "payload": payload,
            "process": process,
            "stdout_base64": base64.b64encode(owned.stdout).decode("ascii"),
            "stderr_base64": base64.b64encode(owned.stderr).decode("ascii"),
            "physical_authority": False,
            "replay_allowed": False,
        }
    )
    if owned.status == "SUCCEEDED" and owned.parsed_result is not None:
        original = codec.validate_result(
            owned.parsed_result,
            payload=payload,
            request_sha256=owned.request_sha256,
            attempt_id=operation_id,
        )
        result = deepcopy(owned.parsed_result["completion"])
    else:
        original = diagnostic
        result = {
            "schema": "rocell.wizard_worker_result.v1",
            "action_id": ACTION,
            "status": (
                owned.status if owned.status in {"CANCELLED", "TIMED_OUT"} else "FAILED"
            ),
            "steps": [
                {
                    "name": "powered_feedback_process",
                    "exit_code": 1,
                    "report": {
                        "status": "NO_ACCEPTED_FEEDBACK_RESULT",
                        "origin": "SYNTHETIC_REHEARSAL",
                        "original_sha256": hashlib.sha256(original).hexdigest(),
                        "physical_authority": False,
                    },
                }
            ],
            "device_open_count": 0,
            "serial_write_count": 0,
            "power_event_count": 0,
            "motion_command_count": 0,
            "contact_command_count": 0,
            "metadata_inventory_performed": False,
            "physical_authority": False,
        }
    report = result["steps"][0]["report"]
    report.update(
        process_status=owned.status,
        process_created=owned.process_created,
        process_tree_exit_confirmed=owned.tree_exit_confirmed,
        process_diagnostic_sha256=hashlib.sha256(diagnostic).hexdigest(),
    )
    # Keep in-memory diagnostics for the service even if durable outcome saving fails.
    try:
        publish_bytes(
            directory,
            "process-outcome.json",
            diagnostic,
            mode=PublicationMode.IMMUTABLE,
            maximum_bytes=1024 * 1024,
        )
        report["process_outcome_saved"] = True
    except Exception as error:
        result["status"] = "FAILED"
        report.update(
            process_outcome_saved=False, persistence_error_type=type(error).__name__
        )
    return result, original, diagnostic
