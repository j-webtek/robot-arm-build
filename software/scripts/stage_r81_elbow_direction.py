"""Stage isolated-elbow direction candidate from compiled r79; no upload."""
import hashlib
from pathlib import Path

from rocell.application.air_typing_elbow_direction_recipe import (
    SOURCE_GOALS,SOURCE_POSITIONS,TARGETS,review_source,validate_recipe,
)
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


R79_COMPILE="wizard-20260925T004112893722Z-c5239fb3d8314cc7b534c1ee70134e88"
R79_APP_SHA="f82f1f87e6e9917dfdf2e9c60c30aaedf18025bdbd3b9777600b46a1458f7e82"
PREVIEW="wizard-20260925T005948801060Z-2d584d3424644bf4ac59094d86af5017"


def replace_one(data,old,new):
    if data.count(old)!=1:raise ValueError("Pinned marker absent or ambiguous")
    return data.replace(old,new)


def specialize(files):
    validate_recipe();files=dict(files)
    policy=files["air_typing_policy.h"]
    old=b'''  static constexpr uint16_t targets[legs][7]={
    {2047,2093,2021,2618,2197,2040,2047},
    {2047,2105,2009,2630,2173,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047},
    {2047,2093,2021,2618,2197,2040,2047},
    {2047,2105,2009,2630,2173,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047}
  };'''
    new=b'''  static constexpr uint16_t targets[legs][7]={
    {2047,2075,2039,2570,2233,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047},
    {2047,2075,2039,2630,2233,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047},
    {2047,2075,2039,2570,2233,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047},
    {2047,2075,2039,2630,2233,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047}
  };'''
    policy=replace_one(policy,b"static constexpr unsigned legs=6;",
                       b"static constexpr unsigned legs=8;")
    policy=replace_one(policy,old,new)
    policy=replace_one(policy,
        b"source_positions[7]={2041,2081,2033,2609,2233,2041,2047}",
        b"source_positions[7]={2041,2082,2033,2609,2233,2041,2047}")
    policy=replace_one(policy,
        b"target_goals[7]={2047,2093,2021,2618,2197,2040,2047}",
        b"target_goals[7]={2047,2075,2039,2570,2233,2040,2047}")
    files["air_typing_policy.h"]=policy
    files["air_typing_owner.h"]=replace_one(files["air_typing_owner.h"],
                                                 b"RCAIRAB501",b"RCAIRAB701")
    routes=replace_one(files["air_typing_routes.h"],b'body!="AIR6"',b'body!="AIRE8"')
    if routes.count(b"/rocell/air-type-repeat/")!=6:
        raise ValueError("Expected six r79 route registrations")
    routes=routes.replace(b"/rocell/air-type-repeat/",b"/rocell/air-elbow-direction/")
    files["air_typing_routes.h"]=routes
    return files


def stage(root):
    root=Path(root).resolve();exports=root/"runs/wizard-exports"
    compiled,compile_digest=_read(exports,R79_COMPILE,"attachment-compile-review.json")
    sweep,sweep_digest=_read(exports,PREVIEW,
                             "attachment-air-typing-elbow-direction-preview.json")
    source_digest=review_source(exports)
    source=root/".firmware-tools/configured-diagnostic-candidate-r79/RoArm-M3_example"
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    sha=lambda data:hashlib.sha256(data).hexdigest()
    prefix=".firmware-tools/configured-diagnostic-candidate-r79/RoArm-M3_example/"
    expected={Path(p).name:h for p,h in compiled["source_hashes"].items()
              if p.replace("\\","/").startswith(prefix)}
    image=(root/".firmware-tools/build-configured-diagnostic-candidate-r79--default-4mb-no-psram/RoArm-M3_example.ino.bin").read_bytes()
    if (compiled["status"]!="COMPILED" or compiled["target"]!="configured-diagnostic-candidate-r79"
            or set(files)!=set(expected)
            or any(sha(data)!=expected[name] for name,data in files.items())
            or sha(image)!=R79_APP_SHA
            or sweep["status"]!="OFFLINE_ELBOW_DIRECTION_SWEEP_PASS_NOT_EXECUTABLE"
            or sweep["source_goals"]!=list(SOURCE_GOALS)
            or sweep["source_positions"]!=list(SOURCE_POSITIONS)
            or [row["goals"] for row in sweep["legs"]]!=[list(x) for x in TARGETS]
            or sweep["source_assessment_sha256"]!=source_digest):
        raise ValueError("Pinned r79 predecessor or elbow source evidence differs")
    candidate=specialize(files)
    target=root/".firmware-tools/configured-diagnostic-candidate-r81/RoArm-M3_example"
    target.mkdir(parents=True,exist_ok=True)
    existing={p.name:p.read_bytes() for p in target.iterdir() if p.is_file()}
    if existing and existing!=candidate:
        raise ValueError("Existing r81 stage differs; no overwrite")
    for name,data in candidate.items():
        if not (target/name).exists():
            with (target/name).open("xb") as stream:stream.write(data)
        if (target/name).read_bytes()!=data:raise ValueError("r81 staged readback differs")
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({"mode":"r81-elbow-direction-stage"},[],attachments={
        "r81-elbow-direction-stage.json":canonical(dict(
            predecessor_revision=79,predecessor_compile_export=R79_COMPILE,
            predecessor_compile_digest=compile_digest,
            source_export="wizard-20260925T005208116238Z-9058a361c92f4d81ba686b724286c712",
            source_assessment_digest=source_digest,
            preview_export=PREVIEW,preview_digest=sweep_digest,
            selector="AIRE8",maximum_writes=8,
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
