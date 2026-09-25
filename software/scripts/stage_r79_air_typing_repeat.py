"""Stage exact six-leg A repeat candidate from compiled r78; no upload."""
import hashlib
from pathlib import Path

from rocell.application.air_typing_repeat_recipe import (
    SOURCE_GOALS,SOURCE_POSITIONS,TARGETS,review_source,validate_recipe,
)
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


R78_COMPILE="wizard-20260924T233709349019Z-1f08fee57ede4a908e054c28210bdd46"
R78_APP_SHA="3b9989e03cd64690e831049c4e19ff38d6c10ab6e2c6c22f3ad1d7e61e1f3aaa"
PREVIEW="wizard-20260925T003809476577Z-68c0aaffc48140e7ac466642e87cb77b"


def replace_one(data,old,new):
    if data.count(old)!=1:raise ValueError("Pinned marker absent or ambiguous")
    return data.replace(old,new)


def specialize(files,root):
    validate_recipe();files=dict(files)
    files["air_typing_policy.h"]=(root/"firmware/diagnostics/air_typing_r79_policy.h").read_bytes()
    files["air_typing_owner.h"]=replace_one(files["air_typing_owner.h"],
                                                 b"RCAIRAB401",b"RCAIRAB501")
    routes=replace_one(files["air_typing_routes.h"],b'body!="AIR4"',b'body!="AIR6"')
    if routes.count(b"/rocell/air-type-last/")!=6:
        raise ValueError("Expected six r78 route registrations")
    routes=routes.replace(b"/rocell/air-type-last/",b"/rocell/air-type-repeat/")
    files["air_typing_routes.h"]=routes
    return files


def stage(root):
    root=Path(root).resolve();exports=root/"runs/wizard-exports"
    compiled,compile_digest=_read(exports,R78_COMPILE,"attachment-compile-review.json")
    sweep,sweep_digest=_read(exports,PREVIEW,"attachment-air-typing-repeat-preview.json")
    source_digest=review_source(exports)
    source=root/".firmware-tools/configured-diagnostic-candidate-r78/RoArm-M3_example"
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    sha=lambda data:hashlib.sha256(data).hexdigest()
    prefix=".firmware-tools/configured-diagnostic-candidate-r78/RoArm-M3_example/"
    expected={Path(p).name:h for p,h in compiled["source_hashes"].items()
              if p.replace("\\","/").startswith(prefix)}
    image=(root/".firmware-tools/build-configured-diagnostic-candidate-r78--default-4mb-no-psram/RoArm-M3_example.ino.bin").read_bytes()
    if (compiled["status"]!="COMPILED" or compiled["target"]!="configured-diagnostic-candidate-r78"
            or set(files)!=set(expected)
            or any(sha(data)!=expected[name] for name,data in files.items())
            or sha(image)!=R78_APP_SHA
            or sweep["status"]!="OFFLINE_REPEAT_SWEEP_PASS_NOT_EXECUTABLE"
            or sweep["source_goals"]!=list(SOURCE_GOALS)
            or sweep["source_positions"]!=list(SOURCE_POSITIONS)
            or [row["goals"] for row in sweep["legs"]]!=[list(x) for x in TARGETS]
            or sweep["source_assessment_sha256"]!=source_digest):
        raise ValueError("Pinned r78 predecessor or repeat source evidence differs")
    candidate=specialize(files,root)
    target=root/".firmware-tools/configured-diagnostic-candidate-r79/RoArm-M3_example"
    target.mkdir(parents=True,exist_ok=True)
    existing={p.name:p.read_bytes() for p in target.iterdir() if p.is_file()}
    if existing and existing!=candidate:
        raise ValueError("Existing r79 stage differs; no overwrite")
    for name,data in candidate.items():
        if not (target/name).exists():
            with (target/name).open("xb") as stream:stream.write(data)
        if (target/name).read_bytes()!=data:raise ValueError("r79 staged readback differs")
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({"mode":"r79-air-typing-repeat-stage"},[],attachments={
        "r79-air-typing-repeat-stage.json":canonical(dict(
            predecessor_revision=78,predecessor_compile_export=R78_COMPILE,
            predecessor_compile_digest=compile_digest,
            source_export="wizard-20260924T234900259937Z-5d6c8c652fe24e2abb137b9046dc7811",
            source_assessment_digest=source_digest,
            preview_export=PREVIEW,preview_digest=sweep_digest,
            selector="AIR6",maximum_writes=6,
            source_goals=list(SOURCE_GOALS),source_positions=list(SOURCE_POSITIONS),
            targets=[list(x) for x in TARGETS],record_bytes=1130,
            changed_files={name:dict(before=sha(files[name]) if name in files else None,
                                     after=sha(data)) for name,data in candidate.items()
                           if data!=files.get(name)},
            hardware_access=False,uploaded=False,deployable=False))})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Stage export invalid")
    return saved["path"]


if __name__=="__main__":print(stage(Path(__file__).resolve().parents[1]))
