"""Strict mission-intent boundary above RoCell's semantic ActionPlan compiler."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .adapter import inspect


MISSION_SCHEMA = "rocell.mission_intent.v1"
COMPILATION_SCHEMA = "rocell.mission_compilation.v1"
CAPABILITY_SCHEMA = "rocell.mission_capabilities.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMON = {"schema", "request_id", "observation_ref", "decision"}
_SHAPES = {
    "execute": _COMMON
    | {
        "operation",
        "device",
        "arguments",
        "required_capability",
        "observation_policy",
    },
    "clarify": _COMMON | {"reason"},
    "unsupported": _COMMON
    | {"operation", "device", "required_capability", "reason"},
}
_CLARIFY_REASONS = {"device_ambiguous", "payload_ambiguous", "intent_ambiguous"}
_UNSUPPORTED_REASONS = {"operation_not_available", "unsupported_by_profile"}
_BLOCK_REASONS = _CLARIFY_REASONS | _UNSUPPORTED_REASONS | {
    "stale_observation",
    "phone_state_unverified",
    "capability_mismatch",
    "capability_not_available",
}
_CAPABILITY_FIELDS = {
    "capability_id",
    "operation",
    "device",
    "offline_compiler_available",
    "semantic_profile_id",
    "required_observation_policy",
    "required_device_state",
    "physical_runtime_released",
}


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{name} contains a control character")
    return value


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def decode_mission_intent(payload: str) -> dict[str, Any]:
    """Decode bounded JSON while rejecting duplicate fields and non-objects."""

    if not isinstance(payload, str) or len(payload.encode("utf-8")) > 16_384:
        raise ValueError("mission payload must be a bounded JSON string")
    try:
        value = json.loads(payload, object_pairs_hook=_object_without_duplicates)
    except json.JSONDecodeError as error:
        raise ValueError("mission payload is not valid JSON") from error
    if not isinstance(value, dict):
        raise ValueError("mission intent must be an object")
    return value


def canonical_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_capabilities(path: Path | None = None) -> dict[str, dict[str, Any]]:
    if path is None:
        path = Path(__file__).resolve().parents[1] / "capabilities/mission_capabilities_v1.json"
    value = json.loads(path.read_text(), object_pairs_hook=_object_without_duplicates)
    if not isinstance(value, dict) or set(value) != {"schema", "capabilities"}:
        raise ValueError("invalid capability matrix fields")
    if value["schema"] != CAPABILITY_SCHEMA or not isinstance(value["capabilities"], list):
        raise ValueError("invalid capability matrix")
    result: dict[str, dict[str, Any]] = {}
    operation_devices: set[tuple[str, str, str]] = set()
    for item in value["capabilities"]:
        if not isinstance(item, dict) or set(item) != _CAPABILITY_FIELDS:
            raise ValueError("invalid capability entry fields")
        capability_id = _identifier(item["capability_id"], "capability_id")
        operation = _identifier(item["operation"], "operation")
        device = _identifier(item["device"], "device")
        policy = _identifier(
            item["required_observation_policy"], "required_observation_policy"
        )
        if device not in {"keyboard", "phone"}:
            raise ValueError("invalid capability device")
        if policy not in {
            "verify_after_each_action",
            "verify_after_each_state_change",
        }:
            raise ValueError("invalid observation policy")
        if not isinstance(item["offline_compiler_available"], bool) or not isinstance(
            item["physical_runtime_released"], bool
        ):
            raise ValueError("capability availability fields must be booleans")
        profile = item["semantic_profile_id"]
        if item["offline_compiler_available"]:
            _identifier(profile, "semantic_profile_id")
        elif profile is not None:
            raise ValueError("unavailable capability cannot name a semantic profile")
        state = item["required_device_state"]
        if state is not None:
            _identifier(state, "required_device_state")
        if capability_id in result:
            raise ValueError("duplicate capability_id")
        identity = (operation, device, capability_id)
        if identity in operation_devices:
            raise ValueError("duplicate capability identity")
        operation_devices.add(identity)
        result[capability_id] = item
    return result


def validate_mission_intent(
    value: Any, capabilities: dict[str, dict[str, Any]] | None = None
) -> None:
    if capabilities is None:
        capabilities = load_capabilities()
    if not isinstance(value, dict):
        raise ValueError("mission intent must be an object")
    decision = value.get("decision")
    if decision not in _SHAPES or set(value) != _SHAPES[decision]:
        raise ValueError("mission intent has invalid fields")
    if value["schema"] != MISSION_SCHEMA:
        raise ValueError("mission intent has invalid schema")
    _identifier(value["request_id"], "request_id")
    _identifier(value["observation_ref"], "observation_ref")
    if decision == "clarify":
        if value["reason"] not in _CLARIFY_REASONS:
            raise ValueError("invalid clarification reason")
        return

    operation = _identifier(value["operation"], "operation")
    device = _identifier(value["device"], "device")
    capability_id = _identifier(value["required_capability"], "required_capability")
    capability = capabilities.get(capability_id)
    if capability is None:
        raise ValueError("unknown required capability")
    if capability["operation"] != operation or capability["device"] != device:
        raise ValueError("capability does not match operation and device")

    if decision == "unsupported":
        if value["reason"] not in _UNSUPPORTED_REASONS:
            raise ValueError("invalid unsupported reason")
        if capability["offline_compiler_available"]:
            raise ValueError("available capability cannot be declared unsupported")
        return

    if operation != "type_text" or device not in {"keyboard", "phone"}:
        raise ValueError("unsupported executable mission operation")
    if not capability["offline_compiler_available"]:
        raise ValueError("executable mission requires an available offline compiler")
    if value["observation_policy"] != capability["required_observation_policy"]:
        raise ValueError("observation policy does not match capability")
    arguments = value["arguments"]
    if not isinstance(arguments, dict) or set(arguments) != {"text"}:
        raise ValueError("type_text arguments must contain only text")
    if not isinstance(arguments["text"], str) or not arguments["text"]:
        raise ValueError("text must be nonempty")


def validate_compilation(value: Any) -> None:
    if not isinstance(value, dict) or value.get("schema") != COMPILATION_SCHEMA:
        raise ValueError("invalid mission compilation schema")
    for key in ("request_id", "observation_ref"):
        _identifier(value.get(key), key)
    if not isinstance(value.get("mission_sha256"), str) or not _SHA256.fullmatch(
        value["mission_sha256"]
    ):
        raise ValueError("invalid mission hash")
    if value.get("status") == "accepted":
        expected = {
            "schema",
            "request_id",
            "observation_ref",
            "mission_sha256",
            "capability_id",
            "status",
            "profile_id",
            "plan_hash",
            "action_plan",
        }
        if set(value) != expected:
            raise ValueError("invalid accepted compilation fields")
        _identifier(value["capability_id"], "capability_id")
        _identifier(value["profile_id"], "profile_id")
        if not isinstance(value["plan_hash"], str) or not _SHA256.fullmatch(
            value["plan_hash"]
        ):
            raise ValueError("invalid plan hash")
        if not isinstance(value["action_plan"], dict) or value["action_plan"].get(
            "schema"
        ) != "rocell.action_plan.v1":
            raise ValueError("invalid action plan")
    elif value.get("status") == "blocked":
        expected = {
            "schema",
            "request_id",
            "observation_ref",
            "mission_sha256",
            "status",
            "reason",
        }
        if set(value) != expected or value["reason"] not in _BLOCK_REASONS:
            raise ValueError("invalid blocked compilation")
    else:
        raise ValueError("invalid compilation status")


def compile_mission_intent(
    intent: dict[str, Any], observation: dict[str, Any]
) -> dict[str, Any]:
    """Compile a validated mission through the existing read-only adapter."""

    capabilities = load_capabilities()
    validate_mission_intent(intent, capabilities)
    mission_hash = canonical_sha256(intent)
    base = {
        "schema": COMPILATION_SCHEMA,
        "request_id": intent["request_id"],
        "observation_ref": intent["observation_ref"],
        "mission_sha256": mission_hash,
    }

    def blocked(reason: str) -> dict[str, Any]:
        result = {**base, "status": "blocked", "reason": reason}
        validate_compilation(result)
        return result

    if intent["decision"] != "execute":
        return blocked(intent["reason"])
    capability = capabilities[intent["required_capability"]]
    proposal = {
        "schema": "rocell.ai_task_proposal.v0",
        "request_id": intent["request_id"],
        "observation_ref": intent["observation_ref"],
        "decision": "type_text",
        "device": intent["device"],
        "text": intent["arguments"]["text"],
    }
    inspected = inspect(proposal, observation)
    if inspected["status"] != "accepted":
        return blocked(inspected["reason"])
    if inspected["profile_id"] != capability["semantic_profile_id"]:
        return blocked("capability_mismatch")
    result = {
        **base,
        "capability_id": intent["required_capability"],
        "status": "accepted",
        "profile_id": inspected["profile_id"],
        "plan_hash": inspected["plan_hash"],
        "action_plan": inspected["action_plan"],
    }
    validate_compilation(result)
    return result
