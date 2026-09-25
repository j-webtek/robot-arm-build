"""Read-only command entry for the RoCell AI baseline and benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


AI_DIR = Path(__file__).resolve().parent
SOFTWARE_DIR = AI_DIR.parent
sys.path.insert(0, str(SOFTWARE_DIR / "src"))

from rocell_ai.baseline import propose  # noqa: E402
from rocell_ai.adapter import inspect  # noqa: E402
from rocell_ai.contract import validate_proposal  # noqa: E402
from rocell_ai.evaluation import evaluate  # noqa: E402
from rocell_ai.model_eval import evaluate_model  # noqa: E402
from rocell_ai.admission_eval import evaluate_admission  # noqa: E402
from rocell_ai.grounded import propose as grounded_propose  # noqa: E402
from rocell_ai.grounded_eval import evaluate_grounded  # noqa: E402
from rocell_ai.review import review_benchmark  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline English-to-RoCell task baseline")
    sub = parser.add_subparsers(dest="command", required=True)
    single = sub.add_parser("propose", help="Propose a single task without hardware access")
    single.add_argument("--request", required=True)
    single.add_argument("--request-id", default="manual-001")
    single.add_argument("--observation-ref", default="manual-offline")
    single.add_argument("--phone-state", default="UNKNOWN")
    single.add_argument("--stale", action="store_true")
    checked = sub.add_parser("inspect", help="Propose and inspect a RoCell semantic plan offline")
    checked.add_argument("--request", required=True)
    checked.add_argument("--request-id", default="manual-001")
    checked.add_argument("--observation-ref", default="manual-offline")
    checked.add_argument("--phone-state", default="UNKNOWN")
    checked.add_argument("--stale", action="store_true")
    batch = sub.add_parser("evaluate", help="Evaluate the frozen offline benchmark")
    batch.add_argument("--cases", type=Path, default=AI_DIR / "eval" / "benchmark_v0.jsonl")
    batch.add_argument("--manifest", type=Path, default=AI_DIR / "eval" / "benchmark_v0.manifest.json")
    batch.add_argument("--output", type=Path)
    model_batch = sub.add_parser("evaluate-model", help="Evaluate a locally installed Ollama model offline")
    model_batch.add_argument("--model", required=True)
    model_batch.add_argument("--cases", type=Path, default=AI_DIR / "eval" / "benchmark_v1.jsonl")
    model_batch.add_argument("--manifest", type=Path, default=AI_DIR / "eval" / "benchmark_v1.manifest.json")
    model_batch.add_argument("--output", type=Path)
    review = sub.add_parser("review", help="Cross-check agent-authored benchmark labels against RoCell")
    review.add_argument("--cases", type=Path, default=AI_DIR / "eval" / "benchmark_v1.jsonl")
    review.add_argument("--manifest", type=Path, default=AI_DIR / "eval" / "benchmark_v1.manifest.json")
    review.add_argument("--prior", type=Path, action="append", help="Prior benchmark to check for exact request reuse; repeat as needed")
    review.add_argument("--output", type=Path)
    admission = sub.add_parser("admit-score", help="Replay a frozen model scorecard through request grounding")
    admission.add_argument("--cases", type=Path, required=True)
    admission.add_argument("--manifest", type=Path, required=True)
    admission.add_argument("--raw-scorecard", type=Path, required=True)
    admission.add_argument("--output", type=Path)
    grounded = sub.add_parser("ground", help="Extract and inspect grounded slots offline")
    grounded.add_argument("--request", required=True)
    grounded.add_argument("--request-id", default="manual-001")
    grounded.add_argument("--observation-ref", default="manual-offline")
    grounded.add_argument("--phone-state", default="UNKNOWN")
    grounded.add_argument("--stale", action="store_true")
    grounded_batch = sub.add_parser("evaluate-grounded", help="Score the grounded intent path offline")
    grounded_batch.add_argument("--cases", type=Path, required=True)
    grounded_batch.add_argument("--manifest", type=Path, required=True)
    grounded_batch.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.command in {"propose", "inspect"}:
        observation = {"ref": args.observation_ref, "fresh": not args.stale, "phone_state": args.phone_state}
        proposal = propose(
            request_id=args.request_id,
            request=args.request,
            observation=observation,
        )
        validate_proposal(proposal)
        result = proposal if args.command == "propose" else {"proposal": proposal, "inspection": inspect(proposal, observation)}
    elif args.command == "evaluate":
        result = evaluate(args.cases, args.manifest)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    elif args.command == "evaluate-model":
        result = evaluate_model(args.cases, args.manifest, args.model)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    elif args.command == "admit-score":
        result = evaluate_admission(args.cases, args.manifest, args.raw_scorecard)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    elif args.command == "ground":
        observation = {"ref": args.observation_ref, "fresh": not args.stale, "phone_state": args.phone_state}
        proposal = grounded_propose(request_id=args.request_id, request=args.request, observation=observation)
        result = {"proposal": proposal, "inspection": inspect(proposal, observation)}
    elif args.command == "evaluate-grounded":
        result = evaluate_grounded(args.cases, args.manifest)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    else:
        result = review_benchmark(args.cases, args.manifest, args.prior or [AI_DIR / "eval" / "benchmark_v0.jsonl"])
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.command == "review" and result["issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
