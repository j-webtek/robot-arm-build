"""Bounded passive-attempt evidence, verified against its exact request.

This is a result codec, not proof that a claimed observation happened. The
future supervisor must retain raw child output and authenticate its runtime and
provenance before publication. Invalid results must not erase those raw bytes.
Neither a valid result nor a clean close qualifies the arm or proves power off.
"""

import base64
import binascii
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .arm_bench_qualification_contract import (
    PassiveBenchRequest,
    BenchContractError,
    MAX_STARTUP_BYTES,
    OBSERVATION_MS,
    CLEANUP_MS,
    _canonical,
    _object,
    _reject_constant,
    _require,
)


SCHEMA = "rocell.arm_passive_bench_result.v1"
MAX_RESULT_BYTES = 96 * 1024
ERROR_CODES = frozenset(
    {
        "OPEN_FAILED",
        "CONFIGURATION_FAILED",
        "READBACK_MISMATCH",
        "OBSERVATION_FAILED",
        "DEADLINE_EXCEEDED",
        "CANCELLED",
        "CLOSE_FAILED",
        "OWNER_LOST",
        "STARTUP_DATA_LIMIT",
        "UNEXPECTED_OUTBOUND_EFFECT",
    }
)
_FIELDS = frozenset(
    {
        "schema",
        "request_sha256",
        "attempt_id",
        "launch_id",
        "origin",
        "runtime_sha256",
        "open_state",
        "close_state",
        "settings_verified",
        "observation_complete",
        "started_monotonic_ns",
        "observation_finished_monotonic_ns",
        "finished_monotonic_ns",
        "outbound_bytes",
        "startup",
        "errors",
    }
)


def _integer(value, minimum=0, maximum=2**63 - 1):
    _require(
        type(value) is int and minimum <= value <= maximum, "Invalid result integer"
    )


def _validate(payload: bytes, request: PassiveBenchRequest) -> dict[str, Any]:
    _require(type(request) is PassiveBenchRequest, "Exact passive request required")
    _require(
        type(payload) is bytes and 0 < len(payload) <= MAX_RESULT_BYTES,
        "Expected bounded passive result bytes",
    )
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_object,
            parse_constant=_reject_constant,
        )
    except (ValueError, RecursionError) as error:
        raise BenchContractError("Invalid result JSON") from error
    _require(type(value) is dict and set(value) == _FIELDS, "Invalid result fields")
    expected = request.to_dict()
    _require(value["schema"] == SCHEMA, "Wrong result schema")
    _require(
        value["request_sha256"] == request.request_sha256, "Result/request mismatch"
    )
    for key in ("attempt_id", "launch_id"):
        _require(value[key] == expected[key], "Result attempt/launch mismatch")
    _require(
        value["runtime_sha256"] == expected["references"]["runtime_sha256"],
        "Result runtime mismatch",
    )
    _require(
        value["origin"]
        == (
            "SYNTHETIC_REHEARSAL"
            if expected["mode"] == "rehearsal"
            else "PHYSICAL_OBSERVATION"
        ),
        "Result provenance mismatch",
    )
    opened, closed = value["open_state"], value["close_state"]
    _require(
        opened in ("NOT_ATTEMPTED", "FAILED", "SUCCEEDED", "UNKNOWN"),
        "Invalid open state",
    )
    _require(closed in ("NOT_REQUIRED", "CONFIRMED", "UNKNOWN"), "Invalid close state")
    for key in ("settings_verified", "observation_complete"):
        _require(type(value[key]) is bool, "Invalid observation flag")
    if opened in ("NOT_ATTEMPTED", "FAILED"):
        _require(closed == "NOT_REQUIRED", "Unopened port cannot claim close")
    elif opened == "UNKNOWN":
        _require(closed == "UNKNOWN", "Unknown open cannot prove cleanup")
    else:
        _require(closed != "NOT_REQUIRED", "Opened port requires cleanup evidence")
    if opened != "SUCCEEDED":
        _require(
            not value["settings_verified"] and not value["observation_complete"],
            "Unobserved open cannot verify settings or observation",
        )
    for key in (
        "started_monotonic_ns",
        "observation_finished_monotonic_ns",
        "finished_monotonic_ns",
    ):
        _integer(value[key], 1)
    _require(
        value["started_monotonic_ns"]
        <= value["observation_finished_monotonic_ns"]
        <= value["finished_monotonic_ns"],
        "Result timestamps reversed",
    )
    if value["outbound_bytes"] is not None:
        _integer(value["outbound_bytes"])
    startup = value["startup"]
    _require(
        type(startup) is dict
        and set(startup) == {"base64", "sha256", "bytes", "unretained_bytes"},
        "Invalid startup evidence",
    )
    _integer(startup["bytes"], 0, MAX_STARTUP_BYTES)
    if startup["unretained_bytes"] is not None:
        _integer(startup["unretained_bytes"])
    _require(
        type(startup["base64"]) is str
        and len(startup["base64"]) <= 4 * ((MAX_STARTUP_BYTES + 2) // 3),
        "Startup encoding limit",
    )
    try:
        raw = base64.b64decode(startup["base64"], validate=True)
    except (ValueError, binascii.Error) as error:
        raise BenchContractError("Invalid startup encoding") from error
    _require(
        len(raw) == startup["bytes"]
        and base64.b64encode(raw).decode("ascii") == startup["base64"]
        and hashlib.sha256(raw).hexdigest() == startup["sha256"],
        "Startup evidence mismatch",
    )
    if opened in ("NOT_ATTEMPTED", "FAILED"):
        _require(
            startup["bytes"] == startup["unretained_bytes"] == 0,
            "Unopened port cannot supply startup data",
        )
    _require(
        type(value["errors"]) is list
        and len(value["errors"]) <= len(ERROR_CODES)
        and all(type(code) is str and code in ERROR_CODES for code in value["errors"]),
        "Invalid error codes",
    )
    _require(len(set(value["errors"])) == len(value["errors"]), "Duplicate error codes")
    # Unexpected outbound effects, exceeded deadlines and failed cleanup remain
    # representable. Their presence becomes a hold, never a fabricated zero.
    return value


@dataclass(frozen=True, slots=True)
class PassiveBenchResult:
    payload: bytes
    request: PassiveBenchRequest

    def __post_init__(self):
        object.__setattr__(
            self, "payload", _canonical(_validate(self.payload, self.request))
        )

    @property
    def result_sha256(self):
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self):
        return json.loads(self.payload)

    def summary(self):
        value, request = self.to_dict(), self.request.to_dict()
        holds = list(value["errors"])
        observation_ns = (
            value["observation_finished_monotonic_ns"] - value["started_monotonic_ns"]
        )
        cleanup_ns = (
            value["finished_monotonic_ns"] - value["observation_finished_monotonic_ns"]
        )
        if (
            value["finished_monotonic_ns"] > request["parent_deadline_monotonic_ns"]
            or observation_ns > OBSERVATION_MS * 1_000_000
            or cleanup_ns > CLEANUP_MS * 1_000_000
        ):
            holds.append("DEADLINE_EXCEEDED")
        if value["outbound_bytes"] is None:
            holds.append("OUTBOUND_EFFECT_UNKNOWN")
        elif value["outbound_bytes"] != 0:
            holds.append("UNEXPECTED_OUTBOUND_EFFECT")
        if value["startup"]["unretained_bytes"] is None:
            holds.append("STARTUP_DATA_UNACCOUNTED")
        elif value["startup"]["unretained_bytes"]:
            holds.append("STARTUP_DATA_LIMIT")
        if value["open_state"] == "SUCCEEDED" and not value["settings_verified"]:
            holds.append("SETTINGS_NOT_VERIFIED")
        if not value["observation_complete"]:
            holds.append("OBSERVATION_NOT_COMPLETE")
        cleanup = value["close_state"] == "CONFIRMED"
        if value["close_state"] == "UNKNOWN":
            holds.append("CLEANUP_UNKNOWN")
        status = (
            "CLEANUP_UNCERTAIN"
            if value["close_state"] == "UNKNOWN"
            else (
                "SIDE_EFFECT_UNCERTAIN"
                if value["outbound_bytes"] is None
                else (
                    "INCIDENT_HOLD"
                    if value["outbound_bytes"] > 0
                    else (
                        "OBSERVED_CLOSED"
                        if value["open_state"] == "SUCCEEDED" and cleanup and not holds
                        else (
                            "NOT_OPENED"
                            if value["open_state"] == "NOT_ATTEMPTED"
                            else "FAILED_KNOWN"
                        )
                    )
                )
            )
        )
        return {
            "schema": "rocell.arm_passive_bench_result_summary.v1",
            "status": status,
            "origin": value["origin"],
            "request_sha256": self.request.request_sha256,
            "result_sha256": self.result_sha256,
            "holds": sorted(set(holds)),
            "reported_port_close_confirmed": cleanup,
            "outbound_bytes": value["outbound_bytes"],
            "startup_bytes": value["startup"]["bytes"],
            "startup_unretained_bytes": value["startup"]["unretained_bytes"],
            "runtime_authenticated": False,
            "physical_authority": False,
            "connected": False,
            "qualified": False,
            "final_power_state": "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
        }
