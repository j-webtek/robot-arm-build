"""Service-owned passive attempt orchestration, not a browser dispatch API.

The caller supplies its pinned setup receipt and a current-state check. This
module selects the executable itself, burns intent before dispatch and retains
raw output before returning any interpretation. Native serial remains held by
the provider; successful process execution is never commissioning acceptance.
"""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import sys
from threading import Lock
import time

from .arm_bench_qualification_contract import _canonical
from .passive_arm_attempt_store import MAX_STDOUT_BYTES, MAX_STDERR_BYTES
from .passive_arm_preparation import prepare_attempt
from .physical_onboarding_durability import safe_root, read_bounded_regular_file
from rocell.providers.windows import passive_native_package as package
from rocell.providers.windows import passive_native_registration as protocol
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessRegistration,
    WorkerProcessBudget,
    OwnedWorkerRequest,
    OwnedWorkerResult,
    OwnedWindowsWorker,
    owned_registration_document,
)


@dataclass(frozen=True, slots=True)
class PassiveCoordinatorOutcome:
    process: OwnedWorkerResult
    outcome_sha256: str | None
    persistence_error: str | None

    def wizard_publication(self):
        """Separate process completion, passive observation and qualification.

        The parsed result comes only from the owned supervisor's bound wire
        validation. A source hold is not evidence of a defective arm.
        """
        from rocell.providers.windows.nonpurging_serial_api import NATIVE_HOLD

        status, code = "FAILED", "PASSIVE_ATTEMPT_INCOMPLETE"
        message = "Passive attempt did not complete; inspect and export diagnostics. Do not replay uncertain attempts."
        observation = (
            (self.process.parsed_result or {})
            .get("child_result", {})
            .get("observation", {})
        )
        summary = observation.get("summary", {})
        primary = observation.get("lifecycle", {}).get("primary_error") or {}
        if not self.outcome_sha256 or self.persistence_error:
            code = "PASSIVE_OUTCOME_PERSISTENCE_FAILED"
            message = "Saving the attempt outcome failed. Raw logs remain in this session; export before closing."
        elif not self.process.tree_exit_confirmed and self.process.process_created:
            code = "PASSIVE_PROCESS_CLEANUP_UNKNOWN"
            message = "Child-process cleanup is unconfirmed. Do not reconnect or replay; export diagnostics."
        elif self.process.status in {"CANCELLED", "TIMED_OUT"}:
            status = self.process.status
            code = "PASSIVE_" + status
        elif self.process.status == "SUCCEEDED":
            if primary.get("code") == NATIVE_HOLD:
                code = "PASSIVE_NATIVE_RELEASE_HELD"
                message = "Software qualification still blocks native serial access. This does not indicate an arm fault."
            elif (
                summary.get("status") == "OBSERVED_CLOSED"
                and summary.get("holds") == []
            ):
                status, code = "SUCCEEDED", "PASSIVE_OBSERVATION_COMPLETED"
                message = "The bounded zero-write observation completed and reported port closure. The arm is not connected for commands; commissioning and motion remain unqualified."
        return {
            "schema": "rocell.wizard_passive_arm_result.v1",
            "action_id": "run_passive_arm_connection",
            "status": status,
            "code": code,
            "message": message,
            "steps": [
                {
                    "name": "passive_arm_attempt",
                    "exit_code": 0 if status == "SUCCEEDED" else 1,
                    "report": self.summary(),
                }
            ],
            "physical_authority": False,
        }

    def summary(self):
        # Full native metadata is nested inside the validated wire result. Keep
        # it only in the raw outcome journal/exports, not recursively inside the
        # wizard's already-nested operation envelope (which has a depth budget).
        process_view = self.process.to_dict()
        process_view.pop("parsed_result", None)
        observation = (
            (self.process.parsed_result or {})
            .get("child_result", {})
            .get("observation", {})
        )
        return dict(
            schema="rocell.wizard_passive_coordinator_result.v1",
            process=process_view,
            observation_summary=observation.get("summary"),
            outcome_sha256=self.outcome_sha256,
            persistence_error=self.persistence_error,
            status=(
                "OUTCOME_RETAINED_NOT_DEVICE_ACCEPTANCE"
                if self.outcome_sha256
                else "OUTCOME_PERSISTENCE_FAILED"
            ),
            connected=False,
            physical_authority=False,
            replay_allowed=False,
        )


def _pin(path):
    raw = read_bounded_regular_file(path, maximum_bytes=32 * 1024 * 1024)
    return PinnedWorkerFile(path, hashlib.sha256(raw).hexdigest())


def _registration(root, attempt_id):
    # Refuse pre-existing attempt directories, including links. No overwrite or
    # recursive cleanup: failed preparation stays available for diagnosis.
    directory = root / (attempt_id + "-native-child")
    directory.mkdir()
    archive = _pin(package.prepare(directory))
    return WorkerProcessRegistration(
        protocol.WORKER_ID,
        _pin(Path(getattr(sys, "_base_executable", sys.executable))),
        ("-I", "-S", str(package.CHILD), str(archive.path), archive.sha256, "observe"),
        (_pin(package.CHILD), archive),
        directory,
        WorkerProcessBudget(
            run_timeout_ms=20_000,
            cleanup_timeout_ms=2000,
            stdin_bytes=65536,
            stdout_bytes=MAX_STDOUT_BYTES,
            stderr_bytes=MAX_STDERR_BYTES,
            process_count=1,
        ),
        "PHYSICAL_UNQUALIFIED",
        protocol.REQUEST_SCHEMA,
        protocol.RESULT_SCHEMA,
    )


class PassiveArmCoordinator:
    """One coordinator per launch; even failed preparation consumes this owner.

    Recovery is inspection only. Retain the returned object in the service even
    if outcome publication fails: it still owns the complete bounded raw logs.
    ``check_current`` must raise if source, selection or setup receipt changed.
    It is checked again by the supervisor while authorizing the pinned child.
    """

    def __init__(self):
        self._lock = Lock()
        self._used = False

    def run(
        self,
        *,
        root,
        setup_operation_id,
        expected_setup_sha256,
        session_id,
        source_sha256,
        attempt_id,
        deadline_ns,
        cancellation,
        check_current,
    ):
        with self._lock:
            if self._used:
                raise ValueError("Passive coordinator already consumed")
            self._used = True
        if not callable(check_current):
            raise ValueError("Service current-state check required")
        if type(attempt_id) is not str or not re.fullmatch(
            r"operation-[a-f0-9]{32}", attempt_id
        ):
            raise ValueError("Exact service attempt required")
        check_current()
        root = safe_root(Path(root))
        reg = _registration(root, attempt_id)
        runtime = owned_registration_document(reg)
        prepared = prepare_attempt(
            root=root,
            setup_operation_id=setup_operation_id,
            expected_setup_sha256=expected_setup_sha256,
            session_id=session_id,
            source_sha256=source_sha256,
            attempt_id=attempt_id,
            registration=runtime,
            deadline_ns=deadline_ns,
            now_monotonic_ns=time.monotonic_ns(),
        )
        check_current()
        consumed = prepared.journal.consume(now_monotonic_ns=time.monotonic_ns())
        body = prepared.request.to_dict()
        handoff = dict(
            schema=protocol.PAYLOAD_SCHEMA,
            root=str(root),
            request=body,
            setup_operation_id=setup_operation_id,
            consumption_sha256=consumed["consumption_sha256"],
            registration=runtime,
        )
        outer = OwnedWorkerRequest(
            attempt_id,
            session_id,
            source_sha256,
            prepared.request.request_sha256,
            body["references"]["native_metadata_review_sha256"],
            deadline_ns,
            _canonical(handoff),
        )
        worker = OwnedWindowsWorker(reg, authorizer=lambda *args: check_current())
        process = worker.run(outer, cancellation=cancellation, deadline_ns=deadline_ns)
        # Preserve unsuccessful and malformed child output, not just JSON results.
        try:
            digest = prepared.journal.retain_outcome(
                stdout=process.stdout,
                stderr=process.stderr,
                process_status=process.status,
            )
        except Exception as error:
            return PassiveCoordinatorOutcome(process, None, type(error).__name__)
        return PassiveCoordinatorOutcome(process, digest, None)
