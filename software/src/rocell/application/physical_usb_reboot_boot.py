"""Post-reboot boot scopes and one-shot original-owned boot collection.

These bytes describe the independently reviewed boot step that must precede
the fourth USB query. They are not an executable ticket. The future original
collector authenticates the complete v12 predecessor, current preparation,
reviews and one-use request under leases before using the fixed host observer.
Neither loading an intent nor classifying a report authenticates that storage.

Cross-boot comparisons use UTC only. A new monotonic epoch is expected and
remains subject to the host observer's existing local deadline/cleanup checks.
"""

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock
from time import monotonic_ns, time_ns
from typing import Any, Callable

from . import physical_camera_usb_qualification as qualification
from .physical_camera_usb_reboot import (
    UsbRebootPreparation,
    verify_usb_reboot_preparation,
)
from .physical_camera_usb_reboot_constants import (
    USB_REBOOT_ROLE_BYTES,
    SOURCE_WORKFLOW_USB_REBOOT_SCHEMA,
    usb_reboot_event,
    usb_reboot_label,
)
from .commissioning_camera_persistence import (
    M1PhysicalCameraTransaction,
    physical_camera_source_binding,
)
from .physical_onboarding_leases import LeaseLevel, LeaseSpec
from .wizard_diagnostic_coordinator import source_fingerprint
from .physical_onboarding import (
    EvidenceReference,
    STAGE_ORDER,
    _parse_evidence_reference,
)
from .physical_onboarding_v2 import V2JournalEvent, V2StageState, _parse_event
from .physical_usb_presence_binding import _manifest, _subject_manifest
from .physical_usb_reboot_phase import FLAGS, UsbRebootOperatorEvent, _phase_id
from .physical_usb_reconnect_phase import (
    PHASE_LIMIT as RECONNECT_LIMIT,
    UsbReconnectQualificationPhase,
)
from .physical_usb_trial_boot import _terminal as boot_terminal
from rocell.providers.windows.host_boot_observation import (
    HostBootObservation,
    HostBootRequest,
    WindowsHostBootObserver,
    SCRIPT_SHA256,
    _utc_ns,
    compare_boot_observations,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest

SCHEMA = INTENT_SCHEMA = "rocell.usb_reboot_boot_intent.v1"
MAX_INTENT_BYTES = 16 * 1024
MAX_HOST_BOOT_BYTES = 32 * 1024
PHASE = "AFTER_REBOOT"
_STAGE = STAGE_ORDER[3]
_BUDGET = dict(admission_window_ms=30000, process_run_ms=10000, cleanup_ms=2000)
_FLAGS = dict(**FLAGS, arm_access_authorized=False, automatic_replay=False)
_FIELDS = {
    "schema",
    "binding",
    "plan_sha256",
    "plan_reference",
    "baseline_sha256",
    "absence_sha256",
    "reconnect_sha256",
    "reconnect_reference",
    "reconnect_finished_at_utc_ns",
    "reconnect_host_boot",
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


class UsbRebootBootError(ValueError):
    """Closed report/scope mismatch, without echoing original diagnostic data."""


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise UsbRebootBootError(code)


def _refs(*references: EvidenceReference) -> tuple[EvidenceReference, ...]:
    _need(
        all(type(ref) is EvidenceReference for ref in references)
        and len({ref.evidence_id for ref in references}) == len(references),
        "DISTINCT_REBOOT_BOOT_ORIGINALS_REQUIRED",
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
        and event.detail_code == usb_reboot_event(kind, phase_id)
        and event.evidence == _refs(*references),
        "REBOOT_BOOT_ORIGINAL_EVENT_MISMATCH",
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
        for key in (
            "plan_sha256",
            "baseline_sha256",
            "absence_sha256",
            "reconnect_sha256",
            "operation_sha256",
        ):
            qualification._sha(d[key])
        _need(
            d["schema"] == SCHEMA
            and d["phase"] == PHASE
            and d["script_sha256"] == SCRIPT_SHA256
            and canonical(d["budget"]) == canonical(_BUDGET)
            and all(d[key] is False for key in _FLAGS),
            "REBOOT_BOOT_POLICY_CHANGED",
        )
        plan = qualification._reference(d["plan_reference"])
        reconnect = qualification._reference(d["reconnect_reference"])
        _need(
            plan.payload_sha256 == d["plan_sha256"]
            and 0 < plan.payload_bytes <= qualification.UsbQualificationPlan.limit
            and reconnect.payload_sha256 == d["reconnect_sha256"]
            and 0 < reconnect.payload_bytes <= RECONNECT_LIMIT,
            "REBOOT_BOOT_PREDECESSOR_REFERENCE_MISMATCH",
        )
        refs = [
            plan,
            reconnect,
            _manifest(d["reconnect_host_boot"], maximum=MAX_HOST_BOOT_BYTES),
        ]
        for role in ("preparation", "operator_event", "enrollment"):
            refs.append(_manifest(d[role], maximum=USB_REBOOT_ROLE_BYTES[role]))
        _refs(*refs)
        qualification._integer(d["reconnect_finished_at_utc_ns"], 1)
        # A restart epoch must fit strictly after reconnect and at/before Begin.
        qualification._integer(
            d["phase_started_at_utc_ns"], d["reconnect_finished_at_utc_ns"] + 1
        )
        qualification._integer(d["reported_at_utc_ns"], d["phase_started_at_utc_ns"])
        qualification._integer(d["prepared_at_utc_ns"], d["reported_at_utc_ns"])
        start = _event(
            d["phase_start_event"],
            binding=d["binding"],
            phase_id=d["phase_id"],
            kind="PREPARATION_REQUESTED",
            previous=V2StageState.BLOCKED,
            state=V2StageState.WAITING_OPERATOR,
            references=(reconnect,),
        )
        _need(
            start.occurred_at_ns == d["phase_started_at_utc_ns"],
            "REBOOT_BOOT_START_TIME_MISMATCH",
        )
        return d
    except UsbRebootBootError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise UsbRebootBootError("INVALID_REBOOT_BOOT_INTENT") from exc


@dataclass(frozen=True, slots=True)
class UsbRebootBootIntent:
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
            schema="rocell.usb_reboot_boot_intent_summary.v1",
            sha256=self.sha256,
            phase=PHASE,
            phase_id=d["phase_id"],
            status="DECLARED_BOOT_SCOPE_NOT_EXECUTABLE",
            reconnect_sha256=d["reconnect_sha256"],
            required_relation="SAME_HOST_DIFFERENT_BOOT",
            **_FLAGS,
        )


def build_usb_reboot_boot_intent(
    *,
    preparation: UsbRebootPreparation,
    preparation_reference: EvidenceReference,
    reconnect: UsbReconnectQualificationPhase,
    reconnect_reference: EvidenceReference,
) -> UsbRebootBootIntent:
    """Bind retained subjects, not their original-store authenticity.

    The original owner must first reconstruct the full predecessor and
    preparation from independent original sources, including the old permit.
    This builder never substitutes a status or self-hash for that operation.
    """
    _need(
        type(preparation) is UsbRebootPreparation
        and type(preparation_reference) is EvidenceReference
        and type(reconnect) is UsbReconnectQualificationPhase
        and type(reconnect_reference) is EvidenceReference,
        "EXACT_REBOOT_BOOT_PREPARATION_REQUIRED",
    )
    preparation = UsbRebootPreparation(preparation.payload)
    reconnect = UsbReconnectQualificationPhase(reconnect.payload)
    d, old = preparation.to_dict(), reconnect.to_dict()
    report = UsbRebootOperatorEvent(canonical(d["operator_event"]))
    r = report.to_dict()
    _subject_manifest(reconnect, reconnect_reference)
    _need(
        old["status"] == "RECONNECT_OBSERVATIONS_RETAINED"
        and old["missing_requirements"] == []
        and d["reconnect_sha256"] == reconnect.sha256
        and d["reconnect_reference"] == reconnect_reference.to_dict()
        and old["plan_sha256"] == d["plan_sha256"]
        and old["baseline_sha256"] == d["baseline_sha256"]
        and old["predecessor_sha256"] == d["absence_sha256"]
        and old["context"]["launch_session_id"] != r["launch_session_id"]
        and old["context"]["operation_id"] != d["phase_id"],
        "REBOOT_BOOT_EXACT_RECONNECT_REQUIRED",
    )
    previous_boot = next(row for row in old["records"] if row["role"] == "host_boot")
    enrollment_ref = qualification._reference(d["enrollment_reference"])
    return UsbRebootBootIntent(
        canonical(
            dict(
                schema=SCHEMA,
                binding=r["binding"],
                plan_sha256=d["plan_sha256"],
                plan_reference=d["plan_reference"],
                baseline_sha256=d["baseline_sha256"],
                absence_sha256=d["absence_sha256"],
                reconnect_sha256=reconnect.sha256,
                reconnect_reference=reconnect_reference.to_dict(),
                reconnect_finished_at_utc_ns=old["context"]["finished_at_utc_ns"],
                reconnect_host_boot={
                    key: previous_boot[key]
                    for key in ("sha256", "payload_bytes", "reference")
                },
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


def verify_usb_reboot_boot_intent(
    value: Any,
    *,
    expected_sha256: str,
    preparation: UsbRebootPreparation,
    preparation_reference: EvidenceReference,
    reconnect: UsbReconnectQualificationPhase,
    reconnect_reference: EvidenceReference,
) -> UsbRebootBootIntent:
    qualification._sha(expected_sha256)
    current = UsbRebootBootIntent(
        value.payload if type(value) is UsbRebootBootIntent else value
    )
    expected = build_usb_reboot_boot_intent(
        preparation=preparation,
        preparation_reference=preparation_reference,
        reconnect=reconnect,
        reconnect_reference=reconnect_reference,
    )
    _need(
        current.sha256 == expected_sha256 and current.payload == expected.payload,
        "REBOOT_BOOT_INTENT_RECONSTRUCTION_MISMATCH",
    )
    return current


def verify_usb_reboot_boot_observation(
    value: Any,
    *,
    intent: UsbRebootBootIntent,
    expected_sha256: str,
    requested_event: V2JournalEvent,
) -> HostBootObservation:
    """Join the exact request/report. Bad restart facts remain retainable data."""
    _need(
        type(intent) is UsbRebootBootIntent and type(requested_event) is V2JournalEvent,
        "EXACT_REBOOT_BOOT_OBSERVATION_INPUTS",
    )
    qualification._sha(expected_sha256)
    intent = UsbRebootBootIntent(intent.payload)
    i = intent.to_dict()
    event = _parse_event(requested_event.to_dict())
    _need(len(event.evidence) == 1, "EXACT_REBOOT_BOOT_INTENT_REFERENCE_REQUIRED")
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
        "REBOOT_BOOT_OBSERVATION_INTENT_MISMATCH",
    )
    return report


def classify_usb_reboot_boot_observation(
    value: Any,
    *,
    intent: UsbRebootBootIntent,
    expected_sha256: str,
    requested_event: V2JournalEvent,
    reconnect_boot: HostBootObservation,
) -> str:
    """A derived terminal label, never permission to perform the next USB query.

    Uncertain cleanup cannot be downgraded by a wrong boot relation. The later
    collector retains the full returned report and commits this outcome before
    any separate query action; no automatic query belongs in this classifier.
    """
    report = verify_usb_reboot_boot_observation(
        value,
        intent=intent,
        expected_sha256=expected_sha256,
        requested_event=requested_event,
    )
    _need(type(reconnect_boot) is HostBootObservation, "EXACT_RECONNECT_BOOT_REQUIRED")
    reconnect_boot = HostBootObservation(reconnect_boot.payload)
    i = intent.to_dict()
    previous_ref = _manifest(i["reconnect_host_boot"], maximum=MAX_HOST_BOOT_BYTES)
    _subject_manifest(reconnect_boot, previous_ref)
    status = boot_terminal(report)
    if status != "BOOT_RETAINED":
        return status
    before, after = reconnect_boot.to_dict(), report.to_dict()
    # HostBootObservation validates response time syntax and confirmations.
    # Its comparison alone bounds the new epoch after the earlier boot report,
    # not after the later reconnect USB completion. Enforce that stronger bound.
    response = after["response"]
    epoch = None if response is None else _utc_ns(response["last_boot_up_time_utc"])
    valid_restart = (
        boot_terminal(reconnect_boot) == "BOOT_RETAINED"
        and compare_boot_observations(reconnect_boot, report)["status"]
        == "SAME_HOST_DIFFERENT_BOOT"
        and before["execution"]["finished_utc_ns"] <= i["reconnect_finished_at_utc_ns"]
        and epoch is not None
        and i["reconnect_finished_at_utc_ns"] < epoch <= i["phase_started_at_utc_ns"]
    )
    return "BOOT_RETAINED" if valid_restart else "BOOT_HELD"


def read_usb_reboot_boot_originals(
    tx: M1PhysicalCameraTransaction,
    *,
    workspace: Path,
    source_sha256: str,
    launch_session_id: str,
    expected_header_sha256: str,
    cancellation: Event,
    deadline_ns: int,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    """Fixed same-transaction reader; never a caller cache or injected verifier.

    Import lazily because the original reader also uses these pure boot codecs.
    The reader authenticates every package and the complete sibling campaign
    family, including the independently retained historical descriptor permit.
    """
    from .physical_camera_session import read_usb_reboot_boot_originals as read

    return read(
        tx,
        workspace=workspace,
        source_sha256=source_sha256,
        launch_session_id=launch_session_id,
        expected_header_sha256=expected_header_sha256,
        cancellation=cancellation,
        deadline_ns=deadline_ns,
    )


def _read(
    tx: M1PhysicalCameraTransaction, ref: EvidenceReference, maximum: int
) -> bytes:
    ref = qualification._reference(ref)
    _need(0 < ref.payload_bytes <= maximum, "REBOOT_BOOT_ORIGINAL_BYTES_LIMIT")
    raw = tx.read_stage_evidence(ref)
    qualification._reference(ref, raw)
    return raw


def _inventory(snapshot: Any) -> tuple[bytes, ...]:
    """Compare the full audit, including prior stages and uncommitted additions.

    The authenticated snapshot contains source, design and receipt evidence as
    well as stage-4 USB records. Parse every reference without filtering those
    earlier stages out. Individual boot-role reads still use the stage-4-only
    validator in _read; full inventory membership is a different boundary.
    """
    refs = tuple(
        _parse_evidence_reference(
            ref.to_dict() if type(ref) is EvidenceReference else ref
        )
        for ref in snapshot.evidence
    )
    _need(
        len({ref.evidence_id for ref in refs}) == len(refs),
        "REBOOT_BOOT_ORIGINAL_INVENTORY_CHANGED",
    )
    return tuple(sorted(canonical(ref.to_dict()) for ref in refs))


def _checked_originals(
    tx: M1PhysicalCameraTransaction,
    intent: UsbRebootBootIntent,
    intent_reference: EvidenceReference,
    snapshot: Any,
    workflow: dict[str, Any],
    predecessor: dict[str, Any],
) -> tuple[UsbRebootPreparation, HostBootObservation]:
    """Rebuild the fixed reader's result and reread the exact reviewed originals."""
    i = intent.to_dict()
    _need(
        type(workflow) is dict
        and workflow.get("schema") == SOURCE_WORKFLOW_USB_REBOOT_SCHEMA
        and type(predecessor) is dict
        and set(predecessor)
        == {
            "original_baseline",
            "received",
            "absence",
            "absence_reference",
            "absence_sources",
            "reconnect",
            "reconnect_reference",
            "reconnect_sources",
            "reconnect_permit",
        },
        "REBOOT_BOOT_AUTHENTICATED_ORIGINALS_REQUIRED",
    )
    phase = workflow["usb_qualification_reboot"]
    roles = tuple(USB_REBOOT_ROLE_BYTES)
    _need(
        phase["phase"] == PHASE
        and phase["phase_id"] == i["phase_id"]
        and phase["state"] == "REVIEWED"
        and phase["original_campaign"] is None
        and phase["original_campaign_event"] is None
        and all(phase[role] is not None for role in roles[:8])
        and all(phase[role] is None for role in roles[8:]),
        "REBOOT_BOOT_CURRENT_REVIEWED_ORIGINAL_REQUIRED",
    )
    refs: dict[str, EvidenceReference] = {}
    raw: dict[str, bytes] = {}
    for role in roles[:8]:
        record = phase[role]
        qualification._exact(
            record, {"document", "evidence_sha256", "reference", "retention"}
        )
        refs[role] = qualification._reference(record["reference"])
        raw[role] = _read(tx, refs[role], USB_REBOOT_ROLE_BYTES[role])
        _need(
            record["retention"] == "M1_FULL_BYTES_READ_BACK"
            and canonical(record["document"]) == raw[role]
            and record["evidence_sha256"] == digest(raw[role]),
            "REBOOT_BOOT_ORIGINAL_ROLE_CHANGED",
        )
    _refs(*refs.values())
    _need(
        refs["boot_request"] == intent_reference
        and raw["boot_request"] == intent.payload,
        "REBOOT_BOOT_ORIGINAL_INTENT_CHANGED",
    )
    start = _parse_event(i["phase_start_event"])
    original = predecessor["original_baseline"]
    declaration = _parse_event(original["declaration_event"].to_dict())
    events = snapshot.committed_events
    _need(
        len(events) >= 4 and start in events and declaration in events,
        "REBOOT_BOOT_ORIGINAL_PREDECESSOR_EVENTS_REQUIRED",
    )
    prepared, reviewed = events[-2:]
    _event(
        prepared,
        binding=i["binding"],
        phase_id=i["phase_id"],
        kind="PREPARED",
        previous=V2StageState.WAITING_OPERATOR,
        state=V2StageState.REVIEW_PENDING,
        references=_refs(*(refs[role] for role in roles[:4])),
    )
    _event(
        reviewed,
        binding=i["binding"],
        phase_id=i["phase_id"],
        kind="REVIEWED",
        previous=V2StageState.REVIEW_PENDING,
        state=V2StageState.BLOCKED,
        references=_refs(*(refs[role] for role in roles[:8])),
    )
    _need(
        phase["events"] == [event.to_dict() for event in (start, prepared, reviewed)]
        and prepared.sequence == start.sequence + 1
        and prepared.previous_event_sha256 == start.event_sha256
        and reviewed.sequence == prepared.sequence + 1
        and reviewed.previous_event_sha256 == prepared.event_sha256
        and declaration.sequence < start.sequence,
        "REBOOT_BOOT_ORIGINAL_PREPARATION_EVENT_REQUIRED",
    )
    reconnect = predecessor["reconnect"]
    reconnect_ref = predecessor["reconnect_reference"]
    reconnect_code = (
        "CAMERA_USB_TRIAL_RECONNECT_RETAINED_"
        + reconnect.to_dict()["context"]["operation_id"][9:].upper()
    )
    terminals = [event for event in events if event.detail_code == reconnect_code]
    _need(
        len(terminals) == 1
        and terminals[0].stage is _STAGE
        and terminals[0].state is V2StageState.BLOCKED
        and terminals[0].previous_state is V2StageState.WAITING_OPERATOR
        and len(terminals[0].evidence) == 11
        and reconnect_ref in terminals[0].evidence
        and declaration.sequence < terminals[0].sequence < start.sequence
        and reconnect.to_dict()["context"]["finished_at_utc_ns"]
        <= terminals[0].occurred_at_ns
        <= start.occurred_at_ns,
        "REBOOT_BOOT_ORIGINAL_RECONNECT_TERMINAL_REQUIRED",
    )
    preparation = verify_usb_reboot_preparation(
        raw["preparation"],
        expected_sha256=digest(raw["preparation"]),
        **predecessor,
        phase_start_event=start,
        phase_id=i["phase_id"],
        operator_event=UsbRebootOperatorEvent(raw["operator_event"]),
        operator_event_reference=refs["operator_event"],
        enrollment=raw["enrollment"],
        enrollment_reference=refs["enrollment"],
    )
    pd = preparation.to_dict()
    _need(
        raw["operation"] == canonical(pd["operation"])
        and pd["prepared_at_utc_ns"]
        <= prepared.occurred_at_ns
        <= reviewed.occurred_at_ns,
        "REBOOT_BOOT_ORIGINAL_OPERATION_CHANGED",
    )
    verify_usb_reboot_boot_intent(
        intent,
        expected_sha256=intent.sha256,
        preparation=preparation,
        preparation_reference=refs["preparation"],
        reconnect=reconnect,
        reconnect_reference=reconnect_ref,
    )
    boot_ref = _manifest(i["reconnect_host_boot"], maximum=MAX_HOST_BOOT_BYTES)
    previous_boot = _read(tx, boot_ref, MAX_HOST_BOOT_BYTES)
    _need(
        previous_boot == predecessor["reconnect_sources"]["host_boot"],
        "REBOOT_BOOT_ORIGINAL_RECONNECT_BOOT_CHANGED",
    )
    # The fixed full reader verifies policy/runtime/identity reviews and original
    # membership. Repeat the substantive three-way review join over reread bytes.
    # Do not route through the reconnect intent schema: use the phase-neutral
    # campaign codec directly with this reboot operation.
    from .physical_usb_identity_campaign import (
        PhysicalUsbIdentityCampaign,
        UsbIdentityOperation,
    )
    from .usb_identity_stage_policy import (
        UsbIdentityPolicyReview,
        UsbIdentityAdmissionIdentity,
    )
    from rocell.providers.windows.usb_identity_registration import (
        UsbIdentityRuntimeReview,
    )

    policy = UsbIdentityPolicyReview(raw["policy_review"])
    review = UsbIdentityRuntimeReview(raw["runtime_review"])
    identity = UsbIdentityAdmissionIdentity(raw["identity"])
    p, r, d = policy.to_dict(), review.to_dict(), identity.to_dict()
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
        and i["prepared_at_utc_ns"] <= r["reviewed_at_ns"] <= reviewed.occurred_at_ns
        and p["policy_sha256"] == pd["operation"]["policy_sha256"]
        and d["policy_review_sha256"] == policy.sha256
        and d["original_subjects"]
        == [
            dict(role=role, document_sha256=ref.payload_sha256, reference=ref.to_dict())
            for role, ref in (
                ("metadata", refs["enrollment"]),
                ("policy_review", refs["policy_review"]),
                ("runtime_review", refs["runtime_review"]),
            )
        ],
        "REBOOT_BOOT_REVIEW_ORIGINALS_MISMATCH",
    )
    PhysicalUsbIdentityCampaign(
        UsbIdentityOperation(raw["operation"]), identity=identity, review=review
    )
    return preparation, HostBootObservation(previous_boot)


class OriginalUsbRebootBootCollector:
    """One original-reviewed boot observation; no command or executor override."""

    def __init__(self, workspace: Path, intent: UsbRebootBootIntent):
        _need(
            isinstance(workspace, Path)
            and workspace.is_absolute()
            and type(intent) is UsbRebootBootIntent,
            "EXACT_REBOOT_BOOT_COLLECTOR_REQUIRED",
        )
        self._workspace, self._intent = workspace, UsbRebootBootIntent(intent.payload)
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
            "EXACT_REBOOT_BOOT_COLLECTION_SCOPE",
        )
        with self._lock:
            _need(not self._used, "REBOOT_BOOT_COLLECTOR_ALREADY_USED")
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
        initial = tx.snapshot()
        scope(initial)
        _need(
            initial.state_for(_STAGE) is V2StageState.BLOCKED
            and bool(initial.committed_events),
            "REBOOT_BOOT_CURRENT_REVIEWED_ORIGINAL_REQUIRED",
        )
        snap, workflow, predecessor = read_usb_reboot_boot_originals(
            tx,
            workspace=self._workspace,
            source_sha256=b["source_sha256"],
            launch_session_id=i["launch_session_id"],
            expected_header_sha256=b["header_sha256"],
            cancellation=cancellation,
            deadline_ns=deadline_ns,
        )
        scope(snap)
        _need(
            snap.head.head_sha256 == initial.head.head_sha256
            and snap.committed_events == initial.committed_events
            and _inventory(snap) == _inventory(initial),
            "BOOT_ORIGINAL_HEAD_CHANGED",
        )
        preparation, reconnect_boot = _checked_originals(
            tx, self._intent, intent_reference, snap, workflow, predecessor
        )
        _need(
            Path(preparation.to_dict()["operation"]["workspace"]) == self._workspace,
            "BOOT_ORIGINAL_WORKSPACE_CHANGED",
        )
        check()
        current = tx.snapshot()
        scope(current)
        _need(
            current.head.head_sha256 == snap.head.head_sha256
            and current.committed_events == snap.committed_events
            and _inventory(current) == _inventory(snap),
            "BOOT_ORIGINAL_HEAD_CHANGED",
        )
        requested = tx.commit_stage_state(
            _STAGE,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=time_ns(),
            detail_code=usb_reboot_event("BOOT_REQUESTED", phase_id),
            expected_head_sha256=snap.head.head_sha256,
            evidence=(intent_reference,),
        )
        event = requested.committed_events[-1]
        self._diagnostics.update(state="REQUESTED", requested_event=event.to_dict())
        check()  # This durable request is never replayed, even if Stop follows.
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
        expected_inventory = _inventory(requested)

        def admit() -> None:
            check()
            current = tx.snapshot()
            scope(current)
            _need(
                current.head.head_sha256 == requested.head.head_sha256
                and current.committed_events[-1] == event
                and current.state_for(_STAGE) is V2StageState.WAITING_OPERATOR
                and _inventory(current) == expected_inventory
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
        verify_usb_reboot_boot_observation(
            report,
            intent=self._intent,
            expected_sha256=report.sha256,
            requested_event=event,
        )
        self._diagnostics["boot_comparison"] = compare_boot_observations(
            reconnect_boot, report
        )
        try:
            admit()
            context_current = True
        except Exception:
            context_current = False
        self._diagnostics["context_current"] = context_current
        # Stop/source loss cannot erase returned bytes. Head and lease checks
        # still protect writes. Retention itself does not advance the journal.
        ref = tx.store_evidence(
            _STAGE,
            report.payload,
            label=usb_reboot_label("host_boot", phase_id),
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
        expected_inventory = tuple(
            sorted((*expected_inventory, canonical(ref.to_dict())))
        )
        try:
            admit()
        except Exception:
            context_current = False  # A later success never repairs earlier loss.
        self._diagnostics["context_current"] = context_current
        terminal = classify_usb_reboot_boot_observation(
            report,
            intent=self._intent,
            expected_sha256=report.sha256,
            requested_event=event,
            reconnect_boot=reconnect_boot,
        )
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
            detail_code=usb_reboot_event(terminal, phase_id),
            expected_head_sha256=requested.head.head_sha256,
            evidence=_refs(intent_reference, ref),
        )
        self._diagnostics.update(
            state=terminal, terminal_event=finished.committed_events[-1].to_dict()
        )
        return deepcopy(record)
