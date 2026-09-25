"""Fail-closed fusion of a scene observation and precision target prediction."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Iterable

from .scene_observation import FrameEvidence, canonical_hash, parse_utc, validate_observation
from .pixel_quality import assess as assess_pixel_quality
from .visual_observation import MODEL_SCHEMA, validate as validate_visual_targets


SCHEMA = "rocell.ai_vision_fusion.v0"
REASONS = {
    "stale_frame", "device_mismatch", "low_scene_confidence", "observer_abstained",
    "lighting_adverse", "blur_adverse", "glare_adverse", "excessive_occlusion",
    "critical_targets_hidden", "layout_unverified", "phone_state_unverified",
    "precision_frame_mismatch", "precision_image_mismatch", "missing_precision_target",
    "pixel_quality_rejected",
}


def fuse(*, frame: FrameEvidence, scene_observation: dict[str, Any],
         precision_observation: dict[str, Any], device: str,
         required_targets: Iterable[str], target_catalog_sha256: str,
         evaluated_at_utc: str, maximum_age_seconds: float = 2.0,
         minimum_scene_confidence: float = 0.85,
         maximum_occlusion_fraction: float = 0.20) -> dict[str, Any]:
    if device not in {"keyboard", "phone"}:
        raise ValueError("device must be keyboard or phone")
    if not isinstance(target_catalog_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", target_catalog_sha256) is None:
        raise ValueError("invalid target catalog hash")
    if maximum_age_seconds < 0:
        raise ValueError("maximum_age_seconds cannot be negative")
    if not 0 <= minimum_scene_confidence <= 1 or not 0 <= maximum_occlusion_fraction <= 1:
        raise ValueError("fusion thresholds must be between zero and one")
    scene = validate_observation(scene_observation, frame=frame)
    precision = validate_visual_targets(
        precision_observation, device=device, catalog_sha256=target_catalog_sha256,
    )
    if precision["schema"] != MODEL_SCHEMA:
        raise ValueError("fusion requires an image-model precision observation")
    targets = tuple(required_targets)
    if not targets or len(targets) > 256 or any(not isinstance(target, str) or not target for target in targets):
        raise ValueError("required_targets must be a bounded nonempty sequence")

    evaluated = parse_utc(evaluated_at_utc, "evaluated_at_utc")
    captured = parse_utc(frame.captured_at_utc, "captured_at_utc")
    age_seconds = (evaluated - captured).total_seconds()
    reasons: list[str] = []
    pixel_quality = assess_pixel_quality(frame)

    if age_seconds < 0 or age_seconds > maximum_age_seconds:
        reasons.append("stale_frame")
    if not pixel_quality["accepted"]:
        reasons.append("pixel_quality_rejected")
    allowed_presence = {device, "both"}
    if scene["device_presence"] not in allowed_presence:
        reasons.append("device_mismatch")
    if scene["confidence"] < minimum_scene_confidence:
        reasons.append("low_scene_confidence")
    if scene["abstain"]:
        reasons.append("observer_abstained")
    if scene["lighting"] != "acceptable":
        reasons.append("lighting_adverse")
    if scene["blur"] not in {"none", "low"}:
        reasons.append("blur_adverse")
    if scene["glare"] not in {"none", "low"}:
        reasons.append("glare_adverse")
    if scene["occlusion_fraction"] > maximum_occlusion_fraction:
        reasons.append("excessive_occlusion")
    if not scene["critical_targets_visible"]:
        reasons.append("critical_targets_hidden")
    if device == "keyboard" and scene["keyboard_layout"] != "us_qwerty":
        reasons.append("layout_unverified")
    if device == "phone" and scene["phone_state"] == "unknown":
        reasons.append("phone_state_unverified")
    if precision["frame_id"] != frame.frame_id:
        reasons.append("precision_frame_mismatch")
    if precision["image_sha256"] != frame.image_sha256:
        reasons.append("precision_image_mismatch")
    if any(target not in precision["targets"] for target in targets):
        reasons.append("missing_precision_target")

    reasons = list(dict.fromkeys(reasons))
    core = {
        "schema": SCHEMA,
        "frame_id": frame.frame_id,
        "image_sha256": frame.image_sha256,
        "evaluated_at_utc": evaluated_at_utc,
        "device": device,
        "required_targets": list(targets),
        "scene_observation_sha256": scene["observation_sha256"],
        "precision_observation_sha256": precision["observation_sha256"],
        "accepted": not reasons,
        "reasons": reasons,
        "frame_age_seconds": age_seconds,
        "thresholds": {
            "maximum_age_seconds": maximum_age_seconds,
            "minimum_scene_confidence": minimum_scene_confidence,
            "maximum_occlusion_fraction": maximum_occlusion_fraction,
        },
        "pixel_quality": pixel_quality,
        "execution_authorized": False,
    }
    return {**core, "decision_sha256": canonical_hash(core)}
