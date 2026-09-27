"""Tests for repository artifact growth policy."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from check_repository_artifacts import (TreeEntry, evaluate, load_policy,
                                        parse_changed_paths, parse_tree)


def policy(*, limit=10, suffixes=None, exceptions=None):
    return {
        "version": 1,
        "max_changed_file_bytes": limit,
        "governed_binary_suffixes": suffixes or [".step", ".stl"],
        "exceptions": exceptions or [],
    }


class RepositoryArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, relative, content=b"x"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_tree_and_change_parsers(self):
        tree = parse_tree("100644 blob abc123 12\tmodels/a.stl\n")
        self.assertEqual(tree["models/a.stl"].size, 12)
        changes = parse_changed_paths("A\tmodels/a.stl\nM\tdocs/a.md\nD\told.bin\n")
        self.assertEqual(changes, ["docs/a.md", "models/a.stl"])

    def test_small_unique_change_passes(self):
        self.write("models/a.stl", b"small")
        tree = {"models/a.stl": TreeEntry("models/a.stl", "one", 5)}
        self.assertEqual(evaluate(self.root, ["models/a.stl"], tree, policy()), [])

    def test_oversized_change_fails(self):
        self.write("models/a.stl", b"x" * 11)
        tree = {"models/a.stl": TreeEntry("models/a.stl", "one", 11)}
        self.assertTrue(any("limit" in error
                            for error in evaluate(self.root, ["models/a.stl"], tree,
                                                  policy())))

    def test_new_duplicate_binary_fails_but_unchanged_duplicate_is_baselined(self):
        self.write("models/a.stl", b"same")
        self.write("steps/copy.stl", b"same")
        tree = {
            "models/a.stl": TreeEntry("models/a.stl", "same-object", 4),
            "steps/copy.stl": TreeEntry("steps/copy.stl", "same-object", 4),
        }
        self.assertTrue(any("duplicates" in error
                            for error in evaluate(self.root, ["steps/copy.stl"], tree,
                                                  policy())))
        self.assertEqual(evaluate(self.root, [], tree, policy()), [])

    def test_identical_text_is_not_duplicate_governed_binary(self):
        self.write("docs/a.md", b"same")
        self.write("docs/b.md", b"same")
        tree = {
            "docs/a.md": TreeEntry("docs/a.md", "same-object", 4),
            "docs/b.md": TreeEntry("docs/b.md", "same-object", 4),
        }
        self.assertEqual(evaluate(self.root, ["docs/b.md"], tree, policy()), [])

    def test_exact_review_exception_passes_and_changed_bytes_fail(self):
        content = b"reviewed artifact"
        path = self.write("models/a.stl", content)
        digest = hashlib.sha256(content).hexdigest()
        exception = {"path": "models/a.stl", "sha256": digest,
                     "issue": "https://github.com/j-webtek/tactevra/issues/1",
                     "rationale": "Reviewed canonical artifact."}
        tree = {"models/a.stl": TreeEntry("models/a.stl", "one", 100)}
        self.assertEqual(evaluate(
            self.root, ["models/a.stl"], tree,
            policy(limit=10, exceptions=[exception])), [])
        path.write_bytes(b"changed")
        self.assertTrue(any("stale" in error for error in evaluate(
            self.root, ["models/a.stl"], tree,
            policy(limit=10, exceptions=[exception]))))

    def test_policy_loader_rejects_unreviewed_exception(self):
        path = self.root / "policy.json"
        invalid = policy(exceptions=[{
            "path": "models/a.stl", "sha256": "bad", "issue": "https://example.com/1",
            "rationale": "",
        }])
        path.write_text(json.dumps(invalid), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_policy(path)


if __name__ == "__main__":
    unittest.main()
