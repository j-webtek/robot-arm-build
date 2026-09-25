"""Service-owned passive IPC rehearsal; never a physical admission producer.

The existing process owner pins and executes one fixed incapable child. Its
input references are explicitly synthetic except the current source and pinned
runtime. The returned diagnostic retains raw process bytes for ordinary wizard
export; it cannot satisfy original commissioning or electrical-isolation gates.
"""

import base64
import hashlib
from pathlib import Path
import sys
import time

from .arm_bench_qualification_contract import (
    PassiveBenchRequest,
    SCHEMA,
    PURPOSE,
    _LIMITS,
    _REFERENCE_NAMES,
    _canonical,
)
from rocell.providers.windows import passive_arm_process_codec as codec
from rocell.providers.windows.owned_arm_feedback_package import _read, _plain
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessBudget,
    WorkerProcessRegistration,
    OwnedWorkerRequest,
    OwnedWindowsWorker,
    owned_registration_document,
)


ACTION = "rehearse_passive_arm_connection"


def run_passive_rehearsal(
    *,
    parent_directory,
    launch_id,
    operation_id,
    source_sha256,
    scenario,
    deadline_ns,
    cancellation,
    recheck_source
):
    """Called only after the wizard's durable action intent and mode check."""
    if scenario not in codec.SCENARIOS:
        raise ValueError("Unregistered passive scenario")
    parent = Path(parent_directory)
    _plain(parent, directory=True)
    # Only the service-created opaque operation ID becomes a directory name.
    import re

    if re.fullmatch(r"operation-[0-9a-f]{32}", operation_id) is None:
        raise ValueError("Service-owned operation ID required")
    child_directory = parent / (operation_id + "-passive-child")
    child_directory.mkdir(exist_ok=False)

    def pin(path):
        return PinnedWorkerFile(
            path, hashlib.sha256(_read(path, 64 * 1024 * 1024)).hexdigest()
        )

    if scenario.startswith("lifecycle-"):
        from rocell.providers.windows.passive_arm_lifecycle_package import (
            prepare,
            CHILD,
        )

        package = pin(prepare(child_directory))
        arguments = (
            "-I",
            "-S",
            str(CHILD),
            str(package.path),
            package.sha256,
            scenario,
        )
        packages = (pin(CHILD), package)
    else:
        arguments = ("-I", "-S", str(codec.FIXTURE_PATH), scenario)
        packages = (pin(codec.FIXTURE_PATH),)
    registration = WorkerProcessRegistration(
        "incapable-passive-arm",
        pin(Path(getattr(sys, "_base_executable", sys.executable))),
        arguments,
        packages,
        child_directory,
        WorkerProcessBudget(
            run_timeout_ms=8000 if scenario.startswith("lifecycle-") else 2000,
            cleanup_timeout_ms=2000,
            stdout_bytes=128 * 1024,
            stderr_bytes=8192,
            process_count=1,
        ),
        "INCAPABLE_PROCESS_FIXTURE",
        codec.REQUEST_SCHEMA,
        codec.RESULT_SCHEMA,
    )
    refs = {
        key: hashlib.sha256(("SYNTHETIC-NOT-EVIDENCE:" + key).encode()).hexdigest()
        for key in _REFERENCE_NAMES
    }
    refs["source_sha256"] = source_sha256
    refs["runtime_sha256"] = hashlib.sha256(
        _canonical(owned_registration_document(registration))
    ).hexdigest()
    passive = PassiveBenchRequest(
        _canonical(
            dict(
                schema=SCHEMA,
                purpose=PURPOSE,
                attempt_id=operation_id,
                launch_id=launch_id,
                mode="rehearsal",
                references=refs,
                parent_deadline_monotonic_ns=deadline_ns,
                limits=dict(_LIMITS),
            )
        )
    )
    identity = hashlib.sha256(b"SYNTHETIC-PASSIVE-USB-IDENTITY").hexdigest()
    payload = dict(
        schema=codec.PAYLOAD_SCHEMA,
        scenario=scenario,
        request=passive.to_dict(),
        selected_identity_sha256=identity,
    )
    outer = OwnedWorkerRequest(
        operation_id,
        launch_id,
        source_sha256,
        passive.request_sha256,
        identity,
        deadline_ns,
        _canonical(payload),
    )

    def authorize(actual_registration, actual_request, digest):
        if actual_registration != registration or actual_request != outer:
            raise ValueError("Passive rehearsal inputs changed")
        recheck_source()
        passive.require_time_available(time.monotonic_ns())

    # The generic action log precedes package preparation; this second record
    # preserves the actual prepared request/runtime before the child can run.
    # Failure here propagates without dispatch or any automatic retry.
    from .passive_arm_diagnostic_checkpoint import publish_intent

    codec.validate_registration(registration, outer)
    recheck_source()
    intent = publish_intent(
        parent,
        launch_id,
        passive.to_dict(),
        owned_registration_document(registration),
        payload,
    )

    owned = OwnedWindowsWorker(registration, authorizer=authorize).run(
        outer,
        cancellation=cancellation,
        deadline_ns=deadline_ns,
    )
    summary = None
    if owned.parsed_result is not None:
        summary = codec.validate_result(
            owned.parsed_result,
            payload=payload,
            request_sha256=owned.request_sha256,
            attempt_id=operation_id,
        ).summary()
    report = {
        "schema": "rocell.passive_arm_rehearsal_diagnostic.v1",
        "provenance": "INCAPABLE_PROCESS_WITH_SYNTHETIC_DEVICE_OBSERVATIONS",
        "references_are_commissioning_evidence": False,
        "intent": intent,
        "registration": owned_registration_document(registration),
        "request": passive.to_dict(),
        "outer_payload": payload,
        "process": owned.to_dict(),
        "passive_summary": summary,
        "raw_stdout_base64": base64.b64encode(owned.stdout).decode("ascii"),
        "raw_stderr_base64": base64.b64encode(owned.stderr).decode("ascii"),
        "connected": False,
        "qualified": False,
        "physical_authority": False,
    }
    succeeded = (
        owned.status == "SUCCEEDED"
        and summary is not None
        and summary["status"] == "OBSERVED_CLOSED"
    )
    return {
        "schema": "rocell.wizard_worker_result.v1",
        "action_id": ACTION,
        "status": "SUCCEEDED" if succeeded else "FAILED",
        "steps": [
            {
                "name": "passive_arm_owned_rehearsal",
                "exit_code": 0 if succeeded else 1,
                "report": report,
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
