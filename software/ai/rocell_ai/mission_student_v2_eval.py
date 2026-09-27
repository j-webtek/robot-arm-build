"""Compiler-backed scoring for frozen mission student v2 splits."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .mission_intent import compile_mission_intent, decode_mission_intent, validate_mission_intent


def evaluate(
    cases_path: Path,
    predictions_path: Path,
    plan: dict[str, Any],
    expected_cases_sha256: str,
    split: str,
) -> dict[str, Any]:
    cases_raw = cases_path.read_bytes()
    predictions_raw = predictions_path.read_bytes()
    cases_sha256 = hashlib.sha256(cases_raw).hexdigest()
    if cases_sha256 != expected_cases_sha256:
        raise ValueError("case hash mismatch")
    cases = [json.loads(line) for line in cases_raw.decode("utf-8").splitlines()]
    predictions = [json.loads(line) for line in predictions_raw.decode("utf-8").splitlines()]
    by_id = {item["id"]: item for item in predictions}
    if len(by_id) != len(predictions) or set(by_id) != {case["id"] for case in cases}:
        raise ValueError("predictions must contain every case ID exactly once")
    identities = {(item.get("model"), item.get("model_digest")) for item in predictions}
    if len(identities) != 1:
        raise ValueError("predictions must bind one model tag and digest")
    model, model_digest = identities.pop()
    if not isinstance(model, str) or not isinstance(model_digest, str):
        raise ValueError("prediction model identity is missing")

    counts: Counter[str] = Counter(total=len(cases))
    categories: dict[str, Counter[str]] = {}
    rows = []
    for case in cases:
        category = categories.setdefault(case["category"], Counter(total=0))
        category["total"] += 1
        expected = case["target"]
        prediction = by_id[case["id"]]
        actual = None
        compilation = None
        error = None
        try:
            actual = decode_mission_intent(prediction.get("response"))
            validate_mission_intent(actual)
            compilation = compile_mission_intent(actual, case["observation"])
        except (KeyError, TypeError, ValueError) as caught:
            error = type(caught).__name__ + ": " + str(caught)
        exact = actual == expected and compilation is not None
        changed_literal = (
            isinstance(actual, dict)
            and expected["decision"] == "execute"
            and actual.get("decision") == "execute"
            and actual.get("arguments", {}).get("text") != expected["arguments"]["text"]
        )
        actual_accepted = compilation is not None and compilation["status"] == "accepted"
        expected_accepted = case["expected_compilation"]["status"] == "accepted"
        wrong_accepted = actual_accepted and not exact
        accepted_correct = actual_accepted and exact and expected_accepted
        values = {
            "valid": compilation is not None,
            "invalid": compilation is None,
            "exact": exact,
            "changed_literal": changed_literal,
            "actual_accepted": actual_accepted,
            "expected_accepted": expected_accepted,
            "accepted_correct": accepted_correct,
            "wrong_accepted": wrong_accepted,
            "blocked_expected_accepted": expected_accepted and not actual_accepted,
        }
        for name, value in values.items():
            counts[name] += int(value)
            category[name] += int(value)
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "expected": expected,
                "actual": actual,
                "exact": exact,
                "changed_literal": changed_literal,
                "expected_compilation_status": case["expected_compilation"]["status"],
                "actual_compilation_status": compilation["status"] if compilation else None,
                "actual_compilation_reason": compilation.get("reason") if compilation else None,
                "accepted_correct": accepted_correct,
                "wrong_accepted": wrong_accepted,
                "error": error,
            }
        )
    values = dict(sorted(counts.items()))
    category_values = {
        name: dict(sorted(value.items())) for name, value in sorted(categories.items())
    }
    category_exact_fractions = {
        name: value["exact"] / value["total"] for name, value in category_values.items()
    }
    metrics = {
        "exact_fraction": values["exact"] / values["total"],
        "valid_fraction": values["valid"] / values["total"],
        "expected_accepted_coverage": (
            values["accepted_correct"] / values["expected_accepted"]
            if values["expected_accepted"] else 0.0
        ),
        "minimum_category_exact_fraction": min(category_exact_fractions.values()),
    }
    checks = {
        "zero_invalid": values["invalid"] == 0,
        "zero_wrong_accepted": values["wrong_accepted"] == 0,
        "zero_changed_literal": values["changed_literal"] == 0,
        "minimum_exact_fraction": metrics["exact_fraction"] >= plan["minimum_exact_fraction"],
        "minimum_expected_accepted_coverage": metrics["expected_accepted_coverage"] >= plan["minimum_expected_accepted_coverage"],
        "minimum_per_category_exact_fraction": metrics["minimum_category_exact_fraction"] >= plan["minimum_per_category_exact_fraction"],
    }
    return {
        "schema": "rocell.mission_student_scorecard.v2",
        "split": split,
        "model": model,
        "model_digest": model_digest,
        "cases_sha256": cases_sha256,
        "predictions_sha256": hashlib.sha256(predictions_raw).hexdigest(),
        "counts": values,
        "metrics": metrics,
        "category_exact_fractions": category_exact_fractions,
        "categories": category_values,
        "checks": checks,
        "passed": all(checks.values()),
        "cases": rows,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score one manifest-bound mission split")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("scorecard output already exists")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    expected = manifest.get("splits", {}).get(args.split, {}).get("sha256")
    if not isinstance(expected, str):
        raise ValueError("manifest does not define requested split")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    result = evaluate(args.cases, args.predictions, plan, expected, args.split)
    args.output.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], **result["metrics"]}, sort_keys=True))


if __name__ == "__main__":
    main()
