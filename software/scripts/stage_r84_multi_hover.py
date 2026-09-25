"""Stage fixed five-leg multi-joint hover from compiled r83; no upload."""
import hashlib
from pathlib import Path

from rocell.application.air_typing_elbow_grid_recipe import TARGETS as R83_TARGETS
from rocell.application.air_typing_multi_hover_recipe import (
    SOURCE_GOALS, SOURCE_POSITIONS, TARGETS, review_source, validate_recipe,
)
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R83_COMPILE = "wizard-20260925T014214281960Z-84d930680a8a48439513970f4b8e2b2f"
R83_APP_SHA = "5baaa670dd27e1e1f621fa5357f67eba765101b182be4513908e30192d4a00d6"
PREVIEW = "wizard-20260925T015708190225Z-bd58d70ff1634aee926f10143ca8cc90"
R83_EXPORT_LAST = "wizard-20260925T015303129018Z-328caaed1c9046379902acd77dc6a32a"


def replace_one(data, old, new):
    if data.count(old) != 1:
        raise ValueError("Pinned marker absent or ambiguous")
    return data.replace(old, new)


def targets_block(rows):
    return ("  static constexpr uint16_t targets[legs][7]={\n" +
            ",\n".join("    {" + ",".join(str(value) for value in row) + "}" for row in rows) +
            "\n  };").encode("ascii")


def specialize(files):
    validate_recipe()
    files = dict(files)
    policy = files["air_typing_policy.h"]
    policy = replace_one(policy, b"static constexpr unsigned legs=16;",
                         b"static constexpr unsigned legs=5;")
    policy = replace_one(policy, targets_block(R83_TARGETS), targets_block(TARGETS))
    policy = replace_one(policy, b"source_goals[7]={2047,2075,2039,2610,2233,2040,2047}",
                         b"source_goals[7]={2047,2075,2039,2620,2233,2040,2047}")
    policy = replace_one(policy, b"source_positions[7]={2041,2082,2033,2619,2233,2041,2047}",
                         b"source_positions[7]={2041,2082,2033,2622,2233,2041,2047}")
    policy = replace_one(policy, b"target_goals[7]={2047,2075,2039,2560,2233,2040,2047}",
                         b"target_goals[7]={2047,2075,2039,2600,2233,2040,2047}")
    files["air_typing_policy.h"] = policy
    files["air_typing_owner.h"] = replace_one(files["air_typing_owner.h"],
                                                 b"RCAIRAB901", b"RCAIRABA01")
    routes = replace_one(files["air_typing_routes.h"], b'body!="AIRG16"', b'body!="AIRM5"')
    if routes.count(b"/rocell/air-elbow-grid/") != 6:
        raise ValueError("Expected six r83 route registrations")
    routes = routes.replace(b"/rocell/air-elbow-grid/", b"/rocell/air-multi-hover/")
    files["air_typing_routes.h"] = routes
    return files


def stage(root):
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    compiled, compile_digest = _read(exports, R83_COMPILE, "attachment-compile-review.json")
    sweep, sweep_digest = _read(exports, PREVIEW, "attachment-air-typing-multi-hover-preview.json")
    source_digest = review_source(exports)
    source = root / ".firmware-tools/configured-diagnostic-candidate-r83/RoArm-M3_example"
    files = {p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    sha = lambda data: hashlib.sha256(data).hexdigest()
    prefix = ".firmware-tools/configured-diagnostic-candidate-r83/RoArm-M3_example/"
    expected = {Path(p).name:h for p,h in compiled["source_hashes"].items()
                if p.replace("\\", "/").startswith(prefix)}
    image = (root / ".firmware-tools/build-configured-diagnostic-candidate-r83--default-4mb-no-psram/RoArm-M3_example.ino.bin").read_bytes()
    if (compiled["status"] != "COMPILED" or compiled["target"] != "configured-diagnostic-candidate-r83"
            or set(files) != set(expected)
            or any(sha(data) != expected[name] for name,data in files.items())
            or sha(image) != R83_APP_SHA
            or sweep["status"] != "OFFLINE_MULTI_HOVER_SWEEP_PASS_NOT_EXECUTABLE"
            or sweep["source_goals"] != list(SOURCE_GOALS)
            or sweep["source_positions"] != list(SOURCE_POSITIONS)
            or [row["goals"] for row in sweep["legs"]] != [list(x) for x in TARGETS]
            or sweep["source_assessment_sha256"] != source_digest):
        raise ValueError("Pinned r83 predecessor or multi-hover evidence differs")
    candidate = specialize(files)
    target = root / ".firmware-tools/configured-diagnostic-candidate-r84/RoArm-M3_example"
    target.mkdir(parents=True, exist_ok=True)
    existing = {p.name:p.read_bytes() for p in target.iterdir() if p.is_file()}
    if existing and existing != candidate:
        raise ValueError("Existing r84 stage differs; no overwrite")
    for name, data in candidate.items():
        if not (target / name).exists():
            with (target / name).open("xb") as stream:
                stream.write(data)
        if (target / name).read_bytes() != data:
            raise ValueError("r84 staged readback differs")
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode":"r84-multi-hover-stage"}, [], attachments={
        "r84-multi-hover-stage.json":canonical(dict(
            predecessor_revision=83, predecessor_compile_export=R83_COMPILE,
            predecessor_compile_digest=compile_digest,
            source_export=R83_EXPORT_LAST, source_assessment_digest=source_digest,
            preview_export=PREVIEW, preview_digest=sweep_digest,
            selector="AIRM5", maximum_writes=5,
            source_goals=list(SOURCE_GOALS), source_positions=list(SOURCE_POSITIONS),
            targets=[list(x) for x in TARGETS], record_bytes=1130,
            changed_files={name:dict(before=sha(files[name]) if name in files else None,
                                     after=sha(data)) for name,data in candidate.items()
                           if data != files.get(name)},
            hardware_access=False, uploaded=False, deployable=False))})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Stage export invalid")
    return saved["path"]


if __name__ == "__main__":
    print(stage(Path(__file__).resolve().parents[1]))
