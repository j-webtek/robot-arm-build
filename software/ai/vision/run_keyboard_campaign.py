"""Bounded multi-placement, multi-text offline keyboard rehearsal campaign."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

AI_DIR = Path(__file__).resolve().parents[1]
ROOT = AI_DIR.parents[1]
sys.path.insert(0, str(AI_DIR.parent / "src"))
sys.path.insert(0, str(AI_DIR))

from vision.run_keyboard_rehearsal import run as run_rehearsal  # noqa: E402


DEFAULT_CASES = (
    (1_100_001, "hi", "standard"),
    (1_100_002, "robot", "standard"),
    (1_100_003, "123", "standard"),
    (2_100_001, "arm", "appearance_shift"),
    (2_100_002, "test", "appearance_shift"),
    (2_100_003, "safe", "appearance_shift"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metrics(values: list[float]) -> dict:
    ordered = sorted(values)
    p95 = ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]
    return {"mean": statistics.fmean(values), "p95_nearest_rank": p95,
            "maximum": ordered[-1]}


def _case_summary(result: dict) -> dict:
    route = result["rocell_route"]
    virtual = result["virtual_typing"]
    first = route["task_summary"]["first_failure"]
    return {
        "seed": result["seed"],
        "synthetic_domain": result["synthetic_domain"],
        "requested_text": result["requested_text"],
        "status": result["status"],
        "image_sha256": result["image_sha256"],
        "model_sha256": result["model_sha256"],
        "truth_pose_board": result["vision"]["truth_pose_board"],
        "predicted_pose_board": result["vision"]["predicted_pose_board"],
        "center_error_mm": result["vision"]["center_error_mm"],
        "yaw_error_deg": result["vision"]["yaw_error_deg"],
        "intended_keys": [row["intended_key"] for row in virtual["events"]],
        "virtual_hit_keys": [row["virtual_hit_key"] for row in virtual["events"]],
        "virtual_text_if_all_contacts_reached": virtual["virtual_text_if_all_contacts_reached"],
        "all_intended_keys_hit": virtual["all_intended_keys_hit"],
        "dense_route_all_waypoints_accepted": route["dense_route_all_waypoints_accepted"],
        "evaluated_waypoint_count": route["task_summary"]["evaluated_waypoint_count"],
        "planned_waypoint_count": route["task_summary"]["planned_waypoint_count"],
        "first_route_failure": first,
        "virtual_text_after_screened_route": result["virtual_text_after_screened_route"],
        "rehearsal_sha256": route["rehearsal_sha256"],
    }


def run(checkpoint: Path, cases=DEFAULT_CASES) -> dict:
    selected = tuple(cases)
    if not 1 <= len(selected) <= 24:
        raise ValueError("Campaign requires one to 24 cases")
    if len({seed for seed, _, _ in selected}) != len(selected):
        raise ValueError("Campaign seeds must be unique")
    results = []
    for index, (seed, text, domain) in enumerate(selected):
        if (type(seed) is not int or type(text) is not str or not 1 <= len(text) <= 8
                or domain not in {"standard", "appearance_shift"}):
            raise ValueError("Invalid campaign case")
        result = run_rehearsal(
            request=f'Type "{text}" on the keyboard', checkpoint=checkpoint,
            seed=seed, frame_id=f"campaign-{index:03d}-seed-{seed}",
            park_xy_board_mm=(290.0, 10.0), use_promoted_layout=True,
            domain=domain)
        results.append(_case_summary(result))
    model_hashes = {row["model_sha256"] for row in results}
    if len(model_hashes) != 1:
        raise ValueError("Model identity changed during campaign")
    center_errors = [row["center_error_mm"] for row in results]
    yaw_errors = [row["yaw_error_deg"] for row in results]
    key_hits = sum(row["all_intended_keys_hit"] for row in results)
    route_passes = sum(row["dense_route_all_waypoints_accepted"] for row in results)
    successes = sum(row["status"] == "VIRTUAL_SUCCESS_ROUTE_SCREENED" for row in results)
    domain_summary = {}
    for domain in ("standard", "appearance_shift"):
        rows = [row for row in results if row["synthetic_domain"] == domain]
        if rows:
            domain_summary[domain] = {
                "case_count": len(rows),
                "all_intended_keys_hit_count": sum(row["all_intended_keys_hit"] for row in rows),
                "dense_route_pass_count": sum(row["dense_route_all_waypoints_accepted"] for row in rows),
                "end_to_end_success_count": sum(
                    row["status"] == "VIRTUAL_SUCCESS_ROUTE_SCREENED" for row in rows),
            }
    failure_reasons = Counter(
        row["first_route_failure"]["reason"]
        for row in results if row["first_route_failure"] is not None)
    key_ids = sorted({key for row in results for key in row["intended_keys"]})
    core = {
        "schema": "rocell.ai_keyboard_rehearsal_campaign.v1",
        "campaign_id": "synthetic-multitext-promoted-layout-v1",
        "status": ("ALL_CASES_VIRTUAL_SUCCESS_ROUTE_SCREENED"
                   if successes == len(results) else "CAMPAIGN_GAPS_REPORTED"),
        "case_count": len(results),
        "distinct_seed_count": len(results),
        "distinct_requested_key_count": len(key_ids),
        "requested_key_ids": key_ids,
        "model_sha256": next(iter(model_hashes)),
        "source_sha256": {
            "campaign_runner": _sha256(Path(__file__)),
            "rehearsal_runner": _sha256(AI_DIR / "vision" / "run_keyboard_rehearsal.py"),
            "joint_preview": _sha256(AI_DIR / "vision" / "run_joint_preview.py"),
            "layout_profile": _sha256(ROOT / "software" / "config" /
                                      "virtual_commissioning_profile.json"),
        },
        "metrics": {
            "center_error_mm": _metrics(center_errors),
            "yaw_error_deg": _metrics(yaw_errors),
            "all_intended_keys_hit_count": key_hits,
            "all_intended_keys_hit_rate": key_hits / len(results),
            "dense_route_pass_count": route_passes,
            "dense_route_pass_rate": route_passes / len(results),
            "end_to_end_success_count": successes,
            "end_to_end_success_rate": successes / len(results),
            "total_evaluated_waypoints": sum(row["evaluated_waypoint_count"] for row in results),
            "total_planned_waypoints": sum(row["planned_waypoint_count"] for row in results),
            "route_failure_reasons": dict(sorted(failure_reasons.items())),
            "by_domain": domain_summary,
        },
        "cases": results,
        "real_camera_evaluation": False,
        "physical_execution_authorized": False,
        "hardware_commands": 0,
        "physical_input_events_observed": 0,
        "limitations": [
            "All images, target truth, contacts, and outcomes are synthetic",
            "The selected robot base pose and 120 mm tool are unmeasured sensitivity values",
            "Sampled IK does not prove continuous or full-arm collision-free motion",
        ],
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {**core, "report_sha256": hashlib.sha256(encoded).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the bounded offline keyboard campaign")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.checkpoint)
    payload = json.dumps(result, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes((payload + "\n").encode("utf-8"))
    print(payload)


if __name__ == "__main__":
    main()
