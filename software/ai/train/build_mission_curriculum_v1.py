"""Build the frozen compiler-checked mission-intent v1 curriculum."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from rocell_ai.mission_intent import compile_mission_intent, validate_mission_intent


PAYLOADS = (
    "robot",
    "maple",
    "quiet lake",
    "call later",
    "send help",
    "phone",
    "left and right",
    "a=7",
    "test.",
    "blue sky",
    "dial tone",
    "open maps",
    "it",
    "something",
    "zero",
    "arm ready",
)
CALL_NUMBERS = ("5550102", "5550181", "2125550110", "8005550199")


def execute_target(case_id, observation_ref, device, text):
    capability = f"{device}.typing.lowercase"
    policy = (
        "verify_after_each_action"
        if device == "keyboard"
        else "verify_after_each_state_change"
    )
    return {
        "schema": "rocell.mission_intent.v1",
        "request_id": case_id,
        "observation_ref": observation_ref,
        "decision": "execute",
        "operation": "type_text",
        "device": device,
        "arguments": {"text": text},
        "required_capability": capability,
        "observation_policy": policy,
    }


def clarify_target(case_id, observation_ref, reason):
    return {
        "schema": "rocell.mission_intent.v1",
        "request_id": case_id,
        "observation_ref": observation_ref,
        "decision": "clarify",
        "reason": reason,
    }


def unsupported_target(case_id, observation_ref, operation, device, capability, reason):
    return {
        "schema": "rocell.mission_intent.v1",
        "request_id": case_id,
        "observation_ref": observation_ref,
        "decision": "unsupported",
        "operation": operation,
        "device": device,
        "required_capability": capability,
        "reason": reason,
    }


def build_records():
    records: dict[str, list[dict[str, Any]]] = {
        "train": [],
        "validation": [],
        "heldout": [],
    }
    counters: Counter[str] = Counter()

    def add(split, family, category, request, observation, target):
        index = len(records[split]) + 1
        case_id = f"mission-v1-{split[:1]}-{index:04d}"
        observation = {**observation, "ref": f"mission-v1-{split[:1]}-frame-{index:04d}"}
        target = target(case_id, observation["ref"])
        validate_mission_intent(target)
        compilation = compile_mission_intent(target, observation)
        record = {
            "id": case_id,
            "split": split,
            "family": family,
            "category": category,
            "request": request,
            "observation": observation,
            "target": target,
            "expected_compilation": {
                "status": compilation["status"],
                "reason": compilation.get("reason"),
                "plan_hash": compilation.get("plan_hash"),
                "action_count": len(compilation.get("action_plan", {}).get("actions", [])),
            },
            "review": {
                "state": "compiler_checked_simulated_review_no_human",
                "basis": "mission_runtime_validation_and_read_only_compiler",
            },
        }
        records[split].append(record)
        counters[f"{split}:{category}"] += 1

    def add_execute(split, family, category, template, device, text, observation):
        add(
            split,
            family,
            category,
            template.format(text=text),
            observation,
            lambda case_id, ref: execute_target(case_id, ref, device, text),
        )

    def add_clarify(split, family, category, request, observation, reason):
        add(
            split,
            family,
            category,
            request,
            observation,
            lambda case_id, ref: clarify_target(case_id, ref, reason),
        )

    def add_unsupported(
        split, family, category, request, observation, operation, device, capability, reason
    ):
        add(
            split,
            family,
            category,
            request,
            observation,
            lambda case_id, ref: unsupported_target(
                case_id, ref, operation, device, capability, reason
            ),
        )

    train_keyboard = (
        ("train_keyboard_type", 'Type "{text}" on the keyboard.'),
        ("train_keyboard_write", 'Please write "{text}" using the physical keyboard.'),
        ("train_keyboard_enter", 'Keyboard entry request: "{text}".'),
        ("train_keyboard_put", 'Put the exact text "{text}" into the keyboard.'),
        ("train_keyboard_selected", 'The selected keyboard text is "{text}"; enter it.'),
    )
    train_phone = (
        ("train_phone_type", 'Type "{text}" in the phone text field.'),
        ("train_phone_enter", 'On the cell phone keyboard, enter "{text}".'),
        ("train_phone_write", 'Please write "{text}" in the phone editor.'),
        ("train_phone_put", 'Put the exact text "{text}" into the phone field.'),
    )
    for family, template in train_keyboard:
        for text in PAYLOADS:
            add_execute(
                "train", family, "supported_keyboard", template, "keyboard", text, {"fresh": True}
            )
    for family, template in train_phone:
        for text in PAYLOADS:
            add_execute(
                "train",
                family,
                "supported_phone",
                template,
                "phone",
                text,
                {"fresh": True, "phone_state": "KEYBOARD_LOWER"},
            )

    for text in PAYLOADS[:8]:
        add_execute(
            "train",
            "train_literal_command_words",
            "quoted_command_word_literal",
            'Use the keyboard to type "{text}" exactly.',
            "keyboard",
            text,
            {"fresh": True},
        )
        add_execute(
            "train",
            "train_stale_semantics",
            "stale_observation",
            'Type "{text}" on the keyboard.',
            "keyboard",
            text,
            {"fresh": False},
        )
        add_execute(
            "train",
            "train_phone_state_semantics",
            "phone_state_unverified",
            'Enter "{text}" on the phone.',
            "phone",
            text,
            {"fresh": True, "phone_state": "UNKNOWN"},
        )
        add_clarify(
            "train",
            "train_missing_device",
            "device_ambiguous",
            f'Please type "{text}" in the active field.',
            {"fresh": True},
            "device_ambiguous",
        )
        add_clarify(
            "train",
            "train_payload_choice",
            "payload_ambiguous",
            f'Type "{text}" or "{PAYLOADS[-1]}" on the keyboard.',
            {"fresh": True},
            "payload_ambiguous",
        )
        add_clarify(
            "train",
            "train_compound_conflict",
            "intent_ambiguous",
            f'Type "{text}" on the keyboard and email it.',
            {"fresh": True},
            "intent_ambiguous",
        )
        add_unsupported(
            "train",
            "train_shifted_unavailable",
            "unsupported_profile",
            f'Type "{text.upper()}" on the keyboard.',
            {"fresh": True},
            "type_text",
            "keyboard",
            "keyboard.typing.shifted",
            "unsupported_by_profile",
        )
    for number in CALL_NUMBERS * 2:
        add_unsupported(
            "train",
            "train_phone_call_unavailable",
            "unavailable_operation",
            f"Call {number} from the phone.",
            {"fresh": True},
            "place_phone_call",
            "phone",
            "phone.dialer.call",
            "operation_not_available",
        )

    split_specs = {
        "validation": {
            "keyboard": 'Using the attached keyboard, key in "{text}".',
            "phone": 'In the handset editor, insert "{text}".',
            "literal": 'Transcribe "{text}" on the keyboard without interpreting it.',
            "missing_device": 'The literal is "{text}"; enter it in the current field.',
            "choice": 'For the keyboard choose between "{text}" and "{other}".',
            "compound": 'Put "{text}" on the keyboard, then publish it.',
            "shifted": 'Key in "{upper}" with the keyboard.',
            "call": 'Use this handset to dial {number}.',
            "stale": 'Using the keyboard, key in "{text}".',
            "state": 'In the handset editor, insert "{text}".',
        },
        "heldout": {
            "keyboard": 'Please make the hardware keys spell "{text}".',
            "phone": 'Add "{text}" to the mobile text box.',
            "literal": 'The symbols inside these quotes are data: "{text}". Type them on the keyboard.',
            "missing_device": 'Record "{text}" wherever the cursor is.',
            "choice": 'Should the keyboard receive "{text}" or "{other}"?',
            "compound": 'Enter "{text}" with the keyboard while sending a message.',
            "shifted": 'Make the keyboard produce "{upper}".',
            "call": 'Place a phone call to {number}.',
            "stale": 'Please make the hardware keys spell "{text}".',
            "state": 'Add "{text}" to the mobile text box.',
        },
    }
    for split, templates in split_specs.items():
        for index, text in enumerate(PAYLOADS[:8]):
            add_execute(
                split,
                f"{split}_keyboard_novel",
                "supported_keyboard",
                templates["keyboard"],
                "keyboard",
                text,
                {"fresh": True},
            )
            add_execute(
                split,
                f"{split}_phone_novel",
                "supported_phone",
                templates["phone"],
                "phone",
                text,
                {"fresh": True, "phone_state": "KEYBOARD_LOWER"},
            )
            add_execute(
                split,
                f"{split}_literal_novel",
                "quoted_command_word_literal",
                templates["literal"],
                "keyboard",
                text,
                {"fresh": True},
            )
            add_execute(
                split,
                f"{split}_stale_novel",
                "stale_observation",
                templates["stale"],
                "keyboard",
                text,
                {"fresh": False},
            )
            add_execute(
                split,
                f"{split}_state_novel",
                "phone_state_unverified",
                templates["state"],
                "phone",
                text,
                {"fresh": True, "phone_state": "UNKNOWN"},
            )
            add_clarify(
                split,
                f"{split}_device_novel",
                "device_ambiguous",
                templates["missing_device"].format(text=text),
                {"fresh": True},
                "device_ambiguous",
            )
            add_clarify(
                split,
                f"{split}_choice_novel",
                "payload_ambiguous",
                templates["choice"].format(text=text, other=PAYLOADS[-1]),
                {"fresh": True},
                "payload_ambiguous",
            )
            add_clarify(
                split,
                f"{split}_compound_novel",
                "intent_ambiguous",
                templates["compound"].format(text=text),
                {"fresh": True},
                "intent_ambiguous",
            )
            add_unsupported(
                split,
                f"{split}_shifted_novel",
                "unsupported_profile",
                templates["shifted"].format(upper=text.upper()),
                {"fresh": True},
                "type_text",
                "keyboard",
                "keyboard.typing.shifted",
                "unsupported_by_profile",
            )
            number = CALL_NUMBERS[index % len(CALL_NUMBERS)]
            add_unsupported(
                split,
                f"{split}_call_novel",
                "unavailable_operation",
                templates["call"].format(number=number),
                {"fresh": True},
                "place_phone_call",
                "phone",
                "phone.dialer.call",
                "operation_not_available",
            )
    return records, counters


def encoded(records):
    return b"".join(
        (json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
        for record in records
    )


def run():
    records, counters = build_records()
    output = AI / "data"
    payloads = {split: encoded(items) for split, items in records.items()}
    paths = {
        split: output / f"mission_curriculum_v1_{split}.jsonl" for split in records
    }
    manifest_path = output / "mission_curriculum_v1.manifest.json"
    if manifest_path.exists() or any(path.exists() for path in paths.values()):
        raise FileExistsError("existing mission curriculum v1 evidence")
    for split, path in paths.items():
        path.write_bytes(payloads[split])
    families = {
        split: sorted({record["family"] for record in items})
        for split, items in records.items()
    }
    if set(families["train"]) & set(families["validation"]):
        raise AssertionError("train and validation families overlap")
    if set(families["train"]) & set(families["heldout"]):
        raise AssertionError("train and heldout families overlap")
    if set(families["validation"]) & set(families["heldout"]):
        raise AssertionError("validation and heldout families overlap")
    manifest = {
        "schema": "rocell.mission_curriculum.v1",
        "source": "deterministic_agent_authored_compiler_checked_templates",
        "human_reviewed": False,
        "seed": None,
        "mission_schema": "rocell.mission_intent.v1",
        "capability_matrix_sha256": hashlib.sha256(
            (AI / "capabilities/mission_capabilities_v1.json").read_bytes()
        ).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "splits": {
            split: {
                "count": len(records[split]),
                "sha256": hashlib.sha256(payloads[split]).hexdigest(),
                "families": families[split],
            }
            for split in records
        },
        "category_counts": dict(sorted(counters.items())),
        "family_policy": "Template family IDs are disjoint across train, validation, and heldout. Heldout must not influence model, prompt, decoder, or gate changes.",
        "review_state": "compiler_checked_simulated_review_no_human",
        "hardware_writes": 0,
        "physical_movements": 0,
        "limitations": [
            "Agent-authored templated English without independent human labels.",
            "Compiler checks semantic support and order, not physical success.",
            "Only current mission v1 operations and capabilities are represented.",
            "No camera, coordinate, trajectory, controller, or outcome evidence.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"splits": manifest["splits"], "category_counts": manifest["category_counts"]}, indent=2))


if __name__ == "__main__":
    run()
