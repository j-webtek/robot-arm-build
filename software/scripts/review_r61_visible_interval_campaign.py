"""Offline exact-source and artifact review for r61; no hardware access."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.visible_interval_campaign import plan_visible_interval_campaign
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


COMPILE = "wizard-20260922T223520640680Z-05e034234f474e6993f41fec78cba262"
STAGE = "wizard-20260922T223318549875Z-c870a0f57a5e47a5be7058c71c992b2b"
PLAN_EXPORT = "wizard-20260922T223155774570Z-3eabfb9d99bf4b4c8b7fe6ac7c57eafb"
R60_REVIEW = "wizard-20260922T203245596804Z-4cfdf2e1f7934171aed092479582e7be"
APP_SHA = "5f713ae53577b3a4dc6a6419f2a3b84563b2db89f903be9c24bc496482f41451"
R60_SHA = "6f98f372b5a927b016ae81f0673df1ee8ddd0f0b78bc714d181746e575df7211"
CHANGED = {
    "characterization_prepare.h",
    "characterization_controller.h",
    "shoulder_characterization_owner.h",
    "characterization_smoke_board.h",
}


def review(root):
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    compiled, compile_digest = _read(exports, COMPILE, "attachment-compile-review.json")
    staged, stage_digest = _read(exports, STAGE, "attachment-r61-visible-interval-stage.json")
    saved_plan, plan_digest = _read(exports, PLAN_EXPORT,
                                    "attachment-visible-interval-campaign-plan.json")
    predecessor, predecessor_digest = _read(exports, R60_REVIEW,
                                             "attachment-r60-policy-bound-adapter-review.json")
    plan = plan_visible_interval_campaign()
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    if (saved_plan != plan or staged["plan_sha256"] != plan["plan_sha256"] or
            staged["goals"] != plan["manifest"]["goals"] or
            staged["selector"] != "VisibleIntervalCampaign" or
            staged["park_return_route_enabled"] is not False or
            set(staged["changed_files"]) != CHANGED or
            predecessor["app_sha256"] != R60_SHA or
            compiled["status"] != "COMPILED" or
            compiled["target"] != "configured-diagnostic-candidate-r61" or
            compiled["build_profile"] != "default-4mb-no-psram"):
        raise ValueError("Pinned r61 evidence differs")
    old = root / ".firmware-tools/configured-diagnostic-candidate-r60/RoArm-M3_example"
    new = root / ".firmware-tools/configured-diagnostic-candidate-r61/RoArm-M3_example"
    old_files = {p.name: p.read_bytes() for p in old.iterdir() if p.is_file()}
    new_files = {p.name: p.read_bytes() for p in new.iterdir() if p.is_file()}
    if (set(old_files) != set(new_files) or
            {name for name in old_files if old_files[name] != new_files[name]} != CHANGED):
        raise ValueError("Unreviewed r61 source change")
    board = new_files["characterization_smoke_board.h"]
    if (board.count(b"CharacterizationPattern::VisibleIntervalCampaign,false,false,false") != 1 or
            b"CharacterizationPattern::GhostPairTransitionCampaign,false,false,true" in board):
        raise ValueError("r61 board selector differs")
    if b"const int primary[4]={2401,2389,2401,2413}" not in new_files["characterization_prepare.h"]:
        raise ValueError("r61 prepared target sequence differs")
    if b"const int visible_interval[4]={2401,2389,2401,2413}" not in new_files["shoulder_characterization_owner.h"]:
        raise ValueError("r61 owner allow-list differs")
    prefix = ".firmware-tools/configured-diagnostic-candidate-r61/RoArm-M3_example/"
    sources = {name.replace("\\", "/"): digest
               for name, digest in compiled["source_hashes"].items()}
    for name, raw in new_files.items():
        if sources.get(prefix + name) != sha(raw):
            raise ValueError("Compiled r61 source changed")
    for name in CHANGED:
        if staged["changed_files"][name] != {
                "before": sha(old_files[name]), "after": sha(new_files[name])}:
            raise ValueError("Staged r61 hash delta changed")
    image = (root / ".firmware-tools/build-configured-diagnostic-candidate-r61--default-4mb-no-psram/"
             "RoArm-M3_example.ino.bin").read_bytes()
    if (sha(image) != APP_SHA or len(image) != 1183616 or
            compiled["artifact_hashes"]["RoArm-M3_example.ino.bin"] != APP_SHA or
            not all(identity in image for identity in (
                b"/rocell/characterization/start",
                b"/rocell/characterization/receipt",
                b"/rocell/characterization/record-info"))):
        raise ValueError("Compiled r61 application differs")
    for suffix, expected in (
            ("bootloader.bin", "b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7"),
            ("partitions.bin", "148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1")):
        if compiled["artifact_hashes"]["RoArm-M3_example.ino." + suffix] != expected:
            raise ValueError("Boot or partition artifact changed")
    report = {
        "schema": "rocell.r61_visible_interval_review.v1",
        "target": "configured-diagnostic-candidate-r61",
        "app_sha256": APP_SHA,
        "app_bytes": len(image),
        "app_offset": 0x10000,
        "app_slot_bytes": 0x140000,
        "app_headroom_bytes": 0x140000-len(image),
        "predecessor_sha256": R60_SHA,
        "predecessor_review_id": R60_REVIEW,
        "predecessor_review_sha256": predecessor_digest,
        "compile_export_id": COMPILE,
        "compile_report_sha256": compile_digest,
        "stage_export_id": STAGE,
        "stage_report_sha256": stage_digest,
        "plan_export_id": PLAN_EXPORT,
        "plan_report_sha256": plan_digest,
        "plan_sha256": plan["plan_sha256"],
        "changed_files": sorted(CHANGED),
        "goals": plan["manifest"]["goals"],
        "maximum_writes": 4,
        "one_write_per_leg": True,
        "retry_allowed": False,
        "park_return_route_enabled": False,
        "settings_preserved_by_design": True,
        "hardware_access": False,
        "firmware_uploaded": False,
        "deployment_authorized": False,
    }
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r61-visible-interval-review"}, [], attachments={
        "r61-visible-interval-review.json": canonical(report),
    })
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r61 review export invalid")
    return saved["path"], report


if __name__ == "__main__":
    print(review(Path(__file__).resolve().parents[1])[0])
