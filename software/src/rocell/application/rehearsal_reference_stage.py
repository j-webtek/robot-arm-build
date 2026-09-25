"""Source-bound nominal reference mathematics, never installed calibration.

Evaluation invokes the actual graph registry, URDF FK and correspondence fitter.
Retained verification only checks their complete evidence and equations: no
registry lookup, FK evaluator, SVD fit, device/provider, publication or command.
The caller authenticates the exact predecessor binding and expected byte hash.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, NoReturn, cast

from rocell.application.context import load_simulation_context
from rocell.application._pinned_model import load_pinned_urdf
from rocell.application.rehearsal_reference_binding import RehearsalReferenceBinding
from rocell.application.static_phase1_calibration import (
    STATIC_PHASE1_SYNTHETIC_BUILD_ID,
    STATIC_PHASE1_SYNTHETIC_MANIFEST_ID,
    run_static_phase1_calibration_rehearsal,
    static_phase1_context_hashes,
)
from rocell.calibration.artifacts import (
    ArtifactAssessment,
    ArtifactState,
    CalibrationArtifact,
)
from rocell.calibration.static_phase1_requirements import (
    STATIC_OVERHEAD_PHASE1_AUTHORITY,
    STATIC_OVERHEAD_PHASE1_GRAPH,
)
from rocell.calibration.rigid_correspondence import (
    CorrespondenceOrigin,
    DEFAULT_RIGID_CORRESPONDENCE_POLICY,
    RigidCorrespondenceInput,
    RigidPointPair,
    fit_rigid_correspondence,
    verify_rigid_correspondence_result,
)
from rocell.geometry import (
    JointPosition,
    Point3Mm,
    RigidTransform,
    Rotation3,
    UrdfModel,
    Vec3,
)


SCHEMA = "rocell.rehearsal_reference_stage.v1"
MAX_EVIDENCE_BYTES = 112 * 1024
_STAGE = "reference_frame_calibration"
_GRAPH_CONTEXT = "static_phase1_requirement_graph"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_JOINTS = (
    "base_link_to_link1",
    "link1_to_link2",
    "link2_to_link3",
    "link3_to_link4",
    "link4_to_link5",
    "link5_to_gripper_link",
)
# Distinct, bounded, nominal poses. They are neither a route nor startup states.
_OFFSETS = (
    (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    (0.35, 0.2, -0.2, 0.0, 0.0, 0.0),
    (-0.4, -0.15, -0.45, 0.1, 0.0, 0.0),
    (0.15, 0.3, -0.8, 0.1, 0.0, 0.0),
    (-0.2, 0.1, -0.35, -0.1, 0.0, 0.0),
    (0.25, -0.2, -0.6, 0.2, 0.0, 0.0),
)
_PENDING = (
    "bootstrap_phase_receipt",
    "reference_characterization_phase_receipt",
    "arm_to_board_transform",
    "controller_model_correlation",
    "free_state_tool_tcp",
    "keyboard_target_map",
    "phone_target_map",
    "outcome_observer_candidates",
)
_EFFECTS = {
    name: 0
    for name in (
        "device_enumerations",
        "device_opens",
        "camera_frames_captured",
        "hardware_commands",
        "power_events",
        "motion_commands",
        "contact_commands",
        "calibration_artifacts_published",
        "physical_receipts_published",
        "permits_published",
    )
}
_PROVENANCE = {
    "origin": "SYNTHETIC_REHEARSAL_ONLY",
    "graph": "ACTUAL_STATIC_PHASE1_REGISTRY_NOMINAL_GRAPH_AND_EDGE_INVALIDATION",
    "numeric": "ACTUAL_PINNED_URDF_FK_AND_RIGID_CORRESPONDENCE_FIT",
    "board_transform": "SOURCE_NOMINAL_OVERLAY_NOT_MEASURED_ARM_BASE",
    "tool_tcp": "SOURCE_VIRTUAL_FREE_STATE_OFFSET_NOT_MEASURED_TCP",
    "joint_input": "PINNED_SCENARIO_AND_CLOSED_RADIAN_OFFSETS_NOT_T105",
    "camera": "REVIEWED_STAGE_6_7_8_DEPENDENCY_ONLY_NOT_NUMERIC_INPUT",
    "physical_components": "ALL_EIGHT_PENDING_SEPARATELY_RELEASED_NONCONTACT_INTAKE",
    "physical_observation": False,
}
_MEANING = (
    "Nominal graph and reference mathematics only. The fitted candidate uses truth-known "
    "synthetic correspondences, not received arm/camera measurements. All eight physical "
    "reference components remain pending; no motion, contact, calibration promotion or "
    "all-target/reachability acceptance is established."
)
_DEPENDENCY_MODULES = (
    "application/static_phase1_calibration.py",
    "calibration/static_phase1_requirements.py",
    "calibration/registry.py",
    "calibration/artifacts.py",
    "calibration/rigid_correspondence.py",
    "geometry/urdf.py",
    "geometry/transforms.py",
)


class RehearsalReferenceError(ValueError):
    """Missing, oversized, malformed or inconsistently bound nominal evidence."""


def _fail(message: str) -> NoReturn:
    raise RehearsalReferenceError(message)


def _object(value: object, keys: set[str] | None = None) -> dict[str, Any]:
    if type(value) is not dict or (keys is not None and set(value) != keys):
        _fail("reference object has missing or unknown fields")
    return value  # type: ignore[return-value]


def _tree(value: object, depth: int = 0) -> None:
    if depth > 16:
        _fail("reference evidence nesting exceeds its bound")
    if type(value) is dict:
        if len(value) > 128 or any(
            type(key) is not str or len(key) > 256 for key in value
        ):
            _fail("reference object count/keys exceed bounds")
        for item in value.values():
            _tree(item, depth + 1)
    elif type(value) is list:
        if len(value) > 128:
            _fail("reference array exceeds its bound")
        for item in value:
            _tree(item, depth + 1)
    elif type(value) is str:
        if len(value) > 4096:
            _fail("reference text exceeds its bound")
    elif type(value) in (int, float):
        numeric = cast(float, value)
        if not math.isfinite(numeric) or abs(numeric) > 1e15:
            _fail("reference number must be finite and bounded")
    elif value is not None and type(value) is not bool:
        _fail("reference report contains a non-JSON value")


def _canonical(value: object) -> bytes:
    _tree(value)
    result = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")
    if len(result) > MAX_EVIDENCE_BYTES:
        _fail("complete reference evidence exceeds 112 KiB; no truncation is permitted")
    return result


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _same(value: object, expected: object, label: str) -> None:
    if _canonical(value) != _canonical(expected):
        _fail(f"{label} differs from the exact retained contract")


def _digest(value: object) -> str:
    if type(value) is not str or not _HASH.fullmatch(value) or value == "0" * 64:
        _fail("a trusted nonzero SHA-256 digest is required")
    return value  # type: ignore[return-value]


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            _fail("duplicate reference JSON field")
        result[key] = value
    return result


def _decode(payload: bytes) -> dict[str, Any]:
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_EVIDENCE_BYTES:
        _fail("reference evidence must be nonempty bounded bytes")
    try:
        result = _object(json.loads(payload, object_pairs_hook=_pairs))
        if _canonical(result) != payload:
            _fail("reference evidence is not exact canonical JSON")
        return result
    except (
        ValueError,
        UnicodeError,
        TypeError,
        RecursionError,
        OverflowError,
    ) as error:
        if isinstance(error, RehearsalReferenceError):
            raise
        raise RehearsalReferenceError("invalid reference JSON") from error


def _transform(value: RigidTransform) -> dict[str, Any]:
    return {
        "parent_frame": value.parent_frame,
        "child_frame": value.child_frame,
        "matrix_mm": list(value.to_transform().matrix),
    }


def _from_transform(value: object) -> RigidTransform:
    item = _object(value, {"parent_frame", "child_frame", "matrix_mm"})
    matrix = item["matrix_mm"]
    if type(matrix) is not list or len(matrix) != 16:
        _fail("a complete row-major rigid transform is required")
    if matrix[12:] != [0.0, 0.0, 0.0, 1.0]:
        _fail("invalid rigid transform homogeneous row")
    return RigidTransform(
        item["parent_frame"],
        item["child_frame"],
        Rotation3(
            tuple(matrix[row * 4 + column] for row in range(3) for column in range(3))
        ),
        Vec3(matrix[3], matrix[7], matrix[11]),
    )


def _point(point: Point3Mm) -> dict[str, Any]:
    return {"frame": point.frame, "xyz_mm": [point.x, point.y, point.z]}


def _from_point(value: object) -> Point3Mm:
    item = _object(value, {"frame", "xyz_mm"})
    if type(item["xyz_mm"]) is not list or len(item["xyz_mm"]) != 3:
        _fail("a complete frame-labelled millimetre point is required")
    return Point3Mm(item["frame"], *item["xyz_mm"])


def _distance(left: Point3Mm, right: Point3Mm) -> float:
    if left.frame != right.frame:
        _fail("residual points must have the same frame")
    return math.sqrt(
        math.fsum(
            (a - b) ** 2
            for a, b in zip((left.x, left.y, left.z), (right.x, right.y, right.z))
        )
    )


def read_reference_source_context(workspace: Path) -> dict[str, Any]:
    """Read one revalidated, hash-pinned source snapshot; no FK or I/O provider."""
    root = Path(workspace).resolve()
    context = load_simulation_context(
        root, root / "software/config/system_manifest.json"
    )
    hashes = dict(static_phase1_context_hashes(context))
    loaded = load_pinned_urdf(
        context.scenario.model_path, context.scenario.model_sha256
    )
    # Retain XML for pure algebra verification. The separate bounded snapshot
    # must match the model just parsed; a changed path is never accepted.
    with context.scenario.model_path.open("rb") as stream:
        raw = stream.read(4097)
    if len(raw) > 4096 or hashlib.sha256(raw).hexdigest() != loaded.sha256:
        _fail("retained URDF snapshot differs from the exact pinned model")
    ready = {
        name: value.value
        for name, value in context.scenario.ready_arm_joint_positions_rad.items()
    }
    ready["link5_to_gripper_link"] = context.scenario.fixed_gripper_position.value
    if set(ready) != set(_JOINTS):
        _fail("source model differs from the closed six-joint fixture")
    selected = []
    for device, target_id, catalog in (
        ("keyboard", "A", context.targets.keyboard_targets),
        ("phone", "key_q", context.targets.phone_targets),
    ):
        target = catalog[target_id]
        selected.append(
            {
                "device": device,
                "target_id": target_id,
                "point": _point(target.center),
                "source_state": target.source_state,
                "catalog_total": len(catalog),
            }
        )
    geometry = {
        "schema": "rocell.nominal_reference_geometry.v1",
        "manifest_id": context.snapshot.manifest_id,
        "active_build_id": context.snapshot.active_build_id,
        "bundle_sha256": context.bundle_lock.source_lock_sha256,
        "scenario_sha256": context.scenario.source_profile_sha256,
        "urdf_xml": raw.decode("utf-8"),
        "urdf_sha256": loaded.sha256,
        "urdf_bytes": len(raw),
        "board_T_world": _transform(context.scenario.board_T_world),
        "board_transform_state": context.scenario.board_T_world_state,
        "tool_case_id": context.scenario.tool_case_id,
        "hand_T_tip": _transform(
            RigidTransform(
                "hand_tcp",
                "nominal_tip",
                Rotation3.identity(),
                Vec3(0.0, 0.0, context.scenario.hand_tcp_to_tip_z_mm),
            )
        ),
        "joint_order": list(_JOINTS),
        "joint_units": "radians",
        "ready_joint_positions_rad": [ready[name] for name in _JOINTS],
        "fixture_offsets_rad": [list(row) for row in _OFFSETS],
        "training_indices": [0, 1, 2, 3],
        "heldout_indices": [4, 5],
        "board_extent_mm": [
            context.scene.board.maximum.x,
            context.scene.board.maximum.y,
        ],
        "selected_targets": selected,
        "physical_measurements_present": False,
    }
    return {
        "schema": "rocell.rehearsal_reference_sources.v1",
        "static_phase1_graph_sha256": STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash,
        "static_phase1_context_hashes": hashes,
        "nominal_geometry": geometry,
    }


def _source_geometry(
    binding: RehearsalReferenceBinding,
) -> tuple[dict[str, Any], UrdfModel]:
    source = binding.source_context
    _same(
        source["static_phase1_graph_sha256"],
        STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash,
        "static graph identity",
    )
    if set(source["static_phase1_context_hashes"]) != set(
        STATIC_OVERHEAD_PHASE1_GRAPH.required_context_hash_ids
    ):
        _fail("source context must cover every declared static graph dependency")
    geometry = _object(
        source["nominal_geometry"],
        {
            "schema",
            "manifest_id",
            "active_build_id",
            "bundle_sha256",
            "scenario_sha256",
            "urdf_xml",
            "urdf_sha256",
            "urdf_bytes",
            "board_T_world",
            "board_transform_state",
            "tool_case_id",
            "hand_T_tip",
            "joint_order",
            "joint_units",
            "ready_joint_positions_rad",
            "fixture_offsets_rad",
            "training_indices",
            "heldout_indices",
            "board_extent_mm",
            "selected_targets",
            "physical_measurements_present",
        },
    )
    _same(geometry["schema"], "rocell.nominal_reference_geometry.v1", "geometry schema")
    _same(geometry["joint_order"], list(_JOINTS), "joint order")
    _same(geometry["joint_units"], "radians", "joint units")
    _same(
        geometry["fixture_offsets_rad"],
        [list(row) for row in _OFFSETS],
        "closed pose offsets",
    )
    _same(geometry["training_indices"], [0, 1, 2, 3], "training partition")
    _same(geometry["heldout_indices"], [4, 5], "heldout partition")
    _same(geometry["physical_measurements_present"], False, "nominal source authority")
    raw = geometry["urdf_xml"].encode("utf-8")
    if (
        len(raw) != geometry["urdf_bytes"]
        or hashlib.sha256(raw).hexdigest() != geometry["urdf_sha256"]
        or geometry["urdf_sha256"]
        != source["static_phase1_context_hashes"]["kinematic_model"]
    ):
        _fail("retained XML bytes differ from the pinned kinematic source")
    model = UrdfModel.from_xml(geometry["urdf_xml"], source_name="retained-pinned-URDF")
    if model.root_link != "world" or set(model.movable_joint_names) != set(_JOINTS):
        _fail("model frame/joint domain differs from nominal fixture")
    board = _from_transform(geometry["board_T_world"])
    tip = _from_transform(geometry["hand_T_tip"])
    if (board.parent_frame, board.child_frame, tip.parent_frame, tip.child_frame) != (
        "board",
        "world",
        "hand_tcp",
        "nominal_tip",
    ):
        _fail("board/world/hand/tip frames cannot be relabeled")
    if (
        type(geometry["ready_joint_positions_rad"]) is not list
        or len(geometry["ready_joint_positions_rad"]) != 6
    ):
        _fail("six typed source joint values are required")
    if (
        type(geometry["selected_targets"]) is not list
        or len(geometry["selected_targets"]) != 2
    ):
        _fail("exact keyboard and phone subset required")
    for row, expected in zip(
        geometry["selected_targets"], (("keyboard", "A", 46), ("phone", "key_q", 29))
    ):
        _object(row, {"device", "target_id", "point", "source_state", "catalog_total"})
        _same(
            [row["device"], row["target_id"], row["catalog_total"]],
            list(expected),
            "target coverage",
        )
        if (
            _from_point(row["point"]).frame != "board"
            or row["source_state"] != "SIMULATION_ONLY_NOMINAL_UNMEASURED"
        ):
            _fail("target data must remain nominal board coordinates")
    return geometry, model


def _check_graph(
    report: object, binding: RehearsalReferenceBinding
) -> tuple[bool, int]:
    """Check retained graph semantics without registry access or graph replay."""
    expected: Any
    graph = STATIC_OVERHEAD_PHASE1_GRAPH
    source = binding.source_context
    item = _object(
        report,
        {
            "schema",
            "status",
            "graph",
            "manifest_id",
            "active_build_id",
            "physical_registry",
            "device_closures",
            "synthetic_rehearsal",
            "historical_eye_on_arm_requirement_graph_modified",
            "historical_calibration_registry_modified",
            "hardware_accessed",
            "robot_commands_sent",
            "camera_frames_captured",
            "execution_authorized",
            "power_authorized",
            "motion_authorized",
            "contact_authorized",
            "physical_release_effect",
        },
    )
    _same(
        item["schema"],
        "rocell.static_phase1_calibration_rehearsal.v1",
        "graph report schema",
    )
    _same(
        item["graph"],
        {**graph.to_dict(), "graph_hash": graph.graph_hash},
        "complete graph",
    )
    for name in ("manifest_id", "active_build_id"):
        _same(item[name], source["nominal_geometry"][name], "graph build identity")
    for name in (
        "historical_eye_on_arm_requirement_graph_modified",
        "historical_calibration_registry_modified",
        "hardware_accessed",
        "execution_authorized",
        "power_authorized",
        "motion_authorized",
        "contact_authorized",
    ):
        _same(item[name], False, "graph non-authority")
    _same(item["robot_commands_sent"], 0, "graph command count")
    _same(item["camera_frames_captured"], 0, "graph frame count")
    _same(item["physical_release_effect"], "NONE", "graph release")
    synthetic = _object(
        item["synthetic_rehearsal"],
        {
            "status",
            "authority",
            "context_hashes",
            "artifacts",
            "baseline_parent_bindings_coherent",
            "staleness_probes",
            "all_edges_exercised",
            "simulation_graph_verified",
            "physical_artifacts_created",
            "physical_registry_written",
            "hardware_accessed",
            "robot_commands_sent",
            "execution_authorized",
            "physical_release_effect",
            "closure_hash",
        },
    )
    _same(
        synthetic["context_hashes"],
        source["static_phase1_context_hashes"],
        "graph context sources",
    )
    _same(synthetic["authority"], STATIC_OVERHEAD_PHASE1_AUTHORITY, "graph authority")
    expected_artifacts = []
    hashes: dict[str, str] = {}
    for artifact_id in graph.ordered_requirements:
        requirement = graph.requirements[artifact_id]
        dependencies = {
            _GRAPH_CONTEXT: graph.graph_hash,
            **{
                name: synthetic["context_hashes"][name]
                for name in requirement.context_dependencies
            },
        }
        parents = {name: hashes[name] for name in requirement.prerequisites}
        artifact = CalibrationArtifact(
            artifact_id,
            1,
            ArtifactState.NOMINAL_ONLY,
            "2000-01-01T00:00:00Z",
            STATIC_PHASE1_SYNTHETIC_MANIFEST_ID,
            STATIC_PHASE1_SYNTHETIC_BUILD_ID,
            dependencies,
            parents,
            {
                "requirement_artifact_schema": requirement.artifact_schema,
                "graph_id": graph.graph_id,
                "graph_hash": graph.graph_hash,
                "authority": STATIC_OVERHEAD_PHASE1_AUTHORITY,
                "synthetic": True,
                "physical_measurements_present": False,
                "hardware_accessed": False,
                "execution_authorized": False,
                "physical_release_effect": "NONE",
            },
        )
        hashes[artifact_id] = artifact.content_hash
        expected_artifacts.append(
            {
                "artifact_id": artifact_id,
                "requirement_artifact_schema": requirement.artifact_schema,
                "calibration_container_schema": artifact.schema,
                "version": 1,
                "state": "NOMINAL_ONLY",
                "artifact_hash": artifact.content_hash,
                "dependency_hashes": dependencies,
                "parent_artifact_hashes": parents,
                "baseline_reasons": [f"CALIBRATION_STATE:{artifact_id}:NOMINAL_ONLY"],
                "physical_evidence": False,
            }
        )
    _same(
        synthetic["artifacts"], expected_artifacts, "complete nominal artifact baseline"
    )
    expected_edges = [
        ("PARENT_ARTIFACT", parent, child) for parent, child in graph.parent_edges
    ]
    expected_edges += [
        ("CONTEXT_SOURCE", dependency, artifact_id)
        for artifact_id in graph.ordered_requirements
        for dependency in (
            _GRAPH_CONTEXT,
            *graph.requirements[artifact_id].context_dependencies,
        )
    ]
    probes = synthetic["staleness_probes"]
    if type(probes) is not list or len(probes) != len(expected_edges):
        _fail("one retained result for every declared dependency edge is required")
    detected = 0
    for probe, (kind, upstream, downstream) in zip(probes, expected_edges):
        _object(
            probe,
            {
                "edge_kind",
                "upstream_id",
                "downstream_id",
                "expected_reason",
                "observed_stale_reasons",
                "detected",
                "hardware_accessed",
                "execution_authorized",
            },
        )
        prefix = (
            "STALE_PARENT_CALIBRATION"
            if kind == "PARENT_ARTIFACT"
            else "STALE_CALIBRATION_DEPENDENCY"
        )
        reason = f"{prefix}:{downstream}:{upstream}"
        _same(
            [
                probe["edge_kind"],
                probe["upstream_id"],
                probe["downstream_id"],
                probe["expected_reason"],
            ],
            [kind, upstream, downstream, reason],
            "exact graph edge",
        )
        observed = probe["observed_stale_reasons"]
        if type(observed) is not list or any(
            type(value) is not str for value in observed
        ):
            _fail("edge reasons must be a bounded string vector")
        matched = observed == [reason]
        _same(probe["detected"], matched, "edge observed disposition")
        _same(probe["hardware_accessed"], False, "edge hardware access")
        _same(probe["execution_authorized"], False, "edge authority")
        detected += matched
    passed = detected == len(expected_edges)
    for name, expected in (
        ("baseline_parent_bindings_coherent", True),
        ("all_edges_exercised", passed),
        ("simulation_graph_verified", passed),
        ("physical_artifacts_created", False),
        ("physical_registry_written", False),
        ("hardware_accessed", False),
        ("robot_commands_sent", 0),
        ("execution_authorized", False),
        ("physical_release_effect", "NONE"),
    ):
        _same(synthetic[name], expected, "graph derived disposition")
    _same(
        synthetic["status"],
        (
            "SYNTHETIC_GRAPH_VERIFIED_PHYSICAL_EVIDENCE_NOT_CREATED"
            if passed
            else "SYNTHETIC_GRAPH_REHEARSAL_FAILED"
        ),
        "synthetic graph status",
    )
    _same(
        synthetic["closure_hash"],
        _hash(
            {key: value for key, value in synthetic.items() if key != "closure_hash"}
        ),
        "retained closure hash",
    )
    assessments: dict[str, dict[str, Any]] = {}
    closures = item["device_closures"]
    if type(closures) is not list or len(closures) != 2:
        _fail("both complete device graph closures are required")
    for closure, device in zip(closures, ("keyboard", "phone")):
        _object(
            closure,
            {
                "device",
                "terminals",
                "ordered_requirements",
                "physical_artifacts_all_valid",
            },
        )
        _same(closure["device"], device, "device closure order")
        _same(
            closure["terminals"],
            list(graph.device_terminals[device]),
            "device terminals",
        )
        rows = closure["ordered_requirements"]
        ids = graph.device_closure(device)
        if type(rows) is not list or len(rows) != len(ids):
            _fail("device closure is incomplete")
        valid = []
        for row, artifact_id in zip(rows, ids):
            requirement_document = graph.requirements[artifact_id].to_dict()
            _object(row, {*requirement_document, "physical_assessment"})
            _same(
                {key: row[key] for key in requirement_document},
                requirement_document,
                "closure requirement",
            )
            assessment = _object(
                row["physical_assessment"],
                {"state", "valid", "artifact_hash", "reasons"},
            )
            typed = ArtifactAssessment(
                artifact_id,
                ArtifactState(assessment["state"]),
                assessment["artifact_hash"],
                tuple(assessment["reasons"]),
            )
            _same(assessment["valid"], typed.valid, "physical assessment flag")
            if artifact_id in assessments:
                _same(
                    assessments[artifact_id], assessment, "shared physical assessment"
                )
            assessments[artifact_id] = assessment
            valid.append(typed.valid)
        _same(
            closure["physical_artifacts_all_valid"],
            all(valid),
            "device physical closure status",
        )
    if set(assessments) != set(graph.ordered_requirements):
        _fail("full physical assessment projection is incomplete")
    all_valid = all(row["valid"] for row in assessments.values())
    physical = _object(
        item["physical_registry"],
        {
            "relative_path",
            "index_present",
            "assessment_count",
            "missing_artifact_ids",
            "physical_artifacts_all_valid",
            "blocked",
            "read_only",
            "written",
        },
    )
    if type(physical["index_present"]) is not bool:
        _fail("physical index presence must be Boolean")
    for name, expected in (
        ("relative_path", "software/calibrations"),
        ("assessment_count", 15),
        (
            "missing_artifact_ids",
            [
                name
                for name in graph.ordered_requirements
                if assessments[name]["state"] == "MISSING"
            ],
        ),
        ("physical_artifacts_all_valid", all_valid),
        ("blocked", not all_valid),
        ("read_only", True),
        ("written", False),
    ):
        _same(physical[name], expected, "physical registry projection")
    status = (
        "SYNTHETIC_PHASE1_GRAPH_REHEARSAL_FAILED"
        if not passed
        else (
            "SYNTHETIC_PHASE1_GRAPH_VERIFIED_PHYSICAL_ARTIFACTS_PRESENT_NO_AUTHORITY"
            if all_valid
            else "SYNTHETIC_PHASE1_GRAPH_VERIFIED_PHYSICAL_REGISTRY_BLOCKED"
        )
    )
    _same(item["status"], status, "complete graph status")
    return passed, detected


def _positions(geometry: dict[str, Any], index: int) -> dict[str, JointPosition]:
    values = [
        value + offset
        for value, offset in zip(geometry["ready_joint_positions_rad"], _OFFSETS[index])
    ]
    return {name: JointPosition.radians(value) for name, value in zip(_JOINTS, values)}


def _algebraic_hand_transform(
    model: UrdfModel, positions: dict[str, JointPosition]
) -> RigidTransform:
    """Independently compose retained URDF local equations, not the FK evaluator."""
    by_child = {joint.child_link: joint for joint in model.joints}
    chain: list[Any] = []
    child = "hand_tcp"
    while child != model.root_link:
        if len(chain) >= len(model.joints) or child not in by_child:
            _fail("retained hand chain is incomplete or cyclic")
        joint = by_child[child]
        chain.append(joint)
        child = joint.parent_link
    result = RigidTransform.identity(model.root_link)
    for joint in reversed(chain):
        result = result.compose(joint.transform_at(positions.get(joint.name)))
    # Gripper position is outside the hand chain, but its units/limits still
    # belong to the complete source model; never silently omit its validation.
    for name, position in positions.items():
        joint = model.joint(name)
        if joint.limit is None:
            _fail("movable joint limit is unavailable")
        joint.limit.validate(position, joint_name=name)
    return result


def _frame_row(
    geometry: dict[str, Any], index: int, world_hand: RigidTransform
) -> dict[str, Any]:
    board_world = _from_transform(geometry["board_T_world"])
    hand_tip = _from_transform(geometry["hand_T_tip"])
    world_tip = world_hand.compose(hand_tip)
    board_tip = board_world.compose(world_tip)
    origin = Point3Mm("nominal_tip", 0.0, 0.0, 0.0)
    in_world, in_board = world_tip.transform_point(origin), board_tip.transform_point(
        origin
    )
    returned = board_world.inverse().transform_point(in_board)
    return {
        "pose_id": f"pose-{index}",
        "partition": "TRAINING" if index < 4 else "HELD_OUT",
        "joint_positions_rad": [
            position.value for position in _positions(geometry, index).values()
        ],
        "world_T_hand": _transform(world_hand),
        "board_T_tip": _transform(board_tip),
        "world_tip": _point(in_world),
        "board_tip": _point(in_board),
        "roundtrip_error_mm": _distance(in_world, returned),
    }


def _target_roundtrips(geometry: dict[str, Any]) -> list[dict[str, Any]]:
    board_world = _from_transform(geometry["board_T_world"])
    result = []
    for target in geometry["selected_targets"]:
        point = _from_point(target["point"])
        world = board_world.inverse().transform_point(point)
        returned = board_world.transform_point(world)
        result.append(
            {
                "device": target["device"],
                "target_id": target["target_id"],
                "world_point": _point(world),
                "returned_board_point": _point(returned),
                "roundtrip_error_mm": _distance(point, returned),
            }
        )
    return result


def _frame_report(geometry: dict[str, Any], model: UrdfModel) -> dict[str, Any]:
    rows = [
        _frame_row(
            geometry,
            index,
            model.forward_kinematics(_positions(geometry, index))["hand_tcp"],
        )
        for index in range(len(_OFFSETS))
    ]
    return {
        "schema": "rocell.nominal_reference_frame_chain.v1",
        "units": "mm_and_radians",
        "chain": ["board_T_world", "world_T_hand_tcp(q)", "hand_tcp_T_nominal_tip"],
        "joint_reference": "SOURCE_SCENARIO_PLUS_NOMINAL_OFFSETS_NOT_CALIBRATED_CONTROLLER",
        "rows": rows,
        "target_roundtrips": _target_roundtrips(geometry),
        "physical_measurements_present": False,
        "motion_authority": False,
    }


def _verify_frame_report(
    report: object, geometry: dict[str, Any], model: UrdfModel
) -> tuple[list[dict[str, Any]], float]:
    expected: Any
    item = _object(
        report,
        {
            "schema",
            "units",
            "chain",
            "joint_reference",
            "rows",
            "target_roundtrips",
            "physical_measurements_present",
            "motion_authority",
        },
    )
    for name, expected in (
        ("schema", "rocell.nominal_reference_frame_chain.v1"),
        ("units", "mm_and_radians"),
        ("chain", ["board_T_world", "world_T_hand_tcp(q)", "hand_tcp_T_nominal_tip"]),
        (
            "joint_reference",
            "SOURCE_SCENARIO_PLUS_NOMINAL_OFFSETS_NOT_CALIBRATED_CONTROLLER",
        ),
        ("physical_measurements_present", False),
        ("motion_authority", False),
    ):
        _same(item[name], expected, "frame chain convention")
    rows = item["rows"]
    if type(rows) is not list or len(rows) != len(_OFFSETS):
        _fail("the exact six-pose reference subset must be retained")
    for index, row in enumerate(rows):
        expected = _frame_row(
            geometry,
            index,
            _algebraic_hand_transform(model, _positions(geometry, index)),
        )
        _same(row, expected, "retained FK local-equation chain")
    _same(
        item["target_roundtrips"],
        _target_roundtrips(geometry),
        "selected target coordinate roundtrips",
    )
    maximum = max(
        row["roundtrip_error_mm"] for row in [*rows, *item["target_roundtrips"]]
    )
    return rows, maximum


def _fit_input(
    binding: RehearsalReferenceBinding, rows: list[dict[str, Any]], *, fault: bool
) -> RigidCorrespondenceInput:
    pairs = []
    for index, row in enumerate(rows):
        source, target = _from_point(row["world_tip"]), _from_point(row["board_tip"])
        if fault and index == 4:
            target = Point3Mm(target.frame, target.x + 10.0, target.y, target.z)
        pairs.append(RigidPointPair(row["pose_id"], source, target))
    return RigidCorrespondenceInput(
        "REFERENCE-HELDOUT-OFFSET" if fault else "REFERENCE-NOMINAL",
        "world",
        "board",
        tuple(pairs[:4]),
        tuple(pairs[4:]),
        binding.workspace_source_sha256,
        binding.binding_sha256,
        CorrespondenceOrigin.SYNTHETIC_REHEARSAL_ONLY,
    )


def _fault_inputs(geometry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "reflected_rotation": {
            "matrix": [-1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        },
        "disconnected_frames": {
            "left": geometry["board_T_world"],
            "right": geometry["hand_T_tip"],
        },
        "wrong_joint_units": {
            "joint_name": _JOINTS[0],
            "value": geometry["ready_joint_positions_rad"][0],
            "unit": "millimetres",
        },
    }


def _fault_reports(
    geometry: dict[str, Any], model: UrdfModel
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, inputs in _fault_inputs(geometry).items():
        try:
            if name == "reflected_rotation":
                Rotation3(tuple(inputs["matrix"]))
            elif name == "disconnected_frames":
                _from_transform(inputs["left"]).compose(
                    _from_transform(inputs["right"])
                )
            else:
                limit = model.joint(inputs["joint_name"]).limit
                assert limit is not None
                limit.validate(
                    JointPosition.millimetres(inputs["value"]),
                    joint_name=inputs["joint_name"],
                )
        except Exception as error:
            result[name] = {
                "input": inputs,
                "disposition": "REJECTED",
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        else:
            result[name] = {
                "input": inputs,
                "disposition": "ACCEPTED",
                "error_type": None,
                "error_message": None,
            }
    return result


def _derive(
    document: dict[str, Any], binding: RehearsalReferenceBinding
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    geometry, model = _source_geometry(binding)
    reports = _object(
        document["technical_reports"],
        {"graph", "frame_chain", "nominal_fit", "heldout_fault_fit", "refusal_faults"},
    )
    _, detected = _check_graph(reports["graph"], binding)
    rows, maximum = _verify_frame_report(reports["frame_chain"], geometry, model)
    nominal = verify_rigid_correspondence_result(
        _canonical(reports["nominal_fit"]),
        expected_input=_fit_input(binding, rows, fault=False),
        expected_policy=DEFAULT_RIGID_CORRESPONDENCE_POLICY,
        expected_evidence_sha256=_hash(reports["nominal_fit"]),
    )
    negative = verify_rigid_correspondence_result(
        _canonical(reports["heldout_fault_fit"]),
        expected_input=_fit_input(binding, rows, fault=True),
        expected_policy=DEFAULT_RIGID_CORRESPONDENCE_POLICY,
        expected_evidence_sha256=_hash(reports["heldout_fault_fit"]),
    )
    truth = _from_transform(geometry["board_T_world"])
    fitted = nominal.candidate_transform
    translation_error = (fitted.translation_mm - truth.translation_mm).norm
    rotation_error = max(
        abs(a - b) for a, b in zip(fitted.rotation.matrix, truth.rotation.matrix)
    )
    fit_unchanged = negative.candidate_transform.almost_equal(
        fitted, absolute_tolerance=1e-9
    )
    checks = []

    def check(
        name: str, kind: str, passed: bool, observed: dict[str, Any], meaning: str
    ) -> None:
        checks.append(
            {
                "check_id": name,
                "check_kind": kind,
                "passed": passed,
                "observed": observed,
                "meaning": meaning,
            }
        )

    check(
        "nominal_graph_baseline",
        "NOMINAL",
        reports["graph"]["synthetic_rehearsal"]["baseline_parent_bindings_coherent"]
        is True,
        {"nominal_artifacts": 15, "physical_artifacts_promoted": 0},
        "The real graph registry kept every synthetic artifact NOMINAL_ONLY; this is not installed calibration.",
    )
    check(
        "nominal_reference_fit",
        "NOMINAL",
        nominal.diagnostic_pass
        and translation_error <= 1e-7
        and rotation_error <= 1e-9,
        {
            "diagnostic_pass": nominal.diagnostic_pass,
            "translation_error_mm": translation_error,
            "rotation_matrix_max_error": rotation_error,
        },
        "The actual rigid fit recovers the assumed source board/world transform from four training and two untouched synthetic heldouts.",
    )
    check(
        "nominal_frame_chain",
        "NOMINAL",
        maximum <= 1e-7,
        {"poses": 6, "max_roundtrip_error_mm": maximum},
        "Pinned URDF FK and board/world/hand/tip composition agree with retained local joint equations; no controller calibration is inferred.",
    )
    check(
        "dependency_staleness",
        "EXPECTED_FAULT",
        detected == 68,
        {"detected_edges": detected, "expected_edges": 68},
        "Each of the 27 parent and 41 context edges was independently changed and its exact stale reason retained.",
    )
    check(
        "heldout_error_detected",
        "EXPECTED_FAULT",
        not negative.diagnostic_pass
        and fit_unchanged
        and set(negative.diagnostic_failures)
        == {"HELD_OUT_RMS_EXCEEDED", "HELD_OUT_MAXIMUM_EXCEEDED"},
        {
            "diagnostic_pass": negative.diagnostic_pass,
            "failures": list(negative.diagnostic_failures),
            "training_fit_unchanged": fit_unchanged,
        },
        "A ten-millimetre heldout-only error must fail validation without changing the training fit; expected faults cannot create nominal readiness.",
    )
    faults = _object(reports["refusal_faults"], set(_fault_inputs(geometry)))
    for name, inputs in _fault_inputs(geometry).items():
        report = _object(
            faults[name], {"input", "disposition", "error_type", "error_message"}
        )
        _same(report["input"], inputs, "closed refusal input")
        if report["disposition"] not in {"REJECTED", "ACCEPTED"}:
            _fail("unknown refusal disposition")
        if report["disposition"] == "ACCEPTED":
            _same(
                [report["error_type"], report["error_message"]],
                [None, None],
                "accepted fault fields",
            )
        elif (
            type(report["error_type"]) is not str
            or type(report["error_message"]) is not str
            or not report["error_message"]
        ):
            _fail("rejected fault must retain its actual typed error")
        expected_type = {
            "reflected_rotation": "ValueError",
            "disconnected_frames": "FrameMismatchError",
            "wrong_joint_units": "JointStateError",
        }[name]
        check(
            name,
            "EXPECTED_FAULT",
            report["disposition"] == "REJECTED"
            and report["error_type"] == expected_type,
            {"disposition": report["disposition"], "error_type": report["error_type"]},
            "The actual geometry/unit API rejects this closed invalid input; no physical operation was attempted.",
        )
    check(
        "physical_reference_components_pending",
        "INVARIANT",
        document["physical_authority"] is False
        and document["actual_physical_effects"] == _EFFECTS,
        {"pending_components": 8, "physical_authority": False},
        "All eight canonical physical components remain pending, including external bootstrap/reference receipts, correlation, TCP and maps.",
    )
    nominal_dict = nominal.to_dict()
    summary = {
        "schema": "rocell.rehearsal_reference_summary.v1",
        "graph": {
            "nominal_artifacts": 15,
            "parent_edges": 27,
            "context_edges": 41,
            "detected_edges": detected,
        },
        "numeric": {
            "training_points": 4,
            "heldout_points": 2,
            "training_rms_mm": nominal_dict["training_summary"]["rms_mm"],
            "heldout_rms_mm": nominal_dict["held_out_summary"]["rms_mm"],
            "max_roundtrip_error_mm": maximum,
        },
        "target_coverage": {
            "keyboard": {"selected": ["A"], "catalog_total": 46},
            "phone": {"selected": ["key_q"], "catalog_total": 29},
        },
        "claim": "TWO_TARGET_COORDINATE_ROUNDTRIPS_NOT_REACHABILITY_OR_COMPLETE_COVERAGE",
        "physical_components_pending": list(_PENDING),
        "camera_role": "DEPENDENCY_ONLY_NOT_NUMERIC_INPUT",
        "controller_feedback_role": "TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT",
    }
    return checks, summary


@dataclass(frozen=True, slots=True)
class RehearsalReferenceEvidence:
    _payload: bytes

    def __post_init__(self) -> None:
        # This bound does not turn a public constructor into a verifier. Only
        # the required-hash verification API authenticates the full contract.
        _decode(self._payload)

    def canonical_bytes(self) -> bytes:
        return self._payload

    @property
    def evidence_sha256(self) -> str:
        return hashlib.sha256(self._payload).hexdigest()

    @property
    def evaluation_sha256(self) -> str:
        return self.evidence_sha256

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._payload)

    @property
    def checks(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.to_dict()["checks"])

    @property
    def outcome(self) -> str:
        return self.to_dict()["outcome"]


def verify_rehearsal_reference_evidence(
    payload: bytes,
    *,
    expected_binding: RehearsalReferenceBinding,
    expected_evidence_sha256: str,
    expected_evaluator_source_sha256: str,
) -> RehearsalReferenceEvidence:
    """Verify complete retained equations/certificates; no source or device I/O."""
    if type(expected_binding) is not RehearsalReferenceBinding:
        _fail("the exact server-pinned reference binding is required")
    expected_binding.__post_init__()
    decoded = _decode(payload)
    if hashlib.sha256(payload).hexdigest() != _digest(expected_evidence_sha256):
        _fail("reference evidence differs from its trusted retained digest")
    document = _object(
        decoded,
        {
            "schema",
            "stage",
            "binding",
            "evaluator_source_sha256",
            "dependency_source_sha256s",
            "technical_reports",
            "selected_inputs_sha256",
            "checks",
            "reference_summary",
            "outcome",
            "provenance",
            "physical_authority",
            "composition",
            "physical_release_effect",
            "actual_physical_effects",
            "meaning",
        },
    )
    for name, expected in (
        ("schema", SCHEMA),
        ("stage", _STAGE),
        ("binding", expected_binding.to_dict()),
        ("evaluator_source_sha256", _digest(expected_evaluator_source_sha256)),
        ("selected_inputs_sha256", expected_binding.binding_sha256),
        ("provenance", _PROVENANCE),
        ("physical_authority", False),
        ("composition", "HARDWARE_INCAPABLE_REHEARSAL"),
        ("physical_release_effect", "NONE"),
        ("actual_physical_effects", _EFFECTS),
        ("meaning", _MEANING),
    ):
        _same(document[name], expected, "reference identity/authority")
    sources = _object(document["dependency_source_sha256s"], set(_DEPENDENCY_MODULES))
    for digest in sources.values():
        _digest(digest)
    try:
        checks, summary = _derive(document, expected_binding)
        _same(document["checks"], checks, "independently derived reference checks")
        _same(document["reference_summary"], summary, "derived reference summary")
        outcome = (
            "REHEARSAL_CHECKS_PASSED"
            if all(row["passed"] is True for row in checks)
            else "BLOCKED"
        )
        _same(document["outcome"], outcome, "nominal reference outcome")
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        if isinstance(error, RehearsalReferenceError):
            raise
        raise RehearsalReferenceError(
            "retained reference equations or schema are inconsistent"
        ) from error
    return RehearsalReferenceEvidence(payload)


def evaluate_rehearsal_reference_stage(
    workspace: Path, binding: RehearsalReferenceBinding
) -> RehearsalReferenceEvidence:
    """Run the closed graph/FK/fit fixtures, retaining every technical result."""
    if type(binding) is not RehearsalReferenceBinding:
        _fail("the exact source-bound reference binding is required")
    binding.__post_init__()
    root = Path(workspace).resolve()
    _same(
        read_reference_source_context(root),
        binding.source_context,
        "fresh reference source context",
    )
    context = load_simulation_context(
        root, root / "software/config/system_manifest.json"
    )
    geometry, model = _source_geometry(binding)
    frame_report = _frame_report(geometry, model)
    rows = frame_report["rows"]
    sources = {
        name: hashlib.sha256(
            (root / "software/src/rocell" / name).read_bytes()
        ).hexdigest()
        for name in _DEPENDENCY_MODULES
    }
    evaluator_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    document = {
        "schema": SCHEMA,
        "stage": _STAGE,
        "binding": binding.to_dict(),
        "evaluator_source_sha256": evaluator_sha,
        "dependency_source_sha256s": sources,
        "technical_reports": {
            "graph": run_static_phase1_calibration_rehearsal(context).to_dict(),
            "frame_chain": frame_report,
            "nominal_fit": fit_rigid_correspondence(
                _fit_input(binding, rows, fault=False)
            ).to_dict(),
            "heldout_fault_fit": fit_rigid_correspondence(
                _fit_input(binding, rows, fault=True)
            ).to_dict(),
            "refusal_faults": _fault_reports(geometry, model),
        },
        "selected_inputs_sha256": binding.binding_sha256,
        "provenance": dict(_PROVENANCE),
        "physical_authority": False,
        "composition": "HARDWARE_INCAPABLE_REHEARSAL",
        "physical_release_effect": "NONE",
        "actual_physical_effects": dict(_EFFECTS),
        "meaning": _MEANING,
    }
    checks, summary = _derive(document, binding)
    document.update(
        checks=checks,
        reference_summary=summary,
        outcome=(
            "REHEARSAL_CHECKS_PASSED"
            if all(row["passed"] is True for row in checks)
            else "BLOCKED"
        ),
    )
    payload = _canonical(document)
    return verify_rehearsal_reference_evidence(
        payload,
        expected_binding=binding,
        expected_evidence_sha256=hashlib.sha256(payload).hexdigest(),
        expected_evaluator_source_sha256=evaluator_sha,
    )


__all__ = [
    "SCHEMA",
    "MAX_EVIDENCE_BYTES",
    "RehearsalReferenceError",
    "RehearsalReferenceEvidence",
    "read_reference_source_context",
    "evaluate_rehearsal_reference_stage",
    "verify_rehearsal_reference_evidence",
]
