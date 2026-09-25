"""One-use guarded native-probe supervisor; physical composition stays held.

Only the separately compiled, fixed admission-only test executable can run in
this increment. No public backend/argv/path switch can turn that lane physical.
The shared lifecycle below is the native adapter implementation, not permission
to use it. Its external callback validates a previously consumed coordinator
scope; it must not redeem a permit a second time.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, TYPE_CHECKING

from . import owned_worker_process as shared_process
from .native_camera_parent_admission import NativeCameraParentHandshake
from .native_camera_protocol import canonical, digest, MAX_HANDSHAKE_BYTES
from .native_camera_registration import PreparedOwnedNativeProbe
from .native_camera_capture_registration import PreparedOwnedNativeCapture
from .owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessRegistration,
    owned_registration_document,
    decode_owned_json,
)

if TYPE_CHECKING:
    from .owned_native_camera_evidence import OwnedNativeCameraRunEvidence

INCAPABLE_RESULT_SCHEMA = "rocell.native_camera_admission_only_test.v1"
INCAPABLE_PREPARATION_SCHEMA = "rocell.prepared_incapable_native_admission.v1"
_NATIVE = Path(__file__).parents[5] / "software/native/windows_camera"
INCAPABLE_CHILD_PATH = (
    _NATIVE / "build-owned/Release/rocell_camera_admission_entry_tests.exe"
)
# Explicit reviewed *incapable* build pins. No production executable or metadata
# catalog is substituted; build drift is a hold, not an auto-refresh operation.
_TEST_PINS = (
    (
        "build-owned/Release/rocell_camera_admission_entry_tests.exe",
        "2dedfd13dcd57968cb06d859b7cf90017ca399a1ea774af15536efd3d0a5c4a0",
    ),
    (
        "admission_entry_tests.cpp",
        "cb6aa5ab9efec192d530b1a5f99b8f97ce0abfde22b49f706f97e8912cff0c70",
    ),
    (
        "admission_entry.cpp",
        "91aa3c41bde8e24b19f6a2d4494896a847583a92ad5e30b2b42c3809604a9643",
    ),
    (
        "admission_entry.h",
        "69cb306c4d3e0b6527091a7ed3ddbfd3bf6627c67ed789e455fbed7530015a39",
    ),
    (
        "admission_protocol.cpp",
        "54124fbef5eba9e3d3f3484123c280231b9178fd30f5b353dddddc86e876f800",
    ),
    (
        "admission_protocol.h",
        "2f171649b196c8eb18dbf2f57eeb34787e58b8ca50a8d3f6bb015b0988d95a3f",
    ),
    (
        "CMakeLists.txt",
        "7f0dc880a4335fdafa2a0be794d84dbdbed0dd3233114010a555740c99e3da22",
    ),
)


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def _registration(prepared: PreparedOwnedNativeProbe) -> WorkerProcessRegistration:
    pins = tuple(
        PinnedWorkerFile(_NATIVE / name, sha, 1024 * 1024) for name, sha in _TEST_PINS
    )
    return replace(
        prepared.registration,
        worker_id="incapable-native-admission-entry",
        executable=pins[0],
        package_files=pins[1:],
        composition="INCAPABLE_PROCESS_FIXTURE",
        result_schema=INCAPABLE_RESULT_SCHEMA,
    )


@dataclass(frozen=True, slots=True)
class PreparedIncapableNativeAdmission:
    """Closed test registration; it cannot accept a supplied executable or argv."""

    payload: bytes

    def __post_init__(self) -> None:
        value = decode_owned_json(self.payload, maximum=48 * 1024)
        _require(
            canonical(value) == self.payload
            and set(value) == {"schema", "probe", "registration"}
            and value["schema"] == INCAPABLE_PREPARATION_SCHEMA,
            "INCAPABLE_PREPARATION_SCHEMA",
        )
        probe = PreparedOwnedNativeProbe(canonical(value["probe"]))
        _require(
            value["registration"] == owned_registration_document(_registration(probe)),
            "FIXED_INCAPABLE_REGISTRATION_REQUIRED",
        )

    @property
    def probe(self) -> PreparedOwnedNativeProbe:
        return PreparedOwnedNativeProbe(canonical(self.to_dict()["probe"]))

    @property
    def registration(self) -> WorkerProcessRegistration:
        return _registration(self.probe)

    def to_dict(self) -> dict[str, Any]:
        return decode_owned_json(self.payload, maximum=48 * 1024)


def prepare_incapable_native_admission(
    prepared: PreparedOwnedNativeProbe,
) -> PreparedIncapableNativeAdmission:
    """Inert fixed test lane; no pin reads, directory creation or native calls."""
    _require(type(prepared) is PreparedOwnedNativeProbe, "EXACT_PREPARATION_REQUIRED")
    prepared = PreparedOwnedNativeProbe(prepared.payload)
    return PreparedIncapableNativeAdmission(
        canonical(
            {
                "schema": INCAPABLE_PREPARATION_SCHEMA,
                "probe": prepared.to_dict(),
                "registration": owned_registration_document(_registration(prepared)),
            }
        )
    )


def _new_owner() -> Any:
    # Importing/constructing this owner loads Win32. It is unreachable from the
    # held physical public runner and from construction/status/preparation.
    from ._owned_worker_win32 import WindowsOwnedProcess

    return WindowsOwnedProcess()


def _label(error: BaseException) -> str:
    text = str(error)
    if isinstance(error, OSError) and error.args:
        operation = error.args[-1]
        if type(operation) is str and re.fullmatch(r"[A-Za-z0-9_:-]{1,96}", operation):
            return "OS_ERROR:" + operation
    return (
        text if re.fullmatch(r"[A-Z][A-Z0-9_:]{0,127}", text) else type(error).__name__
    )


def validate_incapable_completion(
    raw: dict[str, Any],
    *,
    request_sha256: str,
    child_pid: int,
    challenge_sha256: str,
    returncode: int,
) -> None:
    _require(
        type(raw) is dict
        and set(raw)
        == {
            "schema",
            "admitted",
            "request_sha256",
            "child_pid",
            "challenge_sha256",
            "device_effects",
        },
        "INCAPABLE_RESULT_SCHEMA",
    )
    _require(
        raw["schema"] == INCAPABLE_RESULT_SCHEMA
        and raw["admitted"] is True
        and raw["request_sha256"] == request_sha256
        and type(raw["child_pid"]) is int
        and raw["child_pid"] == child_pid
        and raw["challenge_sha256"] == challenge_sha256
        and type(raw["device_effects"]) is int
        and raw["device_effects"] == 0
        and type(returncode) is int
        and returncode == 0,
        "INCAPABLE_RESULT_BINDING",
    )


class _Runner:
    def __init__(
        self,
        prepared: (
            PreparedOwnedNativeProbe
            | PreparedOwnedNativeCapture
            | PreparedIncapableNativeAdmission
        ),
        revalidate_consumed_permit: Callable[..., None],
    ) -> None:
        _require(callable(revalidate_consumed_permit), "CURRENT_PERMIT_CHECK_REQUIRED")
        self._original = prepared
        self._payload = prepared.payload
        self._callback = revalidate_consumed_permit
        self._lock = threading.Lock()
        self._used = False

    def status(self) -> dict[str, Any]:
        return {
            "consumed": self._used,
            "physical_dispatch_enabled": False,
            "physical_authority": False,
            "implicit_dispatch": False,
            "process_cleanup_hold": shared_process._UNRESOLVED_BACKEND is not None,
            "final_power_state": "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
            "retries": 0,
        }

    def run(
        self, *, cancellation: threading.Event, deadline_ns: int
    ) -> OwnedNativeCameraRunEvidence:
        from .owned_native_camera_evidence import retain_owned_native_camera_run

        with self._lock:
            _require(not self._used, "RUNNER_ALREADY_CONSUMED")
            self._used = True
        started = time.monotonic_ns()
        incapable = type(self._original) is PreparedIncapableNativeAdmission
        fixture = PreparedIncapableNativeAdmission(self._payload) if incapable else None
        probe: PreparedOwnedNativeProbe | PreparedOwnedNativeCapture
        if fixture:
            probe = fixture.probe
        elif type(self._original) is PreparedOwnedNativeCapture:
            probe = PreparedOwnedNativeCapture(self._payload)
        else:
            probe = PreparedOwnedNativeProbe(self._payload)
        registration = fixture.registration if fixture else probe.registration
        sealed_registration = canonical(owned_registration_document(registration))
        primary = None
        native = parent = None
        raw_result = None
        ready_wire = release_wire = b""
        native_validated = admission_only_validated = False
        release_check_passed = False
        owns_dispatch = False
        run_deadline = deadline_ns
        observed: dict[str, Any] = {}

        def live() -> None:
            _require(not cancellation.is_set(), "CANCELLED")
            _require(time.monotonic_ns() < run_deadline, "TIMED_OUT")
            _require(self._original.payload == self._payload, "PREPARATION_CHANGED")
            _require(
                canonical(owned_registration_document(registration))
                == sealed_registration,
                "PROCESS_REGISTRATION_CHANGED",
            )

        try:
            _require(isinstance(cancellation, threading.Event), "CANCELLATION_REQUIRED")
            _require(
                type(deadline_ns) is int and 0 < deadline_ns < 2**63,
                "INVALID_PARENT_DEADLINE",
            )
            live()
            # There is deliberately no configuration flag or authorizer result
            # that opens this physical branch. Runtime qualification is separate.
            _require(incapable, "PHYSICAL_PROVIDER_QUALIFICATION_HELD")
            # Shared private ownership boundary with OwnedWindowsWorker: the
            # reservation spans pinning through cleanup, and uncertain owners
            # retain their pending buffers for process lifetime. Never overwrite.
            owns_dispatch = shared_process._DISPATCH_LOCK.acquire(blocking=False)
            _require(owns_dispatch, "OWNED_PROCESS_ALREADY_RUNNING")
            _require(shared_process._UNRESOLVED_BACKEND is None, "PROCESS_CLEANUP_HOLD")
            _require(
                time.monotonic_ns() + probe.required_lifetime_ns <= deadline_ns,
                "FULL_LIFETIME_DOES_NOT_FIT",
            )
            native = _new_owner()
            native.pin(registration)
            live()
            parent = NativeCameraParentHandshake(
                probe,
                cancellation=cancellation,
                revalidate_consumed_permit=self._callback,
            )
            run_deadline = min(
                deadline_ns,
                time.monotonic_ns() + registration.budget.run_timeout_ms * 1_000_000,
            )
            request_wire = parent.begin(deadline_ns=deadline_ns)

            def start_check() -> None:
                live()
                parent.check_start_boundary()
                live()

            native.start(
                registration, request_wire, check=start_check, keep_stdin_open=True
            )
            while not ready_wire:
                start_check()
                ended = native.poll(registration.budget)
                start_check()
                output = native.stdout
                _require(
                    type(output) is bytes
                    and len(output) <= registration.budget.stdout_bytes,
                    "STDOUT_LIMIT",
                )
                if b"\n" in output and not native.pending:
                    first, extra = output.split(b"\n", 1)
                    _require(not extra, "OUTPUT_BEFORE_RELEASE")
                    _require(len(first) + 1 <= MAX_HANDSHAKE_BYTES, "READY_BYTE_LIMIT")
                    ready_wire = first + b"\n"
                    release_wire = parent.accept_ready(
                        ready_wire, owned_child_pid=native.pid
                    )
                    break
                _require(len(output) < MAX_HANDSHAKE_BYTES, "READY_BYTE_LIMIT")
                _require(not ended, "CHILD_EXIT_BEFORE_READY")
                cancellation.wait(0.005)

            def release_check() -> None:
                nonlocal release_check_passed
                live()
                parent.check_release()
                live()
                release_check_passed = True

            native.send_final_input(release_wire, check=release_check)
            while True:
                live()
                ended = native.poll(registration.budget)
                live()
                if ended:
                    break
                cancellation.wait(0.005)
            _require(native.stdout.startswith(ready_wire), "READY_PREFIX_CHANGED")
            result_wire = native.stdout[len(ready_wire) :]
            if incapable:
                _require(native.returncode == 0, "CHILD_EXIT_FAILED")
                candidate = decode_owned_json(
                    result_wire, maximum=registration.budget.stdout_bytes
                )
                release = decode_owned_json(release_wire, maximum=MAX_HANDSHAKE_BYTES)
                validate_incapable_completion(
                    candidate,
                    request_sha256=probe.admission_request.request_sha256,
                    child_pid=native.pid,
                    challenge_sha256=release["challenge_sha256"],
                    returncode=native.returncode,
                )
                raw_result, admission_only_validated = candidate, True
            else:
                # Native join is implemented but unreachable until separately
                # reviewed physical admission is added; no fixture can enter it.
                raw_result, native_receipt = parent.accept_result(
                    result_wire, returncode=native.returncode
                )
                native_validated = True
                if native_receipt.status != "OK":
                    primary = "NATIVE_DIAGNOSTIC_FAILED"
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
                ("pid", 0),
                ("written", 0),
                ("peak_handles", 0),
                ("peak_processes", 0),
                ("stdout", b""),
                ("stderr", b""),
                ("stdout_eof", False),
                ("stderr_eof", False),
                ("pending", False),
            ):
                try:
                    value = getattr(native, name)
                    valid = (
                        value is None or type(value) is int
                        if name == "returncode"
                        else type(value) is type(default)
                    )
                    if valid:
                        observed[name] = value
                except Exception:
                    pass
                observed.setdefault(name, default)
            for name in ("handles", "unclosed_handles", "pins"):
                try:
                    observed[name + "_remaining"] = len(getattr(native, name))
                except Exception:
                    observed[name + "_remaining"] = 1

        cleanup: tuple[str, ...] = ()
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
                        or len(cleanup) > 256
                        or any(
                            type(code) is not str
                            or not re.fullmatch(r"[A-Za-z0-9_:-]{1,128}", code)
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
                    # We own the global admission reservation until finally.
                    # No second owner can race this non-overwriting retention.
                    _require(
                        shared_process._UNRESOLVED_BACKEND is None,
                        "UNRESOLVED_OWNER_ALREADY_RETAINED",
                    )
                    shared_process._UNRESOLVED_BACKEND = native
            if primary is None:
                if cancellation.is_set():
                    primary = "CANCELLED"
                elif time.monotonic_ns() >= deadline_ns:
                    primary = "TIMED_OUT"
            return retain_owned_native_camera_run(
                probe=probe,
                fixture=fixture,
                deadline_ns=deadline_ns,
                elapsed_ns=max(0, time.monotonic_ns() - started),
                primary_error=primary,
                cleanup_errors=tuple(dict.fromkeys(cleanup)),
                observed=observed,
                ready_wire=ready_wire,
                release_wire=release_wire,
                result=raw_result,
                native_validated=native_validated,
                admission_only_validated=admission_only_validated,
                release_check_passed=release_check_passed,
                handshake=None if parent is None else parent.view(),
            )
        finally:
            if owns_dispatch:
                shared_process._DISPATCH_LOCK.release()


class OwnedNativeCameraRunner(_Runner):
    """Production preparation surface, unconditionally physical-held today."""

    def __init__(
        self,
        prepared: PreparedOwnedNativeProbe | PreparedOwnedNativeCapture,
        *,
        revalidate_consumed_permit: Callable[..., None],
    ) -> None:
        _require(
            type(prepared) in (PreparedOwnedNativeProbe, PreparedOwnedNativeCapture),
            "EXACT_PREPARATION_REQUIRED",
        )
        type(prepared)(prepared.payload)
        super().__init__(prepared, revalidate_consumed_permit)


class IncapableNativeAdmissionRunner(_Runner):
    """Separate closed test-only execution; cannot return native probe success."""

    def __init__(
        self,
        prepared: PreparedIncapableNativeAdmission,
        *,
        revalidate_consumed_permit: Callable[[PreparedOwnedNativeProbe], None],
    ) -> None:
        _require(
            type(prepared) is PreparedIncapableNativeAdmission,
            "EXACT_INCAPABLE_PREPARATION_REQUIRED",
        )
        PreparedIncapableNativeAdmission(prepared.payload)
        super().__init__(prepared, revalidate_consumed_permit)
