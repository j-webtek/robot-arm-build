import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import check_source_archive_footprint as footprint


def valid_policy() -> dict:
    return {
        "schema": footprint.SCHEMA,
        "archive_mode": "github-generated-source-archives",
        "archive_constraint": "All tracked paths are included.",
        "ceilings": {
            "max_tracked_files": 10,
            "max_logical_bytes": 1000,
            "max_single_blob_bytes": 500,
            "duplicate_min_blob_bytes": 100,
            "max_duplicate_bytes": 300,
        },
        "reduction_targets": {"max_logical_bytes": 800, "max_duplicate_bytes": 200},
        "baseline": {
            "commit": "a" * 40,
            "tracked_files": 3,
            "logical_bytes": 700,
            "duplicate_bytes": 100,
        },
    }


class SourceArchiveFootprintTests(unittest.TestCase):
    def test_policy_loads(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "policy.json"
            path.write_text(json.dumps(valid_policy()), encoding="utf-8")
            self.assertEqual(10, footprint.load_policy(path)["ceilings"]["max_tracked_files"])

    def test_policy_rejects_target_above_ceiling(self):
        value = valid_policy()
        value["reduction_targets"]["max_logical_bytes"] = 1001
        with TemporaryDirectory() as folder:
            path = Path(folder) / "policy.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "reduction target"):
                footprint.load_policy(path)

    def test_parse_and_summarize_exact_duplicates(self):
        entries = footprint.parse_tree(
            "100644 blob abc 120\ta.bin\n"
            "100644 blob abc 120\tb.bin\n"
            "100644 blob def 80\tc.txt\n"
        )
        observed = footprint.summarize(entries, duplicate_min_blob_bytes=100)
        self.assertEqual(3, observed.tracked_files)
        self.assertEqual(320, observed.logical_bytes)
        self.assertEqual(120, observed.duplicate_bytes)

    def test_evaluate_reports_each_exceeded_ceiling(self):
        observed = footprint.Footprint(11, 1001, 501, 301)
        errors = footprint.evaluate(observed, valid_policy())
        self.assertEqual(4, len(errors))

    def test_report_separates_ceiling_from_target(self):
        observed = footprint.Footprint(3, 900, 400, 250)
        result = footprint.report(observed, valid_policy())
        self.assertFalse(result["within_reduction_target"]["logical_bytes"])
        self.assertFalse(result["within_reduction_target"]["duplicate_bytes"])


if __name__ == "__main__":
    unittest.main()
