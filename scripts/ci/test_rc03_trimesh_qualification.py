import tempfile
import unittest
from pathlib import Path

import rc03_trimesh_qualification as qualification


class Rc03TrimeshQualificationTests(unittest.TestCase):
    def test_selects_only_mesh_runtime_requirements_in_stable_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "requirements.txt"
            source.write_text(
                "cadquery>=2.5\nnumpy>=2.0\ntrimesh>=5.1 # mesh reader\nPillow>=10\n",
                encoding="utf-8",
            )
            self.assertEqual(
                qualification.select_requirements(source),
                ["trimesh>=5.1", "numpy>=2.0"],
            )

    def test_missing_or_duplicate_requirement_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "requirements.txt"
            source.write_text("numpy>=2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Missing"):
                qualification.select_requirements(source)

            source.write_text("numpy>=2\ntrimesh>=4\nTrimesh>=5\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                qualification.select_requirements(source)


if __name__ == "__main__":
    unittest.main()
