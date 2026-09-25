"""One-use owned arm process; only the exact non-purging memory child can run.

Process creation is real. Serial calls execute the actual worker and backend
against the sealed incapable API in that child. The physical public composition
remains unconditionally held. The callback revalidates an already-consumed scope;
it must never redeem a second permit or substitute a Boolean release flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import threading
import time
from types import MappingProxyType
from typing import Any, Callable, TYPE_CHECKING

from . import owned_worker_process as shared_process
from .arm_feedback_worker import ArmFeedbackCampaignRequest
from .arm_owned_protocol import (
    ArmOwnedRequest,
    ArmOwnedReady,
    INCAPABLE_PROVENANCE,
    REQUEST_SCHEMA,
    LEGACY_REQUEST_SCHEMA,
    PREVIOUS_REQUEST_SCHEMA,
    RESULT_SCHEMA,
    LEGACY_RESULT_SCHEMA,
    ADMISSION_TIMEOUT_MS,
    CLEANUP_TIMEOUT_MS,
    MAX_HANDSHAKE_BYTES,
    build_arm_owned_request,
    parse_arm_owned_ready,
    arm_owned_release,
    parse_arm_owned_result,
)
from .owned_arm_feedback_package import (
    OwnedArmRuntime,
    SCHEMA as RUNTIME_SCHEMA,
    LEGACY_SCHEMA as LEGACY_RUNTIME_SCHEMA,
    canonical,
    digest,
    require,
    revalidate_owned_arm_runtime,
    _path,
    _plain,
)
from .owned_worker_process import (
    WorkerProcessBudget,
    WorkerProcessRegistration,
    OwnedWorkerResult,
    owned_registration_document,
    decode_owned_json,
)

if TYPE_CHECKING:
    from .arm_owned_evidence import ArmOwnedEvidence

LEGACY_PREPARATION_SCHEMA = "rocell.prepared_owned_arm_feedback.v1"
PREPARATION_SCHEMA = "rocell.prepared_owned_arm_feedback.v2"
# Values are (runtime, preparation, result); immutable historical domains never
# inherit a future package roster or an executable result schema.
ARM_PREPARATION_VERSIONS = MappingProxyType(
    {
        LEGACY_REQUEST_SCHEMA: (
            LEGACY_RUNTIME_SCHEMA,
            LEGACY_PREPARATION_SCHEMA,
            LEGACY_RESULT_SCHEMA,
        ),
        PREVIOUS_REQUEST_SCHEMA: (
            LEGACY_RUNTIME_SCHEMA,
            LEGACY_PREPARATION_SCHEMA,
            LEGACY_RESULT_SCHEMA,
        ),
        REQUEST_SCHEMA: (RUNTIME_SCHEMA, PREPARATION_SCHEMA, RESULT_SCHEMA),
    }
)
PROCESS_BUDGET = WorkerProcessBudget(
    run_timeout_ms=20_000,
    cleanup_timeout_ms=2000,
    stdin_bytes=64 * 1024,
    stdout_bytes=64 * 1024,
    stderr_bytes=8 * 1024,
    process_count=1,
)


def _registration(
    runtime: OwnedArmRuntime, cwd: Path, *, request_schema: str = REQUEST_SCHEMA
) -> WorkerProcessRegistration:
    _path(str(cwd))
    require(
        type(request_schema) is str and request_schema in ARM_PREPARATION_VERSIONS,
        "ARM_REQUEST_VERSION_HELD",
    )
    runtime_schema, _, result_schema = ARM_PREPARATION_VERSIONS[request_schema]
    require(
        runtime.to_dict()["schema"] == runtime_schema, "ARM_RUNTIME_VERSION_MISMATCH"
    )
    return WorkerProcessRegistration(
        worker_id="incapable-owned-nonpurging-arm",
        executable=runtime.executable,
        argv=(
            "-I",
            "-S",
            str(runtime.child.path),
            "--incapable-arm",
            str(runtime.package.path),
            "--package-sha256",
            runtime.package.sha256,
            "--guarded",
        ),
        package_files=(runtime.child, runtime.package),
        working_directory=cwd,
        budget=PROCESS_BUDGET,
        composition="INCAPABLE_PROCESS_FIXTURE",
        request_schema=request_schema,
        result_schema=result_schema,
    )


@dataclass(frozen=True, slots=True)
class PreparedOwnedArmFeedback:
    """Pure exact runtime/request/registration join, not an execution permit."""

    payload: bytes

    def __post_init__(self) -> None:
        doc = decode_owned_json(self.payload, maximum=96 * 1024)
        require(
            canonical(doc) == self.payload
            and set(doc) == {"schema", "runtime", "request", "registration"}
            and doc["schema"] in (LEGACY_PREPARATION_SCHEMA, PREPARATION_SCHEMA),
            "ARM_PREPARATION_SCHEMA",
        )
        runtime = OwnedArmRuntime(canonical(doc["runtime"]))
        request = ArmOwnedRequest(canonical(doc["request"]))
        request_schema = request.to_dict()["schema"]
        require(
            doc["schema"] == ARM_PREPARATION_VERSIONS[request_schema][1],
            "ARM_PREPARATION_VERSION_MISMATCH",
        )
        require(
            type(doc["registration"]) is dict
            and type(doc["registration"].get("working_directory")) is str,
            "ARM_REGISTRATION_SCHEMA",
        )
        reg = _registration(
            runtime,
            Path(doc["registration"]["working_directory"]),
            request_schema=request_schema,
        )
        require(
            owned_registration_document(reg) == doc["registration"],
            "ARM_REGISTRATION_MISMATCH",
        )
        require(
            request.to_dict()["worker_registration_sha256"]
            == digest(doc["registration"])
            and request.to_dict()["source_sha256"]
            == runtime.to_dict()["workspace_source_sha256"]
            and request.to_dict()["provenance"] == INCAPABLE_PROVENANCE,
            "ARM_RUNTIME_REQUEST_MISMATCH",
        )

    def to_dict(self) -> dict[str, Any]:
        return decode_owned_json(self.payload, maximum=96 * 1024)

    @property
    def runtime(self) -> OwnedArmRuntime:
        return OwnedArmRuntime(canonical(self.to_dict()["runtime"]))

    @property
    def request(self) -> ArmOwnedRequest:
        return ArmOwnedRequest(canonical(self.to_dict()["request"]))

    @property
    def registration(self) -> WorkerProcessRegistration:
        return _registration(
            self.runtime,
            Path(self.to_dict()["registration"]["working_directory"]),
            request_schema=self.request.to_dict()["schema"],
        )


def prepare_owned_arm_feedback(
    runtime: OwnedArmRuntime,
    inner_request: ArmFeedbackCampaignRequest,
    *,
    session_id: str,
    permit_sha256: str,
    selected_identity_sha256: str,
    working_directory: Path,
    scenario: str = "nominal",
    deadline_ns: int | None = None,
) -> PreparedOwnedArmFeedback:
    """Inert and repeatable; no source reads, package builds, mkdir or dispatch."""
    return reconstruct_owned_arm_feedback(
        runtime,
        inner_request,
        request_schema=REQUEST_SCHEMA,
        session_id=session_id,
        permit_sha256=permit_sha256,
        selected_identity_sha256=selected_identity_sha256,
        working_directory=working_directory,
        scenario=scenario,
        deadline_ns=deadline_ns,
    )


def reconstruct_owned_arm_feedback(
    runtime: OwnedArmRuntime,
    inner_request: ArmFeedbackCampaignRequest,
    *,
    request_schema: str,
    session_id: str,
    permit_sha256: str,
    selected_identity_sha256: str,
    working_directory: Path,
    scenario: str = "nominal",
    deadline_ns: int | None = None,
) -> PreparedOwnedArmFeedback:
    """Pure historical reconstruction, never runtime qualification or dispatch.

    Only the exact version tuple is accepted. Both runners independently refuse
    historical tuples before callbacks, locks, file reads or process creation.
    """
    require(
        type(runtime) is OwnedArmRuntime
        and type(inner_request) is ArmFeedbackCampaignRequest,
        "EXACT_ARM_PREPARATION_REQUIRED",
    )
    runtime = OwnedArmRuntime(runtime.payload)
    registration = _registration(
        runtime, working_directory, request_schema=request_schema
    )
    request = build_arm_owned_request(
        session_id=session_id,
        attempt_id=inner_request.campaign_id,
        source_sha256=inner_request.source_sha256,
        operation_sha256=inner_request.operation_sha256,
        permit_sha256=permit_sha256,
        selected_identity_sha256=selected_identity_sha256,
        worker_registration_sha256=digest(owned_registration_document(registration)),
        feedback_request=inner_request,
        provenance=INCAPABLE_PROVENANCE,
        scenario=scenario,
        parent_deadline_monotonic_ns=(
            inner_request.expires_monotonic_ns if deadline_ns is None else deadline_ns
        ),
    )
    if request_schema != REQUEST_SCHEMA:
        historical = request.to_dict()
        historical["schema"] = request_schema
        historical["admission_timeout_ms"] = (
            2000 if request_schema == LEGACY_REQUEST_SCHEMA else 5000
        )
        historical["request_sha256"] = digest(
            {key: value for key, value in historical.items() if key != "request_sha256"}
        )
        request = ArmOwnedRequest(canonical(historical))
    return PreparedOwnedArmFeedback(
        canonical(
            {
                "schema": ARM_PREPARATION_VERSIONS[request_schema][1],
                "runtime": runtime.to_dict(),
                "request": request.to_dict(),
                "registration": owned_registration_document(registration),
            }
        )
    )


def _new_owner() -> Any:
    from ._owned_worker_win32 import WindowsOwnedProcess

    return WindowsOwnedProcess()


def _empty_directory(path: Path) -> None:
    _plain(path, directory=True)
    with os.scandir(path) as entries:
        require(next(entries, None) is None, "WORKING_DIRECTORY_NOT_EMPTY")


def _label(error: BaseException) -> str:
    text = str(error)
    if isinstance(error, OSError) and error.args:
        text = str(error.args[-1])
    return (
        text
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_:-]{0,127}", text)
        else type(error).__name__
    )


class _Runner:
    def __init__(
        self,
        prepared: PreparedOwnedArmFeedback,
        callback: Callable[[PreparedOwnedArmFeedback], None],
        *,
        incapable: bool,
    ) -> None:
        require(
            type(prepared) is PreparedOwnedArmFeedback and callable(callback),
            "EXACT_ARM_RUNNER_INPUT_REQUIRED",
        )
        PreparedOwnedArmFeedback(prepared.payload)
        require(
            prepared.to_dict()["schema"] == PREPARATION_SCHEMA
            and prepared.request.to_dict()["schema"] == REQUEST_SCHEMA
            and prepared.runtime.to_dict()["schema"] == RUNTIME_SCHEMA,
            "ARM_PREPARATION_VERSION_HELD",
        )
        self._original, self._payload, self._callback = (
            prepared,
            prepared.payload,
            callback,
        )
        self._incapable, self._used, self._lock = incapable, False, threading.Lock()
        self.owned_result: OwnedWorkerResult | None = None

    def status(self) -> dict[str, Any]:
        return {
            "consumed": self._used,
            "physical_authority": False,
            "physical_dispatch_enabled": False,
            "incapable_composition": self._incapable,
            "process_cleanup_hold": shared_process._UNRESOLVED_BACKEND is not None,
            "final_power_state": "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
            "retries": 0,
        }

    def run(
        self, *, cancellation: threading.Event, deadline_ns: int
    ) -> ArmOwnedEvidence:
        from .arm_owned_evidence import retain_arm_owned_evidence

        with self._lock:
            require(not self._used, "ARM_RUNNER_ALREADY_CONSUMED")
            self._used = True
        prepared = PreparedOwnedArmFeedback(self._payload)
        request, registration = prepared.request, prepared.registration
        started = time.monotonic_ns()
        native = None
        ready: ArmOwnedReady | None = None
        release_wire: bytes | None = None
        raw_result = None
        primary: str | None = None
        cleanup: tuple[str, ...] = ()
        owns_dispatch = False
        observed: dict[str, Any] = {}
        run_deadline = deadline_ns

        def live() -> None:
            require(not cancellation.is_set(), "CANCELLED")
            require(time.monotonic_ns() < run_deadline, "TIMED_OUT")
            require(
                self._original.payload == self._payload
                and prepared.payload == self._payload,
                "ARM_PREPARATION_CHANGED",
            )
            require(
                owned_registration_document(registration)
                == prepared.to_dict()["registration"],
                "ARM_REGISTRATION_CHANGED",
            )

        def authority() -> None:
            live()
            require(
                self._callback(prepared) is None, "INVALID_CONSUMED_AUTHORIZATION_ACK"
            )
            live()
            require(
                time.monotonic_ns()
                + (request.feedback_request.budget.duration_ms + CLEANUP_TIMEOUT_MS)
                * 1_000_000
                <= deadline_ns,
                "ARM_FULL_LIFETIME_EXPIRED",
            )

        try:
            require(
                type(cancellation) is threading.Event
                and type(deadline_ns) is int
                and 0 < deadline_ns < 2**63,
                "ARM_ORIGINAL_DEADLINE_REQUIRED",
            )
            require(
                deadline_ns == request.to_dict()["parent_deadline_monotonic_ns"],
                "ARM_PARENT_DEADLINE_MISMATCH",
            )
            live()
            # No callback result, origin flag or runtime descriptor opens this.
            require(self._incapable, "ARM_NONPURGING_PHYSICAL_ACTIVATION_HELD")
            # Shared private reservation spans every owned worker implementation
            # through cleanup. A retained pending owner is never replaced/freed.
            owns_dispatch = shared_process._DISPATCH_LOCK.acquire(blocking=False)
            require(owns_dispatch, "OWNED_PROCESS_ALREADY_RUNNING")
            require(shared_process._UNRESOLVED_BACKEND is None, "PROCESS_CLEANUP_HOLD")
            revalidate_owned_arm_runtime(prepared.runtime)
            _empty_directory(registration.working_directory)
            live()
            native = _new_owner()
            native.pin(registration)
            revalidate_owned_arm_runtime(prepared.runtime)
            _empty_directory(registration.working_directory)
            authority()
            run_deadline = min(
                deadline_ns - CLEANUP_TIMEOUT_MS * 1_000_000,
                time.monotonic_ns() + registration.budget.run_timeout_ms * 1_000_000,
            )
            live()
            ready_deadline = time.monotonic_ns() + ADMISSION_TIMEOUT_MS * 1_000_000

            def start_check() -> None:
                live()
                _empty_directory(registration.working_directory)
                live()

            native.start(
                registration, request.wire(), check=start_check, keep_stdin_open=True
            )
            while ready is None:
                live()
                ended = native.poll(registration.budget)
                live()
                require(time.monotonic_ns() < ready_deadline, "ARM_READY_TIMED_OUT")
                if b"\n" in native.stdout and not native.pending:
                    first, extra = native.stdout.split(b"\n", 1)
                    require(not extra, "OUTPUT_BEFORE_ARM_RELEASE")
                    ready = parse_arm_owned_ready(
                        first + b"\n",
                        expected_request_sha256=request.request_sha256,
                        expected_child_pid=native.pid,
                    )
                    break
                require(len(native.stdout) <= MAX_HANDSHAKE_BYTES, "ARM_READY_LIMIT")
                require(not ended, "ARM_CHILD_EXIT_BEFORE_READY")
                cancellation.wait(0.005)
            release_wire = arm_owned_release(request, ready)
            release_deadline = time.monotonic_ns() + ADMISSION_TIMEOUT_MS * 1_000_000

            def release_check() -> None:
                # This runs directly at the second owned WriteFile boundary.
                authority()
                require(time.monotonic_ns() < release_deadline, "ARM_RELEASE_TIMED_OUT")

            native.send_final_input(release_wire, check=release_check)
            while True:
                live()
                ended = native.poll(registration.budget)
                live()
                if ended:
                    break
                cancellation.wait(0.005)
            require(native.stdout.startswith(ready.wire()), "ARM_READY_PREFIX_CHANGED")
            parsed = parse_arm_owned_result(
                native.stdout[len(ready.wire()) :],
                expected_request=request,
                returncode=native.returncode,
            )
            raw_result = parsed.to_dict()
            live()
        except BaseException as error:
            primary = _label(error)

        def snapshot() -> None:
            if native is None:
                return
            for name, default in (
                ("created", False),
                ("resumed", False),
                ("tree_exited", False),
                ("returncode", None),
                ("written", 0),
                ("peak_handles", 0),
                ("peak_processes", 0),
                ("stdout", b""),
                ("stderr", b""),
                ("pending", False),
            ):
                try:
                    value = getattr(native, name)
                    if (
                        (value is None or type(value) is int)
                        if name == "returncode"
                        else type(value) is type(default)
                    ):
                        observed[name] = value
                except BaseException:
                    pass
                observed.setdefault(name, default)
            for name in ("handles", "unclosed_handles", "pins"):
                try:
                    observed[name + "_remaining"] = len(getattr(native, name))
                except BaseException:
                    observed[name + "_remaining"] = 1

        snapshot()
        try:
            if native is not None:
                cleanup_deadline = (
                    time.monotonic_ns()
                    + registration.budget.cleanup_timeout_ms * 1_000_000
                )
                if type(deadline_ns) is int and deadline_ns > 0:
                    cleanup_deadline = min(cleanup_deadline, deadline_ns)
                try:
                    cleanup = native.cleanup(cleanup_deadline)
                    if (
                        type(cleanup) is not tuple
                        or len(cleanup) > 128
                        or any(
                            type(code) is not str
                            or re.fullmatch(r"[A-Za-z0-9_:-]{1,128}", code) is None
                            for code in cleanup
                        )
                    ):
                        cleanup = ("INVALID_CLEANUP_RECEIPT",)
                except BaseException as error:
                    cleanup = ("CLEANUP_EXCEPTION:" + type(error).__name__,)
                if time.monotonic_ns() > cleanup_deadline:
                    cleanup = (*cleanup, "CLEANUP_DEADLINE_EXCEEDED")
                snapshot()
                if observed.get("pending") or any(
                    observed.get(name + "_remaining", 1)
                    for name in ("handles", "unclosed_handles", "pins")
                ):
                    cleanup = (*cleanup, "PROCESS_RESOURCES_RETAINED")
                if observed.get("created") and not observed.get("tree_exited"):
                    cleanup = (*cleanup, "PROCESS_TREE_EXIT_UNCONFIRMED")
                if cleanup:
                    require(
                        shared_process._UNRESOLVED_BACKEND is None,
                        "UNRESOLVED_OWNER_ALREADY_RETAINED",
                    )
                    shared_process._UNRESOLVED_BACKEND = native
            if primary is None:
                if cancellation.is_set():
                    primary = "CANCELLED"
                elif time.monotonic_ns() >= deadline_ns:
                    primary = "TIMED_OUT"
            status = "SUCCEEDED" if primary is None and not cleanup else "FAILED"
            if primary in {"CANCELLED", "TIMED_OUT"}:
                status = primary
            self.owned_result = OwnedWorkerResult(
                status=status,
                primary_error=primary,
                cleanup_errors=tuple(dict.fromkeys(cleanup)),
                request_sha256=request.request_sha256,
                attempt_id=request.to_dict()["attempt_id"],
                process_created=observed.get("created", False),
                initial_thread_resumed=observed.get("resumed", False),
                tree_exit_confirmed=observed.get("tree_exited", False),
                returncode=observed.get("returncode"),
                elapsed_ns=max(0, time.monotonic_ns() - started),
                stdin_bytes_written=observed.get("written", 0),
                peak_observed_handles=observed.get("peak_handles", 0),
                peak_active_processes=observed.get("peak_processes", 0),
                stdout=observed.get("stdout", b""),
                stderr=observed.get("stderr", b""),
                parsed_result=raw_result,
            )
            return retain_arm_owned_evidence(
                request=request,
                process_result=self.owned_result,
                ready=ready,
                release_wire=release_wire,
            )
        finally:
            if owns_dispatch:
                shared_process._DISPATCH_LOCK.release()


class OwnedArmFeedbackRunner(_Runner):
    """Physical composition held before all file, callback and process effects."""

    def __init__(
        self,
        prepared: PreparedOwnedArmFeedback,
        *,
        revalidate_consumed_permit: Callable[[PreparedOwnedArmFeedback], None],
    ) -> None:
        super().__init__(prepared, revalidate_consumed_permit, incapable=False)


class IncapableOwnedArmFeedbackRunner(_Runner):
    """Exact pinned child; no alternate executable, serial API or physical flag."""

    def __init__(
        self,
        prepared: PreparedOwnedArmFeedback,
        *,
        revalidate_consumed_permit: Callable[[PreparedOwnedArmFeedback], None],
    ) -> None:
        super().__init__(prepared, revalidate_consumed_permit, incapable=True)
