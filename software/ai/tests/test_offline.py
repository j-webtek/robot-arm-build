"""Contract checks for the read-only intent baseline and frozen cases."""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(AI_DIR.parent / "src"))

from rocell_ai.baseline import propose  # noqa: E402
from rocell_ai.adapter import inspect  # noqa: E402
from rocell_ai.contract import validate_proposal  # noqa: E402
from rocell_ai.evaluation import evaluate, load_benchmark  # noqa: E402
from rocell_ai.review import review_benchmark  # noqa: E402


class OfflineContractTests(unittest.TestCase):
    def test_quoted_control_words_are_literal_text(self) -> None:
        value = propose(
            request_id="quoted",
            request='Type "call phone" on keyboard',
            observation={"ref": "fixture-1", "fresh": True},
        )
        self.assertEqual(value["decision"], "type_text")
        self.assertEqual(value["text"], "call phone")
        validate_proposal(value)

    def test_extra_instruction_is_not_silently_dropped(self) -> None:
        value = propose(
            request_id="extra",
            request='Type "test" on keyboard and open an app',
            observation={"ref": "fixture-2", "fresh": True},
        )
        self.assertEqual(value["decision"], "clarify")

    def test_phone_requires_declared_state_and_stale_blocks(self) -> None:
        request = 'Type "test" on phone'
        unknown = propose(request_id="unknown", request=request, observation={"ref": "fixture-3", "fresh": True})
        stale = propose(request_id="stale", request=request, observation={"ref": "fixture-4", "fresh": False, "phone_state": "KEYBOARD_LOWER"})
        self.assertEqual(unknown["reason"], "phone_state_unverified")
        self.assertEqual(stale["reason"], "stale_observation")

    def test_frozen_benchmark_hash_and_baseline(self) -> None:
        cases = AI_DIR / "eval" / "benchmark_v0.jsonl"
        manifest = AI_DIR / "eval" / "benchmark_v0.manifest.json"
        score = evaluate(cases, manifest)
        self.assertEqual(score["counts"]["total"], 28)
        self.assertEqual(score["counts"]["exact"], 28)
        self.assertEqual(score["hardware_commands"], 0)
        with tempfile.TemporaryDirectory() as temp_dir:
            changed = Path(temp_dir) / "cases.jsonl"
            changed.write_bytes(cases.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                load_benchmark(changed, manifest)

    def test_proposal_shape_rejects_extra_motion_field(self) -> None:
        value = {
            "schema": "rocell.ai_task_proposal.v0",
            "request_id": "shape",
            "observation_ref": "fixture-5",
            "decision": "type_text",
            "device": "keyboard",
            "text": "test",
            "joint_angle": 90,
        }
        with self.assertRaisesRegex(ValueError, "invalid fields"):
            validate_proposal(value)
        value.pop("joint_angle")
        value["decision"] = ["type_text"]
        with self.assertRaisesRegex(ValueError, "invalid fields"):
            validate_proposal(value)

    def test_adapter_rejects_stale_proposal_and_preserves_rocell_plan(self) -> None:
        proposal = {
            "schema": "rocell.ai_task_proposal.v0",
            "request_id": "adapter",
            "observation_ref": "fixture-6",
            "decision": "type_text",
            "device": "keyboard",
            "text": "test",
        }
        accepted = inspect(proposal, {"ref": "fixture-6", "fresh": True})
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual(accepted["action_plan"]["schema"], "rocell.action_plan.v1")
        self.assertEqual(len(accepted["action_plan"]["actions"]), 4)
        stale = inspect(proposal, {"ref": "fixture-6", "fresh": False})
        self.assertEqual(stale["reason"], "stale_observation")
        with self.assertRaisesRegex(ValueError, "reference mismatch"):
            inspect(proposal, {"ref": "other", "fresh": True})

    def test_simulated_review_and_held_out_failure_are_explicit(self) -> None:
        folder = AI_DIR / "eval"
        cases = folder / "benchmark_v1.jsonl"
        manifest = folder / "benchmark_v1.manifest.json"
        review = review_benchmark(cases, manifest, folder / "benchmark_v0.jsonl")
        self.assertFalse(review["human_reviewed"])
        self.assertEqual(review["passed"], 31)
        self.assertEqual(review["issues"], [])
        score = evaluate(cases, manifest)
        self.assertEqual(score["counts"]["exact"], 17)
        self.assertEqual(score["counts"]["false_execution"], 1)
        false_rows = [row for row in score["cases"] if row["false_execution"]]
        self.assertEqual([row["case_id"] for row in false_rows], ["v1_c02"])
        self.assertEqual(score["hardware_commands"], 0)

    def test_simulated_review_detects_compiler_label_dispute(self) -> None:
        folder = AI_DIR / "eval"
        rows = [json.loads(line) for line in (folder / "benchmark_v1.jsonl").read_text(encoding="utf-8").splitlines()]
        rows[0]["review"]["text"] = "HELLO"
        with tempfile.TemporaryDirectory() as temp_dir:
            cases = Path(temp_dir) / "cases.jsonl"
            manifest = Path(temp_dir) / "manifest.json"
            raw = ("\n".join(json.dumps(row) for row in rows) + "\n").encode("utf-8")
            cases.write_bytes(raw)
            metadata = json.loads((folder / "benchmark_v1.manifest.json").read_text(encoding="utf-8"))
            metadata["cases_sha256"] = hashlib.sha256(raw).hexdigest()
            manifest.write_text(json.dumps(metadata), encoding="utf-8")
            report = review_benchmark(cases, manifest, folder / "benchmark_v0.jsonl")
        self.assertIn({"case_id": "v1_k01", "issue": "compiler_verdict_mismatch"}, report["issues"])


if __name__ == "__main__":
    unittest.main()
