"""Bind one model coordinate candidate to planning prerequisites without motion.

The gate is intentionally incapable of trajectory generation or hardware access.
It proves that the coordinate proposal, frozen target catalog, build context,
frame contract, configuration-epoch policy, and calibration graph refer to one
coherent planning attempt. Until measured calibration artifacts and their strict
payload decoder exist, the only valid disposition is a documented block.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from rocell.models import ModelMotionProposal
from rocell.rc03.integrity import sha256_file

from .calibration_status import assess_calibration_status
from .context import (
    SimulationContext,
    load_simulation_context,
    revalidate_simulation_context,
)
from .model_motion_bridge import compile_model_motion_proposal


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
        if not isinstance(reasons, list) or any(not isinstance(item, str) for item in reasons):
            raise ModelMotionPlannerGateError("calibration reasons are invalid")
        blockers.extend(reasons)
    return tuple(dict.fromkeys(blockers))


def evaluate_model_motion_planner_gate(
    proposal: ModelMotionProposal,
    context: SimulationContext,
    *,
    minimum_confidence: float = 0.9,
) -> dict[str, Any]:
    """Return a hash-bound, zero-authority planner-admission report.

    A complete calibration graph is necessary but not sufficient. The current
    repository has no reviewed decoder that turns each calibration artifact's
    payload into the closed B -> Wv -> R_u -> G -> T chain while preserving the
    separate R_ctrl correlation. The gate records that implementation blocker
    even if a test registry is populated with nominal artifacts.
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
    status = (
        "BLOCKED_STRICT_CALIBRATION_PAYLOAD_DECODER_REQUIRED"
        if calibration.all_valid
        else "BLOCKED_CALIBRATION_MISSING_OR_STALE"
    )
    blockers.append("STRICT_CALIBRATION_SNAPSHOT_DECODER_NOT_IMPLEMENTED")

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
        "blockers": blockers,
        "next_required_stage": "STRICT_CALIBRATION_SNAPSHOT_DECODER",
        "trajectory_candidate": None,
        "ik_executed": False,
        "route_screen_executed": False,
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
