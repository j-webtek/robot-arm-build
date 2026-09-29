"""Create or verify PC18 retained inputs and its zero-authority report."""

from __future__ import annotations

import json
from pathlib import Path
import sys

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from rocell_ai.actual_output_compatibility_v1 import (  # noqa: E402
    build_actual_emitter_hhi_payload,
    run_actual_output_compatibility_v1,
)


def main() -> None:
    eval_root = AI / "eval"
    hhi_path = eval_root / "actual_ai_emitter_hhi_batch_v2.json"
    payload = build_actual_emitter_hhi_payload(ROOT) + b"\n"
    if hhi_path.exists() and hhi_path.read_bytes() != payload:
        raise ValueError("retained actual-emitter HHI payload differs")
    if not hhi_path.exists():
        hhi_path.write_bytes(payload)

    corpus_path = eval_root / "actual_ai_arm_compatibility_corpus_v1.json"
    report_path = eval_root / "actual_ai_arm_compatibility_report_v1.json"
    report = run_actual_output_compatibility_v1(ROOT, corpus_path)
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if report_path.exists() and report_path.read_text() != rendered:
        raise ValueError("retained PC18 report differs")
    if not report_path.exists():
        report_path.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
