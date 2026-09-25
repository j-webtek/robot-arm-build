"""Qualified rehearsal persistence and closed shared M1 storage mechanics.

This adapter uses the actual M1 NTFS publisher, ordered OS leases, V2 journal,
attempt ledger and quarantine ledger. It does not provide a hardware worker.
An immutable REHEARSAL header and domain-separated source binding prevent its
synthetic observations from being mislabeled as physical diagnostic evidence.
The separate physical preflight facade uses its own immutable domain; the
legacy public adapter and retained-permit decoder remain rehearsal-only.

Stage predicates and assessments belong to the reviewed application service.
The facts callback is server composition, not browser data: it must obtain
hazard/epoch/identity documents from verified sources and retained evidence.
This adapter freezes/hashes those documents; every authoritative store head,
source hash, stage state and qualification hash is read from actual M1 state.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, fields, replace
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any, TYPE_CHECKING

from rocell.application.cell_commissioning_coordinator import (
    AdmissionSnapshot,
    AttemptResult,
    CampaignBudget,
    CampaignEvidence,
    CampaignRegistration,
    CommissioningMode,
    EnergizationEnvelope,
    ObservedPowerState,
    ExactOperationPermit,
    INCAPABLE_COMPOSITION,
    PHYSICAL_DIAGNOSTIC_COMPOSITION,
    PHYSICAL_CAMERA_COMPOSITION,
    PHYSICAL_USB_IDENTITY_COMPOSITION,
    PHYSICAL_USB_PRESENCE_COMPOSITION,
    USB_IDENTITY_ACTION_ID,
    USB_PRESENCE_ACTION_ID,
    UsbIdentityAdmissionSnapshot,
    UsbPresenceAdmissionSnapshot,
    MAX_PERMIT_TTL_NS,
    MAX_RETAINED_CAMPAIGN_BYTES,
    RegisteredActionRequest,
    WorkerReceipt,
    validate_campaign_evidence,
)
from rocell.application.physical_onboarding import (
    EvidenceReference,
    PhysicalOnboardingStage,
    STAGE_PLAN_SHA256,
)
from rocell.application.physical_onboarding_attempts import (
    AttemptBinding,
    AttemptState,
    PhysicalOnboardingAttemptLedger,
    canonical_json_bytes,
    parse_canonical_json,
)
from rocell.application.physical_onboarding_durability import (
    canonical_sha256,
    contained_path,
    safe_root,
)
from rocell.application.physical_onboarding_leases import (
    HeldLeaseSet,
    LeaseLevel,
    LeaseSpec,
)
from rocell.application.physical_onboarding_quarantine import (
    PhysicalOnboardingQuarantineLedger,
)
from rocell.application.physical_onboarding_storage import (
    QualifiedWindowsOnboardingPublication,
)
from rocell.application.physical_onboarding_v2 import (
    PhysicalOnboardingV2Session,
    V2SessionSnapshot,
    V2StageState,
)
from rocell.safety.effects import EffectCertainty, EffectClass

if TYPE_CHECKING:
    from .camera_activation_campaign_evidence import CameraActivationArtifact
    from .camera_activation_evidence_parts import CameraEvidenceParts
    from .camera_sealed_capture_evidence import SealedCameraCaptureEvidence, SealedCaptureParts
    from rocell.application.physical_onboarding_m1 import (
        PhysicalOnboardingM1Runtime,
        M1RuntimeVerification,
    )


REHEARSAL_SOURCE_SCHEMA = "rocell.rehearsal_source.v1"
RECORD_SCHEMA = "rocell.m1_rehearsal_record.v1"
MAX_RECORD_BYTES = 1024 * 1024
MAX_RECORDS = 2048
MAX_RECORD_TOTAL_BYTES = 32 * 1024 * 1024
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_CELL = re.compile(r"wizard-rehearsal-[0-9a-f]{16}\Z")
_SESSION = re.compile(r"rehearsal-[0-9a-f]{32}\Z")
_RECORD = re.compile(
    r"(?:request-[0-9a-f]{64}|(?:receipt|result)-attempt-[0-9a-f]{32}-[a-z_]+|evidence-attempt-[0-9a-f]{32}-retained)\.json\Z"
)


@dataclass(frozen=True, slots=True)
class _PersistenceDomain:
    """Closed storage policies, never a caller-controlled activation switch."""

    mode: CommissioningMode
    composition: str
    record_schema: str
    record_directory: str
    cell_pattern: str
    session_pattern: str


_REHEARSAL_DOMAIN = _PersistenceDomain(
    CommissioningMode.REHEARSAL,
    INCAPABLE_COMPOSITION,
    RECORD_SCHEMA,
    "rehearsal-records",
    r"wizard-rehearsal-[0-9a-f]{16}",
    r"rehearsal-[0-9a-f]{32}",
)
_PHYSICAL_NO_IO_DOMAIN = _PersistenceDomain(
    CommissioningMode.PHYSICAL_DIAGNOSTIC,
    PHYSICAL_DIAGNOSTIC_COMPOSITION,
    "rocell.m1_physical_diagnostic_record.v1",
    "physical-diagnostic-records",
    r"wizard-physical-diagnostic-[0-9a-f]{16}",
    r"physical-diagnostic-[0-9a-f]{32}",
)
_PHYSICAL_CAMERA_DOMAIN = _PersistenceDomain(
    CommissioningMode.PHYSICAL_DIAGNOSTIC,
    PHYSICAL_CAMERA_COMPOSITION,
    "rocell.m1_physical_camera_record.v1",
    "physical-camera-records",
    r"wizard-physical-camera-[0-9a-f]{16}",
    r"physical-camera-[0-9a-f]{32}",
)
_PHYSICAL_USB_IDENTITY_DOMAIN = _PersistenceDomain(
    CommissioningMode.PHYSICAL_DIAGNOSTIC,
    PHYSICAL_USB_IDENTITY_COMPOSITION,
    "rocell.m1_physical_usb_identity_record.v1",
    "physical-usb-identity-records",
    r"wizard-physical-camera-[0-9a-f]{16}",
    r"physical-camera-[0-9a-f]{32}",
)
_PHYSICAL_USB_PRESENCE_DOMAIN = _PersistenceDomain(
    CommissioningMode.PHYSICAL_DIAGNOSTIC,
    PHYSICAL_USB_PRESENCE_COMPOSITION,
    "rocell.m1_physical_usb_presence_record.v1",
    "physical-usb-presence-records",
    r"wizard-physical-camera-[0-9a-f]{16}",
    r"physical-camera-[0-9a-f]{32}",
)
_CAMERA_FAMILY = (
    _PHYSICAL_CAMERA_DOMAIN,
    _PHYSICAL_USB_IDENTITY_DOMAIN,
    _PHYSICAL_USB_PRESENCE_DOMAIN,
)


def _registered_domain(domain: _PersistenceDomain) -> bool:
    # Identity comparison prevents a caller-constructed lookalike policy from
    # weakening a closed domain's effect or retention restrictions.
    return any(
        domain is item
        for item in (_REHEARSAL_DOMAIN, _PHYSICAL_NO_IO_DOMAIN, *_CAMERA_FAMILY)
    )


def _require_domain_permit(
    permit: ExactOperationPermit, domain: _PersistenceDomain
) -> None:
    if not _registered_domain(domain):
        raise M1CommissioningPersistenceError("unregistered persistence domain")
    if permit.admission.mode is not domain.mode:
        raise M1CommissioningPersistenceError(
            "permit belongs to another storage domain"
        )
    if domain is _PHYSICAL_NO_IO_DOMAIN and (
        re.fullmatch(domain.cell_pattern, permit.admission.cell_id) is None
        or re.fullmatch(domain.session_pattern, permit.admission.session_id) is None
        or permit.registration.effect_class is not EffectClass.NO_DEVICE_IO
        or permit.registration.stage
        not in {
            PhysicalOnboardingStage.WORKSPACE_SOURCES,
            PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT,
        }
        or permit.registration.resources != ()
        or permit.envelope is not None
        or any(
            getattr(permit.registration.budget, name) != 0
            for name in (
                "maximum_opens",
                "maximum_reads",
                "maximum_writes",
                "maximum_frames",
                "maximum_closes",
            )
        )
    ):
        raise M1CommissioningPersistenceError(
            "physical diagnostic storage permits NO_DEVICE_IO only"
        )
    if domain is _PHYSICAL_CAMERA_DOMAIN and (
        re.fullmatch(domain.cell_pattern, permit.admission.cell_id) is None
        or re.fullmatch(domain.session_pattern, permit.admission.session_id) is None
        or permit.registration.effect_class is not EffectClass.BOUNDED_CAMERA_CAMPAIGN
        or permit.registration.stage
        not in {
            PhysicalOnboardingStage.CAMERA_MODE_CONTROLS,
            PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS,
        }
        or permit.registration.resources != (LeaseLevel.CAMERA,)
        or permit.registration.budget.timeout_ms > 25000
        or permit.envelope is not None
    ):
        raise M1CommissioningPersistenceError(
            "physical camera storage requires camera-only acquisition without energy authority"
        )
    if domain is _PHYSICAL_USB_IDENTITY_DOMAIN and (
        type(permit.admission) is not UsbIdentityAdmissionSnapshot
        or re.fullmatch(domain.cell_pattern, permit.admission.cell_id) is None
        or re.fullmatch(domain.session_pattern, permit.admission.session_id) is None
        or permit.registration.action_id != USB_IDENTITY_ACTION_ID
        or permit.registration.stage is not PhysicalOnboardingStage.CAMERA_IDENTITY
        or permit.registration.effect_class is not EffectClass.BOUNDED_CAMERA_CAMPAIGN
        or permit.registration.resources != (LeaseLevel.CAMERA,)
        or permit.registration.budget
        != CampaignBudget(25000, 128 * 1024, 32, 128, 0, 0, 32)
        or permit.envelope is not None
    ):
        raise M1CommissioningPersistenceError(
            "USB identity storage requires its exact amended policy/action/budget"
        )
    if domain is _PHYSICAL_USB_PRESENCE_DOMAIN and (
        type(permit.admission) is not UsbPresenceAdmissionSnapshot
        or re.fullmatch(domain.cell_pattern, permit.admission.cell_id) is None
        or re.fullmatch(domain.session_pattern, permit.admission.session_id) is None
        or permit.admission.selected_identity_sha256
        != permit.admission.phase_binding_sha256
        or permit.registration.action_id != USB_PRESENCE_ACTION_ID
        or permit.registration.worker_id != "scoped-physical-native-usb-presence"
        or permit.registration.stage is not PhysicalOnboardingStage.CAMERA_IDENTITY
        or permit.registration.effect_class is not EffectClass.BOUNDED_CAMERA_CAMPAIGN
        or permit.registration.resources != (LeaseLevel.CAMERA,)
        or permit.registration.budget
        != CampaignBudget(25000, 128 * 1024, 0, 4, 0, 0, 0)
        or permit.envelope is not None
    ):
        raise M1CommissioningPersistenceError(
            "USB presence storage requires exact phase-bound policy/action/budget"
        )


class M1CommissioningPersistenceError(RuntimeError):
    """A source, namespace, lease, journal, reservation or result is inconsistent."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def rehearsal_source_binding(workspace_source_sha256: str) -> str:
    """Canonical source-domain separation; never reuse a physical source hash."""
    if (
        type(workspace_source_sha256) is not str
        or _HASH.fullmatch(workspace_source_sha256) is None
        or workspace_source_sha256 == "0" * 64
    ):
        raise M1CommissioningPersistenceError(
            "workspace source must be a nonzero SHA-256"
        )
    return _sha256(
        canonical_json_bytes(
            {
                "schema": REHEARSAL_SOURCE_SCHEMA,
                "composition": INCAPABLE_COMPOSITION,
                "workspace_source_sha256": workspace_source_sha256,
            }
        )
    )


def _freeze_document(value: Mapping[str, Any]) -> bytes:
    if not isinstance(value, Mapping):
        raise M1CommissioningPersistenceError(
            "reviewed facts must be JSON document mappings"
        )
    try:
        payload = json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, RecursionError) as exc:
        raise M1CommissioningPersistenceError(
            "reviewed facts are not finite JSON"
        ) from exc
    if len(payload) > 128 * 1024:
        raise M1CommissioningPersistenceError(
            "reviewed fact document exceeds its byte budget"
        )
    return payload


def _exact_dataclass(value: object, kind: type[Any]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {item.name for item in fields(kind)}:
        raise M1CommissioningPersistenceError(f"stored {kind.__name__} schema mismatch")
    return dict(value)


def _decode_permit(value: object) -> ExactOperationPermit:
    """Strictly reconstruct retained data for validation, never for dispatch."""
    return _decode_domain_permit(value, _REHEARSAL_DOMAIN)


def _decode_domain_permit(
    value: object, domain: _PersistenceDomain
) -> ExactOperationPermit:
    """Shared strict codec; the historical public helper stays rehearsal-only."""
    try:
        permit = _exact_dataclass(value, ExactOperationPermit)
        permit["request"] = RegisteredActionRequest(
            **_exact_dataclass(permit["request"], RegisteredActionRequest)
        )
        admission_type = (
            UsbIdentityAdmissionSnapshot
            if domain is _PHYSICAL_USB_IDENTITY_DOMAIN
            else (
                UsbPresenceAdmissionSnapshot
                if domain is _PHYSICAL_USB_PRESENCE_DOMAIN
                else AdmissionSnapshot
            )
        )
        admission = _exact_dataclass(permit["admission"], admission_type)
        admission["mode"] = CommissioningMode(admission["mode"])
        admission["stage"] = PhysicalOnboardingStage(admission["stage"])
        admission["stage_state"] = V2StageState(admission["stage_state"])
        admission["configuration_epoch_hashes"] = tuple(
            admission["configuration_epoch_hashes"]
        )
        admission["open_blocker_ids"] = tuple(admission["open_blocker_ids"])
        permit["admission"] = admission_type(**admission)
        registration = _exact_dataclass(permit["registration"], CampaignRegistration)
        registration["stage"] = PhysicalOnboardingStage(registration["stage"])
        registration["effect_class"] = EffectClass(registration["effect_class"])
        registration["resources"] = tuple(
            LeaseLevel(item) for item in registration["resources"]
        )
        registration["budget"] = CampaignBudget(
            **_exact_dataclass(registration["budget"], CampaignBudget)
        )
        permit["registration"] = CampaignRegistration(**registration)
        if permit["envelope"] is not None:
            envelope = _exact_dataclass(permit["envelope"], EnergizationEnvelope)
            envelope["required_initial_state"] = ObservedPowerState(
                envelope["required_initial_state"]
            )
            envelope["required_final_state"] = ObservedPowerState(
                envelope["required_final_state"]
            )
            permit["envelope"] = EnergizationEnvelope(**envelope)
        restored = ExactOperationPermit(**permit)
        if (
            type(restored.attempt_id) is not str
            or re.fullmatch(r"attempt-[0-9a-f]{32}", restored.attempt_id) is None
            or type(restored.nonce) is not str
            or _HASH.fullmatch(restored.nonce) is None
            or type(restored.issued_at_ns) is not int
            or type(restored.expires_at_ns) is not int
            or not 0
            <= restored.issued_at_ns
            < restored.expires_at_ns
            <= restored.issued_at_ns + MAX_PERMIT_TTL_NS
            or restored.admission.mode is not domain.mode
            or restored.request.expected_challenge_sha256
            != restored.admission.challenge_sha256
            or restored.request.cell_id != restored.admission.cell_id
            or restored.request.session_id != restored.admission.session_id
            or restored.request.action_id != restored.registration.action_id
            or restored.registration.stage != restored.admission.stage
        ):
            raise M1CommissioningPersistenceError(
                "retained permit bindings are invalid"
            )
        _require_domain_permit(restored, domain)
        return restored
    except (TypeError, ValueError, KeyError) as exc:
        raise M1CommissioningPersistenceError(
            "malformed retained exact permit"
        ) from exc


@dataclass(frozen=True, slots=True)
class _M1AdmissionFacts:
    """Frozen server-pinned facts; never client-authored authoritative hashes."""

    hazard_assessment_document: Mapping[str, Any]
    configuration_epoch_documents: tuple[Mapping[str, Any], ...]
    selected_identity_document: Mapping[str, Any] | None
    open_blocker_ids: tuple[str, ...] = ()
    envelope: EnergizationEnvelope | None = None
    _hazard: bytes = field(init=False, repr=False)
    _epochs: tuple[bytes, ...] = field(init=False, repr=False)
    _identity: bytes | None = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            type(self.configuration_epoch_documents) is not tuple
            or len(self.configuration_epoch_documents) != 8
        ):
            raise M1CommissioningPersistenceError(
                "exactly eight server-pinned epoch documents are required"
            )
        if (
            type(self.open_blocker_ids) is not tuple
            or len(self.open_blocker_ids) > 64
            or any(type(item) is not str for item in self.open_blocker_ids)
        ):
            raise M1CommissioningPersistenceError("blocker IDs must be a bounded tuple")
        if self.envelope is not None and not isinstance(
            self.envelope, EnergizationEnvelope
        ):
            raise M1CommissioningPersistenceError(
                "envelope must be a typed energization envelope"
            )
        object.__setattr__(
            self, "_hazard", _freeze_document(self.hazard_assessment_document)
        )
        object.__setattr__(
            self,
            "_epochs",
            tuple(
                _freeze_document(item) for item in self.configuration_epoch_documents
            ),
        )
        object.__setattr__(
            self,
            "_identity",
            (
                None
                if self.selected_identity_document is None
                else _freeze_document(self.selected_identity_document)
            ),
        )


@dataclass(frozen=True, slots=True)
class RehearsalAdmissionFacts(_M1AdmissionFacts):
    """Exact legacy rehearsal facts; never accepted as physical observations."""


FactsProvider = Callable[
    [RegisteredActionRequest, V2SessionSnapshot], RehearsalAdmissionFacts
]


class _M1CoordinatorTransaction:
    """Narrow scoped view constructed only inside M1's guarded lease boundary.

    Raw publishers/ledgers stay private. Saving a reference to this object past
    the context's lifetime cannot perform subsequent reads or writes through it.
    """

    def __init__(
        self,
        *,
        session: PhysicalOnboardingV2Session,
        attempts: PhysicalOnboardingAttemptLedger,
        quarantine: PhysicalOnboardingQuarantineLedger,
        publication: QualifiedWindowsOnboardingPublication,
        cell_root: Path,
        guard: Callable[[], None],
        held: HeldLeaseSet,
        specs: tuple[LeaseSpec, ...],
        verification: Callable[[], "M1RuntimeVerification"],
        domain: _PersistenceDomain,
        facts_type: type[_M1AdmissionFacts],
    ) -> None:
        if not _registered_domain(domain):
            raise M1CommissioningPersistenceError("unregistered persistence domain")
        self._domain, self._facts_type = domain, facts_type
        self._session, self._attempts, self._quarantine = session, attempts, quarantine
        self._publication, self._guard, self._held = publication, guard, held
        self._specs, self._verification = specs, verification
        self._cell_root = cell_root
        self._records_root = contained_path(
            cell_root, domain.record_directory, label="coordinator records"
        )
        self._active = True
        self._facts_provider: (
            Callable[[RegisteredActionRequest, V2SessionSnapshot], _M1AdmissionFacts]
            | None
        ) = None
        self._facts: _M1AdmissionFacts | None = None
        self._admission: AdmissionSnapshot | None = None
        self._permit: ExactOperationPermit | None = None
        self._retention_authorized = False
        self._check_scope()
        # The immutable header is checked once under CELL ownership. Replaying
        # the whole evidence tree inside every nested guard would multiply the
        # cost without improving ownership: snapshot and mutations still verify
        # their fresh journal/evidence state through V2's qualified readers.
        snapshot = self._session.snapshot()
        if (
            snapshot.header.mode != domain.mode.value
            or re.fullmatch(domain.cell_pattern, snapshot.header.cell_id) is None
            or re.fullmatch(domain.session_pattern, snapshot.header.session_id) is None
        ):
            raise M1CommissioningPersistenceError(
                "immutable session mode/namespace differs from the storage domain"
            )

    def _check_scope(self) -> None:
        if not self._active or self._held.closed:
            raise M1CommissioningPersistenceError(
                "coordinator transaction scope has ended"
            )
        self._guard()

    def _requires_retained_evidence(
        self, permit: ExactOperationPermit, *, domain: _PersistenceDomain | None = None
    ) -> bool:
        # A physical source preflight must retain its actual report, not only a
        # claimed result/hash. Deriving the requirement from the durable domain
        # prevents a restart with different runtime registration flags removing it.
        return (self._domain if domain is None else domain) in (
            _PHYSICAL_NO_IO_DOMAIN,
            *_CAMERA_FAMILY,
        ) or permit.registration.effect_class is EffectClass.SERIAL_OPEN_OR_WRITE

    def close_scope(self) -> None:
        self._active = False

    @property
    def held_leases(self) -> tuple[LeaseSpec, ...]:
        self._check_scope()
        owners = self._held.owners
        if len(owners) != len(self._specs) or any(
            owner.level != spec.level or owner.resource_id != spec.resource_id
            for owner, spec in zip(owners, self._specs)
        ):
            raise M1CommissioningPersistenceError(
                "OS lease ownership does not match the exact transaction"
            )
        return self._specs

    def snapshot(self) -> V2SessionSnapshot:
        self._check_scope()
        return self._session.snapshot()

    def verification(self) -> "M1RuntimeVerification":
        self._check_scope()
        return self._verification()

    def _admission_observation(
        self,
    ) -> tuple[V2SessionSnapshot, "M1RuntimeVerification"]:
        # Legacy domains retain their separate fresh observation paths.
        return self.snapshot(), self.verification()

    def _coherent_admission_observation(
        self,
        observe: Callable[[], tuple[V2SessionSnapshot | None, M1RuntimeVerification]],
        *,
        mismatch_message: str,
    ) -> tuple[V2SessionSnapshot, M1RuntimeVerification]:
        """Check one fresh runtime observation, shared by camera and USB.

        The server-owned callback verifies global/sibling state independently
        from the selected session. Reuse only its returned selected snapshot,
        not a previous observation. This avoids a redundant full inventory read
        while retaining the family audit and later original/context boundaries.
        """
        from .physical_onboarding_m1 import M1RuntimeVerification

        self._check_scope()
        snapshot, verified = observe()
        self._check_scope()
        if (
            type(snapshot) is not V2SessionSnapshot
            or type(verified) is not M1RuntimeVerification
            or verified.cell.cell_id != snapshot.header.cell_id
            or verified.cell.source_binding_sha256
            != snapshot.header.source_binding_sha256
            or verified.session_id != snapshot.header.session_id
            or verified.session_header_sha256 != snapshot.header.header_sha256
            or verified.session_head_sha256 != snapshot.head.head_sha256
            or verified.qualification_anchor_sha256
            != snapshot.header.durability_qualification_sha256
            or verified.session_reconciliation_required
            != snapshot.reconciliation_required
            # Original storage's canonical encoding includes a terminating LF.
            or verified.evidence_inventory_sha256
            != canonical_sha256([ref.to_dict() for ref in snapshot.evidence])
        ):
            raise M1CommissioningPersistenceError(mismatch_message)
        return snapshot, verified

    def _require_stage_mutation(self) -> None:
        self._check_scope()
        self._audit_records()
        self._quarantine.assert_effects_allowed(self._attempts)
        if not self._session.snapshot().mutation_allowed:
            raise M1CommissioningPersistenceError(
                "session suffix requires reconciliation"
            )

    def store_evidence(
        self,
        stage: PhysicalOnboardingStage,
        payload: bytes,
        *,
        label: str,
        media_type: str,
        captured_at_ns: int,
        expected_head_sha256: str,
    ) -> EvidenceReference:
        self._require_stage_mutation()
        return self._session.store_evidence(
            stage,
            payload,
            label=label,
            media_type=media_type,
            captured_at_ns=captured_at_ns,
            expected_head_sha256=expected_head_sha256,
        )

    def commit_stage_state(
        self,
        stage: PhysicalOnboardingStage,
        state: V2StageState,
        *,
        occurred_at_ns: int,
        detail_code: str,
        expected_head_sha256: str,
        evidence: Sequence[EvidenceReference] = (),
    ) -> V2SessionSnapshot:
        self._require_stage_mutation()
        return self._session.commit_stage_state(
            stage,
            state,
            occurred_at_ns=occurred_at_ns,
            detail_code=detail_code,
            expected_head_sha256=expected_head_sha256,
            evidence=evidence,
        )

    def _ensure_records(self) -> None:
        self._check_scope()
        if not os.path.lexists(self._records_root):
            self._records_root.mkdir(exist_ok=False)
            self._publication.sync_directory(self._records_root.parent)
        safe_root(self._records_root, label="coordinator records")

    def _write_record(
        self, filename: str, kind: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        self._ensure_records()
        if _RECORD.fullmatch(filename) is None:
            raise M1CommissioningPersistenceError(
                "unregistered coordinator record path"
            )
        record = self._frame_record(kind, data)
        payload = canonical_json_bytes(record)
        self._publication.write_new_file(self._records_root / filename, payload)
        self._publication.sync_directory(self._records_root)
        return record

    def _frame_record(self, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        """Same immutable envelope for admission sizing and actual publication."""
        core = {
            "schema": self._domain.record_schema,
            "kind": kind,
            "composition": self._domain.composition,
            "physical_authority": False,
            "data": data,
        }
        record = {**core, "record_sha256": _sha256(canonical_json_bytes(core))}
        payload = canonical_json_bytes(record)
        if len(payload) > MAX_RECORD_BYTES:
            raise M1CommissioningPersistenceError(
                "coordinator record exceeds its byte limit"
            )
        return record

    def _read_records(self) -> dict[str, dict[str, Any]]:
        return self._read_domain_records(self._domain, [0, 0])

    def _read_domain_records(
        self, domain: _PersistenceDomain, budget: list[int]
    ) -> dict[str, dict[str, Any]]:
        """Closed sibling roots share one aggregate budget, never a caller path."""
        self._check_scope()
        if not _registered_domain(domain):
            raise M1CommissioningPersistenceError("unregistered record directory")
        root = contained_path(
            self._cell_root, domain.record_directory, label="coordinator records"
        )
        if not os.path.lexists(root):
            return {}
        records = {}
        for filename in self._publication.list_relative_files(
            root, maximum_entries=MAX_RECORDS
        ):
            if _RECORD.fullmatch(filename) is None:
                raise M1CommissioningPersistenceError(
                    "unexpected or partial coordinator record requires review"
                )
            payload = self._publication.read_bounded(
                root, filename, maximum_bytes=MAX_RECORD_BYTES
            )
            budget[0] += 1
            budget[1] += len(payload)
            if budget[0] > MAX_RECORDS or budget[1] > MAX_RECORD_TOTAL_BYTES:
                raise M1CommissioningPersistenceError(
                    "coordinator records exceed the aggregate read budget"
                )
            record = parse_canonical_json(payload, "coordinator record")
            if (
                set(record)
                != {
                    "schema",
                    "kind",
                    "composition",
                    "physical_authority",
                    "data",
                    "record_sha256",
                }
                or record["schema"] != domain.record_schema
                or record["composition"] != domain.composition
                or record["physical_authority"] is not False
                or type(record["data"]) is not dict
            ):
                raise M1CommissioningPersistenceError(
                    "coordinator record schema/provenance mismatch"
                )
            core = {
                key: value for key, value in record.items() if key != "record_sha256"
            }
            if record["record_sha256"] != _sha256(canonical_json_bytes(core)):
                raise M1CommissioningPersistenceError(
                    "coordinator record self hash mismatch"
                )
            records[filename] = record
        return records

    def _audit_records(
        self, *, include_family: bool = False
    ) -> dict[str, dict[str, Any]]:
        # All camera domains share the *actual complete* cell-global ledger.
        # No filtered/fabricated snapshot may hide a sibling attempt or orphan.
        domains = _CAMERA_FAMILY if self._domain in _CAMERA_FAMILY else (self._domain,)
        records: dict[str, dict[str, Any]] = {}
        record_domains: dict[str, _PersistenceDomain] = {}
        budget = [0, 0]
        for domain in domains:
            for filename, record in self._read_domain_records(domain, budget).items():
                if filename in records:
                    raise M1CommissioningPersistenceError(
                        "duplicate camera-family reservation or record"
                    )
                records[filename] = record
                record_domains[filename] = domain
        attempts = self._attempts.snapshot()
        latest_events = {event.attempt_id: event for event in attempts.latest_events}
        intents = {
            event.attempt_id: event
            for event in attempts.events
            if event.state is AttemptState.INTENT_DURABLE
        }
        requests: dict[str, dict[str, Any]] = {}
        permits: dict[str, ExactOperationPermit] = {}
        permit_domains: dict[str, _PersistenceDomain] = {}
        nonces: set[str] = set()
        for filename, record in records.items():
            if not filename.startswith("request-"):
                continue
            data = record["data"]
            domain = record_domains[filename]
            expected_fields = {
                "request_key",
                "attempt_id",
                "permit_sha256",
                "permit",
            }
            if domain in (_PHYSICAL_USB_IDENTITY_DOMAIN, _PHYSICAL_USB_PRESENCE_DOMAIN):
                expected_fields.add("admission_evidence")
            camera_originals = (
                domain is _PHYSICAL_CAMERA_DOMAIN and "admission_evidence" in data
            )
            if camera_originals:
                expected_fields.add("admission_evidence")
            if (
                record["kind"] != "EXACT_REQUEST_RESERVED"
                or set(data) != expected_fields
            ):
                raise M1CommissioningPersistenceError(
                    "request reservation schema mismatch"
                )
            permit = _decode_domain_permit(data["permit"], domain)
            if domain is _PHYSICAL_USB_IDENTITY_DOMAIN:
                from .commissioning_usb_identity_persistence import (
                    _verify_admission_evidence,
                )

                _verify_admission_evidence(data["admission_evidence"], permit.admission)
            elif domain is _PHYSICAL_USB_PRESENCE_DOMAIN:
                from .commissioning_usb_presence_persistence import (
                    verify_usb_presence_admission_evidence,
                )

                verify_usb_presence_admission_evidence(
                    data["admission_evidence"], permit.admission, permit=permit
                )
            elif camera_originals:
                from .commissioning_camera_persistence import (
                    verify_camera_admission_evidence,
                )

                verify_camera_admission_evidence(data["admission_evidence"], permit)
            if (
                data["request_key"] != permit.request.request_key
                or filename
                != f"request-{_sha256(permit.request.request_key.encode('ascii'))}.json"
                or data["permit_sha256"] != permit.permit_sha256
                or permit.attempt_id != data["attempt_id"]
            ):
                raise M1CommissioningPersistenceError("request/permit binding mismatch")
            nonce = permit.nonce
            if (
                type(nonce) is not str
                or _HASH.fullmatch(nonce) is None
                or nonce in nonces
                or data["attempt_id"] in requests
            ):
                raise M1CommissioningPersistenceError(
                    "duplicate or invalid persistent permit nonce/attempt"
                )
            nonces.add(nonce)
            requests[data["attempt_id"]] = data
            permits[data["attempt_id"]] = permit
            permit_domains[data["attempt_id"]] = domain
            event = latest_events.get(data["attempt_id"])
            if event is None:
                raise M1CommissioningPersistenceError(
                    "reserved request lacks committed intent; retain for reconciliation, never replay"
                )
            intent = intents[event.attempt_id]
            if (
                event.operation_binding_sha256 != permit.permit_sha256
                or event.session_id != permit.request.session_id
                or event.cell_id != permit.request.cell_id
                or event.source_binding_sha256 != permit.admission.source_binding_sha256
                or event.stage_plan_sha256 != permit.admission.stage_plan_sha256
                or event.stage != permit.admission.stage.value
                or event.effect_class != permit.registration.effect_class
                or event.operation_id != permit.registration.action_id
                or event.session_journal_head_sha256
                != permit.admission.journal_head_sha256
                or event.evidence_inventory_sha256
                != permit.admission.evidence_inventory_sha256
                or event.durability_qualification_sha256
                != permit.admission.durability_qualification_sha256
                or intent.attempt_head_before_sha256
                != permit.admission.global_attempt_head_sha256
                or intent.quarantine_head_sha256
                != permit.admission.quarantine_head_sha256
            ):
                raise M1CommissioningPersistenceError(
                    "committed attempt does not bind its durable exact permit"
                )
        from .camera_activation_campaign_contract import is_camera_activation_action

        camera_parts: dict[str, CameraEvidenceParts | SealedCaptureParts] = {}
        armed_attempts = {
            event.attempt_id
            for event in attempts.events
            if event.state is AttemptState.EFFECT_ARMED
        }
        for attempt_id, permit in permits.items():
            if is_camera_activation_action(permit):
                parts = self._camera_activation_parts(
                    permit, records, domain=permit_domains[attempt_id]
                )
                if (
                    parts.part_count or parts.complete
                ) and attempt_id not in armed_attempts:
                    raise M1CommissioningPersistenceError(
                        "camera activation evidence lacks original armed predecessor"
                    )
                camera_parts[attempt_id] = parts
        for event in latest_events.values():
            if event.attempt_id not in requests:
                raise M1CommissioningPersistenceError(
                    "attempt is missing its durable request/permit reservation"
                )
            if event.state is AttemptState.SEALED_KNOWN:
                expected = f"result-{event.attempt_id}-sealed_known.json"
                observed = f"receipt-{event.attempt_id}-effect_observed.json"
                cleanup = f"receipt-{event.attempt_id}-cleanup_confirmed.json"
                if any(name not in records for name in (expected, observed, cleanup)):
                    raise M1CommissioningPersistenceError(
                        "known attempt lacks retained result evidence"
                    )
                receipt = records[expected]["data"].get("result", {}).get("receipt")
                if receipt != records[observed]["data"].get(
                    "receipt"
                ) or receipt != records[cleanup]["data"].get("receipt"):
                    raise M1CommissioningPersistenceError(
                        "known result disagrees with retained lifecycle receipts"
                    )
                # Requirement is derived from the immutable effect class, not
                # an optional process flag or a separately removable marker.
                # Historical M1 serial results without raw evidence remain held.
                if self._requires_retained_evidence(
                    permits[event.attempt_id], domain=permit_domains[event.attempt_id]
                ):
                    self._match_retained_campaign(
                        permits[event.attempt_id],
                        self._decode_receipt(receipt),
                        records,
                        domain=permit_domains[event.attempt_id],
                        camera_parts=camera_parts.get(event.attempt_id),
                    )
        for filename, record in records.items():
            if filename.startswith("request-"):
                continue
            data = record["data"]
            attempt_id = data.get("attempt_id")
            if (
                type(attempt_id) is not str
                or attempt_id not in requests
                or data.get("permit_sha256") != requests[attempt_id]["permit_sha256"]
            ):
                raise M1CommissioningPersistenceError(
                    "result/receipt is not bound to a registered attempt"
                )
            permit = permits[attempt_id]
            domain = permit_domains[attempt_id]
            if record_domains[filename] is not domain:
                raise M1CommissioningPersistenceError(
                    "campaign record crossed its original domain"
                )
            if attempt_id in camera_parts and (
                filename == f"evidence-{attempt_id}-retained.json"
                or filename.startswith(f"receipt-{attempt_id}-camera_activation_")
            ):
                # The complete attempt subset was decoded above, including all
                # parts without an index. Envelope, original domain and ledger
                # authentication still apply to every individual record here.
                continue
            if filename.startswith("evidence-"):
                if filename != f"evidence-{attempt_id}-retained.json":
                    raise M1CommissioningPersistenceError(
                        "campaign evidence filename mismatch"
                    )
                self._decode_campaign_evidence(permit, record)
            elif filename.startswith("receipt-"):
                if (
                    record["kind"] != "CAMPAIGN_RECEIPT"
                    or set(data) != {"attempt_id", "permit_sha256", "state", "receipt"}
                    or data["state"] not in {"EFFECT_OBSERVED", "CLEANUP_CONFIRMED"}
                    or filename != f"receipt-{attempt_id}-{data['state'].lower()}.json"
                ):
                    raise M1CommissioningPersistenceError(
                        "retained lifecycle receipt schema mismatch"
                    )
                self._validate_receipt(
                    permit, self._decode_receipt(data["receipt"]), domain=domain
                )
            else:
                if record["kind"] != "CAMPAIGN_RESULT" or set(data) != {
                    "attempt_id",
                    "permit_sha256",
                    "result",
                }:
                    raise M1CommissioningPersistenceError(
                        "retained campaign result schema mismatch"
                    )
                result = _exact_dataclass(data["result"], AttemptResult)
                if (
                    result["attempt_id"] != attempt_id
                    or result["permit_sha256"] != permit.permit_sha256
                    or result["composition"] != domain.composition
                    or result["physical_authority"] != "NONE"
                    or result["state"]
                    not in {"SEALED_KNOWN", "SEALED_UNCERTAIN", "ABORTED_PRE_EFFECT"}
                    or filename != f"result-{attempt_id}-{result['state'].lower()}.json"
                    or type(result["reason_codes"]) is not list
                    or len(result["reason_codes"]) > 64
                    or any(
                        type(reason) is not str or len(reason) > 128
                        for reason in result["reason_codes"]
                    )
                    or type(result["quarantine_latched"]) is not bool
                ):
                    raise M1CommissioningPersistenceError(
                        "retained result bindings are invalid"
                    )
                if result["state"] == "SEALED_KNOWN":
                    if result["reason_codes"] or result["quarantine_latched"]:
                        raise M1CommissioningPersistenceError(
                            "known result cannot retain unresolved reasons/quarantine"
                        )
                    self._validate_receipt(
                        permit, self._decode_receipt(result["receipt"]), domain=domain
                    )
                elif result["state"] == "ABORTED_PRE_EFFECT" and (
                    result["receipt"] is not None or result["quarantine_latched"]
                ):
                    raise M1CommissioningPersistenceError(
                        "pre-effect abort cannot contain claimed effects"
                    )
                elif (
                    result["state"] == "SEALED_UNCERTAIN"
                    and not result["quarantine_latched"]
                ):
                    raise M1CommissioningPersistenceError(
                        "uncertain result cannot clear quarantine"
                    )
                if (
                    result["state"] == "SEALED_UNCERTAIN"
                    and attempt_id in camera_parts
                    and camera_parts[attempt_id].complete
                ):
                    # Failure does not waive accounting integrity. When full
                    # originals exist, available native counts must agree even
                    # if cancellation/publication forced an uncertain outcome.
                    self._match_camera_result_accounting(
                        permit,
                        (
                            None
                            if result["receipt"] is None
                            else self._decode_receipt(result["receipt"])
                        ),
                        camera_parts[attempt_id],
                    )
        return (
            records
            if include_family
            else {
                filename: record
                for filename, record in records.items()
                if record_domains[filename] is self._domain
            }
        )

    def _fresh_admission(
        self, request: RegisteredActionRequest
    ) -> tuple[_M1AdmissionFacts, AdmissionSnapshot, "M1RuntimeVerification"]:
        self._audit_records()
        if self._facts_provider is None:
            raise M1CommissioningPersistenceError(
                "no server-pinned admission policy is configured"
            )
        snapshot, verified = self._admission_observation()
        if (
            request.cell_id != snapshot.header.cell_id
            or request.session_id != snapshot.header.session_id
        ):
            raise M1CommissioningPersistenceError(
                "requested session/cell does not match the scoped store"
            )
        if (
            snapshot.next_action.stage is None
            or snapshot.next_action.stage_state is None
        ):
            raise M1CommissioningPersistenceError("no active stage admits a campaign")
        facts = self._facts_provider(request, snapshot)
        if type(facts) is not self._facts_type:
            raise M1CommissioningPersistenceError(
                "admission callback did not return immutable reviewed facts"
            )
        blockers = facts.open_blocker_ids + (
            ("SESSION_RECONCILIATION_REQUIRED",)
            if snapshot.reconciliation_required
            else ()
        )
        admission = AdmissionSnapshot(
            cell_id=snapshot.header.cell_id,
            session_id=snapshot.header.session_id,
            mode=self._domain.mode,
            stage=snapshot.next_action.stage,
            stage_state=snapshot.next_action.stage_state,
            stage_revision=len(snapshot.committed_events),
            source_binding_sha256=verified.cell.source_binding_sha256,
            stage_plan_sha256=STAGE_PLAN_SHA256,
            journal_head_sha256=verified.session_head_sha256,
            global_attempt_head_sha256=verified.attempt_head_sha256,
            quarantine_head_sha256=verified.quarantine_head_sha256,
            evidence_inventory_sha256=verified.evidence_inventory_sha256,
            hazard_assessment_sha256=_sha256(facts._hazard),
            durability_qualification_sha256=verified.qualification_anchor_sha256,
            configuration_epoch_hashes=tuple(
                _sha256(document) for document in facts._epochs
            ),
            selected_identity_sha256=(
                None if facts._identity is None else _sha256(facts._identity)
            ),
            quarantine_latched=verified.quarantined,
            unresolved_attempts=len(
                set(verified.unresolved_attempt_ids)
                | set(verified.uncertain_attempt_ids)
            ),
            open_blocker_ids=blockers,
        )
        return facts, admission, verified

    def read_admission(self, request: RegisteredActionRequest) -> AdmissionSnapshot:
        facts, admission, _ = self._fresh_admission(request)
        self._facts, self._admission = facts, admission
        return admission

    def read_envelope(
        self, request: RegisteredActionRequest
    ) -> EnergizationEnvelope | None:
        self._check_scope()
        if (
            self._facts is None
            or self._admission is None
            or request.session_id != self._admission.session_id
        ):
            raise M1CommissioningPersistenceError(
                "read exact admission before its envelope"
            )
        return self._facts.envelope

    def begin_intent(
        self, binding: AttemptBinding, permit: ExactOperationPermit
    ) -> None:
        self._require_stage_mutation()
        # A reviewed operation may have stored evidence in this same lease
        # scope. Recompute the actual challenge before writing any reservation;
        # an earlier cached admission never authorizes a new intent.
        fresh = self.read_admission(permit.request)
        if (
            self._admission is None
            or fresh != permit.admission
            or permit.admission != self._admission
            or permit.request.expected_challenge_sha256
            != self._admission.challenge_sha256
        ):
            raise M1CommissioningPersistenceError(
                "permit does not bind the freshly read admission"
            )
        _require_domain_permit(permit, self._domain)
        self._validate_admission_subjects(permit)
        expected = AttemptBinding(
            attempt_id=permit.attempt_id,
            session_id=permit.admission.session_id,
            stage=permit.admission.stage.value,
            effect_class=permit.registration.effect_class,
            operation_id=permit.registration.action_id,
            operation_binding_sha256=permit.permit_sha256,
            source_binding_sha256=permit.admission.source_binding_sha256,
            stage_plan_sha256=STAGE_PLAN_SHA256,
            session_journal_head_sha256=permit.admission.journal_head_sha256,
            evidence_inventory_sha256=permit.admission.evidence_inventory_sha256,
            intent_at_ns=binding.intent_at_ns,
        )
        if binding != expected:
            raise M1CommissioningPersistenceError(
                "attempt binding differs from the exact current permit"
            )
        records = self._audit_records(include_family=True)
        filename = f"request-{_sha256(permit.request.request_key.encode('ascii'))}.json"
        if filename in records:
            raise M1CommissioningPersistenceError(
                "request key is durably consumed; restart/session changes cannot replay it"
            )
        for record in records.values():
            if record["kind"] == "EXACT_REQUEST_RESERVED":
                old = record["data"]["permit"]
                if (
                    old.get("nonce") == permit.nonce
                    or old.get("attempt_id") == permit.attempt_id
                ):
                    raise M1CommissioningPersistenceError(
                        "permit nonce/attempt was already reserved"
                    )
                if (
                    permit.envelope is not None
                    and isinstance(old.get("envelope"), dict)
                    and old["envelope"].get("envelope_id")
                    == permit.envelope.envelope_id
                ):
                    raise M1CommissioningPersistenceError(
                        "energization envelope is already durably consumed"
                    )
        # Reserve request+nonce before durable intent. A crash in between leaves
        # an auditable orphan which blocks admission rather than permitting retry.
        self._write_record(
            filename,
            "EXACT_REQUEST_RESERVED",
            {
                "request_key": permit.request.request_key,
                "attempt_id": permit.attempt_id,
                "permit_sha256": permit.permit_sha256,
                "permit": asdict(permit),
                **self._reservation_evidence(),
            },
        )
        self._attempts.begin_attempt(binding, self._quarantine)
        self._permit = permit

    def _validate_admission_subjects(self, permit: ExactOperationPermit) -> None:
        """Domain joins after the fresh read, before any reservation.

        Historical domains need no extra subjects. A successor validates its
        already-read documents here without repeating the complete M1 audit.
        """

    def _reservation_evidence(self) -> dict[str, Any]:
        """Legacy reservation bytes are unchanged; USB retains its full facts."""
        return {}

    def _require_permit(self, attempt_id: str) -> ExactOperationPermit:
        self._check_scope()
        if self._permit is None or self._permit.attempt_id != attempt_id:
            raise M1CommissioningPersistenceError(
                "no exact attempt was admitted in this lease scope"
            )
        return self._permit

    def consume_permit(self, permit: ExactOperationPermit) -> None:
        admitted = self._require_permit(permit.attempt_id)
        if admitted != permit:
            raise M1CommissioningPersistenceError(
                "permit substitution before consumption"
            )
        latest = self._attempts.snapshot().latest_event(permit.attempt_id)
        if latest is None or latest.state is not AttemptState.INTENT_DURABLE:
            raise M1CommissioningPersistenceError(
                "permit may be consumed only once from committed intent"
            )
        # This append is the authoritative durable consumption boundary. No
        # worker may run until its committed EFFECT_ARMED head is returned.
        self._attempts.transition(
            permit.attempt_id,
            AttemptState.EFFECT_ARMED,
            self._quarantine,
            occurred_at_ns=time.time_ns(),
        )

    def assert_consumed_permit(self, permit: ExactOperationPermit) -> None:
        """One-use acknowledgement of actual committed EFFECT_ARMED under leases."""
        if (
            self._require_permit(permit.attempt_id) != permit
            or self._retention_authorized
        ):
            raise M1CommissioningPersistenceError(
                "exact retained worker authorization is one-use"
            )
        expected = (
            LeaseSpec(LeaseLevel.CELL, permit.request.cell_id),
            LeaseSpec(LeaseLevel.SESSION, permit.request.session_id),
            *(
                LeaseSpec(level, permit.request.cell_id)
                for level in permit.registration.resources
            ),
        )
        latest = self._attempts.snapshot().latest_event(permit.attempt_id)
        if (
            self.held_leases != expected
            or latest is None
            or latest.state is not AttemptState.EFFECT_ARMED
            or latest.operation_binding_sha256 != permit.permit_sha256
            or latest.source_binding_sha256 != permit.admission.source_binding_sha256
        ):
            raise M1CommissioningPersistenceError(
                "consumed permit lacks exact owned committed armed evidence"
            )
        self._retention_authorized = True

    def revalidate_consumed_permit(self, permit: ExactOperationPermit) -> None:
        """Read-only continuity check, not another acknowledgement or redemption.

        Intent/arming intentionally changed the attempt ledger. All other
        admission facts must still match; the only unresolved attempt must be
        this exact committed tail pair. The coordinator separately checks the
        original time bounds immediately before each dispatch boundary.
        """
        if (
            self._require_permit(permit.attempt_id) != permit
            or not self._retention_authorized
        ):
            raise M1CommissioningPersistenceError(
                "revalidation requires the exact prior consumed acknowledgement"
            )
        expected = (
            LeaseSpec(LeaseLevel.CELL, permit.request.cell_id),
            LeaseSpec(LeaseLevel.SESSION, permit.request.session_id),
            *(
                LeaseSpec(level, permit.request.cell_id)
                for level in permit.registration.resources
            ),
        )
        if self.held_leases != expected:
            raise M1CommissioningPersistenceError("consumed lease ownership changed")
        facts, fresh, verified = self._fresh_admission(permit.request)
        events = self._attempts.snapshot().events
        if (
            len(events) < 2
            or tuple(event.state for event in events[-2:])
            != (AttemptState.INTENT_DURABLE, AttemptState.EFFECT_ARMED)
            or any(
                event.attempt_id != permit.attempt_id
                or event.operation_binding_sha256 != permit.permit_sha256
                for event in events[-2:]
            )
            or verified.unresolved_attempt_ids != (permit.attempt_id,)
            or verified.uncertain_attempt_ids
            or facts.envelope != permit.envelope
            or fresh
            != replace(
                permit.admission,
                global_attempt_head_sha256=verified.attempt_head_sha256,
                unresolved_attempts=1,
            )
        ):
            raise M1CommissioningPersistenceError(
                "consumed permit source, stage, facts or armed state changed"
            )

    @staticmethod
    def _decode_campaign_evidence(
        permit: ExactOperationPermit,
        record: dict[str, Any],
    ) -> tuple[CampaignEvidence, ...]:
        data = record.get("data")
        if (
            record.get("kind") != "CAMPAIGN_EVIDENCE"
            or type(data) is not dict
            or set(data) != {"attempt_id", "permit_sha256", "evidence"}
            or data["attempt_id"] != permit.attempt_id
            or data["permit_sha256"] != permit.permit_sha256
            or type(data["evidence"]) is not list
            or not 1 <= len(data["evidence"]) <= 4
        ):
            raise M1CommissioningPersistenceError(
                "campaign evidence record schema/binding mismatch"
            )
        decoded: list[CampaignEvidence] = []
        try:
            for item in data["evidence"]:
                if (
                    type(item) is not dict
                    or set(item)
                    != {
                        "schema",
                        "label",
                        "payload_bytes",
                        "payload_sha256",
                        "payload_base64",
                    }
                    or type(item["payload_base64"]) is not str
                    or len(item["payload_base64"])
                    > 4 * ((MAX_RETAINED_CAMPAIGN_BYTES + 2) // 3)
                ):
                    raise M1CommissioningPersistenceError(
                        "campaign evidence payload envelope is malformed"
                    )
                raw = base64.b64decode(
                    item["payload_base64"].encode("ascii"), validate=True
                )
                artifact = CampaignEvidence(item["schema"], item["label"], raw)
                if (
                    type(item["payload_bytes"]) is not int
                    or item["payload_bytes"] != len(raw)
                    or item["payload_sha256"] != artifact.payload_sha256
                    or base64.b64encode(raw).decode("ascii") != item["payload_base64"]
                ):
                    raise M1CommissioningPersistenceError(
                        "campaign evidence bytes/hash mismatch"
                    )
                decoded.append(artifact)
            result = tuple(decoded)
            validate_campaign_evidence(result)
            return result
        except (ValueError, TypeError, UnicodeError, binascii.Error) as exc:
            raise M1CommissioningPersistenceError(
                "invalid lossless campaign evidence"
            ) from exc

    @staticmethod
    def _match_campaign_evidence(
        receipt: WorkerReceipt, evidence: tuple[CampaignEvidence, ...]
    ) -> None:
        if (
            receipt.evidence_sha256s != tuple(item.payload_sha256 for item in evidence)
            or type(receipt.output_bytes) is not int
            or receipt.output_bytes != sum(len(item.payload) for item in evidence)
        ):
            raise M1CommissioningPersistenceError(
                "known receipt does not match complete retained evidence"
            )

    def _camera_activation_parts(
        self,
        permit: ExactOperationPermit,
        records: dict[str, dict[str, Any]],
        *,
        domain: _PersistenceDomain | None = None,
    ) -> CameraEvidenceParts | SealedCaptureParts:
        from .camera_activation_campaign_contract import (
            validate_camera_activation_binding,
            validate_camera_activation_permit,
        )
        from .camera_activation_evidence_parts import inspect_camera_evidence_parts
        from .camera_sealed_capture_contract import (
            is_sealed_capture,
            validate_sealed_capture_binding,
        )
        from .camera_sealed_capture_evidence import inspect_sealed_capture_parts

        domain = self._domain if domain is None else domain
        if domain is not _PHYSICAL_CAMERA_DOMAIN:
            raise M1CommissioningPersistenceError(
                "camera activation parts require the original camera domain"
            )
        try:
            validate_camera_activation_permit(permit)
            prefix = f"receipt-{permit.attempt_id}-camera_activation_"
            final = f"evidence-{permit.attempt_id}-retained.json"
            inspector = (
                inspect_sealed_capture_parts
                if is_sealed_capture(permit)
                else inspect_camera_evidence_parts
            )
            parts = inspector(
                {
                    name: record
                    for name, record in records.items()
                    if name == final or name.startswith(prefix)
                },
                expected_attempt_id=permit.attempt_id,
                expected_permit_sha256=permit.permit_sha256,
            )
            if parts.artifacts is not None:
                if is_sealed_capture(permit):
                    validate_sealed_capture_binding(permit, parts.artifacts)
                else:
                    if type(parts.artifacts) is not tuple:
                        raise ValueError(
                            "legacy camera evidence must be the exact native pair"
                        )
                    validate_camera_activation_binding(permit, parts.artifacts)
            return parts
        except (ValueError, TypeError) as exc:
            raise M1CommissioningPersistenceError(
                "invalid original camera activation evidence"
            ) from exc

    def _match_retained_campaign(
        self,
        permit: ExactOperationPermit,
        receipt: WorkerReceipt,
        records: dict[str, dict[str, Any]],
        *,
        domain: _PersistenceDomain | None = None,
        camera_parts: CameraEvidenceParts | SealedCaptureParts | None = None,
    ) -> None:
        from .camera_activation_campaign_contract import is_camera_activation_action

        if is_camera_activation_action(permit):
            parts = camera_parts or self._camera_activation_parts(
                permit, records, domain=domain
            )
            self._match_camera_result_accounting(permit, receipt, parts)
            return
        record = records.get(f"evidence-{permit.attempt_id}-retained.json")
        if record is None:
            raise M1CommissioningPersistenceError(
                "known attempt lacks mandatory full campaign evidence"
            )
        self._match_campaign_evidence(
            receipt, self._decode_campaign_evidence(permit, record)
        )

    @staticmethod
    def _match_camera_result_accounting(
        permit: ExactOperationPermit,
        receipt: WorkerReceipt | None,
        parts: CameraEvidenceParts | SealedCaptureParts,
    ) -> None:
        from .camera_activation_campaign_contract import (
            validate_camera_activation_receipt,
        )
        from .camera_activation_campaign_evidence import (
            validate_camera_activation_evidence,
        )

        if not parts.complete or parts.artifacts is None:
            raise M1CommissioningPersistenceError(
                "known camera attempt requires every part and final index"
            )
        try:
            from .camera_sealed_capture_contract import (
                is_sealed_capture,
                validate_sealed_capture_receipt,
            )
            from .camera_sealed_capture_evidence import SealedCameraCaptureEvidence

            if is_sealed_capture(permit):
                if type(parts.artifacts) is not SealedCameraCaptureEvidence:
                    raise ValueError("checksum-bearing collection required")
                run = validate_camera_activation_evidence(parts.artifacts.native).run
                # Reconstruct expected accounting directly from original bytes.
                # There is no incoming execution object to reconstruct twice.
                validate_sealed_capture_receipt(
                    receipt,
                    permit,
                    parts.artifacts,
                    expected_deadline_ns=run.to_dict()["parent_deadline_ns"],
                )
                return
            if type(parts.artifacts) is not tuple:
                raise ValueError("legacy camera evidence must be the exact native pair")
            run = validate_camera_activation_evidence(parts.artifacts).run
            # Original result reasons remain untouched. Deriving the expected
            # native receipt also verifies whether counts are truly unavailable.
            validate_camera_activation_receipt(
                receipt,
                permit,
                parts.artifacts,
                expected_deadline_ns=run.to_dict()["parent_deadline_ns"],
            )
        except (ValueError, TypeError) as exc:
            raise M1CommissioningPersistenceError(
                "camera receipt disagrees with original native accounting"
            ) from exc

    def retain_camera_activation_evidence(
        self,
        permit: ExactOperationPermit,
        evidence: tuple[CameraActivationArtifact, ...] | SealedCameraCaptureEvidence,
    ) -> None:
        """Publish bounded original parts, then the index; never retry/overwrite."""
        from .camera_activation_campaign_contract import (
            validate_camera_activation_binding,
        )
        from .camera_activation_evidence_parts import encode_camera_evidence_parts
        from .camera_sealed_capture_contract import (
            is_sealed_capture,
            validate_sealed_capture_binding,
        )
        from .camera_sealed_capture_evidence import (
            encode_sealed_capture_parts,
            SealedCameraCaptureEvidence,
        )

        if (
            self._domain is not _PHYSICAL_CAMERA_DOMAIN
            or self._require_permit(permit.attempt_id) != permit
            or not self._retention_authorized
        ):
            raise M1CommissioningPersistenceError(
                "camera retention requires exact acknowledged consumed permit"
            )
        latest = self._attempts.snapshot().latest_event(permit.attempt_id)
        if latest is None or latest.state is not AttemptState.EFFECT_ARMED:
            raise M1CommissioningPersistenceError(
                "camera parts require the armed predecessor"
            )
        if is_sealed_capture(permit):
            if type(evidence) is not SealedCameraCaptureEvidence:
                raise ValueError("checksum-bearing collection required")
            validate_sealed_capture_binding(permit, evidence)
            encoded = encode_sealed_capture_parts(evidence)
        else:
            if type(evidence) is not tuple:
                raise ValueError("legacy camera evidence must be the exact native pair")
            validate_camera_activation_binding(permit, evidence)
            encoded = encode_camera_evidence_parts(evidence)
        existing = self._audit_records(include_family=True)
        if any(part.filename in existing for part in encoded):
            raise M1CommissioningPersistenceError(
                "camera publication is one-use; retain partial originals for review"
            )
        framed = [self._frame_record(part.kind, part.data()) for part in encoded]
        # Reserve the existing maximum for each of the two lifecycle receipts
        # and one terminal result. Do not consume the global family's last bytes
        # with diagnostics and leave no room to record the outcome.
        if (
            len(existing) + len(framed) + 3 > MAX_RECORDS
            or sum(len(canonical_json_bytes(record)) for record in existing.values())
            + sum(len(canonical_json_bytes(record)) for record in framed)
            + 3 * MAX_RECORD_BYTES
            > MAX_RECORD_TOTAL_BYTES
        ):
            raise M1CommissioningPersistenceError(
                "camera evidence exceeds shared family publication budget"
            )
        for part, expected in zip(encoded, framed):
            if self._write_record(part.filename, part.kind, part.data()) != expected:
                raise M1CommissioningPersistenceError("camera publication mismatch")
        persisted = self._audit_records()
        parts = self._camera_activation_parts(permit, persisted)
        if not parts.complete or parts.artifacts != evidence:
            raise M1CommissioningPersistenceError("camera evidence readback mismatch")

    def read_camera_activation_evidence(
        self, attempt_id: str
    ) -> tuple[CameraActivationArtifact, ...] | SealedCameraCaptureEvidence:
        """Audited, lease-scoped private bytes; incomplete records stay unavailable."""
        records = self._audit_records()
        permits = [
            record["data"]["permit"]
            for name, record in records.items()
            if name.startswith("request-")
            and record["data"]["attempt_id"] == attempt_id
        ]
        if len(permits) != 1:
            raise M1CommissioningPersistenceError("camera original permit is missing")
        permit = _decode_domain_permit(permits[0], self._domain)
        parts = self._camera_activation_parts(permit, records)
        if not parts.complete or parts.artifacts is None:
            raise M1CommissioningPersistenceError("camera evidence is incomplete")
        return parts.artifacts

    def retain_campaign_evidence(
        self,
        permit: ExactOperationPermit,
        evidence: tuple[CampaignEvidence, ...],
    ) -> None:
        if (
            self._require_permit(permit.attempt_id) != permit
            or not self._retention_authorized
        ):
            raise M1CommissioningPersistenceError(
                "retention requires exact acknowledged consumed permit"
            )
        latest = self._attempts.snapshot().latest_event(permit.attempt_id)
        if latest is None or latest.state is not AttemptState.EFFECT_ARMED:
            raise M1CommissioningPersistenceError(
                "full evidence must be retained from the armed predecessor"
            )
        validate_campaign_evidence(evidence)
        record = self._write_record(
            f"evidence-{permit.attempt_id}-retained.json",
            "CAMPAIGN_EVIDENCE",
            {
                "attempt_id": permit.attempt_id,
                "permit_sha256": permit.permit_sha256,
                "evidence": [
                    {
                        "schema": item.schema,
                        "label": item.label,
                        "payload_bytes": len(item.payload),
                        "payload_sha256": item.payload_sha256,
                        "payload_base64": base64.b64encode(item.payload).decode(
                            "ascii"
                        ),
                    }
                    for item in evidence
                ],
            },
        )
        persisted = self._read_records().get(
            f"evidence-{permit.attempt_id}-retained.json"
        )
        if (
            persisted != record
            or self._decode_campaign_evidence(permit, persisted) != evidence
        ):
            raise M1CommissioningPersistenceError(
                "retained campaign evidence readback mismatch"
            )

    def read_campaign_permit(self, attempt_id: str) -> ExactOperationPermit:
        """Audited retained identity only; restarting cannot redeem this permit."""
        records = self._audit_records()
        matches = [
            record["data"]["permit"]
            for name, record in records.items()
            if name.startswith("request-")
            and record["data"]["attempt_id"] == attempt_id
        ]
        if len(matches) != 1:
            raise M1CommissioningPersistenceError(
                "retained campaign permit is missing or ambiguous"
            )
        return _decode_domain_permit(matches[0], self._domain)

    def read_campaign_evidence(self, attempt_id: str) -> tuple[CampaignEvidence, ...]:
        """Lease-scoped audited private bytes; never a public log/status API."""
        records = self._audit_records()
        matches = [
            record["data"]["permit"]
            for name, record in records.items()
            if name.startswith("request-")
            and record["data"]["attempt_id"] == attempt_id
        ]
        record = records.get(f"evidence-{attempt_id}-retained.json")
        if len(matches) != 1 or record is None:
            raise M1CommissioningPersistenceError(
                "retained campaign evidence is missing or ambiguous"
            )
        return self._decode_campaign_evidence(
            _decode_domain_permit(matches[0], self._domain), record
        )

    def transition(
        self, attempt_id: str, state: AttemptState, receipt: WorkerReceipt | None
    ) -> None:
        permit = self._require_permit(attempt_id)
        allowed = {
            AttemptState.ABORTED_PRE_EFFECT,
            AttemptState.EFFECT_OBSERVED,
            AttemptState.CLEANUP_CONFIRMED,
            AttemptState.SEALED_KNOWN,
        }
        if state not in allowed:
            raise M1CommissioningPersistenceError(
                "transition is outside the closed coordinator boundary"
            )
        if state in {AttemptState.EFFECT_OBSERVED, AttemptState.CLEANUP_CONFIRMED}:
            self._validate_receipt(permit, receipt)
            assert isinstance(receipt, WorkerReceipt)
            self._write_record(
                f"receipt-{attempt_id}-{state.value.lower()}.json",
                "CAMPAIGN_RECEIPT",
                {
                    "attempt_id": attempt_id,
                    "permit_sha256": permit.permit_sha256,
                    "state": state.value,
                    "receipt": asdict(receipt),
                },
            )
        if state is AttemptState.SEALED_KNOWN:
            records = self._read_records()
            result = records.get(f"result-{attempt_id}-sealed_known.json")
            if (
                result is None
                or result["data"].get("permit_sha256") != permit.permit_sha256
            ):
                raise M1CommissioningPersistenceError(
                    "known seal requires retained exact result evidence first"
                )
            if self._requires_retained_evidence(permit):
                record = records.get(f"evidence-{attempt_id}-retained.json")
                if record is None or not isinstance(receipt, WorkerReceipt):
                    raise M1CommissioningPersistenceError(
                        "known seal requires retained full campaign evidence"
                    )
                self._match_retained_campaign(permit, receipt, records)
        self._attempts.transition(
            attempt_id, state, self._quarantine, occurred_at_ns=time.time_ns()
        )

    @staticmethod
    def _decode_receipt(value: object) -> WorkerReceipt:
        try:
            receipt = _exact_dataclass(value, WorkerReceipt)
            receipt["effect_certainty"] = EffectCertainty(receipt["effect_certainty"])
            receipt["final_power_state"] = ObservedPowerState(
                receipt["final_power_state"]
            )
            if type(receipt["evidence_sha256s"]) is not list:
                raise M1CommissioningPersistenceError(
                    "stored evidence digest vector must be an array"
                )
            receipt["evidence_sha256s"] = tuple(receipt["evidence_sha256s"])
            return WorkerReceipt(**receipt)
        except (ValueError, TypeError) as exc:
            raise M1CommissioningPersistenceError("malformed retained receipt") from exc

    def _validate_receipt(
        self,
        permit: ExactOperationPermit,
        receipt: WorkerReceipt | None,
        *,
        domain: _PersistenceDomain | None = None,
    ) -> None:
        domain = self._domain if domain is None else domain
        _require_domain_permit(permit, domain)
        if (
            not isinstance(receipt, WorkerReceipt)
            or receipt.attempt_id != permit.attempt_id
            or receipt.permit_sha256 != permit.permit_sha256
            or receipt.worker_executable_sha256
            != permit.registration.worker_executable_sha256
            or receipt.selected_identity_sha256
            != permit.admission.selected_identity_sha256
            or receipt.composition != domain.composition
            or receipt.effect_certainty is not EffectCertainty.CONFIRMED
            or receipt.cleanup_confirmed is not True
            or not isinstance(receipt.final_power_state, ObservedPowerState)
            or (
                domain.mode is CommissioningMode.PHYSICAL_DIAGNOSTIC
                and receipt.final_power_state is not ObservedPowerState.UNKNOWN
            )
            or (
                permit.envelope is not None
                and receipt.final_power_state is not ObservedPowerState.DEENERGIZED
            )
        ):
            raise M1CommissioningPersistenceError(
                "receipt is not bound to the exact diagnostic campaign"
            )
        for name, maximum in (
            ("opens", "maximum_opens"),
            ("reads", "maximum_reads"),
            ("writes", "maximum_writes"),
            ("frames", "maximum_frames"),
            ("closes", "maximum_closes"),
            ("output_bytes", "maximum_output_bytes"),
        ):
            count = getattr(receipt, name)
            if type(count) is not int or not 0 <= count <= getattr(
                permit.registration.budget, maximum
            ):
                raise M1CommissioningPersistenceError(
                    "receipt exceeds its exact campaign budget"
                )
        if (
            type(receipt.evidence_sha256s) is not tuple
            or len(receipt.evidence_sha256s) > 64
            or any(
                type(digest) is not str
                or _HASH.fullmatch(digest) is None
                or digest == "0" * 64
                for digest in receipt.evidence_sha256s
            )
        ):
            raise M1CommissioningPersistenceError(
                "receipt evidence hashes are malformed"
            )

    def retain_result(self, result: AttemptResult) -> None:
        if not isinstance(result, AttemptResult):
            raise M1CommissioningPersistenceError(
                "result must be a typed attempt result"
            )
        permit = self._require_permit(result.attempt_id)
        if (
            result.permit_sha256 != permit.permit_sha256
            or result.composition != self._domain.composition
            or result.physical_authority != "NONE"
            or result.state
            not in {
                AttemptState.SEALED_KNOWN,
                AttemptState.SEALED_UNCERTAIN,
                AttemptState.ABORTED_PRE_EFFECT,
            }
        ):
            raise M1CommissioningPersistenceError(
                "result exceeds the diagnostic boundary"
            )
        latest = self._attempts.snapshot().latest_event(result.attempt_id)
        required = (
            AttemptState.CLEANUP_CONFIRMED
            if result.state is AttemptState.SEALED_KNOWN
            else result.state
        )
        if latest is None or latest.state is not required:
            raise M1CommissioningPersistenceError(
                "result has no matching committed lifecycle predecessor"
            )
        if result.state is AttemptState.SEALED_KNOWN:
            if result.reason_codes or result.quarantine_latched is not False:
                raise M1CommissioningPersistenceError(
                    "known result cannot contain unresolved reasons/quarantine"
                )
            self._validate_receipt(permit, result.receipt)
            if self._requires_retained_evidence(permit):
                records = self._read_records()
                record = records.get(f"evidence-{permit.attempt_id}-retained.json")
                if record is None or not isinstance(result.receipt, WorkerReceipt):
                    raise M1CommissioningPersistenceError(
                        "known result requires retained full campaign evidence"
                    )
                self._match_retained_campaign(permit, result.receipt, records)
        elif result.state is AttemptState.ABORTED_PRE_EFFECT and (
            result.receipt is not None or result.quarantine_latched is not False
        ):
            raise M1CommissioningPersistenceError(
                "aborted result cannot claim observed effects"
            )
        elif (
            result.state is AttemptState.SEALED_UNCERTAIN
            and result.quarantine_latched is not True
        ):
            raise M1CommissioningPersistenceError(
                "uncertain result must retain its quarantine latch"
            )
        self._write_record(
            f"result-{result.attempt_id}-{result.state.value.lower()}.json",
            "CAMPAIGN_RESULT",
            {
                "attempt_id": result.attempt_id,
                "permit_sha256": result.permit_sha256,
                "result": asdict(result),
            },
        )

    def seal_uncertain(self, attempt_id: str, reason_codes: tuple[str, ...]) -> None:
        self._require_permit(attempt_id)
        latest = self._attempts.snapshot().latest_event(attempt_id)
        if latest is None or latest.state not in {
            AttemptState.EFFECT_ARMED,
            AttemptState.EFFECT_OBSERVED,
            AttemptState.CLEANUP_CONFIRMED,
        }:
            # A torn publication/suffix must remain held for M1 recovery. Never
            # invent an armed transition or rewrite a terminal known result.
            raise M1CommissioningPersistenceError(
                "uncertain state needs review; no valid committed armed predecessor"
            )
        self._attempts.transition(
            attempt_id,
            AttemptState.SEALED_UNCERTAIN,
            self._quarantine,
            occurred_at_ns=time.time_ns(),
        )
        self._quarantine.latch_uncertain_attempt(
            self._attempts, attempt_id, occurred_at_ns=time.time_ns()
        )


class M1RehearsalTransaction(_M1CoordinatorTransaction):
    """Historical rehearsal-only facade over the closed shared mechanics."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            **kwargs, domain=_REHEARSAL_DOMAIN, facts_type=RehearsalAdmissionFacts
        )


class M1CommissioningPersistence:
    """Concrete lease-owning core adapter plus safe reviewed-stage operations."""

    composition = INCAPABLE_COMPOSITION

    def __init__(
        self,
        runtime: "PhysicalOnboardingM1Runtime",
        *,
        workspace_source_sha256: str,
        admission_facts: FactsProvider,
    ) -> None:
        from rocell.application.physical_onboarding_m1 import (
            PhysicalOnboardingM1Runtime,
        )

        if (
            not isinstance(runtime, PhysicalOnboardingM1Runtime)
            or _CELL.fullmatch(runtime.cell.cell_id) is None
        ):
            raise M1CommissioningPersistenceError(
                "adapter requires an isolated actual M1 rehearsal cell"
            )
        if runtime.source_binding_sha256 != rehearsal_source_binding(
            workspace_source_sha256
        ):
            raise M1CommissioningPersistenceError(
                "M1 source is not domain-separated from the supplied workspace"
            )
        if not callable(admission_facts):
            raise M1CommissioningPersistenceError(
                "server-pinned admission facts callback is required"
            )
        self._runtime = runtime
        self._admission_facts = admission_facts

    def snapshot(self, session_id: str) -> V2SessionSnapshot:
        snapshot = self._runtime.session_snapshot(session_id)
        if snapshot.header.mode != "REHEARSAL":
            raise M1CommissioningPersistenceError(
                "physical diagnostic sessions cannot be used for rehearsal"
            )
        return snapshot

    def verification(self, session_id: str) -> "M1RuntimeVerification":
        self.snapshot(session_id)
        return self._runtime.verify(session_id)

    @contextmanager
    def stage_transaction(
        self, session_id: str, *, expected_challenge_sha256: str
    ) -> Iterator[M1RehearsalTransaction]:
        with self._runtime.rehearsal_transaction(
            session_id, expected_challenge_sha256=expected_challenge_sha256
        ) as transaction:
            transaction._audit_records()
            yield transaction

    @contextmanager
    def transaction(
        self, leases: tuple[LeaseSpec, ...]
    ) -> Iterator[M1RehearsalTransaction]:
        if (
            type(leases) is not tuple
            or len(leases) < 2
            or any(not isinstance(spec, LeaseSpec) for spec in leases)
            or leases[0] != LeaseSpec(LeaseLevel.CELL, self._runtime.cell.cell_id)
            or leases[1].level is not LeaseLevel.SESSION
            or any(
                spec.resource_id != self._runtime.cell.cell_id for spec in leases[2:]
            )
        ):
            raise M1CommissioningPersistenceError(
                "core requested a different cell/session resource binding"
            )
        with self._runtime.rehearsal_transaction(
            leases[1].resource_id,
            device_levels=tuple(spec.level for spec in leases[2:]),
        ) as transaction:
            if transaction.held_leases != leases:
                raise M1CommissioningPersistenceError(
                    "actual OS lease set differs from the requested core lease set"
                )
            transaction._facts_provider = self._admission_facts
            yield transaction
