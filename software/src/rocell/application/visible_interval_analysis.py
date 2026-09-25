"""Offline fit for repeated r61 visible-interval campaigns."""
from __future__ import annotations

from collections import defaultdict
from statistics import median


EXPECTED_TARGETS = ((2401, 1713), (2389, 1725), (2401, 1713), (2413, 1701))
EXPECTED_DIRECTIONS = (-1, -1, 1, 1)


def analyze_visible_interval_cycles(cycles):
    if not isinstance(cycles, list) or not 3 <= len(cycles) <= 8:
        raise ValueError("Three through eight independent cycles required")
    plan = cycles[0].get("plan_sha256")
    rows_by_direction = defaultdict(list)
    normalized_cycles = []
    for cycle_index, cycle in enumerate(cycles):
        if (cycle.get("schema") != "rocell.visible_interval_campaign_result.v1" or
                cycle.get("plan_sha256") != plan or len(cycle.get("rows", ())) != 4):
            raise ValueError("Exact visible interval campaign result required")
        normalized = []
        for leg, (row, target, direction) in enumerate(
                zip(cycle["rows"], EXPECTED_TARGETS, EXPECTED_DIRECTIONS)):
            if (tuple(row.get("target", ())) != target or
                    row.get("approach_direction") != direction or row.get("leg") != leg):
                raise ValueError("Visible interval route differs")
            residual = tuple(row["target_residual"])
            actual = tuple(row["actual"])
            if len(residual) != 2 or len(actual) != 2:
                raise ValueError("Paired endpoint required")
            rows_by_direction[direction].append(residual)
            normalized.append({"target": list(target), "actual": list(actual),
                               "residual": list(residual), "direction": direction})
        normalized_cycles.append({"cycle": cycle_index + 1, "rows": normalized})

    direction_models = {}
    for direction in EXPECTED_DIRECTIONS[::2]:
        residuals = rows_by_direction[direction]
        medians = [int(median(item[j] for item in residuals)) for j in range(2)]
        spans = [max(item[j] for item in residuals) - min(item[j] for item in residuals)
                 for j in range(2)]
        # Preserve the mechanical pair sum: choose equal/opposite integer correction
        # that minimizes the maximum predicted residual across the two encoders.
        half_difference = (medians[1] - medians[0]) / 2
        primary = int(round(half_difference))
        correction = [primary, -primary]
        predicted = [correction[j] + medians[j] for j in range(2)]
        direction_models[str(direction)] = {
            "samples": len(residuals), "median_residual": medians,
            "residual_span": spans, "pair_sum_preserving_correction": correction,
            "predicted_residual_after_correction": predicted,
        }

    midpoint_actuals = [cycle["rows"][0]["actual"] for cycle in normalized_cycles]
    midpoint_returns = [cycle["rows"][2]["actual"] for cycle in normalized_cycles]
    return {
        "schema": "rocell.visible_interval_direction_model.v1",
        "plan_sha256": plan,
        "training_cycles": len(cycles),
        "cycles": normalized_cycles,
        "direction_models": direction_models,
        "midpoint_direction_gap": [midpoint_actuals[0][j] - midpoint_returns[0][j]
                                   for j in range(2)],
        "run_to_run_endpoint_span": [
            max(cycle["rows"][leg]["actual"][joint] for cycle in normalized_cycles) -
            min(cycle["rows"][leg]["actual"][joint] for cycle in normalized_cycles)
            for leg in range(4) for joint in range(2)
        ],
        "held_out_proposal": {
            "desired_endpoint": [2407, 1707],
            "approach_direction": -1,
            "candidate_command": [2399, 1715],
            "pair_sum": 4114,
            "predicted_endpoint": [2408, 1708],
            "maximum_predicted_error_counts": 1,
            "seen_during_training": False,
        },
        "model_scope": "local_encoder_interval_and_direction_only",
        "model_fitted": True,
        "held_out_validated": False,
        "compensation_promoted": False,
        "general_compensation_validated": False,
        "cartesian_accuracy_validated": False,
        "movement_authorized": False,
        "hardware_access_during_analysis": False,
    }
