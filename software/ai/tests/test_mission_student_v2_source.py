import hashlib
import json
import sys
from pathlib import Path


AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from rocell_ai.mission_model_v2 import PROMPT_SHA256, SYSTEM_PROMPT, render_user
from rocell_ai.mission_student_v2_eval import evaluate
from rocell_ai.mission_student_v2_ollama import build_payload, manifest_split
from train.select_mission_student_v2 import selection_key


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_plan_hashes_every_development_source_and_excludes_confirmation():
    plan = json.loads((AI / "train/mission_student_v2_plan.json").read_text())
    assert plan["prompt_sha256"] == PROMPT_SHA256
    assert PROMPT_SHA256 == hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()
    assert plan["base_revision"] == "9213176726f574b556790deb65791e0c5aa438b6"
    assert plan["confirmation_policy"] == {
        "present_at_freeze": False,
        "generator_authored_after_selection_freeze": True,
        "single_generation_and_scoring_run": True,
        "no_post_confirmation_tuning": True,
        "same_prompt_decoder_evaluator_and_gates": True,
    }
    assert "confirmation_data" not in plan
    assert plan["hardware_writes"] == plan["physical_movements"] == 0
    for name, digest in plan["file_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest


def test_render_schema_request_and_manifest_binding_are_frozen():
    case = rows(AI / "data/mission_development_v2_validation.jsonl")[0]
    plan = json.loads((AI / "train/mission_student_v2_plan.json").read_text())
    schema = json.loads((AI / plan["mission_schema_path"]).read_text())
    assert json.loads(render_user(case)) == {
        "request_id": case["id"],
        "request": case["request"],
        "observation": case["observation"],
    }
    payload = build_payload("candidate:latest", case, schema, plan)
    assert payload["format"] == schema
    assert payload["stream"] is False
    assert payload["messages"][0]["content"] == SYSTEM_PROMPT
    assert payload["options"] == {
        "temperature": 0,
        "seed": 2910,
        "num_predict": 512,
        "num_ctx": 4096,
    }
    manifest, digest = manifest_split(
        AI / "data/mission_development_v2.manifest.json", "validation"
    )
    assert manifest["confirmation"]["present"] is False
    assert digest == hashlib.sha256(
        (AI / "data/mission_development_v2_validation.jsonl").read_bytes()
    ).hexdigest()


def test_evaluator_passes_perfect_and_detects_wrong_accepted(tmp_path):
    cases_path = AI / "data/mission_development_v2_validation.jsonl"
    cases = rows(cases_path)
    plan = json.loads((AI / "train/mission_student_v2_plan.json").read_text())
    digest = hashlib.sha256(cases_path.read_bytes()).hexdigest()

    def write_predictions(path, targets):
        path.write_bytes(
            b"".join(
                (
                    json.dumps(
                        {
                            "id": case["id"],
                            "response": json.dumps(target),
                            "model": "synthetic:latest",
                            "model_digest": "a" * 64,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                ).encode()
                for case, target in zip(cases, targets)
            )
        )

    perfect = tmp_path / "perfect.jsonl"
    write_predictions(perfect, [case["target"] for case in cases])
    score = evaluate(cases_path, perfect, plan, digest, "validation")
    assert score["passed"]
    assert score["metrics"]["minimum_category_exact_fraction"] == 1.0
    assert score["model_digest"] == "a" * 64

    changed_targets = [json.loads(json.dumps(case["target"])) for case in cases]
    index = next(
        index
        for index, case in enumerate(cases)
        if case["expected_compilation"]["status"] == "accepted"
    )
    changed_targets[index]["arguments"]["text"] += "x"
    dangerous = tmp_path / "dangerous.jsonl"
    write_predictions(dangerous, changed_targets)
    score = evaluate(cases_path, dangerous, plan, digest, "validation")
    assert not score["passed"]
    assert score["counts"]["wrong_accepted"] == 1
    assert score["counts"]["changed_literal"] == 1


def test_selection_rule_prefers_safety_before_more_exact_outputs():
    def candidate(epoch, wrong, invalid, changed, exact, accepted, floor, loss):
        return {
            "epoch": epoch,
            "validation_loss": loss,
            "scorecard": {
                "counts": {
                    "wrong_accepted": wrong,
                    "invalid": invalid,
                    "changed_literal": changed,
                    "exact": exact,
                    "accepted_correct": accepted,
                },
                "metrics": {"minimum_category_exact_fraction": floor},
            },
        }

    safe = candidate(1, 0, 0, 0, 280, 90, 0.75, 0.2)
    unsafe = candidate(2, 1, 0, 0, 320, 96, 1.0, 0.1)
    invalid = candidate(2, 0, 1, 0, 320, 96, 1.0, 0.1)
    assert min([safe, unsafe], key=selection_key) is safe
    assert min([safe, invalid], key=selection_key) is safe
