#!/usr/bin/env python3
"""Render CAD-derived, IKEA-style RC03 assembly illustrations.

The production STLs and ``config/workcell_layout.json`` are the only sources
of released fixture geometry and placement.  Simple hardware, device-envelope,
template, cable, and motion-arrow proxies are generated only to explain the
assembly operation.  They are deliberately colored differently from released
printed parts.

Outputs are written to ``output/assembly_guide/images`` and are intended for
the illustrated assembly guide rather than dimensional inspection.
"""
from __future__ import annotations

import json
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import trimesh
from matplotlib.colors import to_rgb
from vtkmodules.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
from vtkmodules.vtkFiltersCore import vtkPolyDataNormals
from vtkmodules.vtkFiltersSources import vtkPlaneSource
from vtkmodules.vtkIOImage import vtkPNGReader, vtkPNGWriter
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkLight,
    vtkPolyDataMapper,
    vtkRenderer,
    vtkRenderWindow,
    vtkTexture,
    vtkWindowToImageFilter,
)
import vtkmodules.vtkRenderingOpenGL2  # noqa: F401 - register OpenGL backend


ROOT = Path(__file__).resolve().parents[1]
STL_DIR = ROOT / "stl"
FID_DIR = ROOT / "fiducials"
OUT_DIR = ROOT / "output" / "assembly_guide" / "images"
OUT_DIR.mkdir(parents=True, exist_ok=True)

LAYOUT = json.loads((ROOT / "config" / "workcell_layout.json").read_text(encoding="utf-8"))
PARAMS = json.loads((ROOT / "config" / "parameters.json").read_text(encoding="utf-8"))
BOARD_T = float(LAYOUT["board"]["thickness"])

# Restrained technical-illustration palette.  Blue always means "install now";
# gray means already installed; orange is hardware, adhesive, or motion.
BG = "#f6f8fa"
INK = "#20262d"
MUTED = "#66717c"
BOARD = "#e6dfd4"
BOARD_EDGE = "#9d9488"
GHOST = "#c6cdd3"
GHOST_DARK = "#8e99a4"
BLUE = "#147bd1"
BLUE_DARK = "#0a5596"
BLUE_LIGHT = "#8dc9f4"
ORANGE = "#f2a019"
STEEL = "#7f8a94"
CHARCOAL = "#252b31"
SCREEN = "#101419"
TPU = "#23a58b"
RED = "#d63b37"
WHITE = "#ffffff"

CANVAS_W, CANVAS_H = 1800, 1200
BODY_W, BODY_H = 1720, 830


@dataclass
class MeshItem:
    mesh: trimesh.Trimesh
    color: str
    alpha: float = 1.0
    metallic: bool = False


@dataclass
class TextureItem:
    image_path: Path
    x: float
    y: float
    z: float
    size: float
    alpha: float = 1.0


def load_part(name: str, xyz=(0.0, 0.0, 0.0)) -> trimesh.Trimesh:
    """Load a released STL and translate it into board coordinates."""
    mesh = trimesh.load_mesh(STL_DIR / name, force="mesh").copy()
    mesh.apply_translation(np.asarray(xyz, dtype=float))
    return mesh


def box(extents: Sequence[float], xyz: Sequence[float]) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation((
        xyz[0] + extents[0] / 2.0,
        xyz[1] + extents[1] / 2.0,
        xyz[2] + extents[2] / 2.0,
    ))
    return mesh


def cylinder_between(p0, p1, radius: float, sections: int = 40) -> trimesh.Trimesh:
    p0 = np.asarray(p0, dtype=float)
    p1 = np.asarray(p1, dtype=float)
    vector = p1 - p0
    length = float(np.linalg.norm(vector))
    if length <= 1e-9:
        raise ValueError("Cylinder endpoints must differ")
    mesh = trimesh.creation.cylinder(radius=radius, height=length, sections=sections)
    alignment = trimesh.geometry.align_vectors([0, 0, 1], vector / length)
    mesh.apply_transform(alignment)
    mesh.apply_translation((p0 + p1) / 2.0)
    return mesh


def cylinder_z(x: float, y: float, z0: float, height: float, diameter: float,
               sections: int = 40) -> trimesh.Trimesh:
    return cylinder_between((x, y, z0), (x, y, z0 + height), diameter / 2.0, sections)


def arrow(p0, p1, radius: float = 1.8, head_radius: float = 5.2,
          head_length: float = 13.0) -> trimesh.Trimesh:
    """Create a clean, solid 3-D motion arrow whose tip is at ``p1``."""
    p0 = np.asarray(p0, dtype=float)
    p1 = np.asarray(p1, dtype=float)
    vector = p1 - p0
    length = float(np.linalg.norm(vector))
    direction = vector / length
    head_length = min(head_length, length * 0.42)
    shaft_end = p1 - direction * head_length
    shaft = cylinder_between(p0, shaft_end, radius, 32)
    cone = trimesh.creation.cone(radius=head_radius, height=head_length, sections=36)
    cone.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], direction))
    cone.apply_translation(shaft_end)
    return trimesh.util.concatenate([shaft, cone])


def tube(points: Sequence[Sequence[float]], radius: float = 2.2) -> trimesh.Trimesh:
    pieces = [cylinder_between(a, b, radius, 32) for a, b in zip(points[:-1], points[1:])]
    for point in points[1:-1]:
        sphere = trimesh.creation.icosphere(subdivisions=2, radius=radius)
        sphere.apply_translation(point)
        pieces.append(sphere)
    return trimesh.util.concatenate(pieces)


def screw_vertical(x: float, y: float, tip_z: float, head_z: float,
                   diameter: float = 4.0, head_d: float = 9.0) -> trimesh.Trimesh:
    shaft_top = head_z - 2.6
    shaft = cylinder_between((x, y, tip_z), (x, y, shaft_top), diameter / 2.0, 32)
    head = cylinder_z(x, y, shaft_top, 2.6, head_d, 48)
    return trimesh.util.concatenate([shaft, head])


def washer_horizontal(x: float, y: float, z: float, outer_d=9.2,
                      inner_d=4.6, thickness=0.8) -> trimesh.Trimesh:
    washer = trimesh.creation.annulus(
        r_min=inner_d / 2.0, r_max=outer_d / 2.0, height=thickness, sections=48,
    )
    washer.apply_translation((x, y, z))
    return washer


def hex_prism(center, across_corners: float, thickness: float, axis="z") -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=across_corners / 2.0, height=thickness, sections=6)
    if axis == "x":
        mesh.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], [1, 0, 0]))
    elif axis == "y":
        mesh.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], [0, 1, 0]))
    mesh.apply_translation(center)
    return mesh


def surface_fan(apex: Sequence[float], perimeter: Sequence[Sequence[float]]) -> trimesh.Trimesh:
    """Triangulated translucent field-of-view fan for explanatory scenes."""
    vertices = np.asarray([apex, *perimeter], dtype=float)
    faces = []
    for index in range(len(perimeter)):
        faces.append((0, 1 + index, 1 + ((index + 1) % len(perimeter))))
    # A lightly filled target polygon makes coverage legible.
    for index in range(1, len(perimeter) - 1):
        faces.append((1, 1 + index, 2 + index))
    return trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=False)


def helix(center: Sequence[float], radius: float, z0: float, z1: float,
          turns: float = 5.0, wire_radius: float = 0.75) -> trimesh.Trimesh:
    cx, cy = center
    samples = 90
    points = []
    for index in range(samples):
        ratio = index / (samples - 1)
        angle = ratio * turns * 2.0 * math.pi
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle),
                       z0 + (z1 - z0) * ratio))
    return tube(points, wire_radius)


def board_item(alpha=1.0) -> MeshItem:
    return MeshItem(load_part("BOARD_REFERENCE_DO_NOT_PRINT.stl"), BOARD, alpha)


def feature(feature_id: str) -> dict:
    return next(item for item in LAYOUT["board_features"] if item["id"] == feature_id)


def station_mesh(station_name: str, dz=0.0, dx=0.0, dy=0.0) -> trimesh.Trimesh:
    station = LAYOUT["stations"][station_name]
    ox, oy = station["origin_xy"]
    return load_part(station["part"] + ".stl", (ox + dx, oy + dy, BOARD_T + dz))


def clamp_mesh(index: int, dx=0.0, dy=0.0, dz=0.0) -> trimesh.Trimesh:
    hold_id = "KBL-CLAMP" if index == 0 else "KBR-CLAMP"
    hold = feature(hold_id)
    return load_part(
        "keyboard_rear_clamp.stl",
        (hold["x"] - 26.0 + dx, hold["y"] - 22.5 + dy, BOARD_T + 4.0 + dz),
    )


def phone_rail_xyz() -> tuple[float, float, float]:
    station = LAYOUT["stations"]["phone_tcp"]
    rail_x = (
        PARAMS["phone_x"] + 15.0
        + PARAMS["phone_w"] + PARAMS["phone_case_extra_w"]
        + 2 * PARAMS["phone_clearance"] + 6.4 - 3.2
    )
    return rail_x, station["origin_xy"][1], BOARD_T + 4.0


def rail_mesh(dz=0.0) -> trimesh.Trimesh:
    x, y, z = phone_rail_xyz()
    return load_part("phone_clamp_rail.stl", (x, y, z + dz))


def puck_mesh(dz=0.0) -> trimesh.Trimesh:
    station = LAYOUT["stations"]["phone_tcp"]
    x, y = station["origin_xy"]
    return load_part("calibration_puck.stl", (x + 15.0, y + 85.0, BOARD_T + 6.5 + dz))


def keyboard_items(z_lift=0.0, color=CHARCOAL, alpha=1.0) -> list[MeshItem]:
    """Create a nominal device envelope plus non-dimensional keycap graphics."""
    kb = LAYOUT["devices"]["keyboard"]
    x, y = kb["nominal_origin_xy"]
    w, d, h = kb["nominal_size"]
    z = BOARD_T + z_lift
    items = [MeshItem(box((w, d, h), (x, y, z)), color, alpha)]
    # Keycaps are visual-only and stay well within the released envelope.
    key_z = z + h + 0.15
    margin_x, margin_y = 10.0, 11.0
    cols, rows = 18, 6
    pitch_x = (w - 2 * margin_x) / cols
    pitch_y = (d - 2 * margin_y) / rows
    cap_w, cap_d = pitch_x * 0.77, pitch_y * 0.66
    key_color = BLUE_LIGHT if color == BLUE else "#454d55"
    for row in range(rows):
        for col in range(cols):
            # Leave a small navigation gap, making the proxy instantly legible.
            if col in (13, 14) and row in (1, 2, 3):
                continue
            kx = x + margin_x + col * pitch_x + (pitch_x - cap_w) / 2.0
            ky = y + margin_y + row * pitch_y + (pitch_y - cap_d) / 2.0
            items.append(MeshItem(box((cap_w, cap_d, 0.8), (kx, ky, key_z)), key_color, alpha))
    return items


def phone_items(z_lift=0.0, color=BLUE, alpha=1.0) -> list[MeshItem]:
    phone = LAYOUT["devices"]["phone"]
    x, y = phone["nominal_origin_xy"]
    w, d, t = phone["configured_size"]
    z = BOARD_T + phone["support_plane_z"] + z_lift
    body = MeshItem(box((w, d, t), (x, y, z)), color, alpha)
    bezel = 3.0
    screen = MeshItem(
        box((w - 2 * bezel, d - 2 * bezel, 0.35), (x + bezel, y + bezel, z + t)),
        SCREEN if color == BLUE else GHOST_DARK,
        alpha,
    )
    return [body, screen]


def add_vtk_mesh(renderer: vtkRenderer, item: MeshItem) -> None:
    mesh = item.mesh
    points = vtkPoints()
    points.SetData(numpy_to_vtk(np.asarray(mesh.vertices), deep=True))
    encoded_faces = np.column_stack((
        np.full(len(mesh.faces), 3, dtype=np.int64),
        np.asarray(mesh.faces, dtype=np.int64),
    )).ravel()
    cells = vtkCellArray()
    cells.SetCells(len(mesh.faces), numpy_to_vtkIdTypeArray(encoded_faces, deep=True))
    poly = vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(cells)
    normals = vtkPolyDataNormals()
    normals.SetInputData(poly)
    normals.ConsistencyOn()
    normals.AutoOrientNormalsOn()
    normals.SplittingOn()
    normals.SetFeatureAngle(48.0)
    mapper = vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())
    actor = vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(to_rgb(item.color))
    prop.SetOpacity(item.alpha)
    prop.SetAmbient(0.24)
    prop.SetDiffuse(0.72)
    prop.SetSpecular(0.30 if item.metallic else 0.07)
    prop.SetSpecularPower(25.0 if item.metallic else 10.0)
    renderer.AddActor(actor)


def add_vtk_texture(renderer: vtkRenderer, item: TextureItem) -> None:
    plane = vtkPlaneSource()
    plane.SetOrigin(item.x, item.y, item.z)
    plane.SetPoint1(item.x + item.size, item.y, item.z)
    plane.SetPoint2(item.x, item.y + item.size, item.z)
    plane.SetResolution(1, 1)
    reader = vtkPNGReader()
    reader.SetFileName(str(item.image_path))
    texture = vtkTexture()
    texture.SetInputConnection(reader.GetOutputPort())
    texture.InterpolateOff()
    mapper = vtkPolyDataMapper()
    mapper.SetInputConnection(plane.GetOutputPort())
    actor = vtkActor()
    actor.SetMapper(mapper)
    actor.SetTexture(texture)
    actor.GetProperty().SetOpacity(item.alpha)
    actor.GetProperty().SetAmbient(1.0)
    actor.GetProperty().SetDiffuse(0.0)
    renderer.AddActor(actor)


def render_body(items: Iterable[MeshItem], textures: Iterable[TextureItem], output: Path,
                focus_bounds: Sequence[float], elev=32.0, azim=-58.0) -> None:
    renderer = vtkRenderer()
    renderer.SetBackground(to_rgb(BG))
    renderer.SetUseDepthPeeling(1)
    renderer.SetMaximumNumberOfPeels(100)
    renderer.SetOcclusionRatio(0.02)

    window = vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetAlphaBitPlanes(1)
    window.SetMultiSamples(8)
    window.SetSize(BODY_W, BODY_H)
    window.AddRenderer(renderer)

    for item in items:
        add_vtk_mesh(renderer, item)
    for item in textures:
        add_vtk_texture(renderer, item)

    key = vtkLight()
    key.SetLightTypeToSceneLight()
    key.SetPosition(250, -500, 900)
    key.SetFocalPoint(300, 220, 0)
    key.SetColor(1.0, 0.99, 0.96)
    key.SetIntensity(0.85)
    renderer.AddLight(key)
    fill = vtkLight()
    fill.SetLightTypeToSceneLight()
    fill.SetPosition(-500, 300, 500)
    fill.SetFocalPoint(300, 220, 0)
    fill.SetColor(0.82, 0.90, 1.0)
    fill.SetIntensity(0.42)
    renderer.AddLight(fill)

    xmin, xmax, ymin, ymax, zmin, zmax = map(float, focus_bounds)
    center = np.array([(xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2])
    azimuth = math.radians(azim)
    elevation = math.radians(elev)
    direction = np.array([
        math.cos(elevation) * math.cos(azimuth),
        math.cos(elevation) * math.sin(azimuth),
        math.sin(elevation),
    ])
    camera = renderer.GetActiveCamera()
    camera.ParallelProjectionOn()
    camera.SetFocalPoint(*center)
    camera.SetPosition(*(center + direction * 1200.0))
    forward = -direction
    right = np.cross(forward, np.array([0.0, 0.0, 1.0]))
    right /= np.linalg.norm(right)
    view_up = np.cross(right, forward)
    view_up /= np.linalg.norm(view_up)
    camera.SetViewUp(*view_up)
    # Compute an exact orthographic framing scale from the requested region.
    # ResetCamera considers every visible actor (including the full board), so
    # it cannot be used for the detail views.
    corners = np.array([
        (x, y, z)
        for x in (xmin, xmax)
        for y in (ymin, ymax)
        for z in (zmin, zmax)
    ], dtype=float)
    offsets = corners - center
    half_w = float(np.max(np.abs(offsets @ right)))
    half_h = float(np.max(np.abs(offsets @ view_up)))
    aspect = BODY_W / BODY_H
    camera.SetParallelScale(max(half_h, half_w / aspect) * 1.08)
    renderer.ResetCameraClippingRange()

    window.Render()
    capture = vtkWindowToImageFilter()
    capture.SetInput(window)
    capture.SetInputBufferTypeToRGB()
    capture.ReadFrontBufferOff()
    capture.Update()
    writer = vtkPNGWriter()
    writer.SetFileName(str(output))
    writer.SetInputConnection(capture.GetOutputPort())
    writer.Write()
    window.Finalize()


def fonts():
    candidates = {
        "bold": [Path("C:/Windows/Fonts/seguisb.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")],
        "regular": [Path("C:/Windows/Fonts/segoeui.ttf"), Path("C:/Windows/Fonts/arial.ttf")],
    }
    paths = {}
    for style, options in candidates.items():
        paths[style] = next((path for path in options if path.exists()), options[-1])
    return {
        "step": ImageFont.truetype(str(paths["bold"]), 55),
        "title": ImageFont.truetype(str(paths["bold"]), 47),
        "subtitle": ImageFont.truetype(str(paths["regular"]), 27),
        "callout": ImageFont.truetype(str(paths["regular"]), 24),
        "callout_bold": ImageFont.truetype(str(paths["bold"]), 24),
        "legend": ImageFont.truetype(str(paths["regular"]), 20),
        "badge": ImageFont.truetype(str(paths["bold"]), 20),
    }


FONTS = fonts()


def fit_text(draw: ImageDraw.ImageDraw, text: str, width: int,
             font: ImageFont.FreeTypeFont) -> str:
    """Wrap all words to ``width`` without silently dropping instructions."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


def fit_callout(draw: ImageDraw.ImageDraw, text: str, width: int,
                height: int) -> tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int, int], int]:
    """Fit a complete callout into its card, returning text/font/bounds/spacing."""
    for size in range(24, 16, -1):
        font = FONTS["callout"].font_variant(size=size)
        spacing = max(3, round(size * 0.22))
        wrapped = fit_text(draw, text, width, font)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
        if bbox[2] - bbox[0] <= width and bbox[3] - bbox[1] <= height:
            return wrapped, font, bbox, spacing
    # This should only be reached for unexpectedly long future instructions.
    # Preserve the full text and keep reducing rather than clipping or eliding it.
    size = 16
    while size >= 11:
        font = FONTS["callout"].font_variant(size=size)
        spacing = max(2, round(size * 0.18))
        wrapped = fit_text(draw, text, width, font)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
        if bbox[2] - bbox[0] <= width and bbox[3] - bbox[1] <= height:
            return wrapped, font, bbox, spacing
        size -= 1
    raise ValueError(f"Callout cannot fit without clipping: {text!r}")


def draw_arrow_2d(draw: ImageDraw.ImageDraw, start, end, color, width=4,
                  head=10) -> None:
    draw.line((start, end), fill=color, width=width)
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = max(math.hypot(dx, dy), 1e-6)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    base_x, base_y = end[0] - ux * head, end[1] - uy * head
    draw.polygon([
        end,
        (base_x + px * head * 0.55, base_y + py * head * 0.55),
        (base_x - px * head * 0.55, base_y - py * head * 0.55),
    ], fill=color)


def draw_orientation_key(draw: ImageDraw.ImageDraw) -> None:
    """Persistent board-axis key used on every panel."""
    x0, y0, x1, y1 = 1492, 812, 1736, 970
    draw.rounded_rectangle((x0, y0, x1, y1), radius=14, fill=WHITE,
                           outline="#d3dbe2", width=2)
    origin = (1560, 906)
    draw.ellipse((origin[0] - 5, origin[1] - 5, origin[0] + 5, origin[1] + 5), fill=INK)
    draw_arrow_2d(draw, origin, (1694, 906), BLUE_DARK, width=4, head=11)
    draw_arrow_2d(draw, origin, (1560, 840), BLUE_DARK, width=4, head=11)
    draw_arrow_2d(draw, origin, (1560, 946), MUTED, width=3, head=9)
    draw.text((1614, 875), "+X", fill=BLUE_DARK, font=FONTS["badge"])
    draw.text((1580, 834), "+Y REAR", fill=BLUE_DARK, font=FONTS["badge"])
    draw.text((1580, 932), "FRONT", fill=MUTED, font=FONTS["badge"])


def draw_header(draw: ImageDraw.ImageDraw, number: str, title: str,
                subtitle: str, badge: str | None) -> None:
    """Draw the header as the final overlay so no 3D layer can cover it."""
    # Panel 14 has four dense instruction cards and is commonly viewed in a
    # full-canvas preview.  Give that panel an additional 16 px safety inset
    # on both sides so neither the step tile nor the right badge can appear
    # clipped by a viewer's edge treatment.
    side_margin = 64 if number == "14" else 48
    tile_left = side_margin
    tile_right = tile_left + 107
    title_left = tile_right + 30
    draw.rectangle((0, 0, CANVAS_W, 159), fill=BG)
    draw.rounded_rectangle((tile_left, 35, tile_right, 142), radius=18, fill=BLUE)
    step_bbox = draw.textbbox((0, 0), number, font=FONTS["step"])
    tile_center_x = (tile_left + tile_right) / 2
    draw.text((tile_center_x - (step_bbox[2] - step_bbox[0]) / 2,
               87 - (step_bbox[3] - step_bbox[1]) / 2 - step_bbox[1]),
              number, fill=WHITE, font=FONTS["step"])
    draw.text((title_left, 36), title, fill=INK, font=FONTS["title"])
    draw.text((title_left + 2, 100), subtitle, fill=MUTED, font=FONTS["subtitle"])
    if badge:
        badge_box = draw.textbbox((0, 0), badge, font=FONTS["badge"])
        bw = badge_box[2] - badge_box[0] + 34
        badge_right = CANVAS_W - side_margin
        draw.rounded_rectangle((badge_right - bw, 48, badge_right, 92), radius=20,
                               fill="#e7f2fb", outline=BLUE, width=2)
        draw.text((badge_right - bw + 17, 57), badge, fill=BLUE_DARK, font=FONTS["badge"])


def compose_step(raw: Path, output: Path, number: str, title: str, subtitle: str,
                 callouts: Sequence[str], badge: str | None = None) -> None:
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    draw = ImageDraw.Draw(canvas)

    body = Image.open(raw).convert("RGB")
    canvas.paste(body, (40, 164))
    draw.rounded_rectangle((40, 164, 1760, 994), radius=16, outline="#dbe1e6", width=2)
    draw_orientation_key(draw)

    callout_y = 1023
    gap = 24
    count = max(1, len(callouts))
    card_margin = 64 if number == "14" else 48
    card_w = int((CANVAS_W - 2 * card_margin - gap * (count - 1)) / count)
    for index, text in enumerate(callouts, 1):
        x0 = card_margin + (index - 1) * (card_w + gap)
        x1 = x0 + card_w
        draw.rounded_rectangle((x0, callout_y, x1, 1168), radius=14, fill=WHITE,
                               outline="#d9e0e5", width=2)
        draw.ellipse((x0 + 17, callout_y + 18, x0 + 59, callout_y + 60), fill=ORANGE)
        idx = str(index)
        bbox = draw.textbbox((0, 0), idx, font=FONTS["callout_bold"])
        draw.text((x0 + 38 - (bbox[2] - bbox[0]) / 2,
                   callout_y + 39 - (bbox[3] - bbox[1]) / 2 - bbox[1]),
                  idx, fill=WHITE, font=FONTS["callout_bold"])
        text_x = x0 + 73
        text_right = x1 - 18
        text_top = callout_y + 13
        text_bottom = 1155
        wrapped, callout_font, text_bbox, spacing = fit_callout(
            draw, text, text_right - text_x, text_bottom - text_top,
        )
        text_height = text_bbox[3] - text_bbox[1]
        text_y = text_top + (text_bottom - text_top - text_height) / 2 - text_bbox[1]
        draw.multiline_text((text_x, text_y), wrapped, fill=INK,
                            font=callout_font, spacing=spacing)

        # Defensive layout invariant: neither the card nor its complete caption
        # may leave the canvas/card.  A future wording change fails loudly.
        final_bbox = draw.multiline_textbbox((text_x, text_y), wrapped,
                                             font=callout_font, spacing=spacing)
        if final_bbox[0] < text_x or final_bbox[2] > text_right or \
                final_bbox[1] < text_top or final_bbox[3] > text_bottom:
            raise ValueError(f"Callout overflow in panel {number}, card {index}: {final_bbox}")
        if x1 > CANVAS_W - card_margin:
            raise ValueError(f"Callout card leaves canvas in panel {number}: x1={x1}")

    # A final, opaque header pass guarantees the step tile and type remain
    # visible regardless of renderer/axes compositing behavior.
    draw_header(draw, number, title, subtitle, badge)
    canvas.save(output, quality=95)


def scene_prepare_board() -> tuple[list[MeshItem], list[TextureItem]]:
    board = LAYOUT["board"]
    # This scene is intentionally the undrilled rectangular board.  The
    # released board-reference STL contains the final controlled bores, which
    # would incorrectly imply that every M4 anchor always uses a 4.6 mm bore.
    items: list[MeshItem] = [MeshItem(
        box((board["width"], board["depth"], board["thickness"]), (0, 0, 0)),
        BOARD,
    )]
    # Six lightly separated tiles communicate the tiled Letter template while
    # all hole centers continue to come from the controlled layout.
    page_w, page_d = board["width"] / 3.0, board["depth"] / 2.0
    for row in range(2):
        for col in range(3):
            shade = "#ffffff" if (row + col) % 2 == 0 else "#f2f5f7"
            items.append(MeshItem(
                box((page_w - 1.0, page_d - 1.0, 0.28),
                    (col * page_w + 0.5, row * page_d + 0.5, BOARD_T + 0.4)),
                shade, 0.82,
            ))
    for bf in LAYOUT["board_features"]:
        is_locator = bf["type"] == "locator_pin_blind"
        diameter = 12.0 if is_locator else 9.0
        items.append(MeshItem(
            cylinder_z(bf["x"], bf["y"], BOARD_T + 0.8, 0.8, diameter),
            BLUE if is_locator else ORANGE,
        ))
    # A few repeated downward arrows establish the operation without hiding
    # the complete 13-point pattern.
    for fid in ("KBL-LOC-ROUND", "KBR-HOLD-F", "PT-LOC-RADIAL", "PT-HOLD-TCP"):
        bf = feature(fid)
        items.append(MeshItem(arrow((bf["x"], bf["y"], 76),
                                         (bf["x"], bf["y"], BOARD_T + 4)), ORANGE))
    return items, []


def scene_left_station() -> tuple[list[MeshItem], list[TextureItem]]:
    items = [board_item(0.78)]
    items.append(MeshItem(station_mesh("keyboard_left"), BLUE_LIGHT, 0.20))
    lift = 38.0
    items.append(MeshItem(station_mesh("keyboard_left", dz=lift), BLUE))
    # The KBL-CLAMP retainer is shared by station and padded slider.  Keep the
    # slider with the exploded master so the third screw is never depicted as
    # passing through the station alone.
    items.append(MeshItem(clamp_mesh(0, dz=lift), BLUE))
    for fid in ("KBL-LOC-ROUND", "KBL-LOC-RADIAL"):
        bf = feature(fid)
        items.append(MeshItem(cylinder_z(bf["x"], bf["y"], BOARD_T, 5.0, 6.0), STEEL, 1.0, True))
    for fid in ("KBL-HOLD-F", "KBL-HOLD-R", "KBL-CLAMP"):
        bf = feature(fid)
        head_z = BOARD_T + lift + 28
        items.append(MeshItem(screw_vertical(bf["x"], bf["y"], BOARD_T + lift + 2,
                                             head_z), ORANGE, 1.0, True))
        items.append(MeshItem(washer_horizontal(bf["x"], bf["y"], head_z - 3.0),
                              STEEL, 1.0, True))
    items.append(MeshItem(arrow((172, 165, BOARD_T + lift + 50),
                                 (172, 165, BOARD_T + 10)), ORANGE))
    return items, []


def scene_keyboard_slave() -> tuple[list[MeshItem], list[TextureItem]]:
    items = [board_item(0.72)]
    items.append(MeshItem(station_mesh("keyboard_left"), GHOST_DARK, 0.92))
    items.append(MeshItem(station_mesh("keyboard_right"), BLUE_LIGHT, 0.18))
    dx, dz = 31.0, 30.0
    items.append(MeshItem(station_mesh("keyboard_right", dx=dx, dz=dz), BLUE))
    # As with the master, the slave's third retainer passes through its padded
    # slider and station together before reaching the board anchor.
    items.append(MeshItem(clamp_mesh(1, dx=dx, dz=dz), BLUE))
    for fid in ("KBR-HOLD-F", "KBR-HOLD-R", "KBR-CLAMP"):
        bf = feature(fid)
        head_z = BOARD_T + dz + 28
        items.append(MeshItem(screw_vertical(
            bf["x"] + dx, bf["y"], BOARD_T + dz + 2, head_z,
        ), ORANGE, 1.0, True))
        items.append(MeshItem(washer_horizontal(bf["x"] + dx, bf["y"], head_z - 3.0),
                              STEEL, 1.0, True))
    interface = LAYOUT["interfaces"]["keyboard_master_slave"]
    for key in ("front_post_board_xy", "rear_post_board_xy"):
        x, y = interface[key]
        items.append(MeshItem(cylinder_z(x, y, BOARD_T + 4.0,
                                         interface["post_height"], interface["post_diameter"]),
                              ORANGE))
        items.append(MeshItem(arrow((x + dx, y, BOARD_T + dz + 8),
                                     (x, y, BOARD_T + 6)), ORANGE))
    return items, []


def scene_keyboard_device() -> tuple[list[MeshItem], list[TextureItem]]:
    items = [board_item(0.70)]
    items += [
        MeshItem(station_mesh("keyboard_left"), GHOST_DARK, 0.86),
        MeshItem(station_mesh("keyboard_right"), GHOST_DARK, 0.86),
    ]
    # Show the keyboard already resting on the board.  The sliders were fitted
    # in Steps 02/03; translucent rearward copies and horizontal arrows now show
    # their gentle adjustment rather than a second installation.
    items.extend(keyboard_items(0.0, BLUE, 1.0))
    kb = LAYOUT["devices"]["keyboard"]
    x, y = kb["nominal_origin_xy"]
    w, d, _ = kb["nominal_size"]
    items.append(MeshItem(arrow((x + w / 2, y + d / 2, BOARD_T + 72),
                                 (x + w / 2, y + d / 2, BOARD_T + 27)), ORANGE))
    # Only the two actual rear clamp slider parts and their face pads are shown.
    # No keyboard captive nuts or station support-pad recesses are implied.
    for index, fid in enumerate(("KBL-CLAMP", "KBR-CLAMP")):
        items.append(MeshItem(clamp_mesh(index, dy=12.0), BLUE_LIGHT, 0.22))
        items.append(MeshItem(clamp_mesh(index), BLUE))
        hold = feature(fid)
        items.append(MeshItem(screw_vertical(hold["x"], hold["y"], BOARD_T - 1,
                                             BOARD_T + 14), ORANGE, 1.0, True))
        items.append(MeshItem(washer_horizontal(hold["x"], hold["y"], BOARD_T + 10.8),
                              STEEL, 1.0, True))
        items.append(MeshItem(arrow((hold["x"], hold["y"] + 24, BOARD_T + 35),
                                     (hold["x"], hold["y"] - 3, BOARD_T + 35),
                                     radius=1.5, head_radius=4.5, head_length=11), ORANGE))
    return items, []


def scene_phone_station() -> tuple[list[MeshItem], list[TextureItem]]:
    items = [board_item(0.78)]
    items.append(MeshItem(station_mesh("phone_tcp"), BLUE_LIGHT, 0.18))
    lift = 42.0
    items.append(MeshItem(station_mesh("phone_tcp", dz=lift), BLUE))
    for fid in ("PT-LOC-ROUND", "PT-LOC-RADIAL"):
        bf = feature(fid)
        items.append(MeshItem(cylinder_z(bf["x"], bf["y"], BOARD_T, 5.0, 6.0), STEEL, 1.0, True))
    # Only the TCP-side retainer is installed now.  PT-HOLD-R1/R2 are shared by
    # the rail and station, so they deliberately appear only after the rail is
    # fully seated in the later hardware scene.
    bf = feature("PT-HOLD-TCP")
    head_z = BOARD_T + lift + 28
    items.append(MeshItem(screw_vertical(bf["x"], bf["y"], BOARD_T + lift + 2,
                                         head_z), ORANGE, 1.0, True))
    items.append(MeshItem(washer_horizontal(bf["x"], bf["y"], head_z - 3.0),
                          STEEL, 1.0, True))
    items.append(MeshItem(arrow((505, 165, BOARD_T + lift + 52),
                                 (505, 165, BOARD_T + 12)), ORANGE))
    return items, []


def scene_rail_and_puck() -> tuple[list[MeshItem], list[TextureItem]]:
    items = [board_item(0.68), MeshItem(station_mesh("phone_tcp"), GHOST_DARK, 0.88)]
    lift = 37.0
    items += [
        MeshItem(rail_mesh(), BLUE_LIGHT, 0.18),
        MeshItem(puck_mesh(), BLUE_LIGHT, 0.18),
        MeshItem(rail_mesh(lift), BLUE),
        MeshItem(puck_mesh(lift + 8.0), BLUE),
    ]
    rx, ry, rz = phone_rail_xyz()
    items.append(MeshItem(arrow((rx + 9.6, ry + 86.4, rz + lift + 40),
                                 (rx + 9.6, ry + 86.4, rz + 9)), ORANGE))
    tcp = LAYOUT["devices"]["tcp_target"]
    items.append(MeshItem(arrow((tcp["center_xy"][0], tcp["center_xy"][1], BOARD_T + 82),
                                 (tcp["center_xy"][0], tcp["center_xy"][1], BOARD_T + 13)), ORANGE))
    return items, []


def scene_phone_hardware() -> tuple[list[MeshItem], list[TextureItem]]:
    items = [
        board_item(0.68),
        MeshItem(station_mesh("phone_tcp"), GHOST_DARK, 0.90),
        MeshItem(rail_mesh(), BLUE),
        MeshItem(puck_mesh(), BLUE),
    ]
    # Rail is fully seated before the two shared station/rail board screws are
    # shown approaching.  These screws are not depicted in the previous scene.
    for fid in ("PT-HOLD-R1", "PT-HOLD-R2"):
        bf = feature(fid)
        head_z = BOARD_T + 39
        items.append(MeshItem(screw_vertical(bf["x"], bf["y"], BOARD_T + 4,
                                             head_z), ORANGE, 1.0, True))
        items.append(MeshItem(washer_horizontal(bf["x"], bf["y"], head_z - 3.0),
                              STEEL, 1.0, True))
        items.append(MeshItem(arrow((bf["x"] + 11, bf["y"], BOARD_T + 53),
                                     (bf["x"] + 11, bf["y"], BOARD_T + 12),
                                     radius=1.4, head_radius=4.2, head_length=10), ORANGE))
    # Top-loaded M4 clamp nuts, final orientation retained while dropping.
    rail_x, rail_y, rail_z = phone_rail_xyz()
    frame_l = 172.8
    for cy in (rail_y + 30.0, rail_y + frame_l - 30.0):
        nut_x = rail_x + 14.2
        items.append(MeshItem(hex_prism((nut_x, cy, rail_z + 39),
                                         PARAMS["phone_m4_nut_ac"],
                                         PARAMS["m4_nut_thickness"], axis="x"), ORANGE, 1.0, True))
        items.append(MeshItem(arrow((nut_x, cy, rail_z + 54),
                                     (nut_x, cy, rail_z + 14),
                                     radius=1.2, head_radius=3.8, head_length=9), ORANGE))
    # Two controlled M3 cartridge screws.
    for x, y in ((431.0, 170.0), (451.0, 190.0)):
        items.append(MeshItem(screw_vertical(x, y, BOARD_T + 10.0, BOARD_T + 39,
                                             diameter=3.0, head_d=6.2), ORANGE, 1.0, True))
    return items, []


def scene_phone_and_cable() -> tuple[list[MeshItem], list[TextureItem]]:
    items = [
        board_item(0.68),
        MeshItem(station_mesh("phone_tcp"), GHOST_DARK, 0.92),
        MeshItem(rail_mesh(), GHOST_DARK, 0.92),
        MeshItem(puck_mesh(), GHOST_DARK, 0.92),
    ]
    items.extend(phone_items(0.0, BLUE, 1.0))
    phone = LAYOUT["devices"]["phone"]
    px, py = phone["nominal_origin_xy"]
    pw, _, pt = phone["configured_size"]
    pz = BOARD_T + phone["support_plane_z"]
    # Visible USB lead follows the released front-side route and rail saddle.
    cable_points = [
        (px + pw / 2.0, py + 1.5, pz + pt / 2.0),
        (px + pw / 2.0 + 16.0, py - 2.0, BOARD_T + 5.5),
        (581.0, 86.0, BOARD_T + 7.0),
        (581.0, 52.0, BOARD_T + 4.0),
        (572.0, 25.0, BOARD_T + 3.0),
    ]
    items.append(MeshItem(tube(cable_points, 2.0), ORANGE))
    items.append(MeshItem(arrow((581.0, 72.0, BOARD_T + 11.0),
                                 (575.0, 34.0, BOARD_T + 5.0),
                                 radius=1.2, head_radius=4.2, head_length=10), ORANGE))
    # Two M4 clamp screw proxies act along X.  The green ends represent the
    # accepted TPU caps and stop at the measured phone envelope.
    rail_x, rail_y, rail_z = phone_rail_xyz()
    clamp_z = rail_z + min(max(pt / 2.0, 3.5), 6.0)
    for cy in (rail_y + 30.0, rail_y + 142.8):
        items.append(MeshItem(cylinder_between((rail_x + 21.0, cy, clamp_z),
                                                (px + pw + 1.0, cy, clamp_z), 2.0),
                              ORANGE, 1.0, True))
        tip = cylinder_between((px + pw + 1.0, cy, clamp_z),
                               (px + pw - 3.0, cy, clamp_z), 3.6)
        items.append(MeshItem(tip, TPU))
        items.append(MeshItem(arrow((rail_x + 31.0, cy, clamp_z + 11),
                                     (px + pw + 5.0, cy, clamp_z + 11),
                                     radius=1.2, head_radius=4.0, head_length=9), ORANGE))
    return items, []


def scene_phone_no_go() -> tuple[list[MeshItem], list[TextureItem]]:
    """Measured-interface reminder; red proxies are intentionally not datums."""
    items = [
        board_item(0.60),
        MeshItem(station_mesh("phone_tcp"), GHOST_DARK, 0.92),
        MeshItem(rail_mesh(), GHOST_DARK, 0.92),
        MeshItem(puck_mesh(), GHOST_DARK, 0.92),
    ]
    items.extend(phone_items(0.0, BLUE, 1.0))
    phone = LAYOUT["devices"]["phone"]
    px, py = phone["nominal_origin_xy"]
    pw, pd, pt = phone["configured_size"]
    z = BOARD_T + phone["support_plane_z"] + pt + 0.7
    # Screen-edge no-go border.
    border = 3.0
    items += [
        MeshItem(box((pw, border, 0.9), (px, py, z)), RED),
        MeshItem(box((pw, border, 0.9), (px, py + pd - border, z)), RED),
        MeshItem(box((border, pd, 0.9), (px, py, z)), RED),
        MeshItem(box((border, pd, 0.9), (px + pw - border, py, z)), RED),
    ]
    # Representative measurement zones—not released locations—for case camera
    # protrusion and side buttons.  Footer text explicitly requires the actual
    # device/case to define these no-go coordinates.
    items.append(MeshItem(box((25.0, 34.0, 3.0),
                              (px + 5.0, py + pd - 40.0, z + 0.9)), RED, 0.76))
    for by in (py + 63.0, py + 88.0):
        items.append(MeshItem(box((4.0, 16.0, 5.0),
                                  (px + pw - 1.0, by, z - 1.5)), RED, 0.90))
    usb = tube([
        (px + pw / 2.0, py + 1.0, z - 2.0),
        (px + pw / 2.0 + 12.0, py - 3.0, BOARD_T + 7.0),
        (px + pw / 2.0 + 35.0, py - 18.0, BOARD_T + 5.0),
    ], 3.2)
    items.append(MeshItem(usb, RED))
    return items, []


def scene_arm_support() -> tuple[list[MeshItem], list[TextureItem]]:
    """Schematic factory-clamp view with the controlled board dimensions."""
    # Low board opacity is a deliberate cutaway convention: it exposes the
    # reinforcement beneath the board without pretending the board is clear.
    items = [board_item(0.28)]
    # The plate is deliberately a proxy because its released outline follows
    # the measured factory clamp footprint.  Thickness follows the documented
    # minimum aluminum route; steel may instead use the specified 2 mm minimum.
    plate_xyz = (225.0, 372.0, -18.0)
    items.append(MeshItem(box((160.0, 76.0, 3.0), plate_xyz), BLUE, 1.0, True))
    items.append(MeshItem(box((160.0, 76.0, 3.0), (225.0, 372.0, -3.0)),
                          BLUE_LIGHT, 0.18, True))
    items.append(MeshItem(arrow((305.0, 410.0, -30.0), (305.0, 410.0, -5.0)), ORANGE))
    # Factory clamp is schematic only: top pad, lower jaw, and screw path.
    items += [
        MeshItem(box((112.0, 35.0, 9.0), (249.0, 399.0, BOARD_T)), CHARCOAL),
        MeshItem(box((112.0, 35.0, 9.0), (249.0, 399.0, -14.0)), CHARCOAL),
        MeshItem(cylinder_between((305.0, 443.0, -25.0),
                                  (305.0, 443.0, BOARD_T + 16.0), 5.0), STEEL, 1.0, True),
        MeshItem(cylinder_z(305.0, 416.0, BOARD_T + 9.0, 45.0, 88.0), CHARCOAL),
    ]
    return items, []


def scene_camera_fov() -> tuple[list[MeshItem], list[TextureItem]]:
    items: list[MeshItem] = [board_item(0.82)]
    for station in ("keyboard_left", "keyboard_right", "phone_tcp"):
        items.append(MeshItem(station_mesh(station), GHOST, 0.22))
    # Optional independent mast route.  Its exact board/external location is
    # intentionally schematic and must be selected from the measured FOV.
    foot_x, foot_y = 620.0, 330.0
    items.append(MeshItem(load_part("mast_foot_2020.stl", (foot_x, foot_y, 0.0)), BLUE))
    mast_center = (foot_x + 46.0, foot_y + 46.0)
    items.append(MeshItem(box((20.0, 20.0, 270.0),
                              (mast_center[0] - 10.0, mast_center[1] - 10.0, 70.0)),
                          STEEL, 1.0, True))
    plate_x, plate_y, plate_z = mast_center[0] - 45.0, mast_center[1] - 27.5, 338.0
    items.append(MeshItem(load_part("camera_plate_universal.stl",
                                    (plate_x, plate_y, plate_z)), BLUE))
    items.append(MeshItem(box((46.0, 34.0, 24.0),
                              (mast_center[0] - 23.0, mast_center[1] - 17.0, 310.0)),
                          CHARCOAL))
    items.append(MeshItem(cylinder_z(mast_center[0], mast_center[1], 301.0, 9.0, 14.0),
                          CHARCOAL))
    tags = LAYOUT["direct_tags"]["tags"]
    perimeter = [
        (*tags["T0"]["detection_center_xy"], BOARD_T + 1.0),
        (*tags["T1"]["detection_center_xy"], BOARD_T + 1.0),
        (*tags["T3"]["detection_center_xy"], BOARD_T + 1.0),
        (*tags["T2"]["detection_center_xy"], BOARD_T + 1.0),
    ]
    items.append(MeshItem(surface_fan((mast_center[0], mast_center[1], 301.0), perimeter),
                          BLUE_LIGHT, 0.18))
    return items, tag_texture_items()


def scene_compliant_tool() -> tuple[list[MeshItem], list[TextureItem]]:
    """Exploded compliant-tool assembly using released printable STLs."""
    cx, cy = 44.0, 38.0
    items: list[MeshItem] = [
        MeshItem(load_part("compliant_tool_body.stl", (30.0, 26.0, 0.0)), BLUE),
        MeshItem(load_part("compliant_tool_top_cap.stl", (30.0, 26.0, 110.0)), BLUE),
        MeshItem(helix((cx, cy), 6.2, 76.0, 101.0, turns=5.5), ORANGE, 1.0, True),
        MeshItem(load_part("rod_bushing_6_to_9mm.stl", (cx, cy, -34.0)), BLUE),
        MeshItem(cylinder_between((cx, cy, -72.0), (cx, cy, 5.0), 3.0), STEEL, 1.0, True),
        MeshItem(load_part("keyboard_tip_TPU_6mm.stl", (cx, cy, -86.0)), TPU),
    ]
    # Two cap screws follow the actual asymmetric insert coordinates.
    for x, y in ((35.0, 31.0), (53.0, 45.0)):
        items.append(MeshItem(screw_vertical(x, y, 111.0, 145.0,
                                             diameter=3.0, head_d=6.2), ORANGE, 1.0, True))
    items.append(MeshItem(arrow((cx, cy, 157.0), (cx, cy, 119.0)), ORANGE))
    items.append(MeshItem(arrow((cx, cy, 107.0), (cx, cy, 69.0)), ORANGE))
    items.append(MeshItem(arrow((cx, cy, -18.0), (cx, cy, -1.0)), ORANGE))
    # Alternative measured stylus route shown alongside, not simultaneously in
    # the tool.  The collar is the released printed part; barrel is a proxy.
    alt_x = 126.0
    items.append(MeshItem(cylinder_between((alt_x, cy, -68.0),
                                           (alt_x, cy, 32.0), 4.5), GHOST_DARK))
    items.append(MeshItem(load_part("stylus_collar_9mm.stl", (alt_x, cy, -10.0)), BLUE))
    items.append(MeshItem(arrow((alt_x, cy, 54.0), (alt_x, cy, 20.0)), ORANGE))
    return items, []


def tag_texture_items(alpha=1.0) -> list[TextureItem]:
    result: list[TextureItem] = []
    tile = float(LAYOUT["direct_tags"]["tile_size_mm"])
    for name, tag in LAYOUT["direct_tags"]["tags"].items():
        x, y = tag["tile_origin_xy"]
        result.append(TextureItem(
            FID_DIR / f"tag36h11_id{int(tag['id']):02d}_tile55_marker40.png",
            x, y, BOARD_T + 0.48, tile, alpha,
        ))
    return result


def scene_tags() -> tuple[list[MeshItem], list[TextureItem]]:
    items = [
        board_item(0.92),
        MeshItem(station_mesh("keyboard_left"), GHOST, 0.30),
        MeshItem(station_mesh("keyboard_right"), GHOST, 0.30),
        MeshItem(station_mesh("phone_tcp"), GHOST, 0.30),
    ]
    # Reusable application frame is shown over T0.  The frame is removed after
    # each tile; it is never a permanent fixture component.
    t0 = LAYOUT["direct_tags"]["tags"]["T0"]
    tx, ty = t0["tile_origin_xy"]
    frame = load_part("tag_application_frame_55mm.stl", (tx - 10.0, ty - 10.0, BOARD_T + 22.0))
    items.append(MeshItem(frame, BLUE))
    items.append(MeshItem(arrow((tx + 27.5, ty + 27.5, BOARD_T + 63),
                                 (tx + 27.5, ty + 27.5, BOARD_T + 4)), ORANGE))
    return items, tag_texture_items()


def scene_final() -> tuple[list[MeshItem], list[TextureItem]]:
    items = [board_item()]
    items += [
        MeshItem(station_mesh("keyboard_left"), BLUE_DARK),
        MeshItem(station_mesh("keyboard_right"), BLUE_DARK),
        MeshItem(station_mesh("phone_tcp"), BLUE_DARK),
        MeshItem(clamp_mesh(0), BLUE),
        MeshItem(clamp_mesh(1), BLUE),
        MeshItem(rail_mesh(), BLUE),
        MeshItem(puck_mesh(), ORANGE),
    ]
    items.extend(keyboard_items(0.0, CHARCOAL, 1.0))
    items.extend(phone_items(0.0, CHARCOAL, 1.0))
    # Neutral keep-out proxy: the released package intentionally does not
    # assert unmeasured factory RoArm clamp geometry.
    items.append(MeshItem(cylinder_z(305, 420, BOARD_T, 5.0, 150), GHOST, 0.42))
    items.append(MeshItem(cylinder_z(305, 420, BOARD_T, 70.0, 88), CHARCOAL, 0.92))
    return items, tag_texture_items()


def render_tag_transfer_body(output: Path) -> None:
    """Four-stage center/+Y transfer diagram with the controlled ID mapping."""
    panel = Image.new("RGB", (BODY_W, BODY_H), BG)
    draw = ImageDraw.Draw(panel)
    card_gap = 20
    card_x0 = 24
    card_y0 = 22
    card_w = int((BODY_W - 2 * card_x0 - 3 * card_gap) / 4)
    card_h = 530
    headings = [
        ("A", "REGISTER TEMPLATE"),
        ("B", "TRANSFER MARKS"),
        ("C", "REMOVE PAPER"),
        ("D", "FRAME + TAG"),
    ]
    for index, (letter, heading) in enumerate(headings):
        x0 = card_x0 + index * (card_w + card_gap)
        x1 = x0 + card_w
        draw.rounded_rectangle((x0, card_y0, x1, card_y0 + card_h), radius=15,
                               fill=WHITE, outline="#d4dce3", width=2)
        draw.ellipse((x0 + 18, card_y0 + 17, x0 + 62, card_y0 + 61), fill=BLUE)
        bbox = draw.textbbox((0, 0), letter, font=FONTS["callout_bold"])
        draw.text((x0 + 40 - (bbox[2] - bbox[0]) / 2,
                   card_y0 + 39 - (bbox[3] - bbox[1]) / 2 - bbox[1]),
                  letter, fill=WHITE, font=FONTS["callout_bold"])
        draw.text((x0 + 76, card_y0 + 25), heading, fill=INK, font=FONTS["badge"])

        cx = (x0 + x1) // 2
        cy = card_y0 + 300
        if index == 0:
            draw.rounded_rectangle((cx - 145, cy - 130, cx + 145, cy + 130), radius=8,
                                   fill=BOARD, outline=BOARD_EDGE, width=3)
            draw.rectangle((cx - 130, cy - 115, cx + 130, cy + 115),
                           fill="#ffffff", outline="#b8c2ca", width=2)
            for tx in (cx - 43, cx + 44):
                draw.line((tx, cy - 115, tx, cy + 115), fill="#c6cdd3", width=2)
            draw.line((cx - 130, cy, cx + 130, cy), fill="#c6cdd3", width=2)
            draw.line((cx - 18, cy, cx + 18, cy), fill=ORANGE, width=3)
            draw.line((cx, cy - 18, cx, cy + 18), fill=ORANGE, width=3)
            draw.text((cx - 105, cy + 150), "Tape at 100% / Actual Size", fill=MUTED,
                      font=FONTS["legend"])
        elif index == 1:
            draw.rounded_rectangle((cx - 145, cy - 130, cx + 145, cy + 130), radius=8,
                                   fill=BOARD, outline=BOARD_EDGE, width=3)
            draw.line((cx - 35, cy, cx + 35, cy), fill=ORANGE, width=4)
            draw.line((cx, cy - 35, cx, cy + 35), fill=ORANGE, width=4)
            draw.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=ORANGE)
            draw_arrow_2d(draw, (cx, cy - 12), (cx, cy - 105), BLUE_DARK, width=5, head=14)
            draw.text((cx + 18, cy - 108), "+Y / REAR", fill=BLUE_DARK,
                      font=FONTS["badge"])
            draw.text((cx - 126, cy + 150), "Transfer center AND direction", fill=MUTED,
                      font=FONTS["legend"])
        elif index == 2:
            draw.rounded_rectangle((cx - 145, cy - 130, cx + 145, cy + 130), radius=8,
                                   fill=BOARD, outline=BOARD_EDGE, width=3)
            draw.line((cx - 35, cy, cx + 35, cy), fill=ORANGE, width=4)
            draw.line((cx, cy - 35, cx, cy + 35), fill=ORANGE, width=4)
            draw_arrow_2d(draw, (cx, cy - 15), (cx + 95, cy - 120), ORANGE,
                          width=7, head=18)
            draw.polygon([(cx + 34, cy - 30), (cx + 125, cy - 130),
                          (cx + 146, cy - 86), (cx + 62, cy + 8)],
                         fill="#ffffff", outline="#b8c2ca")
            draw.text((cx - 123, cy + 150), "Marks remain on sealed board", fill=MUTED,
                      font=FONTS["legend"])
        else:
            # Exact 75:55 frame-to-tile proportion and actual ID0 artwork.
            outer = 210
            inner = int(outer * 55.0 / 75.0)
            draw.rectangle((cx - outer // 2, cy - outer // 2,
                            cx + outer // 2, cy + outer // 2),
                           outline=BLUE, width=16)
            tag = Image.open(FID_DIR / "tag36h11_id00_tile55_marker40.png").convert("RGB")
            tag = tag.resize((inner, inner), Image.Resampling.NEAREST)
            panel.paste(tag, (cx - inner // 2, cy - inner // 2))
            draw_arrow_2d(draw, (cx, cy - 15), (cx, cy - 150), BLUE_DARK,
                          width=5, head=14)
            draw.text((cx + 15, cy - 162), "+Y", fill=BLUE_DARK, font=FONTS["badge"])
            draw.text((cx - 133, cy + 150), "Square frame is removed after use", fill=MUTED,
                      font=FONTS["legend"])

    # Explicit controlled logical-label to AprilTag-ID map.
    mapping_y = 585
    draw.rounded_rectangle((24, mapping_y, 1434, 800), radius=15, fill=WHITE,
                           outline="#d4dce3", width=2)
    draw.text((46, mapping_y + 18), "CONTROLLED TAG MAP", fill=INK, font=FONTS["callout_bold"])
    ordered = ("T0", "T1", "T2", "T3", "K0", "P0")
    for index, name in enumerate(ordered):
        tag = LAYOUT["direct_tags"]["tags"][name]
        col = index % 3
        row = index // 3
        x = 48 + col * 455
        y = mapping_y + 68 + row * 64
        cx, cy = tag["detection_center_xy"]
        draw.rounded_rectangle((x, y, x + 420, y + 48), radius=10,
                               fill="#eef5fb", outline="#b8d5ec", width=1)
        draw.text((x + 14, y + 10),
                  f"{name} / ID {tag['id']}     center ({cx:g}, {cy:g}) mm",
                  fill=BLUE_DARK, font=FONTS["legend"])
    draw.text((1080, mapping_y + 20), "ALL TOP MARKS FACE +Y / REAR",
              fill=RED, font=FONTS["badge"])
    panel.save(output)


def main() -> None:
    steps = [
        (
            "01_prepare_board.png", "01", "PREPARE THE BOARD",
            "After cure and flatness acceptance, tape the verified 1:1 template and transfer centers.",
            scene_prepare_board, (0, 610, 0, 457, 0, 90), 59, -58,
            ["Seal both faces; cure fully; verify flatness before layout",
             "Blue: 4x 6 mm blind locator centers",
             "Orange: 9x M4 anchor centers; final bore follows selected anchor + scrap test"],
            "NO ROUTER / NO CNC",
        ),
        (
            "02_reinforce_and_clamp_arm.png", "02", "REINFORCE + CLAMP THE ARM",
            "Fit measured precut metal under the board, then use the factory load-bearing clamp.",
            scene_arm_support, (180, 430, 330, 470, -45, 105), 18, -62,
            ["Plate: measured footprint; minimum 3 mm aluminum or 2 mm steel",
             "Keep plate clear of feet, anchors and station hardware",
             "Factory clamp remains load bearing; verify the board stays flat"],
            "FACTORY CLAMP IS SCHEMATIC",
        ),
        (
            "03_install_keyboard_master.png", "03", "INSTALL KEYBOARD MASTER",
            "Seat the left station on its round and radial locator pins.",
            scene_left_station, (55, 285, 48, 280, 0, 115), 31, -58,
            ["2x locator pins set master position; lower squarely",
             "Start front + rear M4/washer retainers loosely",
             "Seat padded slider before the shared third M4/washer retainer"], None,
        ),
        (
            "04_join_keyboard_slave.png", "04", "JOIN KEYBOARD SLAVE",
            "Engage the right station with the master's round post and Y-relieving slot.",
            scene_keyboard_slave, (190, 440, 52, 275, 0, 110), 27, -57,
            ["Align both seam sockets before lowering; no right-side board pins",
             "Start front + rear M4/washer retainers loosely",
             "Seat padded slider before shared third M4; all 3x M4s only clamp"], None,
        ),
        (
            "05_load_keyboard_and_clamps.png", "05", "LOAD AND CLAMP KEYBOARD",
            "Place the keyboard on the board, then slide both rear clamps forward gently.",
            scene_keyboard_device, (55, 430, 54, 300, 0, 125), 29, -58,
            ["Keyboard rests directly on the sealed board", "Rear face pads touch the case - no bending force",
             "Third retainer passes through slider + station into board anchor"], None,
        ),
        (
            "06_install_phone_tcp_station.png", "06", "INSTALL PHONE + TCP STATION",
            "Seat the combined station on its two locator pins before adding hardware.",
            scene_phone_station, (392, 610, 52, 270, 0, 125), 31, -58,
            ["2x locator pins: round socket fixes XY; Y-slot relieves the axis",
             "Install 1x TCP-side M4 + washer only",
             "PT-HOLD-R1/R2 remain empty until the rail is seated in Step 07"], None,
        ),
        (
            "07_seat_phone_rail_and_cartridge.png", "07", "SEAT RAIL + TCP CARTRIDGE",
            "Engage the rail keys first; place the keyed cartridge fully into its receiver.",
            scene_rail_and_puck, (398, 610, 60, 270, 0, 120), 27, -57,
            ["Rail must sit flat on both locating keys", "Clipped cartridge corner permits only one orientation",
             "Do not insert the 2x shared rail screws until both parts are seated"], None,
        ),
        (
            "08_install_phone_service_hardware.png", "08", "INSTALL SERVICE HARDWARE",
            "With the rail seated, add its shared board screws, clamp nuts and TCP screws.",
            scene_phone_hardware, (400, 610, 58, 272, 0, 110), 26, -58,
            ["Install 2x shared rail/station M4 screws + washers",
             "Drop 2x M4 clamp nuts from the top",
             "Install 2x M3 TCP screws; verify cartridge remains flush"], None,
        ),
        (
            "09_load_phone_and_route_cable.png", "09", "LOAD PHONE + ROUTE CABLE",
            "Seat the measured phone/case, retain the USB lead, then advance soft clamp tips.",
            scene_phone_and_cable, (425, 610, 38, 270, 0, 85), 27, -58,
            ["USB plug and bend radius remain unstressed", "Cable exits toward the front through the saddle",
             "TPU tips avoid buttons, camera bump and screen edge"], None,
        ),
        (
            "10_verify_phone_no_go_zones.png", "10", "VERIFY PHONE NO-GO ZONES",
            "Red zones are measurement reminders - not released positions - before either clamp is tightened.",
            scene_phone_no_go, (475, 610, 62, 260, 0, 80), 54, -90,
            ["Screen edge: soft tips remain below glass/bezel",
             "Camera bump: measure actual case protrusion and keep clear",
             "Side buttons: map power/volume positions and keep clear",
             "USB: preserve connector body and measured bend radius"],
            "RED = MEASURED NO-GO",
        ),
        (
            "11_transfer_tag_marks.png", "11", "TRANSFER TAG CENTERS + DIRECTION",
            "Register the 1:1 template, transfer center and +Y marks, then remove all paper.",
            render_tag_transfer_body, None, 0, 0,
            ["Do not glue through the paper template",
             "Logical labels map exactly to IDs 0-5 as shown",
             "Use the transferred +Y mark to prevent a 90° tag rotation"],
            "TEMPLATE → MARKS → SQUARE FRAME",
        ),
        (
            "12_apply_apriltags.png", "12", "APPLY THE SIX APRILTAGS",
            "Place the square 55 mm frame on transferred marks; keep every tag top facing +Y.",
            scene_tags, (0, 610, 0, 457, 0, 90), 61, -58,
            ["Apply directly to the cured sealed board", "Repeat T0, T1, T2, T3, K0 and P0",
             "Remove tool; measure center, yaw and optical plane Z"],
            "SQUARE FRAME = TOOL - REMOVE IT",
        ),
        (
            "13_mount_camera_and_check_fov.png", "13", "CAMERA ARCHITECTURE HOLD",
            "Intended arm-mounted camera is not yet defined. The image shows the fixed-mast fallback only - do not build Step 13.",
            scene_camera_fov, (0, 735, 0, 457, 0, 385), 23, -58,
            ["STOP: exact camera, carrying link/frame and mount are required",
             "Add camera mass/COM, moving-cable sweep, reach and collision proof",
             "Define eye-in-hand calibration, timing and tag visibility by pose"],
            "FALLBACK SHOWN - NOT RELEASED",
        ),
        (
            "14_assemble_compliant_tool.png", "14", "ASSEMBLE COMPLIANT TOOL",
            "Build and qualify each selected contact route one at a time, then calibrate its TCP.",
            scene_compliant_tool, (-20, 165, -10, 88, -100, 170), 18, -58,
            ["Blue: configured body, keyed cap and selected adapter/collar",
             "Orange: spring + 2x M3 cap screws",
             "Select one or both routes; never install both route stacks simultaneously",
             "After every tool change: verify travel, retention and recalibrate TCP"],
            "CONTACT TOOL - NOT A HARD STOP",
        ),
        (
            "15_final_cell.png", "15", "FINAL ASSEMBLY CHECK",
            "Verify every station is seated, every device is gentle and every datum is visible.",
            scene_final, (0, 610, 0, 457, 0, 125), 31, -58,
            ["Black rear cylinder = RoArm keep-out proxy, not released clamp CAD",
             "Run 10x station remove/reinstall cycles; calibrate board + TCP",
             "Run empty-cell motion before keyboard or phone contact"], "RC03-INT-R1",
        ),
    ]

    with tempfile.TemporaryDirectory(prefix="rc03_assembly_render_") as tmp:
        tmp_dir = Path(tmp)
        for filename, number, title, subtitle, factory, focus, elev, azim, callouts, badge in steps:
            raw = tmp_dir / filename
            if factory is render_tag_transfer_body:
                render_tag_transfer_body(raw)
            else:
                items, textures = factory()
                render_body(items, textures, raw, focus, elev=elev, azim=azim)
            compose_step(raw, OUT_DIR / filename, number, title, subtitle, callouts, badge)
            print(f"rendered {OUT_DIR / filename}")

    # Remove only filenames generated by the earlier ten-panel draft.  Never
    # sweep unrelated user assets from the guide directory.
    expected = {step[0] for step in steps}
    previous_managed = {
        "02_install_keyboard_master.png",
        "03_join_keyboard_slave.png",
        "04_load_keyboard_and_clamps.png",
        "05_install_phone_tcp_station.png",
        "06_seat_phone_rail_and_cartridge.png",
        "07_install_phone_service_hardware.png",
        "08_load_phone_and_route_cable.png",
        "09_apply_apriltags.png",
        "10_final_cell.png",
    }
    for stale_name in sorted(previous_managed - expected):
        stale_path = OUT_DIR / stale_name
        if stale_path.exists():
            stale_path.unlink()


if __name__ == "__main__":
    main()
