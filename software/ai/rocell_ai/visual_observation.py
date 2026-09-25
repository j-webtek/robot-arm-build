"""Synthetic visual-target observation contract for intent/motion integration.

The simulator applies a known planar displacement to nominal targets. It does
not infer positions from pixels; a future image detector must produce the same
validated record from an actual frame and measured registration.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from rocell.targets.nominal import load_nominal_target_catalog


SCHEMA = "rocell.ai_visual_targets.v0"
MIN_CONFIDENCE = 0.95


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def simulate(workspace: Path, *, device: str, frame_id: str, offset_x_mm: float = 0.0, offset_y_mm: float = 0.0) -> dict[str, Any]:
    """Make a deterministic test observation with displaced visual targets."""
    if not isinstance(frame_id, str) or not frame_id.strip():
        raise ValueError("frame_id is required")
    if device not in {"keyboard", "phone"}:
        raise ValueError("device must be keyboard or phone")
    dx, dy = _finite(offset_x_mm, "offset_x_mm"), _finite(offset_y_mm, "offset_y_mm")
    if abs(dx) > 30 or abs(dy) > 30:
        raise ValueError("simulated displacement exceeds 30 mm")
    catalog = load_nominal_target_catalog(workspace)
    regions = catalog.keyboard_targets if device == "keyboard" else catalog.phone_targets
    targets = {
        target_id: {
            "center_board_mm": [region.center.x + dx, region.center.y + dy, region.center.z],
            "confidence": 1.0,
        }
        for target_id, region in sorted(regions.items())
    }
    core = {
        "schema": SCHEMA,
        "frame_id": frame_id,
        "device": device,
        "coordinate_frame": "board",
        "coordinate_unit": "mm",
        "source": "SYNTHETIC_DISPLACED_NOMINAL_TARGETS",
        "target_catalog_sha256": catalog.content_sha256,
        "targets": targets,
    }
    return {**core, "observation_sha256": _hash(core)}


def validate(value: Any, *, device: str, catalog_sha256: str) -> dict[str, Any]:
    """Reject malformed, mixed-source, ambiguous, or weak observations."""
    if not isinstance(value, dict) or set(value) != {
        "schema", "frame_id", "device", "coordinate_frame", "coordinate_unit",
        "source", "target_catalog_sha256", "targets", "observation_sha256",
    }:
        raise ValueError("visual observation has invalid fields")
    if value["schema"] != SCHEMA or value["device"] != device or value["target_catalog_sha256"] != catalog_sha256:
        raise ValueError("visual observation identity mismatch")
    if value["coordinate_frame"] != "board" or value["coordinate_unit"] != "mm":
        raise ValueError("visual observation must use board millimetres")
    if value["source"] != "SYNTHETIC_DISPLACED_NOMINAL_TARGETS":
        raise ValueError("unqualified visual source")
    if not isinstance(value["frame_id"], str) or not value["frame_id"].strip():
        raise ValueError("visual frame_id is required")
    targets = value["targets"]
    if not isinstance(targets, dict) or not targets or len(targets) > 256:
        raise ValueError("visual targets must be a bounded object")
    for name, target in targets.items():
        if not isinstance(name, str) or not name or not isinstance(target, dict) or set(target) != {"center_board_mm", "confidence"}:
            raise ValueError("visual target has invalid fields")
        point = target["center_board_mm"]
        if not isinstance(point, list) or len(point) != 3:
            raise ValueError("visual target needs three coordinates")
        for index, coordinate in enumerate(point):
            if abs(_finite(coordinate, f"visual coordinate {index}")) > 1000:
                raise ValueError("visual coordinate outside workcell bound")
        confidence = _finite(target["confidence"], "visual confidence")
        if not MIN_CONFIDENCE <= confidence <= 1.0:
            raise ValueError("visual confidence below threshold")
    core = {key: item for key, item in value.items() if key != "observation_sha256"}
    if value["observation_sha256"] != _hash(core):
        raise ValueError("visual observation hash mismatch")
    return value
