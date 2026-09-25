"""Offline exact-source, sweep, native-test and binary review of r82."""
import hashlib
from pathlib import Path

from stage_r82_elbow_shift import R81_APP_SHA,specialize
from rocell.application.air_typing_elbow_shift_recipe import (
    SOURCE_GOALS,SOURCE_POSITIONS,TARGETS,validate_recipe,
)
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


STAGE="wizard-20260925T012253606744Z-ed92c4b250d5436db8144478d13a00e1"
COMPILE="wizard-20260925T012447190813Z-f18765fe88f6420aab1cce1858c03903"
PREVIEW="wizard-20260925T012204312726Z-dea966e979534a8fa9aad73b673d6d3a"
APP_SHA="0be3db4edf21396c881ee9eeee62f625bc99ebaf33bf96b35656c5dffd3a937c"
APP_BYTES=1204912


def review(root):
    validate_recipe();root=Path(root).resolve();exports=root/"runs/wizard-exports"
    compiled,compile_digest=_read(exports,COMPILE,"attachment-compile-review.json")
    staged,stage_digest=_read(exports,STAGE,"attachment-r82-elbow-shift-stage.json")
    sweep,sweep_digest=_read(exports,PREVIEW,"attachment-air-typing-elbow-shift-preview.json")
    sha=lambda data:hashlib.sha256(data).hexdigest()
    old=root/".firmware-tools/configured-diagnostic-candidate-r81/RoArm-M3_example"
    expected=specialize({p.name:p.read_bytes() for p in old.iterdir() if p.is_file()})
    target=root/".firmware-tools/configured-diagnostic-candidate-r82/RoArm-M3_example"
    actual={p.name:p.read_bytes() for p in target.iterdir() if p.is_file()}
    prefix=".firmware-tools/configured-diagnostic-candidate-r82/RoArm-M3_example/"
    source_hashes={p.replace("\\","/"):h for p,h in compiled["source_hashes"].items()}
    if (actual!=expected or compiled["status"]!="COMPILED"
            or compiled["target"]!="configured-diagnostic-candidate-r82"
            or compiled["build_profile"]!="default-4mb-no-psram"
            or any(source_hashes.get(prefix+name)!=sha(data) for name,data in actual.items())
            or staged["predecessor_revision"]!=81 or staged["selector"]!="AIRH8"
            or staged["maximum_writes"]!=8 or staged["source_goals"]!=list(SOURCE_GOALS)
            or staged["source_positions"]!=list(SOURCE_POSITIONS)
            or staged["targets"]!=[list(row) for row in TARGETS]
            or sweep["status"]!="OFFLINE_ELBOW_SHIFT_SWEEP_PASS_NOT_EXECUTABLE"
            or [row["goals"] for row in sweep["legs"]]!=[list(row) for row in TARGETS]):
        raise ValueError("r82 staged source or sweep differs")
    build=root/".firmware-tools/build-configured-diagnostic-candidate-r82--default-4mb-no-psram"
    image=(build/"RoArm-M3_example.ino.bin").read_bytes()
    if (sha(image)!=APP_SHA or len(image)!=APP_BYTES or len(image)>0x140000
            or compiled["artifact_hashes"]["RoArm-M3_example.ino.bin"]!=APP_SHA
            or not all(marker in image for marker in
                       (b"RCAIRAB801",b"/rocell/air-elbow-shift/start",
                        b"/rocell/air-elbow-shift/source-fault",b"AIRH8"))
            or b"/rocell/air-elbow-direction/start" in image or b"AIRE8" in image):
        raise ValueError("r82 app image differs")
    for suffix,digest in (("bootloader.bin","b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7"),
                          ("partitions.bin","148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1")):
        name="RoArm-M3_example.ino."+suffix
        if sha((build/name).read_bytes())!=digest or compiled["artifact_hashes"][name]!=digest:
            raise ValueError("Protected artifact differs")
    report=dict(schema="rocell.r82_elbow_shift_review.v1",
        target="configured-diagnostic-candidate-r82",app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=81,predecessor_sha256=R81_APP_SHA,
        compile_export_id=COMPILE,compile_report_sha256=compile_digest,
        stage_export_id=STAGE,stage_report_sha256=stage_digest,
        sweep_export_id=PREVIEW,sweep_report_sha256=sweep_digest,
        selector="AIRH8",maximum_writes=8,source_goals=list(SOURCE_GOALS),
        source_positions=list(SOURCE_POSITIONS),targets=[list(row) for row in TARGETS],
        synchronized_servo_ids=[11,12,13,14,15,16,17],
        source_drift_cap_counts=3,source_goal_error_cap_counts=12,
        source_failure_record_route="/rocell/air-elbow-shift/source-fault",
        requires_durable_export_receipt=True,retry_allowed=False,
        settings_preserved_by_design=True,hardware_access=False,
        firmware_uploaded=False,deployment_authorized=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({"mode":"r82-elbow-shift-review"},[],attachments={
        "r82-elbow-shift-review.json":canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Review export invalid")
    return saved["path"]


if __name__=="__main__":print(review(Path(__file__).resolve().parents[1]))
