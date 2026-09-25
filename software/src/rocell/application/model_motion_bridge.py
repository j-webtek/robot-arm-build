"""Offline bridge from model coordinates to a screened nominal motion request.

This module deliberately stops before IK-to-controller compilation because the
physical calibration registry and controller-frame correlation are not commissioned.
It never imports a transport and cannot write to hardware.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from rocell.models import Interaction, ModelMotionProposal, Point3Mm
from rocell.targets import NominalTargetCatalog, load_nominal_target_catalog


class ModelMotionBridgeError(ValueError):
    """A valid model proposal cannot enter the deterministic planning boundary."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _board_target(
    proposal: ModelMotionProposal,
    catalog: NominalTargetCatalog,
) -> Point3Mm:
    if proposal.target.frame == "board":
        return proposal.target
    return catalog.local_to_board(proposal.target, device=proposal.device.value)


def compile_model_motion_proposal(
    proposal: ModelMotionProposal,
    catalog: NominalTargetCatalog,
    *,
    minimum_confidence: float = 0.9,
    plane_tolerance_mm: float = 1e-6,
) -> dict[str, Any]:
    """Validate one model coordinate against the frozen nominal device map.

    The resulting waypoints are board-frame planning requests. They are not joint
    targets or controller commands. A later calibrated planner may consume this
    artifact without allowing the model to access the transport.
    """

    if not isinstance(proposal, ModelMotionProposal):
        raise TypeError("proposal must be a ModelMotionProposal")
    if not isinstance(catalog, NominalTargetCatalog):
        raise TypeError("catalog must be a NominalTargetCatalog")
    if isinstance(minimum_confidence, bool) or not isinstance(minimum_confidence, (int, float)):
        raise TypeError("minimum_confidence must be numeric")
    threshold = float(minimum_confidence)
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("minimum_confidence must be in [0, 1]")
    if proposal.confidence < threshold:
        raise ModelMotionBridgeError(
            f"proposal confidence {proposal.confidence} is below {threshold}"
        )

    nominal = catalog.resolve(proposal.device.value, proposal.target_id)
    board = _board_target(proposal, catalog)
    left, front, right, rear = nominal.safe_rectangle_board_mm
    if not (left <= board.x <= right and front <= board.y <= rear):
        raise ModelMotionBridgeError(
            "model coordinate is outside the named target's nominal safe rectangle"
        )
    if abs(board.z - nominal.center.z) > plane_tolerance_mm:
        raise ModelMotionBridgeError(
            "model coordinate does not lie on the named target's nominal surface plane"
        )

    surface = {"frame": "board", "x": board.x, "y": board.y, "z": board.z}
    hover = {
        "frame": "board",
        "x": board.x,
        "y": board.y,
        "z": board.z + proposal.approach_clearance_mm,
    }
    if proposal.interaction is Interaction.HOVER:
        waypoints = [{"phase": "HOVER_DESTINATION", "point_mm": hover}]
    else:
        waypoints = [
            {"phase": "APPROACH", "point_mm": hover},
            {"phase": "CONTACT_CANDIDATE", "point_mm": surface},
            {"phase": "RETRACT", "point_mm": hover},
        ]

    report: dict[str, Any] = {
        "schema": "rocell.model_motion_candidate.v1",
        "status": "ACCEPTED_OFFLINE_NOMINAL_REQUIRES_CALIBRATED_PLANNER",
        "proposal_sha256": proposal.proposal_sha256,
        "target_catalog_sha256": catalog.content_sha256,
        "source": proposal.source.to_dict(),
        "device": proposal.device.value,
        "target_id": proposal.target_id,
        "interaction": proposal.interaction.value,
        "speed_class": proposal.speed_class.value,
        "confidence": proposal.confidence,
        "minimum_confidence": threshold,
        "proposed_surface_target_board_mm": surface,
        "nominal_target_center_board_mm": {
            "frame": "board",
            "x": nominal.center.x,
            "y": nominal.center.y,
            "z": nominal.center.z,
        },
        "nominal_delta_mm": {
            "x": board.x - nominal.center.x,
            "y": board.y - nominal.center.y,
            "z": board.z - nominal.center.z,
        },
        "nominal_safe_rectangle_board_mm": [left, front, right, rear],
        "requested_waypoints": waypoints,
        "planner_handoff": {
            "required_next_stage": "CALIBRATED_IK_AND_FULL_ROUTE_SCREENING",
            "coordinate_frame": "board",
            "controller_frame_correlation_required": True,
            "tool_transform_required": True,
        },
        "controller_commands": [],
        "hardware_commands_generated": 0,
        "hardware_access": False,
        "physical_authority": False,
        "limitations": [
            "Nominal target map is synthetic and unmeasured",
            "No physical device-placement transform is commissioned",
            "No board-to-controller correlation is commissioned",
            "No IK, full-arm collision, cable, timing, or smoothness screening performed",
        ],
    }
    return {
        **report,
        "candidate_sha256": hashlib.sha256(_canonical(report)).hexdigest(),
    }


def compile_mapping(
    value: object,
    *,
    workspace: Path,
    minimum_confidence: float = 0.9,
) -> dict[str, Any]:
    proposal = ModelMotionProposal.from_mapping(value)
    catalog = load_nominal_target_catalog(Path(workspace))
    return compile_model_motion_proposal(
        proposal,
        catalog,
        minimum_confidence=minimum_confidence,
    )


def _without_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ModelMotionBridgeError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--minimum-confidence", type=float, default=0.9)
    args = parser.parse_args(argv)
    document = json.loads(
        args.proposal.read_text(encoding="utf-8"),
        object_pairs_hook=_without_duplicate_keys,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ModelMotionBridgeError(f"nonfinite JSON constant {value!r}")
        ),
    )
    report = compile_mapping(
        document,
        workspace=args.workspace,
        minimum_confidence=args.minimum_confidence,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through subprocess use
    raise SystemExit(main())
