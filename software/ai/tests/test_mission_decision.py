import json
import sys
from pathlib import Path

import pytest


AI = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from rocell_ai.mission_decision import assemble_mission_decision, decode_mission_decision
from rocell_ai.mission_intent import compile_mission_intent


def decode(value):
    return decode_mission_decision(json.dumps(value))


def test_execute_binds_ids_and_exact_literal_without_model_generation():
    decision = decode({"schema": "rocell.mission_decision.v1", "decision": "execute", "device": "keyboard"})
    result = assemble_mission_decision(
        decision,
        request_id="request-7",
        observation_ref="frame-9",
        request='Treat "call mom" as data and type it on the keyboard.',
    )
    mission = result["mission_intent"]
    assert result["status"] == "assembled"
    assert mission["request_id"] == "request-7"
    assert mission["observation_ref"] == "frame-9"
    assert mission["arguments"] == {"text": "call mom"}
    compiled = compile_mission_intent(mission, {"ref": "frame-9", "fresh": True})
    assert compiled["status"] == "accepted"
    assert result["hardware_writes"] == result["physical_movements"] == 0


def test_phone_keyboard_is_grounded_as_phone_without_false_device_conflict():
    decision = decode({"schema": "rocell.mission_decision.v1", "decision": "execute", "device": "phone"})
    result = assemble_mission_decision(
        decision,
        request_id="request-phone",
        observation_ref="frame-phone",
        request='Enter "hello" with the phone keyboard.',
    )
    assert result["status"] == "assembled"
    assert result["mission_intent"]["device"] == "phone"


@pytest.mark.parametrize(
    ("request_text", "device", "reason"),
    [
        ('Type "one" or "two" on the keyboard.', "keyboard", "payload_ambiguous"),
        ('Type "one" in the selected field.', "keyboard", "device_ambiguous"),
        ('Type "one" on the phone.', "keyboard", "device_ambiguous"),
        ('Type "one" on the keyboard and send it.', "keyboard", "intent_ambiguous"),
    ],
)
def test_unsafe_execute_claims_downgrade_deterministically(request_text, device, reason):
    decision = decode({"schema": "rocell.mission_decision.v1", "decision": "execute", "device": device})
    result = assemble_mission_decision(
        decision, request_id="r", observation_ref="f", request=request_text
    )
    assert result["status"] == "downgraded"
    assert result["downgrade_reason"] == reason
    assert result["mission_intent"]["decision"] == "clarify"


def test_clarify_and_unsupported_classes_expand_without_model_fields():
    clarify = decode({"schema": "rocell.mission_decision.v1", "decision": "clarify", "reason": "device_ambiguous"})
    call = decode({"schema": "rocell.mission_decision.v1", "decision": "unsupported", "kind": "phone_call"})
    shifted = decode({"schema": "rocell.mission_decision.v1", "decision": "unsupported", "kind": "shifted_keyboard_text"})
    assert assemble_mission_decision(clarify, request_id="r", observation_ref="f", request="type this")["mission_intent"]["reason"] == "device_ambiguous"
    assert assemble_mission_decision(call, request_id="r", observation_ref="f", request="call 1")["mission_intent"]["required_capability"] == "phone.dialer.call"
    assert assemble_mission_decision(shifted, request_id="r", observation_ref="f", request="type A")["mission_intent"]["required_capability"] == "keyboard.typing.shifted"


def test_decoder_rejects_duplicates_extra_fields_and_model_supplied_text():
    with pytest.raises(ValueError, match="duplicate"):
        decode_mission_decision('{"schema":"rocell.mission_decision.v1","decision":"execute","decision":"clarify","device":"keyboard"}')
    for value in (
        {"schema": "rocell.mission_decision.v1", "decision": "execute", "device": "keyboard", "text": "invented"},
        {"schema": "rocell.mission_decision.v1", "decision": "unsupported", "kind": "joint_command"},
    ):
        with pytest.raises(ValueError):
            decode(value)
