"""Offline exact-source, sweep and binary review of fixed r78 A-side candidate."""
import hashlib
from pathlib import Path

from stage_r78_air_typing import R77_APP_SHA,specialize
from rocell.application.air_typing_r78_campaign import SOURCE_GOALS,SOURCE_POSITIONS,TARGETS
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


STAGE="wizard-20260924T233457475664Z-a35effc34da845cd86b850946a22dcf1"
COMPILE="wizard-20260924T233709349019Z-1f08fee57ede4a908e054c28210bdd46"
PREVIEW="wizard-20260924T233822573622Z-6f96c934249c456286692c252001e0a0"
APP_SHA="3b9989e03cd64690e831049c4e19ff38d6c10ab6e2c6c22f3ad1d7e61e1f3aaa"
APP_BYTES=1204848


def review(root):
    root=Path(root).resolve();exports=root/"runs/wizard-exports"
    compiled,compile_digest=_read(exports,COMPILE,"attachment-compile-review.json")
    staged,stage_digest=_read(exports,STAGE,"attachment-r78-air-typing-stage.json")
    sweep,sweep_digest=_read(exports,PREVIEW,"attachment-r78-air-typing-preview.json")
    sha=lambda data:hashlib.sha256(data).hexdigest()
    old=root/".firmware-tools/configured-diagnostic-candidate-r77/RoArm-M3_example"
    expected=specialize({p.name:p.read_bytes() for p in old.iterdir() if p.is_file()},root)
    target=root/".firmware-tools/configured-diagnostic-candidate-r78/RoArm-M3_example"
    actual={p.name:p.read_bytes() for p in target.iterdir() if p.is_file()}
    prefix=".firmware-tools/configured-diagnostic-candidate-r78/RoArm-M3_example/"
    source_hashes={p.replace("\\","/"):h for p,h in compiled["source_hashes"].items()}
    if (actual!=expected or compiled["status"]!="COMPILED"
            or compiled["target"]!="configured-diagnostic-candidate-r78"
            or compiled["build_profile"]!="default-4mb-no-psram"
            or any(source_hashes.get(prefix+name)!=sha(data) for name,data in actual.items())
            or staged["predecessor_revision"]!=77 or staged["selector"]!="AIR4"
            or staged["maximum_writes"]!=4
            or staged["source_goals"]!=list(SOURCE_GOALS)
            or staged["source_positions"]!=list(SOURCE_POSITIONS)
            or sweep["status"]!="OFFLINE_R78_SWEEP_PASS_NOT_EXECUTABLE"
            or [row["goals"] for row in sweep["legs"]]!=[list(row) for row in TARGETS]):
        raise ValueError("r78 staged source or sweep differs")
    build=root/".firmware-tools/build-configured-diagnostic-candidate-r78--default-4mb-no-psram"
    image=(build/"RoArm-M3_example.ino.bin").read_bytes()
    if (sha(image)!=APP_SHA or len(image)!=APP_BYTES or len(image)>0x140000
            or compiled["artifact_hashes"]["RoArm-M3_example.ino.bin"]!=APP_SHA
            or not all(marker in image for marker in
                       (b"RCAIRAB401",b"/rocell/air-type-last/start",b"/rocell/air-type-last/source-fault",b"AIR4"))
            or b"/rocell/air-type-final/start" in image or b"AIR7" in image):
        raise ValueError("r78 app image differs")
    for suffix,digest in (("bootloader.bin","b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7"),
                          ("partitions.bin","148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1")):
        name="RoArm-M3_example.ino."+suffix
        if sha((build/name).read_bytes())!=digest or compiled["artifact_hashes"][name]!=digest:
            raise ValueError("Protected build artifact differs")
    report=dict(schema="rocell.r78_air_typing_review.v1",
        target="configured-diagnostic-candidate-r78",app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=77,predecessor_sha256=R77_APP_SHA,
        compile_export_id=COMPILE,compile_report_sha256=compile_digest,
        stage_export_id=STAGE,stage_report_sha256=stage_digest,
        sweep_export_id=PREVIEW,sweep_report_sha256=sweep_digest,
        selector="AIR4",maximum_writes=4,source_goals=list(SOURCE_GOALS),
        source_positions=list(SOURCE_POSITIONS),targets=[list(row) for row in TARGETS],
        synchronized_servo_ids=[11,12,13,14,15,16,17],
        source_drift_cap_counts=3,source_goal_error_cap_counts=12,
        source_failure_record_route="/rocell/air-type-last/source-fault",
        requires_durable_export_receipt=True,retry_allowed=False,
        settings_preserved_by_design=True,hardware_access=False,
        firmware_uploaded=False,deployment_authorized=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({"mode":"r78-air-typing-review"},[],attachments={
        "r78-air-typing-review.json":canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:raise ValueError("Review export invalid")
    return saved["path"]


if __name__=="__main__":print(review(Path(__file__).resolve().parents[1]))
