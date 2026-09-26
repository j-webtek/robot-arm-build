"""Build the sealed, review-only r97 source/image handoff archive."""

from __future__ import annotations

import json
from pathlib import Path

from rocell.application.r97_independent_review_packet import build_r97_review_packet
from review_r97_production_runtime import APP_SHA, COMPILE_ID, review
from stage_r97_production_runtime import TARGET, sources


def build(root: Path, output: Path | None = None) -> dict:
    root = Path(root).resolve()
    first_party = review(root)
    tools = root / ".firmware-tools"
    build_dir = tools / "build-configured-diagnostic-candidate-r97--default-4mb-no-psram"
    compile_report_path = (
        root / "runs/wizard-exports" / COMPILE_ID / "attachment-compile-review.json"
    )
    result = build_r97_review_packet(
        sources=sources(root),
        app_image=(build_dir / "RoArm-M3_example.ino.bin").read_bytes(),
        elf_image=(build_dir / "RoArm-M3_example.ino.elf").read_bytes(),
        compile_report=compile_report_path.read_bytes(),
        first_party_report=(json.dumps(first_party, sort_keys=True, separators=(",", ":"))
                            + "\n").encode("utf-8"),
    )
    if result.app_sha256 != APP_SHA:
        raise ValueError("r97 review packet app identity differs")
    destination = (
        root / "runs/review-packets" /
        f"r97-{result.packet_sha256}.zip"
        if output is None else Path(output).resolve()
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.read_bytes() != result.packet_bytes:
        raise ValueError("existing r97 review packet differs; refusing to overwrite")
    if not destination.exists():
        with destination.open("xb") as stream:
            stream.write(result.packet_bytes)
    return {
        **result.to_dict(),
        "path": str(destination.relative_to(root)),
        "target": TARGET,
        "firmware_uploaded": False,
        "controller_started": False,
        "movement_command_sent": False,
    }


if __name__ == "__main__":
    print(json.dumps(build(Path(__file__).resolve().parents[1]), indent=2))
