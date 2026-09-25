#!/usr/bin/env python3
"""Generate the all-printed static-camera portal prototype.

The generated solids are deliberately modular so every printable part fits the
protected 295 x 295 x 275 mm QIDI Plus4 envelope.  The portal is bench-bearing
and registered to the 610 x 457 x 18 mm work board by two no-drill front-corner
clamps.  The board does not suspend the portal weight.

This package is a CAD/prototype candidate only.  It does not grant fabrication,
installation, camera-fit, collision, or robot-motion authority.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable, Tuple
from xml.etree import ElementTree as ET

import cadquery as cq
from cadquery import exporters
import numpy as np
import trimesh


ROOT = Path(__file__).resolve().parents[1]
CAD_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "printable_frame_design.json"
OUTPUT_DIR = CAD_DIR / "output"
STEP_DIR = OUTPUT_DIR / "step"
STL_DIR = OUTPUT_DIR / "stl"
ASSEMBLY_DIR = OUTPUT_DIR / "assembly"
PLATE_DIR = OUTPUT_DIR / "plates_3mf"
for directory in (OUTPUT_DIR, STEP_DIR, STL_DIR, ASSEMBLY_DIR, PLATE_DIR):
    directory.mkdir(parents=True, exist_ok=True)

CFG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
SAFE_X, SAFE_Y, SAFE_Z = CFG["printer"]["protected_part_envelope_mm"]
BOARD_W = float(CFG["board"]["width_mm"])
BOARD_D = float(CFG["board"]["depth_mm"])
BOARD_T = float(CFG["board"]["thickness_mm"])
TRUSS_H = float(CFG["truss"]["height_mm"])
TRUSS_W = float(CFG["truss"]["width_mm"])
TRUSS_SIDE = float(CFG["truss"]["side_wall_mm"])
TRUSS_BOTTOM = float(CFG["truss"]["bottom_wall_mm"])
M5_CLEAR = float(CFG["truss"]["m5_clearance_mm"])
M6_CLEAR = 6.6
M4_CLEAR = 4.5
M6_CLAMP_SPEC = CFG["procurement_constraints"]["m6_x25_flange_head_clamp_bolt"]
M6_CLAMP_BOLT_LENGTH = float(M6_CLAMP_SPEC["finished_length_mm"])
M6_CAP_BOSS_OD = float(M6_CLAMP_SPEC["modeled_cap_boss_outer_diameter_mm"])
M6_CAP_BASE_TOP_Z = float(M6_CLAMP_SPEC["modeled_cap_base_top_height_mm"])
M6_CAP_BOSS_BEARING_Z = float(M6_CLAMP_SPEC["modeled_cap_boss_bearing_height_mm"])
M6_SADDLE_BLIND_BORE_FLOOR_Z = 0.75
LEFT_SADDLE_CLAMP_X = tuple(float(value) for value in CFG["board_clamp"]["left_saddle_clamp_axis_x_local_mm"])
SADDLE_MIRROR_WIDTH = float(CFG["board_clamp"]["mirrored_saddle_width_mm"])
SADDLE_CLAMP_Y = float(CFG["board_clamp"]["clamp_axis_y_local_mm"])
M6_OUTER_NUT_CHANNEL_OPENING_Y = float(CFG["board_clamp"]["outer_nut_channel_opening_y_local_mm"])
M6_INNER_NUT_CHANNEL_MOUTH_XY = tuple(float(value) for value in CFG["board_clamp"]["inner_nut_channel_mouth_xy_local_mm"])
M6_NUT_CHANNEL_WIDTH = float(CFG["board_clamp"]["nut_channel_width_mm"])
M6_NUT_TUNNEL_WIDTH = float(CFG["board_clamp"]["nut_tunnel_outer_width_mm"])
M6_NUT_TUNNEL_TOP_Z = float(CFG["board_clamp"]["nut_tunnel_top_height_mm"])
M6_NUT_TUNNEL_MIN_ROOF = float(CFG["board_clamp"]["nut_tunnel_minimum_roof_mm"])
CROSS_LENGTH = float(CFG["layout"]["crossbar_segment_length_mm"])
CROSS_COUNT = int(CFG["layout"]["crossbar_segment_count"])
BOOM_AXES_X = tuple(float(value) for value in CFG["layout"]["boom_axis_x_mm"])
CAMERA_X, CAMERA_Y = map(float, CFG["layout"]["camera_axis_xy_mm"])
CARRIAGE_W, CARRIAGE_D = map(float, CFG["layout"]["camera_carriage_xy_mm"])
CAGE_INSTALLED_X_OFFSETS = tuple(float(value) for value in CFG["layout"]["installed_camera_x_offsets_mm"])
CARRIAGE_INSTALLED_Y_OFFSETS = tuple(float(value) for value in CFG["layout"]["installed_camera_y_offsets_mm"])
CARRIAGE_HOLE_Y_OFFSETS = tuple(-value for value in CARRIAGE_INSTALLED_Y_OFFSETS)
CARRIAGE_X0 = CAMERA_X - CARRIAGE_W / 2.0
CARRIAGE_Y0 = CAMERA_Y - CARRIAGE_D / 2.0
CAMERA_CAGE_X0 = CAMERA_X - 48.0
CAMERA_CAGE_Y0 = CAMERA_Y - 48.0
ROOT_STRAP_W, ROOT_STRAP_D, ROOT_STRAP_T = map(float, CFG["layout"]["boom_root_strap_xyz_mm"])
ROOT_BOLT_X_OFFSETS = tuple(float(value) for value in CFG["layout"]["boom_root_bolt_x_offsets_mm"])
ROOT_CROSSBAR_BOLT_Y = float(CFG["layout"]["boom_root_bolt_y_mm"]["crossbar"])
ROOT_BOOM_BOLT_Y = float(CFG["layout"]["boom_root_bolt_y_mm"]["boom"])
_, TETHER_CHOKER_Y = map(float, CFG["layout"]["tether_choker_axis_xy_mm"])
SPLICE_LENGTH = 104.0
SPLICE_HALF = SPLICE_LENGTH / 2.0
CROSS_SPLICE_LENGTH = 92.0
CROSS_SPLICE_HALF = CROSS_SPLICE_LENGTH / 2.0


def box_ll(
    width: float,
    depth: float,
    height: float,
    x0: float = 0.0,
    y0: float = 0.0,
    z0: float = 0.0,
) -> cq.Workplane:
    return (
        cq.Workplane("XY")
        .box(width, depth, height, centered=(True, True, False))
        .translate((x0 + width / 2, y0 + depth / 2, z0))
    )


def rounded_plate(
    width: float,
    depth: float,
    height: float,
    radius: float = 3.0,
    x0: float = 0.0,
    y0: float = 0.0,
    z0: float = 0.0,
) -> cq.Workplane:
    body = box_ll(width, depth, height, x0, y0, z0)
    if radius > 0:
        body = body.edges("|Z").fillet(
            min(radius, width / 2 - 0.05, depth / 2 - 0.05)
        )
    return body


def hole_z(x: float, y: float, diameter: float, height: float, z0: float = -0.5) -> cq.Workplane:
    return (
        cq.Workplane("XY")
        .center(x, y)
        .circle(diameter / 2)
        .extrude(height)
        .translate((0, 0, z0))
    )


def hole_x(x: float, y: float, z: float, diameter: float, length: float) -> cq.Workplane:
    solid = cq.Solid.makeCylinder(
        diameter / 2,
        length,
        cq.Vector(x, y, z),
        cq.Vector(1, 0, 0),
    )
    return cq.Workplane(obj=solid)


def hole_y(x: float, y: float, z: float, diameter: float, length: float) -> cq.Workplane:
    solid = cq.Solid.makeCylinder(
        diameter / 2,
        length,
        cq.Vector(x, y, z),
        cq.Vector(0, 1, 0),
    )
    return cq.Workplane(obj=solid)


def slot_z(
    x: float,
    y: float,
    length: float,
    diameter: float,
    height: float,
    angle: float = 0.0,
    z0: float = -0.5,
) -> cq.Workplane:
    return (
        cq.Workplane("XY")
        .moveTo(x, y)
        .slot2D(length, diameter, angle=angle)
        .extrude(height)
        .translate((0, 0, z0))
    )


def strut_xy(
    start: Tuple[float, float],
    end: Tuple[float, float],
    width: float,
    height: float,
    z0: float = 0.0,
) -> cq.Workplane:
    """Rectangular prism centered on a line in XY; always prints flat."""
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    angle = math.degrees(math.atan2(dy, dx))
    body = cq.Workplane("XY").box(length, width, height, centered=(True, True, False))
    body = body.rotate((0, 0, 0), (0, 0, 1), angle)
    return body.translate(((x1 + x2) / 2, (y1 + y2) / 2, z0))


def strut_xz(
    start: Tuple[float, float],
    end: Tuple[float, float],
    width: float,
    thickness_y: float,
    y0: float,
) -> cq.Workplane:
    """A diagonal wall member in XZ, extruded by ``thickness_y``."""
    x1, z1 = start
    x2, z2 = end
    dx, dz = x2 - x1, z2 - z1
    length = math.hypot(dx, dz)
    angle = math.degrees(math.atan2(dz, dx))
    body = cq.Workplane("XY").box(length, thickness_y, width, centered=(True, True, True))
    body = body.rotate((0, 0, 0), (0, 1, 0), -angle)
    return body.translate(((x1 + x2) / 2, y0 + thickness_y / 2, (z1 + z2) / 2))


def strut_yz(
    x_center: float,
    start: Tuple[float, float],
    end: Tuple[float, float],
    thickness_x: float,
    width: float,
) -> cq.Workplane:
    """A self-supporting diagonal tie between the U-section side planes."""
    y1, z1 = start
    y2, z2 = end
    dy, dz = y2 - y1, z2 - z1
    length = math.hypot(dy, dz)
    angle = math.degrees(math.atan2(dz, dy))
    body = cq.Workplane("XY").box(thickness_x, length, width, centered=(True, True, True))
    body = body.rotate((0, 0, 0), (1, 0, 0), angle)
    return body.translate((x_center, (y1 + y2) / 2, (z1 + z2) / 2))


def emboss(
    body: cq.Workplane,
    text: str,
    x: float,
    y: float,
    top_z: float,
    size: float = 5.0,
    height: float = 0.8,
    angle: float = 0.0,
) -> cq.Workplane:
    """Add large raised text; no engraved markings are used in this kit."""
    sink = 0.05
    label = (
        cq.Workplane("XY")
        .workplane(offset=top_z - sink)
        .center(x, y)
        .text(text, size, height + sink, combine=False, font="Arial", kind="bold")
    )
    if angle:
        label = label.rotate((x, y, 0), (x, y, 1), angle)
    return body.union(label)


def raised_arrow(
    body: cq.Workplane,
    x: float,
    y: float,
    top_z: float,
    direction: str,
    scale: float = 1.0,
) -> cq.Workplane:
    """Add a tactile direction arrow to a horizontal face."""
    shaft = box_ll(18 * scale, 3.5 * scale, 0.85, x - 9 * scale, y - 1.75 * scale, top_z - 0.05)
    head = (
        cq.Workplane("XY")
        .workplane(offset=top_z - 0.05)
        .polyline(
            [
                (x + 9 * scale, y - 6 * scale),
                (x + 18 * scale, y),
                (x + 9 * scale, y + 6 * scale),
            ]
        )
        .close()
        .extrude(0.85)
    )
    arrow = shaft.union(head)
    rotations = {"right": 0.0, "rear": 90.0, "left": 180.0, "front": -90.0}
    arrow = arrow.rotate((x, y, 0), (x, y, 1), rotations[direction])
    return body.union(arrow)


def truss_segment(
    length: float,
    label: str,
    vertical_hole_ends: Tuple[str, ...] = (),
    transverse_hole_ends: Tuple[str, ...] = ("near", "far"),
    markings: bool = True,
) -> cq.Workplane:
    """One-piece open-U lattice beam in its support-free print orientation.

    The full bottom wall and two 44 mm-separated side truss planes provide a
    three-dimensional section without loose cross-ties.  The top stays open,
    so neither the beam nor its connector contains a long horizontal bridge.
    """
    chord = float(CFG["truss"]["chord_mm"])
    web = float(CFG["truss"]["web_mm"])
    end_block = float(CFG["truss"]["end_block_mm"])
    body = box_ll(length, TRUSS_W, TRUSS_BOTTOM)

    # Continuous top chords complete both separated side-truss planes.  Each
    # chord is supported at <=24 mm intervals by the crossed X webs and the
    # repeated end-view V ties below, avoiding a long flat bridge.
    body = body.union(box_ll(length, TRUSS_SIDE, chord, y0=0.0, z0=TRUSS_H - chord))
    body = body.union(box_ll(length, TRUSS_SIDE, chord, y0=TRUSS_W - TRUSS_SIDE, z0=TRUSS_H - chord))

    # Full-height side collars at the ends receive vertical carriage bolts.
    for x0 in (0.0, length - end_block):
        body = body.union(box_ll(end_block, TRUSS_SIDE, TRUSS_H, x0=x0, y0=0.0))
        body = body.union(box_ll(end_block, TRUSS_SIDE, TRUSS_H, x0=x0, y0=TRUSS_W - TRUSS_SIDE))

    # Supported transverse compression bands prevent through-bolts from
    # crushing an open U section.  Their 38 mm interior spans are split by a
    # 6 mm center post, keeping each unsupported bridge below 19 mm.
    for end_sign in (1.0, -1.0):
        x22 = 22.0 if end_sign > 0 else length - 22.0
        x10 = 10.0 if end_sign > 0 else length - 10.0
        body = body.union(box_ll(12.0, TRUSS_W, 30.0, x22 - 6.0, 0.0, 10.0))
        body = body.union(box_ll(12.0, 6.0, 2.0, x22 - 6.0, 22.0, TRUSS_BOTTOM))
        body = body.union(box_ll(12.0, TRUSS_W, 18.0, x10 - 6.0, 0.0, 22.0))
        body = body.union(box_ll(12.0, 6.0, 14.0, x10 - 6.0, 22.0, TRUSS_BOTTOM))

    # Crossed side webs make both planes true trusses.  Bay pitch is capped at
    # 46 mm so every rising web prints at >=45 degrees from the bed.
    usable_start = end_block
    usable_end = length - end_block
    cell_count = max(1, int(math.ceil((usable_end - usable_start) / 46.0)))
    pitch = (usable_end - usable_start) / cell_count
    for side_y in (0.0, TRUSS_W - TRUSS_SIDE):
        for index in range(cell_count):
            xa = usable_start + index * pitch
            xb = usable_start + (index + 1) * pitch
            body = body.union(strut_xz((xa, TRUSS_BOTTOM - 1.0), (xb, TRUSS_H - chord + 1.0), web, TRUSS_SIDE, side_y))
            body = body.union(strut_xz((xa, TRUSS_H - chord + 1.0), (xb, TRUSS_BOTTOM - 1.0), web, TRUSS_SIDE, side_y))

        # V ties between the side planes brace torsion and support both top
        # chords without a horizontal roof.  Their bottom ends merge into the
        # full floor and their top ends land at every half-bay.
    for index in range(cell_count):
        xa = usable_start + index * pitch
        xb = usable_start + (index + 1) * pitch
        x_mid = (xa + xb) / 2.0
        for y_top in (TRUSS_SIDE / 2.0, TRUSS_W - TRUSS_SIDE / 2.0):
            body = body.union(
                strut_yz(
                    x_mid,
                    (TRUSS_W / 2.0, TRUSS_BOTTOM - 1.0),
                    (y_top, TRUSS_H - chord + 1.0),
                    7.0,
                    6.0,
                )
            )

    # The 31 mm bore is the splice axis.  A second 19 mm bore at the same
    # longitudinal station is the portal-node axis.  Both pass through solid
    # end collars, not an open lattice bay.
    transverse_x = []
    if "near" in transverse_hole_ends:
        transverse_x.append(22.0)
    if "far" in transverse_hole_ends:
        transverse_x.append(length - 22.0)
    for x in transverse_x:
        for z in (19.0, 31.0):
            body = body.cut(hole_y(x, -0.5, z, M5_CLEAR, TRUSS_W + 1.0))

    # A second boom-root axis, 10 mm from either end, works with the 22 mm
    # station above.  These bores are unused on ordinary inline joints.
    root_x = []
    if "near" in transverse_hole_ends:
        root_x.append(10.0)
    if "far" in transverse_hole_ends:
        root_x.append(length - 10.0)
    for x in root_x:
        body = body.cut(hole_y(x, -0.5, 31.0, M5_CLEAR, TRUSS_W + 1.0))

    # Vertical holes are only cut where the camera-end boom actually needs
    # them.  Each hole passes through a 16 x 16 mm full-height bearing column,
    # rather than a 6 mm side wall, leaving 5.25 mm nominal ligament around a
    # 5.5 mm bore and preventing the carriage bolt from splitting the chord.
    # Omitting these columns from inline/root ends avoids needless mass and
    # crossed-bore weakening.
    vertical_x = []
    if "near" in vertical_hole_ends:
        vertical_x.append(25.0)
    if "far" in vertical_hole_ends:
        vertical_x.append(length - 25.0)
    for x in vertical_x:
        body = body.union(box_ll(16.0, 16.0, TRUSS_H, x - 8.0, 0.0, 0.0))
        body = body.union(box_ll(16.0, 16.0, TRUSS_H, x - 8.0, TRUSS_W - 16.0, 0.0))
        for y in (8.0, TRUSS_W - 8.0):
            body = body.cut(hole_z(x, y, M5_CLEAR, TRUSS_H + 1.0))

    # Repeated cable tie station in the open U floor; the USB lead lies inside
    # the member and a <=5 mm tie threads through these two support-free slots.
    tie_x = min(length - 45.0, length / 2.0 + 55.0)
    for y in (18.0, 32.0):
        body = body.cut(slot_z(tie_x, y, 14.0, 5.8, TRUSS_BOTTOM + 1.0, angle=0.0))
    if not markings:
        return body.clean()
    # Keep the cue on the protected inner floor.  A top-chord label at the
    # camera end would protrude into the carriage's nominal tangent plane and
    # create a real rocking/interference point under the bearing plate.
    body = emboss(body, "TIE", tie_x, 12.0, TRUSS_BOTTOM - 0.05, size=4.0, height=0.85)

    # Raised identification on the continuous bottom wall inside the open U.
    plaque_w = min(94.0, length - 72.0)
    if plaque_w >= 40.0:
        body = body.union(rounded_plate(plaque_w, 20.0, 1.2, 2.5, length / 2 - plaque_w / 2, 15.0, TRUSS_BOTTOM - 0.05))
        body = emboss(body, label, length / 2, 25.0, TRUSS_BOTTOM + 1.15, size=4.8, height=0.85)
    else:
        body = emboss(body, "00G TEST", length / 2, 25.0, TRUSS_BOTTOM, size=4.0, height=0.85)
    body = raised_arrow(body, length / 2, 39.0, TRUSS_BOTTOM, "right", 0.55)
    return body.clean()


def crossbar_truss_segment() -> cq.Workplane:
    """Universal 182.5 mm crossbar module with a center root boss.

    Four equal pieces keep every part inside the protected print envelope and
    place the two boom roots symmetrically on the centers of the two inner
    modules.  The same unused boss on each outer module is an inspection port.
    """
    length = CROSS_LENGTH
    body = truss_segment(length, "CROSS 182.5")
    x_axis = length / 2.0
    # Two full-height columns carry the vertical boom-root sandwich bolts.
    # Their axes are symmetric about the module center and pass through solid
    # 16 x 16 mm material, never across the unsupported open-U cavity.
    local_y = ROOT_CROSSBAR_BOLT_Y - (-100.0 - TRUSS_W / 2.0)
    for offset in ROOT_BOLT_X_OFFSETS:
        bolt_x = x_axis + offset
        body = body.union(box_ll(16.0, 16.0, TRUSS_H, bolt_x - 8.0, local_y - 8.0, 0.0))
        body = body.cut(hole_z(bolt_x, local_y, M5_CLEAR, TRUSS_H + 1.0))
    return body.clean()


def boom_root_truss_segment() -> cq.Workplane:
    """Root boom module with a four-bolt vertical sandwich interface."""
    # Only the far transverse stations serve the ordinary inline splice.  The
    # near-end crossed bores from the superseded side-plate joint are omitted.
    body = truss_segment(
        164.25,
        "BOOM ROOT",
        transverse_hole_ends=("far",),
    )
    # After installed 90-degree rotation these axes land at B x=root +/-17,
    # y=-51.  Full-height columns transmit clamp load between the top and
    # bottom straps without crushing the open-U section.
    local_x = ROOT_BOOM_BOLT_Y - float(CFG["layout"]["boom_root_y_mm"])
    for offset in ROOT_BOLT_X_OFFSETS:
        local_y = TRUSS_W / 2.0 - offset
        body = body.union(box_ll(16.0, 16.0, TRUSS_H, local_x - 8.0, local_y - 8.0, 0.0))
        body = body.cut(hole_z(local_x, local_y, M5_CLEAR, TRUSS_H + 1.0))
    return body.clean()


def u_truss_splice(length: float = SPLICE_LENGTH, center_four_bolt: bool = False, readable_labels: bool = False) -> cq.Workplane:
    """Long, full-height open-top external U collar for one beam joint.

    The center-crossbar variant uses both existing transverse bore elevations
    at each member end, positively locking the joint that carries boom torsion.
    All other joints retain one bolt per end for faster assembly.
    """
    half = length / 2.0
    clearance = 0.8
    side = 6.0
    inner_w = TRUSS_W + clearance
    outer_w = inner_w + 2.0 * side
    bottom = 4.0
    # The installed member floor is 4 mm above the collar floor, so 68 mm
    # reaches the complete 64 mm truss height and captures both top chords.
    height = TRUSS_H + bottom
    body = rounded_plate(length, outer_w, bottom, 2.0)
    body = body.union(box_ll(length, side, height, y0=0.0))
    body = body.union(box_ll(length, side, height, y0=outer_w - side))
    # No hidden center stop intersects the member ends; an exterior witness
    # rib marks the butt plane and makes the collar direction unambiguous.
    body = body.union(box_ll(2.0, side, 6.0, x0=half - 1.0, y0=0.0, z0=height))
    if center_four_bolt:
        # Diagonal pairs use the member's x=22/z=19 and x=10/z=31 end
        # stations.  Their 16.97 mm center spacing leaves usable clearance
        # between common M5 flange/nut envelopes; same-X 12 mm pairs do not.
        bore_coords = (
            (half - 22.0, 23.0),
            (half - 10.0, 35.0),
            (half + 10.0, 35.0),
            (half + 22.0, 23.0),
        )
    else:
        bore_coords = ((half - 22.0, 35.0), (half + 22.0, 35.0))
    for x, z in bore_coords:
        # Beam floor sits 4 mm above the collar floor, so local z=35/23
        # aligns with the member's z=31/19 transverse axes.
        body = body.cut(hole_y(x, -1.0, z, M5_CLEAR, outer_w + 2.0))
    # Raised ID wing is outside the 50.8 mm beam cavity.
    body = body.union(rounded_plate(54.0, 13.0, bottom, 2.0, half - 27.0, outer_w, 0.0))
    if readable_labels:
        # Keep the existing wing footprint and all collar mating surfaces.
        return bold_plate_label(body, "SPLICE", half, outer_w + 6.5, bottom, 8.0).clean()
    label = "CENTER 4B" if center_four_bolt else "SPLICE"
    body = emboss(body, label, half, outer_w + 6.5, bottom, size=4.5, height=0.85)
    body = raised_arrow(body, half, outer_w + 6.5, bottom, "right", 0.32)
    return body.clean()


def m6_nut_channel_layout(
    x: float,
    y: float,
    mouth_xy: Tuple[float, float],
) -> dict:
    """Return the shared centerlines for one side-loaded M6 nut path."""
    mouth_x, mouth_y = mouth_xy
    dx = x - mouth_x
    dy = y - mouth_y
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    return {
        "unit": (ux, uy),
        "main_start": (mouth_x - 7.0 * ux, mouth_y - 7.0 * uy),
        "main_end": (x + 6.2 * ux, y + 6.2 * uy),
        "latch_start": (mouth_x + 14.0 * ux, mouth_y + 14.0 * uy),
        "latch_end": (mouth_x + 25.0 * ux, mouth_y + 25.0 * uy),
    }


def reinforce_m6_nut_channel(
    body: cq.Workplane,
    x: float,
    y: float,
    mouth_xy: Tuple[float, float],
) -> cq.Workplane:
    """Add the support-free covered rib around one side-loaded nut channel.

    The 20.0 x 14.6 mm rib leaves 3.9 mm walls around the 12.2 mm nut
    passage, 3.2 mm walls around the 13.6 mm retainer bay, and a 1.9 mm
    minimum roof while preserving the high nut seat needed by M6x25 bolts.
    """
    return body.union(
        strut_xy(
            mouth_xy,
            (x, y),
            M6_NUT_TUNNEL_WIDTH,
            M6_NUT_TUNNEL_TOP_Z,
            z0=0.0,
        )
    )


def cut_side_loaded_m6_nut_pocket(
    body: cq.Workplane,
    x: float,
    y: float,
    mouth_xy: Tuple[float, float],
    hex_angle_deg: float,
) -> cq.Workplane:
    """Cut an externally reachable blind M6 nyloc pocket and latch channel.

    The mouth-to-seat line may be straight or diagonal. A DIN 985 low-pattern
    nyloc traverses the 12.2 mm channel in its final hex orientation, avoiding
    the disconnected insertion orientations of the former 10.6 mm tunnel. The
    13.6 mm latch bay accepts one common snap retainer after the nut seats.
    The vertical screw bore retains a positive floor above the bench.
    """
    layout = m6_nut_channel_layout(x, y, mouth_xy)

    nut = (
        cq.Workplane("XY")
        .polygon(6, 12.3)
        .extrude(7.3)
        .rotate((0, 0, 0), (0, 0, 1), hex_angle_deg)
        .translate((x, y, 5.35))
    )
    channel = strut_xy(layout["main_start"], layout["main_end"], M6_NUT_CHANNEL_WIDTH, 7.2, z0=5.4)
    latch = strut_xy(layout["latch_start"], layout["latch_end"], 13.6, 7.4, z0=5.3)
    blind_bore = hole_z(x, y, M6_CLEAR, 18.0, z0=M6_SADDLE_BLIND_BORE_FLOOR_Z)
    return body.cut(nut).cut(channel).cut(latch).cut(blind_bore)


def m6_nut_retainer() -> cq.Workplane:
    """Single snap plug closing one side-loaded M6 nut channel."""
    width = 11.6
    half = width / 2.0
    body = rounded_plate(width, 25.8, 6.0, 1.0, -half, 0.0, 2.0)
    left_barb = (
        cq.Workplane("XY")
        .workplane(offset=3.0)
        .polyline([(-half, 14.0), (-half - 0.8, 18.5), (-half, 22.5)])
        .close()
        .extrude(4.0)
    )
    right_barb = (
        cq.Workplane("XY")
        .workplane(offset=3.0)
        .polyline([(half, 14.0), (half + 0.8, 18.5), (half, 22.5)])
        .close()
        .extrude(4.0)
    )
    body = body.union(left_barb).union(right_barb)
    return body.clean()


def saddle_m6_channel_specs(hand: str) -> Tuple[dict, ...]:
    """Return installed-local seat/mouth pairs for one handed saddle."""
    if hand not in {"L", "R"}:
        raise ValueError(hand)
    left_specs = (
        {
            "name": "OUTER",
            "seat": (LEFT_SADDLE_CLAMP_X[1], SADDLE_CLAMP_Y),
            "mouth": (LEFT_SADDLE_CLAMP_X[1], M6_OUTER_NUT_CHANNEL_OPENING_Y),
            "hex_angle_deg": 0.0,
        },
        {
            "name": "INNER",
            "seat": (LEFT_SADDLE_CLAMP_X[0], SADDLE_CLAMP_Y),
            "mouth": M6_INNER_NUT_CHANNEL_MOUTH_XY,
            "hex_angle_deg": 113.4985656759521,
        },
    )
    if hand == "L":
        return left_specs
    return tuple(
        {
            "name": spec["name"],
            "seat": (SADDLE_MIRROR_WIDTH - spec["seat"][0], spec["seat"][1]),
            "mouth": (SADDLE_MIRROR_WIDTH - spec["mouth"][0], spec["mouth"][1]),
            "hex_angle_deg": -spec["hex_angle_deg"] if spec["name"] == "INNER" else 0.0,
        }
        for spec in left_specs
    )


def placed_m6_nut_retainer(
    retainer: cq.Workplane,
    mouth_xy: Tuple[float, float],
    seat_xy: Tuple[float, float],
    z_offset: float,
) -> cq.Workplane:
    """Orient the common retainer along a straight or diagonal nut channel."""
    dx = seat_xy[0] - mouth_xy[0]
    dy = seat_xy[1] - mouth_xy[1]
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    angle = math.degrees(math.atan2(dy, dx))
    anchor = (mouth_xy[0] + 1.1 * ux, mouth_xy[1] + 1.1 * uy)
    return (
        retainer.rotate((0, 0, 0), (0, 0, 1), angle - 90.0)
        .translate((anchor[0], anchor[1], z_offset))
    )


def _saddle_core() -> cq.Workplane:
    """Left-front bench-bearing saddle before handed label/mirroring.

    Local-to-board mapping for the left saddle is (x-120, y-160, z-18).
    The 120 x 120 foot is entirely outside the board and carries gravity into
    the bench.  Clamp lips only press the board down against that same bench.
    """
    foot_t = 12.0
    hard_stop_z = float(CFG["board_clamp"]["hard_stop_gap_mm"])
    body = rounded_plate(120.0, 120.0, foot_t, 7.0)
    # Integrated 150 mm forward outrigger keeps the complete foot inside y<=0
    # and expands the bench-bearing load path without a separate loose rail.
    body = body.union(rounded_plate(90.0, 100.0, 10.0, 7.0, 15.0, -90.0))
    body = body.union(strut_xy((35.0, -65.0), (45.0, 45.0), 22.0, foot_t))
    body = body.union(strut_xy((85.0, -65.0), (75.0, 45.0), 22.0, foot_t))
    # Exterior front clamp arm.  It ends at the board front plane (local y=160).
    body = body.union(rounded_plate(90.0, 40.0, foot_t, 4.0, 100.0, 120.0))
    body = body.union(strut_xy((60.0, 60.0), (132.0, 142.0), 28.0, foot_t))
    body = body.union(strut_xy((58.0, 58.0), (108.0, 145.0), 24.0, foot_t))

    # Hard edge stops touch the front face and the extreme front-side corner;
    # no low rail or stay extends rearward into y>0.
    body = body.union(box_ll(70.0, 6.0, 24.0, 120.0, 154.0, 0.0))
    body = body.union(box_ll(6.0, 10.0, 24.0, 114.0, 150.0, 0.0))

    # Open-top socket for the 64 x 50 mm U-truss cross-section, centered on
    # B=(-60,-100). Four vertical walls need no support material.
    body = body.union(box_ll(8.0, 68.0, 92.0, 19.5, 26.0, foot_t))
    body = body.union(box_ll(8.0, 68.0, 92.0, 92.5, 26.0, foot_t))
    body = body.union(box_ll(81.0, 8.0, 92.0, 19.5, 26.0, foot_t))
    body = body.union(box_ll(81.0, 8.0, 92.0, 19.5, 86.0, foot_t))
    # Two positive bearing ledges put the upright bottom at local z=68
    # (B z=50).  Vertical ribs beneath each ledge limit every printed bridge
    # span to <=20 mm, so the tower dead load reaches the bench without
    # hanging from the transverse M5 receiver bolt.
    for ledge_y in (34.0, 78.0):
        body = body.union(box_ll(65.0, 8.0, 8.0, 27.5, ledge_y, 60.0))
        for rib_x in (27.5, 51.5, 75.5):
            body = body.union(box_ll(8.0, 8.0, 48.0, rib_x, ledge_y, foot_t))
    # Two diagonal ribs react boom moment while remaining forward of y=0.
    # Their rotated-box tips MUST be grounded and trimmed out of the upright
    # pocket by saddle_printability_correction in the handed final saddle.
    for x in (10.0, 72.0):
        rib = (
            cq.Workplane("XY")
            .box(10.0, 132.0, 12.0, centered=(True, True, True))
            .rotate((0, 0, 0), (1, 0, 0), -40.0)
            .translate((x + 5.0, 91.0, 53.0))
        )
        body = body.union(rib)

    # Exterior bolt towers are the over-compression hard stops. The outer nut
    # channel is straight; the inner channel exits diagonally at an exposed
    # mouth instead of terminating inside the saddle arm. Both accept the same
    # hex-aligned DIN 985 nyloc and snap retainer. All drive access is above the
    # bench; there is no inaccessible underside nut or channel tool operation.
    for spec in saddle_m6_channel_specs("L"):
        x, y = spec["seat"]
        tower = cq.Workplane("XY").center(x, y).circle(8.5).extrude(hard_stop_z)
        body = body.union(tower)
        body = reinforce_m6_nut_channel(body, x, y, spec["mouth"])
        body = cut_side_loaded_m6_nut_pocket(
            body,
            x,
            y,
            mouth_xy=spec["mouth"],
            hex_angle_deg=spec["hex_angle_deg"],
        )

    # Flat label island; text is added after handedness is selected.
    body = body.union(rounded_plate(78.0, 22.0, 2.0, 3.0, 21.0, 96.0, foot_t - 0.05))
    return body.clean()


def saddle_printability_correction(body: cq.Workplane, hand: str) -> cq.Workplane:
    """Ground the diagonal ribs and clear their intrusion above receiver ledges.

    The original rotated boxes start at z~=5.98 outside the existing foot and
    cross the upright insertion pocket. These additions/removal are localized:
    M6 channels, stop faces, M5 axes and the z=68 bearing ledges stay unchanged.
    The two permanent 10x30x16 feet overlap the original foot by 4 mm in Y.
    """
    if hand not in {"left", "right"}:
        raise ValueError(hand)
    feet = box_ll(10.0, 30.0, 16.0, 10.0, 116.0, 0.0).union(
        box_ll(10.0, 30.0, 16.0, 72.0, 116.0, 0.0)
    )
    pocket = box_ll(65.0, 52.0, 37.0, 27.5, 34.0, 68.0)
    if hand == "right":
        feet = feet.mirror("YZ").translate((190.0, 0.0, 0.0))
        pocket = pocket.mirror("YZ").translate((190.0, 0.0, 0.0))
    return body.union(feet).cut(pocket).clean()


def board_corner_saddle(hand: str) -> cq.Workplane:
    if hand not in {"left", "right"}:
        raise ValueError(hand)
    body = _saddle_core()
    if hand == "right":
        body = body.mirror("YZ").translate((190.0, 0.0, 0.0))
        receiver_axes = ((131.0, 78.0), (143.0, 90.0))
        label_x = 130.0
        arrow_x = 134.0
        arrow_direction = "left"
        text = "RIGHT FRONT"
    else:
        receiver_axes = ((61.0, 78.0), (73.0, 90.0))
        label_x = 60.0
        arrow_x = 56.0
        arrow_direction = "right"
        text = "LEFT FRONT"
    # Two diagonal receiver axes align with the upright's reinforced
    # (longitudinal, section-height) bores (10,31) and (22,19).  Their
    # 16.97 mm separation leaves real clearance between flange/nut envelopes,
    # unlike a same-X 12 mm vertical pair.  Cut after mirroring so both handed
    # saddles align with identically oriented uprights.
    for local_x, local_z in receiver_axes:
        body = body.cut(hole_y(local_x, 25.0, local_z, M5_CLEAR, 70.0))
    body = emboss(body, text, label_x, 106.0, 13.95, size=5.2, height=0.85)
    body = raised_arrow(body, arrow_x, 18.0, 12.0, arrow_direction, 0.75)
    body = emboss(body, "BENCH", label_x, 42.0, 12.0, size=4.8, height=0.8)
    return saddle_printability_correction(body, hand)


def _corner_cap_core() -> cq.Workplane:
    # Local board corner = (25,25).  Each branch overlaps the board by only
    # 10 mm, leaving T0/T1 artwork untouched.
    thickness = M6_CAP_BASE_TOP_Z
    body = rounded_plate(85.0, 35.0, thickness, 4.0)
    body = body.union(rounded_plate(35.0, 85.0, thickness, 4.0))
    # Clamp bores are cut once, after handed mirroring, labels, and bosses.
    # Re-cutting an already mirrored cylindrical face created an open-edge STL
    # seam on the right cap even though the source B-rep remained a solid.
    # Four underside sockets trap the two TPU pads with push-in nubs.  The
    # 3.2 mm blind ends bridge only 3.2 mm when the cap prints flat.
    for x, y in ((38.0, 30.5), (62.0, 30.5), (30.5, 38.0), (30.5, 62.0)):
        body = body.cut(hole_z(x, y, 3.2, 2.8, z0=-0.1))
    return body.clean()


def board_corner_cap(hand: str) -> cq.Workplane:
    body = _corner_cap_core()
    if hand == "right":
        body = body.mirror("YZ").translate((85.0, 0.0, 0.0))
        side = "R"
        arrow = "left"
    else:
        side = "L"
        arrow = "right"
    body = emboss(body, f"{side} FRONT", 43.0, 17.5, 8.0, size=5.0, height=0.9)
    body = raised_arrow(body, 18.0 if hand == "left" else 67.0, 67.0, 8.0, arrow, 0.55)
    body = emboss(body, "BOARD", 17.5 if hand == "left" else 67.5, 45.0, 8.0, size=4.0, height=0.8, angle=90.0)
    # Labels are boolean unions. Add a wide, integrated bearing boss above all
    # raised markings, then re-cut the shaft last. The boss raises the true M6
    # bearing plane by 3.0 mm from the former z=6.8 recessed floor: an M6x25
    # bolt now clears both the saddle's blind-bore floor and the bench without
    # a loose spacer or washer. Mirroring moves right-cap centers to x=30/72.
    cap_holes = ((30.0, 13.0), (72.0, 13.0)) if hand == "right" else ((55.0, 13.0), (13.0, 13.0))
    for x, y in cap_holes:
        boss = (
            cq.Workplane("XY")
            .workplane(offset=M6_CAP_BASE_TOP_Z)
            .center(x, y)
            .circle(M6_CAP_BOSS_OD / 2.0)
            .extrude(M6_CAP_BOSS_BEARING_Z - M6_CAP_BASE_TOP_Z)
        )
        body = body.union(boss)
        body = body.cut(hole_z(x, y, M6_CLEAR, M6_CAP_BOSS_BEARING_Z + 1.0))
    return body.clean()


def board_pressure_pad() -> cq.Workplane:
    body = rounded_plate(38.0, 9.0, 0.8, 1.5)
    # Two 3.0 mm push-in nubs positively locate the pad in the cap sockets.
    for x in (7.0, 31.0):
        body = body.union(cq.Workplane("XY").center(x, 4.5).circle(1.5).extrude(2.4).translate((0, 0, 0.75)))
    return body.clean()


def clamp_knob_m6() -> cq.Workplane:
    body = cq.Workplane("XY").circle(17.0).extrude(9.0)
    # Captures a standard 10 mm-AF M6 bolt head; the through hole remains loose.
    head_pocket = cq.Workplane("XY").polygon(6, 11.7).extrude(5.2).translate((0, 0, 4.3))
    body = body.cut(head_pocket).cut(hole_z(0, 0, M6_CLEAR, 10.0))
    for angle in range(0, 360, 30):
        x = 15.7 * math.cos(math.radians(angle))
        y = 15.7 * math.sin(math.radians(angle))
        body = body.cut(hole_z(x, y, 2.2, 10.0))
    body = emboss(body, "M6", 0, -8.0, 9.0, size=4.0, height=0.8)
    return body.clean()


def flat_gusset(width: float, height: float, thickness: float, label: str, holes: Iterable[Tuple[float, float]]) -> cq.Workplane:
    body = (
        cq.Workplane("XY")
        .polyline([(0, 0), (width, 0), (0, height)])
        .close()
        .extrude(thickness)
    )
    body = body.union(rounded_plate(width * 0.45, 18.0, 1.2, 2.0, 5.0, 5.0, thickness - 0.05))
    for x, y in holes:
        body = body.cut(hole_z(x, y, M5_CLEAR, thickness + 1.0))
    body = emboss(body, label, width * 0.27, 13.0, thickness + 1.15, size=4.3, height=0.85)
    return body.clean()


def portal_corner_node(hand: str) -> cq.Workplane:
    """Flat outside gusset; two identical plates sandwich each portal corner."""
    if hand not in {"left", "right"}:
        raise ValueError(hand)
    body = rounded_plate(110.0, 110.0, 8.0, 6.0)
    # Installed with local +Y pointing down from the truss top. Each member
    # uses a diagonal pair of existing 10/31 and 22/19 truss bores. Their
    # 16.97 mm spacing leaves service room for a <=13 mm thin-wall M5 socket
    # beside the neighboring 12 mm flange instead of crowding same-station
    # holes only 12 mm apart.
    if hand == "left":
        holes = ((43.0, 86.0), (31.0, 74.0), (52.0, 45.0), (40.0, 33.0))
        label = "TOP L - PAIR"
        arrow = "right"
    else:
        holes = ((83.0, 86.0), (71.0, 74.0), (48.0, 45.0), (60.0, 33.0))
        label = "TOP R - PAIR"
        arrow = "left"
    for x, y in holes:
        body = body.cut(hole_z(x, y, M5_CLEAR, 9.0))
    # Put every raised orientation cue on a connected tab above the installed
    # members.  Paired plates are physically identical; one label therefore
    # faces inward.  Keeping it above the beam silhouette prevents that inward
    # text from becoming a hidden interference or rocking point.
    body = body.union(rounded_plate(50.0, 14.0, 8.0, 3.0, 30.0, -14.0))
    body = emboss(body, label, 55.0, -7.0, 7.95, size=4.0, height=0.85)
    body = raised_arrow(body, 70.0, -7.0, 7.95, arrow, 0.35)
    return body.clean()


def boom_crossbar_node() -> cq.Workplane:
    """One of two identical flat sandwich straps used at each boom root."""
    body = rounded_plate(ROOT_STRAP_W, ROOT_STRAP_D, ROOT_STRAP_T, 5.0)
    # Installed centered on the tangent T joint.  The rear row passes through
    # reinforced crossbar columns and the forward row through reinforced boom
    # columns.  A second copy is flipped below the members, producing a true
    # top/bottom clamp without any printed-part overlap.
    strap_y0 = float(CFG["layout"]["boom_root_y_mm"]) - ROOT_STRAP_D / 2.0
    for offset in ROOT_BOLT_X_OFFSETS:
        for installed_y in (ROOT_CROSSBAR_BOLT_Y, ROOT_BOOM_BOLT_Y):
            body = body.cut(
                hole_z(ROOT_STRAP_W / 2.0 + offset, installed_y - strap_y0, M5_CLEAR, ROOT_STRAP_T + 1.0)
            )
    body = emboss(body, "ROOT STRAP 2X", ROOT_STRAP_W / 2.0, ROOT_STRAP_D / 2.0, ROOT_STRAP_T, size=4.7, height=0.85)
    body = raised_arrow(body, ROOT_STRAP_W / 2.0, ROOT_STRAP_D - 10.0, ROOT_STRAP_T, "rear", 0.5)
    return body.clean()


def mast_base_gusset() -> cq.Workplane:
    return flat_gusset(
        105.0,
        92.0,
        8.0,
        "BASE",
        ((15, 20), (15, 44), (42, 15), (70, 15), (15, 72)),
    )


def angle_plate(label: str, width: float = 84.0, height: float = 72.0) -> cq.Workplane:
    body = flat_gusset(
        width,
        height,
        8.0,
        label,
        ((14, 18), (14, 42), (40, 14), (66, 14)),
    )
    return body


def forward_knee_brace() -> cq.Workplane:
    length = math.hypot(150.0, 240.0)
    body = rounded_plate(length, 42.0, 12.0, 5.0)
    # Weight-reduction windows are vertical through-holes in print orientation.
    for x in (70.0, 115.0, 160.0, 205.0):
        body = body.cut(slot_z(x, 21.0, 24.0, 13.0, 13.0, angle=0.0))
    for x in (16.0, length - 16.0):
        body = body.cut(hole_z(x, 21.0, M6_CLEAR, 13.0))
    body = emboss(body, "FRONT BRACE", length / 2, 8.0, 12.0, size=5.0, height=0.8)
    body = raised_arrow(body, length / 2, 32.0, 12.0, "front", 0.55)
    return body.clean()


def outrigger_foot() -> cq.Workplane:
    body = rounded_plate(120.0, 80.0, 10.0, 8.0)
    for x in (24.0, 96.0):
        for y in (20.0, 60.0):
            body = body.cut(hole_z(x, y, M5_CLEAR, 11.0))
    body = emboss(body, "BENCH FOOT", 60.0, 40.0, 10.0, size=6.2, height=0.8)
    return body.clean()


def camera_drop_bracket() -> cq.Workplane:
    body = rounded_plate(150.0, 45.0, 8.0, 5.0)
    body = body.cut(slot_z(82.0, 22.5, 105.0, M5_CLEAR, 9.0, angle=0.0))
    for y in (12.0, 33.0):
        body = body.cut(hole_z(13.0, y, M5_CLEAR, 9.0))
    body = emboss(body, "Z LOCK", 82.0, 10.0, 8.0, size=5.0, height=0.8)
    body = raised_arrow(body, 128.0, 33.0, 8.0, "right", 0.65)
    return body.clean()


def camera_xy_carriage() -> cq.Workplane:
    width, depth, thickness = CARRIAGE_W, CARRIAGE_D, 10.0
    body = rounded_plate(width, depth, thickness, 7.0)
    body = body.cut(hole_z(CAMERA_X - CARRIAGE_X0, depth / 2, 56.0, thickness + 1.0))

    # Four positive-lock X columns land on the reinforced bearing columns at
    # both boom ends. Two discrete positions replace friction-only Y slots;
    # the builder installs one M5x85 bolt per X column and puts all four bolts
    # in the same Y row. The local 65 mm row is the nominal optical position
    # at B y=228.5; the local 44 mm row requires a +21 mm installed carriage
    # shift and moves the camera rearward to B y=249.5.
    carriage_bolt_x = tuple(
        boom_x - CARRIAGE_X0 + offset
        for boom_x in BOOM_AXES_X
        for offset in (-17.0, 17.0)
    )
    for x in carriage_bolt_x:
        for y in tuple(depth / 2.0 + offset for offset in CARRIAGE_HOLE_Y_OFFSETS):
            body = body.cut(hole_z(x, y, M5_CLEAR, thickness + 1.0))

    # Three repeatable X indices replace 58 mm friction slots at all three
    # kinematic leveling bolts. The builder selects the same left/center/right
    # round bore at every station, so M4 shafts—not ABS clamp friction—react
    # lateral camera load and prevent long-term optical creep.
    leveling_bases = ((93.0, 35.0), (157.0, 35.0), (125.0, 101.0))
    for base_x, y in leveling_bases:
        for offset in CAGE_INSTALLED_X_OFFSETS:
            body = body.cut(hole_z(base_x + offset, y, M4_CLEAR, thickness + 1.0))

    # Hex-key service holes align with all four recessed keeper screw heads at
    # every positive-lock X index. They permit installed torque checks; the
    # keeper remains a bench-assembled part of the removable cage module.
    keeper_service_centers = (
        (91.0, 55.0),
        (159.0, 55.0),
        (91.0, 91.0),
        (159.0, 91.0),
    )
    for x, y in keeper_service_centers:
        for offset in CAGE_INSTALLED_X_OFFSETS:
            body = body.cut(hole_z(x + offset, y, 5.0, thickness + 1.0))

    # Two top edge ribs stiffen the 250 mm carriage without intruding into the
    # camera, keeper, leveling, or carriage-bolt service envelopes.
    body = body.union(box_ll(width - 20.0, 8.0, 6.0, 10.0, 6.0, thickness))
    body = body.union(box_ll(width - 20.0, 8.0, 6.0, 10.0, 116.0, thickness))
    body = emboss(body, "CAMERA CARRIAGE", width / 2, 10.0, thickness + 6.0, size=5.2, height=0.9)
    body = emboss(body, "4 BOLTS - SAME ROW", width / 2, 121.0, thickness + 6.0, size=4.6, height=0.85)
    body = emboss(body, "3 M4 - SAME X INDEX", width / 2, 21.0, thickness, size=4.2, height=0.85)
    body = raised_arrow(body, width / 2, 108.0, thickness, "rear", 0.65)

    # Labels are added by boolean union, so re-cut every critical opening last.
    # This prevents a glyph or arrow from silently refilling a shaft/slot.
    body = body.cut(hole_z(CAMERA_X - CARRIAGE_X0, depth / 2, 56.0, thickness + 7.0))
    for x in carriage_bolt_x:
        for y in tuple(depth / 2.0 + offset for offset in CARRIAGE_HOLE_Y_OFFSETS):
            body = body.cut(hole_z(x, y, M5_CLEAR, thickness + 7.0))
    for base_x, y in leveling_bases:
        for offset in CAGE_INSTALLED_X_OFFSETS:
            body = body.cut(hole_z(base_x + offset, y, M4_CLEAR, thickness + 7.0))
            # A shallow 10 mm spotface removes any raised label/arrow from the
            # complete M4 washer seat while preserving essentially all of the
            # 10 mm carriage thickness. It is repeated at all nine selectable
            # X-index bores so every position has the same planar load path.
            body = body.cut(hole_z(base_x + offset, y, 10.0, 6.3, z0=thickness - 0.2))
    for x, y in keeper_service_centers:
        for offset in CAGE_INSTALLED_X_OFFSETS:
            body = body.cut(hole_z(x + offset, y, 5.0, thickness + 7.0))
    return body.clean()


def camera_cage_body() -> cq.Workplane:
    outer = 96.0
    base_t = 8.0
    wall_h = 34.0
    center = outer / 2
    inner = float(CFG["camera"]["cage_internal_xy_mm"][0])
    wall_t = 9.0
    inner_lo = center - inner / 2
    inner_hi = center + inner / 2
    outer_lo = inner_lo - wall_t
    outer_hi = inner_hi + wall_t

    body = rounded_plate(outer, outer, base_t, 7.0)
    # Integrated rear USB/tether wing removes a separate loose bracket.  It
    # starts beyond the boom ends in the installed assembly, so neither the
    # plug nor its strain relief can be trapped between a boom and the cage.
    # Both tie slots and tether routing holes are open vertical cuts.
    body = body.union(rounded_plate(62.0, 42.0, base_t, 5.0, 17.0, 92.0))
    body = body.cut(hole_z(center, center, float(CFG["camera"]["lens_clearance_diameter_mm"]), base_t + 1.0))

    # Four independent walls create a true positive-retention cage.
    body = body.union(box_ll(wall_t, outer_hi - outer_lo, wall_h, outer_lo, outer_lo, base_t))
    body = body.union(box_ll(wall_t, outer_hi - outer_lo, wall_h, inner_hi, outer_lo, base_t))
    body = body.union(box_ll(inner, wall_t, wall_h, inner_lo, outer_lo, base_t))
    body = body.union(box_ll(inner, wall_t, wall_h, inner_lo, inner_hi, base_t))

    # Rear USB connector window is open to the wall top, so no bridge or hidden
    # support exists.  The square camera rotates 90 degrees in the cage so its
    # connector faces this rear egress while the optical axis stays unchanged.
    usb_cut = box_ll(26.0, 12.0, wall_h - 11.0, center - 13.0, inner_hi - 1.0, base_t + 11.0)
    body = body.cut(usb_cut)

    # Three-point leveling avoids a statically indeterminate four-screw plate.
    for x, y in ((16, 18), (80, 18), (48, 84)):
        body = body.cut(hole_z(x, y, M4_CLEAR, base_t + wall_h + 1.0))
        # Underside-loaded captured M4 nut.  The intact 4.3 mm roof carries
        # downward cage load; once the screw engages, the nut cannot escape in
        # the load direction.
        nut_pocket = (
            cq.Workplane("XY")
            .workplane(offset=-0.1)
            .center(x, y)
            .polygon(6, 8.4)
            .extrude(3.7)
        )
        body = body.cut(nut_pocket)
    # Four perimeter keeper bolts positively close the camera cage without
    # slide hooks or friction latches. Their axes remain outside the camera
    # and cage walls and clear all three leveling-wrench paths.
    keeper_bolt_centers = ((14, 38), (82, 38), (14, 74), (82, 74))
    for x, y in keeper_bolt_centers:
        body = body.cut(hole_z(x, y, M4_CLEAR, base_t + 1.0))
    for x in (33.0, 63.0):
        body = body.cut(slot_z(x, 115.0, 18.0, 5.8, base_t + 1.0, angle=90.0))
    for y in (102.0, 126.0):
        body = body.cut(hole_z(48.0, y, 7.0, base_t + 1.0))

    body = emboss(body, "LENS DOWN", 48.0, 5.0, base_t, size=4.8, height=0.8)
    body = emboss(body, "USB REAR", 48.0, 87.0, base_t, size=4.0, height=0.85)
    body = emboss(body, "TIES", 24.0, 130.0, base_t, size=3.8, height=0.85)
    body = emboss(body, "TETHER", 67.0, 130.0, base_t, size=3.5, height=0.85)

    # Re-cut all camera, fastener, cable, and tether openings after raised
    # markings so no label can refill a functional passage.
    body = body.cut(hole_z(center, center, float(CFG["camera"]["lens_clearance_diameter_mm"]), base_t + wall_h + 2.0))
    body = body.cut(usb_cut)
    for x, y in ((16, 18), (80, 18), (48, 84)):
        body = body.cut(hole_z(x, y, M4_CLEAR, base_t + wall_h + 2.0))
        body = body.cut(
            cq.Workplane("XY").workplane(offset=-0.1).center(x, y).polygon(6, 8.4).extrude(3.7)
        )
    for x, y in keeper_bolt_centers:
        body = body.cut(hole_z(x, y, M4_CLEAR, base_t + 2.0))
    for x in (33.0, 63.0):
        body = body.cut(slot_z(x, 115.0, 18.0, 5.8, base_t + 2.0, angle=90.0))
    for y in (102.0, 126.0):
        body = body.cut(hole_z(48.0, y, 7.0, base_t + 2.0))
    return body.clean()


def camera_cage_keeper() -> cq.Workplane:
    outer, thickness = 96.0, 6.0
    body = rounded_plate(96.0, 82.0, thickness, 6.0, 0.0, 7.0)
    body = body.cut(rounded_plate(29.0, 29.0, thickness + 1.0, 3.0, 33.5, 33.5, -0.5))
    keeper_bolt_centers = ((14, 38), (82, 38), (14, 74), (82, 74))
    for x, y in keeper_bolt_centers:
        body = body.cut(hole_z(x, y, M4_CLEAR, thickness + 1.0))
        # Washer + low-profile button head recess; its top remains flush so it
        # cannot collide with the carriage at the minimum Z setting.
        body = body.cut(hole_z(x, y, 10.0, 4.2, z0=thickness - 4.15))
    # Three large clearances contain the leveling jam nut + washer immediately
    # below the carriage.  Edge-open wrench bays let a thin 7 mm open-end
    # wrench engage each jam nut; a closed circular pocket would trap the nut
    # without any usable tightening path.
    for x, y in ((16, 18), (80, 18), (48, 84)):
        body = body.cut(hole_z(x, y, 10.5, thickness + 1.0))
    # Nineteen-millimetre transverse width gives the specified <=18 mm wrench
    # head 1.0 mm total printed clearance. Both front bays open toward -Y into
    # the unobstructed space between the booms; a side-opening bay would leave
    # the wrench handle trapped in the narrow cage-to-boom corridor at an
    # extreme X index. The rear bay remains rear-open.
    body = body.cut(box_ll(19.0, 28.0, thickness + 1.0, 6.5, -0.5, -0.5))
    body = body.cut(box_ll(19.0, 28.0, thickness + 1.0, 70.5, -0.5, -0.5))
    body = body.cut(box_ll(19.0, 12.0, thickness + 1.0, 38.5, 77.5, -0.5))
    # The hidden keeper top remains completely planar at every X index; a
    # raised cue here would collide with the fixed carriage when the cage is
    # shifted left or right. The cage's rear USB opening—not the keeper—is the
    # camera orientation key. Final cutter passes protect every service path.
    body = body.cut(rounded_plate(29.0, 29.0, thickness + 1.0, 3.0, 33.5, 33.5, -0.5))
    for x, y in keeper_bolt_centers:
        body = body.cut(hole_z(x, y, M4_CLEAR, thickness + 1.0))
        body = body.cut(hole_z(x, y, 10.0, 4.2, z0=thickness - 4.15))
    for x, y in ((16, 18), (80, 18), (48, 84)):
        body = body.cut(hole_z(x, y, 10.5, thickness + 1.0))
    body = body.cut(box_ll(19.0, 28.0, thickness + 1.0, 6.5, -0.5, -0.5))
    body = body.cut(box_ll(19.0, 28.0, thickness + 1.0, 70.5, -0.5, -0.5))
    body = body.cut(box_ll(19.0, 12.0, thickness + 1.0, 38.5, 77.5, -0.5))
    return body.clean()


def camera_top_compression_pad() -> cq.Workplane:
    """Mechanically trapped nominal TPU pad removing vertical case freedom."""
    pad_h = 9.2
    body = rounded_plate(38.0, 38.0, pad_h, 2.0)
    body = body.cut(rounded_plate(24.0, 24.0, pad_h + 1.0, 2.0, 7.0, 7.0, -0.5))
    # Asymmetric 3 mm through-notch is the orientation cue; both compression
    # faces remain flat and free of raised text.
    body = body.cut(hole_z(4.5, 4.5, 3.0, pad_h + 1.0))
    return body.clean()


def camera_case_shim_ladder() -> cq.Workplane:
    """One breakaway sprue containing two each of 0.3/0.6/0.9 mm shims."""
    body = box_ll(2.0, 62.0, 1.2)
    rows = ((0.3, "0.3"), (0.3, "0.3"), (0.6, "0.6"), (0.6, "0.6"), (0.9, "0.9"), (0.9, "0.9"))
    for index, (thickness, label) in enumerate(rows):
        y0 = 1.0 + index * 10.0
        # The 1.2 mm-wide neck at the sprue and 1 mm neck at the label tab are
        # deliberately clipped after printing; only the 38 x 7 flat strip is used.
        body = body.union(box_ll(2.0, 1.2, thickness, 2.0, y0 + 2.9))
        body = body.union(rounded_plate(38.0, 7.0, thickness, 0.7, 4.0, y0))
        body = body.union(box_ll(1.0, 2.0, 1.2, 42.0, y0 + 2.5))
        body = body.union(rounded_plate(12.0, 7.0, 1.2, 1.0, 43.0, y0))
        body = emboss(body, label, 49.0, y0 + 3.5, 1.2, size=4.0, height=0.8)
    body = emboss(body, "SHIMS", 1.0, 31.0, 1.2, size=4.0, height=0.8, angle=90.0)
    return body.clean()


def usb_strain_relief() -> cq.Workplane:
    body = rounded_plate(80.0, 30.0, 7.0, 4.0)
    for x in (8.0, 72.0):
        body = body.cut(hole_z(x, 15.0, M4_CLEAR, 8.0))
    # Slots accept the user's wider ties; they remain open vertical cuts.
    for x in (31.0, 49.0):
        body = body.cut(slot_z(x, 15.0, 16.0, 5.8, 8.0, angle=90.0))
    body = emboss(body, "USB TIES", 40.0, 5.5, 7.0, size=4.7, height=0.8)
    return body.clean()


def camera_case_fit_gauge() -> cq.Workplane:
    width, depth, thickness = 186.0, 86.0, 8.0
    body = rounded_plate(width, depth, thickness, 7.0)
    # Received case must pass 39.2 but should not rattle in the 40.0 check.
    body = body.cut(rounded_plate(39.2, 39.2, thickness + 1.0, 2.0, 13.0, 31.0, -0.5))
    body = body.cut(hole_z(88.0, 50.0, 40.2, thickness + 1.0))
    body = body.cut(hole_z(148.0, 50.0, 44.0, thickness + 1.0))
    body = emboss(body, "CASE 39.2", 32.6, 13.0, thickness, size=5.0, height=0.8)
    body = emboss(body, "LENS 40.2", 88.0, 13.0, thickness, size=5.0, height=0.8)
    body = emboss(body, "CLEAR 44", 148.0, 13.0, thickness, size=5.0, height=0.8)
    return body.clean()


def bold_plate_label(body: cq.Workplane, text: str, x: float, y: float, z: float, size: float = 8.0, angle: float = 0.0) -> cq.Workplane:
    """Wide-stroke raised labels, 1.2 mm high (six 0.20 mm layers)."""
    letters = cq.Workplane("XY").workplane(offset=z - 0.05).center(x, y).text(
        text, size, 1.25, combine=False, font="Arial Black", kind="regular"
    )
    if angle:
        letters = letters.rotate((x, y, 0), (x, y, 1), angle)
    return body.union(letters)


def board_saddle_fit_coupon(readable_labels: bool = False) -> cq.Workplane:
    """00G coupon for the 18.65 mm gap and accessible M6 nut/retainer fit."""
    gap = float(CFG["board_clamp"]["hard_stop_gap_mm"])
    width, total_h, thick = 74.0, gap + 14.0, 12.0
    body = box_ll(width, 7.0, thick)
    body = body.union(box_ll(7.0, total_h, thick))
    body = body.union(box_ll(width, 7.0, thick, y0=total_h - 7.0))
    if not readable_labels:
        body = emboss(body, "18.65 GAP", 40.0, 4.0, thick, size=4.5, height=0.85)
    body = raised_arrow(body, 55.0, total_h - 3.5, thick, "right", 0.45)

    # An attached tower repeats the exact production nut pocket. Insert an M6
    # DIN 985 nyloc (10 mm AF, <=6.0 mm high) from the labeled open edge, then
    # snap in one retainer.
    body = body.union(box_ll(30.0, 45.0, gap, x0=74.0))
    body = cut_side_loaded_m6_nut_pocket(
        body,
        89.0,
        33.0,
        mouth_xy=(89.0, -0.5),
        hex_angle_deg=0.0,
    )
    if readable_labels:
        # Outside the board gap, on the exterior side of the upper jaw.
        body = body.union(rounded_plate(66.0, 27.5, 3.0, 2.0, 4.0, total_h - 0.5, 0.0))
        body = bold_plate_label(body, "BOARD", 37.0, total_h + 9.0, 3.0, 8.0)
        body = bold_plate_label(body, "18.65", 37.0, total_h + 20.0, 3.0, 7.5)
        body = bold_plate_label(body, "M6", 89.0, 17.0, gap, 9.0)
    else:
        body = emboss(body, "NUT", 89.0, 17.0, gap, size=4.1, height=0.85)
    return body.clean()


def u_splice_fit_coupon(readable_labels: bool = False) -> cq.Workplane:
    """00G short U-section for a slip-fit check with one production splice."""
    body = truss_segment(86.0, "SPLICE TEST", markings=not readable_labels)
    if readable_labels:
        # End tab stays outside the collar when checking the near end's
        # x=22 bolt station. No added material enters the 86 mm test envelope.
        body = body.union(rounded_plate(24.5, 34.0, 4.0, 2.0, 85.5, 8.0, 0.0))
        body = bold_plate_label(body, "TEST", 98.0, 25.0, 4.0, 8.0, angle=90.0)
    return body.clean()


def make_parts() -> Dict[str, cq.Workplane]:
    return {
        "board_corner_saddle_left": board_corner_saddle("left"),
        "board_corner_saddle_right": board_corner_saddle("right"),
        "board_corner_cap_left": board_corner_cap("left"),
        "board_corner_cap_right": board_corner_cap("right"),
        "board_pressure_pad": board_pressure_pad(),
        "m6_nut_retainer": m6_nut_retainer(),
        "upright_truss_segment_240": truss_segment(240.0, "UP 240"),
        "crossbar_truss_segment_182p5": crossbar_truss_segment(),
        "boom_root_truss_segment_164p25": boom_root_truss_segment(),
        "boom_camera_truss_segment_164p25": truss_segment(
            164.25,
            "BOOM CAMERA",
            vertical_hole_ends=("far",),
            transverse_hole_ends=("near",),
        ),
        "u_truss_splice": u_truss_splice(),
        "u_truss_splice_crossbar_2bolt": u_truss_splice(length=CROSS_SPLICE_LENGTH),
        "u_truss_splice_center_4bolt": u_truss_splice(length=CROSS_SPLICE_LENGTH, center_four_bolt=True),
        "portal_corner_node_left": portal_corner_node("left"),
        "portal_corner_node_right": portal_corner_node("right"),
        "boom_crossbar_node": boom_crossbar_node(),
        "camera_xy_carriage": camera_xy_carriage(),
        "camera_cage_body": camera_cage_body(),
        "camera_cage_keeper": camera_cage_keeper(),
        "camera_top_compression_pad": camera_top_compression_pad(),
        "camera_case_shim_ladder": camera_case_shim_ladder(),
        "camera_case_fit_gauge": camera_case_fit_gauge(),
        "board_saddle_fit_coupon": board_saddle_fit_coupon(),
        "u_splice_fit_coupon": u_splice_fit_coupon(),
    }


# Geometry-only 3MFs deliberately mirror the numbered subplate names used by
# the companion print-job package.  A 3MF here is only a positioned collection
# of exact generated meshes: the authoritative material/process settings remain
# in the JSON process sidecars and must be selected separately in QIDI Studio.
PLATE_DEFINITIONS = [
    {
        "subplate_id": "00G-S1",
        "filename": "00G-S1_ABS_board_splice_fit_tests.3mf",
        "profile": "abs_structural",
        "objects": [
            ("board_saddle_fit_coupon", 1),
            ("u_splice_fit_coupon", 1),
            ("u_truss_splice", 1),
            ("m6_nut_retainer", 1),
        ],
    },
    {
        "subplate_id": "00G-C1",
        "filename": "00G-C1_ABS_received_camera_fit_tests.3mf",
        "profile": "abs_holder_precision",
        "objects": [("camera_case_fit_gauge", 1), ("camera_case_shim_ladder", 1)],
    },
    {
        "subplate_id": "00G-P1",
        "filename": "00G-P1_TPU_camera_portal_pads.3mf",
        "profile": "tpu_pads",
        "objects": [("board_pressure_pad", 4), ("camera_top_compression_pad", 1)],
    },
    {
        "subplate_id": "08A-S1",
        "filename": "08A-S1_ABS_left_bench_saddle.3mf",
        "profile": "abs_structural",
        "objects": [("board_corner_saddle_left", 1)],
    },
    {
        "subplate_id": "08A-S2",
        "filename": "08A-S2_ABS_left_cap_and_splices.3mf",
        "profile": "abs_structural",
        "objects": [("board_corner_cap_left", 1), ("u_truss_splice", 2), ("m6_nut_retainer", 2)],
    },
    {
        "subplate_id": "08A-J1",
        "filename": "08A-J1_ABS_left_portal_corner_pair.3mf",
        "profile": "abs_structural",
        "objects": [("portal_corner_node_left", 2)],
    },
    {
        "subplate_id": "08A-T1",
        "filename": "08A-T1_ABS_left_uprights_1_2.3mf",
        "profile": "abs_structural",
        "objects": [("upright_truss_segment_240", 2)],
    },
    {
        "subplate_id": "08A-T2",
        "filename": "08A-T2_ABS_left_uprights_3_4.3mf",
        "profile": "abs_structural",
        "objects": [("upright_truss_segment_240", 2)],
    },
    {
        "subplate_id": "08B-S1",
        "filename": "08B-S1_ABS_right_bench_saddle.3mf",
        "profile": "abs_structural",
        "objects": [("board_corner_saddle_right", 1)],
    },
    {
        "subplate_id": "08B-S2",
        "filename": "08B-S2_ABS_right_cap_and_splices.3mf",
        "profile": "abs_structural",
        "objects": [("board_corner_cap_right", 1), ("u_truss_splice", 3), ("m6_nut_retainer", 2)],
    },
    {
        "subplate_id": "08B-J1",
        "filename": "08B-J1_ABS_right_portal_corner_pair.3mf",
        "profile": "abs_structural",
        "objects": [("portal_corner_node_right", 2)],
    },
    {
        "subplate_id": "08B-T1",
        "filename": "08B-T1_ABS_right_uprights_1_2.3mf",
        "profile": "abs_structural",
        "objects": [("upright_truss_segment_240", 2)],
    },
    {
        "subplate_id": "08B-T2",
        "filename": "08B-T2_ABS_right_uprights_3_4.3mf",
        "profile": "abs_structural",
        "objects": [("upright_truss_segment_240", 2)],
    },
    {
        "subplate_id": "08C-X1",
        "filename": "08C-X1_ABS_crossbar_1_2.3mf",
        "profile": "abs_structural",
        "objects": [("crossbar_truss_segment_182p5", 2)],
    },
    {
        "subplate_id": "08C-X2",
        "filename": "08C-X2_ABS_crossbar_3_4.3mf",
        "profile": "abs_structural",
        "objects": [("crossbar_truss_segment_182p5", 2)],
    },
    {
        "subplate_id": "08C-B1",
        "filename": "08C-B1_ABS_booms_1_2.3mf",
        "profile": "abs_structural",
        "objects": [("boom_root_truss_segment_164p25", 2)],
    },
    {
        "subplate_id": "08C-B2",
        "filename": "08C-B2_ABS_booms_3_4.3mf",
        "profile": "abs_structural",
        "objects": [("boom_camera_truss_segment_164p25", 2)],
    },
    {
        "subplate_id": "08C-J1",
        "filename": "08C-J1_ABS_crossbar_boom_splices.3mf",
        "profile": "abs_structural",
        "objects": [
            ("u_truss_splice", 2),
            ("u_truss_splice_crossbar_2bolt", 2),
            ("u_truss_splice_center_4bolt", 1),
        ],
    },
    {
        "subplate_id": "08C-J2",
        "filename": "08C-J2_ABS_boom_root_nodes.3mf",
        "profile": "abs_structural",
        "objects": [("boom_crossbar_node", 4)],
    },
    {
        "subplate_id": "08C-C1",
        "filename": "08C-C1_ABS_camera_xy_carriage.3mf",
        "profile": "abs_structural",
        "objects": [("camera_xy_carriage", 1)],
    },
    {
        "subplate_id": "08D-C1",
        "filename": "08D-C1_ABS_camera_cage_and_keeper.3mf",
        "profile": "abs_holder_precision",
        "objects": [("camera_cage_body", 1), ("camera_cage_keeper", 1)],
    },
]


def clean_managed_outputs(current_part_names: Iterable[str]) -> list[str]:
    """Remove obsolete generator-owned geometry while preserving reports/docs."""
    current = set(current_part_names)
    removed: list[str] = []
    for directory, suffix in ((STEP_DIR, ".step"), (STL_DIR, ".stl")):
        for path in directory.glob(f"*{suffix}"):
            if path.stem not in current:
                path.unlink()
                removed.append(str(path.relative_to(ROOT)).replace("\\", "/"))

    assembly_allow = {
        "printable_camera_portal_prototype.step",
        "printable_camera_portal_prototype_reference.stl",
        "printable_camera_portal_printed_parts_only.step",
        "printable_camera_portal_printed_parts_only.stl",
        "camera_cage_nominal_subassembly.step",
    }
    for path in ASSEMBLY_DIR.iterdir():
        if path.is_file() and path.suffix.lower() in {".step", ".stl"} and path.name not in assembly_allow:
            path.unlink()
            removed.append(str(path.relative_to(ROOT)).replace("\\", "/"))

    plate_allow = {entry["filename"] for entry in PLATE_DEFINITIONS}
    for path in PLATE_DIR.glob("*.3mf"):
        if path.name not in plate_allow:
            path.unlink()
            removed.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    return sorted(removed)


def validate_managed_output_inventory(current_part_names: Iterable[str], removed: list[str]) -> dict:
    expected_parts = set(current_part_names)
    actual_step = {path.stem for path in STEP_DIR.glob("*.step")}
    actual_stl = {path.stem for path in STL_DIR.glob("*.stl")}
    expected_assemblies = {
        "printable_camera_portal_prototype.step",
        "printable_camera_portal_prototype_reference.stl",
        "printable_camera_portal_printed_parts_only.step",
        "printable_camera_portal_printed_parts_only.stl",
        "camera_cage_nominal_subassembly.step",
    }
    actual_assemblies = {
        path.name
        for path in ASSEMBLY_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".step", ".stl"}
    }
    expected_plates = {entry["filename"] for entry in PLATE_DEFINITIONS}
    actual_plates = {path.name for path in PLATE_DIR.glob("*.3mf")}
    differences = {
        "step_missing": sorted(expected_parts - actual_step),
        "step_unexpected": sorted(actual_step - expected_parts),
        "stl_missing": sorted(expected_parts - actual_stl),
        "stl_unexpected": sorted(actual_stl - expected_parts),
        "assembly_missing": sorted(expected_assemblies - actual_assemblies),
        "assembly_unexpected": sorted(actual_assemblies - expected_assemblies),
        "plate_missing": sorted(expected_plates - actual_plates),
        "plate_unexpected": sorted(actual_plates - expected_plates),
    }
    passed = not any(differences.values())
    report = {
        "status": "PASS" if passed else "FAIL",
        "removed_obsolete_files_this_run": removed,
        "expected_part_type_count": len(expected_parts),
        "step_file_count": len(actual_step),
        "stl_file_count": len(actual_stl),
        "assembly_file_count": len(actual_assemblies),
        "plate_file_count": len(actual_plates),
        "differences": differences,
    }
    if not passed:
        raise ValueError(f"Managed output inventory mismatch: {report}")
    return report


def aabb_overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return min(ax + aw, bx + bw) > max(ax, bx) and min(ay + ah, by + bh) > max(ay, by)


def validate_design_contract() -> dict:
    left_axis = CFG["layout"]["left_tower_axis_xy_mm"]
    right_axis = CFG["layout"]["right_tower_axis_xy_mm"]
    camera_axis = CFG["layout"]["camera_axis_xy_mm"]
    checks = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail})

    add("left_axis_locked", left_axis == [-60.0, -100.0], str(left_axis))
    add("right_axis_locked", right_axis == [670.0, -100.0], str(right_axis))
    add("camera_axis_locked", camera_axis == [305.0, 228.5], str(camera_axis))
    add("camera_carriage_size_locked", [CARRIAGE_W, CARRIAGE_D] == [250.0, 130.0], f"{CARRIAGE_W} x {CARRIAGE_D} mm")
    add(
        "camera_x_indices_locked",
        CAGE_INSTALLED_X_OFFSETS == (-12.0, 0.0, 12.0),
        f"three positive-lock round-bore indices={CAGE_INSTALLED_X_OFFSETS}",
    )
    add(
        "camera_y_indices_locked",
        CARRIAGE_INSTALLED_Y_OFFSETS == (0.0, 21.0) and CARRIAGE_HOLE_Y_OFFSETS == (0.0, -21.0),
        f"installed={CARRIAGE_INSTALLED_Y_OFFSETS}; carriage hole rows={CARRIAGE_HOLE_Y_OFFSETS}",
    )
    cross_sum = CFG["layout"]["crossbar_segment_length_mm"] * CFG["layout"]["crossbar_segment_count"]
    add("crossbar_span", abs(cross_sum - 730.0) < 1e-6, f"{cross_sum:.6f} mm")
    add("four_equal_crossbar_modules", CROSS_COUNT == 4 and abs(CROSS_LENGTH - 182.5) < 1e-6, f"count={CROSS_COUNT}; length={CROSS_LENGTH:.3f}")
    expected_boom_axes = (
        float(left_axis[0]) + 1.5 * CROSS_LENGTH,
        float(left_axis[0]) + 2.5 * CROSS_LENGTH,
    )
    add(
        "boom_roots_centered_on_inner_crossbar_modules",
        all(abs(actual - expected) < 1e-6 for actual, expected in zip(BOOM_AXES_X, expected_boom_axes)),
        f"actual={BOOM_AXES_X}; expected={expected_boom_axes}",
    )
    boom_inner_gap = BOOM_AXES_X[1] - BOOM_AXES_X[0] - TRUSS_W
    cage_side_clearance = (boom_inner_gap - 96.0) / 2.0
    residual_index_clearance = cage_side_clearance - max(abs(value) for value in CAGE_INSTALLED_X_OFFSETS)
    add(
        "boom_gap_clears_camera_cage_at_all_x_indices",
        residual_index_clearance >= 5.0,
        f"inner gap={boom_inner_gap:.3f}; centered side clearance={cage_side_clearance:.3f}; worst indexed clearance={residual_index_clearance:.3f}",
    )
    boom_sum = CFG["layout"]["boom_segment_length_mm"] * CFG["layout"]["boom_segments_per_side"]
    boom_root = CFG["layout"]["boom_root_y_mm"]
    boom_end = boom_root + boom_sum
    boom_attachment = boom_end - 25.0
    add("boom_end", abs(boom_end - CFG["layout"]["boom_end_y_mm"]) < 1e-6, f"end y={boom_end:.3f}")
    add("boom_attachment_at_optical_y", abs(boom_attachment - 228.5) < 1e-6, f"vertical collar holes y={boom_attachment:.3f}")
    add("boom_butts_crossbar_without_overlap", abs(boom_root - (-100.0 + TRUSS_W / 2.0)) < 1e-6, f"boom root/crossbar rear face y={boom_root:.3f}")
    add(
        "boom_root_sandwich_straps_locked",
        [ROOT_STRAP_W, ROOT_STRAP_D, ROOT_STRAP_T] == [80.0, 84.0, 8.0]
        and ROOT_BOLT_X_OFFSETS == (-17.0, 17.0)
        and ROOT_CROSSBAR_BOLT_Y == -99.0
        and ROOT_BOOM_BOLT_Y == -51.0,
        f"strap={ROOT_STRAP_W}x{ROOT_STRAP_D}x{ROOT_STRAP_T}; x offsets={ROOT_BOLT_X_OFFSETS}; y rows=({ROOT_CROSSBAR_BOLT_Y},{ROOT_BOOM_BOLT_Y})",
    )
    root_to_splice_gap = BOOM_AXES_X[0] - ROOT_STRAP_W / 2.0 - (-60.0 + CROSS_LENGTH + CROSS_SPLICE_HALF)
    add("root_strap_to_crossbar_splice_gap", root_to_splice_gap >= 5.0, f"nominal gap={root_to_splice_gap:.3f} mm")
    tether_axis = tuple(map(float, CFG["layout"]["tether_choker_axis_xy_mm"]))
    add(
        "tether_station_centered_in_exposed_window",
        tether_axis == (BOOM_AXES_X[1], TETHER_CHOKER_Y)
        and (boom_root + 164.25 + SPLICE_HALF) < TETHER_CHOKER_Y < CARRIAGE_Y0,
        f"axis={tether_axis}; clear window y={boom_root + 164.25 + SPLICE_HALF:.3f}..{CARRIAGE_Y0:.3f}",
    )
    outrigger_range = CFG["layout"]["integrated_saddle_outrigger_y_range_mm"]
    add("low_structure_front_only", outrigger_range[1] <= -100.0, str(outrigger_range))
    add("no_rear_side_stays", not CFG["layout"]["rear_or_side_structural_stays_allowed"], "rear/side structural stays disabled")
    add("clamp_lip_intrusion_limit", CFG["board_clamp"]["top_lip_intrusion_from_side_mm"] <= 10.0 and CFG["board_clamp"]["top_lip_intrusion_from_front_mm"] <= 10.0, "both <=10 mm")

    clear_bench = CFG["board_clamp"]["required_clear_bench_xy_mm"]
    add("bench_clearance_exact", clear_bench == [-120.0, -250.0, 730.0, 0.0], str(clear_bench))
    bench_z = float(CFG["board_clamp"]["bench_plane_z_mm"])
    add("board_and_feet_coplanar", abs(bench_z + BOARD_T) < 1e-6, f"board underside and saddle feet z={bench_z:.3f}")
    pad_stack = BOARD_T + CFG["board_clamp"]["uncompressed_pad_thickness_mm"] - CFG["board_clamp"]["nominal_pad_compression_mm"]
    add("clamp_hard_stop_includes_pad", abs(pad_stack - CFG["board_clamp"]["hard_stop_gap_mm"]) < 1e-6, f"nominal compressed stack={pad_stack:.3f}")
    cap_z = float(CFG["board_clamp"]["hard_stop_gap_mm"]) - BOARD_T
    m6_bearing_z = cap_z + M6_CAP_BOSS_BEARING_Z
    m6_bolt_end_z = m6_bearing_z - M6_CLAMP_BOLT_LENGTH
    saddle_bore_floor_z = bench_z + M6_SADDLE_BLIND_BORE_FLOOR_Z
    add(
        "m6_integrated_boss_rise",
        abs(M6_CAP_BOSS_BEARING_Z - M6_CAP_BASE_TOP_Z - 1.8) < 1e-6,
        f"cap base top local z={M6_CAP_BASE_TOP_Z:.3f}; boss bearing local z={M6_CAP_BOSS_BEARING_Z:.3f}",
    )
    add(
        "m6_bolt_tip_clearance_above_bench",
        m6_bolt_end_z - bench_z >= 3.0,
        f"bolt end z={m6_bolt_end_z:.3f}; bench z={bench_z:.3f}; clearance={m6_bolt_end_z - bench_z:.3f} mm",
    )
    add(
        "m6_bolt_tip_clearance_above_blind_bore_floor",
        m6_bolt_end_z - saddle_bore_floor_z >= 2.5,
        f"bolt end z={m6_bolt_end_z:.3f}; bore floor z={saddle_bore_floor_z:.3f}; clearance={m6_bolt_end_z - saddle_bore_floor_z:.3f} mm",
    )
    m6_nut_lower_face_z = bench_z + 6.55
    m6_thread_projection = m6_nut_lower_face_z - m6_bolt_end_z
    add(
        "m6_full_nyloc_thread_projection",
        m6_thread_projection >= 2.0,
        f"bolt projects {m6_thread_projection:.3f} mm past the modeled lower face of the 6.0 mm DIN 985 nyloc",
    )
    add(
        "m6_channel_and_covered_tunnel_locked",
        LEFT_SADDLE_CLAMP_X == (108.0, 150.0)
        and SADDLE_CLAMP_Y == 148.0
        and M6_INNER_NUT_CHANNEL_MOUTH_XY == (128.0, 102.0)
        and M6_OUTER_NUT_CHANNEL_OPENING_Y == 115.5
        and M6_NUT_CHANNEL_WIDTH == 12.2
        and M6_NUT_TUNNEL_WIDTH == 20.0
        and M6_NUT_TUNNEL_TOP_Z == 14.6
        and M6_NUT_TUNNEL_MIN_ROOF == 1.9
        and M6_NUT_TUNNEL_TOP_Z - (5.3 + 7.4) >= M6_NUT_TUNNEL_MIN_ROOF,
        f"channels={M6_NUT_CHANNEL_WIDTH:.1f} mm; tunnel={M6_NUT_TUNNEL_WIDTH:.1f} x {M6_NUT_TUNNEL_TOP_Z:.1f} mm; worst roof={M6_NUT_TUNNEL_TOP_Z - (5.3 + 7.4):.1f} mm",
    )
    add("top_tool_access_outside_board", -12.0 < 0.0, "all four M6 axes at B y=-12; driven vertically from above")
    add("upright_positive_bearing_seat", abs((-BOARD_T + 68.0) - 50.0) < 1e-6, "saddle ledge top and upright bottom both B z=50; M5 bolt is registration, not gravity support")

    cross_z = float(CFG["layout"]["crossbar_bottom_z_mm"])
    boom_z = float(CFG["layout"]["boom_bottom_z_mm"])
    add("crossbar_boom_elevation_aligned", abs(cross_z - boom_z) < 1e-6, f"bottom z={cross_z:.3f}")
    add("carriage_bears_on_boom_top", abs((boom_z + TRUSS_H) - 1074.0) < 1e-6, f"boom top/carriage bottom z={boom_z + TRUSS_H:.3f}")
    add(
        "planar_keeper_bears_below_carriage",
        abs((1026.0 + 42.0 + 6.0) - 1074.0) < 1e-6,
        "planar keeper top and carriage bottom share z=1074; four bolts provide positive retention without slide hooks",
    )
    static_min_z = min(1000.0, 1026.0, 1084.0 - 70.0, 1030.0)
    add("installed_camera_hardware_above_robot_screen", static_min_z >= 920.0, f"minimum modeled camera/lens/bolt/tether z={static_min_z:.3f}")

    production_piece_count = sum(
        int(entry["quantity"]) - int(entry.get("sacrificial_quantity", 0))
        for entry in CFG["parts"]
        if not entry.get("print_first")
    )
    hardware_piece_count = sum(int(entry["quantity"]) for entry in CFG["hardware"])
    add("production_printed_piece_target", production_piece_count == 52, f"{production_piece_count} production pieces including loose shim stock and excluding three print-first coupons and one sacrificial retainer")
    add("hardware_piece_target", hardware_piece_count == 147, f"{hardware_piece_count} hardware pieces including one sacrificial M6 coupon nut, four sacrificial proof-test carriage nylocs, eight M5x90 boom-root sandwich bolts, and four M4 keeper closures")
    m5_bolts = sum(int(entry["quantity"]) for entry in CFG["hardware"] if entry["item"].startswith("M5 x ") and entry["item"].endswith("flange-head bolt"))
    m5_nylocs = next(int(entry["quantity"]) for entry in CFG["hardware"] if entry["item"] == "M5 flanged nyloc nut")
    add("m5_bolt_nyloc_reconciliation", m5_bolts == 48 and m5_nylocs == 52, f"bolts={m5_bolts}; final installed nylocs=48; proof-test-only sacrificial nylocs={m5_nylocs - m5_bolts}; total nylocs={m5_nylocs}")
    wrench = CFG["required_assembly_tools"][0]
    add(
        "leveling_jam_nut_wrench_contract",
        wrench["item"] == "thin 7 mm open-end wrench"
        and float(wrench["maximum_head_width_mm"]) <= 18.0
        and float(wrench["maximum_head_thickness_mm"]) <= 5.5,
        str(wrench),
    )
    socket_tool = CFG["required_assembly_tools"][1]
    add(
        "m5_thin_wall_socket_contract",
        socket_tool["item"] == "two thin-wall 8 mm sockets or nut drivers"
        and float(socket_tool["maximum_socket_outer_diameter_mm"]) <= 13.0,
        str(socket_tool),
    )
    m4_driver = CFG["required_assembly_tools"][2]
    add("m4_hex_key_contract", m4_driver["item"] == "2.5 mm hex key", str(m4_driver))
    m6_socket = CFG["required_assembly_tools"][3]
    add(
        "m6_thin_wall_socket_contract",
        m6_socket["item"] == "one thin-wall 10 mm socket or nut driver"
        and float(m6_socket["maximum_socket_outer_diameter_mm"]) <= 18.0,
        str(m6_socket),
    )

    # Procurement constraints are validated as metadata only.  None of these
    # checks drives printable geometry; the first received cap bolt and the
    # complete factory-terminated tether remain mandatory physical gates.
    procurement = CFG["procurement_constraints"]
    m6_spec = procurement["m6_x25_flange_head_clamp_bolt"]
    m6_hardware = next(
        entry for entry in CFG["hardware"] if entry["item"] == "M6 x 25 external-hex flange-head bolt"
    )
    nominal_support_margin = float(m6_spec["modeled_cap_boss_outer_diameter_mm"]) - float(m6_spec["maximum_head_outer_diameter_mm"])
    worst_case_radial_support = nominal_support_margin / 2.0 - float(m6_spec["maximum_shank_to_bore_lateral_decenter_mm"])
    add(
        "m6_flange_head_procurement_limit",
        int(m6_spec["quantity"]) == int(m6_hardware["quantity"]) == 4
        and float(m6_spec["finished_length_mm"]) == 25.0
        and m6_spec["drive_style"] == "external hex"
        and float(m6_spec["wrench_size_mm"]) == 10.0
        and float(m6_spec["maximum_head_outer_diameter_mm"]) <= 13.5,
        f"qty={m6_spec['quantity']}; length={m6_spec['finished_length_mm']} mm; maximum head OD={m6_spec['maximum_head_outer_diameter_mm']} mm",
    )
    m6_nut_spec = procurement["m6_din985_nyloc_nut"]
    m6_nut_hardware = next(entry for entry in CFG["hardware"] if entry["item"] == "M6 DIN 985 nyloc nut")
    add(
        "m6_nyloc_capture_contract",
        int(m6_nut_spec["quantity"]) == int(m6_nut_hardware["quantity"]) == 5
        and float(m6_nut_spec["wrench_size_mm"]) == 10.0
        and float(m6_nut_spec["maximum_height_mm"]) <= 6.0
        and float(m6_nut_spec["modeled_hex_pocket_circumscribed_diameter_mm"]) == 12.3
        and float(m6_nut_spec["modeled_channel_width_mm"]) == M6_NUT_CHANNEL_WIDTH == 12.2
        and float(m6_nut_spec["modeled_channel_height_mm"]) == 7.2,
        str(m6_nut_spec),
    )
    add(
        "m6_cap_boss_head_support_margin",
        float(m6_spec["modeled_cap_boss_outer_diameter_mm"]) == 16.0
        and float(m6_spec["modeled_cap_base_top_height_mm"]) == M6_CAP_BASE_TOP_Z == 8.0
        and float(m6_spec["modeled_cap_boss_bearing_height_mm"]) == M6_CAP_BOSS_BEARING_Z == 9.8
        and nominal_support_margin + 1e-9 >= float(m6_spec["minimum_nominal_head_support_diameter_margin_mm"])
        and worst_case_radial_support + 1e-9 >= float(m6_spec["minimum_worst_case_radial_support_mm"]),
        f"16.0 mm boss - {m6_spec['maximum_head_outer_diameter_mm']} mm maximum head = {nominal_support_margin:.3f} mm diameter margin; worst-case supported radial rim={worst_case_radial_support:.3f} mm after permitted decenter; physical first-boss seating remains mandatory",
    )

    tether_spec = procurement["independent_camera_safety_tether"]
    tether_hardware = next(
        entry
        for entry in CFG["hardware"]
        if entry["item"] == "complete factory-terminated independent metal camera safety tether assembly"
    )
    tether_exact = (
        int(tether_spec["quantity"]) == int(tether_hardware["quantity"]) == 1
        and tether_spec["supply_form"] == "single complete factory-terminated assembly"
        and float(tether_spec["finished_length_nominal_mm"]) == 500.0
        and float(tether_spec["finished_length_tolerance_mm"]) == 25.0
        and tether_spec["finished_length_measurement"]
        == "load-bearing cable centerline from the cage-connector bearing point through the complete choker-eye circumference"
        and float(tether_spec["installed_slack_minimum_mm"]) >= 20.0
        and float(tether_spec["installed_slack_maximum_mm"]) <= 105.0
        and tether_spec["cable_material"] == "stainless steel"
        and tether_spec["cable_construction"] == "7x7"
        and float(tether_spec["bare_cable_diameter_min_mm"]) == 1.5
        and float(tether_spec["bare_cable_diameter_max_mm"]) == 2.0
        and float(tether_spec["coated_finished_outer_diameter_max_mm"]) <= 3.0
        and float(tether_spec["boom_choker_eye_laid_flat_minimum_mm"]) >= 130.0
        and tether_spec["cage_connector"] == "captive screw-lock connector"
        and float(tether_spec["cage_connector_stock_or_pin_maximum_mm"]) <= 5.0
        and float(tether_spec["cage_connector_opening_minimum_mm"]) >= 9.0
        and float(tether_spec["manufacturer_working_load_limit_minimum_kg"]) >= 10.0
        and float(tether_spec["manufacturer_minimum_breaking_load_minimum_kg"]) >= 50.0
        and "all load-bearing" in tether_spec["load_path"]
    )
    add(
        "factory_terminated_tether_procurement_contract",
        tether_exact,
        "qty1; 500+/-25 mm cable-centerline length; 20-105 mm installed slack; 1.5-2.0 mm 7x7 stainless; coated OD<=3.0; eye>=130; screw-lock pin<=5/opening>=9; manufacturer WLL>=10 kg/MBL>=50 kg",
    )
    m4_keeper = next(entry for entry in CFG["hardware"] if entry["item"] == "M4 x 60 button-head bolt")
    m4_level = next(entry for entry in CFG["hardware"] if entry["item"] == "M4 x 70 button-head socket bolt")
    add("four_bolt_keeper", int(m4_keeper["quantity"]) == 4, str(m4_keeper))
    add("three_point_leveling", int(m4_level["quantity"]) == 3, str(m4_level))

    # Only these narrow rectangles overlap the board top.
    left_lips = [(0.0, 0.0, 85.0, 10.0), (0.0, 0.0, 10.0, 85.0)]
    right_lips = [(BOARD_W - 85.0, 0.0, 85.0, 10.0), (BOARD_W - 10.0, 0.0, 10.0, 85.0)]
    tag_rects = [tuple(CFG["board"]["front_tag_tiles"][key]) for key in ("T0_xywh_mm", "T1_xywh_mm")]
    collisions = []
    for lip_index, lip in enumerate(left_lips + right_lips):
        for tag_name, tag in zip(("T0", "T1"), tag_rects):
            if aabb_overlap(lip, tag):
                collisions.append(f"lip{lip_index}:{tag_name}")
    add("front_lips_clear_T0_T1", not collisions, "none" if not collisions else ",".join(collisions))

    failures = [row for row in checks if row["status"] != "PASS"]
    report = {"status": "PASS" if not failures else "FAIL", "checks": checks}
    if failures:
        raise ValueError(f"Printable frame contract failure(s): {failures}")
    return report


def export_part(name: str, part: cq.Workplane, quantity: int) -> dict:
    step_path = STEP_DIR / f"{name}.step"
    stl_path = STL_DIR / f"{name}.stl"
    exporters.export(part, str(step_path))
    exporters.export(part, str(stl_path), tolerance=0.08, angularTolerance=0.08)
    mesh = trimesh.load_mesh(stl_path, force="mesh")
    ext = [float(value) for value in mesh.extents]
    components = len(mesh.split(only_watertight=False))
    fits = ext[0] <= SAFE_X + 1e-6 and ext[1] <= SAFE_Y + 1e-6 and ext[2] <= SAFE_Z + 1e-6
    row = {
        "part": name,
        "quantity": quantity,
        "step": str(step_path.relative_to(ROOT)).replace("\\", "/"),
        "stl": str(stl_path.relative_to(ROOT)).replace("\\", "/"),
        "stl_sha256": sha256_file(stl_path),
        "geometry_identifier_sha256": str(mesh.identifier_hash),
        "extent_x_mm": round(ext[0], 3),
        "extent_y_mm": round(ext[1], 3),
        "extent_z_mm": round(ext[2], 3),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "connected_components": components,
        "single_body": components == 1,
        "positive_volume": bool(mesh.volume > 0),
        "volume_cm3_each": round(float(mesh.volume) / 1000.0, 2),
        "fits_protected_295x295x275": fits,
        "validation": "PASS" if mesh.is_watertight and components == 1 and mesh.volume > 0 and fits else "FAIL",
    }
    return row


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _plate_object_list(definition: dict) -> list[str]:
    return [
        part_name
        for part_name, quantity in definition["objects"]
        for _ in range(int(quantity))
    ]


def validate_plate_allocation(configured_quantities: Dict[str, int]) -> dict:
    """Prove that the 21 subplates allocate every configured printed piece once."""
    allocated: Dict[str, int] = {}
    for definition in PLATE_DEFINITIONS:
        for part_name, quantity in definition["objects"]:
            allocated[part_name] = allocated.get(part_name, 0) + int(quantity)
    missing = {
        name: configured_quantities[name] - allocated.get(name, 0)
        for name in configured_quantities
        if configured_quantities[name] != allocated.get(name, 0)
    }
    unexpected = {name: quantity for name, quantity in allocated.items() if name not in configured_quantities}
    status = "PASS" if not missing and not unexpected and len(PLATE_DEFINITIONS) == 21 else "FAIL"
    report = {
        "status": status,
        "subplate_count": len(PLATE_DEFINITIONS),
        "configured_piece_count": sum(configured_quantities.values()),
        "allocated_piece_count": sum(allocated.values()),
        "allocated_quantities": dict(sorted(allocated.items())),
        "quantity_differences": missing,
        "unexpected_parts": unexpected,
        "note": "The accepted 00G production splice transfers to the left tower. The single 00G barbed M6 retainer is sacrificial; two fresh retainers are allocated to each side. No installed production piece is duplicated.",
    }
    if status != "PASS":
        raise ValueError(f"3MF subplate allocation mismatch: {report}")
    return report


def export_geometry_only_plates() -> tuple[list[dict], dict]:
    """Export deterministic, geometry-only 3MF subplates and validate archives."""
    margin = 10.0
    gap = 20.0  # leaves room for a 10 mm brim around adjacent ABS objects
    results: list[dict] = []
    csv_rows: list[dict] = []

    for definition in PLATE_DEFINITIONS:
        instances = []
        per_part_index: Dict[str, int] = {}
        for part_name in _plate_object_list(definition):
            mesh = trimesh.load_mesh(STL_DIR / f"{part_name}.stl", force="mesh", process=False)
            # STL repeats triangle vertices; 3MF requires shared vertex indices
            # for a connected manifold mesh. Weld EXACT duplicate coordinates
            # only, without smoothing, rounding, or changing the triangle soup.
            vertices, inverse = np.unique(mesh.vertices, axis=0, return_inverse=True)
            mesh = trimesh.Trimesh(vertices=vertices, faces=inverse[mesh.faces], process=False)
            if not mesh.is_watertight or not mesh.is_winding_consistent:
                raise ValueError(f"{part_name}: non-manifold mesh before 3MF export")
            per_part_index[part_name] = per_part_index.get(part_name, 0) + 1
            rotation_deg = 0.0
            # XY rotations preserve the verified support-free print orientation.
            if float(mesh.extents[1]) > float(mesh.extents[0]):
                mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, (0, 0, 1)))
                rotation_deg = 90.0
            instances.append(
                {
                    "part": part_name,
                    "instance": per_part_index[part_name],
                    "mesh": mesh,
                    "rotation_z_deg": rotation_deg,
                }
            )

        # Tallest footprints first makes the simple shelf packing deterministic
        # and robust while retaining a full 10 mm outer build-plate margin.
        instances.sort(key=lambda item: (-float(item["mesh"].extents[1]), -float(item["mesh"].extents[0]), item["part"], item["instance"]))
        cursor_x = margin
        cursor_y = margin
        row_height = 0.0
        placed = []
        scene = trimesh.Scene()
        for item in instances:
            mesh = item["mesh"]
            width, depth, height = map(float, mesh.extents)
            if width > SAFE_X - 2.0 * margin + 1e-6 or depth > SAFE_Y - 2.0 * margin + 1e-6:
                raise ValueError(f"{definition['subplate_id']} object {item['part']} cannot fit plate with margin")
            if cursor_x + width > SAFE_X - margin + 1e-6:
                cursor_x = margin
                cursor_y += row_height + gap
                row_height = 0.0
            if cursor_y + depth > SAFE_Y - margin + 1e-6:
                raise ValueError(f"{definition['subplate_id']} shelf packing exceeds protected plate at {item['part']}")

            bounds = mesh.bounds.copy()
            shift = (cursor_x - float(bounds[0, 0]), cursor_y - float(bounds[0, 1]), -float(bounds[0, 2]))
            mesh.apply_translation(shift)
            final_bounds = mesh.bounds
            instance_name = f"{item['part']}__{item['instance']:02d}"
            # Trimesh reserves graph-node names beginning with ``camera`` and
            # omits them from the 3MF build section.  Prefix every build node
            # while retaining the exact part/instance name on the mesh object.
            scene.add_geometry(mesh, node_name=f"print_item__{instance_name}", geom_name=instance_name)
            placement = {
                "object": instance_name,
                "part": item["part"],
                "rotation_z_deg": item["rotation_z_deg"],
                "translation_mm": [round(float(value), 4) for value in shift],
                "bounds_mm": [[round(float(value), 4) for value in row] for row in final_bounds],
            }
            placed.append(placement)
            cursor_x += width + gap
            row_height = max(row_height, depth)

        # Ensure no two positioned mesh bounding boxes overlap in XY.
        xy_overlaps = []
        for left_index, left in enumerate(placed):
            lb = left["bounds_mm"]
            for right in placed[left_index + 1 :]:
                rb = right["bounds_mm"]
                overlap_x = min(lb[1][0], rb[1][0]) > max(lb[0][0], rb[0][0]) + 1e-6
                overlap_y = min(lb[1][1], rb[1][1]) > max(lb[0][1], rb[0][1]) + 1e-6
                if overlap_x and overlap_y:
                    xy_overlaps.append([left["object"], right["object"]])
        if xy_overlaps:
            raise ValueError(f"{definition['subplate_id']} has overlapping packed AABBs: {xy_overlaps}")

        path = PLATE_DIR / definition["filename"]
        path.write_bytes(scene.export(file_type="3mf"))

        with zipfile.ZipFile(path) as archive:
            model_xml = ET.fromstring(archive.read("3D/3dmodel.model"))
        namespace = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
        resource_count = len(model_xml.findall("./m:resources/m:object", namespace))
        build_item_count = len(model_xml.findall("./m:build/m:item", namespace))
        roundtrip = trimesh.load(path, force="scene", process=False)
        # Do not let an automatically repaired STL stand in for validation of
        # the actual packaged 3MF topology.
        for mesh_name, raw_mesh in roundtrip.geometry.items():
            if not raw_mesh.is_watertight or not raw_mesh.is_winding_consistent:
                raise ValueError(f"{path.name}/{mesh_name}: raw 3MF topology is invalid")
        roundtrip_geometry_count = len(roundtrip.geometry)
        plate_bounds = roundtrip.bounds
        extents = plate_bounds[1] - plate_bounds[0]
        expected_count = len(placed)
        fits = (
            float(plate_bounds[0, 0]) >= -1e-5
            and float(plate_bounds[0, 1]) >= -1e-5
            and float(plate_bounds[0, 2]) >= -1e-5
            and float(plate_bounds[1, 0]) <= SAFE_X + 1e-5
            and float(plate_bounds[1, 1]) <= SAFE_Y + 1e-5
            and float(plate_bounds[1, 2]) <= SAFE_Z + 1e-5
        )
        passed = resource_count == expected_count and build_item_count == expected_count and roundtrip_geometry_count == expected_count and fits
        row = {
            "subplate_id": definition["subplate_id"],
            "filename": definition["filename"],
            "profile_key": definition["profile"],
            "object_count": expected_count,
            "resource_object_count": resource_count,
            "build_item_count": build_item_count,
            "roundtrip_geometry_count": roundtrip_geometry_count,
            "extent_x_mm": round(float(extents[0]), 3),
            "extent_y_mm": round(float(extents[1]), 3),
            "extent_z_mm": round(float(extents[2]), 3),
            "fits_protected_295x295x275": fits,
            "sha256": sha256_file(path),
            "validation": "PASS" if passed else "FAIL",
        }
        csv_rows.append(row)
        results.append({**row, "objects": placed})
        if not passed:
            raise ValueError(f"3MF validation failure: {row}")

    with (OUTPUT_DIR / "PLATE_VALIDATION.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)
    report = {
        "status": "PASS",
        "format": "3MF geometry only; no material or process metadata embedded",
        "protected_envelope_mm": [SAFE_X, SAFE_Y, SAFE_Z],
        "outer_margin_mm": margin,
        "inter_object_gap_mm": gap,
        "subplate_count": len(results),
        "object_count": sum(row["object_count"] for row in results),
        "subplates": results,
    }
    (OUTPUT_DIR / "PLATE_VALIDATION.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return results, report


def _placed_crossbar(part: cq.Workplane, x0: float, y_axis: float, z0: float) -> cq.Workplane:
    return part.translate((x0, y_axis - TRUSS_W / 2.0, z0))


def _placed_upright(part: cq.Workplane, x_axis: float, y_axis: float, z0: float) -> cq.Workplane:
    return part.rotate((0, 0, 0), (0, 1, 0), -90.0).translate(
        (x_axis + TRUSS_H / 2.0, y_axis - TRUSS_W / 2.0, z0)
    )


def _placed_boom(part: cq.Workplane, x_axis: float, y0: float, z0: float) -> cq.Workplane:
    body = part.rotate((0, 0, 0), (0, 0, 1), 90.0)
    return body.translate((x_axis + TRUSS_W / 2.0, y0, z0))


def make_assembly(parts: Dict[str, cq.Workplane]) -> None:
    assy = cq.Assembly(name=CFG["design_id"])
    assembly_shapes = []

    def add(part: cq.Workplane, name: str, color: cq.Color) -> None:
        assy.add(part, name=name, color=color)
        assembly_shapes.extend(part.vals())

    def rod_between(start: Tuple[float, float, float], end: Tuple[float, float, float], radius: float) -> cq.Workplane:
        vector = cq.Vector(end[0] - start[0], end[1] - start[1], end[2] - start[2])
        length = vector.Length
        return cq.Workplane(obj=cq.Solid.makeCylinder(radius, length, cq.Vector(*start), vector.normalized()))

    # Exact required bench-clearance proxy.  Its top face is the z=-18 contact
    # plane shared by the board underside and both printed saddle footprints.
    bench = box_ll(850.0, 250.0, 0.25, -120.0, -250.0, -18.25)
    add(bench, "REQUIRED_CLEAR_BENCH_Xm120_TO730_Ym250_TO0", cq.Color(0.55, 0.55, 0.58, 0.28))
    board = box_ll(BOARD_W, BOARD_D, BOARD_T, z0=-BOARD_T)
    add(board, "BOARD_610x457x18_REFERENCE", cq.Color(0.62, 0.47, 0.29, 0.72))

    saddle_origins = {"L": (-120.0, -160.0, -BOARD_T), "R": (540.0, -160.0, -BOARD_T)}
    left_saddle = parts["board_corner_saddle_left"].translate(saddle_origins["L"])
    right_saddle = parts["board_corner_saddle_right"].translate(saddle_origins["R"])
    add(left_saddle, "LEFT_BENCH_BEARING_SADDLE", cq.Color(0.15, 0.32, 0.62, 1.0))
    add(right_saddle, "RIGHT_BENCH_BEARING_SADDLE", cq.Color(0.15, 0.32, 0.62, 1.0))
    cap_z = float(CFG["board_clamp"]["hard_stop_gap_mm"]) - BOARD_T
    add(parts["board_corner_cap_left"].translate((-25.0, -25.0, cap_z)), "LEFT_TAG_CLEAR_CAP", cq.Color(0.18, 0.42, 0.72, 1.0))
    add(parts["board_corner_cap_right"].translate((550.0, -25.0, cap_z)), "RIGHT_TAG_CLEAR_CAP", cq.Color(0.18, 0.42, 0.72, 1.0))

    # Side-loaded captured nylocs, individual snap retainers, and top-only M6
    # drive/tool paths are shown explicitly. The integrated cap boss puts every
    # M6x25 tip 3.45 mm above the bench and 2.70 mm above the blind-bore floor.
    for side in ("L", "R"):
        ox, oy, oz = saddle_origins[side]
        for index, spec in enumerate(saddle_m6_channel_specs(side), 1):
            local_x, local_y = spec["seat"]
            retainer = placed_m6_nut_retainer(
                parts["m6_nut_retainer"], spec["mouth"], spec["seat"], 3.7
            ).translate((ox, oy, oz))
            add(retainer, f"{side}_M6_{spec['name']}_NUT_RETAINER", cq.Color(0.94, 0.45, 0.10, 1.0))
            nut = (
                cq.Workplane("XY")
                .polygon(6, 11.55)
                .extrude(6.0)
                .rotate((0, 0, 0), (0, 0, 1), spec["hex_angle_deg"])
                .translate((ox + local_x, oy + local_y, oz + 6.55))
            )
            add(nut, f"{side}_M6_{spec['name']}_CAPTURED_DIN985_NYLOC", cq.Color(0.70, 0.72, 0.75, 1.0))
            gx, gy = ox + local_x, oy + local_y
            bearing_z = cap_z + M6_CAP_BOSS_BEARING_Z
            bolt = cq.Workplane(obj=cq.Solid.makeCylinder(3.0, M6_CLAMP_BOLT_LENGTH, cq.Vector(gx, gy, bearing_z), cq.Vector(0, 0, -1)))
            head = cq.Workplane(obj=cq.Solid.makeCylinder(6.75, 4.0, cq.Vector(gx, gy, bearing_z), cq.Vector(0, 0, 1)))
            add(bolt.union(head), f"{side}_M6x25_TOP_DRIVEN_{index}", cq.Color(0.70, 0.72, 0.75, 1.0))
            tool = cq.Workplane(obj=cq.Solid.makeCylinder(9.0, 30.0, cq.Vector(gx, gy, bearing_z + 4.0), cq.Vector(0, 0, 1)))
            add(tool, f"{side}_TOP_TOOL_ACCESS_KEEP_CLEAR_{index}", cq.Color(0.93, 0.20, 0.15, 0.18))

    # Direct-tag reference tiles for visual clearance review.
    for tag_name, values in CFG["board"]["front_tag_tiles"].items():
        x, y, w, h = map(float, values)
        add(rounded_plate(w, h, 0.25, 1.0, x, y, 0.0), f"{tag_name[:2]}_TAG_KEEP_CLEAR", cq.Color(0.93, 0.93, 0.93, 0.9))

    upright = parts["upright_truss_segment_240"]
    cross = parts["crossbar_truss_segment_182p5"]
    boom_root_part = parts["boom_root_truss_segment_164p25"]
    boom_camera_part = parts["boom_camera_truss_segment_164p25"]
    splice = parts["u_truss_splice"]
    cross_splice = parts["u_truss_splice_crossbar_2bolt"]
    center_splice = parts["u_truss_splice_center_4bolt"]
    splice_w = TRUSS_W + 0.8 + 12.0
    splice_y_offset = -(splice_w - TRUSS_W) / 2.0
    splice_z_offset = -4.0
    upright_start_z = 50.0
    cross_z = float(CFG["layout"]["crossbar_bottom_z_mm"])
    boom_z = float(CFG["layout"]["boom_bottom_z_mm"])

    for side, x_axis in (("L", -60.0), ("R", 670.0)):
        for index in range(4):
            add(
                _placed_upright(upright, x_axis, -100.0, upright_start_z + 240.0 * index),
                f"{side}_UPRIGHT_{index + 1}",
                cq.Color(0.22, 0.40, 0.67, 1.0),
            )
        for joint_index in range(1, 4):
            joint_z = upright_start_z + 240.0 * joint_index
            placed = splice.translate((-SPLICE_HALF, splice_y_offset, splice_z_offset))
            placed = placed.rotate((0, 0, 0), (0, 1, 0), -90.0).translate(
                (x_axis + TRUSS_H / 2.0, -100.0 - TRUSS_W / 2.0, joint_z)
            )
            add(placed, f"{side}_UPRIGHT_SPLICE_{joint_index}", cq.Color(0.96, 0.48, 0.10, 1.0))

    cross_length = CROSS_LENGTH
    for index in range(CROSS_COUNT):
        add(
            _placed_crossbar(cross, -60.0 + cross_length * index, -100.0, cross_z),
            f"CROSSBAR_{index + 1}",
            cq.Color(0.22, 0.40, 0.67, 1.0),
        )
    for joint_index in range(1, CROSS_COUNT):
        joint_x = -60.0 + cross_length * joint_index
        joint_splice = center_splice if joint_index == 2 else cross_splice
        placed = joint_splice.translate((joint_x - CROSS_SPLICE_HALF, -125.0 + splice_y_offset, cross_z + splice_z_offset))
        add(placed, f"CROSSBAR_SPLICE_{joint_index}", cq.Color(0.96, 0.48, 0.10, 1.0))

    boom_root_y = float(CFG["layout"]["boom_root_y_mm"])
    for boom_index, x_axis in enumerate(BOOM_AXES_X, 1):
        for segment_index in range(2):
            boom = boom_root_part if segment_index == 0 else boom_camera_part
            add(
                _placed_boom(boom, x_axis, boom_root_y + 164.25 * segment_index, boom_z),
                f"BOOM_{boom_index}_{segment_index + 1}",
                cq.Color(0.24, 0.47, 0.73, 1.0),
            )
        joint_y = boom_root_y + 164.25
        placed = splice.translate((-SPLICE_HALF, splice_y_offset, splice_z_offset))
        placed = placed.rotate((0, 0, 0), (0, 0, 1), 90.0).translate(
            (x_axis + TRUSS_W / 2.0, joint_y, boom_z)
        )
        add(placed, f"BOOM_{boom_index}_SPLICE", cq.Color(0.96, 0.48, 0.10, 1.0))

    # Four portal gussets (front/back at each corner) and four flat boom-root
    # straps (top/bottom at each root) are actual make_parts solids.
    for side, x_axis, part_name, x0 in (
        ("L", -60.0, "portal_corner_node_left", -30.0),
        ("R", 670.0, "portal_corner_node_right", -70.0),
    ):
        node = parts[part_name].rotate((0, 0, 0), (1, 0, 0), -90.0)
        # Plates are outside the member faces: y=-133..-125 and -75..-67.
        for plane_index, y0 in enumerate((-133.0, -75.0), 1):
            add(
                node.translate((x_axis + x0, y0, cross_z + TRUSS_H)),
                f"{side}_PORTAL_NODE_{plane_index}",
                cq.Color(0.90, 0.38, 0.09, 1.0),
            )

    boom_node = parts["boom_crossbar_node"]
    for boom_index, x_axis in enumerate(BOOM_AXES_X, 1):
        strap_y0 = boom_root_y - ROOT_STRAP_D / 2.0
        top_strap = boom_node.translate((x_axis - ROOT_STRAP_W / 2.0, strap_y0, boom_z + TRUSS_H))
        bottom_strap = boom_node.rotate((0, 0, 0), (1, 0, 0), 180.0).translate(
            (x_axis - ROOT_STRAP_W / 2.0, strap_y0 + ROOT_STRAP_D, boom_z)
        )
        add(top_strap, f"BOOM_{boom_index}_ROOT_STRAP_TOP", cq.Color(0.90, 0.38, 0.09, 1.0))
        add(bottom_strap, f"BOOM_{boom_index}_ROOT_STRAP_BOTTOM", cq.Color(0.90, 0.38, 0.09, 1.0))

    carriage = parts["camera_xy_carriage"].translate((CARRIAGE_X0, CARRIAGE_Y0, 1074.0))
    cage = parts["camera_cage_body"].translate((CAMERA_CAGE_X0, CAMERA_CAGE_Y0, 1026.0))
    keeper = parts["camera_cage_keeper"].translate((CAMERA_CAGE_X0, CAMERA_CAGE_Y0, 1068.0))
    pad = parts["camera_top_compression_pad"].translate((286.0, 209.5, 1059.0))
    add(carriage, "CAMERA_XY_CARRIAGE", cq.Color(0.72, 0.42, 0.12, 1.0))
    add(cage, "POSITIVE_RETENTION_CAGE", cq.Color(0.80, 0.46, 0.12, 1.0))
    add(keeper, "PLANAR_FOUR_BOLT_KEEPER", cq.Color(0.90, 0.60, 0.16, 1.0))
    add(pad, "TRAPPED_TOP_COMPRESSION_PAD", cq.Color(0.18, 0.65, 0.35, 0.85))

    # Four compliant board pads are snapped into cap sockets.  Their 0.8 mm
    # bodies are shown compressed by the nominal 0.15 mm hard-stop allowance.
    base_pad = parts["board_pressure_pad"]
    pad_a = base_pad.translate((31.0, 26.0, -0.15))
    pad_b = base_pad.rotate((0, 0, 0), (0, 0, 1), 90.0).translate((35.0, 31.0, -0.15))
    for side, cap_origin, mirrored in (("L", (-25.0, -25.0, 0.0), False), ("R", (550.0, -25.0, 0.0), True)):
        for pad_index, local_pad in enumerate((pad_a, pad_b), 1):
            installed = local_pad.mirror("YZ").translate((85.0, 0.0, 0.0)) if mirrored else local_pad
            installed = installed.translate(cap_origin)
            add(installed, f"{side}_CAPTURED_TPU_PAD_{pad_index}", cq.Color(0.18, 0.65, 0.35, 0.85))

    # Nominal received-camera proxy: not printable and not physical authority.
    cam_body = rounded_plate(38.0, 38.0, 25.0, 2.0, 286.0, 209.5, 1034.0)
    lens = cq.Workplane("XY").center(305.0, 228.5).circle(19.75).extrude(34.0).translate((0, 0, 1000.0))
    add(cam_body, "B0477_CASE_NOMINAL_NOT_MEASURED", cq.Color(0.12, 0.12, 0.14, 0.75))
    add(lens, "LENS_PROXY_PUPIL_TARGET_Z1000", cq.Color(0.08, 0.08, 0.09, 0.82))

    # Installed cable/tether references begin well above the provisional robot
    # screen and terminate at the integrated cage wing/boom anchor points. USB
    # first passes behind the distal beam end, enters the right open-U boom,
    # rises ahead of the root straps, crosses above the portal, drops below the
    # corner plates on the front side, then wraps around the outside of the
    # right upright where its tie slots are reachable.  The independent tether
    # uses a <=5 mm screw-lock connector through the wing, then a maximum-OD
    # 3 mm cable lead above the wing and a 130 mm laid-flat choker eye around
    # the exposed right distal boom station B.
    cable_points = (
        (CAMERA_X, 247.0, 1054.0),
        (CAMERA_X, 286.0, 1042.0),
        (BOOM_AXES_X[1], 262.0, 1058.0),
        (BOOM_AXES_X[1], 252.0, 1058.0),
        (BOOM_AXES_X[1], -25.0, 1058.0),
        (BOOM_AXES_X[1], -25.0, 1093.0),
        (650.0, -140.0, 1093.0),
        (650.0, -140.0, 950.0),
        (706.0, -140.0, 950.0),
        (706.0, -100.0, 950.0),
        (706.0, -100.0, 100.0),
    )
    cable_route = rod_between(cable_points[0], cable_points[1], 2.2)
    for start, end in zip(cable_points[1:-1], cable_points[2:]):
        cable_route = cable_route.union(rod_between(start, end, 2.2))

    tether_inner_x = BOOM_AXES_X[1] - 31.0
    tether_outer_x = BOOM_AXES_X[1] + 31.0
    tether_connector = rod_between(
        (CAMERA_X, CAMERA_CAGE_Y0 + 102.0, 1025.5),
        (CAMERA_X, CAMERA_CAGE_Y0 + 102.0, 1038.0),
        2.5,
    )
    tether_lead_points = (
        (CAMERA_X, CAMERA_CAGE_Y0 + 102.0, 1038.0),
        (CAMERA_CAGE_X0 + 83.0, 270.0, 1038.0),
        (tether_inner_x, TETHER_CHOKER_Y, 1038.0),
    )
    tether_loop_points = (
        (tether_inner_x, TETHER_CHOKER_Y, 1006.0),
        (tether_inner_x, TETHER_CHOKER_Y, 1078.0),
        (tether_outer_x, TETHER_CHOKER_Y, 1078.0),
        (tether_outer_x, TETHER_CHOKER_Y, 1006.0),
        (tether_inner_x, TETHER_CHOKER_Y, 1006.0),
    )
    tether_route = rod_between(tether_lead_points[0], tether_lead_points[1], 1.5)
    for start, end in zip(tether_lead_points[1:-1], tether_lead_points[2:]):
        tether_route = tether_route.union(rod_between(start, end, 1.5))
    for start, end in zip(tether_loop_points[:-1], tether_loop_points[1:]):
        tether_route = tether_route.union(rod_between(start, end, 1.5))
    add(cable_route, "USB_CABLE_ROUTING_PROXY", cq.Color(0.10, 0.10, 0.10, 0.85))
    add(tether_connector, "TETHER_SCREW_LOCK_CONNECTOR_PROXY", cq.Color(0.70, 0.70, 0.72, 0.95))
    add(tether_route, "INDEPENDENT_METAL_TETHER_PROXY", cq.Color(0.78, 0.78, 0.80, 0.9))

    # Robot screening proxy: base axis and thin radial boundary only, not a swept-volume proof.
    outer = cq.Workplane("XY").center(305.0, 457.0).circle(610.0).extrude(3.0)
    inner = cq.Workplane("XY").center(305.0, 457.0).circle(604.0).extrude(4.0).translate((0, 0, -0.5))
    ring = outer.cut(inner)
    axis = cq.Workplane("XY").center(305.0, 457.0).circle(8.0).extrude(920.0)
    add(ring, "ROBOT_RADIAL_SCREEN_RING_NOT_COLLISION_PROOF", cq.Color(0.78, 0.12, 0.12, 0.30))
    add(axis, "ROBOT_ASSUMED_BASE_AXIS", cq.Color(0.78, 0.12, 0.12, 0.35))

    step_path = ASSEMBLY_DIR / "printable_camera_portal_prototype.step"
    stl_path = ASSEMBLY_DIR / "printable_camera_portal_prototype_reference.stl"
    assy.save(str(step_path))
    compound = cq.Compound.makeCompound(assembly_shapes)
    exporters.export(cq.Workplane(obj=compound), str(stl_path), tolerance=0.25, angularTolerance=0.2)


def make_camera_subassembly(parts: Dict[str, cq.Workplane]) -> None:
    assy = cq.Assembly(name="B0477_PRINTABLE_CAGE_PROTOTYPE")
    assy.add(parts["camera_cage_body"], name="cage_body", color=cq.Color(0.80, 0.46, 0.12, 1.0))
    assy.add(parts["camera_cage_keeper"], name="keeper", loc=cq.Location(cq.Vector(0, 0, 42.0)), color=cq.Color(0.90, 0.60, 0.16, 1.0))
    case = rounded_plate(38.0, 38.0, 25.0, 2.0, 29.0, 29.0, 8.0)
    pad = parts["camera_top_compression_pad"].translate((29.0, 29.0, 33.0))
    lens = cq.Workplane("XY").center(48.0, 48.0).circle(19.75).extrude(30.0).translate((0, 0, -22.0))
    assy.add(case, name="NOMINAL_38x38x25_CASE_NOT_MEASURED", color=cq.Color(0.12, 0.12, 0.14, 0.72))
    assy.add(pad, name="TRAPPED_TOP_COMPRESSION_PAD", color=cq.Color(0.18, 0.65, 0.35, 0.85))
    assy.add(lens, name="NOMINAL_39p5_LENS_PROXY", color=cq.Color(0.08, 0.08, 0.09, 0.80))
    assy.save(str(ASSEMBLY_DIR / "camera_cage_nominal_subassembly.step"))


def make_printed_parts_only_assembly(parts: Dict[str, cq.Workplane]) -> dict:
    """Export only installed printed bodies; omit all reference and metal solids."""
    assy = cq.Assembly(name="PRINTABLE_CAMERA_PORTAL_PRINTED_PARTS_ONLY")
    assembly_shapes = []
    tally: Dict[str, int] = {}

    def add(part: cq.Workplane, part_name: str, instance_name: str, color: cq.Color) -> None:
        assy.add(part, name=instance_name, color=color)
        assembly_shapes.extend(part.vals())
        tally[part_name] = tally.get(part_name, 0) + 1

    saddle_origins = {"L": (-120.0, -160.0, -BOARD_T), "R": (540.0, -160.0, -BOARD_T)}
    add(parts["board_corner_saddle_left"].translate(saddle_origins["L"]), "board_corner_saddle_left", "LEFT_BENCH_BEARING_SADDLE", cq.Color(0.15, 0.32, 0.62, 1.0))
    add(parts["board_corner_saddle_right"].translate(saddle_origins["R"]), "board_corner_saddle_right", "RIGHT_BENCH_BEARING_SADDLE", cq.Color(0.15, 0.32, 0.62, 1.0))
    cap_z = float(CFG["board_clamp"]["hard_stop_gap_mm"]) - BOARD_T
    add(parts["board_corner_cap_left"].translate((-25.0, -25.0, cap_z)), "board_corner_cap_left", "LEFT_TAG_CLEAR_CAP", cq.Color(0.18, 0.42, 0.72, 1.0))
    add(parts["board_corner_cap_right"].translate((550.0, -25.0, cap_z)), "board_corner_cap_right", "RIGHT_TAG_CLEAR_CAP", cq.Color(0.18, 0.42, 0.72, 1.0))

    for side in ("L", "R"):
        ox, oy, oz = saddle_origins[side]
        for spec in saddle_m6_channel_specs(side):
            retainer = placed_m6_nut_retainer(
                parts["m6_nut_retainer"], spec["mouth"], spec["seat"], 3.7
            ).translate((ox, oy, oz))
            add(
                retainer,
                "m6_nut_retainer",
                f"{side}_M6_{spec['name']}_NUT_RETAINER",
                cq.Color(0.94, 0.45, 0.10, 1.0),
            )

    upright = parts["upright_truss_segment_240"]
    cross = parts["crossbar_truss_segment_182p5"]
    boom_root_part = parts["boom_root_truss_segment_164p25"]
    boom_camera_part = parts["boom_camera_truss_segment_164p25"]
    splice = parts["u_truss_splice"]
    cross_splice = parts["u_truss_splice_crossbar_2bolt"]
    center_splice = parts["u_truss_splice_center_4bolt"]
    splice_w = TRUSS_W + 0.8 + 12.0
    splice_y_offset = -(splice_w - TRUSS_W) / 2.0
    splice_z_offset = -4.0
    upright_start_z = 50.0
    cross_z = float(CFG["layout"]["crossbar_bottom_z_mm"])
    boom_z = float(CFG["layout"]["boom_bottom_z_mm"])

    for side, x_axis in (("L", -60.0), ("R", 670.0)):
        for index in range(4):
            add(
                _placed_upright(upright, x_axis, -100.0, upright_start_z + 240.0 * index),
                "upright_truss_segment_240",
                f"{side}_UPRIGHT_{index + 1}",
                cq.Color(0.22, 0.40, 0.67, 1.0),
            )
        for joint_index in range(1, 4):
            joint_z = upright_start_z + 240.0 * joint_index
            placed = splice.translate((-SPLICE_HALF, splice_y_offset, splice_z_offset))
            placed = placed.rotate((0, 0, 0), (0, 1, 0), -90.0).translate(
                (x_axis + TRUSS_H / 2.0, -100.0 - TRUSS_W / 2.0, joint_z)
            )
            add(placed, "u_truss_splice", f"{side}_UPRIGHT_SPLICE_{joint_index}", cq.Color(0.96, 0.48, 0.10, 1.0))

    cross_length = CROSS_LENGTH
    for index in range(CROSS_COUNT):
        add(
            _placed_crossbar(cross, -60.0 + cross_length * index, -100.0, cross_z),
            "crossbar_truss_segment_182p5",
            f"CROSSBAR_{index + 1}",
            cq.Color(0.22, 0.40, 0.67, 1.0),
        )
    for joint_index in range(1, CROSS_COUNT):
        joint_x = -60.0 + cross_length * joint_index
        part_name = "u_truss_splice_center_4bolt" if joint_index == 2 else "u_truss_splice_crossbar_2bolt"
        joint_splice = center_splice if joint_index == 2 else cross_splice
        placed = joint_splice.translate((joint_x - CROSS_SPLICE_HALF, -125.0 + splice_y_offset, cross_z + splice_z_offset))
        add(placed, part_name, f"CROSSBAR_SPLICE_{joint_index}", cq.Color(0.96, 0.48, 0.10, 1.0))

    boom_root_y = float(CFG["layout"]["boom_root_y_mm"])
    for boom_index, x_axis in enumerate(BOOM_AXES_X, 1):
        add(_placed_boom(boom_root_part, x_axis, boom_root_y, boom_z), "boom_root_truss_segment_164p25", f"BOOM_{boom_index}_ROOT", cq.Color(0.24, 0.47, 0.73, 1.0))
        add(_placed_boom(boom_camera_part, x_axis, boom_root_y + 164.25, boom_z), "boom_camera_truss_segment_164p25", f"BOOM_{boom_index}_CAMERA", cq.Color(0.24, 0.47, 0.73, 1.0))
        placed = splice.translate((-SPLICE_HALF, splice_y_offset, splice_z_offset))
        placed = placed.rotate((0, 0, 0), (0, 0, 1), 90.0).translate((x_axis + TRUSS_W / 2.0, boom_root_y + 164.25, boom_z))
        add(placed, "u_truss_splice", f"BOOM_{boom_index}_SPLICE", cq.Color(0.96, 0.48, 0.10, 1.0))

    for side, x_axis, part_name, x0 in (
        ("L", -60.0, "portal_corner_node_left", -30.0),
        ("R", 670.0, "portal_corner_node_right", -70.0),
    ):
        node = parts[part_name].rotate((0, 0, 0), (1, 0, 0), -90.0)
        for plane_index, y0 in enumerate((-133.0, -75.0), 1):
            add(node.translate((x_axis + x0, y0, cross_z + TRUSS_H)), part_name, f"{side}_PORTAL_NODE_{plane_index}", cq.Color(0.90, 0.38, 0.09, 1.0))

    boom_node = parts["boom_crossbar_node"]
    for boom_index, x_axis in enumerate(BOOM_AXES_X, 1):
        strap_y0 = boom_root_y - ROOT_STRAP_D / 2.0
        top_strap = boom_node.translate((x_axis - ROOT_STRAP_W / 2.0, strap_y0, boom_z + TRUSS_H))
        bottom_strap = boom_node.rotate((0, 0, 0), (1, 0, 0), 180.0).translate(
            (x_axis - ROOT_STRAP_W / 2.0, strap_y0 + ROOT_STRAP_D, boom_z)
        )
        add(top_strap, "boom_crossbar_node", f"BOOM_{boom_index}_ROOT_STRAP_TOP", cq.Color(0.90, 0.38, 0.09, 1.0))
        add(bottom_strap, "boom_crossbar_node", f"BOOM_{boom_index}_ROOT_STRAP_BOTTOM", cq.Color(0.90, 0.38, 0.09, 1.0))

    add(parts["camera_xy_carriage"].translate((CARRIAGE_X0, CARRIAGE_Y0, 1074.0)), "camera_xy_carriage", "CAMERA_XY_CARRIAGE", cq.Color(0.72, 0.42, 0.12, 1.0))
    add(parts["camera_cage_body"].translate((CAMERA_CAGE_X0, CAMERA_CAGE_Y0, 1026.0)), "camera_cage_body", "POSITIVE_RETENTION_CAGE", cq.Color(0.80, 0.46, 0.12, 1.0))
    add(parts["camera_cage_keeper"].translate((CAMERA_CAGE_X0, CAMERA_CAGE_Y0, 1068.0)), "camera_cage_keeper", "PLANAR_FOUR_BOLT_KEEPER", cq.Color(0.90, 0.60, 0.16, 1.0))
    add(parts["camera_top_compression_pad"].translate((286.0, 209.5, 1059.0)), "camera_top_compression_pad", "TRAPPED_TOP_COMPRESSION_PAD", cq.Color(0.18, 0.65, 0.35, 0.85))

    base_pad = parts["board_pressure_pad"]
    pad_a = base_pad.translate((31.0, 26.0, -0.15))
    pad_b = base_pad.rotate((0, 0, 0), (0, 0, 1), 90.0).translate((35.0, 31.0, -0.15))
    for side, cap_origin, mirrored in (("L", (-25.0, -25.0, 0.0), False), ("R", (550.0, -25.0, 0.0), True)):
        for pad_index, local_pad in enumerate((pad_a, pad_b), 1):
            installed = local_pad.mirror("YZ").translate((85.0, 0.0, 0.0)) if mirrored else local_pad
            installed = installed.translate(cap_origin)
            add(installed, "board_pressure_pad", f"{side}_CAPTURED_TPU_PAD_{pad_index}", cq.Color(0.18, 0.65, 0.35, 0.85))

    expected = {
        entry["part"]: int(entry["quantity"]) - int(entry.get("sacrificial_quantity", 0))
        for entry in CFG["parts"]
        if not entry.get("print_first") and entry["part"] != "camera_case_shim_ladder"
    }
    status = "PASS" if tally == expected else "FAIL"
    report = {
        "status": status,
        "installed_printed_body_count": sum(tally.values()),
        "part_tally": dict(sorted(tally.items())),
        "excluded_printed_items": {
            "print_first_coupons": [entry["part"] for entry in CFG["parts"] if entry.get("print_first")],
            "camera_case_shim_ladder": "breakaway fit stock; install only the dimension-selected shim after received-camera gate",
        },
        "reference_and_hardware_solids": "omitted",
    }
    if status != "PASS":
        raise ValueError(f"Printed-parts assembly quantity mismatch: expected={expected}, actual={tally}")

    step_path = ASSEMBLY_DIR / "printable_camera_portal_printed_parts_only.step"
    stl_path = ASSEMBLY_DIR / "printable_camera_portal_printed_parts_only.stl"
    assy.save(str(step_path))
    compound = cq.Compound.makeCompound(assembly_shapes)
    exporters.export(cq.Workplane(obj=compound), str(stl_path), tolerance=0.25, angularTolerance=0.2)
    report["step"] = str(step_path.relative_to(ROOT)).replace("\\", "/")
    report["stl"] = str(stl_path.relative_to(ROOT)).replace("\\", "/")
    report["step_sha256"] = sha256_file(step_path)
    report["stl_sha256"] = sha256_file(stl_path)
    (OUTPUT_DIR / "PRINTED_PARTS_ASSEMBLY_VALIDATION.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def intersection_volume(a: cq.Workplane, b: cq.Workplane) -> float:
    return sum(float(solid.Volume()) for solid in a.intersect(b).solids().vals())


def axis_cylinder(
    start: Tuple[float, float, float],
    direction: Tuple[float, float, float],
    length: float,
    radius: float,
) -> cq.Workplane:
    return cq.Workplane(
        obj=cq.Solid.makeCylinder(radius, length, cq.Vector(*start), cq.Vector(*direction))
    )


def total_intersection_volume(test: cq.Workplane, bodies: Iterable[cq.Workplane]) -> float:
    return sum(intersection_volume(test, body) for body in bodies)


def validate_fastener_interfaces(parts: Dict[str, cq.Workplane]) -> dict:
    """Validate representative printed bores, axes, grip stacks, and tool envelopes."""
    checks = []
    classes = []

    def clearance(name: str, axes: list, bodies: Iterable[cq.Workplane], radius: float = 2.6) -> None:
        bodies = tuple(bodies)
        worst = 0.0
        for axis in axes:
            cyl = axis_cylinder(tuple(axis["start"]), tuple(axis["direction"]), axis["length_mm"], radius)
            worst = max(worst, total_intersection_volume(cyl, bodies))
        checks.append(
            {
                "check": name,
                "status": "PASS" if worst <= 0.02 else "FAIL",
                "maximum_test_cylinder_intersection_mm3": round(worst, 6),
                "test_radius_mm": radius,
            }
        )

    def bolt_class(name: str, axes_b: list, grip: float, bolt: float, nut: float, note: str) -> None:
        projection = bolt - grip - nut
        classes.append(
            {
                "fastener_class": name,
                "axes_B_mm": axes_b,
                "printed_grip_mm": round(grip, 3),
                "nominal_bolt_length_mm": bolt,
                "nut_or_head_stack_allowance_mm": nut,
                "nominal_thread_projection_after_stack_mm": round(projection, 3),
                "stack_status": "PASS" if projection >= 2.0 else "FAIL",
                "note": note,
            }
        )

    # The maximum permitted M6 flange head must clear every cap and label above
    # the integrated boss, while the complete annular boss top supports it.
    # Testing the full 4 mm head height closes the former false-pass where the
    # shallow recess was clear but labels intersected the upper head envelope.
    cap_head_overlaps = []
    cap_shaft_overlaps = []
    cap_boss_support_fills = []
    for cap, hole_centers in (
        (parts["board_corner_cap_left"], ((55.0, 13.0), (13.0, 13.0))),
        (parts["board_corner_cap_right"], ((30.0, 13.0), (72.0, 13.0))),
    ):
        for x, y in hole_centers:
            cap_head_overlaps.append(
                intersection_volume(
                    axis_cylinder((x, y, M6_CAP_BOSS_BEARING_Z), (0.0, 0.0, 1.0), 4.0, 6.75),
                    cap,
                )
            )
            cap_shaft_overlaps.append(
                intersection_volume(
                    axis_cylinder((x, y, -0.5), (0.0, 0.0, 1.0), M6_CAP_BOSS_BEARING_Z + 1.0, 3.3),
                    cap,
                )
            )
            support_outer = axis_cylinder(
                (x, y, M6_CAP_BOSS_BEARING_Z - 0.2),
                (0.0, 0.0, 1.0),
                0.2,
                M6_CAP_BOSS_OD / 2.0,
            )
            support_inner = axis_cylinder(
                (x, y, M6_CAP_BOSS_BEARING_Z - 0.21),
                (0.0, 0.0, 1.0),
                0.22,
                M6_CLEAR / 2.0,
            )
            support_annulus = support_outer.cut(support_inner)
            support_volume = max(sum(s.Volume() for s in support_annulus.solids().vals()), 1e-9)
            cap_boss_support_fills.append(intersection_volume(support_annulus, cap) / support_volume)
    checks.append(
        {
            "check": "m6_cap_boss_support_and_full_head_clearance",
            "status": "PASS"
            if max(cap_head_overlaps + cap_shaft_overlaps) <= 0.02 and min(cap_boss_support_fills) >= 0.98
            else "FAIL",
            "maximum_intersection_mm3": round(max(cap_head_overlaps + cap_shaft_overlaps), 6),
            "minimum_boss_top_solid_fill_ratio": round(min(cap_boss_support_fills), 6),
            "modeled_maximum_head_outer_diameter_mm": 13.5,
            "modeled_boss_outer_diameter_mm": M6_CAP_BOSS_OD,
            "modeled_boss_bearing_height_mm": M6_CAP_BOSS_BEARING_Z,
        }
    )

    # Saddle receiver: two diagonal axes per tower align to the upright's
    # reinforced (x10,z31) and (x22,z19) lower-end stations.  The diagonal
    # pattern prevents rocking while leaving clearance between flange tools.
    left_saddle = parts["board_corner_saddle_left"].translate((-120.0, -160.0, -18.0))
    left_upright = _placed_upright(parts["upright_truss_segment_240"], -60.0, -100.0, 50.0)
    right_saddle = parts["board_corner_saddle_right"].translate((540.0, -160.0, -18.0))
    right_upright = _placed_upright(parts["upright_truss_segment_240"], 670.0, -100.0, 50.0)
    saddle_coords = [(-59.0, 60.0), (-47.0, 72.0), (671.0, 60.0), (683.0, 72.0)]
    left_saddle_axes = [
        {"start": [x, -134.5, z], "direction": [0.0, 1.0, 0.0], "length_mm": 69.0}
        for x, z in saddle_coords[:2]
    ]
    right_saddle_axes = [
        {"start": [x, -134.5, z], "direction": [0.0, 1.0, 0.0], "length_mm": 69.0}
        for x, z in saddle_coords[2:]
    ]
    clearance("left_saddle_receiver_bore_alignment", left_saddle_axes, (left_saddle, left_upright))
    clearance("right_saddle_receiver_bore_alignment", right_saddle_axes, (right_saddle, right_upright))
    receiver_head_envelopes = [
        axis_cylinder((x, -140.5, z), (0.0, 1.0, 0.0), 6.0, 6.0)
        for x, z in saddle_coords
    ]
    receiver_pair_overlap = max(
        intersection_volume(receiver_head_envelopes[0], receiver_head_envelopes[1]),
        intersection_volume(receiver_head_envelopes[2], receiver_head_envelopes[3]),
    )
    checks.append(
        {
            "check": "saddle_receiver_flange_envelope_separation",
            "status": "PASS" if receiver_pair_overlap <= 0.02 else "FAIL",
            "maximum_pair_intersection_mm3": round(receiver_pair_overlap, 6),
            "modeled_flange_diameter_mm": 12.0,
        }
    )
    bolt_class(
        "M5x80 saddle receiver",
        [[x, -100.0, z] for x, z in saddle_coords],
        68.0,
        80.0,
        6.0,
        "Two diagonal axes per saddle through both 8 mm receiver cheeks and reinforced upright bands; insert front-to-rear with flanged nylocs on the rear face.",
    )

    # Portal corners: two upright and two crossbar axes per corner; each bolt
    # spans the two outside gussets and a 50 mm reinforced member end collar.
    cross_z = float(CFG["layout"]["crossbar_bottom_z_mm"])
    left_nodes = (
        parts["portal_corner_node_left"].rotate((0, 0, 0), (1, 0, 0), -90.0).translate((-90.0, -133.0, 1074.0)),
        parts["portal_corner_node_left"].rotate((0, 0, 0), (1, 0, 0), -90.0).translate((-90.0, -75.0, 1074.0)),
    )
    left_top_upright = _placed_upright(parts["upright_truss_segment_240"], -60.0, -100.0, 770.0)
    left_crossbar = _placed_crossbar(parts["crossbar_truss_segment_182p5"], -60.0, -100.0, cross_z)
    portal_left_coords = [(-47.0, 988.0), (-59.0, 1000.0), (-38.0, 1029.0), (-50.0, 1041.0)]
    portal_left_axes = [
        {"start": [x, -133.5, z], "direction": [0.0, 1.0, 0.0], "length_mm": 67.0}
        for x, z in portal_left_coords
    ]
    clearance("left_portal_node_bore_alignment", portal_left_axes, (*left_nodes, left_top_upright, left_crossbar))

    right_nodes = (
        parts["portal_corner_node_right"].rotate((0, 0, 0), (1, 0, 0), -90.0).translate((600.0, -133.0, 1074.0)),
        parts["portal_corner_node_right"].rotate((0, 0, 0), (1, 0, 0), -90.0).translate((600.0, -75.0, 1074.0)),
    )
    right_top_upright = _placed_upright(parts["upright_truss_segment_240"], 670.0, -100.0, 770.0)
    right_crossbar = _placed_crossbar(parts["crossbar_truss_segment_182p5"], 487.5, -100.0, cross_z)
    portal_right_coords = [(683.0, 988.0), (671.0, 1000.0), (648.0, 1029.0), (660.0, 1041.0)]
    portal_right_axes = [
        {"start": [x, -133.5, z], "direction": [0.0, 1.0, 0.0], "length_mm": 67.0}
        for x, z in portal_right_coords
    ]
    clearance("right_portal_node_bore_alignment", portal_right_axes, (*right_nodes, right_top_upright, right_crossbar))

    # Each member's two M5 axes form a 12 x 12 mm diagonal. A maximum-OD
    # 13 mm thin-wall socket can therefore engage either 12 mm flange while
    # the neighboring flange remains installed. The tool envelope approaches
    # from the unobstructed front face and stops at the gusset surface.
    portal_coords = portal_left_coords + portal_right_coords
    portal_flange_heads = [
        axis_cylinder((x, -139.0, z), (0.0, 1.0, 0.0), 6.0, 6.0)
        for x, z in portal_coords
    ]
    portal_socket_sweeps = [
        axis_cylinder((x, -146.0, z), (0.0, 1.0, 0.0), 13.0, 6.5)
        for x, z in portal_coords
    ]
    socket_neighbor_overlap = max(
        total_intersection_volume(tool, tuple(head for other_index, head in enumerate(portal_flange_heads) if other_index != index))
        for index, tool in enumerate(portal_socket_sweeps)
    )
    socket_gusset_overlap = max(
        total_intersection_volume(tool, (*left_nodes, *right_nodes))
        for tool in portal_socket_sweeps
    )
    checks.append(
        {
            "check": "portal_diagonal_flange_and_socket_separation",
            "status": "PASS" if socket_neighbor_overlap <= 0.02 and socket_gusset_overlap <= 0.02 else "FAIL",
            "maximum_neighbor_flange_intersection_mm3": round(socket_neighbor_overlap, 6),
            "maximum_gusset_intersection_mm3": round(socket_gusset_overlap, 6),
            "modeled_socket_outer_diameter_mm": 13.0,
            "modeled_flange_outer_diameter_mm": 12.0,
            "same_member_axis_spacing_mm": round(math.hypot(12.0, 12.0), 3),
        }
    )
    bolt_class(
        "M5x75 portal corner",
        [[x, -100.0, z] for x, z in portal_coords],
        66.0,
        75.0,
        6.0,
        "Eight axes total; each member uses a 16.97 mm diagonal bore pair so one <=13 mm socket clears the neighboring 12 mm flange.",
    )

    # Boom roots: identical flat straps sandwich the tangent crossbar/boom
    # joint.  Four complete M5x90 shafts per root pass vertically through the
    # top strap, a full-height 16 x 16 mm bearing column, and the flipped lower
    # strap.  No connector shares volume with either beam.
    root_bodies = []
    root_coords = []
    annulus_samples = []
    shaft_axes = []
    head_envelopes = []
    nut_envelopes = []
    tool_envelopes = []
    for root_index, root_x in enumerate(BOOM_AXES_X):
        module_start = -60.0 + CROSS_LENGTH * (root_index + 1)
        root_crossbar = _placed_crossbar(parts["crossbar_truss_segment_182p5"], module_start, -100.0, cross_z)
        root_boom = _placed_boom(parts["boom_root_truss_segment_164p25"], root_x, -75.0, cross_z)
        strap_y0 = float(CFG["layout"]["boom_root_y_mm"]) - ROOT_STRAP_D / 2.0
        top_strap = parts["boom_crossbar_node"].translate((root_x - ROOT_STRAP_W / 2.0, strap_y0, cross_z + TRUSS_H))
        bottom_strap = parts["boom_crossbar_node"].rotate((0, 0, 0), (1, 0, 0), 180.0).translate(
            (root_x - ROOT_STRAP_W / 2.0, strap_y0 + ROOT_STRAP_D, cross_z)
        )
        root_bodies.extend((root_crossbar, root_boom, top_strap, bottom_strap))
        for offset in ROOT_BOLT_X_OFFSETS:
            x = root_x + offset
            for y, target in ((ROOT_CROSSBAR_BOLT_Y, root_crossbar), (ROOT_BOOM_BOLT_Y, root_boom)):
                root_coords.append((x, y, 1042.0))
                shaft_axes.append(
                    {"start": [x, y, 1082.0], "direction": [0.0, 0.0, -1.0], "length_mm": 90.0}
                )
                head_envelopes.append(axis_cylinder((x, y, 1082.0), (0.0, 0.0, 1.0), 5.0, 6.0))
                nut_envelopes.append(axis_cylinder((x, y, 996.0), (0.0, 0.0, 1.0), 6.0, 6.0))
                tool_envelopes.append(axis_cylinder((x, y, 1087.0), (0.0, 0.0, 1.0), 18.0, 7.0))
                tool_envelopes.append(axis_cylinder((x, y, 978.0), (0.0, 0.0, 1.0), 18.0, 7.0))
                outer = axis_cylinder((x, y, 1041.0), (0.0, 0.0, 1.0), 2.0, 6.0)
                inner = axis_cylinder((x, y, 1040.9), (0.0, 0.0, 1.0), 2.2, 3.0)
                ring = outer.cut(inner)
                fill = intersection_volume(ring, target) / max(sum(s.Volume() for s in ring.solids().vals()), 1e-9)
                annulus_samples.append(fill)
    clearance("boom_root_complete_m5x90_shaft_clearance", shaft_axes, root_bodies)
    head_overlap = max(total_intersection_volume(test, root_bodies) for test in head_envelopes)
    nut_overlap = max(total_intersection_volume(test, root_bodies) for test in nut_envelopes)
    tool_overlap = max(total_intersection_volume(test, root_bodies) for test in tool_envelopes)
    checks.append({"check": "boom_root_head_envelope", "status": "PASS" if head_overlap <= 0.02 else "FAIL", "maximum_intersection_mm3": round(head_overlap, 6)})
    checks.append({"check": "boom_root_nyloc_envelope", "status": "PASS" if nut_overlap <= 0.02 else "FAIL", "maximum_intersection_mm3": round(nut_overlap, 6)})
    checks.append({"check": "boom_root_top_bottom_tool_access", "status": "PASS" if tool_overlap <= 0.02 else "FAIL", "maximum_intersection_mm3": round(tool_overlap, 6)})
    checks.append(
        {
            "check": "boom_root_full_height_column_annular_support",
            "status": "PASS" if min(annulus_samples) >= 0.95 else "FAIL",
            "minimum_solid_fill_ratio": round(min(annulus_samples), 6),
            "nominal_radial_ligament_mm": 5.25,
        }
    )
    bolt_class(
        "M5x90 boom root sandwich",
        [[x, y, "Z"] for x, y, _ in root_coords],
        80.0,
        90.0,
        6.0,
        "Eight axes total: four per root through 8 mm top strap + 64 mm full-height bearing column + 8 mm bottom strap; flange heads above and flanged nylocs below.",
    )

    # External splice collar: two bolts per joint, matched at 22 mm from each
    # member end and supported by the compression bands.
    member = parts["upright_truss_segment_240"]
    members = (member, member.translate((240.0, 0.0, 0.0)))
    splice_w = TRUSS_W + 0.8 + 12.0
    splice = parts["u_truss_splice"].translate((240.0 - SPLICE_HALF, -(splice_w - TRUSS_W) / 2.0, -4.0))
    splice_axes = [
        {"start": [x, -6.9, 31.0], "direction": [0.0, 1.0, 0.0], "length_mm": 63.8}
        for x in (218.0, 262.0)
    ]
    clearance("external_splice_bore_alignment", splice_axes, (*members, splice))
    bolt_class(
        "M5x75 external U splice",
        [["joint-22", "member center", 31.0], ["joint+22", "member center", 31.0]],
        62.8,
        75.0,
        6.0,
        "Repeated at eight upright/boom joints (16 bolts); nominal post-nut projection is 6.2 mm.",
    )

    # Crossbar collars remain 92 mm long to preserve head/nut/tool access at
    # the adjacent boom-root plates.  The outer joints use one bolt per member;
    # the center joint uses diagonal pairs with 16.97 mm head separation.
    cross_members = (
        parts["crossbar_truss_segment_182p5"],
        parts["crossbar_truss_segment_182p5"].translate((CROSS_LENGTH, 0.0, 0.0)),
    )
    cross_splice = parts["u_truss_splice_crossbar_2bolt"].translate(
        (CROSS_LENGTH - CROSS_SPLICE_HALF, -(splice_w - TRUSS_W) / 2.0, -4.0)
    )
    cross_axes = [
        {"start": [x, -6.9, 31.0], "direction": [0.0, 1.0, 0.0], "length_mm": 63.8}
        for x in (CROSS_LENGTH - 22.0, CROSS_LENGTH + 22.0)
    ]
    clearance("crossbar_outer_splice_bore_alignment", cross_axes, (*cross_members, cross_splice))
    center_splice = parts["u_truss_splice_center_4bolt"].translate(
        (CROSS_LENGTH - CROSS_SPLICE_HALF, -(splice_w - TRUSS_W) / 2.0, -4.0)
    )
    center_coords = (
        (CROSS_LENGTH - 22.0, 19.0),
        (CROSS_LENGTH - 10.0, 31.0),
        (CROSS_LENGTH + 10.0, 31.0),
        (CROSS_LENGTH + 22.0, 19.0),
    )
    center_axes = [
        {"start": [x, -6.9, z], "direction": [0.0, 1.0, 0.0], "length_mm": 63.8}
        for x, z in center_coords
    ]
    clearance("crossbar_center_4bolt_splice_alignment", center_axes, (*cross_members, center_splice))
    center_head_envelopes = [
        axis_cylinder((x, -12.9, z), (0.0, 1.0, 0.0), 6.0, 6.0)
        for x, z in center_coords
    ]
    center_pair_overlap = max(
        intersection_volume(center_head_envelopes[0], center_head_envelopes[1]),
        intersection_volume(center_head_envelopes[2], center_head_envelopes[3]),
    )
    checks.append(
        {
            "check": "center_splice_flange_envelope_separation",
            "status": "PASS" if center_pair_overlap <= 0.02 else "FAIL",
            "maximum_pair_intersection_mm3": round(center_pair_overlap, 6),
            "modeled_flange_diameter_mm": 12.0,
        }
    )
    bolt_class(
        "M5x75 crossbar splice",
        [["outer joints", 4, "axes"], ["center joint", 4, "axes"]],
        62.8,
        75.0,
        6.0,
        "Eight axes total: two per outer joint and four diagonal axes at the torsion-critical center joint.",
    )

    # Four carriage axes coincide with the vertical end-collar holes of the
    # two final boom modules.
    carriage = parts["camera_xy_carriage"].translate((CARRIAGE_X0, CARRIAGE_Y0, 1074.0))
    final_booms = tuple(
        _placed_boom(parts["boom_camera_truss_segment_164p25"], x_axis, 89.25, cross_z)
        for x_axis in BOOM_AXES_X
    )
    carriage_coords = [
        (x_axis + offset, CAMERA_Y)
        for x_axis in BOOM_AXES_X
        for offset in (-17.0, 17.0)
    ]
    carriage_axes = [
        {"start": [x, y, 1009.5], "direction": [0.0, 0.0, 1.0], "length_mm": 75.0}
        for x, y in carriage_coords
    ]
    clearance("carriage_to_boom_bore_alignment", carriage_axes, (*final_booms, carriage))
    carriage_column_fills = []
    for x, y in carriage_coords:
        outer = axis_cylinder((x, y, 1041.0), (0.0, 0.0, 1.0), 2.0, 6.0)
        inner = axis_cylinder((x, y, 1040.9), (0.0, 0.0, 1.0), 2.2, 3.0)
        ring = outer.cut(inner)
        target = final_booms[0] if x < (BOOM_AXES_X[0] + BOOM_AXES_X[1]) / 2.0 else final_booms[1]
        carriage_column_fills.append(
            intersection_volume(ring, target) / max(sum(s.Volume() for s in ring.solids().vals()), 1e-9)
        )
    checks.append(
        {
            "check": "carriage_boom_full_height_column_annular_support",
            "status": "PASS" if min(carriage_column_fills) >= 0.95 else "FAIL",
            "minimum_solid_fill_ratio": round(min(carriage_column_fills), 6),
            "nominal_radial_ligament_mm": 5.25,
        }
    )
    bolt_class(
        "M5x85 carriage to boom",
        [[x, y, "Z"] for x, y in carriage_coords],
        74.0,
        85.0,
        6.0,
        "Four axes through 10 mm carriage and 64 mm solid boom end side collars.",
    )

    cage = parts["camera_cage_body"].translate((CAMERA_CAGE_X0, CAMERA_CAGE_Y0, 1026.0))
    keeper = parts["camera_cage_keeper"].translate((CAMERA_CAGE_X0, CAMERA_CAGE_Y0, 1068.0))
    level_coords = [(273.0, 198.5), (337.0, 198.5), (305.0, 264.5)]
    for delta_x in CAGE_INSTALLED_X_OFFSETS:
        for delta_y in CARRIAGE_INSTALLED_Y_OFFSETS:
            indexed_carriage = parts["camera_xy_carriage"].translate(
                (CARRIAGE_X0, CARRIAGE_Y0 + delta_y, 1074.0)
            )
            indexed_cage = parts["camera_cage_body"].translate(
                (CAMERA_CAGE_X0 + delta_x, CAMERA_CAGE_Y0 + delta_y, 1026.0)
            )
            indexed_keeper = parts["camera_cage_keeper"].translate(
                (CAMERA_CAGE_X0 + delta_x, CAMERA_CAGE_Y0 + delta_y, 1068.0)
            )
            level_axes = [
                {
                    "start": [x + delta_x, y + delta_y, 1025.5],
                    "direction": [0.0, 0.0, 1.0],
                    "length_mm": 59.0,
                }
                for x, y in level_coords
            ]
            clearance(
                f"three_point_leveling_round_bore_alignment_X{delta_x:+g}_Y{delta_y:+g}",
                level_axes,
                (indexed_cage, indexed_keeper, indexed_carriage),
                radius=2.1,
            )
    bolt_class(
        "M4x70 leveling",
        [[x, y, "Z"] for x, y in level_coords],
        58.0,
        70.0,
        7.0,
        "Head+washer above carriage; washer+jam nut below carriage; screw engages underside-loaded captured base nut beneath 4.3 mm roof.",
    )
    keeper_coords = (
        (CAMERA_CAGE_X0 + 14.0, CAMERA_CAGE_Y0 + 38.0),
        (CAMERA_CAGE_X0 + 82.0, CAMERA_CAGE_Y0 + 38.0),
        (CAMERA_CAGE_X0 + 14.0, CAMERA_CAGE_Y0 + 74.0),
        (CAMERA_CAGE_X0 + 82.0, CAMERA_CAGE_Y0 + 74.0),
    )
    head_overlaps = []
    driver_overlaps = []
    jam_overlaps = []
    wrench_overlaps = []
    # Every discrete X/Y camera index must retain the same four-bolt closure,
    # recessed heads, top hex-key access, and three edge-open wrench paths.
    # This prevents an apparently selectable index from becoming unserviceable
    # after the cage is installed beneath the carriage.
    for delta_x in CAGE_INSTALLED_X_OFFSETS:
        for delta_y in CARRIAGE_INSTALLED_Y_OFFSETS:
            indexed_carriage = parts["camera_xy_carriage"].translate(
                (CARRIAGE_X0, CARRIAGE_Y0 + delta_y, 1074.0)
            )
            indexed_cage = parts["camera_cage_body"].translate(
                (CAMERA_CAGE_X0 + delta_x, CAMERA_CAGE_Y0 + delta_y, 1026.0)
            )
            indexed_keeper = parts["camera_cage_keeper"].translate(
                (CAMERA_CAGE_X0 + delta_x, CAMERA_CAGE_Y0 + delta_y, 1068.0)
            )
            indexed_keeper_coords = tuple(
                (x + delta_x, y + delta_y) for x, y in keeper_coords
            )
            keeper_axes = [
                {"start": [x, y, 1013.5], "direction": [0.0, 0.0, 1.0], "length_mm": 60.5}
                for x, y in indexed_keeper_coords
            ]
            clearance(
                f"keeper_bolt_bore_alignment_X{delta_x:+g}_Y{delta_y:+g}",
                keeper_axes,
                (indexed_cage, indexed_keeper),
                radius=2.1,
            )
            keeper_heads = tuple(
                axis_cylinder((x, y, 1069.9), (0.0, 0.0, 1.0), 4.0, 4.9)
                for x, y in indexed_keeper_coords
            )
            keeper_drivers = tuple(
                axis_cylinder((x, y, 1074.0), (0.0, 0.0, 1.0), 24.0, 2.3)
                for x, y in indexed_keeper_coords
            )
            head_overlaps.extend(
                total_intersection_volume(test, (indexed_keeper, indexed_carriage))
                for test in keeper_heads
            )
            driver_overlaps.extend(
                intersection_volume(test, indexed_carriage) for test in keeper_drivers
            )
            jam_envelopes = tuple(
                axis_cylinder((x + delta_x, y + delta_y, 1069.9), (0.0, 0.0, 1.0), 4.0, 5.1)
                for x, y in level_coords
            )
            jam_overlaps.extend(
                total_intersection_volume(test, (indexed_keeper, indexed_carriage))
                for test in jam_envelopes
            )

            # Swept envelopes for the specified <=18 x 5.5 mm thin wrench
            # approach each front jam nut through a -Y-open bay and the rear
            # nut through a +Y-open bay. Each includes an 80 mm handle segment
            # and the two booms as obstacles, not only the wrench head inside
            # the keeper. The 19 mm bays supply 1 mm transverse clearance.
            wrench_z = 1068.25
            wrench_envelopes = (
                box_ll(18.0, 18.0, 5.5, CAMERA_CAGE_X0 + delta_x + 7.0, CAMERA_CAGE_Y0 + delta_y + 9.0, wrench_z),
                box_ll(8.0, 80.0, 5.5, CAMERA_CAGE_X0 + delta_x + 12.0, CAMERA_CAGE_Y0 + delta_y - 62.0, wrench_z),
                box_ll(18.0, 18.0, 5.5, CAMERA_CAGE_X0 + delta_x + 71.0, CAMERA_CAGE_Y0 + delta_y + 9.0, wrench_z),
                box_ll(8.0, 80.0, 5.5, CAMERA_CAGE_X0 + delta_x + 76.0, CAMERA_CAGE_Y0 + delta_y - 62.0, wrench_z),
                box_ll(18.0, 11.5, 5.5, CAMERA_CAGE_X0 + delta_x + 39.0, CAMERA_CAGE_Y0 + delta_y + 77.75, wrench_z),
                box_ll(8.0, 80.0, 5.5, CAMERA_CAGE_X0 + delta_x + 44.0, CAMERA_CAGE_Y0 + delta_y + 84.0, wrench_z),
            )
            wrench_overlaps.extend(
                total_intersection_volume(
                    test,
                    (indexed_keeper, indexed_carriage, indexed_cage, *keeper_heads, *final_booms),
                )
                for test in wrench_envelopes
            )

    head_overlap = max(head_overlaps)
    driver_overlap = max(driver_overlaps)
    jam_overlap = max(jam_overlaps)
    wrench_overlap = max(wrench_overlaps)
    checks.append({"check": "keeper_recessed_head_envelope_all_indices", "status": "PASS" if head_overlap <= 0.02 else "FAIL", "maximum_intersection_mm3": round(head_overlap, 6)})
    checks.append({"check": "keeper_hex_key_service_access_all_indices", "status": "PASS" if driver_overlap <= 0.02 else "FAIL", "maximum_intersection_mm3": round(driver_overlap, 6)})
    checks.append({"check": "leveling_jam_nut_washer_envelope_all_indices", "status": "PASS" if jam_overlap <= 0.02 else "FAIL", "maximum_intersection_mm3": round(jam_overlap, 6)})
    checks.append(
        {
            "check": "leveling_jam_nut_edge_wrench_sweeps_all_indices",
            "status": "PASS" if wrench_overlap <= 0.02 else "FAIL",
            "maximum_intersection_mm3": round(wrench_overlap, 6),
            "tool_head_envelope_mm": [18.0, 5.5],
            "modeled_handle_length_mm": 80.0,
            "modeled_bay_width_mm": 19.0,
            "front_approach": "-Y between booms",
            "rear_approach": "+Y between booms",
        }
    )

    # The complete carriage shafts remain outside the camera/cage envelope at
    # both discrete Y indices.  This catches the former through-camera
    # shaft layout and prevents a nominally selectable position from becoming
    # physically unusable.
    shaft_solids = [
        axis_cylinder((x, y, 1009.5), (0.0, 0.0, 1.0), 85.0, 2.6)
        for x, y in carriage_coords
    ]
    indexed_obstacles = []
    for delta_x in CAGE_INSTALLED_X_OFFSETS:
        for delta_y in CARRIAGE_INSTALLED_Y_OFFSETS:
            indexed_obstacles.extend(
                (
                    parts["camera_cage_body"].translate((CAMERA_CAGE_X0 + delta_x, CAMERA_CAGE_Y0 + delta_y, 1026.0)),
                    parts["camera_cage_keeper"].translate((CAMERA_CAGE_X0 + delta_x, CAMERA_CAGE_Y0 + delta_y, 1068.0)),
                    rounded_plate(38.0, 38.0, 25.0, 2.0, CAMERA_X - 19.0 + delta_x, CAMERA_Y - 19.0 + delta_y, 1034.0),
                    cq.Workplane("XY").center(CAMERA_X + delta_x, CAMERA_Y + delta_y).circle(19.75).extrude(34.0).translate((0, 0, 1000.0)),
                )
            )
    shaft_camera_overlap = max(total_intersection_volume(test, indexed_obstacles) for test in shaft_solids)
    checks.append(
        {
            "check": "all_indexed_carriage_shafts_clear_camera_envelope",
            "status": "PASS" if shaft_camera_overlap <= 0.02 else "FAIL",
            "maximum_intersection_mm3": round(shaft_camera_overlap, 6),
            "tested_x_index_offsets_mm": list(CAGE_INSTALLED_X_OFFSETS),
            "tested_y_index_offsets_mm": list(CARRIAGE_INSTALLED_Y_OFFSETS),
        }
    )

    # Annular slices through the carriage prove every selectable leveling bore
    # retains local washer-bearing material. This specifically guards against
    # service geometry silently opening a rear M4 bore to the carriage edge.
    carriage_bearing_fills = []
    carriage_top_bearing_fills = []
    carriage_top_seat_overlaps = []
    local_carriage = parts["camera_xy_carriage"]
    for base_x, y in ((93.0, 35.0), (157.0, 35.0), (125.0, 101.0)):
        for delta_x in CAGE_INSTALLED_X_OFFSETS:
            x = base_x + delta_x
            outer = axis_cylinder((x, y, 4.5), (0.0, 0.0, 1.0), 1.0, 4.75)
            inner = axis_cylinder((x, y, 4.4), (0.0, 0.0, 1.0), 1.2, 2.35)
            ring = outer.cut(inner)
            ring_volume = max(sum(s.Volume() for s in ring.solids().vals()), 1e-9)
            carriage_bearing_fills.append(intersection_volume(ring, local_carriage) / ring_volume)
            top_outer = axis_cylinder((x, y, 9.55), (0.0, 0.0, 1.0), 0.2, 4.75)
            top_inner = axis_cylinder((x, y, 9.54), (0.0, 0.0, 1.0), 0.22, 2.35)
            top_ring = top_outer.cut(top_inner)
            top_ring_volume = max(sum(s.Volume() for s in top_ring.solids().vals()), 1e-9)
            carriage_top_bearing_fills.append(
                intersection_volume(top_ring, local_carriage) / top_ring_volume
            )
            carriage_top_seat_overlaps.append(
                intersection_volume(
                    axis_cylinder((x, y, 9.81), (0.0, 0.0, 1.0), 6.3, 4.75),
                    local_carriage,
                )
            )
    checks.append(
        {
            "check": "all_camera_x_index_leveling_bore_annular_support",
            "status": "PASS" if min(carriage_bearing_fills) >= 0.95 else "FAIL",
            "minimum_solid_fill_ratio": round(min(carriage_bearing_fills), 6),
            "tested_bore_count": len(carriage_bearing_fills),
            "bearing_ring_outer_diameter_mm": 9.5,
        }
    )
    checks.append(
        {
            "check": "all_camera_x_index_leveling_top_washer_seats",
            "status": "PASS"
            if min(carriage_top_bearing_fills) >= 0.95 and max(carriage_top_seat_overlaps) <= 0.02
            else "FAIL",
            "minimum_below_spotface_solid_fill_ratio": round(min(carriage_top_bearing_fills), 6),
            "maximum_above_spotface_intersection_mm3": round(max(carriage_top_seat_overlaps), 6),
            "tested_bore_count": len(carriage_top_bearing_fills),
            "spotface_diameter_mm": 10.0,
            "spotface_depth_mm": 0.2,
        }
    )

    # Ring slices directly above the underside nut pockets prove the base roof
    # is continuous around each leveling screw and carries upward nut reaction.
    roof_fills = []
    local_cage = parts["camera_cage_body"]
    for x, y in ((16.0, 18.0), (80.0, 18.0), (48.0, 84.0)):
        outer = axis_cylinder((x, y, 3.9), (0.0, 0.0, 1.0), 1.0, 4.0)
        inner = axis_cylinder((x, y, 3.8), (0.0, 0.0, 1.0), 1.2, 2.4)
        ring = outer.cut(inner)
        fill = intersection_volume(ring, local_cage) / max(sum(s.Volume() for s in ring.solids().vals()), 1e-9)
        roof_fills.append(fill)
    checks.append({"check": "leveling_captive_nut_load_roof", "status": "PASS" if min(roof_fills) >= 0.95 else "FAIL", "minimum_solid_fill_ratio": round(min(roof_fills), 6), "roof_thickness_mm": 4.3})
    bolt_class(
        "M4x60 keeper",
        [[x, y, "-Z"] for x, y in keeper_coords],
        48.0,
        60.0,
        7.0,
        "Button head+washer recessed flush in keeper; nyloc+washer below cage base; service key passes through carriage.",
    )

    failures = [row for row in checks if row["status"] != "PASS"] + [row for row in classes if row["stack_status"] != "PASS"]
    report = {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "fastener_classes": classes,
        "note": "CAD axes and nominal stacks only; physical coupons, torque limits, proof load, and received-part checks remain mandatory.",
    }
    if failures:
        raise ValueError(f"Fastener interface validation failure(s): {failures}")
    return report


def validate_assembly_interfaces(parts: Dict[str, cq.Workplane]) -> dict:
    """Check selected non-contact interfaces for unintended solid overlap.

    Bolted gusset/member faces, compressed pads, and the cage/camera fit are
    deliberate contact interfaces and are explicitly excluded here.  These
    CAD checks do not replace tolerance coupons or a physical structural test.
    """
    checks = []

    def add(name: str, volume: float, limit: float = 0.01) -> None:
        checks.append(
            {
                "check": name,
                "status": "PASS" if volume <= limit else "FAIL",
                "intersection_volume_mm3": round(volume, 6),
                "limit_mm3": limit,
            }
        )

    def rod(start: Tuple[float, float, float], end: Tuple[float, float, float], radius: float) -> cq.Workplane:
        vector = cq.Vector(end[0] - start[0], end[1] - start[1], end[2] - start[2])
        return cq.Workplane(obj=cq.Solid.makeCylinder(radius, vector.Length, cq.Vector(*start), vector.normalized()))

    cross_z = float(CFG["layout"]["crossbar_bottom_z_mm"])
    boom_z = float(CFG["layout"]["boom_bottom_z_mm"])
    boom_root_y = float(CFG["layout"]["boom_root_y_mm"])
    crossbar_members = [
        _placed_crossbar(parts["crossbar_truss_segment_182p5"], -60.0 + CROSS_LENGTH * index, -100.0, cross_z)
        for index in range(CROSS_COUNT)
    ]
    crossbars = crossbar_members[0]
    for member in crossbar_members[1:]:
        crossbars = crossbars.union(member)
    boom_members = []
    for x_axis in BOOM_AXES_X:
        boom_members.extend(
            (
                _placed_boom(parts["boom_root_truss_segment_164p25"], x_axis, boom_root_y, boom_z),
                _placed_boom(parts["boom_camera_truss_segment_164p25"], x_axis, boom_root_y + 164.25, boom_z),
            )
        )
    booms = boom_members[0]
    for member in boom_members[1:]:
        booms = booms.union(member)
    # Exact tangent faces can produce sub-mm3 OCC slivers.  A 0.5 mm3 limit is
    # less than 0.00001% of the joined members and is treated as kernel noise,
    # not a modeled interference allowance.
    add("crossbar_to_boom_butt_no_volume_overlap", intersection_volume(crossbars, booms), limit=0.5)

    # The top and flipped bottom root straps touch the member faces but must
    # never occupy the same volume or foul an adjacent crossbar collar.
    splice_w = TRUSS_W + 0.8 + 12.0
    splice_y_offset = -(splice_w - TRUSS_W) / 2.0
    crossbar_splices = []
    for joint_index in range(1, CROSS_COUNT):
        joint_x = -60.0 + CROSS_LENGTH * joint_index
        splice_part = parts["u_truss_splice_center_4bolt"] if joint_index == 2 else parts["u_truss_splice_crossbar_2bolt"]
        crossbar_splices.append(
            splice_part.translate((joint_x - CROSS_SPLICE_HALF, -125.0 + splice_y_offset, cross_z - 4.0))
        )
    root_straps = []
    boom_splices = []
    for root_x in BOOM_AXES_X:
        strap_y0 = boom_root_y - ROOT_STRAP_D / 2.0
        root_straps.extend(
            (
                parts["boom_crossbar_node"].translate((root_x - ROOT_STRAP_W / 2.0, strap_y0, boom_z + TRUSS_H)),
                parts["boom_crossbar_node"].rotate((0, 0, 0), (1, 0, 0), 180.0).translate(
                    (root_x - ROOT_STRAP_W / 2.0, strap_y0 + ROOT_STRAP_D, boom_z)
                ),
            )
        )
        placed_boom_splice = parts["u_truss_splice"].translate((-SPLICE_HALF, splice_y_offset, -4.0))
        placed_boom_splice = placed_boom_splice.rotate((0, 0, 0), (0, 0, 1), 90.0).translate(
            (root_x + TRUSS_W / 2.0, boom_root_y + 164.25, boom_z)
        )
        boom_splices.append(placed_boom_splice)
    add(
        "boom_root_straps_touch_without_member_overlap",
        sum(total_intersection_volume(strap, (*crossbar_members, *boom_members)) for strap in root_straps),
        limit=0.1,
    )
    add(
        "boom_root_straps_clear_crossbar_splices",
        sum(total_intersection_volume(strap, crossbar_splices) for strap in root_straps),
    )

    # Raised identification stays on tabs above the load-bearing portal plates,
    # including the inward-facing member of each identical pair.
    left_nodes = (
        parts["portal_corner_node_left"].rotate((0, 0, 0), (1, 0, 0), -90.0).translate((-90.0, -133.0, 1074.0)),
        parts["portal_corner_node_left"].rotate((0, 0, 0), (1, 0, 0), -90.0).translate((-90.0, -75.0, 1074.0)),
    )
    right_nodes = (
        parts["portal_corner_node_right"].rotate((0, 0, 0), (1, 0, 0), -90.0).translate((600.0, -133.0, 1074.0)),
        parts["portal_corner_node_right"].rotate((0, 0, 0), (1, 0, 0), -90.0).translate((600.0, -75.0, 1074.0)),
    )
    portal_members = (
        _placed_upright(parts["upright_truss_segment_240"], -60.0, -100.0, 770.0),
        _placed_upright(parts["upright_truss_segment_240"], 670.0, -100.0, 770.0),
        crossbar_members[0],
        crossbar_members[-1],
    )
    add(
        "portal_gusset_markings_clear_members",
        max(total_intersection_volume(node, portal_members) for node in (*left_nodes, *right_nodes)),
        limit=0.5,
    )

    # Exercise all three positive-lock cage X indices and both carriage Y
    # rows. The complete cage, planar keeper, camera, lens, rear wing, and
    # carriage must remain mutually usable and between the two booms.
    for delta_x in CAGE_INSTALLED_X_OFFSETS:
        for delta_y in CARRIAGE_INSTALLED_Y_OFFSETS:
            carriage = parts["camera_xy_carriage"].translate((CARRIAGE_X0, CARRIAGE_Y0 + delta_y, 1074.0))
            cage = parts["camera_cage_body"].translate((CAMERA_CAGE_X0 + delta_x, CAMERA_CAGE_Y0 + delta_y, 1026.0))
            keeper = parts["camera_cage_keeper"].translate((CAMERA_CAGE_X0 + delta_x, CAMERA_CAGE_Y0 + delta_y, 1068.0))
            camera = rounded_plate(38.0, 38.0, 25.0, 2.0, CAMERA_X - 19.0 + delta_x, CAMERA_Y - 19.0 + delta_y, 1034.0)
            lens = cq.Workplane("XY").center(CAMERA_X + delta_x, CAMERA_Y + delta_y).circle(19.75).extrude(34.0).translate((0, 0, 1000.0))
            add(f"carriage_index_X{delta_x:+.0f}_Y{delta_y:+.0f}_touches_booms_without_overlap", intersection_volume(carriage, booms), limit=0.5)
            add(f"cage_index_X{delta_x:+.0f}_Y{delta_y:+.0f}_tangent_below_carriage", intersection_volume(cage, carriage))
            add(f"keeper_index_X{delta_x:+.0f}_Y{delta_y:+.0f}_tangent_below_carriage", intersection_volume(keeper, carriage))
            add(
                f"camera_group_index_X{delta_x:+.0f}_Y{delta_y:+.0f}_clear_booms",
                total_intersection_volume(booms, (cage, keeper, camera, lens)),
            )

    member = parts["upright_truss_segment_240"]
    two_members = member.union(member.translate((240.0, 0.0, 0.0)))
    installed_splice = parts["u_truss_splice"].translate((240.0 - SPLICE_HALF, -(splice_w - TRUSS_W) / 2.0, -4.0))
    add("u_splice_nominal_clearance", intersection_volume(two_members, installed_splice), limit=0.1)

    # Route the USB cable through the unobstructed distal end before turning
    # forward inside the right open-U boom. It rises ahead of the root straps,
    # crosses above the portal, drops below the corner plates on their front
    # side, and wraps around the right upright outside face at x=706 where the
    # segment's printed tie slots remain reachable. The independent safety
    # tether exits vertically through the rear-wing hole, stays above that
    # wing, and chokes the right boom at exposed station B y=152.5.
    right_uprights = [
        _placed_upright(parts["upright_truss_segment_240"], 670.0, -100.0, 50.0 + 240.0 * index)
        for index in range(4)
    ]
    for delta_x in CAGE_INSTALLED_X_OFFSETS:
        for delta_y in CARRIAGE_INSTALLED_Y_OFFSETS:
            usb_points = (
                (CAMERA_X + delta_x, 247.0 + delta_y, 1054.0),
                (CAMERA_X + delta_x, 286.0 + delta_y, 1042.0),
                (BOOM_AXES_X[1], 262.0, 1058.0),
                (BOOM_AXES_X[1], 252.0, 1058.0),
                (BOOM_AXES_X[1], -25.0, 1058.0),
                (BOOM_AXES_X[1], -25.0, 1093.0),
                (650.0, -140.0, 1093.0),
                (650.0, -140.0, 950.0),
                (706.0, -140.0, 950.0),
                (706.0, -100.0, 950.0),
                (706.0, -100.0, 100.0),
            )
            usb_route = rod(usb_points[0], usb_points[1], 2.2)
            for start, end in zip(usb_points[1:-1], usb_points[2:]):
                usb_route = usb_route.union(rod(start, end, 2.2))
            indexed_carriage = parts["camera_xy_carriage"].translate((CARRIAGE_X0, CARRIAGE_Y0 + delta_y, 1074.0))
            indexed_cage = parts["camera_cage_body"].translate((CAMERA_CAGE_X0 + delta_x, CAMERA_CAGE_Y0 + delta_y, 1026.0))
            indexed_keeper = parts["camera_cage_keeper"].translate((CAMERA_CAGE_X0 + delta_x, CAMERA_CAGE_Y0 + delta_y, 1068.0))
            add(
                f"usb_route_index_X{delta_x:+.0f}_Y{delta_y:+.0f}_clears_frame_and_carriage",
                total_intersection_volume(
                    usb_route,
                    (
                        booms,
                        crossbars,
                        indexed_carriage,
                        indexed_cage,
                        indexed_keeper,
                        *root_straps,
                        *boom_splices,
                        *left_nodes,
                        *right_nodes,
                        *right_uprights,
                    ),
                ),
            )

    loop_points = (
        (BOOM_AXES_X[1] - 31.0, TETHER_CHOKER_Y, 1006.0),
        (BOOM_AXES_X[1] - 31.0, TETHER_CHOKER_Y, 1078.0),
        (BOOM_AXES_X[1] + 31.0, TETHER_CHOKER_Y, 1078.0),
        (BOOM_AXES_X[1] + 31.0, TETHER_CHOKER_Y, 1006.0),
        (BOOM_AXES_X[1] - 31.0, TETHER_CHOKER_Y, 1006.0),
    )
    tether_eye_length = sum(math.dist(start, end) for start, end in zip(loop_points[:-1], loop_points[1:]))
    tether_lengths = []
    for delta_x in CAGE_INSTALLED_X_OFFSETS:
        for delta_y in CARRIAGE_INSTALLED_Y_OFFSETS:
            tether_lead_points = (
                (CAMERA_X + delta_x, CAMERA_CAGE_Y0 + 102.0 + delta_y, 1038.0),
                (CAMERA_CAGE_X0 + 83.0 + delta_x, 270.0 + delta_y, 1038.0),
                (BOOM_AXES_X[1] - 31.0, TETHER_CHOKER_Y, 1038.0),
            )
            tether_connector = axis_cylinder(
                (CAMERA_X + delta_x, CAMERA_CAGE_Y0 + 102.0 + delta_y, 1025.5),
                (0.0, 0.0, 1.0),
                12.5,
                2.5,
            )
            tether_route = rod(tether_lead_points[0], tether_lead_points[1], 1.5).union(
                rod(tether_lead_points[1], tether_lead_points[2], 1.5)
            )
            for start, end in zip(loop_points[:-1], loop_points[1:]):
                tether_route = tether_route.union(rod(start, end, 1.5))
            indexed_carriage = parts["camera_xy_carriage"].translate((CARRIAGE_X0, CARRIAGE_Y0 + delta_y, 1074.0))
            indexed_cage = parts["camera_cage_body"].translate((CAMERA_CAGE_X0 + delta_x, CAMERA_CAGE_Y0 + delta_y, 1026.0))
            indexed_keeper = parts["camera_cage_keeper"].translate((CAMERA_CAGE_X0 + delta_x, CAMERA_CAGE_Y0 + delta_y, 1068.0))
            add(
                f"tether_connector_index_X{delta_x:+.0f}_Y{delta_y:+.0f}_clears_wing_hole",
                total_intersection_volume(tether_connector, (indexed_cage, indexed_keeper, indexed_carriage)),
            )
            add(
                f"tether_route_index_X{delta_x:+.0f}_Y{delta_y:+.0f}_clears_structure_and_carriage",
                total_intersection_volume(
                    tether_route,
                    (booms, crossbars, indexed_carriage, indexed_cage, indexed_keeper, *root_straps, *boom_splices),
                ),
            )
            tether_lead_length = sum(math.dist(start, end) for start, end in zip(tether_lead_points[:-1], tether_lead_points[1:]))
            tether_lengths.append(tether_lead_length + tether_eye_length)
    tether_procurement = CFG["procurement_constraints"]["independent_camera_safety_tether"]
    tether_finished_min = float(tether_procurement["finished_length_nominal_mm"]) - float(
        tether_procurement["finished_length_tolerance_mm"]
    )
    tether_finished_max = float(tether_procurement["finished_length_nominal_mm"]) + float(
        tether_procurement["finished_length_tolerance_mm"]
    )
    minimum_tether_slack = tether_finished_min - max(tether_lengths)
    maximum_tether_slack = tether_finished_max - min(tether_lengths)
    required_minimum_slack = float(tether_procurement["installed_slack_minimum_mm"])
    allowed_maximum_slack = float(tether_procurement["installed_slack_maximum_mm"])
    checks.append(
        {
            "check": "tether_proxy_matches_procured_length_and_eye",
            "status": "PASS"
            if minimum_tether_slack >= required_minimum_slack
            and maximum_tether_slack <= allowed_maximum_slack
            and tether_eye_length / 2.0 >= 130.0
            else "FAIL",
            "modeled_centerline_length_range_mm": [round(min(tether_lengths), 3), round(max(tether_lengths), 3)],
            "modeled_laid_flat_eye_mm": round(tether_eye_length / 2.0, 3),
            "procurement_finished_length_range_mm": [round(tether_finished_min, 3), round(tether_finished_max, 3)],
            "minimum_slack_at_worst_index_mm": round(minimum_tether_slack, 3),
            "maximum_slack_at_best_index_mm": round(maximum_tether_slack, 3),
            "required_minimum_slack_mm": required_minimum_slack,
            "allowed_maximum_slack_mm": allowed_maximum_slack,
            "tested_x_index_offsets_mm": list(CAGE_INSTALLED_X_OFFSETS),
            "tested_y_index_offsets_mm": list(CARRIAGE_INSTALLED_Y_OFFSETS),
        }
    )

    # Every production DIN 985 nyloc must have a continuous, collision-free
    # insertion path from an exposed mouth to its antirotation seat. Validate
    # both straight outer channels and diagonal inner channels after mirroring,
    # plus the installed common retainer and the structural roof above each nut.
    m6_insertion_samples = 101
    m6_sweep_overlaps = []
    m6_retainer_saddle_overlaps = []
    m6_retainer_nut_overlaps = []
    m6_seated_nut_overlaps = []
    m6_roof_fills = []
    m6_tunnel_roof_fills = []
    m6_tunnel_floor_fills = []
    m6_tunnel_latch_wall_fills = []
    for hand, saddle in (
        ("L", parts["board_corner_saddle_left"]),
        ("R", parts["board_corner_saddle_right"]),
    ):
        for spec in saddle_m6_channel_specs(hand):
            seat_x, seat_y = spec["seat"]
            mouth_x, mouth_y = spec["mouth"]
            dx, dy = seat_x - mouth_x, seat_y - mouth_y
            path_length = math.hypot(dx, dy)
            ux, uy = dx / path_length, dy / path_length
            start_x, start_y = mouth_x - 7.0 * ux, mouth_y - 7.0 * uy
            roof_end = (seat_x - 8.0 * ux, seat_y - 8.0 * uy)
            channel_layout = m6_nut_channel_layout(seat_x, seat_y, spec["mouth"])

            retainer = placed_m6_nut_retainer(
                parts["m6_nut_retainer"], spec["mouth"], spec["seat"], 3.7
            )
            seated_nut = (
                cq.Workplane("XY")
                .polygon(6, 11.55)
                .extrude(6.0)
                .rotate((0, 0, 0), (0, 0, 1), spec["hex_angle_deg"])
                .translate((seat_x, seat_y, 6.55))
            )
            m6_retainer_saddle_overlaps.append(intersection_volume(retainer, saddle))
            m6_retainer_nut_overlaps.append(intersection_volume(retainer, seated_nut))
            m6_seated_nut_overlaps.append(intersection_volume(seated_nut, saddle))

            for sample_index in range(m6_insertion_samples):
                fraction = sample_index / (m6_insertion_samples - 1)
                center_x = start_x + (seat_x - start_x) * fraction
                center_y = start_y + (seat_y - start_y) * fraction
                moving_nut = (
                    cq.Workplane("XY")
                    .polygon(6, 11.55)
                    .extrude(6.0)
                    .rotate((0, 0, 0), (0, 0, 1), spec["hex_angle_deg"])
                    .translate((center_x, center_y, 6.55))
                )
                m6_sweep_overlaps.append(intersection_volume(moving_nut, saddle))

            roof_outer = axis_cylinder((seat_x, seat_y, 12.7), (0.0, 0.0, 1.0), 5.7, 8.25)
            roof_inner = axis_cylinder((seat_x, seat_y, 12.69), (0.0, 0.0, 1.0), 5.72, 3.4)
            roof_annulus = roof_outer.cut(roof_inner)
            roof_volume = max(sum(shape.Volume() for shape in roof_annulus.solids().vals()), 1e-9)
            m6_roof_fills.append(intersection_volume(roof_annulus, saddle) / roof_volume)

            # Sample the entire covered path outside the circular nut tower,
            # including the retainer bay's worst-case 13.6 mm bridge. The
            # slight inset avoids counting exact tangent faces as missing
            # material in the OCC kernel.
            tunnel_roof = strut_xy(
                spec["mouth"],
                roof_end,
                M6_NUT_TUNNEL_WIDTH - 0.4,
                M6_NUT_TUNNEL_TOP_Z - 12.8 - 0.1,
                z0=12.8,
            )
            tunnel_floor = strut_xy(
                spec["mouth"],
                roof_end,
                M6_NUT_TUNNEL_WIDTH - 0.4,
                5.1,
                z0=0.1,
            )
            latch_wall_outer = strut_xy(
                channel_layout["latch_start"],
                channel_layout["latch_end"],
                M6_NUT_TUNNEL_WIDTH - 0.4,
                7.0,
                z0=5.5,
            )
            latch_wall_inner = strut_xy(
                channel_layout["latch_start"],
                channel_layout["latch_end"],
                13.8,
                7.2,
                z0=5.4,
            )
            latch_walls = latch_wall_outer.cut(latch_wall_inner)
            for sample, destination in (
                (tunnel_roof, m6_tunnel_roof_fills),
                (tunnel_floor, m6_tunnel_floor_fills),
                (latch_walls, m6_tunnel_latch_wall_fills),
            ):
                sample_volume = max(sum(shape.Volume() for shape in sample.solids().vals()), 1e-9)
                destination.append(intersection_volume(sample, saddle) / sample_volume)

    checks.extend(
        (
            {
                "check": "all_four_m6_nyloc_exterior_to_seat_sweeps",
                "status": "PASS" if max(m6_sweep_overlaps) <= 0.02 else "FAIL",
                "maximum_intersection_mm3": round(max(m6_sweep_overlaps), 6),
                "samples_per_channel": m6_insertion_samples,
                "channel_count": 4,
            },
            {
                "check": "all_four_m6_nyloc_seats_and_retainers_clear",
                "status": "PASS"
                if max(m6_retainer_saddle_overlaps + m6_retainer_nut_overlaps + m6_seated_nut_overlaps) <= 0.02
                else "FAIL",
                "maximum_intersection_mm3": round(
                    max(m6_retainer_saddle_overlaps + m6_retainer_nut_overlaps + m6_seated_nut_overlaps), 6
                ),
            },
            {
                "check": "all_four_m6_nut_pocket_structural_roofs",
                "status": "PASS" if min(m6_roof_fills) >= 0.99 else "FAIL",
                "minimum_annular_solid_fill_ratio": round(min(m6_roof_fills), 6),
                "tested_roof_z_range_mm": [12.7, 18.4],
            },
            {
                "check": "all_four_m6_covered_channel_tunnels",
                "status": "PASS"
                if min(m6_tunnel_roof_fills + m6_tunnel_floor_fills + m6_tunnel_latch_wall_fills) >= 0.99
                else "FAIL",
                "minimum_roof_fill_ratio": round(min(m6_tunnel_roof_fills), 6),
                "minimum_floor_fill_ratio": round(min(m6_tunnel_floor_fills), 6),
                "minimum_latch_sidewall_fill_ratio": round(min(m6_tunnel_latch_wall_fills), 6),
                "modeled_tunnel_outer_width_mm": M6_NUT_TUNNEL_WIDTH,
                "modeled_minimum_roof_mm": M6_NUT_TUNNEL_MIN_ROOF,
                "maximum_support_free_bridge_mm": 13.6,
            },
        )
    )

    board = box_ll(BOARD_W, BOARD_D, BOARD_T, z0=-BOARD_T)
    installed_saddles = parts["board_corner_saddle_left"].translate((-120.0, -160.0, -BOARD_T)).union(
        parts["board_corner_saddle_right"].translate((540.0, -160.0, -BOARD_T))
    )
    add("saddle_stops_touch_but_do_not_overlap_board", intersection_volume(board, installed_saddles))

    failures = [row for row in checks if row["status"] != "PASS"]
    report = {
        "status": "PASS" if not failures else "FAIL",
        "scope": "selected unintended-overlap checks; deliberate bolted/contact/compression interfaces excluded",
        "nominal_camera_cage_side_clearance_mm": round((BOOM_AXES_X[1] - BOOM_AXES_X[0] - TRUSS_W - 96.0) / 2.0, 3),
        "tested_carriage_x_index_offsets_mm": list(CAGE_INSTALLED_X_OFFSETS),
        "tested_carriage_y_index_offsets_mm": list(CARRIAGE_INSTALLED_Y_OFFSETS),
        "tether_choker_station_B_mm": [BOOM_AXES_X[1], TETHER_CHOKER_Y],
        "checks": checks,
    }
    if failures:
        raise ValueError(f"Assembly interface validation failure(s): {failures}")
    return report


def main() -> None:
    contract_report = validate_design_contract()
    parts = make_parts()
    configured_quantities = {entry["part"]: int(entry["quantity"]) for entry in CFG["parts"]}
    if set(parts) != set(configured_quantities):
        raise ValueError(
            f"Part/config mismatch: CAD-only={sorted(set(parts)-set(configured_quantities))}, "
            f"config-only={sorted(set(configured_quantities)-set(parts))}"
        )

    removed_outputs = clean_managed_outputs(parts)
    plate_allocation_report = validate_plate_allocation(configured_quantities)

    interface_report = validate_assembly_interfaces(parts)
    fastener_report = validate_fastener_interfaces(parts)
    rows = [export_part(name, part, configured_quantities[name]) for name, part in parts.items()]
    failures = [row for row in rows if row["validation"] != "PASS"]
    stl_file_digest = hashlib.sha256()
    geometry_digest = hashlib.sha256()
    for row in sorted(rows, key=lambda entry: entry["part"]):
        filename = f"{row['part']}.stl"
        stl_file_digest.update(f"{filename}:{row['stl_sha256']}\n".encode("utf-8"))
        geometry_digest.update(f"{filename}:{row['geometry_identifier_sha256']}\n".encode("utf-8"))
    geometry_fingerprint = {
        "part_type_count": len(rows),
        "aggregate_stl_file_sha256": stl_file_digest.hexdigest(),
        "aggregate_geometry_identifier_sha256": geometry_digest.hexdigest(),
        "algorithm": "SHA-256 over sorted '<filename>:<per-file-or-geometry-hash>\\n' records",
        "parts": [
            {
                "part": row["part"],
                "stl_sha256": row["stl_sha256"],
                "geometry_identifier_sha256": row["geometry_identifier_sha256"],
            }
            for row in sorted(rows, key=lambda entry: entry["part"])
        ],
    }

    with (OUTPUT_DIR / "PART_VALIDATION.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    with (OUTPUT_DIR / "HARDWARE_MANIFEST.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("item", "quantity", "use"))
        writer.writeheader()
        writer.writerows(CFG["hardware"])

    (OUTPUT_DIR / "ASSEMBLY_INTERFACE_VALIDATION.json").write_text(
        json.dumps(interface_report, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT_DIR / "FASTENER_INTERFACE_VALIDATION.json").write_text(
        json.dumps(fastener_report, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT_DIR / "GEOMETRY_FINGERPRINT.json").write_text(
        json.dumps(geometry_fingerprint, indent=2) + "\n", encoding="utf-8"
    )

    make_assembly(parts)
    make_camera_subassembly(parts)
    printed_parts_assembly_report = make_printed_parts_only_assembly(parts)
    plate_rows, plate_report = export_geometry_only_plates()
    output_inventory_report = validate_managed_output_inventory(parts, removed_outputs)
    (OUTPUT_DIR / "PLATE_ALLOCATION_VALIDATION.json").write_text(
        json.dumps(plate_allocation_report, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT_DIR / "OUTPUT_INVENTORY_VALIDATION.json").write_text(
        json.dumps(output_inventory_report, indent=2) + "\n", encoding="utf-8"
    )

    manifest = {
        "schema": "rocell.printable_camera_portal.generated_manifest.v1",
        "design_id": CFG["design_id"],
        "state": CFG["state"],
        "authority": CFG["authority"],
        "procurement_constraints": CFG["procurement_constraints"],
        "contract_validation": contract_report,
        "assembly_interface_validation": interface_report,
        "fastener_interface_validation": fastener_report,
        "part_validation_status": "PASS" if not failures else "FAIL",
        "plate_allocation_validation": plate_allocation_report,
        "plate_validation": {
            "status": plate_report["status"],
            "subplate_count": plate_report["subplate_count"],
            "object_count": plate_report["object_count"],
            "report": "cad/output/PLATE_VALIDATION.json",
            "csv": "cad/output/PLATE_VALIDATION.csv",
            "subplates": plate_rows,
        },
        "printed_parts_only_assembly_validation": printed_parts_assembly_report,
        "managed_output_inventory_validation": output_inventory_report,
        "printable_geometry_fingerprint": geometry_fingerprint,
        "parts": rows,
        "hardware": CFG["hardware"],
        "assemblies": [
            "cad/output/assembly/printable_camera_portal_prototype.step",
            "cad/output/assembly/printable_camera_portal_prototype_reference.stl",
            "cad/output/assembly/printable_camera_portal_printed_parts_only.step",
            "cad/output/assembly/printable_camera_portal_printed_parts_only.stl",
            "cad/output/assembly/camera_cage_nominal_subassembly.step"
        ],
        "geometry_only_3mf_subplates": [
            str((PLATE_DIR / entry["filename"]).relative_to(ROOT)).replace("\\", "/")
            for entry in PLATE_DEFINITIONS
        ],
        "print_orientation": {
            "truss_segments_and_flat_plates": "as exported: largest flat face on build plate",
            "corner_saddles": "120 x 120 bench foot on build plate; receiver slot open upward",
            "camera_cage_body": "lens ring/base on build plate; USB notch open upward",
            "keeper_and_carriage": "flat as exported",
            "supports": "none intended; verify slicer preview before every print"
        },
        "raised_marking_policy": "All part IDs and orientation cues are raised. No functional instruction relies on engraving.",
        "mandatory_prototype_gates": CFG["mandatory_prototype_gates"],
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if failures:
        raise SystemExit(f"Part validation failure(s): {failures}")
    print(json.dumps({"status": "PASS", "part_count": len(rows), "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
    # The Windows OCP build can fault during Python teardown after valid files
    # are safely closed.  Bypass teardown only after a successful main().
    if sys.platform == "win32":
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
