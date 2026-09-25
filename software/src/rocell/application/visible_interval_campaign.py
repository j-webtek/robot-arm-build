"""Frozen four-leg shoulder campaign around the verified r60 endpoint."""
from __future__ import annotations

import hashlib
import json


PAIR_SUM = 4114
SOURCE_GOALS = (2413, 1701)
SOURCE_POSITIONS = (2415, 1700)
PRIMARY_ROUTE = (2401, 2389, 2401, 2413)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def plan_visible_interval_campaign():
    goals = [[primary, PAIR_SUM-primary] for primary in PRIMARY_ROUTE]
    value = {
        "schema": "rocell.visible_interval_campaign.v1",
        "candidate_revision": 61,
        "purpose": "bounded_midpoint_return_and_repeat_from_verified_r60_endpoint",
        "initial_gate": {
            "goals": list(SOURCE_GOALS),
            "positions": list(SOURCE_POSITIONS),
            "position_tolerance_counts": 1,
        },
        "manifest": {
            "goals": goals,
            "legs": len(goals),
            "pair_sum": PAIR_SUM,
            "roles": ["midpoint_inbound", "lower_endpoint", "midpoint_outbound", "upper_endpoint"],
        },
        "limits": {
            "writes_per_leg": 1,
            "maximum_writes": 4,
            "maximum_selected_anchor_excursion_counts": 32,
            "maximum_neighbor_excursion_counts": 2,
            "speed": 20,
            "acceleration": 1,
            "automatic_retry": False,
            "automatic_return": False,
        },
        "continuation": {
            "fresh_three_sample_baseline_per_leg": True,
            "durable_export_receipt_per_leg": True,
            "stop_on_uncertain_write_or_invalid_feedback": True,
        },
        "claims": {
            "movement_authorized": False,
            "hardware_access_during_planning": False,
            "cartesian_accuracy_verified": False,
            "general_compensation_validated": False,
        },
    }
    value["plan_sha256"] = hashlib.sha256(_canonical(value)).hexdigest()
    return value

