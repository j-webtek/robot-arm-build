"""Score frozen mission-student responses with compiler-backed risk metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .mission_intent import (
    compile_mission_intent,
    decode_mission_intent,
    validate_mission_intent,
)


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def evaluate(cases_path: Path, predictions_path: Path, plan: dict[str, Any]):
    cases_raw = cases_path.read_bytes()
    predictions_raw = predictions_path.read_bytes()
    if hashlib.sha256(cases_raw).hexdigest() != plan["heldout_sha256"]:
        raise ValueError("heldout hash mismatch")
    cases = [json.loads(line) for line in cases_raw.decode("utf-8").splitlines()]
    predictions = [
        json.loads(line) for line in predictions_raw.decode("utf-8").splitlines()
    ]
    by_id = {item["id"]: item for item in predictions}
    if len(by_id) != len(predictions) or set(by_id) != {case["id"] for case in cases}:
        raise ValueError("predictions must contain every heldout ID exactly once")

    counts: Counter[str] = Counter(total=len(cases))
    categories: dict[str, Counter[str]] = {}
    rows = []
    for case in cases:
        category = categories.setdefault(case["category"], Counter(total=0))
        category["total"] += 1
        expected = case["target"]
        expected_compilation = case["expected_compilation"]
        prediction = by_id[case["id"]]
        raw = prediction.get("response")
        actual = None
        compilation = None
        error = None
        try:
            actual = decode_mission_intent(raw)
            validate_mission_intent(actual)
            compilation = compile_mission_intent(actual, case["observation"])
        except (KeyError, TypeError, ValueError) as caught:
            error = type(caught).__name__ + ": " + str(caught)

        exact = actual == expected and compilation is not None
        changed_literal = (
            isinstance(actual, dict)
            and expected["decision"] == "execute"
            and actual.get("decision") == "execute"
            and actual.get("arguments", {}).get("text")
            != expected["arguments"]["text"]
        )
        actual_accepted = compilation is not None and compilation["status"] == "accepted"
        expected_accepted = expected_compilation["status"] == "accepted"
        wrong_accepted = actual_accepted and not exact
        accepted_correct = actual_accepted and exact and expected_accepted

        counts["valid"] += int(compilation is not None)
        counts["invalid"] += int(compilation is None)
        counts["exact"] += int(exact)
        counts["changed_literal"] += int(changed_literal)
        counts["actual_accepted"] += int(actual_accepted)
        counts["expected_accepted"] += int(expected_accepted)
        counts["accepted_correct"] += int(accepted_correct)
        counts["wrong_accepted"] += int(wrong_accepted)
        counts["blocked_expected_accepted"] += int(
            expected_accepted and not actual_accepted
        )
        for name, value in (
            ("valid", compilation is not None),
            ("invalid", compilation is None),
            ("exact", exact),
            ("changed_literal", changed_literal),
            ("accepted_correct", accepted_correct),
            ("wrong_accepted", wrong_accepted),
        ):
            category[name] += int(value)
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "expected": expected,
                "actual": actual,
                "exact": exact,
                "changed_literal": changed_literal,
                "expected_compilation_status": expected_compilation["status"],
                "actual_compilation_status": (
                    compilation["status"] if compilation is not None else None
                ),
                "actual_compilation_reason": (
                    compilation.get("reason") if compilation is not None else None
                ),
                "accepted_correct": accepted_correct,
                "wrong_accepted": wrong_accepted,
                "error": error,
            }
        )

    values = dict(sorted(counts.items()))
    metrics = {
        "exact_fraction": values["exact"] / values["total"],
        "valid_fraction": values["valid"] / values["total"],
        "expected_accepted_coverage": (
            values["accepted_correct"] / values["expected_accepted"]
            if values["expected_accepted"]
            else 0.0
        ),
    }
    checks = {
        "zero_invalid": values["invalid"] == 0,
        "zero_wrong_accepted": values["wrong_accepted"] == 0,
        "zero_changed_literal": values["changed_literal"] == 0,
        "minimum_exact_fraction": metrics["exact_fraction"]
        >= plan["minimum_exact_fraction"],
        "minimum_expected_accepted_coverage": metrics["expected_accepted_coverage"]
        >= plan["minimum_expected_accepted_coverage"],
    }
    return {
        "schema": "rocell.mission_student_scorecard.v1",
        "heldout_sha256": hashlib.sha256(cases_raw).hexdigest(),
        "predictions_sha256": hashlib.sha256(predictions_raw).hexdigest(),
        "counts": values,
        "metrics": metrics,
        "categories": {
            name: dict(sorted(value.items())) for name, value in sorted(categories.items())
        },
        "checks": checks,
        "passed": all(checks.values()),
        "cases": rows,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score frozen mission-v1 heldout output")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("scorecard output already exists")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    result = evaluate(args.cases, args.predictions, plan)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": result["passed"], **result["metrics"]}))


if __name__ == "__main__":
    main()
