"""One-use parent side of the guarded probe handshake, with no process launch.

This is a production protocol primitive, not a physical composition or permit
issuer. A future qualified coordinator must own the leases, pin the exact
registration, consume the exact attempt, and supply its current-permit check.
The existing application dispatcher still rejects physical registrations.

The low-level pipe owner sends the returned release only with ``check_release``
as its final WriteFile check. Producing bytes does not mean they were delivered,
the native camera opened, or any cleanup succeeded.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from .camera_worker_client import NativeCameraReceipt, NativeCameraReceiptMetadata
from .native_camera_protocol import (
    NativeCameraReady,
    native_camera_release,
    parse_native_camera_ready,
    parse_owned_native_camera_result,
)
from .native_camera_registration import PreparedOwnedNativeProbe
from .native_camera_capture_registration import PreparedOwnedNativeCapture
from .native_camera_capture_protocol import (
    native_camera_capture_release,
    parse_owned_native_camera_capture_result,
)
from .native_camera_activation_registration import PreparedOwnedNativeActivation
from .native_camera_activation_protocol import (
    activation_release,
    parse_owned_activation_result,
)

NativePreparation = (
    PreparedOwnedNativeProbe
    | PreparedOwnedNativeCapture
    | PreparedOwnedNativeActivation
)


class NativeCameraParentAdmissionError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise NativeCameraParentAdmissionError(code)


class NativeCameraParentHandshake:
    """Inert until explicitly begun; failed admission never permits retry.

    The callback checks an *already consumed* permit against the entire exact
    preparation (including cwd, registration, all budgets, and source). It must
    not issue or consume another permit. A request hash alone is insufficient.
    Calls are serialized and non-reentrant; cancellation is independently safe
    to signal from another thread.
    """

    def __init__(
        self,
        prepared: NativePreparation,
        *,
        cancellation: threading.Event,
        revalidate_consumed_permit: Callable[..., None],
        _clock: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        _require(
            type(prepared)
            in (
                PreparedOwnedNativeProbe,
                PreparedOwnedNativeCapture,
                PreparedOwnedNativeActivation,
            ),
            "EXACT_PREPARATION_REQUIRED",
        )
        _require(isinstance(cancellation, threading.Event), "CANCELLATION_REQUIRED")
        _require(callable(revalidate_consumed_permit), "CURRENT_PERMIT_CHECK_REQUIRED")
        self._prepared_type = type(prepared)
        self._payload = self._prepared_type(prepared.payload).payload
        self._original = prepared
        self._cancel = cancellation
        self._revalidate = revalidate_consumed_permit
        self._clock = _clock
        self._state = "PREPARED_NO_DISPATCH"
        self._ready_payload: bytes | None = None
        self._owned_child_pid: int | None = None
        self._deadline = self._run_deadline = self._admission_deadline = 0
        self._last_now = 0
        self._lock = threading.Lock()

    def _now(self) -> int:
        now = self._clock()
        _require(
            type(now) is int and self._last_now <= now < 2**63,
            "INVALID_MONOTONIC_CLOCK",
        )
        self._last_now = now
        return now

    def _prepared(self) -> NativePreparation:
        _require(self._original.payload == self._payload, "PREPARATION_CHANGED")
        return self._prepared_type(self._payload)

    def _live(self) -> tuple[NativePreparation, int]:
        _require(not self._cancel.is_set(), "CANCELLED")
        prepared = self._prepared()
        now = self._now()
        _require(
            now < self._deadline and now < self._run_deadline, "PARENT_DEADLINE_EXPIRED"
        )
        return prepared, now

    def _current_permit(self, prepared: NativePreparation) -> None:
        # Never expose the stored object to a callback, even though it is frozen.
        exact = self._prepared_type(prepared.payload)
        _require(self._revalidate(exact) is None, "PERMIT_CHECK_MUST_RETURN_NONE")
        _require(exact.payload == self._payload, "PERMIT_CHECK_INPUT_CHANGED")
        self._prepared()

    def _enter(self) -> None:
        _require(self._lock.acquire(blocking=False), "CONCURRENT_HANDSHAKE_CALL")

    def begin(self, *, deadline_ns: int) -> bytes:
        """After pins/consumption, recheck exact authority and obtain first wire.

        This does not start a process. The caller must preserve this deadline
        through launch, the READY wait, native work, cleanup, and retention.
        """
        self._enter()
        try:
            _require(self._state == "PREPARED_NO_DISPATCH", "HANDSHAKE_ALREADY_BEGUN")
            self._state = "BEGIN_CHECK_PENDING"
            prepared = self._prepared()
            _require(
                type(deadline_ns) is int and 0 < deadline_ns < 2**63,
                "INVALID_PARENT_DEADLINE",
            )
            _require(not self._cancel.is_set(), "CANCELLED")
            _require(
                self._now() + prepared.required_lifetime_ns <= deadline_ns,
                "FULL_LIFETIME_DOES_NOT_FIT",
            )
            self._current_permit(prepared)
            _require(not self._cancel.is_set(), "CANCELLED")
            now = self._now()
            _require(
                now + prepared.required_lifetime_ns <= deadline_ns,
                "FULL_LIFETIME_DOES_NOT_FIT",
            )
            budget = prepared.registration.budget
            request = prepared.admission_request
            self._deadline = deadline_ns
            self._run_deadline = now + budget.run_timeout_ms * 1_000_000
            # Bound startup and the parent's wait too, not just child parsing.
            self._admission_deadline = (
                now + request.to_dict()["admission_timeout_ms"] * 1_000_000
            )
            self._state = "REQUEST_READY_FOR_TRANSPORT"
            return request.wire()
        except BaseException:
            self._state = "FAILED_NO_RETRY"
            raise
        finally:
            self._lock.release()

    def check_start_boundary(self) -> None:
        """Pure current-input/deadline checks at create, resume and first write."""
        self._enter()
        try:
            _require(
                self._state == "REQUEST_READY_FOR_TRANSPORT", "REQUEST_NOT_AVAILABLE"
            )
            _, now = self._live()
            _require(now < self._admission_deadline, "ADMISSION_DEADLINE_EXPIRED")
        except BaseException:
            self._state = "FAILED_NO_RETRY"
            raise
        finally:
            self._lock.release()

    def accept_ready(self, wire: bytes, *, owned_child_pid: int) -> bytes:
        """Validate one complete READY against the actual owned process PID.

        The supervisor retains partial pipe bytes and calls this only once a
        bounded line is complete; no native work is permitted while waiting.
        The returned release still requires ``check_release`` at WriteFile.
        """
        self._enter()
        try:
            _require(self._state == "REQUEST_READY_FOR_TRANSPORT", "READY_NOT_EXPECTED")
            self._state = "READY_VALIDATION_PENDING"
            prepared, now = self._live()
            _require(now < self._admission_deadline, "ADMISSION_DEADLINE_EXPIRED")
            ready = parse_native_camera_ready(
                wire,
                expected_request_sha256=prepared.admission_request.request_sha256,
                expected_child_pid=owned_child_pid,
            )
            _, now = self._live()
            _require(now < self._admission_deadline, "ADMISSION_DEADLINE_EXPIRED")
            self._ready_payload = ready.payload
            self._owned_child_pid = owned_child_pid
            self._state = "READY_VALIDATED_RELEASE_NOT_CHECKED"
            if isinstance(prepared, PreparedOwnedNativeActivation):
                return activation_release(
                    prepared.admission_request,
                    ready,
                    expected_child_pid=owned_child_pid,
                )
            if isinstance(prepared, PreparedOwnedNativeCapture):
                return native_camera_capture_release(prepared.admission_request, ready)
            return native_camera_release(prepared.admission_request, ready)
        except BaseException:
            self._state = "FAILED_NO_RETRY"
            raise
        finally:
            self._lock.release()

    def check_release(self) -> None:
        """Consume one final check immediately before the release WriteFile.

        Recheck the exact consumed permit after READY; no automatic renewal or
        second redemption. A failed/slow callback leaves the release unusable.
        """
        self._enter()
        try:
            _require(
                self._state == "READY_VALIDATED_RELEASE_NOT_CHECKED",
                "RELEASE_CHECK_NOT_AVAILABLE",
            )
            self._state = "RELEASE_CHECK_PENDING"
            prepared, now = self._live()
            _require(now < self._admission_deadline, "ADMISSION_DEADLINE_EXPIRED")
            self._current_permit(prepared)
            prepared, now = self._live()
            _require(now < self._admission_deadline, "ADMISSION_DEADLINE_EXPIRED")
            native_ns = (
                prepared.admission_request.to_dict()["native_duration_ms"] * 1_000_000
            )
            cleanup_ns = prepared.registration.budget.cleanup_timeout_ms * 1_000_000
            _require(
                now + native_ns < self._run_deadline
                and now + native_ns + cleanup_ns <= self._deadline,
                "NATIVE_LIFETIME_DOES_NOT_FIT",
            )
            self._state = "RELEASE_CHECK_PASSED_DELIVERY_UNOBSERVED"
        except BaseException:
            self._state = "FAILED_NO_RETRY"
            raise
        finally:
            self._lock.release()

    def accept_result(
        self, wire: bytes, *, returncode: int
    ) -> tuple[dict[str, Any], NativeCameraReceipt | NativeCameraReceiptMetadata]:
        """Validate inner native receipt separately; never infer device cleanup."""
        self._enter()
        try:
            _require(
                self._state == "RELEASE_CHECK_PASSED_DELIVERY_UNOBSERVED"
                and self._ready_payload is not None,
                "RESULT_NOT_EXPECTED",
            )
            self._state = "RESULT_VALIDATION_PENDING"
            prepared, _ = self._live()
            assert self._ready_payload is not None
            # Capture validation is metadata-only here. Artifact reads belong
            # to the explicit file verifier, never to retained reconstruction.
            result: tuple[
                dict[str, Any], NativeCameraReceipt | NativeCameraReceiptMetadata
            ]
            if isinstance(prepared, PreparedOwnedNativeActivation):
                assert self._owned_child_pid is not None
                # The transport bounds the complete stream, not each message
                # independently. Retained reconstruction must enforce that too.
                _require(
                    type(wire) is bytes
                    and len(wire) + len(self._ready_payload) + 1
                    <= prepared.registration.budget.stdout_bytes,
                    "RESULT_COMBINED_STDOUT_LIMIT",
                )
                validated = parse_owned_activation_result(
                    wire,
                    request=prepared.admission_request,
                    ready=NativeCameraReady(self._ready_payload),
                    expected_child_pid=self._owned_child_pid,
                    returncode=returncode,
                )
                result = validated.to_dict(), validated.receipt
            elif isinstance(prepared, PreparedOwnedNativeCapture):
                result = parse_owned_native_camera_capture_result(
                    wire,
                    request=prepared.admission_request,
                    ready=NativeCameraReady(self._ready_payload),
                    returncode=returncode,
                )
            else:
                result = parse_owned_native_camera_result(
                    wire,
                    request=prepared.admission_request,
                    ready=NativeCameraReady(self._ready_payload),
                    returncode=returncode,
                )
            self._live()
            self._state = "RESULT_VALIDATED_NOT_QUALIFIED"
            return result
        except BaseException:
            self._state = "FAILED_NO_RETRY"
            raise
        finally:
            self._lock.release()

    def view(self) -> dict[str, Any]:
        """No raw challenge/endpoint, runtime access, or liveness side effects."""
        return {
            "schema": (
                "rocell.native_camera_parent_handshake.v2"
                if self._prepared_type is PreparedOwnedNativeActivation
                else "rocell.native_camera_parent_handshake.v1"
            ),
            "state": self._state,
            "preparation_sha256": self._prepared_type(self._payload).preparation_sha256,
            "physical_dispatch_enabled": False,
            "physical_authority": False,
            "device_cleanup_confirmed": False,
            "final_power_state": "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
            "retries": 0,
        }
