"""Bounded lossless-retained native admission evidence, with a pure verifier.

Trusted callers provide independent evidence and preparation digests. Validation
checks retained facts; it cannot prove an OS effect happened or qualify hardware.
Pipes retain exactly the bytes available from the bounded owner, not imaginary
complete child output after a timeout/overflow. Unknown omitted bytes stay None.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import re
from typing import Any, TYPE_CHECKING

from .native_camera_protocol import (
    canonical,
    digest,
    parse_native_camera_ready,
    native_camera_release,
    parse_owned_native_camera_result,
)
from .native_camera_registration import PreparedOwnedNativeProbe
from .camera_worker_client import NativeCameraReceipt, NativeCameraReceiptMetadata
from .owned_worker_process import decode_owned_json, owned_registration_document

if TYPE_CHECKING:
    from .native_camera_capture_registration import PreparedOwnedNativeCapture

SCHEMA = "rocell.owned_native_camera_run_evidence.v1"
CAPTURE_SCHEMA = "rocell.owned_native_camera_capture_run_evidence.v1"
MAX_EVIDENCE_BYTES = 128 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_CODE = re.compile(r"[A-Za-z0-9_:-]{1,128}\Z")
_OBSERVATION_DEFAULTS = {
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
}


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def _uint(value: Any, maximum: int = 2**63 - 1) -> None:
    _require(type(value) is int and 0 <= value <= maximum, "EVIDENCE_INTEGER")


def _wire(data: bytes, *, complete: bool) -> dict[str, Any]:
    return {
        "base64": base64.b64encode(data).decode("ascii"),
        "retained_bytes": len(data),
        "retained_sha256": digest(data),
        "capture_complete": complete,
        "omitted_bytes_exact": 0 if complete else None,
    }


def _read_wire(value: Any, maximum: int) -> bytes:
    _require(
        type(value) is dict
        and set(value)
        == {
            "base64",
            "retained_bytes",
            "retained_sha256",
            "capture_complete",
            "omitted_bytes_exact",
        },
        "PIPE_EVIDENCE_SCHEMA",
    )
    _require(
        type(value["base64"]) is str
        and len(value["base64"]) <= 4 * ((maximum + 2) // 3),
        "PIPE_BASE64_LIMIT",
    )
    try:
        data = base64.b64decode(value["base64"], validate=True)
    except Exception as exc:
        raise ValueError("PIPE_BASE64_INVALID") from exc
    _uint(value["retained_bytes"], maximum)
    _require(
        len(data) == value["retained_bytes"]
        and digest(data) == value["retained_sha256"]
        and base64.b64encode(data).decode("ascii") == value["base64"],
        "PIPE_BYTES_HASH",
    )
    _require(type(value["capture_complete"]) is bool, "PIPE_COMPLETENESS_BOOL")
    if value["capture_complete"]:
        _require(
            type(value["omitted_bytes_exact"]) is int
            and value["omitted_bytes_exact"] == 0,
            "PIPE_OMISSION_ACCOUNTING",
        )
    else:
        _require(value["omitted_bytes_exact"] is None, "PIPE_OMISSION_UNKNOWN")
    return data


def _status(
    primary: str | None, cleanup: list[str], *, native: bool, fixture: bool
) -> str:
    if primary == "PHYSICAL_PROVIDER_QUALIFICATION_HELD":
        return "HELD"
    if primary == "CANCELLED":
        return "CANCELLED"
    if primary in {
        "TIMED_OUT",
        "PARENT_DEADLINE_EXPIRED",
        "ADMISSION_DEADLINE_EXPIRED",
    }:
        return "TIMED_OUT"
    if primary or cleanup:
        return "FAILED"
    if native:
        return "SUCCEEDED_NATIVE_DIAGNOSTIC"
    if fixture:
        return "SUCCEEDED_ADMISSION_ONLY"
    return "FAILED"


def _preparation(
    value: dict[str, Any], *, capture: bool
) -> PreparedOwnedNativeProbe | PreparedOwnedNativeCapture:
    if capture:
        from .native_camera_capture_registration import PreparedOwnedNativeCapture

        return PreparedOwnedNativeCapture(canonical(value))
    return PreparedOwnedNativeProbe(canonical(value))


def _release(probe: Any, ready: Any) -> bytes:
    if type(probe) is PreparedOwnedNativeProbe:
        return native_camera_release(probe.admission_request, ready)
    from .native_camera_capture_protocol import native_camera_capture_release

    return native_camera_capture_release(probe.admission_request, ready)


def _native_result(
    probe: Any, wire: bytes, *, ready: Any, returncode: int
) -> tuple[dict[str, Any], NativeCameraReceipt | NativeCameraReceiptMetadata]:
    if type(probe) is PreparedOwnedNativeProbe:
        return parse_owned_native_camera_result(
            wire, request=probe.admission_request, ready=ready, returncode=returncode
        )
    from .native_camera_capture_protocol import parse_owned_native_camera_capture_result

    return parse_owned_native_camera_capture_result(
        wire, request=probe.admission_request, ready=ready, returncode=returncode
    )


def _validate(payload: bytes) -> dict[str, Any]:
    from .owned_native_camera_runner import (
        PreparedIncapableNativeAdmission,
        validate_incapable_completion,
    )

    _require(type(payload) is bytes, "EXACT_EVIDENCE_BYTES")
    data = decode_owned_json(payload, maximum=MAX_EVIDENCE_BYTES)
    _require(
        canonical(data) == payload
        and set(data)
        == {
            "schema",
            "preparation",
            "preparation_sha256",
            "fixture_preparation",
            "registration",
            "registration_sha256",
            "source_sha256",
            "parent_deadline_ns",
            "elapsed_ns",
            "primary_error",
            "cleanup_errors",
            "owner_constructed",
            "process",
            "stdout",
            "stderr",
            "ready_wire",
            "release_wire",
            "release_check_passed",
            "native_validated",
            "admission_only_validated",
            "validated_result",
            "handshake",
            "status",
            "provenance",
            "physical_authority",
            "hardware_qualified",
            "final_power_state",
        },
        "EVIDENCE_SCHEMA",
    )
    _require(data["schema"] in {SCHEMA, CAPTURE_SCHEMA}, "EVIDENCE_VERSION")
    capture = data["schema"] == CAPTURE_SCHEMA
    probe = _preparation(data["preparation"], capture=capture)
    _require(
        probe.preparation_sha256 == data["preparation_sha256"]
        and data["source_sha256"] == probe.admission_request.to_dict()["source_sha256"],
        "EVIDENCE_SOURCE_BINDING",
    )
    fixture = None
    if data["fixture_preparation"] is not None:
        _require(not capture, "CAPTURE_CANNOT_RELABEL_ADMISSION_FIXTURE")
        fixture = PreparedIncapableNativeAdmission(
            canonical(data["fixture_preparation"])
        )
        _require(fixture.probe.payload == probe.payload, "EVIDENCE_FIXTURE_BINDING")
    registration = fixture.registration if fixture else probe.registration
    expected_reg = owned_registration_document(registration)
    _require(
        data["registration"] == expected_reg
        and data["registration_sha256"] == digest(canonical(expected_reg)),
        "EVIDENCE_REGISTRATION_BINDING",
    )
    _require(
        data["provenance"]
        == ("INCAPABLE_NATIVE_ADMISSION_ONLY" if fixture else "PHYSICAL_UNQUALIFIED"),
        "EVIDENCE_PROVENANCE",
    )
    _require(
        data["physical_authority"] is False
        and data["hardware_qualified"] is False
        and data["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
        "EVIDENCE_PHYSICAL_HOLD",
    )
    for key in (
        "owner_constructed",
        "release_check_passed",
        "native_validated",
        "admission_only_validated",
    ):
        _require(type(data[key]) is bool, "EVIDENCE_LITERAL_BOOL")
    _require(
        not (data["native_validated"] and data["admission_only_validated"])
        and (not data["native_validated"] or fixture is None)
        and (not data["admission_only_validated"] or fixture is not None),
        "EVIDENCE_RESULT_DOMAIN",
    )
    primary = data["primary_error"]
    _require(
        primary is None or (type(primary) is str and bool(_CODE.fullmatch(primary))),
        "EVIDENCE_ERROR_LABEL",
    )
    cleanup = data["cleanup_errors"]
    _require(
        type(cleanup) is list
        and len(cleanup) <= 260
        and all(type(code) is str and bool(_CODE.fullmatch(code)) for code in cleanup)
        and len(set(cleanup)) == len(cleanup),
        "EVIDENCE_CLEANUP_ERRORS",
    )
    if data["parent_deadline_ns"] is not None:
        _uint(data["parent_deadline_ns"])
    _uint(data["elapsed_ns"])
    p = data["process"]
    _require(
        type(p) is dict and set(p) == set(_OBSERVATION_DEFAULTS),
        "PROCESS_OBSERVATIONS_SCHEMA",
    )
    for key, default in _OBSERVATION_DEFAULTS.items():
        if key == "returncode":
            _require(
                p[key] is None or (type(p[key]) is int and -(2**31) <= p[key] < 2**32),
                "PROCESS_EXIT_CODE",
            )
        elif type(default) is bool:
            _require(type(p[key]) is bool, "PROCESS_LITERAL_BOOL")
        else:
            _uint(p[key])
    _uint(p["pid"], 2**32 - 1)
    _uint(p["written"], registration.budget.stdin_bytes)
    _uint(p["peak_processes"], registration.budget.process_count)
    _require(not p["resumed"] or p["created"], "RESUME_WITHOUT_PROCESS")
    _require(not p["written"] or p["resumed"], "WRITE_WITHOUT_RESUME")
    _require(not p["created"] or p["pid"] > 0, "CREATED_PROCESS_PID")
    _require(
        data["owner_constructed"] or p == _OBSERVATION_DEFAULTS,
        "OBSERVATIONS_WITHOUT_OWNER",
    )
    stdout = _read_wire(data["stdout"], registration.budget.stdout_bytes)
    stderr = _read_wire(data["stderr"], registration.budget.stderr_bytes)
    ready_wire = _read_wire(data["ready_wire"], 1024)
    release_wire = _read_wire(data["release_wire"], 1024)
    for name in ("stdout", "stderr"):
        expected_complete = (
            data["owner_constructed"]
            and p[name + "_eof"]
            and primary != name.upper() + "_LIMIT"
        )
        _require(
            data[name]["capture_complete"] == expected_complete,
            "PIPE_COMPLETENESS_OBSERVATION",
        )
    _require(
        data["ready_wire"]["capture_complete"]
        and data["release_wire"]["capture_complete"],
        "MESSAGE_RETENTION_INCOMPLETE",
    )
    _require(
        not ready_wire or stdout.startswith(ready_wire), "READY_NOT_RETAINED_IN_STDOUT"
    )
    if release_wire:
        ready = parse_native_camera_ready(
            ready_wire,
            expected_request_sha256=probe.admission_request.request_sha256,
            expected_child_pid=p["pid"],
        )
        _require(
            release_wire == _release(probe, ready),
            "RELEASE_WIRE_BINDING",
        )
    else:
        ready = None
    _require(
        not data["release_check_passed"] or (ready is not None and p["resumed"]),
        "RELEASE_CHECK_WITHOUT_READY",
    )
    _require(
        p["written"] <= len(probe.admission_request.wire()) + len(release_wire),
        "STDIN_ACCOUNTING",
    )
    _require(
        p["written"] <= len(probe.admission_request.wire())
        or data["release_check_passed"],
        "RELEASE_WRITE_BEFORE_CHECK",
    )
    if not data["owner_constructed"]:
        _require(
            not stdout
            and not stderr
            and not ready_wire
            and not release_wire
            and data["handshake"] is None,
            "PIPE_OR_HANDSHAKE_WITHOUT_OWNER",
        )
    if data["handshake"] is not None:
        h = data["handshake"]
        _require(
            type(h) is dict
            and set(h)
            == {
                "schema",
                "state",
                "preparation_sha256",
                "physical_dispatch_enabled",
                "physical_authority",
                "device_cleanup_confirmed",
                "final_power_state",
                "retries",
            }
            and h["schema"] == "rocell.native_camera_parent_handshake.v1"
            and h["preparation_sha256"] == probe.preparation_sha256
            and type(h["state"]) is str
            and bool(_CODE.fullmatch(h["state"]))
            and all(
                h[k] is False
                for k in (
                    "physical_dispatch_enabled",
                    "physical_authority",
                    "device_cleanup_confirmed",
                )
            )
            and h["final_power_state"] == data["final_power_state"]
            and type(h["retries"]) is int
            and h["retries"] == 0,
            "HANDSHAKE_RETAINED_SCHEMA",
        )
    validated = data["native_validated"] or data["admission_only_validated"]
    _require(
        (data["validated_result"] is not None) == validated, "RESULT_VALIDATION_CLAIM"
    )
    if validated:
        _require(
            ready is not None
            and data["release_check_passed"]
            and p["tree_exited"]
            and p["written"] == len(probe.admission_request.wire()) + len(release_wire)
            and p["stdout_eof"]
            and p["stderr_eof"]
            and not p["pending"],
            "INCOMPLETE_RESULT_DELIVERY",
        )
        assert ready is not None
        result_wire = stdout[len(ready_wire) :]
        raw = decode_owned_json(result_wire, maximum=registration.budget.stdout_bytes)
        _require(raw == data["validated_result"], "RESULT_RAW_BINDING")
        if data["admission_only_validated"]:
            validate_incapable_completion(
                raw,
                request_sha256=probe.admission_request.request_sha256,
                child_pid=p["pid"],
                challenge_sha256=ready.challenge_sha256,
                returncode=p["returncode"],
            )
        else:
            _, receipt = _native_result(
                probe,
                result_wire,
                ready=ready,
                returncode=p["returncode"],
            )
            if receipt.status != "OK":
                _require(
                    primary is not None or bool(cleanup),
                    "NATIVE_DIAGNOSTIC_FAILURE_WITHOUT_HOLD",
                )
    _require(
        not (
            p["pending"]
            or p["handles_remaining"]
            or p["unclosed_handles_remaining"]
            or p["pins_remaining"]
        )
        or "PROCESS_RESOURCES_RETAINED" in cleanup,
        "RESOURCE_UNCERTAINTY_NOT_RETAINED",
    )
    _require(
        not p["created"]
        or p["tree_exited"]
        or "PROCESS_TREE_EXIT_UNCONFIRMED" in cleanup,
        "TREE_UNCERTAINTY_NOT_RETAINED",
    )
    _require(
        data["status"]
        == _status(
            primary,
            cleanup,
            native=data["native_validated"],
            fixture=data["admission_only_validated"],
        ),
        "EVIDENCE_STATUS_DERIVATION",
    )
    if data["status"] == "HELD":
        _require(
            fixture is None and not data["owner_constructed"], "HELD_PHYSICAL_EFFECT"
        )
    return data


@dataclass(frozen=True, slots=True)
class OwnedNativeCameraRunEvidence:
    payload: bytes

    def __post_init__(self) -> None:
        _validate(self.payload)

    @property
    def evidence_sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _validate(self.payload)

    @property
    def native_receipt(
        self,
    ) -> NativeCameraReceipt | NativeCameraReceiptMetadata | None:
        """Capture returns metadata only: never hashes or reads a frame on reopen."""
        data = self.to_dict()
        if not data["native_validated"]:
            return None
        probe = _preparation(
            data["preparation"], capture=data["schema"] == CAPTURE_SCHEMA
        )
        ready_wire = _read_wire(data["ready_wire"], 1024)
        ready = parse_native_camera_ready(
            ready_wire,
            expected_request_sha256=probe.admission_request.request_sha256,
            expected_child_pid=data["process"]["pid"],
        )
        _, receipt = _native_result(
            probe,
            _read_wire(data["stdout"], probe.registration.budget.stdout_bytes)[
                len(ready_wire) :
            ],
            ready=ready,
            returncode=data["process"]["returncode"],
        )
        return receipt

    def safe_summary(self) -> dict[str, Any]:
        data = self.to_dict()
        p = data["process"]
        receipt = self.native_receipt
        native_cleanup = receipt is not None and receipt.cleanup_confirmed
        summary = {
            "schema": "rocell.owned_native_camera_run_summary.v1",
            "status": data["status"],
            "provenance": data["provenance"],
            "preparation_sha256": data["preparation_sha256"],
            "evidence_sha256": self.evidence_sha256,
            "native_receipt_valid": data["native_validated"],
            "admission_only_valid": data["admission_only_validated"],
            "native_cleanup_confirmed": native_cleanup,
            "process_cleanup_confirmed": data["owner_constructed"]
            and not data["cleanup_errors"]
            and (not p["created"] or p["tree_exited"]),
            "process_created": p["created"],
            "primary_error": data["primary_error"],
            "cleanup_errors": list(data["cleanup_errors"]),
            "physical_authority": False,
            "hardware_qualified": False,
            "final_power_state": data["final_power_state"],
            "retries": 0,
        }
        if data["schema"] == CAPTURE_SCHEMA:
            summary.update(
                {
                    "schema": "rocell.owned_native_camera_capture_run_summary.v1",
                    "operation": "capture",
                    "capture_metadata": (
                        None
                        if receipt is None
                        else {
                            "status": receipt.status,
                            "frames_reported": len(receipt.frames),
                            "total_frame_bytes_reported": sum(
                                frame.length_bytes for frame in receipt.frames
                            ),
                        }
                    ),
                    "frame_content_verified": False,
                    "device_cleanup_proven": False,
                    "meaning": "Retained unqualified native capture metadata, not verified pixels or received-hardware qualification. Native cleanup and owned-process cleanup are separate; file validation and PHYSICAL_UNVERIFIED ingestion remain explicit later actions.",
                }
            )
        return summary


def retain_owned_native_camera_run(
    *,
    probe: PreparedOwnedNativeProbe | PreparedOwnedNativeCapture,
    fixture: Any,
    deadline_ns: Any,
    elapsed_ns: int,
    primary_error: str | None,
    cleanup_errors: tuple[str, ...],
    observed: dict[str, Any],
    ready_wire: bytes,
    release_wire: bytes,
    result: dict | None,
    native_validated: bool,
    admission_only_validated: bool,
    release_check_passed: bool,
    handshake: dict | None,
) -> OwnedNativeCameraRunEvidence:
    """Own complete bounded available evidence; never derive camera success from process exit."""
    capture = type(probe) is not PreparedOwnedNativeProbe
    if capture:
        from .native_camera_capture_registration import PreparedOwnedNativeCapture

        _require(
            type(probe) is PreparedOwnedNativeCapture, "EXACT_PREPARATION_REQUIRED"
        )
    checked = _preparation(probe.to_dict(), capture=capture)
    _require(
        type(probe) is type(checked) and probe.payload == checked.payload,
        "EXACT_PREPARATION_REQUIRED",
    )
    if capture:
        _require(fixture is None, "CAPTURE_CANNOT_RELABEL_ADMISSION_FIXTURE")
    registration = fixture.registration if fixture else probe.registration
    p = {
        key: observed.get(key, default)
        for key, default in _OBSERVATION_DEFAULTS.items()
    }
    owner = bool(observed)
    pipes = {}
    for name, maximum in (
        ("stdout", registration.budget.stdout_bytes),
        ("stderr", registration.budget.stderr_bytes),
    ):
        value = observed.get(name, b"")
        _require(
            type(value) is bytes and len(value) <= maximum, "OWNER_PIPE_SNAPSHOT_LIMIT"
        )
        pipes[name] = _wire(
            value,
            complete=owner
            and p[name + "_eof"] is True
            and primary_error != name.upper() + "_LIMIT",
        )
    reg = owned_registration_document(registration)
    data = {
        "schema": CAPTURE_SCHEMA if capture else SCHEMA,
        "preparation": probe.to_dict(),
        "preparation_sha256": probe.preparation_sha256,
        "fixture_preparation": None if fixture is None else fixture.to_dict(),
        "registration": reg,
        "registration_sha256": digest(canonical(reg)),
        "source_sha256": probe.admission_request.to_dict()["source_sha256"],
        "parent_deadline_ns": (
            deadline_ns
            if type(deadline_ns) is int and 0 < deadline_ns < 2**63
            else None
        ),
        "elapsed_ns": elapsed_ns,
        "primary_error": primary_error,
        "cleanup_errors": list(cleanup_errors),
        "owner_constructed": owner,
        "process": p,
        **pipes,
        "ready_wire": _wire(ready_wire, complete=True),
        "release_wire": _wire(release_wire, complete=True),
        "release_check_passed": release_check_passed,
        "native_validated": native_validated,
        "admission_only_validated": admission_only_validated,
        "validated_result": result,
        "handshake": handshake,
        "status": _status(
            primary_error,
            list(cleanup_errors),
            native=native_validated,
            fixture=admission_only_validated,
        ),
        "provenance": (
            "INCAPABLE_NATIVE_ADMISSION_ONLY" if fixture else "PHYSICAL_UNQUALIFIED"
        ),
        "physical_authority": False,
        "hardware_qualified": False,
        "final_power_state": "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
    }
    return OwnedNativeCameraRunEvidence(canonical(data))


def verify_owned_native_camera_run_evidence(
    value: dict[str, Any] | OwnedNativeCameraRunEvidence,
    *,
    expected_preparation_sha256: str,
    expected_evidence_sha256: str,
) -> OwnedNativeCameraRunEvidence:
    """Pure admission of retained bytes against independent trusted M1 references."""
    _require(
        type(expected_preparation_sha256) is str
        and bool(_SHA.fullmatch(expected_preparation_sha256))
        and type(expected_evidence_sha256) is str
        and bool(_SHA.fullmatch(expected_evidence_sha256)),
        "TRUSTED_EVIDENCE_HASH_REQUIRED",
    )
    payload = (
        value.payload
        if type(value) is OwnedNativeCameraRunEvidence
        else canonical(value)
    )
    _require(
        digest(payload) == expected_evidence_sha256, "EVIDENCE_TRUSTED_HASH_MISMATCH"
    )
    evidence = OwnedNativeCameraRunEvidence(payload)
    _require(
        evidence.to_dict()["preparation_sha256"] == expected_preparation_sha256,
        "EVIDENCE_TRUSTED_PREPARATION_MISMATCH",
    )
    return evidence
