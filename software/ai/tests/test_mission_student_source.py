import hashlib
import json
import sys
from pathlib import Path

import pytest


AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from rocell_ai.mission_model import PROMPT_SHA256, SYSTEM_PROMPT, render_user
from rocell_ai.mission_student_eval import evaluate
from rocell_ai.mission_student_ollama import build_payload


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_frozen_plan_hashes_sources_data_and_prompt():
    plan = json.loads((AI / "train/mission_student_v1_plan.json").read_text())
    assert plan["prompt_sha256"] == PROMPT_SHA256
    assert PROMPT_SHA256 == hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()
    assert plan["base_revision"] == "9213176726f574b556790deb65791e0c5aa438b6"
    assert plan["heldout_policy"] == "never read by training or checkpoint selection"
    assert plan["hardware_writes"] == plan["physical_movements"] == 0
    for name, digest in plan["file_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    for name, digest in plan["split_sha256"].items():
        assert hashlib.sha256((AI / "data" / name).read_bytes()).hexdigest() == digest


def test_render_and_structured_request_are_frozen():
    case = rows(AI / "data/mission_curriculum_v1_validation.jsonl")[0]
    plan = json.loads((AI / "train/mission_student_v1_plan.json").read_text())
    schema = json.loads((AI / plan["mission_schema_path"]).read_text())
    rendered = json.loads(render_user(case))
    assert rendered == {
        "request_id": case["id"],
        "request": case["request"],
        "observation": case["observation"],
    }
    payload = build_payload("frozen:latest", case, schema, plan)
    assert payload["format"] == schema
    assert payload["stream"] is False
    assert payload["messages"][0]["content"] == SYSTEM_PROMPT
    assert payload["options"] == {
        "temperature": 0,
        "seed": 2810,
        "num_predict": 512,
        "num_ctx": 4096,
    }


def test_evaluator_accepts_perfect_and_rejects_wrong_execution(tmp_path):
    cases_path = AI / "data/mission_curriculum_v1_heldout.jsonl"
    heldout = rows(cases_path)
    plan = {
        "heldout_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "minimum_exact_fraction": 0.75,
        "minimum_expected_accepted_coverage": 0.75,
    }
    perfect = tmp_path / "perfect.jsonl"
    perfect.write_text(
        "".join(json.dumps({"id": row["id"], "response": json.dumps(row["target"])}) + "\n" for row in heldout)
    )
    score = evaluate(cases_path, perfect, plan)
    assert score["passed"]
    assert score["counts"]["exact"] == len(heldout)
    assert score["hardware_writes"] == score["physical_movements"] == 0

    dangerous = tmp_path / "dangerous.jsonl"
    predictions = []
    changed = False
    for row in heldout:
        response = row["target"]
        if not changed and row["expected_compilation"]["status"] == "accepted":
            response = json.loads(json.dumps(response))
            response["arguments"]["text"] += "x"
            changed = True
        predictions.append({"id": row["id"], "response": json.dumps(response)})
    dangerous.write_text("".join(json.dumps(row) + "\n" for row in predictions))
    score = evaluate(cases_path, dangerous, plan)
    assert not score["passed"]
    assert score["counts"]["wrong_accepted"] > 0


def test_evaluator_rejects_missing_or_duplicate_predictions(tmp_path):
    cases_path = AI / "data/mission_curriculum_v1_heldout.jsonl"
    heldout = rows(cases_path)
    plan = {
        "heldout_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "minimum_exact_fraction": 0.75,
        "minimum_expected_accepted_coverage": 0.75,
    }
    incomplete = tmp_path / "incomplete.jsonl"
    incomplete.write_text(json.dumps({"id": heldout[0]["id"], "response": "{}"}) + "\n")
    with pytest.raises(ValueError, match="every heldout ID"):
        evaluate(cases_path, incomplete, plan)
