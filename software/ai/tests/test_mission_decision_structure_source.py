import json
from pathlib import Path

from rocell_ai.mission_decision_structure import structural_decision


AI = Path(__file__).resolve().parents[1]


def test_structural_baseline_matches_every_frozen_validation_target():
    rows = [
        json.loads(line)
        for line in (AI / "data/mission_decision_curriculum_v1_validation.jsonl").read_text().splitlines()
    ]
    assert len(rows) == 320
    assert all(structural_decision(row["request"]) == row["target"] for row in rows)


def test_structural_baseline_keeps_phone_keyboard_compound_and_conflict_distinct():
    assert structural_decision('Type "one" on the phone keyboard.') == {
        "schema": "rocell.mission_decision.v1", "decision": "execute", "device": "phone"
    }
    assert structural_decision('Type "one" on the phone or the keyboard.') == {
        "schema": "rocell.mission_decision.v1", "decision": "clarify", "reason": "device_ambiguous"
    }


def test_structural_baseline_routes_explicit_unsupported_and_ambiguity():
    assert structural_decision("Have the handset telephone 2025550101.")["kind"] == "phone_call"
    assert structural_decision('Make a keyboard entry containing "UPPER".')["kind"] == "shifted_keyboard_text"
    assert structural_decision('Put "one" into the input area.')["reason"] == "device_ambiguous"
    assert structural_decision('Use the keyboard for "one" or "two".')["reason"] == "payload_ambiguous"
    assert structural_decision('Type "one" on the keyboard while forwarding email.')["reason"] == "intent_ambiguous"
