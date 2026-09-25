"""Deterministically stage one finite r96 registration leg from pinned r95.

Filesystem-only: this script does not compile, install, start or move hardware.
"""
import hashlib
from pathlib import Path

from rocell.application.registration_ladder_preview import (
    SOURCE_GOALS, SOURCE_POSITIONS, TARGET_GOALS, preview,
)


TARGET = "configured-diagnostic-candidate-r96"


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    if source.count(old) != 1:
        raise ValueError("Pinned r95 template no longer matches")
    return source.replace(old, new)


def _literal(values) -> bytes:
    return b",".join(str(value).encode() for value in values)


def sources(root: Path) -> dict[str, bytes]:
    root = Path(root).resolve()
    old = root / ".firmware-tools/configured-diagnostic-candidate-r95/RoArm-M3_example"
    files = {path.name: path.read_bytes() for path in old.iterdir() if path.is_file()}
    board = files.pop("bare_gripper_hover_board.h")
    boot = files["diagnostic_boot.h"]
    old_targets = b"""    static const uint16_t targets[5][7]={
      {1994,2093,2021,2618,2197,2040,1897},
      {1994,2075,2039,2600,2233,2040,1897},
      {2047,2075,2039,2600,2233,2040,1897},
      {2047,2093,2021,2618,2197,2040,1897},
      {2047,2075,2039,2600,2233,2040,1897},
    };"""
    new_targets = (b"    static const uint16_t targets[1][7]={{" +
                   _literal(TARGET_GOALS) + b"}};")
    board = _replace_once(board, old_targets, new_targets)
    board = _replace_once(board, b"return index<5?targets[index]:nullptr;",
                          b"return index<1?targets[index]:nullptr;")
    board = _replace_once(board, b"if(next_leg_>=5||sent_||faulted_||!snapshot_valid_)",
                          b"if(next_leg_>=1||sent_||faulted_||!snapshot_valid_)")
    board = _replace_once(board, b"bool attempted_[5]{}", b"bool attempted_[1]{}")
    board = _replace_once(board, b'\\"maximum_legs\\":5',
                          b'\\"maximum_legs\\":1')
    board = _replace_once(board,
        b"static const uint16_t initial_goals[7]={1994,2075,2039,2600,2233,2040,1897};",
        b"static const uint16_t initial_goals[7]={" + _literal(SOURCE_GOALS) + b"};")
    board = _replace_once(board,
        b"static const uint16_t initial_positions[7]={2001,2082,2033,2609,2233,2041,1900};",
        b"static const uint16_t initial_positions[7]={" + _literal(SOURCE_POSITIONS) + b"};")
    board = _replace_once(board, b"BareGripperHoverBoard", b"RegistrationLadderBoard")
    board = _replace_once(board, b"/rocell/hover-two-region/capabilities",
                          b"/rocell/registration-ladder/capabilities")
    board = _replace_once(board, b"rocell.bare_gripper_hover.v1",
                          b"rocell.registration_ladder.v1")
    board = _replace_once(board,
        b"// Dedicated, manually gated B-key ghost cycle. No generic motion parser.",
        b"// Dedicated one-leg high-clear registration step. No generic motion parser.")
    boot = _replace_once(boot, b"bare_gripper_hover_board.h",
                         b"registration_ladder_board.h")
    boot = _replace_once(boot, b"BareGripperHoverBoard", b"RegistrationLadderBoard")
    files["registration_ladder_board.h"] = board
    files["diagnostic_boot.h"] = boot
    if (b"targets[5]" in board or b"next_leg_>=5" in board or
            b"webCtrlServer()" in board or b"serialCtrl()" in board or
            _literal(TARGET_GOALS) not in board):
        raise ValueError("Unexpected r96 movement or parser surface")
    return files


def stage(root: Path) -> dict:
    root = Path(root).resolve()
    result = preview(root / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf")
    files = sources(root)
    destination = root / ".firmware-tools" / TARGET / "RoArm-M3_example"
    existing = ({path.name: path.read_bytes() for path in destination.iterdir()
                 if path.is_file()} if destination.exists() else {})
    if existing and existing != files:
        raise ValueError("Existing r96 stage differs; refusing to overwrite")
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        path = destination / name
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(data)
        if path.read_bytes() != data:
            raise ValueError("Staged r96 source readback differs")
    return dict(status="STAGED_OFFLINE_NOT_INSTALLED", target=TARGET,
                preview=result,
                source_hashes={name: hashlib.sha256(data).hexdigest()
                               for name, data in files.items()},
                hardware_access=False, motion_authorized=False)


if __name__ == "__main__":
    import json
    print(json.dumps(stage(Path(__file__).resolve().parents[1]), indent=2))
