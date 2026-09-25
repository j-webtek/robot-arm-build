#!/usr/bin/env python3
"""Generate RC03 direct-board AprilTags and the ChArUco calibration target."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from generate_drawings import (
    direct_tag_rows,
    direct_tag_spec,
    layout_sha256,
    load_layout,
    release_revision,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fiducials"
MEASUREMENT_PATH = ROOT / "config" / "measurement_record.json"
OUT.mkdir(parents=True, exist_ok=True)

TAG_FAMILY = "tag36h11"
TAG_IDS = list(range(6))
TAG_MEASUREMENT_GATE = "tag_plane_placement_measured"

# Canonical OpenCV DICT_APRILTAG_36h11 markers 0-5, including the one-cell
# black border. Keeping the six released patterns here makes tag artwork
# generation deterministic and independent of an OpenCV binary installation.
# ``0`` is black and ``1`` is white.
APRILTAG_36H11_8X8 = {
    0: ("00000000", "00010000", "00110100", "00001010", "00001100", "01011100", "01010110", "00000000"),
    1: ("00000000", "01001000", "01011010", "00001100", "00011110", "01110100", "00110110", "00000000"),
    2: ("00000000", "00111000", "00010000", "01001000", "00000010", "00100100", "01110110", "00000000"),
    3: ("00000000", "00001100", "00100110", "01001010", "01110010", "01110000", "01001110", "00000000"),
    4: ("00000000", "00100010", "00000010", "00101000", "01111010", "00011110", "00101110", "00000000"),
    5: ("00000000", "00011010", "00111000", "01101010", "00110110", "01000110", "00011110", "00000000"),
}


def tag_dimensions(layout: dict[str, Any]) -> tuple[float, float, float]:
    spec = direct_tag_spec(layout)
    detection = float(spec["detection_edge_mm"])
    tile = float(spec["tile_size_mm"])
    return detection, tile, (tile - detection) / 2.0


def marker_grid(tag_id: int) -> tuple[tuple[int, ...], ...]:
    try:
        encoded = APRILTAG_36H11_8X8[tag_id]
    except KeyError as exc:
        raise ValueError(f"Only released tag IDs {TAG_IDS} may be generated") from exc
    return tuple(tuple(255 if cell == "1" else 0 for cell in row) for row in encoded)


def write_tag_svg(tag_id: int, path: Path, detection_mm: float, tile_mm: float, quiet_mm: float) -> None:
    grid = marker_grid(tag_id)
    size_cells = len(grid)
    cell = detection_mm / size_cells
    drawing = svgwrite.Drawing(
        str(path), size=(f"{tile_mm}mm", f"{tile_mm}mm"),
        viewBox=f"0 0 {tile_mm} {tile_mm}",
    )
    drawing.add(drawing.rect(insert=(0, 0), size=(tile_mm, tile_mm), fill="white"))
    for row in range(size_cells):
        for column in range(size_cells):
            if grid[row][column] < 128:
                drawing.add(drawing.rect(
                    insert=(quiet_mm + column * cell, quiet_mm + row * cell),
                    size=(cell, cell), fill="black", stroke="none",
                ))
    drawing.save()


def write_tag_png(
    tag_id: int, path: Path, detection_mm: float, tile_mm: float, dpi: int = 600,
) -> None:
    pixels = int(round(tile_mm / 25.4 * dpi))
    marker_pixels = int(round(detection_mm / 25.4 * dpi))
    quiet_pixels = (pixels - marker_pixels) // 2
    grid = marker_grid(tag_id)
    size_cells = len(grid)
    canvas_image = Image.new("L", (pixels, pixels), 255)
    draw = ImageDraw.Draw(canvas_image)
    for row in range(size_cells):
        y0 = quiet_pixels + round(row * marker_pixels / size_cells)
        y1 = quiet_pixels + round((row + 1) * marker_pixels / size_cells)
        for column in range(size_cells):
            if grid[row][column] >= 128:
                continue
            x0 = quiet_pixels + round(column * marker_pixels / size_cells)
            x1 = quiet_pixels + round((column + 1) * marker_pixels / size_cells)
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=0)
    canvas_image.save(path, dpi=(dpi, dpi))


def write_tag_sheet_pdf(
    revision: str, detection_mm: float, tile_mm: float,
) -> None:
    path = OUT / "apriltag36h11_ID0-5_40mm_detection_edge.pdf"
    pdf = canvas.Canvas(str(path), pagesize=letter)
    page_width, page_height = letter
    pdf.setTitle(f"RoCell {revision} AprilTag 36h11 set")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(16 * mm, page_height - 16 * mm, f"RoCell {revision} direct-board runtime AprilTags")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(
        16 * mm, page_height - 23 * mm,
        f"Print at 100% / Actual Size. Detection edge {detection_mm:.1f} mm; cut tile {tile_mm:.1f} mm.",
    )
    pdf.drawString(
        16 * mm, page_height - 29 * mm,
        "Do not use Fit, Shrink, or borderless scaling. The page-top edge points toward board +Y/rear.",
    )
    start_x = 35 * mm
    start_y = page_height - 55 * mm
    gap_x = 85 * mm
    gap_y = 70 * mm
    for index, tag_id in enumerate(TAG_IDS):
        column, row = index % 2, index // 2
        x = start_x + column * gap_x
        y = start_y - row * gap_y - tile_mm * mm
        png = OUT / f"tag36h11_id{tag_id:02d}_tile55_marker40.png"
        pdf.drawImage(str(png), x, y, tile_mm * mm, tile_mm * mm, mask="auto")
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(x + tile_mm * mm / 2, y - 4 * mm, f"ID {tag_id}   TOP = +Y")
    bar_x, bar_y = 55 * mm, 12 * mm
    pdf.setLineWidth(1)
    pdf.line(bar_x, bar_y, bar_x + 100 * mm, bar_y)
    for tick in range(11):
        height = 4 * mm if tick in (0, 10) else 2 * mm
        pdf.line(bar_x + tick * 10 * mm, bar_y - height / 2, bar_x + tick * 10 * mm, bar_y + height / 2)
    pdf.setFont("Helvetica", 7)
    pdf.drawString(bar_x, bar_y + 4 * mm, "100 mm print-scale check")
    pdf.save()


def write_tag_sheet_svg(detection_mm: float, tile_mm: float, quiet_mm: float) -> None:
    width, height = 190.0, 225.0
    drawing = svgwrite.Drawing(
        str(OUT / "apriltag36h11_ID0-5_sheet.svg"),
        size=(f"{width}mm", f"{height}mm"), viewBox=f"0 0 {width} {height}",
    )
    drawing.add(drawing.rect(insert=(0, 0), size=(width, height), fill="white"))
    for index, tag_id in enumerate(TAG_IDS):
        column, row = index % 2, index // 2
        x, y = 20 + column * 90, 15 + row * 68
        grid = marker_grid(tag_id)
        size_cells = len(grid)
        cell = detection_mm / size_cells
        drawing.add(drawing.rect(
            insert=(x, y), size=(tile_mm, tile_mm), fill="white",
            stroke="#999", stroke_width=0.2,
        ))
        for grid_row in range(size_cells):
            for grid_column in range(size_cells):
                if grid[grid_row][grid_column] < 128:
                    drawing.add(drawing.rect(
                        insert=(x + quiet_mm + grid_column * cell, y + quiet_mm + grid_row * cell),
                        size=(cell, cell), fill="black",
                    ))
        drawing.add(drawing.text(
            f"ID {tag_id}   TOP = +Y",
            insert=(x + tile_mm / 2, y + tile_mm + 5), text_anchor="middle",
            font_size="4px", font_family="sans-serif",
        ))
    drawing.add(drawing.line(start=(45, 218), end=(145, 218), stroke="black", stroke_width=0.5))
    for tick in range(11):
        height_tick = 4 if tick in (0, 10) else 2
        drawing.add(drawing.line(
            start=(45 + tick * 10, 218 - height_tick / 2),
            end=(45 + tick * 10, 218 + height_tick / 2),
            stroke="black", stroke_width=0.4,
        ))
    drawing.add(drawing.text(
        "100 mm", insert=(95, 214), text_anchor="middle",
        font_size="4px", font_family="sans-serif",
    ))
    drawing.save()


def write_charuco(revision: str) -> None:
    squares_x, squares_y = 5, 7
    square_mm, marker_mm = 25.0, 17.5
    board_width, board_height = squares_x * square_mm, squares_y * square_mm
    pixels_per_mm = 24
    png = OUT / "charuco_5x7_square25_marker17_5.png"
    if not png.exists():
        raise RuntimeError(
            "The released ChArUco raster is missing. Restore "
            f"{png.name} before regenerating its revision-controlled wrapper."
        )
    expected_pixels = (int(board_width * pixels_per_mm), int(board_height * pixels_per_mm))
    with Image.open(png) as existing:
        image = existing.convert("L").copy()
    if image.size != expected_pixels:
        raise ValueError(f"Unexpected ChArUco raster size {image.size}; expected {expected_pixels}")
    image.save(png, dpi=(pixels_per_mm * 25.4, pixels_per_mm * 25.4))
    pdf_path = OUT / "charuco_5x7_square25_marker17_5_1to1.pdf"
    pdf = canvas.Canvas(str(pdf_path), pagesize=letter)
    page_width, page_height = letter
    pdf.setTitle(f"RoCell {revision} ChArUco calibration board")
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(14 * mm, page_height - 15 * mm, f"RoCell {revision} camera calibration board - ChArUco")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(14 * mm, page_height - 22 * mm, "5 x 7 squares; square 25.0 mm; marker 17.5 mm; DICT_5X5_100.")
    pdf.drawString(14 * mm, page_height - 28 * mm, "Print at 100% / Actual Size on matte paper and mount perfectly flat.")
    x = (page_width - board_width * mm) / 2
    y = 45 * mm
    pdf.drawImage(str(png), x, y, board_width * mm, board_height * mm, mask="auto")
    pdf.setLineWidth(0.5)
    pdf.rect(x, y, board_width * mm, board_height * mm, stroke=1, fill=0)
    bar_x, bar_y = (page_width - 100 * mm) / 2, 25 * mm
    pdf.setLineWidth(1)
    pdf.line(bar_x, bar_y, bar_x + 100 * mm, bar_y)
    for tick in range(11):
        height_tick = 4 * mm if tick in (0, 10) else 2 * mm
        pdf.line(bar_x + tick * 10 * mm, bar_y - height_tick / 2, bar_x + tick * 10 * mm, bar_y + height_tick / 2)
    pdf.setFont("Helvetica", 7)
    pdf.drawString(bar_x, bar_y + 4 * mm, "100 mm print-scale check")
    pdf.save()
    metadata = {
        "schema_version": 2,
        "design_revision": revision,
        "type": "ChArUco",
        "dictionary": "DICT_5X5_100",
        "squares_x": squares_x,
        "squares_y": squares_y,
        "square_length_mm": square_mm,
        "marker_length_mm": marker_mm,
        "physical_width_mm": board_width,
        "physical_height_mm": board_height,
    }
    (OUT / "charuco_board_definition.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8",
    )


def _load_measurement_gate() -> tuple[str, dict[str, Any], dict[str, Any]]:
    if not MEASUREMENT_PATH.exists():
        return "NOT_TESTED", {}, {}
    document = json.loads(MEASUREMENT_PATH.read_text(encoding="utf-8"))
    gate = document.get("gates", {}).get(TAG_MEASUREMENT_GATE, {})
    return str(gate.get("status", "NOT_TESTED")), gate.get("recorded_values") or {}, gate


def _finite(value: Any, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def installed_tag_measurements() -> tuple[str, dict[str, dict[str, float]], dict[str, Any]]:
    status, recorded, gate = _load_measurement_gate()
    if status != "PASS":
        return "nominal_layout", {}, {
            "gate": TAG_MEASUREMENT_GATE,
            "status": status,
            "measurement_method": recorded.get("measurement_method"),
            "measurement_tool_id": recorded.get("measurement_tool_id"),
            "evidence_reference": recorded.get("evidence_reference"),
        }
    tags = recorded.get("tags")
    if not isinstance(tags, dict) or set(tags) != {"T0", "T1", "T2", "T3", "K0", "P0"}:
        raise ValueError(
            f"PASS {TAG_MEASUREMENT_GATE} must contain exactly six named tag measurements"
        )
    for field in ("measurement_method", "measurement_tool_id", "evidence_reference"):
        value = recorded.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"PASS {TAG_MEASUREMENT_GATE} requires nonblank {field}")
    parsed: dict[str, dict[str, float]] = {}
    for name, row in tags.items():
        if not isinstance(row, dict):
            raise ValueError(f"Measured tag {name} must be an object")
        required = {"center_x_mm", "center_y_mm", "plane_z_mm", "yaw_deg"}
        if set(row) != required:
            raise ValueError(f"Measured tag {name} keys must be exactly {sorted(required)}")
        parsed[name] = {key: _finite(row[key], f"{name}.{key}") for key in required}
    metadata = {
        "gate": TAG_MEASUREMENT_GATE,
        "status": status,
        "measurement_method": recorded.get("measurement_method"),
        "measurement_tool_id": recorded.get("measurement_tool_id"),
        "evidence_reference": recorded.get("evidence_reference"),
        "scope": gate.get("scope"),
    }
    return "measured_installation", parsed, metadata


def build_tag_map(layout: dict[str, Any]) -> dict[str, Any]:
    spec = direct_tag_spec(layout)
    expected_axes = {"+x": "right", "+y": "rear/toward arm", "+z": "up"}
    axes = layout.get("axes", expected_axes)
    if axes != expected_axes:
        raise ValueError(f"Unexpected board axes {axes!r}; expected {expected_axes!r}")
    coordinate_source, measured, measurement_metadata = installed_tag_measurements()
    tags: dict[str, dict[str, Any]] = {}
    for nominal in direct_tag_rows(layout):
        name = nominal["name"]
        if coordinate_source == "measured_installation":
            observed = measured[name]
            detection_center_xyz = [
                observed["center_x_mm"], observed["center_y_mm"], observed["plane_z_mm"],
            ]
            yaw = observed["yaw_deg"]
        else:
            detection_center_xyz = [
                nominal["detection_center_x_mm"],
                nominal["detection_center_y_mm"],
                spec["direct_tag_plane_nominal_z_mm"],
            ]
            yaw = nominal["expected_yaw_deg"]
        tags[name] = {
            "id": nominal["id"],
            "role": nominal["role"],
            "mounting": "direct_adhesive",
            "tile_origin_xy_mm": [nominal["tile_origin_x_mm"], nominal["tile_origin_y_mm"]],
            "nominal_detection_center_xy_mm": [
                nominal["detection_center_x_mm"], nominal["detection_center_y_mm"],
            ],
            "detection_center_xyz_mm": detection_center_xyz,
            "expected_yaw_deg_in_board_frame": yaw,
            "coordinate_source": coordinate_source,
        }
    return {
        "schema": "rocell.apriltag_map.v2",
        "schema_version": 2,
        "design_revision": release_revision(layout),
        "layout_sha256": layout_sha256(),
        "family": TAG_FAMILY,
        "detection_edge_mm": spec["detection_edge_mm"],
        "tile_size_mm": spec["tile_size_mm"],
        "mounting": "direct_adhesive",
        "board_z_reference": spec["board_z_reference"],
        "direct_tag_plane_nominal_z_mm": spec["direct_tag_plane_nominal_z_mm"],
        "coordinate_source": coordinate_source,
        "measurement": measurement_metadata,
        "board_axes": axes,
        "paper_top_edge_faces": "+Y / board rear for every tag",
        "tags": tags,
        "ids": {name: tags[name]["id"] for name in tags},
        "note": (
            "Configure tag size as the measured 40 mm detection edge (0.040 m). "
            "The tiles attach directly to the cured sealed board; never use the removed RC02 frames. "
            "Board-coordinate solving requires a PASS tag_plane_placement_measured gate."
        ),
    }


def write_tag_map(layout: dict[str, Any]) -> dict[str, Any]:
    tag_map = build_tag_map(layout)
    (OUT / "apriltag_map.json").write_text(
        json.dumps(tag_map, indent=2) + "\n", encoding="utf-8",
    )
    return tag_map


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--map-only", action="store_true",
        help="Regenerate only apriltag_map.json from layout and measurement records",
    )
    args = parser.parse_args()
    layout = load_layout()
    detection_mm, tile_mm, quiet_mm = tag_dimensions(layout)
    if not args.map_only:
        # Map-only remains independent of the optional OpenCV image stack.
        global Image, ImageDraw, letter, mm, canvas, svgwrite
        from PIL import Image, ImageDraw
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
        import svgwrite
        for tag_id in TAG_IDS:
            write_tag_svg(
                tag_id, OUT / f"tag36h11_id{tag_id:02d}_tile55_marker40.svg",
                detection_mm, tile_mm, quiet_mm,
            )
            write_tag_png(
                tag_id, OUT / f"tag36h11_id{tag_id:02d}_tile55_marker40.png",
                detection_mm, tile_mm,
            )
        write_tag_sheet_pdf(release_revision(layout), detection_mm, tile_mm)
        write_tag_sheet_svg(detection_mm, tile_mm, quiet_mm)
        write_charuco(release_revision(layout))
    generated_map = write_tag_map(layout)
    print(json.dumps({
        "design_revision": generated_map["design_revision"],
        "coordinate_source": generated_map["coordinate_source"],
        "layout_sha256": generated_map["layout_sha256"],
        "direct_tags": len(generated_map["tags"]),
        "status": "generated fiducials",
    }, indent=2))


if __name__ == "__main__":
    main()
