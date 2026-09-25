"""Offline exact-source/image review of fail-closed r85; never deploys."""
from __future__ import annotations

import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


COMPILE = "wizard-20260925T031915246927Z-86950360cffe4640ad2cf64764a31a05"
R84_APP = "d1e141a9b73d0b104ffb2ac1b07cae213c1321300a2251bd8cd3dcf0596f97cd"
R85_APP = "e8f8c2f553fd604c05aefd1e917a54323abd3df12044da38123c85d5c2fc9cb9"
ADDED = (
    "reviewed_hover_board_adapter.h", "reviewed_hover_board.h",
    "reviewed_hover_composition.h", "reviewed_hover_live_admission.h",
    "reviewed_hover_manifest.h", "reviewed_hover_owner.h",
    "reviewed_hover_routes.h",
)


def review(root: Path) -> dict:
    root = Path(root).resolve()
    sha = lambda data: hashlib.sha256(data).hexdigest()
    exports = root / "runs/wizard-exports"
    compiled, compile_digest = _read(exports, COMPILE, "attachment-compile-review.json")
    prior = root / ".firmware-tools/configured-diagnostic-candidate-r84/RoArm-M3_example"
    staged = root / ".firmware-tools/configured-diagnostic-candidate-r85/RoArm-M3_example"
    old = {p.name: p.read_bytes() for p in prior.iterdir() if p.is_file()}
    actual = {p.name: p.read_bytes() for p in staged.iterdir() if p.is_file()}
    expected = dict(old)
    expected["air_typing_policy.h"] = (
        root / "firmware/diagnostics/air_typing_policy.h").read_bytes()
    old_shoulder = old["shoulder_board_session.h"]
    if old_shoulder.count(b"#define ROCELL_CHARACTERIZATION_SMOKE 1") != 1 or \
            old_shoulder.count(b"#if defined(ROCELL_CHARACTERIZATION_SMOKE)\n") != 1:
        raise ValueError("r84 shoulder selector differs")
    expected["shoulder_board_session.h"] = old_shoulder.replace(
        b"#define ROCELL_CHARACTERIZATION_SMOKE 1",
        b"#define ROCELL_REVIEWED_HOVER 1").replace(
        b"#if defined(ROCELL_CHARACTERIZATION_SMOKE)\n",
        b"#if defined(ROCELL_REVIEWED_HOVER)\n#include \"reviewed_hover_board.h\"\n"
        b"#elif defined(ROCELL_CHARACTERIZATION_SMOKE)\n")
    for name in ADDED:
        expected[name] = (root / "firmware/diagnostics" / name).read_bytes()
    if actual != expected:
        raise ValueError("r85 staged source differs from exact r84 delta")
    if (compiled.get("status") != "COMPILED" or
            compiled.get("target") != "configured-diagnostic-candidate-r85" or
            compiled.get("build_profile") != "default-4mb-no-psram"):
        raise ValueError("r85 compile report differs")
    prefix = ".firmware-tools/configured-diagnostic-candidate-r85/RoArm-M3_example/"
    hashes = {name.replace("\\", "/"): digest
              for name, digest in compiled["source_hashes"].items()}
    if any(hashes.get(prefix + name) != sha(data) for name, data in actual.items()):
        raise ValueError("Compile input hashes differ")
    build = root / ".firmware-tools/build-configured-diagnostic-candidate-r85--default-4mb-no-psram"
    image = (build / "RoArm-M3_example.ino.bin").read_bytes()
    if (sha(image) != R85_APP or len(image) > 0x140000 or
            compiled["artifact_hashes"].get("RoArm-M3_example.ino.bin") != R85_APP or
            not all(marker in image for marker in
                    (b"/rocell/reviewed-hover/start", b"LIVE_RELEASE_UNAVAILABLE")) or
            b"/rocell/air-multi-hover/start" in image):
        raise ValueError("r85 app image or fail-closed marker differs")
    for suffix, digest in (
        ("bootloader.bin", "b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7"),
        ("partitions.bin", "148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1"),
    ):
        name = "RoArm-M3_example.ino." + suffix
        if sha((build / name).read_bytes()) != digest or compiled["artifact_hashes"].get(name) != digest:
            raise ValueError("Protected r85 artifact differs")
    report = dict(schema="rocell.r85_reviewed_hover_compile_review.v1",
                  predecessor_app_sha256=R84_APP, app_sha256=R85_APP,
                  app_bytes=len(image), app_slot_bytes=0x140000,
                  compile_export_id=COMPILE, compile_report_sha256=compile_digest,
                  added_headers=list(ADDED), changed_inherited_files=[
                      "air_typing_policy.h", "shoulder_board_session.h"],
                  reviewed_start_present=True, release_identity_available=False,
                  old_air_multi_start_present=False,
                  hardware_access=False, firmware_uploaded=False,
                  deployment_authorized=False, motion_authorized=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r85-reviewed-hover-compile-review"}, [],
                            attachments={"r85-reviewed-hover-compile-review.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r85 review export failed")
    return {"status": "COMPILE_ONLY_REVIEWED_NOT_DEPLOYABLE",
            "export": saved["path"], "app_sha256": R85_APP}


if __name__ == "__main__":
    import json
    print(json.dumps(review(Path(__file__).resolve().parents[1])))
