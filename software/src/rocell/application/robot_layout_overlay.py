"""Load the documented rank-1 robot-layout sensitivity as an offline overlay."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import math
from pathlib import Path

from rocell.geometry import RigidTransform, Rotation3, Vec3
from rocell.simulation._validation import load_json_object
from rocell.simulation.scenario import VirtualToolCase

from .first_motion_contract import canonical


def promoted_rank1_robot_layout(context, profile_path: Path):
    """Return a scenario using the source-bound, unmeasured rank-1 hypothesis."""
    path = Path(profile_path).resolve(strict=True)
    root = context.workspace.resolve()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("Robot layout profile must be beneath the workspace") from exc
    document = load_json_object(path)
    binding = document.get("binding")
    selection = document.get("selection")
    study = document.get("study_input")
    authority = document.get("authority")
    if (
        document.get("schema") != "rocell.virtual_commissioning_profile.v1"
        or document.get("status") != "UNMEASURED_SENSITIVITY_OVERLAY"
        or document.get("simulation_only") is not True
        or document.get("physical_release_effect") != "NONE"
        or not isinstance(binding, dict)
        or binding.get("system_manifest_id") != context.snapshot.manifest_id
        or binding.get("design_revision") != context.snapshot.design_revision
        or not isinstance(selection, dict)
        or selection.get("rank") != 1
        or selection.get("source_layout_report_hash")
        != "3b65e3bca509f7c7e1583e5801e189639ab9e40cbf30827b71794752cd7259b4"
        or not isinstance(study, dict)
        or study.get("study_input_id") != "reach-944d7463f4c67905"
        or study.get("canonical_context_modified") is not False
        or study.get("physical_release_effect") != "NONE"
        or not isinstance(authority, dict)
        or authority.get("simulation_only") is not True
        or authority.get("live_hardware_access_allowed") is not False
        or authority.get("hardware_commands_generated") != 0
    ):
        raise ValueError("Robot layout profile lost its rank-1 simulation-only contract")
    derived = study.get("derived_solver_transform")
    tools = study.get("route_tool_lengths_mm")
    if not isinstance(derived, dict) or derived.get("transform") != "B_T_Wv":
        raise ValueError("Robot layout profile has no board-to-vendor-world transform")
    matrix = derived.get("matrix_row_major")
    if (
        not isinstance(matrix, list)
        or len(matrix) != 16
        or any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) for value in matrix)
        or matrix[12:] != [0.0, 0.0, 0.0, 1.0]
    ):
        raise ValueError("Robot layout transform must be one finite homogeneous matrix")
    if not isinstance(tools, dict) or tools.get("keyboard") != 120.0:
        raise ValueError("Robot layout profile lost its selected keyboard tool")
    board_T_world = RigidTransform(
        "board", "world",
        Rotation3((matrix[0], matrix[1], matrix[2], matrix[4], matrix[5], matrix[6],
                   matrix[8], matrix[9], matrix[10])),
        Vec3(matrix[3], matrix[7], matrix[11]),
    )
    tool = VirtualToolCase("rank1_unmeasured_keyboard_120mm", -120.0)
    scenario = replace(
        context.scenario,
        board_T_world=board_T_world,
        hand_tcp_to_tip_z_mm=tool.hand_tcp_to_tip_z_mm,
        tool_case_id=tool.case_id,
        tool_cases=(*context.scenario.tool_cases, tool),
    )
    core = {
        "schema": "rocell.robot_layout_sensitivity_overlay.v1",
        "source_profile": relative,
        "source_profile_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_layout_report_hash": selection["source_layout_report_hash"],
        "source_mission_route_coverage_hash": selection["source_mission_route_coverage_hash"],
        "study_input_id": study["study_input_id"],
        "rank": 1,
        "board_T_vendor_world_matrix_row_major": matrix,
        "keyboard_tool_length_mm": 120.0,
        "installed_position_verified": False,
        "installed_tool_verified": False,
        "motion_authorized": False,
        "frozen_geometry_modified": False,
        "physical_release_effect": "NONE",
    }
    return scenario, {**core, "overlay_sha256": hashlib.sha256(canonical(core)).hexdigest()}
