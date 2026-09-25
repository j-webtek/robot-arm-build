"""Offline consistency review of the five manually gated r94 B-cycle legs.

Controller readbacks are evidence of servo positions, not measured tool or key
positions. This module has no hardware path or motion authority.
"""
from __future__ import annotations

from collections.abc import Sequence

from .ghost_typing_resume_preview import SOURCE_GOALS, SOURCE_POSITIONS, TARGETS


def analyze(records: Sequence[dict]) -> dict:
    if len(records) != len(TARGETS):
        raise ValueError("Five verified B-cycle records required")
    boot = records[0].get("boot_id")
    app = records[0].get("app_sha256")
    if not isinstance(boot, str) or not isinstance(app, str):
        raise ValueError("Missing controller identity")
    rows = []
    prior_after = None
    prior_goals = list(SOURCE_GOALS)
    for leg, (record, target) in enumerate(zip(records, TARGETS), 1):
        before = record.get("before")
        after = record.get("after")
        selected = [i for i, (old, new) in enumerate(zip(prior_goals, target))
                    if old != new]
        if (record.get("schema") != "rocell.ghost_b_leg_attempt.v1" or
                record.get("category") != "LEG_VERIFIED" or
                record.get("leg") != leg or
                record.get("boot_id") != boot or
                record.get("app_sha256") != app or
                record.get("retry_allowed") is not False or
                record.get("automatic_progression") is not False or
                record.get("physical_key_contact") is not False or
                record.get("one_write_max") is not True or
                record.get("write_attempted") is not True or
                record.get("selected_joints") != selected or
                record.get("target_goals") != list(target) or
                not isinstance(before, dict) or not isinstance(after, dict) or
                before.get("goals") != prior_goals or
                after.get("goals") != list(target) or
                (prior_after is not None and before != prior_after)):
            raise ValueError(f"B-cycle leg {leg} evidence differs")
        positions_before = before.get("positions")
        positions_after = after.get("positions")
        if (not isinstance(positions_before, list) or
                not isinstance(positions_after, list) or
                len(positions_before) != 7 or len(positions_after) != 7 or
                any(type(v) is not int or not 0 <= v <= 4095
                    for v in positions_before + positions_after) or
                6 in selected):
            raise ValueError(f"B-cycle leg {leg} positions differ")
        if (leg == 1 and any(abs(a - b) > 16 for a, b in
                             zip(positions_before, SOURCE_POSITIONS))):
            raise ValueError("B-cycle source position differs")
        residual = [positions_after[i] - target[i] for i in selected]
        unselected_delta = [positions_after[i] - positions_before[i]
                            for i in range(7) if i not in selected]
        if max(map(abs, residual)) > 12 or any(abs(v) > 16 for v in unselected_delta):
            raise ValueError(f"B-cycle leg {leg} readback outside limits")
        rows.append(dict(leg=leg, selected_joints=selected,
                         selected_goal_step_counts=sum(
                             abs(target[i] - prior_goals[i]) for i in selected),
                         maximum_selected_goal_residual_counts=max(map(abs, residual)),
                         maximum_unselected_position_delta_counts=max(
                             map(abs, unselected_delta), default=0)))
        prior_after = after
        prior_goals = list(target)
    return dict(schema="rocell.ghost_b_cycle_analysis.v1",
                status="CONTROLLER_SEQUENCE_CONSISTENT_NOT_PHYSICAL_KEY_VALIDATION",
                boot_id=boot, app_sha256=app, legs=rows,
                maximum_selected_goal_residual_counts=max(
                    row["maximum_selected_goal_residual_counts"] for row in rows),
                total_selected_goal_step_counts=sum(
                    row["selected_goal_step_counts"] for row in rows),
                final_positions=prior_after["positions"],
                final_goals=prior_after["goals"],
                keyboard_registered=False, tool_geometry_measured=False,
                physical_key_contact_verified=False, motion_authorized=False)
