"""Stage nearby held-out elbow target from compiled r81; no upload."""
import hashlib
from pathlib import Path

from rocell.application.air_typing_elbow_shift_recipe import (
    SOURCE_GOALS,SOURCE_POSITIONS,TARGETS,review_source,validate_recipe,
)
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


R81_COMPILE="wizard-20260925T010248299584Z-d2e2a507bc71496b867012d312a1add9"
R81_APP_SHA="2580a872ce612c331cb02dce15be9b34f75f1e19ac4bc6043072e438e8b948d1"
PREVIEW="wizard-20260925T012204312726Z-dea966e979534a8fa9aad73b673d6d3a"


def replace_one(data,old,new):
    if data.count(old)!=1:raise ValueError("Pinned marker absent or ambiguous")
    return data.replace(old,new)


def specialize(files):
    validate_recipe();files=dict(files)
    policy=files["air_typing_policy.h"]
    old=b'''  static constexpr uint16_t targets[legs][7]={
    {2047,2075,2039,2570,2233,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047},
    {2047,2075,2039,2630,2233,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047},
    {2047,2075,2039,2570,2233,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047},
    {2047,2075,2039,2630,2233,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047}
  };'''
    new=b'''  static constexpr uint16_t targets[legs][7]={
    {2047,2075,2039,2580,2233,2040,2047},
    {2047,2075,2039,2610,2233,2040,2047},
    {2047,2075,2039,2640,2233,2040,2047},
    {2047,2075,2039,2610,2233,2040,2047},
    {2047,2075,2039,2580,2233,2040,2047},
    {2047,2075,2039,2610,2233,2040,2047},
    {2047,2075,2039,2640,2233,2040,2047},
    {2047,2075,2039,2610,2233,2040,2047}
  };'''
    policy=replace_one(policy,old,new)
    policy=replace_one(policy,b"target_goals[7]={2047,2075,2039,2570,2233,2040,2047}",
                             b"target_goals[7]={2047,2075,2039,2580,2233,2040,2047}")
    files["air_typing_policy.h"]=policy
    files["air_typing_owner.h"]=replace_one(files["air_typing_owner.h"],
                                                b"RCAIRAB701",b"RCAIRAB801")
    routes=replace_one(files["air_typing_routes.h"],b'body!="AIRE8"',b'body!="AIRH8"')
    if routes.count(b"/rocell/air-elbow-direction/")!=6:
        raise ValueError("Expected six r81 route registrations")
    routes=routes.replace(b"/rocell/air-elbow-direction/",b"/rocell/air-elbow-shift/")
    files["air_typing_routes.h"]=routes
    return files


def stage(root):
    root=Path(root).resolve();exports=root/"runs/wizard-exports"
    compiled,compile_digest=_read(exports,R81_COMPILE,"attachment-compile-review.json")
    sweep,sweep_digest=_read(exports,PREVIEW,
                             "attachment-air-typing-elbow-shift-preview.json")
    source_digest=review_source(exports)
    source=root/".firmware-tools/configured-diagnostic-candidate-r81/RoArm-M3_example"
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    sha=lambda data:hashlib.sha256(data).hexdigest()
    prefix=".firmware-tools/configured-diagnostic-candidate-r81/RoArm-M3_example/"
    expected={Path(p).name:h for p,h in compiled["source_hashes"].items()
              if p.replace("\\","/").startswith(prefix)}
    image=(root/".firmware-tools/build-configured-diagnostic-candidate-r81--default-4mb-no-psram/RoArm-M3_example.ino.bin").read_bytes()
    if (compiled["status"]!="COMPILED" or compiled["target"]!="configured-diagnostic-candidate-r81"
            or set(files)!=set(expected)
            or any(sha(data)!=expected[name] for name,data in files.items())
            or sha(image)!=R81_APP_SHA
            or sweep["status"]!="OFFLINE_ELBOW_SHIFT_SWEEP_PASS_NOT_EXECUTABLE"
            or sweep["source_goals"]!=list(SOURCE_GOALS)
            or sweep["source_positions"]!=list(SOURCE_POSITIONS)
            or [row["goals"] for row in sweep["legs"]]!=[list(x) for x in TARGETS]
            or sweep["source_assessment_sha256"]!=source_digest):
        raise ValueError("Pinned r81 predecessor or elbow-shift evidence differs")
    candidate=specialize(files)
    target=root/".firmware-tools/configured-diagnostic-candidate-r82/RoArm-M3_example"
    target.mkdir(parents=True,exist_ok=True)
    existing={p.name:p.read_bytes() for p in target.iterdir() if p.is_file()}
    if existing and existing!=candidate:
        raise ValueError("Existing r82 stage differs; no overwrite")
    for name,data in candidate.items():
        if not (target/name).exists():
            with (target/name).open("xb") as stream:stream.write(data)
        if (target/name).read_bytes()!=data:raise ValueError("r82 staged readback differs")
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({"mode":"r82-elbow-shift-stage"},[],attachments={
        "r82-elbow-shift-stage.json":canonical(dict(
            predecessor_revision=81,predecessor_compile_export=R81_COMPILE,
            predecessor_compile_digest=compile_digest,
            source_export=R81_EXPORT_LAST,source_assessment_digest=source_digest,
            preview_export=PREVIEW,preview_digest=sweep_digest,
            selector="AIRH8",maximum_writes=8,
            source_goals=list(SOURCE_GOALS),source_positions=list(SOURCE_POSITIONS),
            targets=[list(x) for x in TARGETS],record_bytes=1130,
            changed_files={name:dict(before=sha(files[name]) if name in files else None,
                                     after=sha(data)) for name,data in candidate.items()
                           if data!=files.get(name)},
            hardware_access=False,uploaded=False,deployable=False))})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Stage export invalid")
    return saved["path"]


R81_EXPORT_LAST="wizard-20260925T011719439949Z-665b83c9c1304bc29729329396a1dc7a"


if __name__=="__main__":print(stage(Path(__file__).resolve().parents[1]))
