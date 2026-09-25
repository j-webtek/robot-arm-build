#!/usr/bin/env python3
"""Generate RC03 board setup drawings from the authoritative workcell layout.

The drawing package deliberately separates four kinds of geometry:

* blue double-ring board features are 6 mm blind locator bores;
* orange dashed-square board features are anchor centers only, never bore sizes;
* green 55 mm squares locate direct-adhesive paper tiles;
* cyan 40 mm squares are the AprilTag detection edges and are never cut/drilled.

The normalizers accept the final RC03 schema and the former RC02 layout while
the CAD package is being regenerated. Legacy tag-frame holes are never carried
into an RC03 drawing.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DRAW = ROOT / "drawings"
IMAGES = ROOT / "images"
PDF_OUTPUT = ROOT / "output" / "pdf"
CFG = ROOT / "config"
LAYOUT_PATH = CFG / "workcell_layout.json"
mm = 72.0 / 25.4
EXPECTED_REVISION = "RC03-INT-R1"
TAG_ORDER = ("T0", "T1", "T2", "T3", "K0", "P0")
TAG_IDS = {name: index for index, name in enumerate(TAG_ORDER)}
TAG_ROLES = {
    "T0": "world", "T1": "world", "T2": "world", "T3": "world",
    "K0": "station_check", "P0": "station_check",
}
RC03_FEATURE_IDS = (
    "KBL-LOC-ROUND", "KBL-LOC-RADIAL", "KBL-HOLD-F", "KBL-HOLD-R", "KBL-CLAMP",
    "KBR-HOLD-F", "KBR-HOLD-R", "KBR-CLAMP",
    "PT-LOC-ROUND", "PT-LOC-RADIAL", "PT-HOLD-TCP", "PT-HOLD-R1", "PT-HOLD-R2",
)
FROZEN_CENTERS = {
    "T0": (47.0, 40.0), "T1": (440.0, 40.0),
    "T2": (47.0, 410.0), "T3": (563.0, 410.0),
    "K0": (324.0, 309.0), "P0": (459.0, 309.0),
}
LEGACY_HOLE_IDS = (
    "KB-L1", "KB-L2", "KB-L3", "KB-L4",
    "KB-R1", "KB-R2", "KB-R3", "KB-R4",
    "KB-CLAMP-1", "KB-CLAMP-2",
    "PHONE-1", "PHONE-2", "PHONE-3", "PHONE-4",
    "CAL-1", "CAL-2",
)
TAG_HOLE_ID = re.compile(r"^(?:T[0-3]|K0|P0)-[AB]$")

DRAW.mkdir(parents=True, exist_ok=True)
IMAGES.mkdir(parents=True, exist_ok=True)
PDF_OUTPUT.mkdir(parents=True, exist_ok=True)

LETTER_DRILL_GUIDE = PDF_OUTPUT / "RC03_BOARD_DRILL_GUIDE_LETTER_1TO1.pdf"
FULL_SIZE_DRILL_GUIDE = PDF_OUTPUT / "RC03_BOARD_DRILL_GUIDE_24X36_FULL_SIZE_1TO1.pdf"
LEGACY_LETTER_TEMPLATE = DRAW / "board_drill_template_letter_1to1.pdf"
TILE_OVERLAP_MM = 12.0
TILE_MARGIN_MM = 14.0


def load_layout() -> dict[str, Any]:
    layout = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    revision = layout.get("release_revision") or layout.get("design_revision")
    if revision not in (None, EXPECTED_REVISION):
        raise ValueError(f"Layout revision {revision!r} does not match {EXPECTED_REVISION}")
    if int(layout.get("schema_version", 0)) >= 3 and revision != EXPECTED_REVISION:
        raise ValueError(f"Schema v3 layout must declare release_revision {EXPECTED_REVISION}")
    return layout


def layout_sha256() -> str:
    return hashlib.sha256(LAYOUT_PATH.read_bytes()).hexdigest()


def _xy(value: Any, *, field: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ValueError(f"{field} must contain X and Y")
    return float(value[0]), float(value[1])


def _first_xy(record: dict[str, Any], keys: Iterable[str], *, field: str) -> tuple[float, float] | None:
    for key in keys:
        if key in record and record[key] is not None:
            return _xy(record[key], field=f"{field}.{key}")
    return None


def release_revision(layout: dict[str, Any]) -> str:
    return str(layout.get("release_revision") or layout.get("design_revision") or EXPECTED_REVISION)


def board_size(layout: dict[str, Any]) -> tuple[float, float, float]:
    board = layout["board"]
    size = float(board["width"]), float(board["depth"]), float(board["thickness"])
    if int(layout.get("schema_version", 0)) >= 3 and any(
        not math.isclose(actual, expected, abs_tol=1e-9)
        for actual, expected in zip(size, (610.0, 457.0, 18.0))
    ):
        raise ValueError(f"RC03 board must remain 610 x 457 x 18 mm, got {size}")
    return size


def direct_tag_spec(layout: dict[str, Any]) -> dict[str, Any]:
    strict = int(layout.get("schema_version", 0)) >= 3
    if strict and not isinstance(layout.get("direct_tags"), dict):
        raise ValueError("Schema v3 requires a direct_tags object")
    direct = layout.get("direct_tags") or layout.get("fiducials") or {}
    tile = float(direct.get("tile_size", direct.get("tile_size_mm", 55.0)))
    detection = float(direct.get("detection_edge", direct.get("detection_edge_mm", 40.0)))
    mount = str(direct.get("mount", direct.get("mounting", "direct_adhesive")))
    board_reference = str(direct.get("board_z_reference", "finished sealed board top surface"))
    plane_z = direct.get(
        "direct_tag_plane_nominal_z_mm",
        direct.get("nominal_plane_z_mm", direct.get("plane_z_mm")),
    )
    if plane_z is not None:
        plane_z = float(plane_z)
    if abs(tile - 55.0) > 1e-6 or abs(detection - 40.0) > 1e-6:
        raise ValueError(f"RC03 controlled tag geometry must be 55/40 mm, got {tile}/{detection}")
    if strict and mount != "direct_adhesive":
        raise ValueError(f"RC03 tags must mount direct_adhesive, got {mount!r}")
    return {
        "tile_size_mm": tile,
        "detection_edge_mm": detection,
        "mounting": mount,
        "board_z_reference": board_reference,
        "direct_tag_plane_nominal_z_mm": plane_z,
    }


def direct_tag_rows(layout: dict[str, Any]) -> list[dict[str, Any]]:
    strict = int(layout.get("schema_version", 0)) >= 3
    spec = direct_tag_spec(layout)
    direct = layout.get("direct_tags") or layout.get("fiducials") or {}
    source = direct.get("tags") or direct.get("placements")
    if source is None and any(name in direct for name in TAG_ORDER):
        source = direct
    source = source or {}
    if strict and (not isinstance(source, dict) or set(source) != set(TAG_ORDER)):
        actual = sorted(source) if isinstance(source, dict) else type(source).__name__
        raise ValueError(f"Schema v3 direct_tags.tags must contain exactly {list(TAG_ORDER)}; got {actual}")
    rows: list[dict[str, Any]] = []
    for name in TAG_ORDER:
        entry = source.get(name, {}) if isinstance(source, dict) else {}
        if not isinstance(entry, dict):
            entry = {}
        supplied_center = _first_xy(
            entry,
            ("detection_center_xy", "detection_center_xy_mm", "nominal_detection_center_xy_mm", "center_xy"),
            field=f"direct_tags.{name}",
        )
        if strict and supplied_center is None:
            raise ValueError(f"Schema v3 direct tag {name} is missing its detection center")
        center = supplied_center or FROZEN_CENTERS[name]
        expected = FROZEN_CENTERS[name]
        if not (math.isclose(center[0], expected[0], abs_tol=1e-6) and
                math.isclose(center[1], expected[1], abs_tol=1e-6)):
            raise ValueError(f"Frozen RC03 center changed for {name}: {center} != {expected}")
        tile_origin = _first_xy(
            entry, ("tile_origin_xy", "tile_origin_xy_mm"), field=f"direct_tags.{name}",
        )
        derived_origin = (
            center[0] - spec["tile_size_mm"] / 2.0,
            center[1] - spec["tile_size_mm"] / 2.0,
        )
        if tile_origin is None:
            tile_origin = derived_origin
        if not (math.isclose(tile_origin[0], derived_origin[0], abs_tol=1e-6) and
                math.isclose(tile_origin[1], derived_origin[1], abs_tol=1e-6)):
            raise ValueError(f"Tile origin for {name} does not center on its detection center")
        row = {
            "name": name,
            "id": int(entry.get("id", TAG_IDS[name])),
            "role": str(entry.get("role", TAG_ROLES[name])),
            "mounting": str(entry.get("mount", entry.get("mounting", spec["mounting"]))),
            "tile_origin_x_mm": tile_origin[0],
            "tile_origin_y_mm": tile_origin[1],
            "tile_size_mm": spec["tile_size_mm"],
            "detection_center_x_mm": center[0],
            "detection_center_y_mm": center[1],
            "detection_edge_mm": spec["detection_edge_mm"],
            "expected_yaw_deg": float(entry.get("yaw", entry.get("yaw_deg", entry.get("expected_yaw_deg_in_board_frame", 0.0)))),
            "board_z_reference": spec["board_z_reference"],
            "nominal_plane_z_mm": spec["direct_tag_plane_nominal_z_mm"],
        }
        if row["id"] != TAG_IDS[name]:
            raise ValueError(f"RC03 tag {name} must use printed ID {TAG_IDS[name]}, got {row['id']}")
        if row["role"] != TAG_ROLES[name]:
            raise ValueError(f"RC03 tag {name} must have role {TAG_ROLES[name]!r}, got {row['role']!r}")
        if row["mounting"] != "direct_adhesive":
            raise ValueError(f"RC03 tag {name} must mount direct_adhesive")
        if not math.isclose(row["expected_yaw_deg"], 0.0, abs_tol=1e-9):
            raise ValueError(f"RC03 tag {name} nominal yaw must be 0 degrees")
        bw, bd, _ = board_size(layout)
        if not (0 <= tile_origin[0] <= bw - spec["tile_size_mm"] and
                0 <= tile_origin[1] <= bd - spec["tile_size_mm"]):
            raise ValueError(f"RC03 tag {name} tile is outside the board envelope")
        rows.append(row)
    return rows


def _feature_instruction(feature: dict[str, Any]) -> str:
    explicit = feature.get("instruction")
    if explicit:
        return str(explicit)
    feature_type = str(feature.get("type", "board_hole"))
    diameter = float(feature.get("diameter", feature.get("diameter_mm", 0.0)))
    depth = feature.get("depth", feature.get("depth_mm"))
    protrusion = feature.get("protrusion", feature.get("protrusion_mm"))
    if feature_type == "locator_pin_blind":
        suffix = f" to {float(depth):.1f} mm depth" if depth is not None else " as a blind hole"
        if protrusion is not None:
            suffix += f"; set locator protrusion to {float(protrusion):.1f} mm"
        return f"Drill/ream diameter {diameter:.2f} mm{suffix}; verify with the datum coupon"
    if feature_type == "m4_retention_through":
        return (
            "Transfer/center-punch this M4 anchor center only. The nominal "
            f"{diameter:.2f} mm value is the station/CAD passage reference, not a "
            "universal wood-bore command. Drill the final board bore only from the "
            "qualified anchor maker data and completed FASTENER_MAP.csv row."
        )
    return f"Fabricate diameter {diameter:.2f} mm {feature_type.replace('_', ' ')} per RC03 setup drawing"


def _optional_text(value: Any) -> str:
    return "" if value is None else str(value)


def board_feature_rows(layout: dict[str, Any]) -> list[dict[str, Any]]:
    strict = int(layout.get("schema_version", 0)) >= 3
    raw = layout.get("board_features")
    if strict and raw is None:
        raise ValueError("Schema v3 requires authoritative board_features")
    if raw is None:
        raw = layout.get("pilot_holes", [])
    if isinstance(raw, dict):
        values = []
        for feature_id, record in raw.items():
            item = dict(record)
            item.setdefault("id", feature_id)
            values.append(item)
        raw = values
    if not isinstance(raw, list):
        raise ValueError("board_features/pilot_holes must be a list or mapping")
    legacy_unnamed = bool(raw) and all(isinstance(item, dict) and "id" not in item for item in raw)
    if legacy_unnamed and len(raw) == 28:
        raw = raw[:16]
    rows: list[dict[str, Any]] = []
    for index, record in enumerate(raw):
        if not isinstance(record, dict):
            raise ValueError(f"Board feature {index} is not an object")
        feature_id = str(record.get("id") or (LEGACY_HOLE_IDS[index] if len(raw) == 16 else f"BOARD-{index + 1:02d}"))
        feature_type = str(record.get("type", "m4_retention_through"))
        if TAG_HOLE_ID.match(feature_id) or feature_type in {"tag_frame_mount", "tag_mount"}:
            continue
        diameter = float(record.get("diameter", record.get("diameter_mm", 0.0)))
        if diameter <= 0:
            raise ValueError(f"Board feature {feature_id} has no positive diameter")
        board_xy = _first_xy(record, ("board_xy",), field=f"board_features.{feature_id}")
        x, y = float(record["x"]), float(record["y"])
        if board_xy is not None and not (
            math.isclose(x, board_xy[0], abs_tol=1e-9) and
            math.isclose(y, board_xy[1], abs_tol=1e-9)
        ):
            raise ValueError(f"Board feature {feature_id} x/y does not match board_xy")
        local_xy = _first_xy(record, ("local_xy",), field=f"board_features.{feature_id}")
        row = {
            "id": feature_id,
            "type": feature_type,
            "station": str(record.get("station", record.get("owner", ""))),
            "x": x,
            "y": y,
            "local_x_mm": local_xy[0] if local_xy is not None else "",
            "local_y_mm": local_xy[1] if local_xy is not None else "",
            "diameter": diameter,
            "depth_mm": record.get("depth", record.get("depth_mm", "")),
            "protrusion_mm": record.get("protrusion", record.get("protrusion_mm", "")),
            "station_clearance_d_mm": record.get("station_clearance_d", ""),
            "slot_axis": _optional_text(record.get("slot_axis")),
            "interface": _optional_text(record.get("interface")),
            "instruction": _feature_instruction(record),
        }
        rows.append(row)
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Board feature IDs are not unique")
    if strict and set(ids) != set(RC03_FEATURE_IDS):
        raise ValueError(f"Schema v3 board feature IDs changed: {sorted(ids)}")
    bw, bd, _ = board_size(layout)
    for row in rows:
        if not (0 <= row["x"] <= bw and 0 <= row["y"] <= bd):
            raise ValueError(f"Board feature {row['id']} lies outside the board envelope")
        row.update({
            "left_edge_x_mm": round(row["x"], 3),
            "front_edge_y_mm": round(row["y"], 3),
            "right_edge_mm": round(bw - row["x"], 3),
            "rear_edge_mm": round(bd - row["y"], 3),
            "template_action": (
                "DRILL_6.0_MM_BLIND_15.0_MM_AFTER_PILOT"
                if row["type"] == "locator_pin_blind"
                else "CENTER_PUNCH_ONLY_FINAL_BORE_FROM_FASTENER_MAP"
            ),
            "final_board_bore_control": (
                "6.0 mm blind to 15.0 mm nominal depth; preserve at least 2.0 mm floor"
                if row["type"] == "locator_pin_blind"
                else "FASTENER_MAP.csv qualified anchor row"
            ),
        })
    return rows


def station_rects(layout: dict[str, Any]) -> list[tuple[str, float, float, float, float]]:
    rects: list[tuple[str, float, float, float, float]] = []
    stations = layout.get("stations")
    if isinstance(stations, dict):
        for key, station in stations.items():
            if not isinstance(station, dict):
                continue
            origin = _first_xy(station, ("origin_xy", "origin_xy_mm"), field=f"stations.{key}")
            size = _first_xy(
                station,
                ("outer_envelope", "outer_envelope_mm", "footprint", "footprint_mm", "size"),
                field=f"stations.{key}",
            )
            if origin and size:
                label = str(station.get("label", key.replace("_", " ").upper()))
                rects.append((label, origin[0], origin[1], size[0], size[1]))
    if rects:
        return rects
    for key, label in (
        ("keyboard", "KEYBOARD STATIONS"),
        ("phone", "PHONE/TCP STATION"),
        ("calibration_puck", "TCP INSERT"),
    ):
        record = layout.get(key)
        if not isinstance(record, dict):
            continue
        origin = _first_xy(record, ("origin_xy",), field=key)
        size = _first_xy(record, ("outer_envelope", "size"), field=key)
        if origin and size:
            rects.append((label, origin[0], origin[1], size[0], size[1]))
    return rects


def generate_csv(layout: dict[str, Any]) -> None:
    hole_rows = board_feature_rows(layout)
    hole_fields = [
        "release_revision", "layout_sha256", "id", "type", "station", "x", "y",
        "left_edge_x_mm", "front_edge_y_mm", "right_edge_mm", "rear_edge_mm",
        "local_x_mm", "local_y_mm",
        "diameter", "depth_mm", "protrusion_mm", "station_clearance_d_mm",
        "slot_axis", "interface", "template_action", "final_board_bore_control", "instruction",
    ]
    digest = layout_sha256()
    with (DRAW / "board_hole_coordinates.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=hole_fields)
        writer.writeheader()
        for row in hole_rows:
            writer.writerow({"release_revision": release_revision(layout), "layout_sha256": digest, **row})
    tag_fields = [
        "release_revision", "layout_sha256", "name", "id", "role", "mounting",
        "tile_origin_x_mm", "tile_origin_y_mm", "tile_size_mm",
        "detection_center_x_mm", "detection_center_y_mm", "detection_edge_mm",
        "expected_yaw_deg", "board_z_reference", "nominal_plane_z_mm",
    ]
    with (DRAW / "tag_application_coordinates.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tag_fields)
        writer.writeheader()
        for row in direct_tag_rows(layout):
            writer.writerow({"release_revision": release_revision(layout), "layout_sha256": digest, **row})


def _add_dxf_polyline(msp: Any, x: float, y: float, w: float, h: float, layer: str) -> None:
    msp.add_lwpolyline(
        [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)],
        dxfattribs={"layer": layer},
    )


def _feature_label_position(row: dict[str, Any], board_width: float) -> tuple[float, str]:
    if row["x"] > board_width - 45:
        return row["x"] - 3, "right"
    return row["x"] + 3, "left"


def generate_dxf(layout: dict[str, Any]) -> None:
    import ezdxf
    from ezdxf.enums import TextEntityAlignment

    bw, bd, _ = board_size(layout)
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    for layer, color in [
        ("BOARD", 7), ("STATIONS", 5), ("LOCATOR_BLIND", 5),
        ("ANCHOR_CENTER_ONLY", 30), ("TAG_TILE", 3),
        ("TAG_DETECTION", 4), ("TAG_CENTER", 6), ("ARM_ZONE", 2),
        ("TEXT", 7), ("CENTER", 4),
    ]:
        if layer not in doc.layers:
            doc.layers.add(layer, color=color)
    msp = doc.modelspace()
    _add_dxf_polyline(msp, 0, 0, bw, bd, "BOARD")
    for name, x, y, w, h in station_rects(layout):
        _add_dxf_polyline(msp, x, y, w, h, "STATIONS")
        msp.add_text(name, dxfattribs={"height": 5, "layer": "TEXT"}).set_placement((x + 3, y + h - 8))
    for row in direct_tag_rows(layout):
        tile = row["tile_size_mm"]
        tx, ty = row["tile_origin_x_mm"], row["tile_origin_y_mm"]
        cx, cy = row["detection_center_x_mm"], row["detection_center_y_mm"]
        edge = row["detection_edge_mm"]
        _add_dxf_polyline(msp, tx, ty, tile, tile, "TAG_TILE")
        _add_dxf_polyline(msp, cx - edge / 2, cy - edge / 2, edge, edge, "TAG_DETECTION")
        msp.add_line((cx - 3, cy), (cx + 3, cy), dxfattribs={"layer": "TAG_CENTER"})
        msp.add_line((cx, cy - 3), (cx, cy + 3), dxfattribs={"layer": "TAG_CENTER"})
        msp.add_line((cx, cy), (cx, cy + 18), dxfattribs={"layer": "TAG_CENTER"})
        msp.add_text(f"{row['name']} / ID{row['id']}  +Y", dxfattribs={"height": 3.5, "layer": "TEXT"}).set_placement((tx + 2, ty + tile - 5))
    ax0, ax1 = layout.get("arm_clamp_zone", {}).get("rear_edge_x_range", [225, 385])
    _add_dxf_polyline(msp, 0.0 + float(ax0), bd - 30, float(ax1) - float(ax0), 30, "ARM_ZONE")
    msp.add_text("ROARM FACTORY CLAMP ZONE - NO DRILLING", dxfattribs={"height": 5, "layer": "TEXT"}).set_placement((float(ax0) + 3, bd - 18))
    for row in board_feature_rows(layout):
        x, y, diameter = row["x"], row["y"], row["diameter"]
        is_locator = row["type"] == "locator_pin_blind"
        if is_locator:
            msp.add_circle((x, y), diameter / 2, dxfattribs={"layer": "LOCATOR_BLIND"})
            msp.add_circle((x, y), 4.6, dxfattribs={"layer": "LOCATOR_BLIND"})
        else:
            _add_dxf_polyline(msp, x - 4.2, y - 4.2, 8.4, 8.4, "ANCHOR_CENTER_ONLY")
        msp.add_line((x - 4, y), (x + 4, y), dxfattribs={"layer": "CENTER"})
        msp.add_line((x, y - 4), (x, y + 4), dxfattribs={"layer": "CENTER"})
        label_x, anchor = _feature_label_position(row, bw)
        alignment = TextEntityAlignment.RIGHT if anchor == "right" else TextEntityAlignment.LEFT
        suffix = "BLIND 6.0 x 15.0" if is_locator else "CENTER ONLY - BORE FROM FASTENER MAP"
        msp.add_text(f"{row['id']}  {suffix}", dxfattribs={"height": 3, "layer": "TEXT"}).set_placement(
            (label_x, y + 3), align=alignment,
        )
    msp.add_text(
        f"{release_revision(layout)}  LAYOUT {layout_sha256()[:12]}  "
        "ORIGIN (0,0) FRONT-LEFT FINISHED TOP; +X RIGHT; +Y REAR",
        dxfattribs={"height": 6, "layer": "TEXT"},
    ).set_placement((10, bd + 10))
    msp.add_text(
        "BLUE LOCATOR_BLIND = DRILL 6.0 x 15.0; ORANGE ANCHOR_CENTER_ONLY = CENTER TARGET, NOT BORE SIZE",
        dxfattribs={"height": 4, "layer": "TEXT"},
    ).set_placement((10, bd + 2))
    doc.saveas(DRAW / "board_610x457_drill_layout.dxf")


def generate_svg(layout: dict[str, Any]) -> None:
    import svgwrite

    bw, bd, _ = board_size(layout)
    dwg = svgwrite.Drawing(
        str(DRAW / "board_610x457_drill_layout.svg"),
        size=(f"{bw}mm", f"{bd + 25}mm"), viewBox=f"0 -25 {bw} {bd + 25}",
    )
    g = dwg.g(transform=f"translate(0,{bd}) scale(1,-1)")
    g.add(dwg.rect(insert=(0, 0), size=(bw, bd), fill="white", stroke="black", stroke_width=1))
    for _, x, y, w, h in station_rects(layout):
        g.add(dwg.rect(insert=(x, y), size=(w, h), fill="none", stroke="#2e6fbb", stroke_width=0.8))
    for row in direct_tag_rows(layout):
        tile, edge = row["tile_size_mm"], row["detection_edge_mm"]
        tx, ty = row["tile_origin_x_mm"], row["tile_origin_y_mm"]
        cx, cy = row["detection_center_x_mm"], row["detection_center_y_mm"]
        g.add(dwg.rect(insert=(tx, ty), size=(tile, tile), fill="none", stroke="#16804c", stroke_width=0.8))
        g.add(dwg.rect(insert=(cx - edge / 2, cy - edge / 2), size=(edge, edge), fill="none", stroke="#008caa", stroke_width=0.5, stroke_dasharray="2,1"))
        g.add(dwg.line(start=(cx - 3, cy), end=(cx + 3, cy), stroke="#8a2be2", stroke_width=0.35))
        g.add(dwg.line(start=(cx, cy - 3), end=(cx, cy + 18), stroke="#8a2be2", stroke_width=0.35))
    ax0, ax1 = layout.get("arm_clamp_zone", {}).get("rear_edge_x_range", [225, 385])
    g.add(dwg.rect(insert=(ax0, bd - 30), size=(ax1 - ax0, 30), fill="none", stroke="#c33", stroke_dasharray="5,3"))
    for row in board_feature_rows(layout):
        x, y, diameter = row["x"], row["y"], row["diameter"]
        is_locator = row["type"] == "locator_pin_blind"
        color = "#075bd8" if is_locator else "#e85f00"
        if is_locator:
            g.add(dwg.circle(center=(x, y), r=diameter / 2, fill="none", stroke=color, stroke_width=0.6))
            g.add(dwg.circle(center=(x, y), r=4.6, fill="none", stroke=color, stroke_width=0.5))
        else:
            g.add(dwg.rect(insert=(x - 4.2, y - 4.2), size=(8.4, 8.4), fill="none", stroke=color, stroke_width=0.6, stroke_dasharray="2,1"))
        g.add(dwg.line(start=(x - 3, y), end=(x + 3, y), stroke=color, stroke_width=0.35))
        g.add(dwg.line(start=(x, y - 3), end=(x, y + 3), stroke=color, stroke_width=0.35))
    dwg.add(g)
    for name, x, y, _, h in station_rects(layout):
        dwg.add(dwg.text(name, insert=(x + 3, bd - (y + h) + 9), font_size="5px", font_family="sans-serif"))
    for row in direct_tag_rows(layout):
        dwg.add(dwg.text(
            f"{row['name']} ID{row['id']} +Y",
            insert=(row["tile_origin_x_mm"] + 2, bd - (row["tile_origin_y_mm"] + row["tile_size_mm"]) + 7),
            font_size="3.5px", font_family="sans-serif",
        ))
    for row in board_feature_rows(layout):
        label_x, anchor = _feature_label_position(row, bw)
        is_locator = row["type"] == "locator_pin_blind"
        suffix = "BLIND 6.0/15.0" if is_locator else "CENTER ONLY"
        dwg.add(dwg.text(
            f"{row['id']} {suffix}", insert=(label_x, bd - row["y"] - 3),
            text_anchor="end" if anchor == "right" else "start",
            font_size="3px", font_family="sans-serif",
            fill="#075bd8" if is_locator else "#b74700",
        ))
    dwg.add(dwg.text(
        f"RoCell {release_revision(layout)} board setup layout - dimensions in mm",
        insert=(8, -8), font_size="7px", font_weight="bold", font_family="sans-serif",
    ))
    dwg.add(dwg.text(
        "Blue double ring = 6.0 x 15.0 blind locator; orange square = anchor center only, final bore from FASTENER_MAP.csv.",
        insert=(8, -16), font_size="5px", font_family="sans-serif",
    ))
    dwg.add(dwg.text(
        f"Layout SHA-256: {layout_sha256()}",
        insert=(350, -16), font_size="4px", font_family="monospace",
    ))
    dwg.save()


def draw_reportlab_layout(
    c: Any, layout: dict[str, Any], ox_pt: float = 0,
    oy_pt: float = 0, scale: float = 1.0, labels: bool = True,
) -> None:
    bw, bd, _ = board_size(layout)
    c.saveState()
    c.translate(ox_pt, oy_pt)
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(0, 0, bw * mm * scale, bd * mm * scale, stroke=1, fill=0)
    for name, x, y, w, h in station_rects(layout):
        c.setStrokeColorRGB(0.1, 0.35, 0.7)
        c.rect(x * mm * scale, y * mm * scale, w * mm * scale, h * mm * scale, stroke=1, fill=0)
        if labels:
            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica", 5.5)
            c.drawString((x + 3) * mm * scale, (y + h - 8) * mm * scale, name)
    for row in direct_tag_rows(layout):
        tile, edge = row["tile_size_mm"], row["detection_edge_mm"]
        tx, ty = row["tile_origin_x_mm"], row["tile_origin_y_mm"]
        cx, cy = row["detection_center_x_mm"], row["detection_center_y_mm"]
        c.setStrokeColorRGB(0.05, 0.52, 0.25)
        c.rect(tx * mm * scale, ty * mm * scale, tile * mm * scale, tile * mm * scale, stroke=1, fill=0)
        c.setStrokeColorRGB(0.0, 0.55, 0.7)
        c.setDash(2, 1)
        c.rect((cx - edge / 2) * mm * scale, (cy - edge / 2) * mm * scale, edge * mm * scale, edge * mm * scale, stroke=1, fill=0)
        c.setDash()
        c.setStrokeColorRGB(0.45, 0.1, 0.6)
        c.line((cx - 3) * mm * scale, cy * mm * scale, (cx + 3) * mm * scale, cy * mm * scale)
        c.line(cx * mm * scale, (cy - 3) * mm * scale, cx * mm * scale, (cy + 18) * mm * scale)
        if labels:
            c.setFillColorRGB(0.02, 0.35, 0.15)
            c.setFont("Helvetica-Bold", 5.2)
            c.drawString((tx + 2) * mm * scale, (ty + tile - 6) * mm * scale, f"{row['name']} ID{row['id']} +Y")
    ax0, ax1 = layout.get("arm_clamp_zone", {}).get("rear_edge_x_range", [225, 385])
    c.setStrokeColorRGB(0.8, 0.1, 0.1)
    c.setDash(4, 2)
    c.rect(ax0 * mm * scale, (bd - 30) * mm * scale, (ax1 - ax0) * mm * scale, 30 * mm * scale, stroke=1, fill=0)
    c.setDash()
    if labels:
        c.setFillColorRGB(0.65, 0, 0)
        c.setFont("Helvetica-Bold", 6)
        c.drawCentredString(((ax0 + ax1) / 2) * mm * scale, (bd - 18) * mm * scale, "ROARM CLAMP ZONE")
    for row in board_feature_rows(layout):
        x, y, diameter = row["x"], row["y"], row["diameter"]
        is_locator = row["type"] == "locator_pin_blind"
        if is_locator:
            c.setStrokeColorRGB(0.02, 0.30, 0.78)
            c.setDash()
            c.circle(x * mm * scale, y * mm * scale, diameter / 2 * mm * scale, stroke=1, fill=0)
            c.circle(x * mm * scale, y * mm * scale, 4.2 * mm * scale, stroke=1, fill=0)
        else:
            c.setStrokeColorRGB(0.92, 0.38, 0.02)
            c.setDash(2, 1)
            c.rect(
                (x - 4) * mm * scale, (y - 4) * mm * scale,
                8 * mm * scale, 8 * mm * scale, stroke=1, fill=0,
            )
            c.setDash()
        c.line((x - 3) * mm * scale, y * mm * scale, (x + 3) * mm * scale, y * mm * scale)
        c.line(x * mm * scale, (y - 3) * mm * scale, x * mm * scale, (y + 3) * mm * scale)
        if labels:
            c.setFillColorRGB(0.02, 0.22, 0.60) if is_locator else c.setFillColorRGB(0.70, 0.24, 0.00)
            c.setFont("Helvetica-Bold", 5.0)
            label_x, anchor = _feature_label_position(row, bw)
            draw_label = c.drawRightString if anchor == "right" else c.drawString
            draw_label(label_x * mm * scale, (y + 3) * mm * scale, row["id"])
    c.restoreState()


def _wrapped_lines(c: Any, text: str, width: float, font: str, size: float) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and c.stringWidth(candidate, font, size) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _draw_scale_controls(
    c: Any, pw: float, ph: float, tile_id: str,
    *, horizontal_y_mm: float = 11.5, instruction_y_mm: float = 10.5,
) -> None:
    """Draw independent 100 mm X and Y controls inside common printer-safe margins."""
    c.saveState()
    c.setStrokeColorRGB(0, 0, 0)
    c.setFillColorRGB(0, 0, 0)
    c.setLineWidth(0.9)
    hx, hy = 18 * mm, horizontal_y_mm * mm
    c.line(hx, hy, hx + 100 * mm, hy)
    for tick in range(11):
        height = 4 * mm if tick in (0, 10) else 2 * mm
        c.line(hx + tick * 10 * mm, hy - height / 2, hx + tick * 10 * mm, hy + height / 2)
    c.setFont("Helvetica-Bold", 6.8)
    c.drawString(hx, hy + 3.0 * mm, f"X SCALE - 100.0 mm - TILE {tile_id}")

    vx, vy = pw - 14.5 * mm, 25 * mm
    c.line(vx, vy, vx, vy + 100 * mm)
    for tick in range(11):
        width = 4 * mm if tick in (0, 10) else 2 * mm
        c.line(vx - width / 2, vy + tick * 10 * mm, vx + width / 2, vy + tick * 10 * mm)
    c.saveState()
    c.translate(vx - 3.0 * mm, vy)
    c.rotate(90)
    c.setFont("Helvetica-Bold", 6.8)
    c.drawString(0, 0, f"Y SCALE - 100.0 mm - TILE {tile_id}")
    c.restoreState()
    c.setFont("Helvetica", 5.8)
    c.drawRightString(pw - 24 * mm, instruction_y_mm * mm, "ACTUAL SIZE / 100% ONLY - NO FIT, SHRINK, POSTER, OR DUPLEX")
    c.restoreState()


def _registration_points(usable_w_mm: float, usable_h_mm: float) -> list[tuple[str, float, float]]:
    stride_x = usable_w_mm - TILE_OVERLAP_MM
    stride_y = usable_h_mm - TILE_OVERLAP_MM
    points: list[tuple[str, float, float]] = []
    for seam in (1, 2):
        x = seam * stride_x + TILE_OVERLAP_MM / 2.0
        for row in range(3):
            for index, fraction in enumerate((0.25, 0.55), start=1):
                y = row * stride_y + usable_h_mm * fraction
                points.append((f"V{seam}-{row + 1}{index}", x, y))
    for seam in (1, 2):
        y = seam * stride_y + TILE_OVERLAP_MM / 2.0
        for col in range(3):
            for index, fraction in enumerate((0.25, 0.55), start=1):
                x = col * stride_x + usable_w_mm * fraction
                points.append((f"H{seam}-{col + 1}{index}", x, y))
    return points


def _draw_registration_marks(
    c: Any, ox_pt: float, oy_pt: float, usable_w_mm: float, usable_h_mm: float,
) -> None:
    c.saveState()
    c.translate(ox_pt, oy_pt)
    c.setStrokeColorRGB(0.38, 0.12, 0.55)
    c.setFillColorRGB(0.28, 0.05, 0.42)
    c.setLineWidth(0.55)
    c.setFont("Helvetica-Bold", 4.8)
    for mark_id, x, y in _registration_points(usable_w_mm, usable_h_mm):
        xp, yp = x * mm, y * mm
        c.circle(xp, yp, 2.5 * mm, stroke=1, fill=0)
        c.line(xp - 4 * mm, yp, xp + 4 * mm, yp)
        c.line(xp, yp - 4 * mm, xp, yp + 4 * mm)
        c.line(xp - 1.8 * mm, yp - 1.8 * mm, xp + 1.8 * mm, yp + 1.8 * mm)
        c.line(xp - 1.8 * mm, yp + 1.8 * mm, xp + 1.8 * mm, yp - 1.8 * mm)
        c.drawString(xp + 3.2 * mm, yp + 2.2 * mm, f"MATCH {mark_id}")
        c.drawRightString(xp - 3.2 * mm, yp + 2.2 * mm, f"MATCH {mark_id}")
    c.restoreState()


def _draw_drill_layout(
    c: Any,
    layout: dict[str, Any],
    ox_pt: float,
    oy_pt: float,
    *,
    scale: float = 1.0,
    labels: bool = True,
    include_tags: bool = True,
    include_registration: bool = False,
    usable_w_mm: float = 0.0,
    usable_h_mm: float = 0.0,
) -> None:
    """Draw the board map with non-color-dependent locator and anchor symbols."""
    bw, bd, _ = board_size(layout)
    c.saveState()
    c.translate(ox_pt, oy_pt)
    c.setStrokeColorRGB(0.86, 0.86, 0.86)
    for x in range(25, int(bw), 25):
        c.setLineWidth(0.35 if x % 50 == 0 else 0.18)
        c.line(x * mm * scale, 0, x * mm * scale, bd * mm * scale)
    for y in range(25, int(bd), 25):
        c.setLineWidth(0.35 if y % 50 == 0 else 0.18)
        c.line(0, y * mm * scale, bw * mm * scale, y * mm * scale)
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1.0)
    c.rect(0, 0, bw * mm * scale, bd * mm * scale, stroke=1, fill=0)

    for name, x, y, w, h in station_rects(layout):
        c.setStrokeColorRGB(0.32, 0.47, 0.67)
        c.setDash(5, 2)
        c.rect(x * mm * scale, y * mm * scale, w * mm * scale, h * mm * scale, stroke=1, fill=0)
        c.setDash()
        if labels:
            c.setFillColorRGB(0.12, 0.22, 0.36)
            c.setFont("Helvetica-Bold", 6.0)
            c.drawString((x + 3) * mm * scale, (y + h - 7) * mm * scale, f"STATION ENVELOPE - {name}")

    if include_tags:
        for row in direct_tag_rows(layout):
            tile, edge = row["tile_size_mm"], row["detection_edge_mm"]
            tx, ty = row["tile_origin_x_mm"], row["tile_origin_y_mm"]
            cx, cy = row["detection_center_x_mm"], row["detection_center_y_mm"]
            c.setStrokeColorRGB(0.05, 0.52, 0.25)
            c.setDash(4, 2)
            c.rect(tx * mm * scale, ty * mm * scale, tile * mm * scale, tile * mm * scale, stroke=1, fill=0)
            c.setDash(2, 1)
            c.setStrokeColorRGB(0.0, 0.55, 0.70)
            c.rect((cx - edge / 2) * mm * scale, (cy - edge / 2) * mm * scale, edge * mm * scale, edge * mm * scale, stroke=1, fill=0)
            c.setDash()
            if labels:
                c.setFillColorRGB(0.02, 0.36, 0.15)
                c.setFont("Helvetica-Bold", 5.0)
                c.drawString((tx + 2) * mm * scale, (ty + tile - 6) * mm * scale, f"TAG ONLY - {row['name']} ID{row['id']} - NO DRILL")

    ax0, ax1 = layout.get("arm_clamp_zone", {}).get("rear_edge_x_range", [225, 385])
    c.setStrokeColorRGB(0.82, 0.05, 0.05)
    c.setDash(5, 2)
    c.rect(ax0 * mm * scale, (bd - 30) * mm * scale, (ax1 - ax0) * mm * scale, 30 * mm * scale, stroke=1, fill=0)
    c.setDash()
    if labels:
        c.setFillColorRGB(0.70, 0, 0)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(((ax0 + ax1) / 2) * mm * scale, (bd - 18) * mm * scale, "NO DRILL - ROARM CLAMP ZONE")

    for row in board_feature_rows(layout):
        x, y = row["x"], row["y"]
        is_locator = row["type"] == "locator_pin_blind"
        if is_locator:
            c.setStrokeColorRGB(0.02, 0.28, 0.78)
            c.setDash()
            c.circle(x * mm * scale, y * mm * scale, 3.0 * mm * scale, stroke=1, fill=0)
            c.circle(x * mm * scale, y * mm * scale, 4.6 * mm * scale, stroke=1, fill=0)
        else:
            c.setStrokeColorRGB(0.92, 0.38, 0.02)
            c.setDash(2, 1)
            c.rect((x - 4.2) * mm * scale, (y - 4.2) * mm * scale, 8.4 * mm * scale, 8.4 * mm * scale, stroke=1, fill=0)
            c.setDash()
        c.setLineWidth(0.65)
        c.line((x - 3.5) * mm * scale, y * mm * scale, (x + 3.5) * mm * scale, y * mm * scale)
        c.line(x * mm * scale, (y - 3.5) * mm * scale, x * mm * scale, (y + 3.5) * mm * scale)
        if labels:
            c.setFillColorRGB(0.02, 0.20, 0.60) if is_locator else c.setFillColorRGB(0.68, 0.23, 0.00)
            c.setFont("Helvetica-Bold", 5.5)
            label_x, anchor = _feature_label_position(row, bw)
            draw_label = c.drawRightString if anchor == "right" else c.drawString
            suffix = "L-BLIND 6.0/15.0" if is_locator else "A-CENTER ONLY"
            draw_label(label_x * mm * scale, (y + 3.0) * mm * scale, f"{row['id']}  {suffix}")

    c.setFillColorRGB(0, 0, 0)
    if labels:
        c.setFont("Helvetica-Bold", 7.0)
        c.drawString(4 * mm * scale, 4 * mm * scale, "FRONT EDGE / Y=0")
        c.drawRightString((bw - 4) * mm * scale, 4 * mm * scale, "+X RIGHT")
        c.drawString(4 * mm * scale, (bd - 8) * mm * scale, "REAR / +Y")
        c.saveState()
        c.translate(4 * mm * scale, bd / 2 * mm * scale)
        c.rotate(90)
        c.drawCentredString(0, 0, "LEFT EDGE / X=0")
        c.restoreState()
    c.restoreState()
    if include_registration:
        _draw_registration_marks(c, ox_pt, oy_pt, usable_w_mm, usable_h_mm)


def _draw_cover_page(c: Any, layout: dict[str, Any], pw: float, ph: float) -> None:
    bw, bd, _ = board_size(layout)
    c.setFillColorRGB(0.08, 0.12, 0.18)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(16 * mm, ph - 18 * mm, f"RoCell {release_revision(layout)} - Printable Board Drill Guide")
    c.setFillColorRGB(0.72, 0.02, 0.02)
    c.roundRect(16 * mm, ph - 42 * mm, pw - 32 * mm, 16 * mm, 2 * mm, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(pw / 2, ph - 36 * mm, "OVERVIEW ONLY - NOT 1:1 - DO NOT MARK OR DRILL FROM THIS PAGE")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 8.5)
    cover_lines = [
        f"Finished board: {bw:.1f} x {bd:.1f} x 18.0 mm. Origin is the finished TOP, FRONT-LEFT corner.",
        "Home printer: print tile pages at Actual Size / 100%, one-sided, Landscape Letter. Never use Fit, Shrink, Poster, or duplex.",
        "Blue double-ring target = locator: 6.0 mm BLIND bore, 15.0 mm nominal depth. Preserve at least 2.0 mm of material below it.",
        "Orange dashed square = M4 ANCHOR CENTER ONLY. Final wood-bore size comes from the qualified anchor and completed FASTENER_MAP.csv.",
        "Green/cyan dashed squares are AprilTag setup references only. They are never drilled.",
        "The printed guide transfers centers; it does not replace square drilling, depth control, coordinate checks, or the complete station dry fit.",
    ]
    y = ph - 51 * mm
    for line in cover_lines:
        c.drawString(17 * mm, y, line)
        y -= 5.5 * mm
    scale = min((pw - 32 * mm) / (bw * mm), 102 * mm / (bd * mm))
    _draw_drill_layout(c, layout, 16 * mm, 18 * mm, scale=scale, labels=False, include_tags=True)
    c.setFont("Courier", 6.0)
    c.drawRightString(pw - 16 * mm, 12 * mm, f"SOURCE LAYOUT SHA-256 {layout_sha256()}")


def _draw_schedule_page(c: Any, layout: dict[str, Any], pw: float, ph: float) -> None:
    c.setFont("Helvetica-Bold", 16)
    c.drawString(14 * mm, ph - 16 * mm, "Hole Schedule - Verify Every Center Before Drilling")
    c.setFont("Helvetica", 7.2)
    c.drawString(14 * mm, ph - 23 * mm, "X is measured from the finished LEFT edge. Y is measured from the finished FRONT edge. Right/rear values are independent edge cross-checks.")
    c.drawString(14 * mm, ph - 28 * mm, "No numeric hand-drilling positional tolerance has been released. If the template, edge measurements, or dry fit disagree, place the step on HOLD.")
    rows = board_feature_rows(layout)
    columns = [
        ("ID", 38 * mm), ("TYPE / ACTION", 49 * mm), ("X LEFT", 19 * mm),
        ("Y FRONT", 19 * mm), ("FROM RIGHT", 22 * mm), ("FROM REAR", 22 * mm),
        ("FABRICATION CONTROL", pw - 28 * mm - 169 * mm),
    ]
    x0, y_top = 14 * mm, ph - 36 * mm
    row_h = 10.3 * mm
    x = x0
    c.setFillColorRGB(0.13, 0.20, 0.31)
    c.rect(x0, y_top - row_h, sum(width for _, width in columns), row_h, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 6.6)
    for label, width in columns:
        c.drawString(x + 1.5 * mm, y_top - 6.4 * mm, label)
        x += width
    c.setFillColorRGB(0, 0, 0)
    y = y_top - row_h
    for index, row in enumerate(rows):
        y -= row_h
        if index % 2 == 0:
            c.setFillColorRGB(0.95, 0.96, 0.98)
            c.rect(x0, y, sum(width for _, width in columns), row_h, stroke=0, fill=1)
        c.setStrokeColorRGB(0.72, 0.74, 0.78)
        c.rect(x0, y, sum(width for _, width in columns), row_h, stroke=1, fill=0)
        is_locator = row["type"] == "locator_pin_blind"
        values = [
            row["id"],
            "L-BLIND / DRILL" if is_locator else "A-ANCHOR / CENTER ONLY",
            f"{row['left_edge_x_mm']:.2f}", f"{row['front_edge_y_mm']:.2f}",
            f"{row['right_edge_mm']:.2f}", f"{row['rear_edge_mm']:.2f}",
            (
                "6.0 mm blind; 15.0 mm nominal; depth stop; no breakthrough"
                if is_locator else
                "Final bit/bore only from completed FASTENER_MAP and tested anchor"
            ),
        ]
        x = x0
        for (label, width), value in zip(columns, values):
            c.setFillColorRGB(0.02, 0.20, 0.60) if is_locator else c.setFillColorRGB(0.56, 0.20, 0.00)
            font_name = "Helvetica-Bold" if label in {"ID", "TYPE / ACTION"} else "Helvetica"
            c.setFont(font_name, 6.2)
            lines = _wrapped_lines(c, str(value), width - 3 * mm, font_name, 6.2)[:2]
            for line_index, line in enumerate(lines):
                c.drawString(x + 1.5 * mm, y + 6.2 * mm - line_index * 3.2 * mm, line)
            x += width
    c.setFillColorRGB(0.72, 0.02, 0.02)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(14 * mm, 10 * mm, "STOP: the nine orange anchor symbols are center targets, not final board-bore diameters.")


def _draw_assembly_page(
    c: Any, layout: dict[str, Any], pw: float, ph: float,
    usable_w_mm: float, usable_h_mm: float,
) -> None:
    c.setFont("Helvetica-Bold", 16)
    c.drawString(14 * mm, ph - 16 * mm, "Assemble the Nine 1:1 Tiles Before Marking the Board")
    c.setFont("Helvetica", 8)
    c.drawString(14 * mm, ph - 23 * mm, "Rows A/B/C run FRONT to REAR. Columns 1/2/3 run LEFT to RIGHT. Adjacent tiles overlap by exactly 12.0 mm.")
    grid_x, grid_y = 18 * mm, 43 * mm
    cell_w, cell_h = 45 * mm, 33 * mm
    for row in range(3):
        for col in range(3):
            tile = f"{chr(65 + row)}{col + 1}"
            x = grid_x + col * cell_w
            y = grid_y + row * cell_h
            c.setFillColorRGB(0.92, 0.95, 0.98)
            c.setStrokeColorRGB(0.18, 0.31, 0.48)
            c.rect(x, y, cell_w - 2 * mm, cell_h - 2 * mm, stroke=1, fill=1)
            c.setFillColorRGB(0.08, 0.15, 0.25)
            c.setFont("Helvetica-Bold", 15)
            c.drawCentredString(x + (cell_w - 2 * mm) / 2, y + 13 * mm, tile)
            c.setFont("Helvetica", 6.4)
            c.drawCentredString(x + (cell_w - 2 * mm) / 2, y + 6 * mm, f"page {4 + row * 3 + col}")
    c.setFont("Helvetica-Bold", 8)
    c.drawString(grid_x, grid_y - 8 * mm, "FRONT / Y=0")
    c.drawString(grid_x, grid_y + 3 * cell_h + 2 * mm, "REAR / +Y")
    c.drawString(grid_x + 3 * cell_w - 12 * mm, grid_y - 8 * mm, "+X RIGHT")

    steps = [
        "1. Print pages 4-12 at Actual Size / 100%, Landscape Letter, one-sided. Do not print page borders as a Poster job.",
        "2. Measure both the horizontal X bar and vertical Y bar on every tile. Each must be 100.0 +/- 0.2 mm. Reject any sheet that fails.",
        "3. Arrange A1-A3 at the front, B1-B3 in the middle, and C1-C3 at the rear. Never butt the paper edges together.",
        "4. Overlay adjacent sheets by 12.0 mm. Align every repeated purple MATCH target with its identical ID. Use a window/light or pinholes if needed.",
        "5. Tape seams without stretching paper. Confirm the assembled board outline is nominally 610.0 x 457.0 mm and both diagonals are nominally 762.200 mm.",
        "6. Place the assembled guide on the finished TOP face. Match the FRONT, LEFT, RIGHT, and REAR board outlines; tape outside station/load areas.",
        "7. Independently compare every blue/orange center with the schedule. Center-punch only after the full pattern, board orientation, and all repeated marks agree.",
        "8. Remove all paper. Drill locators and anchors as two separate operations. Never drill through a blind-locator pilot.",
        "9. Passing scale bars and match marks does not establish final positional acceptance. Square drilling, measured depths, completed FASTENER_MAP rows, and the full station dry fit remain mandatory.",
    ]
    x = 166 * mm
    y = ph - 39 * mm
    max_width = pw - x - 15 * mm
    for step in steps:
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica", 7.6)
        lines = _wrapped_lines(c, step, max_width, "Helvetica", 7.6)
        for line in lines:
            c.drawString(x, y, line)
            y -= 4.2 * mm
        y -= 1.2 * mm
    c.setFillColorRGB(0.72, 0.02, 0.02)
    c.setFont("Helvetica-Bold", 8.3)
    c.drawString(14 * mm, 12 * mm, "STOP if a scale bar, match target, board edge, coordinate, or dry-fit result disagrees. Do not average the error away.")


def _draw_tile_map(c: Any, pw: float, ph: float, active_row: int, active_col: int) -> None:
    base_x, base_y = pw - 47 * mm, ph - 17 * mm
    cell = 5.3 * mm
    for row in range(3):
        for col in range(3):
            c.setFillColorRGB(0.18, 0.42, 0.72) if (row, col) == (active_row, active_col) else c.setFillColorRGB(0.91, 0.93, 0.96)
            c.setStrokeColorRGB(0.25, 0.30, 0.38)
            c.rect(base_x + col * cell, base_y + row * cell, cell, cell, stroke=1, fill=1)
            c.setFillColorRGB(1, 1, 1) if (row, col) == (active_row, active_col) else c.setFillColorRGB(0.12, 0.17, 0.25)
            c.setFont("Helvetica-Bold", 4.5)
            c.drawCentredString(base_x + col * cell + cell / 2, base_y + row * cell + 1.5 * mm, f"{chr(65 + row)}{col + 1}")


def generate_tiled_pdf(layout: dict[str, Any]) -> None:
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.pdfgen import canvas

    page = landscape(letter)
    pw, ph = page
    left_margin = 18 * mm
    right_margin = 22 * mm
    bottom_margin = 20 * mm
    top_margin = 18 * mm
    usable_w = pw - left_margin - right_margin
    usable_h = ph - bottom_margin - top_margin
    usable_w_mm = usable_w / mm
    usable_h_mm = usable_h / mm
    stride_x = usable_w - TILE_OVERLAP_MM * mm
    stride_y = usable_h - TILE_OVERLAP_MM * mm
    c = canvas.Canvas(str(LETTER_DRILL_GUIDE), pagesize=page, pageCompression=1, invariant=1)
    c.setTitle(f"RoCell {release_revision(layout)} Letter 1:1 board drill guide")
    c.setAuthor("RoCell controlled drawing generator")

    _draw_cover_page(c, layout, pw, ph)
    c.showPage()
    _draw_schedule_page(c, layout, pw, ph)
    c.showPage()
    _draw_assembly_page(c, layout, pw, ph, usable_w_mm, usable_h_mm)
    c.showPage()

    for row in range(3):
        for col in range(3):
            tile_id = f"{chr(65 + row)}{col + 1}"
            x0_pt = col * stride_x
            y0_pt = row * stride_y
            c.setFillColorRGB(0.07, 0.12, 0.19)
            c.setFont("Helvetica-Bold", 10.5)
            c.drawString(
                18 * mm, ph - 11.5 * mm,
                f"DRILL TILE {tile_id} - 1:1 - X {x0_pt/mm:.1f}..{(x0_pt + usable_w)/mm:.1f} - Y {y0_pt/mm:.1f}..{(y0_pt + usable_h)/mm:.1f} mm",
            )
            _draw_tile_map(c, pw, ph, row, col)
            c.setFillColorRGB(0.72, 0.02, 0.02)
            c.setFont("Helvetica-Bold", 6.4)
            c.drawCentredString(pw / 2, ph - 16.2 * mm, "ANCHORS: CENTER-PUNCH ONLY - FINAL BOARD BORE COMES FROM COMPLETED FASTENER_MAP.csv")
            c.saveState()
            clip = c.beginPath()
            clip.rect(left_margin, bottom_margin, usable_w, usable_h)
            c.clipPath(clip, stroke=0, fill=0)
            _draw_drill_layout(
                c, layout, left_margin - x0_pt, bottom_margin - y0_pt,
                scale=1.0, labels=True, include_tags=True, include_registration=True,
                usable_w_mm=usable_w_mm, usable_h_mm=usable_h_mm,
            )
            c.restoreState()
            c.setStrokeColorRGB(0.25, 0.28, 0.34)
            c.setLineWidth(0.6)
            c.rect(left_margin, bottom_margin, usable_w, usable_h, stroke=1, fill=0)
            _draw_scale_controls(c, pw, ph, tile_id)
            c.setFont("Courier", 5.3)
            c.setFillColorRGB(0.15, 0.17, 0.22)
            c.drawString(18 * mm, 4.8 * mm, f"RC03-INT-R1  TILE {tile_id}  SOURCE {layout_sha256()[:16]}  PAGE {4 + row * 3 + col}/12")
            c.showPage()
    c.save()
    shutil.copyfile(LETTER_DRILL_GUIDE, LEGACY_LETTER_TEMPLATE)


def generate_full_size_pdf(layout: dict[str, Any]) -> None:
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas

    page = (36 * inch, 24 * inch)
    pw, ph = page
    bw, bd, _ = board_size(layout)
    board_x = (pw - bw * mm) / 2.0
    board_y = (ph - bd * mm) / 2.0
    c = canvas.Canvas(str(FULL_SIZE_DRILL_GUIDE), pagesize=page, pageCompression=1, invariant=1)
    c.setTitle(f"RoCell {release_revision(layout)} 24x36 full-size board drill guide")
    c.setAuthor("RoCell controlled drawing generator")
    c.setFont("Helvetica-Bold", 18)
    c.drawString(18 * mm, ph - 18 * mm, f"RoCell {release_revision(layout)} - 24 x 36 in FULL-SIZE Board Drill Guide")
    c.setFillColorRGB(0.72, 0.02, 0.02)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(18 * mm, ph - 27 * mm, "PRINT ONE-SIDED AT ACTUAL SIZE / 100%. VERIFY BOTH 100 mm BARS. ANCHOR SQUARES ARE CENTER TARGETS ONLY.")
    _draw_drill_layout(c, layout, board_x, board_y, scale=1.0, labels=True, include_tags=True)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 8)
    c.drawString(18 * mm, 26 * mm, "Blue double ring: 6.0 mm blind locator, 15.0 mm nominal depth. Orange dashed square: M4 anchor center only; final bore from FASTENER_MAP.csv.")
    c.drawString(18 * mm, 20 * mm, f"Board outline: {bw:.1f} x {bd:.1f} mm. Origin: finished TOP, FRONT-LEFT. Nominal diagonal: {math.hypot(bw, bd):.3f} mm.")
    c.setFont("Courier", 6.3)
    c.drawString(18 * mm, 8 * mm, f"SOURCE LAYOUT SHA-256 {layout_sha256()}")
    _draw_scale_controls(c, pw, ph, "FULL-SIZE", horizontal_y_mm=38.0, instruction_y_mm=11.0)
    c.save()


def generate_preview_png(layout: dict[str, Any]) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle

    bw, bd, _ = board_size(layout)
    fig, ax = plt.subplots(figsize=(13, 9))
    ax.add_patch(Rectangle((0, 0), bw, bd, facecolor="#f4f1ea", edgecolor="black", linewidth=2))
    for name, x, y, w, h in station_rects(layout):
        ax.add_patch(Rectangle((x, y), w, h, facecolor="none", edgecolor="#2f6fb0", linewidth=1.5))
        ax.text(x + w / 2, y + h / 2, name, ha="center", va="center", fontsize=8)
    for row in direct_tag_rows(layout):
        tile, edge = row["tile_size_mm"], row["detection_edge_mm"]
        tx, ty = row["tile_origin_x_mm"], row["tile_origin_y_mm"]
        cx, cy = row["detection_center_x_mm"], row["detection_center_y_mm"]
        ax.add_patch(Rectangle((tx, ty), tile, tile, facecolor="none", edgecolor="#28895a", linewidth=1.5))
        ax.add_patch(Rectangle((cx - edge / 2, cy - edge / 2), edge, edge, facecolor="none", edgecolor="#008caa", linewidth=0.8, linestyle="--"))
        ax.plot([cx, cx], [cy, cy + 18], color="#7b2cbf", linewidth=0.8)
        ax.text(cx, cy, f"{row['name']}\nID{row['id']}", ha="center", va="center", fontsize=6)
    ax0, ax1 = layout.get("arm_clamp_zone", {}).get("rear_edge_x_range", [225, 385])
    ax.add_patch(Rectangle((ax0, bd - 30), ax1 - ax0, 30, facecolor="none", edgecolor="red", linestyle="--", linewidth=1.5))
    ax.text((ax0 + ax1) / 2, bd - 15, "RoArm clamp zone", ha="center", va="center", fontsize=8, color="red")
    for row in board_feature_rows(layout):
        is_locator = row["type"] == "locator_pin_blind"
        if is_locator:
            ax.add_patch(Circle((row["x"], row["y"]), row["diameter"] / 2, facecolor="none", edgecolor="#075bd8", linewidth=0.9))
            ax.add_patch(Circle((row["x"], row["y"]), 4.6, facecolor="none", edgecolor="#075bd8", linewidth=0.7))
        else:
            ax.add_patch(Rectangle(
                (row["x"] - 4.2, row["y"] - 4.2), 8.4, 8.4,
                facecolor="none", edgecolor="#e85f00", linestyle="--", linewidth=0.9,
            ))
        label_x, anchor = _feature_label_position(row, bw)
        suffix = "BLIND 6.0/15.0" if is_locator else "CENTER ONLY"
        ax.text(
            label_x, row["y"] + 3, f"{row['id']} {suffix}", fontsize=5,
            color="#075bd8" if is_locator else "#a13b00", ha=anchor,
        )
    ax.set_xlim(-20, bw + 20)
    ax.set_ylim(-20, bd + 35)
    ax.set_aspect("equal")
    ax.set_xlabel("X mm - right")
    ax.set_ylabel("Y mm - rear/toward arm")
    ax.set_title(f"RoCell {release_revision(layout)} board setup layout ({bw:g} x {bd:g} mm)")
    ax.grid(True, linewidth=0.25, alpha=0.5)
    fig.tight_layout()
    fig.savefig(IMAGES / "board_layout_dimensioned.png", dpi=180)
    plt.close(fig)


def main() -> None:
    layout = load_layout()
    generate_csv(layout)
    generate_dxf(layout)
    generate_svg(layout)
    generate_tiled_pdf(layout)
    generate_full_size_pdf(layout)
    generate_preview_png(layout)
    print(json.dumps({
        "revision": release_revision(layout),
        "board_features": len(board_feature_rows(layout)),
        "direct_tags": len(direct_tag_rows(layout)),
        "layout_sha256": layout_sha256(),
        "letter_guide": str(LETTER_DRILL_GUIDE.relative_to(ROOT)),
        "letter_guide_sha256": hashlib.sha256(LETTER_DRILL_GUIDE.read_bytes()).hexdigest(),
        "full_size_guide": str(FULL_SIZE_DRILL_GUIDE.relative_to(ROOT)),
        "full_size_guide_sha256": hashlib.sha256(FULL_SIZE_DRILL_GUIDE.read_bytes()).hexdigest(),
        "status": "generated board setup drawings",
    }, indent=2))


if __name__ == "__main__":
    main()
