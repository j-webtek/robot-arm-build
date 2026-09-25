from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from rocell.application.mission_journal import (
    ActionJournalState,
    MissionJournalError,
    ZeroAuthorityMissionJournal,
)
from rocell.application.multi_action_mission import (
    ActionOutcomeReceipt,
    AuthorizationV2MissionCursor,
    BoundOpaqueValue,
    BoundaryStatus,
    CompletedMissionAuthorizationCursor,
    MissionBoundary,
    MissionCommandAuthorizationBinding,
    MultiActionMissionError,
    MultiActionMissionReport,
    MultiActionMissionSpec,
    MultiActionSpec,
    ObservedSemanticOutcome,
    SimulationCommandAuthorizationCursor,
    build_mission_authorization_schedule,
    prepare_zero_authority_mission_journals,
    reopen_zero_authority_mission_journals,
    run_zero_authority_multi_action_mission,
)
from rocell.application.runtime_emulation import (
    DeterministicControllerPort,
    RuntimeEmulationFault,
    RuntimeEmulationFaultTrigger,
    make_deterministic_runtime_ports,
)
from rocell.application.runtime_ports import (
    ArmExecutionPort,
    ArmExecutionRequest,
    ArmExecutionResult,
    CancellationCheck,
    CancellationPort,
    CancellationStatus,
    ClockPort,
    LifecycleRequest,
    LifecycleResult,
    MissionRuntimePorts,
    OutcomeObservation,
    OutcomeObserverPort,
    OutcomeRequest,
    RuntimeAuthority,
    RuntimeContractError,
    RuntimeExecutionMode,
    RuntimeInstant,
    RuntimePortMetadata,
)
from rocell.calibration.static_phase1_requirements import (
    STATIC_OVERHEAD_PHASE1_GRAPH,
)
from rocell.safety.authorization_v2 import (
    AuthorizationContinuityEvidence,
    AuthorizationEvidence,
    BuildReleaseIdentity,
    CalibrationArtifactBinding,
    CalibrationClosureEvidence,
    CollisionClearanceState,
    CollisionTrajectoryEvidence,
    ControllerSessionEvidence,
    EvidenceOnlyReleaseScope,
    InterlockChannel,
    InterlockChannelEvidence,
    InterlockEvidenceBundle,
    InterlockEvidenceState,
    NamedSha256,
    OperatorArmEvidence,
    SimulatedContactCapability,
    continuity_from_authorization,
    trajectory_sequence_sha256,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _bound(value: object, binding: str) -> BoundOpaqueValue[object]:
    payload = json.dumps(
        {"binding": binding, "value": value},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return BoundOpaqueValue(payload)


def _action(key: str) -> MultiActionSpec[object, object]:
    return MultiActionSpec(
        action_id=f"key-{key}",
        hover_command=_bound({"phase": "hover", "key": key}, f"{key}-hover"),
        approach_command=_bound(
            {"phase": "approach", "key": key}, f"{key}-approach"
        ),
        contact_command=_bound(
            {"phase": "contact", "key": key}, f"{key}-contact-command"
        ),
        retract_command=_bound(
            {"phase": "retract", "key": key}, f"{key}-retract"
        ),
        device_contact=_bound({"key": key}, f"{key}-device-contact"),
        expected_outcome=cast(
            BoundOpaqueValue[bytes],
            _bound({"activated_key": key}, f"{key}-expected-outcome"),
        ),
        route_authorization_sha256=_digest(f"collision-cleared-route-{key}"),
    )


def _spec(
    text: str = "test",
    *,
    deadline_expiry_boundary: MissionBoundary | None = None,
    deadline_expiry_action_index: int | None = None,
) -> MultiActionMissionSpec[object, object]:
    return MultiActionMissionSpec(
        mission_id="keyboard-test-mission",
        actions=tuple(_action(key) for key in text),
        park_command=_bound({"phase": "park"}, "mission-park"),
        preflight_binding_sha256=_digest("zero-authority-preflight"),
        deadline_expiry_boundary=deadline_expiry_boundary,
        deadline_expiry_action_index=deadline_expiry_action_index,
    )


def _journals(
    tmp_path: Path,
    spec: MultiActionMissionSpec[object, object],
) -> tuple[ZeroAuthorityMissionJournal, ...]:
    root = tmp_path / "journals"
    root.mkdir(parents=True)
    return prepare_zero_authority_mission_journals(root, spec, created_at_ns=100)


def _controller_evidence() -> ControllerSessionEvidence:
    return ControllerSessionEvidence(
        arm_hardware_id="roarm-m3-pro-received-0001",
        controller_hardware_id="esp32-controller-received-0001",
        firmware_build_id="waveshare-firmware-observed-0001",
        firmware_sha256=_digest("firmware"),
        connection_session_id="connection-session-0001",
        persistent_port_id="usb-port-controller-persistent-0001",
        transport_descriptor_sha256=_digest("transport"),
    )


def _build_evidence() -> BuildReleaseIdentity:
    return BuildReleaseIdentity(
        active_build_id="rc03-received-build-0001",
        build_snapshot_sha256=_digest("build"),
        manifest_id="rc03-system-manifest",
        manifest_sha256=_digest("manifest"),
        release_receipt_id="simulation-evidence-receipt-0001",
        release_receipt_sha256=_digest("release"),
        scope=EvidenceOnlyReleaseScope.SIMULATION_EVIDENCE_ONLY,
    )


def _calibration_evidence() -> CalibrationClosureEvidence:
    artifact_ids = STATIC_OVERHEAD_PHASE1_GRAPH.device_closure("keyboard")
    artifact_hashes = {
        artifact_id: _digest(f"artifact:{artifact_id}")
        for artifact_id in artifact_ids
    }
    context_hashes = {
        context_id: _digest(f"context:{context_id}")
        for artifact_id in artifact_ids
        for context_id in STATIC_OVERHEAD_PHASE1_GRAPH.requirements[
            artifact_id
        ].context_dependencies
    }
    return CalibrationClosureEvidence(
        capability=SimulatedContactCapability.KEYBOARD,
        graph_id=STATIC_OVERHEAD_PHASE1_GRAPH.graph_id,
        graph_sha256=STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash,
        artifacts=tuple(
            CalibrationArtifactBinding(
                artifact_id=artifact_id,
                artifact_sha256=artifact_hashes[artifact_id],
                dependency_hashes=tuple(
                    NamedSha256(parent, artifact_hashes[parent])
                    for parent in STATIC_OVERHEAD_PHASE1_GRAPH.requirements[
                        artifact_id
                    ].prerequisites
                ),
                context_hashes=tuple(
                    NamedSha256(context, context_hashes[context])
                    for context in STATIC_OVERHEAD_PHASE1_GRAPH.requirements[
                        artifact_id
                    ].context_dependencies
                ),
            )
            for artifact_id in artifact_ids
        ),
    )


def _interlocks(
    *,
    sequence: int,
    captured: float,
    state: InterlockEvidenceState = InterlockEvidenceState.PASS,
) -> InterlockEvidenceBundle:
    return InterlockEvidenceBundle(
        channels=tuple(
            InterlockChannelEvidence(
                channel=channel,
                source_id=f"{channel.value}-source",
                sequence=sequence,
                captured_monotonic=captured,
                raw_sha256=_digest(
                    f"{channel.value}:{sequence}:{captured:.6f}"
                ),
                state=state,
            )
            for channel in InterlockChannel
        )
    )


def _authorization(
    spec: MultiActionMissionSpec[object, object],
    journals: tuple[ZeroAuthorityMissionJournal, ...],
    *,
    deny_relative_ordinal: int | None = None,
) -> AuthorizationV2MissionCursor | CompletedMissionAuthorizationCursor:
    snapshots = tuple(journal.snapshot() for journal in journals)
    bindings = build_mission_authorization_schedule(spec, snapshots)
    if not bindings:
        return CompletedMissionAuthorizationCursor(spec.plan_sha256)
    commands = tuple(binding.simulation_command for binding in bindings)
    grouped: list[str] = []
    for binding in bindings:
        if not grouped or grouped[-1] != binding.action_occurrence_sha256:
            grouped.append(binding.action_occurrence_sha256)
    initial_interlocks = _interlocks(sequence=0, captured=99.8)
    evidence = AuthorizationEvidence(
        capability=SimulatedContactCapability.KEYBOARD,
        controller=_controller_evidence(),
        build_release=_build_evidence(),
        calibration=_calibration_evidence(),
        collision=CollisionTrajectoryEvidence(
            report_sha256=_digest("collision-report"),
            cleared_trajectory_sha256=trajectory_sequence_sha256(commands),
            state=CollisionClearanceState.CLEAR_FOR_SIMULATION,
        ),
        device_state_sha256=_digest("keyboard-device-state"),
        interlocks=initial_interlocks,
        operator_arm=OperatorArmEvidence(
            operator_id="operator-local-0001",
            nonce_sha256=_digest("operator-nonce"),
            armed_at_monotonic=99.0,
            expires_at_monotonic=130.0,
        ),
        plan_sha256=spec.plan_sha256,
        ordered_action_occurrence_ids=tuple(grouped),
        ordered_commands=commands,
    )

    def continuity(
        _binding: MissionCommandAuthorizationBinding,
        relative_ordinal: int,
    ) -> tuple[AuthorizationContinuityEvidence, float]:
        now = 100.0 + (relative_ordinal + 1) * 0.001
        return (
            continuity_from_authorization(
                evidence,
                interlocks=_interlocks(
                    sequence=relative_ordinal + 1,
                    captured=now - 0.1,
                    state=(
                        InterlockEvidenceState.FAIL
                        if relative_ordinal == deny_relative_ordinal
                        else InterlockEvidenceState.PASS
                    ),
                ),
            ),
            now,
        )

    return AuthorizationV2MissionCursor.issue(
        evidence=evidence,
        bindings=bindings,
        starting_ordinal=bindings[0].absolute_ordinal,
        continuity_supplier=continuity,
        ttl_s=20.0,
        now_monotonic=100.0,
    )


class _SemanticOutcomePort:
    """Test adapter that gives the fake observer explicit device semantics."""

    def __init__(
        self,
        base: OutcomeObserverPort[object],
        spec: MultiActionMissionSpec[object, object],
        *,
        wrong_semantic_index: int | None = None,
        wrong_occurrence_index: int | None = None,
        wrong_events_index: int | None = None,
    ) -> None:
        self.runtime_metadata = base.runtime_metadata
        self._base = base
        self._expected_outcomes = tuple(
            action.expected_outcome for action in spec.actions
        )
        self._occurrence_ids = tuple(
            occurrence.occurrence_id for occurrence in spec.occurrences
        )
        self._event_ids = tuple(
            f"event-{spec.operation_id(MissionBoundary.DEVICE_CONTACT, index)}"
            for index in range(len(spec.actions))
        )
        self._wrong_semantic_index = wrong_semantic_index
        self._wrong_occurrence_index = wrong_occurrence_index
        self._wrong_events_index = wrong_events_index

    def observe_outcome(
        self, request: OutcomeRequest, cancellation: CancellationPort
    ) -> OutcomeObservation[object]:
        observed = self._base.observe_outcome(request, cancellation)
        if not observed.valid:
            return observed
        assert request.action_index is not None
        index = request.action_index
        expected = self._expected_outcomes[index]
        semantic = (
            BoundOpaqueValue(b'{"wrong":"meaning"}')
            if index == self._wrong_semantic_index
            else expected
        )
        occurrence_id = self._occurrence_ids[index]
        if index == self._wrong_occurrence_index:
            occurrence_id = self._occurrence_ids[(index + 1) % len(self._occurrence_ids)]
            if occurrence_id == self._occurrence_ids[index]:
                occurrence_id = "occ-" + "0" * 32
        event_id = (
            "event-wrong-contact"
            if index == self._wrong_events_index
            else self._event_ids[index]
        )
        return OutcomeObservation(
            observed.checkpoint_id,
            observed.observed_at,
            observed.sequence,
            ObservedSemanticOutcome(
                occurrence_id,
                semantic,
                (event_id,),
            ),
            True,
        )


def _ports(
    spec: MultiActionMissionSpec[object, object],
    triggers: tuple[RuntimeEmulationFaultTrigger, ...] = (),
    *,
    mode: RuntimeExecutionMode = RuntimeExecutionMode.VIRTUAL,
    wrong_semantic_index: int | None = None,
    wrong_occurrence_index: int | None = None,
    wrong_events_index: int | None = None,
) -> MissionRuntimePorts[object, object, object, object, object]:
    base = cast(
        MissionRuntimePorts[object, object, object, object, object],
        make_deterministic_runtime_ports(
            "multi-action-runtime",
            execution_mode=mode,
            fault_triggers=triggers,
        ),
    )
    return replace(
        base,
        outcome_observer=_SemanticOutcomePort(
            base.outcome_observer,
            spec,
            wrong_semantic_index=wrong_semantic_index,
            wrong_occurrence_index=wrong_occurrence_index,
            wrong_events_index=wrong_events_index,
        ),
    )


def _run(
    tmp_path: Path,
    spec: MultiActionMissionSpec[object, object],
    *,
    triggers: tuple[RuntimeEmulationFaultTrigger, ...] = (),
    mode: RuntimeExecutionMode = RuntimeExecutionMode.VIRTUAL,
) -> tuple[
    MissionRuntimePorts[object, object, object, object, object],
    tuple[ZeroAuthorityMissionJournal, ...],
    MultiActionMissionReport,
]:
    ports = _ports(spec, triggers, mode=mode)
    journals = _journals(tmp_path, spec)
    return ports, journals, run_zero_authority_multi_action_mission(
        ports, spec, journals, _authorization(spec, journals)
    )


@pytest.mark.parametrize(
    "mode", (RuntimeExecutionMode.VIRTUAL, RuntimeExecutionMode.REPLAY)
)
def test_keyboard_test_runs_in_exact_safe_order_with_zero_authority(
    tmp_path: Path, mode: RuntimeExecutionMode
) -> None:
    spec = _spec("test")
    ports, journals, untyped_report = _run(tmp_path, spec, mode=mode)
    report = untyped_report

    assert report.passed is True
    assert report.primary_failure is None
    assert report.cleanup_failures == ()
    assert report.zero_authority is True
    assert report.hardware_accessed is False
    assert report.hardware_commands_generated == 0
    assert report.plan_sha256 == spec.plan_sha256
    assert report.occurrence_ids == tuple(
        occurrence.occurrence_id for occurrence in spec.occurrences
    )
    assert report.final_states == (ActionJournalState.PARKED,) * 4
    assert len(set(report.occurrence_ids)) == 4
    assert spec.occurrences[0].action_sha256 == spec.occurrences[3].action_sha256
    assert spec.occurrences[0].occurrence_id != spec.occurrences[3].occurrence_id

    per_action = (
        MissionBoundary.ACTION_GATE,
        MissionBoundary.PRE_MOTION_FEEDBACK,
        MissionBoundary.FRESH_OBSERVATION,
        MissionBoundary.ROUTE_AUTHORIZATION,
        MissionBoundary.HOVER_EXECUTE,
        MissionBoundary.APPROACH_EXECUTE,
        MissionBoundary.JOURNAL_PRE_CONTACT,
        MissionBoundary.JOURNAL_CONTACT_BOUNDARY,
        MissionBoundary.CONTACT_EXECUTE,
        MissionBoundary.CONTACT_FEEDBACK,
        MissionBoundary.DEVICE_CONTACT,
        MissionBoundary.OUTCOME_OBSERVATION,
        MissionBoundary.JOURNAL_OUTCOME_CONFIRMED,
        MissionBoundary.RETRACT_EXECUTE,
        MissionBoundary.RETRACT_FEEDBACK,
        MissionBoundary.JOURNAL_RETRACTED,
    )
    for index in range(4):
        assert tuple(
            record.boundary
            for record in report.records
            if record.action_index == index
            and record.boundary is not MissionBoundary.JOURNAL_PARKED
        ) == per_action
        boundary_positions = {
            record.boundary: ordinal
            for ordinal, record in enumerate(report.records)
            if record.action_index == index
        }
        assert boundary_positions[MissionBoundary.JOURNAL_CONTACT_BOUNDARY] < (
            boundary_positions[MissionBoundary.CONTACT_EXECUTE]
        )
        assert boundary_positions[MissionBoundary.JOURNAL_CONTACT_BOUNDARY] < (
            boundary_positions[MissionBoundary.DEVICE_CONTACT]
        )

    assert len(report.records) == 77
    assert len(report.authorization_receipt_sha256s) == 17
    assert len(report.outcome_receipts) == 4
    assert report.authorization_complete is True
    assert report.journals_verified is True
    assert len(report.contact_operation_ids) == 8
    assert all(record.status is BoundaryStatus.PASSED for record in report.records)
    assert [event.state for event in journals[0].snapshot().events] == [
        ActionJournalState.INTENT_COMMITTED,
        ActionJournalState.PRE_CONTACT,
        ActionJournalState.CONTACT_MAY_HAVE_OCCURRED,
        ActionJournalState.OUTCOME_CONFIRMED,
        ActionJournalState.RETRACTED,
        ActionJournalState.PARKED,
    ]
    controller = ports.arm_execution
    assert isinstance(controller, DeterministicControllerPort)
    assert controller.state == "CLOSED"
    assert report.report_sha256 == report.to_dict()["report_sha256"]


def test_nominal_report_and_occurrences_are_deterministic(tmp_path: Path) -> None:
    spec = _spec("tt")
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first_journals = prepare_zero_authority_mission_journals(
        first_root, spec, created_at_ns=100
    )
    second_journals = prepare_zero_authority_mission_journals(
        second_root, spec, created_at_ns=100
    )
    first = run_zero_authority_multi_action_mission(
        _ports(spec), spec, first_journals, _authorization(spec, first_journals)
    )
    second = run_zero_authority_multi_action_mission(
        _ports(spec), spec, second_journals, _authorization(spec, second_journals)
    )

    assert first.to_dict() == second.to_dict()
    assert first.report_sha256 == second.report_sha256
    assert spec.occurrences[0].action_sha256 == spec.occurrences[1].action_sha256
    assert spec.occurrences[0].occurrence_id != spec.occurrences[1].occurrence_id


def test_one_action_cannot_normalize_a_double_activation_as_success() -> None:
    base = _action("t")

    with pytest.raises(ValueError, match="exactly one device activation"):
        replace(base, required_activation_count=2)


_PORT_FAULT_CASES = (
    (MissionBoundary.CONNECT, None, RuntimeEmulationFault.TIMEOUT, "ARM_TIMEOUT"),
    (MissionBoundary.REFERENCE, None, RuntimeEmulationFault.RESET, "ARM_RESET"),
    (
        MissionBoundary.ACTION_GATE,
        0,
        RuntimeEmulationFault.CANCELLED,
        "OPERATION_CANCELLED",
    ),
    (
        MissionBoundary.PRE_MOTION_FEEDBACK,
        0,
        RuntimeEmulationFault.STALE_FEEDBACK,
        "ARM_FEEDBACK_STALE",
    ),
    (
        MissionBoundary.FRESH_OBSERVATION,
        0,
        RuntimeEmulationFault.OBSERVATION_FAILURE,
        "EMULATED_OBSERVATION_FAILURE",
    ),
    (
        MissionBoundary.ROUTE_AUTHORIZATION,
        0,
        RuntimeEmulationFault.CANCELLED,
        "OPERATION_CANCELLED",
    ),
    (
        MissionBoundary.HOVER_EXECUTE,
        0,
        RuntimeEmulationFault.DISCONNECT,
        "ARM_DISCONNECT",
    ),
    (
        MissionBoundary.APPROACH_EXECUTE,
        0,
        RuntimeEmulationFault.RESET,
        "ARM_RESET",
    ),
    (
        MissionBoundary.CONTACT_EXECUTE,
        0,
        RuntimeEmulationFault.DISCONNECT,
        "ARM_DISCONNECT",
    ),
    (
        MissionBoundary.CONTACT_FEEDBACK,
        0,
        RuntimeEmulationFault.STALE_FEEDBACK,
        "ARM_FEEDBACK_STALE",
    ),
    (
        MissionBoundary.DEVICE_CONTACT,
        0,
        RuntimeEmulationFault.CONTACT_FAILURE,
        "EMULATED_CONTACT_FAILURE",
    ),
    (
        MissionBoundary.OUTCOME_OBSERVATION,
        0,
        RuntimeEmulationFault.OUTCOME_FAILURE,
        "EMULATED_OUTCOME_FAILURE",
    ),
    (
        MissionBoundary.RETRACT_EXECUTE,
        0,
        RuntimeEmulationFault.DISCONNECT,
        "ARM_DISCONNECT",
    ),
    (
        MissionBoundary.RETRACT_FEEDBACK,
        0,
        RuntimeEmulationFault.REORDERED_FEEDBACK,
        "ARM_FEEDBACK_REORDERED",
    ),
    (
        MissionBoundary.PARK_EXECUTE,
        None,
        RuntimeEmulationFault.DISCONNECT,
        "ARM_DISCONNECT",
    ),
    (
        MissionBoundary.PARK_FEEDBACK,
        None,
        RuntimeEmulationFault.STALE_FEEDBACK,
        "ARM_FEEDBACK_STALE",
    ),
)


@pytest.mark.parametrize(
    ("boundary", "action_index", "fault", "expected_code"), _PORT_FAULT_CASES
)
def test_every_port_boundary_fails_stopped_without_later_contact(
    tmp_path: Path,
    boundary: MissionBoundary,
    action_index: int | None,
    fault: RuntimeEmulationFault,
    expected_code: str,
) -> None:
    spec = _spec("te")
    operation_id = spec.operation_id(boundary, action_index)
    trigger = RuntimeEmulationFaultTrigger(operation_id, fault)
    _ports_value, journals, untyped_report = _run(
        tmp_path, spec, triggers=(trigger,)
    )
    report = untyped_report

    assert report.passed is False
    assert report.primary_failure is not None
    assert report.primary_failure.boundary is boundary
    assert report.primary_failure.fault_code == expected_code
    failed_position = next(
        index
        for index, record in enumerate(report.records)
        if record.boundary is boundary
        and record.action_index == action_index
        and record.status is BoundaryStatus.FAILED
    )
    assert not any(
        record.action_index == 1
        and record.boundary
        in {MissionBoundary.CONTACT_EXECUTE, MissionBoundary.DEVICE_CONTACT}
        for record in report.records[failed_position + 1 :]
    )
    if boundary in {
        MissionBoundary.CONTACT_EXECUTE,
        MissionBoundary.CONTACT_FEEDBACK,
        MissionBoundary.DEVICE_CONTACT,
        MissionBoundary.OUTCOME_OBSERVATION,
    }:
        assert journals[0].snapshot().current_state is (
            ActionJournalState.OUTCOME_UNCERTAIN
        )
    if boundary in {
        MissionBoundary.PARK_EXECUTE,
        MissionBoundary.PARK_FEEDBACK,
    }:
        assert sum(record.boundary is boundary for record in report.records) == 1
    assert report.hardware_commands_generated == 0
    assert report.zero_authority is True


@pytest.mark.parametrize(
    ("method_name", "boundary"),
    (
        ("commit_pre_contact", MissionBoundary.JOURNAL_PRE_CONTACT),
        ("commit_contact_boundary", MissionBoundary.JOURNAL_CONTACT_BOUNDARY),
        ("confirm_outcome", MissionBoundary.JOURNAL_OUTCOME_CONFIRMED),
        ("confirm_retracted", MissionBoundary.JOURNAL_RETRACTED),
        ("confirm_parked", MissionBoundary.JOURNAL_PARKED),
    ),
)
def test_every_durable_transition_failure_is_fail_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    boundary: MissionBoundary,
) -> None:
    spec = _spec("te")
    journals = _journals(tmp_path, spec)

    def fail_transition(self: object, **_kwargs: object) -> object:
        raise MissionJournalError("injected durable transition failure")

    monkeypatch.setattr(ZeroAuthorityMissionJournal, method_name, fail_transition)
    report = run_zero_authority_multi_action_mission(
        _ports(spec), spec, journals, _authorization(spec, journals)
    )

    assert report.passed is False
    assert report.primary_failure is not None
    assert report.primary_failure.boundary is boundary
    assert report.primary_failure.fault_code == "MISSION_JOURNAL_ERROR"
    first_failure = next(
        index
        for index, record in enumerate(report.records)
        if record.status is BoundaryStatus.FAILED
    )
    assert not any(
        record.action_index == 1
        and record.boundary
        in {MissionBoundary.CONTACT_EXECUTE, MissionBoundary.DEVICE_CONTACT}
        for record in report.records[first_failure + 1 :]
    )
    if boundary is MissionBoundary.JOURNAL_CONTACT_BOUNDARY:
        assert not any(
            record.boundary is MissionBoundary.CONTACT_EXECUTE
            for record in report.records
        )


def _advance_journal(
    journal: ZeroAuthorityMissionJournal, state: ActionJournalState
) -> None:
    if state is ActionJournalState.INTENT_COMMITTED:
        return
    journal.commit_pre_contact(event_time_ns=200, route_sha256=_digest("route"))
    if state is ActionJournalState.PRE_CONTACT:
        return
    journal.commit_contact_boundary(
        event_time_ns=300, command_sha256=_digest("contact")
    )
    if state is ActionJournalState.CONTACT_MAY_HAVE_OCCURRED:
        return
    journal.confirm_outcome(event_time_ns=400, outcome_sha256=_digest("outcome"))
    if state is ActionJournalState.OUTCOME_CONFIRMED:
        return
    journal.confirm_retracted(
        event_time_ns=500, feedback_sha256=_digest("retracted")
    )
    if state is ActionJournalState.RETRACTED:
        return
    journal.confirm_parked(event_time_ns=600, feedback_sha256=_digest("parked"))


@pytest.mark.parametrize(
    "restart_state",
    (
        ActionJournalState.INTENT_COMMITTED,
        ActionJournalState.PRE_CONTACT,
        ActionJournalState.CONTACT_MAY_HAVE_OCCURRED,
        ActionJournalState.OUTCOME_CONFIRMED,
        ActionJournalState.RETRACTED,
        ActionJournalState.PARKED,
    ),
)
def test_process_restart_resumes_from_each_safe_journal_state_without_retry(
    tmp_path: Path, restart_state: ActionJournalState
) -> None:
    spec = _spec("t")
    journals = _journals(tmp_path, spec)
    _advance_journal(journals[0], restart_state)
    reopened = reopen_zero_authority_mission_journals(
        tuple(journal.directory for journal in journals)
    )
    authorization = _authorization(spec, reopened)

    report = run_zero_authority_multi_action_mission(
        _ports(spec), spec, reopened, authorization
    )

    assert report.passed is True
    assert report.initial_states == (restart_state,)
    assert report.final_states == (ActionJournalState.PARKED,)
    expected_authorized_commands = {
        ActionJournalState.INTENT_COMMITTED: 5,
        ActionJournalState.PRE_CONTACT: 5,
        ActionJournalState.CONTACT_MAY_HAVE_OCCURRED: 2,
        ActionJournalState.OUTCOME_CONFIRMED: 2,
        ActionJournalState.RETRACTED: 1,
        ActionJournalState.PARKED: 0,
    }[restart_state]
    assert len(report.authorization_receipt_sha256s) == expected_authorized_commands
    assert report.authorization_complete is True
    contact_boundaries = {
        MissionBoundary.JOURNAL_CONTACT_BOUNDARY,
        MissionBoundary.CONTACT_EXECUTE,
        MissionBoundary.CONTACT_FEEDBACK,
        MissionBoundary.DEVICE_CONTACT,
    }
    contact_records = tuple(
        record for record in report.records if record.boundary in contact_boundaries
    )
    if restart_state in {
        ActionJournalState.CONTACT_MAY_HAVE_OCCURRED,
        ActionJournalState.OUTCOME_CONFIRMED,
        ActionJournalState.RETRACTED,
        ActionJournalState.PARKED,
    }:
        assert contact_records == ()
        assert report.contact_operation_ids == ()
    else:
        assert sum(
            record.boundary is MissionBoundary.CONTACT_EXECUTE
            for record in contact_records
        ) == 1
        assert sum(
            record.boundary is MissionBoundary.DEVICE_CONTACT
            for record in contact_records
        ) == 1
    if restart_state is ActionJournalState.PRE_CONTACT:
        precontact = next(
            record
            for record in report.records
            if record.boundary is MissionBoundary.JOURNAL_PRE_CONTACT
        )
        assert precontact.status is BoundaryStatus.RESUMED
    if restart_state is ActionJournalState.PARKED:
        assert tuple(record.boundary for record in report.records) == (
            MissionBoundary.VALIDATE_PORTS_INITIAL,
            MissionBoundary.VALIDATE_PORTS_FINAL,
            MissionBoundary.VALIDATE_JOURNALS_FINAL,
        )


@pytest.mark.parametrize(
    "terminal_state",
    (ActionJournalState.FAULTED, ActionJournalState.OUTCOME_UNCERTAIN),
)
def test_terminal_restart_requires_manual_review_and_never_contacts(
    tmp_path: Path, terminal_state: ActionJournalState
) -> None:
    spec = _spec("t")
    journals = _journals(tmp_path, spec)
    if terminal_state is ActionJournalState.FAULTED:
        journals[0].mark_faulted(
            event_time_ns=200, detail_code="INJECTED_PRE_CONTACT_FAILURE"
        )
    else:
        journals[0].commit_pre_contact(
            event_time_ns=200, route_sha256=_digest("route")
        )
        journals[0].commit_contact_boundary(
            event_time_ns=300, command_sha256=_digest("contact")
        )
        journals[0].mark_outcome_uncertain(
            event_time_ns=400, detail_code="INJECTED_OUTCOME_UNCERTAIN"
        )

    report = run_zero_authority_multi_action_mission(
        _ports(spec), spec, journals, _authorization(spec, journals)
    )

    assert report.passed is False
    assert report.primary_failure is not None
    assert report.primary_failure.fault_code == "JOURNAL_MANUAL_REVIEW_REQUIRED"
    assert report.contact_operation_ids == ()
    assert not any(
        record.boundary
        in {
            MissionBoundary.CONNECT,
            MissionBoundary.REFERENCE,
            MissionBoundary.CONTACT_EXECUTE,
            MissionBoundary.DEVICE_CONTACT,
        }
        for record in report.records
    )


def test_expired_deadline_and_current_cancellation_stop_before_command(
    tmp_path: Path,
) -> None:
    deadline_spec = _spec(
        "t",
        deadline_expiry_boundary=MissionBoundary.HOVER_EXECUTE,
        deadline_expiry_action_index=0,
    )
    deadline_journals = _journals(tmp_path / "deadline", deadline_spec)
    deadline_report = run_zero_authority_multi_action_mission(
        _ports(deadline_spec),
        deadline_spec,
        deadline_journals,
        _authorization(deadline_spec, deadline_journals),
    )
    assert deadline_report.primary_failure is not None
    assert deadline_report.primary_failure.boundary is MissionBoundary.HOVER_EXECUTE
    assert deadline_report.primary_failure.fault_code == "DEADLINE_EXPIRED"
    assert deadline_report.contact_operation_ids == ()

    cancel_spec = _spec("t")
    cancel_id = cancel_spec.operation_id(MissionBoundary.ACTION_GATE, 0)
    cancelled_journals = _journals(tmp_path / "cancelled", cancel_spec)
    cancelled_report = run_zero_authority_multi_action_mission(
        _ports(
            cancel_spec,
            (
                RuntimeEmulationFaultTrigger(
                    cancel_id, RuntimeEmulationFault.CANCELLED
                ),
            )
        ),
        cancel_spec,
        cancelled_journals,
        _authorization(cancel_spec, cancelled_journals),
    )
    assert cancelled_report.primary_failure is not None
    assert cancelled_report.primary_failure.fault_code == "OPERATION_CANCELLED"
    assert not any(
        record.boundary is MissionBoundary.HOVER_EXECUTE
        for record in cancelled_report.records
    )


def test_primary_and_all_cleanup_failures_are_preserved(tmp_path: Path) -> None:
    spec = _spec("t")
    triggers = (
        RuntimeEmulationFaultTrigger(
            spec.operation_id(MissionBoundary.DEVICE_CONTACT, 0),
            RuntimeEmulationFault.CONTACT_FAILURE,
        ),
        RuntimeEmulationFaultTrigger(
            spec.operation_id(MissionBoundary.STOP), RuntimeEmulationFault.TIMEOUT
        ),
        RuntimeEmulationFaultTrigger(
            spec.operation_id(MissionBoundary.CLOSE), RuntimeEmulationFault.RESET
        ),
    )

    journals = _journals(tmp_path, spec)
    report = run_zero_authority_multi_action_mission(
        _ports(spec, triggers), spec, journals, _authorization(spec, journals)
    )

    assert report.primary_failure is not None
    assert report.primary_failure.boundary is MissionBoundary.DEVICE_CONTACT
    assert report.primary_failure.fault_code == "EMULATED_CONTACT_FAILURE"
    assert tuple(item.boundary for item in report.cleanup_failures) == (
        MissionBoundary.STOP,
        MissionBoundary.CLOSE,
    )
    assert tuple(item.fault_code for item in report.cleanup_failures) == (
        "ARM_TIMEOUT",
        "ARM_RESET",
    )
    assert report.final_states == (ActionJournalState.OUTCOME_UNCERTAIN,)
    assert not any(
        record.boundary is MissionBoundary.PARK_EXECUTE
        for record in report.records
    )


def test_plan_or_journal_substitution_is_rejected_before_runtime(
    tmp_path: Path,
) -> None:
    original = _spec("t")
    journals = _journals(tmp_path, original)
    substituted = _spec("e")

    with pytest.raises(
        ValueError, match="journal occurrence does not match the immutable mission plan"
    ):
        run_zero_authority_multi_action_mission(
            _ports(substituted),
            substituted,
            journals,
            _authorization(substituted, journals),
        )


@pytest.mark.parametrize(
    "states",
    (
        (
            ActionJournalState.INTENT_COMMITTED,
            ActionJournalState.PRE_CONTACT,
        ),
        (ActionJournalState.PRE_CONTACT, ActionJournalState.RETRACTED),
        (ActionJournalState.RETRACTED, ActionJournalState.PARKED),
        (ActionJournalState.PARKED, ActionJournalState.INTENT_COMMITTED),
    ),
)
def test_cross_journal_progress_must_be_one_global_prefix(
    tmp_path: Path,
    states: tuple[ActionJournalState, ActionJournalState],
) -> None:
    spec = _spec("te")
    journals = _journals(tmp_path, spec)
    for journal, state in zip(journals, states):
        _advance_journal(journal, state)

    with pytest.raises(
        MultiActionMissionError,
        match="ordered prefix|later action|parking starts",
    ):
        run_zero_authority_multi_action_mission(
            _ports(spec),
            spec,
            journals,
            cast(
                SimulationCommandAuthorizationCursor,
                CompletedMissionAuthorizationCursor(spec.plan_sha256),
            ),
        )


def test_authorization_cursor_must_match_exact_restart_suffix(tmp_path: Path) -> None:
    spec = _spec("t")
    journals = _journals(tmp_path, spec)
    stale_cursor = _authorization(spec, journals)
    _advance_journal(journals[0], ActionJournalState.CONTACT_MAY_HAVE_OCCURRED)

    with pytest.raises(
        MultiActionMissionError, match="exact safe mission suffix"
    ):
        run_zero_authority_multi_action_mission(
            _ports(spec), spec, journals, stale_cursor
        )


def test_missing_and_naked_authorization_are_rejected(tmp_path: Path) -> None:
    spec = _spec("t")
    journals = _journals(tmp_path, spec)
    cursor = _authorization(spec, journals)
    assert isinstance(cursor, AuthorizationV2MissionCursor)

    for invalid in (None, cursor._permit):
        with pytest.raises(MultiActionMissionError, match="concrete mission"):
            run_zero_authority_multi_action_mission(
                _ports(spec),
                spec,
                journals,
                cast(SimulationCommandAuthorizationCursor, invalid),
            )


def test_authorization_denial_occurs_before_contact_command_send(
    tmp_path: Path,
) -> None:
    spec = _spec("t")
    journals = _journals(tmp_path, spec)
    cursor = _authorization(spec, journals, deny_relative_ordinal=2)

    report = run_zero_authority_multi_action_mission(
        _ports(spec), spec, journals, cursor
    )

    assert report.primary_failure is not None
    assert report.primary_failure.boundary is MissionBoundary.CONTACT_EXECUTE
    assert report.primary_failure.fault_code == "SIMULATION_AUTHORIZATION_DENIED"
    assert len(report.authorization_receipt_sha256s) == 2
    assert not any(
        record.boundary is MissionBoundary.DEVICE_CONTACT
        for record in report.records
    )
    assert journals[0].snapshot().current_state is (
        ActionJournalState.OUTCOME_UNCERTAIN
    )


@pytest.mark.parametrize(
    "wrong_field",
    ("semantic", "occurrence", "events"),
)
def test_wrong_semantic_outcome_fails_closed_without_retract(
    tmp_path: Path, wrong_field: str
) -> None:
    spec = _spec("t")
    journals = _journals(tmp_path, spec)
    report = run_zero_authority_multi_action_mission(
        _ports(
            spec,
            wrong_semantic_index=(0 if wrong_field == "semantic" else None),
            wrong_occurrence_index=(0 if wrong_field == "occurrence" else None),
            wrong_events_index=(0 if wrong_field == "events" else None),
        ),
        spec,
        journals,
        _authorization(spec, journals),
    )

    assert report.primary_failure is not None
    assert report.primary_failure.boundary is MissionBoundary.OUTCOME_OBSERVATION
    assert report.outcome_receipts == ()
    assert journals[0].snapshot().current_state is (
        ActionJournalState.OUTCOME_UNCERTAIN
    )
    assert not any(
        record.boundary is MissionBoundary.RETRACT_EXECUTE
        for record in report.records
    )


def test_restart_without_contact_result_still_requires_correct_outcome_meaning(
    tmp_path: Path,
) -> None:
    spec = _spec("t")
    journals = _journals(tmp_path, spec)
    _advance_journal(journals[0], ActionJournalState.CONTACT_MAY_HAVE_OCCURRED)

    report = run_zero_authority_multi_action_mission(
        _ports(spec, wrong_semantic_index=0),
        spec,
        journals,
        _authorization(spec, journals),
    )

    assert report.primary_failure is not None
    assert report.primary_failure.boundary is MissionBoundary.OUTCOME_OBSERVATION
    assert report.contact_operation_ids == ()
    assert not any(
        record.boundary is MissionBoundary.RETRACT_EXECUTE
        for record in report.records
    )


class _RecordingExecution:
    def __init__(self, inner: ArmExecutionPort[object, object]) -> None:
        self._inner = inner
        self.runtime_metadata = inner.runtime_metadata
        self.requests: list[ArmExecutionRequest[object]] = []

    def execute(
        self,
        request: ArmExecutionRequest[object],
        cancellation: CancellationPort,
    ) -> ArmExecutionResult[object]:
        self.requests.append(request)
        return self._inner.execute(request, cancellation)


class _MutateOriginalOnConnect:
    def __init__(self, inner: object, payload: BoundOpaqueValue[object]) -> None:
        self._inner = inner
        self._payload = payload
        self.runtime_metadata = getattr(inner, "runtime_metadata")

    def connect(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        result = self._inner.connect(request, cancellation)  # type: ignore[attr-defined,no-any-return]
        object.__setattr__(self._payload, "canonical_bytes", b"mutated-after-plan")
        return result

    def reference(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return self._inner.reference(request, cancellation)  # type: ignore[attr-defined,no-any-return]

    def stop(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return self._inner.stop(request, cancellation)  # type: ignore[attr-defined,no-any-return]

    def close(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return self._inner.close(request, cancellation)  # type: ignore[attr-defined,no-any-return]


def test_commands_use_the_exact_prebound_immutable_materialization(
    tmp_path: Path,
) -> None:
    spec = _spec("t")
    original_hover = spec.actions[0].hover_command.verified_payload()
    journals = _journals(tmp_path, spec)
    cursor = _authorization(spec, journals)
    base = _ports(spec)
    recorder = _RecordingExecution(
        cast(ArmExecutionPort[object, object], base.arm_execution)
    )
    ports = replace(
        base,
        arm_lifecycle=_MutateOriginalOnConnect(
            base.arm_lifecycle, spec.actions[0].hover_command
        ),
        arm_execution=recorder,
    )

    report = run_zero_authority_multi_action_mission(
        ports, spec, journals, cursor
    )

    assert report.passed is True
    assert recorder.requests[0].command == original_hover
    assert recorder.requests[0].command != b"mutated-after-plan"


def test_preentry_payload_seal_tampering_is_rejected(tmp_path: Path) -> None:
    spec = _spec("t")
    journals = _journals(tmp_path, spec)
    cursor = _authorization(spec, journals)
    object.__setattr__(
        spec.actions[0].hover_command, "canonical_bytes", b"tampered"
    )

    with pytest.raises(MultiActionMissionError, match="changed after plan sealing"):
        run_zero_authority_multi_action_mission(
            _ports(spec), spec, journals, cursor
        )


class _RecordingCancellation:
    def __init__(self, inner: CancellationPort) -> None:
        self._inner = inner
        self.runtime_metadata = inner.runtime_metadata
        self.operation_ids: list[str] = []

    def poll(self, request: CancellationCheck) -> CancellationStatus:
        self.operation_ids.append(request.checkpoint_id)
        return self._inner.poll(request)


_CANCELLATION_BOUNDARIES = frozenset(
    {
        MissionBoundary.CONNECT,
        MissionBoundary.REFERENCE,
        MissionBoundary.ACTION_GATE,
        MissionBoundary.PRE_MOTION_FEEDBACK,
        MissionBoundary.FRESH_OBSERVATION,
        MissionBoundary.ROUTE_AUTHORIZATION,
        MissionBoundary.HOVER_EXECUTE,
        MissionBoundary.APPROACH_EXECUTE,
        MissionBoundary.CONTACT_EXECUTE,
        MissionBoundary.CONTACT_FEEDBACK,
        MissionBoundary.DEVICE_CONTACT,
        MissionBoundary.OUTCOME_OBSERVATION,
        MissionBoundary.RETRACT_EXECUTE,
        MissionBoundary.RETRACT_FEEDBACK,
        MissionBoundary.PARK_EXECUTE,
        MissionBoundary.PARK_FEEDBACK,
        MissionBoundary.STOP,
        MissionBoundary.CLOSE,
    }
)


def test_exact_top_level_operation_accounting_matches_every_cancellation_poll(
    tmp_path: Path,
) -> None:
    spec = _spec("test")
    base = _ports(spec)
    recorder = _RecordingCancellation(base.cancellation)
    ports = replace(base, cancellation=recorder)

    journals = _journals(tmp_path, spec)
    report = run_zero_authority_multi_action_mission(
        ports, spec, journals, _authorization(spec, journals)
    )

    assert report.passed is True
    expected = [
        record.operation_id
        for record in report.records
        if record.boundary in _CANCELLATION_BOUNDARIES
    ]
    assert recorder.operation_ids == expected
    assert len(recorder.operation_ids) == 54
    assert len(recorder.operation_ids) == len(set(recorder.operation_ids))


def _report_values(report: MultiActionMissionReport) -> dict[str, object]:
    return {
        "mission_id": report.mission_id,
        "plan_sha256": report.plan_sha256,
        "runtime_id": report.runtime_id,
        "occurrence_ids": report.occurrence_ids,
        "initial_states": report.initial_states,
        "final_states": report.final_states,
        "records": report.records,
        "outcome_receipts": report.outcome_receipts,
        "authorization_receipt_sha256s": report.authorization_receipt_sha256s,
        "authorization_complete": report.authorization_complete,
        "journals_verified": report.journals_verified,
        "primary_failure": report.primary_failure,
        "cleanup_failures": report.cleanup_failures,
        "zero_authority": report.zero_authority,
        "hardware_accessed": report.hardware_accessed,
        "hardware_commands_generated": report.hardware_commands_generated,
        "schema": report.schema,
    }


def test_report_is_factory_sealed_and_revalidates_all_accounting(
    tmp_path: Path,
) -> None:
    spec = _spec("t")
    _ports_value, _journals_value, report = _run(tmp_path, spec)
    values = _report_values(report)

    with pytest.raises(MultiActionMissionError, match="only be issued"):
        MultiActionMissionReport(**values)  # type: ignore[arg-type]
    with pytest.raises(MultiActionMissionError, match="only be issued"):
        replace(report, hardware_accessed=True)

    malformed = dict(values)
    malformed["initial_states"] = ()
    with pytest.raises(MultiActionMissionError, match="cardinality"):
        MultiActionMissionReport._issued(**malformed)

    malformed = dict(values)
    malformed["records"] = tuple(reversed(report.records))
    with pytest.raises(MultiActionMissionError, match="begin"):
        MultiActionMissionReport._issued(**malformed)

    malformed = dict(values)
    malformed["authorization_receipt_sha256s"] = (
        report.authorization_receipt_sha256s[:-1]
    )
    with pytest.raises(MultiActionMissionError, match="authorization receipts"):
        MultiActionMissionReport._issued(**malformed)

    malformed = dict(values)
    malformed["hardware_accessed"] = True
    with pytest.raises(MultiActionMissionError, match="zero physical authority"):
        MultiActionMissionReport._issued(**malformed)

    object.__setattr__(report, "hardware_accessed", True)
    with pytest.raises(MultiActionMissionError, match="zero physical authority"):
        report.to_dict()


class _BroadFailureLifecycle:
    def __init__(self, inner: object) -> None:
        self._inner = inner
        self.runtime_metadata = getattr(inner, "runtime_metadata")
        self.calls: list[MissionBoundary] = []

    def connect(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return self._inner.connect(request, cancellation)  # type: ignore[attr-defined,no-any-return]

    def reference(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return self._inner.reference(request, cancellation)  # type: ignore[attr-defined,no-any-return]

    def stop(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        del request, cancellation
        self.calls.append(MissionBoundary.STOP)
        raise LookupError("broad stop failure")

    def close(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        del request, cancellation
        self.calls.append(MissionBoundary.CLOSE)
        raise OSError("broad close failure")


def test_broad_cleanup_failures_are_aggregated_and_final_validation_runs(
    tmp_path: Path,
) -> None:
    spec = _spec("t")
    contact_fault = RuntimeEmulationFaultTrigger(
        spec.operation_id(MissionBoundary.DEVICE_CONTACT, 0),
        RuntimeEmulationFault.CONTACT_FAILURE,
    )
    base = _ports(spec, (contact_fault,))
    lifecycle = _BroadFailureLifecycle(base.arm_lifecycle)
    ports = replace(base, arm_lifecycle=lifecycle)
    journals = _journals(tmp_path, spec)

    report = run_zero_authority_multi_action_mission(
        ports, spec, journals, _authorization(spec, journals)
    )

    assert report.primary_failure is not None
    assert report.primary_failure.boundary is MissionBoundary.DEVICE_CONTACT
    assert lifecycle.calls == [MissionBoundary.STOP, MissionBoundary.CLOSE]
    assert tuple(failure.boundary for failure in report.cleanup_failures) == (
        MissionBoundary.STOP,
        MissionBoundary.CLOSE,
    )
    assert report.records[-2].boundary is MissionBoundary.VALIDATE_PORTS_FINAL
    assert report.records[-1].boundary is MissionBoundary.VALIDATE_JOURNALS_FINAL


def test_final_journal_snapshot_exception_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _spec("t")
    base = _ports(spec)
    controller = cast(DeterministicControllerPort, base.arm_execution)
    journals = _journals(tmp_path, spec)
    original_snapshot = ZeroAuthorityMissionJournal.snapshot

    def fail_after_close(
        self: ZeroAuthorityMissionJournal,
    ) -> object:
        if controller.state == "CLOSED":
            raise RuntimeError("injected final snapshot failure")
        return original_snapshot(self)

    monkeypatch.setattr(ZeroAuthorityMissionJournal, "snapshot", fail_after_close)
    report = run_zero_authority_multi_action_mission(
        base, spec, journals, _authorization(spec, journals)
    )

    assert report.passed is False
    assert report.primary_failure is not None
    assert report.primary_failure.boundary is MissionBoundary.VALIDATE_JOURNALS_FINAL
    assert report.journals_verified is False
    assert report.final_states == (ActionJournalState.PARKED,)
    assert report.records[-1].status is BoundaryStatus.FAILED


class _FailAfterCloseClock:
    def __init__(
        self, inner: ClockPort, controller: DeterministicControllerPort
    ) -> None:
        self._inner = inner
        self._controller = controller
        self.runtime_metadata = inner.runtime_metadata

    def now(self) -> RuntimeInstant:
        if self._controller.state == "CLOSED":
            raise RuntimeError("injected post-close clock failure")
        return self._inner.now()


def test_clock_failures_cannot_suppress_close_or_final_accounting(
    tmp_path: Path,
) -> None:
    spec = _spec("t")
    base = _ports(spec)
    controller = cast(DeterministicControllerPort, base.arm_execution)
    clock = _FailAfterCloseClock(base.clock, controller)
    ports = replace(base, clock=clock)
    journals = _journals(tmp_path, spec)

    report = run_zero_authority_multi_action_mission(
        ports, spec, journals, _authorization(spec, journals)
    )

    assert controller.state == "CLOSED"
    assert report.passed is False
    assert any(
        record.boundary is MissionBoundary.CLOSE
        and record.status is BoundaryStatus.FAILED
        for record in report.records
    )
    assert tuple(record.boundary for record in report.records[-2:]) == (
        MissionBoundary.VALIDATE_PORTS_FINAL,
        MissionBoundary.VALIDATE_JOURNALS_FINAL,
    )
    assert all(
        record.status is BoundaryStatus.FAILED for record in report.records[-2:]
    )


class _SwitchableClock:
    def __init__(self, inner: ClockPort) -> None:
        self._inner = inner
        self.drifted = False

    @property
    def runtime_metadata(self) -> RuntimePortMetadata:
        metadata = self._inner.runtime_metadata
        if not self.drifted:
            return metadata
        return replace(metadata, implementation_id=f"{metadata.implementation_id}.drift")

    def now(self) -> RuntimeInstant:
        return self._inner.now()


class _DriftAfterCloseLifecycle:
    def __init__(self, inner: object, clock: _SwitchableClock) -> None:
        self._inner = inner
        self._clock = clock
        self.runtime_metadata = getattr(inner, "runtime_metadata")

    def connect(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return self._inner.connect(request, cancellation)  # type: ignore[attr-defined,no-any-return]

    def reference(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return self._inner.reference(request, cancellation)  # type: ignore[attr-defined,no-any-return]

    def stop(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        return self._inner.stop(request, cancellation)  # type: ignore[attr-defined,no-any-return]

    def close(
        self, request: LifecycleRequest, cancellation: CancellationPort
    ) -> LifecycleResult:
        result = self._inner.close(request, cancellation)  # type: ignore[attr-defined,no-any-return]
        self._clock.drifted = True
        return result


def test_final_runtime_identity_drift_is_a_terminal_validation_failure(
    tmp_path: Path,
) -> None:
    spec = _spec("t")
    base = _ports(spec)
    clock = _SwitchableClock(base.clock)
    lifecycle = _DriftAfterCloseLifecycle(base.arm_lifecycle, clock)
    ports = replace(base, clock=clock, arm_lifecycle=lifecycle)

    journals = _journals(tmp_path, spec)
    report = run_zero_authority_multi_action_mission(
        ports, spec, journals, _authorization(spec, journals)
    )

    assert report.passed is False
    assert report.primary_failure is not None
    assert report.primary_failure.boundary is MissionBoundary.VALIDATE_PORTS_FINAL
    assert report.primary_failure.fault_code == "MISSION_KERNEL_ERROR"
    assert report.final_states == (ActionJournalState.PARKED,)


class _PhysicalClaimClock:
    def __init__(self, inner: ClockPort) -> None:
        self._inner = inner
        metadata = inner.runtime_metadata
        self.runtime_metadata = replace(
            metadata,
            authority=RuntimeAuthority(
                execution_mode=RuntimeExecutionMode.PHYSICAL,
                hardware_accessed=True,
                hardware_commands_generated=0,
                live_motion_authorized=False,
                physical_contact_authorized=False,
                physical_release_effect="NONE",
            ),
        )

    def now(self) -> RuntimeInstant:
        return self._inner.now()


def test_nonzero_authority_port_is_rejected_before_any_operation(
    tmp_path: Path,
) -> None:
    spec = _spec("t")
    base = _ports(spec)
    ports = replace(base, clock=_PhysicalClaimClock(base.clock))
    journals = _journals(tmp_path, spec)

    with pytest.raises(RuntimeContractError, match="not zero-authority"):
        run_zero_authority_multi_action_mission(
            ports, spec, journals, _authorization(spec, journals)
        )

    assert tuple(journal.snapshot().current_state for journal in journals) == (
        ActionJournalState.INTENT_COMMITTED,
    )
