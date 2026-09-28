import tempfile
import unittest
from pathlib import Path

import rc03_reportlab_qualification as qualification


class Rc03ReportLabQualificationTests(unittest.TestCase):
    def test_selects_only_reportlab_and_preserves_constraint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "requirements.txt"
            source.write_text(
                "numpy>=2\nReportLab>=5.0.1 # controlled PDF renderer\nPillow>=10\n",
                encoding="utf-8",
            )
            self.assertEqual(
                qualification.select_reportlab_requirement(source),
                "ReportLab>=5.0.1",
            )

    def test_missing_or_duplicate_reportlab_requirement_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "requirements.txt"
            source.write_text("numpy>=2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Expected one"):
                qualification.select_reportlab_requirement(source)

            source.write_text("reportlab>=4\nReportLab>=5\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "found 2"):
                qualification.select_reportlab_requirement(source)


if __name__ == "__main__":
    unittest.main()
