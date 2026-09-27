"""Tests for the external-artifact manifest contract."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from check_external_artifact import inspect_artifact, load_manifest


class ExternalArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = b"reviewed checkpoint bytes"
        self.relative = "software/ai/results/example/pose_model.pt"

    def document(self) -> dict:
        return {
            "schema_version": 1,
            "artifact_id": "example-pose-checkpoint-v1",
            "artifact_kind": "model-checkpoint",
            "repository_path": self.relative,
            "sha256": hashlib.sha256(self.payload).hexdigest(),
            "size_bytes": len(self.payload),
            "storage": "external",
            "required_for": ["artifact-present qualification"],
            "provenance": {
                "source_commit": "a" * 40,
                "producer_command": "python train.py --plan example.json",
            },
            "retention": {"owner": "j-webtek", "review_after": "2027-09-27"},
            "limitations": ["Synthetic example; not model promotion."],
        }

    def write_manifest(self, document=None) -> Path:
        path = self.root / "manifest.json"
        path.write_text(json.dumps(document or self.document()), encoding="utf-8")
        return path

    def write_artifact(self, payload=None) -> Path:
        path = self.root / self.relative
        path.parent.mkdir(parents=True)
        path.write_bytes(self.payload if payload is None else payload)
        return path

    def test_absent_external_artifact_is_explicit(self):
        manifest = load_manifest(self.write_manifest())
        result = inspect_artifact(self.root, manifest)
        self.assertEqual(result.status, "external_artifact_unavailable")
        self.assertIsNone(result.actual_sha256)

    def test_present_artifact_verifies_size_and_digest(self):
        self.write_artifact()
        result = inspect_artifact(self.root, load_manifest(self.write_manifest()))
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.actual_size_bytes, len(self.payload))

    def test_wrong_bytes_are_not_accepted(self):
        self.write_artifact(b"different checkpoint bytes")
        result = inspect_artifact(self.root, load_manifest(self.write_manifest()))
        self.assertIn(result.status, {"size_mismatch", "digest_mismatch"})

    def test_same_size_wrong_digest_is_distinct(self):
        self.write_artifact(b"x" * len(self.payload))
        result = inspect_artifact(self.root, load_manifest(self.write_manifest()))
        self.assertEqual(result.status, "digest_mismatch")

    def test_manifest_rejects_escape_untracked_root_and_bad_commit(self):
        for field, value in (
            ("repository_path", "../secret.pt"),
            ("repository_path", "models/checkpoint.pt"),
        ):
            document = self.document()
            document[field] = value
            with self.assertRaises(ValueError):
                load_manifest(self.write_manifest(document))
        document = self.document()
        document["provenance"]["source_commit"] = "short"
        with self.assertRaises(ValueError):
            load_manifest(self.write_manifest(document))


if __name__ == "__main__":
    unittest.main()
