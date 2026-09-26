"""Bind one model coordinate candidate to planning prerequisites without motion.

The gate is intentionally incapable of trajectory generation or hardware access.
It proves that the coordinate proposal, frozen target catalog, build context,
frame contract, configuration-epoch policy, and calibration graph refer to one
coherent planning attempt. Until measured calibration artifacts and their strict
payload decoder exist, the valid disposition is a documented block. With a valid
snapshot, measured target reprojection may advance to offline IK/route screening.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from rocell.models import ModelMotionProposal
from rocell.rc03.integrity import sha256_file
from rocell.calibration import (
    CalibrationRegistry,
    PlannerCalibrationSnapshotError,
    decode_planner_calibration_snapshot,
    required_planner_artifact_ids,
)

from .calibration_status import assess_calibration_status
from .context import (
    SimulationContext,
    load_simulation_context,
    revalidate_simulation_context,
)
from .model_motion_bridge import compile_model_motion_proposal
from .measured_target_reprojection import (
    MeasuredTargetReprojectionError,
    reproject_measured_target,
)
from .measured_trajectory_screening import (
    MeasuredTrajectoryScreeningError,
    screen_measured_trajectory,
)
from .observed_planner_start_state import ObservedPlannerStartState


class ModelMotionPlannerGateError(ValueError):
    """The proposal cannot be bound to the deterministic planner boundary."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _strict_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ModelMotionPlannerGateError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _calibration_blockers(document: Mapping[str, Any]) -> tuple[str, ...]:
    blockers: list[str] = []
    rows = document.get("ordered_requirements")
    if not isinstance(rows, list):
        raise ModelMotionPlannerGateError("calibration report requirements are invalid")
    for row in rows:
        if not isinstance(row, Mapping):
            raise ModelMotionPlannerGateError("calibration requirement row is invalid")
        assessment = row.get("assessment")
        if not isinstance(assessment, Mapping):
            raise ModelMotionPlannerGateError("calibration assessment is invalid")
        reasons = assessment.get("reasons")
        if not isinstance(reasons, list) or any(
            not isinstance(item, str) for item in reasons
        ):
            raise ModelMotionPlannerGateError("calibration reasons are invalid")
        blockers.extend(reasons)
    return tuple(dict.fromkeys(blockers))


def evaluate_model_motion_planner_gate(
    proposal: ModelMotionProposal,
    context: SimulationContext,
    *,
    minimum_confidence: float = 0.9,
    observed_start_state: ObservedPlannerStartState | None = None,
    evaluation_monotonic_ns: int | None = None,
) -> dict[str, Any]:
    """Return a hash-bound, zero-authority planner-admission report.

    A complete calibration graph is necessary but not sufficient. Valid artifacts
    are decoded through the strict planner snapshot contract and the model target is
    reprojected through measured device placement. IK and route screening remain a
    later stage.
    """

    if not isinstance(proposal, ModelMotionProposal):
        raise TypeError("proposal must be a ModelMotionProposal")
    if not isinstance(context, SimulationContext):
        raise TypeError("context must be a SimulationContext")
    revalidate_simulation_context(context)

    candidate = compile_model_motion_proposal(
        proposal,
        context.targets,
        minimum_confidence=minimum_confidence,
    )
    if candidate["target_catalog_sha256"] != context.targets.content_sha256:
        raise ModelMotionPlannerGateError("candidate target catalog binding mismatch")

    calibration = assess_calibration_status(context, proposal.device.value)
    calibration_document = calibration.to_dict()
    blockers = list(_calibration_blockers(calibration_document))
    calibration_snapshot = None
    calibration_snapshot_sha256 = None
    measured_target_reprojection = None
    measured_target_reprojection_sha256 = None
    trajectory_candidate = None
    if calibration.all_valid:
        artifact_ids = required_planner_artifact_ids(proposal.device.value)
        registry = CalibrationRegistry(context.workspace / "software/calibrations")
        artifacts = {}
        for artifact_id in artifact_ids:
            artifact = registry.get_current(artifact_id)
            if artifact is None:
                raise ModelMotionPlannerGateError(
                    "calibration resolution was valid but a required artifact disappeared"
                )
            artifacts[artifact_id] = artifact
        assessments = {item.artifact_id: item for item in calibration.assessments}
        try:
            decoded = decode_planner_calibration_snapshot(
                device=proposal.device.value,
                artifacts=artifacts,
                assessments={
                    artifact_id: assessments[artifact_id]
                    for artifact_id in artifact_ids
                },
                expected_target_map_sha256=context.targets.content_sha256,
            )
        except PlannerCalibrationSnapshotError as exc:
            status = "BLOCKED_CALIBRATION_PAYLOAD_INVALID"
            blockers.append(f"CALIBRATION_PAYLOAD_INVALID:{exc}")
            next_stage = "CORRECT_MEASURED_CALIBRATION_PAYLOADS"
        else:
            calibration_snapshot = decoded.to_dict()
            calibration_snapshot_sha256 = decoded.snapshot_sha256
            try:
                reprojected = reproject_measured_target(
                    proposal,
                    context.targets,
                    decoded,
                    model_motion_candidate_sha256=candidate["candidate_sha256"],
                )
            except MeasuredTargetReprojectionError as exc:
                status = "BLOCKED_MEASURED_TARGET_REPROJECTION_INVALID"
                blockers.append(f"MEASURED_TARGET_REPROJECTION_INVALID:{exc}")
                next_stage = "CORRECT_MODEL_TARGET_OR_MEASURED_DEVICE_PLACEMENT"
            else:
                measured_target_reprojection = reprojected
                measured_target_reprojection_sha256 = reprojected["reprojection_sha256"]
                try:
                    trajectory_candidate = screen_measured_trajectory(
                        proposal,
                        context,
                        decoded,
                        reprojected,
                        observed_start_state=observed_start_state,
                        evaluation_monotonic_ns=evaluation_monotonic_ns,
                    )
                except MeasuredTrajectoryScreeningError as exc:
                    status = "BLOCKED_MEASURED_TRAJECTORY_INPUT_INVALID"
                    blockers.append(f"MEASURED_TRAJECTORY_INPUT_INVALID:{exc}")
                    next_stage = "CORRECT_MEASURED_TRAJECTORY_INPUT"
                else:
                    status = trajectory_candidate["status"]
                    blockers.extend(trajectory_candidate["blockers"])
                    next_stage = trajectory_candidate["next_required_stage"]
    else:
        status = "BLOCKED_CALIBRATION_MISSING_OR_STALE"
        next_stage = "COMMISSION_REQUIRED_CALIBRATIONS"

    epoch_policy_path = context.workspace / "software/config/configuration_epochs.json"
    arm_frame_lock = context.bundle_lock.artifact("arm_frame_contract")
    report: dict[str, Any] = {
        "schema": "rocell.model_motion_planner_gate.v1",
        "status": status,
        "model_motion_candidate_sha256": candidate["candidate_sha256"],
        "model_motion_candidate": candidate,
        "source_bindings": {
            "manifest_id": context.snapshot.manifest_id,
            "system_manifest_sha256": context.snapshot.manifest_sha256,
            "build_snapshot_sha256": context.snapshot.snapshot_hash,
            "active_build_id": context.snapshot.active_build_id,
            "simulation_bundle_id": context.bundle_lock.bundle_id,
            "simulation_bundle_sha256": context.bundle_lock.source_lock_sha256,
            "target_catalog_sha256": context.targets.content_sha256,
            "kinematic_model_sha256": context.scenario.model_sha256,
            "arm_frame_contract_sha256": arm_frame_lock.sha256,
            "configuration_epoch_policy_sha256": sha256_file(epoch_policy_path),
        },
        "calibration_status_sha256": calibration.report_hash,
        "calibration_status": calibration_document,
        "calibration_snapshot_sha256": calibration_snapshot_sha256,
        "calibration_snapshot": calibration_snapshot,
        "measured_target_reprojection_sha256": measured_target_reprojection_sha256,
        "measured_target_reprojection": measured_target_reprojection,
        "blockers": blockers,
        "next_required_stage": next_stage,
        "trajectory_candidate": trajectory_candidate,
        "ik_executed": bool(
            trajectory_candidate and trajectory_candidate.get("ik_executed", False)
        ),
        "route_screen_executed": bool(
            trajectory_candidate and trajectory_candidate.get("waypoints", [])
        ),
        "controller_commands": [],
        "hardware_commands_generated": 0,
        "hardware_access": False,
        "physical_authority": False,
    }
    return {
        **report,
        "planner_gate_sha256": hashlib.sha256(_canonical(report)).hexdigest(),
    }


def evaluate_mapping(
    value: object,
    *,
    workspace: Path,
    manifest_path: Path | None = None,
    minimum_confidence: float = 0.9,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    selected_manifest = (
        Path(manifest_path).resolve()
        if manifest_path is not None
        else root / "software/config/system_manifest.json"
    )
    proposal = ModelMotionProposal.from_mapping(value)
    context = load_simulation_context(root, selected_manifest)
    return evaluate_model_motion_planner_gate(
        proposal,
        context,
        minimum_confidence=minimum_confidence,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--minimum-confidence", type=float, default=0.9)
    args = parser.parse_args(argv)
    document = json.loads(
        args.proposal.read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ModelMotionPlannerGateError(f"nonfinite JSON constant {value!r}")
        ),
    )
    report = evaluate_mapping(
        document,
        workspace=args.workspace,
        manifest_path=args.manifest,
        minimum_confidence=args.minimum_confidence,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through subprocess use
    raise SystemExit(main())
