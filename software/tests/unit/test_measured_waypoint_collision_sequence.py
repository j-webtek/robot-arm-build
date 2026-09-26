from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.installed_collision_geometry import (
    InstalledCollisionGeometryProfile,
)
from rocell.application.measured_waypoint_collision_sequence import (
    MAX_WAYPOINT_COLLISION_SAMPLES,
    MeasuredWaypointCollisionSample,
    MeasuredWaypointCollisionSequenceError,
    evaluate_measured_waypoint_collision_sequence,
)
from rocell.geometry import RigidTransform, Rotation3, Vec3
from rocell.simulation.collision import (
    CapsuleMm,
    CollisionBindingMode,
    CollisionBody,
    CollisionBodyRequirement,
    CollisionBodyRole,
    CollisionClearanceEvidenceState,
    CollisionClearancePolicy,
    CollisionEvidenceState,
    CollisionGeometryContract,
    CollisionPose,
    OrientedBoxMm,
    SampledCollisionGeometry,
    SphereMm,
)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def profile() -> InstalledCollisionGeometryProfile:
    requirements = (
        CollisionBodyRequirement("link", "link", CollisionBodyRole.ROBOT_LINK),
        CollisionBodyRequirement(
            "cable",
            "board",
            CollisionBodyRole.CABLE,
            CollisionBindingMode.CONFIGURATION_SAMPLED,
        ),
        CollisionBodyRequirement(
            "fixture",
            "board",
            CollisionBodyRole.STATIC_ENVIRONMENT,
            CollisionBindingMode.STATIC_ROOT,
        ),
    )
    bodies = (
        CollisionBody(
            "link",
            "link",
            CollisionBodyRole.ROBOT_LINK,
            CollisionEvidenceState.ACCEPTED_MEASURED,
            (SphereMm(Vec3.zero(), 2.0),),
            source_reference="measured link",
        ),
        CollisionBody(
            "cable",
            "board",
            CollisionBodyRole.CABLE,
            CollisionEvidenceState.ACCEPTED_MEASURED,
            (),
            CollisionBindingMode.CONFIGURATION_SAMPLED,
            "measured cable identity",
        ),
        CollisionBody(
            "fixture",
            "board",
            CollisionBodyRole.STATIC_ENVIRONMENT,
            CollisionEvidenceState.ACCEPTED_MEASURED,
            (OrientedBoxMm(Vec3(100.0, 0.0, 0.0), Vec3(2.0, 2.0, 2.0)),),
            CollisionBindingMode.STATIC_ROOT,
            "measured fixture",
        ),
    )
    contract = CollisionGeometryContract(
        "measured-waypoint-test", "board", requirements, bodies
    )
    clearance = CollisionClearancePolicy(
        1.0,
        0.25,
        0.25,
        CollisionClearanceEvidenceState.ACCEPTED_MEASURED,
        "measured clearance",
    )
    return InstalledCollisionGeometryProfile(
        "profile",
        "manifest",
        "1" * 64,
        "build",
        "2" * 64,
        "3" * 64,
        "4" * 64,
        {"metrology": "5" * 64},
        contract,
        clearance,
        "6" * 64,
        "7" * 64,
    )


def trajectory(installed: InstalledCollisionGeometryProfile, count: int = 2):
    report = {
        "schema": "rocell.measured_trajectory_screening.v2",
        "installed_collision_profile_sha256": installed.content_sha256,
        "collision_contract_sha256": installed.contract.content_hash,
        "ik_all_waypoints_accepted": True,
        "waypoints": [
            {"sequence": index, "point_mm": [float(index), 0.0, 0.0]}
            for index in range(count)
        ],
        "joint_results": [
            {"accepted": True, "solution": [float(index)]} for index in range(count)
        ],
    }
    return {**report, "trajectory_screening_sha256": digest(report)}


def cable(x: float = 30.0) -> SampledCollisionGeometry:
    return SampledCollisionGeometry(
        (CapsuleMm(Vec3(x, 0.0, 0.0), Vec3(x + 5.0, 0.0, 0.0), 0.5),),
        CollisionEvidenceState.ACCEPTED_MEASURED,
        "configuration-correlated cable sample",
    )


def samples(route, positions=(10.0, 12.0), *, include_cable=True):
    result = []
    for index, x in enumerate(positions):
        pose = CollisionPose(
            f"waypoint-{index:04d}",
            "board",
            {
                "link": RigidTransform(
                    "board", "link", Rotation3.identity(), Vec3(x, 0.0, 0.0)
                ),
                "board": RigidTransform.identity("board"),
            },
            {"cable": cable()} if include_cable else {},
        )
        result.append(
            MeasuredWaypointCollisionSample(
                index,
                digest(route["waypoints"][index]),
                digest(route["joint_results"][index]),
                pose,
            )
        )
    return tuple(result)


def test_clear_waypoint_sequence_remains_blocked_on_continuous_proof() -> None:
    installed = profile()
    route = trajectory(installed)
    first = evaluate_measured_waypoint_collision_sequence(
        installed, route, samples(route)
    )
    second = evaluate_measured_waypoint_collision_sequence(
        installed, route, samples(route)
    )

    assert first == second
    assert first["status"] == "DISCRETE_WAYPOINTS_CLEAR_CONTINUOUS_PROOF_REQUIRED"
    assert first["all_waypoints_collision_free_at_supplied_samples"] is True
    assert first["configuration_sampled_body_ids"] == ["cable"]
    assert first["continuous_collision_proven"] is False
    assert first["blockers"] == ["CONTINUOUS_FULL_BODY_COLLISION_SWEEP_REQUIRED"]
    assert first["hardware_commands_generated"] == 0
    assert first["physical_authority"] is False
    schema = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "software/ai/schemas/measured_waypoint_collision_sequence_v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(first)


def test_detected_collision_blocks_route() -> None:
    installed = profile()
    route = trajectory(installed)
    report = evaluate_measured_waypoint_collision_sequence(
        installed, route, samples(route, positions=(10.0, 100.0))
    )

    assert report["status"] == "BLOCKED_COLLISION_DETECTED"
    assert report["all_waypoints_collision_free_at_supplied_samples"] is False
    assert report["pose_reports"][1]["collisions"]
    assert "COLLISION_DETECTED" in report["blockers"][0]


def test_missing_cable_sample_is_explicitly_incomplete() -> None:
    installed = profile()
    route = trajectory(installed)
    report = evaluate_measured_waypoint_collision_sequence(
        installed, route, samples(route, include_cable=False)
    )

    assert report["status"] == "BLOCKED_INCOMPLETE_WAYPOINT_COLLISION_EVIDENCE"
    assert report["pose_reports"][0]["status"] == "BLOCKED_INCOMPLETE_POSE"
    assert report["pose_reports"][0]["pose_blockers"][0]["code"] == (
        "CONFIGURATION_GEOMETRY_MISSING"
    )


def test_crossed_lineage_and_waypoint_bindings_reject() -> None:
    installed = profile()
    route = trajectory(installed)
    crossed = replace(installed, content_sha256="8" * 64)
    with pytest.raises(MeasuredWaypointCollisionSequenceError, match="lineage"):
        evaluate_measured_waypoint_collision_sequence(
            crossed, route, samples(route)
        )

    bad = list(samples(route))
    bad[0] = replace(bad[0], source_joint_result_sha256="9" * 64)
    with pytest.raises(MeasuredWaypointCollisionSequenceError, match="exact planner"):
        evaluate_measured_waypoint_collision_sequence(installed, route, bad)


def test_sample_cap_and_complete_coverage_are_enforced() -> None:
    installed = profile()
    route = trajectory(installed, 1)
    with pytest.raises(MeasuredWaypointCollisionSequenceError, match="exactly one"):
        evaluate_measured_waypoint_collision_sequence(installed, route, ())

    oversized = trajectory(installed, MAX_WAYPOINT_COLLISION_SAMPLES + 1)
    with pytest.raises(MeasuredWaypointCollisionSequenceError, match="hard maximum"):
        evaluate_measured_waypoint_collision_sequence(
            installed,
            oversized,
            tuple(samples(oversized, positions=(10.0,) * (MAX_WAYPOINT_COLLISION_SAMPLES + 1))),
        )
