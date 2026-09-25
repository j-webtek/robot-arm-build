"""Build a second synthetic SFT set with varied, compiler-checked requests."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sys


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(AI_DIR.parent / "src"))

from rocell_ai import SCHEMA_ID  # noqa: E402
from rocell_ai.adapter import inspect  # noqa: E402
from rocell_ai.contract import validate_proposal  # noqa: E402
from build_sft_data import signature, WORDS  # noqa: E402


SEED = 2110
VERSIONS = ("v0", "v1", "v2", "v3", "v4", "v5")


def _prior_data() -> tuple[list[dict], str]:
    folder = AI_DIR / "data"
    manifest_path = folder / "synthetic_sft_v0.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for split in ("train", "validation"):
        raw = (folder / f"synthetic_sft_v0_{split}.jsonl").read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest[f"{split}_sha256"]:
            raise ValueError("v0 data hash mismatch")
        rows.extend(json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip())
    return rows, hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def build() -> tuple[list[dict], list[dict], dict]:
    rng = random.Random(SEED)
    records, prior_manifest_hash = _prior_data()
    records = [{**row, "id": "v1-" + row["id"], "family": "v0_" + row["family"]} for row in records]

    def add(family: str, request: str, observation: dict, target: dict) -> None:
        case_id = f"v1-synthetic-{len(records):04d}"
        proposal = {"schema": SCHEMA_ID, "request_id": case_id,
                    "observation_ref": observation["ref"], **target}
        validate_proposal(proposal)
        outcome = inspect(proposal, observation)
        if (outcome["status"] == "accepted") != (target["decision"] == "type_text"):
            raise ValueError(f"compiler/label dispute: {case_id}")
        records.append({"id": case_id, "family": family, "request": request,
                        "observation": observation, "target": target})

    keyboard_templates = (
        'Please enter "{text}" with the physical keyboard.',
        'Use the keyboard to write "{text}" into the focused field.',
        'I want the keyboard to type "{text}".',
        'Write "{text}" by pressing keys on the keyboard.',
        'For keyboard input, type exactly "{text}".',
        'The keyboard should type this literal string: "{text}".',
    )
    phone_templates = (
        'Please type "{text}" into the mobile phone editor.',
        'Using the phone on-screen keyboard, enter "{text}".',
        'I want the phone to type "{text}" in its ready text field.',
        'Write "{text}" into the cell phone input field.',
        'For phone text input, type exactly "{text}".',
        'The phone keyboard should enter this literal string: "{text}".',
    )
    for i in range(90):
        text = f"{WORDS[i % len(WORDS)]} {WORDS[(i * 7 + 3) % len(WORDS)]}"
        if i % 5 == 0:
            text = f"{WORDS[i % len(WORDS)]} {200 + i}"
        add("keyboard_paraphrase", keyboard_templates[i % len(keyboard_templates)].format(text=text),
            {"ref": f"v1-k-{i}", "fresh": True},
            {"decision": "type_text", "device": "keyboard", "text": text})
        phone_text = f"{WORDS[(i * 3 + 1) % len(WORDS)]} {WORDS[(i * 11 + 2) % len(WORDS)]}"
        if i % 5 == 0:
            phone_text = WORDS[i % len(WORDS)] + "."
        add("phone_paraphrase", phone_templates[i % len(phone_templates)].format(text=phone_text),
            {"ref": f"v1-p-{i}", "fresh": True, "phone_state": "KEYBOARD_LOWER"},
            {"decision": "type_text", "device": "phone", "text": phone_text})

    for i in range(20):
        upper = WORDS[i].upper()
        add("keyboard_profile_reject", f'Please enter "{upper}" with the physical keyboard.',
            {"ref": f"v1-ku-{i}", "fresh": True},
            {"decision": "unsupported", "reason": "unsupported_by_profile"})
        digits = str(300 + i)
        add("phone_profile_reject", f'Using the phone on-screen keyboard, enter "{digits}".',
            {"ref": f"v1-pu-{i}", "fresh": True, "phone_state": "KEYBOARD_LOWER"},
            {"decision": "unsupported", "reason": "unsupported_by_profile"})
        add("multi_step_unavailable", f'After typing "{WORDS[i]}" with the physical keyboard, place a phone call to {500 + i}-{2000 + i}.',
            {"ref": f"v1-op-{i}", "fresh": True},
            {"decision": "unsupported", "reason": "operation_not_available"})
        add("device_missing", f'Please write "{WORDS[i]}" into the selected input field.',
            {"ref": f"v1-cd-{i}", "fresh": True},
            {"decision": "clarify", "reason": "device_ambiguous"})
        add("text_missing", f'Please put that earlier text on the keyboard, ticket {3000 + i}.',
            {"ref": f"v1-ct-{i}", "fresh": True},
            {"decision": "clarify", "reason": "text_ambiguous"})

    for i in range(15):
        add("ambiguous_choice", f'For the keyboard, choose between "{WORDS[i]}" and "{WORDS[i + 1]}" to type.',
            {"ref": f"v1-ca-{i}", "fresh": True},
            {"decision": "clarify", "reason": "text_ambiguous"})
        add("ambiguous_two_devices", f'Please type "{WORDS[i]}" on both the keyboard and the phone.',
            {"ref": f"v1-cb-{i}", "fresh": True, "phone_state": "KEYBOARD_LOWER"},
            {"decision": "clarify", "reason": "device_ambiguous"})
        add("intent_missing", f'Please handle the phone screen for task {4000 + i}.',
            {"ref": f"v1-ci-{i}", "fresh": True, "phone_state": "KEYBOARD_LOWER"},
            {"decision": "clarify", "reason": "intent_ambiguous"})

    for i in range(10):
        add("call_unavailable", f'Place a phone call to {600 + i}-{3000 + i}.',
            {"ref": f"v1-call-{i}", "fresh": True},
            {"decision": "unsupported", "reason": "operation_not_available"})
        add("app_unavailable", f'Open the {WORDS[i]} app on the phone.',
            {"ref": f"v1-app-{i}", "fresh": True},
            {"decision": "unsupported", "reason": "operation_not_available"})
        add("stale_observation", f'Please type "{WORDS[i]}" into the mobile phone editor.',
            {"ref": f"v1-stale-{i}", "fresh": False, "phone_state": "KEYBOARD_LOWER"},
            {"decision": "unsupported", "reason": "stale_observation"})
        add("phone_state_unknown", f'Using the phone on-screen keyboard, enter "{WORDS[i]}".',
            {"ref": f"v1-unknown-{i}", "fresh": True, "phone_state": "UNKNOWN"},
            {"decision": "unsupported", "reason": "phone_state_unverified"})

    benchmark_hashes: dict[str, str] = {}
    benchmark_exact: set[str] = set()
    benchmark_signatures: set[str] = set()
    for version in VERSIONS:
        raw = (AI_DIR / "eval" / f"benchmark_{version}.jsonl").read_bytes()
        benchmark_hashes[version] = hashlib.sha256(raw).hexdigest()
        for line in raw.decode("utf-8").splitlines():
            request = json.loads(line)["request"]
            benchmark_exact.add(request.casefold().strip())
            benchmark_signatures.add(signature(request))
    seen: set[str] = set()
    for row in records:
        normalized = row["request"].casefold().strip()
        if normalized in seen or normalized in benchmark_exact or signature(row["request"]) in benchmark_signatures:
            raise ValueError(f"benchmark overlap or duplicate synthetic request: {row['id']}")
        seen.add(normalized)
    rng.shuffle(records)
    validation_ids = {row["id"] for row in records[:60]}
    train = [row for row in records if row["id"] not in validation_ids]
    validation = [row for row in records if row["id"] in validation_ids]
    manifest = {
        "schema": "rocell.ai_synthetic_sft_data.v1", "seed": SEED,
        "source": "agent_authored_paraphrase_templates_compiler_checked",
        "human_reviewed": False, "prior_data_manifest_sha256": prior_manifest_hash,
        "limitations": "Exact and normalized signature overlap checks cannot prove semantic independence; validation shares request families with training.",
        "benchmark_sha256": benchmark_hashes,
        "counts": {"train": len(train), "validation": len(validation),
                   "families": dict(sorted(Counter(row["family"] for row in records).items()))},
    }
    return train, validation, manifest


def main() -> None:
    train, validation, manifest = build()
    folder = AI_DIR / "data"
    for split, rows in (("train", train), ("validation", validation)):
        raw = ("\n".join(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows) + "\n").encode("utf-8")
        (folder / f"synthetic_sft_v1_{split}.jsonl").write_bytes(raw)
        manifest[f"{split}_sha256"] = hashlib.sha256(raw).hexdigest()
    (folder / "synthetic_sft_v1.manifest.json").write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
