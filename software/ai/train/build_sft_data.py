"""Create a deterministic, synthetic, compiler-checked SFT pilot dataset."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import re
import sys


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(AI_DIR.parent / "src"))

from rocell_ai.adapter import inspect  # noqa: E402
from rocell_ai.contract import validate_proposal  # noqa: E402
from rocell_ai import SCHEMA_ID  # noqa: E402
from rocell.typing import UnsupportedCharacterError, compile_development_text  # noqa: E402


SEED = 2109
WORDS = (
    "cedar", "amber", "river", "quiet", "stone", "paper", "orbit", "garden",
    "copper", "silver", "pencil", "forest", "window", "bright", "little",
    "north", "south", "table", "circle", "planet", "music", "flower",
    "market", "water", "yellow", "purple", "simple", "future",
    "button", "letter", "summer", "winter", "morning", "evening", "light",
)


def signature(request: str) -> str:
    text = re.sub(r'"[^"]*"', '"<text>"', request.casefold())
    text = re.sub(r"\d+", "<num>", text)
    return " ".join(text.split())


def _benchmark_requests() -> tuple[set[str], set[str], dict[str, str]]:
    exact: set[str] = set()
    signatures: set[str] = set()
    digests: dict[str, str] = {}
    for version in ("v0", "v1", "v2"):
        path = AI_DIR / "eval" / f"benchmark_{version}.jsonl"
        digests[version] = hashlib.sha256(path.read_bytes()).hexdigest()
        for line in path.read_text(encoding="utf-8").splitlines():
            request = json.loads(line)["request"]
            exact.add(request.casefold().strip())
            signatures.add(signature(request))
    return exact, signatures, digests


def build() -> tuple[list[dict], list[dict], dict]:
    rng = random.Random(SEED)
    records: list[dict] = []

    def add(family: str, request: str, observation: dict, target: dict) -> None:
        case_id = f"synthetic-{len(records):04d}"
        proposal = {
            "schema": SCHEMA_ID,
            "request_id": case_id,
            "observation_ref": observation["ref"],
            **target,
        }
        validate_proposal(proposal)
        outcome = inspect(proposal, observation)
        if (outcome["status"] == "accepted") != (target["decision"] == "type_text"):
            raise ValueError(f"compiler/label dispute in {case_id}")
        if family in {"keyboard_profile_reject", "phone_profile_reject"}:
            device = "keyboard" if family.startswith("keyboard") else "phone"
            payload = request.split('"')[1]
            try:
                compile_development_text(device, payload)
            except UnsupportedCharacterError:
                pass
            else:
                raise ValueError(f"profile rejection label accepted by compiler in {case_id}")
        records.append({"id": case_id, "family": family, "request": request, "observation": observation, "target": target})

    word_index = 0

    def words() -> str:
        nonlocal word_index
        pair = f"{WORDS[(word_index // len(WORDS)) % len(WORDS)]} {WORDS[word_index % len(WORDS)]}"
        word_index += 1
        return pair

    for i in range(72):
        payload = words() if i % 3 else f"{rng.choice(WORDS)} {100 + i}"
        request = f'Keyboard entry request, literal payload: "{payload}".'
        add("keyboard_literal", request, {"ref": f"sft-k-{i}", "fresh": True},
            {"decision": "type_text", "device": "keyboard", "text": payload})
    for i in range(72):
        payload = words() if i % 4 else f"{WORDS[i // 4]}."
        request = f'Phone editor entry request, literal payload: "{payload}".'
        add("phone_literal", request, {"ref": f"sft-p-{i}", "fresh": True, "phone_state": "KEYBOARD_LOWER"},
            {"decision": "type_text", "device": "phone", "text": payload})
    for i in range(18):
        payload = WORDS[i].upper()
        request = f'Keyboard entry request, literal payload: "{payload}".'
        add("keyboard_profile_reject", request, {"ref": f"sft-ku-{i}", "fresh": True},
            {"decision": "unsupported", "reason": "unsupported_by_profile"})
    for i in range(18):
        payload = str(rng.randrange(100, 9999))
        request = f'Phone editor entry request, literal payload: "{payload}".'
        add("phone_profile_reject", request, {"ref": f"sft-pu-{i}", "fresh": True, "phone_state": "KEYBOARD_LOWER"},
            {"decision": "unsupported", "reason": "unsupported_by_profile"})
    for i in range(24):
        request = f"Outbound phone call request, destination {rng.randrange(200, 999)}-{rng.randrange(1000, 9999)}."
        add("operation_unavailable", request, {"ref": f"sft-op-{i}", "fresh": True},
            {"decision": "unsupported", "reason": "operation_not_available"})
    for i in range(24):
        request = f'Keyboard entry request, literal payload: "{words()}".'
        add("stale_observation", request, {"ref": f"sft-stale-{i}", "fresh": False},
            {"decision": "unsupported", "reason": "stale_observation"})
    for i in range(24):
        request = f'Phone editor entry request, literal payload: "{words()}".'
        add("phone_state_unknown", request, {"ref": f"sft-unknown-{i}", "fresh": True, "phone_state": "UNKNOWN"},
            {"decision": "unsupported", "reason": "phone_state_unverified"})
    for i in range(16):
        request = f'Literal payload for an unspecified input surface: "{words()}".'
        add("device_missing", request, {"ref": f"sft-cd-{i}", "fresh": True},
            {"decision": "clarify", "reason": "device_ambiguous"})
    for i in range(16):
        request = f"Keyboard entry request, payload omitted in ticket {1000 + i}."
        add("text_missing", request, {"ref": f"sft-ct-{i}", "fresh": True},
            {"decision": "clarify", "reason": "text_ambiguous"})
    for i in range(16):
        request = f"Phone task request {1000 + i}: take care of the screen."
        add("intent_missing", request, {"ref": f"sft-ci-{i}", "fresh": True, "phone_state": "KEYBOARD_LOWER"},
            {"decision": "clarify", "reason": "intent_ambiguous"})

    exact, signatures, benchmark_hashes = _benchmark_requests()
    seen: set[str] = set()
    for row in records:
        normalized = row["request"].casefold().strip()
        if normalized in exact or normalized in seen or signature(row["request"]) in signatures:
            raise ValueError(f"benchmark overlap or duplicate synthetic request: {row['id']}")
        seen.add(normalized)
    rng.shuffle(records)
    valid_ids = {row["id"] for row in records[:36]}
    train = [row for row in records if row["id"] not in valid_ids]
    valid = [row for row in records if row["id"] in valid_ids]
    manifest = {
        "schema": "rocell.ai_synthetic_sft_data.v0",
        "seed": SEED,
        "source": "agent_authored_templates_compiler_checked",
        "human_reviewed": False,
        "limitations": "Exact and template-signature overlap is checked; semantic paraphrase leakage is not automatically provable.",
        "benchmark_sha256": benchmark_hashes,
        "counts": {"train": len(train), "validation": len(valid), "families": dict(sorted(Counter(row["family"] for row in records).items()))},
    }
    return train, valid, manifest


def main() -> None:
    train, valid, manifest = build()
    folder = AI_DIR / "data"
    for name, rows in (("train", train), ("validation", valid)):
        path = folder / f"synthetic_sft_v0_{name}.jsonl"
        raw = ("\n".join(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows) + "\n").encode("utf-8")
        path.write_bytes(raw)
        manifest[f"{name}_sha256"] = hashlib.sha256(raw).hexdigest()
    (folder / "synthetic_sft_v0.manifest.json").write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
