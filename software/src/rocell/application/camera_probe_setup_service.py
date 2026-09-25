"""File-only probe preparation/review inside the existing Setup operation owner.

This module neither enumerates nor opens devices. Arrival supplies its current
enrollment and one-use queue; Session authenticates all originals under the same
stage transaction used for writes. The later CAMERA-lease admission is separate.
"""

from copy import deepcopy
from pathlib import Path
from time import monotonic_ns, time_ns
from uuid import uuid4

from .camera_activation_runtime_policy import (
    reviewed_activation_runtime_candidate,
    verify_reviewed_activation_runtime,
)
from .camera_probe_preparation import (
    SOURCE_WORKFLOW_PROBE_SCHEMA,
    CameraProbePreparation,
    CameraProbePreparationReview,
    build_camera_probe_preparation,
    build_camera_probe_preparation_review,
    camera_probe_event,
    camera_probe_label,
)
from .camera_probe_preparation_readback import verify_probe_preparation_context
from .physical_camera_activation_campaign import PhysicalCameraActivationCampaign
from .physical_camera_mode_entry import SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA
from .physical_onboarding import STAGE_ORDER, _parse_evidence_reference
from .physical_onboarding_v2 import V2StageState
from .wizard_actions import WizardError
from .wizard_diagnostic_coordinator import source_fingerprint
from .wizard_native_camera_enrollment import WizardNativeCameraEnrollment
from rocell.providers.windows.native_camera_protocol import canonical

PREPARE = "physical_camera_probe_prepare"
REVIEW = "physical_camera_probe_review"
ACTIONS = frozenset((PREPARE, REVIEW))
TIMEOUT_NS = 180_000_000_000


def record_boundary(workflow, action_id):
    """Cached availability only; execution still authenticates original bytes."""
    if type(workflow) is not dict or action_id not in ACTIONS:
        return False
    entry = workflow.get("camera_mode_entry")
    if type(entry) is not dict or entry.get("state") != "ENTERED":
        return False
    row = workflow.get("camera_probe_preparation")
    if action_id == PREPARE:
        return (
            workflow.get("schema") == SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA and row is None
        )
    return (
        workflow.get("schema") == SOURCE_WORKFLOW_PROBE_SCHEMA
        and type(row) is dict
        and row.get("state") == "PREPARED_REVIEW_REQUIRED"
        and type(row.get("preparation")) is dict
        and row.get("review") is None
    )


def _need(ok, code, message):
    if not ok:
        raise WizardError(
            code, message + " Inspect/export diagnostics without automatic replay."
        )


def write_probe_record(
    setup,
    action_id,
    *,
    operator_id,
    enrollment,
    cancellation,
    progress,
    deadline_ns,
    validate_current_enrollment,
):
    """Append one record/event; Arrival alone may publish the final completion.

    Stop cannot undo a committed write. Each known boundary is saved before the
    next fallible operation so a failed result does not hide partial publication.
    No successful return here grants camera access or a physical stage PASS.
    """
    from .physical_camera_session import _read_original_evidence_under_lease

    started = monotonic_ns()
    _need(
        action_id in ACTIONS
        and type(deadline_ns) is int
        and started < deadline_ns <= started + TIMEOUT_NS,
        "CAMERA_PROBE_DEADLINE",
        "Use the original bounded preparation/review operation.",
    )
    _need(
        type(enrollment) is WizardNativeCameraEnrollment,
        "CAMERA_PROBE_CURRENT_ENROLLMENT",
        "Current application-owned enrollment is required.",
    )
    _need(
        callable(validate_current_enrollment),
        "CAMERA_PROBE_CURRENT_ENROLLMENT",
        "The owning wizard must recheck its current enrollment.",
    )
    session, bound = setup.session, setup.session.descriptor()
    workflow = setup.original_source_workflow()
    _need(
        record_boundary(workflow, action_id),
        "CAMERA_PROBE_ORIGINAL_BOUNDARY",
        "The exact original preparation/review boundary is missing or incomplete.",
    )
    queue = setup._probe_queues.get(action_id)
    _need(
        type(queue) is dict and queue.get("claimed") is True,
        "CAMERA_PROBE_QUEUE_REQUIRED",
        "Use the wizard's one-time reviewed action.",
    )
    expected, binding, current_enrollment = (
        canonical(workflow),
        canonical(bound),
        canonical(enrollment.export_snapshot()),
    )
    header = workflow["session_header_sha256"]

    def check(*, source=True):
        _need(
            setup.session is session
            and canonical(session.descriptor()) == binding
            and setup._probe_queues.get(action_id) is queue,
            "CAMERA_PROBE_CONTEXT_CHANGED",
            "Original setup ownership changed.",
        )
        _need(
            not cancellation.is_set() and monotonic_ns() < deadline_ns,
            "CAMERA_PROBE_INTERRUPTED",
            "The operation was stopped or expired.",
        )
        _need(
            validate_current_enrollment() is None,
            "CAMERA_PROBE_CURRENT_ENROLLMENT",
            "The current wizard enrollment was not verified.",
        )
        _need(
            canonical(enrollment.export_snapshot()) == current_enrollment,
            "CAMERA_PROBE_ENROLLMENT_CHANGED",
            "The supplied current enrollment changed.",
        )
        if source:
            _need(
                source_fingerprint(setup.workspace) == setup.source_sha256,
                "CAMERA_SETUP_SOURCE_CHANGED",
                "The application build changed.",
            )
            check(source=False)

    check()
    verification = session.view()["verification"]
    _need(
        type(verification) is dict
        and verification.get("effects_allowed_by_m1_storage") is True,
        "CAMERA_PROBE_STORAGE_REQUIRED",
        "Verify the original store before retaining a probe record.",
    )
    attempt = dict(
        action_id=action_id,
        record=None,
        events=[],
        software={},
        status="ORIGINAL_READ_PENDING",
    )
    setup._probe_attempts[action_id] = attempt
    progress(
        "Verifying original camera setup and installed software; no device is opened."
    )
    with session.stage_transaction(
        expected_challenge_sha256=verification["challenge_sha256"]
    ) as tx:
        _, original = _read_original_evidence_under_lease(
            tx,
            bound=bound,
            expected_header_sha256=header,
            strict_workflow=True,
            check=check,
        )
        _need(
            canonical(original) == expected,
            "CAMERA_PROBE_ORIGINAL_CHANGED",
            "The original setup differs from the preview.",
        )
        assert (
            original is not None
        )  # Full original readback matched the cached boundary.
        check()
        if action_id == PREPARE:
            runtime = reviewed_activation_runtime_candidate(
                setup.workspace, purpose="probe", source_sha256=setup.source_sha256
            )
            plan = PhysicalCameraActivationCampaign.from_enrollment(
                setup.workspace,
                Path(bound["directory"]) / "native-camera-output",
                enrollment=enrollment,
                launch_session_id=setup.launch_id,
                source_sha256=setup.source_sha256,
                cell_id=bound["cell_id"],
                session_id=bound["session_id"],
                runtime=runtime,
            ).plan()
        else:
            preparation = CameraProbePreparation(
                canonical(
                    original["camera_probe_preparation"]["preparation"]["document"]
                )
            )
            data = preparation.to_dict()
            _need(
                canonical(data["enrollment"]) == current_enrollment
                and data["plan"]["launch_session_id"] == setup.launch_id,
                "CAMERA_PROBE_REVIEW_CURRENTNESS",
                "Review requires the same preparation and current launch enrollment; reopening does not restore them.",
            )
        # These point-in-time software checks do not replace the checks inside
        # a later admitted native campaign. Each keeps its existing 10s cap.
        for purpose in ("probe", "capture"):
            check()
            candidate = reviewed_activation_runtime_candidate(
                setup.workspace, purpose=purpose, source_sha256=setup.source_sha256
            )
            attempt["software"][purpose] = verify_reviewed_activation_runtime(
                candidate, cancellation=cancellation, deadline_ns=deadline_ns
            )
            check()
        subject: CameraProbePreparation | CameraProbePreparationReview
        if action_id == PREPARE:
            entry = original["camera_mode_entry"]
            subject = build_camera_probe_preparation(
                preparation_id="cameraprobe-" + uuid4().hex,
                entry_sha256=entry["entry"]["evidence_sha256"],
                entry_event_sha256=entry["events"][0]["event_sha256"],
                plan=plan,
                enrollment=enrollment.export_snapshot(),
                software=attempt["software"],
                operator_id=operator_id,
                prepared_at_utc_ns=time_ns(),
            )
            verify_probe_preparation_context(original, subject, bound)
            kind, phase, next_state = "preparation", "PREPARED", V2StageState.BLOCKED
        else:
            subject = build_camera_probe_preparation_review(
                preparation, reviewer_id=operator_id, reviewed_at_utc_ns=time_ns()
            )
            kind, phase, next_state = (
                "review",
                "REVIEWED",
                V2StageState.WAITING_OPERATOR,
            )
        data = subject.to_dict()
        record = dict(
            document=data,
            evidence_sha256=subject.sha256,
            reference=None,
            retention="COLLECTED_NOT_M1_RETAINED",
        )
        attempt.update(record=record, status="RECORD_COLLECTED")
        check()
        record["retention"] = "M1_PUBLICATION_UNCONFIRMED"
        if action_id == REVIEW:
            # Generic evidence storage deliberately refuses BLOCKED stages.
            # The exact original review has a closed stage-only M1 writer.
            ref = tx.store_camera_probe_review(
                subject.payload,
                captured_at_ns=time_ns(),
                expected_head_sha256=tx.snapshot().head.head_sha256,
            )
        else:
            ref = tx.store_evidence(
                STAGE_ORDER[4],
                subject.payload,
                label=camera_probe_label(kind, data["preparation_id"]),
                media_type="application/json",
                captured_at_ns=time_ns(),
                expected_head_sha256=tx.snapshot().head.head_sha256,
            )
        record.update(
            reference=ref.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
        )
        check()
        _need(
            tx.read_stage_evidence(ref) == subject.payload,
            "CAMERA_PROBE_READBACK_CHANGED",
            "The stored record did not read back exactly.",
        )
        record["retention"] = "M1_FULL_BYTES_READ_BACK"
        cited = [ref]
        if action_id == REVIEW:
            cited.append(
                _parse_evidence_reference(
                    original["camera_probe_preparation"]["preparation"]["reference"]
                )
            )
        check()
        attempt["status"] = "COMMIT_UNCONFIRMED"
        snapshot = tx.commit_stage_state(
            STAGE_ORDER[4],
            next_state,
            occurred_at_ns=time_ns(),
            detail_code=camera_probe_event(phase, data["preparation_id"]),
            expected_head_sha256=tx.snapshot().head.head_sha256,
            evidence=tuple(sorted(cited, key=lambda item: item.evidence_id)),
        )
        attempt["events"].append(snapshot.committed_events[-1].to_dict())
        attempt["status"] = "COMMITTED_READBACK_PENDING"
        check()
    check()
    session.refresh(cancellation=cancellation, progress=progress)
    check()
    result = session.read_original_source_workflow(
        expected_header_sha256=header,
        cancellation=cancellation,
        progress=progress,
        deadline_ns=deadline_ns,
    )
    check()
    row = result["camera_probe_preparation"]
    _need(
        row[kind]["document"] == data
        and row["state"]
        == (
            "PREPARED_REVIEW_REQUIRED"
            if action_id == PREPARE
            else "REVIEWED_FOR_ADMISSION"
        ),
        "CAMERA_PROBE_RESULT_CHANGED",
        "The resulting original workflow differs from the requested record.",
    )
    setup._adopt_source_workflow(result)
    attempt["status"] = "ORIGINAL_READ_BACK"
    check()
    progress(
        "Probe record retained and reread; camera admission and device access remain separate."
    )
    check()
    return deepcopy(row)
