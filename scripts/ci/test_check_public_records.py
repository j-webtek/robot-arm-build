import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import check_public_records as checks


class PublicRecordTests(unittest.TestCase):
    def fixture(self, root: Path) -> None:
        files = {
            "presentations/blender/dimension_manifest.json": b"authority",
            "assets/media/tactevra-overview.mp4": b"video",
            "assets/media/tactevra-overview-poster.jpg": b"poster",
            "assets/media/tactevra-overview.en.vtt": b"captions",
        }
        records = []
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            record = {
                "path": relative,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            if relative.startswith("assets/media/"):
                records.append(record)
            else:
                authority = record
        receipt = {
            "schema": "tactevra.published-media-verification.v1",
            "asset_revision_commit": "d" * 40,
            "source_pull_request": "https://github.com/j-webtek/tactevra/pull/112",
            "authority": authority,
            "outputs": records,
            "limitations": [
                "Tracked at https://github.com/j-webtek/tactevra/issues/88.",
                "This is not physical qualification.",
            ],
        }
        (root / checks.RECEIPT).write_text(json.dumps(receipt), encoding="utf-8")

    def test_valid_receipt(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            self.assertEqual([], checks.media_errors(root))

    def test_byte_drift_is_rejected(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            (root / "assets/media/tactevra-overview.mp4").write_bytes(b"changed")
            self.assertTrue(any("drift" in error for error in checks.media_errors(root)))

    def test_unsafe_path_is_rejected(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            receipt_path = root / checks.RECEIPT
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["outputs"][0]["path"] = "../outside.mp4"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            self.assertTrue(any("unsafe" in error for error in checks.media_errors(root)))

    def test_missing_output_is_rejected(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            receipt_path = root / checks.RECEIPT
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["outputs"].pop()
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            self.assertTrue(any("exactly" in error for error in checks.media_errors(root)))

    def test_status_matches_latest_arm_record(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "software/ai/docs").mkdir(parents=True)
            (root / "software/ai/docs/EVIDENCE_LEDGER.md").write_text(
                "### E-20260927-ARM-067 — old\n### E-20260927-ARM-068 — current\n",
                encoding="utf-8",
            )
            (root / "PROJECT_STATUS.md").write_text(
                "Reviewed September 27, 2026 through the ARM-068 current increment.\n"
                "[Issue #45](https://github.com/j-webtek/tactevra/issues/45) was closed.\n",
                encoding="utf-8",
            )
            self.assertEqual([], checks.status_errors(root))

    def test_stale_status_is_rejected(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "software/ai/docs").mkdir(parents=True)
            (root / "software/ai/docs/EVIDENCE_LEDGER.md").write_text(
                "### E-20260927-ARM-068 — current\n", encoding="utf-8"
            )
            (root / "PROJECT_STATUS.md").write_text(
                "Reviewed September 27, 2026 through the ARM-048 old increment.\n",
                encoding="utf-8",
            )
            errors = checks.status_errors(root)
            self.assertTrue(any("stale" in error for error in errors))
            self.assertTrue(any("issue #45" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
