"""Closed new-trial BASELINE subjects; original ownership remains with M1.

The enrollment role is the unchanged native enrollment document. Preparation
binds its separate original bytes and the trusted acquisition ledger; no packet
timestamp, physical observation, or legacy standalone trial is manufactured.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from .physical_camera_usb_baseline import FLAGS, _file_report
from .physical_camera_usb_qualification import UsbQualificationPlan
from .physical_camera_selection import selection_from_enrollment_snapshot
from .physical_onboarding import (
    EvidenceReference,
    STAGE_ORDER,
    _parse_evidence_reference,
)
from .physical_onboarding_v2 import V2JournalEvent, V2StageState, _parse_event
from .physical_usb_identity_campaign import (
    UsbIdentityOperation,
    verify_phase_operation_context,
)
from .wizard_native_camera_enrollment import verify_native_camera_enrollment_snapshot
from rocell.providers.windows.owned_worker_process import decode_owned_json
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.providers.windows.usb_identity_registration import (
    UsbIdentityRuntimeRegistration,
)


USB_PHASE_ROLE_BYTES = {
    "enrollment": 768 * 1024,
    "preparation": 128 * 1024,
    "policy_review": 8 * 1024,
    "runtime_review": 8 * 1024,
    "identity": 16 * 1024,
    "boot_request": 16 * 1024,
    "host_boot": 32 * 1024,
    "execution": 128 * 1024,
    "phase_record": 32 * 1024,
}
USB_PHASE_EVENTS = (
    "ENTERED",
    "PREPARATION_REQUESTED",
    "PREPARED",
    "REVIEWED",
    "BOOT_REQUESTED",
    "BOOT_RETAINED",
    "BOOT_HELD",
    "BOOT_UNCERTAIN",
    "QUERY_REQUESTED",
    "RETAINED",
)
USB_PHASE_LABEL = re.compile(
    r"camera-usb-trial-baseline-(enrollment|preparation|policy-review|runtime-review|"
    r"identity|boot-request|host-boot|execution|phase-record)-v1:(usbphase-[0-9a-f]{32})"
)
USB_PHASE_EVENT = re.compile(
    r"CAMERA_USB_TRIAL_BASELINE_(" + "|".join(USB_PHASE_EVENTS) + r")_([0-9A-F]{32})"
)


def usb_phase_event(event: str, phase_id: str) -> str:
    if (
        type(event) is not str
        or event not in USB_PHASE_EVENTS
        or type(phase_id) is not str
        or re.fullmatch(r"usbphase-[0-9a-f]{32}", phase_id) is None
    ):
        raise ValueError("USB_PHASE_EVENT_INVALID")
    return "CAMERA_USB_TRIAL_BASELINE_" + event + "_" + phase_id[9:].upper()


def usb_phase_label(role: str, phase_id: str) -> str:
    if type(role) is not str or role not in USB_PHASE_ROLE_BYTES:
        raise ValueError("USB_PHASE_ROLE_INVALID")
    usb_phase_event("ENTERED", phase_id)
    return "camera-usb-trial-baseline-" + role.replace("_", "-") + "-v1:" + phase_id


PREPARATION_SCHEMA = "rocell.usb_trial_baseline_preparation.v1"
PREPARATION_MEANING = "FRESH_DECLARED_METADATA_AND_FILES_NOT_QUERY_PERMISSION"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_ACQUISITIONS = (
    ("GENERIC_INVENTORY", "inventory_devices"),
    ("NATIVE_INVENTORY", "native_camera_inventory"),
    ("NATIVE_IDENTITY", "native_camera_identity"),
)


def _need(ok: bool) -> None:
    if not ok:
        raise ValueError("USB_TRIAL_PREPARATION_INVALID")


def _sha(value: Any) -> None:
    _need(type(value) is str and _SHA.fullmatch(value) is not None)


def _time(value: Any) -> None:
    _need(type(value) is int and 0 < value < 2**63)


def _reference(value: Any, sha: str, size: int | None = None) -> EvidenceReference:
    result = _parse_evidence_reference(value)
    _need(result.stage is STAGE_ORDER[3] and result.payload_sha256 == sha)
    if size is not None:
        _need(result.payload_bytes == size)
    return result


def _preparation(payload: bytes) -> dict[str, Any]:
    value = decode_owned_json(payload, maximum=USB_PHASE_ROLE_BYTES["preparation"])
    _need(
        canonical(value) == payload
        and set(value)
        == {
            "schema",
            "plan_sha256",
            "plan_reference",
            "phase_id",
            "phase_start_event",
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
    )
    _need(
        value["schema"] == PREPARATION_SCHEMA
        and value["meaning"] == PREPARATION_MEANING
        and all(value[key] is False for key in FLAGS)
    )
    phase_id = value["phase_id"]
    usb_phase_event("ENTERED", phase_id)
    operation = UsbIdentityOperation(canonical(value["operation"]))
    op = operation.to_dict()
    _need(op["schema"] == "rocell.physical_usb_identity_operation.v2")
    plan = UsbQualificationPlan(canonical(op["qualification_plan"]))
    verify_phase_operation_context(operation, plan, "BASELINE", phase_id, None)
    p = plan.to_dict()
    _need(
        p["mode"] == "PHYSICAL"
        and plan.sha256 == value["plan_sha256"]
        and operation.sha256 == value["operation_sha256"]
    )
    plan_ref = _reference(value["plan_reference"], plan.sha256, len(plan.payload))
    _sha(value["enrollment_sha256"])
    enrollment_ref = _reference(
        value["enrollment_reference"], value["enrollment_sha256"]
    )
    _need(
        enrollment_ref.evidence_id != plan_ref.evidence_id
        and 0 < enrollment_ref.payload_bytes <= USB_PHASE_ROLE_BYTES["enrollment"]
    )
    event = _parse_event(value["phase_start_event"])
    _need(
        event.stage is STAGE_ORDER[3]
        and event.previous_state is V2StageState.BLOCKED
        and event.state is V2StageState.WAITING_OPERATOR
        and event.detail_code == usb_phase_event("PREPARATION_REQUESTED", phase_id)
        and event.session_id == p["binding"]["session_id"]
        and event.session_header_sha256 == p["binding"]["header_sha256"]
        and event.evidence == (plan_ref,)
        and event.occurred_at_ns >= p["created_at_utc_ns"]
    )
    _time(value["prepared_at_utc_ns"])
    _need(
        type(value["operator_id"]) is str
        and 0 < len(value["operator_id"]) <= 64
        and value["operator_id"] == value["operator_id"].strip()
        and all(32 <= ord(c) <= 126 for c in value["operator_id"])
    )
    ledger = value["acquisition_ledger"]
    _need(
        type(ledger) is dict
        and set(ledger)
        == {
            "schema",
            "source_sha256",
            "session_id",
            "launch_session_id",
            "trial_id",
            "phase_id",
            "phase_started_at_utc_ns",
            "entries",
        }
    )
    _need(
        ledger["schema"] == "rocell.usb_phase_metadata_acquisition_ledger.v1"
        and all(
            ledger[key] == p["binding"][key]
            for key in ("source_sha256", "session_id", "trial_id")
        )
        and type(ledger["launch_session_id"]) is str
        and _ID.fullmatch(ledger["launch_session_id"]) is not None
        and ledger["phase_id"] == phase_id
        and type(ledger["phase_started_at_utc_ns"]) is int
        and ledger["phase_started_at_utc_ns"] == event.occurred_at_ns
    )
    rows = ledger["entries"]
    _need(type(rows) is list and len(rows) == 3)
    previous = event.occurred_at_ns
    ids = set()
    for row, (role, action) in zip(rows, _ACQUISITIONS):
        _need(
            type(row) is dict
            and set(row)
            == {
                "role",
                "action_id",
                "operation_id",
                "started_at_utc_ns",
                "finished_at_utc_ns",
                "published_at_utc_ns",
                "document_sha256",
                "result_sha256",
                "completion_logged",
            }
        )
        _need(
            row["role"] == role
            and row["action_id"] == action
            and type(row["operation_id"]) is str
            and _ID.fullmatch(row["operation_id"]) is not None
            and row["operation_id"] not in ids
            and row["operation_id"] != phase_id
            and row["completion_logged"] is True
        )
        for key in ("started_at_utc_ns", "finished_at_utc_ns", "published_at_utc_ns"):
            _time(row[key])
        _need(
            previous
            <= row["started_at_utc_ns"]
            <= row["finished_at_utc_ns"]
            <= row["published_at_utc_ns"]
            <= value["prepared_at_utc_ns"]
        )
        _sha(row["document_sha256"])
        _sha(row["result_sha256"])
        ids.add(row["operation_id"])
        previous = row["published_at_utc_ns"]
    _file_report(
        value["runtime_report"],
        UsbIdentityRuntimeRegistration(canonical(op["runtime"])),
    )
    return value


@dataclass(frozen=True, slots=True)
class UsbTrialBaselinePreparation:
    payload: bytes

    def __post_init__(self) -> None:
        _preparation(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _preparation(self.payload)

    def safe_summary(self) -> dict[str, Any]:
        d = self.to_dict()
        return dict(
            schema="rocell.usb_trial_baseline_preparation_summary.v1",
            phase_id=d["phase_id"],
            plan_sha256=d["plan_sha256"],
            preparation_sha256=self.sha256,
            enrollment_sha256=d["enrollment_sha256"],
            operation_sha256=d["operation_sha256"],
            operator_id=d["operator_id"],
            phase_started_at_utc_ns=d["phase_start_event"]["occurred_at_ns"],
            prepared_at_utc_ns=d["prepared_at_utc_ns"],
            acquisition_count=3,
            meaning=PREPARATION_MEANING,
            **FLAGS,
        )


def build_usb_trial_baseline_preparation(
    *,
    plan: UsbQualificationPlan,
    plan_reference: EvidenceReference,
    phase_start_event: V2JournalEvent,
    phase_id: str,
    enrollment: bytes,
    enrollment_reference: EvidenceReference,
    acquisition_ledger: dict[str, Any],
    operation: UsbIdentityOperation,
    runtime_report: dict[str, Any],
    prepared_at_utc_ns: int,
    operator_id: str,
) -> UsbTrialBaselinePreparation:
    _need(
        type(plan) is UsbQualificationPlan
        and type(plan_reference) is EvidenceReference
        and type(phase_start_event) is V2JournalEvent
        and type(enrollment_reference) is EvidenceReference
        and type(enrollment) is bytes
        and 0 < len(enrollment) <= USB_PHASE_ROLE_BYTES["enrollment"]
        and type(operation) is UsbIdentityOperation
    )
    checked = UsbTrialBaselinePreparation(
        canonical(
            dict(
                schema=PREPARATION_SCHEMA,
                plan_sha256=plan.sha256,
                plan_reference=plan_reference.to_dict(),
                phase_id=phase_id,
                phase_start_event=phase_start_event.to_dict(),
                enrollment_sha256=digest(enrollment),
                enrollment_reference=enrollment_reference.to_dict(),
                acquisition_ledger=acquisition_ledger,
                operation=operation.to_dict(),
                operation_sha256=operation.sha256,
                runtime_report=runtime_report,
                prepared_at_utc_ns=prepared_at_utc_ns,
                operator_id=operator_id,
                meaning=PREPARATION_MEANING,
                **FLAGS,
            )
        )
    )
    d = checked.to_dict()
    _need(
        canonical(d["operation"]["qualification_plan"]) == plan.payload
        and enrollment_reference.payload_bytes == len(enrollment)
    )
    raw = json.loads(enrollment)
    _need(canonical(raw) == enrollment)
    bound = plan.to_dict()["binding"]
    launch = d["acquisition_ledger"]["launch_session_id"]
    verified = verify_native_camera_enrollment_snapshot(
        raw, source_sha256=bound["source_sha256"], launch_session_id=launch
    )
    selection = selection_from_enrollment_snapshot(
        verified, source_sha256=bound["source_sha256"], launch_session_id=launch
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
    for row, document, operation_id in zip(
        d["acquisition_ledger"]["entries"], documents, ids
    ):
        _need(
            row["document_sha256"] == digest(canonical(document))
            and row["operation_id"] == operation_id
        )
    return checked


def verify_usb_trial_baseline_preparation(
    payload: bytes,
    *,
    plan: UsbQualificationPlan,
    plan_reference: EvidenceReference,
    phase_start_event: V2JournalEvent,
    phase_id: str,
    enrollment: bytes,
    enrollment_reference: EvidenceReference,
    expected_sha256: str,
) -> UsbTrialBaselinePreparation:
    checked = UsbTrialBaselinePreparation(payload)
    _sha(expected_sha256)
    _need(checked.sha256 == expected_sha256)
    d = checked.to_dict()
    rebuilt = build_usb_trial_baseline_preparation(
        plan=plan,
        plan_reference=plan_reference,
        phase_start_event=phase_start_event,
        phase_id=phase_id,
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
