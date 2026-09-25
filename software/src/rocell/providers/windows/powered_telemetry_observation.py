"""Bounded zero-write powered capture, separate from the T105 query lifecycle.

This collector never calls write, purges input, toggles torque or changes robot
settings. Opening/configuring the USB controller can still cause startup motion.
Physical entry retains the existing live claim and fresh identity requirements.
"""

from threading import Event
import base64
import hashlib
import time

from rocell.arm.telemetry_stream import TelemetryStream, compact_capture
from rocell.application.powered_arm_feedback_contract import TELEMETRY_PURPOSE
from rocell.application.physical_connection_contracts import EvidenceOrigin
from .powered_feedback_binding import PoweredFeedbackBinding
from .nonpurging_serial_api import IncapableWin32SerialApi
from .nonpurging_serial_backend import NonPurgingSerialConnection


def observe_rehearsal(binding, api, cancellation):
    if type(api) is not IncapableWin32SerialApi:
        raise ValueError("Exact incapable telemetry API required")
    return _observe(binding, api, cancellation, EvidenceOrigin.SYNTHETIC_REHEARSAL)


def observe_physical(binding, api, cancellation):
    from .powered_feedback_serial_api import WindowsPoweredFeedbackSerialApi
    if (type(api) is not WindowsPoweredFeedbackSerialApi
            or type(binding) is not PoweredFeedbackBinding
            or api.admitted_request_sha256 != binding.intent.request_sha256):
        raise ValueError("Live-claim-admitted telemetry API required")
    return _observe(binding, api, cancellation, EvidenceOrigin.PHYSICAL_OBSERVATION)


def _observe(binding, api, cancellation, origin):
    if (type(binding) is not PoweredFeedbackBinding
            or binding.origin is not origin or type(cancellation) is not Event
            or binding.intent.to_dict()["purpose"] != TELEMETRY_PURPOSE):
        raise ValueError("Exact zero-write telemetry intent and provenance required")
    binding.__post_init__()
    intent = binding.intent
    started = time.monotonic_ns()
    intent.require_time_available(started)
    limits = intent.to_dict()["limits"]
    deadline = started + limits["observation_timeout_ms"] * 1_000_000
    parser = TelemetryStream()
    owner = NonPurgingSerialConnection(binding, api=api)
    errors, reads, reason = [], 0, "OBSERVATION_WINDOW_COMPLETE"
    read_windows = []
    acquisition_started = None
    try:
        if cancellation.is_set():
            raise RuntimeError("CANCELLED")
        owner.open()
        # Keep startup inside the original finite deadline, but do not label
        # USB opening/configuration latency as a gap between acquired reports.
        acquisition_started = time.monotonic_ns()
        while time.monotonic_ns() < deadline:
            if cancellation.is_set():
                raise RuntimeError("CANCELLED")
            if parser.remaining_bytes == 0:
                reason = "BYTE_CAPACITY_REACHED"
                break
            if reads == limits["maximum_read_calls"]:
                reason = "READ_CALL_LIMIT_REACHED"
                break
            count = owner.in_waiting
            if count:
                reads += 1
                offset = 65536 - parser.remaining_bytes
                read_started = time.monotonic_ns()
                read_finished = None
                try:
                    block = owner.read(min(count, 256, parser.remaining_bytes), timeout_ms=100)
                    read_finished = time.monotonic_ns()
                    parser.feed(block)
                finally:
                    # Compact rows avoid the IPC node cost of 512 dictionaries.
                    # These bracket the host call, not sensor sample creation.
                    read_windows.append([offset, 65536 - parser.remaining_bytes,
                                         read_started, read_finished if read_finished is not None else time.monotonic_ns()])
            else:
                cancellation.wait(.01)
    except Exception as error:
        errors.append(getattr(error, "code", None) or
                      (str(error) if type(error) is RuntimeError else type(error).__name__))
        reason = "CAPTURE_ERROR"
    finally:
        observation_finished = time.monotonic_ns()
        try:
            owner.close()
        except Exception as error:
            errors.append(getattr(error, "code", type(error).__name__))
    finished = time.monotonic_ns()
    lifecycle = owner.status()
    if not lifecycle["cleanup_confirmed"]:
        errors.append("CLEANUP_UNKNOWN")
    if finished - observation_finished > limits["cleanup_timeout_ms"] * 1_000_000:
        errors.append("CLEANUP_DEADLINE_EXCEEDED")
    if finished > intent.to_dict()["parent_deadline_monotonic_ns"]:
        errors.append("PARENT_DEADLINE_EXCEEDED")
    if lifecycle["confirmed_write_bytes"] != 0:
        errors.append("ZERO_WRITE_INVARIANT_VIOLATED")
    capture = compact_capture(parser.finish())
    return {
        "schema": "rocell.powered_telemetry_observation.v3",
        "origin": origin.value, "request_sha256": intent.request_sha256,
        "status": "CAPTURED_CLOSED" if not errors else "FAILED",
        "stop_reason": reason, "errors": errors, "capture": capture,
        # A timed-out/cancelled read can complete during cleanup. Preserve those
        # bytes separately; they were not parsed in the observation window.
        "late_cleanup_input": {
            "bytes": len(owner.late_read_bytes),
            "sha256": hashlib.sha256(owner.late_read_bytes).hexdigest(),
            "base64": base64.b64encode(owner.late_read_bytes).decode("ascii"),
        },
        "lifecycle": lifecycle, "read_calls": reads,
        "read_windows": read_windows,
        "read_window_columns": ["start_byte", "end_byte", "host_read_started_ns", "host_read_finished_ns"],
        "started_monotonic_ns": started,
        "acquisition_started_monotonic_ns": acquisition_started,
        "observation_finished_monotonic_ns": observation_finished,
        "finished_monotonic_ns": finished,
        "connected": False, "motion_authorized": False, "physical_authority": False,
    }
