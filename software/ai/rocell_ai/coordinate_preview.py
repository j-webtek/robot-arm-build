"""Resolve a grounded typing request to nominal board-frame target coordinates.

This is a data bridge for motion integration, not a controller command source.
The target catalog is explicitly synthetic and no installed calibration or
collision/IK result is available through this interface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rocell.targets.nominal import TARGET_STATUS, load_nominal_target_catalog

from .adapter import inspect
from .grounded import propose
from .visual_observation import validate as validate_visual_observation


def preview(request: str, observation: dict[str, Any], *, request_id: str, workspace: Path,
            visual_observation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return coordinate candidates, preserving all execution blockers."""

    proposal = propose(request_id=request_id, request=request, observation=observation)
    inspected = inspect(proposal, observation)
    base = {
        "schema": "rocell.ai_coordinate_preview.v0",
        "request_id": request_id,
        "observation_ref": proposal["observation_ref"],
        "proposal": proposal,
        "plan_result": inspected,
        "coordinate_frame": "board",
        "coordinate_unit": "mm",
        "coordinate_source": TARGET_STATUS,
        "execution_authorized": False,
        "controller_commands": [],
    }
    if inspected["status"] != "accepted":
        return {**base, "status": "blocked", "reason": inspected["reason"], "targets": []}

    catalog = load_nominal_target_catalog(workspace)
    device = proposal["device"]
    if catalog.semantic_profile_id_for(device) != inspected["profile_id"]:
        raise ValueError("semantic plan and coordinate catalog profile mismatch")
    visual = None
    if visual_observation is not None:
        visual = validate_visual_observation(visual_observation, device=device, catalog_sha256=catalog.content_sha256)
        if visual["frame_id"] != observation["ref"]:
            raise ValueError("visual frame and request observation differ")
    targets = []
    for action_index, action in enumerate(inspected["action_plan"]["actions"]):
        if action["type"] == "verify_phone_state":
            targets.append({"action_index": action_index, "action": "verify_phone_state", "state": action["state"], "center_board_mm": None})
            continue
        target_id = action["key"] if action["type"] == "press_key" else action["target"]
        region = catalog.resolve(device, target_id)
        center = [region.center.x, region.center.y, region.center.z]
        if visual is not None:
            if target_id not in visual["targets"]:
                raise ValueError(f"visual observation missing {target_id!r}")
            center = visual["targets"][target_id]["center_board_mm"]
            if any(abs(center[index] - nominal) > 30.0 for index, nominal in enumerate((region.center.x, region.center.y))):
                raise ValueError(f"visual target {target_id!r} exceeds displacement bound")
            if center[2] != region.center.z:
                raise ValueError(f"visual target {target_id!r} has unregistered height")
        targets.append({
            "action_index": action_index,
            "action": action["type"],
            "target_id": target_id,
            "center_board_mm": center,
            "nominal_center_board_mm": [region.center.x, region.center.y, region.center.z],
            "nominal_safe_rectangle_board_mm": list(region.safe_rectangle_board_mm),
        })
    return {
        **base,
        "status": "coordinate_preview",
        "plan_hash": inspected["plan_hash"],
        "target_catalog_sha256": catalog.content_sha256,
        "coordinate_source": TARGET_STATUS if visual is None else visual["source"],
        "visual_observation_sha256": None if visual is None else visual["observation_sha256"],
        "targets": targets,
        "missing_before_execution": [
            "measured_target_registration",
            "camera_and_arm_frame_binding",
            "tool_tip_and_contact_calibration",
            "collision_checked_trajectory_and_inverse_kinematics",
            "runtime_motion_authorization",
            "independent_input_verification",
        ],
    }
