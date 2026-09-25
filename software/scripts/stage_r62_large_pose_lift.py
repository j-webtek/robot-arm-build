"""Pin reviewed r61 source and stage exact P0 -> T1 lift offline; never upload."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R61_COMPILE = "wizard-20260922T223520640680Z-05e034234f474e6993f41fec78cba262"
PLAN_EXPORT = "wizard-20260923T002558386911Z-d2593a863cfa467697466277d00d2bc8"
OVERLAY = (
    "characterization_board_services.h",
    "characterization_composition.h",
    "large_pose_lift_policy.h",
    "large_pose_lift_owner.h",
    "large_pose_lift_routes.h",
)


def stage(root):
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    compiled, compile_receipt = _read(exports, R61_COMPILE, "attachment-compile-review.json")
    plan, plan_receipt = _read(exports, PLAN_EXPORT, "attachment-large-pose-ladder.json")
    prefix = ".firmware-tools/configured-diagnostic-candidate-r61/RoArm-M3_example/"
    source = root / prefix
    files = {path.name: path.read_bytes() for path in source.iterdir() if path.is_file()}
    expected = {Path(path).name: digest for path, digest in compiled["source_hashes"].items()
                if path.replace("\\", "/").startswith(prefix)}
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    if (compiled["status"] != "COMPILED" or
            compiled["target"] != "configured-diagnostic-candidate-r61" or
            set(files) != set(expected) or
            any(sha(raw) != expected[name] for name, raw in files.items())):
        raise ValueError("Pinned r61 source differs")
    changed = {}
    for name in OVERLAY:
        old = files.get(name)
        new = (root / "firmware/diagnostics" / name).read_bytes()
        files[name] = new
        changed[name] = {"before": sha(old) if old is not None else None, "after": sha(new)}
    board = "characterization_smoke_board.h"
    old = files[board]
    needle = (b"CharacterizationPattern::VisibleIntervalCampaign,false,false,false" b"))")
    replacement = (b"CharacterizationPattern::VisibleIntervalCampaign,false,false,false,true" b"))")
    if old.count(needle) != 1:
        raise ValueError("Expected one exact r61 composition call")
    files[board] = old.replace(needle, replacement)
    changed[board] = {"before": sha(old), "after": sha(files[board])}
    target = root / ".firmware-tools/configured-diagnostic-candidate-r62/RoArm-M3_example"
    target.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (target / name).open("xb") as stream:
            stream.write(raw)
        if (target / name).read_bytes() != raw:
            raise ValueError("Staged source readback differs")
    exporter = WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved = exporter.export({"mode": "r62-large-pose-lift-stage"}, [], attachments={
        "r62-large-pose-lift-stage.json": canonical({
            "revision": 62,
            "predecessor_revision": 61,
            "predecessor_compile_receipt": compile_receipt,
            "plan_export_id": PLAN_EXPORT,
            "plan_receipt": plan_receipt,
            "plan_report_sha256": plan_receipt,
            "changed_files": changed,
            "route": "/rocell/large-pose-lift/start",
            "selector_body": "T1",
            "source_goals": [2047, 2413, 1701, 2907, 1589, 2040, 2047],
            "targets": {"12": 2348, "13": 1766, "15": 1654},
            "maximum_writes": 1,
            "retry_allowed": False,
            "return_allowed": False,
            "hardware_access": False,
            "uploaded": False,
            "settings_changed": False,
            "deployable": False,
        })
    })
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Stage export invalid")
    return saved["path"]


if __name__ == "__main__":
    print(stage(Path(__file__).resolve().parents[1]))
