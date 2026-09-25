"""Finite owned-process lifecycle for the v2 camera protocol.

This is an internal transport component, not a runtime reviewer or permission
issuer. The application must enter it only through a reviewed runtime and an
already-consumed, still-current commissioning scope. Existing application and
legacy runner holds are unchanged; no UI action calls this component yet.

The production entry uses only the exact preparation's registration. The private
core also serves contained-process tests; its actual registration is retained,
and a different test registration cannot become a physical run-evidence record.
"""

from dataclasses import dataclass
import re
import threading
import time
from typing import Any, Callable

from . import owned_worker_process as shared
from .native_camera_activation_evidence import (
    OwnedNativeCameraActivationRunEvidence,
    retain_activation_run,
)
from .native_camera_activation_observations import (
    ActivationOwnerObservation,
    capture_activation_owner,
    _wire,
)
from .native_camera_activation_registration import PreparedOwnedNativeActivation
from .native_camera_parent_admission import NativeCameraParentHandshake
from .native_camera_protocol import canonical, digest, MAX_HANDSHAKE_BYTES, _require
from .owned_native_camera_runner import _label as _legacy_label
from .owned_worker_process import (
    WorkerProcessRegistration,
    decode_owned_json,
    owned_registration_document,
)

_CODE = re.compile(r"[A-Za-z0-9_:-]{1,128}\Z")
MAX_SUPERVISION_BYTES = 1024 * 1024
SUPERVISION_SCHEMA = "rocell.native_camera_activation_supervision.v1"


def _label(error: BaseException) -> str:
    label = _legacy_label(error)
    return label if _CODE.fullmatch(label) else "UNCLASSIFIED_ERROR"


def _new_owner() -> Any:
    # Lazy construction: importing/status/preparation do not load Win32.
    from ._owned_worker_win32 import WindowsOwnedCameraActivationPipeProcess

    return WindowsOwnedCameraActivationPipeProcess()


@dataclass(frozen=True, slots=True)
class ActivationSupervision:
    """Immutable in-memory outcome, including observations needed after failure.

    Retain diagnostics together with the derived v2 record in the future original
    campaign join. The pre-cleanup observation is deliberately separate: a later
    failed property read must not erase the earlier bytes, or make them appear
    to be a successful post-cleanup observation.
    """

    preparation_sha256: str
    actual_registration: bytes
    before_cleanup: ActivationOwnerObservation | None
    after_cleanup: ActivationOwnerObservation | None
    owner_constructed: bool
    started_ns: int | None
    finished_ns: int | None
    parent_deadline_ns: int | None
    primary_error: str | None
    cleanup: bytes
    supervisor_errors: tuple[str, ...]
    ready_wire: bytes
    release_wire: bytes
    release_check_passed: bool
    accepted_result_sha256: str | None
    unresolved_owner_retained: bool

    def run_evidence(
        self, prepared: PreparedOwnedNativeActivation
    ) -> OwnedNativeCameraActivationRunEvidence:
        """Do not relabel a different executed registration as this preparation."""
        _require(
            type(prepared) is PreparedOwnedNativeActivation,
            "EXACT_PREPARATION_REQUIRED",
        )
        prepared = PreparedOwnedNativeActivation(prepared.payload)
        _require(
            self.preparation_sha256 == prepared.preparation_sha256
            and self.actual_registration
            == canonical(owned_registration_document(prepared.registration)),
            "EXECUTED_ACTIVATION_REGISTRATION_MISMATCH",
        )
        return retain_activation_run(
            prepared=prepared,
            owner_constructed=self.owner_constructed,
            owner_observation=self.after_cleanup,
            started_ns=self.started_ns,
            finished_ns=self.finished_ns,
            parent_deadline_ns=self.parent_deadline_ns,
            primary_error=self.primary_error,
            cleanup=decode_owned_json(self.cleanup, maximum=40 * 1024),
            ready_wire=self.ready_wire,
            release_wire=self.release_wire,
            release_check_passed=self.release_check_passed,
            accepted_result_sha256=self.accepted_result_sha256,
        )

    def diagnostics(self) -> dict[str, Any]:
        """Private bounded diagnostic detail, NOT an ordinary public UI summary.

        Contains registration paths and exact pipe bytes. The existing export
        privacy policy must apply at the future campaign/UI integration boundary.
        No stored status or final-power assertion can grant execution authority.
        """
        result = dict(
            schema=SUPERVISION_SCHEMA,
            preparation_sha256=self.preparation_sha256,
            actual_registration=decode_owned_json(
                self.actual_registration, maximum=48 * 1024
            ),
            before_cleanup=(
                None if self.before_cleanup is None else self.before_cleanup.to_dict()
            ),
            after_cleanup=(
                None if self.after_cleanup is None else self.after_cleanup.to_dict()
            ),
            owner_constructed=self.owner_constructed,
            started_ns=self.started_ns,
            finished_ns=self.finished_ns,
            parent_deadline_ns=self.parent_deadline_ns,
            primary_error=self.primary_error,
            cleanup=decode_owned_json(self.cleanup, maximum=40 * 1024),
            supervisor_errors=list(self.supervisor_errors),
            ready_wire=_wire(self.ready_wire, MAX_HANDSHAKE_BYTES),
            release_wire=_wire(self.release_wire, MAX_HANDSHAKE_BYTES),
            release_check_passed=self.release_check_passed,
            accepted_result_sha256=self.accepted_result_sha256,
            unresolved_owner_retained=self.unresolved_owner_retained,
            physical_authority=False,
            hardware_qualified=False,
        )
        _require(
            len(canonical(result)) <= MAX_SUPERVISION_BYTES, "SUPERVISION_BYTE_LIMIT"
        )
        return result


def _supervise(
    prepared: PreparedOwnedNativeActivation,
    registration: WorkerProcessRegistration,
    *,
    revalidate_consumed_permit: Callable[..., None],
    cancellation: threading.Event,
    deadline_ns: int,
    _clock: Callable[[], int] = time.monotonic_ns,
) -> ActivationSupervision:
    """Shared internal lifecycle; registration overrides are not a public option.

    No retries, directory creation, runtime installation or device enumeration.
    This function owns the shared process reservation until cleanup observations
    are retained, including when cancellation/validation raises BaseException.
    """
    _require(
        type(prepared) is PreparedOwnedNativeActivation, "EXACT_PREPARATION_REQUIRED"
    )
    checked = PreparedOwnedNativeActivation(prepared.payload)
    _require(
        type(registration) is WorkerProcessRegistration, "EXACT_REGISTRATION_REQUIRED"
    )
    registration.__post_init__()
    expected_registration = checked.registration
    # Own the original limits separately from the registration handed to the
    # process owner. Detected input drift must not change cleanup's deadline.
    budget = expected_registration.budget
    _require(
        registration.budget == budget
        and registration.working_directory == expected_registration.working_directory
        and registration.request_schema == expected_registration.request_schema
        and registration.result_schema == expected_registration.result_schema,
        "ACTIVATION_TRANSPORT_CONTRACT_MISMATCH",
    )
    _require(callable(revalidate_consumed_permit), "CURRENT_PERMIT_CHECK_REQUIRED")
    sealed = canonical(owned_registration_document(registration))
    primary = None
    owner = None
    before = after = None
    owns_dispatch = retained = released = clean = False
    ready_wire = release_wire = b""
    accepted = None
    last_now = -1
    started = finished = None
    errors: list[str] = []
    parent_deadline = (
        deadline_ns if type(deadline_ns) is int and 0 < deadline_ns < 2**63 else None
    )
    run_deadline = parent_deadline
    cleanup: dict[str, Any] = dict(
        attempted=False, returned=False, deadline_ns=None, finished_ns=None, errors=None
    )

    def now() -> int:
        nonlocal last_now
        tick = _clock()
        _require(
            type(tick) is int and 0 <= tick and last_now <= tick < 2**63,
            "INVALID_MONOTONIC_CLOCK",
        )
        last_now = tick
        return tick

    def observe_time(boundary: str) -> int | None:
        try:
            return now()
        except BaseException as error:
            errors.append(boundary + ":" + _label(error))
            return None

    def snapshot(boundary: str) -> ActivationOwnerObservation | None:
        if owner is None:
            return None
        try:
            return capture_activation_owner(owner, budget)
        except BaseException as error:
            errors.append(boundary + ":" + _label(error))
            return None

    def live() -> None:
        _require(not cancellation.is_set(), "CANCELLED")
        _require(run_deadline is not None and now() < run_deadline, "TIMED_OUT")
        _require(prepared.payload == checked.payload, "PREPARATION_CHANGED")
        _require(
            canonical(owned_registration_document(registration)) == sealed,
            "PROCESS_REGISTRATION_CHANGED",
        )

    try:
        try:
            started = now()
            _require(isinstance(cancellation, threading.Event), "CANCELLATION_REQUIRED")
            _require(parent_deadline is not None, "INVALID_PARENT_DEADLINE")
            live()
            owns_dispatch = shared._DISPATCH_LOCK.acquire(blocking=False)
            _require(owns_dispatch, "OWNED_PROCESS_ALREADY_RUNNING")
            _require(shared._UNRESOLVED_BACKEND is None, "PROCESS_CLEANUP_HOLD")
            assert parent_deadline is not None
            _require(
                now() + checked.required_lifetime_ns <= parent_deadline,
                "FULL_LIFETIME_DOES_NOT_FIT",
            )
            owner = _new_owner()
            owner.pin(registration)
            live()
            parent = NativeCameraParentHandshake(
                checked,
                cancellation=cancellation,
                revalidate_consumed_permit=revalidate_consumed_permit,
                _clock=now,
            )
            run_deadline = min(
                parent_deadline, now() + budget.run_timeout_ms * 1_000_000
            )
            request = parent.begin(deadline_ns=parent_deadline)

            def start_check() -> None:
                live()
                parent.check_start_boundary()
                live()

            owner.start(registration, request, check=start_check, keep_stdin_open=True)
            while not ready_wire:
                start_check()
                ended = owner.poll(budget)
                start_check()
                output = owner.stdout
                _require(
                    type(output) is bytes and len(output) <= budget.stdout_bytes,
                    "STDOUT_LIMIT",
                )
                if b"\n" in output and owner.pending is False:
                    first, extra = output.split(b"\n", 1)
                    _require(not extra, "OUTPUT_BEFORE_RELEASE")
                    _require(len(first) + 1 <= MAX_HANDSHAKE_BYTES, "READY_BYTE_LIMIT")
                    ready_wire = first + b"\n"
                    release_wire = parent.accept_ready(
                        ready_wire, owned_child_pid=owner.pid
                    )
                    break
                _require(len(output) < MAX_HANDSHAKE_BYTES, "READY_BYTE_LIMIT")
                _require(ended is False, "CHILD_EXIT_BEFORE_READY")
                cancellation.wait(0.005)

            def release_check() -> None:
                nonlocal released
                live()
                parent.check_release()
                live()
                released = True

            owner.send_final_input(release_wire, check=release_check)
            while True:
                live()
                ended = owner.poll(budget)
                live()
                _require(type(ended) is bool, "INVALID_PROCESS_POLL_RESULT")
                if ended:
                    break
                cancellation.wait(0.005)
            _require(owner.stdout.startswith(ready_wire), "READY_PREFIX_CHANGED")
            result_wire = owner.stdout[len(ready_wire) :]
            _, receipt = parent.accept_result(result_wire, returncode=owner.returncode)
            accepted = digest(result_wire)
            if receipt.status != "OK":
                primary = "NATIVE_DIAGNOSTIC_FAILED"
            live()
        except BaseException as error:
            primary = _label(error)

        before = snapshot("BEFORE_CLEANUP")
        if owner is not None:
            cleanup_now = observe_time("CLEANUP_START_CLOCK")
            # If the clock fails, use the LAST OBSERVED tick as a no-wait
            # cleanup boundary, not an invented current time or a fresh TTL.
            cleanup_deadline = (
                cleanup_now + budget.cleanup_timeout_ms * 1_000_000
                if cleanup_now is not None
                else max(0, last_now)
            )
            if parent_deadline is not None:
                cleanup_deadline = min(cleanup_deadline, parent_deadline)
            cleanup.update(attempted=True, deadline_ns=cleanup_deadline)
            try:
                result = owner.cleanup(cleanup_deadline)
                valid = (
                    type(result) is tuple
                    and len(result) <= 256
                    and all(
                        type(code) is str and bool(_CODE.fullmatch(code))
                        for code in result
                    )
                )
                # A returned but malformed receipt is an explicit supervisor
                # failure; do not accept it as an empty successful error list.
                cleanup.update(
                    returned=True,
                    errors=(
                        list(dict.fromkeys(result))
                        if valid
                        else ["INVALID_CLEANUP_RECEIPT"]
                    ),
                )
            except BaseException as error:
                errors.append("CLEANUP_EXCEPTION:" + _label(error))
            cleanup["finished_ns"] = observe_time("CLEANUP_FINISH_CLOCK")
            after = snapshot("AFTER_CLEANUP")
            try:
                values = {} if after is None else after.values()
            except BaseException as error:
                # Even interruption during observation decoding must leave the
                # owner alive if resource closure cannot be established.
                errors.append("AFTER_CLEANUP_VALUES:" + _label(error))
                values = {}
            clean = bool(
                cleanup["returned"]
                and cleanup["errors"] == []
                and type(cleanup["finished_ns"]) is int
                and cleanup["finished_ns"] <= cleanup_deadline
                and not errors
                and values.get("pending") is False
                and all(
                    name in values and values[name] == 0
                    for name in (
                        "handles_remaining",
                        "unclosed_handles_remaining",
                        "pins_remaining",
                    )
                )
                and (
                    values.get("created") is False
                    or values.get("created") is True
                    and values.get("tree_exited") is True
                )
            )
            if not clean:
                # The reservation is still held; another worker cannot replace
                # this owner or free storage still referenced by pending I/O.
                _require(
                    shared._UNRESOLVED_BACKEND is None,
                    "UNRESOLVED_OWNER_ALREADY_RETAINED",
                )
                shared._UNRESOLVED_BACKEND = owner
                retained = True
        finished = observe_time("FINISH_CLOCK")
        if primary is None:
            if isinstance(cancellation, threading.Event) and cancellation.is_set():
                primary = "CANCELLED"
            elif errors:
                primary = "SUPERVISOR_OBSERVATION_FAILED"
            elif (
                finished is None
                or parent_deadline is None
                or finished >= parent_deadline
            ):
                primary = "TIMED_OUT"
        return ActivationSupervision(
            checked.preparation_sha256,
            sealed,
            before,
            after,
            owner is not None,
            started,
            finished,
            parent_deadline,
            primary,
            canonical(cleanup),
            tuple(errors),
            ready_wire,
            release_wire,
            released,
            accepted,
            retained,
        )
    finally:
        if owns_dispatch:
            try:
                if owner is not None and not clean and not retained:
                    # Last-resort protection if an unexpected exception leaves
                    # the diagnostic/retention path early. The shared reservation
                    # makes this a non-overwriting operation, just like above.
                    _require(
                        shared._UNRESOLVED_BACKEND is None,
                        "UNRESOLVED_OWNER_ALREADY_RETAINED",
                    )
                    shared._UNRESOLVED_BACKEND = owner
            finally:
                shared._DISPATCH_LOCK.release()


class ActivationProcessSupervisor:
    """One-use internal exact-preparation entry; construction/status are inert.

    The scope callback must validate the application's already-consumed permit,
    complete preparation and current original context. It does not issue or
    renew authority. No callback/backend/executable setting is exposed in the UI.
    """

    def __init__(
        self,
        prepared: PreparedOwnedNativeActivation,
        *,
        revalidate_consumed_permit: Callable[..., None],
    ) -> None:
        _require(
            type(prepared) is PreparedOwnedNativeActivation,
            "EXACT_PREPARATION_REQUIRED",
        )
        self._prepared = PreparedOwnedNativeActivation(prepared.payload)
        _require(callable(revalidate_consumed_permit), "CURRENT_PERMIT_CHECK_REQUIRED")
        self._current = revalidate_consumed_permit
        self._used = False
        self._lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        return dict(
            consumed=self._used,
            physical_authority=False,
            implicit_dispatch=False,
            process_cleanup_hold=shared._UNRESOLVED_BACKEND is not None,
            retries=0,
        )

    def run(
        self, *, cancellation: threading.Event, deadline_ns: int
    ) -> ActivationSupervision:
        with self._lock:
            _require(not self._used, "SUPERVISOR_ALREADY_CONSUMED")
            self._used = True
        return _supervise(
            self._prepared,
            self._prepared.registration,
            revalidate_consumed_permit=self._current,
            cancellation=cancellation,
            deadline_ns=deadline_ns,
        )
