import json
import sys
from pathlib import Path

import jsonschema
import pytest

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path.insert(0, str(AI))
sys.path.insert(0, str(AI.parent / "src"))

from rocell_ai.mission_intent import (
    canonical_sha256,
    compile_mission_intent,
    decode_mission_intent,
    load_capabilities,
    validate_compilation,
    validate_mission_intent,
)


def keyboard_mission(text="robot"):
    return {
        "schema": "rocell.mission_intent.v1",
        "request_id": "request-001",
        "observation_ref": "frame-001",
        "decision": "execute",
        "operation": "type_text",
        "device": "keyboard",
        "arguments": {"text": text},
        "required_capability": "keyboard.typing.lowercase",
        "observation_policy": "verify_after_each_action",
    }


def phone_mission(text="test"):
    return {
        "schema": "rocell.mission_intent.v1",
        "request_id": "request-002",
        "observation_ref": "frame-002",
        "decision": "execute",
        "operation": "type_text",
        "device": "phone",
        "arguments": {"text": text},
        "required_capability": "phone.typing.lowercase",
        "observation_policy": "verify_after_each_state_change",
    }


def test_keyboard_mission_compiles_exact_literal_order():
    intent = keyboard_mission("robot")
    result = compile_mission_intent(intent, {"ref": "frame-001", "fresh": True})
    assert result["status"] == "accepted"
    assert result["mission_sha256"] == canonical_sha256(intent)
    assert result["capability_id"] == "keyboard.typing.lowercase"
    assert [action["key"] for action in result["action_plan"]["actions"]] == [
        "R",
        "O",
        "B",
        "O",
        "T",
    ]
    assert "coordinates" not in json.dumps(result)
    validate_compilation(result)


def test_phone_mission_requires_fresh_verified_state():
    intent = phone_mission()
    stale = compile_mission_intent(
        intent, {"ref": "frame-002", "fresh": False, "phone_state": "KEYBOARD_LOWER"}
    )
    assert stale["status"] == "blocked" and stale["reason"] == "stale_observation"
    wrong_state = compile_mission_intent(
        intent, {"ref": "frame-002", "fresh": True, "phone_state": "HOME"}
    )
    assert wrong_state["status"] == "blocked"
    assert wrong_state["reason"] == "phone_state_unverified"
    accepted = compile_mission_intent(
        intent, {"ref": "frame-002", "fresh": True, "phone_state": "KEYBOARD_LOWER"}
    )
    assert accepted["status"] == "accepted"
    assert accepted["action_plan"]["actions"][0] == {
        "type": "verify_phone_state",
        "state": "KEYBOARD_LOWER",
    }


def test_unsupported_call_is_understood_and_blocked_without_compilation():
    intent = {
        "schema": "rocell.mission_intent.v1",
        "request_id": "request-003",
        "observation_ref": "frame-003",
        "decision": "unsupported",
        "operation": "place_phone_call",
        "device": "phone",
        "required_capability": "phone.dialer.call",
        "reason": "operation_not_available",
    }
    result = compile_mission_intent(intent, {"ref": "frame-003", "fresh": True})
    assert result["status"] == "blocked"
    assert result["reason"] == "operation_not_available"
    assert "action_plan" not in result


def test_clarification_and_unsupported_profile_remain_zero_plan():
    clarify = {
        "schema": "rocell.mission_intent.v1",
        "request_id": "request-004",
        "observation_ref": "frame-004",
        "decision": "clarify",
        "reason": "payload_ambiguous",
    }
    result = compile_mission_intent(clarify, {"ref": "frame-004", "fresh": True})
    assert result["status"] == "blocked" and "action_plan" not in result

    uppercase = compile_mission_intent(
        keyboard_mission("Hello"), {"ref": "frame-001", "fresh": True}
    )
    assert uppercase["status"] == "blocked"
    assert uppercase["reason"] == "unsupported_by_profile"


def test_strict_decoder_and_semantic_validation_reject_tampering():
    with pytest.raises(ValueError, match="duplicate JSON field"):
        decode_mission_intent(
            '{"schema":"rocell.mission_intent.v1","schema":"tampered"}'
        )
    extra = {**keyboard_mission(), "joint_angles": [0, 1, 2]}
    with pytest.raises(ValueError, match="invalid fields"):
        validate_mission_intent(extra)
    wrong_capability = {
        **keyboard_mission(),
        "required_capability": "phone.typing.lowercase",
    }
    with pytest.raises(ValueError, match="does not match"):
        validate_mission_intent(wrong_capability)
    wrong_policy = {
        **keyboard_mission(),
        "observation_policy": "verify_after_each_state_change",
    }
    with pytest.raises(ValueError, match="does not match"):
        validate_mission_intent(wrong_policy)


def test_committed_schemas_and_capability_matrix_match_runtime():
    intent_schema = json.loads((AI / "schemas/mission_intent_v1.schema.json").read_text())
    compilation_schema = json.loads(
        (AI / "schemas/mission_compilation_v1.schema.json").read_text()
    )
    intent = keyboard_mission()
    result = compile_mission_intent(intent, {"ref": "frame-001", "fresh": True})
    jsonschema.Draft202012Validator(intent_schema).validate(intent)
    jsonschema.Draft202012Validator(compilation_schema).validate(result)

    capabilities = load_capabilities()
    assert set(capabilities) == {
        "keyboard.typing.lowercase",
        "phone.typing.lowercase",
        "keyboard.typing.shifted",
        "phone.dialer.call",
    }
    assert all(not item["physical_runtime_released"] for item in capabilities.values())
    assert capabilities["keyboard.typing.lowercase"]["offline_compiler_available"]
    assert capabilities["phone.typing.lowercase"]["required_device_state"] == "KEYBOARD_LOWER"
    assert not capabilities["phone.dialer.call"]["offline_compiler_available"]
