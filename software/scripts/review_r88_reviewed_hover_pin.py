"""Offline source/stamp/image and recipe-pin review for r88; never deploys."""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.reviewed_hover_release_identity import (
    derive_release_identity, render_release_stamp, verify_release_pair,
)
from rocell.application.reviewed_hover_manifest import ghost_key_manifest, validate_manifest
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


COMPILE = "wizard-20260925T034109658406Z-fc5e9c41bdf84ec8b6eeb2219dea3516"
APP = "80d9a7eb3e574a1d3db7c5c4e8dea0f18ec6983a15e99433b4b6a8f79a35161f"
TARGET = "configured-diagnostic-candidate-r88"


def review(root: Path) -> dict:
    root = Path(root).resolve()
    sha = lambda data: hashlib.sha256(data).hexdigest()
    exports = root / "runs/wizard-exports"
    compiled, compile_digest = _read(exports, COMPILE, "attachment-compile-review.json")
    prior = root / ".firmware-tools/configured-diagnostic-candidate-r87/RoArm-M3_example"
    staged = root / ".firmware-tools/configured-diagnostic-candidate-r88/RoArm-M3_example"
    old = {p.name: p.read_bytes() for p in prior.iterdir() if p.is_file()}
    actual = {p.name: p.read_bytes() for p in staged.iterdir() if p.is_file()}
    if ({name for name in old if old[name] != actual.get(name)} !=
            {"reviewed_hover_board_adapter.h", "reviewed_hover_routes.h",
             "reviewed_hover_release_stamp.h"} or
            set(actual) - set(old) or
            set(old) - set(actual)):
        raise ValueError("r88 staged source differs from stamped predecessor")
    adapter = actual["reviewed_hover_board_adapter.h"]
    if (b"return false;" not in adapter or
            b"No independently verified image/release identity is wired yet" not in adapter):
        raise ValueError("r88 live adapter unexpectedly enabled")
    if (compiled.get("status") != "COMPILED" or compiled.get("target") != TARGET or
            compiled.get("build_profile") != "default-4mb-no-psram"):
        raise ValueError("r88 compile report differs")
    normalized = {name.replace("\\", "/"): digest
                  for name, digest in compiled["source_hashes"].items()}
    prefix = f".firmware-tools/{TARGET}/RoArm-M3_example/"
    if any(normalized.get(prefix + name) != sha(data) for name, data in actual.items()):
        raise ValueError("r88 compiled source differs")
    stamp_path = prefix + "reviewed_hover_release_stamp.h"
    source_hashes = {name: digest for name, digest in normalized.items()
                     if name != stamp_path}
    source_bytes = {name: (root / name).read_bytes() for name in source_hashes}
    recipe = validate_manifest(ghost_key_manifest())["manifest_sha256"]
    pin = re.search(rb"static constexpr uint8_t pinned\[32\]=\{([^}]+)\};", adapter)
    if not pin or bytes(int(item, 16) for item in
            re.findall(rb"0x([0-9a-f]{2})", pin.group(1))) != bytes.fromhex(recipe):
        raise ValueError("r88 controller recipe pin differs")
    route = actual["reviewed_hover_routes.h"]
    if (route.find(b"reviewed_hover_recipe_digest(pinned_recipe)") < 0 or
            route.find(b"reviewed_hover_recipe_digest(pinned_recipe)") >
            route.find(b"owner_.configure(ids,count,boot_,digest)")):
        raise ValueError("r88 pin is absent or after reservation")
    release = derive_release_identity(source_hashes=source_hashes,
        toolchain_lock_sha256=compiled["toolchain_lock_sha256"],
        recipe_sha256=recipe, build_profile="default-4mb-no-psram")
    if actual["reviewed_hover_release_stamp.h"] != render_release_stamp(release):
        raise ValueError("r88 generated stamp differs")
    image = (root / f".firmware-tools/build-{TARGET}--default-4mb-no-psram"
             / "RoArm-M3_example.ino.bin").read_bytes()
    if (sha(image) != APP or len(image) > 0x140000 or
            b"LIVE_RELEASE_UNAVAILABLE" not in image):
        raise ValueError("r88 app image differs or fail-closed marker absent")
    build = root / f".firmware-tools/build-{TARGET}--default-4mb-no-psram"
    nm = root / ".firmware-tools/data/packages/esp32/tools/esp-x32/2302/bin/xtensa-esp32-elf-nm.exe"
    symbols = subprocess.run([str(nm), "-C", str(build / "RoArm-M3_example.ino.elf")],
                             check=True, capture_output=True, text=True).stdout
    if ("registerShoulderSessionRoutes()" not in symbols or
            any(symbol in symbols for symbol in (
                "registerDiagnosticRoutes()", "webCtrlServer()",
                "initHttpWebServer()", "registerHoldDiagnosticRoutes()"))):
        raise ValueError("r88 linked registrar selection differs")
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
    saved = exporter.export({"mode": "r88-reviewed-hover-pin-review"}, [],
                            attachments={
                                "r88-reviewed-hover-release-review.json": canonical(record),
                                "r88-reviewed-hover-pair-check.json": canonical(checked),
                                "r88-compile-attachment-digest.json": canonical({
                                    "sha256": compile_digest,
                                    "export_id": COMPILE,
                                }),
                            })
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r88 pin review export failed")
    return {"status": "RECIPE_PINNED_OFFLINE_NOT_DEPLOYABLE",
            "export": saved["path"], "release_sha256": release,
            "app_sha256": APP, "app_bytes": len(image)}


if __name__ == "__main__":
    import json
    print(json.dumps(review(Path(__file__).resolve().parents[1])))
