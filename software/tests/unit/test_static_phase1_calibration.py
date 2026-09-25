from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocell.application import (
    build_static_phase1_synthetic_closure,
    run_static_phase1_calibration_rehearsal,
    static_phase1_context_hashes,
)
from rocell.application.context import load_simulation_context
from rocell.application.static_phase1_calibration import (
    StaticPhase1CalibrationError,
    StaticPhase1StalenessProbe,
)
from rocell.calibration import (
    REQUIREMENTS,
    STATIC_OVERHEAD_PHASE1_AUTHORITY,
    STATIC_OVERHEAD_PHASE1_GRAPH,
    STATIC_OVERHEAD_PHASE1_GRAPH_ID,
    STATIC_OVERHEAD_PHASE1_GRAPH_SCHEMA,
    STATIC_OVERHEAD_PHASE1_REQUIREMENTS,
    ArtifactState,
    StaticPhase1CalibrationGraph,
    StaticPhase1CalibrationRequirement,
    StaticPhase1RequirementError,
    ordered_static_phase1_requirement_closure,
)


WORKSPACE = Path(__file__).resolve().parents[3]
MANIFEST = WORKSPACE / "software/config/system_manifest.json"


@pytest.fixture(scope="module")
def simulation_context():  # type: ignore[no-untyped-def]
    return load_simulation_context(WORKSPACE, MANIFEST)


@pytest.fixture(scope="module")
def context_hashes(simulation_context):  # type: ignore[no-untyped-def]
    return static_phase1_context_hashes(simulation_context)


@pytest.fixture(scope="module")
def synthetic_closure(context_hashes):  # type: ignore[no-untyped-def]
    return build_static_phase1_synthetic_closure(context_hashes)


def _registry_bytes() -> dict[str, bytes]:
    root = WORKSPACE / "software/calibrations"
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_static_graph_is_additive_and_keeps_historical_eye_on_arm_ids() -> None:
    # These are the historical Freeze-009 IDs.  The static graph must never
    # silently reinterpret them because old evidence refers to their original
    # eye-on-arm meanings.
    assert tuple(REQUIREMENTS) == (
        "camera_intrinsics",
        "measured_tag_map",
        "robot_reference",
        "eye_on_arm_extrinsic",
        "arm_board",
        "controller_correlation",
        "keyboard_pose",
        "keyboard_tcp",
        "keyboard_outcome_observer",
        "phone_screen",
        "phone_tcp",
        "phone_ui_observer",
    )
    assert REQUIREMENTS["eye_on_arm_extrinsic"].purpose.startswith("Solve link2")
    assert set(REQUIREMENTS).isdisjoint(STATIC_OVERHEAD_PHASE1_REQUIREMENTS)
    assert STATIC_OVERHEAD_PHASE1_GRAPH_ID.endswith(".v1")
    assert STATIC_OVERHEAD_PHASE1_GRAPH_SCHEMA.endswith(".v1")
    assert STATIC_OVERHEAD_PHASE1_AUTHORITY == (
        "SIMULATION_ONLY_ZERO_PHYSICAL_AUTHORITY"
    )


def test_graph_has_complete_b0477_keyboard_and_phone_requirements() -> None:
    graph = STATIC_OVERHEAD_PHASE1_GRAPH
    assert len(graph.requirements) == 15
    assert graph.ordered_requirements == tuple(graph.requirements)
    assert set(graph.requirements) == {
        "phase1_b0477_identity",
        "phase1_b0477_mode",
        "phase1_b0477_settings",
        "phase1_static_intrinsics",
        "phase1_measured_tag_map",
        "phase1_static_extrinsic",
        "phase1_robot_reference",
        "phase1_controller_correlation",
        "phase1_arm_board",
        "phase1_keyboard_target_map",
        "phase1_keyboard_tcp",
        "phase1_keyboard_outcome_observer",
        "phase1_phone_target_map",
        "phase1_phone_tcp",
        "phase1_phone_outcome_observer",
    }
    assert graph.device_terminals == {
        "keyboard": ("phase1_keyboard_tcp", "phase1_keyboard_outcome_observer"),
        "phone": ("phase1_phone_tcp", "phase1_phone_outcome_observer"),
    }
    assert len(graph.graph_hash) == 64
    assert graph.graph_hash == STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash


@pytest.mark.parametrize("device", ["keyboard", "phone"])
def test_device_closure_is_complete_and_prerequisite_first(device: str) -> None:
    graph = STATIC_OVERHEAD_PHASE1_GRAPH
    closure = graph.device_closure(device)
    assert len(closure) == 12
    for child in closure:
        for parent in graph.requirements[child].prerequisites:
            assert closure.index(parent) < closure.index(child)
    assert "phase1_b0477_identity" in closure
    assert "phase1_b0477_mode" in closure
    assert "phase1_b0477_settings" in closure
    assert "phase1_static_intrinsics" in closure
    assert "phase1_measured_tag_map" in closure
    assert "phase1_static_extrinsic" in closure
    assert "phase1_robot_reference" in closure
    assert "phase1_controller_correlation" in closure
    assert "phase1_arm_board" in closure
    assert f"phase1_{device}_target_map" in closure
    assert f"phase1_{device}_tcp" in closure
    assert f"phase1_{device}_outcome_observer" in closure
    other = "phone" if device == "keyboard" else "keyboard"
    assert not any(item.startswith(f"phase1_{other}_") for item in closure)


def test_selected_graph_convenience_closure_rejects_unknown() -> None:
    assert ordered_static_phase1_requirement_closure(
        ("phase1_phone_tcp",)
    ) == STATIC_OVERHEAD_PHASE1_GRAPH.ordered_closure(("phase1_phone_tcp",))
    with pytest.raises(StaticPhase1RequirementError, match="Unknown"):
        ordered_static_phase1_requirement_closure(("not_a_requirement",))
    with pytest.raises(StaticPhase1RequirementError, match="Unsupported"):
        STATIC_OVERHEAD_PHASE1_GRAPH.device_closure("tablet")


def test_graph_model_rejects_cycle_and_unknown_parent() -> None:
    def requirement(
        artifact_id: str, prerequisites: tuple[str, ...]
    ) -> StaticPhase1CalibrationRequirement:
        return StaticPhase1CalibrationRequirement(
            artifact_id=artifact_id,
            artifact_schema=f"rocell.{artifact_id}.v1",
            prerequisites=prerequisites,
            context_dependencies=(),
            purpose="test purpose",
            acceptance_evidence="test evidence",
        )

    with pytest.raises(StaticPhase1RequirementError, match="unknown prerequisite"):
        StaticPhase1CalibrationGraph(
            requirements={"a": requirement("a", ("missing",))},
            device_terminals={"keyboard": ("a",), "phone": ("a",)},
        )
    with pytest.raises(StaticPhase1RequirementError, match="cycle"):
        StaticPhase1CalibrationGraph(
            requirements={
                "a": requirement("a", ("b",)),
                "b": requirement("b", ("a",)),
            },
            device_terminals={"keyboard": ("a",), "phone": ("b",)},
        )


def test_static_context_hashes_cover_exact_declared_sources(context_hashes) -> None:  # type: ignore[no-untyped-def]
    assert tuple(context_hashes) == STATIC_OVERHEAD_PHASE1_GRAPH.required_context_hash_ids
    assert all(len(value) == 64 and value == value.lower() for value in context_hashes.values())
    with pytest.raises(TypeError, match="SimulationContext"):
        static_phase1_context_hashes(object())  # type: ignore[arg-type]


def test_synthetic_artifacts_are_nominal_only_and_bind_every_direct_parent(
    synthetic_closure,  # type: ignore[no-untyped-def]
) -> None:
    graph = STATIC_OVERHEAD_PHASE1_GRAPH
    artifacts = {row.artifact_id: row for row in synthetic_closure.artifacts}
    assert tuple(artifacts) == graph.ordered_requirements
    assert all(row.state is ArtifactState.NOMINAL_ONLY for row in artifacts.values())
    assert all(row.version == 1 for row in artifacts.values())
    assert all(row.payload["synthetic"] is True for row in artifacts.values())
    assert all(
        row.payload["physical_measurements_present"] is False
        for row in artifacts.values()
    )
    assert all(row.payload["execution_authorized"] is False for row in artifacts.values())
    for artifact_id, artifact in artifacts.items():
        requirement = graph.requirements[artifact_id]
        assert set(artifact.parent_artifact_hashes) == set(requirement.prerequisites)
        assert artifact.parent_artifact_hashes == {
            parent: artifacts[parent].content_hash
            for parent in requirement.prerequisites
        }
        assert set(artifact.dependency_hashes) == {
            "static_phase1_requirement_graph",
            *requirement.context_dependencies,
        }


def test_synthetic_baseline_is_coherent_but_cannot_be_physical_validation(
    synthetic_closure,  # type: ignore[no-untyped-def]
) -> None:
    assert synthetic_closure.baseline_parent_bindings_coherent is True
    assert synthetic_closure.simulation_graph_verified is True
    assert all(row.valid is False for row in synthetic_closure.baseline_assessments)
    assert all(
        row.reasons
        == (f"CALIBRATION_STATE:{row.artifact_id}:NOMINAL_ONLY",)
        for row in synthetic_closure.baseline_assessments
    )
    document = synthetic_closure.to_dict()
    assert document["physical_artifacts_created"] is False
    assert document["physical_registry_written"] is False
    assert document["hardware_accessed"] is False
    assert document["robot_commands_sent"] == 0
    assert document["execution_authorized"] is False
    assert document["physical_release_effect"] == "NONE"


def test_every_parent_and_context_edge_detects_exact_staleness(
    synthetic_closure,  # type: ignore[no-untyped-def]
) -> None:
    graph = STATIC_OVERHEAD_PHASE1_GRAPH
    parent_probes = {
        (probe.upstream_id, probe.downstream_id): probe
        for probe in synthetic_closure.staleness_probes
        if probe.edge_kind == "PARENT_ARTIFACT"
    }
    assert set(parent_probes) == set(graph.parent_edges)

    expected_context_edges = {
        ("static_phase1_requirement_graph", artifact_id)
        for artifact_id in graph.ordered_requirements
    }
    expected_context_edges.update(
        (dependency, artifact_id)
        for artifact_id in graph.ordered_requirements
        for dependency in graph.requirements[artifact_id].context_dependencies
    )
    context_probes = {
        (probe.upstream_id, probe.downstream_id): probe
        for probe in synthetic_closure.staleness_probes
        if probe.edge_kind == "CONTEXT_SOURCE"
    }
    assert set(context_probes) == expected_context_edges
    assert len(parent_probes) == 27
    assert len(context_probes) == 41
    assert len(synthetic_closure.staleness_probes) == 68
    assert synthetic_closure.all_edges_exercised is True
    assert all(probe.detected for probe in synthetic_closure.staleness_probes)
    assert all(
        probe.observed_stale_reasons == (probe.expected_reason,)
        for probe in synthetic_closure.staleness_probes
    )


def test_retained_optical_stack_directly_invalidates_settings_and_intrinsics() -> None:
    graph = STATIC_OVERHEAD_PHASE1_GRAPH
    for artifact_id in ("phase1_b0477_settings", "phase1_static_intrinsics"):
        dependencies = set(graph.requirements[artifact_id].context_dependencies)
        assert "camera_architecture_plan" in dependencies
        assert "static_camera_support" in dependencies


def test_synthetic_builder_rejects_missing_extra_and_malformed_hashes(
    context_hashes,  # type: ignore[no-untyped-def]
) -> None:
    missing = dict(context_hashes)
    missing.pop(next(iter(missing)))
    with pytest.raises(StaticPhase1CalibrationError, match="missing"):
        build_static_phase1_synthetic_closure(missing)

    extra = {**context_hashes, "unbound_source": "a" * 64}
    with pytest.raises(StaticPhase1CalibrationError, match="unexpected"):
        build_static_phase1_synthetic_closure(extra)

    malformed = dict(context_hashes)
    malformed[next(iter(malformed))] = "NOT_A_HASH"
    with pytest.raises(StaticPhase1CalibrationError, match="SHA-256"):
        build_static_phase1_synthetic_closure(malformed)


def test_probe_model_rejects_a_false_detected_claim() -> None:
    with pytest.raises(StaticPhase1CalibrationError, match="detected flag"):
        StaticPhase1StalenessProbe(
            edge_kind="PARENT_ARTIFACT",
            upstream_id="a",
            downstream_id="b",
            expected_reason="STALE_PARENT_CALIBRATION:b:a",
            observed_stale_reasons=(),
            detected=True,
        )


def test_root_rehearsal_keeps_current_physical_registry_blocked_and_unchanged(
    simulation_context,  # type: ignore[no-untyped-def]
) -> None:
    before = _registry_bytes()
    index = WORKSPACE / "software/calibrations/index.json"
    index_existed = index.exists()

    report = run_static_phase1_calibration_rehearsal(simulation_context)

    assert _registry_bytes() == before
    assert index.exists() is index_existed
    assert report.status == (
        "SYNTHETIC_PHASE1_GRAPH_VERIFIED_PHYSICAL_REGISTRY_BLOCKED"
    )
    assert report.physical_registry_blocked is True
    assert report.physical_artifacts_all_valid is False
    assert len(report.physical_assessments) == 15
    assert all(row.state is ArtifactState.MISSING for row in report.physical_assessments)
    assert [row.device for row in report.device_closures] == ["keyboard", "phone"]
    assert all(len(row.ordered_requirements) == 12 for row in report.device_closures)
    assert all(row.physical_artifacts_all_valid is False for row in report.device_closures)
    assert report.synthetic.simulation_graph_verified is True

    document = report.to_dict()
    assert document["physical_registry"]["blocked"] is True
    assert document["physical_registry"]["read_only"] is True
    assert document["physical_registry"]["written"] is False
    assert len(document["physical_registry"]["missing_artifact_ids"]) == 15
    assert document["historical_eye_on_arm_requirement_graph_modified"] is False
    assert document["historical_calibration_registry_modified"] is False
    assert document["hardware_accessed"] is False
    assert document["robot_commands_sent"] == 0
    assert document["camera_frames_captured"] == 0
    assert document["power_authorized"] is False
    assert document["motion_authorized"] is False
    assert document["contact_authorized"] is False
    assert document["physical_release_effect"] == "NONE"
    json.dumps(document, sort_keys=True, allow_nan=False)


def test_root_rehearsal_is_deterministic(simulation_context) -> None:  # type: ignore[no-untyped-def]
    first = run_static_phase1_calibration_rehearsal(simulation_context)
    second = run_static_phase1_calibration_rehearsal(simulation_context)
    assert first == second
    assert first.report_hash == second.report_hash
