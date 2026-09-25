"""Scoped coordinator bridge to the actual, hardware-incapable arm child.

An explicit factory builds the closed development runtime before admission.
Execution consumes one original permit and rechecks that same scope after file
pinning and immediately before RELEASE. Reopening verifies retained bytes only;
it neither rebuilds a runtime nor replays a serial transaction. Process cleanup,
simulated serial cleanup, and a separate synthetic power observation are distinct.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
from threading import Event, Lock
import time
from typing import Any

from .arm_feedback_rehearsal_campaign import (
    ArmFeedbackRehearsalPlan,
    _ACTUAL_EFFECTS,
    _canonical,
    _decode,
    _digest,
    _exact,
    _hash,
    _moment,
    _same,
)
from .cell_commissioning_coordinator import (
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
from .commissioning_m1_persistence import rehearsal_source_binding
from .consumed_commissioning_scope import ConsumedCommissioningScope
from .physical_connection_contracts import SingleT105FeedbackRequest, canonical_sha256
from .physical_onboarding import PhysicalOnboardingStage
from .physical_onboarding_attempts import canonical_json_bytes
from .physical_onboarding_leases import LeaseLevel
from .wizard_diagnostic_coordinator import require_regular_path, source_fingerprint
from .wizard_diagnostic_export import _directory_guard
from rocell.providers.windows.arm_feedback_worker import (
    ArmFeedbackBudget,
    ArmFeedbackCampaignRequest,
    ArmFeedbackCampaignResult,
    ArmFeedbackOutcome,
)
from rocell.providers.windows.arm_owned_protocol import (
    ADMISSION_TIMEOUT_MS,
    ArmOwnedRequest,
    LEGACY_REQUEST_SCHEMA,
    REQUEST_SCHEMA,
    SCENARIOS,
)
from rocell.providers.windows.arm_owned_evidence import (
    ArmOwnedEvidence,
    verify_arm_owned_evidence,
)
from rocell.providers.windows.owned_arm_feedback_package import (
    OwnedArmRuntime,
    prepare_owned_arm_runtime,
)
from rocell.providers.windows.owned_arm_feedback_runner import (
    ARM_PREPARATION_VERSIONS,
    IncapableOwnedArmFeedbackRunner,
    PreparedOwnedArmFeedback,
    prepare_owned_arm_feedback,
    reconstruct_owned_arm_feedback,
)
from rocell.safety.effects import EffectCertainty, EffectClass

SCHEMA = "rocell.rehearsal_owned_arm_feedback_campaign.v1"
ACTION_ID = "rehearsal-owned-arm-feedback"
WORKER_ID = "incapable-owned-arm-feedback-worker"


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _directory(directory: Path) -> Path:
    # Structural only: the caller supplies the independently audited M1 root.
    _require(
        isinstance(directory, Path)
        and directory.is_absolute()
        and ".." not in directory.parts
        and directory.name == "owned-arm-feedback"
        and not str(directory).startswith(("\\\\", "//")),
        "ASSIGNED_CAMPAIGN_DIRECTORY_REQUIRED",
    )
    return directory


def _operation(
    plan: ArmFeedbackRehearsalPlan,
    runtime: OwnedArmRuntime,
    directory: Path,
    scenario: str,
    *,
    request_schema: str = REQUEST_SCHEMA,
) -> dict[str, Any]:
    _require(
        type(plan) is ArmFeedbackRehearsalPlan and type(runtime) is OwnedArmRuntime,
        "EXACT_OWNED_CAMPAIGN_INPUTS_REQUIRED",
    )
    plan.__post_init__()
    doc = OwnedArmRuntime(runtime.payload).to_dict()
    _require(
        type(request_schema) is str
        and request_schema in ARM_PREPARATION_VERSIONS
        and doc["schema"] == ARM_PREPARATION_VERSIONS[request_schema][0],
        "OWNED_OPERATION_VERSION_MISMATCH",
    )
    _require(
        type(scenario) is str and scenario in SCENARIOS, "CLOSED_SCENARIO_REQUIRED"
    )
    _require(
        doc["workspace_source_sha256"] == plan.source_sha256,
        "RUNTIME_PLAN_SOURCE_MISMATCH",
    )
    return {
        "schema": (
            "rocell.owned_arm_feedback_operation.v2"
            if request_schema == REQUEST_SCHEMA
            else "rocell.owned_arm_feedback_operation.v1"
        ),
        "plan": plan.to_dict(),
        "runtime": doc,
        "runtime_sha256": runtime.runtime_sha256,
        "directory": str(_directory(directory)),
        "scenario": scenario,
        # The permit explicitly binds the IPC version and its fixed handshake
        # budget; a newer runtime cannot quietly reinterpret an old request.
        "ipc_request_schema": request_schema,
        "admission_timeout_ms": (
            2000
            if request_schema == "rocell.arm_owned_request.v1"
            else ADMISSION_TIMEOUT_MS
        ),
        "campaign_timeout_ms": 20000,
        "feedback_budget": asdict(ArmFeedbackBudget()),
        "feedback_maximum_line_bytes": 2048,
        "maximum_evidence_bytes": MAX_RETAINED_CAMPAIGN_BYTES,
        "composition": INCAPABLE_COMPOSITION,
        "physical_authority": False,
    }


def owned_feedback_registration(
    plan: ArmFeedbackRehearsalPlan,
    *,
    runtime: OwnedArmRuntime,
    directory: Path,
    scenario: str = "nominal",
) -> CampaignRegistration:
    return _operation_registration(
        runtime, _operation(plan, runtime, directory, scenario)
    )


def _operation_registration(
    runtime: OwnedArmRuntime, operation: dict[str, Any]
) -> CampaignRegistration:
    """Pure registration for an independently reconstructed exact operation."""
    return CampaignRegistration(
        ACTION_ID,
        PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION,
        EffectClass.SERIAL_OPEN_OR_WRITE,
        WORKER_ID,
        runtime.executable.sha256,
        _hash(operation),
        (LeaseLevel.ARM_CONTROLLER,),
        CampaignBudget(20000, MAX_RETAINED_CAMPAIGN_BYTES, 1, 512, 1, 0, 1),
    )


def _permit(
    plan: ArmFeedbackRehearsalPlan,
    permit: ExactOperationPermit,
    registration: CampaignRegistration,
) -> None:
    _require(type(permit) is ExactOperationPermit, "EXACT_PERMIT_REQUIRED")
    _require(
        permit.registration == registration
        and permit.request.action_id == ACTION_ID
        and permit.admission.mode is CommissioningMode.REHEARSAL
        and permit.admission.stage is PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION
        and permit.admission.source_binding_sha256
        == rehearsal_source_binding(plan.source_sha256)
        and permit.admission.selected_identity_sha256
        == plan.controller.identity.identity_sha256
        and permit.admission.challenge_sha256
        == permit.request.expected_challenge_sha256
        and permit.request.cell_id == permit.admission.cell_id
        and permit.request.session_id == permit.admission.session_id,
        "OWNED_CAMPAIGN_PERMIT_MISMATCH",
    )
    envelope = permit.envelope
    _require(envelope is not None, "EXACT_ENVELOPE_REQUIRED")
    assert envelope is not None
    _require(
        envelope.operation_sha256 == registration.operation_sha256
        and envelope.configuration_epoch_vector_sha256
        == hashlib.sha256(
            canonical_json_bytes(permit.admission.configuration_epoch_hashes)
        ).hexdigest()
        and envelope.required_initial_state is ObservedPowerState.DEENERGIZED
        and envelope.required_final_state is ObservedPowerState.DEENERGIZED,
        "EXACT_ENVELOPE_MISMATCH",
    )
    if plan.final_power_observation is not None:
        _require(
            plan.final_power_observation.observer_id == envelope.observer_id
            and envelope.observer_id != envelope.operator_id,
            "INDEPENDENT_SYNTHETIC_OBSERVER_REQUIRED",
        )


def _request(
    plan: ArmFeedbackRehearsalPlan,
    permit: ExactOperationPermit,
    started: int,
    deadline: int,
) -> ArmFeedbackCampaignRequest:
    assert permit.envelope is not None
    return ArmFeedbackCampaignRequest(
        campaign_id=permit.attempt_id,
        source_sha256=plan.source_sha256,
        operation_sha256=permit.registration.operation_sha256,
        energization_envelope_sha256=canonical_sha256(asdict(permit.envelope)),
        controller=plan.controller,
        feedback=SingleT105FeedbackRequest(
            permit.request.session_id,
            plan.controller.identity_receipt_sha256,
            plan.controller.identity.identity_sha256,
            plan.power_event_observation_sha256,
            permit.permit_sha256,
            "synthetic-" + permit.attempt_id,
            _moment(started),
            2048,
        ),
        expires_monotonic_ns=_moment(deadline),
        budget=ArmFeedbackBudget(),
    )


def _prepared(
    runtime: OwnedArmRuntime,
    request: ArmFeedbackCampaignRequest,
    permit: ExactOperationPermit,
    directory: Path,
    scenario: str,
    deadline: int,
    *,
    historical_request_schema: str | None = None,
) -> PreparedOwnedArmFeedback:
    assert permit.admission.selected_identity_sha256 is not None
    factory = (
        prepare_owned_arm_feedback
        if historical_request_schema is None
        else reconstruct_owned_arm_feedback
    )
    version = (
        {}
        if historical_request_schema is None
        else {"request_schema": historical_request_schema}
    )
    return factory(
        runtime,
        request,
        session_id=permit.request.session_id,
        permit_sha256=permit.permit_sha256,
        selected_identity_sha256=permit.admission.selected_identity_sha256,
        working_directory=directory / ("owned-arm-" + permit.attempt_id),
        scenario=scenario,
        deadline_ns=deadline,
        **version,
    )


def _observation(
    plan: ArmFeedbackRehearsalPlan,
    permit: ExactOperationPermit,
    owned_hash: str,
    feedback_hash: str | None,
    finished: int,
    observed: int,
) -> dict[str, Any] | None:
    spec = plan.final_power_observation
    if spec is None:
        return None
    _require(
        _moment(observed) >= _moment(finished),
        "OBSERVATION_PRECEDES_PROCESS_COMPLETION",
    )
    assert permit.envelope is not None
    value = {
        "schema": "rocell.owned_arm_synthetic_final_power_observation.v1",
        "origin": "SYNTHETIC_REHEARSAL",
        "observation_kind": "INDEPENDENT_POST_CAMPAIGN_FIXTURE",
        "observer_id": spec.observer_id,
        "observed_power_state": spec.observed_power_state.value,
        "observed_monotonic_ns": observed,
        "worker_finished_monotonic_ns": finished,
        "observed_after_worker": True,
        "permit_sha256": permit.permit_sha256,
        "owned_evidence_sha256": owned_hash,
        "feedback_evidence_sha256": feedback_hash,
        "source_sha256": plan.source_sha256,
        "binding_sha256": plan.binding_sha256,
        "power_event_observation_sha256": plan.power_event_observation_sha256,
        "energization_envelope_sha256": canonical_sha256(asdict(permit.envelope)),
        "physical_observation": False,
        "serial_close_used_to_infer_power": False,
        "process_cleanup_used_to_infer_power": False,
    }
    return {**value, "observation_sha256": _hash(value)}


@dataclass(frozen=True, slots=True)
class VerifiedOwnedArmFeedbackCampaign:
    _payload: bytes
    owned: ArmOwnedEvidence
    request: ArmFeedbackCampaignRequest

    def canonical_bytes(self) -> bytes:
        return self._payload

    @property
    def evidence_sha256(self) -> str:
        return hashlib.sha256(self._payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return _decode(self._payload)

    @property
    def result(self) -> ArmFeedbackCampaignResult | None:
        return self.owned.feedback.result if self.owned.feedback is not None else None

    def safe_summary(self) -> dict[str, Any]:
        if self.owned.feedback is not None:
            return self.owned.feedback.safe_summary()
        # Missing child evidence is not a manufactured feedback result. Nullable
        # counts prevent an incomplete process record being read as zero effects.
        return {
            "schema": "rocell.unavailable_owned_arm_feedback_summary.v1",
            "source_sha256": self.request.source_sha256,
            "request_sha256": self.request.request_sha256,
            "worker_outcome": "UNAVAILABLE",
            "technical_response_valid": False,
            "feedback_receipt_valid": False,
            "serial_cleanup_confirmed": False,
            "effect_uncertain": True,
            "api_counts": None,
            "final_power_state": "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
            "physical_authority": False,
            "arm_connected": False,
        }

    def process_summary(self) -> dict[str, Any]:
        return self.owned.safe_summary()

    def resolution_diagnostics(self) -> dict[str, Any]:
        """Full bounded metadata trace; never raw serial bytes or a new query."""
        trace = self.owned.resolution
        return {
            "status": "RETAINED" if trace is not None else "NOT_RETAINED",
            "trace": None if trace is None else trace.to_dict(),
            "trace_sha256": None if trace is None else trace.sha256,
            "physical_authority": False,
        }

    @property
    def final_power_observation(self) -> dict[str, Any] | None:
        return self.to_dict()["final_power_observation"]


def verify_retained_owned_arm_feedback_campaign(
    payload: bytes,
    *,
    expected_plan: ArmFeedbackRehearsalPlan,
    expected_permit: ExactOperationPermit,
    expected_evidence_sha256: str,
    expected_directory: Path,
) -> VerifiedOwnedArmFeedbackCampaign:
    """Pure historical verifier; expected directory comes from the original M1 store."""
    _require(
        type(payload) is bytes
        and hashlib.sha256(payload).hexdigest() == _digest(expected_evidence_sha256),
        "RETAINED_OWNED_CAMPAIGN_HASH_MISMATCH",
    )
    doc = _exact(
        _decode(payload),
        {
            "schema",
            "plan",
            "operation",
            "scenario",
            "permit_sha256",
            "request",
            "request_started_monotonic_ns",
            "deadline_monotonic_ns",
            "worker_finished_monotonic_ns",
            "owned_evidence",
            "owned_evidence_sha256",
            "final_power_observation",
            "actual_effect_counts",
            "physical_authority",
            "composition",
        },
    )
    _same(doc["schema"], SCHEMA, "owned campaign schema")
    _same(doc["plan"], expected_plan.to_dict(), "owned campaign plan")
    _require(type(doc["operation"]) is dict, "OPERATION_REQUIRED")
    runtime = OwnedArmRuntime(_canonical(doc["operation"].get("runtime")))
    # The first v1 producer had neither IPC tag in its operation. Select that
    # exact historical shape only from the strictly decoded original request;
    # missing/partial tags are never permission to guess a newer version.
    _require(type(doc["owned_evidence"]) is dict, "OWNED_REQUEST_REQUIRED")
    original_request = ArmOwnedRequest(_canonical(doc["owned_evidence"].get("request")))
    request_schema = original_request.to_dict()["schema"]
    version_fields = {"ipc_request_schema", "admission_timeout_ms"}
    present = version_fields.intersection(doc["operation"])
    _require(
        not present or present == version_fields,
        "OWNED_OPERATION_VERSION_PAIR_REQUIRED",
    )
    untagged_v1 = not present
    _require(
        (
            request_schema == LEGACY_REQUEST_SCHEMA
            if untagged_v1
            else doc["operation"]["ipc_request_schema"] == request_schema
        ),
        "OWNED_OPERATION_VERSION_MISMATCH",
    )
    operation = _operation(
        expected_plan,
        runtime,
        expected_directory,
        doc["scenario"],
        request_schema=request_schema,
    )
    if untagged_v1:
        # Preserve the original operation/permit hash domain byte-for-byte.
        # Never add fields to, migrate, or execute the retained v1 artifact.
        del operation["ipc_request_schema"], operation["admission_timeout_ms"]
    _same(doc["operation"], operation, "full operation")
    _permit(
        expected_plan,
        expected_permit,
        _operation_registration(runtime, operation),
    )
    _same(doc["permit_sha256"], expected_permit.permit_sha256, "consumed permit")
    _same(doc["actual_effect_counts"], _ACTUAL_EFFECTS, "physical effect counts")
    _same(doc["physical_authority"], False, "physical authority")
    _same(doc["composition"], INCAPABLE_COMPOSITION, "incapable composition")
    started, deadline, finished = (
        _moment(doc[k])
        for k in (
            "request_started_monotonic_ns",
            "deadline_monotonic_ns",
            "worker_finished_monotonic_ns",
        )
    )
    assert expected_permit.envelope is not None
    _require(
        expected_permit.issued_at_ns
        <= started
        < deadline
        <= expected_permit.expires_at_ns
        and deadline <= expected_permit.envelope.expires_at_ns
        and deadline
        <= started + expected_permit.registration.budget.timeout_ms * 1_000_000
        and finished >= started,
        "ORIGINAL_OWNED_CAMPAIGN_TIMING_MISMATCH",
    )
    request = _request(expected_plan, expected_permit, started, deadline)
    _same(doc["request"], request.to_dict(), "inner feedback request")
    prepared = _prepared(
        runtime,
        request,
        expected_permit,
        expected_directory,
        doc["scenario"],
        deadline,
        historical_request_schema=request_schema,
    )
    owned = verify_arm_owned_evidence(
        _canonical(doc["owned_evidence"]),
        expected_request=prepared.request,
        expected_evidence_sha256=_digest(doc["owned_evidence_sha256"]),
    )
    # The owned process includes admission and cleanup, not just feedback I/O.
    # Even an incomplete/malformed child result must not move its independent
    # post-process observation ahead of the retained process lifecycle.
    _require(
        finished >= started + owned.to_dict()["process"]["report"]["elapsed_ns"],
        "WRAPPER_COMPLETION_PRECEDES_PROCESS",
    )
    if owned.feedback is not None:
        result = owned.feedback.result
        _require(
            finished >= started + result.elapsed_ns
            and (
                result.closed_monotonic_ns is None
                or finished >= result.closed_monotonic_ns
            ),
            "WRAPPER_COMPLETION_PRECEDES_WORKER",
        )
    observation = doc["final_power_observation"]
    if expected_plan.final_power_observation is None:
        _same(observation, None, "absent independent power observation")
    else:
        _require(type(observation) is dict, "INDEPENDENT_OBSERVATION_MISSING")
        _same(
            observation,
            _observation(
                expected_plan,
                expected_permit,
                owned.evidence_sha256,
                owned.feedback.evidence_sha256 if owned.feedback is not None else None,
                finished,
                _moment(observation.get("observed_monotonic_ns")),
            ),
            "independent power observation",
        )
    return VerifiedOwnedArmFeedbackCampaign(payload, owned, request)


def prepare_owned_arm_feedback_campaign(
    plan: ArmFeedbackRehearsalPlan,
    *,
    workspace: Path,
    directory: Path,
    scenario: str = "nominal",
) -> OwnedArmFeedbackRehearsalCampaign:
    """Explicit development package build, called only on the selected wizard action."""
    _directory(directory)
    _require(
        type(plan) is ArmFeedbackRehearsalPlan and scenario in SCENARIOS,
        "EXACT_OWNED_CAMPAIGN_INPUTS_REQUIRED",
    )
    _require(
        source_fingerprint(workspace) == plan.source_sha256, "WORKSPACE_SOURCE_CHANGED"
    )
    runtime = prepare_owned_arm_runtime(
        workspace, workspace / "software/runs/owned-arm-packages"
    )
    require_regular_path(directory.parent, directory=True)
    with _directory_guard(directory.parent):
        _require(
            source_fingerprint(workspace) == plan.source_sha256,
            "WORKSPACE_SOURCE_CHANGED",
        )
        directory.mkdir(exist_ok=False)
        require_regular_path(directory, directory=True)
    return OwnedArmFeedbackRehearsalCampaign(
        plan, runtime=runtime, directory=directory, scenario=scenario
    )


def owned_feedback_checks(summary: dict[str, Any]) -> dict[str, bool]:
    """Independent predicates over the already-verified closed process summary."""
    process, native, handshake = (
        summary["process"],
        summary["native"],
        summary["handshake"],
    )
    checks = {
        "owned_process_cleanup": process["process_created"] is True
        and process["tree_exit_confirmed"] is True
        and process["cleanup_error_count"] == 0,
        "owned_process_completed": process["status"] == "SUCCEEDED"
        and process["initial_thread_resumed"] is True
        and process["returncode"] == 0
        and process["primary_error"] is None,
        "owned_release_handshake": handshake["ready_retained"] is True
        and handshake["release_retained"] is True
        and type(handshake["child_pid"]) is int,
        "nonpurging_native_cleanup": native is not None
        and native["native_cleanup_confirmed"] is True
        and native["pending_io_unresolved"] is False,
    }
    if summary["schema"] == "rocell.arm_owned_evidence_summary.v2":
        # A current nominal rehearsal needs both independently retained checks.
        # Historical v1 assessments keep their original predicates and remain
        # explicitly trace-unavailable in the UI, never retroactively upgraded.
        resolution = summary["resolution"]
        checks["controller_resolution_before_open_and_write"] = (
            resolution is not None
            and resolution["status"] == "PRE_WRITE_MATCHED"
            and resolution["attempt_count"] == 2
        )
    return checks


class OwnedArmFeedbackRehearsalCampaign:
    composition = INCAPABLE_COMPOSITION

    def __init__(
        self,
        plan: ArmFeedbackRehearsalPlan,
        *,
        runtime: OwnedArmRuntime,
        directory: Path,
        scenario: str = "nominal",
    ) -> None:
        self.plan, self.runtime, self.directory, self.scenario = (
            plan,
            runtime,
            directory,
            scenario,
        )
        self._operation_bytes = _canonical(
            _operation(plan, runtime, directory, scenario)
        )
        self.worker_executable_sha256 = runtime.executable.sha256
        self._used, self._lock = False, Lock()
        self.evidence: VerifiedOwnedArmFeedbackCampaign | None = None
        self.request: ArmFeedbackCampaignRequest | None = None

    def registration(self) -> CampaignRegistration:
        return owned_feedback_registration(
            self.plan,
            runtime=self.runtime,
            directory=self.directory,
            scenario=self.scenario,
        )

    def status(self) -> dict[str, Any]:
        return {
            "consumed": self._used,
            "composition": INCAPABLE_COMPOSITION,
            "physical_authority": False,
            "scenario": self.scenario,
        }

    def run_campaign(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("SCOPED_RETAINED_EXECUTION_REQUIRED")

    def run_retained_campaign(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("SCOPED_RETAINED_EXECUTION_REQUIRED")

    def run_scoped_campaign(
        self,
        permit: ExactOperationPermit,
        *,
        deadline_ns: int,
        cancellation: Event,
        authorization: ConsumedCommissioningScope,
    ) -> RetainedCampaignExecution:
        with self._lock:
            _require(not self._used, "OWNED_CAMPAIGN_ALREADY_CONSUMED")
            self._used = True
        _require(
            type(authorization) is ConsumedCommissioningScope
            and isinstance(cancellation, Event),
            "EXACT_CONSUMED_SCOPE_REQUIRED",
        )
        _permit(self.plan, permit, self.registration())
        _require(
            type(deadline_ns) is int
            and permit.issued_at_ns < deadline_ns <= permit.expires_at_ns,
            "ORIGINAL_CAMPAIGN_DEADLINE_REQUIRED",
        )
        sealed = canonical_json_bytes(asdict(permit))
        authorization.acknowledge(permit)

        def current() -> None:
            _require(
                not cancellation.is_set() and time.monotonic_ns() < deadline_ns,
                "OWNED_CAMPAIGN_CANCELLED_OR_EXPIRED",
            )
            _require(
                canonical_json_bytes(asdict(permit)) == sealed
                and _canonical(
                    _operation(self.plan, self.runtime, self.directory, self.scenario)
                )
                == self._operation_bytes
                and self.worker_executable_sha256 == self.runtime.executable.sha256,
                "SCOPED_OWNED_INPUTS_CHANGED",
            )
            _require(
                source_fingerprint(Path(self.runtime.to_dict()["workspace"]))
                == self.plan.source_sha256,
                "CURRENT_WORKSPACE_SOURCE_CHANGED",
            )

        current()
        require_regular_path(self.directory, directory=True)
        working = self.directory / ("owned-arm-" + permit.attempt_id)
        with _directory_guard(self.directory):
            current()
            working.mkdir(exist_ok=False)
        started = time.monotonic_ns()
        request = _request(self.plan, permit, started, deadline_ns)
        self.request = request
        prepared = _prepared(
            self.runtime, request, permit, self.directory, self.scenario, deadline_ns
        )
        prepared_bytes = prepared.payload

        def revalidate(exact: PreparedOwnedArmFeedback) -> None:
            current()
            _require(
                type(exact) is PreparedOwnedArmFeedback
                and exact.payload == prepared_bytes,
                "EXACT_OWNED_RUNNER_SCOPE_MISMATCH",
            )
            authorization.revalidate(permit)
            current()

        owned = IncapableOwnedArmFeedbackRunner(
            prepared, revalidate_consumed_permit=revalidate
        ).run(cancellation=cancellation, deadline_ns=deadline_ns)
        finished = time.monotonic_ns()
        observation = _observation(
            self.plan,
            permit,
            owned.evidence_sha256,
            owned.feedback.evidence_sha256 if owned.feedback is not None else None,
            finished,
            time.monotonic_ns(),
        )
        payload = _canonical(
            {
                "schema": SCHEMA,
                "plan": self.plan.to_dict(),
                "operation": _decode(self._operation_bytes),
                "scenario": self.scenario,
                "permit_sha256": permit.permit_sha256,
                "request": request.to_dict(),
                "request_started_monotonic_ns": started,
                "deadline_monotonic_ns": deadline_ns,
                "worker_finished_monotonic_ns": finished,
                "owned_evidence": owned.to_dict(),
                "owned_evidence_sha256": owned.evidence_sha256,
                "final_power_observation": observation,
                "actual_effect_counts": _ACTUAL_EFFECTS,
                "physical_authority": False,
                "composition": INCAPABLE_COMPOSITION,
            }
        )
        self.evidence = verify_retained_owned_arm_feedback_campaign(
            payload,
            expected_plan=self.plan,
            expected_permit=permit,
            expected_evidence_sha256=hashlib.sha256(payload).hexdigest(),
            expected_directory=self.directory,
        )
        artifact = CampaignEvidence(SCHEMA, "owned-arm-feedback-campaign", payload)
        result, summary = self.evidence.result, self.evidence.process_summary()
        checks = owned_feedback_checks(summary)
        complete = (
            summary["status"] == "COMPLETE_INCAPABLE_EVIDENCE"
            and all(checks.values())
            and result is not None
            and result.outcome is ArmFeedbackOutcome.SUCCEEDED_DIAGNOSTIC
        )
        counts = result.api_counts if result is not None else None
        serial_closed = (
            result is not None
            and result.connection_closed
            and counts is not None
            and counts.closes_confirmed == counts.open_attempts == 1
        )
        receipt = WorkerReceipt(
            permit.attempt_id,
            permit.permit_sha256,
            self.worker_executable_sha256,
            permit.admission.selected_identity_sha256,
            EffectCertainty.CONFIRMED if complete else EffectCertainty.UNCERTAIN,
            serial_closed
            and checks["owned_process_cleanup"]
            and checks["nonpurging_native_cleanup"],
            (
                ObservedPowerState.UNKNOWN
                if observation is None
                else ObservedPowerState(observation["observed_power_state"])
            ),
            counts.open_attempts if counts else 0,
            counts.read_attempts if counts else 0,
            counts.write_attempts if counts else 0,
            0,
            counts.close_attempts if counts else 0,
            len(payload),
            (artifact.payload_sha256,),
            INCAPABLE_COMPOSITION,
        )
        return RetainedCampaignExecution(receipt, (artifact,))
