"""Build the offline ARM-065 r97 runtime-transition assessment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rocell.application.r97_runtime_transition_assessment_v1 import (
    assess_r97_runtime_transition_v1,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    receipt = ROOT / "ai/eval/arm064_active_feedback_qualification_20260927.json"
    report = assess_r97_runtime_transition_v1(receipt.read_bytes()).to_dict()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
