"""Reconstruct telemetry interpretation from retained bytes at the worker boundary."""

import base64
import hashlib

from rocell.arm.telemetry_stream import TelemetryStream, compact_capture
from rocell.application.arm_bench_qualification_contract import _canonical
from .powered_feedback_native_registration import require


def _blob(value, maximum):
    require(type(value) is dict and set(value) == {"bytes", "sha256", "base64"}
            and type(value["base64"]) is str
            and len(value["base64"]) <= ((maximum + 2) // 3) * 4,
            "TELEMETRY_BLOB_FIELDS")
    raw = base64.b64decode(value["base64"], validate=True)
    require(type(value["bytes"]) is int and value["bytes"] == len(raw) <= maximum
            and hashlib.sha256(raw).hexdigest() == value["sha256"],
            "TELEMETRY_BLOB_HASH")
    return raw


def validate_observation(obs, *, wire):
    v3 = type(obs) is dict and obs.get("schema") == "rocell.powered_telemetry_observation.v3"
    require(type(obs) is dict and set(obs) == {
        "schema", "origin", "request_sha256", "status", "stop_reason", "errors",
        "capture", "late_cleanup_input", "lifecycle", "read_calls",
        "read_windows", "read_window_columns",
        "started_monotonic_ns", "observation_finished_monotonic_ns", "finished_monotonic_ns",
        "connected", "motion_authorized", "physical_authority",
    } | ({"acquisition_started_monotonic_ns"} if v3 else set()), "TELEMETRY_OBSERVATION_FIELDS")
    require(obs["schema"] in {"rocell.powered_telemetry_observation.v2", "rocell.powered_telemetry_observation.v3"}
            and obs["origin"] == "PHYSICAL_OBSERVATION"
            and obs["request_sha256"] == wire["operation_sha256"]
            and obs["status"] in {"CAPTURED_CLOSED", "FAILED"}
            and all(obs[name] is False for name in ("connected", "motion_authorized", "physical_authority")),
            "TELEMETRY_OBSERVATION_DOMAIN")
    require(type(obs["read_calls"]) is int and 0 <= obs["read_calls"] <= 512
            and type(obs["errors"]) is list and len(obs["errors"]) <= 16
            and all(type(e) is str and len(e) <= 256 for e in obs["errors"]),
            "TELEMETRY_OBSERVATION_LIMITS")
    capture = obs["capture"]
    require(type(capture) is dict, "TELEMETRY_CAPTURE_FIELDS")
    raw = _blob(capture.get("raw"), 65536)
    parser = TelemetryStream()
    parser.feed(raw)
    # Parsed fields, counts and authority flags must exactly follow originals;
    # a child cannot invent a pose, complete a suffix, or assert freshness.
    require(_canonical(compact_capture(parser.finish())) == _canonical(capture), "TELEMETRY_CAPTURE_RECONSTRUCTION")
    _blob(obs["late_cleanup_input"], 65536)
    lifecycle = obs["lifecycle"]
    require(type(lifecycle) is dict
            and lifecycle.get("composition") == "WINDOWS_POWERED_FEEDBACK_ENGINEERING"
            and lifecycle.get("physical_authority") is False
            and lifecycle.get("arm_connected") is False
            and type(lifecycle.get("confirmed_write_bytes")) is int
            and lifecycle["confirmed_write_bytes"] == 0
            and lifecycle.get("write_consumed") is False,
            "TELEMETRY_ZERO_WRITE_LIFECYCLE")
    times = [obs[key] for key in ("started_monotonic_ns", "observation_finished_monotonic_ns", "finished_monotonic_ns")]
    require(all(type(t) is int and t > 0 for t in times) and times == sorted(times),
            "TELEMETRY_TIMESTAMPS")
    require(obs["read_window_columns"] == ["start_byte", "end_byte", "host_read_started_ns", "host_read_finished_ns"]
            and type(obs["read_windows"]) is list
            and len(obs["read_windows"]) == obs["read_calls"], "TELEMETRY_READ_WINDOWS")
    acquisition = obs.get("acquisition_started_monotonic_ns", times[0])
    if v3:
        require((type(acquisition) is int and times[0] <= acquisition <= times[1])
                or (acquisition is None and obs["status"] == "FAILED" and not obs["read_windows"]
                    and not raw), "TELEMETRY_ACQUISITION_START")
    offset, last_time = 0, acquisition if acquisition is not None else times[0]
    for row in obs["read_windows"]:
        require(type(row) is list and len(row) == 4
                and all(type(value) is int for value in row), "TELEMETRY_READ_WINDOW_FIELDS")
        start, end, read_start, read_end = row
        require(start == offset and start <= end <= len(raw) and end - start <= 256
                and last_time <= read_start <= read_end <= times[1], "TELEMETRY_READ_WINDOW_COVERAGE")
        offset, last_time = end, read_end
    require(offset == len(raw), "TELEMETRY_READ_WINDOW_COVERAGE")
    require(obs["stop_reason"] in {"OBSERVATION_WINDOW_COMPLETE", "BYTE_CAPACITY_REACHED",
            "READ_CALL_LIMIT_REACHED", "CAPTURE_ERROR"}, "TELEMETRY_STOP_REASON")
    if obs["status"] == "CAPTURED_CLOSED":
        require(not obs["errors"] and lifecycle.get("cleanup_confirmed") is True
                and times[2] <= wire["parent_deadline_monotonic_ns"]
                and times[2] - times[1] <= 2_000_000_000
                and obs["stop_reason"] != "CAPTURE_ERROR", "TELEMETRY_CAPTURE_SUCCESS")
        if obs["stop_reason"] == "OBSERVATION_WINDOW_COMPLETE":
            require(times[1] - times[0] >= 5_000_000_000, "TELEMETRY_WINDOW_EARLY")
        elif obs["stop_reason"] == "BYTE_CAPACITY_REACHED":
            require(len(raw) == 65536, "TELEMETRY_CAPACITY_EARLY")
        else:
            require(obs["read_calls"] == 512, "TELEMETRY_READ_LIMIT_EARLY")
    return obs
