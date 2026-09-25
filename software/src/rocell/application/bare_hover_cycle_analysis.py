"""Offline consistency review of the five manually gated r95 hover legs.

This establishes controller repeatability and separability only. It does not
measure the gripper in board coordinates or validate any physical key center.
"""
from __future__ import annotations

from collections.abc import Sequence
import math

from rocell.kinematics.firmware_reference import forward

from .air_typing_continuation_preview import _angles
from .bare_gripper_hover_preview import SOURCE_GOALS, SOURCE_POSITIONS, TARGETS


def _reference_xyz(counts: Sequence[int]) -> tuple[float, float, float]:
    """Pinned firmware FK result, not an installed-frame measurement."""
    return forward(*_angles(counts)[:4])[:3]


def _delta(a: Sequence[float], b: Sequence[float]) -> list[float]:
    return [round(y - x, 6) for x, y in zip(a, b)]


def analyze(records: Sequence[dict]) -> dict:
    if len(records) != len(TARGETS):
        raise ValueError("Five verified r95 hover records required")
    boot = records[0].get("boot_id")
    app = records[0].get("app_sha256")
    if not isinstance(boot, str) or not isinstance(app, str):
        raise ValueError("Missing controller identity")
    rows = []
    prior_after = None
    prior_goals = list(SOURCE_GOALS)
    endpoints = {}
    for leg, (record, target) in enumerate(zip(records, TARGETS), 1):
        before, after = record.get("before"), record.get("after")
        selected = [i for i, (old, new) in enumerate(zip(prior_goals, target))
                    if old != new]
        if (record.get("schema") != "rocell.bare_hover_leg_attempt.v1" or
                record.get("category") != "LEG_VERIFIED" or
                record.get("leg") != leg or record.get("boot_id") != boot or
                record.get("app_sha256") != app or
                record.get("retry_allowed") is not False or
                record.get("automatic_progression") is not False or
                record.get("physical_key_contact") is not False or
                record.get("physical_key_center_verified") is not False or
                record.get("one_write_max") is not True or
                record.get("write_attempted") is not True or
                record.get("selected_joints") != selected or
                record.get("target_goals") != list(target) or
                not isinstance(before, dict) or not isinstance(after, dict) or
                before.get("goals") != prior_goals or
                after.get("goals") != list(target) or
                (prior_after is not None and before != prior_after)):
            raise ValueError(f"r95 hover leg {leg} evidence differs")
        positions_before = before.get("positions")
        positions_after = after.get("positions")
        if (not isinstance(positions_before, list) or
                not isinstance(positions_after, list) or
                len(positions_before) != 7 or len(positions_after) != 7 or
                any(type(value) is not int or not 0 <= value <= 4095
                    for value in positions_before + positions_after) or
                6 in selected):
            raise ValueError(f"r95 hover leg {leg} positions differ")
        if leg == 1 and any(abs(a-b) > 16 for a,b in
                            zip(positions_before, SOURCE_POSITIONS)):
            raise ValueError("r95 hover source differs")
        residuals = [positions_after[i] - target[i] for i in selected]
        unselected = [positions_after[i] - positions_before[i]
                      for i in range(7) if i not in selected]
        if max(map(abs, residuals)) > 12 or any(abs(value) > 16 for value in unselected):
            raise ValueError(f"r95 hover leg {leg} readback outside limits")
        rows.append(dict(leg=leg, selected_joints=selected,
                         maximum_selected_goal_residual_counts=max(map(abs, residuals)),
                         maximum_unselected_position_delta_counts=max(map(abs, unselected), default=0)))
        endpoints[leg] = list(positions_after)
        prior_after, prior_goals = after, list(target)

    # Legs 1/4 share the same hover shape except base; legs 2/5 share clear.
    hover_shape_delta = [endpoints[4][i] - endpoints[1][i] for i in range(1, 7)]
    clear_shape_delta = [endpoints[5][i] - endpoints[2][i] for i in range(1, 7)]
    b_stroke = [endpoints[1][i] - endpoints[2][i] for i in range(1, 5)]
    a_stroke = [endpoints[4][i] - endpoints[5][i] for i in range(1, 5)]
    stroke_difference = [a-b for a,b in zip(a_stroke, b_stroke)]
    b_hover_xyz, b_clear_xyz = map(_reference_xyz, TARGETS[:2])
    a_clear_xyz, a_hover_xyz = map(_reference_xyz, TARGETS[2:4])
    modeled_b_stroke = _delta(b_clear_xyz, b_hover_xyz)
    modeled_a_stroke = _delta(a_clear_xyz, a_hover_xyz)
    modeled_hover_region_delta = _delta(b_hover_xyz, a_hover_xyz)
    modeled_clear_region_delta = _delta(b_clear_xyz, a_clear_xyz)
    return dict(schema="rocell.bare_hover_cycle_analysis.v1",
                status="CONTROLLER_COMPOSITION_CONSISTENT_NOT_BOARD_CALIBRATION",
                boot_id=boot, app_sha256=app, legs=rows,
                maximum_selected_goal_residual_counts=max(
                    row["maximum_selected_goal_residual_counts"] for row in rows),
                hover_nonbase_repeatability_max_counts=max(map(abs, hover_shape_delta)),
                clear_nonbase_repeatability_max_counts=max(map(abs, clear_shape_delta)),
                stroke_vector_b_counts=b_stroke, stroke_vector_a_counts=a_stroke,
                stroke_vector_difference_max_counts=max(map(abs, stroke_difference)),
                corresponding_endpoint_base_separation_counts=dict(
                    hover=endpoints[4][0]-endpoints[1][0],
                    clear=endpoints[5][0]-endpoints[2][0]),
                pinned_firmware_reference_model=dict(
                    status="MODEL_ONLY_NOT_INSTALLED_BOARD_FRAME",
                    b_clear_to_hover_xyz_mm=modeled_b_stroke,
                    a_clear_to_hover_xyz_mm=modeled_a_stroke,
                    b_to_a_hover_xyz_mm=modeled_hover_region_delta,
                    b_to_a_clear_xyz_mm=modeled_clear_region_delta,
                    clear_to_hover_distance_mm=round(math.dist(b_clear_xyz, b_hover_xyz), 6),
                    region_separation_distance_mm=round(math.dist(b_hover_xyz, a_hover_xyz), 6)),
                final_positions=endpoints[5], final_goals=list(TARGETS[-1]),
                keyboard_to_board_photo_estimated=True,
                board_to_controller_verified=False,
                bare_gripper_reference_point_measured=False,
                physical_key_centers_verified=False, motion_authorized=False)
