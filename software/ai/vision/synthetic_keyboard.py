"""Render a variable keyboard workcell image with exact simulated pose labels."""

from __future__ import annotations

import math
from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from rocell.targets.nominal import NominalTargetCatalog, load_nominal_target_catalog


BOARD_WIDTH_MM = 610.0
BOARD_DEPTH_MM = 457.0
IMAGE_SIZE = (256, 192)
NOMINAL_CENTER_MM = (242.5, 158.5)  # RoCell's unrotated nominal target-map center
PHOTO_STUDY_CENTER_MM = (235.0, 154.0)  # approximate, not a measured installation
KEYBOARD_HALF_SIZE_MM = (157.5, 73.5)
PHOTO_05_CROP_QUAD_PX = (1120, 260, 870, 2330, 2230, 2340, 2110, 260)


def transform_target(x_mm: float, y_mm: float, center_mm: tuple[float, float], angle_rad: float) -> tuple[float, float]:
    dx, dy = x_mm - NOMINAL_CENTER_MM[0], y_mm - NOMINAL_CENTER_MM[1]
    cosine, sine = math.cos(angle_rad), math.sin(angle_rad)
    return center_mm[0] + cosine * dx - sine * dy, center_mm[1] + sine * dx + cosine * dy


def _pixel(point_mm: tuple[float, float]) -> tuple[float, float]:
    return point_mm[0] * IMAGE_SIZE[0] / BOARD_WIDTH_MM, point_mm[1] * IMAGE_SIZE[1] / BOARD_DEPTH_MM


def _rectangle_points(center_mm: tuple[float, float], half_size_mm: tuple[float, float], angle_rad: float) -> list[tuple[float, float]]:
    cosine, sine = math.cos(angle_rad), math.sin(angle_rad)
    points = []
    for dx, dy in ((-half_size_mm[0], -half_size_mm[1]), (half_size_mm[0], -half_size_mm[1]),
                   (half_size_mm[0], half_size_mm[1]), (-half_size_mm[0], half_size_mm[1])):
        points.append(_pixel((center_mm[0] + cosine * dx - sine * dy,
                              center_mm[1] + sine * dx + cosine * dy)))
    return points


def load_photo_texture(photo_path: Path, expected_sha256: str) -> Image.Image:
    """Rectify an agent-estimated keyboard crop; never call it a key label."""
    import hashlib

    if hashlib.sha256(photo_path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("photo texture source hash mismatch")
    with Image.open(photo_path) as source:
        if source.size != (2880, 3840):
            raise ValueError("photo texture source dimensions changed")
        return source.transform((240, 512), Image.Transform.QUAD,
                                PHOTO_05_CROP_QUAD_PX, Image.Resampling.BICUBIC).rotate(90, expand=True).convert("RGBA")


def render(seed: int, catalog: NominalTargetCatalog, *, domain: str = "standard",
           photo_texture: Image.Image | None = None) -> tuple[Image.Image, tuple[float, float, float]]:
    """Return RGB pixels and (board-x, board-y, yaw-radians) ground truth."""
    if domain not in {"standard", "appearance_shift"}:
        raise ValueError("unknown synthetic image domain")
    rng = random.Random(seed)
    center = (PHOTO_STUDY_CENTER_MM[0] + rng.uniform(-30, 30),
              PHOTO_STUDY_CENTER_MM[1] + rng.uniform(-24, 24))
    # The repo's photo study found key legends approximately half-turned from
    # the nominal board axes. Its source JPEG hash differs from the newly
    # supplied seed, so this is a broad simulation prior, not a training label.
    angle = math.pi + math.radians(rng.uniform(-11, 11))
    background = rng.randint(205, 252)
    image = Image.new("RGB", IMAGE_SIZE, (background, background - rng.randint(0, 10), background - rng.randint(0, 15)))
    draw = ImageDraw.Draw(image)
    # Paper seams and printed reference marks seen in the real seed photos.
    for _ in range(rng.randint(2, 6)):
        x = rng.randrange(IMAGE_SIZE[0])
        y = rng.randrange(IMAGE_SIZE[1])
        tone = rng.randint(165, 205)
        draw.line((x - 4, y, x + 4, y), fill=(tone, tone, tone), width=1)
        draw.line((x, y - 4, x, y + 4), fill=(tone, tone, tone), width=1)
    for _ in range(rng.randint(1, 3)):
        y = rng.randrange(IMAGE_SIZE[1])
        draw.line((0, y, IMAGE_SIZE[0], y + rng.randint(-8, 8)), fill=(190, 187, 177), width=1)
    # Keyboard case and individual dark keys. The geometry is the RoCell nominal
    # catalog, while color/cover/occlusion are approximate photo-inspired cues.
    if photo_texture is not None and rng.random() < 0.55:
        scaled = photo_texture.resize((132, 62), Image.Resampling.BILINEAR)
        rotated = scaled.rotate(-math.degrees(angle), expand=True, resample=Image.Resampling.BICUBIC)
        cx, cy = _pixel(center)
        image.paste(rotated, (round(cx - rotated.width / 2), round(cy - rotated.height / 2)), rotated)
        draw = ImageDraw.Draw(image)
    else:
        draw.polygon(_rectangle_points(center, KEYBOARD_HALF_SIZE_MM, angle), fill=(18, 22, 29))
        for region in catalog.keyboard_targets.values():
            key_center = transform_target(region.center.x, region.center.y, center, angle)
            blue = rng.randint(30, 70)
            draw.polygon(_rectangle_points(key_center, (region.half_extent_x_mm * .89, region.half_extent_y_mm * .84), angle),
                         fill=(blue // 2, blue // 2 + 4, blue))
    # Reflective keyboard cover, ruler-like clutter, and occasional arm shadow.
    if rng.random() < 0.55:
        upper = _pixel(transform_target(385, 213, center, angle))
        lower = _pixel(transform_target(105, 213, center, angle))
        draw.line((*upper, *lower), fill=(105, 119, 128), width=rng.randint(1, 3))
    if rng.random() < 0.6:
        y = rng.choice((rng.randint(4, 25), rng.randint(164, 188)))
        draw.line((rng.randint(-30, 20), y, rng.randint(235, 290), y + rng.randint(-7, 7)),
                  fill=(220, 165, 22), width=rng.randint(3, 6))
    if rng.random() < 0.35:
        x = rng.randint(35, 225)
        draw.line((x, -15, x + rng.randint(-25, 25), rng.randint(45, 110)),
                  fill=(17, 20, 24), width=rng.randint(4, 12))
    if rng.random() < 0.22:
        image = image.filter(ImageFilter.GaussianBlur(rng.uniform(0.2, 0.75)))
    if rng.random() < 0.5:
        image = Image.blend(image, Image.new("RGB", IMAGE_SIZE, (rng.randint(180, 255),) * 3), rng.uniform(0.02, 0.18))
    if domain == "appearance_shift":
        # Separate image style probes dependence on the rendering palette and
        # lighting. It is still synthetic, not a real-camera validation set.
        image = ImageEnhance.Contrast(image).enhance(rng.uniform(0.45, 0.8))
        image = ImageEnhance.Color(image).enhance(rng.uniform(0.2, 0.6))
        image = image.filter(ImageFilter.GaussianBlur(rng.uniform(0.5, 1.25)))
    return image, (center[0], center[1], angle)


def catalog_for_workspace(workspace: Path) -> NominalTargetCatalog:
    return load_nominal_target_catalog(workspace)
