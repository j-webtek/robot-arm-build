"""Deterministic, conservative image-quality checks before learned inference."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

from .scene_observation import FrameEvidence, canonical_hash


def assess(frame: FrameEvidence) -> dict[str, Any]:
    reasons: list[str] = []
    metrics: dict[str, float] = {}
    try:
        image = Image.open(BytesIO(frame.image_bytes))
        image.load()
        gray = image.convert("L")
        gray.thumbnail((512, 512))
        statistics = ImageStat.Stat(gray)
        histogram = gray.histogram()
        count = float(sum(histogram))
        edge_variance = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).var[0]
        metrics = {
            "mean_luminance": round(statistics.mean[0], 6),
            "luminance_stddev": round(statistics.stddev[0], 6),
            "edge_variance": round(edge_variance, 6),
            "dark_pixel_fraction": round(sum(histogram[:25]) / count, 6),
            "bright_pixel_fraction": round(sum(histogram[245:]) / count, 6),
        }
        if metrics["mean_luminance"] < 25:
            reasons.append("mean_too_dark")
        if metrics["mean_luminance"] > 245:
            reasons.append("mean_overexposed")
        if metrics["luminance_stddev"] < 10:
            reasons.append("low_dynamic_range")
        if metrics["edge_variance"] < 300:
            reasons.append("low_edge_energy")
        if metrics["dark_pixel_fraction"] > 0.40:
            reasons.append("excessive_dark_area")
        if metrics["bright_pixel_fraction"] > 0.20:
            reasons.append("excessive_bright_area")
    except (OSError, UnidentifiedImageError, ValueError):
        reasons.append("invalid_image")
    core = {
        "schema": "rocell.ai_pixel_quality.v0",
        "frame_id": frame.frame_id,
        "image_sha256": frame.image_sha256,
        "metrics": metrics,
        "accepted": not reasons,
        "reasons": reasons,
        "threshold_profile": "development_stress_v0",
        "physical_calibration": False,
    }
    return {**core, "assessment_sha256": canonical_hash(core)}
