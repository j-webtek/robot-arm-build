"""Pure close/reopen comparisons for two explicitly selected native captures.

This is the first M2 comparison layer, NOT an original-store reader or approval
API. The future original-bound owner must authenticate the supplied launch and
settings context against each permit/admission/plan before using these results.
Matching caller-supplied context never authenticates a clock domain. No devices,
files, processes, clocks, stage transitions or persistence are accessed here.
"""

from dataclasses import dataclass
from typing import Any

from .camera_activation_campaign_evidence import validate_camera_activation_evidence
from .camera_operating_evidence_preflight import CameraNativeEvidenceSubject
from rocell.providers.windows.native_camera_activation_registration import (
    PreparedOwnedNativeActivation,
)
from rocell.providers.windows.native_camera_protocol import (
    _ID,
    _require,
    _sha,
    canonical,
)

SCHEMA = "rocell.camera_capture_lifecycle_comparison.v1"
OWNER_OBLIGATIONS = (
    "ORIGINAL_STORE_AND_ADMISSION_CONTEXT_NOT_AUTHENTICATED",
    "COMMON_LAUNCH_CLOCK_DOMAIN_NOT_AUTHENTICATED",
    "USB_IDENTITY_AND_NEGOTIATED_LINK_NOT_ASSESSED",
    "PIXEL_CONTENT_AND_FRAME_FRESHNESS_NOT_ASSESSED",
    "SEPARATE_OPERATING_REVIEW_NOT_RECORDED",
)


@dataclass(frozen=True, slots=True)
class CameraCaptureLifecycleSubject:
    """Untrusted input bundle; context must come from independently read originals.

    Keep the settings epoch as well as the request's mode/control bytes: selecting
    the same values after a settings change does not restore the earlier epoch.
    None explicitly represents an unavailable launch context, never this launch.
    """

    native: CameraNativeEvidenceSubject
    request_key: str
    launch_session_id: str | None
    settings_epoch: str
    admission_sha256: str


def _identifier(value: Any) -> bool:
    return type(value) is str and bool(_ID.fullmatch(value))


def _read(subject: CameraCaptureLifecycleSubject):
    _require(type(subject) is CameraCaptureLifecycleSubject, "LIFECYCLE_EXACT_SUBJECT")
    _require(_identifier(subject.request_key), "LIFECYCLE_REQUEST_KEY")
    _require(
        subject.launch_session_id is None or _identifier(subject.launch_session_id),
        "LIFECYCLE_LAUNCH_CONTEXT",
    )
    for value in (subject.settings_epoch, subject.admission_sha256):
        _sha(value)
        _require(value != "0" * 64, "LIFECYCLE_ZERO_CONTEXT_DIGEST")
    native = subject.native
    _require(type(native) is CameraNativeEvidenceSubject, "LIFECYCLE_EXACT_NATIVE")
    _require(
        type(native.preparation) is PreparedOwnedNativeActivation,
        "LIFECYCLE_V2_PREPARATION_REQUIRED",
    )
    if type(native.evidence) is not tuple:
        raise ValueError("LIFECYCLE_V2_PAIR_REQUIRED")
    # This paired validator preserves failed and unavailable observations. Do not
    # replace its after-cleanup snapshot with older before-cleanup information.
    pair = validate_camera_activation_evidence(native.evidence)
    _require(
        pair.prepared.payload == native.preparation.payload
        and native.evidence[0].payload_sha256 == native.expected_evidence_sha256
        and native.evidence[1].payload_sha256 == native.expected_supervision_sha256,
        "LIFECYCLE_NATIVE_REFERENCE_MISMATCH",
    )
    request = pair.prepared.admission_request
    _require(request.purpose == "capture", "LIFECYCLE_CAPTURE_REQUIRED")
    configuration = request.configuration
    assert configuration is not None
    config = configuration.to_dict()
    # Different fresh directories are necessary per acquisition. They must not
    # make otherwise identical requested mode/control/budget comparisons fail.
    settings = {
        key: value for key, value in config.items() if key != "output_directory"
    }
    data, assessment = pair.run.to_dict(), pair.run.assessment()
    return request.to_dict(), settings, data, assessment


def assess_camera_capture_lifecycle(
    first: CameraCaptureLifecycleSubject,
    second: CameraCaptureLifecycleSubject,
) -> dict[str, Any]:
    """Preserve caller order and compare complete bounded native observations.

    Invalid/misbound records raise; valid failures produce explicit holds. A
    strictly positive gap is required to establish order from these timestamps.
    Equal ticks can occur in the native nondecreasing clock contract, but cannot
    establish inter-operation order alone. There is no arbitrary minimum delay.
    Even a consistent result leaves original provenance and stage review open.
    """
    subjects = (first, second)
    rows = tuple(_read(subject) for subject in subjects)
    requests = tuple(row[0] for row in rows)
    failures: list[str] = []

    def check(condition: bool, code: str) -> None:
        if not condition:
            failures.append(code)

    check(
        first.request_key != second.request_key
        and all(
            requests[0][key] != requests[1][key]
            for key in ("attempt_id", "permit_sha256")
        ),
        "DISTINCT_CAPTURE_ATTEMPTS_REQUIRED",
    )
    same_clock = (
        first.launch_session_id is not None
        and first.launch_session_id == second.launch_session_id
        and requests[0]["session_id"] == requests[1]["session_id"]
    )
    check(same_clock, "COMMON_LAUNCH_CONTEXT_MISSING_OR_CHANGED")
    for key in (
        "source_sha256",
        "selected_identity_sha256",
        "endpoint_sha256",
        "runtime_registration_sha256",
        "helper_sha256",
        "activation_identity_json",
    ):
        check(requests[0][key] == requests[1][key], "CHANGED_" + key.upper())
    check(first.settings_epoch == second.settings_epoch, "SETTINGS_EPOCH_CHANGED")
    check(canonical(rows[0][1]) == canonical(rows[1][1]), "CAPTURE_SETTINGS_CHANGED")

    captures = []
    for label, subject, (request, _, data, assessment) in zip(
        ("FIRST", "SECOND"), subjects, rows
    ):
        native_clean = (
            assessment.native is not None
            and assessment.native.receipt.cleanup_confirmed
        )
        check(
            assessment.status == "SUCCEEDED_NATIVE_DIAGNOSTIC",
            label + "_RUN_NOT_SUCCESSFUL",
        )
        check(
            assessment.process_cleanup_confirmed, label + "_PROCESS_CLEANUP_UNCONFIRMED"
        )
        check(native_clean, label + "_NATIVE_CLEANUP_UNCONFIRMED")
        captures.append(
            dict(
                request_key=subject.request_key,
                attempt_id=request["attempt_id"],
                permit_sha256=request["permit_sha256"],
                admission_sha256=subject.admission_sha256,
                launch_session_id=subject.launch_session_id,
                settings_epoch=subject.settings_epoch,
                preparation_sha256=subject.native.preparation.preparation_sha256,
                evidence_sha256=subject.native.expected_evidence_sha256,
                supervision_sha256=subject.native.expected_supervision_sha256,
                started_ns=data["started_ns"],
                cleanup_finished_ns=data["cleanup"]["finished_ns"],
                finished_ns=data["finished_ns"],
                status=assessment.status,
                native_reasons=list(assessment.reasons),
                process_cleanup_confirmed=assessment.process_cleanup_confirmed,
                native_cleanup_confirmed=native_clean,
            )
        )

    finish, start = captures[0]["finished_ns"], captures[1]["started_ns"]
    # Do not compute/subtract unrelated clock magnitudes, even for diagnostics.
    gap = (
        start - finish
        if same_clock and type(finish) is int and type(start) is int
        else None
    )
    check(gap is not None and gap > 0, "STRICT_FINISH_BEFORE_NEXT_START_UNPROVEN")
    return dict(
        schema=SCHEMA,
        status="HELD" if failures else "CONSISTENT_PENDING_ORIGINAL_AUTHENTICATION",
        captures=captures,
        inter_run_gap_ns=gap,
        clock_semantics="SUPPLIED_COMMON_LAUNCH_MONOTONIC_NS_REQUIRES_ORIGINAL_JOIN",
        failed_checks=failures,
        owner_obligations=list(OWNER_OBLIGATIONS),
        original_stage_authenticated=False,
        clock_domain_authenticated=False,
        stage_passed=False,
        approved_operating_policy=False,
        physical_authority=False,
        hardware_qualified=False,
        connected=False,
        device_io_performed=False,
    )
