"""Pure original owned USB execution evidence; never replays a process or USB call.

Native receipt bytes remain in the original bounded stdout. Re-parsing those
bytes avoids retaining a second mutable/synthetic copy of the observation.
Process cleanup and the native report's USB handle accounting are independent.
"""

from __future__ import annotations
import base64
from dataclasses import dataclass
import re
from typing import Any, cast
from .owned_worker_process import decode_owned_json
from .usb_identity_protocol import (
    UsbIdentityObservation,
    UsbIdentityReady,
    canonical,
    digest,
    parse_usb_identity_ready,
    parse_owned_usb_identity_result,
    usb_identity_release,
)
from .usb_identity_registration import (
    Preparation,
    PreparedOwnedUsbIdentity,
    PreparedIncapableUsbIdentity,
    PREPARATION_SCHEMA,
)

SCHEMA = "rocell.owned_usb_identity_run.v1"
MAX_EVIDENCE_BYTES = 128 * 1024
# The historical wire admits at most 32 labels. Reserve four slots for the
# supervisor's deadline, resources, tree-exit and unresolved-owner conditions.
MAX_CLEANUP_ERRORS = 32
MAX_OWNER_CLEANUP_ERRORS = MAX_CLEANUP_ERRORS - 4
BOUNDARIES = ("PRE_PIN", "POST_PIN", "PRE_START", "PRE_RELEASE", "POST_RESULT")
_CODE = re.compile(r"[A-Za-z0-9_:-]{1,128}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
PROCESS_DEFAULTS = {
    "created": False,
    "resumed": False,
    "tree_exited": False,
    "returncode": None,
    "pid": 0,
    "written": 0,
    "peak_handles": 0,
    "peak_processes": 0,
    "stdout_eof": False,
    "stderr_eof": False,
    "pending": False,
    "handles_remaining": 0,
    "unclosed_handles_remaining": 0,
    "pins_remaining": 0,
    "observation_complete": True,
}


class OwnedUsbIdentityEvidenceError(ValueError):
    pass


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise OwnedUsbIdentityEvidenceError(code)


def stream_record(raw: bytes, *, complete: bool) -> dict[str, Any]:
    _need(type(raw) is bytes and type(complete) is bool, "EXACT_USB_STREAM")
    return {
        "length_bytes": len(raw),
        "sha256": digest(raw),
        "complete": complete,
        "base64_chunks": [
            base64.b64encode(raw[i : i + 16384]).decode("ascii")
            for i in range(0, len(raw), 16384)
        ],
    }


def stream_bytes(value: Any, maximum: int) -> bytes:
    _need(
        type(value) is dict
        and set(value) == {"length_bytes", "sha256", "complete", "base64_chunks"},
        "EXACT_USB_STREAM_FIELDS",
    )
    _need(
        type(value["length_bytes"]) is int
        and 0 <= value["length_bytes"] <= maximum
        and type(value["complete"]) is bool
        and type(value["sha256"]) is str
        and bool(_SHA.fullmatch(value["sha256"])),
        "USB_STREAM_BOUND",
    )
    chunks = value["base64_chunks"]
    _need(
        type(chunks) is list
        and len(chunks) <= (maximum + 16383) // 16384
        and all(type(c) is str and len(c) <= 21848 for c in chunks),
        "USB_STREAM_CHUNKS",
    )
    try:
        raw = b"".join(base64.b64decode(c, validate=True) for c in chunks)
    except (ValueError, UnicodeError) as e:
        raise OwnedUsbIdentityEvidenceError("USB_STREAM_ENCODING") from e
    _need(
        len(raw) == value["length_bytes"]
        and digest(raw) == value["sha256"]
        and canonical(stream_record(raw, complete=value["complete"]))
        == canonical(value),
        "USB_STREAM_ORIGINAL_HASH",
    )
    return raw


def preparation_from_document(value: dict[str, Any]) -> Preparation:
    _need(type(value) is dict, "EXACT_USB_PREPARATION_DOCUMENT")
    cls = (
        PreparedOwnedUsbIdentity
        if value.get("schema") == PREPARATION_SCHEMA
        else PreparedIncapableUsbIdentity
    )
    return cls(canonical(value))


def _observation(
    v: dict[str, Any], prepared: Preparation
) -> UsbIdentityObservation | None:
    if not v["result_validated"]:
        return None
    stdout = stream_bytes(v["stdout"], 66 * 1024)
    ready_wire = stdout[: v["ready_length"]]
    ready = parse_usb_identity_ready(
        ready_wire,
        expected_request_sha256=prepared.request.request_sha256,
        expected_child_pid=v["process"]["pid"],
    )
    _, result = parse_owned_usb_identity_result(
        stdout[v["ready_length"] :],
        request=prepared.request,
        ready=ready,
        returncode=v["process"]["returncode"],
    )
    return result


def _process_clean(v: dict[str, Any]) -> bool:
    p = v["process"]
    return bool(
        v["owner_constructed"]
        and p["observation_complete"]
        and not v["cleanup_errors"]
        and not p["pending"]
        and not any(
            p[n]
            for n in (
                "handles_remaining",
                "unclosed_handles_remaining",
                "pins_remaining",
            )
        )
        and (not p["created"] or p["tree_exited"])
    )


def _status(v: dict[str, Any], observation: UsbIdentityObservation | None) -> str:
    p = v["process"]
    if v["cleanup_errors"] or (v["owner_constructed"] and not _process_clean(v)):
        return "CLEANUP_UNCERTAIN"
    if v["primary_error"] in {"CANCELLED", "TIMED_OUT"}:
        return v["primary_error"]
    if v["primary_error"] is not None:
        return "FAILED"
    if observation is None:
        return "FAILED"
    return observation.to_dict()["outcome"]


def _validate(payload: bytes) -> dict[str, Any]:
    v = decode_owned_json(payload, maximum=MAX_EVIDENCE_BYTES)
    _need(
        canonical(v) == payload
        and set(v)
        == {
            "schema",
            "preparation",
            "preparation_sha256",
            "provenance",
            "original_deadline_ns",
            "started_monotonic_ns",
            "finished_monotonic_ns",
            "started_utc_ns",
            "finished_utc_ns",
            "scope_checks",
            "owner_constructed",
            "process",
            "stdout",
            "stderr",
            "ready_length",
            "release_wire",
            "release_write_attempted",
            "release_check_passed",
            "release_delivery_confirmed",
            "result_validated",
            "primary_error",
            "cleanup_errors",
            "status",
            "physical_authority",
            "hardware_qualified",
            "retries",
        },
        "EXACT_USB_EVIDENCE_FIELDS",
    )
    _need(v["schema"] == SCHEMA, "EXACT_USB_EVIDENCE_SCHEMA")
    prepared = preparation_from_document(v["preparation"])
    _need(
        prepared.sha256 == v["preparation_sha256"]
        and v["provenance"]
        == (
            "INCAPABLE_USB_QUERY"
            if type(prepared) is PreparedIncapableUsbIdentity
            else "PHYSICAL_USB_QUERY"
        ),
        "USB_EVIDENCE_PREPARATION",
    )
    for name in (
        "original_deadline_ns",
        "started_monotonic_ns",
        "finished_monotonic_ns",
        "started_utc_ns",
        "finished_utc_ns",
    ):
        _need(type(v[name]) is int and 0 < v[name] < 2**63, "USB_EVIDENCE_TIME")
    _need(
        v["finished_monotonic_ns"] >= v["started_monotonic_ns"], "USB_CLOCK_REGRESSION"
    )
    for name in (
        "owner_constructed",
        "release_write_attempted",
        "release_check_passed",
        "release_delivery_confirmed",
        "result_validated",
    ):
        _need(type(v[name]) is bool, "USB_EVIDENCE_BOOLEAN")
    _need(
        v["physical_authority"] is False
        and v["hardware_qualified"] is False
        and type(v["retries"]) is int
        and v["retries"] == 0,
        "USB_EVIDENCE_NO_AUTHORITY",
    )
    errors = v["cleanup_errors"]
    _need(
        type(errors) is list
        and len(errors) <= MAX_CLEANUP_ERRORS
        and all(type(x) is str and _CODE.fullmatch(x) for x in errors)
        and len(errors) == len(set(errors)),
        "USB_CLEANUP_ERRORS",
    )
    _need(
        v["primary_error"] is None
        or type(v["primary_error"]) is str
        and bool(_CODE.fullmatch(v["primary_error"])),
        "USB_PRIMARY_ERROR",
    )
    p = v["process"]
    _need(type(p) is dict and set(p) == set(PROCESS_DEFAULTS), "USB_PROCESS_FIELDS")
    for name, default in PROCESS_DEFAULTS.items():
        if name == "returncode":
            _need(
                p[name] is None or type(p[name]) is int and -(2**31) <= p[name] < 2**32,
                "USB_PROCESS_EXIT",
            )
        elif type(default) is bool:
            _need(type(p[name]) is bool, "USB_PROCESS_BOOLEAN")
        else:
            _need(type(p[name]) is int and 0 <= p[name] < 2**32, "USB_PROCESS_COUNTER")
    _need(not p["resumed"] or p["created"], "USB_PROCESS_RESUME")
    _need(
        not p["created"] or v["owner_constructed"] and p["pid"] > 0, "USB_PROCESS_OWNER"
    )
    stdout, stderr = stream_bytes(v["stdout"], 66 * 1024), stream_bytes(
        v["stderr"], 4 * 1024
    )
    _need(
        type(v["ready_length"]) is int
        and 0 <= v["ready_length"] <= min(1024, len(stdout)),
        "USB_READY_LENGTH",
    )
    release = stream_bytes(v["release_wire"], 1024)
    ready: UsbIdentityReady | None = None
    if v["ready_length"]:
        ready = parse_usb_identity_ready(
            stdout[: v["ready_length"]],
            expected_request_sha256=prepared.request.request_sha256,
            expected_child_pid=p["pid"],
        )
    if release:
        _need(
            ready is not None
            and release == usb_identity_release(prepared.request, ready),
            "USB_RELEASE_EXACT_BYTES",
        )
    _need(
        not v["release_check_passed"] or ready is not None and bool(release),
        "USB_RELEASE_WITHOUT_READY",
    )
    _need(
        not v["release_write_attempted"] or v["release_check_passed"],
        "USB_UNCHECKED_RELEASE",
    )
    _need(
        not v["release_delivery_confirmed"]
        or v["release_write_attempted"]
        and p["written"] == len(prepared.request.wire()) + len(release),
        "USB_RELEASE_DELIVERY",
    )
    _need(
        not v["result_validated"] or v["release_write_attempted"] and ready is not None,
        "USB_RESULT_WITHOUT_RELEASE",
    )
    checks = v["scope_checks"]
    _need(type(checks) is list and len(checks) <= 5, "USB_SCOPE_CHECK_BOUND")
    last = v["started_monotonic_ns"]
    for n, check in enumerate(checks):
        _need(
            type(check) is dict
            and set(check) == {"boundary", "started_ns", "finished_ns", "passed"}
            and check["boundary"] == BOUNDARIES[n]
            and type(check["passed"]) is bool,
            "USB_SCOPE_CHECK_FIELDS",
        )
        _need(
            type(check["started_ns"]) is int
            and type(check["finished_ns"]) is int
            and last
            <= check["started_ns"]
            <= check["finished_ns"]
            <= v["finished_monotonic_ns"],
            "USB_SCOPE_CHECK_TIME",
        )
        _need(check["passed"] or n == len(checks) - 1, "USB_SCOPE_CHECK_AFTER_FAILURE")
        last = check["finished_ns"]
    observation = _observation(v, prepared)
    _need(v["status"] == _status(v, observation), "USB_STATUS_DERIVED")
    if v["status"] in {"OBSERVED", "HELD"}:
        _need(
            len(checks) == 5
            and all(c["passed"] for c in checks)
            and v["release_delivery_confirmed"]
            and p["created"]
            and p["resumed"]
            and p["tree_exited"]
            and p["peak_processes"] <= prepared.registration.budget.process_count
            and p["peak_handles"]
            <= prepared.registration.budget.observed_handles_per_process
            and p["stdout_eof"]
            and p["stderr_eof"]
            and v["stdout"]["complete"]
            and v["stderr"]["complete"]
            and v["finished_monotonic_ns"] < v["original_deadline_ns"]
            and v["finished_utc_ns"] >= v["started_utc_ns"],
            "USB_OBSERVED_LIFECYCLE",
        )
    if not v["owner_constructed"]:
        _need(
            canonical(p) == canonical(PROCESS_DEFAULTS)
            and not stdout
            and not stderr
            and not release,
            "USB_EFFECT_WITHOUT_OWNER",
        )
    return v


@dataclass(frozen=True, slots=True)
class OwnedUsbIdentityRunEvidence:
    payload: bytes

    def __post_init__(self) -> None:
        _validate(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _validate(self.payload)

    @property
    def preparation(self) -> Preparation:
        return preparation_from_document(self.to_dict()["preparation"])

    @property
    def observation(self) -> UsbIdentityObservation | None:
        v = self.to_dict()
        return _observation(v, preparation_from_document(v["preparation"]))

    @property
    def status(self) -> str:
        return self.to_dict()["status"]

    @property
    def error(self) -> str | None:
        return self.to_dict()["primary_error"]

    @property
    def released(self) -> bool:
        return self.to_dict()["release_delivery_confirmed"]

    @property
    def no_attempt(self) -> bool:
        v = self.to_dict()
        return (
            not v["owner_constructed"]
            or v["process"]["observation_complete"]
            and not v["process"]["created"]
        )

    @property
    def process_cleanup_confirmed(self) -> bool:
        return _process_clean(self.to_dict())

    @property
    def usb_cleanup_confirmed(self) -> bool:
        o = self.observation
        if o is None:
            return False
        c = o.to_dict()["accounting"]
        return (
            c["remaining_open_handles"] == 0
            and c["hub_open_successes"] == c["close_successes"] == c["close_attempts"]
        )

    @property
    def actual_counts(self) -> dict[str, int] | None:
        o = self.observation
        if o is not None:
            return o.to_dict()["accounting"]
        if self.no_attempt:
            return {
                key: 0
                for key in (
                    "api_calls",
                    "hub_open_attempts",
                    "hub_open_successes",
                    "ioctl_attempts",
                    "ioctl_successes",
                    "descriptor_requests",
                    "close_attempts",
                    "close_successes",
                    "peak_open_handles",
                    "remaining_open_handles",
                    "returned_bytes",
                )
            }
        return None

    def safe_summary(self) -> dict[str, Any]:
        v = self.to_dict()
        effect = self.bounded_effect_summary()
        return {
            "schema": "rocell.owned_usb_identity_run_summary.v1",
            "evidence_sha256": self.sha256,
            "preparation_sha256": v["preparation_sha256"],
            "status": v["status"],
            "provenance": v["provenance"],
            "released": effect["released"],
            "no_attempt": effect["no_attempt"],
            "counter_coverage": (
                "NATIVE_RECEIPT"
                if v["result_validated"]
                else "NO_PROCESS_CREATED" if effect["no_attempt"] else "NOT_REPORTED"
            ),
            "actual_counts": effect["actual_counts"],
            "process_cleanup_confirmed": effect["process_cleanup_confirmed"],
            "usb_cleanup_confirmed": effect["usb_cleanup_confirmed"],
            "error": v["primary_error"],
            "cleanup_errors": v["cleanup_errors"],
            "physical_authority": False,
            "hardware_qualified": False,
            "retries": 0,
        }

    def bounded_effect_summary(self) -> dict[str, Any]:
        """One checked projection for effect mapping, not stage qualification."""
        v = self.to_dict()
        observation = _observation(v, preparation_from_document(v["preparation"]))
        no_attempt = not v["owner_constructed"] or (
            v["process"]["observation_complete"] and not v["process"]["created"]
        )
        counts = None if observation is None else observation.to_dict()["accounting"]
        native_outcome = (
            None if observation is None else observation.to_dict()["outcome"]
        )
        usb_clean = (
            counts is not None
            and counts["remaining_open_handles"] == 0
            and (
                counts["hub_open_successes"]
                == counts["close_successes"]
                == counts["close_attempts"]
            )
        )
        if counts is None and no_attempt:
            counts = {
                key: 0
                for key in (
                    "api_calls",
                    "hub_open_attempts",
                    "hub_open_successes",
                    "ioctl_attempts",
                    "ioctl_successes",
                    "descriptor_requests",
                    "close_attempts",
                    "close_successes",
                    "peak_open_handles",
                    "remaining_open_handles",
                    "returned_bytes",
                )
            }
        return {
            "status": v["status"],
            "current_complete": v["status"] in {"OBSERVED", "HELD"},
            "native_outcome": native_outcome,
            "actual_counts": counts,
            "no_attempt": no_attempt,
            "released": v["release_delivery_confirmed"],
            "process_cleanup_confirmed": _process_clean(v),
            "usb_cleanup_confirmed": usb_clean,
        }


def retain_owned_usb_identity_run(value: dict[str, Any]) -> OwnedUsbIdentityRunEvidence:
    """Internal runner finalization; derive validity from retained original bytes."""
    prepared = preparation_from_document(value["preparation"])
    value["result_validated"] = False
    if value["release_write_attempted"] and value["ready_length"]:
        try:
            candidate = dict(value, result_validated=True)
            _observation(candidate, prepared)
            value["result_validated"] = True
        except (ValueError, TypeError, KeyError):
            pass
    observation = _observation(value, prepared)
    value["status"] = _status(value, observation)
    return OwnedUsbIdentityRunEvidence(canonical(value))


def verify_owned_usb_identity_run_evidence(
    value: bytes | OwnedUsbIdentityRunEvidence,
    *,
    expected_preparation_sha256: str,
    expected_evidence_sha256: str,
) -> OwnedUsbIdentityRunEvidence:
    _need(
        type(expected_preparation_sha256) is str
        and bool(_SHA.fullmatch(expected_preparation_sha256))
        and type(expected_evidence_sha256) is str
        and bool(_SHA.fullmatch(expected_evidence_sha256)),
        "TRUSTED_USB_EVIDENCE_HASHES",
    )
    result = OwnedUsbIdentityRunEvidence(
        value.payload
        if type(value) is OwnedUsbIdentityRunEvidence
        else cast(bytes, value)
    )
    _need(
        result.sha256 == expected_evidence_sha256
        and result.to_dict()["preparation_sha256"] == expected_preparation_sha256,
        "TRUSTED_USB_EVIDENCE_MISMATCH",
    )
    return result
