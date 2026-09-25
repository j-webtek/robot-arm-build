"""Original M1 records for one phase-bound physical USB presence observation.

Only server composition supplies current, independently reconstructed original
facts. This module persists their exact bytes and consumed-permit ownership; it
does not approve a runtime, acquire a phase, launch a helper or infer absence.
Sibling camera/query records stay in the complete cell-global audit.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import json
import re
from typing import Any, TYPE_CHECKING, cast

from .cell_commissioning_coordinator import (
    AttemptResult,
    CampaignEvidence,
    ExactOperationPermit,
    PHYSICAL_USB_PRESENCE_COMPOSITION,
    RegisteredActionRequest,
    UsbPresenceAdmissionSnapshot,
)
from .commissioning_camera_persistence import (
    M1PhysicalCameraTransaction,
    physical_camera_source_binding,
)
from .commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
    _HASH,
    _M1AdmissionFacts,
    _M1CoordinatorTransaction,
    _PHYSICAL_USB_PRESENCE_DOMAIN,
    _decode_domain_permit,
    _exact_dataclass,
    _freeze_document,
    _sha256,
)
from .physical_onboarding import (
    EvidenceReference,
    PhysicalOnboardingStage,
    _parse_evidence_reference,
)
from .physical_onboarding_attempts import (
    AttemptState,
    canonical_json_bytes,
)
from .physical_onboarding_leases import LeaseLevel, LeaseSpec
from .physical_onboarding_v2 import (
    V2JournalEvent,
    V2SessionSnapshot,
    V2StageState,
    _parse_event,
)
from .physical_usb_presence_binding import UsbPresencePhaseBinding
from .usb_presence_stage_policy import UsbPresenceStagePolicy
from rocell.providers.windows.usb_presence_review import UsbPresenceRuntimeReview

if TYPE_CHECKING:
    from .physical_onboarding_m1 import (
        PhysicalOnboardingM1Runtime,
        M1RuntimeVerification,
    )

RECORD_SCHEMA = _PHYSICAL_USB_PRESENCE_DOMAIN.record_schema


def decode_physical_usb_presence_permit(value: object) -> ExactOperationPermit:
    """Read retained permit data; this never re-admits or renews a saved permit."""
    return _decode_domain_permit(value, _PHYSICAL_USB_PRESENCE_DOMAIN)


def verify_usb_presence_admission_evidence(
    value: object, admission: object, *, permit: ExactOperationPermit | None = None
) -> None:
    """Join full frozen documents to their independently ledger-bound snapshot."""
    if (
        type(value) is not dict
        or set(value)
        != {
            "stage_policy",
            "hazard_assessment",
            "configuration_epochs",
            "selected_identity",
            "runtime_review",
            "runtime_review_reference",
            "runtime_review_event",
        }
        or type(admission) is not UsbPresenceAdmissionSnapshot
    ):
        raise M1CommissioningPersistenceError(
            "presence admission evidence schema differs"
        )
    try:
        policy = UsbPresenceStagePolicy(_freeze_document(value["stage_policy"]))
        binding = UsbPresencePhaseBinding(_freeze_document(value["selected_identity"]))
        original = binding.to_dict()["binding"]
        review = UsbPresenceRuntimeReview(_freeze_document(value["runtime_review"]))
        reviewed = review.to_dict()
        reference = _parse_evidence_reference(value["runtime_review_reference"])
        event = _parse_event(value["runtime_review_event"])
        epochs = value["configuration_epochs"]
        if (
            type(epochs) is not list
            or len(epochs) != 8
            or policy.sha256 != admission.usb_presence_policy_sha256
            or _sha256(_freeze_document(value["hazard_assessment"]))
            != admission.hazard_assessment_sha256
            or tuple(_sha256(_freeze_document(item)) for item in epochs)
            != admission.configuration_epoch_hashes
            or binding.sha256 != admission.selected_identity_sha256
            or binding.sha256 != admission.phase_binding_sha256
            or original["cell_id"] != admission.cell_id
            or original["session_id"] != admission.session_id
            or physical_camera_source_binding(original["source_sha256"])
            != admission.source_binding_sha256
            or review.sha256 != admission.runtime_review_sha256
            or reviewed["phase_binding_sha256"] != binding.sha256
            or reviewed["usb_presence_policy_sha256"] != policy.sha256
            or any(
                reviewed[key] != original[key]
                for key in (
                    "source_sha256",
                    "cell_id",
                    "session_id",
                    "header_sha256",
                    "trial_id",
                )
            )
            or reviewed["target_instance_id_sha256"]
            != binding.to_dict()["target"]["physical_usb_instance_id_sha256"]
            or reviewed["reviewed_at_ns"] < binding.to_dict()["not_before_utc_ns"]
            or reference.stage is not PhysicalOnboardingStage.CAMERA_IDENTITY
            or reference.payload_sha256 != review.sha256
            or reference.payload_bytes != len(review.payload)
            or event.session_id != original["session_id"]
            or event.session_header_sha256 != original["header_sha256"]
            or event.stage is not PhysicalOnboardingStage.CAMERA_IDENTITY
            or event.previous_state is not V2StageState.REVIEW_PENDING
            or event.state is not V2StageState.BLOCKED
            or event.detail_code
            != "CAMERA_USB_PRESENCE_RUNTIME_REVIEWED_"
            + original["trial_id"][9:].upper()
            or event.evidence != (reference,)
            or event.occurred_at_ns < reviewed["reviewed_at_ns"]
        ):
            raise M1CommissioningPersistenceError(
                "presence original admission hash/context joins differ"
            )
        if permit is not None and (
            type(permit) is not ExactOperationPermit
            or permit.admission != admission
            or permit.registration.operation_sha256 != reviewed["operation_sha256"]
            or permit.registration.worker_executable_sha256 != reviewed["helper_sha256"]
        ):
            raise M1CommissioningPersistenceError(
                "presence permit differs from original reviewed operation/runtime"
            )
    except (TypeError, ValueError, KeyError) as exc:
        raise M1CommissioningPersistenceError(
            "invalid retained presence admission evidence"
        ) from exc


@dataclass(frozen=True, slots=True)
class PhysicalUsbPresenceAdmissionFacts(_M1AdmissionFacts):
    """Frozen server-owned facts; pure binding validation is not original trust."""

    stage_policy: UsbPresenceStagePolicy = field(kw_only=True)
    phase_binding: UsbPresencePhaseBinding = field(kw_only=True)
    runtime_review: UsbPresenceRuntimeReview = field(kw_only=True)
    runtime_review_reference: EvidenceReference = field(kw_only=True)
    runtime_review_event: V2JournalEvent = field(kw_only=True)
    _policy: bytes = field(init=False, repr=False)
    _phase: bytes = field(init=False, repr=False)
    _review: bytes = field(init=False, repr=False)
    _review_reference: bytes = field(init=False, repr=False)
    _review_event: bytes = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _M1AdmissionFacts.__post_init__(self)
        if (
            type(self.stage_policy) is not UsbPresenceStagePolicy
            or type(self.phase_binding) is not UsbPresencePhaseBinding
            or type(self.runtime_review) is not UsbPresenceRuntimeReview
            or type(self.runtime_review_reference) is not EvidenceReference
            or type(self.runtime_review_event) is not V2JournalEvent
            or self.envelope is not None
            or self._identity is None
        ):
            raise M1CommissioningPersistenceError(
                "presence facts need exact policy/binding and no energy envelope"
            )
        policy = UsbPresenceStagePolicy(self.stage_policy.payload)
        binding = UsbPresencePhaseBinding(self.phase_binding.payload)
        if binding.payload != self._identity:
            raise M1CommissioningPersistenceError(
                "presence selected identity must be the exact original phase binding"
            )
        object.__setattr__(self, "stage_policy", policy)
        object.__setattr__(self, "phase_binding", binding)
        object.__setattr__(self, "_policy", policy.payload)
        object.__setattr__(self, "_phase", binding.payload)
        review = UsbPresenceRuntimeReview(self.runtime_review.payload)
        reference = _parse_evidence_reference(self.runtime_review_reference.to_dict())
        event = _parse_event(self.runtime_review_event.to_dict())
        object.__setattr__(self, "runtime_review", review)
        object.__setattr__(self, "runtime_review_reference", reference)
        object.__setattr__(self, "runtime_review_event", event)
        object.__setattr__(self, "_review", review.payload)
        object.__setattr__(
            self, "_review_reference", canonical_json_bytes(reference.to_dict())
        )
        object.__setattr__(self, "_review_event", canonical_json_bytes(event.to_dict()))

    def retained_documents(self) -> dict[str, Any]:
        return {
            "stage_policy": json.loads(self._policy),
            "hazard_assessment": json.loads(self._hazard),
            "configuration_epochs": [json.loads(item) for item in self._epochs],
            "selected_identity": json.loads(self._phase),
            "runtime_review": json.loads(self._review),
            "runtime_review_reference": json.loads(self._review_reference),
            "runtime_review_event": json.loads(self._review_event),
        }


PhysicalUsbPresenceFactsProvider = Callable[
    [RegisteredActionRequest, V2SessionSnapshot], PhysicalUsbPresenceAdmissionFacts
]


class M1PhysicalUsbPresenceTransaction(_M1CoordinatorTransaction):
    """Separate records and exact CELL/SESSION[/CAMERA] ownership, no ARM lease."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            **kwargs,
            domain=_PHYSICAL_USB_PRESENCE_DOMAIN,
            facts_type=PhysicalUsbPresenceAdmissionFacts,
        )
        snapshot = self.snapshot()
        base = (
            LeaseSpec(LeaseLevel.CELL, snapshot.header.cell_id),
            LeaseSpec(LeaseLevel.SESSION, snapshot.header.session_id),
        )
        if self.held_leases not in (
            base,
            (*base, LeaseSpec(LeaseLevel.CAMERA, snapshot.header.cell_id)),
        ):
            raise M1CommissioningPersistenceError(
                "presence requires camera-only leases"
            )

    # Reuse the original bounded package reader, not a path-based alternative.
    read_stage_evidence = M1PhysicalCameraTransaction.read_stage_evidence
    read_camera_evidence = cast(
        Callable[[Any, EvidenceReference], bytes],
        M1PhysicalCameraTransaction.read_camera_evidence,
    )
    _read_original_evidence = M1PhysicalCameraTransaction._read_original_evidence

    def _fresh_admission(self, request: RegisteredActionRequest) -> tuple[
        PhysicalUsbPresenceAdmissionFacts,
        UsbPresenceAdmissionSnapshot,
        M1RuntimeVerification,
    ]:
        facts, base, verified = super()._fresh_admission(request)
        if type(facts) is not PhysicalUsbPresenceAdmissionFacts:
            raise M1CommissioningPersistenceError("exact presence facts required")
        # One fresh post-admission snapshot supplies both immutable header and
        # committed review/request context in this call. Do not load the same
        # complete evidence tree twice around only pure document validation.
        # The camera package reader below still performs its own fresh read,
        # full family audit and pre/post byte checks before returning evidence.
        snapshot = self.snapshot()
        # The selected original cannot be transplanted into a different header
        # even if a test/provider reuses the same cell/session identifiers.
        if (
            UsbPresencePhaseBinding(facts._phase).to_dict()["binding"]["header_sha256"]
            != snapshot.header.header_sha256
        ):
            raise M1CommissioningPersistenceError(
                "presence original session header differs"
            )
        admission = UsbPresenceAdmissionSnapshot(
            **asdict(base),
            usb_presence_policy_sha256=UsbPresenceStagePolicy(facts._policy).sha256,
            phase_binding_sha256=UsbPresencePhaseBinding(facts._phase).sha256,
            runtime_review_sha256=UsbPresenceRuntimeReview(facts._review).sha256,
        )
        verify_usb_presence_admission_evidence(facts.retained_documents(), admission)
        # Metadata equality alone is insufficient: the original bytes and review
        # event must exist in this owned store, followed by an explicit request.
        reference = _parse_evidence_reference(json.loads(facts._review_reference))
        event = _parse_event(json.loads(facts._review_event))
        events = snapshot.committed_events
        original = UsbPresencePhaseBinding(facts._phase).to_dict()["binding"]
        if (
            event not in events
            or reference not in snapshot.evidence
            or self.read_camera_evidence(reference) != facts._review
            or not events
            or events[-1].sequence != event.sequence + 1
            or events[-1].stage is not PhysicalOnboardingStage.CAMERA_IDENTITY
            or events[-1].previous_state is not V2StageState.BLOCKED
            or events[-1].state is not V2StageState.WAITING_OPERATOR
            or events[-1].detail_code
            != "CAMERA_USB_PRESENCE_QUERY_REQUESTED_" + original["trial_id"][9:].upper()
            or events[-1].evidence != (reference,)
        ):
            raise M1CommissioningPersistenceError(
                "presence requires authentic original review and explicit current request"
            )
        return facts, admission, verified

    def _validate_admission_subjects(self, permit: ExactOperationPermit) -> None:
        # Called by the original owner after its fresh read and before any
        # reservation. Do not repeat that read or renew the original deadline.
        if type(self._facts) is not PhysicalUsbPresenceAdmissionFacts:
            raise M1CommissioningPersistenceError(
                "presence original reviewed facts missing"
            )
        verify_usb_presence_admission_evidence(
            self._facts.retained_documents(), self._admission, permit=permit
        )

    def revalidate_consumed_permit(self, permit: ExactOperationPermit) -> None:
        super().revalidate_consumed_permit(permit)
        if type(self._facts) is not PhysicalUsbPresenceAdmissionFacts:
            raise M1CommissioningPersistenceError(
                "presence original reviewed facts missing"
            )
        verify_usb_presence_admission_evidence(
            self._facts.retained_documents(), permit.admission, permit=permit
        )

    def _reservation_evidence(self) -> dict[str, Any]:
        if type(self._facts) is not PhysicalUsbPresenceAdmissionFacts:
            raise M1CommissioningPersistenceError(
                "presence reservation lacks exact facts"
            )
        result = self._facts.retained_documents()
        verify_usb_presence_admission_evidence(result, self._admission)
        return {"admission_evidence": result}

    def read_campaign_admission_evidence(self, attempt_id: str) -> dict[str, Any]:
        """Full detached documents after the complete sibling-domain audit."""
        permit = self.read_campaign_permit(attempt_id)
        records = self._audit_records()
        rows = [
            record["data"]["admission_evidence"]
            for name, record in records.items()
            if name.startswith("request-")
            and record["data"]["attempt_id"] == permit.attempt_id
        ]
        if len(rows) != 1:
            raise M1CommissioningPersistenceError(
                "presence admission evidence missing or ambiguous"
            )
        return json.loads(canonical_json_bytes(rows[0]))

    def read_optional_campaign_evidence(
        self, attempt_id: str
    ) -> tuple[CampaignEvidence, ...]:
        """Preserve a genuine terminal failure that retained no worker artifact.

        The generic evidence reader remains strict. Absence here is not an
        empty successful observation: it is accepted only after an audited
        original terminal with no receipt. Present artifacts still use the
        existing full-byte reader, and corruption/ambiguity must propagate.
        """
        self._check_scope()
        terminal = self.read_campaign_result(attempt_id)
        records = self._audit_records()
        if f"evidence-{attempt_id}-retained.json" in records:
            return self.read_campaign_evidence(attempt_id)
        if terminal.receipt is not None or terminal.state not in {
            AttemptState.SEALED_UNCERTAIN,
            AttemptState.ABORTED_PRE_EFFECT,
        }:
            raise M1CommissioningPersistenceError(
                "presence terminal requires missing original campaign evidence"
            )
        self._check_scope()
        return ()

    def read_campaign_result(self, attempt_id: str) -> AttemptResult:
        """Never promote an unsealed result document to terminal known effects."""
        self._check_scope()
        if (
            type(attempt_id) is not str
            or re.fullmatch(r"attempt-[0-9a-f]{32}", attempt_id) is None
        ):
            raise M1CommissioningPersistenceError("exact retained attempt ID required")
        leases = self.held_leases
        records = self._audit_records()
        latest = self._attempts.snapshot().latest_event(attempt_id)
        if latest is None or latest.state not in {
            AttemptState.SEALED_KNOWN,
            AttemptState.SEALED_UNCERTAIN,
            AttemptState.ABORTED_PRE_EFFECT,
        }:
            raise M1CommissioningPersistenceError(
                "presence campaign has no durable terminal state"
            )
        requests = [
            record["data"]["permit"]
            for name, record in records.items()
            if name.startswith("request-")
            and record["data"]["attempt_id"] == attempt_id
        ]
        record = records.get(f"result-{attempt_id}-{latest.state.value.lower()}.json")
        if len(requests) != 1 or record is None:
            raise M1CommissioningPersistenceError(
                "presence terminal result missing or ambiguous"
            )
        permit = decode_physical_usb_presence_permit(requests[0])
        data = _exact_dataclass(record["data"]["result"], AttemptResult)
        if (
            latest.operation_binding_sha256 != permit.permit_sha256
            or latest.session_id != permit.request.session_id
            or latest.cell_id != permit.request.cell_id
            or latest.source_binding_sha256 != permit.admission.source_binding_sha256
            or data["state"] != latest.state.value
            or data["attempt_id"] != permit.attempt_id
            or data["permit_sha256"] != permit.permit_sha256
            or data["composition"] != PHYSICAL_USB_PRESENCE_COMPOSITION
            or data["physical_authority"] != "NONE"
        ):
            raise M1CommissioningPersistenceError(
                "presence result differs from terminal original attempt"
            )
        data["state"] = latest.state
        data["reason_codes"] = tuple(data["reason_codes"])
        if data["receipt"] is not None:
            receipt = self._decode_receipt(data["receipt"])
            if (
                receipt.attempt_id != permit.attempt_id
                or receipt.permit_sha256 != permit.permit_sha256
                or receipt.composition != PHYSICAL_USB_PRESENCE_COMPOSITION
                or receipt.worker_executable_sha256
                != permit.registration.worker_executable_sha256
                or receipt.selected_identity_sha256
                != permit.admission.selected_identity_sha256
            ):
                raise M1CommissioningPersistenceError(
                    "presence receipt differs from original permit"
                )
            data["receipt"] = receipt
        result = AttemptResult(**data)
        if (
            self._attempts.snapshot().latest_event(attempt_id) != latest
            or self.held_leases != leases
        ):
            raise M1CommissioningPersistenceError(
                "presence terminal state/leases changed during readback"
            )
        return result


class M1PhysicalUsbPresencePersistence:
    """Original camera namespace/source, distinct presence records and policy."""

    composition = PHYSICAL_USB_PRESENCE_COMPOSITION

    def __init__(
        self,
        runtime: PhysicalOnboardingM1Runtime,
        *,
        workspace_source_sha256: str,
        stage_policy: UsbPresenceStagePolicy,
        expected_usb_presence_policy_sha256: str,
        admission_facts: PhysicalUsbPresenceFactsProvider,
    ) -> None:
        from .physical_onboarding_m1 import PhysicalOnboardingM1Runtime

        if (
            type(runtime) is not PhysicalOnboardingM1Runtime
            or re.fullmatch(
                _PHYSICAL_USB_PRESENCE_DOMAIN.cell_pattern, runtime.cell.cell_id
            )
            is None
            or runtime.source_binding_sha256
            != physical_camera_source_binding(workspace_source_sha256)
            or type(stage_policy) is not UsbPresenceStagePolicy
            or type(expected_usb_presence_policy_sha256) is not str
            or _HASH.fullmatch(expected_usb_presence_policy_sha256) is None
            or not callable(admission_facts)
        ):
            raise M1CommissioningPersistenceError(
                "presence persistence requires original namespace/source/policy/facts"
            )
        self._policy = UsbPresenceStagePolicy(stage_policy.payload)
        if self._policy.sha256 != expected_usb_presence_policy_sha256:
            raise M1CommissioningPersistenceError(
                "presence policy differs from independent server pin"
            )
        self._runtime, self._facts = runtime, admission_facts

    def _checked_facts(
        self, request: RegisteredActionRequest, snapshot: V2SessionSnapshot
    ) -> PhysicalUsbPresenceAdmissionFacts:
        facts = self._facts(request, snapshot)
        if (
            type(facts) is not PhysicalUsbPresenceAdmissionFacts
            or facts._policy != self._policy.payload
        ):
            raise M1CommissioningPersistenceError(
                "presence current facts differ from pinned policy"
            )
        return facts

    def snapshot(self, session_id: str) -> V2SessionSnapshot:
        if (
            type(session_id) is not str
            or re.fullmatch(_PHYSICAL_USB_PRESENCE_DOMAIN.session_pattern, session_id)
            is None
        ):
            raise M1CommissioningPersistenceError(
                "original camera session namespace required"
            )
        snapshot = self._runtime.session_snapshot(session_id)
        if snapshot.header.mode != "PHYSICAL_DIAGNOSTIC":
            raise M1CommissioningPersistenceError("presence session mode differs")
        return snapshot

    def verification(self, session_id: str) -> M1RuntimeVerification:
        self.snapshot(session_id)
        return self._runtime.verify(session_id)

    @contextmanager
    def stage_transaction(
        self, session_id: str, *, expected_challenge_sha256: str
    ) -> Iterator[M1PhysicalUsbPresenceTransaction]:
        with self._runtime.physical_usb_presence_transaction(
            session_id, expected_challenge_sha256=expected_challenge_sha256
        ) as transaction:
            transaction._audit_records()
            yield transaction

    @contextmanager
    def transaction(
        self, leases: tuple[LeaseSpec, ...]
    ) -> Iterator[M1PhysicalUsbPresenceTransaction]:
        if (
            type(leases) is not tuple
            or len(leases) != 3
            or any(type(spec) is not LeaseSpec for spec in leases)
            or leases[0] != LeaseSpec(LeaseLevel.CELL, self._runtime.cell.cell_id)
            or leases[1].level is not LeaseLevel.SESSION
            or leases[2] != LeaseSpec(LeaseLevel.CAMERA, self._runtime.cell.cell_id)
        ):
            raise M1CommissioningPersistenceError(
                "presence needs exact CELL/SESSION/CAMERA leases"
            )
        with self._runtime.physical_usb_presence_transaction(
            leases[1].resource_id, device_levels=(LeaseLevel.CAMERA,)
        ) as transaction:
            if transaction.held_leases != leases:
                raise M1CommissioningPersistenceError("actual presence leases differ")
            transaction._facts_provider = self._checked_facts
            yield transaction
