#!/usr/bin/env python3
"""Regression checks for the controlled board-drilling guide package."""

from __future__ import annotations

import csv
import hashlib
import math
import unittest
from pathlib import Path

import ezdxf
import pdfplumber
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
LETTER = ROOT / "output" / "pdf" / "RC03_BOARD_DRILL_GUIDE_LETTER_1TO1.pdf"
FULL_SIZE = ROOT / "output" / "pdf" / "RC03_BOARD_DRILL_GUIDE_24X36_FULL_SIZE_1TO1.pdf"
LEGACY_ALIAS = ROOT / "drawings" / "board_drill_template_letter_1to1.pdf"
COORDINATES = ROOT / "drawings" / "board_hole_coordinates.csv"
LAYOUT = ROOT / "config" / "workcell_layout.json"
MM_PT = 72.0 / 25.4

FEATURE_IDS = (
    "KBL-LOC-ROUND", "KBL-LOC-RADIAL", "KBL-HOLD-F", "KBL-HOLD-R", "KBL-CLAMP",
    "KBR-HOLD-F", "KBR-HOLD-R", "KBR-CLAMP",
    "PT-LOC-ROUND", "PT-LOC-RADIAL", "PT-HOLD-TCP", "PT-HOLD-R1", "PT-HOLD-R2",
)
TILE_IDS = ("A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3")


class DrillGuideTests(unittest.TestCase):
    def test_letter_guide_page_structure_and_controls(self) -> None:
        reader = PdfReader(str(LETTER))
        self.assertEqual(len(reader.pages), 12)
        for page in reader.pages:
            self.assertAlmostEqual(float(page.mediabox.width), 11.0 * 72.0, places=3)
            self.assertAlmostEqual(float(page.mediabox.height), 8.5 * 72.0, places=3)

        cover = reader.pages[0].extract_text()
        self.assertIn("OVERVIEW ONLY", cover)
        self.assertIn("DO NOT MARK OR DRILL", cover)
        schedule = reader.pages[1].extract_text()
        self.assertIn("Hole Schedule", schedule)
        for feature_id in FEATURE_IDS:
            self.assertIn(feature_id, schedule)
        assembly = reader.pages[2].extract_text()
        assembly_flat = " ".join(assembly.split())
        self.assertIn("overlap by exactly 12.0 mm", assembly_flat)
        self.assertIn("Never butt", assembly_flat)
        self.assertIn("100.0 +/- 0.2 mm", assembly_flat)

        with pdfplumber.open(LETTER) as pdf:
            for page_index, tile_id in enumerate(TILE_IDS, start=3):
                text = reader.pages[page_index].extract_text()
                self.assertIn(f"DRILL TILE {tile_id} - 1:1", text)
                self.assertIn(f"X SCALE - 100.0 mm - TILE {tile_id}", text)
                self.assertIn(f"Y SCALE - 100.0 mm - TILE {tile_id}", text)
                self.assertIn("CENTER-PUNCH ONLY", text)
                self.assertIn("MATCH", text)
                self.assertIn("ACTUAL SIZE / 100% ONLY", text)
                self._assert_physical_scale_bars(pdf.pages[page_index])

    def test_full_size_guide_is_one_36_by_24_inch_page(self) -> None:
        reader = PdfReader(str(FULL_SIZE))
        self.assertEqual(len(reader.pages), 1)
        page = reader.pages[0]
        self.assertAlmostEqual(float(page.mediabox.width), 36.0 * 72.0, places=3)
        self.assertAlmostEqual(float(page.mediabox.height), 24.0 * 72.0, places=3)
        text = page.extract_text()
        self.assertIn("FULL-SIZE Board Drill Guide", text)
        self.assertIn("ANCHOR SQUARES ARE CENTER TARGETS ONLY", text)
        self.assertIn("X SCALE - 100.0 mm", text)
        self.assertIn("Y SCALE - 100.0 mm", text)
        with pdfplumber.open(FULL_SIZE) as pdf:
            self._assert_physical_scale_bars(pdf.pages[0])

    def test_legacy_letter_path_is_an_exact_alias(self) -> None:
        self.assertEqual(LETTER.read_bytes(), LEGACY_ALIAS.read_bytes())

    def test_coordinate_schedule_has_exact_centers_and_safe_actions(self) -> None:
        with COORDINATES.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(tuple(row["id"] for row in rows), FEATURE_IDS)
        self.assertEqual({row["layout_sha256"] for row in rows}, {hashlib.sha256(LAYOUT.read_bytes()).hexdigest()})

        locators = [row for row in rows if row["type"] == "locator_pin_blind"]
        anchors = [row for row in rows if row["type"] == "m4_retention_through"]
        self.assertEqual(len(locators), 4)
        self.assertEqual(len(anchors), 9)
        for row in locators:
            self.assertEqual(row["template_action"], "DRILL_6.0_MM_BLIND_15.0_MM_AFTER_PILOT")
            self.assertAlmostEqual(float(row["diameter"]), 6.0)
            self.assertAlmostEqual(float(row["depth_mm"]), 15.0)
            self.assertIn("preserve at least 2.0 mm floor", row["final_board_bore_control"])
        for row in anchors:
            self.assertEqual(row["template_action"], "CENTER_PUNCH_ONLY_FINAL_BORE_FROM_FASTENER_MAP")
            self.assertEqual(row["final_board_bore_control"], "FASTENER_MAP.csv qualified anchor row")

        for row in rows:
            x, y = float(row["x"]), float(row["y"])
            self.assertAlmostEqual(float(row["left_edge_x_mm"]), x, places=3)
            self.assertAlmostEqual(float(row["front_edge_y_mm"]), y, places=3)
            self.assertAlmostEqual(float(row["right_edge_mm"]), 610.0 - x, places=3)
            self.assertAlmostEqual(float(row["rear_edge_mm"]), 457.0 - y, places=3)
            self.assertGreaterEqual(min(x, y, 610.0 - x, 457.0 - y), 0.0)

    def test_vector_companion_files_cannot_misstate_anchor_bores(self) -> None:
        svg = (ROOT / "drawings" / "board_610x457_drill_layout.svg").read_text(encoding="utf-8")
        self.assertIn("Blue double ring", svg)
        self.assertIn("orange square", svg)
        self.assertIn("CENTER ONLY", svg)
        self.assertNotIn("Red = drill", svg)

        doc = ezdxf.readfile(ROOT / "drawings" / "board_610x457_drill_layout.dxf")
        self.assertIn("LOCATOR_BLIND", doc.layers)
        self.assertIn("ANCHOR_CENTER_ONLY", doc.layers)
        model = doc.modelspace()
        self.assertEqual(len(model.query('CIRCLE[layer=="LOCATOR_BLIND"]')), 8)
        self.assertEqual(len(model.query('LWPOLYLINE[layer=="ANCHOR_CENTER_ONLY"]')), 9)

    def _assert_physical_scale_bars(self, page: pdfplumber.page.Page) -> None:
        target = 100.0 * MM_PT
        horizontal = [
            line for line in page.lines
            if math.isclose(abs(float(line["x1"]) - float(line["x0"])), target, abs_tol=0.02)
            and math.isclose(float(line["y1"]), float(line["y0"]), abs_tol=0.02)
        ]
        vertical = [
            line for line in page.lines
            if math.isclose(abs(float(line["y1"]) - float(line["y0"])), target, abs_tol=0.02)
            and math.isclose(float(line["x1"]), float(line["x0"]), abs_tol=0.02)
        ]
        self.assertTrue(horizontal, "missing exact 100 mm X scale-control vector")
        self.assertTrue(vertical, "missing exact 100 mm Y scale-control vector")


if __name__ == "__main__":
    unittest.main()
