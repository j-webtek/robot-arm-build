import hashlib
import json
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI))
sys.path.insert(0, str(AI.parent / "src"))

from rocell_ai.mission_intent import compile_mission_intent, validate_mission_intent
from train.build_mission_curriculum_v1 import build_records, encoded


SPLITS = ("train", "validation", "heldout")
FORBIDDEN_FIELDS = {
    "coordinates",
    "joint_angles",
    "pwm",
    "serial",
    "controller_json",
    "permit",
    "transport",
}


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_curriculum_reproduces_exact_bytes_and_manifest_hashes():
    manifest_path = AI / "data/mission_curriculum_v1.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    generated, counters = build_records()
    assert manifest["schema"] == "rocell.mission_curriculum.v1"
    assert not manifest["human_reviewed"]
    assert manifest["hardware_writes"] == manifest["physical_movements"] == 0
    assert manifest["generator_sha256"] == hashlib.sha256(
        (AI / "train/build_mission_curriculum_v1.py").read_bytes()
    ).hexdigest()
    assert manifest["capability_matrix_sha256"] == hashlib.sha256(
        (AI / "capabilities/mission_capabilities_v1.json").read_bytes()
    ).hexdigest()
    assert manifest["category_counts"] == dict(sorted(counters.items()))

    for split in SPLITS:
        path = AI / f"data/mission_curriculum_v1_{split}.jsonl"
        raw = path.read_bytes()
        assert raw == encoded(generated[split])
        assert manifest["splits"][split]["count"] == len(generated[split])
        assert manifest["splits"][split]["sha256"] == hashlib.sha256(raw).hexdigest()


def test_families_are_disjoint_and_heldout_is_balanced():
    manifest = json.loads((AI / "data/mission_curriculum_v1.manifest.json").read_text())
    families = {
        split: set(manifest["splits"][split]["families"]) for split in SPLITS
    }
    assert families["train"].isdisjoint(families["validation"])
    assert families["train"].isdisjoint(families["heldout"])
    assert families["validation"].isdisjoint(families["heldout"])
    heldout_counts = {
        key.split(":", 1)[1]: value
        for key, value in manifest["category_counts"].items()
        if key.startswith("heldout:")
    }
    assert set(heldout_counts.values()) == {8}
    assert len(heldout_counts) == 10


def test_every_record_validates_and_reproduces_compilation_outcome():
    ids = set()
    for split in SPLITS:
        records = load_jsonl(AI / f"data/mission_curriculum_v1_{split}.jsonl")
        for record in records:
            assert record["id"] not in ids
            ids.add(record["id"])
            assert record["split"] == split
            assert record["review"] == {
                "basis": "mission_runtime_validation_and_read_only_compiler",
                "state": "compiler_checked_simulated_review_no_human",
            }
            validate_mission_intent(record["target"])
            result = compile_mission_intent(record["target"], record["observation"])
            actual = {
                "status": result["status"],
                "reason": result.get("reason"),
                "plan_hash": result.get("plan_hash"),
                "action_count": len(result.get("action_plan", {}).get("actions", [])),
            }
            assert actual == record["expected_compilation"]
            serialized = json.dumps(record["target"], sort_keys=True)
            assert not any(field in serialized for field in FORBIDDEN_FIELDS)


def test_stale_and_unverified_state_keep_semantics_but_block_compilation():
    records = []
    for split in SPLITS:
        records.extend(load_jsonl(AI / f"data/mission_curriculum_v1_{split}.jsonl"))
    state_cases = [
        record
        for record in records
        if record["category"] in {"stale_observation", "phone_state_unverified"}
    ]
    assert state_cases
    assert all(record["target"]["decision"] == "execute" for record in state_cases)
    assert {record["expected_compilation"]["reason"] for record in state_cases} == {
        "stale_observation",
        "phone_state_unverified",
    }
    assert all(record["expected_compilation"]["action_count"] == 0 for record in state_cases)


def test_unavailable_and_ambiguous_targets_never_create_plans():
    records = []
    for split in SPLITS:
        records.extend(load_jsonl(AI / f"data/mission_curriculum_v1_{split}.jsonl"))
    blocked = [record for record in records if record["target"]["decision"] != "execute"]
    assert blocked
    assert all(record["expected_compilation"]["status"] == "blocked" for record in blocked)
    assert all(record["expected_compilation"]["plan_hash"] is None for record in blocked)
    assert all(record["expected_compilation"]["action_count"] == 0 for record in blocked)
