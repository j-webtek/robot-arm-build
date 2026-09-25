"""One original-requested local boot observation inside a USB trial.

The durable intent is recorded before collection; it is not a saved process
permit. Only a collector entering from the original REVIEWED state may commit
BOOT_REQUESTED and run the fixed local observer. A reopened pending request
cannot be replayed. No USB, camera, serial, reboot or motion API belongs here.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import re
from threading import Event, Lock
from time import monotonic_ns, time_ns
from typing import Any, Callable

from .commissioning_camera_persistence import (
    M1PhysicalCameraTransaction,
    physical_camera_source_binding,
)
from .physical_camera_usb_phase import usb_phase_event, usb_phase_label
from .physical_camera_usb_qualification import UsbQualificationPlan, _binding
from .physical_onboarding import (
    EvidenceReference,
    STAGE_ORDER,
    _parse_evidence_reference,
)
from .physical_onboarding_leases import LeaseLevel, LeaseSpec
from .physical_onboarding_v2 import V2JournalEvent, V2StageState, _parse_event
from .wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.host_boot_observation import (
    HostBootObservation,
    HostBootRequest,
    SCRIPT_SHA256,
    WindowsHostBootObserver,
)
from rocell.providers.windows.owned_worker_process import decode_owned_json
from rocell.providers.windows.usb_identity_protocol import canonical, digest

SCHEMA = "rocell.usb_trial_boot_intent.v1"
MAX_INTENT_BYTES = 16 * 1024
_STAGE = STAGE_ORDER[3]
_BUDGET = dict(admission_window_ms=30000, process_run_ms=10000, cleanup_ms=2000)
_FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    camera_capture_authorized=False,
    arm_access_authorized=False,
    automatic_replay=False,
)


class UsbTrialBootError(ValueError):
    pass


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise UsbTrialBootError(code)


@dataclass(frozen=True, slots=True)
class UsbTrialBootIntent:
    """Immutable review subject; construction never reads files or starts work."""

    payload: bytes

    def __post_init__(self) -> None:
        d = decode_owned_json(self.payload, maximum=MAX_INTENT_BYTES)
        _need(
            canonical(d) == self.payload
            and set(d)
            == {
                "schema",
                "binding",
                "plan_sha256",
                "plan_reference",
                "phase",
                "phase_id",
                "phase_start_event",
                "launch_session_id",
                "script_sha256",
                "budget",
                *_FLAGS,
            },
            "EXACT_BOOT_INTENT_REQUIRED",
        )
        _binding(d["binding"])
        ref = _parse_evidence_reference(d["plan_reference"])
        event = _parse_event(d["phase_start_event"])
        _need(
            d["schema"] == SCHEMA
            and d["phase"] == "BASELINE"
            and type(d["phase_id"]) is str
            and re.fullmatch(r"usbphase-[0-9a-f]{32}", d["phase_id"]) is not None
            and type(d["launch_session_id"]) is str
            and re.fullmatch(r"wizard-[0-9a-f]{32}", d["launch_session_id"]) is not None
            and d["script_sha256"] == SCRIPT_SHA256
            and canonical(d["budget"]) == canonical(_BUDGET)
            and all(d[k] is False for k in _FLAGS),
            "BOOT_INTENT_POLICY_CHANGED",
        )
        b = d["binding"]
        _need(
            ref.stage is _STAGE
            and ref.payload_sha256 == d["plan_sha256"]
            and event.session_id == b["session_id"]
            and event.session_header_sha256 == b["header_sha256"]
            and event.stage is _STAGE
            and event.previous_state is V2StageState.BLOCKED
            and event.state is V2StageState.WAITING_OPERATOR
            and event.detail_code
            == usb_phase_event("PREPARATION_REQUESTED", d["phase_id"])
            and event.evidence == (ref,),
            "BOOT_INTENT_ORIGINAL_BINDING_CHANGED",
        )

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return decode_owned_json(self.payload, maximum=MAX_INTENT_BYTES)


def build_usb_trial_boot_intent(
    *,
    plan: UsbQualificationPlan,
    plan_reference: EvidenceReference,
    phase_start_event: V2JournalEvent,
    phase_id: str,
    launch_session_id: str,
) -> UsbTrialBootIntent:
    _need(
        type(plan) is UsbQualificationPlan
        and type(plan_reference) is EvidenceReference
        and type(phase_start_event) is V2JournalEvent,
        "EXACT_BOOT_INTENT_INPUTS_REQUIRED",
    )
    p = UsbQualificationPlan(plan.payload).to_dict()
    _need(
        p["mode"] == "PHYSICAL"
        and plan_reference.payload_sha256 == plan.sha256
        and plan_reference.payload_bytes == len(plan.payload)
        and phase_start_event.occurred_at_ns >= p["created_at_utc_ns"],
        "BOOT_INTENT_PLAN_MISMATCH",
    )
    return UsbTrialBootIntent(
        canonical(
            dict(
                schema=SCHEMA,
                binding=p["binding"],
                plan_sha256=plan.sha256,
                plan_reference=plan_reference.to_dict(),
                phase="BASELINE",
                phase_id=phase_id,
                phase_start_event=phase_start_event.to_dict(),
                launch_session_id=launch_session_id,
                script_sha256=SCRIPT_SHA256,
                budget=_BUDGET,
                **_FLAGS,
            )
        )
    )


def verify_usb_trial_boot_intent(
    value: Any, *, expected_sha256: str, **originals: Any
) -> UsbTrialBootIntent:
    intent = UsbTrialBootIntent(
        value.payload if type(value) is UsbTrialBootIntent else value
    )
    expected = build_usb_trial_boot_intent(**originals)
    _need(
        intent.sha256 == expected_sha256 and intent.payload == expected.payload,
        "BOOT_INTENT_RECONSTRUCTION_MISMATCH",
    )
    return intent


def verify_usb_trial_boot_observation(
    value: Any,
    *,
    intent: UsbTrialBootIntent,
    expected_sha256: str,
    requested_event: V2JournalEvent,
) -> HostBootObservation:
    """Join full observed bytes to the intent and original request event.

    This verifies data, including held reports. It is not original-store trust
    or proof that an injected/incapable executor observed the received host.
    """
    _need(
        type(intent) is UsbTrialBootIntent and type(requested_event) is V2JournalEvent,
        "EXACT_BOOT_OBSERVATION_INPUTS_REQUIRED",
    )
    intent = UsbTrialBootIntent(intent.payload)
    requested_event = _parse_event(requested_event.to_dict())
    report = HostBootObservation(
        value.payload if type(value) is HostBootObservation else value
    )
    d, i = report.to_dict(), intent.to_dict()
    request = d["request"]
    _need(
        report.sha256 == expected_sha256
        and all(
            request[k] == expected
            for k, expected in dict(
                source_sha256=i["binding"]["source_sha256"],
                session_id=i["binding"]["session_id"],
                trial_id=i["binding"]["trial_id"],
                phase=i["phase"],
                operation_id=i["phase_id"],
                launch_session_id=i["launch_session_id"],
            ).items()
        )
        and requested_event.detail_code
        == usb_phase_event("BOOT_REQUESTED", i["phase_id"])
        and requested_event.stage is _STAGE
        and requested_event.previous_state is V2StageState.BLOCKED
        and requested_event.state is V2StageState.WAITING_OPERATOR
        and requested_event.session_id == i["binding"]["session_id"]
        and requested_event.session_header_sha256 == i["binding"]["header_sha256"]
        and len(requested_event.evidence) == 1
        and requested_event.evidence[0].payload_sha256 == intent.sha256
        and requested_event.evidence[0].payload_bytes == len(intent.payload)
        and d["execution"]["started_utc_ns"] >= requested_event.occurred_at_ns
        and d["deadline_ns"] == request["expires_at_ns"]
        and d["deadline_ns"] - d["execution"]["started_monotonic_ns"] <= 30_000_000_000,
        "BOOT_OBSERVATION_INTENT_MISMATCH",
    )
    return report


def _terminal(report: HostBootObservation) -> str:
    d = report.to_dict()
    ex = d["execution"]
    ownership = ex.get("ownership")
    complete = (
        d["schema"] == "rocell.host_boot_observation.v2"
        and type(ownership) is dict
        and ownership.get("accounting_complete") is True
        and not ex["cleanup_errors"]
        and (not ex["process_created"] or ex["tree_exit_confirmed"])
        and all(
            ownership.get(name) == 0
            for name in (
                "handles_remaining",
                "pins_remaining",
                "unclosed_handles_remaining",
            )
        )
        and ownership.get("stdin_pending") is False
        and (
            (
                ownership.get("cleanup_deadline_ns") is None
                and not ex["process_created"]
                and ownership.get("pid") == 0
                and ownership.get("peak_processes") == 0
            )
            or (
                type(ownership.get("cleanup_deadline_ns")) is int
                and ex["finished_monotonic_ns"]
                <= ownership["cleanup_deadline_ns"]
                <= d["deadline_ns"]
            )
        )
    )
    if not complete:
        return "BOOT_UNCERTAIN"
    if d["origin"] == "WINDOWS_LOCAL_CIM" and d["status"] == "OBSERVED_HOST_BOOT":
        return "BOOT_RETAINED"
    return "BOOT_HELD"


class OriginalUsbTrialBootCollector:
    """Original M1-only one-shot process owner; no backend or argv injection."""

    def __init__(self, workspace: Path, intent: UsbTrialBootIntent):
        _need(
            isinstance(workspace, Path) and type(intent) is UsbTrialBootIntent,
            "EXACT_BOOT_COLLECTOR_REQUIRED",
        )
        self._workspace = workspace
        self._intent = UsbTrialBootIntent(intent.payload)
        self._lock, self._used = Lock(), False
        self._diagnostics: dict[str, Any] = dict(
            state="NOT_STARTED",
            requested_event=None,
            host_boot=None,
            terminal_event=None,
            **_FLAGS,
        )

    def retained_diagnostics(self) -> dict[str, Any]:
        return deepcopy(self._diagnostics)

    def collect(
        self,
        tx: M1PhysicalCameraTransaction,
        *,
        intent_reference: EvidenceReference,
        cancellation: Event,
        deadline_ns: int,
        revalidate_context: Callable[[], None],
    ) -> dict[str, Any]:
        _need(
            type(tx) is M1PhysicalCameraTransaction
            and type(intent_reference) is EvidenceReference
            and isinstance(cancellation, Event)
            and callable(revalidate_context)
            and type(deadline_ns) is int,
            "EXACT_BOOT_COLLECTION_SCOPE_REQUIRED",
        )
        with self._lock:
            _need(not self._used, "BOOT_COLLECTOR_ALREADY_USED")
            self._used = True
        i = self._intent.to_dict()
        b = i["binding"]
        phase_id = i["phase_id"]

        def check() -> None:
            _need(
                not cancellation.is_set() and monotonic_ns() < deadline_ns,
                "BOOT_ACTION_INTERRUPTED",
            )
            # Check the runtime result too: a truthy return is not permission.
            guard_result: Any = revalidate_context()  # type: ignore[func-returns-value]
            _need(guard_result is None, "BOOT_CONTEXT_GUARD_REQUIRED")
            _need(
                source_fingerprint(self._workspace) == b["source_sha256"],
                "BOOT_SOURCE_CHANGED",
            )
            _need(
                not cancellation.is_set() and monotonic_ns() < deadline_ns,
                "BOOT_ACTION_INTERRUPTED",
            )

        check()
        snap = tx.snapshot()
        _need(
            tx.held_leases
            == (
                LeaseSpec(LeaseLevel.CELL, b["cell_id"]),
                LeaseSpec(LeaseLevel.SESSION, b["session_id"]),
            )
            and snap.header.header_sha256 == b["header_sha256"]
            and snap.header.source_binding_sha256
            == physical_camera_source_binding(b["source_sha256"])
            and not snap.reconciliation_required
            and all(snap.state_for(s) is V2StageState.PASS for s in STAGE_ORDER[:3])
            and all(snap.state_for(s) is V2StageState.PENDING for s in STAGE_ORDER[4:])
            and snap.state_for(_STAGE) is V2StageState.BLOCKED
            and bool(snap.committed_events)
            and snap.committed_events[-1].detail_code
            == usb_phase_event("REVIEWED", phase_id)
            and snap.committed_events[-1].stage is _STAGE
            and snap.committed_events[-1].previous_state is V2StageState.REVIEW_PENDING
            and snap.committed_events[-1].state is V2StageState.BLOCKED
            and intent_reference in snap.committed_events[-1].evidence,
            "BOOT_CURRENT_REVIEWED_ORIGINAL_REQUIRED",
        )
        _need(
            tx.read_stage_evidence(intent_reference) == self._intent.payload,
            "BOOT_ORIGINAL_INTENT_CHANGED",
        )
        plan_ref = _parse_evidence_reference(i["plan_reference"])
        plan = UsbQualificationPlan(tx.read_stage_evidence(plan_ref))
        start = _parse_event(i["phase_start_event"])
        _need(start in snap.committed_events, "BOOT_ORIGINAL_PHASE_START_REQUIRED")
        verify_usb_trial_boot_intent(
            self._intent,
            plan=plan,
            plan_reference=plan_ref,
            phase_start_event=start,
            phase_id=phase_id,
            launch_session_id=i["launch_session_id"],
            expected_sha256=self._intent.sha256,
        )
        check()
        requested = tx.commit_stage_state(
            _STAGE,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=time_ns(),
            detail_code=usb_phase_event("BOOT_REQUESTED", phase_id),
            expected_head_sha256=tx.snapshot().head.head_sha256,
            evidence=(intent_reference,),
        )
        event = requested.committed_events[-1]
        self._diagnostics.update(state="REQUESTED", requested_event=event.to_dict())
        # From here a crash/Stop leaves a durable pending request. No later
        # collector accepts that state, even if no child had yet been created.
        check()
        original_head = requested.head.head_sha256
        execution_deadline = min(deadline_ns, monotonic_ns() + 30_000_000_000)
        request = HostBootRequest(
            b["source_sha256"],
            b["session_id"],
            i["launch_session_id"],
            phase_id,
            b["trial_id"],
            i["phase"],
            execution_deadline,
        )

        def admit() -> None:
            check()
            current = tx.snapshot()
            _need(
                current.head.head_sha256 == original_head
                and current.committed_events[-1] == event
                and current.state_for(_STAGE) is V2StageState.WAITING_OPERATOR
                and not current.reconciliation_required
                and monotonic_ns() < execution_deadline,
                "BOOT_ADMISSION_CHANGED",
            )

        observer = WindowsHostBootObserver()
        self._diagnostics["state"] = "OBSERVING"
        report = observer.observe(
            request,
            cancellation=cancellation,
            deadline_ns=execution_deadline,
            admission_check=admit,
        )
        record = dict(
            document=report.to_dict(),
            evidence_sha256=report.sha256,
            reference=None,
            retention="COLLECTED_NOT_M1_RETAINED",
        )
        self._diagnostics["host_boot"] = record
        verify_usb_trial_boot_observation(
            report,
            intent=self._intent,
            expected_sha256=report.sha256,
            requested_event=event,
        )
        # Retention is deliberately not cancelled with acquisition. Full held
        # results belong in the original log even after Stop or timeout.
        reference = tx.store_evidence(
            _STAGE,
            report.payload,
            label=usb_phase_label("host_boot", phase_id),
            media_type="application/json",
            captured_at_ns=time_ns(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        record.update(
            reference=reference.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
        )
        _need(
            tx.read_stage_evidence(reference) == report.payload,
            "BOOT_ORIGINAL_REPORT_CHANGED",
        )
        record["retention"] = "M1_FULL_BYTES_READ_BACK"
        terminal = _terminal(report)
        finished = tx.commit_stage_state(
            _STAGE,
            (
                V2StageState.SIDE_EFFECT_UNCERTAIN
                if terminal == "BOOT_UNCERTAIN"
                else V2StageState.BLOCKED
            ),
            occurred_at_ns=time_ns(),
            detail_code=usb_phase_event(terminal, phase_id),
            expected_head_sha256=tx.snapshot().head.head_sha256,
            evidence=tuple(
                sorted((intent_reference, reference), key=lambda r: r.evidence_id)
            ),
        )
        self._diagnostics.update(
            state=terminal, terminal_event=finished.committed_events[-1].to_dict()
        )
        return deepcopy(record)
