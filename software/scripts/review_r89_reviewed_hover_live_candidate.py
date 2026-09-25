"""Offline exact-source/image review of the r89 live-capable candidate; never deploys."""
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


COMPILE = "wizard-20260925T034619289604Z-68658f0139aa430793f4b8ba5c5345b4"
APP = "89c0d91334ab4362d392a3e3e66433c216d7e1740842dbba1b87881b722236b0"
TARGET = "configured-diagnostic-candidate-r89"


def review(root: Path) -> dict:
    root = Path(root).resolve()
    sha = lambda data: hashlib.sha256(data).hexdigest()
    exports = root / "runs/wizard-exports"
    compiled, compile_digest = _read(exports, COMPILE, "attachment-compile-review.json")
    prior = root / ".firmware-tools/configured-diagnostic-candidate-r88/RoArm-M3_example"
    staged = root / ".firmware-tools/configured-diagnostic-candidate-r89/RoArm-M3_example"
    old = {p.name: p.read_bytes() for p in prior.iterdir() if p.is_file()}
    actual = {p.name: p.read_bytes() for p in staged.iterdir() if p.is_file()}
    if ({name for name in old if old[name] != actual.get(name)} !=
            {"reviewed_hover_board_adapter.h", "reviewed_hover_board.h",
             "reviewed_hover_release_stamp.h"} or
            set(actual) - set(old) or
            set(old) - set(actual)):
        raise ValueError("r89 staged source differs from pinned predecessor")
    adapter = actual["reviewed_hover_board_adapter.h"]
    board = actual["reviewed_hover_board.h"]
    if (b'#include "reviewed_hover_release_stamp.h"' not in adapter or
            b"digest[i]=reviewed_hover_release_sha256[i]" not in adapter or
            b"return aggregate!=0;" not in adapter or
            b'live_release_available\\":true' not in board):
        raise ValueError("r89 release identity wiring differs")
    if (compiled.get("status") != "COMPILED" or compiled.get("target") != TARGET or
            compiled.get("build_profile") != "default-4mb-no-psram"):
        raise ValueError("r89 compile report differs")
    normalized = {name.replace("\\", "/"): digest
                  for name, digest in compiled["source_hashes"].items()}
    prefix = f".firmware-tools/{TARGET}/RoArm-M3_example/"
    if any(normalized.get(prefix + name) != sha(data) for name, data in actual.items()):
        raise ValueError("r89 compiled source differs")
    stamp_path = prefix + "reviewed_hover_release_stamp.h"
    source_hashes = {name: digest for name, digest in normalized.items()
                     if name != stamp_path}
    source_bytes = {name: (root / name).read_bytes() for name in source_hashes}
    recipe = validate_manifest(ghost_key_manifest())["manifest_sha256"]
    pin = re.search(rb"static constexpr uint8_t pinned\[32\]=\{([^}]+)\};", adapter)
    if not pin or bytes(int(item, 16) for item in
            re.findall(rb"0x([0-9a-f]{2})", pin.group(1))) != bytes.fromhex(recipe):
        raise ValueError("r89 controller recipe pin differs")
    route = actual["reviewed_hover_routes.h"]
    if (route.find(b"reviewed_hover_recipe_digest(pinned_recipe)") < 0 or
            route.find(b"reviewed_hover_recipe_digest(pinned_recipe)") >
            route.find(b"owner_.configure(ids,count,boot_,digest)")):
        raise ValueError("r89 pin is absent or after reservation")
    release = derive_release_identity(source_hashes=source_hashes,
        toolchain_lock_sha256=compiled["toolchain_lock_sha256"],
        recipe_sha256=recipe, build_profile="default-4mb-no-psram")
    if actual["reviewed_hover_release_stamp.h"] != render_release_stamp(release):
        raise ValueError("r89 generated stamp differs")
    image = (root / f".firmware-tools/build-{TARGET}--default-4mb-no-psram"
             / "RoArm-M3_example.ino.bin").read_bytes()
    if (sha(image) != APP or len(image) > 0x140000 or
            b"RECIPE_NOT_RELEASED" not in image or
            b"/rocell/reviewed-hover/start" not in image):
        raise ValueError("r89 app image or route marker differs")
    build = root / f".firmware-tools/build-{TARGET}--default-4mb-no-psram"
    nm = root / ".firmware-tools/data/packages/esp32/tools/esp-x32/2302/bin/xtensa-esp32-elf-nm.exe"
    symbols = subprocess.run([str(nm), "-C", str(build / "RoArm-M3_example.ino.elf")],
                             check=True, capture_output=True, text=True).stdout
    if ("registerShoulderSessionRoutes()" not in symbols or
            any(symbol in symbols for symbol in (
                "registerDiagnosticRoutes()", "webCtrlServer()",
                "initHttpWebServer()", "registerHoldDiagnosticRoutes()"))):
        raise ValueError("r89 linked registrar selection differs")
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
    saved = exporter.export({"mode": "r89-reviewed-hover-live-candidate-review"}, [],
                            attachments={
                                "r89-reviewed-hover-release-review.json": canonical(record),
                                "r89-reviewed-hover-pair-check.json": canonical(checked),
                                "r89-compile-attachment-digest.json": canonical({
                                    "sha256": compile_digest,
                                    "export_id": COMPILE,
                                }),
                            })
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r89 candidate review export failed")
    return {"status": "LIVE_CAPABLE_CANDIDATE_NOT_DEPLOYED",
            "export": saved["path"], "release_sha256": release,
            "app_sha256": APP, "app_bytes": len(image)}


if __name__ == "__main__":
    import json
    print(json.dumps(review(Path(__file__).resolve().parents[1])))
