from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application.context import load_simulation_context
from rocell.application.static_phase1_calibration import (
    StaticPhase1SyntheticClosure,
    build_static_phase1_synthetic_closure,
    static_phase1_context_hashes,
)
from rocell.calibration import ArtifactState
from rocell.calibration.static_phase1_requirements import (
    STATIC_OVERHEAD_PHASE1_AUTHORITY,
    STATIC_OVERHEAD_PHASE1_GRAPH,
)
from rocell.safety.authorization_v2 import (
    ZERO_AUTHORITY,
    AuthorizationV2Error,
    EvidenceOnlyReleaseScope,
    InterlockChannel,
    SimulatedContactCapability,
    SimulationPrimitive,
    SimulationTrajectoryCommand,
    issue_ordered_simulation_permit,
    trajectory_sequence_sha256,
)
from rocell.safety.synthetic_authorization import (
    SYNTHETIC_AUTHORIZATION_BUNDLE_SCHEMA,
    SYNTHETIC_CALIBRATION_PROJECTION_SCHEMA,
    SYNTHETIC_CONTINUITY_SAMPLE_SCHEMA,
    SYNTHETIC_EMULATOR_IDENTITY_SCHEMA,
    SYNTHETIC_INTERLOCK_MAX_AGE_S,
    SYNTHETIC_ISSUANCE_MONOTONIC,
    SYNTHETIC_PERMIT_TTL_S,
    SyntheticAuthorizationError,
    SyntheticCalibrationProjection,
    SyntheticEmulatorIdentity,
    SyntheticInterlockContinuity,
    build_synthetic_authorization_evidence,
    project_static_phase1_synthetic_closure,
)


WORKSPACE = Path(__file__).resolve().parents[3]
MANIFEST = WORKSPACE / "software/config/system_manifest.json"


def _hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def synthetic_closure() -> StaticPhase1SyntheticClosure:
    context = load_simulation_context(WORKSPACE, MANIFEST)
    return build_static_phase1_synthetic_closure(
        static_phase1_context_hashes(context)
    )


def _emulator() -> SyntheticEmulatorIdentity:
    return SyntheticEmulatorIdentity(
        emulator_id="deterministic-roarm-m3-emulator-v1",
        configuration_sha256=_hash("emulator configuration"),
        session_id="synthetic-session-0001",
    )


def _commands() -> tuple[tuple[str, ...], tuple[SimulationTrajectoryCommand, ...]]:
    occurrences = (_hash("physical occurrence 0"), _hash("physical occurrence 1"))
    commands = (
        SimulationTrajectoryCommand(
            command_occurrence_id=_hash("command occurrence 0"),
            action_occurrence_id=occurrences[0],
            primitive=SimulationPrimitive.MOVE_ABOVE,
            target_state_sha256=_hash("target state 0"),
            constraint_set_sha256=_hash("constraint set 0"),
        ),
        SimulationTrajectoryCommand(
            command_occurrence_id=_hash("command occurrence 1"),
            action_occurrence_id=occurrences[0],
            primitive=SimulationPrimitive.CONTACT_INTENT,
            target_state_sha256=_hash("target state 1"),
            constraint_set_sha256=_hash("constraint set 1"),
        ),
        SimulationTrajectoryCommand(
            command_occurrence_id=_hash("command occurrence 2"),
            action_occurrence_id=occurrences[1],
            primitive=SimulationPrimitive.RETRACT,
            target_state_sha256=_hash("target state 2"),
            constraint_set_sha256=_hash("constraint set 2"),
        ),
    )
    return occurrences, commands


def _projection(
    source: StaticPhase1SyntheticClosure,
    capability: SimulatedContactCapability = SimulatedContactCapability.KEYBOARD,
) -> SyntheticCalibrationProjection:
    return project_static_phase1_synthetic_closure(
        source, capability=capability
    )


def _authorization(
    source: StaticPhase1SyntheticClosure,
    capability: SimulatedContactCapability = SimulatedContactCapability.KEYBOARD,
):  # type: ignore[no-untyped-def]
    occurrences, commands = _commands()
    return build_synthetic_authorization_evidence(
        calibration=_projection(source, capability),
        ordered_physical_occurrence_ids=occurrences,
        ordered_commands=commands,
        collision_report_sha256=_hash("static route collision report"),
        device_safety_context_sha256=_hash("stable device safety context"),
        build_snapshot_sha256=_hash("build snapshot"),
        plan_sha256=_hash("semantic integration plan"),
        emulator=_emulator(),
    )


@pytest.mark.parametrize(
    ("capability", "device"),
    [
        (SimulatedContactCapability.KEYBOARD, "keyboard"),
        (SimulatedContactCapability.PHONE, "phone"),
    ],
)
def test_projection_is_exact_capability_specific_and_nominal_only(
    synthetic_closure: StaticPhase1SyntheticClosure,
    capability: SimulatedContactCapability,
    device: str,
) -> None:
    projection = _projection(synthetic_closure, capability)
    expected_ids = STATIC_OVERHEAD_PHASE1_GRAPH.device_closure(device)

    assert projection.schema == SYNTHETIC_CALIBRATION_PROJECTION_SCHEMA
    assert projection.capability is capability
    assert projection.source_closure_sha256 == synthetic_closure.closure_hash
    assert tuple(item.name for item in projection.nominal_artifact_hashes) == (
        expected_ids
    )
    assert tuple(item.artifact_id for item in projection.calibration.artifacts) == (
        expected_ids
    )
    assert projection.calibration.capability is capability
    assert projection.calibration.graph_id == STATIC_OVERHEAD_PHASE1_GRAPH.graph_id
    assert (
        projection.calibration.graph_sha256
        == STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash
    )
    assert tuple(item.name for item in projection.source_context_hashes) == tuple(
        sorted(STATIC_OVERHEAD_PHASE1_GRAPH.required_context_hash_ids)
    )
    assert tuple(item.sha256 for item in projection.nominal_artifact_hashes) == tuple(
        item.artifact_sha256 for item in projection.calibration.artifacts
    )
    projection.assert_matches_source(synthetic_closure)

    document = projection.to_dict()
    assert document["source_static_phase1"]["authority"] == (  # type: ignore[index]
        STATIC_OVERHEAD_PHASE1_AUTHORITY
    )
    assert all(
        row["state"] == ArtifactState.NOMINAL_ONLY.value
        and row["synthetic"] is True
        and row["physical_measurements_present"] is False
        and row["execution_authorized"] is False
        for row in document["artifacts"]  # type: ignore[union-attr]
    )
    assert document["authority"] == ZERO_AUTHORITY
    assert document["simulation_only"] is True
    assert document["hardware_accessed"] is False
    assert document["hardware_commands_generated"] == 0
    assert document["live_motion_authorized"] is False
    assert document["physical_contact_authorized"] is False
    assert document["physical_release_effect"] == "NONE"


def test_projection_is_deterministic_and_does_not_mutate_source(
    synthetic_closure: StaticPhase1SyntheticClosure,
) -> None:
    source_before = synthetic_closure.to_dict()
    first = _projection(synthetic_closure)
    second = _projection(synthetic_closure)

    assert first == second
    assert first.to_dict() == second.to_dict()
    assert first.projection_sha256 == second.projection_sha256
    assert synthetic_closure.to_dict() == source_before


def test_projection_rejects_source_context_graph_and_artifact_drift(
    synthetic_closure: StaticPhase1SyntheticClosure,
) -> None:
    changed_context = build_static_phase1_synthetic_closure(
        dict(synthetic_closure.context_hashes)
    )
    context_rows = list(changed_context.context_hashes)
    context_rows[0] = (context_rows[0][0], _hash("drifted context"))
    object.__setattr__(changed_context, "context_hashes", tuple(context_rows))
    with pytest.raises(SyntheticAuthorizationError, match="source bindings|closure"):
        _projection(changed_context)

    changed_graph = build_static_phase1_synthetic_closure(
        dict(synthetic_closure.context_hashes)
    )
    first_artifact = changed_graph.artifacts[0]
    dependencies = dict(first_artifact.dependency_hashes)
    dependencies["static_phase1_requirement_graph"] = _hash("wrong graph")
    drifted_artifact = replace(first_artifact, dependency_hashes=dependencies)
    object.__setattr__(
        changed_graph,
        "artifacts",
        (drifted_artifact, *changed_graph.artifacts[1:]),
    )
    with pytest.raises(SyntheticAuthorizationError, match="source bindings|closure"):
        _projection(changed_graph)

    changed_artifact = build_static_phase1_synthetic_closure(
        dict(synthetic_closure.context_hashes)
    )
    original = changed_artifact.artifacts[0]
    new_artifact = replace(
        original,
        payload={**dict(original.payload), "synthetic_drift": True},
    )
    object.__setattr__(
        changed_artifact,
        "artifacts",
        (new_artifact, *changed_artifact.artifacts[1:]),
    )
    with pytest.raises(SyntheticAuthorizationError, match="closure"):
        _projection(changed_artifact)


def test_projection_rejects_false_edge_evidence_and_type_substitution(
    synthetic_closure: StaticPhase1SyntheticClosure,
) -> None:
    changed = build_static_phase1_synthetic_closure(
        dict(synthetic_closure.context_hashes)
    )
    object.__setattr__(changed, "staleness_probes", changed.staleness_probes[:-1])
    with pytest.raises(SyntheticAuthorizationError, match="every synthetic graph edge"):
        _projection(changed)

    class DerivedClosure(StaticPhase1SyntheticClosure):
        pass

    derived = DerivedClosure(
        context_hashes=synthetic_closure.context_hashes,
        artifacts=synthetic_closure.artifacts,
        baseline_assessments=synthetic_closure.baseline_assessments,
        staleness_probes=synthetic_closure.staleness_probes,
    )
    with pytest.raises(TypeError, match="exactly StaticPhase1SyntheticClosure"):
        _projection(derived)


def test_projection_rejects_postconstruction_binding_mutation(
    synthetic_closure: StaticPhase1SyntheticClosure,
) -> None:
    projection = _projection(synthetic_closure)
    object.__setattr__(projection, "source_closure_sha256", "0" * 64)
    with pytest.raises(SyntheticAuthorizationError, match="changed|source"):
        projection.validate()


def test_emulator_identity_is_exact_deterministic_and_zero_authority() -> None:
    first = _emulator()
    second = _emulator()
    assert first.schema == SYNTHETIC_EMULATOR_IDENTITY_SCHEMA
    assert first == second
    assert first.identity_sha256 == second.identity_sha256
    assert first.to_dict()["hardware_accessed"] is False
    assert first.to_dict()["hardware_commands_generated"] == 0
    assert first.to_dict()["physical_contact_authorized"] is False
    with pytest.raises(FrozenInstanceError):
        first.session_id = "changed"  # type: ignore[misc]


def test_authorization_maps_every_exact_input_deterministically(
    synthetic_closure: StaticPhase1SyntheticClosure,
) -> None:
    first = _authorization(synthetic_closure)
    second = _authorization(synthetic_closure)
    occurrences, commands = _commands()

    assert first.schema == SYNTHETIC_AUTHORIZATION_BUNDLE_SCHEMA
    assert first == second
    assert first.to_dict() == second.to_dict()
    assert first.bundle_sha256 == second.bundle_sha256
    assert first.ordered_physical_occurrence_ids == occurrences
    assert first.ordered_commands == commands
    assert first.evidence.ordered_action_occurrence_ids == occurrences
    assert first.evidence.ordered_commands == commands
    assert first.evidence.ordered_trajectory_command_hashes == tuple(
        command.command_sha256 for command in commands
    )
    assert (
        first.evidence.collision.cleared_trajectory_sha256
        == trajectory_sequence_sha256(commands)
    )
    assert first.evidence.collision.report_sha256 == _hash(
        "static route collision report"
    )
    assert first.evidence.device_state_sha256 == _hash(
        "stable device safety context"
    )
    assert first.evidence.build_release.build_snapshot_sha256 == _hash(
        "build snapshot"
    )
    assert (
        first.evidence.build_release.scope
        is EvidenceOnlyReleaseScope.SIMULATION_EVIDENCE_ONLY
    )
    assert first.evidence.controller.controller_hardware_id == (
        _emulator().emulator_id
    )
    assert first.evidence.controller.connection_session_id == _emulator().session_id
    assert first.evidence.controller.firmware_sha256 == (
        _emulator().configuration_sha256
    )
    assert first.evidence.controller.transport_descriptor_sha256 == (
        _emulator().identity_sha256
    )
    assert first.evidence.calibration is first.calibration.calibration
    assert first.evidence.plan_sha256 == _hash("semantic integration plan")
    assert first.evidence.to_dict()["authority"] == ZERO_AUTHORITY

    document = first.to_dict()
    assert document["authority"] == ZERO_AUTHORITY
    assert document["simulation_only"] is True
    assert document["hardware_accessed"] is False
    assert document["hardware_commands_generated"] == 0
    assert document["power_authorized"] is False
    assert document["live_motion_authorized"] is False
    assert document["physical_contact_authorized"] is False
    assert document["physical_release_effect"] == "NONE"


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("collision_report_sha256", _hash("different collision")),
        ("device_safety_context_sha256", _hash("different safety context")),
        ("build_snapshot_sha256", _hash("different build")),
        ("plan_sha256", _hash("different plan")),
        ("authorization_seed_sha256", _hash("different seed")),
    ],
)
def test_authorization_bundle_rejects_binding_drift(
    synthetic_closure: StaticPhase1SyntheticClosure,
    field: str,
    changed: str,
) -> None:
    bundle = _authorization(synthetic_closure)
    with pytest.raises(SyntheticAuthorizationError, match="drifted|seed"):
        replace(bundle, **{field: changed})


def test_authorization_rejects_non_tuple_empty_duplicate_and_unordered_inputs(
    synthetic_closure: StaticPhase1SyntheticClosure,
) -> None:
    projection = _projection(synthetic_closure)
    occurrences, commands = _commands()
    common = {
        "calibration": projection,
        "collision_report_sha256": _hash("collision"),
        "device_safety_context_sha256": _hash("device context"),
        "build_snapshot_sha256": _hash("build"),
        "plan_sha256": _hash("plan"),
        "emulator": _emulator(),
    }
    with pytest.raises(TypeError, match="ordered_commands"):
        build_synthetic_authorization_evidence(
            ordered_physical_occurrence_ids=occurrences,
            ordered_commands=list(commands),  # type: ignore[arg-type]
            **common,  # type: ignore[arg-type]
        )
    with pytest.raises(SyntheticAuthorizationError, match="empty"):
        build_synthetic_authorization_evidence(
            ordered_physical_occurrence_ids=occurrences,
            ordered_commands=(),
            **common,  # type: ignore[arg-type]
        )
    with pytest.raises(SyntheticAuthorizationError, match="must be unique"):
        build_synthetic_authorization_evidence(
            ordered_physical_occurrence_ids=(occurrences[0], occurrences[0]),
            ordered_commands=commands,
            **common,  # type: ignore[arg-type]
        )

    noncontiguous = (commands[0], commands[2], commands[1])
    with pytest.raises(AuthorizationV2Error, match="contiguous|grouping"):
        build_synthetic_authorization_evidence(
            ordered_physical_occurrence_ids=occurrences,
            ordered_commands=noncontiguous,
            **common,  # type: ignore[arg-type]
        )


def test_authorization_rejects_command_and_emulator_type_substitution(
    synthetic_closure: StaticPhase1SyntheticClosure,
) -> None:
    class DerivedCommand(SimulationTrajectoryCommand):
        pass

    occurrences, commands = _commands()
    substituted = object.__new__(DerivedCommand)
    for name in (
        "command_occurrence_id",
        "action_occurrence_id",
        "primitive",
        "target_state_sha256",
        "constraint_set_sha256",
    ):
        object.__setattr__(substituted, name, getattr(commands[0], name))
    with pytest.raises(SyntheticAuthorizationError, match="substituted command"):
        build_synthetic_authorization_evidence(
            calibration=_projection(synthetic_closure),
            ordered_physical_occurrence_ids=occurrences,
            ordered_commands=(substituted, *commands[1:]),
            collision_report_sha256=_hash("collision"),
            device_safety_context_sha256=_hash("device"),
            build_snapshot_sha256=_hash("build"),
            plan_sha256=_hash("plan"),
            emulator=_emulator(),
        )

    class DerivedEmulator(SyntheticEmulatorIdentity):
        pass

    derived = DerivedEmulator(
        emulator_id="derived-emulator",
        configuration_sha256=_hash("derived config"),
        session_id="derived-session",
    )
    with pytest.raises(TypeError, match="exactly SyntheticEmulatorIdentity"):
        build_synthetic_authorization_evidence(
            calibration=_projection(synthetic_closure),
            ordered_physical_occurrence_ids=occurrences,
            ordered_commands=commands,
            collision_report_sha256=_hash("collision"),
            device_safety_context_sha256=_hash("device"),
            build_snapshot_sha256=_hash("build"),
            plan_sha256=_hash("plan"),
            emulator=derived,
        )


def test_continuity_advances_sequence_time_and_raw_hash_per_command(
    synthetic_closure: StaticPhase1SyntheticClosure,
) -> None:
    bundle = _authorization(synthetic_closure)
    cursor = SyntheticInterlockContinuity(bundle)
    permit = issue_ordered_simulation_permit(
        bundle.evidence,
        ttl_s=SYNTHETIC_PERMIT_TTL_S,
        now_monotonic=SYNTHETIC_ISSUANCE_MONOTONIC,
        interlock_max_age_s=SYNTHETIC_INTERLOCK_MAX_AGE_S,
    )
    previous_sequences = {channel: 0 for channel in InterlockChannel}
    previous_times = {
        channel: SYNTHETIC_ISSUANCE_MONOTONIC for channel in InterlockChannel
    }
    previous_hashes = {
        channel.channel: channel.raw_sha256
        for channel in bundle.evidence.interlocks.channels
    }

    for ordinal, command in enumerate(bundle.ordered_commands):
        assert cursor.next_ordinal == ordinal
        sample = cursor.next_sample()
        assert sample.schema == SYNTHETIC_CONTINUITY_SAMPLE_SCHEMA
        assert sample.command_ordinal == ordinal
        assert sample.to_dict()["hardware_accessed"] is False
        assert sample.to_dict()["hardware_commands_generated"] == 0
        for channel in sample.continuity.interlocks.channels:
            assert channel.sequence > previous_sequences[channel.channel]
            assert channel.captured_monotonic > previous_times[channel.channel]
            assert channel.raw_sha256 != previous_hashes[channel.channel]
            assert channel.source_id == f"synthetic-{channel.channel.value}-source-v1"
            previous_sequences[channel.channel] = channel.sequence
            previous_times[channel.channel] = channel.captured_monotonic
            previous_hashes[channel.channel] = channel.raw_sha256

        receipt = permit.consume_next(
            ordinal=sample.command_ordinal,
            action_occurrence_id=command.action_occurrence_id,
            command=command,
            continuity=sample.continuity,
            now_monotonic=sample.now_monotonic,
        )
        assert receipt.ordinal == ordinal

    assert cursor.next_ordinal is None
    assert cursor.remaining_samples == 0
    assert permit.complete is True
    assert cursor.zero_authority is True
    with pytest.raises(SyntheticAuthorizationError, match="exhausted"):
        cursor.next_sample()


def test_continuity_is_deterministic_and_rejects_raw_or_bundle_mutation(
    synthetic_closure: StaticPhase1SyntheticClosure,
) -> None:
    bundle = _authorization(synthetic_closure)
    first = SyntheticInterlockContinuity(bundle).next_sample()
    second = SyntheticInterlockContinuity(bundle).next_sample()
    assert first == second
    assert first.to_dict() == second.to_dict()

    changed_channel = replace(
        first.continuity.interlocks.channels[0], raw_sha256=_hash("changed raw")
    )
    changed_bundle = replace(
        first.continuity.interlocks,
        channels=(changed_channel, *first.continuity.interlocks.channels[1:]),
    )
    changed_continuity = replace(first.continuity, interlocks=changed_bundle)
    with pytest.raises(SyntheticAuthorizationError, match="exact advancing sample"):
        replace(first, continuity=changed_continuity)

    cursor = SyntheticInterlockContinuity(bundle)
    object.__setattr__(bundle, "device_safety_context_sha256", _hash("mutated"))
    with pytest.raises(SyntheticAuthorizationError, match="drifted|changed"):
        cursor.next_sample()


def test_continuity_callable_matches_mission_cursor_supplier_shape(
    synthetic_closure: StaticPhase1SyntheticClosure,
) -> None:
    bundle = _authorization(synthetic_closure)
    supplier = SyntheticInterlockContinuity(bundle)
    command = bundle.ordered_commands[0]
    binding = SimpleNamespace(
        simulation_command=command,
        action_occurrence_sha256=command.action_occurrence_id,
    )

    continuity, now = supplier(binding, 0)
    assert all(row.sequence == 1 for row in continuity.interlocks.channels)
    assert all(row.captured_monotonic < now for row in continuity.interlocks.channels)
    with pytest.raises(SyntheticAuthorizationError, match="skipped|duplicated"):
        supplier(binding, 0)

    wrong_supplier = SyntheticInterlockContinuity(bundle)
    wrong_binding = SimpleNamespace(
        simulation_command=bundle.ordered_commands[1],
        action_occurrence_sha256=bundle.ordered_commands[1].action_occurrence_id,
    )
    with pytest.raises(SyntheticAuthorizationError, match="differs"):
        wrong_supplier(wrong_binding, 0)
