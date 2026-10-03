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
            "assets/media/tactevra-overview.chapters.vtt": b"chapters",
            "assets/media/tactevra-social-preview.jpg": b"social-preview",
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
                "Governed by docs/decisions/0001-waveshare-model-license-disposition.md.",
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

    def test_noncanonical_source_pull_request_is_rejected(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            receipt_path = root / checks.RECEIPT
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["source_pull_request"] = "https://example.com/pull/118"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            self.assertTrue(any(
                "canonical Tactevra PR URL" in error
                for error in checks.media_errors(root)
            ))

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

    def test_pages_runtime_baseline(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            workflow = root / checks.PAGES_WORKFLOW
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "runs-on: ubuntu-24.04\n"
                "uses: actions/configure-pages@"
                f"{checks.CONFIGURE_PAGES_V6_SHA} # v6.0.0\n"
                "uses: actions/deploy-pages@"
                f"{checks.DEPLOY_PAGES_V5_SHA} # v5.0.1\n"
                "runs-on: ubuntu-24.04\n",
                encoding="utf-8",
            )
            self.assertEqual([], checks.pages_workflow_errors(root))

    def test_pages_moving_runner_and_old_action_are_rejected(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            workflow = root / checks.PAGES_WORKFLOW
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "runs-on: ubuntu-latest\n"
                "uses: actions/configure-pages@old # v5\n"
                "uses: actions/deploy-pages@old # v4\n"
                "runs-on: ubuntu-latest\n",
                encoding="utf-8",
            )
            errors = checks.pages_workflow_errors(root)
            self.assertTrue(any("ubuntu-24.04" in error for error in errors))
            self.assertTrue(any("ubuntu-latest" in error for error in errors))
            self.assertTrue(any("v6.0.0" in error for error in errors))
            self.assertTrue(any("v5.0.1" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
