"""Read-only compatibility adapter to RoCell's semantic text compilers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import string
from typing import Any

from rocell.typing import PhoneStateError, UnsupportedCharacterError, compile_development_text

from .contract import validate_proposal, validate_result


_DESKTOP_SHIFTED_CHARACTERS = frozenset(
    string.ascii_uppercase + '~!@#$%^&*()_+{}|:"<>?'
)
_PHONE_LAYERED_CHARACTERS = frozenset(
    string.ascii_uppercase + string.digits + string.punctuation
)


def planner_capability_contract(
    *,
    keyboard_target_ids: tuple[str, ...] = (),
    sticky_keys_verified: bool = False,
    phone_target_ids: tuple[str, ...] = (),
    adb_layer_verification: bool = False,
) -> dict[str, Any]:
    """Describe the commissioned prerequisites for sequential shifted input.

    This is a capability audit, not a target map or execution permit.  The
    language model never supplies these target identities or capability facts.
    """

    keyboard_targets = frozenset(keyboard_target_ids)
    phone_targets = frozenset(phone_target_ids)
    keyboard_ready = "SHIFT" in keyboard_targets and sticky_keys_verified is True
    required_phone_targets = frozenset({"key_shift", "key_symbols", "key_letters"})
    phone_ready = required_phone_targets <= phone_targets and adb_layer_verification is True
    core: dict[str, Any] = {
        "schema": "rocell.ai_planner_capability_contract.v1",
        "keyboard": {
            "strategy": "STICKY_KEYS_SEQUENTIAL_MODIFIER",
            "simultaneous_chord_supported": False,
            "caps_lock_optimization_enabled": False,
            "required_target_ids": ["SHIFT"],
            "sticky_keys_commissioning_evidence_required": True,
            "ready": keyboard_ready,
            "blocked_reason": None if keyboard_ready else "keyboard_modifier_uncommissioned",
        },
        "phone": {
            "strategy": "VERIFIED_LAYER_STATE_MACHINE",
            "states": ["KEYBOARD_LOWER", "KEYBOARD_UPPER", "SYMBOLS_1"],
            "required_transition_target_ids": sorted(required_phone_targets),
            "adb_verification_before_every_press": True,
            "ready": phone_ready,
            "blocked_reason": None if phone_ready else "phone_layer_uncommissioned",
        },
        "language_model_may_emit_target_ids": False,
        "coordinates_present": False,
        "hardware_commands_generated": 0,
        "physical_authority": False,
    }
    encoded = json.dumps(
        core, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return {**core, "contract_sha256": hashlib.sha256(encoded).hexdigest()}


def build_planner_capability_audit(
    target_catalog_path: Path, source_commit: str
) -> dict[str, Any]:
    """Audit the current nominal catalog against the frozen capability contract."""

    source = json.loads(target_catalog_path.read_text(encoding="utf-8"))

    def target_ids(section: dict[str, Any]) -> tuple[str, ...]:
        values: list[str] = []
        for row in section["rows"]:
            values.extend(row.get("key_ids", row.get("target_ids", ())))
        values.extend(section["explicit_targets"])
        return tuple(values)

    keyboard_ids = target_ids(source["keyboard"])
    phone_ids = target_ids(source["phone"])
    core: dict[str, Any] = {
        "schema": "rocell.ai_planner_capability_audit.v1",
        "source_commit": source_commit,
        "target_catalog_file": target_catalog_path.as_posix(),
        "target_catalog_file_sha256": hashlib.sha256(
            target_catalog_path.read_bytes()
        ).hexdigest(),
        "contract": planner_capability_contract(
            keyboard_target_ids=keyboard_ids,
            sticky_keys_verified=False,
            phone_target_ids=phone_ids,
            adb_layer_verification=False,
        ),
        "keyboard_target_count": len(keyboard_ids),
        "phone_target_count": len(phone_ids),
        "hardware_writes": 0,
        "physical_movements": 0,
        "physical_authority": False,
    }
    encoded = json.dumps(
        core, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return {**core, "audit_sha256": hashlib.sha256(encoded).hexdigest()}


def inspect(proposal: dict[str, str], observation: dict[str, Any]) -> dict[str, Any]:
    """Compile a supported proposal without camera, controller, or arm access."""

    validate_proposal(proposal)
    if not isinstance(observation, dict) or observation.get("ref") != proposal["observation_ref"]:
        raise ValueError("observation reference mismatch")

    base = {
        "schema": "rocell.ai_plan_result.v0",
        "request_id": proposal["request_id"],
        "observation_ref": proposal["observation_ref"],
    }

    def blocked(reason: str) -> dict[str, Any]:
        result = {**base, "status": "blocked", "reason": reason}
        validate_result(result)
        return result

    if observation.get("fresh") is not True:
        return blocked("stale_observation")
    if proposal["decision"] != "type_text":
        return blocked(proposal["reason"])
    if proposal["device"] == "phone" and observation.get("phone_state") != "KEYBOARD_LOWER":
        return blocked("phone_state_unverified")
    if proposal["device"] == "keyboard" and any(
        character in _DESKTOP_SHIFTED_CHARACTERS for character in proposal["text"]
    ):
        return blocked("keyboard_modifier_uncommissioned")
    if proposal["device"] == "phone" and any(
        character in _PHONE_LAYERED_CHARACTERS
        and character not in {".", "\n"}
        for character in proposal["text"]
    ):
        return blocked("phone_layer_uncommissioned")
    try:
        plan = compile_development_text(proposal["device"], proposal["text"])
    except UnsupportedCharacterError:
        return blocked("unsupported_by_profile")
    except PhoneStateError:
        return blocked("phone_state_unverified")
    result = {
        **base,
        "status": "accepted",
        "profile_id": plan.profile_id,
        "plan_hash": plan.plan_hash,
        "action_plan": plan.to_dict(),
    }
    validate_result(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-catalog", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_planner_capability_audit(args.target_catalog, args.source_commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
