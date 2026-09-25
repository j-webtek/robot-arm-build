"""Offline exact-source review for r62. Does not contact or upload to hardware."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


COMPILE = "wizard-20260923T004133494491Z-9f85eff5009a41c5bf3b93353ed08145"
STAGE = "wizard-20260923T003938781696Z-04680e734bcf44df857eba794f7de478"
APP_SHA = "ee259799cb6b74b80cc4a45e16934ac6476b81d7a4536cc31406fffb766fd6e4"
R61_SHA = "5f713ae53577b3a4dc6a6419f2a3b84563b2db89f903be9c24bc496482f41451"
CHANGED = {
    "characterization_board_services.h", "characterization_composition.h",
    "characterization_smoke_board.h", "large_pose_lift_policy.h",
    "large_pose_lift_owner.h", "large_pose_lift_routes.h",
}


def review(root):
    root = Path(root).resolve();exports = root / "runs/wizard-exports"
    compiled, compile_digest = _read(exports, COMPILE, "attachment-compile-review.json")
    staged, stage_digest = _read(exports, STAGE, "attachment-r62-large-pose-lift-stage.json")
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    old = root / ".firmware-tools/configured-diagnostic-candidate-r61/RoArm-M3_example"
    new = root / ".firmware-tools/configured-diagnostic-candidate-r62/RoArm-M3_example"
    old_files = {p.name: p.read_bytes() for p in old.iterdir() if p.is_file()}
    new_files = {p.name: p.read_bytes() for p in new.iterdir() if p.is_file()}
    changed = {name for name in old_files if old_files[name] != new_files.get(name)}
    changed |= set(new_files) - set(old_files)
    if (compiled["status"] != "COMPILED" or
            compiled["target"] != "configured-diagnostic-candidate-r62" or
            compiled["build_profile"] != "default-4mb-no-psram" or
            set(staged["changed_files"]) != CHANGED or changed != CHANGED or
            staged["targets"] != {"12": 2348, "13": 1766, "15": 1654} or
            staged["maximum_writes"] != 1 or staged["retry_allowed"] or
            staged["return_allowed"]):
        raise ValueError("Pinned r62 evidence differs")
    prefix = ".firmware-tools/configured-diagnostic-candidate-r62/RoArm-M3_example/"
    sources = {name.replace("\\", "/"): digest
               for name, digest in compiled["source_hashes"].items()}
    for name, raw in new_files.items():
        if sources.get(prefix + name) != sha(raw):
            raise ValueError("Compiled r62 source changed")
    board = new_files["characterization_smoke_board.h"]
    owner = new_files["large_pose_lift_owner.h"]
    services = new_files["characterization_board_services.h"]
    if (board.count(b"VisibleIntervalCampaign,false,false,false,true") != 1 or
            owner.count(b"write(uint8_t(12),uint8_t(13),uint8_t(15),uint16_t(2348)") != 1 or
            services.count(b"st.SyncWritePosEx(ids,3,targets,speeds,acc)") != 1):
        raise ValueError("r62 exact route/target binding differs")
    image = (root / ".firmware-tools/build-configured-diagnostic-candidate-r62--default-4mb-no-psram/"
             "RoArm-M3_example.ino.bin").read_bytes()
    identities = (b"/rocell/large-pose-lift/start", b"/rocell/large-pose-lift/receipt",
                  b"RCLIFT0001", b"LARGE_POSE_T1_RECORDED")
    if sha(image) != APP_SHA or len(image) != 1192368 or not all(x in image for x in identities):
        raise ValueError("Compiled r62 application differs")
    for suffix, expected in (
        ("bootloader.bin", "b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7"),
        ("partitions.bin", "148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1")):
        if compiled["artifact_hashes"]["RoArm-M3_example.ino." + suffix] != expected:
            raise ValueError("Boot or partition artifact changed")
    report = {
        "schema": "rocell.r62_large_pose_lift_review.v1",
        "target": "configured-diagnostic-candidate-r62",
        "app_sha256": APP_SHA,
        "app_bytes": len(image),
        "app_offset": 0x10000,
        "app_slot_bytes": 0x140000,
        "app_headroom_bytes": 0x140000 - len(image),
        "predecessor_sha256": R61_SHA,
        "compile_export_id": COMPILE,
        "compile_report_sha256": compile_digest,
        "stage_export_id": STAGE,
        "stage_report_sha256": stage_digest,
        "changed_files": sorted(CHANGED),
        "source_pose": "P0",
        "target_pose": "T1",
        "synchronized_servo_ids": [12, 13, 15],
        "targets": [2348, 1766, 1654],
        "maximum_writes": 1,
        "retry_allowed": False,
        "return_allowed": False,
        "requires_fresh_three_sample_source": True,
        "requires_fresh_three_sample_endpoint": True,
        "requires_durable_export_receipt": True,
        "settings_preserved_by_design": True,
        "hardware_access": False,
        "firmware_uploaded": False,
        "deployment_authorized": False,
    }
    exporter = WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved = exporter.export({"mode": "r62-large-pose-lift-review"}, [], attachments={
        "r62-large-pose-lift-review.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Review export invalid")
    return saved["path"], report


if __name__ == "__main__":
    print(review(Path(__file__).resolve().parents[1])[0])
