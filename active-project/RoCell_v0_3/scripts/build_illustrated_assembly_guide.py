#!/usr/bin/env python3
"""Build the printable RC03 illustrated assembly guide.

The guide is intentionally generated from released package data rather than
duplicating the fastener map or bill of materials in prose.  The 15 PNG panels
are explanatory views; dimensional authority remains with the released CAD,
configuration, drawings, and recorded physical acceptance results.
"""
from __future__ import annotations

import csv
import json
import math
import unicodedata
from pathlib import Path
from typing import Callable, Iterable, Sequence

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "output" / "assembly_guide" / "images"
OUTPUT_PDF = ROOT / "output" / "pdf" / "RC03_ILLUSTRATED_ASSEMBLY_GUIDE.pdf"
BOM_CSV = ROOT / "BOM.csv"
FASTENER_CSV = ROOT / "FASTENER_MAP.csv"
LAYOUT_JSON = ROOT / "config" / "workcell_layout.json"

PAGE_W, PAGE_H = landscape(letter)
MARGIN = 30.0
FOOTER_H = 22.0

INK = HexColor("#20262d")
MUTED = HexColor("#66717c")
PAPER = HexColor("#f6f8fa")
WHITE = colors.white
NAVY = HexColor("#162633")
BLUE = HexColor("#147bd1")
BLUE_DARK = HexColor("#0a5596")
BLUE_LIGHT = HexColor("#dceefa")
ORANGE = HexColor("#f2a019")
ORANGE_LIGHT = HexColor("#fff0d1")
TEAL = HexColor("#23a58b")
RED = HexColor("#d63b37")
RED_LIGHT = HexColor("#fde6e5")
GRAY = HexColor("#c6cdd3")
GRAY_LIGHT = HexColor("#edf1f4")
LINE = HexColor("#c9d1d8")

EXPECTED_PANELS: list[tuple[str, str]] = [
    ("01_prepare_board.png", "Prepare the board"),
    ("02_reinforce_and_clamp_arm.png", "Reinforce and clamp the arm"),
    ("03_install_keyboard_master.png", "Install keyboard master"),
    ("04_join_keyboard_slave.png", "Join keyboard slave"),
    ("05_load_keyboard_and_clamps.png", "Load and clamp keyboard"),
    ("06_install_phone_tcp_station.png", "Install phone and TCP station"),
    ("07_seat_phone_rail_and_cartridge.png", "Seat rail and TCP cartridge"),
    ("08_install_phone_service_hardware.png", "Install service hardware"),
    ("09_load_phone_and_route_cable.png", "Load phone and route cable"),
    ("10_verify_phone_no_go_zones.png", "Verify phone no-go zones"),
    ("11_transfer_tag_marks.png", "Transfer tag centers and direction"),
    ("12_apply_apriltags.png", "Apply the six AprilTags"),
    ("13_mount_camera_and_check_fov.png", "Resolve camera architecture hold"),
    ("14_assemble_compliant_tool.png", "Assemble compliant tool"),
    ("15_final_cell.png", "Final assembly check"),
]

EXPECTED_FASTENERS = [
    "KBL-HOLD-F",
    "KBL-HOLD-R",
    "KBL-CLAMP",
    "KBR-HOLD-F",
    "KBR-HOLD-R",
    "KBR-CLAMP",
    "PT-HOLD-TCP",
    "PT-HOLD-R1",
    "PT-HOLD-R2",
]

INSTALLED_SPARE_LABELS = {
    ("Board interface", "6 mm precision dowel pins"): "4 installed + 2 spares",
    ("Board interface", "M4 board threaded interfaces"): "9 installed + 3 spares",
    ("Board interface", "M4 station retention screws"): "7 installed + 3 spares",
    ("Board interface", "M4 station washers"): "9 installed + 3 spares",
    ("Assembly", "M4 low-profile keyboard clamp/retention screws"): "2 installed + 2 spares",
    ("Vision", "Full-surface matte adhesive AprilTag tiles"): "6 installed + 6 spares",
    ("Phone clamp", "M4 captured hex nuts"): "2 installed + 2 spares",
    ("TCP receiver", "M3 heat-set inserts"): "2 installed + 2 spares",
    ("TCP receiver", "M3 x 10 mm button-head screws"): "2 installed + 2 spares",
}


def safe_text(value: object) -> str:
    """Convert source text to the WinAnsi-safe character set used here."""
    text = str(value or "")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u2212", "-").replace("\u00b1", "+/-")
    text = unicodedata.normalize("NFKD", text)
    return text.encode("ascii", "ignore").decode("ascii")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{safe_text(k): safe_text(v) for k, v in row.items()}
                for row in csv.DictReader(handle)]


def wrap_lines(text: object, font: str, size: float, max_width: float) -> list[str]:
    words = safe_text(text).split()
    if not words:
        return [""]
    lines: list[str] = []
    line = words[0]
    for word in words[1:]:
        candidate = f"{line} {word}"
        if stringWidth(candidate, font, size) <= max_width:
            line = candidate
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def clipped_lines(
    text: object,
    font: str,
    size: float,
    max_width: float,
    max_lines: int,
) -> list[str]:
    lines = wrap_lines(text, font, size, max_width)
    if len(lines) <= max_lines:
        return lines
    lines = lines[:max_lines]
    tail = lines[-1]
    while tail and stringWidth(tail + "...", font, size) > max_width:
        tail = tail[:-1].rstrip()
    lines[-1] = tail + "..."
    return lines


def draw_wrapped(
    c: canvas.Canvas,
    text: object,
    x: float,
    y: float,
    max_width: float,
    *,
    font: str = "Helvetica",
    size: float = 9.0,
    leading: float | None = None,
    color: colors.Color = INK,
    max_lines: int | None = None,
) -> float:
    leading = leading or size * 1.25
    lines = wrap_lines(text, font, size, max_width)
    if max_lines is not None:
        lines = clipped_lines(text, font, size, max_width, max_lines)
    c.setFont(font, size)
    c.setFillColor(color)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def draw_checkbox_line(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    *,
    size: float = 9.0,
    color: colors.Color = INK,
) -> float:
    box = 9.0
    c.setStrokeColor(color)
    c.setLineWidth(0.8)
    c.rect(x, y - box + 1.0, box, box, stroke=1, fill=0)
    lines = wrap_lines(text, "Helvetica", size, width - box - 8.0)
    c.setFont("Helvetica", size)
    c.setFillColor(color)
    baseline = y
    for line in lines:
        c.drawString(x + box + 7.0, baseline, line)
        baseline -= size * 1.25
    return min(y - 15.0, baseline - 3.0)


def draw_title_bar(
    c: canvas.Canvas,
    section: str,
    title: str,
    subtitle: str = "",
) -> float:
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 66, PAGE_W, 66, stroke=0, fill=1)
    c.setFillColor(ORANGE)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(MARGIN, PAGE_H - 20, safe_text(section).upper())
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(MARGIN, PAGE_H - 45, safe_text(title))
    if subtitle:
        c.setFont("Helvetica", 8.5)
        c.setFillColor(GRAY)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 43, safe_text(subtitle))
    return PAGE_H - 84


def draw_footer(c: canvas.Canvas, revision: str, page_no: int, page_total: int) -> None:
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(MARGIN, FOOTER_H, PAGE_W - MARGIN, FOOTER_H)
    c.setFont("Helvetica", 6.8)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, 10.5, f"RoCell {revision} - illustrated assembly guide")
    c.setFont("Helvetica-Bold", 6.8)
    c.setFillColor(RED)
    c.drawCentredString(PAGE_W / 2.0, 10.5,
                        "DIGITAL VALIDATION ONLY - PHYSICAL RELEASE REQUIRES RECORDED TESTS")
    c.setFont("Helvetica", 6.8)
    c.setFillColor(MUTED)
    c.drawRightString(PAGE_W - MARGIN, 10.5, f"PAGE {page_no} / {page_total}")


def draw_card(
    c: canvas.Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    fill: colors.Color = WHITE,
    stroke: colors.Color = LINE,
    radius: float = 8.0,
) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(0.8)
    c.roundRect(x, y, width, height, radius, stroke=1, fill=1)


def draw_fitted_image(
    c: canvas.Canvas,
    path: Path,
    x: float,
    y: float,
    max_width: float,
    max_height: float,
) -> tuple[float, float, float, float]:
    with PILImage.open(path) as image:
        image_w, image_h = image.size
    scale = min(max_width / image_w, max_height / image_h)
    width, height = image_w * scale, image_h * scale
    px = x + (max_width - width) / 2.0
    py = y + (max_height - height) / 2.0
    c.drawImage(ImageReader(str(path)), px, py, width, height,
                preserveAspectRatio=True, mask="auto")
    return px, py, width, height


def split_bom(bom: Sequence[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in bom:
        grouped.setdefault(row["category"], []).append(row)
    return grouped


def draw_cover(c: canvas.Canvas, revision: str) -> None:
    c.setFillColor(NAVY)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    c.setFillColor(ORANGE)
    c.rect(0, PAGE_H - 13, PAGE_W, 13, stroke=0, fill=1)

    c.setFillColor(ORANGE)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(42, PAGE_H - 52, "ROCELL OPEN INDEXED WORKCELL")
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 31)
    c.drawString(42, PAGE_H - 94, "ILLUSTRATED")
    c.drawString(42, PAGE_H - 129, "ASSEMBLY GUIDE")
    c.setFont("Helvetica", 12)
    c.setFillColor(GRAY)
    c.drawString(42, PAGE_H - 157, "QIDI Plus4 optimized print package")
    c.drawString(42, PAGE_H - 175, "305 x 305 x 280 mm nominal envelope")

    hero_x, hero_y, hero_w, hero_h = 348, 137, 410, 320
    c.setFillColor(WHITE)
    c.roundRect(hero_x - 7, hero_y - 7, hero_w + 14, hero_h + 14, 12, stroke=0, fill=1)
    draw_fitted_image(c, IMAGE_DIR / "15_final_cell.png", hero_x, hero_y,
                      hero_w, hero_h)

    draw_card(c, 42, 180, 270, 126, fill=HexColor("#213746"), stroke=HexColor("#365263"))
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(58, 283, "BUILD ARCHITECTURE")
    y = 260
    for line in [
        "610 x 457 x 18 mm precut board",
        "3 indexed printed stations",
        "4 locator pins + 9 M4 retainers",
        "Direct-applied T0-T3 / K0 / P0 tags",
        "No router. No CNC.",
    ]:
        c.setFillColor(ORANGE if line == "No router. No CNC." else GRAY_LIGHT)
        c.setFont("Helvetica-Bold" if line == "No router. No CNC." else "Helvetica", 9.5)
        c.drawString(58, y, line)
        y -= 19

    c.setFillColor(RED_LIGHT)
    c.roundRect(42, 83, 716, 68, 8, stroke=0, fill=1)
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(58, 126, "RELEASE STATUS: UNRELEASED")
    c.setFillColor(INK)
    c.setFont("Helvetica", 9.2)
    c.drawString(58, 106,
                 "Digital geometry and document checks do not constitute physical release.")
    c.drawString(58, 91,
                 "Build, measure, proof-load, commission, record, and sign every acceptance gate.")

    c.setFillColor(GRAY)
    c.setFont("Helvetica", 8)
    c.drawString(42, 47, f"REVISION {revision}")
    c.drawRightString(PAGE_W - 42, 47, "Print at 100 percent scale - landscape letter")


def draw_release_and_safety(c: canvas.Canvas, revision: str) -> None:
    y = draw_title_bar(c, "Release gate", "Stop before fabrication if any box is open",
                       revision)
    c.setFillColor(RED_LIGHT)
    c.roundRect(MARGIN, y - 78, PAGE_W - 2 * MARGIN, 66, 8, stroke=0, fill=1)
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(MARGIN + 16, y - 40, "UNRELEASED UNTIL PHYSICAL ACCEPTANCE IS RECORDED")
    c.setFillColor(INK)
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN + 16, y - 58,
                 "The drawings and renders communicate intent. They cannot prove fit, strength, motion clearance, or camera performance.")

    col_w = (PAGE_W - 2 * MARGIN - 18) / 2.0
    left_x, right_x = MARGIN, MARGIN + col_w + 18
    box_y, box_h = 72, 346
    draw_card(c, left_x, box_y, col_w, box_h, fill=WHITE)
    draw_card(c, right_x, box_y, col_w, box_h, fill=WHITE)

    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(BLUE_DARK)
    c.drawString(left_x + 16, box_y + box_h - 28, "BEFORE DRILLING OR INSERTS")
    yy = box_y + box_h - 52
    for item in [
        "BOM, FASTENER_MAP.csv, and revision agree",
        "Board is 610 x 457 x 18 mm and secured against shift",
        "Board is flat, sealed equally on both faces, and fully cured",
        "All fit coupons passed after cooling",
        "M4 anchor type and final bore were selected on the 18 mm cutoff test",
        "Arm reinforcement plate is measured metal and fits the factory clamp load path",
        "E-stop is mounted outside robot reach",
        "Power is locked out for drilling, insert installation, and measurement",
        "1:1 template scale has been verified in X and Y",
        "No router or CNC operation is planned or required",
    ]:
        yy = draw_checkbox_line(c, item, left_x + 16, yy, col_w - 32, size=8.3)

    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(RED)
    c.drawString(right_x + 16, box_y + box_h - 28, "NO-GO CONDITIONS")
    yy = box_y + box_h - 52
    for item in [
        "Do not drill direct AprilTag sites",
        "Do not use printed parts as the arm structural load path",
        "Do not force locator pins or ream production parts to hide a fit error",
        "Do not tighten screws before every shared stack is fully seated",
        "Do not power motion with a device or tool installed during the empty-cell test",
        "Do not accept bottomed screws, underside projection, rocking, or clamp distortion",
        "Do not treat the rendered arm cylinder or camera view as measured clearance",
        "Do not release from CAD checks alone",
    ]:
        yy = draw_checkbox_line(c, item, right_x + 16, yy, col_w - 32, size=8.5,
                                color=RED if item.startswith("Do not") else INK)


def draw_bom_column(
    c: canvas.Canvas,
    groups: dict[str, list[dict[str, str]]],
    categories: Sequence[str],
    x: float,
    y: float,
    width: float,
) -> None:
    for category in categories:
        rows = groups.get(category, [])
        if not rows:
            continue
        c.setFillColor(BLUE_LIGHT)
        c.roundRect(x, y - 13, width, 17, 4, stroke=0, fill=1)
        c.setFillColor(BLUE_DARK)
        c.setFont("Helvetica-Bold", 8.3)
        c.drawString(x + 7, y - 8, category.upper())
        y -= 22
        for row in rows:
            requirement = row.get("required", "")
            item = f"[ ] {row.get('qty', '')} x {row.get('item', '')}"
            installed_spare = INSTALLED_SPARE_LABELS.get(
                (category, row.get("item", "")), ""
            )
            if installed_spare:
                item += f" ({installed_spare})"
            if requirement and requirement.lower() not in {"yes", "required"}:
                item += f" - {requirement}"
            lines = clipped_lines(item, "Helvetica", 7.7, width - 9, 2)
            c.setFillColor(INK)
            c.setFont("Helvetica", 7.7)
            for line in lines:
                c.drawString(x + 5, y, line)
                y -= 9.4
            y -= 2.0
        y -= 5.0


def draw_inventory_page(
    c: canvas.Canvas,
    revision: str,
    groups: dict[str, list[dict[str, str]]],
    title: str,
    left_categories: Sequence[str],
    right_categories: Sequence[str],
    page_note: str,
) -> None:
    y = draw_title_bar(c, "Parts and tools", title, revision)
    c.setFillColor(ORANGE_LIGHT)
    c.roundRect(MARGIN, y - 39, PAGE_W - 2 * MARGIN, 29, 6, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica", 8.4)
    c.drawString(MARGIN + 12, y - 29, page_note)
    col_gap = 22
    col_w = (PAGE_W - 2 * MARGIN - col_gap) / 2.0
    top = y - 62
    draw_bom_column(c, groups, left_categories, MARGIN, top, col_w)
    draw_bom_column(c, groups, right_categories, MARGIN + col_w + col_gap, top, col_w)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.2)
    c.drawRightString(PAGE_W - MARGIN, 31,
                      "Specifications and procurement notes remain authoritative in BOM.csv")


def draw_flow_card(
    c: canvas.Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
    phase: str,
    title: str,
    lines: Sequence[str],
) -> None:
    draw_card(c, x, y, width, height, fill=WHITE)
    c.setFillColor(BLUE)
    c.roundRect(x + 14, y + height - 45, 34, 30, 5, stroke=0, fill=1)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(x + 31, y + height - 35, phase)
    c.setFillColor(BLUE_DARK)
    title_lines = clipped_lines(
        safe_text(title).upper(), "Helvetica-Bold", 8.8, width - 74, 2
    )
    c.setFont("Helvetica-Bold", 8.8)
    title_y = y + height - 32
    for title_line in title_lines:
        c.drawString(x + 58, title_y, title_line)
        title_y -= 10.0
    yy = y + height - 66
    for line in lines:
        yy = draw_checkbox_line(c, safe_text(line), x + 16, yy, width - 32, size=8.0)


def draw_print_qualification_flow(c: canvas.Canvas, revision: str) -> None:
    y = draw_title_bar(c, "Before assembly", "Print and qualify in this order", revision)
    c.setFillColor(ORANGE_LIGHT)
    c.roundRect(MARGIN, y - 38, PAGE_W - 2 * MARGIN, 29, 6, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8.3)
    c.drawString(MARGIN + 12, y - 28,
                 "PRINT ONLY A SELECTED JOB MARKED READY. Keep every accepted coupon with its job, profile, spool lot, and date.")

    gap = 18.0
    width = (PAGE_W - 2 * MARGIN - 2 * gap) / 3.0
    card_y = 112.0
    card_h = 338.0
    draw_flow_card(c, MARGIN, card_y, width, card_h, "A", "Qualify process",
                   [
                       "Confirm the installed 0.4 mm nozzle.",
                       "Calibrate each exact dry PETG, TPU, and selected ASA profile.",
                       "Print required diagnostics 00A, 00B, 00C, 00E, and 00F at 100 percent with their assigned profiles; add 00D only for a selected phone-stylus route.",
                       "Cool completely before measuring; record evidence with the supplied script.",
                       "Retain the accepted coupons as controlled setup tools.",
                   ])
    draw_flow_card(c, MARGIN + width + gap, card_y, width, card_h, "B", "Release core prints",
                   [
                       "Print and accept job 01 keyboard master first.",
                       "Use the actual master posts with the retained seam ladder; release job 02 only after the seam gate passes.",
                       "Then qualify 03A station, 03B sliders, 03C1 rail, 03C2 setup tool, and two 03D cartridges; keep 03C3 blocked pending camera-architecture alignment.",
                       "Print 05A TPU first article before the 05B phone-tip batch.",
                       "Do not drill the final board until all three stations are accepted.",
                   ])
    draw_flow_card(c, MARGIN + 2 * (width + gap), card_y, width, card_h, "C", "Select routes",
                   [
                       "Shared compliant body: job 04A after at least one tool route is selected.",
                       "Phone route: 04B measured stylus collars.",
                       "Keyboard route: 04C rod bushings, then 05C first article and 05D batch.",
                       "Fixed-mast fallback: keep jobs 06/07A/07B blocked until the arm-camera decision is ALIGNED_AND_REVISED and that same controlled decision explicitly authorizes the fallback; then qualify it physically.",
                       "Never globally scale or auto-orient a released production plate.",
                   ])

    c.setFillColor(RED_LIGHT)
    c.roundRect(MARGIN, 61, PAGE_W - 2 * MARGIN, 35, 6, stroke=0, fill=1)
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGIN + 12, 75,
                 "STOP: mesh PASS, successful slicing, or visual fit is not a physical coupon or first-article PASS.")


def draw_board_fabrication_flow(c: canvas.Canvas, revision: str) -> None:
    y = draw_title_bar(c, "Before illustrated step 01", "Board fabrication - detailed order", revision)
    c.setFillColor(ORANGE_LIGHT)
    c.roundRect(MARGIN, y - 38, PAGE_W - 2 * MARGIN, 29, 6, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8.3)
    c.drawString(MARGIN + 12, y - 28,
                 "No router. No CNC. Remove the paper before final drilling; use positive depth stops and the accepted hardware route.")

    cards = [
        ("1", "Finish and qualify", [
            "610 x 457 x 18 mm board; mark front-left origin, +X right, +Y rear.",
            "Seal both faces and all edges equally; cure fully.",
            "PASS: local gap <=0.50 mm/300 mm; overall bow <=1.50 mm.",
        ]),
        ("2", "Register and transfer", [
            "Print the template at Actual Size / 100 percent.",
            "Both 100 mm bars must measure 100.0 +/-0.2 mm.",
            "Transfer 4 locator and 9 anchor centers; tag outlines are not holes.",
        ]),
        ("3", "Drill controlled bores", [
            "Drill four 6 mm locator bores 15 mm blind with a positive stop.",
            "Prepare nine anchor bores with the exact method proven in an 18 mm cutoff.",
            "The 4.60 mm drawing symbol is not a universal final anchor bore.",
        ]),
        ("4", "Install and prove anchors", [
            "Require >=5 mm thread engagement with no bottoming or underside projection.",
            "Cycle three times at 0.25-0.35 N m.",
            "Proof every anchor at 50 N axial load for 60 seconds.",
        ]),
        ("5", "Dry-fit full stack", [
            "Insert four pins dry at 5.0 mm projection; use no station shims.",
            "Seat all three stations plus sliders and phone rail.",
            "Start all nine washer/screw stacks; complete three remove/reinstall cycles.",
        ]),
        ("6", "Bond only the pins", [
            "Remove every printed station after the dry fit passes.",
            "Apply sparse slow-cure epoxy only to the four board pins.",
            "Hold 5.0 mm projection; keep adhesive out of printed sockets; cure fully.",
        ]),
        ("7", "Recheck registration", [
            "Each master station must drop on and lift off by hand.",
            "STOP for binding, rocking, whitening, forced pins, or screw bottoming.",
            "Record the cured pin projection and station seating evidence.",
        ]),
        ("8", "Protect the underside", [
            "Confirm anchors and reinforcement will clear all feet.",
            "Install anti-shift feet only after underside clearance is proven.",
            "Continue to illustrated Step 02 for the measured metal plate and factory arm clamp.",
        ]),
    ]
    gap_x = 14.0
    gap_y = 16.0
    width = (PAGE_W - 2 * MARGIN - 3 * gap_x) / 4.0
    height = 173.0
    top_y = 286.0
    for index, (number, title, lines) in enumerate(cards):
        row = index // 4
        col = index % 4
        x = MARGIN + col * (width + gap_x)
        card_y = top_y - row * (height + gap_y)
        draw_flow_card(c, x, card_y, width, height, number, title, lines)

    c.setFillColor(RED_LIGHT)
    c.roundRect(MARGIN, 54, PAGE_W - 2 * MARGIN, 31, 6, stroke=0, fill=1)
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 8.6)
    c.drawString(MARGIN + 12, 66,
                 "STOP: do not proceed to production assembly until the complete dry fit, anchor proof, epoxy cure, and post-cure drop-on checks pass.")


def draw_orientation_legend(c: canvas.Canvas, revision: str, layout: dict) -> None:
    y = draw_title_bar(c, "Orientation", "Read this page before placing any station", revision)

    legend_x = MARGIN
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(legend_x, y - 5, "ILLUSTRATION COLOR KEY")
    legend = [
        (BLUE, "Blue", "Install, place, or act on this item now"),
        (GRAY, "Gray", "Already installed or contextual geometry"),
        (ORANGE, "Orange", "Hardware, adhesive, cable, or motion"),
        (TEAL, "Teal", "Compliant or soft-contact component"),
        (RED, "Red", "Stop, no-go, collision, or release warning"),
    ]
    yy = y - 36
    for swatch, name, meaning in legend:
        c.setFillColor(swatch)
        c.roundRect(legend_x, yy - 11, 24, 16, 3, stroke=0, fill=1)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(legend_x + 34, yy, name)
        draw_wrapped(c, meaning, legend_x + 76, yy, 235,
                     font="Helvetica", size=8.2, color=MUTED, max_lines=2)
        yy -= 34

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(legend_x, yy - 3, "INTERFACE RULES")
    yy -= 28
    for rule in [
        "Pins locate. Screws clamp.",
        "Keyboard left is the master. Keyboard right is located by the seam.",
        "Seat shared rails and sliders before installing their screws.",
        "Direct tags are adhesive features - never drilled features.",
        "The setup template transfers centers and direction only.",
    ]:
        yy = draw_checkbox_line(c, rule, legend_x, yy, 315, size=8.2)

    board = layout["board"]
    bx, by, bw = 388, 116, 365
    bh = bw * float(board["depth"]) / float(board["width"])
    c.setFillColor(HexColor("#e6dfd4"))
    c.setStrokeColor(HexColor("#9d9488"))
    c.setLineWidth(2)
    c.roundRect(bx, by, bw, bh, 4, stroke=1, fill=1)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(bx + bw / 2, by - 20, "FRONT EDGE - OPERATOR SIDE")
    c.setFont("Helvetica", 8)
    c.drawCentredString(bx + bw / 2, by + bh + 12, "REAR - TOWARD ARM")

    origin_x, origin_y = bx + 24, by + 24
    c.setStrokeColor(BLUE)
    c.setFillColor(BLUE)
    c.setLineWidth(3)
    c.line(origin_x, origin_y, origin_x + 104, origin_y)
    c.line(origin_x, origin_y, origin_x, origin_y + 92)
    c.line(origin_x + 104, origin_y, origin_x + 94, origin_y + 5)
    c.line(origin_x + 104, origin_y, origin_x + 94, origin_y - 5)
    c.line(origin_x, origin_y + 92, origin_x - 5, origin_y + 82)
    c.line(origin_x, origin_y + 92, origin_x + 5, origin_y + 82)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(origin_x + 110, origin_y - 3, "+X RIGHT")
    c.drawString(origin_x + 9, origin_y + 88, "+Y REAR")
    c.setFillColor(INK)
    c.setFont("Helvetica", 8)
    c.drawString(origin_x + 9, origin_y + 70, "+Z is up from the board top")
    c.setFont("Helvetica-Bold", 9)
    c.drawString(origin_x - 5, origin_y - 16, "ORIGIN")

    c.setFillColor(WHITE)
    c.setStrokeColor(LINE)
    c.roundRect(bx + 175, by + 45, 160, 86, 7, stroke=1, fill=1)
    c.setFillColor(BLUE_DARK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(bx + 190, by + 108, "DATUM LANGUAGE")
    c.setFillColor(INK)
    c.setFont("Helvetica", 8)
    c.drawString(bx + 190, by + 87, "X/Y = board top plane coordinates")
    c.drawString(bx + 190, by + 69, "Z = height above board top")
    c.drawString(bx + 190, by + 51, "Yaw = rotation viewed from +Z")


def table_row_height(cells: Sequence[str], widths: Sequence[float],
                     font: str, size: float, leading: float,
                     padding: float = 5.0, max_lines: int = 4) -> float:
    count = 1
    for text, width in zip(cells, widths):
        count = max(count, min(max_lines, len(wrap_lines(text, font, size, width - 2 * padding))))
    return count * leading + 2 * padding


def draw_table(
    c: canvas.Canvas,
    x: float,
    top_y: float,
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    widths: Sequence[float],
    *,
    font_size: float = 7.0,
    leading: float = 8.4,
    row_max_lines: int = 4,
) -> float:
    header_h = 27.0
    c.setFillColor(NAVY)
    c.rect(x, top_y - header_h, sum(widths), header_h, stroke=0, fill=1)
    xx = x
    for header, width in zip(headers, widths):
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", font_size)
        for index, line in enumerate(clipped_lines(header, "Helvetica-Bold", font_size,
                                                   width - 8, 2)):
            c.drawString(xx + 4, top_y - 10 - index * leading, line)
        c.setStrokeColor(HexColor("#425665"))
        c.line(xx + width, top_y - header_h, xx + width, top_y)
        xx += width
    current_y = top_y - header_h
    for row_index, row in enumerate(rows):
        height = table_row_height(row, widths, "Helvetica", font_size, leading,
                                  max_lines=row_max_lines)
        c.setFillColor(WHITE if row_index % 2 == 0 else GRAY_LIGHT)
        c.rect(x, current_y - height, sum(widths), height, stroke=0, fill=1)
        xx = x
        for value, width in zip(row, widths):
            c.setFillColor(INK)
            c.setFont("Helvetica", font_size)
            lines = clipped_lines(value, "Helvetica", font_size, width - 8, row_max_lines)
            baseline = current_y - 7 - font_size
            for line in lines:
                c.drawString(xx + 4, baseline, line)
                baseline -= leading
            c.setStrokeColor(LINE)
            c.setLineWidth(0.45)
            c.line(xx + width, current_y - height, xx + width, current_y)
            xx += width
        c.setStrokeColor(LINE)
        c.line(x, current_y - height, x + sum(widths), current_y - height)
        current_y -= height
    c.setStrokeColor(LINE)
    c.rect(x, current_y, sum(widths), top_y - current_y, stroke=1, fill=0)
    return current_y


def draw_fastener_map(c: canvas.Canvas, revision: str,
                      fasteners: Sequence[dict[str, str]]) -> None:
    y = draw_title_bar(c, "Hardware bags", "Authoritative nine-row M4 map", revision)
    c.setFillColor(ORANGE_LIGHT)
    c.roundRect(MARGIN, y - 47, PAGE_W - 2 * MARGIN, 37, 6, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8.4)
    c.drawString(MARGIN + 12, y - 26,
                 "Do not select screw length from the render. Select it on the actual stack and 18 mm cutoff test.")
    c.setFont("Helvetica", 7.8)
    c.drawString(MARGIN + 12, y - 39,
                 "Every row requires >=5 mm engagement, no bottoming, no underside projection, one washer, and 0.25-0.35 N m final torque.")

    headers = ["ID", "Station", "Role", "Stack", "Hardware class", "Candidate", "Selected", "Acceptance / sequence"]
    widths = [66, 62, 134, 38, 96, 68, 55, 155]
    rows: list[list[str]] = []
    for row in fasteners:
        selected = row.get("selected_length_mm", "").strip()
        rows.append([
            row.get("feature_id", ""),
            row.get("station", "").replace("_", " "),
            row.get("fastener_role", ""),
            f"{row.get('printed_stack_mm', '')} mm",
            row.get("hardware_class", ""),
            row.get("candidate_length", ""),
            f"{selected} mm [ ]" if selected else "____ mm [ ]",
            row.get("acceptance", ""),
        ])
    bottom = draw_table(c, 59, y - 61, headers, rows, widths,
                        font_size=6.2, leading=7.2, row_max_lines=5)
    note_y = max(47, bottom - 18)
    c.setFillColor(BLUE_LIGHT)
    c.roundRect(59, note_y - 32, sum(widths), 30, 5, stroke=0, fill=1)
    c.setFillColor(BLUE_DARK)
    c.setFont("Helvetica-Bold", 7.8)
    c.drawString(69, note_y - 14,
                 "[ ] 9 / 9 anchors installed   [ ] Shared sliders and rails seated first   [ ] Final torque witnessed")
    c.setFont("Helvetica", 7.2)
    c.drawRightString(59 + sum(widths) - 10, note_y - 26,
                      "Bag labels must use the feature IDs shown above")


def draw_build_panel(c: canvas.Canvas, panel_no: int, path: Path, title: str) -> None:
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 47, PAGE_W, 47, stroke=0, fill=1)
    c.setFillColor(ORANGE)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(MARGIN, PAGE_H - 18, "BUILD SEQUENCE")
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(MARGIN, PAGE_H - 37, f"{panel_no:02d} / 15  {safe_text(title).upper()}")

    frame_x, frame_y, frame_w, frame_h = MARGIN, 61, PAGE_W - 2 * MARGIN, 486
    c.setFillColor(WHITE)
    c.setStrokeColor(LINE)
    c.roundRect(frame_x, frame_y, frame_w, frame_h, 8, stroke=1, fill=1)
    draw_fitted_image(c, path, frame_x + 8, frame_y + 8, frame_w - 16, frame_h - 16)

    c.setFillColor(WHITE)
    c.setStrokeColor(LINE)
    c.roundRect(MARGIN, 31, PAGE_W - 2 * MARGIN, 22, 5, stroke=1, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica", 7.5)
    c.drawString(MARGIN + 10, 39, "[ ] STEP ACCEPTED")
    c.drawString(MARGIN + 128, 39, "Measurement / photo ID: ______________________________")
    c.drawRightString(PAGE_W - MARGIN - 10, 39,
                      "If a gate fails: stop, correct, and repeat this step")


ACCEPTANCE_A = [
    ("A01", "Board local flatness", "<=0.50 mm over any 300 mm span", "Worst: ______ mm"),
    ("A02", "Board overall bow", "<=1.50 mm over full board", "Measured: ______ mm"),
    ("A03", "Station free-state corner lift", "<=0.75 mm before clamping", "Worst: ______ mm"),
    ("A04", "Keyboard support plane", "<=0.40 mm variation", "Range: ______ mm"),
    ("A05", "Phone support plane", "<=0.30 mm variation", "Range: ______ mm"),
    ("A06", "TCP cartridge seat", "<=0.15 mm seat error", "Measured: ______ mm"),
    ("A07", "Keyboard seam gap", "<=0.40 mm", "Measured: ______ mm"),
    ("A08", "Keyboard seam flush", "<=0.25 mm", "Measured: ______ mm"),
    ("A09", "Locator bores", "15 mm blind depth; no breakout", "Depths: __________"),
    ("A10", "Locator projection", "5.0 mm above board top", "Pins: __________ mm"),
    ("A11", "Station retainers", "0.25-0.35 N m; >=5 mm engagement", "Torque: ______ N m"),
    ("A12", "Screw termination", "No bottoming or underside projection", "[ ] All 9 pass"),
]

ACCEPTANCE_B = [
    ("B01", "Station reinstall repeatability", "10 cycles: X/Y <=0.25 mm; yaw <=0.20 deg; Z <=0.20 mm", "Worst: __________"),
    ("B02", "Keyboard device pose", "<=0.50 mm from recorded reference", "Error: ______ mm"),
    ("B03", "Phone device pose", "<=0.35 mm from recorded reference", "Error: ______ mm"),
    ("B04", "Cartridge free play", "<=0.15 mm", "Measured: ______ mm"),
    ("B05", "Cartridge height range", "<=0.10 mm across removals", "Range: ______ mm"),
    ("B06", "Printed AprilTag tile", "55.0 +/-0.2 mm; marker edge 40.0 +/-0.2 mm", "Worst: __________"),
    ("B07", "Tag placement", "Center <=0.50 mm; yaw <=0.30 deg; edge lift <=0.20 mm", "Worst: __________"),
    ("B08", "Vision detection", "20 / 20 detections per tag", "T0-T3/K0/P0: ______"),
    ("B09", "Vision reprojection", "<=1.0 px", "Worst: ______ px"),
    ("B10", "Station proof loads", "20 N lateral; 10 N functional; permanent shift <=0.10 mm", "Shift: ______ mm"),
    ("B11", "Board anchor proof", "50 N axial for 60 s; no damage or shift", "Worst: __________"),
    ("B12", "Compliant tool travel", "3-6 mm smooth travel; returns freely", "Travel: ______ mm"),
    ("B13", "Empty-cell motion", "No collision; measured clearance recorded", "Min: ______ mm"),
]


def draw_acceptance_page(c: canvas.Canvas, revision: str, title: str,
                         subtitle: str, gates: Sequence[tuple[str, str, str, str]]) -> None:
    y = draw_title_bar(c, "Acceptance", title, revision)
    c.setFillColor(RED_LIGHT)
    c.roundRect(MARGIN, y - 40, PAGE_W - 2 * MARGIN, 30, 5, stroke=0, fill=1)
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(MARGIN + 11, y - 29, subtitle)
    rows = [[gate, criterion, limit, f"{blank}   PASS [ ]  FAIL [ ]"]
            for gate, criterion, limit, blank in gates]
    widths = [40, 178, 270, 244]
    bottom = draw_table(c, MARGIN, y - 55,
                        ["Gate", "Check", "Acceptance limit", "Measured result"],
                        rows, widths, font_size=7.2, leading=8.7, row_max_lines=3)
    c.setFillColor(BLUE_LIGHT)
    c.roundRect(MARGIN, max(31, bottom - 37), PAGE_W - 2 * MARGIN, 30, 5,
                stroke=0, fill=1)
    c.setFillColor(BLUE_DARK)
    c.setFont("Helvetica-Bold", 7.8)
    c.drawString(MARGIN + 10, max(42, bottom - 25),
                 "Evidence folder / report: ______________________________   Witness: __________________   Date: __________")


def draw_commissioning(c: canvas.Canvas, revision: str) -> None:
    y = draw_title_bar(c, "Commissioning", "Final controlled startup and signoff", revision)
    col_gap = 18
    col_w = (PAGE_W - 2 * MARGIN - col_gap) / 2.0
    left_x = MARGIN
    right_x = MARGIN + col_w + col_gap
    card_y, card_h = 235, 277
    draw_card(c, left_x, card_y, col_w, card_h)
    draw_card(c, right_x, card_y, col_w, card_h)

    c.setFillColor(BLUE_DARK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_x + 15, card_y + card_h - 25, "FIRST POWERED RUN")
    yy = card_y + card_h - 48
    for item in [
        "E-stop function test passes before robot enable",
        "All devices and removable tools are out of the cell",
        "Speed and force limits are set to commissioning values",
        "Empty-cell path runs without collision",
        "Minimum measured clearance is recorded",
        "Camera sees T0-T3, K0, and P0 across required motion",
        "One device at a time is loaded and verified",
        "Cable slack loop clears the screen, rail, and robot envelope",
        "Final process path passes at controlled speed",
    ]:
        yy = draw_checkbox_line(c, item, left_x + 15, yy, col_w - 30, size=8.2)

    c.setFillColor(BLUE_DARK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(right_x + 15, card_y + card_h - 25, "RELEASE RECORD")
    fields = [
        "Builder: ______________________________",
        "Witness: ______________________________",
        "Build date: __________   Location: __________",
        "QIDI Plus4 serial: ________________________",
        "Filament / lot: ___________________________",
        "Caliper ID: __________  Torque tool ID: ______",
        "Force gauge ID: __________________________",
        "Evidence folder: _________________________",
        "Deviation record: ________________________",
        "Final measured clearance: ______ mm",
    ]
    yy = card_y + card_h - 49
    c.setFillColor(INK)
    c.setFont("Helvetica", 8.4)
    for field in fields:
        c.drawString(right_x + 15, yy, field)
        yy -= 20

    c.setFillColor(RED_LIGHT)
    c.roundRect(MARGIN, 106, PAGE_W - 2 * MARGIN, 104, 8, stroke=0, fill=1)
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(MARGIN + 16, 182, "PHYSICAL RELEASE DECISION")
    c.setFillColor(INK)
    c.setFont("Helvetica", 8.8)
    c.drawString(MARGIN + 16, 162,
                 "I confirm that every acceptance gate was physically measured, passed, and linked to retained evidence.")
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(MARGIN + 16, 137, "RELEASED [ ]    NOT RELEASED [ ]    CONDITIONAL - DEVIATION ATTACHED [ ]")
    c.setFont("Helvetica", 8.8)
    c.drawString(MARGIN + 16, 117,
                 "Responsible signature: ______________________________   Date: __________   Revision: " + revision)

    c.setFillColor(NAVY)
    c.roundRect(MARGIN, 48, PAGE_W - 2 * MARGIN, 43, 7, stroke=0, fill=1)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGIN + 15, 72,
                 "Digital validation is not physical release. An unsigned guide remains UNRELEASED.")
    c.setFont("Helvetica", 8)
    c.drawString(MARGIN + 15, 57,
                 "Archive this signed record with photos, measurement sheets, force data, camera evidence, and deviations.")


def validate_inputs(bom: Sequence[dict[str, str]],
                    fasteners: Sequence[dict[str, str]]) -> None:
    missing_files = [name for name, _ in EXPECTED_PANELS if not (IMAGE_DIR / name).is_file()]
    if missing_files:
        raise FileNotFoundError("Missing assembly panels: " + ", ".join(missing_files))
    actual_pngs = sorted(path.name for path in IMAGE_DIR.glob("*.png"))
    expected_pngs = sorted(name for name, _ in EXPECTED_PANELS)
    if actual_pngs != expected_pngs:
        extras = sorted(set(actual_pngs) - set(expected_pngs))
        raise RuntimeError(
            "Assembly panel directory must contain exactly the 15 released panels. "
            f"Unexpected PNGs: {extras}"
        )
    if not bom:
        raise RuntimeError("BOM.csv contains no rows")
    actual_fasteners = [row.get("feature_id", "") for row in fasteners]
    if actual_fasteners != EXPECTED_FASTENERS:
        raise RuntimeError(
            "FASTENER_MAP.csv must contain the authoritative nine rows in release order. "
            f"Found: {actual_fasteners}"
        )


PageDrawer = Callable[[canvas.Canvas], None]


def build_pdf() -> Path:
    layout = json.loads(LAYOUT_JSON.read_text(encoding="utf-8"))
    revision = safe_text(layout.get("release_revision", "RC03-INT-R1"))
    bom = read_csv(BOM_CSV)
    fasteners = read_csv(FASTENER_CSV)
    validate_inputs(bom, fasteners)
    groups = split_bom(bom)

    pages: list[PageDrawer] = []
    pages.append(lambda c: draw_cover(c, revision))
    pages.append(lambda c: draw_release_and_safety(c, revision))
    pages.append(lambda c: draw_inventory_page(
        c, revision, groups, "Core parts and load-path hardware",
        ["Core", "Board interface", "Arm interface", "Assembly"],
        ["Phone clamp", "TCP receiver", "Compliant tool", "Keyboard tool",
         "Phone tool", "Tool retention", "Safety"],
        "Stage items into labeled bags. A checkmark means the exact quantity and specification were verified.",
    ))
    pages.append(lambda c: draw_inventory_page(
        c, revision, groups, "Fabrication, vision, cable, and optional support",
        ["Fabrication", "Vision", "Cable management"],
        ["Camera stand", "Board", "Service spares"],
        "Recommended and optional lines remain labeled as such. Do not substitute required measurement or safety tools.",
    ))
    pages.append(lambda c: draw_orientation_legend(c, revision, layout))
    pages.append(lambda c: draw_print_qualification_flow(c, revision))
    pages.append(lambda c: draw_board_fabrication_flow(c, revision))
    pages.append(lambda c: draw_fastener_map(c, revision, fasteners))
    for index, (filename, title) in enumerate(EXPECTED_PANELS, start=1):
        pages.append(lambda c, i=index, p=IMAGE_DIR / filename, t=title:
                     draw_build_panel(c, i, p, t))
    pages.append(lambda c: draw_acceptance_page(
        c, revision, "Dimensional and seating gates",
        "Record actual values. A checkmark without a measured result is not acceptable evidence.",
        ACCEPTANCE_A,
    ))
    pages.append(lambda c: draw_acceptance_page(
        c, revision, "Repeatability, vision, structure, and motion gates",
        "Stop at the first failure. Correct the cause, repeat the affected build step, then repeat this gate.",
        ACCEPTANCE_B,
    ))
    pages.append(lambda c: draw_commissioning(c, revision))

    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUTPUT_PDF), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    pdf.setTitle(f"RoCell {revision} Illustrated Assembly Guide")
    pdf.setAuthor("RoCell build package")
    pdf.setSubject("Printable step-by-step assembly, acceptance, and commissioning guide")
    pdf.setCreator("scripts/build_illustrated_assembly_guide.py")

    total = len(pages)
    for page_no, drawer in enumerate(pages, start=1):
        pdf.setFillColor(PAPER)
        pdf.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
        drawer(pdf)
        draw_footer(pdf, revision, page_no, total)
        pdf.showPage()
    pdf.save()
    return OUTPUT_PDF


def main() -> None:
    output = build_pdf()
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
