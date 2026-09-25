"""Inert reboot preparation and owner-supplied v12 original-data adapter.

No filesystem authentication, provider, registration or wizard action is
implemented here. The caller authenticates whole original workflows, Start
events and completion logs. Their closed JSON shape alone is not that proof.
Historical preparation contracts remain unchanged; only their phase-neutral
ledger and fixed runtime report validators are reused.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from . import physical_camera_usb_qualification as qualification
from .cell_commissioning_coordinator import (
    AttemptResult,
    ExactOperationPermit,
    ObservedPowerState,
    WorkerReceipt,
)
from .commissioning_usb_identity_persistence import decode_physical_usb_identity_permit
from .physical_camera_usb_absence import _record
from .physical_camera_usb_baseline import _file_report
from .physical_camera_usb_reconnect import (
    _ACQUISITIONS,
    _ledger,
    original_usb_reconnect_predecessor_v12,
)
from .physical_camera_usb_reconnect_constants import USB_RECONNECT_ROLE_BYTES
from .physical_camera_usb_reboot_constants import (
    USB_REBOOT_ROLE_BYTES,
    usb_reboot_event,
    usb_reboot_label,
)
from .physical_camera_selection import selection_from_enrollment_snapshot
from .physical_onboarding import EvidenceReference, STAGE_ORDER
from .physical_onboarding_attempts import AttemptState
from rocell.safety.effects import EffectCertainty
from .physical_onboarding_v2 import V2JournalEvent, V2StageState, _parse_event
from .physical_usb_identity_campaign import (
    PhysicalUsbIdentityCampaign,
    UsbIdentityOperation,
    verify_phase_operation_context,
)
from .physical_usb_presence_phase import UsbPresenceQualificationPhase
from .physical_usb_reboot_phase import (
    FLAGS,
    UsbRebootOperatorEvent,
    _historical_ids,
    _metadata_ids,
    verify_usb_reboot_predecessor,
)
from .physical_usb_reconnect_phase import UsbReconnectQualificationPhase
from .wizard_native_camera_enrollment import verify_native_camera_enrollment_snapshot
from rocell.providers.windows.owned_usb_identity_evidence import (
    OwnedUsbIdentityRunEvidence,
)
from rocell.providers.windows.usb_identity_registration import (
    UsbIdentityRuntimeRegistration,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest

PREPARATION_SCHEMA = "rocell.usb_reboot_preparation.v1"
MEANING = "FRESH_REBOOT_METADATA_AND_FILES_NOT_QUERY_PERMISSION"
_STAGE = STAGE_ORDER[3]
_FIELDS = {
    "schema",
    "plan_sha256",
    "plan_reference",
    "baseline_sha256",
    "absence_sha256",
    "absence_reference",
    "reconnect_sha256",
    "reconnect_reference",
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


class UsbRebootPreparationError(ValueError):
    """Closed invalid-original/preparation failure; never an admission decision."""


def _need(ok: bool) -> None:
    if not ok:
        raise UsbRebootPreparationError("USB_REBOOT_PREPARATION_INVALID")


def _ref(value: Any, sha: str, size: int | None = None) -> EvidenceReference:
    result = qualification._reference(value)
    _need(result.payload_sha256 == sha)
    if size is not None:
        _need(result.payload_bytes == size)
    return result


def original_usb_reboot_predecessor(
    workflow: dict[str, Any], *, received: dict[str, Any]
) -> dict[str, Any]:
    """Reconstruct a complete supplied v12; caller separately authenticates M1.

    This deliberately does not interpret a saved export as a current store.
    It returns the nine independent inputs accepted by the pure reboot codec.
    """
    return _original_usb_reboot_predecessor(
        workflow, received=received, successor=False
    )


def original_usb_reboot_predecessor_v13(
    workflow: dict[str, Any], *, received: dict[str, Any]
) -> dict[str, Any]:
    """Join unchanged originals from an authenticated v13, without relabeling it.

    The caller must independently authenticate the complete current suffix and
    campaign family. This data adapter is not store or current-launch authority.
    """
    _need(
        type(workflow) is dict
        and type(workflow.get("usb_qualification_reboot")) is dict
    )
    _need(workflow["usb_qualification_reboot"].get("phase") == "AFTER_REBOOT")
    return _original_usb_reboot_predecessor(workflow, received=received, successor=True)


def _original_usb_reboot_predecessor(
    workflow: dict[str, Any],
    *,
    received: dict[str, Any],
    successor: bool,
    complete_successor: bool = False,
) -> dict[str, Any]:
    try:
        _need(
            type(complete_successor) is bool and (not complete_successor or successor)
        )
        if successor:
            from .physical_camera_usb_reconnect import (
                _original_usb_reconnect_predecessor,
            )

            previous = _original_usb_reconnect_predecessor(
                workflow,
                successor=True,
                reboot_successor=True,
                complete_successor=complete_successor,
            )
        else:
            previous = original_usb_reconnect_predecessor_v12(workflow)
        phase = workflow["usb_qualification_reconnect"]
        _need(
            phase["phase"] == "AFTER_RECONNECT" and phase["state"] == "RETAINED_BLOCKED"
        )
        records = {role: _record(phase[role]) for role in USB_RECONNECT_ROLE_BYTES}
        _need(
            all(
                len(raw) <= USB_RECONNECT_ROLE_BYTES[role]
                for role, (raw, _) in records.items()
            )
        )
        _need(len({ref.evidence_id for _, ref in records.values()}) == len(records))
        raw, ref = records["phase_record"]
        reconnect = UsbReconnectQualificationPhase(raw)
        sources = {
            role: records[stored][0]
            for role, stored in (
                ("operation", "operation"),
                ("operator_event", "operator_event"),
                ("native_enrollment", "enrollment"),
                ("owned_usb_run", "execution"),
                ("host_boot", "host_boot"),
            )
        }
        rd = reconnect.to_dict()
        _need(phase["phase_id"] == rd["context"]["operation_id"])
        for row, stored in zip(
            rd["records"],
            ("operation", "operator_event", "enrollment", "execution", "host_boot"),
        ):
            _need(
                canonical(row["reference"]) == canonical(records[stored][1].to_dict())
            )
        original = phase["original_campaign"]
        qualification._exact(
            original,
            {
                "permit",
                "result",
                "admission_evidence",
                "evidence",
                "evidence_sha256",
                "reference",
                "retention",
            },
        )
        _need(
            original["retention"] == "M1_FULL_BYTES_READ_BACK"
            and type(original["admission_evidence"]) is dict
            and canonical(original["evidence"]) == sources["owned_usb_run"]
            and original["evidence_sha256"] == digest(sources["owned_usb_run"])
        )
        permit = decode_physical_usb_identity_permit(original["permit"])
        result = dict(
            previous,
            received=received,
            reconnect=reconnect,
            reconnect_reference=ref,
            reconnect_sources=sources,
            reconnect_permit=permit,
        )
        verify_usb_reboot_predecessor(**result)
        run = OwnedUsbIdentityRunEvidence(sources["owned_usb_run"])
        prepared = run.preparation
        campaign = PhysicalUsbIdentityCampaign(
            UsbIdentityOperation(sources["operation"]),
            identity=prepared.identity,
            review=prepared.review,
        )
        effect = run.bounded_effect_summary()
        counts = effect["actual_counts"]
        _need(
            run.status == "OBSERVED"
            and effect["current_complete"]
            and effect["released"]
            and effect["process_cleanup_confirmed"]
            and effect["usb_cleanup_confirmed"]
            and counts is not None
        )
        assert counts is not None
        expected_receipt = WorkerReceipt(
            permit.attempt_id,
            permit.permit_sha256,
            permit.registration.worker_executable_sha256,
            permit.admission.selected_identity_sha256,
            EffectCertainty.CONFIRMED,
            True,
            ObservedPowerState.UNKNOWN,
            counts["hub_open_attempts"],
            counts["api_calls"]
            - counts["hub_open_attempts"]
            - counts["close_attempts"],
            0,
            0,
            counts["close_attempts"],
            len(run.payload),
            (run.sha256,),
            campaign.composition,
        )
        expected_result = AttemptResult(
            permit.attempt_id,
            AttemptState.SEALED_KNOWN,
            permit.permit_sha256,
            (),
            expected_receipt,
            False,
            campaign.composition,
        )
        _need(canonical(original["result"]) == canonical(asdict(expected_result)))
        _need(
            canonical(original["reference"])
            == canonical(
                dict(
                    schema="rocell.usb_identity_campaign_reference.v1",
                    cell_id=permit.request.cell_id,
                    session_id=permit.request.session_id,
                    attempt_id=permit.attempt_id,
                    permit_sha256=permit.permit_sha256,
                    evidence_sha256=run.sha256,
                    payload_bytes=len(run.payload),
                    label="physical-native-usb-identity",
                )
            )
        )
        return result
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        IndexError,
        RecursionError,
    ) as exc:
        raise UsbRebootPreparationError("USB_REBOOT_PREDECESSOR_INVALID") from exc


def _load(payload: bytes) -> dict[str, Any]:
    try:
        d = qualification._load(payload, USB_REBOOT_ROLE_BYTES["preparation"])
        qualification._exact(d, _FIELDS)
        _need(
            d["schema"] == PREPARATION_SCHEMA
            and d["meaning"] == MEANING
            and all(d[key] is False for key in FLAGS)
        )
        operation = UsbIdentityOperation(canonical(d["operation"]))
        op = operation.to_dict()
        _need(op["schema"] == "rocell.physical_usb_identity_operation.v2")
        plan = qualification.UsbQualificationPlan(canonical(op["qualification_plan"]))
        p = plan.to_dict()
        for key in ("baseline_sha256", "absence_sha256", "reconnect_sha256"):
            qualification._sha(d[key])
        verify_phase_operation_context(
            operation, plan, "AFTER_REBOOT", d["phase_id"], d["reconnect_sha256"]
        )
        _need(
            p["mode"] == "PHYSICAL"
            and d["plan_sha256"] == plan.sha256
            and d["operation_sha256"] == operation.sha256
        )
        report = UsbRebootOperatorEvent(canonical(d["operator_event"]))
        r = report.to_dict()
        _need(
            r["binding"] == p["binding"]
            and r["plan_sha256"] == plan.sha256
            and r["baseline_sha256"] == d["baseline_sha256"]
            and r["absence_sha256"] == d["absence_sha256"]
            and r["predecessor_sha256"] == d["reconnect_sha256"]
            and r["phase_id"] == d["phase_id"]
            and r["operator_id"] == d["operator_id"]
        )
        refs = (
            _ref(d["plan_reference"], plan.sha256, len(plan.payload)),
            _ref(d["absence_reference"], d["absence_sha256"]),
            _ref(d["reconnect_reference"], d["reconnect_sha256"]),
            _ref(d["operator_event_reference"], report.sha256, len(report.payload)),
            _ref(d["enrollment_reference"], d["enrollment_sha256"]),
        )
        _need(
            len({ref.evidence_id for ref in refs}) == len(refs)
            and 0 < refs[1].payload_bytes <= 16 * 1024
            and 0 < refs[2].payload_bytes <= 32 * 1024
            and 0 < refs[4].payload_bytes <= USB_REBOOT_ROLE_BYTES["enrollment"]
        )
        event = _parse_event(d["phase_start_event"])
        _need(
            event.stage is _STAGE
            and event.session_id == p["binding"]["session_id"]
            and event.session_header_sha256 == p["binding"]["header_sha256"]
            and event.previous_state is V2StageState.BLOCKED
            and event.state is V2StageState.WAITING_OPERATOR
            and event.detail_code
            == usb_reboot_event("PREPARATION_REQUESTED", d["phase_id"])
            and event.evidence == (refs[2],)
            and event.occurred_at_ns == r["phase_started_at_utc_ns"]
            and event.occurred_at_ns >= p["created_at_utc_ns"]
        )
        qualification._integer(d["prepared_at_utc_ns"], r["reported_at_utc_ns"])
        qualification._text(d["operator_id"], 64)
        _need(all(32 <= ord(char) <= 126 for char in d["operator_id"]))
        _ledger(d, p["binding"])
        _file_report(
            d["runtime_report"],
            UsbIdentityRuntimeRegistration(canonical(op["runtime"])),
        )
        return d
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        IndexError,
        RecursionError,
    ) as exc:
        raise UsbRebootPreparationError("USB_REBOOT_PREPARATION_INVALID") from exc


@dataclass(frozen=True, slots=True)
class UsbRebootPreparation:
    payload: bytes

    def __post_init__(self) -> None:
        _load(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload)

    def safe_summary(self) -> dict[str, Any]:
        d = self.to_dict()
        result = dict(
            schema="rocell.usb_reboot_preparation_summary.v1",
            preparation_sha256=self.sha256,
            **{
                key: d[key]
                for key in (
                    "plan_sha256",
                    "baseline_sha256",
                    "absence_sha256",
                    "reconnect_sha256",
                    "phase_id",
                    "enrollment_sha256",
                    "operation_sha256",
                    "prepared_at_utc_ns",
                    "operator_id",
                    "meaning",
                )
            },
            launch_session_id=d["operator_event"]["launch_session_id"],
            acquisition_ledger=d["acquisition_ledger"],
            **FLAGS,
        )
        _need(len(canonical(result)) <= 16 * 1024)
        return result


def build_usb_reboot_preparation(
    *,
    original_baseline: dict[str, Any],
    received: dict[str, Any],
    absence: UsbPresenceQualificationPhase,
    absence_reference: EvidenceReference,
    absence_sources: dict[str, bytes],
    reconnect: UsbReconnectQualificationPhase,
    reconnect_reference: EvidenceReference,
    reconnect_sources: dict[str, bytes],
    reconnect_permit: ExactOperationPermit,
    phase_start_event: V2JournalEvent,
    phase_id: str,
    operator_event: UsbRebootOperatorEvent,
    operator_event_reference: EvidenceReference,
    enrollment: bytes,
    enrollment_reference: EvidenceReference,
    acquisition_ledger: dict[str, Any],
    operation: UsbIdentityOperation,
    runtime_report: dict[str, Any],
    prepared_at_utc_ns: int,
    operator_id: str,
) -> UsbRebootPreparation:
    """Rebuild exact full predecessor and current three published acquisitions.

    The ledger's actual original-log membership is checked later by its owner,
    not fabricated from timestamps here. No boot epoch is invented at Prepare.
    """
    try:
        reconnect = verify_usb_reboot_predecessor(
            original_baseline=original_baseline,
            received=received,
            absence=absence,
            absence_reference=absence_reference,
            absence_sources=absence_sources,
            reconnect=reconnect,
            reconnect_reference=reconnect_reference,
            reconnect_sources=reconnect_sources,
            reconnect_permit=reconnect_permit,
        )
        _need(
            type(absence_reference) is EvidenceReference
            and type(reconnect_reference) is EvidenceReference
            and type(phase_start_event) is V2JournalEvent
            and type(operator_event) is UsbRebootOperatorEvent
            and type(operator_event_reference) is EvidenceReference
            and type(enrollment_reference) is EvidenceReference
            and type(operation) is UsbIdentityOperation
        )
        plan = original_baseline["plan"]
        report = UsbRebootOperatorEvent(operator_event.payload).to_dict()
        prior_contexts = [
            subject.to_dict()["context"]
            for subject in (original_baseline["baseline"], absence, reconnect)
        ]
        prior_ids = {ctx["operation_id"] for ctx in prior_contexts}
        _need(
            report["baseline_sha256"] == original_baseline["baseline"].sha256
            and report["absence_sha256"] == absence.sha256
            and report["predecessor_sha256"] == reconnect.sha256
            and report["phase_started_at_utc_ns"]
            > reconnect.to_dict()["context"]["finished_at_utc_ns"]
            and phase_id not in prior_ids
            and report["launch_session_id"]
            not in {ctx["launch_session_id"] for ctx in prior_contexts}
        )
        used = _historical_ids(original_baseline, absence, reconnect)
        used.update((absence_reference.evidence_id, reconnect_reference.evidence_id))
        _need(
            not used.intersection(
                (operator_event_reference.evidence_id, enrollment_reference.evidence_id)
            )
        )
        raw = qualification._load(enrollment, USB_REBOOT_ROLE_BYTES["enrollment"])
        checked = UsbRebootPreparation(
            canonical(
                dict(
                    schema=PREPARATION_SCHEMA,
                    plan_sha256=plan.sha256,
                    plan_reference=original_baseline["plan_reference"].to_dict(),
                    baseline_sha256=original_baseline["baseline"].sha256,
                    absence_sha256=absence.sha256,
                    absence_reference=absence_reference.to_dict(),
                    reconnect_sha256=reconnect.sha256,
                    reconnect_reference=reconnect_reference.to_dict(),
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
        source, launch = (
            plan.to_dict()["binding"]["source_sha256"],
            report["launch_session_id"],
        )
        verified = verify_native_camera_enrollment_snapshot(
            raw, source_sha256=source, launch_session_id=launch
        )
        selection = selection_from_enrollment_snapshot(
            verified, source_sha256=source, launch_session_id=launch
        )
        _need(
            selection is not None
            and canonical(selection.identity_document)
            == canonical(d["operation"]["selection"])
        )
        documents = (
            verified["generic_review"]["inventory_report"],
            verified["inventory_packet"],
            verified["identity_packet"],
        )
        ids = _metadata_ids(enrollment)
        previous_ids = prior_ids | {phase_id}
        previous_ids.update(
            _metadata_ids(original_baseline["baseline_sources"]["native_enrollment"])
        )
        previous_ids.update(_metadata_ids(reconnect_sources["native_enrollment"]))
        _need(not previous_ids.intersection(ids))
        for row, document, op_id in zip(
            d["acquisition_ledger"]["entries"], documents, ids
        ):
            _need(
                row["document_sha256"] == digest(canonical(document))
                and row["operation_id"] == op_id
            )
        return checked
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        IndexError,
        RecursionError,
    ) as exc:
        raise UsbRebootPreparationError("USB_REBOOT_PREPARATION_INVALID") from exc


def verify_usb_reboot_preparation(
    payload: bytes,
    *,
    expected_sha256: str,
    original_baseline: dict[str, Any],
    received: dict[str, Any],
    absence: UsbPresenceQualificationPhase,
    absence_reference: EvidenceReference,
    absence_sources: dict[str, bytes],
    reconnect: UsbReconnectQualificationPhase,
    reconnect_reference: EvidenceReference,
    reconnect_sources: dict[str, bytes],
    reconnect_permit: ExactOperationPermit,
    phase_start_event: V2JournalEvent,
    phase_id: str,
    operator_event: UsbRebootOperatorEvent,
    operator_event_reference: EvidenceReference,
    enrollment: bytes,
    enrollment_reference: EvidenceReference,
) -> UsbRebootPreparation:
    """Independent originals must rebuild the exact saved preparation bytes."""
    checked = UsbRebootPreparation(payload)
    qualification._sha(expected_sha256)
    _need(checked.sha256 == expected_sha256)
    d = checked.to_dict()
    rebuilt = build_usb_reboot_preparation(
        original_baseline=original_baseline,
        received=received,
        absence=absence,
        absence_reference=absence_reference,
        absence_sources=absence_sources,
        reconnect=reconnect,
        reconnect_reference=reconnect_reference,
        reconnect_sources=reconnect_sources,
        reconnect_permit=reconnect_permit,
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
