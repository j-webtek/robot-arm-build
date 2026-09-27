"""Build the hash-bound ARM-067 owner acceptance; performs no hardware I/O."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rocell.application.r97_independent_review_decision_v1 import (
    build_synthetic_r97_review_rehearsal_v1,
)
from rocell.application.r97_owner_ai_review_acceptance_v1 import (
    accept_r97_internal_ai_review_v1,
)


def build(output: Path) -> dict:
    decision, _ = build_synthetic_r97_review_rehearsal_v1(
        rehearsal_id="arm-067-owner-ai-review",
        review_started_utc="2026-09-27T14:10:00Z",
        review_completed_utc="2026-09-27T14:11:00Z",
    )
    acceptance = accept_r97_internal_ai_review_v1(
        decision, acceptance_id="arm-067-owner-ai-acceptance",
        owner_id="project-owner", accepted_utc="2026-09-27T14:12:00Z")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(acceptance.to_dict(), indent=2) + "\n")
    return acceptance.to_dict()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
