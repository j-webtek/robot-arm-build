#!/usr/bin/env python3
"""RoCell RC03-INT-R1 parametric CAD generator.

Creates editable STEP, print-ready STL, assembly STEP, board drawings, and metadata.
Units: millimetres.

Default hardware:
- Samsung Galaxy A16 5G bare phone: 164.4 x 77.9 x 7.9 mm
- Perixx PERIBOARD-409 keyboard: 315 x 147 x 21 mm
- QIDI Plus4 nominal build volume: 305 x 305 x 280 mm
- Provisional protected plate envelope: 295 x 295 x 275 mm

RC03 is the printer-only integrated-datum revision.  The structural board carries
the keyboard directly; three indexed printed stations provide datums, retention,
the phone fixture, and the replaceable TCP target without a redundant printed deck.

The phone fixture remains adjustable. Measure any case and edit PARAMS before
regenerating its production station.
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Tuple, List

import cadquery as cq
from cadquery import exporters
import trimesh

ROOT = Path(__file__).resolve().parents[1]
RELEASE_REVISION = "RC03-INT-R1"
STEP_DIR = ROOT / "cad" / "step"
STL_DIR = ROOT / "stl"
LARGE_STEP_DIR = ROOT / "cad" / "step" / "large_printer_optional"
LARGE_STL_DIR = ROOT / "stl_large_printer_optional"
CFG_DIR = ROOT / "config"
DRAW_DIR = ROOT / "drawings"
for d in (STEP_DIR, STL_DIR, LARGE_STEP_DIR, LARGE_STL_DIR, CFG_DIR, DRAW_DIR):
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
    printer_safe_z: float = 275.0

    # RC03 indexed-station interface.  Two board pins locate each master
    # station; the right keyboard station is a slave of the left station and
    # deliberately has no independent board locators.
    station_base_t: float = 4.0
    locator_pin_d: float = 6.0
    locator_pin_length: float = 20.0
    locator_blind_depth: float = 15.0
    locator_pin_protrusion: float = 5.0
    locator_slot_length: float = 10.0
    locator_socket_depth: float = 5.35
    locator_leadin_d: float = 7.2
    locator_leadin_depth: float = 0.8
    keyboard_locator_socket_d: float = 6.2
    keyboard_locator_slot_w: float = 6.2
    phone_locator_socket_d: float = 6.2
    phone_locator_slot_w: float = 6.2
    seam_post_d: float = 8.0
    seam_round_socket_d: float = 8.3
    seam_radial_slot_w: float = 8.3
    seam_slot_length: float = 12.0
    seam_post_h: float = 3.0
    relieved_m4_d: float = 5.6
    phone_m4_nut_ac: float = 7.2
    m4_nut_thickness: float = 3.2

    # Keyboard - Perixx PERIBOARD-409 nominal envelope
    keyboard_w: float = 315.0
    keyboard_d: float = 147.0
    keyboard_h: float = 21.0
    keyboard_clearance: float = 1.0
    keyboard_tray_base_t: float = 4.0
    keyboard_tray_wall_t: float = 4.0
    keyboard_tray_wall_h: float = 7.0
    keyboard_station_y: float = 72.0
    keyboard_station_d: float = 192.0
    keyboard_front_flange_d: float = 12.0
    keyboard_rear_spine_d: float = 31.0

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
    phone_station_m3_insert_pocket_d: float = 4.6
    compliant_tool_m3_insert_pocket_d: float = 4.6
    m3_head_recess_d: float = 6.2
    m4_washer_od: float = 9.2
    m5_washer_od: float = 11.0
    mast_socket_size: float = 20.5
    m5_nut_ac: float = 9.4
    camera_hex_ac: float = 13.2
    zip_tie_slot_w: float = 5.6
    zip_tie_tunnel_h: float = 2.2

    # Workcell layout, board origin = front-left; +X right, +Y rear
    keyboard_x: float = 80.0
    keyboard_y: float = 80.0
    phone_x: float = 480.0
    phone_y: float = 80.0
    calibration_x: float = 411.0
    calibration_y: float = 150.0
    # The 78 mm frame keeps M4 washer tracks completely outside the 55 mm tag
    # artwork while preserving the original tag-center world coordinates.

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


def emboss_text(body: cq.Workplane, text: str, x: float, y: float,
                top_z: float, size: float = 3.2,
                height: float = 0.6) -> cq.Workplane:
    """Add a bold, three-layer diagnostic label to a horizontal top face.

    The 0.05 mm overlap makes every glyph (including decimal points) part of
    the coupon rather than a coincident, disconnected shell.  This helper is
    intentionally separate from ``engrave_text``: production-part markings
    remain recessed, while fit coupons get tactile, shadow-casting labels that
    are reliable with a 0.4 mm nozzle and 0.2 mm layers.
    """
    sink = 0.05
    label = (cq.Workplane("XY").workplane(offset=top_z - sink)
             .center(x, y).text(
                 text, size, height + sink, combine=False,
                 font="Arial", kind="bold",
             ))
    return body.union(label)


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


def locator_socket(body: cq.Workplane, cx: float, cy: float,
                   socket_d: float, slot_width: float,
                   slot_axis: str | None = None) -> cq.Workplane:
    """Cut a blind, bottom-entry station socket for a 6 mm board dowel.

    The first master socket is round.  The second is a capsule elongated only
    along the line between pins, avoiding an overconstrained thermal loop while
    still controlling yaw.  A broad entry taper makes station installation
    possible without looking under the part.
    """
    if slot_axis is None:
        bore = through_hole(
            cx, cy, socket_d, P.locator_socket_depth, z0=0.0,
        )
        entry = cq.Solid.makeCone(
            P.locator_leadin_d / 2,
            socket_d / 2,
            P.locator_leadin_depth,
            cq.Vector(cx, cy, 0), cq.Vector(0, 0, 1),
        )
    else:
        if slot_axis not in {"x", "y"}:
            raise ValueError(f"Unknown locator slot axis: {slot_axis}")
        angle = 0.0 if slot_axis == "x" else 90.0
        bore = slot_solid(
            cx, cy, P.locator_slot_length, slot_width,
            P.locator_socket_depth, angle=angle, z0=0.0,
        )
        entry = slot_solid(
            cx, cy,
            P.locator_slot_length + (P.locator_leadin_d - slot_width),
            P.locator_leadin_d,
            P.locator_leadin_depth,
            angle=angle, z0=0.0,
        ).val()
    return body.cut(bore).cut(cq.Workplane(obj=entry))


def vertical_seam_post(cx: float, cy: float, base_z: float = 0.0) -> cq.Workplane:
    """Tapered vertical printed post carried by the keyboard master tabs."""
    straight_h = max(P.seam_post_h - 0.7, 1.0)
    post = (cq.Workplane("XY").center(cx, cy)
            .circle(P.seam_post_d / 2).extrude(straight_h)
            .translate((0, 0, base_z)))
    tip = cq.Solid.makeCone(
        P.seam_post_d / 2,
        P.seam_post_d / 2 - 0.7,
        P.seam_post_h - straight_h,
        cq.Vector(cx, cy, base_z + straight_h),
        cq.Vector(0, 0, 1),
    )
    return post.union(cq.Workplane(obj=tip))


def seam_socket(body: cq.Workplane, cx: float, cy: float,
                radial_axis: str | None = None) -> cq.Workplane:
    """Cut the slave keyboard station's round/radial master-post receiver."""
    # The front post overlaps the 7 mm datum wall in plan, so the socket must
    # clear the full wall height rather than only the 4 mm station flange.
    h = max(P.station_base_t, P.keyboard_tray_wall_h) + 1.0
    if radial_axis is None:
        cut = through_hole(cx, cy, P.seam_round_socket_d, h, z0=-0.5)
    else:
        angle = 0.0 if radial_axis == "x" else 90.0
        cut = slot_solid(
            cx, cy, P.seam_slot_length, P.seam_radial_slot_w,
            h, angle=angle, z0=-0.5,
        )
    return body.cut(cut)










def keyboard_station(side: str) -> cq.Workplane:
    """RC03 open keyboard datum station.

    The keyboard rests directly on the structural board.  The printed stations
    only establish the front/side datums and carry the serviceable rear clamp,
    so keypress load no longer traverses a redundant PETG tray floor.

    The left station is the board-indexed master.  Its two lap shelves carry a
    round printed post and a Y-relieved post.  The right station drops over
    those posts and has deliberately loose M4 retention holes; this removes the
    four-locator closed loop that would otherwise fight print shrink and board
    drilling error.
    """
    assert side in {"left", "right"}
    pocket_w = P.keyboard_w + 2 * P.keyboard_clearance
    wall = P.keyboard_tray_wall_t
    outer_w = pocket_w + 2 * wall
    half_w = outer_w / 2
    d = P.keyboard_station_d
    base_t = P.station_base_t
    wall_h = P.keyboard_tray_wall_h
    front_d = P.keyboard_front_flange_d
    rear_d = P.keyboard_rear_spine_d
    rear_y = d - rear_d
    device_front_y = P.keyboard_y + wall + P.keyboard_clearance
    local_wall_y = P.keyboard_y - P.keyboard_station_y
    side_rail_d = rear_y - local_wall_y

    # Board-contact structure exists only outside the device footprint.
    body = rounded_plate(half_w, front_d, base_t, r=2.5)
    body = body.union(rounded_plate(
        half_w, rear_d, base_t, r=2.5, x0=0, y0=rear_y,
    ))
    body = body.union(box_ll(
        half_w, wall, wall_h,
        x0=0, y0=local_wall_y, z0=0,
    ))
    side_x = 0.0 if side == "left" else half_w - wall
    body = body.union(box_ll(
        wall, side_rail_d, wall_h,
        x0=side_x, y0=local_wall_y, z0=0,
    ))

    # Two printed lap shelves form the master/slave seam.  The thin shelves sit
    # in underside recesses in the right station while the vertical keys locate
    # XY/yaw.  Board screws only clamp the slave down.
    tab_len = 22.0
    tab_t = 2.0
    tab_root = half_w - 0.8
    front_tab_y, front_tab_d = 2.0, 8.0
    rear_tab_y, rear_tab_d = rear_y + 7.0, 16.0
    seam_x = half_w + tab_len / 2
    front_key_y = front_tab_y + front_tab_d / 2
    rear_key_y = rear_tab_y + rear_tab_d / 2
    if side == "left":
        for ty, td in ((front_tab_y, front_tab_d), (rear_tab_y, rear_tab_d)):
            body = body.union(rounded_plate(
                tab_len + 0.8, td, tab_t, r=1.6,
                x0=tab_root, y0=ty,
            ))
        body = body.union(vertical_seam_post(seam_x, front_key_y, base_z=tab_t))
        body = body.union(vertical_seam_post(seam_x, rear_key_y, base_z=tab_t))
    else:
        # Underside lap clearance: the top skin remains continuous around each
        # socket and visibly confirms that the slave is fully seated.
        lap_clear = 0.30
        for ty, td in ((front_tab_y, front_tab_d), (rear_tab_y, rear_tab_d)):
            # A straight-edged underside recess clears the master's rounded
            # shelf root completely; using another rounded footprint here
            # leaves four tiny crescent collisions at the open seam edge.
            pocket = box_ll(
                tab_len + 1.0,
                td + 2 * lap_clear,
                tab_t + 0.20,
                x0=-0.5, y0=ty - lap_clear, z0=-0.05,
            )
            body = body.cut(pocket)
        body = seam_socket(body, tab_len / 2, front_key_y)
        body = seam_socket(body, tab_len / 2, rear_key_y, radial_axis="y")

    # Two shallow raised tracks guide the replaceable rear clamp without
    # asking its M4 screw to resist yaw.  Matching pockets are molded into the
    # clamp underside.
    clamp_cx = 85.0 if side == "left" else 77.5
    for gx in (clamp_cx - 16.0, clamp_cx + 16.0):
        body = body.union(box_ll(
            3.0, 20.0, 0.8,
            x0=gx - 1.5, y0=rear_y + 5.0, z0=base_t,
        ))

    if side == "left":
        # The locator pads are locally 6 mm thick so the 5 mm board-pin
        # engagement remains blind and the visible top surface stays closed.
        for x in (22.0, half_w - 22.0):
            body = body.union(rounded_plate(
                14.0, front_d, 6.0, r=2.5, x0=x - 7.0, y0=0,
            ))
        body = locator_socket(
            body, 22.0, 6.0,
            P.keyboard_locator_socket_d, P.keyboard_locator_slot_w,
        )
        body = locator_socket(
            body, half_w - 22.0, 6.0,
            P.keyboard_locator_socket_d, P.keyboard_locator_slot_w,
            slot_axis="x",
        )
        holds = (
            (85.0, 6.0, P.m4_clearance, True),
            (22.0, 174.0, P.m4_clearance, True),
            (85.0, 182.5, P.m4_clearance, False),
        )
    else:
        # Slave holes are intentionally relieved; seam posts own XY/yaw.
        holds = (
            (half_w / 2, 6.0, P.relieved_m4_d, True),
            (half_w - 22.0, 174.0, P.relieved_m4_d, True),
            (77.5, 182.5, P.relieved_m4_d, False),
        )

    for x, y, dia, washer in holds:
        body = body.cut(through_hole(x, y, dia, base_t + 2.0, z0=-0.5))
        if washer:
            seat_d = P.m4_washer_od if side == "left" else P.m4_washer_od + 1.0
            body = body.cut(washer_hole_relief(x, y, seat_d, base_t, depth=0.6))

    label = "RC03-L MASTER" if side == "left" else "RC03-R SLAVE"
    body = engrave_text(
        body, label, half_w / 2, d - 5.0, base_t,
        size=2.7, depth=0.35,
    )
    # The calculation documents the direct-support nominal device front even
    # though no printed solid is allowed to extend beneath it.
    assert abs(device_front_y - 85.0) < 1e-6
    return body.clean()


def keyboard_rear_clamp() -> cq.Workplane:
    """Replaceable, guided RC03 rear clamp; two copies serve the keyboard."""
    w, d, bt, face_h = 52.0, 32.0, 4.0, 17.0
    body = rounded_plate(w, d, bt, r=3)
    # The face begins at the clamp underside.  Installed on the 4 mm rear
    # spine it contacts the keyboard from Z=4 through Z=21, its full height.
    body = body.union(box_ll(w, 4.0, face_h, x0=0, y0=0, z0=0))
    # Face pad recess.
    body = body.cut(box_ll(w - 10, 0.8, 10.0, x0=5, y0=-0.01, z0=5.0))
    # Three support-free triangular ribs transfer clamp force into the base and
    # reduce layer-line peel at the vertical-face root.
    for x0 in (6.0, 24.0, 42.0):
        gusset = (cq.Workplane("YZ").polyline([
            (4.0, bt), (14.0, bt), (4.0, bt + 11.0)
        ]).close().extrude(4.0).translate((x0, 0, 0)))
        body = body.union(gusset)
    # Pockets accept the station's raised guide tracks.  They preserve a broad
    # flat seating plane and are open at neither end.  In the installed datum
    # position the tracks span clamp-local Y=6..26 mm, so each pocket provides
    # 0.5 mm end clearance without leaving a hidden solid overlap.
    for gx in (10.0, 42.0):
        body = body.cut(box_ll(
            3.5, 21.0, 1.0,
            x0=gx - 1.75, y0=5.5, z0=-0.05,
        ))
    # Long board slot allows measured forward pressure adjustment.  Its
    # nominal centre reproduces the retained RC02 board coordinate at Y=254.5.
    body = body.cut(slot_solid(w / 2, 22.5, 18.0, P.m4_clearance, bt + 2, angle=90))
    body = body.cut(washer_slot_relief(
        w / 2, 22.5, 18.0, P.m4_clearance, P.m4_washer_od, bt,
        angle=90, depth=0.6,
    ))
    body = add_slot_scale(
        body, w / 2, 22.5, 18.0, P.m4_clearance,
        P.m4_washer_od, bt, axis="y", side=1,
    )
    body = engrave_text(body, "KB R3", w / 2, 28.0, bt, size=2.8)
    return body.clean()




def phone_tcp_station() -> cq.Workplane:
    """RC03 conjoined phone/TCP master station.

    The legacy phone fit coordinates and two corner clamp axes are preserved,
    while the four mounting ears and separate 60 mm puck are replaced by one
    board-indexed skeleton.  A removable right clamp rail carries all nut wear;
    a keyed 30 mm target cartridge carries all TCP contact wear.
    """
    device_w = P.phone_w + P.phone_case_extra_w
    device_l = P.phone_l + P.phone_case_extra_l
    device_t = P.phone_t + P.phone_case_extra_t
    fit_w = device_w + 2 * P.phone_clearance
    fit_l = device_l + 2 * P.phone_clearance
    wall = 3.2
    bt = P.station_base_t
    rail_h = min(max(device_t * 0.75, 6.0), 13.0)
    frame_w = fit_w + 2 * wall
    frame_l = fit_l + 2 * wall

    # Module-local coordinates.  World origin is the legacy calibration-puck
    # origin (411,80 for station X/Y); the fixed phone frame starts at X=495.
    station_x = P.calibration_x
    station_y = P.phone_y
    legacy_phone_local_x = P.phone_x - station_x
    frame_x = legacy_phone_local_x + 15.0
    tower_x = frame_x + frame_w - wall
    module_w = P.phone_x + part_dimensions()["phone_outer"][0] - station_x

    # Earless phone skeleton with the same broad rear-camera relief.
    body = rounded_plate(frame_w, frame_l, bt, r=6, x0=frame_x, y0=0)
    inner_cut = rounded_plate(
        fit_w - 18.0, fit_l - 22.0, bt + 2.0, r=7,
        x0=frame_x + wall + 9.0, y0=wall + 11.0,
    ).translate((0, 0, -0.5))
    body = body.cut(inner_cut)
    body = body.union(box_ll(
        wall, fit_l + 2 * wall, rail_h,
        x0=frame_x, y0=0, z0=bt,
    ))
    body = body.union(box_ll(
        frame_w - wall, wall, rail_h,
        x0=frame_x, y0=frame_l - wall, z0=bt,
    ))
    keeper = 24.0
    body = body.union(box_ll(
        keeper, wall, rail_h, x0=frame_x, y0=0, z0=bt,
    ))
    body = body.union(box_ll(
        keeper - wall, wall, rail_h,
        x0=frame_x + frame_w - keeper, y0=0, z0=bt,
    ))
    cam_relief = box_ll(
        fit_w + 1.0, 68.0, bt + 2.0,
        x0=frame_x + wall - 0.5,
        y0=frame_l - wall - 68.0,
        z0=-0.5,
    )
    body = body.cut(cam_relief)

    # Full support strip for the replaceable clamp rail.  It overlaps the
    # frame's right edge by one wall thickness and remains part of the master.
    # Begin the extension with a deliberate 0.2 mm overlap into the phone base
    # (rather than at the right-wall tangent) to avoid a non-manifold seam in
    # the tessellated STL.
    support_x = frame_x + frame_w - 0.2
    body = body.union(box_ll(
        module_w - support_x, frame_l, bt,
        x0=support_x, y0=0, z0=0,
    ))

    # Integrated TCP island: former 60 x 60 footprint, raised to 10.5 mm so a
    # 4 mm replaceable insert can sit over full-depth 6.2 mm M3 heat-set pockets.
    island_y = P.calibration_y - station_y
    island_h = 10.5
    body = body.union(rounded_plate(
        60.0, 60.0, island_h, r=5.0, x0=0, y0=island_y,
    ))

    # A 15 mm locator spine and two broad bridges make the fixture one body
    # without filling the free cable/camera space between phone and target.
    locator_spine_x = legacy_phone_local_x
    body = body.union(rounded_plate(
        frame_x - locator_spine_x, 132.0, bt, r=2.5,
        x0=locator_spine_x, y0=20.0,
    ))
    for by in (island_y + 2.0, island_y + 44.0):
        body = body.union(rounded_plate(
            frame_x - 60.0, 14.0, bt, r=2.5,
            x0=60.0, y0=by,
        ))

    # Local master locator pads and sockets.  The second socket is relieved in
    # Y, the pin-to-pin axis, so it controls X/yaw without axial overconstraint.
    locator_x = P.phone_x + 7.5 - station_x
    locator_ys = (115.0 - station_y, 217.8 - station_y)
    for y in locator_ys:
        body = body.union(rounded_plate(
            14.0, 14.0, 6.0, r=2.5,
            x0=locator_x - 7.0, y0=y - 7.0,
        ))
    body = locator_socket(
        body, locator_x, locator_ys[0],
        P.phone_locator_socket_d, P.phone_locator_slot_w,
    )
    body = locator_socket(
        body, locator_x, locator_ys[1],
        P.phone_locator_socket_d, P.phone_locator_slot_w,
        slot_axis="y",
    )

    # Keyed 30.4 mm target pocket with a clipped +X/+Y corner.  The insert top
    # is flush with the island; the clipped corner makes 90-degree mistakes
    # impossible.
    target_cx, target_cy = 30.0, island_y + 30.0
    ph = 15.2
    clip = 6.4
    pocket_pts = [
        (target_cx - ph, target_cy - ph),
        (target_cx + ph, target_cy - ph),
        (target_cx + ph, target_cy + ph - clip),
        (target_cx + ph - clip, target_cy + ph),
        (target_cx - ph, target_cy + ph),
    ]
    pocket = (cq.Workplane("XY").polyline(pocket_pts).close()
              .extrude(4.05).translate((0, 0, island_h - 4.0)))
    body = body.cut(pocket)
    insert_floor_z = island_h - 4.0
    for x, y in ((target_cx - 10.0, target_cy - 10.0),
                 (target_cx + 10.0, target_cy + 10.0)):
        body = body.cut(cq.Workplane("XY").center(x, y)
                        .circle(P.phone_station_m3_insert_pocket_d / 2).extrude(6.2)
                        .translate((0, 0, insert_floor_z - 6.2)))
        body = body.cut(vertical_insert_leadin(
            x, y, P.phone_station_m3_insert_pocket_d, insert_floor_z,
        ))

    # Three broad-triangle retention points: one on the target island and two
    # through the replaceable phone rail.  Pins own XY; these screws only clamp.
    # The TCP island retains its 10.5 mm height for the 6.2 mm insert pockets,
    # but its washer sits in a 1.5 mm counterbore.  The resulting 9.0 mm
    # effective M4 stack preserves at least 5 mm nominal engagement for the
    # candidate M4x25/10 mm board-insert architecture across the released board
    # thickness range; physical stack gauging remains mandatory.
    retention = (
        (423.0 - station_x, 160.0 - station_y, island_h, True),
        (588.8 - station_x, 149.12 - station_y, bt, False),
        (588.8 - station_x, 192.32 - station_y, bt, False),
    )
    for x, y, top_z, washer in retention:
        body = body.cut(through_hole(
            x, y, P.m4_clearance, top_z + 2.0, z0=-0.5,
        ))
        if washer:
            body = body.cut(washer_hole_relief(
                x, y, P.m4_washer_od, top_z, depth=1.5,
            ))

    # Raised keys locate the service rail; its two board screws provide clamp
    # force.  Key pockets, not screw clearance, react phone clamp side-load.
    rail_key_x = 588.8 - station_x
    # Keep each shear key clear of its neighbouring M4 retention passage.
    # The former rear-key centre at Y=120.0 overlapped PT-HOLD-R2 by 1.62 mm
    # in plan, leaving 4.34 mm^3 of exact-solid interference after the key was
    # united to the station.  Y=126.0 preserves a 4.0 mm edge-to-edge gap.
    for y in (56.0, 126.0):
        body = body.union(box_ll(
            6.0, 14.0, 1.2,
            x0=rail_key_x - 3.0, y0=y - 7.0, z0=bt,
        ))

    body = engrave_text(body, "USB", frame_x + frame_w / 2, 11.8, bt, size=3.0)
    body = engrave_text(body, "TOP", frame_x + frame_w / 2, frame_l - 7.0, bt, size=3.0)
    body = engrave_text(body, "TCP R3", 30.0, island_y + 55.0, island_h, size=2.5)
    body = engrave_text(body, "RC03 PHONE+TCP", 30.0, island_y + 5.5, island_h, size=2.1)
    return body.clean()


def horizontal_hex_cavity_yz(cx: float, cy: float, cz: float,
                             across_flats: float, thickness: float) -> cq.Workplane:
    """Nut cavity with its hex face in YZ and thread axis along X."""
    radius = across_flats / math.sqrt(3.0)
    return (cq.Workplane("YZ").center(cy, cz).polygon(6, 2 * radius)
            .extrude(thickness).translate((cx, 0, 0)))


def top_loaded_horizontal_nut_channel_yz(
    cx: float,
    cy: float,
    axis_z: float,
    across_flats: float,
    nut_thickness: float,
    tower_height: float,
) -> cq.Workplane:
    """Tight top-loaded M4 nut channel with a positive lower-half hex seat.

    The old channel cut a loose rectangle through nearly the whole hex pocket,
    so its advertised across-flats value was not the retaining width and the
    nut could sit below the screw axis.  Here the lower half of a flat-bottomed
    hex remains intact and locates the thread exactly on ``axis_z``.  The upper
    chute is wide enough for the nut's corners, while the final seat and shallow
    X clearance prevent rotation and excessive fore/aft float.
    """
    radius = across_flats / math.sqrt(3.0)
    pocket_depth = nut_thickness + 0.15
    chute_width = 2.0 * radius + 0.20
    channel = horizontal_hex_cavity_yz(
        cx - pocket_depth / 2.0,
        cy,
        axis_z,
        across_flats,
        pocket_depth,
    )
    channel = channel.union(box_ll(
        pocket_depth,
        chute_width,
        tower_height - axis_z + 0.10,
        x0=cx - pocket_depth / 2.0,
        y0=cy - chute_width / 2.0,
        z0=axis_z,
    ))
    # Short generous mouth makes top loading easy without loosening the seat.
    lead_in_h = 0.8
    channel = channel.union(box_ll(
        pocket_depth + 0.50,
        chute_width + 0.50,
        lead_in_h + 0.10,
        x0=cx - (pocket_depth + 0.50) / 2.0,
        y0=cy - (chute_width + 0.50) / 2.0,
        z0=tower_height - lead_in_h,
    ))
    return channel


def phone_clamp_rail() -> cq.Workplane:
    """Replaceable right keeper and two-nut phone clamp rail.

    The part installs on top of the station's 4 mm support strip.  Its M4 clamp
    axes therefore remain at board Z=8 mm even though the rail is separate.
    Top-loading captive nuts replace heat-set inserts, making field repair a
    cool, reversible operation.
    """
    device_t = P.phone_t + P.phone_case_extra_t
    fit_l = P.phone_l + P.phone_case_extra_l + 2 * P.phone_clearance
    wall = 3.2
    frame_l = fit_l + 2 * wall
    w = part_dimensions()["phone_outer"][0] - (15.0 + (P.phone_w + P.phone_case_extra_w + 2 * P.phone_clearance + 2 * wall) - wall)
    bt = P.station_base_t
    rail_h = min(max(device_t * 0.75, 6.0), 13.0)
    total_h = 16.0
    body = rounded_plate(w, frame_l, bt, r=2.5)

    # Right corner keepers are part of the service rail, not the master.
    body = body.union(box_ll(wall, 25.0, rail_h, x0=0, y0=0, z0=0))
    body = body.union(box_ll(
        wall, 25.0, rail_h, x0=0, y0=frame_l - 25.0, z0=0,
    ))

    tower_d = 24.0
    clamp_ys = (30.0, frame_l - 30.0)
    # A 4.0 mm screw axis leaves a 0.4 mm floor below the selected 7.2 mm
    # flat-bottom hex seat and remains centred on the nominal 7.9 mm phone.
    clamp_z = 4.0
    nut_cx = w - 5.0
    for cy in clamp_ys:
        body = body.union(rounded_plate(
            w, tower_d, total_h, r=2.5,
            x0=0, y0=cy - tower_d / 2,
        ))
        passage = (cq.Workplane("YZ").center(cy, clamp_z)
                   .circle(P.m4_clearance / 2).extrude(w + 4.0)
                   .translate((-2.0, 0, 0)))
        body = body.cut(passage)
        body = body.cut(top_loaded_horizontal_nut_channel_yz(
            nut_cx,
            cy,
            clamp_z,
            P.phone_m4_nut_ac,
            P.m4_nut_thickness,
            total_h,
        ))
        body = engrave_text(body, "NUT", w / 2, cy, total_h, size=2.1, depth=0.3)

    # Two underside pockets mate with station keys before the shared board
    # screws are tightened.
    bolt_x = 588.8 - (P.phone_x + 15.0 + (P.phone_w + P.phone_case_extra_w + 2 * P.phone_clearance + 2 * wall) - wall)
    # These pocket centres must match the station keys above.  The rear key is
    # intentionally displaced from PT-HOLD-R2 so the screw and key have
    # independent, printable load paths.
    for y in (56.0, 126.0):
        body = body.cut(box_ll(
            6.4, 14.4, 1.4,
            x0=bolt_x - 3.2, y0=y - 7.2, z0=-0.05,
        ))
    for y in (69.12, 112.32):
        body = body.cut(through_hole(bolt_x, y, P.m4_clearance, bt + 2.0, z0=-0.5))
        body = body.cut(washer_hole_relief(
            bolt_x, y, P.m4_washer_od, bt, depth=0.6,
        ))
    # Raised cable-tie saddle lives on the replaceable rail, outside the phone
    # fit envelope.  The earlier station-side placement intruded 7 mm beneath
    # the configured phone and also collided with this rail.
    saddle_w, saddle_d, saddle_h = 10.0, 10.0, 4.0
    saddle = box_ll(saddle_w, saddle_d, saddle_h, x0=0.0, y0=2.0, z0=bt)
    tunnel = box_ll(
        P.zip_tie_slot_w, 12.0, P.zip_tie_tunnel_h,
        x0=(saddle_w - P.zip_tie_slot_w) / 2,
        y0=1.0, z0=bt + 0.8,
    )
    body = body.union(saddle).cut(tunnel)
    body = engrave_text(body, "RC03 CLAMP RAIL", w / 2, frame_l / 2, bt, size=1.8)
    return body.clean()


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
    # Keep raised text completely outside the phone support channel.  The tab
    # overlaps the left wall by 1 mm, so it prints as one robust body without
    # changing the tested channel width or either datum wall.
    label_tab_w = 24.0
    body = body.union(rounded_plate(
        label_tab_w, 22.0, bt, r=3.0, x0=1.0 - label_tab_w, y0=7.0,
    ))
    body = emboss_text(body, "PHONE", 1.0 - label_tab_w / 2, 22.0, bt, size=3.2)
    body = emboss_text(
        body, f"FIT {fit_w:.1f}", 1.0 - label_tab_w / 2, 14.0, bt, size=3.0,
    )
    return body.clean()


def keyboard_corner_fit_test() -> cq.Workplane:
    """Small coupon reproducing keyboard front/side datum clearance only."""
    bt = P.keyboard_tray_base_t
    wall = P.keyboard_tray_wall_t
    h = P.keyboard_tray_wall_h
    size = 58.0
    body = rounded_plate(size, size, bt, r=4)
    body = body.union(box_ll(size, wall, h, 0, 0, bt))
    body = body.union(box_ll(wall, size, h, 0, 0, bt))
    body = body.cut(rounded_plate(30, 30, bt + 1, r=3, x0=15, y0=15).translate((0,0,-0.5)))
    # A front-side label tab keeps the raised legend outside the keyboard
    # footprint and both datum faces.  The tested corner geometry is unchanged.
    body = body.union(rounded_plate(
        50.0, 11.0, bt, r=3.0, x0=4.0, y0=-10.0,
    ))
    body = emboss_text(body, "FRONT LEFT", size / 2, -4.5, bt, size=3.5)
    return body.clean()


def hardware_fit_gauge() -> cq.Workplane:
    """M3/M4/M5 clearance-hole ladder for the selected production profile."""
    w, d, h = 160.0, 30.0, 6.0
    body = rounded_plate(w, d, h, r=4)
    hole_diameters = (3.2, 3.4, 3.6, 4.4, 4.6, 4.8, 5.3, 5.5, 5.7)
    for index, dia in enumerate(hole_diameters):
        x = 15.0 + index * 16.25
        body = body.cut(through_hole(x, 16.0, dia, h + 2))
        body = emboss_text(body, f"D{dia:.1f}", x, 4.5, h, size=3.2)
    return body.clean()


def m4_washer_fit_gauge() -> cq.Workplane:
    """Compact M4 washer-track ladder for profile-specific qualification."""
    w, d, h = 78.0, 30.0, 6.0
    body = rounded_plate(w, d, h, r=4)
    for x, diameter in zip((14.0, 39.0, 64.0), (8.8, 9.2, 9.6)):
        body = body.cut(through_hole(x, 17.0, P.m4_clearance, h + 2))
        body = body.cut(through_hole(x, 17.0, diameter, 0.7, z0=h - 0.6))
        body = emboss_text(body, f"OD{diameter:.1f}", x, 5.0, h, size=3.1)
    return body.clean()


def m3_head_fit_gauge() -> cq.Workplane:
    """Compact M3 head-recess ladder matching the keyed tool cap."""
    w, d, h = 78.0, 30.0, 6.0
    body = rounded_plate(w, d, h, r=4)
    for x, diameter in zip((14.0, 39.0, 64.0), (5.8, 6.2, 6.6)):
        body = body.cut(through_hole(x, 17.0, P.m3_clearance, h + 2))
        body = body.cut(through_hole(x, 17.0, diameter, 2.1, z0=h - 2.0))
        body = emboss_text(body, f"H{diameter:.1f}", x, 5.0, h, size=3.2)
    return body.clean()


def phone_m3_insert_fit_gauge() -> cq.Workplane:
    """Phone-station M3 ladder with the production 0.3 mm pocket floor."""
    w, d, h = 78.0, 30.0, 6.5
    body = rounded_plate(w, d, h, r=4)
    for x, dia in zip((14.0, 39.0, 64.0), (4.3, 4.6, 4.9)):
        body = body.cut(cq.Workplane("XY").center(x, d / 2)
                        .circle(dia / 2).extrude(6.2).translate((0, 0, h - 6.2)))
        body = body.cut(vertical_insert_leadin(x, d / 2, dia, h))
        body = emboss_text(body, f"M3 {dia:.1f}", x, 5.0, h, size=3.0)
    body = emboss_text(body, "FLOOR 0.3", w / 2, 25.0, h, size=3.0)
    return body.clean()


def tool_m3_insert_fit_gauge() -> cq.Workplane:
    """Tool-body M3 ladder reproducing the two 5 mm edge ligaments."""
    w, d, h = 78.0, 26.0, 8.0
    body = None
    pad_origins = (0.0, 29.0, 58.0)
    for x0 in pad_origins:
        pad = rounded_plate(20.0, 20.0, h, r=3.0, x0=x0, y0=0.0)
        body = pad if body is None else body.union(pad)
    body = body.union(box_ll(w, 8.0, h, x0=0.0, y0=18.0))
    for x0, dia in zip(pad_origins, (4.3, 4.6, 4.9)):
        x, y = x0 + 5.0, 5.0
        body = body.cut(cq.Workplane("XY").center(x, y)
                        .circle(dia / 2).extrude(6.2).translate((0, 0, h - 6.2)))
        body = body.cut(vertical_insert_leadin(x, y, dia, h))
        body = emboss_text(body, f"M3 {dia:.1f}", x0 + 10.0, 14.0, h, size=3.0)
    body = emboss_text(body, "EDGE 5", w / 2, 23.0, h, size=3.0)
    return body.clean()


def station_locator_fit_gauge() -> cq.Workplane:
    """Profile-specific fit ladder for RC03 board and seam locators."""
    w, d, h = 160.0, 84.0, 7.0
    body = rounded_plate(w, d, h, r=4)
    xs = (30.0, 80.0, 130.0)
    board_round_candidates = (6.1, 6.2, 6.3)
    board_slot_candidates = (6.1, 6.2, 6.3)
    seam_round_candidates = (8.2, 8.3, 8.4)
    seam_slot_candidates = (8.2, 8.3, 8.4)
    for x, dia in zip(xs, board_round_candidates):
        body = body.cut(through_hole(x, 14.0, dia, h + 2.0, z0=-0.5))
        body = emboss_text(body, f"BOARD-R {dia:.1f}", x, 5.0, h, size=3.2)
    for x, width in zip(xs, board_slot_candidates):
        body = body.cut(slot_solid(
            x, 29.0, P.locator_slot_length, width,
            h + 2.0, angle=0.0, z0=-0.5,
        ))
        body = emboss_text(body, f"BOARD-S {width:.1f}", x, 39.0, h, size=3.2)
    for x, dia in zip(xs, seam_round_candidates):
        body = body.cut(through_hole(x, 53.0, dia, h + 2.0, z0=-0.5))
        body = emboss_text(body, f"SEAM-R {dia:.1f}", x, 44.0, h, size=3.2)
    for x, width in zip(xs, seam_slot_candidates):
        body = body.cut(slot_solid(
            x, 69.0, P.seam_slot_length, width,
            h + 2.0, angle=90.0, z0=-0.5,
        ))
        body = emboss_text(body, f"SEAM-S {width:.1f}", x, 79.0, h, size=3.2)
    return body.clean()


def m4_captive_nut_fit_gauge() -> cq.Workplane:
    """Horizontal-axis, top-loaded M4 nut ladder matching the clamp rail."""
    w, d, bt, total_h = 26.0, 90.0, 4.0, 16.0
    body = rounded_plate(w, d, bt, r=3)
    specs = ((15.0, 7.2), (45.0, 7.4), (75.0, 7.6))
    axis_z = 4.0
    nut_cx = w - 5.0
    for cy, ac in specs:
        body = body.union(rounded_plate(
            w, 24.0, total_h, r=2.5, x0=0, y0=cy - 12.0,
        ))
        passage = (cq.Workplane("YZ").center(cy, axis_z)
                   .circle(P.m4_clearance / 2).extrude(w + 4.0)
                   .translate((-2.0, 0, 0)))
        body = body.cut(passage)
        body = body.cut(horizontal_hex_cavity_yz(
            nut_cx - P.m4_nut_thickness / 2,
            cy, axis_z, ac, P.m4_nut_thickness + 0.25,
        ))
        entry_z0 = max(axis_z - ac / 2 - 0.2, 0.2)
        body = body.cut(box_ll(
            P.m4_nut_thickness + 0.35,
            ac + 0.35,
            total_h - entry_z0 + 0.2,
            x0=nut_cx - (P.m4_nut_thickness + 0.35) / 2,
            y0=cy - (ac + 0.35) / 2,
            z0=entry_z0,
        ))
        # The nut entry is on the right side of each tower; the centered label
        # ends before that entry and therefore cannot obstruct insertion.
        body = emboss_text(body, f"N{ac:.1f}", w / 2, cy, total_h, size=3.2)
    return body.clean()


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
            body = emboss_text(
                body, f"{prefix} {diameter:.1f}", x, y - 8.5, h, size=2.8,
            )
    return body.clean()


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
        body = emboss_text(body, f"T{width:.1f}", x + 7.0, 5.0, bt, size=3.2)
    return body.clean()


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
    body = emboss_text(body, "M4", 11.0, 4.0, h, size=3.2)
    body = emboss_text(body, "D6", 27.0, 4.0, h, size=3.2)
    return body.clean()




def tag_application_frame() -> cq.Workplane:
    """Reusable 55 mm direct-tag placement frame; never installed on board."""
    outer, opening, h = 75.0, 55.3, 2.4
    body = rounded_plate(outer, outer, h, r=4)
    # The controlled tag tile is a true 55 x 55 mm square.  A rounded aperture
    # collides with its corners even when the side clearance is correct, so the
    # opening is square and provides 0.15 mm nominal clearance per side.
    body = body.cut(box_ll(
        opening, opening, h + 2.0,
        x0=(outer - opening) / 2,
        y0=(outer - opening) / 2,
        z0=-0.5,
    ))
    # Centre notches align the frame to pencil/printed crosshairs while leaving
    # the adhesive tile fully accessible inside the opening.
    notch_w, notch_d = 1.0, 5.0
    for x, y, w, d in (
        (outer / 2 - notch_w / 2, -0.1, notch_w, notch_d),
        (outer / 2 - notch_w / 2, outer - notch_d + 0.1, notch_w, notch_d),
        (-0.1, outer / 2 - notch_w / 2, notch_d, notch_w),
        (outer - notch_d + 0.1, outer / 2 - notch_w / 2, notch_d, notch_w),
    ):
        body = body.cut(box_ll(w, d, h + 1.0, x0=x, y0=y, z0=-0.5))
    body = engrave_text(body, "+Y / REAR", outer / 2, outer - 4.5, h, size=2.6)
    body = engrave_text(body, "55 mm DIRECT", outer / 2, 4.5, h, size=2.3)
    return body.clean()


def calibration_puck() -> cq.Workplane:
    """Keyed 30 mm service cartridge for the integrated TCP island."""
    w, d, h, clip = 30.0, 30.0, 4.0, 6.0
    pts = [(0, 0), (w, 0), (w, d - clip), (w - clip, d), (0, d)]
    body = cq.Workplane("XY").polyline(pts).close().extrude(h)
    # Split crosshair continues the island's outer witness marks.
    body = body.cut(box_ll(
        24.0, 0.8, 0.8, x0=3.0, y0=d / 2 - 0.4, z0=h - 0.8,
    ))
    body = body.cut(box_ll(
        0.8, 24.0, 0.8, x0=w / 2 - 0.4, y0=3.0, z0=h - 0.8,
    ))
    cone_solid = cq.Solid.makeCone(
        2.2, 0.3, 3.0,
        cq.Vector(w / 2, d / 2, h - 3.0), cq.Vector(0, 0, 1),
    )
    body = body.cut(cq.Workplane(obj=cone_solid))
    for x, y in ((5.0, 5.0), (25.0, 25.0)):
        body = body.cut(through_hole(x, y, P.m3_clearance, h + 2.0, z0=-0.5))
        body = body.cut(through_hole(
            x, y, P.m3_head_recess_d, 2.1, z0=h - 2.0,
        ))
    body = engrave_text(body, "R3", 23.0, 5.0, h, size=2.0, depth=0.3)
    return body.clean()


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
        body = body.cut(slot_solid(
            x, 34.0, 24, P.zip_tie_slot_w, h + 2, angle=90,
        ))
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
                        .circle(P.compliant_tool_m3_insert_pocket_d / 2).extrude(6.2).translate((0, 0, h - 6.2)))
        body = body.cut(vertical_insert_leadin(x, y, P.compliant_tool_m3_insert_pocket_d, h))
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
    bore in Parameters after using the supplied diameter gauge.  Retention is a
    measured sliding/interference fit; if needed, use only a plastics-compatible
    removable retaining compound.  A thin-wall radial screw pilot is unsafe and
    is deliberately absent in RC03.
    """
    od, h = 13.6, 5.5
    bore = P.stylus_nominal_d + 0.25
    body = cq.Workplane("XY").circle(od / 2).extrude(h)
    body = body.cut(cq.Workplane("XY").circle(bore / 2).extrude(h + 2).translate((0, 0, -1)))
    body = body.cut(box_ll(1.2, od / 2 + 1.0, h + 2, x0=-0.6, y0=0, z0=-1))
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
    """Structural board with four blind locator bores and nine M4 retainers."""
    body = rounded_plate(P.board_w, P.board_d, P.board_t, r=3)
    for feature in board_features():
        x, y = feature["board_xy"]
        if feature["type"] == "locator_pin_blind":
            depth = feature["depth"]
            bore = (cq.Workplane("XY").center(x, y)
                    .circle(feature["diameter"] / 2)
                    .extrude(depth + 0.1)
                    .translate((0, 0, P.board_t - depth)))
            body = body.cut(bore)
        else:
            body = body.cut(through_hole(
                x, y, feature["diameter"], P.board_t + 2.0,
            ))
    return body.clean()


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
        "keyboard_station_left": (kb_outer_w / 2 + 22.0, P.keyboard_station_d),
        "keyboard_station_right": (kb_outer_w / 2, P.keyboard_station_d),
        "phone_tcp_station": (round(P.phone_x + phone_outer_w - P.calibration_x, 3), phone_frame_l),
        "phone_clamp_rail": (
            phone_outer_w - (15.0 + phone_frame_w - 3.2), phone_frame_l,
        ),
    }


def direct_tag_centers() -> Dict[str, Tuple[float, float]]:
    """Detection centers retained exactly from RC02."""
    return {
        "T0": (47.0, 40.0),
        "T1": (440.0, 40.0),
        "T2": (47.0, 410.0),
        "T3": (563.0, 410.0),
        "K0": (324.0, 309.0),
        "P0": (459.0, 309.0),
    }


def _feature(feature_id: str, feature_type: str, station: str,
             board_xy: Tuple[float, float], local_xy: Tuple[float, float],
             diameter: float, **extra: object) -> dict:
    row = {
        "id": feature_id,
        "type": feature_type,
        "station": station,
        "board_xy": list(board_xy),
        "local_xy": list(local_xy),
        "x": board_xy[0],
        "y": board_xy[1],
        "diameter": diameter,
    }
    row.update(extra)
    return row


def board_features() -> List[dict]:
    """Authoritative RC03 board feature table (4 locators + 9 retainers)."""
    features = [
        _feature(
            "KBL-LOC-ROUND", "locator_pin_blind", "keyboard_left",
            (102.0, 78.0), (22.0, 6.0), P.locator_pin_d,
            depth=P.locator_blind_depth,
            protrusion=P.locator_pin_protrusion,
            interface="round",
            slot_axis=None,
            instruction="6 mm blind bore, 15 mm deep; epoxy 6x20 dowel with 5 mm projection",
        ),
        _feature(
            "KBL-LOC-RADIAL", "locator_pin_blind", "keyboard_left",
            (220.5, 78.0), (140.5, 6.0), P.locator_pin_d,
            depth=P.locator_blind_depth,
            protrusion=P.locator_pin_protrusion,
            interface="radial_slot",
            slot_axis="x",
            instruction="6 mm blind bore, 15 mm deep; station socket relieves X axis",
        ),
        _feature(
            "KBL-HOLD-F", "m4_retention_through", "keyboard_left",
            (165.0, 78.0), (85.0, 6.0), P.m4_clearance,
            station_clearance_d=P.m4_clearance,
            instruction="M4 through retention; washer/hand knob above, threaded anchor below",
        ),
        _feature(
            "KBL-HOLD-R", "m4_retention_through", "keyboard_left",
            (102.0, 246.0), (22.0, 174.0), P.m4_clearance,
            station_clearance_d=P.m4_clearance,
            instruction="M4 through retention; washer/hand knob above, threaded anchor below",
        ),
        _feature(
            "KBL-CLAMP", "m4_retention_through", "keyboard_left",
            (165.0, 254.5), (85.0, 182.5), P.m4_clearance,
            station_clearance_d=P.m4_clearance,
            instruction="Shared station retention and adjustable rear-clamp hand knob",
        ),
        _feature(
            "KBR-HOLD-F", "m4_retention_through", "keyboard_right",
            (323.75, 78.0), (81.25, 6.0), P.m4_clearance,
            station_clearance_d=P.relieved_m4_d,
            interface="relieved_clamp_only",
            instruction="M4 through retention; 5.6 mm station relief, seam owns XY/yaw",
        ),
        _feature(
            "KBR-HOLD-R", "m4_retention_through", "keyboard_right",
            (383.0, 246.0), (140.5, 174.0), P.m4_clearance,
            station_clearance_d=P.relieved_m4_d,
            interface="relieved_clamp_only",
            instruction="M4 through retention; 5.6 mm station relief, seam owns XY/yaw",
        ),
        _feature(
            "KBR-CLAMP", "m4_retention_through", "keyboard_right",
            (320.0, 254.5), (77.5, 182.5), P.m4_clearance,
            station_clearance_d=P.relieved_m4_d,
            interface="relieved_clamp_only",
            instruction="Shared slave-station retention and adjustable rear-clamp hand knob",
        ),
        _feature(
            "PT-LOC-ROUND", "locator_pin_blind", "phone_tcp",
            (487.5, 115.0), (76.5, 35.0), P.locator_pin_d,
            depth=P.locator_blind_depth,
            protrusion=P.locator_pin_protrusion,
            interface="round",
            slot_axis=None,
            instruction="6 mm blind bore, 15 mm deep; epoxy 6x20 dowel with 5 mm projection",
        ),
        _feature(
            "PT-LOC-RADIAL", "locator_pin_blind", "phone_tcp",
            (487.5, 217.8), (76.5, 137.8), P.locator_pin_d,
            depth=P.locator_blind_depth,
            protrusion=P.locator_pin_protrusion,
            interface="radial_slot",
            slot_axis="y",
            instruction="6 mm blind bore, 15 mm deep; station socket relieves Y axis",
        ),
        _feature(
            "PT-HOLD-TCP", "m4_retention_through", "phone_tcp",
            (423.0, 160.0), (12.0, 80.0), P.m4_clearance,
            station_clearance_d=P.m4_clearance,
            instruction="M4 through retention at TCP island",
        ),
        _feature(
            "PT-HOLD-R1", "m4_retention_through", "phone_tcp",
            (588.8, 149.12), (177.8, 69.12), P.m4_clearance,
            station_clearance_d=P.m4_clearance,
            instruction="M4 through retention clamps service rail and station to board",
        ),
        _feature(
            "PT-HOLD-R2", "m4_retention_through", "phone_tcp",
            (588.8, 192.32), (177.8, 112.32), P.m4_clearance,
            station_clearance_d=P.m4_clearance,
            instruction="M4 through retention clamps service rail and station to board",
        ),
    ]
    return features


def board_pilot_holes() -> List[Tuple[float, float, float]]:
    """Compatibility projection of the authoritative named feature table."""
    return [(f["x"], f["y"], f["diameter"]) for f in board_features()]


def board_layout_metadata() -> dict:
    dims = part_dimensions()
    kb_half_w = dims["keyboard_half"][0]
    phone_fit_w = P.phone_w + P.phone_case_extra_w + 2 * P.phone_clearance
    phone_fit_l = P.phone_l + P.phone_case_extra_l + 2 * P.phone_clearance
    phone_frame_x = P.phone_x + 15.0
    phone_device_origin = [
        phone_frame_x + 3.2 + P.phone_clearance,
        P.phone_y + 3.2 + P.phone_clearance,
    ]
    tag_ids = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "K0": 4, "P0": 5}
    tag_entries = {}
    for name, (cx, cy) in direct_tag_centers().items():
        tag_entries[name] = {
            "id": tag_ids[name],
            "tile_origin_xy": [cx - 27.5, cy - 27.5],
            "detection_center_xy": [cx, cy],
            "expected_yaw_deg_in_board_frame": 0.0,
            "marked_top_edge_faces": "+Y / board rear",
        }
    features = board_features()
    return {
        "schema_version": 3,
        "release_revision": RELEASE_REVISION,
        "units": "mm",
        "origin": "front-left corner of board top surface",
        "axes": {"+x": "right", "+y": "rear/toward arm", "+z": "up"},
        "board": {
            "width": P.board_w,
            "depth": P.board_d,
            "thickness": P.board_t,
            "top_surface_z": 0.0,
            "bottom_surface_z": -P.board_t,
        },
        "printer": {
            "model": "QIDI Plus4",
            "nominal_envelope": [P.printer_x, P.printer_y, P.printer_z],
            "protected_envelope": [P.printer_safe_x, P.printer_safe_y, P.printer_safe_z],
        },
        "architecture": {
            "type": "open_indexed_stations",
            "keyboard_support": "structural_board_top_direct",
            "keyboard_interface": "left_master_right_seam_slave",
            "phone_tcp_interface": "board_indexed_master_with_service_rail_and_target_cartridge",
            "direct_tags": True,
            "board_feature_count": 13,
            "locator_pin_count": 4,
            "m4_retention_count": 9,
        },
        "devices": {
            "keyboard": {
                "nominal_origin_xy": [85.0, 85.0],
                "nominal_size": [P.keyboard_w, P.keyboard_d, P.keyboard_h],
                "support_plane_z": 0.0,
                "fit_clearance_per_side": P.keyboard_clearance,
                "support": "direct board contact; station solids stay outside nominal footprint",
            },
            "phone": {
                "nominal_origin_xy": phone_device_origin,
                "configured_size": [
                    P.phone_w + P.phone_case_extra_w,
                    P.phone_l + P.phone_case_extra_l,
                    P.phone_t + P.phone_case_extra_t,
                ],
                "fit_envelope": [phone_fit_w, phone_fit_l],
                "support_plane_z": P.station_base_t,
                "nominal_screen_plane_z": P.station_base_t + P.phone_t + P.phone_case_extra_t,
            },
            "tcp_target": {
                "center_xy": [441.0, 180.0],
                "target_plane_z": 10.5,
                "replaceable_part": "calibration_puck",
            },
        },
        "stations": {
            "keyboard_left": {
                "part": "keyboard_station_left",
                "origin_xy": [P.keyboard_x, P.keyboard_station_y],
                "outer_envelope": list(dims["keyboard_station_left"]),
                "installed_z": 0.0,
                "role": "master",
                "production_profile": "abs_rapido_tray_structural_0p4",
                "board_locator_ids": ["KBL-LOC-ROUND", "KBL-LOC-RADIAL"],
                "retention_ids": ["KBL-HOLD-F", "KBL-HOLD-R", "KBL-CLAMP"],
                "service_parts": ["keyboard_rear_clamp"],
            },
            "keyboard_right": {
                "part": "keyboard_station_right",
                "origin_xy": [P.keyboard_x + kb_half_w, P.keyboard_station_y],
                "outer_envelope": list(dims["keyboard_station_right"]),
                "installed_z": 0.0,
                "role": "slave",
                "production_profile": "abs_rapido_tray_structural_0p4",
                "board_locator_ids": [],
                "retention_ids": ["KBR-HOLD-F", "KBR-HOLD-R", "KBR-CLAMP"],
                "located_by": "interfaces.keyboard_master_slave",
                "service_parts": ["keyboard_rear_clamp"],
            },
            "phone_tcp": {
                "part": "phone_tcp_station",
                "origin_xy": [P.calibration_x, P.phone_y],
                "outer_envelope": list(dims["phone_tcp_station"]),
                "installed_z": 0.0,
                "role": "master",
                "production_profile": "abs_rapido_cradle_0p4",
                "board_locator_ids": ["PT-LOC-ROUND", "PT-LOC-RADIAL"],
                "retention_ids": ["PT-HOLD-TCP", "PT-HOLD-R1", "PT-HOLD-R2"],
                "service_parts": ["phone_clamp_rail", "calibration_puck"],
            },
        },
        "interfaces": {
            "keyboard_master_slave": {
                "master_station": "keyboard_left",
                "slave_station": "keyboard_right",
                "front_post_board_xy": [253.5, 78.0],
                "front_post_master_local_xy": [173.5, 6.0],
                "front_socket_slave_local_xy": [11.0, 6.0],
                "front_socket": "round",
                "rear_post_board_xy": [253.5, 248.0],
                "rear_post_master_local_xy": [173.5, 176.0],
                "rear_socket_slave_local_xy": [11.0, 176.0],
                "rear_socket": "radial_slot_y",
                "post_diameter": P.seam_post_d,
                "round_socket_diameter": P.seam_round_socket_d,
                "radial_slot_length": P.seam_slot_length,
                "radial_slot_width": P.seam_radial_slot_w,
                "post_height": P.seam_post_h,
            },
            "board_locator": {
                "pin": f"steel dowel {P.locator_pin_d:.1f} x {P.locator_pin_length:.1f}",
                "blind_bore_depth": P.locator_blind_depth,
                "projection": P.locator_pin_protrusion,
                "radial_slot_length": P.locator_slot_length,
                "entry_leadin_diameter": P.locator_leadin_d,
                "fit_release_part": "station_locator_fit_gauge",
                "keyboard_tray_profile": {
                    "round_socket_diameter_candidate": P.keyboard_locator_socket_d,
                    "radial_slot_width_candidate": P.keyboard_locator_slot_w,
                },
                "phone_cradle_profile": {
                    "round_socket_diameter_candidate": P.phone_locator_socket_d,
                    "radial_slot_width_candidate": P.phone_locator_slot_w,
                },
            },
            "m4_captive_nut": {
                "nut_thickness_candidate": P.m4_nut_thickness,
                "fit_release_part": "m4_captive_nut_fit_gauge",
                "phone_cradle_profile_ac_candidate": P.phone_m4_nut_ac,
                "production_consumer": "phone_clamp_rail",
            },
            "m3_insert_pockets": {
                "phone_station": {
                    "parameter": "phone_station_m3_insert_pocket_d",
                    "diameter_candidate": P.phone_station_m3_insert_pocket_d,
                    "fit_release_part": "phone_m3_insert_fit_gauge",
                    "production_consumer": "phone_tcp_station",
                    "production_profile": "abs_rapido_cradle_0p4",
                    "pocket_depth_mm": 6.2,
                    "residual_floor_mm": 0.3,
                },
                "compliant_tool": {
                    "parameter": "compliant_tool_m3_insert_pocket_d",
                    "diameter_candidate": P.compliant_tool_m3_insert_pocket_d,
                    "fit_release_part": "tool_m3_insert_fit_gauge",
                    "production_consumer": "compliant_tool_body",
                    "production_profile": "abs_rapido_precision_0p4",
                    "pocket_depth_mm": 6.2,
                    "edge_ligament_mm": 5.0,
                },
            },
        },
        "profile_selected_dimensions": {
            "abs_rapido_tray_structural_0p4": {
                "keyboard_locator_socket_d": P.keyboard_locator_socket_d,
                "keyboard_locator_slot_w": P.keyboard_locator_slot_w,
                "seam_post_d": P.seam_post_d,
                "seam_round_socket_d": P.seam_round_socket_d,
                "seam_radial_slot_w": P.seam_radial_slot_w,
                "seam_slot_length": P.seam_slot_length,
            },
            "abs_rapido_cradle_0p4": {
                "phone_locator_socket_d": P.phone_locator_socket_d,
                "phone_locator_slot_w": P.phone_locator_slot_w,
                "phone_m4_nut_ac": P.phone_m4_nut_ac,
                "m4_nut_thickness": P.m4_nut_thickness,
                "phone_station_m3_insert_pocket_d": P.phone_station_m3_insert_pocket_d,
            },
            "abs_rapido_precision_0p4": {
                "compliant_tool_m3_insert_pocket_d": P.compliant_tool_m3_insert_pocket_d,
            },
        },
        "direct_tags": {
            "mount": "direct_adhesive",
            "tile_size_mm": 55.0,
            "detection_edge_mm": 40.0,
            "nominal_plane_z_mm": None,
            "plane_z_status": "MEASURE_AFTER_ADHESIVE_AND_MATTE_LAMINATE",
            "application_tool": "tag_application_frame_55mm",
            "tags": tag_entries,
        },
        "arm_clamp_zone": {"rear_edge_x_range": [225, 385], "note": "No fixed holes; use factory table-edge clamp."},
        "board_features": features,
        "pilot_holes": [
            {
                "id": f["id"], "x": f["x"], "y": f["y"],
                "diameter": f["diameter"], "type": f["type"],
            }
            for f in features
        ],
        "physical_measurements_required": [
            "actual 18 mm board thickness, flatness, and blind-drill depth margin",
            "actual 6 mm dowel diameter and selected printed socket candidate",
            "keyboard underside foot/boss map and direct-board rocking check",
            "phone/case width, length, thickness, camera bump, buttons, USB and cable bend radius",
            "M4 nut across-flats/thickness and selected captive pocket candidate",
            "direct tag adhesive plus matte laminate stack thickness and glare",
        ],
    }


def validate_layout() -> None:
    """Reject out-of-board, overconstrained, or Plus4-unsafe RC03 layouts."""
    layout = board_layout_metadata()
    rectangles = []
    for name, station in layout["stations"].items():
        rectangles.append((
            name, *station["origin_xy"], *station["outer_envelope"], "station",
        ))
        w, d = station["outer_envelope"]
        if w > P.printer_safe_x or d > P.printer_safe_y:
            raise ValueError(f"{name} exceeds protected Plus4 XY envelope: {w} x {d}")
    for name, tag in layout["direct_tags"]["tags"].items():
        rectangles.append((
            f"tag_{name}", *tag["tile_origin_xy"], 55.0, 55.0, "tag",
        ))

    for name, x, y, w, d, _kind in rectangles:
        if x < 0 or y < 0 or x + w > P.board_w or y + d > P.board_d:
            raise ValueError(
                f"{name} leaves board: origin=({x}, {y}), size=({w}, {d}), "
                f"board=({P.board_w}, {P.board_d})"
            )

    allowed_overlap = {frozenset({"keyboard_left", "keyboard_right"})}
    for index, (name_a, ax, ay, aw, ad, kind_a) in enumerate(rectangles):
        for name_b, bx, by, bw, bd, kind_b in rectangles[index + 1:]:
            overlap_x = min(ax + aw, bx + bw) - max(ax, bx)
            overlap_y = min(ay + ad, by + bd) - max(ay, by)
            if overlap_x > 0 and overlap_y > 0:
                if frozenset({name_a, name_b}) in allowed_overlap:
                    continue
                raise ValueError(
                    f"Fixture overlap: {name_a} and {name_b} "
                    f"overlap by {overlap_x:.2f} x {overlap_y:.2f} mm"
                )

    features = layout["board_features"]
    if len(features) != 13:
        raise ValueError(f"RC03 must have 13 board features, found {len(features)}")
    if len({f["id"] for f in features}) != 13:
        raise ValueError("RC03 board feature IDs are not unique")
    locator_count = sum(f["type"] == "locator_pin_blind" for f in features)
    hold_count = sum(f["type"] == "m4_retention_through" for f in features)
    if (locator_count, hold_count) != (4, 9):
        raise ValueError(
            f"RC03 interface must be 4 locator pins + 9 M4 holds, got {locator_count} + {hold_count}"
        )
    if layout["stations"]["keyboard_right"]["board_locator_ids"]:
        raise ValueError("Keyboard-right slave must not own independent board locators")
    for f in features:
        x, y = f["board_xy"]
        if not (0 < x < P.board_w and 0 < y < P.board_d):
            raise ValueError(f"Board feature leaves usable board: {f}")
        if f["type"] == "locator_pin_blind" and f["depth"] >= P.board_t:
            raise ValueError(f"Blind locator breaks through board: {f['id']}")


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
        "fits_plus4_protected_envelope": fits_safe,
    }


def validate_nominal_assembly_fit(parts: Dict[str, cq.Workplane]) -> dict:
    """Run exact-solid interference checks for the nominal installed interfaces.

    These checks establish that the generated solids and their controlled world
    coordinates are mutually coherent.  They do not replace device measurement,
    printed-fit coupons, fastener qualification, or robot-motion validation.
    """
    tolerance_mm3 = 1e-6
    layout = board_layout_metadata()
    dims = part_dimensions()
    station_solids = {
        "keyboard_left": parts["keyboard_station_left"].translate(
            (P.keyboard_x, P.keyboard_station_y, 0)
        ),
        "keyboard_right": parts["keyboard_station_right"].translate(
            (P.keyboard_x + dims["keyboard_half"][0], P.keyboard_station_y, 0)
        ),
        "phone_tcp": parts["phone_tcp_station"].translate(
            (P.calibration_x, P.phone_y, 0)
        ),
    }

    checks: list[dict] = []

    def add_check(check_id: str, first: cq.Workplane, second: cq.Workplane) -> None:
        common = first.intersect(second)
        volume = float(common.val().Volume())
        checks.append(
            {
                "check_id": check_id,
                "intersection_volume_mm3": round(volume, 9),
                "limit_mm3": tolerance_mm3,
                "status": "PASS" if volume <= tolerance_mm3 else "FAIL",
            }
        )

    def m4_shank_at(x: float, y: float) -> cq.Workplane:
        return (
            cq.Workplane("XY")
            .center(x, y)
            .circle(2.0)
            .extrude(20.0)
            .translate((0, 0, -1.0))
        )

    add_check(
        "keyboard_master_slave_no_solid_collision",
        station_solids["keyboard_left"],
        station_solids["keyboard_right"],
    )

    keyboard = layout["devices"]["keyboard"]
    kx, ky = keyboard["nominal_origin_xy"]
    kw, kd, kh = keyboard["nominal_size"]
    keyboard_envelope = box_ll(
        kw, kd, kh, kx, ky, keyboard["support_plane_z"]
    )
    add_check(
        "keyboard_nominal_envelope_clear_of_master_station",
        keyboard_envelope,
        station_solids["keyboard_left"],
    )
    add_check(
        "keyboard_nominal_envelope_clear_of_slave_station",
        keyboard_envelope,
        station_solids["keyboard_right"],
    )

    keyboard_clamps = {
        "keyboard_left": parts["keyboard_rear_clamp"].translate(
            (P.keyboard_x + 85.0 - 26.0, 232.0, P.station_base_t)
        ),
        "keyboard_right": parts["keyboard_rear_clamp"].translate(
            (P.keyboard_x + 240.0 - 26.0, 232.0, P.station_base_t)
        ),
    }
    for owner, clamp in keyboard_clamps.items():
        add_check(
            f"{owner}_rear_clamp_clear_of_station",
            clamp,
            station_solids[owner],
        )

    features_by_id = {feature["id"]: feature for feature in layout["board_features"]}
    for feature_id, owner in (
        ("KBL-CLAMP", "keyboard_left"),
        ("KBR-CLAMP", "keyboard_right"),
    ):
        feature = features_by_id[feature_id]
        add_check(
            f"{feature_id}_m4_shank_clear_of_rear_clamp",
            m4_shank_at(feature["x"], feature["y"]),
            keyboard_clamps[owner],
        )

    phone = layout["devices"]["phone"]
    px, py = phone["nominal_origin_xy"]
    pw, pd, pt = phone["configured_size"]
    phone_envelope = box_ll(pw, pd, pt, px, py, phone["support_plane_z"])
    add_check(
        "phone_nominal_envelope_clear_of_service_station",
        phone_envelope,
        station_solids["phone_tcp"],
    )
    phone_frame_w = (
        P.phone_w
        + P.phone_case_extra_w
        + 2 * P.phone_clearance
        + 6.4
    )
    phone_rail_x = P.phone_x + 15.0 + phone_frame_w - 3.2
    phone_rail_world = parts["phone_clamp_rail"].translate(
        (phone_rail_x, P.phone_y, P.station_base_t)
    )
    add_check(
        "phone_nominal_envelope_clear_of_replaceable_rail",
        phone_envelope,
        phone_rail_world,
    )
    add_check(
        "phone_service_rail_clear_of_master_station",
        phone_rail_world,
        station_solids["phone_tcp"],
    )

    target_cartridge_world = parts["calibration_puck"].translate(
        (P.calibration_x + 15.0, P.calibration_y + 15.0, 10.5 - 4.0)
    )
    add_check(
        "tcp_target_cartridge_clear_of_master_station",
        target_cartridge_world,
        station_solids["phone_tcp"],
    )

    for feature_id in ("PT-HOLD-R1", "PT-HOLD-R2"):
        feature = features_by_id[feature_id]
        add_check(
            f"{feature_id}_m4_shank_clear_of_service_rail",
            m4_shank_at(feature["x"], feature["y"]),
            phone_rail_world,
        )

    for feature in layout["board_features"]:
        owner = feature["station"]
        if feature["type"] == "locator_pin_blind":
            interface_solid = (
                cq.Workplane("XY")
                .center(feature["x"], feature["y"])
                .circle(P.locator_pin_d / 2)
                .extrude(P.locator_pin_protrusion)
            )
            label = "nominal_pin"
        else:
            # Use the 4.0 mm screw shank, not the candidate wood-anchor bore.
            interface_solid = m4_shank_at(feature["x"], feature["y"])
            label = "m4_shank"
        add_check(
            f"{feature['id']}_{label}_clear_of_{owner}_solid",
            interface_solid,
            station_solids[owner],
        )

    failures = [row["check_id"] for row in checks if row["status"] != "PASS"]
    report = {
        "schema_version": 1,
        "design_revision": RELEASE_REVISION,
        "scope": "exact generated solids at nominal configured coordinates; physical qualification still required",
        "intersection_volume_limit_mm3": tolerance_mm3,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
    }
    (CFG_DIR / "digital_fit_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    if failures:
        raise ValueError(f"Nominal assembly interference failures: {failures}")
    return report


def make_assembly(parts: Dict[str, cq.Workplane]) -> None:
    dims = part_dimensions()
    layout = board_layout_metadata()
    kb_half_w = dims["keyboard_half"][0]
    phone_fit_w = P.phone_w + P.phone_case_extra_w + 2 * P.phone_clearance
    phone_frame_w = phone_fit_w + 2 * 3.2
    phone_rail_x = P.phone_x + 15.0 + phone_frame_w - 3.2
    assy = cq.Assembly(name=RELEASE_REVISION)
    assy.add(board_model(), name="board", color=cq.Color(0.68, 0.55, 0.38, 1.0))
    assy.add(parts["keyboard_station_left"], name="keyboard_station_left",
             loc=cq.Location(cq.Vector(P.keyboard_x, P.keyboard_station_y, P.board_t)),
             color=cq.Color(0.15, 0.45, 0.75, 1.0))
    assy.add(parts["keyboard_station_right"], name="keyboard_station_right",
             loc=cq.Location(cq.Vector(P.keyboard_x + kb_half_w, P.keyboard_station_y, P.board_t)),
             color=cq.Color(0.15, 0.45, 0.75, 1.0))
    # Rear clamps sit on station spines; the keyboard itself rests on the board.
    for i, cx in enumerate((P.keyboard_x + 85, P.keyboard_x + 240), 1):
        assy.add(parts["keyboard_rear_clamp"], name=f"keyboard_rear_clamp_{i}",
                 loc=cq.Location(cq.Vector(cx - 26, 232.0, P.board_t + P.station_base_t)),
                 color=cq.Color(0.18, 0.55, 0.30, 1.0))
    assy.add(parts["phone_tcp_station"], name="phone_tcp_station",
             loc=cq.Location(cq.Vector(P.calibration_x, P.phone_y, P.board_t)),
             color=cq.Color(0.75, 0.25, 0.20, 1.0))
    assy.add(parts["phone_clamp_rail"], name="phone_clamp_rail",
             loc=cq.Location(cq.Vector(phone_rail_x, P.phone_y, P.board_t + P.station_base_t)),
             color=cq.Color(0.55, 0.18, 0.16, 1.0))
    assy.add(parts["calibration_puck"], name="calibration_puck",
             loc=cq.Location(cq.Vector(426.0, 165.0, P.board_t + 6.5)),
             color=cq.Color(0.85, 0.65, 0.12, 1.0))

    # Assembly-only device envelopes make the neutral STEP useful for checking
    # the intended physical fit.  Their explicit names prevent nominal catalog
    # geometry from being mistaken for measured/released device CAD.
    keyboard = layout["devices"]["keyboard"]
    kx, ky = keyboard["nominal_origin_xy"]
    kw, kd, kh = keyboard["nominal_size"]
    assy.add(
        box_ll(kw, kd, kh),
        name="KEYBOARD_NOMINAL_ENVELOPE_NOT_MEASURED",
        loc=cq.Location(cq.Vector(kx, ky, P.board_t + keyboard["support_plane_z"])),
        color=cq.Color(0.12, 0.12, 0.14, 0.72),
    )
    phone = layout["devices"]["phone"]
    px, py = phone["nominal_origin_xy"]
    pw, pd, pt = phone["configured_size"]
    assy.add(
        box_ll(pw, pd, pt),
        name="PHONE_NOMINAL_ENVELOPE_NOT_MEASURED",
        loc=cq.Location(cq.Vector(px, py, P.board_t + phone["support_plane_z"])),
        color=cq.Color(0.06, 0.07, 0.10, 0.72),
    )

    # Show the complete 6 x 20 mm locator stack at its nominal 15 mm embedment
    # and 5 mm projection.  Printed station sockets intentionally surround the
    # protruding portion in this non-fused assembly.
    nominal_pin = cq.Workplane("XY").circle(P.locator_pin_d / 2).extrude(P.locator_pin_length)
    for feature in layout["board_features"]:
        if feature["type"] != "locator_pin_blind":
            continue
        assy.add(
            nominal_pin,
            name=f"{feature['id']}_NOMINAL_DOWEL",
            loc=cq.Location(
                cq.Vector(
                    feature["x"],
                    feature["y"],
                    P.board_t - P.locator_blind_depth,
                )
            ),
            color=cq.Color(0.55, 0.57, 0.60, 1.0),
        )
    # Direct tag tiles are represented as 0.2 mm assembly-only laminates.
    tile = rounded_plate(55.0, 55.0, 0.2, r=0.8)
    for name, tag in layout["direct_tags"]["tags"].items():
        x, y = tag["tile_origin_xy"]
        assy.add(tile, name=f"direct_tag_{name}",
                 loc=cq.Location(cq.Vector(x, y, P.board_t)),
                 color=cq.Color(0.92, 0.92, 0.92, 1.0))
    assy.save(str(STEP_DIR / "RoCell_RC03_INT_R1_full_assembly.step"))


def main() -> None:
    validate_layout()
    parts: Dict[str, cq.Workplane] = {
        "keyboard_station_left": keyboard_station("left"),
        "keyboard_station_right": keyboard_station("right"),
        "keyboard_rear_clamp": keyboard_rear_clamp(),
        "phone_tcp_station": phone_tcp_station(),
        "phone_clamp_rail": phone_clamp_rail(),
        "phone_clamp_tip_TPU_M4": phone_clamp_tip_tpu(),
        "phone_width_fit_test": phone_width_fit_test(),
        "keyboard_corner_fit_test": keyboard_corner_fit_test(),
        "hardware_fit_gauge": hardware_fit_gauge(),
        "m4_washer_fit_gauge": m4_washer_fit_gauge(),
        "m3_head_fit_gauge": m3_head_fit_gauge(),
        "phone_m3_insert_fit_gauge": phone_m3_insert_fit_gauge(),
        "tool_m3_insert_fit_gauge": tool_m3_insert_fit_gauge(),
        "station_locator_fit_gauge": station_locator_fit_gauge(),
        "m4_captive_nut_fit_gauge": m4_captive_nut_fit_gauge(),
        "m5_nut_trap_fit_gauge": m5_nut_trap_fit_gauge(),
        "setup_hardware_fit_gauge": setup_hardware_fit_gauge(),
        "cable_tie_saddle_fit_gauge": cable_tie_saddle_fit_gauge(),
        "mast_socket_fit_test": mast_socket_fit_test(),
        "tpu_tip_retention_gauge": tpu_tip_retention_gauge(),
        "tag_application_frame_55mm": tag_application_frame(),
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

    validate_nominal_assembly_fit(parts)

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
    special_steps = {
        "board_610x457x18_RC03.step",
        "RoCell_RC03_INT_R1_full_assembly.step",
    }
    for stale in STEP_DIR.glob("*.step"):
        if stale.name not in special_steps and stale not in expected_steps:
            stale.unlink()

    # RC03 has no large-printer-only fixture.  Remove copied RC02 geometry so
    # the isolated release cannot accidentally offer a superseded tray.
    for stale in list(LARGE_STEP_DIR.glob("*.step")) + list(LARGE_STL_DIR.glob("*.stl")):
        stale.unlink()

    # Board model is CAD-only because it exceeds printer volume.
    board = board_model()
    exporters.export(board, str(STEP_DIR / "board_610x457x18_RC03.step"))
    exporters.export(board, str(STL_DIR / "BOARD_REFERENCE_DO_NOT_PRINT.stl"), tolerance=0.2, angularTolerance=0.2)

    make_assembly(parts)

    (CFG_DIR / "parameters.json").write_text(json.dumps(asdict(P), indent=2), encoding="utf-8")
    (CFG_DIR / "workcell_layout.json").write_text(json.dumps(board_layout_metadata(), indent=2), encoding="utf-8")

    feature_fields = [
        "id", "type", "station", "x", "y", "diameter", "depth",
        "protrusion", "interface", "slot_axis", "station_clearance_d",
        "instruction",
    ]
    with (DRAW_DIR / "board_hole_coordinates.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=feature_fields, extrasaction="ignore")
        writer.writeheader()
        for feature in board_features():
            writer.writerow(feature)

    with (ROOT / "PART_VALIDATION.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    row_by_name = {r["part"]: r for r in rows}
    for part_name, dim_name in (
        ("keyboard_station_left", "keyboard_station_left"),
        ("keyboard_station_right", "keyboard_station_right"),
        ("phone_tcp_station", "phone_tcp_station"),
        ("phone_clamp_rail", "phone_clamp_rail"),
    ):
        expected = part_dimensions()[dim_name]
        row = row_by_name[part_name]
        if (abs(row["extent_x_mm"] - expected[0]) > 0.1 or
                abs(row["extent_y_mm"] - expected[1]) > 0.1):
            raise SystemExit(
                f"{part_name} metadata/export mismatch: metadata={expected}, "
                f"mesh=({row['extent_x_mm']}, {row['extent_y_mm']})"
            )

    failures = [
        r for r in rows
        if (not r["watertight"] or not r["winding_consistent"] or
            not r["single_body"] or not r["positive_volume"] or
            not r["fits_plus4_nominal_305x305x280"] or
            not r["fits_plus4_protected_envelope"])
    ]
    if failures:
        raise SystemExit(f"Validation failures: {failures}")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
    # The bundled Windows OCP build can raise 0xC0000374 during interpreter
    # teardown after every export has safely closed.  Bypass only that teardown
    # path after a successful main(); exceptions still propagate normally.
    if sys.platform == "win32":
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
