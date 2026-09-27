"""Build ARM-068's zero-I/O owner epoch draft and missing-evidence report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rocell.application.owner_governed_configuration_epoch_v1 import (
    assess_owner_governed_configuration_epoch_v1,
    build_owner_governed_configuration_epoch_draft_v1,
)
from rocell.application.r97_owner_ai_review_acceptance_v1 import (
    parse_r97_owner_ai_review_acceptance_v1,
)


def build(*, acceptance_path: Path, output_directory: Path) -> dict:
    acceptance = parse_r97_owner_ai_review_acceptance_v1(
        json.loads(Path(acceptance_path).read_text(encoding="utf-8")))
    draft = build_owner_governed_configuration_epoch_draft_v1(
        epoch_id="arm-068-owner-governed-measured-epoch",
        owner_acceptance=acceptance,
    )
    assessment = assess_owner_governed_configuration_epoch_v1(
        draft,
        evaluated_monotonic_ns=1,
        owner_acceptance=acceptance,
    )
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    outputs = {
        "draft": output_directory / "arm068_owner_epoch_draft.json",
        "assessment": (
            output_directory
            / "arm068_owner_epoch_missing_evidence_report.json"),
    }
    documents = {
        "draft": draft.to_dict(),
        "assessment": assessment.to_dict(),
    }
    for name, path in outputs.items():
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(documents[name], indent=2) + "\n")
    return {
        "draft_path": str(outputs["draft"]),
        "assessment_path": str(outputs["assessment"]),
        "draft_sha256": draft.draft_sha256,
        "assessment_sha256": assessment.assessment_sha256,
        "status": assessment.to_dict()["status"],
        "missing_component_ids": assessment.to_dict()[
            "missing_component_ids"],
        "hardware_access": False,
        "physical_authority": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("acceptance_path", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(
        acceptance_path=args.acceptance_path,
        output_directory=args.output_directory,
    ), indent=2))
