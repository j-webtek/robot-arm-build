import inspect
import sys
from collections import Counter
from pathlib import Path


AI = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from train import build_mission_development_v2 as generator


CATEGORIES = {
    "supported_keyboard",
    "supported_phone",
    "quoted_command_word_literal",
    "stale_observation",
    "phone_state_unverified",
    "device_ambiguous",
    "payload_ambiguous",
    "intent_ambiguous",
    "unsupported_profile",
    "unavailable_operation",
}
FORBIDDEN = {
    "coordinates",
    "joint_angles",
    "pwm",
    "serial",
    "controller_json",
    "permit",
    "transport",
}


def test_balanced_development_population_and_family_separation():
    records, counts = generator.build_records()
    assert set(records) == {"train", "validation"}
    assert len(records["train"]) == 1280
    assert len(records["validation"]) == 320
    for split, expected in (("train", 128), ("validation", 32)):
        split_counts = Counter(record["category"] for record in records[split])
        assert set(split_counts) == CATEGORIES
        assert set(split_counts.values()) == {expected}
        assert all(counts[f"{split}:{name}"] == expected for name in CATEGORIES)
    train_families = {record["family"] for record in records["train"]}
    validation_families = {record["family"] for record in records["validation"]}
    assert train_families.isdisjoint(validation_families)
    assert len(train_families) == 80
    assert len(validation_families) == 20


def test_compiler_outcomes_and_boundary_fields_are_exact():
    records, _ = generator.build_records()
    ids = set()
    for split_records in records.values():
        for record in split_records:
            assert record["id"] not in ids
            ids.add(record["id"])
            target = record["target"]
            assert not FORBIDDEN.intersection(target)
            category = record["category"]
            status = record["expected_compilation"]["status"]
            if category in {"supported_keyboard", "supported_phone", "quoted_command_word_literal"}:
                assert status == "accepted"
                assert record["expected_compilation"]["action_count"] > 0
            else:
                assert status == "blocked"
                assert record["expected_compilation"]["action_count"] == 0
            if category in {"stale_observation", "phone_state_unverified"}:
                assert target["decision"] == "execute"


def test_source_excludes_consumed_heldout_and_confirmation():
    source = inspect.getsource(generator)
    assert "mission_curriculum_v1_heldout.jsonl" not in source
    assert '"confirmation": {' in source
    assert '"present": False' in source
    records, _ = generator.build_records()
    assert "confirmation" not in records
