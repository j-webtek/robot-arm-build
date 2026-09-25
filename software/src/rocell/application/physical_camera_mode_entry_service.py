"""One file-only stage transition inside the existing Setup operation owner.

This is not another connection manager. Setup owns the one-use queued action,
operation lock and final publication; Session owns original storage leases.
This function never opens a camera, serial port, native process or power path.
"""

from copy import deepcopy
from time import monotonic_ns, time_ns
from uuid import uuid4

from .physical_camera_mode_entry import (
    build_camera_mode_entry,
    camera_mode_entry_event,
)
from .physical_camera_mode_entry_readback import camera_mode_entry_binding
from .physical_camera_usb_complete_constants import SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA
from .physical_onboarding import STAGE_ORDER
from .physical_onboarding_v2 import V2StageState
from .wizard_actions import WizardError
from .wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.usb_identity_protocol import canonical

ACTION = "physical_camera_mode_enter"
TIMEOUT_NS = 180_000_000_000
_MESSAGES = {
    "CAMERA_MODE_DEADLINE_INVALID": "The entry action needs its original bounded deadline; its timeout cannot be renewed.",
    "CAMERA_MODE_ORIGINAL_REQUIRED": "Finish and publish the accepted original camera-identity review first. Partial or already entered records are read-only.",
    "CAMERA_MODE_QUEUE_REQUIRED": "Use Continue to camera setup and execute its one-time preview.",
    "CAMERA_MODE_CONTEXT_CHANGED": "The selected original setup changed during entry. No replacement is followed.",
    "CAMERA_MODE_INTERRUPTED": "Camera setup entry was stopped or expired. A committed file change cannot be undone by Stop.",
    "CAMERA_SETUP_SOURCE_CHANGED": "Application files changed. Reopen the matching original build before continuing; do not relabel stored evidence.",
    "CAMERA_MODE_STORAGE_REQUIRED": "The original camera store does not have a current successful storage verification.",
    "CAMERA_MODE_ORIGINAL_CHANGED": "The original identity review or resulting entry differs from the expected record.",
    "CAMERA_MODE_READBACK_CHANGED": "The newly stored entry did not read back exactly; it cannot advance camera setup.",
}


def entry_boundary(workflow) -> bool:
    """Cheap availability check, not original authentication or permission."""
    if type(workflow) is not dict:
        return False
    row = workflow.get("usb_qualification_complete")
    return (
        workflow.get("schema") == SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA
        and workflow.get("camera_mode_entry") is None
        and type(row) is dict
        and row.get("state") == "REVIEWED_PASS"
        and all(
            type(row.get(role)) is dict for role in ("series", "assessment", "review")
        )
        and type(row.get("events")) is list
        and len(row["events"]) == 3
        and type(workflow.get("configuration_epochs")) is dict
    )


def _need(ok, code):
    if not ok:
        raise WizardError(
            code,
            _MESSAGES.get(code, "Camera setup entry could not be verified.")
            + " Inspect/export the original diagnostics; no automatic replay.",
        )


def enter_camera_mode(setup, *, operator_id, cancellation, progress, deadline_ns):
    """Called only by Setup.perform while its existing operation lock is held.

    Read the full accepted predecessor under the same stage-only lease used to
    append the entry. A retained record is diagnostic evidence even if its later
    journal commit/readback fails. Completion remains PENDING until Arrival has
    durably logged the operation and checked cancellation/source again.
    """
    from .physical_camera_session import _read_original_evidence_under_lease

    started = monotonic_ns()
    _need(
        type(deadline_ns) is int and started < deadline_ns <= started + TIMEOUT_NS,
        "CAMERA_MODE_DEADLINE_INVALID",
    )
    session = setup.session
    bound = session.descriptor()
    workflow = setup.original_source_workflow()
    _need(entry_boundary(workflow), "CAMERA_MODE_ORIGINAL_REQUIRED")
    assert workflow is not None
    expected = canonical(workflow)
    original_binding = canonical(bound)
    header = workflow["session_header_sha256"]
    queue = setup._mode_entry_queue
    _need(
        type(queue) is dict and queue.get("claimed") is True,
        "CAMERA_MODE_QUEUE_REQUIRED",
    )

    def check(*, source=True):
        _need(
            setup.session is session
            and canonical(session.descriptor()) == original_binding
            and setup._mode_entry_queue is queue,
            "CAMERA_MODE_CONTEXT_CHANGED",
        )
        _need(
            not cancellation.is_set() and monotonic_ns() < deadline_ns,
            "CAMERA_MODE_INTERRUPTED",
        )
        if source:
            _need(
                source_fingerprint(setup.workspace) == setup.source_sha256,
                "CAMERA_SETUP_SOURCE_CHANGED",
            )
            check(source=False)

    check()
    verification = session.view()["verification"]
    _need(
        type(verification) is dict
        and verification.get("effects_allowed_by_m1_storage") is True,
        "CAMERA_MODE_STORAGE_REQUIRED",
    )
    progress(
        "Verifying the complete original camera identity review; no device is opened."
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
        _need(canonical(original) == expected, "CAMERA_MODE_ORIGINAL_CHANGED")
        binding = camera_mode_entry_binding(original, entry_launch_id=setup.launch_id)
        check()
        entry = build_camera_mode_entry(
            entry_id="cameramode-" + uuid4().hex,
            binding=binding,
            operator_id=operator_id,
            recorded_at_utc_ns=time_ns(),
        )
        document = entry.to_dict()
        check()
        # Preserve each known boundary BEFORE the next fallible operation.
        # Never replace an uncertain/partial outcome with success or zero I/O
        # counts from an unrelated operation.
        record = dict(
            document=document,
            evidence_sha256=entry.sha256,
            reference=None,
            retention="COLLECTED_NOT_M1_RETAINED",
        )
        setup._mode_entry_attempt = dict(
            entry_id=document["entry_id"], record=record, events=[]
        )
        # A storage call can fail after publishing bytes but before returning
        # its reference. Preserve uncertainty rather than claim nothing wrote.
        record["retention"] = "M1_PUBLICATION_UNCONFIRMED"
        reference = tx.store_camera_mode_entry(
            entry.payload,
            captured_at_ns=time_ns(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        record.update(
            reference=reference.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
        )
        check()
        _need(
            tx.read_stage_evidence(reference) == entry.payload,
            "CAMERA_MODE_READBACK_CHANGED",
        )
        record["retention"] = "M1_FULL_BYTES_READ_BACK"
        check()
        snapshot = tx.commit_stage_state(
            STAGE_ORDER[4],
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=time_ns(),
            detail_code=camera_mode_entry_event(document["entry_id"]),
            expected_head_sha256=tx.snapshot().head.head_sha256,
            evidence=(reference,),
        )
        setup._mode_entry_attempt["events"].append(
            snapshot.committed_events[-1].to_dict()
        )
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
    _need(
        type(result) is dict
        and result.get("camera_mode_entry", {}).get("state") == "ENTERED"
        and result["camera_mode_entry"]["entry"]["document"] == document,
        "CAMERA_MODE_ORIGINAL_CHANGED",
    )
    setup._adopt_source_workflow(result)
    check()
    progress(
        "Camera setup entry retained and reread. No capture, arm startup or movement was authorized."
    )
    check()
    return deepcopy(result["camera_mode_entry"])
