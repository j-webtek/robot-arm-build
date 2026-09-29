"""PC18 actual-producer compatibility corpus; offline and zero-authority."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import jsonschema
import pytest

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from rocell_ai.actual_output_compatibility_v1 import (  # noqa: E402
    ActualOutputCompatibilityError,
    build_actual_emitter_hhi_payload,
    run_actual_output_compatibility_v1,
)

CORPUS = AI / "eval/actual_ai_arm_compatibility_corpus_v1.json"
REPORT = AI / "eval/actual_ai_arm_compatibility_report_v1.json"
SCHEMAS = AI / "schemas"


def _report():
    return run_actual_output_compatibility_v1(ROOT, CORPUS)


def test_retained_corpus_and_report_reproduce_and_validate():
    corpus = json.loads(CORPUS.read_text())
    report = _report()
    jsonschema.Draft202012Validator(json.loads(
        (SCHEMAS / "actual_ai_arm_compatibility_corpus_v1.schema.json").read_text()
    )).validate(corpus)
    jsonschema.Draft202012Validator(json.loads(
        (SCHEMAS / "actual_ai_arm_compatibility_report_v1.schema.json").read_text()
    )).validate(report)
    assert json.loads(REPORT.read_text()) == report
    assert report["passed_case_count"] == report["case_count"] == 7
    assert report["controller_commands"] == []
    assert report["hardware_commands_generated"] == 0
    assert report["hardware_access"] is report["physical_authority"] is False


def test_actual_emitter_bytes_and_full_order_are_retained_exactly():
    retained = (AI / "eval/actual_ai_emitter_hhi_batch_v2.json").read_bytes()
    assert retained == build_actual_emitter_hhi_payload(ROOT) + b"\n"
    case = _report()["cases"][0]
    assert case["ordered_target_ids"] == ["H", "H", "I"]
    assert case["contact_target_ids"] == ["H", "H", "I"]
    assert case["disposition"] == "TRAJECTORY_COMPILED"


def test_actual_precision_output_preserves_repeat_digit_and_punctuation_but_blocks():
    case = {item["case_id"]: item for item in _report()["cases"]}[
        "actual-precision-hh1-period-uncertain"]
    assert case["ordered_target_ids"] == ["H", "H", "1", "PERIOD"]
    assert case["disposition"] == "ARM_INGRESS_BLOCKED"
    assert case["blocker_code"] == "COMPOSED_UNCERTAINTY_OUTSIDE_REGION"
    assert case["controller_commands"] == []


@pytest.mark.parametrize("mutation", ["retained_hash", "expected_outcome"])
def test_corpus_mutation_fails_closed(tmp_path, mutation):
    document = json.loads(CORPUS.read_text())
    for record in document["retained_files"].values():
        source = CORPUS.parent / record["relative_path"]
        (tmp_path / record["relative_path"]).write_bytes(source.read_bytes())
    if mutation == "retained_hash":
        document["retained_files"]["actual_emitter_hhi"]["sha256"] = "0" * 64
    else:
        document["expected_cases"]["derived-low-confidence"]["blocker_code"] = (
            "WRONG")
    corpus = tmp_path / CORPUS.name
    corpus.write_text(json.dumps(document, indent=2) + "\n")
    with pytest.raises(ActualOutputCompatibilityError):
        run_actual_output_compatibility_v1(ROOT, corpus)


def test_report_hash_covers_every_result():
    report = _report()
    claimed = report.pop("report_sha256")
    canonical = json.dumps(
        report, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode()
    assert hashlib.sha256(canonical).hexdigest() == claimed
