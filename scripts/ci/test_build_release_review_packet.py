import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import build_release_review_packet as packet


class ReleaseReviewPacketTests(unittest.TestCase):
    def test_parse_checks_requires_unique_bounded_statuses(self):
        self.assertEqual({"docs": 0, "integrity": 1}, packet.parse_checks(["docs=0", "integrity=1"]))
        for values in ([], ["docs"], ["Docs=0"], ["docs=-1"], ["docs=256"], ["docs=0", "docs=1"]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                packet.parse_checks(values)

    def test_parse_tree_preserves_spaces_and_sizes(self):
        raw = (
            b"100644 blob " + b"a" * 40 + b" 12\tdocs/a file.md\0"
            b"100755 blob " + b"b" * 40 + b" 7\tscripts/run.py\0"
        )
        entries = packet.parse_tree(raw)
        self.assertEqual("docs/a file.md", entries[0]["path"])
        self.assertEqual(19, sum(entry["bytes"] for entry in entries))

    def test_build_packet_binds_exact_tree_and_check_results(self):
        expected = "a" * 40
        tree = "b" * 40
        entries = [{"path": "README.md", "mode": "100644", "object_id": "c" * 40, "bytes": 9}]

        def fake_git(*args, root=None):
            values = {
                ("rev-parse", "HEAD"): expected,
                ("status", "--porcelain", "--untracked-files=no"): "",
                ("rev-parse", "HEAD^{tree}"): tree,
                ("rev-parse", "--show-object-format"): "sha1",
                ("show", "-s", "--format=%cI", "HEAD"): "2026-09-28T12:00:00-04:00",
            }
            return values[args]

        with patch.object(packet, "git", side_effect=fake_git), patch.object(packet, "git_tree", return_value=entries):
            metadata, manifest = packet.build_packet(expected, {"docs": 0, "integrity": 1})

        self.assertFalse(metadata["candidate_gate_passed"])
        self.assertFalse(metadata["publishes_release"])
        self.assertEqual(tree, metadata["tree_sha"])
        self.assertEqual(
            hashlib.sha256(packet.canonical_json(manifest)).hexdigest(),
            metadata["source_tree_manifest"]["sha256"],
        )

    def test_write_packet_refuses_to_overwrite_existing_directory(self):
        with TemporaryDirectory() as folder:
            output = Path(folder) / "packet"
            output.mkdir()
            with self.assertRaises(FileExistsError):
                packet.write_packet(output, {}, {})

    def test_written_metadata_is_valid_json_and_summary_states_boundary(self):
        metadata = {
            "candidate_gate_passed": True,
            "candidate_sha": "a" * 40,
            "tree_sha": "b" * 40,
            "source_tree_manifest": {"tracked_file_count": 1, "logical_bytes": 9, "sha256": "c" * 64},
            "checks": {"docs": {"exit_code": 0, "passed": True}},
            "publishes_release": False,
        }
        manifest = {"entries": []}
        with TemporaryDirectory() as folder:
            output = Path(folder) / "packet"
            packet.write_packet(output, metadata, manifest)
            observed = json.loads((output / "candidate-metadata.json").read_text(encoding="utf-8"))
            summary = (output / "REVIEW.md").read_text(encoding="utf-8")
        self.assertEqual(metadata, observed)
        self.assertIn("creates no tag or release", summary)


if __name__ == "__main__":
    unittest.main()
