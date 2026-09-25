#!/usr/bin/env python3
"""Render package previews directly from STL meshes without OpenSCAD."""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
import trimesh
from PIL import Image, ImageChops
from vtkmodules.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
from vtkmodules.vtkIOImage import vtkPNGWriter
from vtkmodules.vtkRenderingCore import (
    vtkActor, vtkPolyDataMapper, vtkRenderer, vtkRenderWindow,
    vtkWindowToImageFilter,
)
import vtkmodules.vtkRenderingOpenGL2  # noqa: F401 - registers OpenGL backend

ROOT = Path(__file__).resolve().parents[1]
STL = ROOT / "stl"
IMG = ROOT / "images"
IMG.mkdir(exist_ok=True)
P = json.loads((ROOT / "config" / "parameters.json").read_text())
L = json.loads((ROOT / "config" / "workcell_layout.json").read_text())


def load_part(filename: str, xyz=(0.0, 0.0, 0.0)) -> trimesh.Trimesh:
    mesh = trimesh.load_mesh(STL / filename, force="mesh").copy()
    mesh.apply_translation(xyz)
    return mesh


def box(extents, xyz) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation((xyz[0] + extents[0] / 2,
                            xyz[1] + extents[1] / 2,
                            xyz[2] + extents[2] / 2))
    return mesh


def cylinder(diameter, height, xyz) -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=diameter / 2, height=height, sections=64)
    mesh.apply_translation((xyz[0], xyz[1], xyz[2] + height / 2))
    return mesh


def add_mesh(ax, mesh: trimesh.Trimesh, color, alpha=1.0) -> None:
    collection = Poly3DCollection(mesh.triangles, linewidths=0, alpha=alpha)
    collection.set_facecolor(color)
    collection.set_edgecolor("none")
    ax.add_collection3d(collection)


def set_equal_view(ax, meshes, elev=28, azim=-58, pad=0.04) -> None:
    bounds = np.array([mesh.bounds for mesh in meshes])
    mins = bounds[:, 0, :].min(axis=0)
    maxs = bounds[:, 1, :].max(axis=0)
    center = (mins + maxs) / 2
    radius = max(maxs - mins) * (0.5 + pad)
    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(max(0, center[2] - radius), center[2] + radius)
    ax.view_init(elev=elev, azim=azim)
    ax.set_proj_type("ortho")
    ax.set_axis_off()


def render_scene(items, output: Path, elev=28, azim=-58) -> None:
    renderer = vtkRenderer()
    renderer.SetBackground(to_rgb("#fffdec"))
    window = vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(1600, 1100)
    window.AddRenderer(renderer)

    bounds = np.array([mesh.bounds for mesh, _, _ in items])
    center = (bounds[:, 0, :].min(axis=0) + bounds[:, 1, :].max(axis=0)) / 2

    for mesh, color, alpha in items:
        points = vtkPoints()
        points.SetData(numpy_to_vtk(np.asarray(mesh.vertices), deep=True))
        encoded_faces = np.column_stack(
            (np.full(len(mesh.faces), 3, dtype=np.int64), np.asarray(mesh.faces, dtype=np.int64))
        ).ravel()
        cells = vtkCellArray()
        cells.SetCells(len(mesh.faces), numpy_to_vtkIdTypeArray(encoded_faces, deep=True))
        poly = vtkPolyData()
        poly.SetPoints(points)
        poly.SetPolys(cells)
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(poly)
        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(to_rgb(color))
        actor.GetProperty().SetOpacity(alpha)
        renderer.AddActor(actor)

    azimuth = math.radians(azim)
    elevation = math.radians(elev)
    view = np.array([
        math.cos(elevation) * math.cos(azimuth),
        math.cos(elevation) * math.sin(azimuth),
        math.sin(elevation),
    ])
    camera = renderer.GetActiveCamera()
    camera.SetFocalPoint(*center)
    camera.SetPosition(*(center + view * 1200))
    camera.SetViewUp(0, 0, 1)
    camera.ParallelProjectionOn()
    renderer.ResetCamera()
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

    rendered = Image.open(output).convert("RGB")
    background = Image.new("RGB", rendered.size, "#fffdec")
    bounds = ImageChops.difference(rendered, background).getbbox()
    if bounds:
        padding = 24
        left = max(0, bounds[0] - padding)
        top = max(0, bounds[1] - padding)
        right = min(rendered.width, bounds[2] + padding)
        bottom = min(rendered.height, bounds[3] + padding)
        rendered.crop((left, top, right, bottom)).save(output)


def assembly_items(exploded=False):
    """Build an RC03 preview from the generated schema-v3 layout.

    The CAD coordinate system uses the finished board top as Z=0.  The preview
    draws the board upward from Z=0, so every installed item receives a visual
    offset equal to the board thickness.  This is a rendering convention only;
    the controlled dimensions remain those in ``workcell_layout.json``.
    """
    board = L["board"]
    board_t = float(board["thickness"])
    top = board_t
    station_lift = 54.0 if exploded else 0.0
    service_lift = 86.0 if exploded else 0.0
    device_lift = 116.0 if exploded else 0.0
    tag_lift = 24.0 if exploded else 0.0

    items = [
        (box((board["width"], board["depth"], board_t), (0, 0, 0)), "#b89b70", 1.0)
    ]

    station_colors = {
        "keyboard_left": "#176fc2",
        "keyboard_right": "#2b86cd",
        "phone_tcp": "#cf3b29",
    }
    for station_name in ("keyboard_left", "keyboard_right", "phone_tcp"):
        station = L["stations"][station_name]
        ox, oy = station["origin_xy"]
        items.append((
            load_part(f"{station['part']}.stl", (ox, oy, top + station_lift)),
            station_colors[station_name], 1.0,
        ))

    # Replaceable service parts are shown in their nominal installed positions.
    left_hold_x = next(f["x"] for f in L["board_features"] if f["id"] == "KBL-CLAMP")
    right_hold_x = next(f["x"] for f in L["board_features"] if f["id"] == "KBR-CLAMP")
    clamp_hold_y = next(f["y"] for f in L["board_features"] if f["id"] == "KBL-CLAMP")
    for hold_x in (left_hold_x, right_hold_x):
        items.append((
            load_part("keyboard_rear_clamp.stl", (hold_x - 26.0, clamp_hold_y - 22.5,
                                                   top + 4.0 + service_lift)),
            "#23853f", 1.0,
        ))

    phone_station = L["stations"]["phone_tcp"]
    phx, phy = phone_station["origin_xy"]
    phone_rail_x = P["phone_x"] + 15.0 + (
        P["phone_w"] + P["phone_case_extra_w"] + 2 * P["phone_clearance"] + 6.4
    ) - 3.2
    items += [
        (load_part("phone_clamp_rail.stl", (phone_rail_x, phy, top + 4.0 + service_lift)),
         "#8a3eb5", 1.0),
        (load_part("calibration_puck.stl", (phx + 15.0, phy + 85.0,
                                             top + 6.5 + service_lift)),
         "#e5a714", 1.0),
    ]

    # Direct-applied tags: white 55 mm stock with a 40 mm dark detection area.
    tile = float(L["direct_tags"]["tile_size_mm"])
    edge = float(L["direct_tags"]["detection_edge_mm"])
    for tag in L["direct_tags"]["tags"].values():
        x, y = tag["tile_origin_xy"]
        z = top + 0.08 + tag_lift
        items.append((box((tile, tile, 0.35), (x, y, z)), "#f7f7f2", 1.0))
        inset = (tile - edge) / 2
        items.append((box((edge, edge, 0.10), (x + inset, y + inset, z + 0.35)),
                      "#16191d", 1.0))

    keyboard = L["devices"]["keyboard"]
    phone = L["devices"]["phone"]
    kx, ky = keyboard["nominal_origin_xy"]
    px, py = phone["nominal_origin_xy"]
    kw, kd, kh = keyboard["nominal_size"]
    pw, pd, pt = phone["configured_size"]
    items += [
        (box((kw, kd, kh), (kx, ky, top + device_lift)), "#202026", 1.0),
        (box((pw, pd, pt), (px, py, top + phone["support_plane_z"] + device_lift)),
         "#10141d", 1.0),
    ]

    if not exploded:
        # A neutral arm keepout proxy communicates scale without asserting the
        # unmeasured factory-clamp geometry as released CAD.
        items += [
            (cylinder(150, 5, (305, 420, top)), "#777777", 0.24),
            (cylinder(88, 70, (305, 420, top)), "#33333b", 1.0),
        ]
    return items


def render_montage() -> None:
    labels = {
        "keyboard_station_left": "Keyboard station - left/master",
        "keyboard_station_right": "Keyboard station - right/slave",
        "phone_tcp_station": "Phone + TCP service station",
        "phone_clamp_rail": "Replaceable phone clamp rail",
        "tag_application_frame_55mm": "Reusable direct-tag placement tool",
        "calibration_puck": "Keyed TCP datum cartridge",
        "station_locator_fit_gauge": "Round/radial locator ladder",
        "m4_captive_nut_fit_gauge": "Phone-rail M4 nut-channel ladder",
    }
    parts = []
    for path in sorted(STL.glob("*.stl")):
        if path.name == "BOARD_REFERENCE_DO_NOT_PRINT.stl":
            continue
        stem = path.stem
        label = labels.get(stem, stem.replace("_", " ").replace("TPU", "TPU"))
        parts.append((path.name, label))
    rows = math.ceil(len(parts) / 4)
    fig = plt.figure(figsize=(12, rows * 3.3), facecolor="white")
    for index, (filename, label) in enumerate(parts, 1):
        ax = fig.add_subplot(rows, 4, index, projection="3d")
        mesh = load_part(filename)
        add_mesh(ax, mesh, "#2478c5")
        set_equal_view(ax, [mesh], elev=26, azim=-55, pad=0.10)
        ax.set_title(label, fontsize=8, loc="left", pad=2)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01, wspace=0.02, hspace=0.08)
    fig.savefig(IMG / "parts_montage.png", dpi=100, facecolor="white")
    plt.close(fig)


def main() -> None:
    render_scene(assembly_items(False), IMG / "assembly_isometric.png")
    render_scene(assembly_items(True), IMG / "assembly_exploded.png")
    render_montage()
    print("rendered previews")


if __name__ == "__main__":
    main()
