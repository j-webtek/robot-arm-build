"""Simulated review of benchmark labels against RoCell's actual capabilities.

This cross-check is deliberately independent of the English baseline parser.
It verifies declared semantic facts and provenance, but cannot replace a
person's judgment about every natural-language interpretation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from rocell.typing import UnsupportedCharacterError, compile_development_text

from .evaluation import load_benchmark


_BASIS_TO_EXPECTED = {
    "compiler_accepts": ("type_text", None),
    "compiler_rejects": ("unsupported", "unsupported_by_profile"),
    "operation_not_available": ("unsupported", "operation_not_available"),
    "stale_observation": ("unsupported", "stale_observation"),
    "phone_state_unverified": ("unsupported", "phone_state_unverified"),
    "device_ambiguous": ("clarify", "device_ambiguous"),
    "text_ambiguous": ("clarify", "text_ambiguous"),
    "intent_ambiguous": ("clarify", "intent_ambiguous"),
}
_UNAVAILABLE_OPERATIONS = {"dial", "call", "send", "open_app"}


def review_benchmark(cases_path: Path, manifest_path: Path, prior_cases_path: Path | list[Path]) -> dict[str, Any]:
    cases, digest = load_benchmark(cases_path, manifest_path)
    prior_paths = [prior_cases_path] if isinstance(prior_cases_path, Path) else prior_cases_path
    prior = {row["request"].strip().casefold() for path in prior_paths for row in _read_cases(path)}
    issues: list[dict[str, str]] = []
    seen: set[str] = set()
    for case in cases:
        case_id = case["case_id"]
        request = case["request"]
        normalized = request.strip().casefold()
        if normalized in seen or normalized in prior:
            issues.append({"case_id": case_id, "issue": "duplicate_or_prior_request"})
        seen.add(normalized)
        review = case.get("review")
        if not isinstance(review, dict) or review.get("basis") not in _BASIS_TO_EXPECTED:
            issues.append({"case_id": case_id, "issue": "missing_or_invalid_review_basis"})
            continue
        if not isinstance(review.get("rationale"), str) or not review["rationale"].strip():
            issues.append({"case_id": case_id, "issue": "missing_rationale"})
        basis = review["basis"]
        decision, reason = _BASIS_TO_EXPECTED[basis]
        expected = case["expected"]
        if expected.get("decision") != decision or (reason is not None and expected.get("reason") != reason):
            issues.append({"case_id": case_id, "issue": "label_basis_mismatch"})

        observation = case["observation"]
        if basis == "stale_observation":
            if observation.get("fresh") is not False:
                issues.append({"case_id": case_id, "issue": "observation_not_stale"})
        elif observation.get("fresh") is not True:
            issues.append({"case_id": case_id, "issue": "unexpected_stale_observation"})
        if basis == "phone_state_unverified" and observation.get("phone_state") == "KEYBOARD_LOWER":
            issues.append({"case_id": case_id, "issue": "phone_state_is_verified"})
        if basis == "operation_not_available" and review.get("operation") not in _UNAVAILABLE_OPERATIONS:
            issues.append({"case_id": case_id, "issue": "unknown_unavailable_operation"})

        if basis in {"compiler_accepts", "compiler_rejects"}:
            device, text = review.get("device"), review.get("text")
            if device not in {"keyboard", "phone"} or not isinstance(text, str) or not text:
                issues.append({"case_id": case_id, "issue": "missing_compiler_inputs"})
                continue
            if basis == "compiler_accepts" and (expected.get("device"), expected.get("text")) != (device, text):
                issues.append({"case_id": case_id, "issue": "expected_text_or_device_mismatch"})
            if device == "phone" and observation.get("phone_state") != "KEYBOARD_LOWER":
                issues.append({"case_id": case_id, "issue": "phone_state_not_ready"})
            try:
                plan = compile_development_text(device, text)
            except UnsupportedCharacterError:
                accepted = False
            else:
                accepted = bool(plan.actions)
            if accepted != (basis == "compiler_accepts"):
                issues.append({"case_id": case_id, "issue": "compiler_verdict_mismatch"})

    return {
        "schema": "rocell.ai_simulated_review.v0",
        "benchmark_sha256": digest,
        "review_type": "independent_semantic_crosscheck",
        "human_reviewed": False,
        "prior_sets": [
            {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in prior_paths
        ],
        "case_count": len(cases),
        "passed": len(cases) - len({issue["case_id"] for issue in issues}),
        "issues": issues,
        "limitations": "English interpretations and coverage are agent-authored; compiler and state checks are automated, not human approval or physical evidence.",
    }


def _read_cases(path: Path) -> list[dict[str, Any]]:
    import json

    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
