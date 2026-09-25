"""Offline source, image and command-surface review for r96."""
import hashlib
import json
from pathlib import Path
import subprocess

from rocell.application.registration_ladder_preview import SOURCE_GOALS, TARGET_GOALS
from deploy_r95_bare_hover import APP_SHA as R95_SHA
from stage_r96_registration_ladder import TARGET, sources


COMPILE_ID = "wizard-20260925T190926813115Z-a2f4df52393f4e938f28b442c10a1982"
APP_SHA = "e3ccc4cbd5693bab8116ba65b63be88c186c19e6b44f9a59a7a9e9e07ea9d033"


def review(root: Path) -> dict:
    root = Path(root).resolve(); tools = root / ".firmware-tools"
    expected = sources(root)
    staged = tools / TARGET / "RoArm-M3_example"
    observed = {path.name: path.read_bytes() for path in staged.iterdir() if path.is_file()}
    if observed != expected:
        raise ValueError("r96 staged source differs")
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    prior = (tools / "build-configured-diagnostic-candidate-r95--default-4mb-no-psram"
             / "RoArm-M3_example.ino.bin").read_bytes()
    build = tools / "build-configured-diagnostic-candidate-r96--default-4mb-no-psram"
    app = (build / "RoArm-M3_example.ino.bin").read_bytes()
    report = json.loads((root / "runs/wizard-exports" / COMPILE_ID /
                         "attachment-compile-review.json").read_text())
    if (report.get("status") != "COMPILED" or report.get("target") != TARGET or
            report.get("build_profile") != "default-4mb-no-psram" or
            report.get("artifact_hashes", {}).get("RoArm-M3_example.ino.bin") != APP_SHA or
            any(sha((root / name).read_bytes()) != digest for name, digest in
                report.get("source_hashes", {}).items()) or
            sha(prior) != R95_SHA or sha(app) != APP_SHA or
            not 0 < len(app) <= 0x140000):
        raise ValueError("r96 compile, source, predecessor or bounds differ")
    nm = tools / "data/packages/esp32/tools/esp-x32/2302/bin/xtensa-esp32-elf-nm.exe"
    symbols = subprocess.run([str(nm), "-C", str(build / "RoArm-M3_example.ino.elf")],
                             check=True, capture_output=True, text=True, timeout=30).stdout
    if ("RegistrationLadderBoard::dispatch" not in symbols or
            any(name in symbols for name in ("webCtrlServer()", "serialCtrl()",
                                             "registerShoulderSessionRoutes()")) or
            b"rocell.registration_ladder.v1" not in app or
            b"rocell.bare_gripper_hover.v1" in app):
        raise ValueError("r96 linked command surface differs")
    board = expected["registration_ladder_board.h"]
    for row in (SOURCE_GOALS, TARGET_GOALS):
        if b",".join(str(value).encode() for value in row) not in board:
            raise ValueError("Reviewed r96 source or target missing")
    return dict(schema="rocell.r96_registration_ladder_review.v1",
                status="COMPILED_NOT_INSTALLED", app_sha256=APP_SHA,
                predecessor_app_sha256=R95_SHA, compile_export_id=COMPILE_ID,
                app_bytes=len(app), app_offset=0x10000, app_slot_bytes=0x140000,
                maximum_legs=1, selected_joints=[0], base_step_counts=60,
                automatic_progression=False, startup_motion=False,
                gripper_writes=False, retry_allowed=False, return_movement=False,
                generic_motion_parser=False, hardware_access=False,
                firmware_uploaded=False, movement_command_sent=False)


if __name__ == "__main__":
    print(json.dumps(review(Path(__file__).resolve().parents[1]), indent=2))
