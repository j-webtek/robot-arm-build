"""Stage fixed 16-leg elbow grid from compiled r82; no upload."""
import hashlib
from pathlib import Path

from rocell.application.air_typing_elbow_shift_recipe import TARGETS as R82_TARGETS
from rocell.application.air_typing_elbow_grid_recipe import (
    SOURCE_GOALS,SOURCE_POSITIONS,TARGETS,review_source,validate_recipe,
)
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


R82_COMPILE="wizard-20260925T012447190813Z-f18765fe88f6420aab1cce1858c03903"
R82_APP_SHA="0be3db4edf21396c881ee9eeee62f625bc99ebaf33bf96b35656c5dffd3a937c"
PREVIEW="wizard-20260925T013911696665Z-0466381551ac4ccb877529e0d7133839"
R82_EXPORT_LAST="wizard-20260925T013537473684Z-d9c823e27197402dbc2b3061a8e679ff"


def replace_one(data,old,new):
    if data.count(old)!=1:raise ValueError("Pinned marker absent or ambiguous")
    return data.replace(old,new)


def targets_block(rows):
    return ("  static constexpr uint16_t targets[legs][7]={\n"+
            ",\n".join("    {"+",".join(str(value) for value in row)+"}" for row in rows)+
            "\n  };").encode("ascii")


def specialize(files):
    validate_recipe();files=dict(files)
    policy=files["air_typing_policy.h"]
    policy=replace_one(policy,b"static constexpr unsigned legs=8;",
                       b"static constexpr unsigned legs=16;")
    policy=replace_one(policy,targets_block(R82_TARGETS),targets_block(TARGETS))
    policy=replace_one(policy,b"source_goals[7]={2047,2075,2039,2600,2233,2040,2047}",
                             b"source_goals[7]={2047,2075,2039,2610,2233,2040,2047}")
    policy=replace_one(policy,b"source_positions[7]={2041,2082,2033,2609,2233,2041,2047}",
                             b"source_positions[7]={2041,2082,2033,2619,2233,2041,2047}")
    policy=replace_one(policy,b"target_goals[7]={2047,2075,2039,2580,2233,2040,2047}",
                             b"target_goals[7]={2047,2075,2039,2560,2233,2040,2047}")
    files["air_typing_policy.h"]=policy
    files["air_typing_owner.h"]=replace_one(files["air_typing_owner.h"],
                                                b"RCAIRAB801",b"RCAIRAB901")
    routes=replace_one(files["air_typing_routes.h"],b'body!="AIRH8"',b'body!="AIRG16"')
    if routes.count(b"/rocell/air-elbow-shift/")!=6:
        raise ValueError("Expected six r82 route registrations")
    routes=routes.replace(b"/rocell/air-elbow-shift/",b"/rocell/air-elbow-grid/")
    files["air_typing_routes.h"]=routes
    return files


def stage(root):
    root=Path(root).resolve();exports=root/"runs/wizard-exports"
    compiled,compile_digest=_read(exports,R82_COMPILE,"attachment-compile-review.json")
    sweep,sweep_digest=_read(exports,PREVIEW,
                             "attachment-air-typing-elbow-grid-preview.json")
    source_digest=review_source(exports)
    source=root/".firmware-tools/configured-diagnostic-candidate-r82/RoArm-M3_example"
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    sha=lambda data:hashlib.sha256(data).hexdigest()
    prefix=".firmware-tools/configured-diagnostic-candidate-r82/RoArm-M3_example/"
    expected={Path(p).name:h for p,h in compiled["source_hashes"].items()
              if p.replace("\\","/").startswith(prefix)}
    image=(root/".firmware-tools/build-configured-diagnostic-candidate-r82--default-4mb-no-psram/RoArm-M3_example.ino.bin").read_bytes()
    if (compiled["status"]!="COMPILED" or compiled["target"]!="configured-diagnostic-candidate-r82"
            or set(files)!=set(expected)
            or any(sha(data)!=expected[name] for name,data in files.items())
            or sha(image)!=R82_APP_SHA
            or sweep["status"]!="OFFLINE_ELBOW_GRID_SWEEP_PASS_NOT_EXECUTABLE"
            or sweep["source_goals"]!=list(SOURCE_GOALS)
            or sweep["source_positions"]!=list(SOURCE_POSITIONS)
            or [row["goals"] for row in sweep["legs"]]!=[list(x) for x in TARGETS]
            or sweep["source_assessment_sha256"]!=source_digest):
        raise ValueError("Pinned r82 predecessor or elbow-grid evidence differs")
    candidate=specialize(files)
    target=root/".firmware-tools/configured-diagnostic-candidate-r83/RoArm-M3_example"
    target.mkdir(parents=True,exist_ok=True)
    existing={p.name:p.read_bytes() for p in target.iterdir() if p.is_file()}
    if existing and existing!=candidate:
        raise ValueError("Existing r83 stage differs; no overwrite")
    for name,data in candidate.items():
        if not (target/name).exists():
            with (target/name).open("xb") as stream:stream.write(data)
        if (target/name).read_bytes()!=data:raise ValueError("r83 staged readback differs")
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({"mode":"r83-elbow-grid-stage"},[],attachments={
        "r83-elbow-grid-stage.json":canonical(dict(
            predecessor_revision=82,predecessor_compile_export=R82_COMPILE,
            predecessor_compile_digest=compile_digest,
            source_export=R82_EXPORT_LAST,source_assessment_digest=source_digest,
            preview_export=PREVIEW,preview_digest=sweep_digest,
            selector="AIRG16",maximum_writes=16,
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
