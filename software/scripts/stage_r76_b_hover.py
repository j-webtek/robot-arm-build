"""Mechanically stage one fixed B-hover app from pinned r75 sources; no device access."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R75_COMPILE = "wizard-20260924T202450174741Z-b9b30442e8e64248b42fe489e34e04dd"
R75_APP_SHA = "da56d6d353918f2654f919914a48a8de4f3a7377ee718c5c122dac397bb92f2d"


def _replace_one(data: bytes, old: bytes, new: bytes) -> bytes:
    if data.count(old) != 1:
        raise ValueError("Pinned source marker is absent or ambiguous")
    return data.replace(old, new)


def specialize(files: dict[str, bytes], root: Path) -> dict[str, bytes]:
    files = dict(files)
    diagnostics = root / "firmware/diagnostics"
    files["air_typing_policy.h"] = (diagnostics / "air_typing_r76_policy.h").read_bytes()
    files["air_typing_r76_endpoint_rule.h"] = (diagnostics / "air_typing_r76_endpoint_rule.h").read_bytes()
    files["air_typing_owner.h"] = _replace_one(files["air_typing_owner.h"],
                                                 b"RCAIRABA01", b"RCAIRAB201")
    files["air_typing_routes.h"] = _replace_one(files["air_typing_routes.h"],
        b"body!=\"AIR17\"", b"body!=\"AIRB1\"")
    if files["air_typing_routes.h"].count(b"/rocell/air-type/") != 5:
        raise ValueError("Expected five r75 campaign routes")
    files["air_typing_routes.h"] = files["air_typing_routes.h"].replace(
        b"/rocell/air-type/", b"/rocell/air-type-b-hover/")
    return files


def stage(root: Path):
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    compiled, digest = _read(exports, R75_COMPILE, "attachment-compile-review.json")
    source = root / ".firmware-tools/configured-diagnostic-candidate-r75/RoArm-M3_example"
    files = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
    sha = lambda data: hashlib.sha256(data).hexdigest()
    prefix = ".firmware-tools/configured-diagnostic-candidate-r75/RoArm-M3_example/"
    expected = {Path(p).name: h for p, h in compiled["source_hashes"].items()
                if p.replace("\\", "/").startswith(prefix)}
    image = (root / ".firmware-tools/build-configured-diagnostic-candidate-r75--default-4mb-no-psram/RoArm-M3_example.ino.bin").read_bytes()
    if (compiled["status"] != "COMPILED" or compiled["target"] != "configured-diagnostic-candidate-r75"
            or set(files) != set(expected)
            or any(sha(data) != expected[name] for name, data in files.items())
            or sha(image) != R75_APP_SHA):
        raise ValueError("Pinned r75 predecessor differs")
    candidate = specialize(files, root)
    target = root / ".firmware-tools/configured-diagnostic-candidate-r76/RoArm-M3_example"
    target.mkdir(parents=True, exist_ok=True)
    existing = {p.name: p.read_bytes() for p in target.iterdir() if p.is_file()}
    if existing and existing != candidate:
        raise ValueError("Existing r76 stage differs; no overwrite")
    for name, data in candidate.items():
        if not (target / name).exists():
            with (target / name).open("xb") as stream:
                stream.write(data)
        if (target / name).read_bytes() != data:
            raise ValueError("r76 staged readback differs")
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r76-b-hover-stage"}, [], attachments={
        "r76-b-hover-stage.json": canonical(dict(predecessor_revision=75,
            predecessor_compile_export=R75_COMPILE, predecessor_compile_digest=digest,
            selector="AIRB1", maximum_writes=1, source_goals=[1941,2080,2034,2591,2236,2040,2047],
            target_goals=[1941,2098,2016,2609,2201,2040,2047], record_bytes=1130,
            changed_files={name: dict(before=sha(files[name]) if name in files else None,
                                      after=sha(data)) for name, data in candidate.items()
                           if data != files.get(name)},
            hardware_access=False, uploaded=False, deployable=False))})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Stage export invalid")
    return saved["path"]


if __name__ == "__main__":
    print(stage(Path(__file__).resolve().parents[1]))
