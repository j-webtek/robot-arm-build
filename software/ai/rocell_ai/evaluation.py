"""Frozen offline evaluation against RoCell's semantic typing compiler."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from .adapter import inspect
from .baseline import propose
from .contract import validate_proposal


def load_benchmark(cases_path: Path, manifest_path: Path) -> tuple[list[dict[str, Any]], str]:
    raw = cases_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "rocell.ai_benchmark_manifest.v0":
        raise ValueError("unsupported benchmark manifest")
    if digest != manifest.get("cases_sha256"):
        raise ValueError("benchmark hash mismatch; create a new version before changing frozen cases")
    cases = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if len(cases) != manifest.get("case_count"):
        raise ValueError("benchmark count mismatch")
    ids = [case["case_id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate benchmark case ID")
    return cases, digest


def evaluate(cases_path: Path, manifest_path: Path) -> dict[str, Any]:
    cases, digest = load_benchmark(cases_path, manifest_path)
    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for case in cases:
        expected = case["expected"]
        proposal = propose(request_id=case["case_id"], request=case["request"], observation=case["observation"])
        validate_proposal(proposal)
        actual = {key: proposal[key] for key in expected}
        exact = actual == expected
        adapter_result = inspect(proposal, case["observation"])
        compiler_accepted = adapter_result["status"] == "accepted"
        plan_hash: str | None = None
        profile_id: str | None = None
        if compiler_accepted:
            plan_hash = adapter_result["plan_hash"]
            profile_id = adapter_result["profile_id"]
        if proposal["decision"] == "type_text" and not compiler_accepted:
            exact = False
        counts["total"] += 1
        counts[f"expected_{expected['decision']}"] += 1
        counts["exact"] += int(exact)
        counts["compiler_accepted"] += int(compiler_accepted)
        rows.append({
            "case_id": case["case_id"],
            "expected": expected,
            "actual": actual,
            "exact": exact,
            "compiler_accepted": compiler_accepted,
            "adapter_status": adapter_result["status"],
            "profile_id": profile_id,
            "plan_hash": plan_hash,
        })
    return {
        "schema": "rocell.ai_baseline_scorecard.v0",
        "benchmark_sha256": digest,
        "baseline": "deterministic_v0",
        "counts": dict(sorted(counts.items())),
        "exact_rate": counts["exact"] / counts["total"] if counts["total"] else 0.0,
        "cases": rows,
        "evidence_class": "offline_compiler_only",
        "hardware_commands": 0,
    }
