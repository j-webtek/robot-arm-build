"""One reviewed original reconnect boot observation, never an executable ticket.

The collector re-reads the original preparation, reviews and physical absence
under stage-only leases before committing its one-use request. The fixed local
observer is constructed only after that commit. Stop, changed context and uncertain
cleanup never discard a returned report or permit replay. Reference tuples are
sorted by evidence_id. No USB, camera, serial, reboot or motion belongs here.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock
from time import monotonic_ns, time_ns
from typing import Any, Callable

from . import physical_camera_usb_qualification as qualification
from .commissioning_camera_persistence import (
    M1PhysicalCameraTransaction,
    physical_camera_source_binding,
)
from .physical_camera_usb_reconnect import (
    UsbReconnectPreparation,
    USB_RECONNECT_ROLE_BYTES,
    usb_reconnect_event,
    usb_reconnect_label,
    verify_usb_reconnect_preparation,
)
from .physical_onboarding import EvidenceReference, STAGE_ORDER
from .physical_onboarding_leases import LeaseLevel, LeaseSpec
from .physical_onboarding_v2 import V2JournalEvent, V2StageState, _parse_event
from .physical_usb_identity_campaign import (
    MAX_OPERATION_BYTES,
    PhysicalUsbIdentityCampaign,
    UsbIdentityOperation,
)
from .physical_usb_presence_binding import _manifest, _subject_manifest
from .physical_usb_presence_campaign import UsbPresenceOperation
from .physical_usb_presence_phase import UsbPresenceQualificationPhase
from .physical_usb_reconnect_phase import UsbReconnectOperatorEvent, _phase_id
from .physical_usb_trial_boot import _terminal as boot_terminal
from .usb_identity_stage_policy import (
    UsbIdentityAdmissionIdentity,
    UsbIdentityPolicyReview,
)
from .wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.host_boot_observation import (
    HostBootObservation,
    HostBootRequest,
    SCRIPT_SHA256,
    WindowsHostBootObserver,
    compare_boot_observations,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.providers.windows.usb_identity_registration import UsbIdentityRuntimeReview

SCHEMA = INTENT_SCHEMA = "rocell.usb_reconnect_boot_intent.v1"
MAX_INTENT_BYTES = 16 * 1024
MAX_HOST_BOOT_BYTES = 32 * 1024
PHASE = "AFTER_RECONNECT"
_STAGE = STAGE_ORDER[3]
_BUDGET = dict(admission_window_ms=30000, process_run_ms=10000, cleanup_ms=2000)
_FLAGS = dict(
    **qualification.FLAGS, arm_access_authorized=False, automatic_replay=False
)
_FIELDS = {
    "schema",
    "binding",
    "plan_sha256",
    "plan_reference",
    "absence_sha256",
    "absence_reference",
    "preparation",
    "operator_event",
    "enrollment",
    "operation_sha256",
    "phase",
    "phase_id",
    "phase_start_event",
    "launch_session_id",
    "operator_id",
    "phase_started_at_utc_ns",
    "reported_at_utc_ns",
    "prepared_at_utc_ns",
    "script_sha256",
    "budget",
    *_FLAGS,
}


class UsbReconnectBootError(ValueError):
    """Closed original-boot mismatch; not raw original diagnostic content."""


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise UsbReconnectBootError(code)


def _refs(*references: EvidenceReference) -> tuple[EvidenceReference, ...]:
    _need(
        all(type(ref) is EvidenceReference for ref in references)
        and len({ref.evidence_id for ref in references}) == len(references),
        "DISTINCT_BOOT_ORIGINALS_REQUIRED",
    )
    return tuple(sorted(references, key=lambda ref: ref.evidence_id))


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
    event = _parse_event(value.to_dict() if type(value) is V2JournalEvent else value)
    _need(
        event.session_id == binding["session_id"]
        and event.session_header_sha256 == binding["header_sha256"]
        and event.stage is _STAGE
        and event.previous_state is previous
        and event.state is state
        and event.detail_code == usb_reconnect_event(kind, phase_id)
        and event.evidence == _refs(*references),
        "RECONNECT_BOOT_ORIGINAL_EVENT_MISMATCH",
    )
    return event


def _load(payload: bytes) -> dict[str, Any]:
    try:
        d = qualification._load(payload, MAX_INTENT_BYTES)
        qualification._exact(d, _FIELDS)
        qualification._binding(d["binding"])
        _phase_id(d["phase_id"])
        qualification._identifier(d["launch_session_id"])
        qualification._text(d["operator_id"], 64)
        for key in ("plan_sha256", "absence_sha256", "operation_sha256"):
            qualification._sha(d[key])
        _need(
            d["schema"] == SCHEMA
            and d["phase"] == PHASE
            and d["script_sha256"] == SCRIPT_SHA256
            and canonical(d["budget"]) == canonical(_BUDGET)
            and all(d[key] is False for key in _FLAGS),
            "RECONNECT_BOOT_POLICY_CHANGED",
        )
        plan = qualification._reference(d["plan_reference"])
        absence = qualification._reference(d["absence_reference"])
        _need(
            plan.payload_sha256 == d["plan_sha256"]
            and 0 < plan.payload_bytes <= qualification.UsbQualificationPlan.limit
            and absence.payload_sha256 == d["absence_sha256"]
            and 0 < absence.payload_bytes <= 16 * 1024,
            "RECONNECT_BOOT_PREDECESSOR_REFERENCE_MISMATCH",
        )
        refs = [plan, absence]
        for name, role in (
            ("preparation", "preparation"),
            ("operator_event", "operator_event"),
            ("enrollment", "enrollment"),
        ):
            refs.append(_manifest(d[name], maximum=USB_RECONNECT_ROLE_BYTES[role]))
        _refs(*refs)
        qualification._integer(d["phase_started_at_utc_ns"], 1)
        qualification._integer(d["reported_at_utc_ns"], d["phase_started_at_utc_ns"])
        qualification._integer(d["prepared_at_utc_ns"], d["reported_at_utc_ns"])
        start = _event(
            d["phase_start_event"],
            binding=d["binding"],
            phase_id=d["phase_id"],
            kind="PREPARATION_REQUESTED",
            previous=V2StageState.BLOCKED,
            state=V2StageState.WAITING_OPERATOR,
            references=(absence,),
        )
        _need(
            start.occurred_at_ns == d["phase_started_at_utc_ns"],
            "RECONNECT_BOOT_START_TIME_MISMATCH",
        )
        return d
    except UsbReconnectBootError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbReconnectBootError("INVALID_RECONNECT_BOOT_INTENT") from exc


@dataclass(frozen=True, slots=True)
class UsbReconnectBootIntent:
    payload: bytes

    def __post_init__(self) -> None:
        _load(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload)


def build_usb_reconnect_boot_intent(
    *, preparation: UsbReconnectPreparation, preparation_reference: EvidenceReference
) -> UsbReconnectBootIntent:
    """Bind an exact preparation; original-byte authentication occurs at collection."""
    _need(
        type(preparation) is UsbReconnectPreparation
        and type(preparation_reference) is EvidenceReference,
        "EXACT_RECONNECT_BOOT_PREPARATION_REQUIRED",
    )
    preparation = UsbReconnectPreparation(preparation.payload)
    d = preparation.to_dict()
    report = UsbReconnectOperatorEvent(canonical(d["operator_event"]))
    r = report.to_dict()
    enrollment_ref = qualification._reference(d["enrollment_reference"])
    return UsbReconnectBootIntent(
        canonical(
            dict(
                schema=SCHEMA,
                binding=r["binding"],
                plan_sha256=d["plan_sha256"],
                plan_reference=d["plan_reference"],
                absence_sha256=d["absence_sha256"],
                absence_reference=d["absence_reference"],
                preparation=_subject_manifest(preparation, preparation_reference),
                operator_event=_subject_manifest(
                    report, qualification._reference(d["operator_event_reference"])
                ),
                enrollment=dict(
                    sha256=d["enrollment_sha256"],
                    payload_bytes=enrollment_ref.payload_bytes,
                    reference=enrollment_ref.to_dict(),
                ),
                operation_sha256=d["operation_sha256"],
                phase=PHASE,
                phase_id=d["phase_id"],
                phase_start_event=d["phase_start_event"],
                launch_session_id=r["launch_session_id"],
                operator_id=d["operator_id"],
                phase_started_at_utc_ns=r["phase_started_at_utc_ns"],
                reported_at_utc_ns=r["reported_at_utc_ns"],
                prepared_at_utc_ns=d["prepared_at_utc_ns"],
                script_sha256=SCRIPT_SHA256,
                budget=_BUDGET,
                **_FLAGS,
            )
        )
    )


def verify_usb_reconnect_boot_intent(
    value: Any,
    *,
    expected_sha256: str,
    preparation: UsbReconnectPreparation,
    preparation_reference: EvidenceReference,
) -> UsbReconnectBootIntent:
    qualification._sha(expected_sha256)
    current = UsbReconnectBootIntent(
        value.payload if type(value) is UsbReconnectBootIntent else value
    )
    expected = build_usb_reconnect_boot_intent(
        preparation=preparation, preparation_reference=preparation_reference
    )
    _need(
        current.sha256 == expected_sha256 and current.payload == expected.payload,
        "RECONNECT_BOOT_INTENT_RECONSTRUCTION_MISMATCH",
    )
    return current


def verify_usb_reconnect_boot_observation(
    value: Any,
    *,
    intent: UsbReconnectBootIntent,
    expected_sha256: str,
    requested_event: V2JournalEvent,
) -> HostBootObservation:
    """Pure original request/report join. HELD/uncertain observations stay readable."""
    _need(
        type(intent) is UsbReconnectBootIntent
        and type(requested_event) is V2JournalEvent,
        "EXACT_RECONNECT_BOOT_OBSERVATION_INPUTS",
    )
    qualification._sha(expected_sha256)
    intent = UsbReconnectBootIntent(intent.payload)
    i = intent.to_dict()
    event = _parse_event(requested_event.to_dict())
    _need(len(event.evidence) == 1, "EXACT_BOOT_INTENT_REFERENCE_REQUIRED")
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
    report = HostBootObservation(
        value.payload if type(value) is HostBootObservation else value
    )
    d = report.to_dict()
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
        and i["prepared_at_utc_ns"]
        <= event.occurred_at_ns
        <= d["execution"]["started_utc_ns"]
        and d["deadline_ns"] == d["request"]["expires_at_ns"]
        and d["deadline_ns"] - d["execution"]["started_monotonic_ns"] <= 30_000_000_000,
        "RECONNECT_BOOT_OBSERVATION_INTENT_MISMATCH",
    )
    return report


def _terminal(report: HostBootObservation, absence_boot: HostBootObservation) -> str:
    status = boot_terminal(HostBootObservation(report.payload))
    if status == "BOOT_RETAINED" and (
        boot_terminal(HostBootObservation(absence_boot.payload)) != "BOOT_RETAINED"
        or compare_boot_observations(HostBootObservation(absence_boot.payload), report)[
            "status"
        ]
        != "SAME_HOST_SAME_BOOT"
    ):
        return "BOOT_HELD"
    return status


def _read(
    tx: M1PhysicalCameraTransaction, ref: EvidenceReference, maximum: int
) -> bytes:
    ref = qualification._reference(ref)
    _need(0 < ref.payload_bytes <= maximum, "BOOT_ORIGINAL_BYTES_LIMIT")
    raw = tx.read_stage_evidence(ref)
    qualification._reference(ref, raw)
    return raw


def _original_preparation(
    tx: M1PhysicalCameraTransaction, intent: UsbReconnectBootIntent, snapshot: Any
) -> tuple[UsbReconnectPreparation, HostBootObservation, EvidenceReference]:
    """Rebuild the full physical predecessor from actual leased original bytes."""
    i = intent.to_dict()
    prep_ref = _manifest(
        i["preparation"], maximum=USB_RECONNECT_ROLE_BYTES["preparation"]
    )
    prep = UsbReconnectPreparation(
        _read(tx, prep_ref, USB_RECONNECT_ROLE_BYTES["preparation"])
    )
    verify_usb_reconnect_boot_intent(
        intent,
        expected_sha256=intent.sha256,
        preparation=prep,
        preparation_reference=prep_ref,
    )
    pd = prep.to_dict()
    absence_ref = qualification._reference(i["absence_reference"])
    absence = UsbPresenceQualificationPhase(_read(tx, absence_ref, 16 * 1024))
    ad = absence.to_dict()
    sources = {}
    limits = dict(
        operation=32 * 1024,
        operator_event=8 * 1024,
        owned_presence_run=128 * 1024,
        host_boot=32 * 1024,
    )
    for row in ad["records"]:
        sources[row["role"]] = _read(
            tx, qualification._reference(row["reference"]), limits[row["role"]]
        )
    bound = UsbPresenceOperation(sources["operation"]).to_dict()["phase_binding"]
    plan_ref = _manifest(
        bound["plan"], maximum=qualification.UsbQualificationPlan.limit
    )
    plan = qualification.UsbQualificationPlan(
        _read(tx, plan_ref, qualification.UsbQualificationPlan.limit)
    )
    baseline_ref = _manifest(
        {
            key: bound["baseline"][key]
            for key in ("sha256", "payload_bytes", "reference")
        },
        maximum=qualification.UsbQualificationPhase.limit,
    )
    baseline = qualification.UsbQualificationPhase(
        _read(tx, baseline_ref, qualification.UsbQualificationPhase.limit)
    )
    baseline_sources = {
        row["role"]: _read(
            tx,
            qualification._reference(row["reference"]),
            qualification.ROLE_LIMITS[row["role"]],
        )
        for row in bound["sources"]
    }
    declaration = _parse_event(bound["declaration_event"])
    start = _parse_event(i["phase_start_event"])
    absent_code = (
        "CAMERA_USB_TRIAL_ABSENCE_RETAINED_" + ad["context"]["operation_id"][9:].upper()
    )
    terminals = [
        event for event in snapshot.committed_events if event.detail_code == absent_code
    ]
    _need(len(terminals) == 1, "EXACT_ORIGINAL_ABSENCE_TERMINAL_REQUIRED")
    terminal = _parse_event(terminals[0].to_dict())
    _need(
        start in snapshot.committed_events
        and declaration in snapshot.committed_events
        and terminal.stage is _STAGE
        and terminal.previous_state is V2StageState.WAITING_OPERATOR
        and terminal.state is V2StageState.BLOCKED
        and terminal.session_id == i["binding"]["session_id"]
        and terminal.session_header_sha256 == i["binding"]["header_sha256"]
        and len(terminal.evidence) == 9
        and absence_ref in terminal.evidence
        and all(
            qualification._reference(row["reference"]) in terminal.evidence
            for row in ad["records"]
        )
        and declaration.sequence
        < terminal.sequence
        < start.sequence
        < snapshot.committed_events[-1].sequence,
        "BOOT_ORIGINAL_PREDECESSOR_EVENTS_REQUIRED",
    )
    operator_ref = _manifest(
        i["operator_event"], maximum=USB_RECONNECT_ROLE_BYTES["operator_event"]
    )
    report = UsbReconnectOperatorEvent(
        _read(tx, operator_ref, USB_RECONNECT_ROLE_BYTES["operator_event"])
    )
    enrollment_ref = _manifest(
        i["enrollment"], maximum=USB_RECONNECT_ROLE_BYTES["enrollment"]
    )
    enrollment = _read(tx, enrollment_ref, USB_RECONNECT_ROLE_BYTES["enrollment"])
    prepared_original = _parse_event(snapshot.committed_events[-2].to_dict())
    known_prepared = _refs(operator_ref, enrollment_ref, prep_ref)
    operation_refs = tuple(
        ref for ref in prepared_original.evidence if ref not in known_prepared
    )
    _need(
        len(prepared_original.evidence) == 4 and len(operation_refs) == 1,
        "EXACT_PREPARED_OPERATION_ORIGINAL_REQUIRED",
    )
    operation_ref = operation_refs[0]
    # The operation is an independent original. Its reference is taken from
    # the committed PREPARED event, never reinterpreted from a nested document.
    operation = UsbIdentityOperation(_read(tx, operation_ref, MAX_OPERATION_BYTES))
    _need(
        operation.payload == canonical(pd["operation"])
        and operation.sha256 == pd["operation_sha256"] == i["operation_sha256"],
        "BOOT_ORIGINAL_OPERATION_MISMATCH",
    )
    prepared_event = _event(
        prepared_original,
        binding=i["binding"],
        phase_id=i["phase_id"],
        kind="PREPARED",
        previous=V2StageState.WAITING_OPERATOR,
        state=V2StageState.REVIEW_PENDING,
        references=_refs(operator_ref, enrollment_ref, prep_ref, operation_ref),
    )
    reviewed = snapshot.committed_events[-1]
    _need(
        prepared_event.sequence == start.sequence + 1
        and prepared_event.previous_event_sha256 == start.event_sha256
        and reviewed.sequence == prepared_event.sequence + 1
        and reviewed.previous_event_sha256 == prepared_event.event_sha256
        and ad["context"]["finished_at_utc_ns"]
        <= terminal.occurred_at_ns
        <= start.occurred_at_ns
        and prepared_event.occurred_at_ns >= pd["prepared_at_utc_ns"],
        "BOOT_ORIGINAL_PREPARATION_EVENT_REQUIRED",
    )
    verify_usb_reconnect_preparation(
        prep.payload,
        expected_sha256=prep.sha256,
        original_baseline=dict(
            plan=plan,
            plan_reference=plan_ref,
            declaration_event=declaration,
            baseline=baseline,
            baseline_reference=baseline_ref,
            baseline_sources=baseline_sources,
        ),
        absence=absence,
        absence_sources=sources,
        absence_reference=absence_ref,
        phase_start_event=start,
        phase_id=i["phase_id"],
        operator_event=report,
        operator_event_reference=operator_ref,
        enrollment=enrollment,
        enrollment_reference=enrollment_ref,
    )
    _need(
        pd["plan_reference"] == plan_ref.to_dict(),
        "BOOT_ORIGINAL_PLAN_REFERENCE_MISMATCH",
    )
    return prep, HostBootObservation(sources["host_boot"]), operation_ref


def _reviewed_originals(
    tx: M1PhysicalCameraTransaction,
    intent: UsbReconnectBootIntent,
    intent_ref: EvidenceReference,
    preparation: UsbReconnectPreparation,
    operation_reference: EvidenceReference,
    reviewed: V2JournalEvent,
) -> None:
    """Eight exact originals, including the operation and fixed boot request."""
    i, pd = intent.to_dict(), preparation.to_dict()
    known = (
        intent_ref,
        operation_reference,
        *(
            _manifest(i[key], maximum=USB_RECONNECT_ROLE_BYTES[key])
            for key in ("operator_event", "enrollment", "preparation")
        ),
    )
    _refs(*known)
    _need(
        len(reviewed.evidence) == 8 and all(ref in reviewed.evidence for ref in known),
        "EXACT_EIGHT_REVIEWED_BOOT_ROLES_REQUIRED",
    )
    extras: dict[str, tuple[EvidenceReference, bytes]] = {}
    schemas = {
        "rocell.usb_identity_stage_policy_review.v1": "policy_review",
        "rocell.usb_identity_runtime_review.v1": "runtime_review",
        "rocell.usb_identity_admission_identity.v1": "identity",
    }
    for ref in reviewed.evidence:
        if ref in known:
            continue
        raw = _read(tx, ref, 16 * 1024)
        schema = qualification._load(raw, 16 * 1024).get("schema")
        _need(
            type(schema) is str and schema in schemas and schemas[schema] not in extras,
            "EXACT_REVIEWED_BOOT_SUBJECT_REQUIRED",
        )
        extras[schemas[schema]] = (ref, raw)
    policy = UsbIdentityPolicyReview(extras["policy_review"][1])
    runtime_review = UsbIdentityRuntimeReview(extras["runtime_review"][1])
    identity = UsbIdentityAdmissionIdentity(extras["identity"][1])
    p, r, identity_data = policy.to_dict(), runtime_review.to_dict(), identity.to_dict()
    _need(
        all(
            p[key] == i["binding"][key]
            for key in ("cell_id", "session_id", "header_sha256", "source_sha256")
        )
        and p["operator_id"] == r["operator_id"] == i["operator_id"]
        and p["reviewer_id"] == r["reviewer_id"]
        and r["launch_session_id"] == i["launch_session_id"]
        and i["prepared_at_utc_ns"]
        <= p["reviewed_at_utc_ns"]
        <= reviewed.occurred_at_ns
        and i["prepared_at_utc_ns"] <= r["reviewed_at_ns"] <= reviewed.occurred_at_ns,
        "RECONNECT_BOOT_REVIEW_CONTEXT_MISMATCH",
    )
    enrollment_ref = _manifest(
        i["enrollment"], maximum=USB_RECONNECT_ROLE_BYTES["enrollment"]
    )
    expected_subjects = [
        dict(role=role, document_sha256=ref.payload_sha256, reference=ref.to_dict())
        for role, ref in (
            ("metadata", enrollment_ref),
            ("policy_review", extras["policy_review"][0]),
            ("runtime_review", extras["runtime_review"][0]),
        )
    ]
    _need(
        identity_data["original_subjects"] == expected_subjects
        and identity_data["policy_review_sha256"] == policy.sha256
        and p["policy_sha256"] == pd["operation"]["policy_sha256"],
        "RECONNECT_BOOT_REVIEW_ORIGINALS_MISMATCH",
    )
    PhysicalUsbIdentityCampaign(
        UsbIdentityOperation(canonical(pd["operation"])),
        identity=identity,
        review=runtime_review,
    )


class OriginalUsbReconnectBootCollector:
    """One original-reviewed scope. No callable executor, script or argv override."""

    def __init__(self, workspace: Path, intent: UsbReconnectBootIntent):
        _need(
            isinstance(workspace, Path)
            and workspace.is_absolute()
            and type(intent) is UsbReconnectBootIntent,
            "EXACT_RECONNECT_BOOT_COLLECTOR_REQUIRED",
        )
        self._workspace, self._intent = workspace, UsbReconnectBootIntent(
            intent.payload
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
        cancellation: Event,
        deadline_ns: int,
        revalidate_context: Callable[[], None],
    ) -> dict[str, Any]:
        _need(
            type(tx) is M1PhysicalCameraTransaction
            and type(intent_reference) is EvidenceReference
            and isinstance(cancellation, Event)
            and type(deadline_ns) is int
            and callable(revalidate_context),
            "EXACT_RECONNECT_BOOT_COLLECTION_SCOPE",
        )
        with self._lock:
            _need(not self._used, "RECONNECT_BOOT_COLLECTOR_ALREADY_USED")
            self._used = True
        i = self._intent.to_dict()
        b, phase_id = i["binding"], i["phase_id"]

        def check() -> None:
            _need(
                not cancellation.is_set() and monotonic_ns() < deadline_ns,
                "BOOT_ACTION_INTERRUPTED",
            )
            result: Any = revalidate_context()  # type: ignore[func-returns-value]
            _need(result is None, "BOOT_CONTEXT_GUARD_REQUIRED")
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
                    snapshot.state_for(stage) is V2StageState.PASS
                    for stage in STAGE_ORDER[:3]
                )
                and all(
                    snapshot.state_for(stage) is V2StageState.PENDING
                    for stage in STAGE_ORDER[4:]
                ),
                "BOOT_EXACT_ORIGINAL_STAGE_SCOPE_REQUIRED",
            )

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
            kind="REVIEWED",
            previous=V2StageState.REVIEW_PENDING,
            state=V2StageState.BLOCKED,
            references=snap.committed_events[-1].evidence,
        )
        _subject_manifest(self._intent, intent_reference)
        _need(
            _read(tx, intent_reference, MAX_INTENT_BYTES) == self._intent.payload,
            "BOOT_ORIGINAL_INTENT_CHANGED",
        )
        preparation, absence_boot, operation_ref = _original_preparation(
            tx, self._intent, snap
        )
        _need(
            Path(preparation.to_dict()["operation"]["workspace"]) == self._workspace,
            "BOOT_ORIGINAL_WORKSPACE_CHANGED",
        )
        _reviewed_originals(
            tx, self._intent, intent_reference, preparation, operation_ref, reviewed
        )
        check()
        current = tx.snapshot()
        scope(current)
        _need(
            current.head.head_sha256 == snap.head.head_sha256
            and current.committed_events[-1] == reviewed,
            "BOOT_ORIGINAL_HEAD_CHANGED",
        )
        requested = tx.commit_stage_state(
            _STAGE,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=time_ns(),
            detail_code=usb_reconnect_event("BOOT_REQUESTED", phase_id),
            expected_head_sha256=snap.head.head_sha256,
            evidence=(intent_reference,),
        )
        event = requested.committed_events[-1]
        self._diagnostics.update(state="REQUESTED", requested_event=event.to_dict())
        check()  # A crash/Stop here leaves the original request, never a retry.
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
        verify_usb_reconnect_boot_observation(
            report,
            intent=self._intent,
            expected_sha256=report.sha256,
            requested_event=event,
        )
        self._diagnostics["boot_comparison"] = compare_boot_observations(
            absence_boot, report
        )
        try:
            admit()
            context_current = True
        except Exception:
            context_current = False
        self._diagnostics["context_current"] = context_current
        # Completed/uncertain effects are retained even after Stop or context
        # loss. Original head/lease protection still applies to every write.
        ref = tx.store_evidence(
            _STAGE,
            report.payload,
            label=usb_reconnect_label("host_boot", phase_id),
            media_type="application/json",
            captured_at_ns=time_ns(),
            expected_head_sha256=requested.head.head_sha256,
        )
        record.update(
            reference=ref.to_dict(), retention="M1_PUBLISHED_READBACK_PENDING"
        )
        _need(
            _read(tx, ref, MAX_HOST_BOOT_BYTES) == report.payload,
            "BOOT_ORIGINAL_REPORT_CHANGED",
        )
        record["retention"] = "M1_FULL_BYTES_READ_BACK"
        try:
            admit()
        except Exception:
            context_current = False  # Monotone: a later success cannot erase loss.
        self._diagnostics["context_current"] = context_current
        terminal = _terminal(report, absence_boot)
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
            detail_code=usb_reconnect_event(terminal, phase_id),
            expected_head_sha256=requested.head.head_sha256,
            evidence=_refs(intent_reference, ref),
        )
        self._diagnostics.update(
            state=terminal, terminal_event=finished.committed_events[-1].to_dict()
        )
        return deepcopy(record)
