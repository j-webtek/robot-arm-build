import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import rc03_manual_qualification as qualification


class Rc03ManualQualificationTests(unittest.TestCase):
    def test_selects_only_manual_runtime_requirements_in_stable_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "requirements.txt"
            source.write_text(
                "numpy>=2\nweasyprint>=70\nbeautifulsoup4>=4.12\n"
                "mistune>=3 # renderer\ncadquery>=2.5\n",
                encoding="utf-8",
            )
            self.assertEqual(
                qualification.select_requirements(source),
                ["mistune>=3", "beautifulsoup4>=4.12", "weasyprint>=70"],
            )

    def test_missing_or_duplicate_requirement_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "requirements.txt"
            source.write_text(
                "mistune>=3\nbeautifulsoup4>=4.12\nBeautifulSoup4>=4.13\nweasyprint>=70\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                qualification.select_requirements(source)

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "pypdf is optional outside the focused job")
    def test_structural_pdf_validation_records_identity_and_scope(self) -> None:
        from pypdf import PdfWriter

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "manual.md"
            source.write_text("# Test manual\n", encoding="utf-8")
            pdf = root / "manual.pdf"
            writer = PdfWriter()
            for _ in range(qualification.MINIMUM_PAGE_COUNT):
                writer.add_blank_page(width=612, height=792)
            with pdf.open("wb") as stream:
                writer.write(stream)

            with mock.patch.object(qualification, "MINIMUM_PDF_BYTES", 100):
                summary = qualification.validate_pdf(pdf, source)
            self.assertEqual(summary["page_count"], qualification.MINIMUM_PAGE_COUNT)
            self.assertEqual(summary["scope"], "render_and_structural_validation_only")
            self.assertEqual(len(summary["pdf_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
