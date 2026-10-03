"""Hardware-free checks for the canonical storyboard video production contract."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "presentations" / "blender"))

import produce_storyboard_v21_video as production  # noqa: E402


class StoryboardVideoContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(production.MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_text_tracks_share_the_manifest_timing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            srt, vtt, chapters, metadata = production.write_text_tracks(
                self.manifest, Path(directory)
            )
            self.assertIn("00:00:04,000 --> 00:00:09,000", srt.read_text(encoding="utf-8"))
            self.assertIn("00:01:36.000 --> 00:01:40.000", vtt.read_text(encoding="utf-8"))
            self.assertIn("Verify", chapters.read_text(encoding="utf-8"))
            self.assertIn("END=100000", metadata.read_text(encoding="utf-8"))

    def test_voice_contract_requires_fourteen_ordered_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for cue in self.manifest["narration"]:
                (root / f"voice_{cue['id']:02d}.wav").write_bytes(b"RIFF")
            selected = production.select_voice_files(self.manifest, root)
            self.assertEqual([path.stem for path in selected], [f"voice_{i:02d}" for i in range(1, 15)])


if __name__ == "__main__":
    unittest.main()
