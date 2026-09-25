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
    board_t = L["board"]["thickness"]
    kb = L["keyboard"]
    ph = L["phone"]
    cp = L["calibration_puck"]
    kb_half = kb["outer_envelope"][0] / 2
    base_z = 65.0 if exploded else board_t
    clamp_z = 100.0 if exploded else board_t
    phone_z = 80.0 if exploded else board_t
    puck_z = 60.0 if exploded else board_t

    items = [(box((L["board"]["width"], L["board"]["depth"], board_t), (0, 0, 0)),
              "#b89b70", 1.0)]
    items += [
        (load_part("keyboard_tray_left.stl", (kb["origin_xy"][0], kb["origin_xy"][1], base_z)), "#176fc2", 1.0),
        (load_part("keyboard_tray_right.stl", (kb["origin_xy"][0] + kb_half, kb["origin_xy"][1], base_z)), "#176fc2", 1.0),
        (load_part("keyboard_rear_clamp.stl", (kb["origin_xy"][0] + 85 - 26,
                                                kb["origin_xy"][1] + P["keyboard_tray_wall_t"] + P["keyboard_d"] + 0.5,
                                                clamp_z)), "#23853f", 1.0),
        (load_part("keyboard_rear_clamp.stl", (kb["origin_xy"][0] + 240 - 26,
                                                kb["origin_xy"][1] + P["keyboard_tray_wall_t"] + P["keyboard_d"] + 0.5,
                                                clamp_z)), "#23853f", 1.0),
        (load_part("phone_cradle_a16.stl", (ph["origin_xy"][0], ph["origin_xy"][1], phone_z)), "#cf3b29", 1.0),
        (load_part("calibration_puck.stl", (cp["origin_xy"][0], cp["origin_xy"][1], puck_z)), "#e5a714", 1.0),
    ]
    tag_ids = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "K0": 4, "P0": 5}
    for index, (name, (x, y)) in enumerate(L["tags"].items()):
        z = 45 + index * 6 if exploded else board_t
        items.append((load_part(f"tag_frame_ID{tag_ids[name]}_55mm.stl", (x, y, z)), "#eeeeee", 1.0))

    if not exploded:
        items += [
            (box((P["keyboard_w"], P["keyboard_d"], P["keyboard_h"]),
                 (kb["origin_xy"][0] + P["keyboard_tray_wall_t"] + P["keyboard_clearance"],
                  kb["origin_xy"][1] + P["keyboard_tray_wall_t"] + P["keyboard_clearance"],
                  board_t + P["keyboard_tray_base_t"])), "#202026", 1.0),
            (box((P["phone_w"], P["phone_l"], P["phone_t"]),
                 (ph["origin_xy"][0] + 15 + 3.2 + P["phone_clearance"],
                  ph["origin_xy"][1] + 3.2 + P["phone_clearance"], board_t + 4.0)), "#10141d", 1.0),
            (cylinder(150, 5, (305, 420, board_t)), "#777777", 0.24),
            (cylinder(88, 70, (305, 420, board_t)), "#33333b", 1.0),
        ]
    return items


def render_montage() -> None:
    parts = [
        ("keyboard_tray_left.stl", "Keyboard tray - left"),
        ("keyboard_tray_right.stl", "Keyboard tray - right"),
        ("phone_cradle_a16.stl", "A16 cradle"),
        ("keyboard_rear_clamp.stl", "Keyboard rear clamp"),
        ("phone_clamp_tip_TPU_M4.stl", "TPU phone clamp tip"),
        ("tag_frame_ID0_55mm.stl", "Tag frame ID0 / T0"),
        ("tag_frame_ID1_55mm.stl", "Tag frame ID1 / T1"),
        ("tag_frame_ID2_55mm.stl", "Tag frame ID2 / T2"),
        ("tag_frame_ID3_55mm.stl", "Tag frame ID3 / T3"),
        ("tag_frame_ID4_55mm.stl", "Tag frame ID4 / K0"),
        ("tag_frame_ID5_55mm.stl", "Tag frame ID5 / P0"),
        ("calibration_puck.stl", "TCP calibration puck"),
        ("compliant_tool_body.stl", "Compliant tool body"),
        ("compliant_tool_top_cap.stl", "Compliant tool cap"),
        ("stylus_collar_9mm.stl", "9 mm stylus collar"),
        ("rod_bushing_6_to_9mm.stl", "6 mm rod adapter"),
        ("keyboard_tip_TPU_6mm.stl", "TPU keyboard tip"),
        ("camera_plate_universal.stl", "Camera plate"),
        ("mast_foot_2020.stl", "2020 mast foot"),
        ("keyboard_seam_fit_male.stl", "Keyboard seam - male"),
        ("keyboard_seam_fit_female.stl", "Keyboard seam - female"),
        ("phone_width_fit_test.stl", "Phone width coupon"),
        ("keyboard_corner_fit_test.stl", "Keyboard corner coupon"),
        ("hardware_fit_gauge.stl", "Hardware fit ladder"),
        ("m4_washer_fit_gauge.stl", "M4 washer recess ladder"),
        ("m3_head_fit_gauge.stl", "M3 head recess ladder"),
        ("m3_insert_fit_gauge.stl", "M3 insert ladder"),
        ("m4_horizontal_insert_fit_gauge.stl", "Horizontal M4 insert ladder"),
        ("m5_nut_trap_fit_gauge.stl", "M5 nut-trap ladder"),
        ("setup_hardware_fit_gauge.stl", "Heads / washers / camera hex"),
        ("thread_pilot_fit_gauge.stl", "M2/M3 thread-pilot ladder"),
        ("cable_tie_saddle_fit_gauge.stl", "Cable-tie saddle ladder"),
        ("mast_socket_fit_test.stl", "2020 socket ladder"),
        ("tpu_tip_retention_gauge.stl", "TPU retention gauge"),
        ("stylus_diameter_gauge.stl", "Stylus diameter ladder"),
        ("compliant_tool_grip_fit_test.stl", "RoArm grip coupon"),
        ("spring_fit_gauge.stl", "Spring OD/ID gauge"),
    ]
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
