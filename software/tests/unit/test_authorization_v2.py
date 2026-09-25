from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
from dataclasses import replace
import hashlib
import math
from pathlib import Path
import pickle
from types import MappingProxyType

import pytest

from rocell.calibration.static_phase1_requirements import (
    STATIC_OVERHEAD_PHASE1_GRAPH,
)
from rocell.calibration import ArtifactState, CalibrationArtifact, CalibrationRegistry
from rocell.safety.authorization_v2 import (
    KEYBOARD_REQUIRED_ARTIFACT_IDS,
    PHONE_REQUIRED_ARTIFACT_IDS,
    ZERO_AUTHORITY,
    AuthorizationContinuityEvidence,
    AuthorizationEvidence,
    AuthorizationV2Error,
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
    OrderedSimulationPermit,
    SimulatedContactCapability,
    SimulationCommandReceipt,
    SimulationPrimitive,
    SimulationTrajectoryCommand,
    calibration_closure_from_registry,
    canonical_record_sha256,
    continuity_from_authorization,
    issue_ordered_simulation_permit,
    trajectory_sequence_sha256,
)


def _hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _controller(
    *,
    session: str = "connection-session-0001",
    port: str = "usb-port-controller-persistent-0001",
) -> ControllerSessionEvidence:
    return ControllerSessionEvidence(
        arm_hardware_id="roarm-m3-pro-received-0001",
        controller_hardware_id="esp32-controller-received-0001",
        firmware_build_id="waveshare-firmware-observed-0001",
        firmware_sha256=_hash("firmware"),
        connection_session_id=session,
        persistent_port_id=port,
        transport_descriptor_sha256=_hash("transport descriptor"),
    )


def _build_release(
    *, active_build_id: str = "rc03-received-build-0001"
) -> BuildReleaseIdentity:
    return BuildReleaseIdentity(
        active_build_id=active_build_id,
        build_snapshot_sha256=_hash("build snapshot"),
        manifest_id="rc03-system-manifest",
        manifest_sha256=_hash("manifest"),
        release_receipt_id="simulation-evidence-receipt-0001",
        release_receipt_sha256=_hash("release receipt"),
        scope=EvidenceOnlyReleaseScope.SIMULATION_EVIDENCE_ONLY,
    )


def _calibration(
    capability: SimulatedContactCapability,
) -> CalibrationClosureEvidence:
    device = (
        "keyboard"
        if capability is SimulatedContactCapability.KEYBOARD
        else "phone"
    )
    artifact_ids = STATIC_OVERHEAD_PHASE1_GRAPH.device_closure(device)
    artifact_hashes = {
        artifact_id: _hash(f"artifact:{artifact_id}") for artifact_id in artifact_ids
    }
    context_hashes = {
        context_id: _hash(f"context:{context_id}")
        for artifact_id in artifact_ids
        for context_id in STATIC_OVERHEAD_PHASE1_GRAPH.requirements[
            artifact_id
        ].context_dependencies
    }
    artifacts = tuple(
        CalibrationArtifactBinding(
            artifact_id=artifact_id,
            artifact_sha256=artifact_hashes[artifact_id],
            dependency_hashes=tuple(
                NamedSha256(dependency, artifact_hashes[dependency])
                for dependency in STATIC_OVERHEAD_PHASE1_GRAPH.requirements[
                    artifact_id
                ].prerequisites
            ),
            context_hashes=tuple(
                NamedSha256(context_id, context_hashes[context_id])
                for context_id in STATIC_OVERHEAD_PHASE1_GRAPH.requirements[
                    artifact_id
                ].context_dependencies
            ),
        )
        for artifact_id in artifact_ids
    )
    return CalibrationClosureEvidence(
        capability=capability,
        graph_id=STATIC_OVERHEAD_PHASE1_GRAPH.graph_id,
        graph_sha256=STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash,
        artifacts=artifacts,
    )


def _registry_calibration(
    root: Path,
    capability: SimulatedContactCapability,
    *,
    state_override: tuple[str, ArtifactState] | None = None,
    extra_parent_on: str | None = None,
) -> tuple[CalibrationRegistry, dict[str, str], str, str]:
    """Install one exact device closure for registry-adapter tests."""

    registry = CalibrationRegistry(root)
    device = (
        "keyboard"
        if capability is SimulatedContactCapability.KEYBOARD
        else "phone"
    )
    artifact_ids = STATIC_OVERHEAD_PHASE1_GRAPH.device_closure(device)
    context_hashes = {
        context_id: _hash(f"registry-context:{context_id}")
        for artifact_id in artifact_ids
        for context_id in STATIC_OVERHEAD_PHASE1_GRAPH.requirements[
            artifact_id
        ].context_dependencies
    }
    manifest_id = "registry-manifest-001"
    active_build_id = "registry-build-001"
    installed: dict[str, CalibrationArtifact] = {}
    extra_parent: CalibrationArtifact | None = None
    if extra_parent_on is not None:
        extra_parent = CalibrationArtifact(
            artifact_id="unmodeled_calibration_parent",
            version=1,
            state=ArtifactState.VALID,
            created_utc="2026-09-05T00:00:00Z",
            manifest_id=manifest_id,
            active_build_id=active_build_id,
            dependency_hashes={},
            parent_artifact_hashes={},
            payload={"test_only": True},
        )
        registry.install(extra_parent)

    for artifact_id in artifact_ids:
        requirement = STATIC_OVERHEAD_PHASE1_GRAPH.requirements[artifact_id]
        state = (
            state_override[1]
            if state_override is not None and state_override[0] == artifact_id
            else ArtifactState.VALID
        )
        parents = {
            parent_id: installed[parent_id].content_hash
            for parent_id in requirement.prerequisites
        }
        if artifact_id == extra_parent_on:
            assert extra_parent is not None
            parents[extra_parent.artifact_id] = extra_parent.content_hash
        artifact = CalibrationArtifact(
            artifact_id=artifact_id,
            version=1,
            state=state,
            created_utc="2026-09-05T00:00:00Z",
            manifest_id=manifest_id,
            active_build_id=active_build_id,
            dependency_hashes={
                "static_phase1_requirement_graph": (
                    STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash
                ),
                **{
                    context_id: context_hashes[context_id]
                    for context_id in requirement.context_dependencies
                },
            },
            parent_artifact_hashes=parents,
            payload={
                "requirement_artifact_schema": requirement.artifact_schema,
                "test_only": True,
            },
        )
        registry.install(artifact)
        installed[artifact_id] = artifact
    return registry, context_hashes, manifest_id, active_build_id


def _interlocks(
    *,
    captured: float = 99.8,
    sequence: int = 7,
    source_suffix: str = "",
    state: InterlockEvidenceState = InterlockEvidenceState.PASS,
) -> InterlockEvidenceBundle:
    return InterlockEvidenceBundle(
        channels=tuple(
            InterlockChannelEvidence(
                channel=channel,
                source_id=f"{channel.value}-source{source_suffix}",
                sequence=sequence,
                captured_monotonic=captured,
                raw_sha256=_hash(
                    f"{channel.value}:{source_suffix}:{sequence}:{captured}:{state.value}"
                ),
                state=state,
            )
            for channel in InterlockChannel
        )
    )


def _command(
    action_id: str,
    ordinal: int,
    *,
    primitive: SimulationPrimitive = SimulationPrimitive.MOVE_ABOVE,
    target_label: str | None = None,
) -> SimulationTrajectoryCommand:
    return SimulationTrajectoryCommand(
        command_occurrence_id=_hash(f"command occurrence:{ordinal}"),
        action_occurrence_id=action_id,
        primitive=primitive,
        target_state_sha256=_hash(target_label or f"target:{ordinal}"),
        constraint_set_sha256=_hash(f"constraints:{ordinal}"),
    )


def _evidence(
    *,
    capability: SimulatedContactCapability = SimulatedContactCapability.KEYBOARD,
    action_count: int = 2,
    commands_per_action: int = 1,
    interlocks: InterlockEvidenceBundle | None = None,
) -> AuthorizationEvidence:
    actions = tuple(_hash(f"action:{index}") for index in range(action_count))
    commands: list[SimulationTrajectoryCommand] = []
    ordinal = 0
    for action in actions:
        for _ in range(commands_per_action):
            commands.append(_command(action, ordinal))
            ordinal += 1
    command_tuple = tuple(commands)
    trajectory_hash = trajectory_sequence_sha256(command_tuple)
    return AuthorizationEvidence(
        capability=capability,
        controller=_controller(),
        build_release=_build_release(),
        calibration=_calibration(capability),
        collision=CollisionTrajectoryEvidence(
            report_sha256=_hash("collision report"),
            cleared_trajectory_sha256=trajectory_hash,
            state=CollisionClearanceState.CLEAR_FOR_SIMULATION,
        ),
        device_state_sha256=_hash(f"{capability.value}:device state"),
        interlocks=_interlocks() if interlocks is None else interlocks,
        operator_arm=OperatorArmEvidence(
            operator_id="operator-local-0001",
            nonce_sha256=_hash("operator arm nonce"),
            armed_at_monotonic=99.0,
            expires_at_monotonic=110.0,
        ),
        plan_sha256=_hash("ordered mission plan"),
        ordered_action_occurrence_ids=actions,
        ordered_commands=command_tuple,
    )


def _issue(evidence: AuthorizationEvidence) -> OrderedSimulationPermit:
    return issue_ordered_simulation_permit(
        evidence,
        ttl_s=5.0,
        now_monotonic=100.0,
        interlock_max_age_s=0.5,
    )


def test_keyboard_and_phone_have_exact_distinct_calibration_closures() -> None:
    keyboard = _calibration(SimulatedContactCapability.KEYBOARD)
    phone = _calibration(SimulatedContactCapability.PHONE)

    assert tuple(item.artifact_id for item in keyboard.artifacts) == (
        KEYBOARD_REQUIRED_ARTIFACT_IDS
    )
    assert tuple(item.artifact_id for item in phone.artifacts) == (
        PHONE_REQUIRED_ARTIFACT_IDS
    )
    assert "phase1_keyboard_tcp" in KEYBOARD_REQUIRED_ARTIFACT_IDS
    assert "phase1_phone_tcp" not in KEYBOARD_REQUIRED_ARTIFACT_IDS
    assert "phase1_phone_tcp" in PHONE_REQUIRED_ARTIFACT_IDS
    assert "phase1_keyboard_tcp" not in PHONE_REQUIRED_ARTIFACT_IDS


@pytest.mark.parametrize(
    "capability",
    (
        SimulatedContactCapability.KEYBOARD,
        SimulatedContactCapability.PHONE,
    ),
)
def test_registry_adapter_resolves_the_exact_valid_device_closure(
    tmp_path: Path, capability: SimulatedContactCapability
) -> None:
    registry, contexts, manifest_id, active_build_id = _registry_calibration(
        tmp_path / capability.name.lower(), capability
    )

    closure = calibration_closure_from_registry(
        registry,
        capability=capability,
        context_hashes=contexts,
        manifest_id=manifest_id,
        active_build_id=active_build_id,
    )

    device = (
        "keyboard"
        if capability is SimulatedContactCapability.KEYBOARD
        else "phone"
    )
    assert tuple(item.artifact_id for item in closure.artifacts) == (
        STATIC_OVERHEAD_PHASE1_GRAPH.device_closure(device)
    )
    assert closure.capability is capability
    assert closure.graph_sha256 == STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash


def test_registry_adapter_rejects_wrong_context_set_and_nonvalid_artifact(
    tmp_path: Path,
) -> None:
    capability = SimulatedContactCapability.KEYBOARD
    registry, contexts, manifest_id, active_build_id = _registry_calibration(
        tmp_path / "valid", capability
    )
    missing = dict(contexts)
    missing.pop(next(iter(missing)))
    with pytest.raises(AuthorizationV2Error, match="exact requirement set"):
        calibration_closure_from_registry(
            registry,
            capability=capability,
            context_hashes=missing,
            manifest_id=manifest_id,
            active_build_id=active_build_id,
        )
    with pytest.raises(AuthorizationV2Error, match="exact requirement set"):
        calibration_closure_from_registry(
            registry,
            capability=capability,
            context_hashes={**contexts, "unrequested_context": _hash("extra")},
            manifest_id=manifest_id,
            active_build_id=active_build_id,
        )

    first_id = STATIC_OVERHEAD_PHASE1_GRAPH.device_closure("keyboard")[0]
    nominal_registry, nominal_contexts, nominal_manifest, nominal_build = (
        _registry_calibration(
            tmp_path / "nominal",
            capability,
            state_override=(first_id, ArtifactState.NOMINAL_ONLY),
        )
    )
    with pytest.raises(AuthorizationV2Error, match="missing, stale, or non-valid"):
        calibration_closure_from_registry(
            nominal_registry,
            capability=capability,
            context_hashes=nominal_contexts,
            manifest_id=nominal_manifest,
            active_build_id=nominal_build,
        )


def test_registry_adapter_rejects_an_unmodeled_parent_even_when_it_is_valid(
    tmp_path: Path,
) -> None:
    capability = SimulatedContactCapability.KEYBOARD
    root_id = STATIC_OVERHEAD_PHASE1_GRAPH.device_closure("keyboard")[0]
    registry, contexts, manifest_id, active_build_id = _registry_calibration(
        tmp_path / "extra-parent",
        capability,
        extra_parent_on=root_id,
    )

    with pytest.raises(AuthorizationV2Error, match="parents differ from the exact graph"):
        calibration_closure_from_registry(
            registry,
            capability=capability,
            context_hashes=contexts,
            manifest_id=manifest_id,
            active_build_id=active_build_id,
        )


def test_exact_calibration_order_dependency_and_context_hashes_are_enforced() -> None:
    valid = _calibration(SimulatedContactCapability.KEYBOARD)

    with pytest.raises(AuthorizationV2Error, match="exact ordered"):
        replace(valid, artifacts=valid.artifacts[::-1])

    child_index = next(
        index
        for index, item in enumerate(valid.artifacts)
        if item.dependency_hashes
    )
    child = valid.artifacts[child_index]
    broken_child = replace(
        child,
        dependency_hashes=(
            replace(child.dependency_hashes[0], sha256=_hash("wrong parent")),
            *child.dependency_hashes[1:],
        ),
    )
    broken_artifacts = list(valid.artifacts)
    broken_artifacts[child_index] = broken_child
    with pytest.raises(AuthorizationV2Error, match="dependency hash mismatch"):
        replace(valid, artifacts=tuple(broken_artifacts))

    context_index = next(
        index for index, item in enumerate(valid.artifacts) if item.context_hashes
    )
    context_item = valid.artifacts[context_index]
    wrong_context_id = replace(context_item.context_hashes[0], name="unexpected_context")
    with pytest.raises(AuthorizationV2Error, match="context IDs"):
        replace(
            valid,
            artifacts=(
                *valid.artifacts[:context_index],
                replace(
                    context_item,
                    context_hashes=(wrong_context_id, *context_item.context_hashes[1:]),
                ),
                *valid.artifacts[context_index + 1 :],
            ),
        )


def test_cross_artifact_context_hash_must_be_consistent() -> None:
    valid = _calibration(SimulatedContactCapability.KEYBOARD)
    locations: dict[str, list[tuple[int, int]]] = {}
    for artifact_index, artifact in enumerate(valid.artifacts):
        for context_index, context in enumerate(artifact.context_hashes):
            locations.setdefault(context.name, []).append(
                (artifact_index, context_index)
            )
    repeated = next(items for items in locations.values() if len(items) >= 2)
    artifact_index, context_index = repeated[-1]
    artifact = valid.artifacts[artifact_index]
    contexts = list(artifact.context_hashes)
    contexts[context_index] = replace(contexts[context_index], sha256=_hash("drift"))
    artifacts = list(valid.artifacts)
    artifacts[artifact_index] = replace(artifact, context_hashes=tuple(contexts))

    with pytest.raises(AuthorizationV2Error, match="context hash is inconsistent"):
        replace(valid, artifacts=tuple(artifacts))


def test_bare_booleans_do_not_satisfy_typed_evidence() -> None:
    with pytest.raises(TypeError, match="InterlockEvidenceState"):
        replace(_interlocks().channels[0], state=True)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="CollisionClearanceState"):
        CollisionTrajectoryEvidence(
            _hash("report"), _hash("trajectory"), True  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="EvidenceOnlyReleaseScope"):
        replace(_build_release(), scope=True)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="SimulatedContactCapability"):
        replace(_calibration(SimulatedContactCapability.KEYBOARD), capability=True)  # type: ignore[arg-type]


def test_canonical_hash_is_order_independent_and_strict() -> None:
    assert canonical_record_sha256({"b": 2, "a": [1, "x"]}) == (
        canonical_record_sha256({"a": [1, "x"], "b": 2})
    )
    with pytest.raises(AuthorizationV2Error, match="finite"):
        canonical_record_sha256({"bad": math.nan})
    with pytest.raises(AuthorizationV2Error, match="exact range"):
        canonical_record_sha256({"bad": 1 << 60})
    with pytest.raises(TypeError, match="exactly dict"):
        canonical_record_sha256(MappingProxyType({"a": 1}))


def test_context_hash_binds_ordered_actions_and_commands() -> None:
    evidence = _evidence()
    reordered_commands = evidence.ordered_commands[::-1]

    assert evidence.to_dict()["authority"] == ZERO_AUTHORITY
    assert evidence.ordered_trajectory_command_hashes == tuple(
        command.command_sha256 for command in evidence.ordered_commands
    )
    assert evidence.context_sha256 == canonical_record_sha256(evidence.to_dict())
    with pytest.raises(AuthorizationV2Error):
        replace(
            evidence,
            collision=replace(
                evidence.collision,
                cleared_trajectory_sha256=trajectory_sequence_sha256(
                    reordered_commands
                ),
            ),
            ordered_commands=reordered_commands,
        )


def test_collision_report_must_clear_exact_ordered_trajectory() -> None:
    evidence = _evidence()
    with pytest.raises(AuthorizationV2Error, match="ordered trajectory"):
        replace(
            evidence,
            collision=replace(
                evidence.collision,
                cleared_trajectory_sha256=_hash("another trajectory"),
            ),
        )
    with pytest.raises(AuthorizationV2Error, match="not clear"):
        replace(
            evidence,
            collision=replace(
                evidence.collision,
                state=CollisionClearanceState.BLOCKED,
            ),
        )


def test_commands_must_cover_unique_contiguous_ordered_occurrences() -> None:
    evidence = _evidence(action_count=2, commands_per_action=2)
    duplicate = replace(
        evidence.ordered_commands[1],
        command_occurrence_id=evidence.ordered_commands[0].command_occurrence_id,
    )
    commands = (
        evidence.ordered_commands[0],
        duplicate,
        *evidence.ordered_commands[2:],
    )
    with pytest.raises(AuthorizationV2Error, match="command occurrence IDs"):
        replace(
            evidence,
            ordered_commands=commands,
            collision=replace(
                evidence.collision,
                cleared_trajectory_sha256=trajectory_sequence_sha256(commands),
            ),
        )

    interleaved = (
        evidence.ordered_commands[0],
        evidence.ordered_commands[2],
        evidence.ordered_commands[1],
        evidence.ordered_commands[3],
    )
    with pytest.raises(AuthorizationV2Error, match="contiguous"):
        replace(
            evidence,
            ordered_commands=interleaved,
            collision=replace(
                evidence.collision,
                cleared_trajectory_sha256=trajectory_sequence_sha256(interleaved),
            ),
        )


def test_permit_consumes_only_next_exact_command() -> None:
    evidence = _evidence()
    permit = _issue(evidence)
    continuity = continuity_from_authorization(evidence)
    first = evidence.ordered_commands[0]

    receipt = permit.consume_next(
        ordinal=0,
        action_occurrence_id=first.action_occurrence_id,
        command=first,
        continuity=continuity,
        now_monotonic=100.1,
    )

    assert receipt.ordinal == 0
    assert receipt.command_sha256 == first.command_sha256
    assert receipt.authority == ZERO_AUTHORITY
    assert receipt.to_dict()["live_transport_authorized"] is False
    assert receipt.to_dict()["hardware_commands_generated"] == 0
    assert permit.next_ordinal == 1
    assert permit.remaining_commands == 1

    refreshed = continuity_from_authorization(
        evidence, interlocks=_interlocks(captured=100.15, sequence=8)
    )
    second = evidence.ordered_commands[1]
    permit.consume_next(
        ordinal=1,
        action_occurrence_id=second.action_occurrence_id,
        command=second,
        continuity=refreshed,
        now_monotonic=100.2,
    )
    assert permit.complete
    assert permit.next_ordinal is None
    assert permit.remaining_commands == 0
    with pytest.raises(AuthorizationV2Error, match="exhausted"):
        permit.consume_next(
            ordinal=1,
            action_occurrence_id=second.action_occurrence_id,
            command=second,
            continuity=refreshed,
            now_monotonic=100.3,
        )


@pytest.mark.parametrize("failure", ["skip", "action", "mutation"])
def test_skip_reorder_and_mutation_fail_closed(failure: str) -> None:
    evidence = _evidence()
    permit = _issue(evidence)
    expected = evidence.ordered_commands[0]
    ordinal = 1 if failure == "skip" else 0
    action = (
        evidence.ordered_action_occurrence_ids[1]
        if failure == "action"
        else expected.action_occurrence_id
    )
    command = (
        replace(expected, target_state_sha256=_hash("mutated target"))
        if failure == "mutation"
        else expected
    )

    with pytest.raises(AuthorizationV2Error):
        permit.consume_next(
            ordinal=ordinal,
            action_occurrence_id=action,
            command=command,
            continuity=continuity_from_authorization(evidence),
            now_monotonic=100.1,
        )
    assert permit.revoked
    assert permit.remaining_commands == 2


def test_interlock_samples_are_fresh_source_bound_and_advance_per_command() -> None:
    evidence = _evidence()
    permit = _issue(evidence)
    first = evidence.ordered_commands[0]
    permit.consume_next(
        ordinal=0,
        action_occurrence_id=first.action_occurrence_id,
        command=first,
        continuity=continuity_from_authorization(evidence),
        now_monotonic=100.1,
    )
    second = evidence.ordered_commands[1]
    with pytest.raises(AuthorizationV2Error, match="sequence did not advance"):
        permit.consume_next(
            ordinal=1,
            action_occurrence_id=second.action_occurrence_id,
            command=second,
            continuity=continuity_from_authorization(evidence),
            now_monotonic=100.2,
        )
    assert permit.revoked

    for replacement, match in (
        (_interlocks(captured=99.0, sequence=8), "stale"),
        (_interlocks(captured=100.3, sequence=8), "future-dated"),
        (_interlocks(captured=100.1, sequence=8, source_suffix="-new"), "source"),
        (
            _interlocks(
                captured=100.1,
                sequence=8,
                state=InterlockEvidenceState.FAIL,
            ),
            "not PASS",
        ),
    ):
        fresh_permit = _issue(evidence)
        with pytest.raises(AuthorizationV2Error, match=match):
            fresh_permit.consume_next(
                ordinal=0,
                action_occurrence_id=first.action_occurrence_id,
                command=first,
                continuity=continuity_from_authorization(
                    evidence, interlocks=replacement
                ),
                now_monotonic=100.2,
            )
        assert fresh_permit.revoked


def test_interlock_samples_cannot_roll_back_or_reuse_raw_evidence() -> None:
    evidence = _evidence()
    first = evidence.ordered_commands[0]
    baseline = evidence.interlocks

    rollback = _interlocks(captured=100.0, sequence=6)
    permit = _issue(evidence)
    with pytest.raises(AuthorizationV2Error, match="rolled back"):
        permit.consume_next(
            ordinal=0,
            action_occurrence_id=first.action_occurrence_id,
            command=first,
            continuity=continuity_from_authorization(
                evidence, interlocks=rollback
            ),
            now_monotonic=100.1,
        )

    reused_sequence = _interlocks(captured=100.0, sequence=7)
    permit = _issue(evidence)
    with pytest.raises(AuthorizationV2Error, match="reused a sequence"):
        permit.consume_next(
            ordinal=0,
            action_occurrence_id=first.action_occurrence_id,
            command=first,
            continuity=continuity_from_authorization(
                evidence, interlocks=reused_sequence
            ),
            now_monotonic=100.1,
        )

    changed_sequence_same_raw = InterlockEvidenceBundle(
        tuple(
            replace(
                channel,
                sequence=8,
                captured_monotonic=100.0,
            )
            for channel in baseline.channels
        )
    )
    permit = _issue(evidence)
    with pytest.raises(AuthorizationV2Error, match="new raw sample"):
        permit.consume_next(
            ordinal=0,
            action_occurrence_id=first.action_occurrence_id,
            command=first,
            continuity=continuity_from_authorization(
                evidence, interlocks=changed_sequence_same_raw
            ),
            now_monotonic=100.1,
        )


def test_issuance_rejects_stale_failed_and_future_interlocks() -> None:
    with pytest.raises(AuthorizationV2Error, match="stale"):
        _issue(_evidence(interlocks=_interlocks(captured=98.0)))
    with pytest.raises(AuthorizationV2Error, match="not PASS"):
        _issue(
            _evidence(
                interlocks=_interlocks(state=InterlockEvidenceState.UNKNOWN)
            )
        )
    with pytest.raises(AuthorizationV2Error, match="future-dated"):
        _issue(_evidence(interlocks=_interlocks(captured=100.1)))


@pytest.mark.parametrize(
    ("field", "replacement", "match"),
    (
        ("controller", _controller(session="connection-session-drifted"), "controller"),
        ("controller", _controller(port="different-persistent-port"), "controller"),
        ("build_release", _build_release(active_build_id="different-build"), "build"),
        ("calibration_closure_sha256", _hash("other calibration"), "calibration"),
        ("collision_report_sha256", _hash("other report"), "collision report"),
        ("trajectory_sha256", _hash("other trajectory"), "trajectory"),
        ("device_state_sha256", _hash("other device state"), "device state"),
        ("operator_nonce_sha256", _hash("other nonce"), "nonce"),
        ("plan_sha256", _hash("other plan"), "plan"),
    ),
)
def test_consumption_rejects_every_bound_identity_drift(
    field: str, replacement: object, match: str
) -> None:
    evidence = _evidence(action_count=1)
    permit = _issue(evidence)
    continuity = replace(
        continuity_from_authorization(evidence), **{field: replacement}
    )
    command = evidence.ordered_commands[0]
    with pytest.raises(AuthorizationV2Error, match=match):
        permit.consume_next(
            ordinal=0,
            action_occurrence_id=command.action_occurrence_id,
            command=command,
            continuity=continuity,
            now_monotonic=100.1,
        )
    assert permit.revoked


def test_expiry_is_capped_by_operator_arm_and_is_fail_closed() -> None:
    evidence = replace(
        _evidence(action_count=1),
        operator_arm=OperatorArmEvidence(
            operator_id="operator-local-0001",
            nonce_sha256=_hash("short operator arm"),
            armed_at_monotonic=99.0,
            expires_at_monotonic=100.25,
        ),
    )
    permit = issue_ordered_simulation_permit(
        evidence, ttl_s=30.0, now_monotonic=100.0
    )
    command = evidence.ordered_commands[0]
    with pytest.raises(AuthorizationV2Error, match="expired"):
        permit.consume_next(
            ordinal=0,
            action_occurrence_id=command.action_occurrence_id,
            command=command,
            continuity=continuity_from_authorization(evidence),
            now_monotonic=100.25,
        )
    assert permit.revoked


def test_only_one_thread_can_consume_a_command_occurrence() -> None:
    evidence = _evidence(action_count=1)
    permit = _issue(evidence)
    command = evidence.ordered_commands[0]
    continuity = continuity_from_authorization(evidence)

    def consume() -> bool:
        try:
            permit.consume_next(
                ordinal=0,
                action_occurrence_id=command.action_occurrence_id,
                command=command,
                continuity=continuity,
                now_monotonic=100.1,
            )
        except AuthorizationV2Error:
            return False
        return True

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = tuple(executor.map(lambda _: consume(), range(64)))
    assert sum(results) == 1
    assert permit.complete
    assert permit.remaining_commands == 0


def test_validated_cursor_and_receipt_constructors_resist_forgery() -> None:
    evidence = _evidence(action_count=1)
    with pytest.raises(AuthorizationV2Error, match="only be issued"):
        OrderedSimulationPermit(
            _issuer=object(),
            evidence=evidence,
            issued_at_monotonic=100.0,
            expires_at_monotonic=101.0,
            interlock_max_age_s=0.5,
        )
    with pytest.raises(AuthorizationV2Error, match="only be issued"):
        SimulationCommandReceipt(
            permit_id=_hash("permit"),
            context_sha256=_hash("context"),
            ordinal=0,
            action_occurrence_id=_hash("action"),
            command_sha256=_hash("command"),
            consumed_at_monotonic=100.0,
        )


def test_cursor_rejects_ordinary_state_mutation_copy_and_serialization() -> None:
    evidence = _evidence(action_count=1)
    permit = _issue(evidence)

    for name, value in (
        ("_cursor", 1),
        ("_revoked", True),
        ("_complete", True),
        ("_expires_at_monotonic", 1.0e9),
        ("_bound_plan_sha256", _hash("forged plan")),
    ):
        with pytest.raises(AuthorizationV2Error, match="internally sealed"):
            setattr(permit, name, value)
    with pytest.raises(TypeError):
        permit._last_interlock_sequences[InterlockChannel.ESTOP_CHAIN] = 999  # type: ignore[index]
    with pytest.raises(AuthorizationV2Error, match="cannot be copied"):
        copy.copy(permit)
    with pytest.raises(AuthorizationV2Error, match="cannot be copied"):
        copy.deepcopy(permit)
    with pytest.raises(AuthorizationV2Error, match="cannot be serialized"):
        pickle.dumps(permit)
    assert permit.next_ordinal == 0
    assert not permit.revoked


def test_genuine_receipt_cannot_be_replaced_or_serialized_after_mutation() -> None:
    evidence = _evidence(action_count=1)
    permit = _issue(evidence)
    command = evidence.ordered_commands[0]
    receipt = permit.consume_next(
        ordinal=0,
        action_occurrence_id=command.action_occurrence_id,
        command=command,
        continuity=continuity_from_authorization(evidence),
        now_monotonic=100.1,
    )
    for changes in (
        {"ordinal": 999},
        {"context_sha256": _hash("forged context")},
        {"authority": "LIVE"},
        {"schema": "forged"},
        {"consumed_at_monotonic": -5.0},
    ):
        with pytest.raises(AuthorizationV2Error, match="only be issued"):
            replace(receipt, **changes)

    object.__setattr__(receipt, "authority", "LIVE")
    with pytest.raises(AuthorizationV2Error, match="authority changed"):
        receipt.to_dict()


def test_huge_numeric_time_revokes_instead_of_escaping_validation() -> None:
    evidence = _evidence(action_count=1)
    permit = _issue(evidence)
    command = evidence.ordered_commands[0]
    with pytest.raises(AuthorizationV2Error, match="invalid consumption evidence"):
        permit.consume_next(
            ordinal=0,
            action_occurrence_id=command.action_occurrence_id,
            command=command,
            continuity=continuity_from_authorization(evidence),
            now_monotonic=10**10_000,
        )
    assert permit.revoked
    assert permit.next_ordinal == 0


def test_issuance_revalidates_records_if_constructor_was_bypassed() -> None:
    evidence = _evidence(action_count=1)
    object.__setattr__(evidence.controller, "persistent_port_id", "")
    with pytest.raises(AuthorizationV2Error, match="persistent_port_id"):
        _issue(evidence)


def test_cursor_is_structurally_incompatible_with_live_transport() -> None:
    evidence = _evidence(action_count=1)
    permit = _issue(evidence)
    command = evidence.ordered_commands[0]

    assert not callable(permit)
    assert permit.can_authorize_live_transport is False
    assert permit.authority == ZERO_AUTHORITY
    assert not hasattr(permit, "allows")
    assert not hasattr(permit, "to_message")
    assert not hasattr(command, "to_message")
    assert all("104" not in primitive.value for primitive in SimulationPrimitive)


def test_strict_finite_bounded_and_lowercase_validation() -> None:
    channel = _interlocks().channels[0]
    with pytest.raises(AuthorizationV2Error, match="finite"):
        replace(channel, captured_monotonic=math.inf)
    with pytest.raises(TypeError, match="non-boolean"):
        replace(channel, sequence=True)  # type: ignore[arg-type]
    with pytest.raises(AuthorizationV2Error, match="lowercase hexadecimal"):
        replace(channel, raw_sha256="A" * 64)
    with pytest.raises(AuthorizationV2Error, match="control"):
        replace(channel, source_id="unsafe\nsource")
    with pytest.raises(TypeError, match="tuple"):
        InterlockEvidenceBundle(list(_interlocks().channels))  # type: ignore[arg-type]


def test_invalid_timing_inputs_do_not_issue() -> None:
    evidence = _evidence(action_count=1)
    for kwargs in (
        {"ttl_s": 0.0, "now_monotonic": 100.0},
        {"ttl_s": math.inf, "now_monotonic": 100.0},
        {"ttl_s": 1.0, "now_monotonic": math.nan},
        {"ttl_s": True, "now_monotonic": 100.0},
    ):
        with pytest.raises((AuthorizationV2Error, TypeError)):
            issue_ordered_simulation_permit(evidence, **kwargs)  # type: ignore[arg-type]

    with pytest.raises(AuthorizationV2Error, match="ttl_s exceeds"):
        issue_ordered_simulation_permit(
            evidence, ttl_s=30.1, now_monotonic=100.0
        )
    with pytest.raises(AuthorizationV2Error, match="interlock_max_age_s exceeds"):
        issue_ordered_simulation_permit(
            evidence,
            ttl_s=1.0,
            now_monotonic=100.0,
            interlock_max_age_s=5.1,
        )


def test_operator_arm_window_is_bounded() -> None:
    with pytest.raises(AuthorizationV2Error, match="window exceeds"):
        OperatorArmEvidence(
            operator_id="operator-local-0001",
            nonce_sha256=_hash("overlong nonce"),
            armed_at_monotonic=1.0,
            expires_at_monotonic=61.1,
        )


def test_revoke_prevents_consumption_without_advancing() -> None:
    evidence = _evidence(action_count=1)
    permit = _issue(evidence)
    permit.revoke()
    command = evidence.ordered_commands[0]
    with pytest.raises(AuthorizationV2Error, match="revoked"):
        permit.consume_next(
            ordinal=0,
            action_occurrence_id=command.action_occurrence_id,
            command=command,
            continuity=continuity_from_authorization(evidence),
            now_monotonic=100.1,
        )
    assert permit.remaining_commands == 1


def test_continuity_record_requires_full_hash_bound_evidence() -> None:
    evidence = _evidence(action_count=1)
    continuity = continuity_from_authorization(evidence)
    assert isinstance(continuity, AuthorizationContinuityEvidence)
    assert continuity.controller.connection_session_id == (
        evidence.controller.connection_session_id
    )
    assert continuity.controller.persistent_port_id == evidence.controller.persistent_port_id
    assert continuity.calibration_closure_sha256 == evidence.calibration.closure_sha256
    assert continuity.trajectory_sha256 == evidence.collision.cleared_trajectory_sha256
