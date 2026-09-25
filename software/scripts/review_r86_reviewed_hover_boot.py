"""Offline review of the r86 narrow boot; never contacts or flashes the arm."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


COMPILE = "wizard-20260925T032454876046Z-c4ffe9f4e8c747fb817722a6ee3ce404"
APP = "5186a02c981053de88f7507fc41328f5c9ffe57bb5527c007556432d1b80e2ef"
CHANGED = {
    "diagnostic_boot.h": "09597819c5fbe9594489b1810401dbabf0b4f3bd8f3879d2f7e43d13626a1174",
    "reviewed_hover_board.h": "85baf0ed5e5cd68d37e46cacfb07f4a5cbc63a038c02832f7008041bc0301185",
}


def review(root: Path) -> dict:
    root = Path(root).resolve()
    sha = lambda data: hashlib.sha256(data).hexdigest()
    exports = root / "runs/wizard-exports"
    compiled, compile_digest = _read(exports, COMPILE, "attachment-compile-review.json")
    prior = root / ".firmware-tools/configured-diagnostic-candidate-r85/RoArm-M3_example"
    staged = root / ".firmware-tools/configured-diagnostic-candidate-r86/RoArm-M3_example"
    old = {p.name: p.read_bytes() for p in prior.iterdir() if p.is_file()}
    actual = {p.name: p.read_bytes() for p in staged.iterdir() if p.is_file()}
    if old.keys() != actual.keys() or {
        name for name in old if old[name] != actual[name]
    } != CHANGED.keys():
        raise ValueError("r86 differs from r85 outside narrow boot changes")
    if any(sha(actual[name]) != digest for name, digest in CHANGED.items()):
        raise ValueError("r86 changed source hash differs")
    boot = actual["diagnostic_boot.h"]
    if (boot.count(b"registerShoulderSessionRoutes();") != 1 or
            b"registerDiagnosticRoutes();" in boot or
            b"webCtrlServer();" in boot or
            b"initHttpWebServer();" in boot or
            b"pollShoulderSession();" not in boot):
        raise ValueError("r86 boot route/poll selection differs")
    if (compiled.get("status") != "COMPILED" or
            compiled.get("target") != "configured-diagnostic-candidate-r86" or
            compiled.get("build_profile") != "default-4mb-no-psram"):
        raise ValueError("r86 compile report differs")
    prefix = ".firmware-tools/configured-diagnostic-candidate-r86/RoArm-M3_example/"
    hashes = {name.replace("\\", "/"): digest
              for name, digest in compiled["source_hashes"].items()}
    if any(hashes.get(prefix + name) != sha(data) for name, data in actual.items()):
        raise ValueError("r86 compile input differs")
    build = root / ".firmware-tools/build-configured-diagnostic-candidate-r86--default-4mb-no-psram"
    image = (build / "RoArm-M3_example.ino.bin").read_bytes()
    if (sha(image) != APP or len(image) > 0x140000 or
            compiled["artifact_hashes"].get("RoArm-M3_example.ino.bin") != APP or
            not all(marker in image for marker in (
                b"/rocell/reviewed-hover/start",
                b"/rocell/reviewed-hover/capabilities",
                b"LIVE_RELEASE_UNAVAILABLE"))):
        raise ValueError("r86 image/hash/marker differs")
    nm = root / ".firmware-tools/data/packages/esp32/tools/esp-x32/2302/bin/xtensa-esp32-elf-nm.exe"
    elf = build / "RoArm-M3_example.ino.elf"
    symbols = subprocess.run([str(nm), "-C", str(elf)], check=True,
                             capture_output=True, text=True).stdout
    if ("registerShoulderSessionRoutes()" not in symbols or
            any(symbol in symbols for symbol in (
                "registerDiagnosticRoutes()", "webCtrlServer()",
                "initHttpWebServer()", "registerHoldDiagnosticRoutes()"))):
        raise ValueError("r86 linked registrar selection differs")
    report = dict(schema="rocell.r86_reviewed_hover_boot_review.v1",
                  app_sha256=APP, app_bytes=len(image), app_slot_bytes=0x140000,
                  compile_export_id=COMPILE, compile_report_sha256=compile_digest,
                  changed_inherited_files=list(CHANGED),
                  boot_registrar="registerShoulderSessionRoutes",
                  linked_legacy_registrars=False,
                  legacy_strings_may_remain=True,
                  release_identity_available=False, hardware_access=False,
                  firmware_uploaded=False, deployment_authorized=False,
                  motion_authorized=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r86-reviewed-hover-boot-review"}, [],
                            attachments={"r86-reviewed-hover-boot-review.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r86 review export failed")
    return {"status": "COMPILE_ONLY_NARROW_BOOT_NOT_DEPLOYABLE",
            "export": saved["path"], "app_sha256": APP}


if __name__ == "__main__":
    import json
    print(json.dumps(review(Path(__file__).resolve().parents[1])))
