import sys
from collections import Counter
from pathlib import Path


AI = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from train.build_mission_decision_curriculum_v1 import build_records


EXPECTED = {
    "execute.keyboard": 384,
    "execute.phone": 256,
    "clarify.device_ambiguous": 128,
    "clarify.payload_ambiguous": 128,
    "clarify.intent_ambiguous": 128,
    "unsupported.shifted_keyboard_text": 128,
    "unsupported.phone_call": 128,
}


def test_every_compact_target_exactly_reassembles_source_mission():
    records, counts = build_records()
    assert len(records["train"]) == 1280
    assert len(records["validation"]) == 320
    assert all(item["assembly_status"] == "assembled" for rows in records.values() for item in rows)
    assert Counter(item["class_label"] for item in records["train"]) == EXPECTED
    assert Counter(item["class_label"] for item in records["validation"]) == {
        label: count // 4 for label, count in EXPECTED.items()
    }
    assert counts == Counter(
        {
            **{f"train:{label}": count for label, count in EXPECTED.items()},
            **{f"validation:{label}": count // 4 for label, count in EXPECTED.items()},
        }
    )


def test_compact_targets_never_contain_literals_or_bindings():
    records, _ = build_records()
    forbidden = {
        "text",
        "request_id",
        "observation_ref",
        "required_capability",
        "observation_policy",
        "coordinates",
        "joint_angles",
        "pwm",
        "permit",
        "transport",
    }
    for rows in records.values():
        for item in rows:
            assert not forbidden.intersection(item["target"])
