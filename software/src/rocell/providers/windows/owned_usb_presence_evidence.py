"""Pure original owned USB execution evidence; never replays a process or USB call.

Native receipt bytes remain in the original bounded stdout. Re-parsing those
bytes avoids retaining a second mutable/synthetic copy of the observation.
The presence helper cannot open device handles; process cleanup is still a
separate measured obligation. A partial stream never supplies absence or counts.
"""

from __future__ import annotations
import base64
from dataclasses import dataclass
import re
from typing import Any, cast
from .owned_worker_process import decode_owned_json
from .usb_presence_protocol import (
    UsbPresenceObservation,
    canonical,
    digest,
    decode_usb_presence_ready,
    decode_usb_presence_result,
    encode_usb_presence_release,
)
from .usb_presence_registration import (
    Preparation,
    PreparedOwnedUsbPresence,
    PreparedIncapableUsbPresence,
    PREPARATION_SCHEMA,
)

SCHEMA = "rocell.owned_usb_presence_run.v1"
MAX_EVIDENCE_BYTES = 128 * 1024
# The owner returns at most 32 codes. Four reserved supervisor conditions may
# be appended without discarding any original cleanup failure.
MAX_OWNER_CLEANUP_ERRORS = 32
MAX_CLEANUP_ERRORS = MAX_OWNER_CLEANUP_ERRORS + 4
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


class OwnedUsbPresenceEvidenceError(ValueError):
    pass


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise OwnedUsbPresenceEvidenceError(code)


def stream_record(
    raw: bytes, *, complete: bool, owner_limit_exceeded: bool = False
) -> dict[str, Any]:
    _need(type(raw) is bytes and type(complete) is bool, "EXACT_USB_STREAM")
    _need(
        type(owner_limit_exceeded) is bool and not (complete and owner_limit_exceeded),
        "EXACT_STREAM_COVERAGE",
    )
    return {
        "length_bytes": len(raw),
        "sha256": digest(raw),
        "complete": complete,
        # The low-level owner preserves a bounded prefix on overflow. It does
        # not report the discarded tail length or hash; neither is invented.
        "coverage": (
            "FULL_STREAM"
            if complete
            else "OWNER_LIMIT_PREFIX" if owner_limit_exceeded else "PREFIX_ONLY"
        ),
        "total_length_bytes": len(raw) if complete else None,
        "total_sha256": digest(raw) if complete else None,
        "base64_chunks": [
            base64.b64encode(raw[i : i + 16384]).decode("ascii")
            for i in range(0, len(raw), 16384)
        ],
    }


def stream_bytes(value: Any, maximum: int) -> bytes:
    _need(
        type(value) is dict
        and set(value)
        == {
            "length_bytes",
            "sha256",
            "complete",
            "base64_chunks",
            "coverage",
            "total_length_bytes",
            "total_sha256",
        },
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
        raise OwnedUsbPresenceEvidenceError("USB_STREAM_ENCODING") from e
    _need(
        len(raw) == value["length_bytes"]
        and digest(raw) == value["sha256"]
        and canonical(
            stream_record(
                raw,
                complete=value["complete"],
                owner_limit_exceeded=value["coverage"] == "OWNER_LIMIT_PREFIX",
            )
        )
        == canonical(value),
        "USB_STREAM_ORIGINAL_HASH",
    )
    return raw


def preparation_from_document(value: dict[str, Any]) -> Preparation:
    _need(type(value) is dict, "EXACT_USB_PREPARATION_DOCUMENT")
    cls = (
        PreparedOwnedUsbPresence
        if value.get("schema") == PREPARATION_SCHEMA
        else PreparedIncapableUsbPresence
    )
    return cls(canonical(value))


def checked_result(
    raw: bytes, prepared: Preparation, ready: dict[str, Any], returncode: int | None
) -> UsbPresenceObservation:
    observation = decode_usb_presence_result(
        raw,
        prepared.request,
        child_pid=ready["child_pid"],
        challenge=ready["challenge"],
        expected_provider=(
            "INCAPABLE_FIXTURE"
            if type(prepared) is PreparedIncapableUsbPresence
            else "WINDOWS_CONFIGURATION_MANAGER"
        ),
    )
    _need(
        returncode == (1 if observation.to_dict()["outcome"] == "HELD" else 0),
        "PRESENCE_NATIVE_EXIT_MISMATCH",
    )
    return observation


def _observation(
    v: dict[str, Any], prepared: Preparation
) -> UsbPresenceObservation | None:
    if not v["result_validated"]:
        return None
    _need(v["stdout"]["complete"], "INCOMPLETE_PRESENCE_RESULT_STREAM")
    stdout = stream_bytes(v["stdout"], 66 * 1024)
    accepted = stream_bytes(v["ready_wire"], 1024)
    _need(stdout.startswith(accepted), "PRESENCE_READY_PREFIX_CHANGED")
    ready = _ready(accepted, prepared, v["process"]["pid"])
    return checked_result(
        stdout[v["ready_length"] :], prepared, ready, v["process"]["returncode"]
    )


def _ready(raw: bytes, prepared: Preparation, pid: int) -> dict[str, Any]:
    _need(raw.endswith(b"\n"), "PRESENCE_READY_LINE_TERMINATOR")
    return decode_usb_presence_ready(raw[:-1], prepared.request, child_pid=pid)


def _process_clean(v: dict[str, Any]) -> bool:
    p = v["process"]
    return bool(
        v["owner_constructed"]
        and v["cleanup_started_ns"] is not None
        and v["cleanup_deadline_ns"] is not None
        and v["cleanup_finished_ns"] is not None
        and v["cleanup_started_ns"]
        <= v["cleanup_finished_ns"]
        <= v["cleanup_deadline_ns"]
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


def _status(v: dict[str, Any], observation: UsbPresenceObservation | None) -> str:
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
            "run_deadline_ns",
            "cleanup_started_ns",
            "cleanup_deadline_ns",
            "cleanup_finished_ns",
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
            "ready_wire",
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
            "INCAPABLE_USB_PRESENCE"
            if type(prepared) is PreparedIncapableUsbPresence
            else "PHYSICAL_USB_PRESENCE"
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
    permit = prepared.permit
    _need(
        permit.issued_at_ns < v["original_deadline_ns"] <= permit.expires_at_ns
        and v["original_deadline_ns"] <= v["started_monotonic_ns"] + 25_000_000_000,
        "PRESENCE_ORIGINAL_DEADLINE_OUTSIDE_PERMIT",
    )
    for name in (
        "run_deadline_ns",
        "cleanup_started_ns",
        "cleanup_deadline_ns",
        "cleanup_finished_ns",
    ):
        _need(
            v[name] is None or type(v[name]) is int and 0 < v[name] < 2**63,
            "PRESENCE_OWNED_CUTOFF_TIME",
        )
    _need(
        v["run_deadline_ns"] is None
        or v["run_deadline_ns"] <= v["original_deadline_ns"] - 2_000_000_000,
        "PRESENCE_RUN_CLEANUP_RESERVE",
    )
    _need(
        (v["cleanup_started_ns"] is None) == (v["cleanup_deadline_ns"] is None)
        and (v["cleanup_started_ns"] is not None or v["cleanup_finished_ns"] is None),
        "PRESENCE_CLEANUP_INTERVAL_FIELDS",
    )
    if v["cleanup_started_ns"] is not None:
        _need(
            v["started_monotonic_ns"]
            <= v["cleanup_started_ns"]
            <= v["finished_monotonic_ns"]
            and v["cleanup_deadline_ns"]
            == min(v["original_deadline_ns"], v["cleanup_started_ns"] + 2_000_000_000),
            "PRESENCE_CLEANUP_ORIGINAL_CUTOFF",
        )
    if v["cleanup_finished_ns"] is not None:
        _need(
            v["cleanup_started_ns"]
            <= v["cleanup_finished_ns"]
            <= v["finished_monotonic_ns"],
            "PRESENCE_CLEANUP_OBSERVED_INTERVAL",
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
        type(v["ready_length"]) is int and 0 <= v["ready_length"] <= 1024,
        "USB_READY_LENGTH",
    )
    accepted = stream_bytes(v["ready_wire"], 1024)
    _need(
        len(accepted) == v["ready_length"] and v["ready_wire"]["complete"],
        "PRESENCE_ACCEPTED_READY_BYTES",
    )
    release = stream_bytes(v["release_wire"], 1024)
    _need(
        p["created"]
        or p["pid"] == p["written"] == p["peak_processes"] == 0
        and not v["ready_length"]
        and not release
        and not v["release_write_attempted"],
        "PRESENCE_EFFECT_WITHOUT_CREATED_PROCESS",
    )
    ready: dict[str, Any] | None = None
    if v["ready_length"]:
        ready = _ready(accepted, prepared, p["pid"])
    if release:
        _need(
            ready is not None
            and release
            == encode_usb_presence_release(ready, prepared.request, child_pid=p["pid"])
            + b"\n",
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
        and p["written"] == len(prepared.request.payload) + 1 + len(release),
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
    if v["status"] in {"PRESENT", "ABSENT", "HELD"}:
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
        _need(
            v["run_deadline_ns"] is not None
            and checks[4]["finished_ns"]
            < v["run_deadline_ns"]
            <= checks[2]["started_ns"] + 13_000_000_000
            and v["cleanup_started_ns"] is not None
            and checks[4]["finished_ns"] <= v["cleanup_started_ns"],
            "PRESENCE_RUN_ORIGINAL_CUTOFF",
        )
        assert observation is not None
        native = observation.to_dict()
        _need(
            prepared.review.to_dict()["reviewed_at_ns"]
            <= v["started_utc_ns"]
            <= native["started"]["utc_ns"]
            <= native["finished"]["utc_ns"]
            <= v["finished_utc_ns"],
            "PRESENCE_OBSERVATION_OUTSIDE_OWNED_INTERVAL",
        )
    if not v["owner_constructed"]:
        _need(
            canonical(p) == canonical(PROCESS_DEFAULTS)
            and not stdout
            and not stderr
            and not release
            and not accepted
            and all(
                v[name] is None
                for name in (
                    "run_deadline_ns",
                    "cleanup_started_ns",
                    "cleanup_deadline_ns",
                    "cleanup_finished_ns",
                )
            ),
            "USB_EFFECT_WITHOUT_OWNER",
        )
    return v


@dataclass(frozen=True, slots=True)
class OwnedUsbPresenceRunEvidence:
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
    def observation(self) -> UsbPresenceObservation | None:
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
    def native_cleanup_confirmed(self) -> bool:
        return self.bounded_effect_summary()["native_cleanup_confirmed"]

    @property
    def actual_counts(self) -> dict[str, int] | None:
        return self.bounded_effect_summary()["actual_counts"]

    def bounded_effect_summary(self) -> dict[str, Any]:
        v = self.to_dict()
        observation = _observation(v, preparation_from_document(v["preparation"]))
        no_attempt = not v["owner_constructed"] or (
            v["process"]["observation_complete"] and not v["process"]["created"]
        )
        observed = None if observation is None else observation.to_dict()
        counts = (
            {
                key: observed[key]
                for key in (
                    "api_calls",
                    "device_handle_opens",
                    "configuration_writes",
                    "frames",
                )
            }
            if observed is not None
            else (
                dict.fromkeys(
                    (
                        "api_calls",
                        "device_handle_opens",
                        "configuration_writes",
                        "frames",
                    ),
                    0,
                )
                if no_attempt
                else None
            )
        )
        return dict(
            status=v["status"],
            current_complete=v["status"] in {"PRESENT", "ABSENT", "HELD"},
            native_outcome=None if observed is None else observed["outcome"],
            actual_counts=counts,
            no_attempt=no_attempt,
            released=v["release_delivery_confirmed"],
            process_cleanup_confirmed=_process_clean(v),
            native_cleanup_confirmed=observed is not None
            and observed["device_handle_opens"] == 0,
        )

    def safe_summary(self) -> dict[str, Any]:
        v = self.to_dict()
        effect = self.bounded_effect_summary()
        return dict(
            schema="rocell.owned_usb_presence_run_summary.v1",
            evidence_sha256=self.sha256,
            preparation_sha256=v["preparation_sha256"],
            provenance=v["provenance"],
            **effect,
            counter_coverage=(
                "NATIVE_RECEIPT"
                if v["result_validated"]
                else "NO_PROCESS_CREATED" if effect["no_attempt"] else "NOT_REPORTED"
            ),
            error=v["primary_error"],
            cleanup_errors=v["cleanup_errors"],
            physical_authority=False,
            hardware_qualified=False,
            retries=0,
        )


def retain_owned_usb_presence_run(value: dict[str, Any]) -> OwnedUsbPresenceRunEvidence:
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
    if observation is not None and value["primary_error"] is None:
        native = observation.to_dict()
        if not (
            prepared.review.to_dict()["reviewed_at_ns"]
            <= value["started_utc_ns"]
            <= native["started"]["utc_ns"]
            <= native["finished"]["utc_ns"]
            <= value["finished_utc_ns"]
        ):
            value["primary_error"] = "PRESENCE_OBSERVATION_OUTSIDE_OWNED_INTERVAL"
    value["status"] = _status(value, observation)
    return OwnedUsbPresenceRunEvidence(canonical(value))


def verify_owned_usb_presence_run_evidence(
    value: bytes | OwnedUsbPresenceRunEvidence,
    *,
    expected_preparation_sha256: str,
    expected_evidence_sha256: str,
) -> OwnedUsbPresenceRunEvidence:
    _need(
        type(expected_preparation_sha256) is str
        and bool(_SHA.fullmatch(expected_preparation_sha256))
        and type(expected_evidence_sha256) is str
        and bool(_SHA.fullmatch(expected_evidence_sha256)),
        "TRUSTED_USB_EVIDENCE_HASHES",
    )
    result = OwnedUsbPresenceRunEvidence(
        value.payload
        if type(value) is OwnedUsbPresenceRunEvidence
        else cast(bytes, value)
    )
    _need(
        result.sha256 == expected_evidence_sha256
        and result.to_dict()["preparation_sha256"] == expected_preparation_sha256,
        "TRUSTED_USB_EVIDENCE_MISMATCH",
    )
    return result
