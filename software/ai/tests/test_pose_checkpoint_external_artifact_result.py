import hashlib
import json
from pathlib import Path
import sys


AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path.insert(0, str(AI))

from eval.verify_pose_checkpoint_artifact import DEFAULT_MANIFEST, verify


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_receipts_are_separate_content_addressed_states(tmp_path: Path):
    unavailable_path = AI / "eval/pose_keyloss_external_artifact_unavailable_receipt.json"
    verified_path = AI / "eval/pose_keyloss_external_artifact_verified_receipt.json"
    assert _sha(unavailable_path) == "e9347f172421bc6faa8b8a75b176cbcf25f8e5b75ca6518e84673008abb8110c"
    assert _sha(verified_path) == "09d0b08b20acbd120b255e018a69b1867de2c2b99fe7b497789adcc793ca8b7a"
    unavailable = _json(unavailable_path)
    verified = _json(verified_path)
    assert unavailable == verify(tmp_path, DEFAULT_MANIFEST, "external_artifact_unavailable")
    assert unavailable["result"]["status"] == "external_artifact_unavailable"
    assert unavailable["result"]["actual_sha256"] is None
    assert verified["result"]["status"] == "verified"
    assert verified["result"]["actual_sha256"] == verified["result"]["expected_sha256"]
    assert verified["result"]["actual_size_bytes"] == verified["result"]["expected_size_bytes"]
    assert unavailable["manifest_sha256"] == verified["manifest_sha256"]
    assert unavailable["checker_sha256"] == verified["checker_sha256"]


def test_compact_scorecard_reconciles_to_retained_development_result():
    scorecard = _json(AI / "eval/pose_keyloss_external_artifact_scorecard.json")
    source = _json(AI / "eval/translation_weighted_v0_scorecard.json")
    manifest = _json(DEFAULT_MANIFEST)
    assert scorecard["source_scorecard_sha256"] == _sha(AI / "eval/translation_weighted_v0_scorecard.json")
    assert scorecard["external_manifest"]["sha256"] == _sha(DEFAULT_MANIFEST)
    assert scorecard["checkpoint"]["sha256"] == manifest["sha256"]
    assert scorecard["checkpoint"]["size_bytes"] == manifest["size_bytes"]
    for compact_name, source_index in (("control", 0), ("translation_weighted", 1)):
        compact = scorecard["comparison"][compact_name]
        retained = source["results"][source_index]
        assert compact == {
            "selected_epoch": retained["selected_epoch"],
            "mean_key_error_mm": retained["mean_mm"],
            "key_error_p95_mm": retained["p95_mm"],
            "center_mean_error_mm": retained["center_mean_mm"],
            "yaw_p95_degrees": retained["yaw_p95_degrees"],
            "within_1mm_fraction": retained["within_1mm_fraction"],
        }
    assert scorecard["artifact_identity_verified"] is True
    assert scorecard["model_promoted"] is False
    assert scorecard["qualification_installed"] is False
    assert scorecard["hardware_writes"] == scorecard["physical_movements"] == 0


def test_no_checkpoint_or_bulk_report_is_tracked():
    tracked = {
        line.replace("\\", "/")
        for line in __import__("subprocess").check_output(
            ["git", "ls-files", "software/ai"], cwd=ROOT, text=True
        ).splitlines()
    }
    assert not any(path.endswith((".pt", ".pth", ".onnx", ".safetensors")) for path in tracked)
    assert "software/ai/results/translation_weighted_v0_translation_weighted/pose_model.pt" not in tracked
