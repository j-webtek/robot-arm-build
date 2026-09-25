"""Lossless bounded v2 run records; validation is not original-store authority.

The native result is retained once, inside exact stdout bytes. On reopening we
rebuild the complete v2 request/READY/result binding; decoded copies and success
Booleans are not stored. Failed/incomplete attempts remain readable diagnostics.
Legacy evidence classes, schemas and limits are deliberately unchanged.
"""

from dataclasses import dataclass
from typing import Any
import re

from .native_camera_activation_observations import (
    ActivationOwnerObservation,
    _wire,
    read_buffer,
)
from .camera_worker_client import CameraWorkerError
from .native_camera_activation_protocol import (
    activation_release,
    parse_owned_activation_result,
    ValidatedActivationResult,
)
from .native_camera_activation_registration import PreparedOwnedNativeActivation
from .native_camera_protocol import (
    MAX_HANDSHAKE_BYTES,
    canonical,
    digest,
    _require,
    _sha,
    parse_native_camera_ready,
)
from .owned_worker_process import decode_owned_json, owned_registration_document

SCHEMA = "rocell.owned_native_camera_activation_run_evidence.v2"
MAX_EVIDENCE_BYTES = 512 * 1024
_CODE = re.compile(r"[A-Za-z0-9_:-]{1,128}\Z")
_FIELDS = {
    "schema",
    "preparation",
    "preparation_sha256",
    "registration_sha256",
    "source_sha256",
    "owner_constructed",
    "owner_observation",
    "started_ns",
    "finished_ns",
    "parent_deadline_ns",
    "primary_error",
    "cleanup",
    "ready_wire",
    "release_wire",
    "release_check_passed",
    "accepted_result_sha256",
    "physical_authority",
    "hardware_qualified",
}
_RESOURCE_FIELDS = (
    "pending",
    "handles_remaining",
    "unclosed_handles_remaining",
    "pins_remaining",
)


def _tick(value: Any) -> bool:
    return type(value) is int and 0 <= value < 2**63


def _label(value: Any) -> bool:
    return type(value) is str and bool(_CODE.fullmatch(value))


def _read(
    payload: bytes,
) -> tuple[
    dict[str, Any], PreparedOwnedNativeActivation, ActivationOwnerObservation | None
]:
    data = decode_owned_json(payload, maximum=MAX_EVIDENCE_BYTES)
    _require(
        canonical(data) == payload
        and set(data) == _FIELDS
        and data["schema"] == SCHEMA,
        "V2_RUN_EVIDENCE_SCHEMA",
    )
    prepared = PreparedOwnedNativeActivation(canonical(data["preparation"]))
    _require(
        data["preparation_sha256"] == prepared.preparation_sha256
        and data["source_sha256"]
        == prepared.admission_request.to_dict()["source_sha256"]
        and data["registration_sha256"]
        == digest(canonical(owned_registration_document(prepared.registration))),
        "V2_RUN_PREPARATION_BINDING",
    )
    _require(
        data["physical_authority"] is False and data["hardware_qualified"] is False,
        "V2_RUN_NOT_AUTHORITY",
    )
    _require(
        type(data["owner_constructed"]) is bool
        and type(data["release_check_passed"]) is bool,
        "V2_RUN_LITERAL_BOOL",
    )
    for name in ("started_ns", "finished_ns", "parent_deadline_ns"):
        _require(data[name] is None or _tick(data[name]), "V2_RUN_CLOCK_VALUE")
    _require(
        data["primary_error"] is None or _label(data["primary_error"]),
        "V2_RUN_ERROR_LABEL",
    )
    cleanup = data["cleanup"]
    _require(
        type(cleanup) is dict
        and set(cleanup)
        == {"attempted", "returned", "deadline_ns", "finished_ns", "errors"}
        and type(cleanup["attempted"]) is bool
        and type(cleanup["returned"]) is bool,
        "V2_RUN_CLEANUP_FIELDS",
    )
    _require(
        not cleanup["returned"] or cleanup["attempted"],
        "V2_RUN_CLEANUP_RETURN_WITHOUT_ATTEMPT",
    )
    for name in ("deadline_ns", "finished_ns"):
        _require(cleanup[name] is None or _tick(cleanup[name]), "V2_RUN_CLEANUP_CLOCK")
    errors = cleanup["errors"]
    _require(
        (
            (
                type(errors) is list
                and len(errors) <= 260
                and all(_label(code) for code in errors)
                and len(errors) == len(set(errors))
            )
            if cleanup["returned"]
            else errors is None
        ),
        "V2_RUN_CLEANUP_RESULT_AVAILABILITY",
    )
    _require(
        cleanup["attempted"]
        or cleanup
        == dict(
            attempted=False,
            returned=False,
            deadline_ns=None,
            finished_ns=None,
            errors=None,
        ),
        "V2_RUN_UNATTEMPTED_CLEANUP",
    )
    observed = (
        None
        if data["owner_observation"] is None
        else ActivationOwnerObservation(canonical(data["owner_observation"]))
    )
    _require(
        data["owner_constructed"] or observed is None and not cleanup["attempted"],
        "V2_RUN_OBSERVATION_WITHOUT_OWNER",
    )
    if observed is not None:
        observation = observed.to_dict()
        _require(
            observation["stdout_limit"] == prepared.registration.budget.stdout_bytes
            and observation["stderr_limit"]
            == prepared.registration.budget.stderr_bytes,
            "V2_RUN_OBSERVATION_BUDGET",
        )
    for name in ("ready_wire", "release_wire"):
        read_buffer(data[name], MAX_HANDSHAKE_BYTES)
        _require(data[name]["omitted_from_observed_buffer"] == 0, "V2_RUN_MESSAGE_LOSS")
    accepted = data["accepted_result_sha256"]
    if accepted is not None:
        _sha(accepted)
    if not data["owner_constructed"]:
        _require(
            not read_buffer(data["ready_wire"], MAX_HANDSHAKE_BYTES)
            and not read_buffer(data["release_wire"], MAX_HANDSHAKE_BYTES)
            and not data["release_check_passed"]
            and accepted is None,
            "V2_RUN_PIPE_OR_ACCEPTANCE_WITHOUT_OWNER",
        )
    return data, prepared, observed


@dataclass(frozen=True, slots=True)
class ActivationRunAssessment:
    status: str
    reasons: tuple[str, ...]
    process_cleanup_confirmed: bool
    native: ValidatedActivationResult | None


def _assess(
    data: dict[str, Any],
    prepared: PreparedOwnedNativeActivation,
    observed: ActivationOwnerObservation | None,
) -> ActivationRunAssessment:
    reasons = []

    def check(condition: bool, code: str) -> None:
        if not condition and code not in reasons:
            reasons.append(code)

    values = {} if observed is None else observed.values()
    check(data["owner_constructed"], "OWNER_NOT_CONSTRUCTED")
    check(
        observed is not None and not observed.unavailable_fields,
        "OWNER_OBSERVATIONS_INCOMPLETE",
    )
    cleanup = data["cleanup"]
    timing = all(
        _tick(data[name])
        for name in ("started_ns", "finished_ns", "parent_deadline_ns")
    )
    check(
        timing
        and data["started_ns"] <= data["finished_ns"] < data["parent_deadline_ns"],
        "ORIGINAL_RUN_TIMING_UNCONFIRMED",
    )
    # This outer interval includes file pinning and admission. The reservation
    # required_lifetime_ns is checked AFTER pinning, not an upper bound on this
    # whole interval. Native/run deadlines remain enforced by the live owner.
    cleanup_timing = _tick(cleanup["deadline_ns"]) and _tick(cleanup["finished_ns"])
    clean = bool(
        data["owner_constructed"]
        and cleanup["attempted"]
        and cleanup["returned"]
        and cleanup["errors"] == []
        and cleanup_timing
        and _tick(data["started_ns"])
        and data["started_ns"] <= cleanup["finished_ns"]
        and cleanup["finished_ns"] <= cleanup["deadline_ns"]
        and _tick(data["finished_ns"])
        and cleanup["finished_ns"] <= data["finished_ns"]
        and _tick(data["parent_deadline_ns"])
        and cleanup["deadline_ns"] <= data["parent_deadline_ns"]
        and all(name in values and values[name] == 0 for name in _RESOURCE_FIELDS)
        and (
            values.get("created") is False
            or values.get("created") is True
            and values.get("tree_exited") is True
        )
    )
    check(clean, "PROCESS_CLEANUP_UNCONFIRMED")
    budget = prepared.registration.budget
    check(
        type(values.get("peak_processes")) is int
        and (1 if values.get("created") is True else 0)
        <= values["peak_processes"]
        <= budget.process_count,
        "PROCESS_COUNT_UNCONFIRMED_OR_EXCEEDED",
    )
    check(
        type(values.get("peak_handles")) is int
        and values["peak_handles"] <= budget.observed_handles_per_process,
        "HANDLE_COUNT_UNCONFIRMED_OR_EXCEEDED",
    )
    check(data["primary_error"] is None, "PRIMARY_ERROR_RETAINED")
    native = None
    # Result parsing is independent of successful process cleanup. A failed
    # cleanup may still have a complete native receipt useful for diagnosis.
    ready_wire = read_buffer(data["ready_wire"], MAX_HANDSHAKE_BYTES)
    release_wire = read_buffer(data["release_wire"], MAX_HANDSHAKE_BYTES)
    result_ready = bool(
        values.get("created") is True
        and values.get("resumed") is True
        and values.get("tree_exited") is True
        and values.get("stdout_eof") is True
        and values.get("stderr_eof") is True
        and values.get("pending") is False
        and type(values.get("pid")) is int
        and 0 < values["pid"] < 2**32
        and type(values.get("returncode")) is int
        and type(values.get("written")) is int
        and values["written"]
        == len(prepared.admission_request.wire()) + len(release_wire)
        and values["written"] <= budget.stdin_bytes
        and data["release_check_passed"]
        and ready_wire
        and release_wire
        and type(values.get("stdout")) is bytes
        and values["stdout"].startswith(ready_wire)
        and data["accepted_result_sha256"] is not None
        and type(values.get("stderr")) is bytes
    )
    if observed is not None:
        fields = observed.to_dict()["fields"]
        result_ready = result_ready and all(
            fields[name]["available"]
            and fields[name]["value"]["omitted_from_observed_buffer"] == 0
            for name in ("stdout", "stderr")
        )
    result_ready = result_ready and data["primary_error"] not in (
        "STDOUT_LIMIT",
        "STDERR_LIMIT",
    )
    if result_ready:
        try:
            ready = parse_native_camera_ready(
                ready_wire,
                expected_request_sha256=prepared.admission_request.request_sha256,
                expected_child_pid=values["pid"],
            )
            _require(
                release_wire
                == activation_release(
                    prepared.admission_request, ready, expected_child_pid=values["pid"]
                ),
                "V2_RETAINED_RELEASE_BINDING",
            )
            result_wire = values["stdout"][len(ready_wire) :]
            _require(
                digest(result_wire) == data["accepted_result_sha256"],
                "V2_ACCEPTED_RESULT_CHANGED",
            )
            native = parse_owned_activation_result(
                result_wire,
                request=prepared.admission_request,
                ready=ready,
                expected_child_pid=values["pid"],
                returncode=values["returncode"],
            )
        except (ValueError, TypeError, KeyError, CameraWorkerError):
            reasons.append("NATIVE_RESULT_REVERIFICATION_FAILED")
    else:
        reasons.append("NATIVE_RESULT_OR_DELIVERY_UNCONFIRMED")
    check(
        native is not None and native.receipt.status == "OK",
        "NATIVE_DIAGNOSTIC_NOT_SUCCESSFUL",
    )
    check(
        native is not None and native.receipt.cleanup_confirmed,
        "NATIVE_CLEANUP_UNCONFIRMED",
    )
    if data["primary_error"] == "CANCELLED":
        status = "CANCELLED"
    elif data["primary_error"] in {
        "TIMED_OUT",
        "PARENT_DEADLINE_EXPIRED",
        "ADMISSION_DEADLINE_EXPIRED",
    }:
        status = "TIMED_OUT"
    elif (
        data["primary_error"] == "PHYSICAL_PROVIDER_QUALIFICATION_HELD"
        and not data["owner_constructed"]
    ):
        status = "HELD"
    else:
        status = "SUCCEEDED_NATIVE_DIAGNOSTIC" if not reasons else "FAILED"
    return ActivationRunAssessment(status, tuple(reasons), clean, native)


@dataclass(frozen=True, slots=True)
class OwnedNativeCameraActivationRunEvidence:
    payload: bytes

    def __post_init__(self) -> None:
        _read(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _read(self.payload)[0]

    @property
    def evidence_sha256(self) -> str:
        return digest(self.payload)

    def assessment(self) -> ActivationRunAssessment:
        return _assess(*_read(self.payload))

    def safe_summary(self) -> dict[str, Any]:
        data, prepared, owner = _read(self.payload)
        assessment = _assess(data, prepared, owner)
        native = assessment.native
        return dict(
            schema="rocell.owned_native_camera_activation_run_summary.v2",
            status=assessment.status,
            preparation_sha256=prepared.preparation_sha256,
            evidence_sha256=self.evidence_sha256,
            operation=prepared.admission_request.purpose,
            process_created=None if owner is None else owner.values().get("created"),
            unavailable_fields=list(owner.unavailable_fields) if owner else None,
            reasons=list(assessment.reasons),
            process_cleanup_confirmed=assessment.process_cleanup_confirmed,
            native_receipt_valid=native is not None,
            native_counts=None if native is None else dict(native.receipt.counts),
            native_cleanup_confirmed=native is not None
            and native.receipt.cleanup_confirmed,
            primary_error=data["primary_error"],
            cleanup_errors=data["cleanup"]["errors"],
            physical_authority=False,
            hardware_qualified=False,
            frame_content_verified=False,
            final_power_state="UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
        )


def retain_activation_run(
    *,
    prepared: PreparedOwnedNativeActivation,
    owner_constructed: bool,
    owner_observation: ActivationOwnerObservation | None,
    started_ns: int | None,
    finished_ns: int | None,
    parent_deadline_ns: int | None,
    primary_error: str | None,
    cleanup: dict[str, Any],
    ready_wire: bytes,
    release_wire: bytes,
    release_check_passed: bool,
    accepted_result_sha256: str | None,
) -> OwnedNativeCameraActivationRunEvidence:
    """Own actual supplied observations; no device, process, file or clock reads."""
    _require(
        type(prepared) is PreparedOwnedNativeActivation, "V2_RUN_EXACT_PREPARATION"
    )
    prepared = PreparedOwnedNativeActivation(prepared.payload)
    _require(
        owner_observation is None
        or type(owner_observation) is ActivationOwnerObservation,
        "V2_RUN_EXACT_OBSERVATION",
    )
    return OwnedNativeCameraActivationRunEvidence(
        canonical(
            dict(
                schema=SCHEMA,
                preparation=prepared.to_dict(),
                preparation_sha256=prepared.preparation_sha256,
                registration_sha256=digest(
                    canonical(owned_registration_document(prepared.registration))
                ),
                source_sha256=prepared.admission_request.to_dict()["source_sha256"],
                owner_constructed=owner_constructed,
                owner_observation=(
                    None if owner_observation is None else owner_observation.to_dict()
                ),
                started_ns=started_ns,
                finished_ns=finished_ns,
                parent_deadline_ns=parent_deadline_ns,
                primary_error=primary_error,
                cleanup=cleanup,
                ready_wire=_wire(ready_wire, MAX_HANDSHAKE_BYTES),
                release_wire=_wire(release_wire, MAX_HANDSHAKE_BYTES),
                release_check_passed=release_check_passed,
                accepted_result_sha256=accepted_result_sha256,
                physical_authority=False,
                hardware_qualified=False,
            )
        )
    )


def verify_activation_run(
    value: OwnedNativeCameraActivationRunEvidence,
    *,
    expected_preparation: PreparedOwnedNativeActivation,
    expected_evidence_sha256: str,
) -> OwnedNativeCameraActivationRunEvidence:
    """Recheck against independently retained originals; self-hashes are not trust."""
    _require(
        type(value) is OwnedNativeCameraActivationRunEvidence
        and type(expected_preparation) is PreparedOwnedNativeActivation,
        "V2_RUN_EXACT_VERIFICATION_INPUTS",
    )
    _sha(expected_evidence_sha256)
    _require(
        digest(value.payload) == expected_evidence_sha256,
        "V2_RUN_TRUSTED_HASH_MISMATCH",
    )
    checked = OwnedNativeCameraActivationRunEvidence(value.payload)
    expected = PreparedOwnedNativeActivation(expected_preparation.payload)
    _require(
        checked.to_dict()["preparation"] == expected.to_dict(),
        "V2_RUN_TRUSTED_PREPARATION_MISMATCH",
    )
    return checked
