"""Stage a dedicated five-leg ghost-B app from pinned r93; no device I/O."""
import hashlib
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

if __package__:
    from .review_r93_gripper_candidate import review, APP_SHA
else:
    from review_r93_gripper_candidate import review, APP_SHA

TARGET = "configured-diagnostic-candidate-r94"


def stage(root: Path) -> dict:
    root = Path(root).resolve()
    review(root)
    tools = root / ".firmware-tools"
    old = tools / "configured-diagnostic-candidate-r93/RoArm-M3_example"
    new = tools / TARGET / "RoArm-M3_example"
    files = {path.name: path.read_bytes() for path in old.iterdir() if path.is_file()}
    if "gripper_loading_board.h" not in files:
        raise ValueError("Pinned r93 gripper board missing")
    del files["gripper_loading_board.h"]
    diagnostics = root / "firmware/diagnostics"
    files["diagnostic_boot.h"] = (diagnostics / "ghost_typing_b_boot.h").read_bytes()
    files["ghost_typing_b_board.h"] = (diagnostics / "ghost_typing_b_board.h").read_bytes()
    if (b'#include "ghost_typing_b_board.h"' not in files["diagnostic_boot.h"] or
            b"SyncWritePosEx(ids,uint8_t(count)" not in files["ghost_typing_b_board.h"] or
            b"if(i==6||" not in files["ghost_typing_b_board.h"] or
            b"automatic_progression\\\":false" not in files["ghost_typing_b_board.h"]):
        raise ValueError("Dedicated route shape differs")
    existing = {path.name: path.read_bytes() for path in new.iterdir()
                if path.is_file()} if new.exists() else {}
    if existing and existing != files:
        raise ValueError("Existing r94 stage differs; no overwrite")
    new.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        path = new / name
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(data)
        if path.read_bytes() != data:
            raise ValueError("r94 staged source readback differs")
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    report = dict(schema="rocell.r94_ghost_b_stage.v1",
                  status="STAGED_OFFLINE", predecessor_app_sha256=APP_SHA,
                  target=TARGET, changed_boot_sha256=sha(files["diagnostic_boot.h"]),
                  added_board_sha256=sha(files["ghost_typing_b_board.h"]),
                  maximum_legs=5, automatic_progression=False,
                  gripper_writes=False, hardware_access=False,
                  firmware_uploaded=False, deployable=False)
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r94-ghost-b-stage"}, [],
        attachments={"r94-ghost-b-stage.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r94 stage export invalid")
    return dict(report=report, export=saved["path"])


if __name__ == "__main__":
    print(json.dumps(stage(Path(__file__).resolve().parents[1])))
