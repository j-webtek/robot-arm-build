"""Stage fixed seven-leg noncontact B-A finale from pinned r76; no upload."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R76_COMPILE="wizard-20260924T224457688000Z-eeab1c5d887b4c6f8f94386202cfd727"
R76_APP_SHA="874c89ca5af7bbb5e492cb5b3cf95ea47116c19fc65190151c638e47aeac0987"


def _replace_one(data, old, new):
    if data.count(old)!=1:
        raise ValueError("Pinned marker absent or ambiguous")
    return data.replace(old,new)


def specialize(files,root):
    files=dict(files)
    files["air_typing_policy.h"]=(root/"firmware/diagnostics/air_typing_r77_policy.h").read_bytes()
    files["air_typing_owner.h"]=_replace_one(files["air_typing_owner.h"],
        b"RCAIRAB201",b"RCAIRAB301")
    files["air_typing_routes.h"]=_replace_one(files["air_typing_routes.h"],
        b'body!="AIRB1"',b'body!="AIR7"')
    if files["air_typing_routes.h"].count(b"/rocell/air-type-b-hover/")!=5:
        raise ValueError("Expected five r76 routes")
    files["air_typing_routes.h"]=files["air_typing_routes.h"].replace(
        b"/rocell/air-type-b-hover/",b"/rocell/air-type-final/")
    return files


def stage(root):
    root=Path(root).resolve();exports=root/"runs/wizard-exports"
    compiled,compile_digest=_read(exports,R76_COMPILE,"attachment-compile-review.json")
    source=root/".firmware-tools/configured-diagnostic-candidate-r76/RoArm-M3_example"
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    sha=lambda data:hashlib.sha256(data).hexdigest()
    prefix=".firmware-tools/configured-diagnostic-candidate-r76/RoArm-M3_example/"
    expected={Path(p).name:h for p,h in compiled["source_hashes"].items()
              if p.replace("\\","/").startswith(prefix)}
    image=(root/".firmware-tools/build-configured-diagnostic-candidate-r76--default-4mb-no-psram/RoArm-M3_example.ino.bin").read_bytes()
    if (compiled["status"]!="COMPILED" or compiled["target"]!="configured-diagnostic-candidate-r76"
            or set(files)!=set(expected) or any(sha(data)!=expected[name] for name,data in files.items())
            or sha(image)!=R76_APP_SHA):
        raise ValueError("Pinned r76 predecessor differs")
    candidate=specialize(files,root)
    target=root/".firmware-tools/configured-diagnostic-candidate-r77/RoArm-M3_example"
    target.mkdir(parents=True,exist_ok=True)
    existing={p.name:p.read_bytes() for p in target.iterdir() if p.is_file()}
    if existing and existing!=candidate:
        raise ValueError("Existing r77 stage differs; no overwrite")
    for name,data in candidate.items():
        if not (target/name).exists():
            with (target/name).open("xb") as stream:stream.write(data)
        if (target/name).read_bytes()!=data:
            raise ValueError("r77 staged readback differs")
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({"mode":"r77-air-typing-stage"},[],attachments={
        "r77-air-typing-stage.json":canonical(dict(predecessor_revision=76,
            predecessor_compile_export=R76_COMPILE,predecessor_compile_digest=compile_digest,
            selector="AIR7",maximum_writes=7,source_goals=[1941,2098,2016,2609,2201,2040,2047],
            source_positions=[1949,2099,2015,2610,2203,2041,2047],record_bytes=1130,
            changed_files={name:dict(before=sha(files[name]) if name in files else None,
                                     after=sha(data)) for name,data in candidate.items() if data!=files.get(name)},
            hardware_access=False,uploaded=False,deployable=False))})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Stage export invalid")
    return saved["path"]


if __name__=="__main__":print(stage(Path(__file__).resolve().parents[1]))
