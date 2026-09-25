"""Stage r61 four-leg campaign from exact reviewed r60 source; offline only."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.visible_interval_campaign import plan_visible_interval_campaign
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R60_COMPILE = "wizard-20260922T203120491645Z-474a80e233d44303a95718d8188c0f2c"
PLAN_EXPORT = "wizard-20260922T223155774570Z-3eabfb9d99bf4b4c8b7fe6ac7c57eafb"
HEADERS = (
    "characterization_prepare.h",
    "characterization_controller.h",
    "shoulder_characterization_owner.h",
)


def stage(root):
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    compiled, compile_receipt = _read(exports, R60_COMPILE, "attachment-compile-review.json")
    saved_plan, plan_receipt = _read(exports, PLAN_EXPORT,
                                     "attachment-visible-interval-campaign-plan.json")
    plan = plan_visible_interval_campaign()
    if saved_plan != plan:
        raise ValueError("Pinned visible interval plan differs")
    prefix = ".firmware-tools/configured-diagnostic-candidate-r60/RoArm-M3_example/"
    source = root / prefix
    files = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
    expected = {Path(path).name: digest for path, digest in compiled["source_hashes"].items()
                if path.replace("\\", "/").startswith(prefix)}
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    if (compiled["status"] != "COMPILED" or
            compiled["target"] != "configured-diagnostic-candidate-r60" or
            set(files) != set(expected) or
            any(sha(raw) != expected[name] for name, raw in files.items())):
        raise ValueError("Pinned r60 source differs")
    before = {name: sha(raw) for name, raw in files.items()}
    for name in HEADERS:
        files[name] = (root / "firmware/diagnostics" / name).read_bytes()
    board = "characterization_smoke_board.h"
    old = (b"CharacterizationPattern::GhostPairTransitionCampaign,false,false,true")
    new = (b"CharacterizationPattern::VisibleIntervalCampaign,false,false,false")
    if files[board].count(old) != 1:
        raise ValueError("Expected one exact r60 board selector")
    files[board] = files[board].replace(old, new)
    changes = {name: {"before": before[name], "after": sha(raw)}
               for name, raw in files.items() if before[name] != sha(raw)}
    if set(changes) != set(HEADERS) | {board}:
        raise ValueError("Unexpected r61 source change set")
    target = root / ".firmware-tools/configured-diagnostic-candidate-r61/RoArm-M3_example"
    target.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (target / name).open("xb") as stream:
            stream.write(raw)
        if (target / name).read_bytes() != raw:
            raise ValueError("r61 staged source readback differs")
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r61-visible-interval-stage"}, [], attachments={
        "r61-visible-interval-stage.json": canonical({
            "revision": 61,
            "predecessor_revision": 60,
            "predecessor_compile_receipt": compile_receipt,
            "plan_export_id": PLAN_EXPORT,
            "plan_receipt": plan_receipt,
            "plan_sha256": plan["plan_sha256"],
            "changed_files": changes,
            "selector": "VisibleIntervalCampaign",
            "goals": plan["manifest"]["goals"],
            "park_return_route_enabled": False,
            "hardware_access": False,
            "uploaded": False,
            "settings_changed": False,
            "deployable": False,
        })
    })
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r61 stage export invalid")
    return saved["path"]


if __name__ == "__main__":
    print(stage(Path(__file__).resolve().parents[1]))
