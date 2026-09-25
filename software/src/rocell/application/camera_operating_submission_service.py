"""File-only original submission; no device dispatch or stage approval.

The public caller must pin the current logged proposal, two explicit captures
and original setup in its existing one-use operation. Assessment uses the
existing CAMERA read owner. Stage mutation then independently authenticates the
same complete history and native inputs under stage-only leases. A change at
that handoff is a failure, never a retry or restored acquisition permission.
"""

from copy import deepcopy
from pathlib import Path
from threading import Event
from time import monotonic_ns, time_ns
from uuid import uuid4

from .camera_operating_assessment_service import run_original_operating_assessment
from .camera_operating_submission import (
    SOURCE_WORKFLOW_OPERATING_SCHEMA,
    build_camera_operating_submission,
    camera_operating_submission_event,
    verify_camera_operating_submission,
)
from .camera_operating_submission_native import (
    verify_operating_submission_native_inputs,
)
from .camera_probe_preparation import (
    SOURCE_WORKFLOW_PROBE_SCHEMA,
    CameraProbePreparation,
    CameraProbePreparationReview,
)
from .commissioning_camera_persistence import M1PhysicalCameraTransaction
from .physical_camera_acquisition_service import PhysicalCameraAcquisitionService
from .physical_camera_mode_entry import CameraModeEntry, camera_mode_operator_valid
from .physical_camera_session import (
    PhysicalCameraSession,
    _read_original_evidence_under_lease,
)
from .physical_onboarding import STAGE_ORDER
from .physical_onboarding_durability import read_bounded_regular_file
from .physical_onboarding_v2 import V2StageState
from .wizard_actions import WizardError
from .wizard_diagnostic_coordinator import require_regular_path, source_fingerprint
from .wizard_native_camera_enrollment import WizardNativeCameraEnrollment
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.vision.camera_profile import MAX_CAMERA_PROFILE_BYTES

# One overall file-only operation budget. Nested readers may shorten it, never
# renew it. This is unrelated to the much shorter native acquisition permit.
TIMEOUT_NS = 300_000_000_000


def _need(ok, code):
    if not ok:
        raise WizardError(
            "OPERATING_SUBMISSION_" + code,
            "The original camera submission could not be verified. Inspect/export "
            "the retained diagnostics; partial writes are never replayed or approved.",
        )


def submission_boundary(workflow) -> bool:
    """Availability only. The owned original reader still verifies all bytes."""
    if type(workflow) is not dict:
        return False
    probe = workflow.get("camera_probe_preparation")
    return (
        workflow.get("schema") == SOURCE_WORKFLOW_PROBE_SCHEMA
        and "camera_operating_submission" not in workflow
        and type(probe) is dict
        and probe.get("state") == "REVIEWED_FOR_ADMISSION"
        and all(type(probe.get(k)) is dict for k in ("preparation", "review"))
        and type(probe.get("events")) is list
        and len(probe["events"]) == 2
    )


def _stage_subjects(workflow):
    """Parse only independently read originals, never browser-supplied records."""
    rows = dict(
        entry=workflow["camera_mode_entry"]["entry"],
        preparation=workflow["camera_probe_preparation"]["preparation"],
        review=workflow["camera_probe_preparation"]["review"],
    )
    subjects = {
        key: cls(canonical(rows[key]["document"]))
        for key, cls in (
            ("entry", CameraModeEntry),
            ("preparation", CameraProbePreparation),
            ("review", CameraProbePreparationReview),
        )
    }
    _need(
        all(
            value.sha256 == rows[key]["evidence_sha256"]
            for key, value in subjects.items()
        ),
        "SUBJECT_HASH",
    )
    return subjects


def _retain_in_stage_transaction(
    transaction,
    *,
    bound,
    expected_header_sha256,
    expected_workflow_payload,
    proposal_payload,
    report,
    operator_id,
    attempt,
    check,
    progress,
):
    """One write/commit, with uncertainty recorded before each fallible boundary.

    Internal service seam, not an import endpoint. The report was computed in
    this operation by the original assessment service. No old report or owner
    can be submitted by a browser. Native inputs are independently reread here.
    """
    _need(type(transaction) is M1PhysicalCameraTransaction, "TRANSACTION")
    _need(type(attempt) is dict and not attempt, "ATTEMPT_ALREADY_CLAIMED")
    check()
    before, original = _read_original_evidence_under_lease(
        transaction,
        bound=bound,
        expected_header_sha256=expected_header_sha256,
        strict_workflow=True,
        check=check,
    )
    _need(
        submission_boundary(original)
        and canonical(original) == expected_workflow_payload,
        "CREATION_HISTORY_CHANGED",
    )
    subjects = _stage_subjects(original)
    binding = dict(
        source_sha256=bound["source_sha256"],
        cell_id=before.header.cell_id,
        session_id=before.header.session_id,
        header_sha256=before.header.header_sha256,
        entry_sha256=subjects["entry"].sha256,
        probe_preparation_sha256=subjects["preparation"].sha256,
        probe_review_sha256=subjects["review"].sha256,
        journal_head_sha256=before.head.head_sha256,
        original_records_sha256=digest(
            canonical(transaction._audit_records(include_family=True))
        ),
    )
    check()
    subject = build_camera_operating_submission(
        submission_id="cameraoperating-" + uuid4().hex,
        operator_id=operator_id,
        recorded_at_utc_ns=time_ns(),
        binding=binding,
        proposal_payload=proposal_payload,
        assessment_payload=canonical(report),
    )
    profile = require_regular_path(
        Path(bound["workspace"])
        / "software/config/camera_profiles/arducam_b0477_imx283_16mm.json",
        directory=False,
    )
    raw_profile = read_bounded_regular_file(
        profile,
        maximum_bytes=MAX_CAMERA_PROFILE_BYTES,
        label="operating purchase profile",
    )
    check()
    verify_operating_submission_native_inputs(
        transaction,
        submission=subject,
        expected_binding=binding,
        **subjects,
        creation_workflow_sha256=digest(expected_workflow_payload),
        purchase_profile_payload=raw_profile,
    )
    check()
    _need(transaction.snapshot() == before, "CREATION_HISTORY_CHANGED")
    document = subject.to_dict()
    record = dict(
        document=document,
        evidence_sha256=subject.sha256,
        reference=None,
        retention="COLLECTED_NOT_M1_RETAINED",
    )
    attempt.update(submission_id=document["submission_id"], record=record, events=[])
    progress(
        "Saving the original proposal and assessment for separate review; no device is opened."
    )
    check()
    record["retention"] = "M1_PUBLICATION_UNCONFIRMED"
    reference = transaction.store_camera_operating_submission(
        subject.payload,
        captured_at_ns=time_ns(),
        expected_head_sha256=before.head.head_sha256,
    )
    record.update(
        reference=reference.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
    )
    check()
    verify_camera_operating_submission(
        transaction.read_stage_evidence(reference),
        expected_sha256=subject.sha256,
        expected_binding=binding,
        expected_proposal_payload=proposal_payload,
        expected_assessment_payload=canonical(report),
    )
    record["retention"] = "M1_FULL_BYTES_READ_BACK"
    check()
    # Exactly this call's record may be committed. A reopened partial package
    # cannot pass the earlier v16 boundary or be supplied as an attempt to resume.
    attempt["commit"] = "UNCONFIRMED"
    committed = transaction.commit_stage_state(
        STAGE_ORDER[4],
        V2StageState.REVIEW_PENDING,
        occurred_at_ns=time_ns(),
        detail_code=camera_operating_submission_event(document["submission_id"]),
        expected_head_sha256=before.head.head_sha256,
        evidence=(reference,),
    )
    attempt["events"].append(committed.committed_events[-1].to_dict())
    attempt["commit"] = "COMMITTED_READBACK_PENDING"
    check()
    _, workflow = _read_original_evidence_under_lease(
        transaction,
        bound=bound,
        expected_header_sha256=expected_header_sha256,
        strict_workflow=True,
        check=check,
    )
    _need(type(workflow) is dict, "COMMITTED_READBACK_CHANGED")
    assert workflow is not None
    _need(
        workflow["schema"] == SOURCE_WORKFLOW_OPERATING_SCHEMA
        and workflow["camera_operating_submission"]["state"]
        == "SUBMITTED_REVIEW_REQUIRED"
        and workflow["camera_operating_submission"]["submission"] == record
        and workflow["camera_operating_submission"]["events"] == attempt["events"],
        "COMMITTED_READBACK_CHANGED",
    )
    check()
    attempt["commit"] = "COMMITTED_ORIGINAL_READ_BACK"
    return workflow


def run_original_operating_submission(
    service,
    session,
    enrollment,
    *,
    context,
    expected_workflow_payload,
    proposal_payload,
    expected_proposal_sha256,
    capture_request_keys,
    request_key,
    operator_id,
    cancellation,
    deadline_ns,
    validate_current_context,
    progress,
    attempt,
):
    """Prepare fresh diagnostic inputs, then retain an unreviewed original.

    Successful return is still pending the wizard's durable completion log and
    final source/Stop publication checks. No caller-provided report is accepted.
    Failure leaves every known write boundary in ``attempt`` for diagnostics.
    """
    started = monotonic_ns()
    _need(
        type(service) is PhysicalCameraAcquisitionService
        and type(session) is PhysicalCameraSession
        and type(enrollment) is WizardNativeCameraEnrollment
        and type(cancellation) is Event
        and type(deadline_ns) is int
        and started < deadline_ns <= started + TIMEOUT_NS
        and type(expected_workflow_payload) is bytes
        and type(capture_request_keys) is tuple
        and all(type(key) is str and 0 < len(key) <= 96 for key in capture_request_keys)
        and len(capture_request_keys) == len(set(capture_request_keys)) == 2
        and camera_mode_operator_valid(operator_id)
        and type(attempt) is dict
        and not attempt
        and callable(validate_current_context)
        and callable(progress),
        "INPUT",
    )
    bound = session.descriptor()
    bound_payload = canonical(bound)
    last_now = started

    def check(*, source=True):
        nonlocal last_now
        now = monotonic_ns()
        _need(
            last_now <= now < deadline_ns and not cancellation.is_set(), "INTERRUPTED"
        )
        last_now = now
        _need(canonical(session.descriptor()) == bound_payload, "OWNER_CHANGED")
        _need(validate_current_context() is None, "CONTEXT_CHANGED")
        if source:
            _need(
                source_fingerprint(service.workspace) == bound["source_sha256"],
                "SOURCE_CHANGED",
            )
            check(source=False)

    check()
    report = run_original_operating_assessment(
        service,
        session,
        enrollment,
        context=context,
        proposal_payload=proposal_payload,
        expected_proposal_sha256=expected_proposal_sha256,
        capture_request_keys=capture_request_keys,
        request_key=request_key,
        cancellation=cancellation,
        deadline_ns=deadline_ns,
        validate_current_context=check,
        progress=progress,
    )
    check()
    # Reacquire the existing dispatcher exclusion for the stage-only handoff.
    # A concurrent operation is a rejection, not queued work or a retry loop.
    _need(service._dispatch_lock.acquire(False), "CAMERA_OPERATION_ACTIVE")
    try:
        verification = session.view()["verification"]
        _need(
            type(verification) is dict
            and verification.get("effects_allowed_by_m1_storage") is True,
            "STORAGE_REQUIRED",
        )
        with session.stage_transaction(
            expected_challenge_sha256=verification["challenge_sha256"]
        ) as transaction:
            workflow = _retain_in_stage_transaction(
                transaction,
                bound=bound,
                expected_header_sha256=report["header_sha256"],
                expected_workflow_payload=expected_workflow_payload,
                proposal_payload=proposal_payload,
                report=report,
                operator_id=operator_id,
                attempt=attempt,
                check=check,
                progress=progress,
            )
        check()
        session.refresh(
            cancellation=cancellation, progress=progress, deadline_ns=deadline_ns
        )
        check()
        reopened = session.read_original_source_workflow(
            expected_header_sha256=report["header_sha256"],
            cancellation=cancellation,
            progress=progress,
            deadline_ns=deadline_ns,
        )
        check()
        _need(canonical(reopened) == canonical(workflow), "REOPEN_CHANGED")
        attempt["commit"] = "COMMITTED_AND_REOPENED_ORIGINAL"
        return deepcopy(reopened)
    finally:
        service._dispatch_lock.release()
