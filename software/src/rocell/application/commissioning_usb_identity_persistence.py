"""Policy-bound USB-query M1 storage in the original camera session.

This is storage/ownership, not an assertion that intake, a driver or a received
unit is qualified. Server composition supplies independently verified facts.
The legacy camera permit decoder and its stage-5/6 authority are unchanged.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import json
import re
from typing import Any, TYPE_CHECKING

from .cell_commissioning_coordinator import (
    AttemptResult,
    ExactOperationPermit,
    PHYSICAL_USB_IDENTITY_COMPOSITION,
    RegisteredActionRequest,
    UsbIdentityAdmissionSnapshot,
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
    _PHYSICAL_USB_IDENTITY_DOMAIN,
    _decode_domain_permit,
    _exact_dataclass,
    _freeze_document,
    _sha256,
)
from .physical_onboarding_attempts import AttemptState, canonical_json_bytes
from .physical_onboarding_leases import LeaseLevel, LeaseSpec
from .physical_onboarding_v2 import V2SessionSnapshot
from .usb_identity_stage_policy import UsbIdentityStagePolicy

if TYPE_CHECKING:
    from .physical_onboarding_m1 import (
        PhysicalOnboardingM1Runtime,
        M1RuntimeVerification,
    )

RECORD_SCHEMA = _PHYSICAL_USB_IDENTITY_DOMAIN.record_schema


def decode_physical_usb_identity_permit(value: object) -> ExactOperationPermit:
    """Strict original-data reconstruction only; never re-admits a saved permit."""
    return _decode_domain_permit(value, _PHYSICAL_USB_IDENTITY_DOMAIN)


def _verify_admission_evidence(value: object, admission: object) -> None:
    """Verify full retained facts against the independently ledger-bound permit."""
    if (
        type(value) is not dict
        or set(value)
        != {
            "stage_policy",
            "hazard_assessment",
            "configuration_epochs",
            "selected_identity",
        }
        or type(admission) is not UsbIdentityAdmissionSnapshot
    ):
        raise M1CommissioningPersistenceError("USB admission evidence schema differs")
    try:
        policy = UsbIdentityStagePolicy(_freeze_document(value["stage_policy"]))
        epochs = value["configuration_epochs"]
        if (
            type(epochs) is not list
            or len(epochs) != 8
            or policy.sha256 != admission.usb_query_policy_sha256
            or _sha256(_freeze_document(value["hazard_assessment"]))
            != admission.hazard_assessment_sha256
            or tuple(_sha256(_freeze_document(item)) for item in epochs)
            != admission.configuration_epoch_hashes
            or _sha256(_freeze_document(value["selected_identity"]))
            != admission.selected_identity_sha256
        ):
            raise M1CommissioningPersistenceError(
                "USB original admission documents/hash joins differ"
            )
    except (TypeError, ValueError, KeyError) as exc:
        raise M1CommissioningPersistenceError(
            "invalid retained USB admission evidence"
        ) from exc


@dataclass(frozen=True, slots=True)
class PhysicalUsbIdentityAdmissionFacts(_M1AdmissionFacts):
    """Frozen server-owned facts; retained references are not caller approvals."""

    stage_policy: UsbIdentityStagePolicy = field(kw_only=True)
    _policy: bytes = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _M1AdmissionFacts.__post_init__(self)
        if (
            type(self.stage_policy) is not UsbIdentityStagePolicy
            or self.envelope is not None
            or self._identity is None
        ):
            raise M1CommissioningPersistenceError(
                "USB facts require exact policy/identity and no energy envelope"
            )
        policy = UsbIdentityStagePolicy(self.stage_policy.payload)
        object.__setattr__(self, "stage_policy", policy)
        object.__setattr__(self, "_policy", policy.payload)

    def retained_documents(self) -> dict[str, Any]:
        return {
            "stage_policy": json.loads(self._policy),
            "hazard_assessment": json.loads(self._hazard),
            "configuration_epochs": [json.loads(item) for item in self._epochs],
            "selected_identity": json.loads(self._identity or b"null"),
        }


PhysicalUsbIdentityFactsProvider = Callable[
    [RegisteredActionRequest, V2SessionSnapshot], PhysicalUsbIdentityAdmissionFacts
]


class M1PhysicalUsbIdentityTransaction(_M1CoordinatorTransaction):
    """Closed CELL/SESSION[/CAMERA] scope; shares the real camera-family audit."""

    def __init__(
        self,
        *,
        _fresh_snapshot_verification: (
            Callable[[], tuple[V2SessionSnapshot | None, M1RuntimeVerification]] | None
        ) = None,
        **kwargs: Any,
    ) -> None:
        self._fresh_snapshot_verification = _fresh_snapshot_verification
        super().__init__(
            **kwargs,
            domain=_PHYSICAL_USB_IDENTITY_DOMAIN,
            facts_type=PhysicalUsbIdentityAdmissionFacts,
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
                "USB identity requires camera-only leases"
            )

    def _admission_observation(
        self,
    ) -> tuple[V2SessionSnapshot, M1RuntimeVerification]:
        if self._fresh_snapshot_verification is None:
            return super()._admission_observation()
        return self._coherent_admission_observation(
            self._fresh_snapshot_verification,
            mismatch_message="fresh USB snapshot and runtime verification differ",
        )

    # Same exact original-package reader, not a second parser or path authority.
    read_stage_evidence = M1PhysicalCameraTransaction.read_stage_evidence
    read_camera_evidence = M1PhysicalCameraTransaction.read_camera_evidence
    _read_original_evidence = M1PhysicalCameraTransaction._read_original_evidence

    def _fresh_admission(self, request: RegisteredActionRequest) -> tuple[
        PhysicalUsbIdentityAdmissionFacts,
        UsbIdentityAdmissionSnapshot,
        M1RuntimeVerification,
    ]:
        facts, base, verified = super()._fresh_admission(request)
        if type(facts) is not PhysicalUsbIdentityAdmissionFacts:
            raise M1CommissioningPersistenceError("exact USB facts required")
        policy = UsbIdentityStagePolicy(facts._policy)
        admission = UsbIdentityAdmissionSnapshot(
            **asdict(base), usb_query_policy_sha256=policy.sha256
        )
        _verify_admission_evidence(facts.retained_documents(), admission)
        return facts, admission, verified

    def _reservation_evidence(self) -> dict[str, Any]:
        if type(self._facts) is not PhysicalUsbIdentityAdmissionFacts:
            raise M1CommissioningPersistenceError(
                "USB reservation has no exact admission facts"
            )
        result = self._facts.retained_documents()
        _verify_admission_evidence(result, self._admission)
        return {"admission_evidence": result}

    def read_campaign_admission_evidence(self, attempt_id: str) -> dict[str, Any]:
        """Detached full original facts after complete cross-domain ledger audit."""
        permit = self.read_campaign_permit(attempt_id)
        records = self._audit_records()
        selected = [
            record["data"]["admission_evidence"]
            for name, record in records.items()
            if name.startswith("request-")
            and record["data"]["attempt_id"] == permit.attempt_id
        ]
        if len(selected) != 1:
            raise M1CommissioningPersistenceError(
                "USB admission evidence missing or ambiguous"
            )
        return json.loads(canonical_json_bytes(selected[0]))

    def read_campaign_result(self, attempt_id: str) -> AttemptResult:
        """Exact terminal readback; a saved pre-seal result never implies success."""
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
                "USB campaign has no durable terminal state"
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
                "USB terminal result missing or ambiguous"
            )
        permit = decode_physical_usb_identity_permit(requests[0])
        data = _exact_dataclass(record["data"]["result"], AttemptResult)
        if (
            latest.operation_binding_sha256 != permit.permit_sha256
            or latest.session_id != permit.request.session_id
            or latest.cell_id != permit.request.cell_id
            or latest.source_binding_sha256 != permit.admission.source_binding_sha256
            or data["state"] != latest.state.value
            or data["attempt_id"] != permit.attempt_id
            or data["permit_sha256"] != permit.permit_sha256
            or data["composition"] != PHYSICAL_USB_IDENTITY_COMPOSITION
            or data["physical_authority"] != "NONE"
        ):
            raise M1CommissioningPersistenceError(
                "USB result differs from original terminal attempt"
            )
        data["state"] = latest.state
        data["reason_codes"] = tuple(data["reason_codes"])
        if data["receipt"] is not None:
            receipt = self._decode_receipt(data["receipt"])
            if (
                receipt.attempt_id != permit.attempt_id
                or receipt.permit_sha256 != permit.permit_sha256
                or receipt.composition != PHYSICAL_USB_IDENTITY_COMPOSITION
                or receipt.worker_executable_sha256
                != permit.registration.worker_executable_sha256
                or receipt.selected_identity_sha256
                != permit.admission.selected_identity_sha256
            ):
                raise M1CommissioningPersistenceError(
                    "USB terminal receipt differs from original permit"
                )
            data["receipt"] = receipt
        result = AttemptResult(**data)
        if (
            self._attempts.snapshot().latest_event(attempt_id) != latest
            or self.held_leases != leases
        ):
            raise M1CommissioningPersistenceError(
                "USB terminal state or leases changed during readback"
            )
        return result


class M1PhysicalUsbIdentityPersistence:
    """Same original camera header/source; distinct query records and policy."""

    composition = PHYSICAL_USB_IDENTITY_COMPOSITION

    def __init__(
        self,
        runtime: PhysicalOnboardingM1Runtime,
        *,
        workspace_source_sha256: str,
        stage_policy: UsbIdentityStagePolicy,
        expected_usb_query_policy_sha256: str,
        admission_facts: PhysicalUsbIdentityFactsProvider,
    ) -> None:
        from .physical_onboarding_m1 import PhysicalOnboardingM1Runtime

        if (
            type(runtime) is not PhysicalOnboardingM1Runtime
            or re.fullmatch(
                _PHYSICAL_USB_IDENTITY_DOMAIN.cell_pattern, runtime.cell.cell_id
            )
            is None
            or runtime.source_binding_sha256
            != physical_camera_source_binding(workspace_source_sha256)
            or type(stage_policy) is not UsbIdentityStagePolicy
            or type(expected_usb_query_policy_sha256) is not str
            or _HASH.fullmatch(expected_usb_query_policy_sha256) is None
            or not callable(admission_facts)
        ):
            raise M1CommissioningPersistenceError(
                "USB persistence requires exact original namespace/source/policy/facts"
            )
        self._policy = UsbIdentityStagePolicy(stage_policy.payload)
        if self._policy.sha256 != expected_usb_query_policy_sha256:
            raise M1CommissioningPersistenceError(
                "USB policy differs from independent server pin"
            )
        self._runtime, self._facts = runtime, admission_facts

    def _checked_facts(
        self, request: RegisteredActionRequest, snapshot: V2SessionSnapshot
    ) -> PhysicalUsbIdentityAdmissionFacts:
        facts = self._facts(request, snapshot)
        if (
            type(facts) is not PhysicalUsbIdentityAdmissionFacts
            or facts._policy != self._policy.payload
        ):
            raise M1CommissioningPersistenceError(
                "USB current facts differ from pinned policy"
            )
        return facts

    def snapshot(self, session_id: str) -> V2SessionSnapshot:
        if (
            type(session_id) is not str
            or re.fullmatch(_PHYSICAL_USB_IDENTITY_DOMAIN.session_pattern, session_id)
            is None
        ):
            raise M1CommissioningPersistenceError(
                "original camera session namespace required"
            )
        snapshot = self._runtime.session_snapshot(session_id)
        if snapshot.header.mode != "PHYSICAL_DIAGNOSTIC":
            raise M1CommissioningPersistenceError("USB session mode differs")
        return snapshot

    def verification(self, session_id: str) -> M1RuntimeVerification:
        self.snapshot(session_id)
        return self._runtime.verify(session_id)

    @contextmanager
    def stage_transaction(
        self, session_id: str, *, expected_challenge_sha256: str
    ) -> Iterator[M1PhysicalUsbIdentityTransaction]:
        with self._runtime.physical_usb_identity_transaction(
            session_id, expected_challenge_sha256=expected_challenge_sha256
        ) as transaction:
            transaction._audit_records()
            yield transaction

    @contextmanager
    def transaction(
        self, leases: tuple[LeaseSpec, ...]
    ) -> Iterator[M1PhysicalUsbIdentityTransaction]:
        if (
            type(leases) is not tuple
            or len(leases) != 3
            or any(type(spec) is not LeaseSpec for spec in leases)
            or leases[0] != LeaseSpec(LeaseLevel.CELL, self._runtime.cell.cell_id)
            or leases[1].level is not LeaseLevel.SESSION
            or leases[2] != LeaseSpec(LeaseLevel.CAMERA, self._runtime.cell.cell_id)
        ):
            raise M1CommissioningPersistenceError(
                "USB query requires exact CELL/SESSION/CAMERA leases"
            )
        with self._runtime.physical_usb_identity_transaction(
            leases[1].resource_id, device_levels=(LeaseLevel.CAMERA,)
        ) as transaction:
            if transaction.held_leases != leases:
                raise M1CommissioningPersistenceError("actual USB camera leases differ")
            transaction._facts_provider = self._checked_facts
            yield transaction
