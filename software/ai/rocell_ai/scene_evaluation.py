"""Evaluate a scene observer on the provenance-marked real photo seed."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

from .scene_observation import FrameEvidence, VisionObserver, canonical_hash, validate_observation


def evaluate_photo_seed(*, observer: VisionObserver, manifest_path: Path, labels_path: Path,
                        raw_directory: Path, captured_at_utc: str | None = None) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "rocell.ai_real_photo_seed_manifest.v0":
        raise ValueError("unsupported real photo manifest")
    if labels.get("schema") != "rocell.ai_real_photo_seed_labels.v0":
        raise ValueError("unsupported real photo labels")
    if labels.get("manifest") != manifest_path.name:
        raise ValueError("photo labels do not bind the manifest")
    label_rows = {row["id"]: row for row in labels["rows"]}
    timestamp = captured_at_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rows: list[dict[str, Any]] = []
    for photo in manifest["photos"]:
        path = raw_directory / photo["file"]
        image_bytes = path.read_bytes()
        if hashlib.sha256(image_bytes).hexdigest() != photo["sha256"] or len(image_bytes) != photo["bytes"]:
            raise ValueError(f"photo source mismatch for {photo['id']}")
        frame = FrameEvidence(photo["id"], timestamp, image_bytes)
        started = perf_counter()
        observation = observer.observe(frame)
        latency_ms = (perf_counter() - started) * 1000
        validate_observation(observation, frame=frame)
        label = label_rows[photo["id"]]
        keyboard_expected = any(item.startswith("keyboard") for item in label["visible"])
        keyboard_detected = observation["device_presence"] in {"keyboard", "both"}
        rows.append({
            "id": photo["id"],
            "source_sha256": photo["sha256"],
            "view": label["view"],
            "label_use": label["use"],
            "keyboard_expected_from_agent_label": keyboard_expected,
            "keyboard_detected": keyboard_detected,
            "keyboard_detection_matches_agent_label": keyboard_detected == keyboard_expected,
            "latency_ms": round(latency_ms, 3),
            "observation": observation,
        })
    ordered_latency = sorted(row["latency_ms"] for row in rows)
    detected = sum(row["keyboard_detection_matches_agent_label"] for row in rows)
    abstained = sum(row["observation"]["abstain"] for row in rows)
    core = {
        "schema": "rocell.ai_scene_observer_photo_seed_evaluation.v0",
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "labels_sha256": hashlib.sha256(labels_path.read_bytes()).hexdigest(),
        "capture_group": manifest["capture_group"],
        "case_count": len(rows),
        "keyboard_detection_matches": detected,
        "keyboard_detection_rate": detected / len(rows),
        "abstention_count": abstained,
        "median_latency_ms": round(median(ordered_latency), 3),
        "maximum_latency_ms": max(ordered_latency),
        "rows": rows,
        "human_reviewed_labels": labels["human_reviewed"],
        "coordinate_truth_available": labels["coordinates_labeled"],
        "deployment_camera_evaluation": False,
        "physical_execution_authorized": False,
        "hardware_commands": 0,
        "limitations": [
            "The labels are agent-authored and not independently reviewed",
            "All images are one correlated handheld development capture group",
            "The photos are not captures from the selected static B0477 camera",
            "No measured coordinates, calibration truth, phone scenes, or adverse-scene negatives exist",
        ],
    }
    return {**core, "report_sha256": canonical_hash(core)}
