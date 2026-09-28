import json
from pathlib import Path
import sys

import pytest


AI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI))

from eval.verify_pose_checkpoint_artifact import DEFAULT_MANIFEST, verify


EXPECTED_SHA256 = "0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d"
EXPECTED_SIZE = 1111650


def test_manifest_pins_pose_keyloss_identity_and_provenance():
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["artifact_id"] == "translation-weighted-pose-keyloss-v0"
    assert manifest["artifact_kind"] == "model-checkpoint"
    assert manifest["storage"] == "external"
    assert manifest["sha256"] == EXPECTED_SHA256
    assert manifest["size_bytes"] == EXPECTED_SIZE
    assert manifest["provenance"] == {
        "source_commit": "fe20dc15376361f38049e4791583af72b62e5a77",
        "producer_command": "python software/ai/vision/train_translation_weighted.py",
    }


def test_clean_root_emits_exact_unavailable_state(tmp_path: Path):
    receipt = verify(tmp_path, DEFAULT_MANIFEST, "external_artifact_unavailable")
    assert receipt["result"]["status"] == "external_artifact_unavailable"
    assert receipt["result"]["actual_sha256"] is None
    assert receipt["result"]["actual_size_bytes"] is None
    assert receipt["artifact_reads"] == receipt["artifact_writes"] == 0
    assert receipt["hardware_writes"] == receipt["physical_movements"] == 0


def test_expected_state_mismatch_fails_closed(tmp_path: Path):
    with pytest.raises(ValueError, match="expected verified, observed external_artifact_unavailable"):
        verify(tmp_path, DEFAULT_MANIFEST, "verified")
