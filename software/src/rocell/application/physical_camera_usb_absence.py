"""Pure original-absence preparation; no file access, query or admission."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .physical_camera_usb_absence_constants import (
    USB_ABSENCE_ROLE_BYTES,
    SOURCE_WORKFLOW_USB_ABSENCE_SCHEMA,
    usb_absence_event,
)
from .physical_camera_usb_qualification import (
    UsbQualificationPlan,
    UsbQualificationPhase,
)
from .physical_onboarding import (
    EvidenceReference,
    STAGE_ORDER,
    _parse_evidence_reference,
)
from .physical_onboarding_v2 import V2JournalEvent, V2StageState, _parse_event
from .physical_usb_presence_binding import build_usb_presence_phase_binding
from .physical_usb_presence_campaign import UsbPresenceOperation
from .physical_usb_presence_phase import UsbPresenceOperatorEvent
from rocell.providers.windows.owned_worker_process import decode_owned_json
from rocell.providers.windows.usb_presence_protocol import canonical, digest
from rocell.providers.windows import usb_presence_registration as registration

PREPARATION_SCHEMA = "rocell.usb_absence_preparation.v1"
FLAGS = dict(
    physical_authority=False, hardware_qualified=False, device_io_performed=False
)
MEANING = "ORIGINAL_FILES_AND_OPERATOR_REPORT_NOT_PRESENCE_PERMISSION"


def _need(ok: bool) -> None:
    if not ok:
        raise ValueError("USB_ABSENCE_PREPARATION_INVALID")


def _sha(value: Any) -> None:
    _need(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None)


def _record(record: Any) -> tuple[bytes, EvidenceReference]:
    _need(
        type(record) is dict
        and set(record)
        == {
            "document",
            "evidence_sha256",
            "reference",
            "retention",
        }
    )
    payload = canonical(record["document"])
    ref = _parse_evidence_reference(record["reference"])
    _need(
        record["retention"] == "M1_FULL_BYTES_READ_BACK"
        and ref.stage is STAGE_ORDER[3]
        and ref.payload_sha256 == record["evidence_sha256"] == digest(payload)
        and ref.payload_bytes == len(payload)
    )
    return payload, ref


def original_usb_absence_baseline(workflow: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct supplied original subjects; caller still authenticates M1."""
    return _original_usb_absence_baseline(workflow, reconnect_successor=False)


def _original_usb_absence_baseline(
    workflow: dict[str, Any],
    *,
    reconnect_successor: bool,
    reboot_successor: bool = False,
    complete_successor: bool = False,
) -> dict[str, Any]:
    """Private versioned data join; never relabel a v12 snapshot as a v11 one."""
    expected = (
        {"rocell.physical_camera_source_workflow_readback.v14"}
        if complete_successor is True
        else (
            {"rocell.physical_camera_source_workflow_readback.v13"}
            if reboot_successor is True
            else (
                {"rocell.physical_camera_source_workflow_readback.v12"}
                if reconnect_successor is True
                else {
                    "rocell.physical_camera_source_workflow_readback.v10",
                    SOURCE_WORKFLOW_USB_ABSENCE_SCHEMA,
                }
            )
        )
    )
    _need(
        type(workflow) is dict
        and type(reconnect_successor) is bool
        and type(reboot_successor) is bool
        and type(complete_successor) is bool
        and (not complete_successor or reboot_successor)
        and (not reboot_successor or reconnect_successor)
        and workflow.get("schema") in expected
    )
    _need(workflow.get("configuration_epochs") is not None)
    trial, phase = (
        workflow["usb_qualification_trial"],
        workflow["usb_qualification_baseline"],
    )
    _need(trial["state"] == "PLAN_DECLARED" and phase["state"] == "RETAINED_BLOCKED")
    plan_raw, plan_ref = _record(trial["plan"])
    baseline_raw, baseline_ref = _record(phase["phase_record"])
    result: dict[str, Any] = dict(
        plan=UsbQualificationPlan(plan_raw),
        plan_reference=plan_ref,
        declaration_event=_parse_event(trial["declaration_event"]),
        baseline=UsbQualificationPhase(baseline_raw),
        baseline_reference=baseline_ref,
        baseline_sources={
            name: _record(phase[role])[0]
            for name, role in (
                ("native_enrollment", "enrollment"),
                ("owned_usb_run", "execution"),
                ("host_boot", "host_boot"),
            )
        },
    )
    binding = build_usb_presence_phase_binding(**result).to_dict()["binding"]
    _need(
        all(
            binding[key] == workflow["binding"][key]
            for key in (
                "source_sha256",
                "cell_id",
                "session_id",
            )
        )
        and binding["header_sha256"] == workflow["session_header_sha256"]
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
    return result


def _file_report(report: Any) -> None:
    _need(
        type(report) is dict
        and set(report)
        == {
            "schema",
            "runtime_registration_sha256",
            "source_sha256",
            "status",
            "files",
            "physical_authority",
            "hardware_qualified",
            "device_io_performed",
        }
    )
    _need(
        report["schema"] == registration.INSPECTION_SCHEMA
        and report["status"] == "FILES_MATCHED"
        and all(report[key] is False for key in FLAGS)
    )
    _sha(report["runtime_registration_sha256"])
    _sha(report["source_sha256"])
    expected = [
        *registration.FIXED_SOURCE_PINS,
        (
            registration.BUILD_RECORD_PATH,
            registration.BUILD_RECORD_SHA256,
            registration.BUILD_RECORD_BYTES,
        ),
        (
            registration.HELPER_PATH,
            registration.HELPER_SHA256,
            registration.HELPER_BYTES,
        ),
    ]
    _need(type(report["files"]) is list and len(report["files"]) == len(expected))
    for row, (path, sha, size) in zip(report["files"], expected):
        _need(
            type(row) is dict
            and set(row) == {"path", "sha256", "bytes"}
            and row["path"] == path
            and row["sha256"] == sha
            and type(row["bytes"]) is int
            and row["bytes"] == size
        )


def _load(payload: bytes) -> dict[str, Any]:
    _need(type(payload) is bytes)
    d = decode_owned_json(payload, maximum=USB_ABSENCE_ROLE_BYTES["preparation"])
    _need(
        canonical(d) == payload
        and set(d)
        == {
            "schema",
            "binding",
            "phase_id",
            "launch_session_id",
            "operator_id",
            "phase_start_event",
            "phase_binding_sha256",
            "operation_reference",
            "operation_sha256",
            "operator_event_reference",
            "operator_event_sha256",
            "runtime_report",
            "prepared_at_utc_ns",
            "meaning",
            *FLAGS,
        }
    )
    _need(
        d["schema"] == PREPARATION_SCHEMA
        and d["meaning"] == MEANING
        and all(d[key] is False for key in FLAGS)
    )
    for key in ("phase_binding_sha256", "operation_sha256", "operator_event_sha256"):
        _sha(d[key])
    for ref_key, sha_key in (
        ("operation_reference", "operation_sha256"),
        ("operator_event_reference", "operator_event_sha256"),
    ):
        ref = _parse_evidence_reference(d[ref_key])
        _need(ref.stage is STAGE_ORDER[3] and ref.payload_sha256 == d[sha_key])
    event = _parse_event(d["phase_start_event"])
    _need(
        event.stage is STAGE_ORDER[3]
        and event.previous_state is V2StageState.BLOCKED
        and event.state is V2StageState.WAITING_OPERATOR
        and event.detail_code
        == usb_absence_event("PREPARATION_REQUESTED", d["phase_id"])
        and type(d["prepared_at_utc_ns"]) is int
        and event.occurred_at_ns <= d["prepared_at_utc_ns"] < 2**63
    )
    _need(
        type(d["launch_session_id"]) is str
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", d["launch_session_id"])
        is not None
    )
    _need(
        type(d["operator_id"]) is str
        and 1 <= len(d["operator_id"]) <= 64
        and d["operator_id"] == d["operator_id"].strip()
        and all(32 <= ord(c) <= 126 for c in d["operator_id"])
    )
    _need(
        type(d["binding"]) is dict
        and event.session_id == d["binding"]["session_id"]
        and event.session_header_sha256 == d["binding"]["header_sha256"]
    )
    _file_report(d["runtime_report"])
    _need(d["runtime_report"]["source_sha256"] == d["binding"]["source_sha256"])
    return d


@dataclass(frozen=True, slots=True)
class UsbAbsencePreparation:
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
        return dict(
            schema="rocell.usb_absence_preparation_summary.v1",
            preparation_sha256=self.sha256,
            phase_id=d["phase_id"],
            launch_session_id=d["launch_session_id"],
            operator_id=d["operator_id"],
            prepared_at_utc_ns=d["prepared_at_utc_ns"],
            phase_started_at_utc_ns=d["phase_start_event"]["occurred_at_ns"],
            phase_binding_sha256=d["phase_binding_sha256"],
            operation_sha256=d["operation_sha256"],
            operator_event_sha256=d["operator_event_sha256"],
            runtime_registration_sha256=d["runtime_report"][
                "runtime_registration_sha256"
            ],
            file_count=len(d["runtime_report"]["files"]),
            status="FILES_MATCHED",
            **FLAGS,
        )


def build_usb_absence_preparation(
    *,
    operation: UsbPresenceOperation,
    operation_reference: EvidenceReference,
    operator_event: UsbPresenceOperatorEvent,
    operator_event_reference: EvidenceReference,
    phase_start_event: V2JournalEvent,
    runtime_report: dict[str, Any],
    prepared_at_utc_ns: int,
    original_baseline: dict[str, Any],
) -> UsbAbsencePreparation:
    _need(
        type(operation) is UsbPresenceOperation
        and type(operator_event) is UsbPresenceOperatorEvent
        and type(phase_start_event) is V2JournalEvent
    )
    op = operation.to_dict()
    event = operator_event.to_dict()
    binding = build_usb_presence_phase_binding(**original_baseline)
    _need(
        op["phase_binding"] == binding.to_dict()
        and event["binding"] == binding.to_dict()["binding"]
        and event["phase_binding_sha256"] == binding.sha256
        and event["phase_id"] == op["operation_id"]
        and event["launch_session_id"] == op["launch_session_id"]
        and event["phase_started_at_utc_ns"] == phase_start_event.occurred_at_ns
        and event["reported_at_utc_ns"] <= prepared_at_utc_ns
        and phase_start_event.evidence == (original_baseline["baseline_reference"],)
    )
    for subject, ref in (
        (operation, operation_reference),
        (operator_event, operator_event_reference),
    ):
        _need(
            type(ref) is EvidenceReference
            and ref.stage is STAGE_ORDER[3]
            and ref.payload_sha256 == subject.sha256
            and ref.payload_bytes == len(subject.payload)
        )
    runtime = registration.UsbPresenceRuntimeRegistration(canonical(op["runtime"]))
    _file_report(runtime_report)
    _need(
        runtime_report["runtime_registration_sha256"] == runtime.sha256
        and runtime_report["source_sha256"] == op["source_sha256"]
    )
    return UsbAbsencePreparation(
        canonical(
            dict(
                schema=PREPARATION_SCHEMA,
                binding=binding.to_dict()["binding"],
                phase_id=op["operation_id"],
                launch_session_id=op["launch_session_id"],
                operator_id=event["operator_id"],
                phase_start_event=phase_start_event.to_dict(),
                phase_binding_sha256=binding.sha256,
                operation_reference=operation_reference.to_dict(),
                operation_sha256=operation.sha256,
                operator_event_reference=operator_event_reference.to_dict(),
                operator_event_sha256=operator_event.sha256,
                runtime_report=runtime_report,
                prepared_at_utc_ns=prepared_at_utc_ns,
                meaning=MEANING,
                **FLAGS,
            )
        )
    )


def verify_usb_absence_preparation(
    payload: bytes, *, expected_sha256: str, **originals
) -> UsbAbsencePreparation:
    _sha(expected_sha256)
    result = UsbAbsencePreparation(payload)
    d = result.to_dict()
    rebuilt = build_usb_absence_preparation(
        **originals,
        runtime_report=d["runtime_report"],
        prepared_at_utc_ns=d["prepared_at_utc_ns"],
    )
    _need(result.sha256 == expected_sha256 and result.payload == rebuilt.payload)
    return result
