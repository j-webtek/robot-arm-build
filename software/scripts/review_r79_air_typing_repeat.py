"""Offline exact-source, sweep, native-test and binary review of r79."""
import hashlib
from pathlib import Path

from stage_r79_air_typing_repeat import R78_APP_SHA,specialize
from rocell.application.air_typing_repeat_recipe import (
    SOURCE_GOALS,SOURCE_POSITIONS,TARGETS,validate_recipe,
)
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


STAGE="wizard-20260925T003919824019Z-fe209814a52e44598848ca84a2dab214"
COMPILE="wizard-20260925T004112893722Z-c5239fb3d8314cc7b534c1ee70134e88"
PREVIEW="wizard-20260925T003809476577Z-68c0aaffc48140e7ac466642e87cb77b"
APP_SHA="f82f1f87e6e9917dfdf2e9c60c30aaedf18025bdbd3b9777600b46a1458f7e82"
APP_BYTES=1204896


def review(root):
    validate_recipe();root=Path(root).resolve();exports=root/"runs/wizard-exports"
    compiled,compile_digest=_read(exports,COMPILE,"attachment-compile-review.json")
    staged,stage_digest=_read(exports,STAGE,"attachment-r79-air-typing-repeat-stage.json")
    sweep,sweep_digest=_read(exports,PREVIEW,"attachment-air-typing-repeat-preview.json")
    sha=lambda data:hashlib.sha256(data).hexdigest()
    old=root/".firmware-tools/configured-diagnostic-candidate-r78/RoArm-M3_example"
    expected=specialize({p.name:p.read_bytes() for p in old.iterdir() if p.is_file()},root)
    target=root/".firmware-tools/configured-diagnostic-candidate-r79/RoArm-M3_example"
    actual={p.name:p.read_bytes() for p in target.iterdir() if p.is_file()}
    prefix=".firmware-tools/configured-diagnostic-candidate-r79/RoArm-M3_example/"
    source_hashes={p.replace("\\","/"):h for p,h in compiled["source_hashes"].items()}
    if (actual!=expected or compiled["status"]!="COMPILED"
            or compiled["target"]!="configured-diagnostic-candidate-r79"
            or compiled["build_profile"]!="default-4mb-no-psram"
            or any(source_hashes.get(prefix+name)!=sha(data) for name,data in actual.items())
            or staged["predecessor_revision"]!=78 or staged["selector"]!="AIR6"
            or staged["maximum_writes"]!=6 or staged["source_goals"]!=list(SOURCE_GOALS)
            or staged["source_positions"]!=list(SOURCE_POSITIONS)
            or staged["targets"]!=[list(row) for row in TARGETS]
            or sweep["status"]!="OFFLINE_REPEAT_SWEEP_PASS_NOT_EXECUTABLE"
            or [row["goals"] for row in sweep["legs"]]!=[list(row) for row in TARGETS]):
        raise ValueError("r79 staged source or sweep differs")
    build=root/".firmware-tools/build-configured-diagnostic-candidate-r79--default-4mb-no-psram"
    image=(build/"RoArm-M3_example.ino.bin").read_bytes()
    if (sha(image)!=APP_SHA or len(image)!=APP_BYTES or len(image)>0x140000
            or compiled["artifact_hashes"]["RoArm-M3_example.ino.bin"]!=APP_SHA
            or not all(marker in image for marker in
                       (b"RCAIRAB501",b"/rocell/air-type-repeat/start",
                        b"/rocell/air-type-repeat/source-fault",b"AIR6"))
            or b"/rocell/air-type-last/start" in image or b"AIR4" in image):
        raise ValueError("r79 app image differs")
    for suffix,digest in (("bootloader.bin","b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7"),
                          ("partitions.bin","148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1")):
        name="RoArm-M3_example.ino."+suffix
        if sha((build/name).read_bytes())!=digest or compiled["artifact_hashes"][name]!=digest:
            raise ValueError("Protected artifact differs")
    report=dict(schema="rocell.r79_air_typing_repeat_review.v1",
        target="configured-diagnostic-candidate-r79",app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=78,predecessor_sha256=R78_APP_SHA,
        compile_export_id=COMPILE,compile_report_sha256=compile_digest,
        stage_export_id=STAGE,stage_report_sha256=stage_digest,
        sweep_export_id=PREVIEW,sweep_report_sha256=sweep_digest,
        selector="AIR6",maximum_writes=6,source_goals=list(SOURCE_GOALS),
        source_positions=list(SOURCE_POSITIONS),targets=[list(row) for row in TARGETS],
        synchronized_servo_ids=[11,12,13,14,15,16,17],
        source_drift_cap_counts=3,source_goal_error_cap_counts=12,
        source_failure_record_route="/rocell/air-type-repeat/source-fault",
        requires_durable_export_receipt=True,retry_allowed=False,
        settings_preserved_by_design=True,hardware_access=False,
        firmware_uploaded=False,deployment_authorized=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({"mode":"r79-air-typing-repeat-review"},[],attachments={
        "r79-air-typing-repeat-review.json":canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Review export invalid")
    return saved["path"]


if __name__=="__main__":print(review(Path(__file__).resolve().parents[1]))
