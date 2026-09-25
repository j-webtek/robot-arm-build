"""Closed DEV-002 commissioning protocol core with distinct storage domains.

This module implements exact admission, permit consumption and attempt ordering
against an injected, lease-owning persistence protocol. It deliberately does
NOT reach into M1's private fields. The separate commissioning_m1_persistence
adapter supplies real qualified NTFS publication and OS leases for the isolated
REHEARSAL domain. The separate PhysicalDiagnosticPreflightCoordinator admits
only retained NO_DEVICE_IO file checks in its physical-diagnostic store. No
activated physical adapter is admitted; the diagnostic UI remains separate.

An adapter must own real CELL -> SESSION -> declared-device leases, use qualified
publication, recheck admission under those leases, reject unresolved attempts and
recover uncertainty before another operation. Explicit retained actions require
one consumed-permit acknowledgement and complete immutable evidence before a
known seal. In-memory test adapters demonstrate only the protocol contract.

Permit/envelope/deadline times use the injected process monotonic clock. Durable
AttemptBinding timestamps use a separate UTC wall-clock nanosecond source; the
future persistence adapter must reject regressions against its committed head.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import re
import secrets
from threading import Event, Lock
import time
from typing import Any, Protocol, TYPE_CHECKING, cast
import uuid

from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import (
    AttemptBinding,
    AttemptState,
    canonical_json_bytes,
)
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.safety.effects import EffectCertainty, EffectClass

if TYPE_CHECKING:
    from .camera_activation_campaign_evidence import CameraActivationArtifact
    from .camera_sealed_capture_evidence import SealedCameraCaptureEvidence


PROTOCOL_SCHEMA = "rocell.commissioning-coordinator-core.v1"
INCAPABLE_COMPOSITION = "HARDWARE_INCAPABLE_REHEARSAL"
PHYSICAL_DIAGNOSTIC_COMPOSITION = "PHYSICAL_DIAGNOSTIC_NO_DEVICE_IO"
PHYSICAL_CAMERA_COMPOSITION = "PHYSICAL_DIAGNOSTIC_CAMERA_ACQUISITION"
PHYSICAL_USB_IDENTITY_COMPOSITION = "PHYSICAL_DIAGNOSTIC_USB_IDENTITY"
USB_IDENTITY_ACTION_ID = "physical-native-usb-identity"
PHYSICAL_USB_PRESENCE_COMPOSITION = "PHYSICAL_DIAGNOSTIC_USB_PRESENCE"
USB_PRESENCE_ACTION_ID = "physical-native-usb-presence"
USB_PRESENCE_WORKER_ID = "scoped-physical-native-usb-presence"
MAX_REGISTRATIONS = 32
MAX_PREPARED_PERMITS = 256
MAX_PERMIT_TTL_NS = 30_000_000_000
# Closed USB preparation needs 18 seconds of execution plus 2 for cleanup.
# A contract test keeps this floor aligned with its purpose-specific runtime.
USB_IDENTITY_MINIMUM_WINDOW_NS = 20_000_000_000
# Physical-node presence has a separate, fixed owned lifecycle and policy.
USB_PRESENCE_MINIMUM_WINDOW_NS = 15_000_000_000
# The distinct one-frame settings action uses the existing capture process:
# 15 seconds run + 2 seconds cleanup. Tests bind this floor to its native budget.
CAMERA_CONFIGURATION_MINIMUM_WINDOW_NS = 17_000_000_000
MAX_RETAINED_CAMPAIGN_BYTES = 128 * 1024
MAX_RETAINED_CAMPAIGN_ARTIFACTS = 4
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_EFFECT_RESOURCES = {
    EffectClass.NO_DEVICE_IO: (),
    EffectClass.READ_ONLY_OS_INVENTORY: (),
    EffectClass.BOUNDED_CAMERA_CAMPAIGN: (LeaseLevel.CAMERA,),
    EffectClass.MANUAL_ENERGY_CHANGE: (LeaseLevel.ARM_CONTROLLER,),
    EffectClass.MANUAL_POSSIBLE_MOTION: (LeaseLevel.ARM_CONTROLLER,),
    EffectClass.SERIAL_OPEN_OR_WRITE: (LeaseLevel.ARM_CONTROLLER,),
    EffectClass.NONCONTACT_ARM_MOTION_EXTERNAL: (
        LeaseLevel.CAMERA,
        LeaseLevel.ARM_CONTROLLER,
    ),
}
_POWER_EFFECTS = frozenset(
    {
        EffectClass.MANUAL_ENERGY_CHANGE,
        EffectClass.MANUAL_POSSIBLE_MOTION,
        EffectClass.SERIAL_OPEN_OR_WRITE,
        EffectClass.NONCONTACT_ARM_MOTION_EXTERNAL,
    }
)


class CommissioningCoordinatorError(RuntimeError):
    """Rejected admission or unresolved persistence; never a retry instruction."""


class CommissioningMode(str, Enum):
    REHEARSAL = "REHEARSAL"
    PHYSICAL_DIAGNOSTIC = "PHYSICAL_DIAGNOSTIC"


class ObservedPowerState(str, Enum):
    DEENERGIZED = "DEENERGIZED"
    ENERGIZED = "ENERGIZED"
    UNKNOWN = "UNKNOWN"


def _identifier(value: object, label: str) -> None:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise CommissioningCoordinatorError(f"{label} must be a bounded identifier")


def _digest(value: object, label: str) -> None:
    if type(value) is not str or _HASH.fullmatch(value) is None or value == "0" * 64:
        raise CommissioningCoordinatorError(f"{label} must be a nonzero SHA-256")


def _integer(value: object, label: str, minimum: int, maximum: int) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise CommissioningCoordinatorError(f"{label} exceeds its integer bounds")


def _hash(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class CampaignBudget:
    """Fixed ceilings; a supervisor must enforce deadlines during real execution."""

    timeout_ms: int
    maximum_output_bytes: int
    maximum_opens: int
    maximum_reads: int
    maximum_writes: int
    maximum_frames: int
    maximum_closes: int

    def __post_init__(self) -> None:
        _integer(self.timeout_ms, "timeout_ms", 1, 120000)
        _integer(self.maximum_output_bytes, "maximum_output_bytes", 1, 16 * 1024 * 1024)
        for name in (
            "maximum_opens",
            "maximum_reads",
            "maximum_writes",
            "maximum_frames",
            "maximum_closes",
        ):
            _integer(getattr(self, name), name, 0, 10000)


@dataclass(frozen=True, slots=True)
class CampaignRegistration:
    """Server-owned exact action; never constructed from browser parameters."""

    action_id: str
    stage: PhysicalOnboardingStage
    effect_class: EffectClass
    worker_id: str
    worker_executable_sha256: str
    operation_sha256: str
    resources: tuple[LeaseLevel, ...]
    budget: CampaignBudget

    def __post_init__(self) -> None:
        _identifier(self.action_id, "action_id")
        _identifier(self.worker_id, "worker_id")
        if not isinstance(self.stage, PhysicalOnboardingStage) or not isinstance(
            self.effect_class, EffectClass
        ):
            raise CommissioningCoordinatorError(
                "registration stage/effect class must be closed enums"
            )
        _digest(self.worker_executable_sha256, "worker_executable_sha256")
        _digest(self.operation_sha256, "operation_sha256")
        if (
            type(self.resources) is not tuple
            or self.resources != _EFFECT_RESOURCES[self.effect_class]
        ):
            raise CommissioningCoordinatorError(
                "registration resource leases do not match the effect class/order"
            )
        if not isinstance(self.budget, CampaignBudget):
            raise CommissioningCoordinatorError(
                "registration requires a typed campaign budget"
            )
        if self.effect_class in {
            EffectClass.NO_DEVICE_IO,
            EffectClass.READ_ONLY_OS_INVENTORY,
            EffectClass.MANUAL_ENERGY_CHANGE,
            EffectClass.MANUAL_POSSIBLE_MOTION,
        } and any(
            (
                self.budget.maximum_opens,
                self.budget.maximum_reads,
                self.budget.maximum_writes,
                self.budget.maximum_frames,
                self.budget.maximum_closes,
            )
        ):
            raise CommissioningCoordinatorError(
                "this effect class cannot carry a device-I/O budget"
            )
        if self.effect_class is EffectClass.SERIAL_OPEN_OR_WRITE and (
            self.budget.maximum_opens != 1
            or self.budget.maximum_writes != 1
            or self.budget.maximum_closes != 1
            or self.budget.maximum_frames != 0
        ):
            raise CommissioningCoordinatorError(
                "onboarding serial registration allows exactly one open/write/close attempt"
            )

    @property
    def registration_sha256(self) -> str:
        return _hash(asdict(self))


@dataclass(frozen=True, slots=True)
class AdmissionSnapshot:
    """Persistence-derived challenge covering every mutable admission dependency."""

    cell_id: str
    session_id: str
    mode: CommissioningMode
    stage: PhysicalOnboardingStage
    stage_state: V2StageState
    stage_revision: int
    source_binding_sha256: str
    stage_plan_sha256: str
    journal_head_sha256: str
    global_attempt_head_sha256: str
    quarantine_head_sha256: str
    evidence_inventory_sha256: str
    hazard_assessment_sha256: str
    durability_qualification_sha256: str
    configuration_epoch_hashes: tuple[str, ...]
    selected_identity_sha256: str | None
    quarantine_latched: bool
    unresolved_attempts: int
    open_blocker_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.cell_id, "cell_id")
        _identifier(self.session_id, "session_id")
        if not isinstance(self.mode, CommissioningMode) or not isinstance(
            self.stage, PhysicalOnboardingStage
        ):
            raise CommissioningCoordinatorError(
                "admission mode/stage must be closed enums"
            )
        if not isinstance(self.stage_state, V2StageState):
            raise CommissioningCoordinatorError(
                "admission stage_state must be V2StageState"
            )
        _integer(self.stage_revision, "stage_revision", 0, 2**63 - 1)
        _integer(self.unresolved_attempts, "unresolved_attempts", 0, 1000000)
        if type(self.quarantine_latched) is not bool:
            raise CommissioningCoordinatorError("quarantine_latched must be Boolean")
        for field in (
            "source_binding_sha256",
            "stage_plan_sha256",
            "journal_head_sha256",
            "global_attempt_head_sha256",
            "quarantine_head_sha256",
            "evidence_inventory_sha256",
            "hazard_assessment_sha256",
            "durability_qualification_sha256",
        ):
            _digest(getattr(self, field), field)
        if type(self.open_blocker_ids) is not tuple or len(self.open_blocker_ids) > 64:
            raise CommissioningCoordinatorError(
                "admission blocker IDs must be a bounded tuple"
            )
        for blocker in self.open_blocker_ids:
            _identifier(blocker, "blocker ID")
        if (
            type(self.configuration_epoch_hashes) is not tuple
            or len(self.configuration_epoch_hashes) != 8
        ):
            raise CommissioningCoordinatorError(
                "admission requires the complete eight-epoch vector"
            )
        for digest in self.configuration_epoch_hashes:
            _digest(digest, "configuration_epoch_hash")
        if self.selected_identity_sha256 is not None:
            _digest(self.selected_identity_sha256, "selected_identity_sha256")

    @property
    def challenge_sha256(self) -> str:
        return _hash(asdict(self))


@dataclass(frozen=True, slots=True, kw_only=True)
class UsbIdentityAdmissionSnapshot(AdmissionSnapshot):
    """Additive USB-only challenge; historical camera snapshot bytes stay exact."""

    usb_query_policy_sha256: str

    def __post_init__(self) -> None:
        AdmissionSnapshot.__post_init__(self)
        _digest(self.usb_query_policy_sha256, "usb_query_policy_sha256")


@dataclass(frozen=True, slots=True, kw_only=True)
class UsbPresenceAdmissionSnapshot(AdmissionSnapshot):
    """Exact phase-bound presence challenge, never a descriptor-query grant."""

    usb_presence_policy_sha256: str
    phase_binding_sha256: str
    runtime_review_sha256: str

    def __post_init__(self) -> None:
        AdmissionSnapshot.__post_init__(self)
        _digest(self.usb_presence_policy_sha256, "usb_presence_policy_sha256")
        _digest(self.phase_binding_sha256, "phase_binding_sha256")
        _digest(self.runtime_review_sha256, "runtime_review_sha256")
        if self.selected_identity_sha256 != self.phase_binding_sha256:
            raise CommissioningCoordinatorError(
                "USB presence selected identity must be the exact phase binding"
            )


@dataclass(frozen=True, slots=True)
class RegisteredActionRequest:
    cell_id: str
    session_id: str
    action_id: str
    request_key: str
    expected_challenge_sha256: str

    def __post_init__(self) -> None:
        for name in ("cell_id", "session_id", "action_id", "request_key"):
            _identifier(getattr(self, name), name)
        _digest(self.expected_challenge_sha256, "expected_challenge_sha256")


@dataclass(frozen=True, slots=True)
class EnergizationEnvelope:
    """One observed off-to-on campaign, bound to its exact intended operation."""

    envelope_id: str
    operation_sha256: str
    power_topology_sha256: str
    safety_review_sha256: str
    installed_object_inventory_sha256: str
    configuration_epoch_vector_sha256: str
    operator_id: str
    observer_id: str
    issued_at_ns: int
    expires_at_ns: int
    required_initial_state: ObservedPowerState = ObservedPowerState.DEENERGIZED
    required_final_state: ObservedPowerState = ObservedPowerState.DEENERGIZED

    def __post_init__(self) -> None:
        for name in ("envelope_id", "operator_id", "observer_id"):
            _identifier(getattr(self, name), name)
        if self.operator_id == self.observer_id:
            raise CommissioningCoordinatorError(
                "operator and observer must be distinct"
            )
        for name in (
            "operation_sha256",
            "power_topology_sha256",
            "safety_review_sha256",
            "installed_object_inventory_sha256",
            "configuration_epoch_vector_sha256",
        ):
            _digest(getattr(self, name), name)
        _integer(self.issued_at_ns, "envelope issued_at_ns", 0, 2**63 - 1)
        _integer(
            self.expires_at_ns,
            "envelope expires_at_ns",
            self.issued_at_ns + 1,
            self.issued_at_ns + MAX_PERMIT_TTL_NS,
        )
        if (
            self.required_initial_state is not ObservedPowerState.DEENERGIZED
            or self.required_final_state is not ObservedPowerState.DEENERGIZED
        ):
            raise CommissioningCoordinatorError(
                "onboarding envelope requires initial and final de-energization"
            )


@dataclass(frozen=True, slots=True)
class ExactOperationPermit:
    """Process-local exact permit; refreshing/restarting never reconstructs it."""

    attempt_id: str
    request: RegisteredActionRequest
    admission: AdmissionSnapshot
    registration: CampaignRegistration
    issued_at_ns: int
    expires_at_ns: int
    nonce: str
    envelope: EnergizationEnvelope | None = None

    @property
    def permit_sha256(self) -> str:
        return _hash(asdict(self))


@dataclass(frozen=True, slots=True)
class WorkerReceipt:
    """Bounded campaign observations; none of these fields grant authority."""

    attempt_id: str
    permit_sha256: str
    worker_executable_sha256: str
    selected_identity_sha256: str | None
    effect_certainty: EffectCertainty
    cleanup_confirmed: bool
    final_power_state: ObservedPowerState
    opens: int
    reads: int
    writes: int
    frames: int
    closes: int
    output_bytes: int
    evidence_sha256s: tuple[str, ...]
    composition: str = INCAPABLE_COMPOSITION


@dataclass(frozen=True, slots=True)
class CampaignEvidence:
    """Exact bounded opaque bytes; only the registered worker builds their schema.

    These bytes are private technical evidence, not a log/status projection.
    Persistence owns their immutable publication; callers supply no destination.
    """

    schema: str
    label: str
    payload: bytes

    def __post_init__(self) -> None:
        _identifier(self.schema, "campaign evidence schema")
        _identifier(self.label, "campaign evidence label")
        if (
            type(self.payload) is not bytes
            or not 0 < len(self.payload) <= MAX_RETAINED_CAMPAIGN_BYTES
        ):
            raise CommissioningCoordinatorError(
                "campaign evidence exceeds its byte bound"
            )

    @property
    def payload_sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


@dataclass(frozen=True, slots=True)
class RetainedCampaignExecution:
    receipt: WorkerReceipt
    evidence: tuple[CampaignEvidence, ...]

    def __post_init__(self) -> None:
        if type(self.receipt) is not WorkerReceipt:
            raise CommissioningCoordinatorError(
                "retained campaign needs an exact WorkerReceipt"
            )
        validate_campaign_evidence(self.evidence)


@dataclass(frozen=True, slots=True)
class RetainedUncertainCampaignExecution:
    """USB-only original diagnostics when no complete device receipt exists."""

    evidence: tuple[CampaignEvidence, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_campaign_evidence(self.evidence)
        if (
            type(self.reason_codes) is not tuple
            or not 1 <= len(self.reason_codes) <= 16
            or any(
                type(code) is not str
                or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code) is None
                for code in self.reason_codes
            )
            or len(set(self.reason_codes)) != len(self.reason_codes)
        ):
            raise CommissioningCoordinatorError(
                "uncertain diagnostics require bounded fixed reason codes"
            )


def validate_campaign_evidence(evidence: tuple[CampaignEvidence, ...]) -> None:
    if (
        type(evidence) is not tuple
        or not 1 <= len(evidence) <= MAX_RETAINED_CAMPAIGN_ARTIFACTS
    ):
        raise CommissioningCoordinatorError(
            "retained campaign evidence tuple is missing or oversized"
        )
    for item in evidence:
        if type(item) is not CampaignEvidence:
            raise CommissioningCoordinatorError("untyped retained campaign evidence")
        item.__post_init__()
    if (
        sum(len(item.payload) for item in evidence) > MAX_RETAINED_CAMPAIGN_BYTES
        or len({item.label for item in evidence}) != len(evidence)
        or len({item.payload_sha256 for item in evidence}) != len(evidence)
    ):
        raise CommissioningCoordinatorError(
            "campaign evidence aggregate/uniqueness bound failed"
        )


@dataclass(frozen=True, slots=True)
class AttemptResult:
    attempt_id: str
    state: AttemptState
    permit_sha256: str
    reason_codes: tuple[str, ...]
    receipt: WorkerReceipt | None
    quarantine_latched: bool
    composition: str = INCAPABLE_COMPOSITION
    physical_authority: str = "NONE"


class CommissioningTransaction(Protocol):
    """Public M1 adapter seam; all methods run while leases are held.

    ``held_leases`` is freshly verified ownership, not requested metadata.
    ``begin_intent`` must reject reused request/attempt/envelope identifiers
    cell-globally; ``consume_permit`` must durably consume once as EFFECT_ARMED.
    ``seal_uncertain`` must persist uncertainty and global quarantine, retaining
    an unresolved attempt if any intermediate publication fails. A restart
    must block on that unresolved suffix, not infer absence of device effects.
    """

    held_leases: tuple[LeaseSpec, ...]

    def read_admission(self, request: RegisteredActionRequest) -> AdmissionSnapshot: ...
    def read_envelope(
        self, request: RegisteredActionRequest
    ) -> EnergizationEnvelope | None: ...
    def begin_intent(
        self, binding: AttemptBinding, permit: ExactOperationPermit
    ) -> None: ...
    def consume_permit(self, permit: ExactOperationPermit) -> None: ...
    def assert_consumed_permit(self, permit: ExactOperationPermit) -> None: ...
    def revalidate_consumed_permit(self, permit: ExactOperationPermit) -> None: ...
    def retain_campaign_evidence(
        self, permit: ExactOperationPermit, evidence: tuple[CampaignEvidence, ...]
    ) -> None: ...
    def retain_camera_activation_evidence(
        self,
        permit: ExactOperationPermit,
        evidence: tuple[CameraActivationArtifact, ...] | SealedCameraCaptureEvidence,
    ) -> None: ...
    def transition(
        self, attempt_id: str, state: AttemptState, receipt: WorkerReceipt | None
    ) -> None: ...
    def retain_result(self, result: AttemptResult) -> None: ...
    def seal_uncertain(
        self, attempt_id: str, reason_codes: tuple[str, ...]
    ) -> None: ...


class CommissioningPersistence(Protocol):
    """Injected lease-owning store; physical activation is not supplied here."""

    composition: str

    def transaction(
        self, leases: tuple[LeaseSpec, ...]
    ) -> AbstractContextManager[CommissioningTransaction]: ...


class BoundedCommissioningWorker(Protocol):
    """Registered test-worker seam, not arbitrary executable/module dispatch.

    Real integration requires a separately qualified supervisor that enforces
    deadlines/cancellation during I/O; this core checks observed completion too.
    """

    composition: str
    worker_executable_sha256: str

    def run_campaign(
        self, permit: ExactOperationPermit, *, deadline_ns: int, cancellation: Event
    ) -> WorkerReceipt: ...


class RetainedBoundedCommissioningWorker(BoundedCommissioningWorker, Protocol):
    """Explicit opt-in path with one-use admission acknowledgement and raw evidence."""

    def run_retained_campaign(
        self,
        permit: ExactOperationPermit,
        *,
        deadline_ns: int,
        cancellation: Event,
        authorize_consumed_permit: Callable[[ExactOperationPermit], None],
    ) -> RetainedCampaignExecution: ...


class CellCommissioningCoordinator:
    """One-use ordered coordinator core; no default store or device worker."""

    _usb_query_policy_sha256: str
    _usb_presence_policy_sha256: str

    def __init__(
        self,
        *,
        persistence: CommissioningPersistence,
        registrations: tuple[CampaignRegistration, ...],
        workers: Mapping[str, BoundedCommissioningWorker],
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        wall_time_ns: Callable[[], int] = time.time_ns,
        retained_campaign_actions: tuple[str, ...] = (),
        scoped_campaign_actions: tuple[str, ...] = (),
    ) -> None:
        # Domain is selected by exact closed constructors, never an
        # HTTP flag or an arbitrary provider's claim that it is qualified.
        if type(self) is CellCommissioningCoordinator:
            self._composition = INCAPABLE_COMPOSITION
            self._mode = CommissioningMode.REHEARSAL
        elif type(self) is PhysicalDiagnosticPreflightCoordinator:
            self._composition = PHYSICAL_DIAGNOSTIC_COMPOSITION
            self._mode = CommissioningMode.PHYSICAL_DIAGNOSTIC
        elif type(self) is PhysicalCameraAcquisitionCoordinator:
            self._composition = PHYSICAL_CAMERA_COMPOSITION
            self._mode = CommissioningMode.PHYSICAL_DIAGNOSTIC
        elif type(self) is PhysicalUsbIdentityCoordinator:
            self._composition = PHYSICAL_USB_IDENTITY_COMPOSITION
            self._mode = CommissioningMode.PHYSICAL_DIAGNOSTIC
        elif type(self) is PhysicalUsbPresenceCoordinator:
            self._composition = PHYSICAL_USB_PRESENCE_COMPOSITION
            self._mode = CommissioningMode.PHYSICAL_DIAGNOSTIC
        else:
            raise CommissioningCoordinatorError("unregistered coordinator domain")
        if persistence.composition != self._composition:
            raise CommissioningCoordinatorError(
                "qualified physical M1 integration is not implemented"
            )
        if (
            type(registrations) is not tuple
            or not 1 <= len(registrations) <= MAX_REGISTRATIONS
        ):
            raise CommissioningCoordinatorError("registry must be a bounded tuple")
        registry = {}
        for registration in registrations:
            if (
                not isinstance(registration, CampaignRegistration)
                or registration.action_id in registry
            ):
                raise CommissioningCoordinatorError(
                    "registry contains an invalid/duplicate action"
                )
            worker = workers.get(registration.worker_id)
            if (
                worker is None
                or worker.composition != self._composition
                or worker.worker_executable_sha256
                != registration.worker_executable_sha256
            ):
                raise CommissioningCoordinatorError(
                    "worker registration/hash/composition is unqualified"
                )
            registry[registration.action_id] = registration
            self._validate_domain_registration(registration)
        if set(workers) != {item.worker_id for item in registrations}:
            raise CommissioningCoordinatorError(
                "unregistered worker supplied to coordinator"
            )
        if (
            type(retained_campaign_actions) is not tuple
            or len(set(retained_campaign_actions)) != len(retained_campaign_actions)
            or any(
                type(action) is not str or action not in registry
                for action in retained_campaign_actions
            )
        ):
            raise CommissioningCoordinatorError(
                "retained actions must be exact unique registered action IDs"
            )
        if (
            type(scoped_campaign_actions) is not tuple
            or len(set(scoped_campaign_actions)) != len(scoped_campaign_actions)
            or any(
                action not in retained_campaign_actions
                for action in scoped_campaign_actions
            )
        ):
            raise CommissioningCoordinatorError(
                "scoped actions must be unique retained action IDs"
            )
        if self._mode is CommissioningMode.PHYSICAL_DIAGNOSTIC and set(
            retained_campaign_actions
        ) != set(registry):
            raise CommissioningCoordinatorError(
                "physical diagnostics require full retained campaign evidence"
            )
        if self._composition in {
            PHYSICAL_CAMERA_COMPOSITION,
            PHYSICAL_USB_IDENTITY_COMPOSITION,
            PHYSICAL_USB_PRESENCE_COMPOSITION,
        } and set(scoped_campaign_actions) != set(registry):
            raise CommissioningCoordinatorError(
                "physical camera acquisition requires original scoped revalidation"
            )
        for action in retained_campaign_actions:
            method = (
                "run_scoped_campaign"
                if action in scoped_campaign_actions
                else "run_retained_campaign"
            )
            if not callable(getattr(workers[registry[action].worker_id], method, None)):
                raise CommissioningCoordinatorError(
                    "retained action has no registered retention worker"
                )
        self._persistence = persistence
        self._registry = registry
        self._workers = dict(workers)
        self._retained_actions = frozenset(retained_campaign_actions)
        self._scoped_actions = frozenset(scoped_campaign_actions)
        self._clock = monotonic_ns
        self._wall_clock = wall_time_ns
        self._last_time = -1
        self._permits: dict[str, ExactOperationPermit] = {}
        self._results: dict[str, AttemptResult] = {}
        self._prepared_requests: dict[tuple[str, str, str], ExactOperationPermit] = {}
        self._cancel_events: dict[str, Event] = {}
        self._lock = Lock()
        self._poisoned = False
        self._transaction_cleanup_failure: BaseException | None = None

    def _validate_domain_registration(self, registration: CampaignRegistration) -> None:
        if self._mode is not CommissioningMode.PHYSICAL_DIAGNOSTIC:
            return
        registration.__post_init__()
        if self._composition == PHYSICAL_USB_PRESENCE_COMPOSITION:
            if (
                registration.action_id != USB_PRESENCE_ACTION_ID
                or registration.worker_id != USB_PRESENCE_WORKER_ID
                or registration.stage is not PhysicalOnboardingStage.CAMERA_IDENTITY
                or registration.effect_class is not EffectClass.BOUNDED_CAMERA_CAMPAIGN
                or registration.resources != (LeaseLevel.CAMERA,)
                or registration.budget
                != CampaignBudget(25000, 128 * 1024, 0, 4, 0, 0, 0)
            ):
                raise CommissioningCoordinatorError(
                    "USB presence requires its exact stage/action/worker/budget"
                )
            return
        if self._composition == PHYSICAL_USB_IDENTITY_COMPOSITION:
            if (
                registration.action_id != USB_IDENTITY_ACTION_ID
                or registration.stage is not PhysicalOnboardingStage.CAMERA_IDENTITY
                or registration.effect_class is not EffectClass.BOUNDED_CAMERA_CAMPAIGN
                or registration.resources != (LeaseLevel.CAMERA,)
                or registration.budget
                != CampaignBudget(25000, 128 * 1024, 32, 128, 0, 0, 32)
            ):
                raise CommissioningCoordinatorError(
                    "USB identity requires its exact amended stage/action/budget"
                )
            return
        if self._composition == PHYSICAL_CAMERA_COMPOSITION:
            if (
                registration.effect_class is not EffectClass.BOUNDED_CAMERA_CAMPAIGN
                or registration.resources != (LeaseLevel.CAMERA,)
                or registration.stage
                not in {
                    PhysicalOnboardingStage.CAMERA_MODE_CONTROLS,
                    PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS,
                }
                or registration.budget.timeout_ms > 25000
            ):
                raise CommissioningCoordinatorError(
                    "physical camera domain requires bounded camera-only scoped acquisition"
                )
            return
        if (
            registration.effect_class is not EffectClass.NO_DEVICE_IO
            or registration.resources != ()
            or registration.stage
            not in {
                PhysicalOnboardingStage.WORKSPACE_SOURCES,
                PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT,
            }
        ):
            raise CommissioningCoordinatorError(
                "physical preflight admits only source-contract NO_DEVICE_IO checks"
            )

    def _raise_transaction_cleanup_hold(self) -> None:
        if self._transaction_cleanup_failure is not None:
            # The original cause is retained for private diagnostics. Public
            # exception text must not copy endpoint/path details from a backend.
            raise CommissioningCoordinatorError(
                "transaction cleanup failed; coordinator held; inspect retained records"
            ) from self._transaction_cleanup_failure

    @contextmanager
    def _transaction_scope(
        self, leases: tuple[LeaseSpec, ...]
    ) -> Iterator[CommissioningTransaction]:
        """Keep an exit failure distinct from the already-durable arm result.

        A normal body return can still fail while the persistence adapter
        releases its leases. Never rewrite a completed attempt in that case,
        retry release, or let its cached result hide the local cleanup hold.
        Ordinary body/admission failures retain their existing semantics.
        """
        body_completed = False
        try:
            with self._persistence.transaction(leases) as transaction:
                yield transaction
                body_completed = True
        except BaseException as failure:
            if not body_completed:
                raise
            self._poisoned = True
            self._transaction_cleanup_failure = failure
            # Process termination remains process termination, while any later
            # caller still observes the latched cleanup failure before cache.
            if not isinstance(failure, Exception):
                raise
            self._raise_transaction_cleanup_hold()

    def _now(self) -> int:
        now = self._clock()
        _integer(now, "monotonic time", 0, 2**63 - 1)
        if now < self._last_time:
            self._poisoned = True
            raise CommissioningCoordinatorError(
                "monotonic clock regressed; coordinator is held"
            )
        self._last_time = now
        return now

    def _leases(
        self, request: RegisteredActionRequest, registration: CampaignRegistration
    ) -> tuple[LeaseSpec, ...]:
        # Cell-wide device resource IDs are stable across sessions; identity is
        # bound independently in admission, never used to split ownership locks.
        return (
            LeaseSpec(LeaseLevel.CELL, request.cell_id),
            LeaseSpec(LeaseLevel.SESSION, request.session_id),
            *(LeaseSpec(level, request.cell_id) for level in registration.resources),
        )

    def _admission(
        self,
        transaction: CommissioningTransaction,
        request: RegisteredActionRequest,
        registration: CampaignRegistration,
        leases: tuple[LeaseSpec, ...],
    ) -> AdmissionSnapshot:
        if transaction.held_leases != leases:
            raise CommissioningCoordinatorError(
                "persistence did not establish exact ordered leases"
            )
        snapshot = transaction.read_admission(request)
        if (
            not isinstance(snapshot, AdmissionSnapshot)
            or snapshot.cell_id != request.cell_id
            or snapshot.session_id != request.session_id
        ):
            raise CommissioningCoordinatorError(
                "admission session/cell binding mismatch"
            )
        if (
            snapshot.mode is not self._mode
            or self._persistence.composition != self._composition
        ):
            raise CommissioningCoordinatorError(
                "physical M1/provider integration is not qualified"
            )
        self._validate_domain_registration(registration)
        if self._composition == PHYSICAL_USB_PRESENCE_COMPOSITION:
            if (
                type(snapshot) is not UsbPresenceAdmissionSnapshot
                or snapshot.usb_presence_policy_sha256
                != self._usb_presence_policy_sha256
            ):
                raise CommissioningCoordinatorError(
                    "USB presence admission differs from the pinned presence policy"
                )
            # Recheck the complete immutable snapshot, including selected
            # identity == phase binding, at each newly leased admission.
            snapshot.__post_init__()
        if self._composition == PHYSICAL_USB_IDENTITY_COMPOSITION and (
            type(snapshot) is not UsbIdentityAdmissionSnapshot
            or snapshot.usb_query_policy_sha256 != self._usb_query_policy_sha256
        ):
            raise CommissioningCoordinatorError(
                "USB admission differs from the independently pinned stage policy"
            )
        if snapshot.challenge_sha256 != request.expected_challenge_sha256:
            raise CommissioningCoordinatorError(
                "stale source/revision/head/identity/epoch challenge"
            )
        if snapshot.quarantine_latched or snapshot.unresolved_attempts:
            raise CommissioningCoordinatorError(
                "cell-global quarantine or unresolved attempt blocks admission"
            )
        if snapshot.open_blocker_ids:
            raise CommissioningCoordinatorError(
                "reviewed admission has unresolved prerequisite blockers"
            )
        if (
            snapshot.stage is not registration.stage
            or snapshot.stage_state is not V2StageState.WAITING_OPERATOR
        ):
            raise CommissioningCoordinatorError(
                "registered action is not allowed in the current reviewed stage"
            )
        if registration.resources and snapshot.selected_identity_sha256 is None:
            raise CommissioningCoordinatorError(
                "registered device campaign requires an identity binding"
            )
        return snapshot

    def _envelope(
        self,
        transaction: CommissioningTransaction,
        request: RegisteredActionRequest,
        registration: CampaignRegistration,
        snapshot: AdmissionSnapshot,
        now: int,
    ) -> EnergizationEnvelope | None:
        envelope = transaction.read_envelope(request)
        if registration.effect_class not in _POWER_EFFECTS:
            if envelope is not None:
                raise CommissioningCoordinatorError(
                    "non-power campaign cannot carry an energy envelope"
                )
            return None
        if (
            not isinstance(envelope, EnergizationEnvelope)
            or envelope.operation_sha256 != registration.operation_sha256
            or envelope.configuration_epoch_vector_sha256
            != _hash(snapshot.configuration_epoch_hashes)
            or not envelope.issued_at_ns <= now < envelope.expires_at_ns
        ):
            raise CommissioningCoordinatorError(
                "a fresh exact reviewed energization envelope is required"
            )
        return envelope

    def prepare(self, request: RegisteredActionRequest) -> ExactOperationPermit:
        """Read/revalidate and prepare one exact ticket; no worker or intent writes."""
        if not isinstance(request, RegisteredActionRequest):
            raise CommissioningCoordinatorError(
                "prepare requires a typed registered request"
            )
        with self._lock:
            self._raise_transaction_cleanup_hold()
            if self._poisoned:
                raise CommissioningCoordinatorError(
                    "coordinator is held; review durable stores"
                )
            registration = self._registry.get(request.action_id)
            if registration is None:
                raise CommissioningCoordinatorError("action is not registered")
            key = (request.cell_id, request.session_id, request.request_key)
            prior = self._prepared_requests.get(key)
            if prior is not None:
                if prior.request != request:
                    raise CommissioningCoordinatorError(
                        "request key cannot be reused for another action/challenge"
                    )
                return prior
            if len(self._permits) >= MAX_PREPARED_PERMITS:
                raise CommissioningCoordinatorError(
                    "prepared permit budget exhausted; no automatic eviction/reissue"
                )
            now = self._now()
            leases = self._leases(request, registration)
            with self._transaction_scope(leases) as transaction:
                snapshot = self._admission(transaction, request, registration, leases)
                envelope = self._envelope(
                    transaction, request, registration, snapshot, now
                )
            if self._composition in {
                PHYSICAL_USB_IDENTITY_COMPOSITION,
                PHYSICAL_USB_PRESENCE_COMPOSITION,
                PHYSICAL_CAMERA_COMPOSITION,
            }:
                # First issuance happens only after the read-only prepare scope
                # has successfully released its leases. Original-history checks
                # and cleanup can both take time; neither is worker execution.
                # No permit, durable intent or effect exists before this point.
                # Execute still reacquires leases and freshly verifies the exact
                # snapshot, and execution must stay within the unchanged TTL.
                # A returned/cached permit is never renewed. Other/energy
                # permits retain their original pre-inspection timestamp.
                if envelope is not None:
                    raise CommissioningCoordinatorError(
                        "Camera/USB diagnostic campaigns cannot issue an energy envelope"
                    )
                now = self._now()
            expires = min(
                now + MAX_PERMIT_TTL_NS,
                envelope.expires_at_ns if envelope else now + MAX_PERMIT_TTL_NS,
            )
            permit = ExactOperationPermit(
                "attempt-" + uuid.uuid4().hex,
                request,
                snapshot,
                registration,
                now,
                expires,
                secrets.token_hex(32),
                envelope,
            )
            self._permits[permit.nonce] = permit
            self._prepared_requests[key] = permit
            self._cancel_events[permit.nonce] = Event()
            return permit

    def cancel(self, permit: ExactOperationPermit) -> None:
        """Request cessation without claiming worker cleanup or power removal."""
        if not isinstance(permit, ExactOperationPermit):
            raise CommissioningCoordinatorError(
                "cancel requires an exact prepared permit"
            )
        original = self._permits.get(permit.nonce)
        if original != permit:
            raise CommissioningCoordinatorError(
                "unknown/substituted cancellation permit"
            )
        self._cancel_events[permit.nonce].set()

    def _receipt_reasons(
        self, permit: ExactOperationPermit, receipt: object, deadline_ns: int
    ) -> tuple[str, ...]:
        if not isinstance(receipt, WorkerReceipt):
            return ("MALFORMED_WORKER_RECEIPT",)
        reasons = []
        if (
            receipt.attempt_id != permit.attempt_id
            or receipt.permit_sha256 != permit.permit_sha256
            or receipt.worker_executable_sha256
            != permit.registration.worker_executable_sha256
            or receipt.selected_identity_sha256
            != permit.admission.selected_identity_sha256
            or receipt.composition != self._composition
        ):
            reasons.append("WORKER_BINDING_MISMATCH")
        if receipt.effect_certainty is not EffectCertainty.CONFIRMED:
            reasons.append("EFFECT_UNCERTAIN")
        if receipt.cleanup_confirmed is not True:
            reasons.append("CLEANUP_UNCONFIRMED")
        if not isinstance(receipt.final_power_state, ObservedPowerState):
            reasons.append("INVALID_FINAL_POWER_STATE")
        if (
            self._mode is CommissioningMode.PHYSICAL_DIAGNOSTIC
            and receipt.final_power_state is not ObservedPowerState.UNKNOWN
        ):
            reasons.append("NO_DEVICE_IO_CANNOT_OBSERVE_POWER_STATE")
        if (
            permit.envelope is not None
            and receipt.final_power_state is not ObservedPowerState.DEENERGIZED
        ):
            reasons.append("FINAL_DEENERGIZATION_UNCONFIRMED")
        for count, ceiling in (
            ("opens", "maximum_opens"),
            ("reads", "maximum_reads"),
            ("writes", "maximum_writes"),
            ("frames", "maximum_frames"),
            ("closes", "maximum_closes"),
            ("output_bytes", "maximum_output_bytes"),
        ):
            observed = getattr(receipt, count)
            if type(observed) is not int or not 0 <= observed <= getattr(
                permit.registration.budget, ceiling
            ):
                reasons.append("WORKER_RESOURCE_BUDGET_EXCEEDED")
        if (
            type(receipt.evidence_sha256s) is not tuple
            or len(receipt.evidence_sha256s) > 64
        ):
            reasons.append("INVALID_EVIDENCE_DIGESTS")
        else:
            for digest in receipt.evidence_sha256s:
                if (
                    type(digest) is not str
                    or _HASH.fullmatch(digest) is None
                    or digest == "0" * 64
                ):
                    reasons.append("INVALID_EVIDENCE_DIGESTS")
                    break
        if self._now() > deadline_ns:
            reasons.append("WORKER_DEADLINE_EXCEEDED")
        if self._cancel_events[permit.nonce].is_set():
            reasons.append("CANCELLATION_AFTER_EFFECT_ARMED")
        return tuple(dict.fromkeys(reasons))

    def execute(
        self, permit: ExactOperationPermit, *, cancellation: Event | None = None
    ) -> AttemptResult:
        """Consume once before dispatch, account cleanup, or latch uncertainty."""
        if not isinstance(permit, ExactOperationPermit):
            raise CommissioningCoordinatorError(
                "execute requires an exact prepared permit"
            )
        if cancellation is not None and not isinstance(cancellation, Event):
            raise CommissioningCoordinatorError(
                "cancellation must be a threading Event"
            )
        # The lock gives duplicate callers one result and one dispatch. Production
        # process concurrency is still the persistence adapter's OS-lease duty.
        with self._lock:
            if self._permits.get(permit.nonce) != permit:
                raise CommissioningCoordinatorError(
                    "unknown, restarted or substituted permit"
                )
            self._raise_transaction_cleanup_hold()
            prior = self._results.get(permit.nonce)
            if prior is not None:
                return prior
            if cancellation is not None:
                # Share the service's event with the worker and lifecycle checks.
                # A prior explicit core cancel remains latched; no watcher thread
                # or polling bridge can lose a cancellation during dispatch.
                if self._cancel_events[permit.nonce].is_set():
                    cancellation.set()
                self._cancel_events[permit.nonce] = cancellation
            if self._poisoned:
                raise CommissioningCoordinatorError(
                    "coordinator is held; no retry is allowed"
                )
            now = self._now()
            if not permit.issued_at_ns <= now < permit.expires_at_ns:
                raise CommissioningCoordinatorError(
                    "permit expired or was issued in the future"
                )
            registration = self._registry.get(permit.request.action_id)
            if registration != permit.registration:
                raise CommissioningCoordinatorError(
                    "registered campaign changed after preparation"
                )
            worker = self._workers[registration.worker_id]
            if (
                worker.worker_executable_sha256 != registration.worker_executable_sha256
                or worker.composition != self._composition
            ):
                raise CommissioningCoordinatorError(
                    "worker identity/hash changed before dispatch"
                )
            leases = self._leases(permit.request, registration)
            with self._transaction_scope(leases) as transaction:
                snapshot = self._admission(
                    transaction, permit.request, registration, leases
                )
                now = self._now()
                if now >= permit.expires_at_ns:
                    raise CommissioningCoordinatorError(
                        "permit expired while acquiring/rechecking leases"
                    )
                envelope = self._envelope(
                    transaction, permit.request, registration, snapshot, now
                )
                if snapshot != permit.admission or envelope != permit.envelope:
                    raise CommissioningCoordinatorError(
                        "admission/envelope changed after preparation"
                    )
                if (
                    envelope is not None
                    and now + registration.budget.timeout_ms * 1_000_000
                    > envelope.expires_at_ns
                ):
                    raise CommissioningCoordinatorError(
                        "energization envelope cannot cover the bounded campaign"
                    )
                intent_time = self._wall_clock()
                _integer(intent_time, "intent UTC timestamp", 0, 2**63 - 1)
                binding = AttemptBinding(
                    attempt_id=permit.attempt_id,
                    session_id=snapshot.session_id,
                    stage=snapshot.stage.value,
                    effect_class=registration.effect_class,
                    operation_id=registration.action_id,
                    operation_binding_sha256=permit.permit_sha256,
                    source_binding_sha256=snapshot.source_binding_sha256,
                    stage_plan_sha256=snapshot.stage_plan_sha256,
                    session_journal_head_sha256=snapshot.journal_head_sha256,
                    evidence_inventory_sha256=snapshot.evidence_inventory_sha256,
                    intent_at_ns=intent_time,
                )
                try:
                    transaction.begin_intent(binding, permit)
                except BaseException:
                    # There was no worker invocation. However, an uncertain
                    # publication must be reviewed before even a new intent.
                    self._poisoned = True
                    raise
                cancellation = self._cancel_events[permit.nonce]
                if cancellation.is_set():
                    result = AttemptResult(
                        permit.attempt_id,
                        AttemptState.ABORTED_PRE_EFFECT,
                        permit.permit_sha256,
                        ("CANCELLED_BEFORE_EFFECT",),
                        None,
                        False,
                        composition=self._composition,
                    )
                    try:
                        transaction.transition(permit.attempt_id, result.state, None)
                        transaction.retain_result(result)
                    except BaseException:
                        self._poisoned = True
                        raise
                    self._results[permit.nonce] = result
                    return result
                receipt = None
                caught: BaseException | None = None
                retained_uncertain_reasons: tuple[str, ...] | None = None
                try:
                    # A failed/ambiguous consume is conservative uncertainty,
                    # never permission to invoke the worker or try consume again.
                    transaction.consume_permit(permit)
                    armed_at = self._now()
                    if armed_at >= permit.expires_at_ns:
                        raise CommissioningCoordinatorError(
                            "permit expired before worker dispatch"
                        )
                    deadline = armed_at + registration.budget.timeout_ms * 1_000_000
                    if self._composition == PHYSICAL_CAMERA_COMPOSITION:
                        from .camera_activation_campaign_contract import (
                            CONFIGURATION_CAPTURE_ACTION_ID,
                            SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
                            validate_camera_activation_permit,
                        )

                        if registration.action_id in (
                            CONFIGURATION_CAPTURE_ACTION_ID,
                            SEALED_CONFIGURATION_CAPTURE_ACTION_ID,
                        ):
                            validate_camera_activation_permit(permit)
                            # The 25-second campaign budget is a ceiling, not a
                            # request to renew time consumed by original audits.
                            # Native preparation repeats its complete lifetime
                            # checks before process start and release.
                            deadline = min(deadline, permit.expires_at_ns)
                            if (
                                deadline - self._now()
                                < CAMERA_CONFIGURATION_MINIMUM_WINDOW_NS
                            ):
                                raise CommissioningCoordinatorError(
                                    "insufficient original permit time for settings capture lifecycle"
                                )
                    if self._composition in {
                        PHYSICAL_USB_IDENTITY_COMPOSITION,
                        PHYSICAL_USB_PRESENCE_COMPOSITION,
                    }:
                        # The fixed 25-second budget is a ceiling. Slow original
                        # audits may leave less; never extend or renew the
                        # consumed permit to recover that time. Still require
                        # the full prepared USB lifecycle, including cleanup.
                        # The runner repeats its floor checks before and after
                        # pinning and may refuse if those checks consume slack.
                        deadline = min(deadline, permit.expires_at_ns)
                        minimum_window = (
                            USB_PRESENCE_MINIMUM_WINDOW_NS
                            if self._composition == PHYSICAL_USB_PRESENCE_COMPOSITION
                            else USB_IDENTITY_MINIMUM_WINDOW_NS
                        )
                        if deadline - self._now() < minimum_window:
                            raise CommissioningCoordinatorError(
                                "insufficient original permit time for the prepared USB lifecycle"
                            )
                    # Intent and consumption can perform slow qualified writes.
                    # For energy-envelope campaigns the full window must still
                    # fit. A no-envelope camera permit authorizes only dispatch;
                    # its independent finite capture budget may outlive that
                    # permit's TTL. Preserve that existing distinction.
                    # Already armed means uncertainty, never envelope renewal.
                    if (
                        permit.envelope is not None
                        or registration.action_id in self._scoped_actions
                        or self._mode is CommissioningMode.PHYSICAL_DIAGNOSTIC
                    ) and deadline > min(
                        permit.expires_at_ns,
                        (
                            permit.envelope.expires_at_ns
                            if permit.envelope is not None
                            else permit.expires_at_ns
                        ),
                    ):
                        raise CommissioningCoordinatorError(
                            "full bounded campaign no longer fits the consumed permit/envelope"
                        )
                    retained_action = registration.action_id in self._retained_actions
                    if registration.action_id in self._scoped_actions:
                        from .camera_activation_campaign_contract import (
                            RetainedCameraActivationExecution,
                            is_camera_activation_action,
                            validate_camera_activation_execution,
                            validate_camera_activation_permit,
                        )
                        from rocell.application.consumed_commissioning_scope import (
                            ConsumedCommissioningScope,
                        )

                        camera_activation = is_camera_activation_action(permit)
                        if camera_activation:
                            if self._composition != PHYSICAL_CAMERA_COMPOSITION:
                                raise CommissioningCoordinatorError(
                                    "camera activation requires its original camera domain"
                                )
                            validate_camera_activation_permit(permit)
                        authority = ConsumedCommissioningScope(
                            permit,
                            transaction=transaction,
                            deadline_ns=deadline,
                            cancellation=cancellation,
                            monotonic_ns=self._now,
                        )
                        scope_error: BaseException | None = None
                        try:
                            execution = worker.run_scoped_campaign(  # type: ignore[attr-defined]
                                permit,
                                deadline_ns=deadline,
                                cancellation=cancellation,
                                authorization=authority,
                            )
                            try:
                                authority.require_completed_checks()
                            except BaseException as error:
                                # A revoked/expired scope cannot grant known
                                # completion. Still retain returned, bounded
                                # failure evidence under the original M1 leases
                                # when acknowledgement/storage remain valid.
                                scope_error = error
                        finally:
                            authority.close_scope()
                        if (
                            self._composition
                            in {
                                PHYSICAL_USB_IDENTITY_COMPOSITION,
                                PHYSICAL_USB_PRESENCE_COMPOSITION,
                            }
                            and type(execution) is RetainedUncertainCampaignExecution
                        ):
                            execution.__post_init__()
                            # Storage independently requires the original exact
                            # acknowledgement, even if a late scope check failed.
                            transaction.retain_campaign_evidence(
                                permit, execution.evidence
                            )
                            retained_uncertain_reasons = execution.reason_codes
                            if (
                                scope_error is not None
                                and "CONSUMED_SCOPE_REVALIDATION_FAILED"
                                not in retained_uncertain_reasons
                            ):
                                retained_uncertain_reasons += (
                                    "CONSUMED_SCOPE_REVALIDATION_FAILED",
                                )
                            raise CommissioningCoordinatorError(
                                "USB original diagnostics retained without complete device accounting"
                            )
                        if camera_activation:
                            from .camera_sealed_capture_contract import (
                                is_sealed_capture,
                                RetainedSealedCaptureExecution,
                                validate_sealed_capture_execution,
                            )

                            if is_sealed_capture(permit):
                                validate_sealed_capture_execution(
                                    execution, permit, expected_deadline_ns=deadline
                                )
                                assert type(execution) is RetainedSealedCaptureExecution
                            else:
                                validate_camera_activation_execution(
                                    execution, permit, expected_deadline_ns=deadline
                                )
                                assert (
                                    type(execution) is RetainedCameraActivationExecution
                                )
                            receipt = execution.receipt
                            transaction.retain_camera_activation_evidence(
                                permit, execution.evidence
                            )
                            retained_uncertain_reasons = execution.reason_codes
                            if scope_error is not None:
                                if (
                                    "CONSUMED_SCOPE_REVALIDATION_FAILED"
                                    not in retained_uncertain_reasons
                                ):
                                    retained_uncertain_reasons += (
                                        "CONSUMED_SCOPE_REVALIDATION_FAILED",
                                    )
                                raise scope_error
                            if receipt is None:
                                raise CommissioningCoordinatorError(
                                    "camera diagnostics retained without complete native accounting"
                                )
                        else:
                            if type(execution) is not RetainedCampaignExecution:
                                raise CommissioningCoordinatorError(
                                    "scoped worker returned no exact retained execution"
                                )
                            execution.__post_init__()
                            receipt = execution.receipt
                            transaction.retain_campaign_evidence(
                                permit, execution.evidence
                            )
                            if scope_error is not None:
                                raise scope_error
                            if (
                                receipt.evidence_sha256s
                                != tuple(
                                    item.payload_sha256 for item in execution.evidence
                                )
                                or type(receipt.output_bytes) is not int
                                or receipt.output_bytes
                                != sum(len(item.payload) for item in execution.evidence)
                            ):
                                raise CommissioningCoordinatorError(
                                    "scoped evidence differs from retained full bytes"
                                )
                    elif retained_action:
                        # The acknowledgement is scoped to this already durable
                        # EFFECT_ARMED transaction, not a reusable authorization
                        # callback handed to an arbitrary provider.
                        authorization_calls = 0
                        authorization_confirmed = False
                        authorization_live = True

                        def authorize_consumed(exact: ExactOperationPermit) -> None:
                            nonlocal authorization_calls, authorization_confirmed
                            if not authorization_live or authorization_calls:
                                raise CommissioningCoordinatorError(
                                    "consumed authorization is one-use and scope-bound"
                                )
                            authorization_calls += 1
                            if (
                                type(exact) is not ExactOperationPermit
                                or exact != permit
                                or cancellation.is_set()
                                or self._now() >= deadline
                            ):
                                raise CommissioningCoordinatorError(
                                    "consumed authorization binding/cancellation/deadline mismatch"
                                )
                            acknowledgement = cast(
                                Callable[[ExactOperationPermit], object],
                                transaction.assert_consumed_permit,
                            )(permit)
                            if acknowledgement is not None:
                                raise CommissioningCoordinatorError(
                                    "consumed transaction acknowledgement must be None"
                                )
                            authorization_confirmed = True

                        try:
                            execution = worker.run_retained_campaign(  # type: ignore[attr-defined]
                                permit,
                                deadline_ns=deadline,
                                cancellation=cancellation,
                                authorize_consumed_permit=authorize_consumed,
                            )
                        finally:
                            authorization_live = False
                        if type(execution) is not RetainedCampaignExecution:
                            raise CommissioningCoordinatorError(
                                "retained worker returned no exact execution evidence"
                            )
                        receipt = execution.receipt
                        execution.__post_init__()
                        if authorization_calls != 1 or not authorization_confirmed:
                            raise CommissioningCoordinatorError(
                                "retained worker did not acknowledge exact consumed authorization once"
                            )
                        # Even a known worker fault is retained before the
                        # uncertainty seal; absence/partial publication remains
                        # an unresolved/quarantined attempt, never known success.
                        transaction.retain_campaign_evidence(permit, execution.evidence)
                        if (
                            receipt.evidence_sha256s
                            != tuple(item.payload_sha256 for item in execution.evidence)
                            or type(receipt.output_bytes) is not int
                            or receipt.output_bytes
                            != sum(len(item.payload) for item in execution.evidence)
                        ):
                            raise CommissioningCoordinatorError(
                                "worker evidence hashes/byte count differ from retained full bytes"
                            )
                    else:
                        receipt = worker.run_campaign(
                            permit, deadline_ns=deadline, cancellation=cancellation
                        )
                    reasons = self._receipt_reasons(permit, receipt, deadline)
                    if not reasons:
                        transaction.transition(
                            permit.attempt_id, AttemptState.EFFECT_OBSERVED, receipt
                        )
                        transaction.transition(
                            permit.attempt_id, AttemptState.CLEANUP_CONFIRMED, receipt
                        )
                        if cancellation.is_set():
                            raise CommissioningCoordinatorError(
                                "cancellation observed before known-result publication"
                            )
                        result = AttemptResult(
                            permit.attempt_id,
                            AttemptState.SEALED_KNOWN,
                            permit.permit_sha256,
                            (),
                            receipt,
                            False,
                            composition=self._composition,
                        )
                        # Persist result evidence before sealing the attempt as known.
                        transaction.retain_result(result)
                        if retained_action and (
                            cancellation.is_set() or self._now() > deadline
                        ):
                            raise CommissioningCoordinatorError(
                                "retained campaign cancelled or expired before known seal"
                            )
                        transaction.transition(
                            permit.attempt_id, AttemptState.SEALED_KNOWN, receipt
                        )
                        self._results[permit.nonce] = result
                        return result
                except BaseException as exc:
                    caught = exc
                    reasons = retained_uncertain_reasons or (
                        "WORKER_OR_POST_ARM_PUBLICATION_FAILED",
                        type(exc).__name__,
                    )
                # Keep uncertainty publication outside the catch block: if it
                # fails it must never be retried by the exception handler.
                result = self._uncertain(
                    transaction,
                    permit,
                    reasons,
                    receipt if isinstance(receipt, WorkerReceipt) else None,
                )
                if caught is not None and not isinstance(caught, Exception):
                    raise caught
                return result

    def _uncertain(
        self,
        transaction: CommissioningTransaction,
        permit: ExactOperationPermit,
        reasons: tuple[str, ...],
        receipt: WorkerReceipt | None,
    ) -> AttemptResult:
        self._poisoned = True
        result = AttemptResult(
            permit.attempt_id,
            AttemptState.SEALED_UNCERTAIN,
            permit.permit_sha256,
            reasons,
            receipt,
            True,
            composition=self._composition,
        )
        # Never cache a success if the durable latch itself fails. Retain the
        # armed suffix, poison this process, and require store-level recovery.
        transaction.seal_uncertain(permit.attempt_id, reasons)
        transaction.retain_result(result)
        self._results[permit.nonce] = result
        return result


class PhysicalDiagnosticPreflightCoordinator(CellCommissioningCoordinator):
    """Real diagnostic storage, retained source checks only; no device release.

    A known NO_DEVICE_IO result is not canonical stage acceptance, a power
    observation, installed-hardware qualification, or authorization to connect.
    """


class PhysicalCameraAcquisitionCoordinator(CellCommissioningCoordinator):
    """Separate camera-only orchestration, not native runtime qualification.

    All actions require retained evidence and the original consumed scope.
    This constructor does not clear the native runner's physical release hold,
    pass prerequisites, admit arm effects, or authorize an energy envelope.
    """


class PhysicalUsbIdentityCoordinator(CellCommissioningCoordinator):
    """Exact policy-pinned USB query; no capture, serial or stage qualification."""

    def __init__(self, *, usb_query_policy_sha256: str, **kwargs: Any) -> None:
        _digest(usb_query_policy_sha256, "usb_query_policy_sha256")
        self._usb_query_policy_sha256 = usb_query_policy_sha256
        super().__init__(**kwargs)


class PhysicalUsbPresenceCoordinator(CellCommissioningCoordinator):
    """Exact physical-node presence domain, not USB descriptor/capture authority.

    The selected identity is a reviewed original phase binding. Every action
    needs CAMERA ownership, retained evidence and fresh consumed-scope checks;
    neither a known receipt nor absent-node diagnostics qualify the device.
    """

    def __init__(self, *, usb_presence_policy_sha256: str, **kwargs: Any) -> None:
        _digest(usb_presence_policy_sha256, "usb_presence_policy_sha256")
        self._usb_presence_policy_sha256 = usb_presence_policy_sha256
        super().__init__(**kwargs)
