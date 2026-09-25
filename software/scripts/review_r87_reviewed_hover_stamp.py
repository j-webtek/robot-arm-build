"""Offline source/stamp/image binding review for r87; never deploys."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.reviewed_hover_release_identity import (
    derive_release_identity, render_release_stamp, verify_release_pair,
)
from rocell.application.reviewed_hover_manifest import ghost_key_manifest, validate_manifest
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


COMPILE = "wizard-20260925T033348685036Z-79e8711857c141299d49d47d57659253"
APP = "d9179f0773b207fa209c6edc39b7942c07d014dd0d092dd79b9d389cbbd3776b"
TARGET = "configured-diagnostic-candidate-r87"


def review(root: Path) -> dict:
    root = Path(root).resolve()
    sha = lambda data: hashlib.sha256(data).hexdigest()
    exports = root / "runs/wizard-exports"
    compiled, compile_digest = _read(exports, COMPILE, "attachment-compile-review.json")
    prior = root / ".firmware-tools/configured-diagnostic-candidate-r86/RoArm-M3_example"
    staged = root / ".firmware-tools/configured-diagnostic-candidate-r87/RoArm-M3_example"
    old = {p.name: p.read_bytes() for p in prior.iterdir() if p.is_file()}
    actual = {p.name: p.read_bytes() for p in staged.iterdir() if p.is_file()}
    if ({name for name in old if old[name] != actual.get(name)} !=
            {"reviewed_hover_board.h"} or
            set(actual) - set(old) != {"reviewed_hover_release_stamp.h"} or
            set(old) - set(actual)):
        raise ValueError("r87 staged source differs from narrow-boot predecessor")
    adapter = actual["reviewed_hover_board_adapter.h"]
    if (b"return false;" not in adapter or
            b"No independently verified image/release identity is wired yet" not in adapter):
        raise ValueError("r87 live adapter unexpectedly enabled")
    if (compiled.get("status") != "COMPILED" or compiled.get("target") != TARGET or
            compiled.get("build_profile") != "default-4mb-no-psram"):
        raise ValueError("r87 compile report differs")
    normalized = {name.replace("\\", "/"): digest
                  for name, digest in compiled["source_hashes"].items()}
    prefix = f".firmware-tools/{TARGET}/RoArm-M3_example/"
    if any(normalized.get(prefix + name) != sha(data) for name, data in actual.items()):
        raise ValueError("r87 compiled source differs")
    stamp_path = prefix + "reviewed_hover_release_stamp.h"
    source_hashes = {name: digest for name, digest in normalized.items()
                     if name != stamp_path}
    source_bytes = {name: (root / name).read_bytes() for name in source_hashes}
    recipe = validate_manifest(ghost_key_manifest())["manifest_sha256"]
    release = derive_release_identity(source_hashes=source_hashes,
        toolchain_lock_sha256=compiled["toolchain_lock_sha256"],
        recipe_sha256=recipe, build_profile="default-4mb-no-psram")
    if actual["reviewed_hover_release_stamp.h"] != render_release_stamp(release):
        raise ValueError("r87 generated stamp differs")
    image = (root / f".firmware-tools/build-{TARGET}--default-4mb-no-psram"
             / "RoArm-M3_example.ino.bin").read_bytes()
    if (sha(image) != APP or len(image) > 0x140000 or
            b"LIVE_RELEASE_UNAVAILABLE" not in image):
        raise ValueError("r87 app image differs or fail-closed marker absent")
    build = root / f".firmware-tools/build-{TARGET}--default-4mb-no-psram"
    nm = root / ".firmware-tools/data/packages/esp32/tools/esp-x32/2302/bin/xtensa-esp32-elf-nm.exe"
    symbols = subprocess.run([str(nm), "-C", str(build / "RoArm-M3_example.ino.elf")],
                             check=True, capture_output=True, text=True).stdout
    if ("registerShoulderSessionRoutes()" not in symbols or
            any(symbol in symbols for symbol in (
                "registerDiagnosticRoutes()", "webCtrlServer()",
                "initHttpWebServer()", "registerHoldDiagnosticRoutes()"))):
        raise ValueError("r87 linked registrar selection differs")
    record = dict(schema="rocell.reviewed_hover_release_review.v1",
        release_sha256=release, app_sha256=APP, app_bytes=len(image),
        app_offset=0x10000, app_slot_bytes=0x140000,
        recipe_sha256=recipe, source_hashes=source_hashes,
        toolchain_lock_sha256=compiled["toolchain_lock_sha256"],
        build_profile="default-4mb-no-psram", target=TARGET,
        compile_review_sha256=sha(canonical(compiled)), hardware_access=False,
        firmware_uploaded=False, deployment_authorized=False)
    checked = verify_release_pair(record, compile_report=compiled,
                                  source_bytes=source_bytes, app_image=image)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r87-reviewed-hover-stamp-review"}, [],
                            attachments={
                                "r87-reviewed-hover-release-review.json": canonical(record),
                                "r87-reviewed-hover-pair-check.json": canonical(checked),
                                "r87-compile-attachment-digest.json": canonical({
                                    "sha256": compile_digest,
                                    "export_id": COMPILE,
                                }),
                            })
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r87 stamp review export failed")
    return {"status": "STAMPED_OFFLINE_NOT_DEPLOYABLE",
            "export": saved["path"], "release_sha256": release,
            "app_sha256": APP, "app_bytes": len(image)}


if __name__ == "__main__":
    import json
    print(json.dumps(review(Path(__file__).resolve().parents[1])))
