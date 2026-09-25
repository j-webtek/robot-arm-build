"""Offline source/binary review of the fixed seven-leg r77 noncontact finale."""
import hashlib
from pathlib import Path

from stage_r77_air_typing import R76_APP_SHA,specialize
from rocell.application.air_typing_r77_campaign import TARGETS
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


STAGE="wizard-20260924T225543409826Z-32173410142a43849da262b5500397ff"
COMPILE="wizard-20260924T230100683072Z-c19dfa5c3c31468fae31a8237f7830a4"
PREVIEW="wizard-20260924T225507396227Z-7f73095433db4366ab3b9d32c02b0b4e"
APP_SHA="7a2059d76243b37e9b443c822093ef597611f136f5497a055f01278c3bcda496"
APP_BYTES=1203152


def review(root):
    root=Path(root).resolve();exports=root/"runs/wizard-exports"
    compiled,compile_digest=_read(exports,COMPILE,"attachment-compile-review.json")
    staged,stage_digest=_read(exports,STAGE,"attachment-r77-air-typing-stage.json")
    sweep,sweep_digest=_read(exports,PREVIEW,"attachment-r77-air-typing-preview.json")
    sha=lambda data:hashlib.sha256(data).hexdigest()
    old=root/".firmware-tools/configured-diagnostic-candidate-r76/RoArm-M3_example"
    expected=specialize({p.name:p.read_bytes() for p in old.iterdir() if p.is_file()},root)
    target=root/".firmware-tools/configured-diagnostic-candidate-r77/RoArm-M3_example"
    actual={p.name:p.read_bytes() for p in target.iterdir() if p.is_file()}
    prefix=".firmware-tools/configured-diagnostic-candidate-r77/RoArm-M3_example/"
    source_hashes={p.replace("\\","/"):h for p,h in compiled["source_hashes"].items()}
    if (actual!=expected or compiled["status"]!="COMPILED"
            or compiled["target"]!="configured-diagnostic-candidate-r77"
            or compiled["build_profile"]!="default-4mb-no-psram"
            or any(source_hashes.get(prefix+name)!=sha(data) for name,data in actual.items())
            or staged["predecessor_revision"]!=76 or staged["selector"]!="AIR7"
            or staged["maximum_writes"]!=7
            or staged["source_goals"]!=[1941,2098,2016,2609,2201,2040,2047]
            or staged["source_positions"]!=[1949,2099,2015,2610,2203,2041,2047]
            or sweep["status"]!="OFFLINE_R77_SWEEP_PASS_NOT_EXECUTABLE"
            or [row["goals"] for row in sweep["legs"]]!=[list(row) for row in TARGETS]):
        raise ValueError("r77 staged source or sweep differs")
    build=root/".firmware-tools/build-configured-diagnostic-candidate-r77--default-4mb-no-psram"
    image=(build/"RoArm-M3_example.ino.bin").read_bytes()
    if (sha(image)!=APP_SHA or len(image)!=APP_BYTES or len(image)>0x140000
            or compiled["artifact_hashes"]["RoArm-M3_example.ino.bin"]!=APP_SHA
            or not all(marker in image for marker in
                       (b"RCAIRAB301",b"/rocell/air-type-final/start",b"AIR7"))
            or b"/rocell/air-type-b-hover/start" in image or b"AIRB1" in image):
        raise ValueError("r77 app image differs")
    for suffix,digest in (("bootloader.bin","b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7"),
                          ("partitions.bin","148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1")):
        name="RoArm-M3_example.ino."+suffix
        if sha((build/name).read_bytes())!=digest or compiled["artifact_hashes"][name]!=digest:
            raise ValueError("Protected build artifact differs")
    report=dict(schema="rocell.r77_air_typing_review.v1",
        target="configured-diagnostic-candidate-r77",app_sha256=APP_SHA,
        app_bytes=APP_BYTES,app_offset=0x10000,app_slot_bytes=0x140000,
        predecessor_revision=76,predecessor_sha256=R76_APP_SHA,
        compile_export_id=COMPILE,compile_report_sha256=compile_digest,
        stage_export_id=STAGE,stage_report_sha256=stage_digest,
        sweep_export_id=PREVIEW,sweep_report_sha256=sweep_digest,
        selector="AIR7",maximum_writes=7,source_goals=staged["source_goals"],
        source_positions=staged["source_positions"],targets=[list(row) for row in TARGETS],
        synchronized_servo_ids=[11,12,13,14,15,16,17],
        requires_durable_export_receipt=True,retry_allowed=False,
        settings_preserved_by_design=True,hardware_access=False,
        firmware_uploaded=False,deployment_authorized=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({"mode":"r77-air-typing-review"},[],attachments={
        "r77-air-typing-review.json":canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Review export invalid")
    return saved["path"]


if __name__=="__main__":print(review(Path(__file__).resolve().parents[1]))
