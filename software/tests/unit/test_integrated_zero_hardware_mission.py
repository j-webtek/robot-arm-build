"""End-to-end contracts for the pre-hardware mission V2 rehearsal.

These tests deliberately cross component boundaries.  They prove that the
semantic schedule, dense trajectory, B0477 evidence, collision query, ordered
authorization, non-wire T104 emulator, virtual device, outcome observer, and
durable contact journals all describe the same bounded mission.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Iterator, Mapping, Sequence, cast

import pytest

from rocell.application.b0477_mission_observations import (
    bind_b0477_mission_observations,
)
from rocell.application.dense_route_schedule import build_dense_route_schedule
from rocell.application.integrated_zero_hardware_mission import (
    INTEGRATED_JOURNAL_SET_FILENAME,
    IntegratedCommandReceipt,
    IntegratedContactReceipt,
    IntegratedFaultReceipt,
    IntegratedZeroHardwareMissionError,
    IntegratedZeroHardwareMissionReport,
    _coordinator_fault_source_sha256,
    assemble_default_zero_hardware_mission_v2,
    open_zero_hardware_mission_v2,
    prepare_zero_hardware_mission_v2,
    run_zero_hardware_mission_v2,
)
from rocell.application.mission_journal import ActionJournalState
from rocell.application.multi_action_mission_v2 import (
    MissionV2CommandBinding,
    MultiActionMissionSpecV2,
    MultiActionMissionV2Error,
    assemble_zero_hardware_mission_v2,
)
from rocell.application.semantic_step_schedule import (
    ContactSemanticStep,
    PhoneStateObservationStep,
)
from rocell.application.virtual_session import build_virtual_device_model
from rocell.motion import MotionPhase
from rocell.safety.synthetic_authorization import SyntheticInterlockContinuity
from rocell.simulation.b0477_replay_camera import (
    B0477ReplayCameraPort,
    B0477ReplayCaptureError,
    B0477ReplayFaultInjection,
    B0477ReplayFaultKind,
    B0477ReplayFaultReceipt,
)
from rocell.simulation.t104_runtime import T104FaultInjection
from rocell.simulation.virtual_workcell import VirtualKeyboard


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def assemblies() -> Mapping[str, MultiActionMissionSpecV2]:
    """Build each real development-profile mission only once per test run."""

    return {
        "keyboard": assemble_default_zero_hardware_mission_v2(
            WORKSPACE,
            "keyboard",
            "test",
            mission_id="integration-keyboard-v2",
            controller_session_id="integration-keyboard-t104-v2",
            camera_starting_sequence=10_000,
        ),
        "phone": assemble_default_zero_hardware_mission_v2(
            WORKSPACE,
            "phone",
            "test.",
            mission_id="integration-phone-v2",
            controller_session_id="integration-phone-t104-v2",
            camera_starting_sequence=20_000,
        ),
    }


def _run(
    assembly: MultiActionMissionSpecV2,
    journal_root: Path,
) -> IntegratedZeroHardwareMissionReport:
    prepared = prepare_zero_hardware_mission_v2(
        assembly,
        journal_root,
        created_at_ns=50_000_000,
    )
    return run_zero_hardware_mission_v2(prepared)


def _relabel_coordinator_fault(
    report: IntegratedZeroHardwareMissionReport,
    *,
    stage: str,
    semantic_step_ordinal: int | None,
    contact_occurrence_ordinal: int | None,
    authorization_command_ordinal: int | None,
    state_observation_count: int | None = None,
) -> IntegratedFaultReceipt:
    """Build a fully sealed alternative label for adversarial replay tests."""

    original = report.fault_receipt
    assert original is not None
    state_count = (
        len(report.state_observation_receipts)
        if state_observation_count is None
        else state_observation_count
    )
    source = _coordinator_fault_source_sha256(
        assembly_sha256=report.assembly_sha256,
        stage=stage,
        fault_kind="COORDINATOR_FAILURE",
        semantic_step_ordinal=semantic_step_ordinal,
        contact_occurrence_ordinal=contact_occurrence_ordinal,
        authorization_command_ordinal=authorization_command_ordinal,
        command_receipt_count=len(report.command_receipts),
        camera_observation_count=len(report.camera_observation_sha256s),
        state_observation_count=state_count,
        contact_receipt_count=len(report.contact_receipts),
    )
    return replace(
        original,
        source_class="IntegratedZeroHardwareMissionCoordinator",
        stage=stage,
        fault_kind="COORDINATOR_FAILURE",
        semantic_step_ordinal=semantic_step_ordinal,
        contact_occurrence_ordinal=contact_occurrence_ordinal,
        authorization_command_ordinal=authorization_command_ordinal,
        state_observation_count=state_count,
        source_evidence_sha256=source,
        camera_fault_receipt=None,
    )


def _all_mappings(value: object) -> Iterator[Mapping[str, object]]:
    """Yield every serialized object so nested authority claims are checked."""

    if isinstance(value, Mapping):
        document = cast(Mapping[str, object], value)
        yield document
        for child in document.values():
            yield from _all_mappings(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            yield from _all_mappings(child)


def _assert_zero_authority(value: object) -> None:
    expected = {
        "simulation_only": True,
        "physical_authority": "ZERO",
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "wire_messages_generated": 0,
        "power_authorized": False,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "can_release_physical_gates": False,
        "physical_release_effect": "NONE",
    }
    seen: set[str] = set()
    for document in _all_mappings(value):
        for key, expected_value in expected.items():
            if key in document:
                seen.add(key)
                assert document[key] == expected_value

    # The integrated envelopes must repeat all high-consequence authority
    # claims instead of relying on an implicit simulation convention.
    assert seen == set(expected)


def _assert_exact_cross_layer_bindings(
    assembly: MultiActionMissionSpecV2,
    report: IntegratedZeroHardwareMissionReport,
) -> None:
    assert len(report.command_receipts) == assembly.command_count
    assert len(assembly.command_bindings) == assembly.dense_route.command_count
    assert len(assembly.collision_fixture.report.command_bindings) == (
        assembly.command_count
    )
    assert len(assembly.collision_fixture.report.endpoint_results) == (
        assembly.dense_route.route_waypoint_count
    )
    assert len(assembly.collision_fixture.report.midpoint_results) == (
        assembly.command_count
    )

    observation_by_contact = {
        item.contact_occurrence_ordinal: item
        for item in assembly.camera_observations.observations
    }
    assert report.camera_observation_sha256s == tuple(
        item.observation_sha256
        for item in assembly.camera_observations.observations
    )
    assert tuple(
        item.camera_sequence for item in assembly.camera_observations.observations
    ) == tuple(
        sorted(
            item.camera_sequence
            for item in assembly.camera_observations.observations
        )
    )
    by_route = {
        item.route_waypoint_ordinal: item for item in assembly.dense_route.commands
    }
    for slice_, observation in zip(
        assembly.dense_route.contact_slices,
        assembly.camera_observations.observations,
    ):
        hover = by_route[slice_.final_hover_route_waypoint_ordinal]
        assert observation.contact_occurrence_ordinal == (
            slice_.contact_occurrence_ordinal
        )
        assert observation.semantic_step_ordinal == slice_.semantic_step_ordinal
        assert observation.target_id == slice_.target_id
        assert observation.route_waypoint_ordinal == hover.route_waypoint_ordinal
        assert observation.authorization_command_ordinal == (
            hover.authorization_command_ordinal
        )
        assert hover.phase is MotionPhase.HOVER
        assert hover.phase_endpoint is True

    for ordinal, (binding, receipt) in enumerate(
        zip(assembly.command_bindings, report.command_receipts)
    ):
        assert type(binding) is MissionV2CommandBinding
        assert binding.dense.authorization_command_ordinal == ordinal
        assert binding.dense.route_waypoint_ordinal == ordinal + 1
        assert receipt.authorization_command_ordinal == ordinal
        assert receipt.route_waypoint_ordinal == ordinal + 1
        assert receipt.semantic_step_ordinal == binding.dense.semantic_step_ordinal
        assert receipt.contact_occurrence_ordinal == (
            binding.dense.contact_occurrence_ordinal
        )
        assert receipt.phase is binding.dense.phase
        assert receipt.mission_tail is binding.dense.mission_tail
        assert receipt.collision_binding_sha256 == binding.collision.content_hash
        assert receipt.camera_observation_sha256 == (
            observation_by_contact[
                binding.dense.contact_occurrence_ordinal
            ].observation_sha256
        )
        assert receipt.success is True
        assert receipt.fault_kind is None

        expected_contact_allowance = (
            binding.dense.phase is MotionPhase.CONTACT
            and binding.dense.phase_endpoint
            and not binding.dense.mission_tail
        )
        assert binding.collision.designated_contact_overlap_allowed is (
            expected_contact_allowance
        )


def test_keyboard_executes_all_47_commands_and_four_contacts(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
) -> None:
    assembly = assemblies["keyboard"]
    report = _run(assembly, tmp_path / "keyboard-journals")

    assert assembly.command_count == 47
    assert assembly.dense_route.route_waypoint_count == 48
    assert assembly.contact_count == 4
    assert assembly.observation_only_step_count == 0
    assert report.completed is True
    assert report.fault_receipt is None
    assert report.fault_detail is None
    assert report.outcome_matches is True
    assert report.observed_output_sha256 == assembly.plan.requested_text_sha256
    assert report.observed_output_length == len("test")
    assert len(report.camera_observation_sha256s) == 4
    assert len(report.state_observation_receipts) == 0
    assert len(report.contact_receipts) == 4
    assert [item.target_id for item in report.contact_receipts] == [
        "T",
        "E",
        "S",
        "T",
    ]
    assert [item.resolved_target_id for item in report.contact_receipts] == [
        "keyboard:T",
        "keyboard:E",
        "keyboard:S",
        "keyboard:T",
    ]
    assert all(
        snapshot.current_state is ActionJournalState.PARKED
        for snapshot in report.journal_snapshots
    )
    assert report.runtime_final_state.terminal is True
    assert report.runtime_final_state.completed_command_count == 47
    execution_document = cast(Mapping[str, object], report.to_dict()["execution"])
    assert execution_document["command_receipts"]
    _assert_exact_cross_layer_bindings(assembly, report)
    _assert_zero_authority(assembly.to_dict())
    _assert_zero_authority(report.to_dict())


def test_collision_fixture_binds_exact_rc03_workcell_layout_bytes(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
) -> None:
    """Keep layout provenance distinct from the enclosing system manifest."""

    source_hashes = (
        assemblies["keyboard"].collision_fixture.contract.sources.source_hashes
    )
    layout_path = (
        WORKSPACE / "active-project/RoCell_v0_3/config/workcell_layout.json"
    )
    manifest_path = WORKSPACE / "software/config/system_manifest.json"

    assert source_hashes["workcell_layout"] == hashlib.sha256(
        layout_path.read_bytes()
    ).hexdigest()
    assert source_hashes["workcell_layout"] != hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest()


def test_phone_observation_step_has_no_arm_command_contact_or_journal(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
) -> None:
    assembly = assemblies["phone"]
    report = _run(assembly, tmp_path / "phone-journals")

    assert assembly.command_count == 60
    assert assembly.dense_route.route_waypoint_count == 61
    assert assembly.contact_count == 5
    assert assembly.observation_only_step_count == 1
    assert report.completed is True
    assert report.outcome_matches is True
    assert report.observed_output_sha256 == assembly.plan.requested_text_sha256
    assert report.observed_output_length == len("test.")
    assert len(report.camera_observation_sha256s) == 5
    assert len(report.contact_receipts) == 5
    assert all(
        snapshot.current_state is ActionJournalState.PARKED
        for snapshot in report.journal_snapshots
    )

    assert type(assembly.semantic_schedule.steps[0]) is PhoneStateObservationStep
    observation = report.state_observation_receipts
    assert len(observation) == 1
    assert observation[0].semantic_step_ordinal == 0
    assert observation[0].passed is True
    observation_document = observation[0].to_dict()
    assert observation_document["arm_command_generated"] is False
    assert observation_document["contact_occurrence_created"] is False
    assert observation_document["journal_created"] is False

    contact_steps = tuple(
        step
        for step in assembly.semantic_schedule.steps
        if type(step) is ContactSemanticStep
    )
    assert [item.semantic_step_ordinal for item in contact_steps] == [1, 2, 3, 4, 5]
    assert [item.semantic_step_ordinal for item in report.contact_receipts] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert all(item.semantic_step_ordinal != 0 for item in report.command_receipts)
    assert len(report.journal_snapshots) == 5
    _assert_exact_cross_layer_bindings(assembly, report)
    _assert_zero_authority(assembly.to_dict())
    _assert_zero_authority(report.to_dict())


def _with_first_contact_stall(
    assembly: MultiActionMissionSpecV2,
) -> MultiActionMissionSpecV2:
    first = assembly.dense_route.contact_slices[0]
    contact_command_ordinal = first.contact_route_waypoint_ordinal - 1
    dense = build_dense_route_schedule(
        mission_id=assembly.mission_id,
        controller_session_id=assembly.dense_route.controller_session_id,
        semantic_schedule=assembly.semantic_schedule,
        trajectory=assembly.trajectory,
        fault_injections=(
            T104FaultInjection(contact_command_ordinal, "STALL"),
        ),
    )
    camera = bind_b0477_mission_observations(
        semantic_schedule=assembly.semantic_schedule,
        dense_route_schedule=dense,
        reports=tuple(
            item.report for item in assembly.camera_observations.observations
        ),
    )
    device, physical_count = build_virtual_device_model(
        assembly.bootstrap,
        assembly.plan,
        assembly.normalized_text,
    )
    assert physical_count == assembly.contact_count
    return assemble_zero_hardware_mission_v2(
        mission_id=assembly.mission_id,
        bootstrap=assembly.bootstrap,
        plan=assembly.plan,
        normalized_text=assembly.normalized_text,
        semantic_schedule=assembly.semantic_schedule,
        trajectory=assembly.trajectory,
        dense_route=dense,
        camera_observations=camera,
        collision_fixture=assembly.collision_fixture,
        virtual_device=device,
    )


def test_contact_fault_is_uncertain_and_restart_is_refused_without_mutation(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
) -> None:
    assembly = _with_first_contact_stall(assemblies["keyboard"])
    journal_root = tmp_path / "fault-journals"
    prepared = prepare_zero_hardware_mission_v2(
        assembly,
        journal_root,
        created_at_ns=80_000_000,
    )
    manifest_path = journal_root / INTEGRATED_JOURNAL_SET_FILENAME
    assert manifest_path.is_file()
    report = run_zero_hardware_mission_v2(prepared)

    first_contact_command = (
        assembly.dense_route.contact_slices[0].contact_route_waypoint_ordinal - 1
    )
    assert report.completed is False
    assert report.status == "ZERO_HARDWARE_MISSION_V2_FAULTED_CLOSED"
    assert report.fault_detail is not None
    assert "STALL" in report.fault_detail
    assert report.fault_receipt is not None
    assert report.fault_receipt.source_class == "InMemoryT104Runtime"
    assert report.fault_receipt.stage == "COMMAND_EXECUTION"
    assert report.fault_receipt.fault_kind == "STALL"
    assert report.fault_receipt.source_evidence_sha256 == (
        report.command_receipts[-1].t104_trace_receipt_sha256
    )
    assert report.fault_receipt.camera_fault_receipt is None
    assert len(report.command_receipts) == first_contact_command + 1
    assert report.command_receipts[-1].phase is MotionPhase.CONTACT
    assert report.command_receipts[-1].success is False
    assert report.command_receipts[-1].fault_kind == "STALL"
    assert report.runtime_final_state.fault_latched == "STALL"
    assert report.runtime_final_state.terminal is True
    assert report.runtime_final_state.attempted_command_count == (
        first_contact_command + 1
    )
    assert report.runtime_final_state.completed_command_count == first_contact_command
    assert len(report.camera_observation_sha256s) == 1
    assert len(report.contact_receipts) == 0
    assert report.observed_output_length == 0
    assert report.outcome_matches is False
    assert report.journal_snapshots[0].current_state is (
        ActionJournalState.OUTCOME_UNCERTAIN
    )
    assert all(
        snapshot.current_state is ActionJournalState.FAULTED
        for snapshot in report.journal_snapshots[1:]
    )
    _assert_zero_authority(report.to_dict())

    event_counts_before = tuple(
        len(snapshot.events) for snapshot in report.journal_snapshots
    )
    reopened = open_zero_hardware_mission_v2(assembly, journal_root)
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="automatic integrated restart is refused",
    ):
        run_zero_hardware_mission_v2(reopened)
    event_counts_after = tuple(
        len(journal.snapshot().events) for journal in reopened.journals
    )
    assert event_counts_after == event_counts_before

    manifest = manifest_path.read_bytes()
    assert assembly.assembly_sha256.encode("ascii") in manifest
    manifest_path.write_bytes(
        manifest.replace(
            assembly.assembly_sha256.encode("ascii"),
            ("0" * 64).encode("ascii"),
            1,
        )
    )
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="journal-set manifest differs from the exact assembly",
    ):
        open_zero_hardware_mission_v2(assembly, journal_root)


def test_command_camera_binding_tamper_is_rejected_during_construction(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
) -> None:
    binding = assemblies["keyboard"].command_bindings[0]
    with pytest.raises(MultiActionMissionV2Error, match="constraint set drifted"):
        replace(binding, camera_observation_sha256="0" * 64)


def test_integrated_command_reorder_is_rejected_by_mission_seal(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
) -> None:
    assembly = assemblies["phone"]
    reordered = (
        assembly.command_bindings[1],
        assembly.command_bindings[0],
        *assembly.command_bindings[2:],
    )
    with pytest.raises(
        MultiActionMissionV2Error,
        match="integrated dense command order differs",
    ):
        replace(assembly, command_bindings=reordered)


def test_complete_report_cannot_be_relabelled_or_emptied(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
) -> None:
    report = _run(assemblies["keyboard"], tmp_path / "report-seal-journals")
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
    ):
        replace(report, command_receipts=())
    object.__setattr__(report, "status", "ZERO_HARDWARE_MISSION_V2_FAULTED_CLOSED")
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
    ):
        report.to_dict()


def test_complete_report_cannot_be_rebound_to_a_fault_scheduled_assembly(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
) -> None:
    nominal = assemblies["keyboard"]
    report = _run(nominal, tmp_path / "fault-schedule-rebind-journals")
    faulting = replace(
        nominal,
        camera_fault_injection=B0477ReplayFaultInjection(
            contact_occurrence_ordinal=0,
            fault_kind=B0477ReplayFaultKind.STALE_FRAME,
        ),
    )
    forged = replace(report, assembly_sha256=faulting.assembly_sha256)
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="precommitted camera",
    ):
        forged.assert_matches_assembly(faulting)


def test_retained_trace_and_state_receipts_are_independently_replayed(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
) -> None:
    keyboard = assemblies["keyboard"]
    keyboard_report = _run(keyboard, tmp_path / "trace-replay-journals")
    first = keyboard_report.command_receipts[0]
    forged_trace = replace(
        first.t104_trace_receipt,
        simulator_trace_sha256="0" * 64,
    )
    forged_command = replace(first, t104_trace_receipt=forged_trace)
    forged_report = replace(
        keyboard_report,
        command_receipts=(forged_command, *keyboard_report.command_receipts[1:]),
    )
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="deterministic replay",
    ):
        forged_report.assert_matches_assembly(keyboard)

    phone = assemblies["phone"]
    phone_report = _run(phone, tmp_path / "state-replay-journals")
    forged_state = replace(
        phone_report.state_observation_receipts[0],
        device_state_before_sha256="0" * 64,
    )
    forged_phone_report = replace(
        phone_report,
        state_observation_receipts=(forged_state,),
    )
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="chronological device truth",
    ):
        forged_phone_report.assert_matches_assembly(phone)


def test_phone_motion_cannot_survive_deletion_of_required_state_observation(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
) -> None:
    phone = assemblies["phone"]
    report = _run(phone, tmp_path / "missing-state-prefix-journals")
    assert report.state_observation_receipts

    forged = replace(report, state_observation_receipts=())
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="motion command receipt exists without every preceding phone-state",
    ):
        forged.assert_matches_assembly(phone)


def test_coordinator_fault_cannot_skip_state_or_unfinished_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The claimed fault step must be the exact chronological next frontier."""

    assembly = assemble_default_zero_hardware_mission_v2(
        WORKSPACE,
        "phone",
        "a\n",
        mission_id="integration-phone-state-frontier-v2",
        controller_session_id="integration-phone-state-frontier-t104-v2",
        camera_starting_sequence=25_000,
    )
    prepared = prepare_zero_hardware_mission_v2(
        assembly,
        tmp_path / "semantic-frontier-journals",
        created_at_ns=75_000_000,
    )
    original_next = SyntheticInterlockContinuity.next_sample

    def fail_first_continuity(
        continuity: SyntheticInterlockContinuity,
    ) -> object:
        del continuity
        monkeypatch.setattr(
            SyntheticInterlockContinuity,
            "next_sample",
            original_next,
        )
        raise RuntimeError("synthetic first-command continuity failure")

    monkeypatch.setattr(
        SyntheticInterlockContinuity,
        "next_sample",
        fail_first_continuity,
    )
    report = run_zero_hardware_mission_v2(prepared)
    assert report.command_receipts == ()
    assert len(report.state_observation_receipts) == 1
    assert report.fault_receipt is not None
    assert report.fault_receipt.stage == "PRE_COMMAND_FAILURE"

    missing_state_fault = _relabel_coordinator_fault(
        report,
        stage="PRE_COMMAND_FAILURE",
        semantic_step_ordinal=1,
        contact_occurrence_ordinal=0,
        authorization_command_ordinal=0,
        state_observation_count=0,
    )
    missing_state_report = replace(
        report,
        state_observation_receipts=(),
        fault_receipt=missing_state_fault,
    )
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="coordinator pre-command fault exists without every preceding",
    ):
        missing_state_report.assert_matches_assembly(assembly)

    observations = tuple(
        item
        for item in assembly.semantic_schedule.steps
        if type(item) is PhoneStateObservationStep
    )
    assert len(observations) == 2
    future_observation_fault = _relabel_coordinator_fault(
        report,
        stage="SEMANTIC_OBSERVATION",
        semantic_step_ordinal=observations[-1].semantic_step_ordinal,
        contact_occurrence_ordinal=None,
        authorization_command_ordinal=None,
    )
    future_observation_report = replace(
        report,
        fault_receipt=future_observation_fault,
    )
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="semantic-observation fault skips an unfinished contact",
    ):
        future_observation_report.assert_matches_assembly(assembly)


def test_contact_post_failure_cannot_be_relabelled_as_retract_precommand(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_contact(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("synthetic virtual-contact boundary failure")

    monkeypatch.setattr(VirtualKeyboard, "apply_contact", fail_contact)
    assembly = assemblies["keyboard"]
    report = _run(assembly, tmp_path / "contact-post-stage-journals")
    assert report.fault_receipt is not None
    assert report.fault_receipt.stage == "CONTACT_POST_COMMAND"
    assert report.command_receipts[-1].phase is MotionPhase.CONTACT
    next_binding = assembly.command_bindings[len(report.command_receipts)].dense
    assert next_binding.phase is MotionPhase.RETRACT

    forged_fault = _relabel_coordinator_fault(
        report,
        stage="PRE_COMMAND_FAILURE",
        semantic_step_ordinal=next_binding.semantic_step_ordinal,
        contact_occurrence_ordinal=next_binding.contact_occurrence_ordinal,
        authorization_command_ordinal=(
            next_binding.authorization_command_ordinal
        ),
    )
    forged = replace(report, fault_receipt=forged_fault)
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="retract command frontier precedes a confirmed contact outcome",
    ):
        forged.assert_matches_assembly(assembly)


def test_retract_precommand_failure_cannot_be_relabelled_as_contact_post(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assembly = assemblies["keyboard"]
    first_slice = assembly.dense_route.contact_slices[0]
    first_retract_authorization = first_slice.contact_route_waypoint_ordinal
    prepared = prepare_zero_hardware_mission_v2(
        assembly,
        tmp_path / "retract-precommand-stage-journals",
        created_at_ns=76_000_000,
    )
    original_next = SyntheticInterlockContinuity.next_sample
    calls = 0

    def fail_at_first_retract(
        continuity: SyntheticInterlockContinuity,
    ) -> object:
        nonlocal calls
        if calls == first_retract_authorization:
            monkeypatch.setattr(
                SyntheticInterlockContinuity,
                "next_sample",
                original_next,
            )
            raise RuntimeError("synthetic retract continuity failure")
        calls += 1
        return original_next(continuity)

    monkeypatch.setattr(
        SyntheticInterlockContinuity,
        "next_sample",
        fail_at_first_retract,
    )
    report = run_zero_hardware_mission_v2(prepared)
    assert report.fault_receipt is not None
    assert report.fault_receipt.stage == "PRE_COMMAND_FAILURE"
    assert report.contact_receipts
    assert report.command_receipts[-1].phase is MotionPhase.CONTACT

    prior = report.command_receipts[-1]
    forged_fault = _relabel_coordinator_fault(
        report,
        stage="CONTACT_POST_COMMAND",
        semantic_step_ordinal=prior.semantic_step_ordinal,
        contact_occurrence_ordinal=prior.contact_occurrence_ordinal,
        authorization_command_ordinal=prior.authorization_command_ordinal,
    )
    forged = replace(report, fault_receipt=forged_fault)
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="contact-post-command fault follows a confirmed outcome",
    ):
        forged.assert_matches_assembly(assembly)


def test_next_group_failure_cannot_be_relabelled_as_retraction_commit(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assembly = assemblies["keyboard"]
    second_group_first_authorization = (
        assembly.dense_route.contact_slices[1].first_authorization_command_ordinal
    )
    prepared = prepare_zero_hardware_mission_v2(
        assembly,
        tmp_path / "post-retract-next-group-journals",
        created_at_ns=77_000_000,
    )
    original_next = SyntheticInterlockContinuity.next_sample
    calls = 0

    def fail_before_second_group(
        continuity: SyntheticInterlockContinuity,
    ) -> object:
        nonlocal calls
        if calls == second_group_first_authorization:
            monkeypatch.setattr(
                SyntheticInterlockContinuity,
                "next_sample",
                original_next,
            )
            raise RuntimeError("synthetic next-group continuity failure")
        calls += 1
        return original_next(continuity)

    monkeypatch.setattr(
        SyntheticInterlockContinuity,
        "next_sample",
        fail_before_second_group,
    )
    report = run_zero_hardware_mission_v2(prepared)
    assert report.fault_receipt is not None
    assert report.fault_receipt.stage == "PRE_COMMAND_FAILURE"
    assert (
        ActionJournalState.RETRACTED
        in tuple(item.state for item in report.journal_snapshots[0].events)
    )
    prior = report.command_receipts[-1]
    assert prior.phase is MotionPhase.RETRACT

    forged_fault = _relabel_coordinator_fault(
        report,
        stage="RETRACTION_COMMIT",
        semantic_step_ordinal=prior.semantic_step_ordinal,
        contact_occurrence_ordinal=prior.contact_occurrence_ordinal,
        authorization_command_ordinal=prior.authorization_command_ordinal,
    )
    forged = replace(report, fault_receipt=forged_fault)
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="retraction-commit fault differs from the exact unpublished endpoint",
    ):
        forged.assert_matches_assembly(assembly)


def test_replay_camera_fault_stops_before_approach_or_contact(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
) -> None:
    assembly = replace(
        assemblies["keyboard"],
        camera_fault_injection=B0477ReplayFaultInjection(
            contact_occurrence_ordinal=0,
            fault_kind=B0477ReplayFaultKind.STALE_FRAME,
        ),
    )
    prepared = prepare_zero_hardware_mission_v2(
        assembly,
        tmp_path / "camera-fault-journals",
        created_at_ns=90_000_000,
    )
    report = run_zero_hardware_mission_v2(prepared)
    assert report.completed is False
    assert report.fault_detail is not None and "STALE_FRAME" in report.fault_detail
    assert report.fault_receipt is not None
    assert report.fault_receipt.source_class == "SettledHoverObservationBoundary"
    assert report.fault_receipt.stage == "SETTLED_HOVER_OBSERVATION"
    assert report.fault_receipt.fault_kind == "OBSERVATION_BOUNDARY_FAILURE"
    assert report.fault_receipt.camera_fault_receipt is not None
    assert (
        report.fault_receipt.camera_fault_receipt.fault_kind
        is B0477ReplayFaultKind.STALE_FRAME
    )
    assert (
        report.to_dict()["fault_receipt"][
            "camera_fault_receipt_is_causal_evidence"
        ]
        is False
    )
    assert report.camera_observation_sha256s == ()
    assert report.contact_receipts == ()
    assert report.command_receipts[-1].phase is MotionPhase.HOVER
    assert report.command_receipts[-1].success is True
    assert all(
        item.current_state is ActionJournalState.FAULTED
        for item in report.journal_snapshots
    )

    # The human-readable detail is not causal evidence, and the execution
    # frontier independently proves that this was a camera capture failure.
    forged_fault = replace(
        report.fault_receipt,
        source_class="InMemoryT104Runtime",
        stage="COMMAND_EXECUTION",
        fault_kind="STALL",
        source_evidence_sha256=(
            report.command_receipts[-1].t104_trace_receipt_sha256
        ),
        camera_fault_receipt=None,
    )
    forged_report = replace(report, fault_receipt=forged_fault)
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="observation-boundary fault differs from its call frontier",
    ):
        forged_report.assert_matches_assembly(assembly)

    forged_camera_source = replace(
        report.fault_receipt.camera_fault_receipt,
        fault_kind=B0477ReplayFaultKind.TIMEOUT,
    )
    forged_kind = replace(
        report.fault_receipt,
        camera_fault_receipt=forged_camera_source,
    )
    forged_kind_report = replace(report, fault_receipt=forged_kind)
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="camera fault diagnostic differs from the precommitted schedule",
    ):
        forged_kind_report.assert_matches_assembly(assembly)


def test_unprintable_unexpected_camera_error_returns_closed_structured_report(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _UnprintableCameraError(RuntimeError):
        def __str__(self) -> str:
            raise RuntimeError("formatting also failed")

    def fail_capture(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise _UnprintableCameraError()

    monkeypatch.setattr(
        B0477ReplayCameraPort,
        "capture_after_settle",
        fail_capture,
    )
    assembly = assemblies["keyboard"]
    prepared = prepare_zero_hardware_mission_v2(
        assembly,
        tmp_path / "unexpected-camera-fault-journals",
        created_at_ns=91_000_000,
    )
    report = run_zero_hardware_mission_v2(prepared)

    assert report.completed is False
    assert report.fault_detail == (
        "_UnprintableCameraError:UNPRINTABLE_EXCEPTION_DETAIL"
    )
    assert report.fault_receipt is not None
    assert report.fault_receipt.source_class == "SettledHoverObservationBoundary"
    assert report.fault_receipt.stage == "SETTLED_HOVER_OBSERVATION"
    assert report.fault_receipt.fault_kind == "OBSERVATION_BOUNDARY_FAILURE"
    assert report.fault_receipt.camera_fault_receipt is None
    assert report.command_receipts[-1].phase is MotionPhase.HOVER
    assert all(
        item.current_state is ActionJournalState.FAULTED
        for item in report.journal_snapshots
    )


def test_hostile_exception_class_name_cannot_bypass_journal_closure(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _HostileNameMeta(type):
        def __getattribute__(cls, name: str) -> object:
            if name == "__name__":
                raise RuntimeError("metaclass name lookup failed")
            return super().__getattribute__(name)

    class _HostileNameCameraError(RuntimeError, metaclass=_HostileNameMeta):
        pass

    def fail_capture(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise _HostileNameCameraError("camera boundary failed")

    monkeypatch.setattr(
        B0477ReplayCameraPort,
        "capture_after_settle",
        fail_capture,
    )
    assembly = assemblies["keyboard"]
    journal_root = tmp_path / "hostile-exception-name-journals"
    prepared = prepare_zero_hardware_mission_v2(
        assembly,
        journal_root,
        created_at_ns=91_500_000,
    )
    report = run_zero_hardware_mission_v2(prepared)

    assert report.completed is False
    assert report.fault_detail == (
        "UNIDENTIFIED_EXCEPTION:camera boundary failed"
    )
    assert report.fault_receipt is not None
    assert report.fault_receipt.source_class == "SettledHoverObservationBoundary"
    assert all(
        item.current_state is ActionJournalState.FAULTED
        for item in report.journal_snapshots
    )
    reopened = open_zero_hardware_mission_v2(assembly, journal_root)
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="automatic integrated restart is refused",
    ):
        run_zero_hardware_mission_v2(reopened)


def test_unlatched_camera_exception_downgrades_to_closed_boundary_report(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    injection = B0477ReplayFaultInjection(
        contact_occurrence_ordinal=0,
        fault_kind=B0477ReplayFaultKind.STALE_FRAME,
    )
    assembly = replace(
        assemblies["keyboard"],
        camera_fault_injection=injection,
    )
    observation = assembly.camera_observations.observations[0]
    malformed = B0477ReplayFaultReceipt(
        fault_kind=injection.fault_kind,
        semantic_step_ordinal=observation.semantic_step_ordinal,
        contact_occurrence_ordinal=observation.contact_occurrence_ordinal,
        target_id=observation.target_id,
        route_waypoint_ordinal=observation.route_waypoint_ordinal,
        authorization_command_ordinal=observation.authorization_command_ordinal,
        settled_controller_pose_sha256=(
            observation.expected_settled_controller_pose_sha256
        ),
        expected_observation_sha256=observation.observation_sha256,
        observation_set_sha256=assembly.camera_observations.canonical_sha256,
        fault_injection_sha256=injection.canonical_sha256,
    )

    def raise_without_port_latch(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise B0477ReplayCaptureError(receipt=malformed)

    monkeypatch.setattr(
        B0477ReplayCameraPort,
        "capture_after_settle",
        raise_without_port_latch,
    )
    journal_root = tmp_path / "malformed-camera-fault-journals"
    prepared = prepare_zero_hardware_mission_v2(
        assembly,
        journal_root,
        created_at_ns=92_000_000,
    )
    report = run_zero_hardware_mission_v2(prepared)

    assert report.completed is False
    assert report.fault_receipt is not None
    assert report.fault_receipt.source_class == "SettledHoverObservationBoundary"
    assert report.fault_receipt.stage == "SETTLED_HOVER_OBSERVATION"
    assert report.fault_receipt.fault_kind == "OBSERVATION_BOUNDARY_FAILURE"
    assert report.fault_receipt.camera_fault_receipt is None
    assert all(
        journal.snapshot().current_state is ActionJournalState.FAULTED
        for journal in prepared.journals
    )
    reopened = open_zero_hardware_mission_v2(assembly, journal_root)
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="automatic integrated restart is refused",
    ):
        run_zero_hardware_mission_v2(reopened)


def test_command_receipt_integrity_failure_closes_journals_before_raising(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unreportable post-runtime bug still disables automatic retry."""

    assembly = assemblies["keyboard"]
    journal_root = tmp_path / "command-wrapper-failure-journals"
    prepared = prepare_zero_hardware_mission_v2(
        assembly,
        journal_root,
        created_at_ns=93_000_000,
    )
    original = IntegratedCommandReceipt.__post_init__
    failed = False

    def fail_once(receipt: IntegratedCommandReceipt) -> None:
        nonlocal failed
        if not failed:
            failed = True
            monkeypatch.setattr(IntegratedCommandReceipt, "__post_init__", original)
            raise RuntimeError("synthetic command-wrapper integrity failure")
        original(receipt)

    monkeypatch.setattr(IntegratedCommandReceipt, "__post_init__", fail_once)
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="runtime counters differ from command receipts",
    ):
        run_zero_hardware_mission_v2(prepared)

    assert failed is True
    assert all(
        journal.snapshot().current_state is ActionJournalState.FAULTED
        for journal in prepared.journals
    )
    reopened = open_zero_hardware_mission_v2(assembly, journal_root)
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="automatic integrated restart is refused",
    ):
        run_zero_hardware_mission_v2(reopened)


def test_contact_receipt_integrity_failure_closes_journals_before_raising(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A post-contact evidence bug cannot reopen a duplicate-contact path."""

    assembly = assemblies["keyboard"]
    journal_root = tmp_path / "contact-wrapper-failure-journals"
    prepared = prepare_zero_hardware_mission_v2(
        assembly,
        journal_root,
        created_at_ns=94_000_000,
    )
    original = IntegratedContactReceipt.__post_init__
    failed = False

    def fail_once(receipt: IntegratedContactReceipt) -> None:
        nonlocal failed
        if not failed:
            failed = True
            monkeypatch.setattr(IntegratedContactReceipt, "__post_init__", original)
            raise RuntimeError("synthetic contact-wrapper integrity failure")
        original(receipt)

    monkeypatch.setattr(IntegratedContactReceipt, "__post_init__", fail_once)
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="output evidence differs from independent contact replay",
    ):
        run_zero_hardware_mission_v2(prepared)

    assert failed is True
    assert all(
        journal.snapshot().current_state is ActionJournalState.FAULTED
        for journal in prepared.journals
    )
    reopened = open_zero_hardware_mission_v2(assembly, journal_root)
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="automatic integrated restart is refused",
    ):
        run_zero_hardware_mission_v2(reopened)


def test_prepare_rejects_timestamp_overflow_before_creating_directory(
    assemblies: Mapping[str, MultiActionMissionSpecV2],
    tmp_path: Path,
) -> None:
    destination = tmp_path / "must-not-exist"
    with pytest.raises(
        IntegratedZeroHardwareMissionError,
        match="lacks bounded headroom",
    ):
        prepare_zero_hardware_mission_v2(
            assemblies["keyboard"],
            destination,
            created_at_ns=2**63 - 1,
        )
    assert not destination.exists()
