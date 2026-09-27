"""Build ARM-069's zero-I/O software-build evidence and partial epoch."""

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
from rocell.application.software_build_epoch_evidence_v1 import (
    build_software_build_epoch_evidence_v1,
    review_software_build_epoch_evidence_v1,
    software_build_epoch_component_v1,
)


def build(*, software_root: Path, acceptance_path: Path,
          output_directory: Path) -> dict:
    acceptance = parse_r97_owner_ai_review_acceptance_v1(json.loads(
        Path(acceptance_path).read_text(encoding="utf-8")))
    evidence = build_software_build_epoch_evidence_v1(software_root)
    review = review_software_build_epoch_evidence_v1(evidence)
    component = software_build_epoch_component_v1(
        evidence, review, measured_monotonic_ns=1,
        valid_until_monotonic_ns=9_223_372_036_854_775_807,
    )
    draft = build_owner_governed_configuration_epoch_draft_v1(
        epoch_id="arm-069-owner-governed-measured-epoch",
        owner_acceptance=acceptance,
        components=(component,),
    )
    assessment = assess_owner_governed_configuration_epoch_v1(
        draft, evaluated_monotonic_ns=2, owner_acceptance=acceptance)
    documents = {
        "software_build_evidence": evidence.to_dict(),
        "software_build_review": review.to_dict(),
        "draft": draft.to_dict(),
        "assessment": assessment.to_dict(),
    }
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    names = {
        "software_build_evidence": "arm069_software_build_evidence.json",
        "software_build_review": "arm069_software_build_owner_ai_review.json",
        "draft": "arm069_owner_epoch_draft.json",
        "assessment": "arm069_owner_epoch_partial_assessment.json",
    }
    for key, file_name in names.items():
        path = output_directory / file_name
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(documents[key], indent=2) + "\n")
    report = assessment.to_dict()
    return {
        "evidence_bundle_sha256": evidence.evidence_bundle_sha256,
        "review_sha256": review.review_sha256,
        "draft_sha256": draft.draft_sha256,
        "assessment_sha256": assessment.assessment_sha256,
        "status": report["status"],
        "ready_component_ids": report["ready_component_ids"],
        "missing_component_ids": report["missing_component_ids"],
        "configuration_epoch_sha256": report["configuration_epoch_sha256"],
        "hardware_access": False,
        "physical_authority": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("software_root", type=Path)
    parser.add_argument("acceptance_path", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(
        software_root=args.software_root,
        acceptance_path=args.acceptance_path,
        output_directory=args.output_directory,
    ), indent=2))
