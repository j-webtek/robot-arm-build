from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_steps() -> dict[str, dict]:
    document = json.loads(
        (ROOT / "config" / "assembly_steps.json").read_text(encoding="utf-8")
    )
    return {step["id"]: step for step in document["steps"]}


class InstructionAccuracyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.steps = load_steps()

    def test_step04_acceptance_covers_fastener_stack_and_rocking(self) -> None:
        acceptance = {row["test_id"]: row for row in self.steps["04"]["acceptance"]}
        self.assertIn("04-D", acceptance)
        self.assertIn("04-E", acceptance)
        stack = " ".join(str(value) for value in acceptance["04-D"].values())
        for phrase in ("5 mm", "0.25-0.35 N m", "bottoming", "underside projection"):
            self.assertIn(phrase, stack)
        self.assertIn("No measurable rocking", acceptance["04-E"]["limit"])

    def test_step11_distinguishes_letter_tiles_and_full_size_route(self) -> None:
        step = self.steps["11"]
        procedure = " ".join(step["procedure"])
        for phrase in ("pages 1-3", "pages 4-12", "12 mm", "never butt", "24 x 36"):
            self.assertIn(phrase, procedure)
        paths = {row["path"] for row in step["extra_files"]}
        self.assertIn("output/pdf/RC03_BOARD_DRILL_GUIDE_LETTER_1TO1.pdf", paths)
        self.assertIn("output/pdf/RC03_BOARD_DRILL_GUIDE_24X36_FULL_SIZE_1TO1.pdf", paths)

    def test_step12_generates_and_hands_off_measured_runtime_map(self) -> None:
        step = self.steps["12"]
        procedure = " ".join(step["procedure"])
        self.assertIn("python scripts/generate_fiducials.py --map-only", procedure)
        self.assertIn("coordinate_source", procedure)
        self.assertIn("measured_installation", procedure)
        self.assertTrue(any(row["test_id"] == "12-D" for row in step["acceptance"]))
        self.assertTrue(any("SHA-256" in item for item in step["handoff"]))

    def test_step13_batch_is_complete_nonoverwriting_and_six_tag_consistent(self) -> None:
        step = self.steps["13"]
        detector_action = next(
            action for action in step["procedure"] if "$frames.Count -lt 20" in action
        )
        for phrase in (
            "$frames.Count -lt 20",
            "existing evidence is never overwritten",
            "--image",
            "--calibration",
            "--tag-map",
            "--output",
            "--annotated",
            "--min-world-tags 4",
            "--require-board-pose",
            "$LASTEXITCODE",
            "$failed.Count -gt 0",
        ):
            self.assertIn(phrase, detector_action)
        self.assertNotIn("--tag-size-m", detector_action)
        for name in ("T0", "T1", "T2", "T3", "K0", "P0"):
            self.assertIn(f"--require-tag {name}", detector_action)

        fov_limit = next(
            row["limit"] for row in step["acceptance"] if row["test_id"] == "13-B"
        )
        for name in ("T0", "T1", "T2", "T3", "K0", "P0"):
            self.assertIn(name, fov_limit)
        self.assertIn("board pose is solved from T0-T3", fov_limit)

    def test_manual_detector_example_matches_real_cli_and_current_guide_colors(self) -> None:
        manual = (ROOT / "ASSEMBLY_MANUAL.md").read_text(encoding="utf-8")
        self.assertNotIn("--tag-size-m", manual)
        detector_line = next(
            line
            for line in manual.splitlines()
            if line.lstrip().startswith("python software_helpers/detect_apriltags.py")
        )
        self.assertIn("--output", detector_line)
        self.assertIn("--annotated", detector_line)
        self.assertNotIn("--tag-size-m", detector_line)
        self.assertNotIn("red circular features", manual.lower())
        self.assertIn("Blue double-ring symbols", manual)
        self.assertIn("Orange dashed-square symbols", manual)

    def test_manual_sync_renderer_uses_current_guide_colors(self) -> None:
        scripts = str(ROOT / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        spec = importlib.util.spec_from_file_location(
            "rc03_sync_documentation", ROOT / "scripts" / "sync_documentation.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rendered = module.render_board_features(module.load_layout())
        self.assertNotIn("red circular features", rendered.lower())
        self.assertIn("blue double-ring symbols", rendered.lower())
        self.assertIn("orange dashed-square symbols", rendered.lower())


if __name__ == "__main__":
    unittest.main()
