from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DetectAprilTagsCliTests(unittest.TestCase):
    def test_help_exposes_repeatable_required_tag_gate_without_loading_opencv(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "software_helpers" / "detect_apriltags.py"), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--require-tag {K0,P0,T0,T1,T2,T3}", completed.stdout)
        self.assertIn("--output OUTPUT", completed.stdout)
        self.assertIn("--annotated ANNOTATED", completed.stdout)
        self.assertNotIn("--tag-size-m", completed.stdout)
        self.assertNotIn("binary-incompatible", completed.stderr)


if __name__ == "__main__":
    unittest.main()
