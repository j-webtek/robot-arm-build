from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "rc03_stage_hash_bound_artifacts",
    ROOT / "scripts" / "stage_hash_bound_artifacts.py",
)
assert SPEC and SPEC.loader
staging = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(staging)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class HashBoundArtifactStagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "project"
        self.root.mkdir()
        self.payload = b"controlled artifact\n"
        self.source = self.root / "stl" / "part.stl"
        self.source.parent.mkdir()
        self.source.write_bytes(self.payload)
        self.manifest = self.root / "STEP_MANIFEST.json"
        self.manifest.write_text(
            json.dumps(
                {
                    "canonical_files": [
                        {
                            "canonical_path": "stl/part.stl",
                            "sha256": digest(self.payload),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_stage_can_be_verified_without_repository_access(self) -> None:
        output = Path(self.temporary.name) / "stage"
        receipt = staging.stage(self.root, [self.manifest], output)
        self.assertEqual(receipt["artifact_count"], 1)
        self.assertEqual((output / "artifacts" / "stl" / "part.stl").read_bytes(), self.payload)

        self.source.unlink()
        result = staging.verify(output)
        self.assertEqual(result["status"], "PASS")

    def test_source_hash_mismatch_fails_closed(self) -> None:
        self.source.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            staging.stage(self.root, [self.manifest], Path(self.temporary.name) / "stage")

    def test_staged_tampering_fails_closed(self) -> None:
        output = Path(self.temporary.name) / "stage"
        staging.stage(self.root, [self.manifest], output)
        (output / "artifacts" / "stl" / "part.stl").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            staging.verify(output)

    def test_path_traversal_is_rejected(self) -> None:
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        value["canonical_files"][0]["canonical_path"] = "../part.stl"
        self.manifest.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unsafe canonical_path"):
            staging.stage(self.root, [self.manifest], Path(self.temporary.name) / "stage")

    def test_existing_output_is_not_overwritten(self) -> None:
        output = Path(self.temporary.name) / "stage"
        output.mkdir()
        with self.assertRaises(FileExistsError):
            staging.stage(self.root, [self.manifest], output)


if __name__ == "__main__":
    unittest.main()
