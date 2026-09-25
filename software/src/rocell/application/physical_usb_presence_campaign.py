"""One original phase-bound presence campaign; no implicit retry or qualification.

The pre-review operation retains its server-assigned phase ID, launch and nonce.
The original-store owner must authenticate its baseline references and current
phase/boot/manual-event lineage. Pure construction does not do that, issue a
permit, open a device, inspect files, or authorize another physical operation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from threading import Event, RLock
from typing import Any, Callable

from .cell_commissioning_coordinator import (
    CampaignBudget,
    CampaignEvidence,
    CampaignRegistration,
    ExactOperationPermit,
    ObservedPowerState,
    RetainedCampaignExecution,
    RetainedUncertainCampaignExecution,
    WorkerReceipt,
)
from .consumed_commissioning_scope import ConsumedCommissioningScope
from .physical_onboarding import PhysicalOnboardingStage
from .physical_onboarding_leases import LeaseLevel
from .physical_usb_presence_binding import UsbPresencePhaseBinding
from .usb_presence_stage_policy import (
    POLICY_ACTION,
    POLICY_COMPOSITION,
    WORKER_ID,
    UsbPresenceStagePolicy,
    usb_presence_stage_policy,
)
from rocell.providers.windows.owned_usb_presence_evidence import (
    OwnedUsbPresenceRunEvidence,
    verify_owned_usb_presence_run_evidence,
)
from rocell.providers.windows.owned_worker_process import decode_owned_json
from rocell.providers.windows.usb_presence_protocol import canonical, digest
from rocell.providers.windows.usb_presence_registration import (
    PreparedOwnedUsbPresence,
    UsbPresenceRuntimeRegistration,
    prepare_owned_usb_presence,
)
from rocell.providers.windows.usb_presence_review import (
    UsbPresenceRuntimeReview,
    verify_usb_presence_runtime_review,
)
from rocell.safety.effects import EffectCertainty, EffectClass

OPERATION_SCHEMA = "rocell.physical_usb_presence_operation.v1"
ARTIFACT_LABEL = "physical-native-usb-presence"
MAX_OPERATION_BYTES = 32 * 1024
_ORIGINAL_FIELDS = (
    "cell_id",
    "session_id",
    "header_sha256",
    "trial_id",
    "source_sha256",
)
_FIELDS = {
    "schema",
    "operation_id",
    "launch_session_id",
    "request_nonce",
    "workspace",
    "policy_sha256",
    "phase_binding",
    "runtime",
    "physical_authority",
    "hardware_qualified",
    *_ORIGINAL_FIELDS,
}


class PhysicalUsbPresenceCampaignError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise PhysicalUsbPresenceCampaignError(code)


def _operation(payload: bytes) -> dict[str, Any]:
    d = decode_owned_json(payload, maximum=MAX_OPERATION_BYTES)
    _require(
        canonical(d) == payload and set(d) == _FIELDS, "EXACT_PRESENCE_OPERATION_FIELDS"
    )
    _require(
        d["schema"] == OPERATION_SCHEMA
        and d["physical_authority"] is False
        and d["hardware_qualified"] is False,
        "EXACT_PRESENCE_OPERATION_MEANING",
    )
    for key, pattern in (
        ("operation_id", r"usbphase-[0-9a-f]{32}"),
        ("launch_session_id", r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}"),
        ("request_nonce", r"[0-9a-f]{64}"),
    ):
        _require(
            type(d[key]) is str and re.fullmatch(pattern, d[key]) is not None,
            "EXACT_SERVER_PRESENCE_OPERATION_IDENTITY",
        )
    phase = UsbPresencePhaseBinding(canonical(d["phase_binding"]))
    runtime = UsbPresenceRuntimeRegistration(canonical(d["runtime"]))
    p, r = phase.to_dict(), runtime.to_dict()
    _require(
        all(d[key] == p["binding"][key] for key in _ORIGINAL_FIELDS)
        and d["source_sha256"] == r["source_sha256"]
        and d["workspace"] == r["workspace"]
        and d["policy_sha256"] == usb_presence_stage_policy().sha256,
        "PRESENCE_OPERATION_ORIGINAL_CONTEXT_MISMATCH",
    )
    return d


@dataclass(frozen=True, slots=True)
class UsbPresenceOperation:
    """Immutable pre-review subject, not original-store or process authority."""

    payload: bytes

    def __post_init__(self) -> None:
        _operation(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _operation(self.payload)


def usb_presence_operation(
    *,
    phase_binding: UsbPresencePhaseBinding,
    runtime: UsbPresenceRuntimeRegistration,
    policy: UsbPresenceStagePolicy,
    operation_id: str,
    launch_session_id: str,
    request_nonce: str,
) -> UsbPresenceOperation:
    """Derive the target from the retained baseline; never accept a target string.

    The application assigns the phase ID and nonce once before original review.
    A later reader uses these retained values, never fresh entropy or a new launch.
    Review and permit hashes are intentionally absent to avoid a dependency cycle.
    """
    _require(
        type(phase_binding) is UsbPresencePhaseBinding
        and type(runtime) is UsbPresenceRuntimeRegistration
        and type(policy) is UsbPresenceStagePolicy,
        "EXACT_PRESENCE_OPERATION_INPUTS",
    )
    p, r = phase_binding.to_dict(), runtime.to_dict()
    return UsbPresenceOperation(
        canonical(
            dict(
                schema=OPERATION_SCHEMA,
                operation_id=operation_id,
                launch_session_id=launch_session_id,
                request_nonce=request_nonce,
                **{key: p["binding"][key] for key in _ORIGINAL_FIELDS},
                workspace=r["workspace"],
                policy_sha256=policy.sha256,
                phase_binding=p,
                runtime=r,
                physical_authority=False,
                hardware_qualified=False,
            )
        )
    )


class PhysicalUsbPresenceCampaign:
    """Exact physical worker reachable only under one consumed presence scope."""

    composition = POLICY_COMPOSITION

    def __init__(
        self, operation: UsbPresenceOperation, *, review: UsbPresenceRuntimeReview
    ):
        _require(
            type(operation) is UsbPresenceOperation
            and type(review) is UsbPresenceRuntimeReview,
            "EXACT_PRESENCE_CAMPAIGN_INPUTS",
        )
        self._operation = UsbPresenceOperation(operation.payload)
        self._review = UsbPresenceRuntimeReview(review.payload)
        self._lock = RLock()
        self._used = False
        self._guard: Callable[[], None] | None = None
        self._evidence: bytes | None = None
        d = self._operation.to_dict()
        verify_usb_presence_runtime_review(
            self._review,
            runtime=UsbPresenceRuntimeRegistration(canonical(d["runtime"])),
            phase_binding=UsbPresencePhaseBinding(canonical(d["phase_binding"])),
            policy=usb_presence_stage_policy(),
            operation_sha256=self._operation.sha256,
            expected_review_sha256=self._review.sha256,
        )
        _require(
            self._review.to_dict()["launch_session_id"] == d["launch_session_id"],
            "PRESENCE_REVIEW_CURRENT_LAUNCH_MISMATCH",
        )

    @property
    def operation(self) -> UsbPresenceOperation:
        return UsbPresenceOperation(self._operation.payload)

    @property
    def phase_binding(self) -> UsbPresencePhaseBinding:
        return UsbPresencePhaseBinding(
            canonical(self.operation.to_dict()["phase_binding"])
        )

    @property
    def review(self) -> UsbPresenceRuntimeReview:
        return UsbPresenceRuntimeReview(self._review.payload)

    @property
    def worker_executable_sha256(self) -> str:
        return self.operation.to_dict()["runtime"]["helper"]["sha256"]

    @property
    def retained_evidence(self) -> OwnedUsbPresenceRunEvidence | None:
        with self._lock:
            return (
                None
                if self._evidence is None
                else OwnedUsbPresenceRunEvidence(self._evidence)
            )

    def registration(self) -> CampaignRegistration:
        return CampaignRegistration(
            POLICY_ACTION,
            PhysicalOnboardingStage.CAMERA_IDENTITY,
            EffectClass.BOUNDED_CAMERA_CAMPAIGN,
            WORKER_ID,
            self.worker_executable_sha256,
            self.operation.sha256,
            (LeaseLevel.CAMERA,),
            CampaignBudget(**usb_presence_stage_policy().to_dict()["budget"]),
        )

    def preparation_for_permit(
        self, permit: ExactOperationPermit
    ) -> PreparedOwnedUsbPresence:
        _require(
            type(permit) is ExactOperationPermit,
            "EXACT_ORIGINAL_PRESENCE_PERMIT_REQUIRED",
        )
        _require(
            canonical(asdict(permit.registration))
            == canonical(asdict(self.registration())),
            "PRESENCE_CAMPAIGN_REGISTRATION_MISMATCH",
        )
        d = self.operation.to_dict()
        # The frozen preparation independently validates the full original
        # presence-domain permit, including its authenticated review SHA.
        return prepare_owned_usb_presence(
            UsbPresenceRuntimeRegistration(canonical(d["runtime"])),
            phase_binding=self.phase_binding,
            policy=usb_presence_stage_policy(),
            review=self.review,
            permit=permit,
            request_nonce=d["request_nonce"],
        )

    def _bind_application_guard(self, guard: Callable[[], None]) -> None:
        with self._lock:
            _require(
                not self._used and self._guard is None and callable(guard),
                "PRESENCE_APPLICATION_GUARD_REQUIRED_ONCE",
            )
            self._guard = guard

    def run_campaign(self, *args: Any, **kwargs: Any) -> Any:
        raise PhysicalUsbPresenceCampaignError("SCOPED_PRESENCE_EXECUTION_REQUIRED")

    def run_retained_campaign(self, *args: Any, **kwargs: Any) -> Any:
        raise PhysicalUsbPresenceCampaignError("SCOPED_PRESENCE_EXECUTION_REQUIRED")

    def run_scoped_campaign(
        self,
        permit: ExactOperationPermit,
        *,
        deadline_ns: int,
        cancellation: Event,
        authorization: ConsumedCommissioningScope,
    ) -> RetainedCampaignExecution | RetainedUncertainCampaignExecution:
        from rocell.providers.windows.owned_usb_presence_runner import (
            OwnedUsbPresenceRunner,
        )

        with self._lock:
            _require(not self._used, "PRESENCE_CAMPAIGN_ALREADY_USED")
            self._used = True
            guard = self._guard
        _require(guard is not None, "PRESENCE_APPLICATION_GUARD_REQUIRED_ONCE")
        assert guard is not None
        prepared = self.preparation_for_permit(permit)
        # Only the runner acknowledges the consumed scope. The campaign cannot
        # acquire another permit or retry this attempt after any failure.
        report = OwnedUsbPresenceRunner(
            prepared,
            permit=permit,
            authorization=authorization,
            application_guard=guard,
        ).run(cancellation=cancellation, deadline_ns=deadline_ns)
        checked = verify_usb_presence_campaign_evidence(
            report,
            campaign=self,
            permit=permit,
            expected_evidence_sha256=report.sha256,
        )
        with self._lock:
            self._evidence = checked.payload
        artifact = CampaignEvidence(
            checked.to_dict()["schema"], ARTIFACT_LABEL, checked.payload
        )
        effect = checked.bounded_effect_summary()
        counts = effect["actual_counts"]
        if counts is None:
            return RetainedUncertainCampaignExecution(
                (artifact,), ("PRESENCE_ACCOUNTING_UNAVAILABLE",)
            )
        # Known diagnostic effects do not prove physical absence, mechanical
        # unplug cause, power isolation, stage PASS or permission for camera I/O.
        known = (
            effect["current_complete"]
            and effect["process_cleanup_confirmed"]
            and effect["native_cleanup_confirmed"]
        )
        return RetainedCampaignExecution(
            WorkerReceipt(
                permit.attempt_id,
                permit.permit_sha256,
                self.worker_executable_sha256,
                self.phase_binding.sha256,
                EffectCertainty.CONFIRMED if known else EffectCertainty.UNCERTAIN,
                bool(known),
                ObservedPowerState.UNKNOWN,
                counts["device_handle_opens"],
                counts["api_calls"],
                counts["configuration_writes"],
                counts["frames"],
                0,
                len(artifact.payload),
                (artifact.payload_sha256,),
                self.composition,
            ),
            (artifact,),
        )


def verify_usb_presence_campaign_evidence(
    evidence: OwnedUsbPresenceRunEvidence,
    *,
    campaign: PhysicalUsbPresenceCampaign,
    permit: ExactOperationPermit,
    expected_evidence_sha256: str,
) -> OwnedUsbPresenceRunEvidence:
    """Pure full original join. Reopening cannot issue or renew a saved permit."""
    _require(
        type(campaign) is PhysicalUsbPresenceCampaign
        and type(evidence) is OwnedUsbPresenceRunEvidence,
        "EXACT_PRESENCE_CAMPAIGN_EVIDENCE_REQUIRED",
    )
    prepared = campaign.preparation_for_permit(permit)
    checked = verify_owned_usb_presence_run_evidence(
        evidence,
        expected_preparation_sha256=prepared.sha256,
        expected_evidence_sha256=expected_evidence_sha256,
    )
    _require(
        canonical(checked.to_dict()["preparation"]) == prepared.payload,
        "PRESENCE_ORIGINAL_CAMPAIGN_EVIDENCE_MISMATCH",
    )
    # The frozen owned codec also checks the original permit expiry, <=25s
    # campaign bound, actual run/cleanup cutoffs and complete result provenance.
    return checked
