"""Replay a frozen model scorecard through the request-grounding gate."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from . import SCHEMA_ID
from .admission import admit
from .evaluation import load_benchmark


POLICY_SHA256 = hashlib.sha256((Path(__file__).with_name("admission.py")).read_bytes()).hexdigest()


def evaluate_admission(cases_path: Path, manifest_path: Path, raw_scorecard_path: Path) -> dict[str, Any]:
    cases, benchmark_digest = load_benchmark(cases_path, manifest_path)
    raw_bytes = raw_scorecard_path.read_bytes()
    raw_score = json.loads(raw_bytes)
    if raw_score.get("schema") != "rocell.ai_model_scorecard.v0" or raw_score.get("benchmark_sha256") != benchmark_digest:
        raise ValueError("raw scorecard does not match benchmark")
    raw_rows = raw_score.get("cases")
    if not isinstance(raw_rows, list) or [row["case_id"] for row in raw_rows] != [case["case_id"] for case in cases]:
        raise ValueError("raw scorecard case IDs do not match benchmark")
    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for case, raw_row in zip(cases, raw_rows):
        actual = raw_row["actual"]
        if actual is None:
            status, reason = "blocked", "invalid_output"
        else:
            if not isinstance(actual, dict):
                raise ValueError("raw scorecard actual must be an object or null")
            proposal = {
                **actual,
                "schema": SCHEMA_ID,
                "request_id": case["case_id"],
                "observation_ref": case["observation"]["ref"],
            }
            result = admit(case["request"], proposal, case["observation"])
            status, reason = result["status"], result.get("reason")
            if status == "accepted" and raw_row["adapter_status"] != "accepted":
                raise ValueError("admission accepted a plan the raw compiler rejected")
        accepted = status == "accepted"
        correct = accepted and actual == case["expected"]
        false_execution = accepted and not correct
        counts["total"] += 1
        counts["accepted"] += int(accepted)
        counts["accepted_correct"] += int(correct)
        counts["false_execution"] += int(false_execution)
        counts["blocked_supported"] += int(not accepted and case["expected"]["decision"] == "type_text")
        counts["blocked_unsupported_or_ambiguous"] += int(not accepted and case["expected"]["decision"] != "type_text")
        rows.append({
            "case_id": case["case_id"],
            "expected": case["expected"],
            "raw_actual": actual,
            "raw_exact": raw_row["exact"],
            "raw_false_execution": raw_row["false_execution"],
            "admission_status": status,
            "admission_reason": reason,
            "accepted_correct": correct,
            "false_execution": false_execution,
        })
    return {
        "schema": "rocell.ai_admission_scorecard.v0",
        "benchmark_sha256": benchmark_digest,
        "raw_scorecard_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "model": raw_score["model"],
        "model_digest": raw_score["model_digest"],
        "prompt_sha256": raw_score["prompt_sha256"],
        "policy_sha256": POLICY_SHA256,
        "counts": dict(sorted(counts.items())),
        "cases": rows,
        "evidence_class": "offline_admission_only",
        "hardware_commands": 0,
    }
