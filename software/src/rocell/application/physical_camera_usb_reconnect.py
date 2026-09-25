"""Inert reconnect preparation; original admission remains the owner's job.

The reconnect report precedes three freshly logged metadata acquisitions. This
codec checks their exact documents and chronology, not the truth of a caller's
JSON or original-store membership. Nothing here starts a process or queries a
camera. Public v1-v11 readers and BASELINE-only preparation remain unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from . import physical_camera_usb_qualification as qualification
from .physical_camera_usb_absence import (
    _record,
    _original_usb_absence_baseline,
    original_usb_absence_baseline,
)
from .physical_camera_usb_baseline import _file_report
from .physical_camera_usb_phase import USB_PHASE_ROLE_BYTES
from .physical_camera_usb_reconnect_constants import (
    USB_RECONNECT_ROLE_BYTES,
    USB_RECONNECT_EVENTS,
    usb_reconnect_event,
    usb_reconnect_label,
)
from .physical_camera_selection import selection_from_enrollment_snapshot
from .physical_onboarding import EvidenceReference, STAGE_ORDER
from .physical_onboarding_v2 import V2JournalEvent, V2StageState, _parse_event
from .physical_usb_identity_campaign import (
    UsbIdentityOperation,
    verify_phase_operation_context,
)
from .physical_usb_presence_phase import UsbPresenceQualificationPhase
from .physical_usb_reconnect_phase import (
    FLAGS,
    UsbReconnectOperatorEvent,
    verify_usb_reconnect_predecessor,
)
from .wizard_native_camera_enrollment import verify_native_camera_enrollment_snapshot
from rocell.providers.windows.usb_identity_registration import (
    UsbIdentityRuntimeRegistration,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest

PREPARATION_SCHEMA = "rocell.usb_reconnect_preparation.v1"
MEANING = "FRESH_RECONNECT_METADATA_AND_FILES_NOT_QUERY_PERMISSION"
_STAGE = STAGE_ORDER[3]
_ACQUISITIONS = (
    ("GENERIC_INVENTORY", "inventory_devices"),
    ("NATIVE_INVENTORY", "native_camera_inventory"),
    ("NATIVE_IDENTITY", "native_camera_identity"),
)
_FIELDS = {
    "schema",
    "plan_sha256",
    "plan_reference",
    "absence_sha256",
    "absence_reference",
    "phase_id",
    "phase_start_event",
    "operator_event",
    "operator_event_reference",
    "enrollment_sha256",
    "enrollment_reference",
    "acquisition_ledger",
    "operation",
    "operation_sha256",
    "runtime_report",
    "prepared_at_utc_ns",
    "operator_id",
    "meaning",
    *FLAGS,
}


def _need(ok: bool) -> None:
    if not ok:
        raise ValueError("USB_RECONNECT_PREPARATION_INVALID")


def original_usb_reconnect_predecessor(workflow: dict[str, Any]) -> dict[str, Any]:
    """Join the complete v11 subjects supplied by the authenticated owner.

    This is a data adapter, not an original-store reader. The caller must first
    authenticate the entire workflow and its journal/campaign membership; a
    saved diagnostic copy cannot resume a session or provide admission facts.
    """
    return _original_usb_reconnect_predecessor(workflow, successor=False)


def original_usb_reconnect_predecessor_v12(workflow: dict[str, Any]) -> dict[str, Any]:
    """Extract unchanged predecessor bytes from an authenticated v12 workflow.

    This separate entry keeps the v11 adapter's closed version contract. The
    original reader must first verify the entire successor and historical
    inventories; neither changing a schema label nor this adapter supplies that
    authentication or makes a reopened phase resumable.
    """
    return _original_usb_reconnect_predecessor(workflow, successor=True)


def _original_usb_reconnect_predecessor(
    workflow: dict[str, Any],
    *,
    successor: bool,
    reboot_successor: bool = False,
    complete_successor: bool = False,
) -> dict[str, Any]:
    _need(
        type(workflow) is dict
        and type(successor) is bool
        and type(reboot_successor) is bool
        and type(complete_successor) is bool
        and (not complete_successor or reboot_successor)
        and (not reboot_successor or successor)
        and workflow.get("schema")
        == (
            "rocell.physical_camera_source_workflow_readback.v14"
            if complete_successor
            else (
                "rocell.physical_camera_source_workflow_readback.v13"
                if reboot_successor
                else (
                    "rocell.physical_camera_source_workflow_readback.v12"
                    if successor
                    else "rocell.physical_camera_source_workflow_readback.v11"
                )
            )
        )
    )
    if successor:
        reconnect = workflow.get("usb_qualification_reconnect")
        _need(type(reconnect) is dict and reconnect.get("phase") == "AFTER_RECONNECT")
        baseline = _original_usb_absence_baseline(
            workflow,
            reconnect_successor=True,
            reboot_successor=reboot_successor,
            complete_successor=complete_successor,
        )
    else:
        baseline = original_usb_absence_baseline(workflow)
    phase = workflow["usb_qualification_absence"]
    _need(
        type(phase) is dict
        and phase["phase"] == "RECONNECT_ABSENCE"
        and phase["state"] == "RETAINED_BLOCKED"
    )
    raw, ref = _record(phase["phase_record"])
    result: dict[str, Any] = dict(
        original_baseline=baseline,
        absence=UsbPresenceQualificationPhase(raw),
        absence_reference=ref,
        absence_sources={
            name: _record(phase[role])[0]
            for name, role in (
                ("operation", "operation"),
                ("operator_event", "operator_event"),
                ("owned_presence_run", "execution"),
                ("host_boot", "host_boot"),
            )
        },
    )
    original = phase["original_campaign"]
    _need(
        type(original) is dict
        and original["result"] is not None
        and original["result"]["state"] == "SEALED_KNOWN"
        and original["result"]["quarantine_latched"] is False
        and original["evidence"] == phase["execution"]["document"]
        and original["evidence_sha256"] == phase["execution"]["evidence_sha256"]
    )
    verify_usb_reconnect_predecessor(
        original_baseline=baseline,
        absence=result["absence"],
        absence_sources=result["absence_sources"],
    )
    return result


def _ref(value: Any, sha: str, size: int | None = None) -> EvidenceReference:
    result = qualification._reference(value)
    _need(result.payload_sha256 == sha)
    if size is not None:
        _need(result.payload_bytes == size)
    return result


def _ledger(d: dict[str, Any], binding: dict[str, Any]) -> None:
    """Check current interval/launch and exact successful publication order.

    The existing ledger wire schema is phase-neutral. Its original completion
    log must still be authenticated by the service; timestamps alone cannot
    prove that an acquisition occurred.
    """
    ledger, report = d["acquisition_ledger"], d["operator_event"]
    qualification._exact(
        ledger,
        {
            "schema",
            "source_sha256",
            "session_id",
            "launch_session_id",
            "trial_id",
            "phase_id",
            "phase_started_at_utc_ns",
            "entries",
        },
    )
    _need(
        ledger["schema"] == "rocell.usb_phase_metadata_acquisition_ledger.v1"
        and all(
            ledger[k] == binding[k] for k in ("source_sha256", "session_id", "trial_id")
        )
        and ledger["launch_session_id"] == report["launch_session_id"]
        and ledger["phase_id"] == d["phase_id"]
        and type(ledger["phase_started_at_utc_ns"]) is int
        and ledger["phase_started_at_utc_ns"]
        == d["phase_start_event"]["occurred_at_ns"]
        and type(ledger["entries"]) is list
        and len(ledger["entries"]) == len(_ACQUISITIONS)
    )
    previous = report["reported_at_utc_ns"]
    ids: set[str] = set()
    for row, (role, action) in zip(ledger["entries"], _ACQUISITIONS):
        qualification._exact(
            row,
            {
                "role",
                "action_id",
                "operation_id",
                "started_at_utc_ns",
                "finished_at_utc_ns",
                "published_at_utc_ns",
                "document_sha256",
                "result_sha256",
                "completion_logged",
            },
        )
        qualification._identifier(row["operation_id"])
        _need(
            row["role"] == role
            and row["action_id"] == action
            and row["operation_id"] not in ids
            and row["operation_id"] != d["phase_id"]
            and row["completion_logged"] is True
        )
        for key in ("started_at_utc_ns", "finished_at_utc_ns", "published_at_utc_ns"):
            qualification._integer(row[key], 1)
        _need(
            previous
            <= row["started_at_utc_ns"]
            <= row["finished_at_utc_ns"]
            <= row["published_at_utc_ns"]
            <= d["prepared_at_utc_ns"]
        )
        qualification._sha(row["document_sha256"])
        qualification._sha(row["result_sha256"])
        ids.add(row["operation_id"])
        previous = row["published_at_utc_ns"]


def _load(payload: bytes) -> dict[str, Any]:
    d = qualification._load(payload, USB_RECONNECT_ROLE_BYTES["preparation"])
    qualification._exact(d, _FIELDS)
    _need(
        d["schema"] == PREPARATION_SCHEMA
        and d["meaning"] == MEANING
        and all(d[k] is False for k in FLAGS)
    )
    operation = UsbIdentityOperation(canonical(d["operation"]))
    op = operation.to_dict()
    _need(op["schema"] == "rocell.physical_usb_identity_operation.v2")
    plan = qualification.UsbQualificationPlan(canonical(op["qualification_plan"]))
    p = plan.to_dict()
    qualification._sha(d["absence_sha256"])
    verify_phase_operation_context(
        operation, plan, "AFTER_RECONNECT", d["phase_id"], d["absence_sha256"]
    )
    _need(
        p["mode"] == "PHYSICAL"
        and d["plan_sha256"] == plan.sha256
        and d["operation_sha256"] == operation.sha256
    )
    report = UsbReconnectOperatorEvent(canonical(d["operator_event"]))
    r = report.to_dict()
    _need(
        r["binding"] == p["binding"]
        and r["plan_sha256"] == plan.sha256
        and r["predecessor_sha256"] == d["absence_sha256"]
        and r["phase_id"] == d["phase_id"]
        and r["operator_id"] == d["operator_id"]
    )
    refs = (
        _ref(d["plan_reference"], plan.sha256, len(plan.payload)),
        _ref(d["absence_reference"], d["absence_sha256"]),
        _ref(d["operator_event_reference"], report.sha256, len(report.payload)),
        _ref(d["enrollment_reference"], d["enrollment_sha256"]),
    )
    _need(
        len({ref.evidence_id for ref in refs}) == len(refs)
        and 0 < refs[1].payload_bytes <= 16 * 1024
        and 0 < refs[3].payload_bytes <= USB_RECONNECT_ROLE_BYTES["enrollment"]
    )
    event = _parse_event(d["phase_start_event"])
    _need(
        event.stage is _STAGE
        and event.session_id == p["binding"]["session_id"]
        and event.session_header_sha256 == p["binding"]["header_sha256"]
        and event.previous_state is V2StageState.BLOCKED
        and event.state is V2StageState.WAITING_OPERATOR
        and event.detail_code
        == usb_reconnect_event("PREPARATION_REQUESTED", d["phase_id"])
        and event.evidence == (refs[1],)
        and event.occurred_at_ns == r["phase_started_at_utc_ns"]
        and event.occurred_at_ns >= p["created_at_utc_ns"]
    )
    qualification._integer(d["prepared_at_utc_ns"], r["reported_at_utc_ns"])
    qualification._text(d["operator_id"], 64)
    _need(all(32 <= ord(c) <= 126 for c in d["operator_id"]))
    _ledger(d, p["binding"])
    _file_report(
        d["runtime_report"], UsbIdentityRuntimeRegistration(canonical(op["runtime"]))
    )
    return d


@dataclass(frozen=True, slots=True)
class UsbReconnectPreparation:
    payload: bytes

    def __post_init__(self) -> None:
        _load(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload)


def build_usb_reconnect_preparation(
    *,
    original_baseline: dict[str, Any],
    absence: UsbPresenceQualificationPhase,
    absence_sources: dict[str, bytes],
    absence_reference: EvidenceReference,
    phase_start_event: V2JournalEvent,
    phase_id: str,
    operator_event: UsbReconnectOperatorEvent,
    operator_event_reference: EvidenceReference,
    enrollment: bytes,
    enrollment_reference: EvidenceReference,
    acquisition_ledger: dict[str, Any],
    operation: UsbIdentityOperation,
    runtime_report: dict[str, Any],
    prepared_at_utc_ns: int,
    operator_id: str,
) -> UsbReconnectPreparation:
    """Rebuild full sources, retaining the acquisition ledger without replay.

    Caller authenticates the supplied references, Start event and ledger against
    the original store/log. A closed content-shaped reference is not that proof.
    """
    absence = verify_usb_reconnect_predecessor(
        original_baseline=original_baseline,
        absence=absence,
        absence_sources=absence_sources,
    )
    _need(
        type(absence_reference) is EvidenceReference
        and type(phase_start_event) is V2JournalEvent
        and type(operator_event) is UsbReconnectOperatorEvent
        and type(operator_event_reference) is EvidenceReference
        and type(enrollment_reference) is EvidenceReference
        and type(operation) is UsbIdentityOperation
    )
    plan = original_baseline["plan"]
    _ref(absence_reference, absence.sha256, len(absence.payload))
    report = operator_event.to_dict()
    _need(
        report["baseline_sha256"] == original_baseline["baseline"].sha256
        and report["predecessor_sha256"] == absence.sha256
        and report["phase_started_at_utc_ns"]
        >= absence.to_dict()["context"]["finished_at_utc_ns"]
        and phase_id
        not in {
            absence.to_dict()["context"]["operation_id"],
            original_baseline["baseline"].to_dict()["context"]["operation_id"],
        }
    )
    raw = qualification._load(enrollment, USB_RECONNECT_ROLE_BYTES["enrollment"])
    checked = UsbReconnectPreparation(
        canonical(
            dict(
                schema=PREPARATION_SCHEMA,
                plan_sha256=plan.sha256,
                plan_reference=original_baseline["plan_reference"].to_dict(),
                absence_sha256=absence.sha256,
                absence_reference=absence_reference.to_dict(),
                phase_id=phase_id,
                phase_start_event=phase_start_event.to_dict(),
                operator_event=report,
                operator_event_reference=operator_event_reference.to_dict(),
                enrollment_sha256=digest(enrollment),
                enrollment_reference=enrollment_reference.to_dict(),
                acquisition_ledger=acquisition_ledger,
                operation=operation.to_dict(),
                operation_sha256=operation.sha256,
                runtime_report=runtime_report,
                prepared_at_utc_ns=prepared_at_utc_ns,
                operator_id=operator_id,
                meaning=MEANING,
                **FLAGS,
            )
        )
    )
    d = checked.to_dict()
    _need(canonical(d["operation"]["qualification_plan"]) == plan.payload)
    _ref(enrollment_reference, digest(enrollment), len(enrollment))
    binding = plan.to_dict()["binding"]
    launch = d["acquisition_ledger"]["launch_session_id"]
    verified = verify_native_camera_enrollment_snapshot(
        raw,
        source_sha256=binding["source_sha256"],
        launch_session_id=launch,
    )
    selection = selection_from_enrollment_snapshot(
        verified,
        source_sha256=binding["source_sha256"],
        launch_session_id=launch,
    )
    _need(
        selection is not None
        and selection.identity_document == d["operation"]["selection"]
    )
    documents = (
        verified["generic_review"]["inventory_report"],
        verified["inventory_packet"],
        verified["identity_packet"],
    )
    ids = (
        verified["generic_review"]["operation_id"],
        verified["view"]["inventory_operation_id"],
        verified["view"]["identity"]["operation_id"],
    )
    # A newly written ledger must not relabel the baseline's old acquisitions
    # with later timestamps, even when both phases use the same app launch.
    baseline_enrollment = qualification._load(
        original_baseline["baseline_sources"]["native_enrollment"],
        USB_RECONNECT_ROLE_BYTES["enrollment"],
    )
    previous_ids = {
        baseline_enrollment["generic_review"]["operation_id"],
        baseline_enrollment["view"]["inventory_operation_id"],
        baseline_enrollment["view"]["identity"]["operation_id"],
        original_baseline["baseline"].to_dict()["context"]["operation_id"],
        absence.to_dict()["context"]["operation_id"],
    }
    _need(not previous_ids.intersection(ids))
    for row, document, operation_id in zip(
        d["acquisition_ledger"]["entries"], documents, ids
    ):
        _need(
            row["document_sha256"] == digest(canonical(document))
            and row["operation_id"] == operation_id
        )
    return checked


def verify_usb_reconnect_preparation(
    payload: bytes,
    *,
    expected_sha256: str,
    original_baseline: dict[str, Any],
    absence: UsbPresenceQualificationPhase,
    absence_sources: dict[str, bytes],
    absence_reference: EvidenceReference,
    phase_start_event: V2JournalEvent,
    phase_id: str,
    operator_event: UsbReconnectOperatorEvent,
    operator_event_reference: EvidenceReference,
    enrollment: bytes,
    enrollment_reference: EvidenceReference,
) -> UsbReconnectPreparation:
    """Compare independent original bytes, not only a self-consistent hash."""
    checked = UsbReconnectPreparation(payload)
    qualification._sha(expected_sha256)
    _need(checked.sha256 == expected_sha256)
    d = checked.to_dict()
    rebuilt = build_usb_reconnect_preparation(
        original_baseline=original_baseline,
        absence=absence,
        absence_sources=absence_sources,
        absence_reference=absence_reference,
        phase_start_event=phase_start_event,
        phase_id=phase_id,
        operator_event=operator_event,
        operator_event_reference=operator_event_reference,
        enrollment=enrollment,
        enrollment_reference=enrollment_reference,
        acquisition_ledger=d["acquisition_ledger"],
        operation=UsbIdentityOperation(canonical(d["operation"])),
        runtime_report=d["runtime_report"],
        prepared_at_utc_ns=d["prepared_at_utc_ns"],
        operator_id=d["operator_id"],
    )
    _need(rebuilt.payload == checked.payload)
    return checked
