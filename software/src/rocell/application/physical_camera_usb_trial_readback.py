"""Original file-only USB trial declaration, not phase acquisition or replay.

The existing plan codec is reused unchanged. Only this reader owns the new
two-event/one-role suffix over a complete audited camera snapshot.
"""

from __future__ import annotations

import re
from typing import Any

from .physical_camera_prerequisites import PhysicalCameraPrerequisites
from .physical_camera_usb_baseline import METADATA_ROLES, USB_ROLE_BYTES
from .physical_camera_usb_qualification import (
    UsbQualificationPlan,
    build_usb_qualification_plan,
    verify_usb_qualification_plan,
)
from .physical_onboarding import STAGE_ORDER, _parse_evidence_reference
from .physical_onboarding_v2 import V2SessionSnapshot, V2StageState
from .physical_received_camera_submission import (
    ReceivedCameraSubmission,
    verify_received_camera_submission_assessment,
    verify_received_camera_submission_review,
)
from .usb_identity_stage_policy import usb_identity_stage_policy
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
)

TRIAL_PLAN_BYTES = 16 * 1024
TRIAL_LABEL_PREFIX = "camera-usb-qualification-plan-v1:"
TRIAL_LABEL = re.compile(r"camera-usb-qualification-plan-v1:(usbtrial-[0-9a-f]{32})")
TRIAL_EVENT = re.compile(
    r"CAMERA_USB_QUALIFICATION_(REQUESTED|DECLARED)_([0-9A-F]{32})"
)


def _need(ok: bool) -> None:
    if not ok:
        raise ValueError("USB_QUALIFICATION_ORIGINAL_REQUIRED")


def usb_qualification_event(phase: str, trial_id: str) -> str:
    _need(phase in {"REQUESTED", "DECLARED"} and type(trial_id) is str)
    _need(re.fullmatch(r"usbtrial-[0-9a-f]{32}", trial_id) is not None)
    return "CAMERA_USB_QUALIFICATION_" + phase + "_" + trial_id[9:].upper()


def usb_qualification_predecessor_references(workflow: dict[str, Any]) -> tuple:
    """Resolve server-read originals; this is not an independent M1 audit."""
    _need(
        type(workflow) is dict
        and workflow.get("schema")
        in {
            "rocell.physical_camera_source_workflow_readback.v7",
            "rocell.physical_camera_source_workflow_readback.v8",
        }
    )
    _need(workflow.get("configuration_epochs") is not None)
    _need(
        workflow.get("state") == "PASS" and bool(workflow.get("camera_identity_cycles"))
    )
    _need(workflow["received_camera_cycles"][-1]["state"] == "REVIEWED_PASS")
    latest = workflow["camera_identity_cycles"][-1]
    _need(latest["state"] == "REVIEWED_BLOCKED")
    records = [latest[role] for role in METADATA_ROLES]
    baseline = workflow.get("usb_baseline")
    if workflow["schema"].endswith(".v8"):
        _need(type(baseline) is dict and baseline["state"] == "RETAINED_BLOCKED")
        assert isinstance(baseline, dict)
        original = baseline["original_campaign"]
        _need(original is not None and original["result"] is not None)
        _need(
            original["result"]["state"] == "SEALED_KNOWN"
            and original["result"]["quarantine_latched"] is False
            and original["evidence"] is not None
        )
        run = OwnedUsbIdentityRunEvidence(canonical(original["evidence"]))
        effect = run.bounded_effect_summary()
        _need(
            effect["current_complete"]
            and effect["process_cleanup_confirmed"]
            and effect["usb_cleanup_confirmed"]
        )
        records += [baseline[role] for role in USB_ROLE_BYTES]
    else:
        _need(baseline is None)
    refs = tuple(_parse_evidence_reference(record["reference"]) for record in records)
    _need(len({ref.evidence_id for ref in refs}) == len(refs))
    return tuple(sorted(refs, key=lambda ref: ref.evidence_id))


def _received(prerequisites: PhysicalCameraPrerequisites, workflow: dict[str, Any]):
    _need(type(prerequisites) is PhysicalCameraPrerequisites)
    row = workflow["received_camera_cycles"][-1]
    submission = ReceivedCameraSubmission(
        canonical(row["submission"]["document"]), prerequisites
    )
    assessment = verify_received_camera_submission_assessment(
        canonical(row["assessment"]["document"]),
        submission=submission,
        expected_assessment_sha256=row["assessment"]["evidence_sha256"],
    )
    review = verify_received_camera_submission_review(
        canonical(row["review"]["document"]),
        submission=submission,
        assessment=assessment,
        expected_review_sha256=row["review"]["evidence_sha256"],
    )
    return submission, assessment, review


def build_original_usb_qualification_plan(
    prerequisites: PhysicalCameraPrerequisites,
    workflow: dict[str, Any],
    *,
    trial_id: str,
    operator_id: str,
    launch_session_id: str,
    cable_label: str,
    port_label: str,
    created_at_utc_ns: int,
) -> UsbQualificationPlan:
    """Build from freshly authenticated original context; performs no I/O."""
    usb_qualification_predecessor_references(workflow)
    usb_qualification_event("REQUESTED", trial_id)
    submission, assessment, review = _received(prerequisites, workflow)
    bound = workflow["binding"]
    policy = usb_identity_stage_policy().to_dict()
    row = workflow["received_camera_cycles"][-1]
    return build_usb_qualification_plan(
        binding=dict(
            trial_id=trial_id,
            source_sha256=bound["source_sha256"],
            cell_id=bound["cell_id"],
            session_id=bound["session_id"],
            header_sha256=workflow["session_header_sha256"],
            origin_launch_id=bound["launch_id"],
            prerequisites_sha256=digest(prerequisites.payload),
            identity_entry_sha256=workflow["camera_identity_request"]["event_sha256"],
            stage_policy_sha256=usb_identity_stage_policy().sha256,
            stage_catalog_sha256=policy["base_catalog_sha256"],
            stage_order_sha256=policy["canonical_stage_order_sha256"],
        ),
        mode="PHYSICAL",
        operator_id=operator_id,
        launch_session_id=launch_session_id,
        created_at_utc_ns=created_at_utc_ns,
        cable_label=cable_label,
        port_label=port_label,
        received_submission=submission,
        received_assessment=assessment,
        received_review=review,
        received_references=[
            row[role]["reference"] for role in ("submission", "assessment", "review")
        ],
    )


def verify_usb_qualification_trial_workflow(
    bound,
    snapshot: V2SessionSnapshot,
    expected_header_sha256,
    roles,
    intake_packages,
    qualification_packages,
    qualification_originals,
    static_packages,
    received_packages,
    received_originals,
    identity_packages,
    usb_packages,
    trial_packages,
    *,
    original_campaigns=(),
) -> dict[str, Any]:
    return _verify_usb_qualification_trial_prefix(
        bound,
        snapshot,
        expected_header_sha256,
        roles,
        intake_packages,
        qualification_packages,
        qualification_originals,
        static_packages,
        received_packages,
        received_originals,
        identity_packages,
        usb_packages,
        trial_packages,
        original_campaigns=original_campaigns,
        prefix_event_count=None,
        usb_phase_evidence_ids=frozenset(),
    )


def _verify_usb_qualification_trial_prefix(
    bound,
    snapshot,
    expected_header_sha256,
    roles,
    intake_packages,
    qualification_packages,
    qualification_originals,
    static_packages,
    received_packages,
    received_originals,
    identity_packages,
    usb_packages,
    trial_packages,
    *,
    original_campaigns=(),
    prefix_event_count,
    usb_phase_evidence_ids,
    usb_absence_evidence_ids=frozenset(),
    usb_absence_extension=False,
    usb_reconnect_extension=False,
    usb_reboot_extension: bool = False,
    usb_reboot_evidence_ids: frozenset[str] = frozenset(),
    usb_complete_extension: bool = False,
    camera_mode_entry=None,
    usb_complete_evidence_ids: frozenset[str] = frozenset(),
    usb_reconnect_evidence_ids=frozenset(),
) -> dict[str, Any]:
    from .physical_camera_session import (
        _require,
        PhysicalCameraSessionError,
        SOURCE_WORKFLOW_USB_TRIAL_SCHEMA,
    )
    from .physical_camera_identity_readback import _verify_camera_identity_prefix
    from .physical_camera_usb_readback import _verify_usb_baseline_prefix
    from .physical_camera_prerequisites import verify_physical_camera_prerequisites

    error = "CAMERA_SESSION_USB_TRIAL_INVALID"
    from .physical_camera_mode_entry_layout import _camera_mode_entry_extension

    mode_evidence_ids, mode_event_count = _camera_mode_entry_extension(
        snapshot, camera_mode_entry
    )
    _require(camera_mode_entry is None or usb_complete_extension is True, error)
    _require(type(snapshot) is V2SessionSnapshot, error)
    _require(
        type(usb_phase_evidence_ids) is frozenset
        and len(usb_phase_evidence_ids) <= 9
        and (prefix_event_count is not None or not usb_phase_evidence_ids),
        error,
    )
    _require(
        type(usb_complete_extension) is bool
        and (not usb_complete_extension or usb_reboot_extension)
        and type(usb_complete_evidence_ids) is frozenset
        and len(usb_complete_evidence_ids) <= 3
        and (usb_complete_extension or not usb_complete_evidence_ids)
        and usb_complete_evidence_ids.isdisjoint(usb_reboot_evidence_ids)
        and type(usb_reboot_extension) is bool
        and (not usb_reboot_extension or usb_reconnect_extension)
        and type(usb_reboot_evidence_ids) is frozenset
        and len(usb_reboot_evidence_ids) <= 11
        and (usb_reboot_extension or not usb_reboot_evidence_ids)
        and usb_reboot_evidence_ids.isdisjoint(
            usb_absence_evidence_ids
            | usb_reconnect_evidence_ids
            | usb_phase_evidence_ids
        ),
        error,
    )
    _require(
        type(usb_reconnect_extension) is bool
        and (not usb_reconnect_extension or usb_absence_extension),
        error,
    )
    _require(
        type(usb_absence_extension) is bool
        and type(usb_absence_evidence_ids) is frozenset
        and len(usb_absence_evidence_ids) <= 9
        and (usb_absence_extension or not usb_absence_evidence_ids)
        and (not usb_absence_extension or prefix_event_count is not None)
        and usb_absence_evidence_ids.isdisjoint(usb_phase_evidence_ids),
        error,
    )
    _require(
        type(usb_reconnect_evidence_ids) is frozenset
        and len(usb_reconnect_evidence_ids) <= 11
        and (usb_reconnect_extension or not usb_reconnect_evidence_ids)
        and usb_reconnect_evidence_ids.isdisjoint(
            usb_absence_evidence_ids | usb_phase_evidence_ids
        ),
        error,
    )
    if prefix_event_count is not None:
        _require(
            type(prefix_event_count) is int
            and 0 < prefix_event_count < len(snapshot.committed_events)
            and len(snapshot.committed_events) - prefix_event_count - mode_event_count
            <= (
                (35 if usb_complete_extension else 32)
                if usb_reboot_extension
                else (
                    25
                    if usb_reconnect_extension
                    else (18 if usb_absence_extension else 8)
                )
            ),
            error,
        )
    starts = [
        (i, e)
        for i, e in enumerate(snapshot.committed_events)
        if e.detail_code.startswith("CAMERA_USB_QUALIFICATION_REQUESTED_")
    ]
    _require(len(starts) == 1 and len(trial_packages) <= 1, error)
    index, request = starts[0]
    match = TRIAL_EVENT.fullmatch(request.detail_code)
    _require(match is not None and index > 0, error)
    assert match is not None
    trial_id = "usbtrial-" + match[2].lower()
    events = snapshot.committed_events[index:prefix_event_count]
    _require(1 <= len(events) <= 2, error)
    inventory = {ref.evidence_id: ref.to_dict() for ref in snapshot.evidence}
    ids = frozenset(trial_packages)
    _require(
        not ids.intersection(identity_packages) and not ids.intersection(usb_packages),
        error,
    )
    _require(
        usb_phase_evidence_ids.isdisjoint(
            ids | frozenset(identity_packages) | frozenset(usb_packages)
        ),
        error,
    )
    original_args = (
        bound,
        snapshot,
        expected_header_sha256,
        roles,
        intake_packages,
        qualification_packages,
        qualification_originals,
        static_packages,
        received_packages,
        received_originals,
        identity_packages,
    )
    if usb_packages or any(
        e.detail_code.startswith("CAMERA_USB_INSPECTION_STARTED_")
        for e in snapshot.committed_events[:index]
    ):
        original = _verify_usb_baseline_prefix(
            *original_args,
            usb_packages,
            original_campaigns=original_campaigns,
            prefix_event_count=index,
            trial_evidence_ids=ids,
            usb_phase_evidence_ids=usb_phase_evidence_ids,
            usb_phase_extension=prefix_event_count is not None,
            usb_absence_evidence_ids=usb_absence_evidence_ids,
            usb_absence_extension=usb_absence_extension,
            usb_reconnect_extension=usb_reconnect_extension,
            usb_reboot_extension=usb_reboot_extension,
            usb_reconnect_evidence_ids=usb_reconnect_evidence_ids,
            usb_reboot_evidence_ids=usb_reboot_evidence_ids,
            usb_complete_extension=usb_complete_extension,
            camera_mode_entry=camera_mode_entry,
            usb_complete_evidence_ids=usb_complete_evidence_ids,
        )
    else:
        _require(not original_campaigns, error)
        original = _verify_camera_identity_prefix(
            *original_args,
            prefix_event_count=index,
            usb_evidence_ids=frozenset(),
            trial_evidence_ids=ids,
            usb_trial_extension=True,
            usb_phase_evidence_ids=usb_phase_evidence_ids,
            usb_phase_extension=prefix_event_count is not None,
            usb_absence_evidence_ids=usb_absence_evidence_ids,
            usb_absence_extension=usb_absence_extension,
            usb_reconnect_extension=usb_reconnect_extension,
            usb_reboot_extension=usb_reboot_extension,
            usb_reconnect_evidence_ids=usb_reconnect_evidence_ids,
            usb_reboot_evidence_ids=usb_reboot_evidence_ids,
            usb_complete_extension=usb_complete_extension,
            camera_mode_entry=camera_mode_entry,
            usb_complete_evidence_ids=usb_complete_evidence_ids,
        )
    try:
        refs = usb_qualification_predecessor_references(original)
        _require(
            request.stage is STAGE_ORDER[3]
            and request.state is V2StageState.WAITING_OPERATOR
            and request.evidence == refs,
            error,
        )
        plan_record = None
        if trial_packages:
            key, package = next(iter(trial_packages.items()))
            _require(
                set(package) == {"trial_id", "record"}
                and package["trial_id"] == trial_id,
                error,
            )
            plan_record = package["record"]
            _require(
                set(plan_record)
                == {"document", "evidence_sha256", "reference", "retention"}
                and plan_record["retention"] == "M1_FULL_BYTES_READ_BACK"
                and inventory.get(key) == plan_record["reference"],
                error,
            )
            raw = canonical(plan_record["document"])
            _require(
                0 < len(raw) <= TRIAL_PLAN_BYTES
                and len(raw) == plan_record["reference"]["payload_bytes"]
                and digest(raw)
                == plan_record["evidence_sha256"]
                == plan_record["reference"]["payload_sha256"],
                error,
            )
            prerequisites = verify_physical_camera_prerequisites(
                canonical(roles["prerequisites"]["document"]),
                expected_source_sha256=bound["source_sha256"],
                expected_session_id=bound["session_id"],
                expected_launch_session_id=bound["launch_id"],
                expected_evidence_sha256=roles["prerequisites"]["evidence_sha256"],
            )
            document = plan_record["document"]
            expected = build_original_usb_qualification_plan(
                prerequisites,
                original,
                trial_id=trial_id,
                **{
                    k: document[k]
                    for k in (
                        "operator_id",
                        "launch_session_id",
                        "cable_label",
                        "port_label",
                        "created_at_utc_ns",
                    )
                },
            )
            _require(
                expected.payload == raw
                and request.occurred_at_ns <= document["created_at_utc_ns"],
                error,
            )
            submission, assessment, review = _received(prerequisites, original)
            verify_usb_qualification_plan(
                raw,
                expected_sha256=plan_record["evidence_sha256"],
                received_submission=submission,
                received_assessment=assessment,
                received_review=review,
            )
        if len(events) == 2:
            declaration = events[1]
            _require(
                plan_record is not None
                and declaration.stage is STAGE_ORDER[3]
                and declaration.state is V2StageState.REVIEW_PENDING
                and declaration.detail_code
                == usb_qualification_event("DECLARED", trial_id)
                and [ref.to_dict() for ref in declaration.evidence]
                == [plan_record["reference"]]
                and declaration.occurred_at_ns
                >= plan_record["document"]["created_at_utc_ns"],
                error,
            )
        _require(
            (
                prefix_event_count is not None
                or snapshot.stages[3].state is events[-1].state
            )
            and all(
                row.state is V2StageState.PENDING and not row.evidence_ids
                for row in snapshot.stages[4 if camera_mode_entry is None else 5 :]
            ),
            error,
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise PhysicalCameraSessionError(error) from exc
    return {
        **original,
        "schema": SOURCE_WORKFLOW_USB_TRIAL_SCHEMA,
        "usb_qualification_trial": dict(
            trial_id=trial_id,
            state=(
                "PLAN_DECLARED"
                if len(events) == 2
                else (
                    "PLAN_RETAINED_NOT_COMMITTED"
                    if plan_record is not None
                    else "INCOMPLETE"
                )
            ),
            request_event=request.to_dict(),
            declaration_event=None if len(events) == 1 else events[1].to_dict(),
            plan=plan_record,
        ),
    }
