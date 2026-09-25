"""Offline source, image and command-surface review for r95 hover app."""
import hashlib
import json
from pathlib import Path
import subprocess

from rocell.application.bare_gripper_hover_preview import SOURCE_GOALS, TARGETS
from stage_r95_bare_hover import sources, TARGET
from deploy_r94_ghost_b import APP_SHA as R94_SHA

COMPILE_ID = "wizard-20260925T174236165422Z-825e4504233d47118ac7000b8162098b"
APP_SHA = "d4aafbbb0ede6e93f7085fe07eb7a064344120f9493a423f5d2e2eb65aa73045"


def review(root: Path) -> dict:
    root = Path(root).resolve()
    tools = root / ".firmware-tools"
    expected = sources(root)
    staged = tools / TARGET / "RoArm-M3_example"
    observed = {path.name: path.read_bytes() for path in staged.iterdir() if path.is_file()}
    if observed != expected:
        raise ValueError("r95 source differs from deterministic hover stage")
    prior = (tools / "build-configured-diagnostic-candidate-r94--default-4mb-no-psram"
             / "RoArm-M3_example.ino.bin").read_bytes()
    build = tools / "build-configured-diagnostic-candidate-r95--default-4mb-no-psram"
    app = (build / "RoArm-M3_example.ino.bin").read_bytes()
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    report = json.loads((root / "runs/wizard-exports" / COMPILE_ID /
                         "attachment-compile-review.json").read_text())
    if (report.get("status") != "COMPILED" or report.get("target") != TARGET or
            report.get("build_profile") != "default-4mb-no-psram" or
            report.get("artifact_hashes", {}).get("RoArm-M3_example.ino.bin") != APP_SHA or
            any(sha((root / name).read_bytes()) != digest for name, digest in
                report.get("source_hashes", {}).items()) or
            sha(prior) != R94_SHA or sha(app) != APP_SHA or
            not 0 < len(app) <= 0x140000):
        raise ValueError("r95 compile, source, predecessor or app-slot bounds differ")
    nm = tools / "data/packages/esp32/tools/esp-x32/2302/bin/xtensa-esp32-elf-nm.exe"
    symbols = subprocess.run([str(nm), "-C", str(build / "RoArm-M3_example.ino.elf")],
                             check=True, capture_output=True, text=True, timeout=30).stdout
    if ("BareGripperHoverBoard::dispatch" not in symbols or
            any(name in symbols for name in ("webCtrlServer()", "serialCtrl()",
                                            "registerShoulderSessionRoutes()")) or
            b"rocell.bare_gripper_hover.v1" not in app or
            b"rocell.ghost_b.v1" in app):
        raise ValueError("r95 linked command surface differs")
    board = expected["bare_gripper_hover_board.h"]
    for row in TARGETS:
        literal = b"{" + b",".join(str(v).encode() for v in row) + b"}"
        if literal not in board:
            raise ValueError("Reviewed hover target missing")
    if b",".join(str(v).encode() for v in SOURCE_GOALS) not in board:
        raise ValueError("Reviewed source goals missing")
    return dict(schema="rocell.r95_bare_gripper_hover_review.v1",
                status="COMPILED_NOT_INSTALLED", app_sha256=APP_SHA,
                predecessor_app_sha256=R94_SHA, app_bytes=len(app),
                app_offset=0x10000, app_slot_bytes=0x140000,
                maximum_legs=5, automatic_progression=False,
                gripper_writes=False, startup_motion=False,
                generic_motion_parser=False, hardware_access=False,
                firmware_uploaded=False, movement_command_sent=False)


if __name__ == "__main__":
    print(json.dumps(review(Path(__file__).resolve().parents[1])))
