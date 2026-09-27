import hashlib
import json
import sys
from pathlib import Path


AI = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from train.build_mission_decision_curriculum_v1 import build_records, encoded


def test_compact_curriculum_reproduces_exact_bytes_manifest_and_lineage():
    manifest_path = AI / "data/mission_decision_curriculum_v1.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    records, _ = build_records()
    assert manifest["exact_reassembly_count"] == 1600
    assert manifest["conservative_downgrade_count"] == 0
    assert manifest["confirmation"]["present"] is False
    assert manifest["source_manifest_sha256"] == hashlib.sha256(
        (AI / "data/mission_development_v2.manifest.json").read_bytes()
    ).hexdigest()
    assert manifest["generator_sha256"] == hashlib.sha256(
        (AI / "train/build_mission_decision_curriculum_v1.py").read_bytes()
    ).hexdigest()
    for split in ("train", "validation"):
        path = AI / f"data/mission_decision_curriculum_v1_{split}.jsonl"
        raw = path.read_bytes()
        assert raw == encoded(records[split])
        assert manifest["splits"][split]["sha256"] == hashlib.sha256(raw).hexdigest()
        assert manifest["splits"][split]["count"] == len(records[split])
    assert not list((AI / "data").glob("mission_decision_curriculum_v1_confirmation*"))


def test_inverse_frequency_weights_equalize_training_class_mass():
    manifest = json.loads(
        (AI / "data/mission_decision_curriculum_v1.manifest.json").read_text()
    )
    counts = manifest["class_counts"]["train"]
    weights = manifest["recommended_inverse_frequency_weights"]["train"]
    weighted = {label: counts[label] * weights[label] for label in counts}
    assert max(weighted.values()) - min(weighted.values()) < 1e-12
