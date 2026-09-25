"""Fixed, raw-free explanations of retained camera rehearsal failures.

This is a diagnostic projection, not an evidence assessor or recovery policy.
The caller still owns the trusted M1 digest/permit join. Existing pure evidence
validation is repeated, but no provider, process, filesystem or ledger is used.
In particular, a client's reported rejection does not validate its rejected
native packet or establish any requested/observed control values.
"""

from __future__ import annotations

from typing import Any

from rocell.application.rehearsal_owned_camera_evidence import (
    MAX_EVIDENCE_BYTES,
    OwnedCameraEvidenceError,
    RehearsalOwnedCameraEvidence,
    verify_owned_camera_evidence,
)

SCHEMA = "rocell.camera_fault_diagnostic.v1"

# Match the complete local exception signature, not substrings in arbitrary
# error text or untrusted process output. Unknown versions stay unclassified.
_READBACK_REJECTION = {
    "code": "INVALID_CAMERA_CONTRACT",
    "error_type": "CameraWorkerError",
    "message": ("INVALID_CAMERA_CONTRACT: requested control did not read back exactly"),
}

_REASONS = {
    "CONTROL_READBACK_MISMATCH_REPORTED": (
        "The retained camera client reported that a requested control did not "
        "read back exactly. The rejected native packet is not a verified observation.",
        "Export the original attempt. Review its private requested control mode/value "
        "and rejected readback with the retained probe capabilities. Investigate the "
        "configuration or adapter; do not guess a control value or retry this attempt.",
    ),
    "PROCESS_CLEANUP_UNCONFIRMED": (
        "The retained process report does not confirm complete process cleanup. "
        "This is separate from native camera cleanup.",
        "Export the original attempt and inspect retained process ownership and "
        "cleanup evidence. Preserve any existing quarantine and unresolved resources; "
        "do not reopen the camera or retry cleanup automatically.",
    ),
    "OPERATION_CANCELLED": (
        "The retained process report records cancellation. Any partial output "
        "remains diagnostic evidence, not an accepted capture.",
        "Review the original cancellation and cleanup evidence, then export it. "
        "A stopped attempt cannot resume; any later action requires separate admission.",
    ),
    "OPERATION_TIMED_OUT": (
        "The retained process report records an expired execution budget. "
        "No deadline extension or successful capture is inferred.",
        "Export timing and cleanup evidence. Investigate bounded admission, process "
        "execution and retention timing without extending or replaying the original permit.",
    ),
    "UNCLASSIFIED_CALLER_ERROR": (
        "The caller retained an error that has no exact approved diagnostic mapping. "
        "Its private text is intentionally omitted here.",
        "Export the original attempt for developer inspection of the full private "
        "error and its request/evidence bindings. Do not infer a hardware cause or retry.",
    ),
    "PROCESS_EXECUTION_UNCONFIRMED": (
        "The retained process report does not confirm successful execution.",
        "Export the original process status, bounded output and cleanup evidence "
        "for developer review. Do not treat process termination as camera cleanup.",
    ),
    "REQUEST_OR_PROCESS_EVIDENCE_UNAVAILABLE": (
        "The exact activation request or owned process result is unavailable.",
        "Inspect the original admission and evidence-retention failure. Preserve "
        "partial records and export diagnostics; do not reconstruct missing observations.",
    ),
    "NATIVE_EVIDENCE_UNVERIFIED": (
        "The retained native packet/request join or synthetic capture cleanup "
        "is unverified. No native success or control observation is inferred.",
        "Export the original request, rejected packet and cleanup evidence for "
        "developer comparison. Do not substitute an endpoint or accept partial output.",
    ),
    "CAPTURE_RETENTION_UNVERIFIED": (
        "The capture dataset metadata and its request/source bindings are unverified.",
        "Preserve the original files and incomplete publication markers. Review "
        "retention budgets, hashes and cancellation evidence; do not repair or replay automatically.",
    ),
    "NONE": (
        "This retained rehearsal evidence reports no camera campaign fault. "
        "It does not establish received-hardware or current-session qualification.",
        "Continue only through the existing separately admitted stage workflow. "
        "This projection grants no retry, recovery or physical permission.",
    ),
}


class CameraFaultDiagnosticError(ValueError):
    """Invalid projection input, without copying private exception details."""

    code = "INVALID_CAMERA_FAULT_EVIDENCE"

    def __init__(self) -> None:
        super().__init__(
            "A bounded, valid retained camera evidence artifact is required."
        )


def camera_fault_diagnostic(evidence: RehearsalOwnedCameraEvidence) -> dict[str, Any]:
    """Explain a retained fault with fixed prose; never expose raw error text.

    The returned evidence hash is a reference, not authentication. The input may
    be historical: this function neither audits M1 nor declares a current source,
    attempt, quarantine or image valid. Recovery flags describe the absence of
    authority granted by this projection, not the existence of a recovery permit.
    """
    if (
        type(evidence) is not RehearsalOwnedCameraEvidence
        or type(evidence.payload) is not bytes
        or not 1 <= len(evidence.payload) <= MAX_EVIDENCE_BYTES
    ):
        raise CameraFaultDiagnosticError()
    try:
        document = evidence.to_dict()
        checked = verify_owned_camera_evidence(evidence.payload, document["binding"])
        view = checked.view()
    except (OwnedCameraEvidenceError, ValueError, TypeError, KeyError, RecursionError):
        raise CameraFaultDiagnosticError() from None

    process, error = view["process"], document["error"]
    blockers = frozenset(view["blockers"])
    category, basis, code = "NONE", "NONE", None
    if process is not None and (
        process["cleanup_error_count"]
        or (process["created"] and not process["tree_exit_confirmed"])
    ):
        category, basis = "PROCESS_CLEANUP_UNCONFIRMED", "RETAINED_PROCESS_STATUS"
    elif process is not None and process["status"] in {"CANCELLED", "TIMED_OUT"}:
        category = (
            "OPERATION_CANCELLED"
            if process["status"] == "CANCELLED"
            else "OPERATION_TIMED_OUT"
        )
        basis, code = "RETAINED_PROCESS_STATUS", process["status"]
    elif (
        error == _READBACK_REJECTION
        and document["activation_request"] is not None
        and document["activation_request"]["controls"]
    ):
        category = "CONTROL_READBACK_MISMATCH_REPORTED"
        basis, code = "RETAINED_CALLER_ERROR_EXACT_MATCH", "INVALID_CAMERA_CONTRACT"
    elif error is not None:
        category, basis, code = (
            "UNCLASSIFIED_CALLER_ERROR",
            "RETAINED_VALIDATION_HOLD",
            "UNCLASSIFIED",
        )
    elif "OWNED_PROCESS_NOT_CONFIRMED_SUCCESSFUL" in blockers:
        category, basis = "PROCESS_EXECUTION_UNCONFIRMED", "RETAINED_PROCESS_STATUS"
    elif blockers & {
        "ACTIVATION_REQUEST_UNAVAILABLE",
        "OWNED_PROCESS_RESULT_UNAVAILABLE",
    }:
        category = "REQUEST_OR_PROCESS_EVIDENCE_UNAVAILABLE"
        basis = "RETAINED_VALIDATION_HOLD"
    elif blockers & {
        "NATIVE_WIRE_OR_REQUEST_BINDING_UNVERIFIED",
        "SYNTHETIC_NATIVE_CAPTURE_NOT_CONFIRMED",
    }:
        category, basis = "NATIVE_EVIDENCE_UNVERIFIED", "RETAINED_VALIDATION_HOLD"
    elif "CAPTURE_METADATA_BINDING_UNVERIFIED" in blockers:
        category, basis = "CAPTURE_RETENTION_UNVERIFIED", "RETAINED_VALIDATION_HOLD"

    reason, next_investigation = _REASONS[category]
    return {
        "schema": SCHEMA,
        "status": "NO_REPORTED_FAULT" if category == "NONE" else "FAULT_REPORTED",
        "evidence_sha256": checked.evidence_sha256,
        "reason_category": category,
        "reported_code": code,
        "basis": basis,
        "reason": reason,
        "next_investigation": next_investigation,
        "retry_this_attempt_allowed": False,
        "automatic_retry_allowed": False,
        "clear_quarantine_allowed": False,
        "physical_authority": False,
        "qualified": False,
        "meaning": (
            "Fixed explanation of retained rehearsal evidence, not a new observation "
            "or full M1 audit. Preserve existing quarantine and approval requirements. "
            "No raw packet, endpoint, error message or power observation is exposed."
        ),
    }
