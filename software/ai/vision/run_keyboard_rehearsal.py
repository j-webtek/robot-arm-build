"""Offline image-to-keyboard rehearsal with independent virtual key-hit truth."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

AI_DIR = Path(__file__).resolve().parents[1]
ROOT = AI_DIR.parents[1]
sys.path.insert(0, str(AI_DIR.parent / "src"))
sys.path.insert(0, str(AI_DIR))

from rocell.application.static_simulation_context import load_static_simulation_context  # noqa: E402
from rocell.application.static_task_rehearsal import run_static_task_rehearsal  # noqa: E402
from rocell.typing.development_profiles import development_keyboard_profile  # noqa: E402
from vision.run_joint_preview import run as joint_preview  # noqa: E402
from vision.synthetic_keyboard import NOMINAL_CENTER_MM, transform_target  # noqa: E402


def virtual_key_at(x: float, y: float, catalog, truth_pose: tuple[float, float, float]) -> str | None:
    """Resolve a board point against hidden synthetic key rectangles."""
    center_x, center_y, yaw = truth_pose
    cosine, sine = math.cos(yaw), math.sin(yaw)
    dx, dy = x - center_x, y - center_y
    nominal_x = NOMINAL_CENTER_MM[0] + cosine * dx + sine * dy
    nominal_y = NOMINAL_CENTER_MM[1] - sine * dx + cosine * dy
    hits = []
    for key, region in catalog.keyboard_targets.items():
        local_x, local_y = nominal_x - region.center.x, nominal_y - region.center.y
        if abs(local_x) <= region.half_extent_x_mm and abs(local_y) <= region.half_extent_y_mm:
            hits.append((math.hypot(local_x / region.half_extent_x_mm,
                                    local_y / region.half_extent_y_mm), key))
    return min(hits)[1] if hits else None


def evaluate_virtual_typing(targets: list[dict], catalog, truth_pose: tuple[float, float, float],
                            requested_text: str) -> dict:
    inverse = {keys[0]: char for char, keys in development_keyboard_profile().character_keys.items()
               if len(keys) == 1}
    events = []
    for target in targets:
        if target.get("action") != "press_key":
            raise ValueError("Keyboard rehearsal requires only press_key actions")
        x, y, _ = target["center_board_mm"]
        hit = virtual_key_at(x, y, catalog, truth_pose)
        events.append({"intended_key": target["target_id"], "virtual_hit_key": hit,
                       "hit_intended_key": hit == target["target_id"],
                       "predicted_contact_board_xy_mm": [x, y]})
    potential_text = "".join(inverse.get(row["virtual_hit_key"], "") for row in events)
    return {"requested_text": requested_text, "virtual_text_if_all_contacts_reached": potential_text,
            "all_intended_keys_hit": all(row["hit_intended_key"] for row in events),
            "events": events,
            "interpretation": "Hidden synthetic layout hit test; no arm movement or input event occurred"}


def run(*, request: str, checkpoint: Path, seed: int, frame_id: str,
        image_output: Path | None = None, photo_path: Path | None = None,
        park_xy_board_mm: tuple[float, float] | None = None,
        use_promoted_layout: bool = False, domain: str = "standard") -> dict:
    joint = joint_preview(request=request, checkpoint=checkpoint, seed=seed,
                          frame_id=frame_id, image_output=image_output, photo_path=photo_path,
                          domain=domain)
    coordinates = joint["coordinate_preview"]
    base = {"schema": "rocell.ai_offline_keyboard_rehearsal.v1", "seed": seed,
            "request": request, "synthetic_domain": domain,
            "image_sha256": joint["image_sha256"],
            "model_sha256": joint["model_sha256"],
            "physical_execution_authorized": False, "hardware_commands": 0,
            "physical_input_events_observed": 0}
    if coordinates["status"] != "coordinate_preview":
        return {**base, "status": "INTENT_BLOCKED", "reason": coordinates["reason"]}
    proposal = coordinates["proposal"]
    if proposal["device"] != "keyboard":
        return {**base, "status": "UNSUPPORTED_DEVICE", "reason": "keyboard_only_rehearsal"}
    text = proposal["text"]
    if len(text) > 8:
        return {**base, "status": "TEXT_TOO_LONG_FOR_STATIC_REHEARSAL",
                "reason": "static_route_limit_eight_characters"}
    context = load_static_simulation_context(ROOT)
    from rocell.targets.nominal import load_nominal_target_catalog
    legacy = load_nominal_target_catalog(ROOT)
    if coordinates["target_catalog_sha256"] != legacy.content_sha256:
        raise ValueError("Image coordinate catalog changed")
    for key, region in context.targets.keyboard_targets.items():
        old = legacy.keyboard_targets[key]
        if region.center != old.center or (region.half_extent_x_mm, region.half_extent_y_mm) != (
                old.half_extent_x_mm, old.half_extent_y_mm):
            raise ValueError("Static and image key geometry differ")
    predicted = joint["predicted_keyboard_pose_board"]
    for target in coordinates["targets"]:
        region = context.targets.keyboard_targets[target["target_id"]]
        expected = transform_target(region.center.x, region.center.y, predicted[:2], predicted[2])
        if math.dist(expected, target["center_board_mm"][:2]) > 1e-6:
            raise ValueError("Selected coordinate differs from image model pose")
    estimate = {"schema": "rocell.synthetic_model_keyboard_estimate.v1",
                "source": "SYNTHETIC_IMAGE_MODEL_PREDICTION", "motion_authorized": False,
                "target_catalog_sha256": context.targets.content_sha256,
                "image_sha256": joint["image_sha256"], "model_sha256": joint["model_sha256"],
                "center_board_xy_mm": predicted[:2], "yaw_rad": predicted[2]}
    truth = tuple(joint["simulator_truth_keyboard_pose_board"])
    virtual = evaluate_virtual_typing(coordinates["targets"], context.targets, truth, text)
    rehearsal = run_static_task_rehearsal(context, device="keyboard", text=text, dense=True,
                                           keyboard_model_estimate=estimate,
                                           park_xy_board_mm=park_xy_board_mm,
                                           robot_layout_profile=(
                                               ROOT / "software" / "config" /
                                               "virtual_commissioning_profile.json"
                                               if use_promoted_layout else None))
    if rehearsal["task_summary"]["requested_targets"] != [
            target["target_id"] for target in coordinates["targets"]]:
        raise ValueError("Static and image semantic plans disagree")
    route_pass = rehearsal["dense_route"]["all_waypoints_accepted"] is True
    hit = virtual["all_intended_keys_hit"]
    status = ("VIRTUAL_SUCCESS_ROUTE_SCREENED" if route_pass and hit else
              "ROUTE_BLOCKED_AND_VIRTUAL_KEY_MISS" if not route_pass and not hit else
              "VIRTUAL_KEY_MISS" if not hit else "ROUTE_BLOCKED")
    result = {**base, "status": status, "requested_text": text,
              "vision": {"truth_pose_board": list(truth), "predicted_pose_board": predicted,
                         "center_error_mm": joint["center_error_mm"],
                         "yaw_error_deg": joint["yaw_error_deg"]},
              "virtual_typing": virtual,
              "rocell_route": {"status": rehearsal["status"],
                               "park_selection": rehearsal["park_selection"],
                               "robot_layout_overlay": rehearsal["robot_layout_overlay"],
                               "geometry_all_checks_pass": rehearsal["geometry"]["all_checks_pass"],
                               "sampled_ik_all_converged": rehearsal["ik"]["all_sampled_converged"],
                               "dense_route_all_waypoints_accepted": route_pass,
                               "task_summary": rehearsal["task_summary"],
                               "rehearsal_sha256": rehearsal["report_sha256"]},
              "virtual_text_after_screened_route": virtual["virtual_text_if_all_contacts_reached"]
              if route_pass else None,
              "limitations": ["Synthetic image and hidden synthetic key layout only",
                              "Pinned arm kinematics and sampled route checks, no hardware execution",
                              *(["Robot base pose and route tool are unmeasured sensitivity values"]
                                 if use_promoted_layout else []),
                              "Virtual key hits are not observed physical input events"]}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline image-to-keyboard arm rehearsal")
    parser.add_argument("--request", required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1_000_001)
    parser.add_argument("--frame-id", default="synthetic-camera-frame-001")
    parser.add_argument("--image-output", type=Path)
    parser.add_argument("--photo-path", type=Path)
    parser.add_argument("--report-output", type=Path)
    parser.add_argument("--park-x-mm", type=float)
    parser.add_argument("--park-y-mm", type=float)
    parser.add_argument("--use-promoted-layout", action="store_true")
    parser.add_argument("--domain", choices=("standard", "appearance_shift"), default="standard")
    args = parser.parse_args()
    if (args.park_x_mm is None) != (args.park_y_mm is None):
        parser.error("--park-x-mm and --park-y-mm must be supplied together")
    result = run(request=args.request, checkpoint=args.checkpoint, seed=args.seed,
                 frame_id=args.frame_id, image_output=args.image_output,
                 photo_path=args.photo_path,
                 park_xy_board_mm=None if args.park_x_mm is None else
                 (args.park_x_mm, args.park_y_mm),
                 use_promoted_layout=args.use_promoted_layout, domain=args.domain)
    payload = json.dumps(result, indent=2)
    if args.report_output is not None:
        args.report_output.parent.mkdir(parents=True, exist_ok=True)
        args.report_output.write_bytes((payload + "\n").encode("utf-8"))
    print(payload)


if __name__ == "__main__":
    main()
