"""Offline source, image, and fixed-route review for r75; no hardware access."""
import hashlib
from pathlib import Path

from stage_r75_air_typing import R74_APP_SHA, RECIPE_SHA, specialize
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


STAGE = "wizard-20260924T202251819551Z-8d565e052a86423c82e0739c2529aca9"
COMPILE = "wizard-20260924T202450174741Z-b9b30442e8e64248b42fe489e34e04dd"
APP_SHA = "da56d6d353918f2654f919914a48a8de4f3a7377ee718c5c122dac397bb92f2d"
APP_BYTES = 1203040


def review(root):
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    compiled, compile_digest = _read(exports, COMPILE, "attachment-compile-review.json")
    staged, stage_digest = _read(exports, STAGE, "attachment-r75-air-typing-stage.json")
    sha = lambda data: hashlib.sha256(data).hexdigest()
    prefix = ".firmware-tools/configured-diagnostic-candidate-r75/RoArm-M3_example/"
    old = root / ".firmware-tools/configured-diagnostic-candidate-r74/RoArm-M3_example"
    expected = specialize({p.name: p.read_bytes() for p in old.iterdir() if p.is_file()}, root)
    actual = {p.name: p.read_bytes() for p in (root / prefix).iterdir() if p.is_file()}
    source_hashes = {p.replace("\\", "/"): h for p, h in compiled["source_hashes"].items()}
    if (actual != expected or compiled["status"] != "COMPILED"
            or compiled["target"] != "configured-diagnostic-candidate-r75"
            or compiled["build_profile"] != "default-4mb-no-psram"
            or any(source_hashes.get(prefix + name) != sha(data) for name, data in actual.items())
            or staged["predecessor_revision"] != 74 or staged["selector"] != "AIR17"
            or staged["maximum_writes"] != 17 or staged["recipe_report_sha256"] != RECIPE_SHA):
        raise ValueError("r75 source or stage differs")
    build = root / ".firmware-tools/build-configured-diagnostic-candidate-r75--default-4mb-no-psram"
    image = (build / "RoArm-M3_example.ino.bin").read_bytes()
    if (sha(image) != APP_SHA or len(image) != APP_BYTES or len(image) > 0x140000
            or compiled["artifact_hashes"]["RoArm-M3_example.ino.bin"] != APP_SHA
            or not all(marker in image for marker in
                       (b"RCAIRABA01", b"AIR_TYPING_COMPLETE", b"/rocell/air-type/start", b"AIR17"))
            or b"/rocell/p4-midpoint/start" in image):
        raise ValueError("r75 application differs")
    for suffix, digest in (("bootloader.bin", "b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7"),
                           ("partitions.bin", "148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1")):
        name = "RoArm-M3_example.ino." + suffix
        if sha((build / name).read_bytes()) != digest or compiled["artifact_hashes"][name] != digest:
            raise ValueError("Protected build artifact differs")
    report = dict(schema="rocell.r75_air_typing_review.v1", target="configured-diagnostic-candidate-r75",
                  app_sha256=APP_SHA, app_bytes=APP_BYTES, app_offset=0x10000, app_slot_bytes=0x140000,
                  predecessor_revision=74, predecessor_sha256=R74_APP_SHA,
                  compile_export_id=COMPILE, compile_report_sha256=compile_digest,
                  stage_export_id=STAGE, stage_report_sha256=stage_digest,
                  recipe_report_sha256=RECIPE_SHA, selector="AIR17", maximum_writes=17,
                  synchronized_servo_ids=[11, 12, 13, 14, 15, 16, 17],
                  requires_durable_export_receipt=True, retry_allowed=False,
                  settings_preserved_by_design=True, hardware_access=False,
                  firmware_uploaded=False, deployment_authorized=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r75-air-typing-review"}, [], attachments={
        "r75-air-typing-review.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Review export invalid")
    return saved["path"]


if __name__ == "__main__":
    print(review(Path(__file__).resolve().parents[1]))
