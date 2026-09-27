"""Build ARM-070's zero-I/O camera/support evidence-readiness assessment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rocell.application.camera_support_optics_epoch_intake_v1 import (
    assess_camera_support_optics_epoch_intake_v1,
    build_camera_support_optics_epoch_intake_v1,
)


def build(*, repository_root: Path, output_directory: Path) -> dict:
    intake = build_camera_support_optics_epoch_intake_v1(repository_root)
    assessment = assess_camera_support_optics_epoch_intake_v1(
        intake, evaluated_monotonic_ns=1)
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    documents = {
        "arm070_camera_support_optics_intake.json": intake.to_dict(),
        "arm070_camera_support_optics_readiness.json": assessment.to_dict(),
    }
    for name, document in documents.items():
        with (output_directory / name).open(
            "x", encoding="utf-8", newline="\n"
        ) as stream:
            stream.write(json.dumps(document, indent=2) + "\n")
    report = assessment.to_dict()
    return {
        "intake_sha256": intake.intake_sha256,
        "assessment_sha256": assessment.assessment_sha256,
        "status": report["status"],
        "missing_binding_ids": report["missing_binding_ids"],
        "component_admission_ready": report["component_admission_ready"],
        "epoch_advanced": False,
        "hardware_access": False,
        "physical_authority": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository_root", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(
        repository_root=args.repository_root,
        output_directory=args.output_directory,
    ), indent=2))
