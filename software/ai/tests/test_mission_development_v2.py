import hashlib
import json
import sys
from pathlib import Path


AI = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from rocell_ai.mission_intent import compile_mission_intent, validate_mission_intent
from train.build_mission_development_v2 import build_records, encoded


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_development_v2_reproduces_exact_bytes_and_manifest():
    manifest_path = AI / "data/mission_development_v2.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    generated, counts = build_records()
    assert manifest["schema"] == "rocell.mission_development.v2"
    assert manifest["category_counts"] == dict(sorted(counts.items()))
    assert manifest["generator_sha256"] == hashlib.sha256(
        (AI / "train/build_mission_development_v2.py").read_bytes()
    ).hexdigest()
    assert manifest["capability_matrix_sha256"] == hashlib.sha256(
        (AI / "capabilities/mission_capabilities_v1.json").read_bytes()
    ).hexdigest()
    assert manifest["confirmation"]["present"] is False
    assert manifest["hardware_writes"] == manifest["physical_movements"] == 0
    for split in ("train", "validation"):
        path = AI / f"data/mission_development_v2_{split}.jsonl"
        raw = path.read_bytes()
        assert raw == encoded(generated[split])
        assert manifest["splits"][split]["sha256"] == hashlib.sha256(raw).hexdigest()
        assert manifest["splits"][split]["count"] == len(generated[split])
        assert manifest["splits"][split]["families"] == sorted(
            {row["family"] for row in generated[split]}
        )


def test_every_serialized_record_revalidates_and_recompiles():
    ids = set()
    for split in ("train", "validation"):
        rows = load_jsonl(AI / f"data/mission_development_v2_{split}.jsonl")
        for row in rows:
            assert row["id"] not in ids
            ids.add(row["id"])
            validate_mission_intent(row["target"])
            compilation = compile_mission_intent(row["target"], row["observation"])
            assert row["expected_compilation"] == {
                "status": compilation["status"],
                "reason": compilation.get("reason"),
                "plan_hash": compilation.get("plan_hash"),
                "action_count": len(
                    compilation.get("action_plan", {}).get("actions", [])
                ),
            }


def test_no_confirmation_artifact_or_family_exists():
    assert not list((AI / "data").glob("mission_development_v2_confirmation*"))
    manifest = json.loads((AI / "data/mission_development_v2.manifest.json").read_text())
    families = {
        split: set(details["families"])
        for split, details in manifest["splits"].items()
    }
    assert set(families) == {"train", "validation"}
    assert families["train"].isdisjoint(families["validation"])
    assert not any("confirmation" in family for values in families.values() for family in values)
