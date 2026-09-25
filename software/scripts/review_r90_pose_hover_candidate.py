"""Offline source/image/route review for r90; never deploys or moves hardware."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

if __package__:
    from .preflight_r89_live_campaign import local_install_review
else:
    from preflight_r89_live_campaign import local_install_review
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.reviewed_hover_manifest import ghost_key_manifest, validate_manifest
from rocell.application.reviewed_hover_release_identity import (
    derive_release_identity, render_release_stamp, verify_release_pair,
)
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


TARGET = "configured-diagnostic-candidate-r90"
STAGE = "wizard-20260925T115135790589Z-58de5734b2394a18aad26c7238621742"


def review(root: Path, compile_export: str) -> dict:
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    predecessor = local_install_review(root)
    stage, _ = _read(exports, STAGE, "attachment-r90-pose-hover-stage.json")
    compiled, _ = _read(exports, compile_export, "attachment-compile-review.json")
    if (stage.get("status") != "STAGED_OFFLINE"
            or stage.get("predecessor_app_sha256") != predecessor["app_sha256"]
            or set(stage.get("changed_files", {})) != {
                "diagnostic_boot.h", "reviewed_hover_release_stamp.h"}
            or compiled.get("status") != "COMPILED"
            or compiled.get("target") != TARGET
            or compiled.get("build_profile") != "default-4mb-no-psram"):
        raise ValueError("Pinned r90 stage/compile differs")
    build = root / f".firmware-tools/build-{TARGET}--default-4mb-no-psram"
    app = (build / "RoArm-M3_example.ino.bin").read_bytes()
    sha = lambda data: hashlib.sha256(data).hexdigest()
    app_sha = sha(app)
    if (compiled.get("artifact_hashes", {}).get("RoArm-M3_example.ino.bin") != app_sha
            or len(app) > 0x140000):
        raise ValueError("r90 app exceeds slot or differs from compile")
    source_hashes = {name.replace("\\", "/"): digest
                     for name, digest in compiled["source_hashes"].items()
                     if not name.replace("\\", "/").endswith(
                         "/reviewed_hover_release_stamp.h")}
    source_bytes = {name: (root / name).read_bytes() for name in source_hashes}
    recipe = validate_manifest(ghost_key_manifest())["manifest_sha256"]
    release = derive_release_identity(source_hashes=source_hashes,
        toolchain_lock_sha256=compiled["toolchain_lock_sha256"],
        recipe_sha256=recipe, build_profile="default-4mb-no-psram")
    stamp = (root / ".firmware-tools" / TARGET / "RoArm-M3_example"
             / "reviewed_hover_release_stamp.h").read_bytes()
    if release != stage["release_sha256"] or stamp != render_release_stamp(release):
        raise ValueError("r90 release identity differs")
    record = dict(schema="rocell.reviewed_hover_release_review.v1",
                  release_sha256=release, app_sha256=app_sha, app_bytes=len(app),
                  app_offset=0x10000, app_slot_bytes=0x140000,
                  recipe_sha256=recipe, source_hashes=source_hashes,
                  toolchain_lock_sha256=compiled["toolchain_lock_sha256"],
                  build_profile="default-4mb-no-psram", target=TARGET,
                  compile_review_sha256=sha(canonical(compiled)),
                  hardware_access=False, firmware_uploaded=False,
                  deployment_authorized=False)
    verify_release_pair(record, compile_report=compiled,
                        source_bytes=source_bytes, app_image=app)
    nm = root / ".firmware-tools/data/packages/esp32/tools/esp-x32/2302/bin/xtensa-esp32-elf-nm.exe"
    symbols = subprocess.run([str(nm), "-C", str(build / "RoArm-M3_example.ino.elf")],
                             check=True, capture_output=True, text=True).stdout
    required = ("registerShoulderSessionRoutes()", "registerPoseObservationRoutes()",
                "pollPoseObservation()")
    forbidden = ("registerDiagnosticRoutes()", "webCtrlServer()",
                 "initHttpWebServer()")
    if (any(symbol not in symbols for symbol in required)
            or any(symbol in symbols for symbol in forbidden)
            or b"/rocell/reviewed-hover/start" not in app
            or b"/rocell/pose/capture" not in app
            or b"/rocell/pose/record" not in app):
        raise ValueError("r90 linked route selection differs")
    return dict(schema="rocell.r90_pose_hover_candidate_review.v1",
                status="COMPILED_ROUTE_PRESENT_NOT_DEPLOYED",
                app_sha256=app_sha, app_bytes=len(app), release_sha256=release,
                predecessor_app_sha256=predecessor["app_sha256"],
                linked_entrypoints=list(required), absent_entrypoints=list(forbidden),
                pose_route_markers_present=True, reviewed_hover_route_present=True,
                hardware_access=False, firmware_uploaded=False,
                deployment_authorized=False, movement_tested=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compile-export", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = review(root, args.compile_export)
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r90-pose-hover-candidate-review"}, [],
                            attachments={"r90-pose-hover-candidate-review.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r90 candidate review export invalid")
    print(json.dumps(dict(report=report, export=saved["path"])))


if __name__ == "__main__":
    main()
