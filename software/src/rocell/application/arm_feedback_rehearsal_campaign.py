"""Exact consumed-permit adapter for a memory-only stage-12 serial campaign.

No diagnostic shortcut, arbitrary serial factory, native backend or power-control
API is present. Full private evidence is returned to the coordinator's explicit
retention path; the coordinator persists it before sealing a known completion.
The separately specified post-worker power observation is explicitly synthetic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import re
from threading import Event, Lock
import time
from typing import Any

from rocell.application.cell_commissioning_coordinator import (
    CampaignBudget,
    CampaignEvidence,
    CampaignRegistration,
    CommissioningMode,
    ExactOperationPermit,
    INCAPABLE_COMPOSITION,
    MAX_RETAINED_CAMPAIGN_BYTES,
    ObservedPowerState,
    RetainedCampaignExecution,
    WorkerReceipt,
)
from rocell.application.commissioning_m1_persistence import rehearsal_source_binding
from rocell.application.physical_connection_contracts import (
    EvidenceOrigin,
    RoArmUsbSerialIdentity,
    SingleT105FeedbackRequest,
    canonical_sha256,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import canonical_json_bytes
from rocell.application.physical_onboarding_leases import LeaseLevel
from rocell.application.rehearsal_arm_feedback_evidence import (
    RehearsalArmFeedbackEvidence,
    retain_rehearsal_arm_feedback_evidence,
    verify_rehearsal_arm_feedback_evidence,
)
from rocell.providers.windows.arm_feedback_worker import (
    ArmFeedbackBudget,
    ArmFeedbackCampaignRequest,
    ArmFeedbackCampaignResult,
    ArmFeedbackOutcome,
    ArmFeedbackWorker,
    ArmFeedbackWorkerError,
    IncapableSerialBackend,
    IncapableSerialScenario,
    ReviewedControllerBinding,
    parse_arm_feedback_request,
)
from rocell.safety.effects import EffectCertainty, EffectClass


SCHEMA = "rocell.rehearsal_arm_feedback_campaign.v1"
PLAN_SCHEMA = "rocell.rehearsal_arm_feedback_plan.v1"
OBSERVATION_SCHEMA = "rocell.synthetic_final_power_observation.v1"
ACTION_ID = "rehearsal-arm-feedback"
WORKER_ID = "incapable-arm-feedback-worker"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_SCENARIOS = (
    "nominal",
    "boot-bytes",
    "short-write",
    "timeout",
    "identity-change",
    "close-failure",
    "malformed-response",
    "wrong-response",
    "extra-response",
)
_ACTUAL_EFFECTS = {
    "device_enumerations": 0,
    "device_opens": 0,
    "serial_transactions": 0,
    "robot_commands_sent": 0,
    "robot_power_operations": 0,
}


class ArmFeedbackRehearsalError(ValueError):
    """A closed incapable plan, permit, retained artifact or observation differs."""


def _digest(value: object) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None or value == "0" * 64:
        raise ArmFeedbackRehearsalError("an exact nonzero SHA-256 digest is required")
    return value


def _moment(value: object) -> int:
    if type(value) is not int or not 0 < value < 2**63:
        raise ArmFeedbackRehearsalError(
            "a positive monotonic integer timestamp is required"
        )
    return value


def _canonical(value: object) -> bytes:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise ArmFeedbackRehearsalError("invalid campaign JSON") from error
    if not 0 < len(payload) <= MAX_RETAINED_CAMPAIGN_BYTES:
        raise ArmFeedbackRehearsalError(
            "campaign exceeds its untruncated 128 KiB retention budget"
        )
    return payload


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _same(actual: object, expected: object, label: str) -> None:
    if _canonical(actual) != _canonical(expected):
        raise ArmFeedbackRehearsalError(f"{label} mismatch")


def _exact(value: object, keys: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ArmFeedbackRehearsalError("campaign object has missing or unknown fields")
    return value


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ArmFeedbackRehearsalError("duplicate campaign JSON field")
        result[key] = value
    return result


def _tree(value: object, depth: int = 0) -> None:
    if depth > 24:
        raise ArmFeedbackRehearsalError("campaign JSON nesting exceeds its bound")
    if type(value) is dict:
        if len(value) > 128 or any(
            type(key) is not str or len(key) > 256 for key in value
        ):
            raise ArmFeedbackRehearsalError("campaign object exceeds its bound")
        for item in value.values():
            _tree(item, depth + 1)
    elif type(value) is list:
        if len(value) > 1024:
            raise ArmFeedbackRehearsalError("campaign array exceeds its bound")
        for item in value:
            _tree(item, depth + 1)
    elif type(value) is str:
        if len(value) > MAX_RETAINED_CAMPAIGN_BYTES:
            raise ArmFeedbackRehearsalError("campaign text exceeds its bound")
    elif type(value) is int:
        if not -(2**63) < value < 2**63:
            raise ArmFeedbackRehearsalError("campaign integer exceeds its bound")
    elif type(value) is float:
        # The inner feedback contract validates all numeric fields. Floats in
        # a parsed pose are not a reason to lose raw evidence on a failed run.
        import math

        if not math.isfinite(value):
            raise ArmFeedbackRehearsalError("nonfinite campaign numeric value")
    elif value is not None and type(value) is not bool:
        raise ArmFeedbackRehearsalError("unsupported campaign value")


def _decode(payload: bytes) -> dict[str, Any]:
    if (
        type(payload) is not bytes
        or not 0 < len(payload) <= MAX_RETAINED_CAMPAIGN_BYTES
    ):
        raise ArmFeedbackRehearsalError("retained campaign must be bounded bytes")
    try:
        result = json.loads(payload.decode("ascii"), object_pairs_hook=_pairs)
        _tree(result)
        if type(result) is not dict or _canonical(result) != payload:
            raise ArmFeedbackRehearsalError(
                "retained campaign must use exact canonical JSON"
            )
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise ArmFeedbackRehearsalError("invalid retained campaign JSON") from error


@dataclass(frozen=True, slots=True)
class SyntheticFinalPowerObservationSpec:
    """An explicit fixture specification, never a preexisting measured receipt."""

    observer_id: str
    observed_power_state: ObservedPowerState

    def __post_init__(self) -> None:
        if type(self.observer_id) is not str or _ID.fullmatch(self.observer_id) is None:
            raise ArmFeedbackRehearsalError(
                "an exact distinct synthetic observer ID is required"
            )
        if type(self.observed_power_state) is not ObservedPowerState:
            raise ArmFeedbackRehearsalError(
                "synthetic final power requires a closed state enum"
            )

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "schema": "rocell.synthetic_final_power_observation_spec.v1",
            "observer_id": self.observer_id,
            "observed_power_state": self.observed_power_state.value,
            "purpose": "POST_WORKER_FIXTURE_SPECIFICATION_NOT_AN_OBSERVATION",
            "physical_observation": False,
        }


@dataclass(frozen=True, slots=True)
class ArmFeedbackRehearsalPlan:
    binding_sha256: str
    source_sha256: str
    controller: ReviewedControllerBinding
    power_event_observation_sha256: str
    scenario: str = "nominal"
    final_power_observation: SyntheticFinalPowerObservationSpec | None = None

    def __post_init__(self) -> None:
        for name in (
            "binding_sha256",
            "source_sha256",
            "power_event_observation_sha256",
        ):
            _digest(getattr(self, name))
        if (
            type(self.controller) is not ReviewedControllerBinding
            or self.controller.origin is not EvidenceOrigin.SYNTHETIC_REHEARSAL
        ):
            raise ArmFeedbackRehearsalError(
                "only an explicitly synthetic reviewed controller is admitted"
            )
        self.controller.__post_init__()
        if type(self.scenario) is not str or self.scenario not in _SCENARIOS:
            raise ArmFeedbackRehearsalError(
                "unknown closed incapable feedback scenario"
            )
        if self.final_power_observation is not None:
            if (
                type(self.final_power_observation)
                is not SyntheticFinalPowerObservationSpec
            ):
                raise ArmFeedbackRehearsalError(
                    "final-power input must be a synthetic specification"
                )
            self.final_power_observation.__post_init__()

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "schema": PLAN_SCHEMA,
            "binding_sha256": self.binding_sha256,
            "source_sha256": self.source_sha256,
            "controller": self.controller.to_dict(),
            "power_event_observation_sha256": self.power_event_observation_sha256,
            "scenario": self.scenario,
            "final_power_observation": (
                self.final_power_observation.to_dict()
                if self.final_power_observation
                else None
            ),
            "composition": INCAPABLE_COMPOSITION,
            "physical_authority": False,
        }

    @property
    def plan_sha256(self) -> str:
        return _hash(self.to_dict())


def _registration(
    plan: ArmFeedbackRehearsalPlan, worker_sha256: str
) -> CampaignRegistration:
    return CampaignRegistration(
        ACTION_ID,
        PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION,
        EffectClass.SERIAL_OPEN_OR_WRITE,
        WORKER_ID,
        _digest(worker_sha256),
        plan.plan_sha256,
        (LeaseLevel.ARM_CONTROLLER,),
        CampaignBudget(10000, MAX_RETAINED_CAMPAIGN_BYTES, 1, 512, 1, 0, 1),
    )


def _validate_permit(
    plan: ArmFeedbackRehearsalPlan, permit: ExactOperationPermit, worker_sha256: str
) -> None:
    if (
        type(plan) is not ArmFeedbackRehearsalPlan
        or type(permit) is not ExactOperationPermit
    ):
        raise ArmFeedbackRehearsalError("exact typed plan/permit required")
    plan.__post_init__()
    if (
        permit.registration != _registration(plan, worker_sha256)
        or permit.request.action_id != ACTION_ID
        or permit.admission.mode is not CommissioningMode.REHEARSAL
        or permit.admission.stage
        is not PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION
        or permit.admission.source_binding_sha256
        != rehearsal_source_binding(plan.source_sha256)
        or permit.admission.selected_identity_sha256
        != plan.controller.identity.identity_sha256
        or permit.admission.challenge_sha256 != permit.request.expected_challenge_sha256
        or permit.request.cell_id != permit.admission.cell_id
        or permit.request.session_id != permit.admission.session_id
    ):
        raise ArmFeedbackRehearsalError(
            "registered request/source/controller/admission differs from exact plan"
        )
    envelope = permit.envelope
    if (
        envelope is None
        or envelope.operation_sha256 != plan.plan_sha256
        or envelope.configuration_epoch_vector_sha256
        != hashlib.sha256(
            canonical_json_bytes(permit.admission.configuration_epoch_hashes)
        ).hexdigest()
        or envelope.required_initial_state is not ObservedPowerState.DEENERGIZED
        or envelope.required_final_state is not ObservedPowerState.DEENERGIZED
    ):
        raise ArmFeedbackRehearsalError(
            "exact source-bound energization envelope is required"
        )
    if plan.final_power_observation is not None and (
        plan.final_power_observation.observer_id != envelope.observer_id
        or plan.final_power_observation.observer_id == envelope.operator_id
    ):
        raise ArmFeedbackRehearsalError(
            "post-worker synthetic observer must match the independent envelope observer"
        )


def _request(
    plan: ArmFeedbackRehearsalPlan,
    permit: ExactOperationPermit,
    started_ns: int,
    deadline_ns: int,
) -> ArmFeedbackCampaignRequest:
    assert permit.envelope is not None
    return ArmFeedbackCampaignRequest(
        campaign_id=permit.attempt_id,
        source_sha256=plan.source_sha256,
        operation_sha256=plan.plan_sha256,
        energization_envelope_sha256=canonical_sha256(asdict(permit.envelope)),
        controller=plan.controller,
        feedback=SingleT105FeedbackRequest(
            permit.request.session_id,
            plan.controller.identity_receipt_sha256,
            plan.controller.identity.identity_sha256,
            plan.power_event_observation_sha256,
            permit.permit_sha256,
            "synthetic-" + permit.attempt_id,
            _moment(started_ns),
            2048,
        ),
        expires_monotonic_ns=min(_moment(deadline_ns), permit.expires_at_ns),
        budget=ArmFeedbackBudget(),
    )


def _context(
    plan: ArmFeedbackRehearsalPlan,
    permit: ExactOperationPermit,
    request: ArmFeedbackCampaignRequest,
) -> dict[str, Any]:
    return {
        "schema": "rocell.rehearsal_arm_feedback_campaign_context.v1",
        "plan_sha256": plan.plan_sha256,
        "permit_sha256": permit.permit_sha256,
        "attempt_id": permit.attempt_id,
        "request_sha256": request.request_sha256,
    }


def _observation(
    plan: ArmFeedbackRehearsalPlan,
    permit: ExactOperationPermit,
    feedback_hash: str,
    finished_ns: int,
    observed_ns: int,
) -> dict[str, Any] | None:
    spec = plan.final_power_observation
    if spec is None:
        return None
    if _moment(observed_ns) < _moment(finished_ns):
        raise ArmFeedbackRehearsalError(
            "final observation timestamp precedes worker completion"
        )
    assert permit.envelope is not None
    core = {
        "schema": OBSERVATION_SCHEMA,
        "origin": "SYNTHETIC_REHEARSAL",
        "observation_kind": "INDEPENDENT_POST_CAMPAIGN_FIXTURE",
        "observer_id": spec.observer_id,
        "observed_power_state": spec.observed_power_state.value,
        "observed_monotonic_ns": observed_ns,
        "worker_finished_monotonic_ns": finished_ns,
        "observed_after_worker": True,
        "permit_sha256": permit.permit_sha256,
        "feedback_evidence_sha256": feedback_hash,
        "source_sha256": plan.source_sha256,
        "binding_sha256": plan.binding_sha256,
        "power_event_observation_sha256": plan.power_event_observation_sha256,
        "energization_envelope_sha256": canonical_sha256(asdict(permit.envelope)),
        "physical_observation": False,
        "serial_close_used_to_infer_power": False,
    }
    return {**core, "observation_sha256": _hash(core)}


def _safe_observation(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    return {
        key: document[key]
        for key in (
            "schema",
            "origin",
            "observation_kind",
            "observer_id",
            "observed_power_state",
            "observed_after_worker",
            "permit_sha256",
            "feedback_evidence_sha256",
            "observation_sha256",
            "physical_observation",
            "serial_close_used_to_infer_power",
        )
    }


@dataclass(frozen=True, slots=True)
class VerifiedArmFeedbackCampaign:
    _payload: bytes
    _inner: RehearsalArmFeedbackEvidence
    _request: ArmFeedbackCampaignRequest

    def canonical_bytes(self) -> bytes:
        return self._payload

    @property
    def evidence_sha256(self) -> str:
        return hashlib.sha256(self._payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return _decode(self._payload)

    def safe_summary(self) -> dict[str, Any]:
        return self._inner.safe_summary()

    @property
    def request(self) -> ArmFeedbackCampaignRequest:
        return self._request

    @property
    def result(self) -> ArmFeedbackCampaignResult:
        return self._inner.result

    @property
    def final_power_observation(self) -> dict[str, Any] | None:
        return _safe_observation(self.to_dict()["final_power_observation"])


def verify_retained_arm_feedback_campaign(
    payload: bytes,
    *,
    expected_plan: ArmFeedbackRehearsalPlan,
    expected_permit: ExactOperationPermit,
    expected_evidence_sha256: str,
) -> VerifiedArmFeedbackCampaign:
    """Strict pure reconstruction from independently audited original M1 inputs."""
    if (
        type(payload) is not bytes
        or not 0 < len(payload) <= MAX_RETAINED_CAMPAIGN_BYTES
    ):
        raise ArmFeedbackRehearsalError("retained campaign must be bounded bytes")
    if type(expected_permit) is not ExactOperationPermit:
        raise ArmFeedbackRehearsalError(
            "retained verification requires the audited exact permit"
        )
    if hashlib.sha256(payload).hexdigest() != _digest(expected_evidence_sha256):
        raise ArmFeedbackRehearsalError("complete retained campaign digest mismatch")
    _validate_permit(
        expected_plan,
        expected_permit,
        expected_permit.registration.worker_executable_sha256,
    )
    document = _exact(
        _decode(payload),
        {
            "schema",
            "plan",
            "context",
            "worker_executable_sha256",
            "request",
            "request_started_monotonic_ns",
            "deadline_monotonic_ns",
            "worker_finished_monotonic_ns",
            "feedback_evidence",
            "feedback_evidence_sha256",
            "final_power_observation",
            "actual_effect_counts",
            "physical_authority",
            "composition",
        },
    )
    _same(document["schema"], SCHEMA, "campaign schema")
    _same(document["plan"], expected_plan.to_dict(), "campaign plan")
    _same(document["composition"], INCAPABLE_COMPOSITION, "incapable composition")
    _same(document["physical_authority"], False, "physical authority")
    _same(document["actual_effect_counts"], _ACTUAL_EFFECTS, "actual zero effects")
    _same(
        document["worker_executable_sha256"],
        expected_permit.registration.worker_executable_sha256,
        "registered worker source",
    )
    started, deadline, finished = (
        _moment(document[key])
        for key in (
            "request_started_monotonic_ns",
            "deadline_monotonic_ns",
            "worker_finished_monotonic_ns",
        )
    )
    if (
        not expected_permit.issued_at_ns <= started < expected_permit.expires_at_ns
        or deadline > expected_permit.expires_at_ns
        or deadline
        > started + expected_permit.registration.budget.timeout_ms * 1_000_000
        or finished < started
    ):
        raise ArmFeedbackRehearsalError(
            "retained campaign times differ from permit/budget"
        )
    request = _request(expected_plan, expected_permit, started, deadline)
    parsed_request = parse_arm_feedback_request(_canonical(document["request"]))
    _same(parsed_request.to_dict(), request.to_dict(), "exact retained request")
    context = _context(expected_plan, expected_permit, request)
    _same(document["context"], context, "complete campaign context")
    inner = verify_rehearsal_arm_feedback_evidence(
        _canonical(document["feedback_evidence"]),
        expected_request=request,
        expected_binding_sha256=_hash(context),
        expected_evidence_sha256=_digest(document["feedback_evidence_sha256"]),
        expected_source_sha256=expected_plan.source_sha256,
    )
    result = inner.result
    if finished < started + result.elapsed_ns or (
        result.closed_monotonic_ns is not None and finished < result.closed_monotonic_ns
    ):
        raise ArmFeedbackRehearsalError(
            "retained wrapper completion precedes worker result"
        )
    observed = document["final_power_observation"]
    if expected_plan.final_power_observation is None:
        _same(observed, None, "absent independent observation")
    else:
        if type(observed) is not dict:
            raise ArmFeedbackRehearsalError(
                "explicit post-worker synthetic observation is missing"
            )
        _same(
            observed,
            _observation(
                expected_plan,
                expected_permit,
                inner.evidence_sha256,
                finished,
                _moment(observed.get("observed_monotonic_ns")),
            ),
            "independent post-worker observation",
        )
    return VerifiedArmFeedbackCampaign(payload, inner, request)


class ArmFeedbackRehearsalCampaign:
    """One-use stage-12 composition, with no native dispatch alternative."""

    composition = INCAPABLE_COMPOSITION

    def __init__(
        self,
        plan: ArmFeedbackRehearsalPlan,
        *,
        worker_executable_sha256: str,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        wait: Callable[[Event, float], bool] = lambda event, seconds: event.wait(
            seconds
        ),
    ) -> None:
        if (
            type(plan) is not ArmFeedbackRehearsalPlan
            or not callable(monotonic_ns)
            or not callable(wait)
        ):
            raise ArmFeedbackRehearsalError(
                "closed plan and bounded clock/wait contract required"
            )
        plan.__post_init__()
        self.plan = plan
        self.worker_executable_sha256 = _digest(worker_executable_sha256)
        self._clock, self._wait, self._lock = monotonic_ns, wait, Lock()
        self._used = False
        self.evidence: VerifiedArmFeedbackCampaign | None = None
        self.request: ArmFeedbackCampaignRequest | None = None

    def registration(self) -> CampaignRegistration:
        return _registration(self.plan, self.worker_executable_sha256)

    def status(self) -> dict[str, Any]:
        return {
            "consumed": self._used,
            "composition": INCAPABLE_COMPOSITION,
            "physical_authority": False,
            "hardware_accessed": False,
            "evidence_available": self.evidence is not None,
        }

    def run_campaign(
        self, permit: ExactOperationPermit, *, deadline_ns: int, cancellation: Event
    ) -> WorkerReceipt:
        raise ArmFeedbackRehearsalError(
            "stage12 requires the coordinator's explicit durable retention path"
        )

    def run_retained_campaign(
        self,
        permit: ExactOperationPermit,
        *,
        deadline_ns: int,
        cancellation: Event,
        authorize_consumed_permit: Callable[[ExactOperationPermit], None],
    ) -> RetainedCampaignExecution:
        with self._lock:
            if self._used:
                raise ArmFeedbackRehearsalError(
                    "campaign adapter cannot replay a consumed request"
                )
            self._used = True
        _validate_permit(self.plan, permit, self.worker_executable_sha256)
        if type(cancellation) is not Event or not callable(authorize_consumed_permit):
            raise ArmFeedbackRehearsalError(
                "exact cancellation and consumed-authority acknowledgement required"
            )
        started = _moment(self._clock())
        if not permit.issued_at_ns <= started < permit.expires_at_ns:
            raise ArmFeedbackRehearsalError(
                "campaign permit expired before request construction"
            )
        request = _request(self.plan, permit, started, deadline_ns)
        self.request = request
        acknowledged = False

        def authorize(observed: ArmFeedbackCampaignRequest) -> None:
            nonlocal acknowledged
            if (
                acknowledged
                or observed is not request
                or observed.request_sha256 != request.request_sha256
            ):
                raise ArmFeedbackWorkerError(
                    "EXACT_PERMIT_REQUEST_MISMATCH",
                    "request authorization is exact and one-use",
                )
            acknowledged = True
            _validate_permit(self.plan, permit, self.worker_executable_sha256)
            _same(
                observed.to_dict(),
                _request(self.plan, permit, started, deadline_ns).to_dict(),
                "authorized request",
            )
            authorize_consumed_permit(permit)

        scenarios = {
            "nominal": IncapableSerialScenario(),
            "boot-bytes": IncapableSerialScenario(
                preexisting_bytes=b"SYNTHETIC boot bytes\n"
            ),
            "short-write": IncapableSerialScenario(short_write_count=1),
            "timeout": IncapableSerialScenario(response_bytes=b""),
            "identity-change": IncapableSerialScenario(),
            "close-failure": IncapableSerialScenario(fail_at=("close",)),
            "malformed-response": IncapableSerialScenario(response_bytes=b"not-json\n"),
            "wrong-response": IncapableSerialScenario(response_bytes=b'{"T":42}\n'),
            "extra-response": IncapableSerialScenario(
                response_bytes=IncapableSerialScenario().response_bytes + b"EXTRA\n"
            ),
        }
        identity_checks = 0

        def resolve(expected: RoArmUsbSerialIdentity) -> RoArmUsbSerialIdentity:
            nonlocal identity_checks
            identity_checks += 1
            if expected != self.plan.controller.identity:
                raise ArmFeedbackRehearsalError(
                    "memory identity selection differs from reviewed controller"
                )
            if self.plan.scenario == "identity-change" and identity_checks == 2:
                return replace(
                    expected,
                    port_name="COM43" if expected.port_name != "COM43" else "COM44",
                )
            return expected

        worker = ArmFeedbackWorker(
            authorizer=authorize,
            identity_resolver=resolve,
            backend=IncapableSerialBackend(scenarios[self.plan.scenario]),
            monotonic_ns=self._clock,
            wait=self._wait,
        )
        result = worker.run(request, cancellation=cancellation)
        finished = _moment(self._clock())
        context = _context(self.plan, permit, request)
        inner = retain_rehearsal_arm_feedback_evidence(
            request,
            result,
            binding_sha256=_hash(context),
            source_sha256=self.plan.source_sha256,
        )
        # This separate fixture runs after the serial worker. Its state comes
        # only from the explicit specification, never connection_closed/counts.
        observation = _observation(
            self.plan, permit, inner.evidence_sha256, finished, _moment(self._clock())
        )
        document = {
            "schema": SCHEMA,
            "plan": self.plan.to_dict(),
            "context": context,
            "worker_executable_sha256": self.worker_executable_sha256,
            "request": request.to_dict(),
            "request_started_monotonic_ns": started,
            "deadline_monotonic_ns": deadline_ns,
            "worker_finished_monotonic_ns": finished,
            "feedback_evidence": inner.to_dict(),
            "feedback_evidence_sha256": inner.evidence_sha256,
            "final_power_observation": observation,
            "actual_effect_counts": _ACTUAL_EFFECTS,
            "physical_authority": False,
            "composition": INCAPABLE_COMPOSITION,
        }
        payload = _canonical(document)
        self.evidence = verify_retained_arm_feedback_campaign(
            payload,
            expected_plan=self.plan,
            expected_permit=permit,
            expected_evidence_sha256=hashlib.sha256(payload).hexdigest(),
        )
        artifact = CampaignEvidence(SCHEMA, "arm-feedback-campaign", payload)
        counts = result.api_counts
        receipt = WorkerReceipt(
            permit.attempt_id,
            permit.permit_sha256,
            self.worker_executable_sha256,
            permit.admission.selected_identity_sha256,
            (
                EffectCertainty.CONFIRMED
                if result.outcome is ArmFeedbackOutcome.SUCCEEDED_DIAGNOSTIC
                else EffectCertainty.UNCERTAIN
            ),
            result.connection_closed
            and counts.closes_confirmed == counts.open_attempts == 1,
            (
                ObservedPowerState.UNKNOWN
                if observation is None
                else ObservedPowerState(observation["observed_power_state"])
            ),
            counts.open_attempts,
            counts.read_attempts,
            counts.write_attempts,
            0,
            counts.close_attempts,
            len(payload),
            (artifact.payload_sha256,),
        )
        return RetainedCampaignExecution(receipt, (artifact,))


__all__ = [
    "SCHEMA",
    "PLAN_SCHEMA",
    "ACTION_ID",
    "WORKER_ID",
    "ArmFeedbackRehearsalError",
    "SyntheticFinalPowerObservationSpec",
    "ArmFeedbackRehearsalPlan",
    "ArmFeedbackRehearsalCampaign",
    "VerifiedArmFeedbackCampaign",
    "verify_retained_arm_feedback_campaign",
]
