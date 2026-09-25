"""Deterministically stage a dedicated, five-leg hover-only app from pinned r94.

This is filesystem-only: it does not compile, install, start or move hardware.
"""
import hashlib
from pathlib import Path

from rocell.application.bare_gripper_hover_preview import (
    SOURCE_GOALS, SOURCE_POSITIONS, TARGETS, preview,
)


TARGET = "configured-diagnostic-candidate-r95"


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    if source.count(old) != 1:
        raise ValueError("Pinned firmware template no longer matches expected shape")
    return source.replace(old, new)


def sources(root: Path) -> dict[str, bytes]:
    root = Path(root).resolve()
    old = root / ".firmware-tools/configured-diagnostic-candidate-r94/RoArm-M3_example"
    files = {path.name: path.read_bytes() for path in old.iterdir() if path.is_file()}
    if "ghost_typing_b_board.h" not in files or "diagnostic_boot.h" not in files:
        raise ValueError("Pinned r94 template files missing")
    board = files.pop("ghost_typing_b_board.h")
    boot = files["diagnostic_boot.h"]
    targets = b"\n".join(
        b"      {" + b",".join(str(value).encode() for value in row) + b"},"
        for row in TARGETS)
    old_targets = (b"""      {1994,2075,2039,2600,2233,2040,1897}, // B clear
      {1994,2093,2021,2618,2197,2040,1897}, // B hover
      {1994,2105,2009,2630,2173,2040,1897}, // virtual down
      {1994,2093,2021,2618,2197,2040,1897}, // retract
      {1994,2075,2039,2600,2233,2040,1897}, // B clear""")
    board = _replace_once(board, old_targets, targets)
    board = _replace_once(board,
        b"static const uint16_t initial_goals[7]={2047,2075,2039,2600,2233,2040,1897};",
        b"static const uint16_t initial_goals[7]={" +
        b",".join(str(value).encode() for value in SOURCE_GOALS) + b"};")
    board = _replace_once(board,
        b"static const uint16_t initial_positions[7]={2046,2079,2036,2605,2235,2041,1893};",
        b"static const uint16_t initial_positions[7]={" +
        b",".join(str(value).encode() for value in SOURCE_POSITIONS) + b"};")
    board = _replace_once(board, b"GhostTypingBBoard", b"BareGripperHoverBoard")
    board = _replace_once(board, b"/rocell/ghost-b/capabilities",
                          b"/rocell/hover-two-region/capabilities")
    board = _replace_once(board, b"rocell.ghost_b.v1",
                          b"rocell.bare_gripper_hover.v1")
    boot = _replace_once(boot, b"ghost_typing_b_board.h",
                         b"bare_gripper_hover_board.h")
    boot = _replace_once(boot, b"GhostTypingBBoard", b"BareGripperHoverBoard")
    files["bare_gripper_hover_board.h"] = board
    files["diagnostic_boot.h"] = boot
    if (b"virtual down" in board or b"ghost_typing_b_board.h" in boot or
            b"webCtrlServer()" in board or b"serialCtrl()" in board):
        raise ValueError("Unexpected r95 movement or parser surface")
    return files


def stage(root: Path) -> dict:
    root = Path(root).resolve()
    preview(root / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf",
            root / "runs/wizard-exports")
    files = sources(root)
    destination = root / ".firmware-tools" / TARGET / "RoArm-M3_example"
    existing = {path.name: path.read_bytes() for path in destination.iterdir()
                if path.is_file()} if destination.exists() else {}
    if existing and existing != files:
        raise ValueError("Existing r95 stage differs; refusing to overwrite")
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        path = destination / name
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(data)
        if path.read_bytes() != data:
            raise ValueError("Staged source readback differs")
    return dict(status="STAGED_OFFLINE_NOT_INSTALLED", target=TARGET,
                source_hashes={name: hashlib.sha256(data).hexdigest()
                               for name, data in files.items()},
                hardware_access=False, motion_authorized=False)


if __name__ == "__main__":
    import json
    print(json.dumps(stage(Path(__file__).resolve().parents[1])))
