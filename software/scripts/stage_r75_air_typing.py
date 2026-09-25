"""Stage the fixed air-typing controller from the verified r74 source; no upload."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R74_COMPILE = "wizard-20260924T193848829614Z-68ba88683b8f4de2a307b30ed5f5b92e"
R74_APP_SHA = "1f2c6822f428b9dd9fdf2eb17444d3f89f5d7243a7aad89edae4acda0b721bc5"
RECIPE_SHA = "011edbd4256d81ec94bccaee056fce9a056e580b318e4d71cf9bd9d6a70ba92d"


def specialize(files, root):
    files = dict(files)
    files["large_pose_relief_routes.h"] = (
        b'#pragma once\n#include "air_typing_routes.h"\nnamespace rocell_diag { '
        b'template<class C,class S,class K,class W> using LargePoseReliefRoutes='
        b'AirTypingRoutes<C,S,K,W>; }\n'
    )
    for name in ("air_typing_policy.h", "air_typing_owner.h", "air_typing_routes.h",
                 "characterization_board_services.h"):
        files[name] = (root / "firmware/diagnostics" / name).read_bytes()
    return files


def stage(root):
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    compiled, compile_digest = _read(exports, R74_COMPILE, "attachment-compile-review.json")
    source = root / ".firmware-tools/configured-diagnostic-candidate-r74/RoArm-M3_example"
    files = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    prefix = ".firmware-tools/configured-diagnostic-candidate-r74/RoArm-M3_example/"
    expected = {Path(p).name: digest for p, digest in compiled["source_hashes"].items()
                if p.replace("\\", "/").startswith(prefix)}
    if (compiled["status"] != "COMPILED" or compiled["target"] != "configured-diagnostic-candidate-r74"
            or set(files) != set(expected)
            or any(sha(data) != expected[name] for name, data in files.items())):
        raise ValueError("Pinned r74 source differs")
    old_image = (root / ".firmware-tools/build-configured-diagnostic-candidate-r74--default-4mb-no-psram/RoArm-M3_example.ino.bin").read_bytes()
    if sha(old_image) != R74_APP_SHA:
        raise ValueError("Pinned r74 application differs")
    candidate = specialize(files, root)
    target = root / ".firmware-tools/configured-diagnostic-candidate-r75/RoArm-M3_example"
    target.mkdir(parents=True, exist_ok=True)
    existing = {p.name: p.read_bytes() for p in target.iterdir() if p.is_file()}
    if existing and existing != candidate:
        raise ValueError("Existing r75 stage differs; no overwrite")
    for name, data in candidate.items():
        if not (target / name).exists():
            with (target / name).open("xb") as stream:
                stream.write(data)
        if (target / name).read_bytes() != data:
            raise ValueError("Staged readback differs")
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r75-air-typing-stage"}, [], attachments={
        "r75-air-typing-stage.json": canonical(dict(
            predecessor_revision=74, predecessor_compile_export=R74_COMPILE,
            predecessor_compile_digest=compile_digest, recipe_report_sha256=RECIPE_SHA,
            selector="AIR17", maximum_writes=17, record_bytes=1130,
            changed_files={name: dict(before=sha(files[name]) if name in files else None, after=sha(data))
                           for name, data in candidate.items() if data != files.get(name)},
            hardware_access=False, uploaded=False, deployable=False))})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Stage export invalid")
    return saved["path"]


if __name__ == "__main__":
    print(stage(Path(__file__).resolve().parents[1]))
