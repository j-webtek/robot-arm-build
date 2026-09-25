"""One-use physical USB supervisor, reachable only through exact consumed M1 scope.

There is no production enable flag, backend argument or endpoint CLI. The
separately named incapable runner has a different fixed binary/preparation.
Both reuse the same low-level atomic-Job/pipe owner without changing old camera
registration or release paths.
"""

from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import re
from threading import Event, Lock
import time
from typing import Any, Callable, cast

from rocell.application.cell_commissioning_coordinator import (
    ExactOperationPermit,
    UsbIdentityAdmissionSnapshot,
    CampaignBudget,
    CommissioningMode,
)
from rocell.application.consumed_commissioning_scope import ConsumedCommissioningScope
from rocell.application.commissioning_camera_persistence import (
    physical_camera_source_binding,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_leases import LeaseLevel
from rocell.application.usb_identity_stage_policy import usb_identity_stage_policy
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.safety.effects import EffectClass
from . import owned_worker_process as shared_process
from .owned_worker_process import owned_registration_document
from .usb_identity_protocol import (
    canonical,
    parse_usb_identity_ready,
    parse_owned_usb_identity_result,
    usb_identity_release,
)
from .usb_identity_registration import (
    Preparation,
    PreparedOwnedUsbIdentity,
    PreparedIncapableUsbIdentity,
    inspect_usb_identity_runtime,
)
from .owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
    PROCESS_DEFAULTS,
    SCHEMA,
    BOUNDARIES,
    MAX_OWNER_CLEANUP_ERRORS,
    stream_record,
    retain_owned_usb_identity_run,
)


class OwnedUsbIdentityRunnerError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise OwnedUsbIdentityRunnerError(code)


def _label(error: BaseException) -> str:
    value = getattr(error, "code", None)
    if type(value) is str and re.fullmatch(r"[A-Za-z0-9_:-]{1,128}", value):
        return value
    value = error.args[0] if error.args else None
    if type(value) is str and re.fullmatch(r"[A-Z][A-Z0-9_:-]{0,127}", value):
        return value
    return type(error).__name__


def _new_owner() -> Any:
    from ._owned_worker_win32 import WindowsOwnedUsbPipeProcess

    return WindowsOwnedUsbPipeProcess()


def _permit_matches(prepared: Preparation, permit: ExactOperationPermit) -> None:
    _need(
        type(permit) is ExactOperationPermit
        and type(permit.admission) is UsbIdentityAdmissionSnapshot,
        "EXACT_USB_DOMAIN_PERMIT",
    )
    i, q = prepared.identity.to_dict(), prepared.request.to_dict()
    a = cast(UsbIdentityAdmissionSnapshot, permit.admission)
    r = permit.registration
    _need(
        permit.request.cell_id == a.cell_id == i["cell_id"]
        and permit.request.session_id
        == a.session_id
        == i["session_id"]
        == q["session_id"]
        and permit.request.action_id == r.action_id == "physical-native-usb-identity"
        and permit.request.expected_challenge_sha256 == a.challenge_sha256
        and a.mode is CommissioningMode.PHYSICAL_DIAGNOSTIC
        and a.stage is r.stage is PhysicalOnboardingStage.CAMERA_IDENTITY
        and r.effect_class is EffectClass.BOUNDED_CAMERA_CAMPAIGN
        and r.worker_id == "scoped-physical-native-usb-identity"
        and r.resources == (LeaseLevel.CAMERA,)
        and a.source_binding_sha256
        == physical_camera_source_binding(q["source_sha256"])
        and a.selected_identity_sha256
        == prepared.identity.sha256
        == q["selected_identity_sha256"]
        and a.usb_query_policy_sha256
        == i["stage_policy_sha256"]
        == usb_identity_stage_policy().sha256
        and r.worker_executable_sha256 == q["helper_sha256"]
        and r.operation_sha256 == q["operation_sha256"]
        and permit.attempt_id == q["attempt_id"]
        and permit.permit_sha256 == q["permit_sha256"]
        and permit.envelope is None,
        "USB_PERMIT_PREPARATION_MISMATCH",
    )
    _need(
        canonical(asdict(r.budget))
        == canonical(asdict(CampaignBudget(25000, 128 * 1024, 32, 128, 0, 0, 32))),
        "EXACT_USB_CAMPAIGN_BUDGET",
    )
    _need(
        not a.quarantine_latched
        and a.unresolved_attempts == 0
        and not a.open_blocker_ids,
        "USB_ADMISSION_BLOCKED",
    )


class _Runner:
    def __init__(
        self,
        prepared: Preparation,
        *,
        permit: ExactOperationPermit,
        authorization: ConsumedCommissioningScope,
        application_guard: Callable[[], None],
    ) -> None:
        _need(
            type(authorization) is ConsumedCommissioningScope
            and callable(application_guard),
            "EXACT_USB_SCOPED_GUARD",
        )
        type(prepared)(prepared.payload)
        _permit_matches(prepared, permit)
        self._prepared, self._payload = prepared, prepared.payload
        self._permit, self._permit_bytes = permit, canonical(asdict(permit))
        self._authorization, self._guard = authorization, application_guard
        self._used = False
        self._lock = Lock()
        self._evidence: bytes | None = None
        self._unresolved_owner: Any = None

    @property
    def retained_evidence(self) -> OwnedUsbIdentityRunEvidence | None:
        return (
            None
            if self._evidence is None
            else OwnedUsbIdentityRunEvidence(self._evidence)
        )

    def run(
        self, *, cancellation: Event, deadline_ns: int
    ) -> OwnedUsbIdentityRunEvidence:
        with self._lock:
            _need(not self._used, "USB_RUNNER_ALREADY_CONSUMED")
            self._used = True
        _need(
            isinstance(cancellation, Event)
            and type(deadline_ns) is int
            and self._permit.issued_at_ns < deadline_ns <= self._permit.expires_at_ns,
            "ORIGINAL_USB_DEADLINE",
        )
        started, utc_started = time.monotonic_ns(), time.time_ns()
        _need(deadline_ns <= started + 25_000_000_000, "USB_CAMPAIGN_DURATION_BOUND")
        prepared = type(self._prepared)(self._payload)
        registration = prepared.registration
        registration_bytes = canonical(owned_registration_document(registration))
        permit, scope, guard = self._permit, self._authorization, self._guard
        owner = None
        owns_dispatch = False
        primary = None
        cleanup: tuple[str, ...] = ()
        checks: list[dict[str, Any]] = []
        ready_length = 0
        release = b""
        release_attempted = release_checked = release_delivered = False
        ready = None
        run_deadline = deadline_ns - 2_000_000_000
        admission_deadline = 0
        last_now = started
        process = dict(PROCESS_DEFAULTS)
        stdout = stderr = b""

        def now() -> int:
            nonlocal last_now
            value = time.monotonic_ns()
            _need(type(value) is int and value >= last_now, "MONOTONIC_CLOCK_REGRESSED")
            last_now = value
            return value

        def current() -> None:
            _need(not cancellation.is_set(), "CANCELLED")
            _need(now() < run_deadline, "TIMED_OUT")
            _need(
                self._prepared.payload == self._payload
                and canonical(asdict(permit)) == self._permit_bytes
                and self._guard is guard
                and self._authorization is scope
                and canonical(owned_registration_document(registration))
                == registration_bytes,
                "USB_ORIGINAL_INPUT_CHANGED",
            )
            _need(guard() is None, "USB_GUARD_CANNOT_GRANT_AUTHORITY")
            _need(not cancellation.is_set(), "CANCELLED")
            _need(now() < run_deadline, "TIMED_OUT")

        def scope_check(boundary: str) -> None:
            _need(
                len(checks) < 5 and boundary == BOUNDARIES[len(checks)],
                "USB_SCOPE_CHECK_ORDER",
            )
            current()
            row = {
                "boundary": boundary,
                "started_ns": now(),
                "finished_ns": now(),
                "passed": False,
            }
            checks.append(row)
            try:
                runtime = prepared.runtime.to_dict()
                _need(
                    source_fingerprint(Path(runtime["workspace"]))
                    == runtime["source_sha256"],
                    "CURRENT_USB_WORKSPACE_SOURCE_CHANGED",
                )
                current()
                _permit_matches(prepared, permit)
                scope.revalidate(permit)
                current()
                row["passed"] = True
            finally:
                row["finished_ns"] = now()

        def snapshot() -> None:
            nonlocal stdout, stderr, process
            if owner is None:
                return
            complete = True
            values = dict(PROCESS_DEFAULTS)
            for name, default in PROCESS_DEFAULTS.items():
                if name in {
                    "handles_remaining",
                    "unclosed_handles_remaining",
                    "pins_remaining",
                    "observation_complete",
                }:
                    continue
                try:
                    value = getattr(owner, name)
                    valid = (
                        (value is None or type(value) is int)
                        if name == "returncode"
                        else type(value) is type(default)
                    )
                    _need(valid, "USB_OWNER_OBSERVATION_TYPE")
                    values[name] = value
                except Exception:
                    complete = False
            for name in ("handles", "unclosed_handles", "pins"):
                try:
                    values[name + "_remaining"] = len(getattr(owner, name))
                except Exception:
                    values[name + "_remaining"] = 1
                    complete = False
            for name, maximum in (
                ("stdout", registration.budget.stdout_bytes),
                ("stderr", registration.budget.stderr_bytes),
            ):
                try:
                    raw = getattr(owner, name)
                    _need(
                        type(raw) is bytes and len(raw) <= maximum,
                        "USB_OWNER_STREAM_BOUND",
                    )
                    if name == "stdout":
                        stdout = raw
                    else:
                        stderr = raw
                except Exception:
                    complete = False
            values["observation_complete"] = complete
            process = values

        try:
            current()
            _need(
                now() + prepared.required_lifetime_ns <= deadline_ns,
                "FULL_USB_LIFETIME_DOES_NOT_FIT",
            )
            scope.acknowledge(permit)
            scope_check("PRE_PIN")
            owns_dispatch = shared_process._DISPATCH_LOCK.acquire(blocking=False)
            _need(owns_dispatch, "OWNED_PROCESS_ALREADY_RUNNING")
            _need(shared_process._UNRESOLVED_BACKEND is None, "PROCESS_CLEANUP_HOLD")
            owner = _new_owner()
            owner.pin(registration)
            inspect_usb_identity_runtime(
                prepared.runtime, cancellation=cancellation, deadline_ns=run_deadline
            )
            scope_check("POST_PIN")
            _need(
                now() + prepared.required_lifetime_ns <= deadline_ns,
                "FULL_USB_LIFETIME_DOES_NOT_FIT",
            )
            run_deadline = min(deadline_ns - 2_000_000_000, now() + 18_000_000_000)
            admission_deadline = now() + 5_000_000_000
            prestart = False

            def start_check() -> None:
                nonlocal prestart
                current()
                _need(now() < admission_deadline, "USB_ADMISSION_TIMED_OUT")
                if not prestart:
                    prestart = True
                    scope_check("PRE_START")
                current()
                _need(now() < admission_deadline, "USB_ADMISSION_TIMED_OUT")

            owner.start(
                registration,
                prepared.request.wire(),
                check=start_check,
                keep_stdin_open=True,
            )
            while ready is None:
                current()
                _need(now() < admission_deadline, "USB_ADMISSION_TIMED_OUT")
                ended = owner.poll(registration.budget)
                _need(
                    owner.peak_processes <= registration.budget.process_count,
                    "USB_OWNED_PROCESS_COUNT_EXCEEDED",
                )
                current()
                output = owner.stdout
                if b"\n" in output and not owner.pending:
                    wire, extra = output.split(b"\n", 1)
                    _need(not extra, "OUTPUT_BEFORE_USB_RELEASE")
                    _need(len(wire) + 1 <= 1024, "USB_READY_BYTE_LIMIT")
                    ready = parse_usb_identity_ready(
                        wire + b"\n",
                        expected_request_sha256=prepared.request.request_sha256,
                        expected_child_pid=owner.pid,
                    )
                    ready_length = len(wire) + 1
                    release = usb_identity_release(prepared.request, ready)
                    break
                _need(len(output) < 1024, "USB_READY_BYTE_LIMIT")
                _need(not ended, "USB_CHILD_EXIT_BEFORE_READY")
                cancellation.wait(0.005)

            def release_check() -> None:
                nonlocal release_checked, release_attempted
                _need(not release_checked, "USB_RELEASE_ALREADY_CHECKED")
                scope_check("PRE_RELEASE")
                current()
                moment = now()
                _need(moment < admission_deadline, "USB_ADMISSION_TIMED_OUT")
                _need(
                    moment + 10_000_000_000 < run_deadline
                    and moment + 12_000_000_000 <= deadline_ns,
                    "USB_NATIVE_LIFETIME_DOES_NOT_FIT",
                )
                release_checked = True
                release_attempted = True

            # Low-level owner calls the fresh check immediately before WriteFile.
            owner.send_final_input(release, check=release_check)
            while True:
                current()
                ended = owner.poll(registration.budget)
                _need(
                    owner.peak_processes <= registration.budget.process_count,
                    "USB_OWNED_PROCESS_COUNT_EXCEEDED",
                )
                if (
                    not owner.pending
                    and owner.written == len(prepared.request.wire()) + len(release)
                    and not owner.errors
                    and not owner.unclosed_handles
                ):
                    release_delivered = True
                current()
                if ended:
                    break
                cancellation.wait(0.005)
            _need(
                owner.stdout.startswith(ready.payload + b"\n"),
                "USB_READY_PREFIX_CHANGED",
            )
            parse_owned_usb_identity_result(
                owner.stdout[ready_length:],
                request=prepared.request,
                ready=ready,
                returncode=owner.returncode,
            )
            scope_check("POST_RESULT")
        except BaseException as error:
            primary = _label(error)
        finally:
            snapshot()
            if owner is not None:
                cleanup_deadline = min(deadline_ns, time.monotonic_ns() + 2_000_000_000)
                try:
                    cleanup = owner.cleanup(cleanup_deadline)
                    _need(
                        type(cleanup) is tuple
                        and len(cleanup) <= MAX_OWNER_CLEANUP_ERRORS
                        and all(
                            type(c) is str and re.fullmatch(r"[A-Za-z0-9_:-]{1,128}", c)
                            for c in cleanup
                        ),
                        "USB_INVALID_CLEANUP_RECEIPT",
                    )
                except OwnedUsbIdentityRunnerError as error:
                    # A rejected owner receipt is not a clean/truncated receipt.
                    # Native streams and any independently parsed effect counts
                    # remain intact; the retained process outcome is uncertain.
                    cleanup = (_label(error),)
                except BaseException as error:
                    cleanup = ("CLEANUP_EXCEPTION:" + type(error).__name__,)
                if time.monotonic_ns() > cleanup_deadline:
                    cleanup = (*cleanup, "CLEANUP_DEADLINE_EXCEEDED")
                snapshot()
                if (
                    not process["observation_complete"]
                    or process["pending"]
                    or any(
                        process[n]
                        for n in (
                            "handles_remaining",
                            "unclosed_handles_remaining",
                            "pins_remaining",
                        )
                    )
                ):
                    cleanup = (*cleanup, "PROCESS_RESOURCES_RETAINED")
                if process["created"] and not process["tree_exited"]:
                    cleanup = (*cleanup, "PROCESS_TREE_EXIT_UNCONFIRMED")
                if cleanup:
                    # Keep outstanding overlapped storage/pins alive; never replace
                    # another owner or permit a second process after uncertain cleanup.
                    if shared_process._UNRESOLVED_BACKEND is None:
                        shared_process._UNRESOLVED_BACKEND = owner
                    else:
                        # Preserve both owners if a violated internal invariant
                        # is observed; never lose this attempt's failure bytes.
                        self._unresolved_owner = owner
                        cleanup = (*cleanup, "UNRESOLVED_OWNER_ALREADY_RETAINED")
            try:
                if primary is None:
                    try:
                        current()
                    except BaseException as error:
                        primary = _label(error)
                finished = time.monotonic_ns()
                utc_finished = time.time_ns()
                if (
                    cast(int, process["peak_processes"])
                    > registration.budget.process_count
                    and primary is None
                ):
                    primary = "USB_OWNED_PROCESS_COUNT_EXCEEDED"
                if utc_finished < utc_started and primary is None:
                    primary = "UTC_CLOCK_REGRESSED"
                value = {
                    "schema": SCHEMA,
                    "preparation": prepared.to_dict(),
                    "preparation_sha256": prepared.sha256,
                    "provenance": (
                        "INCAPABLE_USB_QUERY"
                        if type(prepared) is PreparedIncapableUsbIdentity
                        else "PHYSICAL_USB_QUERY"
                    ),
                    "original_deadline_ns": deadline_ns,
                    "started_monotonic_ns": started,
                    "finished_monotonic_ns": finished,
                    "started_utc_ns": utc_started,
                    "finished_utc_ns": utc_finished,
                    "scope_checks": checks,
                    "owner_constructed": owner is not None,
                    "process": process,
                    "stdout": stream_record(
                        stdout,
                        complete=process["stdout_eof"] is True
                        and primary != "STDOUT_LIMIT",
                    ),
                    "stderr": stream_record(
                        stderr,
                        complete=process["stderr_eof"] is True
                        and primary != "STDERR_LIMIT",
                    ),
                    "ready_length": ready_length,
                    "release_wire": stream_record(release, complete=True),
                    "release_write_attempted": release_attempted and release_checked,
                    "release_check_passed": release_checked,
                    "release_delivery_confirmed": release_delivered,
                    "result_validated": False,
                    "primary_error": primary,
                    "cleanup_errors": list(dict.fromkeys(cleanup)),
                    "status": "FAILED",
                    "physical_authority": False,
                    "hardware_qualified": False,
                    "retries": 0,
                }
                evidence = retain_owned_usb_identity_run(value)
                self._evidence = evidence.payload
                return evidence
            finally:
                if owns_dispatch:
                    shared_process._DISPATCH_LOCK.release()


class OwnedUsbIdentityRunner(_Runner):
    def __init__(
        self,
        prepared: PreparedOwnedUsbIdentity,
        *,
        permit: ExactOperationPermit,
        authorization: ConsumedCommissioningScope,
        application_guard: Callable[[], None],
    ) -> None:
        _need(
            type(prepared) is PreparedOwnedUsbIdentity, "EXACT_PHYSICAL_USB_PREPARATION"
        )
        super().__init__(
            prepared,
            permit=permit,
            authorization=authorization,
            application_guard=application_guard,
        )


class IncapableUsbIdentityRunner(_Runner):
    """Same owner and protocol, separately pinned executable without USB APIs."""

    def __init__(
        self,
        prepared: PreparedIncapableUsbIdentity,
        *,
        permit: ExactOperationPermit,
        authorization: ConsumedCommissioningScope,
        application_guard: Callable[[], None],
    ) -> None:
        _need(
            type(prepared) is PreparedIncapableUsbIdentity,
            "EXACT_INCAPABLE_USB_PREPARATION",
        )
        super().__init__(
            prepared,
            permit=permit,
            authorization=authorization,
            application_guard=application_guard,
        )
