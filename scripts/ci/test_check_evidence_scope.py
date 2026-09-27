"""Tests for the generated-evidence change budget."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from check_evidence_scope import (MAX_ADDED_LINES_PER_FILE, MAX_CHANGED_FILES,
                                  MAX_FILE_BYTES, evaluate, is_evidence_data,
                                  load_exceptions, parse_numstat, registry_errors)


class EvidenceScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, relative: str, content: bytes = b"{}") -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_scope_is_narrow(self):
        self.assertTrue(is_evidence_data("software/ai/eval/result.json"))
        self.assertTrue(is_evidence_data("evidence/run/data.csv"))
        self.assertFalse(is_evidence_data("software/ai/eval/README.md"))
        self.assertFalse(is_evidence_data("software/ai/tests/fixture.json"))

    def test_numstat_parses_text_and_binary(self):
        self.assertEqual(parse_numstat("12\t3\tevidence/a.json\n-\t-\tevidence/a.npz\n"),
                         [(12, 3, "evidence/a.json"), (None, None, "evidence/a.npz")])

    def test_small_change_passes_and_unrelated_file_is_ignored(self):
        self.write("software/ai/eval/result.json")
        self.write("src/large.json", b"x" * (MAX_FILE_BYTES + 1))
        entries = [(100, 0, "software/ai/eval/result.json"),
                   (999_999, 0, "src/large.json")]
        self.assertEqual(evaluate(entries, self.root, {}), [])

    def test_line_file_count_and_size_limits(self):
        entries = []
        for index in range(MAX_CHANGED_FILES + 1):
            relative = f"software/ai/eval/{index}.json"
            self.write(relative)
            entries.append((1, 0, relative))
        oversized = "evidence/run/large.json"
        self.write(oversized, b"x" * (MAX_FILE_BYTES + 1))
        entries.append((MAX_ADDED_LINES_PER_FILE + 1, 0, oversized))
        errors = evaluate(entries, self.root, {})
        self.assertTrue(any("touches" in error for error in errors))
        self.assertTrue(any("adds" in error and oversized in error for error in errors))
        self.assertTrue(any("bytes" in error and oversized in error for error in errors))

    def test_total_line_limit(self):
        entries = []
        for index in range(3):
            relative = f"software/ai/eval/total-{index}.json"
            self.write(relative)
            entries.append((MAX_ADDED_LINES_PER_FILE, 0, relative))
        self.assertTrue(any("change adds" in error
                            for error in evaluate(entries, self.root, {})))

    def test_exact_exception_exempts_and_digest_change_fails(self):
        relative = "software/ai/eval/large.json"
        path = self.write(relative, b"reviewed")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        exception = {relative: {"path": relative, "sha256": digest,
                                "issue": "https://github.com/j-webtek/tactevra/issues/1",
                                "rationale": "Required frozen evidence."}}
        entry = [(MAX_ADDED_LINES_PER_FILE + 1, 0, relative)]
        self.assertEqual(evaluate(entry, self.root, exception), [])
        path.write_bytes(b"changed")
        self.assertTrue(any("stale" in error for error in evaluate(entry, self.root, exception)))
        self.assertTrue(registry_errors(self.root, exception))
        path.unlink()
        self.assertTrue(any("missing" in error for error in registry_errors(self.root, exception)))

    def test_deletion_is_not_counted(self):
        self.assertEqual(evaluate([(99_999, 2, "evidence/deleted.json")], self.root, {}), [])

    def test_registry_requires_exact_review_metadata(self):
        registry = self.root / "registry.json"
        registry.write_text(json.dumps({"version": 1, "exceptions": [{
            "path": "software/ai/eval/result.json",
            "sha256": "a" * 64,
            "issue": "https://github.com/j-webtek/tactevra/issues/61",
            "rationale": "Reviewed exception.",
        }]}), encoding="utf-8")
        self.assertIn("software/ai/eval/result.json", load_exceptions(registry))
        registry.write_text(json.dumps({"version": 1, "exceptions": [{
            "path": "software/ai/eval/result.json", "sha256": "bad",
            "issue": "https://example.com/1", "rationale": ""
        }]}), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_exceptions(registry)


if __name__ == "__main__":
    unittest.main()
