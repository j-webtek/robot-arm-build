"""Offline-only r93 gripper-loader source and linked-image review."""
import hashlib
import json
from pathlib import Path
import subprocess

from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from rocell.application.first_motion_contract import canonical

COMPILE_ID = "wizard-20260925T150537999690Z-d1d053347bda48da944da9d6054fe3ed"
APP_SHA = "8e261c27749c66b3db4c8e8564cdb6d4a42ed9c3ca8867cb19cac5503c649a9b"
R92_SHA = "6d649c3c89f9642d656c62df8a62f6e3e4ba18a3923e682485839b94f7680c15"


def review(root: Path) -> dict:
    root = Path(root).resolve()
    tools = root / ".firmware-tools"
    old = tools / "configured-diagnostic-candidate-r92/RoArm-M3_example"
    new = tools / "configured-diagnostic-candidate-r93/RoArm-M3_example"
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    old_files = {p.name: p.read_bytes() for p in old.iterdir() if p.is_file()}
    new_files = {p.name: p.read_bytes() for p in new.iterdir() if p.is_file()}
    if (set(new_files) != set(old_files) or
            [name for name in sorted(new_files) if new_files[name] != old_files[name]] !=
            ["gripper_loading_board.h"] or
            new_files["gripper_loading_board.h"] !=
            (root / "firmware/diagnostics/gripper_loading_board.h").read_bytes()):
        raise ValueError("r93 source differs beyond gripper-only board")
    report = json.loads((root / "runs/wizard-exports" / COMPILE_ID /
                         "attachment-compile-review.json").read_text())
    if (report.get("status") != "COMPILED" or
            report.get("target") != "configured-diagnostic-candidate-r93" or
            report.get("build_profile") != "default-4mb-no-psram" or
            report.get("artifact_hashes", {}).get("RoArm-M3_example.ino.bin") != APP_SHA or
            any(sha((root / name).read_bytes()) != digest for name, digest in
                report.get("source_hashes", {}).items())):
        raise ValueError("r93 compile evidence differs")
    build = tools / "build-configured-diagnostic-candidate-r93--default-4mb-no-psram"
    app = (build / "RoArm-M3_example.ino.bin").read_bytes()
    prior = (tools / "build-configured-diagnostic-candidate-r92--default-4mb-no-psram"
             / "RoArm-M3_example.ino.bin").read_bytes()
    if sha(app) != APP_SHA or sha(prior) != R92_SHA or not 0 < len(app) <= 0x140000:
        raise ValueError("r93 app slot or predecessor differs")
    nm = (tools / "data/packages/esp32/tools/esp-x32/2302/bin"
          / "xtensa-esp32-elf-nm.exe")
    symbols = subprocess.run([str(nm), "-C", str(build / "RoArm-M3_example.ino.elf")],
                             check=True, capture_output=True, text=True, timeout=30).stdout
    if ("GripperLoadingBoard::dispatch" not in symbols or
            any(name in symbols for name in ("webCtrlServer()", "serialCtrl()",
                                            "registerShoulderSessionRoutes()")) or
            b"rocell.gripper_loader.v2" not in app):
        raise ValueError("r93 linked command surface differs")
    return dict(schema="rocell.r93_gripper_candidate_review.v1",
                status="COMPILED_NOT_INSTALLED", app_sha256=APP_SHA,
                predecessor_app_sha256=R92_SHA, app_bytes=len(app),
                app_offset=0x10000, app_slot_bytes=0x140000,
                changed_file="gripper_loading_board.h",
                one_open_write_max=True, manual_close_steps_max=4,
                automatic_close=False, other_joint_writes=False,
                firmware_uploaded=False, movement_command_sent=False)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    result = review(root)
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r93-gripper-candidate-review"}, [],
                            attachments={"r93-gripper-review.json": canonical(result)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r93 review export failed")
    print(json.dumps(dict(result=result, export=saved["path"])))
