"""Reviewed, one-shot original boot scope for a physical-node absence phase.

An intent reconstructs the complete original BASELINE; it is not an executable
permit. The collector authenticates those originals under stage-only M1 leases,
then records a request before constructing the fixed local boot observer. A
pending request is never replayable. No USB, camera, serial, reboot or motion
operation belongs here. Every event reference tuple is sorted by evidence_id.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import re
from threading import Event, Lock
from time import monotonic_ns, time_ns
from typing import Any, Callable

from . import physical_camera_usb_qualification as qualification
from .commissioning_camera_persistence import (
    M1PhysicalCameraTransaction,
    physical_camera_source_binding,
)
from .physical_onboarding import EvidenceReference, STAGE_ORDER
from .physical_onboarding_leases import LeaseLevel, LeaseSpec
from .physical_onboarding_v2 import V2JournalEvent, V2StageState, _parse_event
from .physical_usb_presence_binding import (
    UsbPresencePhaseBinding,
    _manifest,
    _subject_manifest,
    verify_usb_presence_phase_binding,
)
from .physical_usb_presence_campaign import MAX_OPERATION_BYTES, UsbPresenceOperation
from .physical_usb_presence_phase import EVENT_LIMIT, UsbPresenceOperatorEvent
from .physical_usb_trial_boot import _terminal as boot_terminal
from .wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.host_boot_observation import (
    HostBootObservation,
    HostBootRequest,
    SCRIPT_SHA256,
    WindowsHostBootObserver,
    compare_boot_observations,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest

INTENT_SCHEMA = "rocell.usb_absence_boot_intent.v1"
REVIEW_SCHEMA = "rocell.usb_absence_boot_review.v1"
MAX_INTENT_BYTES = 16 * 1024
MAX_REVIEW_BYTES = 8 * 1024
MAX_HOST_BOOT_BYTES = 32 * 1024
PHASE = "RECONNECT_ABSENCE"
_STAGE = STAGE_ORDER[3]
_BUDGET = dict(admission_window_ms=30000, process_run_ms=10000, cleanup_ms=2000)
_FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    camera_capture_authorized=False,
    arm_access_authorized=False,
    automatic_replay=False,
)
_EVENTS = frozenset(
    (
        "PREPARATION_REQUESTED",
        "BOOT_REVIEWED",
        "BOOT_REQUESTED",
        "BOOT_RETAINED",
        "BOOT_HELD",
        "BOOT_UNCERTAIN",
    )
)
_LABELS = dict(
    boot_intent="camera-usb-absence-boot-intent-v1",
    boot_review="camera-usb-absence-boot-review-v1",
    host_boot="camera-usb-absence-host-boot-v1",
)
_INTENT_FIELDS = {
    "schema",
    "binding",
    "phase",
    "phase_id",
    "launch_session_id",
    "operator_id",
    "phase_binding_sha256",
    "baseline",
    "operation",
    "operator_event",
    "phase_start_event",
    "phase_started_at_utc_ns",
    "reported_at_utc_ns",
    "script_sha256",
    "budget",
    *_FLAGS,
}
_REVIEW_FIELDS = {
    "schema",
    "binding",
    "phase",
    "phase_id",
    "launch_session_id",
    "operator_id",
    "reviewer_id",
    "reviewed_at_ns",
    "intent_sha256",
    "script_sha256",
    "budget",
    "decision",
    "distinct_operator_labels",
    "authenticated_independent_people",
    *_FLAGS,
}


class UsbAbsenceBootError(ValueError):
    pass


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise UsbAbsenceBootError(code)


def _phase_id(value: Any) -> None:
    _need(
        type(value) is str
        and re.fullmatch(r"usbphase-[0-9a-f]{32}", value) is not None,
        "EXACT_ABSENCE_PHASE_ID_REQUIRED",
    )


def usb_absence_boot_event(kind: str, phase_id: str) -> str:
    _phase_id(phase_id)
    _need(type(kind) is str and kind in _EVENTS, "EXACT_ABSENCE_BOOT_EVENT_REQUIRED")
    return "CAMERA_USB_TRIAL_ABSENCE_" + kind + "_" + phase_id[9:].upper()


def usb_absence_boot_label(role: str, phase_id: str) -> str:
    _phase_id(phase_id)
    _need(type(role) is str and role in _LABELS, "EXACT_ABSENCE_BOOT_ROLE_REQUIRED")
    return _LABELS[role] + ":" + phase_id


def _refs(*references: EvidenceReference) -> tuple[EvidenceReference, ...]:
    _need(
        all(type(r) is EvidenceReference for r in references)
        and len({r.evidence_id for r in references}) == len(references),
        "DISTINCT_ORIGINAL_REFERENCES_REQUIRED",
    )
    return tuple(sorted(references, key=lambda r: r.evidence_id))


def _event(
    value: Any,
    *,
    binding: dict[str, Any],
    phase_id: str,
    kind: str,
    previous: V2StageState,
    state: V2StageState,
    references: tuple[EvidenceReference, ...],
) -> V2JournalEvent:
    result = _parse_event(value.to_dict() if type(value) is V2JournalEvent else value)
    _need(
        result.session_id == binding["session_id"]
        and result.session_header_sha256 == binding["header_sha256"]
        and result.stage is _STAGE
        and result.previous_state is previous
        and result.state is state
        and result.detail_code == usb_absence_boot_event(kind, phase_id)
        and result.evidence == _refs(*references),
        "ABSENCE_BOOT_ORIGINAL_EVENT_MISMATCH",
    )
    return result


def _load(payload: bytes, *, review: bool) -> dict[str, Any]:
    try:
        d = qualification._load(
            payload, MAX_REVIEW_BYTES if review else MAX_INTENT_BYTES
        )
        qualification._exact(d, _REVIEW_FIELDS if review else _INTENT_FIELDS)
        qualification._binding(d["binding"])
        _phase_id(d["phase_id"])
        qualification._identifier(d["launch_session_id"])
        qualification._text(d["operator_id"], 64)
        _need(
            d["schema"] == (REVIEW_SCHEMA if review else INTENT_SCHEMA)
            and d["phase"] == PHASE
            and d["script_sha256"] == SCRIPT_SHA256
            and canonical(d["budget"]) == canonical(_BUDGET)
            and all(d[key] is False for key in _FLAGS),
            "ABSENCE_BOOT_POLICY_CHANGED",
        )
        if review:
            qualification._sha(d["intent_sha256"])
            qualification._text(d["reviewer_id"], 64)
            qualification._integer(d["reviewed_at_ns"], 1)
            _need(
                d["operator_id"].casefold() != d["reviewer_id"].casefold()
                and d["decision"] == "ACKNOWLEDGE_EXACT_LOCAL_HOST_BOOT_SCOPE"
                and d["distinct_operator_labels"] is True
                and d["authenticated_independent_people"] is False,
                "DISTINCT_EXACT_BOOT_SCOPE_REVIEW_REQUIRED",
            )
        else:
            qualification._sha(d["phase_binding_sha256"])
            baseline = _manifest(
                d["baseline"], maximum=qualification.UsbQualificationPhase.limit
            )
            operation = _manifest(d["operation"], maximum=MAX_OPERATION_BYTES)
            operator = _manifest(d["operator_event"], maximum=EVENT_LIMIT)
            _refs(baseline, operation, operator)
            qualification._integer(d["phase_started_at_utc_ns"], 1)
            qualification._integer(
                d["reported_at_utc_ns"], d["phase_started_at_utc_ns"]
            )
            start = _event(
                d["phase_start_event"],
                binding=d["binding"],
                phase_id=d["phase_id"],
                kind="PREPARATION_REQUESTED",
                previous=V2StageState.BLOCKED,
                state=V2StageState.WAITING_OPERATOR,
                references=(baseline,),
            )
            _need(
                start.occurred_at_ns == d["phase_started_at_utc_ns"],
                "EXACT_PHASE_START_TIME_REQUIRED",
            )
        return d
    except UsbAbsenceBootError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbAbsenceBootError("INVALID_ABSENCE_BOOT_FIELDS") from exc


@dataclass(frozen=True, slots=True)
class UsbAbsenceBootIntent:
    """Pure immutable intent; original-store authentication is a separate duty."""

    payload: bytes

    def __post_init__(self) -> None:
        _load(self.payload, review=False)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, review=False)


@dataclass(frozen=True, slots=True)
class UsbAbsenceBootReview:
    """Distinct actor labels do not authenticate different people."""

    payload: bytes

    def __post_init__(self) -> None:
        _load(self.payload, review=True)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, review=True)


def build_usb_absence_boot_intent(
    *,
    operation: UsbPresenceOperation,
    operation_reference: EvidenceReference,
    operator_event: UsbPresenceOperatorEvent,
    operator_event_reference: EvidenceReference,
    phase_start_event: V2JournalEvent,
    original_baseline: dict[str, Any],
) -> UsbAbsenceBootIntent:
    _need(
        type(operation) is UsbPresenceOperation
        and type(operator_event) is UsbPresenceOperatorEvent
        and type(phase_start_event) is V2JournalEvent
        and type(original_baseline) is dict,
        "EXACT_ABSENCE_BOOT_INPUTS_REQUIRED",
    )
    operation = UsbPresenceOperation(operation.payload)
    operator_event = UsbPresenceOperatorEvent(operator_event.payload)
    o, reported = operation.to_dict(), operator_event.to_dict()
    phase = UsbPresencePhaseBinding(canonical(o["phase_binding"]))
    bound = verify_usb_presence_phase_binding(
        phase.payload, expected_sha256=phase.sha256, **original_baseline
    ).to_dict()
    baseline_ref = qualification._reference(bound["baseline"]["reference"])
    start = _event(
        phase_start_event,
        binding=bound["binding"],
        phase_id=o["operation_id"],
        kind="PREPARATION_REQUESTED",
        previous=V2StageState.BLOCKED,
        state=V2StageState.WAITING_OPERATOR,
        references=(baseline_ref,),
    )
    _need(
        o["operation_id"] != bound["baseline"]["context"]["operation_id"]
        and canonical(reported["binding"]) == canonical(bound["binding"])
        and reported["phase_binding_sha256"] == phase.sha256
        and reported["phase_id"] == o["operation_id"]
        and reported["launch_session_id"] == o["launch_session_id"]
        and reported["phase_started_at_utc_ns"] == start.occurred_at_ns
        and start.occurred_at_ns >= bound["not_before_utc_ns"],
        "ABSENCE_BOOT_ORIGINAL_SUBJECTS_MISMATCH",
    )
    return UsbAbsenceBootIntent(
        canonical(
            dict(
                schema=INTENT_SCHEMA,
                binding=bound["binding"],
                phase=PHASE,
                phase_id=o["operation_id"],
                launch_session_id=o["launch_session_id"],
                operator_id=reported["operator_id"],
                phase_binding_sha256=phase.sha256,
                baseline={
                    key: bound["baseline"][key]
                    for key in ("sha256", "payload_bytes", "reference")
                },
                operation=_subject_manifest(operation, operation_reference),
                operator_event=_subject_manifest(
                    operator_event, operator_event_reference
                ),
                phase_start_event=start.to_dict(),
                phase_started_at_utc_ns=start.occurred_at_ns,
                reported_at_utc_ns=reported["reported_at_utc_ns"],
                script_sha256=SCRIPT_SHA256,
                budget=_BUDGET,
                **_FLAGS,
            )
        )
    )


def verify_usb_absence_boot_intent(
    value: Any,
    *,
    expected_sha256: str,
    **originals: Any,
) -> UsbAbsenceBootIntent:
    result = UsbAbsenceBootIntent(
        value.payload if type(value) is UsbAbsenceBootIntent else value
    )
    expected = build_usb_absence_boot_intent(**originals)
    _need(
        result.sha256 == expected_sha256 and result.payload == expected.payload,
        "ABSENCE_BOOT_INTENT_RECONSTRUCTION_MISMATCH",
    )
    return result


def review_usb_absence_boot_intent(
    intent: UsbAbsenceBootIntent,
    *,
    reviewer_id: str,
    launch_session_id: str,
    reviewed_at_ns: int,
) -> UsbAbsenceBootReview:
    _need(type(intent) is UsbAbsenceBootIntent, "EXACT_ABSENCE_BOOT_INTENT_REQUIRED")
    d = UsbAbsenceBootIntent(intent.payload).to_dict()
    qualification._integer(reviewed_at_ns, d["reported_at_utc_ns"])
    _need(
        launch_session_id == d["launch_session_id"],
        "BOOT_REVIEW_CURRENT_LAUNCH_REQUIRED",
    )
    return UsbAbsenceBootReview(
        canonical(
            dict(
                schema=REVIEW_SCHEMA,
                **{
                    key: d[key]
                    for key in (
                        "binding",
                        "phase",
                        "phase_id",
                        "launch_session_id",
                        "operator_id",
                        "script_sha256",
                        "budget",
                    )
                },
                reviewer_id=reviewer_id,
                reviewed_at_ns=reviewed_at_ns,
                intent_sha256=intent.sha256,
                decision="ACKNOWLEDGE_EXACT_LOCAL_HOST_BOOT_SCOPE",
                distinct_operator_labels=True,
                authenticated_independent_people=False,
                **_FLAGS,
            )
        )
    )


def verify_usb_absence_boot_review(
    value: Any,
    *,
    intent: UsbAbsenceBootIntent,
    expected_sha256: str,
) -> UsbAbsenceBootReview:
    review = UsbAbsenceBootReview(
        value.payload if type(value) is UsbAbsenceBootReview else value
    )
    d = review.to_dict()
    expected = review_usb_absence_boot_intent(
        intent,
        reviewer_id=d["reviewer_id"],
        launch_session_id=d["launch_session_id"],
        reviewed_at_ns=d["reviewed_at_ns"],
    )
    _need(
        review.sha256 == expected_sha256 and review.payload == expected.payload,
        "ABSENCE_BOOT_REVIEW_RECONSTRUCTION_MISMATCH",
    )
    return review


def verify_usb_absence_boot_observation(
    value: Any,
    *,
    intent: UsbAbsenceBootIntent,
    expected_sha256: str,
    requested_event: V2JournalEvent,
) -> HostBootObservation:
    """Pure byte/context join, not proof of original M1 or physical execution."""
    _need(
        type(intent) is UsbAbsenceBootIntent
        and type(requested_event) is V2JournalEvent,
        "EXACT_ABSENCE_BOOT_OBSERVATION_INPUTS_REQUIRED",
    )
    i = UsbAbsenceBootIntent(intent.payload).to_dict()
    report = HostBootObservation(
        value.payload if type(value) is HostBootObservation else value
    )
    d = report.to_dict()
    event = _parse_event(requested_event.to_dict())
    _need(len(event.evidence) == 1, "EXACT_BOOT_REQUEST_INTENT_REFERENCE_REQUIRED")
    _subject_manifest(intent, event.evidence[0])
    _event(
        event,
        binding=i["binding"],
        phase_id=i["phase_id"],
        kind="BOOT_REQUESTED",
        previous=V2StageState.BLOCKED,
        state=V2StageState.WAITING_OPERATOR,
        references=event.evidence,
    )
    _need(
        len(report.payload) <= MAX_HOST_BOOT_BYTES
        and report.sha256 == expected_sha256
        and all(
            d["request"][key] == expected
            for key, expected in dict(
                source_sha256=i["binding"]["source_sha256"],
                session_id=i["binding"]["session_id"],
                trial_id=i["binding"]["trial_id"],
                phase=PHASE,
                operation_id=i["phase_id"],
                launch_session_id=i["launch_session_id"],
            ).items()
        )
        and i["reported_at_utc_ns"]
        <= event.occurred_at_ns
        <= d["execution"]["started_utc_ns"]
        and d["deadline_ns"] == d["request"]["expires_at_ns"]
        and d["deadline_ns"] - d["execution"]["started_monotonic_ns"] <= 30_000_000_000,
        "ABSENCE_BOOT_OBSERVATION_INTENT_MISMATCH",
    )
    return report


def _terminal(report: HostBootObservation, baseline_boot: HostBootObservation) -> str:
    status = boot_terminal(report)
    if (
        status == "BOOT_RETAINED"
        and compare_boot_observations(baseline_boot, report)["status"]
        != "SAME_HOST_SAME_BOOT"
    ):
        return "BOOT_HELD"
    return status


class OriginalUsbAbsenceBootCollector:
    """One original-reviewed boot request; no executor or command override."""

    def __init__(
        self,
        workspace: Path,
        intent: UsbAbsenceBootIntent,
        review: UsbAbsenceBootReview,
    ):
        _need(
            isinstance(workspace, Path)
            and workspace.is_absolute()
            and type(intent) is UsbAbsenceBootIntent
            and type(review) is UsbAbsenceBootReview,
            "EXACT_ABSENCE_BOOT_COLLECTOR_REQUIRED",
        )
        self._workspace = workspace
        self._intent = UsbAbsenceBootIntent(intent.payload)
        self._review = verify_usb_absence_boot_review(
            review, intent=self._intent, expected_sha256=review.sha256
        )
        self._lock, self._used = Lock(), False
        self._diagnostics: dict[str, Any] = dict(
            state="NOT_STARTED",
            requested_event=None,
            host_boot=None,
            boot_comparison=None,
            context_current=None,
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
        review_reference: EvidenceReference,
        cancellation: Event,
        deadline_ns: int,
        revalidate_context: Callable[[], None],
    ) -> dict[str, Any]:
        _need(
            type(tx) is M1PhysicalCameraTransaction
            and type(intent_reference) is EvidenceReference
            and type(review_reference) is EvidenceReference
            and isinstance(cancellation, Event)
            and type(deadline_ns) is int
            and callable(revalidate_context),
            "EXACT_ABSENCE_BOOT_COLLECTION_SCOPE_REQUIRED",
        )
        with self._lock:
            _need(not self._used, "ABSENCE_BOOT_COLLECTOR_ALREADY_USED")
            self._used = True
        i = self._intent.to_dict()
        b, phase_id = i["binding"], i["phase_id"]

        def check() -> None:
            _need(
                not cancellation.is_set() and monotonic_ns() < deadline_ns,
                "BOOT_ACTION_INTERRUPTED",
            )
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

        def scope(snapshot: Any) -> None:
            _need(
                tx.held_leases
                == (
                    LeaseSpec(LeaseLevel.CELL, b["cell_id"]),
                    LeaseSpec(LeaseLevel.SESSION, b["session_id"]),
                )
                and snapshot.header.header_sha256 == b["header_sha256"]
                and snapshot.header.session_id == b["session_id"]
                and snapshot.header.cell_id == b["cell_id"]
                and snapshot.header.source_binding_sha256
                == physical_camera_source_binding(b["source_sha256"])
                and not snapshot.reconciliation_required
                and all(
                    snapshot.state_for(s) is V2StageState.PASS for s in STAGE_ORDER[:3]
                )
                and all(
                    snapshot.state_for(s) is V2StageState.PENDING
                    for s in STAGE_ORDER[4:]
                ),
                "BOOT_EXACT_ORIGINAL_STAGE_SCOPE_REQUIRED",
            )

        def read(
            manifest: dict[str, Any], maximum: int
        ) -> tuple[EvidenceReference, bytes]:
            reference = _manifest(manifest, maximum=maximum)
            payload = tx.read_stage_evidence(reference)
            qualification._reference(reference, payload)
            return reference, payload

        check()
        snap = tx.snapshot()
        scope(snap)
        _need(
            snap.state_for(_STAGE) is V2StageState.BLOCKED
            and bool(snap.committed_events),
            "BOOT_CURRENT_REVIEWED_ORIGINAL_REQUIRED",
        )
        reviewed = _event(
            snap.committed_events[-1],
            binding=b,
            phase_id=phase_id,
            kind="BOOT_REVIEWED",
            previous=V2StageState.REVIEW_PENDING,
            state=V2StageState.BLOCKED,
            references=_refs(intent_reference, review_reference),
        )
        _subject_manifest(self._intent, intent_reference)
        _subject_manifest(self._review, review_reference)
        _need(
            tx.read_stage_evidence(intent_reference) == self._intent.payload
            and tx.read_stage_evidence(review_reference) == self._review.payload,
            "BOOT_ORIGINAL_REVIEW_SUBJECTS_CHANGED",
        )
        _need(
            reviewed.occurred_at_ns >= self._review.to_dict()["reviewed_at_ns"],
            "BOOT_REVIEW_EVENT_CHRONOLOGY",
        )
        op_ref, op_bytes = read(i["operation"], MAX_OPERATION_BYTES)
        report_ref, report_bytes = read(i["operator_event"], EVENT_LIMIT)
        operation = UsbPresenceOperation(op_bytes)
        o = operation.to_dict()
        _need(
            Path(o["workspace"]) == self._workspace, "BOOT_ORIGINAL_WORKSPACE_CHANGED"
        )
        bound = o["phase_binding"]
        plan_ref, plan_bytes = read(
            bound["plan"], qualification.UsbQualificationPlan.limit
        )
        baseline_ref, baseline_bytes = read(
            {
                key: bound["baseline"][key]
                for key in ("sha256", "payload_bytes", "reference")
            },
            qualification.UsbQualificationPhase.limit,
        )
        sources = {}
        for row in bound["sources"]:
            _, raw = read(
                {key: row[key] for key in ("sha256", "payload_bytes", "reference")},
                qualification.ROLE_LIMITS[row["role"]],
            )
            sources[row["role"]] = raw
        start = _parse_event(i["phase_start_event"])
        declaration = _parse_event(bound["declaration_event"])
        _need(
            start in snap.committed_events
            and declaration in snap.committed_events
            and declaration.sequence < start.sequence < reviewed.sequence,
            "BOOT_ORIGINAL_START_AND_DECLARATION_REQUIRED",
        )
        verify_usb_absence_boot_intent(
            self._intent,
            expected_sha256=self._intent.sha256,
            operation=operation,
            operation_reference=op_ref,
            operator_event=UsbPresenceOperatorEvent(report_bytes),
            operator_event_reference=report_ref,
            phase_start_event=start,
            original_baseline=dict(
                plan=qualification.UsbQualificationPlan(plan_bytes),
                plan_reference=plan_ref,
                declaration_event=declaration,
                baseline=qualification.UsbQualificationPhase(baseline_bytes),
                baseline_reference=baseline_ref,
                baseline_sources=sources,
            ),
        )
        baseline_boot = HostBootObservation(sources["host_boot"])
        check()
        # The original head cannot change while the two stage leases are held.
        current = tx.snapshot()
        scope(current)
        _need(
            current.head.head_sha256 == snap.head.head_sha256,
            "BOOT_ORIGINAL_HEAD_CHANGED",
        )
        requested = tx.commit_stage_state(
            _STAGE,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=time_ns(),
            detail_code=usb_absence_boot_event("BOOT_REQUESTED", phase_id),
            expected_head_sha256=snap.head.head_sha256,
            evidence=(intent_reference,),
        )
        event = requested.committed_events[-1]
        self._diagnostics.update(state="REQUESTED", requested_event=event.to_dict())
        # A crash or Stop here leaves an original pending request, not a retry.
        check()
        execution_deadline = min(deadline_ns, monotonic_ns() + 30_000_000_000)
        request = HostBootRequest(
            b["source_sha256"],
            b["session_id"],
            i["launch_session_id"],
            phase_id,
            b["trial_id"],
            PHASE,
            execution_deadline,
        )

        def admit() -> None:
            check()
            current = tx.snapshot()
            scope(current)
            _need(
                current.head.head_sha256 == requested.head.head_sha256
                and current.committed_events[-1] == event
                and current.state_for(_STAGE) is V2StageState.WAITING_OPERATOR
                and monotonic_ns() < execution_deadline,
                "BOOT_ADMISSION_CHANGED",
            )

        self._diagnostics["state"] = "OBSERVING"
        report = WindowsHostBootObserver().observe(
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
        verify_usb_absence_boot_observation(
            report,
            intent=self._intent,
            expected_sha256=report.sha256,
            requested_event=event,
        )
        self._diagnostics["boot_comparison"] = compare_boot_observations(
            baseline_boot, report
        )
        # Currentness never controls retention of a completed or uncertain effect.
        # Stop/source/guard failures prevent a clean report from becoming a ready
        # successor, but the exact original bytes and actual counters survive.
        try:
            admit()
            context_current = True
        except Exception:
            context_current = False
        self._diagnostics["context_current"] = context_current
        reference = tx.store_evidence(
            _STAGE,
            report.payload,
            label=usb_absence_boot_label("host_boot", phase_id),
            media_type="application/json",
            captured_at_ns=time_ns(),
            expected_head_sha256=requested.head.head_sha256,
        )
        record.update(
            reference=reference.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
        )
        _need(
            tx.read_stage_evidence(reference) == report.payload,
            "BOOT_ORIGINAL_REPORT_CHANGED",
        )
        record["retention"] = "M1_FULL_BYTES_READ_BACK"
        # Retention can itself span Stop or source/context changes. A later
        # successful check cannot erase an earlier loss of currentness.
        try:
            admit()
        except Exception:
            context_current = False
        self._diagnostics["context_current"] = context_current
        terminal = _terminal(report, baseline_boot)
        if terminal == "BOOT_RETAINED" and not context_current:
            terminal = "BOOT_HELD"
        finished = tx.commit_stage_state(
            _STAGE,
            (
                V2StageState.SIDE_EFFECT_UNCERTAIN
                if terminal == "BOOT_UNCERTAIN"
                else V2StageState.BLOCKED
            ),
            occurred_at_ns=time_ns(),
            detail_code=usb_absence_boot_event(terminal, phase_id),
            expected_head_sha256=requested.head.head_sha256,
            evidence=_refs(intent_reference, reference),
        )
        self._diagnostics.update(
            state=terminal, terminal_event=finished.committed_events[-1].to_dict()
        )
        return deepcopy(record)
