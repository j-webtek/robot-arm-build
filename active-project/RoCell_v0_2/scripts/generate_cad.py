#!/usr/bin/env python3
"""RoCell v0.2 parametric CAD generator.

Creates editable STEP, print-ready STL, assembly STEP, board drawings, and metadata.
Units: millimetres.

Default hardware:
- Samsung Galaxy A16 5G bare phone: 164.4 x 77.9 x 7.9 mm
- Perixx PERIBOARD-409 keyboard: 315 x 147 x 21 mm
- QIDI Plus4 nominal build volume: 305 x 305 x 280 mm
- Conservative automatic plate envelope: 295 x 295 x 280 mm

The phone cradle is deliberately adjustable. Measure any case and edit PARAMS before
regenerating the final cradle.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Tuple, List

import cadquery as cq
from cadquery import exporters
import trimesh

ROOT = Path(__file__).resolve().parents[1]
STEP_DIR = ROOT / "cad" / "step"
STL_DIR = ROOT / "stl"
LARGE_STEP_DIR = ROOT / "cad" / "step" / "large_printer_optional"
LARGE_STL_DIR = ROOT / "stl_large_printer_optional"
CFG_DIR = ROOT / "config"
for d in (STEP_DIR, STL_DIR, LARGE_STEP_DIR, LARGE_STL_DIR, CFG_DIR):
    d.mkdir(parents=True, exist_ok=True)


@dataclass
class Parameters:
    # Structural work surface
    board_w: float = 610.0
    board_d: float = 457.0
    board_t: float = 18.0

    # QIDI Plus4 printer envelopes.  The nominal values document the machine;
    # automatic validation and packing use the safe values to preserve a 5 mm
    # edge margin on each side of the 305 mm build plate.
    printer_x: float = 305.0
    printer_y: float = 305.0
    printer_z: float = 280.0
    printer_safe_x: float = 295.0
    printer_safe_y: float = 295.0
    printer_safe_z: float = 280.0
    printer_edge_margin: float = 5.0

    # Keyboard - Perixx PERIBOARD-409 nominal envelope
    keyboard_w: float = 315.0
    keyboard_d: float = 147.0
    keyboard_h: float = 21.0
    keyboard_clearance: float = 1.0
    keyboard_tray_base_t: float = 4.0
    keyboard_tray_wall_t: float = 4.0
    keyboard_tray_wall_h: float = 7.0

    # Phone - Samsung Galaxy A16 5G nominal bare-body envelope
    phone_l: float = 164.4
    phone_w: float = 77.9
    phone_t: float = 7.9
    phone_clearance: float = 1.0
    phone_case_extra_w: float = 0.0
    phone_case_extra_l: float = 0.0
    phone_case_extra_t: float = 0.0

    # Mounting hardware
    m4_clearance: float = 4.6
    m5_clearance: float = 5.5
    m3_clearance: float = 3.4
    heatset_m3_od: float = 4.6
    m3_head_recess_d: float = 6.2
    m4_washer_od: float = 9.2
    m5_washer_od: float = 11.0
    m4_horizontal_insert_od: float = 6.2
    m4_insert_depth: float = 6.2
    mast_socket_size: float = 20.5
    m5_nut_ac: float = 9.4
    camera_hex_ac: float = 13.2
    zip_tie_slot_w: float = 3.2
    zip_tie_slot_l: float = 10.0
    zip_tie_tunnel_h: float = 1.8
    tag_pocket_depth: float = 0.4

    # Workcell layout, board origin = front-left; +X right, +Y rear
    keyboard_x: float = 80.0
    keyboard_y: float = 80.0
    phone_x: float = 480.0
    phone_y: float = 80.0
    calibration_x: float = 411.0
    calibration_y: float = 150.0
    tag_margin: float = 8.0
    # The 78 mm frame keeps M4 washer tracks completely outside the 55 mm tag
    # artwork while preserving the original tag-center world coordinates.
    tag_frame_size: float = 78.0

    # Stylus system
    stylus_nominal_d: float = 9.0
    keyboard_rod_d: float = 6.0


def load_parameters() -> Parameters:
    """Load optional user dimension overrides without requiring code edits."""
    params = Parameters()
    override_path = CFG_DIR / "user_overrides.json"
    if override_path.exists():
        data = json.loads(override_path.read_text(encoding="utf-8"))
        valid = set(asdict(params))
        unknown = sorted(set(data) - valid)
        if unknown:
            raise ValueError(f"Unknown parameter override(s): {unknown}")
        for key, value in data.items():
            setattr(params, key, float(value))
    return params


P = load_parameters()


def rounded_plate(w: float, d: float, h: float, r: float = 3.0,
                  x0: float = 0.0, y0: float = 0.0) -> cq.Workplane:
    """Rounded rectangular prism with lower-left XY origin at x0/y0 and base Z=0."""
    obj = cq.Workplane("XY").box(w, d, h, centered=(True, True, False))
    if r > 0:
        obj = obj.edges("|Z").fillet(min(r, w / 2 - 0.01, d / 2 - 0.01))
    return obj.translate((x0 + w / 2, y0 + d / 2, 0))


def box_ll(w: float, d: float, h: float, x0: float = 0.0, y0: float = 0.0,
           z0: float = 0.0) -> cq.Workplane:
    return cq.Workplane("XY").box(w, d, h, centered=(True, True, False)).translate(
        (x0 + w / 2, y0 + d / 2, z0)
    )


def slot_solid(cx: float, cy: float, length: float, diameter: float,
               height: float, angle: float = 0.0, z0: float = -0.5) -> cq.Workplane:
    return (
        cq.Workplane("XY")
        .moveTo(cx, cy)
        .slot2D(length, diameter, angle=angle)
        .extrude(height)
        .translate((0, 0, z0))
    )


def through_hole(cx: float, cy: float, dia: float, height: float,
                 z0: float = -0.5) -> cq.Workplane:
    return (
        cq.Workplane("XY")
        .center(cx, cy)
        .circle(dia / 2)
        .extrude(height)
        .translate((0, 0, z0))
    )


def washer_slot_relief(cx: float, cy: float, slot_length: float,
                       hole_diameter: float, washer_diameter: float,
                       top_z: float, angle: float = 0.0,
                       depth: float = 0.6) -> cq.Workplane:
    """Shallow top-side washer track preserving the slot's bolt travel.

    The larger slot is lengthened by the washer/hole diameter difference so a
    standard washer can remain seated through the original adjustment range.
    """
    relief_length = slot_length + washer_diameter - hole_diameter
    return slot_solid(
        cx, cy, relief_length, washer_diameter, depth + 0.1,
        angle=angle, z0=top_z - depth,
    )


def washer_hole_relief(cx: float, cy: float, washer_diameter: float,
                       top_z: float, depth: float = 0.8) -> cq.Workplane:
    """Shallow circular washer seat around a top-access mounting hole."""
    return through_hole(
        cx, cy, washer_diameter, depth + 0.1, z0=top_z - depth,
    )


def vertical_insert_leadin(cx: float, cy: float, pocket_diameter: float,
                           top_z: float, depth: float = 0.7,
                           radial_extra: float = 0.45) -> cq.Workplane:
    """Tapered top entry that helps a heat-set insert start squarely."""
    cone = cq.Solid.makeCone(
        pocket_diameter / 2,
        pocket_diameter / 2 + radial_extra,
        depth,
        cq.Vector(cx, cy, top_z - depth),
        cq.Vector(0, 0, 1),
    )
    return cq.Workplane(obj=cone)


def engrave_text(body: cq.Workplane, text: str, x: float, y: float,
                 top_z: float, size: float = 2.8, depth: float = 0.35) -> cq.Workplane:
    """Cut shallow, print-readable identification text into a horizontal top face."""
    cutter = (cq.Workplane("XY").workplane(offset=top_z - depth)
              .center(x, y).text(text, size, depth + 0.1, combine=False))
    return body.cut(cutter)


def add_slot_scale(body: cq.Workplane, cx: float, cy: float,
                   slot_length: float, hole_diameter: float,
                   washer_diameter: float, top_z: float,
                   axis: str = "x", side: int = 1,
                   pitch: float = 2.0, depth: float = 0.35) -> cq.Workplane:
    """Add open-topped graduation ticks without changing the mounting slot."""
    assert axis in {"x", "y"}
    travel = slot_length - hole_diameter
    count = int(math.floor((travel / 2) / pitch))
    offsets = [i * pitch for i in range(-count, count + 1)]
    for offset in offsets:
        tick_len = 3.0 if abs(offset) < 1e-6 else 1.8
        tick_w = 0.45
        gap = 0.45
        if axis == "x":
            x0 = cx + offset - tick_w / 2
            y0 = (cy + washer_diameter / 2 + gap) if side > 0 else (
                cy - washer_diameter / 2 - gap - tick_len
            )
            cutter = box_ll(
                tick_w, tick_len, depth + 0.1, x0=x0, y0=y0,
                z0=top_z - depth,
            )
        else:
            y0 = cy + offset - tick_w / 2
            x0 = (cx + washer_diameter / 2 + gap) if side > 0 else (
                cx - washer_diameter / 2 - gap - tick_len
            )
            cutter = box_ll(
                tick_len, tick_w, depth + 0.1, x0=x0, y0=y0,
                z0=top_z - depth,
            )
        body = body.cut(cutter)
    return body


def phone_mount_slot_centers(frame_l: float, frame_w: float, ear_w: float) -> List[Tuple[float, float]]:
    """Mounting slots kept clear of the two corner screw-clamp towers."""
    left_x = ear_w / 2
    right_x = ear_w + frame_w + ear_w / 2
    left_ys = (35.0, frame_l - 35.0)
    right_ys = (0.40 * frame_l, 0.65 * frame_l)
    return [(left_x, y) for y in left_ys] + [(right_x, y) for y in right_ys]


def keyboard_seam_spec() -> dict:
    """Shared dimensions for the tray joint and its mandatory fit coupon."""
    return {
        "tab_len": 22.0,
        "tab_depth": 30.0,
        "clearance": 0.28,
        "corner_radius": 3.5,
    }


def keyboard_tray_half(side: str) -> cq.Workplane:
    """One of two large keyboard tray halves. Prints flat without support."""
    assert side in {"left", "right"}
    pocket_w = P.keyboard_w + 2 * P.keyboard_clearance
    pocket_d = P.keyboard_d + 2 * P.keyboard_clearance
    wall = P.keyboard_tray_wall_t
    base_t = P.keyboard_tray_base_t
    outer_w = pocket_w + 2 * wall
    outer_d = pocket_d + 2 * wall
    half_w = outer_w / 2

    # Perimeter/rib skeleton: start with plate, remove two large windows.
    body = rounded_plate(half_w, outer_d, base_t, r=4)
    rim = 18.0
    rib = 14.0
    window_w = half_w - 2 * rim
    y_gap = (outer_d - 2 * rim - rib) / 2
    for wy in (rim, rim + y_gap + rib):
        cut = rounded_plate(window_w, y_gap, base_t + 1.0, r=4,
                            x0=rim, y0=wy).translate((0, 0, -0.5))
        body = body.cut(cut)

    # Add one full-depth support rib through the centre of each window. These
    # keep the keyboard shell from spanning the original ~57 mm openings and
    # also tie the outer rail to the centre seam rail under repeated keypresses.
    support_rib = 8.0
    for wy in (rim + y_gap / 2, rim + y_gap + rib + y_gap / 2):
        body = body.union(box_ll(
            half_w - 2 * rim, support_rib, base_t,
            x0=rim, y0=wy - support_rib / 2,
        ))

    # Low front lip and outer side lip. Rear remains open for adjustable clamps.
    body = body.union(box_ll(half_w, wall, P.keyboard_tray_wall_h,
                             x0=0, y0=0, z0=base_t))
    if side == "left":
        body = body.union(box_ll(wall, outer_d, P.keyboard_tray_wall_h,
                                 x0=0, y0=0, z0=base_t))
    else:
        body = body.union(box_ll(wall, outer_d, P.keyboard_tray_wall_h,
                                 x0=half_w - wall, y0=0, z0=base_t))

    # Centre seam: rounded keys engage the skeleton rails without severing the
    # central rail. A small root overlap prevents a zero-thickness union.
    seam = keyboard_seam_spec()
    tab_len = seam["tab_len"]
    tab_depth = seam["tab_depth"]
    # Three keys control yaw and vertical mismatch along the whole seam. The
    # halves are still independently fastened to the board, so these keys only
    # align the datum plane and do not carry the fixture's primary load.
    tab_y = (
        18.0,
        (outer_d - tab_depth) / 2,
        outer_d - 18.0 - tab_depth,
    )
    if side == "left":
        for y in tab_y:
            body = body.union(rounded_plate(
                tab_len + 1.0, tab_depth, base_t,
                r=seam["corner_radius"], x0=half_w - 1.0, y0=y,
            ))
    else:
        clearance = seam["clearance"]
        for y in tab_y:
            pocket = rounded_plate(
                tab_len + 2 * clearance + 0.2,
                tab_depth + 2 * clearance,
                base_t + 1.0,
                r=seam["corner_radius"] + clearance,
                x0=-clearance - 0.1,
                y0=y - clearance,
            ).translate((0, 0, -0.5))
            # A straight entry mouth removes the two re-entrant corner cusps
            # that a filleted open pocket would otherwise leave at the seam.
            mouth = box_ll(
                seam["corner_radius"] + clearance + 1.0,
                tab_depth + 2 * clearance,
                base_t + 1.0,
                x0=-0.5,
                y0=y - clearance,
                z0=-0.5,
            )
            body = body.cut(pocket.union(mouth))

    # Four board-adjustment slots.
    # Dedicated mounting locations on the intact 18 mm front/rear rails. The
    # former y=23/outer-23 centers fell inside the skeleton windows and offered
    # no washer-bearing material.
    slot_pts = [
        (22, 10), (half_w - 22, 10),
        (22, outer_d - 10), (half_w - 22, outer_d - 10),
    ]
    for x, y in slot_pts:
        body = body.cut(slot_solid(x, y, 18, P.m4_clearance, base_t + 2, angle=0))
        body = body.cut(washer_slot_relief(
            x, y, 18, P.m4_clearance, P.m4_washer_od, base_t, angle=0, depth=0.5,
        ))
        # Point the ticks toward the intact outside rails, not the skeleton
        # windows immediately inboard of the mounting slots.
        scale_side = -1 if y < outer_d / 2 else 1
        body = add_slot_scale(
            body, x, y, 18, P.m4_clearance, P.m4_washer_od,
            base_t, axis="x", side=scale_side,
        )

    # Shallow anti-slip pad recesses on intact front/rear rails. Earlier
    # positions coincided with the open skeleton windows and held no pads.
    x = half_w / 2 - 8.0
    for y in (4.0, outer_d - 14.0):
        recess = rounded_plate(16, 10, 0.6, r=2, x0=x, y0=y).translate((0, 0, base_t - 0.6))
        body = body.cut(recess)

    # Rear seam witness mark stays visible during dry assembly but sits below
    # the keyboard after installation.
    mark_x = half_w - 8.0 if side == "left" else 8.0
    body = engrave_text(body, "RC02-L" if side == "left" else "RC02-R",
                        mark_x, outer_d - 8.0, base_t, size=3.0)

    return body


def keyboard_tray_full_large_printer() -> cq.Workplane:
    """One-piece keyboard tray for a printer with at least ~330 x 165 mm clear area."""
    half_w, _ = part_dimensions()["keyboard_half"]
    left = keyboard_tray_half("left")
    right = keyboard_tray_half("right").translate((half_w, 0, 0))
    return left.union(right).clean()


def keyboard_rear_clamp() -> cq.Workplane:
    w, d, bt, face_h = 52.0, 34.0, 5.0, 20.0
    body = rounded_plate(w, d, bt, r=3)
    body = body.union(box_ll(w, 5.0, face_h, x0=0, y0=0, z0=bt))
    # Face pad recess.
    body = body.cut(box_ll(w - 10, 0.8, 10.0, x0=5, y0=-0.01, z0=bt + 5))
    # Three support-free triangular ribs transfer clamp force into the base and
    # reduce layer-line peel at the vertical-face root.
    for x0 in (6.0, 24.0, 42.0):
        gusset = (cq.Workplane("YZ").polyline([
            (5.0, bt), (15.0, bt), (5.0, bt + 14.0)
        ]).close().extrude(4.0).translate((x0, 0, 0)))
        body = body.union(gusset)
    # Long board slot allows forward pressure adjustment.
    body = body.cut(slot_solid(w / 2, 23.0, 20.0, P.m4_clearance, bt + 2, angle=90))
    body = body.cut(washer_slot_relief(
        w / 2, 23.0, 20.0, P.m4_clearance, P.m4_washer_od, bt,
        angle=90, depth=0.6,
    ))
    body = add_slot_scale(
        body, w / 2, 23.0, 20.0, P.m4_clearance,
        P.m4_washer_od, bt, axis="y", side=1,
    )
    body = engrave_text(body, "KB", w / 2, 29.0, bt, size=3.0)
    return body


def phone_cradle() -> cq.Workplane:
    """One-piece Galaxy A16 cradle with two captive horizontal screw clamps.

    The clamp screws are carried by towers printed as part of the cradle, so no
    retainer bolt needs to pass into the structural board.  Clamp stations are
    intentionally near the phone corners, away from the usual side-button zone.
    """
    device_w = P.phone_w + P.phone_case_extra_w
    device_l = P.phone_l + P.phone_case_extra_l
    device_t = P.phone_t + P.phone_case_extra_t
    fit_w = device_w + 2 * P.phone_clearance
    fit_l = device_l + 2 * P.phone_clearance
    wall = 3.2
    bt = 4.0
    rail_h = min(max(device_t * 0.75, 6.0), 13.0)
    frame_w = fit_w + 2 * wall
    frame_l = fit_l + 2 * wall
    ear_w = 15.0
    ear_l = 34.0
    # Mounting ears extend 1 mm beyond the nominal 15 mm side allowance.
    outer_w = frame_w + 2 * ear_w + 1.0

    # One-piece skeleton base.
    body = rounded_plate(frame_w, frame_l, bt, r=6, x0=ear_w, y0=0)
    # Open centre for cooling and broad rear-camera-bump clearance.
    inner_cut = rounded_plate(fit_w - 18, fit_l - 22, bt + 2, r=7,
                              x0=ear_w + wall + 9, y0=wall + 11).translate((0, 0, -0.5))
    body = body.cut(inner_cut)

    # Four integrated board-mounting ears.  The right-side pair is shifted
    # inward so the mounting screws remain accessible beside the clamp towers.
    mount_centers = phone_mount_slot_centers(frame_l, frame_w, ear_w)
    for cx, cy in mount_centers:
        x0 = 0.0 if cx < outer_w / 2 else ear_w + frame_w
        body = body.union(rounded_plate(ear_w + 1.0, ear_l, bt, r=3,
                                        x0=x0, y0=cy - ear_l / 2))

    # Fixed datums: left and top. USB-C edge (bottom) remains open at centre.
    body = body.union(box_ll(wall, fit_l + 2 * wall, rail_h,
                             x0=ear_w, y0=0, z0=bt))
    body = body.union(box_ll(frame_w, wall, rail_h,
                             x0=ear_w, y0=frame_l - wall, z0=bt))

    # Bottom corner keepers leave a 40+ mm USB-C/cable opening.
    keeper = 24.0
    body = body.union(box_ll(keeper, wall, rail_h,
                             x0=ear_w, y0=0, z0=bt))
    body = body.union(box_ll(keeper, wall, rail_h,
                             x0=ear_w + frame_w - keeper, y0=0, z0=bt))

    # Right-side keeper tabs only at the extreme corners.
    body = body.union(box_ll(wall, 25.0, rail_h,
                             x0=ear_w + frame_w - wall, y0=0, z0=bt))
    body = body.union(box_ll(wall, 25.0, rail_h,
                             x0=ear_w + frame_w - wall, y0=frame_l - 25.0, z0=bt))

    # Broad full-width rear-camera relief in the upper support frame. This
    # avoids depending on whether a phone/case presents its camera bump on the
    # left or right when the device is placed screen-up.
    cam_relief = box_ll(fit_w + 1.0, 68.0, bt + 2,
                        x0=ear_w + wall - 0.5,
                        y0=frame_l - wall - 68.0,
                        z0=-0.5)
    body = body.cut(cam_relief)

    # M4 board-mounting slots run along Y inside the 34 mm ears. The earlier
    # X-oriented 18 mm slots opened through the 16 mm ear ends and could not
    # retain a washer safely.
    for x, y in mount_centers:
        body = body.cut(slot_solid(x, y, 18, P.m4_clearance, bt + 2, angle=90))
        body = body.cut(washer_slot_relief(
            x, y, 18, P.m4_clearance, P.m4_washer_od, bt, angle=90, depth=0.5,
        ))

    # Raised cable-tie saddle on the outer-right lower band. The strap passes
    # through a horizontal tunnel above the board, so no tie head is trapped
    # under the cradle and the mounting plane remains flat.
    saddle_x0 = ear_w + frame_w - wall
    saddle = box_ll(8.0, 10.0, 3.0, x0=saddle_x0, y0=2.0, z0=bt)
    tunnel = box_ll(
        P.zip_tie_slot_w, 12.0, P.zip_tie_tunnel_h,
        x0=saddle_x0 + (8.0 - P.zip_tie_slot_w) / 2,
        y0=1.0, z0=bt + 0.6,
    )
    body = body.union(saddle).cut(tunnel)

    # Two integrated clamp towers.  M4 heat-set inserts install from the outer
    # face; M4 screws advance horizontally and use separate TPU tip caps.
    # Towers overlap the right frame rail and extend down to the print bed.
    # The previous 1 mm stand-off produced two disconnected, floating solids.
    tower_x = ear_w + frame_w - wall
    tower_w = outer_w - tower_x
    tower_d = 24.0
    tower_h = max(bt + rail_h + 6.0, 20.0)
    clamp_ys = (30.0, frame_l - 30.0)
    clamp_z = bt + max(3.5, min(device_t / 2.0, 6.0))
    for cy in clamp_ys:
        body = body.union(rounded_plate(tower_w, tower_d, tower_h, r=2.5,
                                        x0=tower_x, y0=cy - tower_d / 2))
        # M4 screw passage along X.
        passage = (cq.Workplane("YZ").center(cy, clamp_z)
                   .circle(P.m4_clearance / 2)
                   .extrude(tower_w + 4.0)
                   .translate((tower_x - 2.0, 0, 0)))
        body = body.cut(passage)
        # Typical short M4 heat-set insert pocket (verify your insert dimensions).
        insert = (cq.Workplane("YZ").center(cy, clamp_z)
                  .circle(P.m4_horizontal_insert_od / 2)
                  .extrude(P.m4_insert_depth)
                  .translate((outer_w - P.m4_insert_depth, 0, 0)))
        body = body.cut(insert)

        # A short outer-face taper helps the insert enter squarely without
        # changing the full-depth production pocket tested by the H coupons.
        leadin = cq.Solid.makeCone(
            P.m4_horizontal_insert_od / 2,
            P.m4_horizontal_insert_od / 2 + 0.45, 0.7,
            cq.Vector(outer_w - 0.7, cy, clamp_z), cq.Vector(1, 0, 0),
        )
        body = body.cut(cq.Workplane(obj=leadin))
        body = engrave_text(
            body, "HAND", outer_w - tower_w / 2, cy,
            tower_h, size=2.3, depth=0.3,
        )

    body = engrave_text(body, "USB", ear_w + frame_w / 2, 11.8, bt, size=3.0)
    body = engrave_text(body, "TOP", ear_w + frame_w / 2, frame_l - 7.0, bt, size=3.0)

    return body


def phone_clamp_tip_tpu() -> cq.Workplane:
    """Soft push-fit cap for the inner end of an M4 phone clamp screw."""
    # Keep the 7.5 mm contact inside the nominal 7.9 mm phone thickness so it
    # cannot wedge against the cradle base or curl over the screen edge.
    body = cq.Workplane("XY").circle(3.75).extrude(8.0)
    body = body.edges(">Z").fillet(3.1)
    # 4.1 mm blind pocket grips the threaded M4 screw end.
    body = body.cut(cq.Workplane("XY").circle(2.05).extrude(5.8).translate((0, 0, -0.2)))
    # Flared first-layer entry prevents elephant-foot squeeze from blocking the
    # M4 screw and makes the soft cap easier to start squarely.
    entry = cq.Solid.makeCone(2.4, 2.05, 0.8, cq.Vector(0, 0, 0), cq.Vector(0, 0, 1))
    body = body.cut(cq.Workplane(obj=entry))
    # Shallow seating witness below the fillet; this remains printable while
    # preserving more than 1.5 mm radial wall around the blind bore.
    witness = (cq.Workplane("XY").workplane(offset=4.5)
               .circle(3.76).circle(3.58).extrude(0.3))
    body = body.cut(witness)
    return body


def phone_width_fit_test() -> cq.Workplane:
    """Small U-channel coupon that tests actual phone/case width and rail height."""
    device_w = P.phone_w + P.phone_case_extra_w
    device_t = P.phone_t + P.phone_case_extra_t
    fit_w = device_w + 2 * P.phone_clearance
    bt, wall = 3.0, 3.2
    h = min(max(device_t * 0.75, 6.0), 13.0)
    depth = 36.0
    outer_w = fit_w + 2 * wall
    body = rounded_plate(outer_w, depth, bt, r=4)
    body = body.union(box_ll(wall, depth, h, 0, 0, bt))
    body = body.union(box_ll(wall, depth, h, outer_w - wall, 0, bt))
    body = engrave_text(body, f"FIT{fit_w:.1f}", outer_w / 2, 6.0, bt, size=2.8)
    return body


def keyboard_corner_fit_test() -> cq.Workplane:
    """Small coupon reproducing the keyboard tray front-left datum."""
    bt = P.keyboard_tray_base_t
    wall = P.keyboard_tray_wall_t
    h = P.keyboard_tray_wall_h
    size = 58.0
    body = rounded_plate(size, size, bt, r=4)
    body = body.union(box_ll(size, wall, h, 0, 0, bt))
    body = body.union(box_ll(wall, size, h, 0, 0, bt))
    body = body.cut(rounded_plate(30, 30, bt + 1, r=3, x0=15, y0=15).translate((0,0,-0.5)))
    body = engrave_text(body, "FRONT-L", size / 2, 7.0, bt, size=2.8)
    return body


def keyboard_seam_fit_test(side: str) -> cq.Workplane:
    """Small male/female coupon reproducing the production keyboard seam."""
    assert side in {"male", "female"}
    seam = keyboard_seam_spec()
    base_t = P.keyboard_tray_base_t
    block_w, block_d = 38.0, 38.0
    y = (block_d - seam["tab_depth"]) / 2
    body = rounded_plate(block_w, block_d, base_t, r=4)
    if side == "male":
        body = body.union(rounded_plate(
            seam["tab_len"] + 1.0,
            seam["tab_depth"],
            base_t,
            r=seam["corner_radius"],
            x0=block_w - 1.0,
            y0=y,
        ))
    else:
        c = seam["clearance"]
        pocket = rounded_plate(
            seam["tab_len"] + 2 * c + 0.2,
            seam["tab_depth"] + 2 * c,
            base_t + 1.0,
            r=seam["corner_radius"] + c,
            x0=-c - 0.1,
            y0=y - c,
        ).translate((0, 0, -0.5))
        mouth = box_ll(
            seam["corner_radius"] + c + 1.0,
            seam["tab_depth"] + 2 * c,
            base_t + 1.0,
            x0=-0.5,
            y0=y - c,
            z0=-0.5,
        )
        body = body.cut(pocket.union(mouth))
    body = engrave_text(
        body,
        "M" if side == "male" else "F",
        10.0 if side == "male" else 29.0,
        31.0,
        base_t,
        size=4.0,
    )
    body = engrave_text(body, f"C{seam['clearance']:.2f}", block_w / 2, 6.0, base_t, size=2.5)
    return body


def hardware_fit_gauge() -> cq.Workplane:
    """M3/M4/M5 clearance-hole ladder for the selected PETG profile."""
    w, d, h = 160.0, 30.0, 6.0
    body = rounded_plate(w, d, h, r=4)
    hole_diameters = (3.2, 3.4, 3.6, 4.4, 4.6, 4.8, 5.3, 5.5, 5.7)
    for index, dia in enumerate(hole_diameters):
        x = 15.0 + index * 16.25
        body = body.cut(through_hole(x, 16.0, dia, h + 2))
        body = engrave_text(body, f"{dia:.1f}", x, 4.5, h, size=2.5)
    return body


def m4_washer_fit_gauge() -> cq.Workplane:
    """Compact M4 washer-track ladder for profile-specific qualification."""
    w, d, h = 78.0, 30.0, 6.0
    body = rounded_plate(w, d, h, r=4)
    for x, diameter in zip((14.0, 39.0, 64.0), (8.8, 9.2, 9.6)):
        body = body.cut(through_hole(x, 17.0, P.m4_clearance, h + 2))
        body = body.cut(through_hole(x, 17.0, diameter, 0.7, z0=h - 0.6))
        body = engrave_text(body, f"W{diameter:.1f}", x, 5.0, h, size=2.3)
    return body


def m3_head_fit_gauge() -> cq.Workplane:
    """Compact M3 head-recess ladder matching the keyed tool cap."""
    w, d, h = 78.0, 30.0, 6.0
    body = rounded_plate(w, d, h, r=4)
    for x, diameter in zip((14.0, 39.0, 64.0), (5.8, 6.2, 6.6)):
        body = body.cut(through_hole(x, 17.0, P.m3_clearance, h + 2))
        body = body.cut(through_hole(x, 17.0, diameter, 2.1, z0=h - 2.0))
        body = engrave_text(body, f"H{diameter:.1f}", x, 5.0, h, size=2.3)
    return body


def m3_insert_fit_gauge() -> cq.Workplane:
    """Full-depth vertical M3 heat-set ladder printed with the tool profile."""
    w, d, h = 78.0, 30.0, 8.0
    body = rounded_plate(w, d, h, r=4)
    for x, dia in zip((14.0, 39.0, 64.0), (4.3, 4.6, 4.9)):
        body = body.cut(cq.Workplane("XY").center(x, d / 2)
                        .circle(dia / 2).extrude(6.2).translate((0, 0, h - 6.2)))
        body = body.cut(vertical_insert_leadin(x, d / 2, dia, h))
        body = engrave_text(body, f"M3-{dia:.1f}", x, 5.0, h, size=2.3)
    return body


def m4_horizontal_insert_fit_gauge() -> cq.Workplane:
    """Horizontal M4 insert ladder matching the phone-tower print direction."""
    w, d, h = 26.0, 80.0, 16.0
    body = rounded_plate(w, d, h, r=3)
    for y, dia in zip((14.0, 40.0, 66.0), (5.9, 6.2, 6.5)):
        # Full M4 passage followed by a 6.2 mm deep insert pocket from the
        # outer face, identical in axis and depth to the phone cradle towers.
        passage = (cq.Workplane("YZ").center(y, h / 2)
                   .circle(P.m4_clearance / 2).extrude(w + 2.0)
                   .translate((-1.0, 0, 0)))
        pocket = (cq.Workplane("YZ").center(y, h / 2)
                  .circle(dia / 2).extrude(6.2)
                  .translate((w - 6.2, 0, 0)))
        body = body.cut(passage).cut(pocket)
        leadin = cq.Solid.makeCone(
            dia / 2, dia / 2 + 0.45, 0.7,
            cq.Vector(w - 0.7, y, h / 2), cq.Vector(1, 0, 0),
        )
        body = body.cut(cq.Workplane(obj=leadin))
        body = engrave_text(body, f"H{dia:.1f}", w / 2, y, h, size=2.4)
    body = engrave_text(body, "OUTER", w / 2, 5.0, h, size=2.4)
    return body


def compliant_tool_grip_fit_test() -> cq.Workplane:
    """Short coupon reproducing the compliant tool's RoArm gripping faces."""
    w, d, h = 28.0, 24.0, 34.0
    body = rounded_plate(w, d, h, r=3.0)
    body = body.cut(box_ll(18.0, 1.2, 28.0, x0=5.0, y0=-0.01, z0=3.0))
    body = body.cut(box_ll(18.0, 1.2, 28.0, x0=5.0, y0=d - 1.19, z0=3.0))
    return engrave_text(body, "G", w / 2, d / 2, h, size=4.0)


def spring_fit_gauge() -> cq.Workplane:
    """Cup gauge checking compliant-tool spring OD and ID simultaneously."""
    w, d, h = 30.0, 30.0, 14.0
    body = rounded_plate(w, d, h, r=4.0)
    body = body.cut(cq.Workplane("XY").center(w / 2, d / 2)
                    .circle(15.2 / 2).extrude(6.2)
                    .translate((0, 0, 3.0)))
    body = body.cut(cq.Workplane("XY").center(w / 2, d / 2)
                    .circle(14.2 / 2).extrude(5.2)
                    .translate((0, 0, 8.9)))
    body = body.union(cq.Workplane("XY").center(w / 2, d / 2)
                      .circle(10.0 / 2).extrude(8.0)
                      .translate((0, 0, 3.0)))
    return engrave_text(body, "SPR", w / 2, 4.5, h, size=2.8)


def setup_hardware_fit_gauge() -> cq.Workplane:
    """Head, washer, and camera-hex recess ladder for measured hardware."""
    w, d, h = 160.0, 84.0, 8.0
    body = rounded_plate(w, d, h, r=4)
    xs = (30.0, 80.0, 130.0)
    rows = (
        (14.0, "M3H", (5.8, 6.2, 6.6), P.m3_clearance, 2.0),
        (34.0, "M4W", (8.8, 9.2, 9.6), P.m4_clearance, 0.6),
        (54.0, "M5W", (10.0, 11.0, 12.0), P.m5_clearance, 0.8),
        (74.0, "QTR-AC", (12.6, 13.2, 13.8), 6.8, 3.2),
    )
    for y, prefix, diameters, passage_d, depth in rows:
        for x, diameter in zip(xs, diameters):
            body = body.cut(through_hole(x, y, passage_d, h + 2))
            if prefix == "QTR-AC":
                recess = (cq.Workplane("XY").center(x, y)
                           .polygon(6, diameter).extrude(depth + 0.1)
                           .translate((0, 0, h - depth)))
                body = body.cut(recess)
            else:
                body = body.cut(through_hole(
                    x, y, diameter, depth + 0.1, z0=h - depth,
                ))
            body = engrave_text(body, f"{prefix}{diameter:.1f}", x, y - 8.5, h, size=2.0)
    return body


def thread_pilot_fit_gauge() -> cq.Workplane:
    """Horizontal blind pilot ladder for flush M2/M3 adapter grub screws."""
    w, d, h = 26.0, 106.0, 18.0
    body = rounded_plate(w, d, h, r=3)
    specs = (
        (12.0, "M2-1.5", 1.5), (28.0, "M2-1.6", 1.6),
        (44.0, "M2-1.7", 1.7), (64.0, "M3-2.4", 2.4),
        (80.0, "M3-2.5", 2.5), (96.0, "M3-2.6", 2.6),
    )
    for y, label, diameter in specs:
        pilot = cq.Solid.makeCylinder(
            diameter / 2, 7.0,
            cq.Vector(w + 0.5, y, h / 2), cq.Vector(-1, 0, 0),
        )
        body = body.cut(cq.Workplane(obj=pilot))
        body = engrave_text(body, label, w / 2, y, h, size=2.0)
    return body


def cable_tie_saddle_fit_gauge() -> cq.Workplane:
    """Raised-saddle tunnel ladder for the actual strain-relief tie."""
    w, d, bt = 84.0, 30.0, 4.0
    body = rounded_plate(w, d, bt, r=4)
    for x, width in zip((12.0, 36.0, 60.0), (2.6, 3.2, 4.0)):
        saddle = box_ll(14.0, 10.0, 3.0, x0=x, y0=10.0, z0=bt)
        tunnel = box_ll(
            width, 12.0, 1.8,
            x0=x + (14.0 - width) / 2, y0=9.0, z0=bt + 0.6,
        )
        body = body.union(saddle).cut(tunnel)
        body = engrave_text(body, f"T{width:.1f}", x + 7.0, 5.0, bt, size=2.4)
    return body


def m5_nut_trap_fit_gauge() -> cq.Workplane:
    """Production-axis M5 nut, clearance-hole, and washer-seat ladder."""
    w, d, h = 26.0, 90.0, 30.0
    body = rounded_plate(w, d, h, r=4)
    ys = (15.0, 45.0, 75.0)
    for y, diameter in zip(ys, (9.1, 9.4, 9.7)):
        passage = (cq.Workplane("YZ").center(y, 8.0)
                   .circle(P.m5_clearance / 2).extrude(w + 2.0)
                   .translate((-1.0, 0, 0)))
        pocket = (cq.Workplane("YZ").center(y, 8.0)
                  .polygon(6, diameter).extrude(5.0)
                  .translate((w - 5.0, 0, 0)))
        entry = (cq.Workplane("YZ").center(y, 8.0)
                 .polygon(6, diameter + 0.6).extrude(0.7)
                 .translate((w - 0.7, 0, 0)))
        body = body.cut(passage).cut(pocket).cut(entry)
        body = engrave_text(body, f"N{diameter:.1f}", w / 2, y, h, size=2.3)
    for y, hole_d, washer_d in zip(ys, (5.3, 5.5, 5.7), (10.0, 11.0, 12.0)):
        passage = (cq.Workplane("YZ").center(y, 22.0)
                   .circle(hole_d / 2).extrude(w + 2.0)
                   .translate((-1.0, 0, 0)))
        seat = (cq.Workplane("YZ").center(y, 22.0)
                .circle(washer_d / 2).extrude(0.8)
                .translate((-0.01, 0, 0)))
        body = body.cut(passage).cut(seat)
        body = engrave_text(body, f"C{hole_d:.1f}", w / 2, y, h, size=2.1)
    return body


def mast_socket_fit_test() -> cq.Workplane:
    """Three connected 2020 sockets with 0.2/0.5/0.8 mm total clearance."""
    w, d, base_t, socket_h = 110.0, 36.0, 4.0, 24.0
    body = rounded_plate(w, d, base_t, r=4)
    for index, socket in enumerate((20.2, 20.5, 20.8)):
        x0 = 2.0 + index * 36.0
        body = body.union(rounded_plate(34.0, 34.0, socket_h, r=3, x0=x0, y0=1.0))
        body = body.cut(box_ll(socket, socket, socket_h + 1,
                               x0=x0 + (34.0 - socket) / 2,
                               y0=(d - socket) / 2,
                               z0=base_t))
        entry = (cq.Workplane("XY").workplane(offset=socket_h - 1.0)
                 .center(x0 + 17.0, d / 2).rect(socket, socket)
                 .workplane(offset=1.1).rect(socket + 2.0, socket + 2.0)
                 .loft(combine=False))
        body = body.cut(entry)
        body = engrave_text(body, f"{socket:.1f}", x0 + 17.0, 4.5,
                            socket_h, size=2.6)
    return body


def tpu_tip_retention_gauge() -> cq.Workplane:
    """Rigid M4 and 6 mm pegs used to verify both TPU push-fit tips."""
    w, d, h = 38.0, 22.0, 3.0
    body = rounded_plate(w, d, h, r=3)
    body = body.union(cq.Workplane("XY").center(11.0, d / 2)
                      .circle(2.0).extrude(8.0).translate((0, 0, h)))
    body = body.union(cq.Workplane("XY").center(27.0, d / 2)
                      .circle(3.0).extrude(11.0).translate((0, 0, h)))
    m4_band = (cq.Workplane("XY").workplane(offset=h + 5.5)
               .center(11.0, d / 2).circle(2.01).circle(1.85).extrude(0.3))
    rod_band = (cq.Workplane("XY").workplane(offset=h + 8.5)
                .center(27.0, d / 2).circle(3.01).circle(2.8).extrude(0.3))
    body = body.cut(m4_band).cut(rod_band)
    body = engrave_text(body, "M4", 11.0, 4.0, h, size=2.5)
    body = engrave_text(body, "6", 27.0, 4.0, h, size=2.5)
    return body


def tag_frame(tag_id: int) -> cq.Workplane:
    outer = P.tag_frame_size
    bt = 4.0
    recess = 55.4  # accepts 55 mm paper tile with slight clearance
    paper_pocket_depth = P.tag_pocket_depth
    body = rounded_plate(outer, outer, bt, r=4)
    body = body.cut(rounded_plate(recess, recess, paper_pocket_depth, r=1.5,
                                  x0=(outer - recess) / 2,
                                  y0=(outer - recess) / 2).translate((0, 0, bt - paper_pocket_depth)))
    # Fasteners and washers remain entirely outside the paper tile.
    for x in (6.0, outer - 6.0):
        body = body.cut(slot_solid(x, outer / 2, 14, P.m4_clearance, bt + 2, angle=90))
        body = body.cut(washer_slot_relief(
            x, outer / 2, 14, P.m4_clearance, P.m4_washer_od, bt,
            angle=90, depth=0.5,
        ))
    # Shallow thumbnail scoop intersects the paper recess without piercing the
    # frame, allowing artwork replacement without a knife.
    scoop = (cq.Workplane("XY").workplane(offset=bt - 1.0)
             .center(outer / 2, (outer - recess) / 2)
             .circle(4.5).extrude(1.1))
    body = body.cut(scoop)
    body = engrave_text(body, f"ID{tag_id} +Y", outer / 2, outer - 4.8, bt, size=2.8)
    return body


def calibration_puck() -> cq.Workplane:
    w, d, h = 60.0, 60.0, 8.0
    body = rounded_plate(w, d, h, r=5)
    # Fine crosshair grooves.
    body = body.cut(box_ll(42, 0.8, 0.8, x0=9, y0=d / 2 - 0.4, z0=h - 0.8))
    body = body.cut(box_ll(0.8, 42, 0.8, x0=w / 2 - 0.4, y0=9, z0=h - 0.8))
    # Central conical divot for TCP calibration.
    cone_solid = cq.Solid.makeCone(2.2, 0.3, 3.0, cq.Vector(w / 2, d / 2, h - 3.0), cq.Vector(0, 0, 1))
    body = body.cut(cq.Workplane(obj=cone_solid))
    for x in (12, w - 12):
        body = body.cut(slot_solid(x, 10, 12, P.m4_clearance, h + 2, angle=90))
        body = body.cut(washer_slot_relief(
            x, 10, 12, P.m4_clearance, P.m4_washer_od, h,
            angle=90, depth=0.6,
        ))
        body = add_slot_scale(
            body, x, 10, 12, P.m4_clearance, P.m4_washer_od,
            h, axis="y", side=1 if x < w / 2 else -1,
        )
    body = engrave_text(body, "TCP R2", w / 2, d - 5.0, h, size=2.8)
    return body


def camera_plate() -> cq.Workplane:
    w, d, h = 90.0, 55.0, 6.0
    body = rounded_plate(w, d, h, r=5)
    # Generic 1/4-20 passage and top-access hex pocket. Final use as a captured
    # bolt head or nut is gated by the actual camera mounting interface.
    body = body.cut(through_hole(w / 2, d / 2, 6.8, h + 2))
    nut = (cq.Workplane("XY").center(w / 2, d / 2)
           .polygon(6, P.camera_hex_ac).extrude(3.2)
           .translate((0, 0, h - 3.2)))
    body = body.cut(nut)
    # Cable-tie/webcam strap slots.
    for x in (18.0, w - 18.0):
        body = body.cut(slot_solid(x, 34.0, 24, 4.8, h + 2, angle=90))
    # 2020/T-slot mounting slots.
    for x in (w / 2 - 20, w / 2 + 20):
        body = body.cut(slot_solid(x, 10.0, 15, P.m5_clearance, h + 2, angle=0))
        body = body.cut(washer_slot_relief(
            x, 10.0, 15, P.m5_clearance, P.m5_washer_od, h,
            angle=0, depth=0.7,
        ))
        body = add_slot_scale(
            body, x, 10.0, 15, P.m5_clearance, P.m5_washer_od,
            h, axis="x", side=1,
        )
    body = engrave_text(body, "CAM", w / 2, d - 7.0, h, size=3.2)
    body = engrave_text(body, "MAST", w / 2, 7.0, h, size=2.8)
    body = engrave_text(body, "1/4", w / 2, d / 2 + 9.0, h, size=2.5)
    return body


def mast_foot_2020() -> cq.Workplane:
    # Plus4-optimized optional stand foot. The wider base, taller socket,
    # paired clamp bolts, and tapered ribs resist camera-mast bending.
    bw, bd, bt = 92.0, 92.0, 10.0
    tower, th = 48.0, 64.0
    body = rounded_plate(bw, bd, bt, r=6)
    body = body.union(rounded_plate(tower, tower, th, r=4,
                                    x0=(bw - tower) / 2,
                                    y0=(bd - tower) / 2).translate((0, 0, bt)))
    # 2020 extrusion socket; 0.5 mm total clearance.
    body = body.cut(box_ll(P.mast_socket_size, P.mast_socket_size, th + 2,
                           x0=(bw - P.mast_socket_size) / 2,
                           y0=(bd - P.mast_socket_size) / 2,
                           z0=bt - 0.5))
    socket_entry = (cq.Workplane("XY").workplane(offset=bt + th - 1.0)
                    .center(bw / 2, bd / 2).rect(P.mast_socket_size, P.mast_socket_size)
                    .workplane(offset=1.1).rect(P.mast_socket_size + 2.0, P.mast_socket_size + 2.0)
                    .loft(combine=False))
    body = body.cut(socket_entry)
    # Clamp slit to rear edge.
    body = body.cut(box_ll(3.0, tower / 2 + 6, th + 2,
                           x0=bw / 2 - 1.5,
                           y0=bd / 2,
                           z0=bt - 0.5))
    # Four tapered ribs bridge the tower-to-base transition.
    rib_w, rib_run, rib_h = 16.0, 18.0, 32.0
    rib_offset = bw / 2 - rib_w / 2
    y0, y1 = (bd - tower) / 2, (bd + tower) / 2
    front = (cq.Workplane("YZ").polyline([
        (y0 - rib_run, bt), (y0 + 0.5, bt), (y0 + 0.5, bt + rib_h)
    ]).close().extrude(rib_w).translate((rib_offset, 0, 0)))
    rear = (cq.Workplane("YZ").polyline([
        (y1 - 0.5, bt + rib_h), (y1 - 0.5, bt), (y1 + rib_run, bt)
    ]).close().extrude(rib_w).translate((rib_offset, 0, 0)))
    x0, x1 = (bw - tower) / 2, (bw + tower) / 2
    left = (cq.Workplane("XZ").polyline([
        (x0 - rib_run, bt), (x0 + 0.5, bt), (x0 + 0.5, bt + rib_h)
    ]).close().extrude(rib_w).translate((0, rib_offset, 0)))
    right = (cq.Workplane("XZ").polyline([
        (x1 - 0.5, bt + rib_h), (x1 - 0.5, bt), (x1 + rib_run, bt)
    ]).close().extrude(rib_w).translate((0, rib_offset, 0)))
    body = body.union(front).union(rear).union(left).union(right)

    # Two transverse M5 clamp bolts distribute force along the taller socket.
    tower_x_max = (bw + tower) / 2
    clamp_y = bd / 2 + 16.0  # rear split lugs, clear of the 20.5 mm socket
    for bolt_z in (bt + 24.0, bt + 48.0):
        bolt = (cq.Workplane("YZ").center(clamp_y, bolt_z)
                .circle(P.m5_clearance / 2).extrude(bw + 2).translate((-1, 0, 0)))
        body = body.cut(bolt)
        nut = (cq.Workplane("YZ").center(clamp_y, bolt_z)
               .polygon(6, P.m5_nut_ac).extrude(5.0).translate((tower_x_max - 5.0, 0, 0)))
        nut_entry = (cq.Workplane("YZ").center(clamp_y, bolt_z)
                     .polygon(6, P.m5_nut_ac + 0.6).extrude(0.7)
                     .translate((tower_x_max - 0.7, 0, 0)))
        body = body.cut(nut).cut(nut_entry)
    # Board mounting holes.
    for x in (15.0, bw - 15.0):
        for y in (15.0, bd - 15.0):
            body = body.cut(through_hole(x, y, P.m5_clearance, bt + 2))
            body = body.cut(washer_hole_relief(x, y, P.m5_washer_od, bt, depth=0.8))
    body = body.cut(box_ll(
        0.6, 8.1, 0.4, x0=bw / 2 - 0.3, y0=-0.1, z0=bt - 0.4,
    ))
    return body


def compliant_tool_body() -> cq.Workplane:
    """Rigid gripper-held body for a positively retained spring plunger.

    A 9 mm commercial stylus, or the 6 mm rod adapter, slides in the lower guide
    bore.  Its collar/flange is trapped in the larger spring chamber by the
    screwed top cap.  Contact moves the plunger upward and compresses the spring.
    """
    w, d, h = 28.0, 24.0, 65.0
    guide_d = P.stylus_nominal_d + 1.0  # 10 mm nominal guide
    chamber_d = 15.2
    shoulder_z = 44.0
    body = rounded_plate(w, d, h, r=3.0)
    # Lower sliding guide and upper spring/collar chamber.
    body = body.cut(cq.Workplane("XY").center(w / 2, d / 2)
                    .circle(guide_d / 2).extrude(shoulder_z + 1).translate((0, 0, -0.5)))
    body = body.cut(cq.Workplane("XY").center(w / 2, d / 2)
                    .circle(chamber_d / 2).extrude(h - shoulder_z + 1).translate((0, 0, shoulder_z)))
    # Gripper flats/recesses on both long faces.
    body = body.cut(box_ll(18.0, 1.2, 28.0, x0=5.0, y0=-0.01, z0=14.0))
    body = body.cut(box_ll(18.0, 1.2, 28.0, x0=5.0, y0=d - 1.19, z0=14.0))
    # Two vertical M3 heat-set insert pockets for the retaining cap.
    for x, y in ((5.0, 5.0), (w - 5.0, d - 5.0)):
        body = body.cut(cq.Workplane("XY").center(x, y)
                        .circle(P.heatset_m3_od / 2).extrude(6.2).translate((0, 0, h - 6.2)))
        body = body.cut(vertical_insert_leadin(x, y, P.heatset_m3_od, h))
    # Asymmetric locating pin makes an upside-down or rotated cap impossible
    # to seat while remaining clear of both inserts and the spring chamber.
    body = body.union(cq.Workplane("XY").center(w - 5.0, 5.0)
                      .circle(1.3).extrude(1.2).translate((0, 0, h)))
    return body


def compliant_tool_top_cap() -> cq.Workplane:
    w, d, h = 28.0, 24.0, 5.0
    body = rounded_plate(w, d, h, r=3.0)
    body = body.cut(cq.Workplane("XY").center(w / 2, d / 2)
                    .circle((P.stylus_nominal_d + 1.6) / 2).extrude(h + 2).translate((0, 0, -1)))
    # Annular spring-locating groove on the underside. Keeping the central
    # island reduces the unsupported roof from 14.2 mm to a 2.1 mm radial span.
    outer = (cq.Workplane("XY").center(w / 2, d / 2)
             .circle(14.2 / 2).extrude(1.2))
    inner = (cq.Workplane("XY").center(w / 2, d / 2)
             .circle(10.0 / 2).extrude(1.4).translate((0, 0, -0.1)))
    body = body.cut(outer.cut(inner))
    body = body.cut(cq.Workplane("XY").center(w - 5.0, 5.0)
                    .circle(1.55).extrude(1.5).translate((0, 0, -0.1)))
    for x, y in ((5.0, 5.0), (w - 5.0, d - 5.0)):
        body = body.cut(through_hole(x, y, P.m3_clearance, h + 2))
        body = body.cut(cq.Workplane("XY").center(x, y)
                        .circle(P.m3_head_recess_d / 2).extrude(2.0).translate((0, 0, h - 2.0)))
    body = engrave_text(body, "UP", w / 2, d - 4.0, h, size=2.8)
    return body


def stylus_collar() -> cq.Workplane:
    """Low-profile split collar for a nominal 9 mm stylus barrel.

    The collar must slide freely inside the 15.2 mm spring chamber.  Adjust the
    bore in Parameters after using the supplied diameter gauge; secure the final
    location with an M2 flat/nylon-tip grub screw after pilot selection.
    """
    od, h = 13.6, 5.5
    bore = P.stylus_nominal_d + 0.25
    body = cq.Workplane("XY").circle(od / 2).extrude(h)
    body = body.cut(cq.Workplane("XY").circle(bore / 2).extrude(h + 2).translate((0, 0, -1)))
    body = body.cut(box_ll(1.2, od / 2 + 1.0, h + 2, x0=-0.6, y0=0, z0=-1))
    pilot = cq.Solid.makeCylinder(
        0.8, od / 2 - bore / 2 + 1.0,
        cq.Vector(od / 2 + 0.4, 0, h / 2), cq.Vector(-1, 0, 0),
    )
    body = body.cut(cq.Workplane(obj=pilot))
    return body


def rod_bushing_6_to_9() -> cq.Workplane:
    od = P.stylus_nominal_d - 0.15
    inner = P.keyboard_rod_d + 0.25
    straight_length = 33.5
    transition_h = 2.5
    flange_z = straight_length + transition_h
    body = cq.Workplane("XY").circle(od / 2).extrude(straight_length)
    transition = cq.Solid.makeCone(
        od / 2, 13.5 / 2, transition_h,
        cq.Vector(0, 0, straight_length), cq.Vector(0, 0, 1),
    )
    body = body.union(cq.Workplane(obj=transition))
    body = body.union(cq.Workplane("XY").circle(13.5 / 2).extrude(2.8).translate((0, 0, flange_z)))
    body = body.cut(cq.Workplane("XY").circle(inner / 2).extrude(flange_z + 4).translate((0, 0, -1)))
    # The split sleeve permits measured adhesive/interference retention. A
    # radial M3 pilot is intentionally omitted: the 2.8 mm flange is too thin
    # to hold a reliable printed thread without compromising the spring seat.
    body = body.cut(box_ll(1.2, od / 2 + 1, flange_z + 2.8 + 2,
                           x0=-0.6, y0=0, z0=-1))
    return body


def keyboard_tip() -> cq.Workplane:
    """TPU push-fit tip for a 6 mm rod; prints upright without support."""
    bore = P.keyboard_rod_d + 0.25
    body = cq.Workplane("XY").circle(6.0).extrude(14.0)
    body = body.edges(">Z").fillet(5.5)
    body = body.cut(cq.Workplane("XY").circle(bore / 2).extrude(9.0).translate((0, 0, -0.5)))
    entry = cq.Solid.makeCone(3.45, bore / 2, 1.0,
                              cq.Vector(0, 0, 0), cq.Vector(0, 0, 1))
    body = body.cut(cq.Workplane(obj=entry))
    witness = (cq.Workplane("XY").workplane(offset=8.1)
               .circle(6.01).circle(5.8).extrude(0.3))
    body = body.cut(witness)
    return body


def stylus_diameter_gauge() -> cq.Workplane:
    w, d, h = 92.0, 28.0, 4.0
    body = rounded_plate(w, d, h, r=4)
    diameters = [8.0, 8.5, 9.0, 9.5, 10.0]
    xs = [12 + i * 17 for i in range(len(diameters))]
    for x, dia in zip(xs, diameters):
        body = body.cut(through_hole(x, d / 2, dia + 0.2, h + 2))
        body = engrave_text(body, f"{dia:.1f}", x, 4.0, h, size=2.5)
    body = engrave_text(body, "SLIDE +0.2", w / 2, d - 4.0, h, size=2.8)
    return body


def board_model() -> cq.Workplane:
    """Structural board model with fixture pilot holes. Fabricate from plywood/MDF."""
    body = rounded_plate(P.board_w, P.board_d, P.board_t, r=3)
    for x, y, dia in board_pilot_holes():
        body = body.cut(through_hole(x, y, dia, P.board_t + 2))
    return body


def part_dimensions() -> Dict[str, Tuple[float, float]]:
    pocket_w = P.keyboard_w + 2 * P.keyboard_clearance
    pocket_d = P.keyboard_d + 2 * P.keyboard_clearance
    wall = P.keyboard_tray_wall_t
    kb_outer_w = pocket_w + 2 * wall
    kb_outer_d = pocket_d + 2 * wall
    phone_fit_w = P.phone_w + P.phone_case_extra_w + 2 * P.phone_clearance
    phone_fit_l = P.phone_l + P.phone_case_extra_l + 2 * P.phone_clearance
    phone_frame_w = phone_fit_w + 2 * 3.2
    phone_frame_l = phone_fit_l + 2 * 3.2
    # Four mounting ears are 16 mm wide and add 1 mm beyond the nominal
    # 15 mm side allowance used to position the phone frame.
    phone_outer_w = phone_frame_w + 31.0
    return {
        "keyboard_outer": (kb_outer_w, kb_outer_d),
        "keyboard_half": (kb_outer_w / 2, kb_outer_d),
        "phone_outer": (phone_outer_w, phone_frame_l),
    }


def tag_frame_origins() -> Dict[str, Tuple[float, float]]:
    """Frame origins with safe board-edge margins and a clear phone-cable lane."""
    # The lower frames finish 1 mm ahead of the keyboard/phone datum line, so
    # they cannot overlap the fixtures. T1 sits entirely left of the phone,
    # preserving the front USB-C cable path. Fastener centres remain at least
    # 14 mm from every board edge even though the frame itself may sit closer.
    return {
        "T0": (8.0, 1.0),
        "T1": (401.0, 1.0),
        "T2": (8.0, 371.0),
        "T3": (524.0, 371.0),
        "K0": (285.0, 270.0),
        "P0": (420.0, 270.0),
    }


def board_pilot_holes() -> List[Tuple[float, float, float]]:
    """Pilot/through-hole centres matching the board layout.

    M4 fixture locations use 4.6 mm through holes in the board model. In wood,
    the assembly guide recommends 3 mm pilot holes for wood screws or 4.5-5 mm
    through holes for bolts, depending on chosen hardware.
    """
    dims = part_dimensions()
    kb_half_w, kb_d = dims["keyboard_half"]
    holes: List[Tuple[float, float, float]] = []

    # Keyboard tray half slot centres, left and right.
    local_pts = [(22, 10), (kb_half_w - 22, 10),
                 (22, kb_d - 10), (kb_half_w - 22, kb_d - 10)]
    for offset_x in (P.keyboard_x, P.keyboard_x + kb_half_w):
        for x, y in local_pts:
            holes.append((offset_x + x, P.keyboard_y + y, P.m4_clearance))

    # Rear clamps: nominal initial positions. Their slots allow final adjustment.
    for cx in (P.keyboard_x + 85, P.keyboard_x + 240):
        holes.append((cx, P.keyboard_y + P.keyboard_tray_wall_t + P.keyboard_d + 0.5 + 23, P.m4_clearance))

    # Phone cradle mounting slots; shared helper keeps CAD and board drawing aligned.
    phone_outer_w, phone_frame_l = dims["phone_outer"]
    frame_w = phone_outer_w - 31.0
    ear_w = 15.0
    for x, y in phone_mount_slot_centers(phone_frame_l, frame_w, ear_w):
        holes.append((P.phone_x + x, P.phone_y + y, P.m4_clearance))

    # Calibration puck two slots - use their nominal centres.
    for x in (12, 48):
        holes.append((P.calibration_x + x, P.calibration_y + 10, P.m4_clearance))

    # Six tag frames: four world tags + keyboard and phone device tags.
    t = P.tag_frame_size
    tag_origins = tag_frame_origins()
    for ox, oy in tag_origins.values():
        for x in (6.0, t - 6.0):
            holes.append((ox + x, oy + t / 2, P.m4_clearance))

    return holes


def board_layout_metadata() -> dict:
    dims = part_dimensions()
    t = P.tag_frame_size
    return {
        "units": "mm",
        "origin": "front-left corner of board top surface",
        "axes": {"+x": "right", "+y": "rear/toward arm", "+z": "up"},
        "board": {"width": P.board_w, "depth": P.board_d, "thickness": P.board_t},
        "keyboard": {
            "origin_xy": [P.keyboard_x, P.keyboard_y],
            "outer_envelope": list(dims["keyboard_outer"]),
            "device_nominal": [P.keyboard_w, P.keyboard_d, P.keyboard_h],
        },
        "phone": {
            "origin_xy": [P.phone_x, P.phone_y],
            "outer_envelope": list(dims["phone_outer"]),
            "device_nominal": [P.phone_w, P.phone_l, P.phone_t],
        },
        "calibration_puck": {"origin_xy": [P.calibration_x, P.calibration_y], "size": [60, 60]},
        "arm_clamp_zone": {"rear_edge_x_range": [225, 385], "note": "No fixed holes; use factory table-edge clamp."},
        "tags": {name: list(origin) for name, origin in tag_frame_origins().items()},
        "pilot_holes": [{"x": x, "y": y, "diameter": dia} for x, y, dia in board_pilot_holes()],
    }


def validate_layout() -> None:
    """Reject fixture layouts that leave the board or overlap another fixture."""
    layout = board_layout_metadata()
    rectangles = [
        ("keyboard", *layout["keyboard"]["origin_xy"], *layout["keyboard"]["outer_envelope"]),
        ("phone", *layout["phone"]["origin_xy"], *layout["phone"]["outer_envelope"]),
        ("calibration_puck", *layout["calibration_puck"]["origin_xy"],
         *layout["calibration_puck"]["size"]),
    ]
    rectangles.extend(
        (f"tag_{name}", x, y, P.tag_frame_size, P.tag_frame_size)
        for name, (x, y) in layout["tags"].items()
    )

    for name, x, y, w, d in rectangles:
        if x < 0 or y < 0 or x + w > P.board_w or y + d > P.board_d:
            raise ValueError(
                f"{name} leaves board: origin=({x}, {y}), size=({w}, {d}), "
                f"board=({P.board_w}, {P.board_d})"
            )

    for index, (name_a, ax, ay, aw, ad) in enumerate(rectangles):
        for name_b, bx, by, bw, bd in rectangles[index + 1:]:
            overlap_x = min(ax + aw, bx + bw) - max(ax, bx)
            overlap_y = min(ay + ad, by + bd) - max(ay, by)
            if overlap_x > 0 and overlap_y > 0:
                raise ValueError(
                    f"Fixture overlap: {name_a} and {name_b} "
                    f"overlap by {overlap_x:.2f} x {overlap_y:.2f} mm"
                )


def export_part(name: str, obj: cq.Workplane) -> dict:
    step_path = STEP_DIR / f"{name}.step"
    stl_path = STL_DIR / f"{name}.stl"
    exporters.export(obj, str(step_path))
    exporters.export(obj, str(stl_path), tolerance=0.08, angularTolerance=0.08)
    mesh = trimesh.load_mesh(stl_path, force="mesh")
    ext = mesh.extents
    components = len(mesh.split(only_watertight=False))
    fits_nominal = bool(
        ext[0] <= P.printer_x + 1e-6
        and ext[1] <= P.printer_y + 1e-6
        and ext[2] <= P.printer_z + 1e-6
    )
    fits_safe = bool(
        ext[0] <= P.printer_safe_x + 1e-6
        and ext[1] <= P.printer_safe_y + 1e-6
        and ext[2] <= P.printer_safe_z + 1e-6
    )
    return {
        "part": name,
        "stl": str(stl_path.relative_to(ROOT)),
        "step": str(step_path.relative_to(ROOT)),
        "extent_x_mm": round(float(ext[0]), 3),
        "extent_y_mm": round(float(ext[1]), 3),
        "extent_z_mm": round(float(ext[2]), 3),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "connected_components": components,
        "single_body": components == 1,
        "positive_volume": bool(mesh.volume > 0),
        "volume_cm3": round(float(mesh.volume) / 1000.0, 2),
        "fits_plus4_nominal_305x305x280": fits_nominal,
        "fits_plus4_safe_295x295x280": fits_safe,
    }


def make_assembly(parts: Dict[str, cq.Workplane]) -> None:
    dims = part_dimensions()
    kb_half_w, kb_d = dims["keyboard_half"]
    phone_outer_w, phone_frame_l = dims["phone_outer"]
    assy = cq.Assembly(name="RoCell_v0_2")
    assy.add(board_model(), name="board", color=cq.Color(0.68, 0.55, 0.38, 1.0))
    assy.add(parts["keyboard_tray_left"], name="keyboard_tray_left",
             loc=cq.Location(cq.Vector(P.keyboard_x, P.keyboard_y, P.board_t)),
             color=cq.Color(0.15, 0.45, 0.75, 1.0))
    assy.add(parts["keyboard_tray_right"], name="keyboard_tray_right",
             loc=cq.Location(cq.Vector(P.keyboard_x + kb_half_w, P.keyboard_y, P.board_t)),
             color=cq.Color(0.15, 0.45, 0.75, 1.0))
    # Rear clamps, nominal positions.
    for i, cx in enumerate((P.keyboard_x + 85, P.keyboard_x + 240), 1):
        assy.add(parts["keyboard_rear_clamp"], name=f"keyboard_rear_clamp_{i}",
                 loc=cq.Location(cq.Vector(cx - 26, P.keyboard_y + P.keyboard_tray_wall_t + P.keyboard_d + 0.5, P.board_t)),
                 color=cq.Color(0.18, 0.55, 0.30, 1.0))
    assy.add(parts["phone_cradle_a16"], name="phone_cradle_a16",
             loc=cq.Location(cq.Vector(P.phone_x, P.phone_y, P.board_t)),
             color=cq.Color(0.75, 0.25, 0.20, 1.0))
    assy.add(parts["calibration_puck"], name="calibration_puck",
             loc=cq.Location(cq.Vector(P.calibration_x, P.calibration_y, P.board_t)),
             color=cq.Color(0.85, 0.65, 0.12, 1.0))
    tag_origins = board_layout_metadata()["tags"]
    tag_ids = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "K0": 4, "P0": 5}
    for name, (x, y) in tag_origins.items():
        assy.add(parts[f"tag_frame_ID{tag_ids[name]}_55mm"], name=f"tag_{name}",
                 loc=cq.Location(cq.Vector(x, y, P.board_t)),
                 color=cq.Color(0.92, 0.92, 0.92, 1.0))
    assy.save(str(STEP_DIR / "RoCell_v0_2_full_assembly.step"))


def main() -> None:
    validate_layout()
    parts: Dict[str, cq.Workplane] = {
        "keyboard_tray_left": keyboard_tray_half("left"),
        "keyboard_tray_right": keyboard_tray_half("right"),
        "keyboard_rear_clamp": keyboard_rear_clamp(),
        "phone_cradle_a16": phone_cradle(),
        "phone_clamp_tip_TPU_M4": phone_clamp_tip_tpu(),
        "phone_width_fit_test": phone_width_fit_test(),
        "keyboard_corner_fit_test": keyboard_corner_fit_test(),
        "keyboard_seam_fit_male": keyboard_seam_fit_test("male"),
        "keyboard_seam_fit_female": keyboard_seam_fit_test("female"),
        "hardware_fit_gauge": hardware_fit_gauge(),
        "m4_washer_fit_gauge": m4_washer_fit_gauge(),
        "m3_head_fit_gauge": m3_head_fit_gauge(),
        "m3_insert_fit_gauge": m3_insert_fit_gauge(),
        "m4_horizontal_insert_fit_gauge": m4_horizontal_insert_fit_gauge(),
        "m5_nut_trap_fit_gauge": m5_nut_trap_fit_gauge(),
        "setup_hardware_fit_gauge": setup_hardware_fit_gauge(),
        "thread_pilot_fit_gauge": thread_pilot_fit_gauge(),
        "cable_tie_saddle_fit_gauge": cable_tie_saddle_fit_gauge(),
        "mast_socket_fit_test": mast_socket_fit_test(),
        "tpu_tip_retention_gauge": tpu_tip_retention_gauge(),
        **{f"tag_frame_ID{tag_id}_55mm": tag_frame(tag_id) for tag_id in range(6)},
        "calibration_puck": calibration_puck(),
        "camera_plate_universal": camera_plate(),
        "mast_foot_2020": mast_foot_2020(),
        "compliant_tool_body": compliant_tool_body(),
        "compliant_tool_top_cap": compliant_tool_top_cap(),
        "compliant_tool_grip_fit_test": compliant_tool_grip_fit_test(),
        "spring_fit_gauge": spring_fit_gauge(),
        "stylus_collar_9mm": stylus_collar(),
        "rod_bushing_6_to_9mm": rod_bushing_6_to_9(),
        "keyboard_tip_TPU_6mm": keyboard_tip(),
        "stylus_diameter_gauge": stylus_diameter_gauge(),
    }

    rows = []
    for name, obj in parts.items():
        rows.append(export_part(name, obj))

    # Remove superseded printable exports so the folder remains an exact
    # release set rather than accumulating ambiguous old revisions.
    expected_stls = {STL_DIR / f"{name}.stl" for name in parts}
    expected_steps = {STEP_DIR / f"{name}.step" for name in parts}
    for stale in STL_DIR.glob("*.stl"):
        if stale.name != "BOARD_REFERENCE_DO_NOT_PRINT.stl" and stale not in expected_stls:
            stale.unlink()
    for stale in STEP_DIR.glob("*.step"):
        if stale.name not in {"board_610x457x18_drilled.step", "RoCell_v0_2_full_assembly.step"} and stale not in expected_steps:
            stale.unlink()

    # Optional one-piece keyboard tray for larger-format printers. It is not
    # included in Plus4 validation because it is 325 mm wide and cannot fit
    # the 305 mm bed in any flat orientation.
    full_tray = keyboard_tray_full_large_printer()
    exporters.export(full_tray, str(LARGE_STEP_DIR / "keyboard_tray_full_325mm.step"))
    exporters.export(
        full_tray,
        str(LARGE_STL_DIR / "keyboard_tray_full_325mm.stl"),
        tolerance=0.08,
        angularTolerance=0.08,
    )

    # Board model is CAD-only because it exceeds printer volume.
    board = board_model()
    exporters.export(board, str(STEP_DIR / "board_610x457x18_drilled.step"))
    exporters.export(board, str(STL_DIR / "BOARD_REFERENCE_DO_NOT_PRINT.stl"), tolerance=0.2, angularTolerance=0.2)

    make_assembly(parts)

    (CFG_DIR / "parameters.json").write_text(json.dumps(asdict(P), indent=2), encoding="utf-8")
    (CFG_DIR / "workcell_layout.json").write_text(json.dumps(board_layout_metadata(), indent=2), encoding="utf-8")

    with (ROOT / "PART_VALIDATION.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    row_by_name = {r["part"]: r for r in rows}
    phone_dims = part_dimensions()["phone_outer"]
    phone_row = row_by_name["phone_cradle_a16"]
    if (abs(phone_row["extent_x_mm"] - phone_dims[0]) > 0.1 or
            abs(phone_row["extent_y_mm"] - phone_dims[1]) > 0.1):
        raise SystemExit(
            f"Phone metadata/export mismatch: metadata={phone_dims}, "
            f"mesh=({phone_row['extent_x_mm']}, {phone_row['extent_y_mm']})"
        )

    failures = [
        r for r in rows
        if (not r["watertight"] or not r["winding_consistent"] or
            not r["single_body"] or not r["positive_volume"] or
            not r["fits_plus4_nominal_305x305x280"] or
            not r["fits_plus4_safe_295x295x280"])
    ]
    if failures:
        raise SystemExit(f"Validation failures: {failures}")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
