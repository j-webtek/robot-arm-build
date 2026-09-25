"""Gate the existing coordinate preview with fused image observations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rocell.targets.nominal import load_nominal_target_catalog

from .adapter import inspect
from .coordinate_preview import preview
from .grounded import propose
from .scene_observation import FrameEvidence
from .vision_fusion import fuse


def guarded_preview(request: str, observation: dict[str, Any], *, request_id: str,
                    workspace: Path, frame: FrameEvidence,
                    scene_observation: dict[str, Any],
                    precision_observation: dict[str, Any],
                    evaluated_at_utc: str) -> dict[str, Any]:
    proposal = propose(request_id=request_id, request=request, observation=observation)
    plan = inspect(proposal, observation)
    base = {
        "schema": "rocell.ai_multimodal_coordinate_preview.v0",
        "request_id": request_id,
        "proposal": proposal,
        "plan_result": plan,
        "execution_authorized": False,
        "controller_commands": [],
    }
    if plan["status"] != "accepted":
        return {**base, "status": "blocked", "reason": plan["reason"], "fusion": None, "targets": []}

    target_ids = [
        action["key"] if action["type"] == "press_key" else action["target"]
        for action in plan["action_plan"]["actions"]
        if action["type"] != "verify_phone_state"
    ]
    catalog = load_nominal_target_catalog(workspace)
    decision = fuse(
        frame=frame,
        scene_observation=scene_observation,
        precision_observation=precision_observation,
        device=proposal["device"],
        required_targets=target_ids,
        target_catalog_sha256=catalog.content_sha256,
        evaluated_at_utc=evaluated_at_utc,
    )
    if not decision["accepted"]:
        return {
            **base, "status": "blocked", "reason": "vision_fusion_rejected",
            "fusion": decision, "targets": [],
        }
    coordinates = preview(
        request, observation, request_id=request_id, workspace=workspace,
        visual_observation=precision_observation,
    )
    return {**base, "status": "coordinate_preview", "fusion": decision, "coordinates": coordinates,
            "targets": coordinates["targets"]}
