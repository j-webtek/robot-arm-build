"""Offline-only source, image and command-surface review for r94."""
import hashlib
import json
from pathlib import Path
import subprocess

from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

if __package__:
    from .review_r93_gripper_candidate import APP_SHA as R93_SHA
else:
    from review_r93_gripper_candidate import APP_SHA as R93_SHA

COMPILE_ID = "wizard-20260925T153706780940Z-b2feb880d4954a8f8f9ba62418001e17"


def review(root: Path, compile_id: str) -> dict:
    root = Path(root).resolve()
    tools = root / ".firmware-tools"
    old = tools / "configured-diagnostic-candidate-r93/RoArm-M3_example"
    new = tools / "configured-diagnostic-candidate-r94/RoArm-M3_example"
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    old_files = {p.name: p.read_bytes() for p in old.iterdir() if p.is_file()}
    new_files = {p.name: p.read_bytes() for p in new.iterdir() if p.is_file()}
    expected = dict(old_files)
    del expected["gripper_loading_board.h"]
    expected["diagnostic_boot.h"] = (root / "firmware/diagnostics/ghost_typing_b_boot.h").read_bytes()
    expected["ghost_typing_b_board.h"] = (root / "firmware/diagnostics/ghost_typing_b_board.h").read_bytes()
    if new_files != expected:
        raise ValueError("r94 source differs beyond the dedicated board/boot")
    report = json.loads((root / "runs/wizard-exports" / compile_id /
                         "attachment-compile-review.json").read_text())
    build = tools / "build-configured-diagnostic-candidate-r94--default-4mb-no-psram"
    app = (build / "RoArm-M3_example.ino.bin").read_bytes()
    prior = (tools / "build-configured-diagnostic-candidate-r93--default-4mb-no-psram"
             / "RoArm-M3_example.ino.bin").read_bytes()
    app_sha = sha(app)
    if (report.get("status") != "COMPILED" or
            report.get("target") != "configured-diagnostic-candidate-r94" or
            report.get("build_profile") != "default-4mb-no-psram" or
            report.get("artifact_hashes", {}).get("RoArm-M3_example.ino.bin") != app_sha or
            any(sha((root / name).read_bytes()) != digest for name, digest in
                report.get("source_hashes", {}).items()) or
            sha(prior) != R93_SHA or not 0 < len(app) <= 0x140000):
        raise ValueError("r94 compile, source, predecessor or slot differs")
    nm = (tools / "data/packages/esp32/tools/esp-x32/2302/bin"
          / "xtensa-esp32-elf-nm.exe")
    symbols = subprocess.run([str(nm), "-C", str(build / "RoArm-M3_example.ino.elf")],
                             check=True, capture_output=True, text=True, timeout=30).stdout
    if ("GhostTypingBBoard::dispatch" not in symbols or
            any(name in symbols for name in ("webCtrlServer()", "serialCtrl()",
                                            "registerShoulderSessionRoutes()")) or
            b"rocell.ghost_b.v1" not in app):
        raise ValueError("r94 linked command surface differs")
    return dict(schema="rocell.r94_ghost_b_candidate_review.v1",
                status="COMPILED_NOT_INSTALLED", app_sha256=app_sha,
                predecessor_app_sha256=R93_SHA, app_bytes=len(app),
                app_offset=0x10000, app_slot_bytes=0x140000,
                changed_file="diagnostic_boot.h",
                added_file="ghost_typing_b_board.h",
                removed_file="gripper_loading_board.h",
                maximum_legs=5, automatic_progression=False,
                gripper_writes=False, hardware_access=False,
                firmware_uploaded=False, movement_command_sent=False)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    result = review(root, COMPILE_ID)
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r94-ghost-b-candidate-review"}, [],
                            attachments={"r94-ghost-b-review.json": canonical(result)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r94 review export failed")
    print(json.dumps(dict(result=result, export=saved["path"])))
