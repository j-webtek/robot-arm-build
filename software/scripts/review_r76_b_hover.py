"""Offline source and binary review of the one-move r76 candidate."""
import hashlib
from pathlib import Path

from stage_r76_b_hover import R75_APP_SHA, specialize
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


STAGE = "wizard-20260924T224024890431Z-a2ca8ee3c88e47a2b6a29c3e0a536fd5"
COMPILE = "wizard-20260924T224457688000Z-eeab1c5d887b4c6f8f94386202cfd727"
APP_SHA = "874c89ca5af7bbb5e492cb5b3cf95ea47116c19fc65190151c638e47aeac0987"
APP_BYTES = 1202960
PREVIEW = "wizard-20260924T222354001496Z-61801fa3c16244049c43e482bf3dadf6"


def review(root: Path):
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    compiled, compile_digest = _read(exports, COMPILE, "attachment-compile-review.json")
    staged, stage_digest = _read(exports, STAGE, "attachment-r76-b-hover-stage.json")
    sweep, sweep_digest = _read(exports, PREVIEW, "attachment-r76-continuation-preview.json")
    sha = lambda data: hashlib.sha256(data).hexdigest()
    old = root / ".firmware-tools/configured-diagnostic-candidate-r75/RoArm-M3_example"
    expected = specialize({p.name: p.read_bytes() for p in old.iterdir() if p.is_file()}, root)
    target = root / ".firmware-tools/configured-diagnostic-candidate-r76/RoArm-M3_example"
    actual = {p.name: p.read_bytes() for p in target.iterdir() if p.is_file()}
    prefix = ".firmware-tools/configured-diagnostic-candidate-r76/RoArm-M3_example/"
    source_hashes = {p.replace("\\", "/"): h for p, h in compiled["source_hashes"].items()}
    if (actual != expected or compiled["status"] != "COMPILED"
            or compiled["target"] != "configured-diagnostic-candidate-r76"
            or compiled["build_profile"] != "default-4mb-no-psram"
            or any(source_hashes.get(prefix + name) != sha(data) for name, data in actual.items())
            or staged["predecessor_revision"] != 75 or staged["selector"] != "AIRB1"
            or staged["maximum_writes"] != 1
            or staged["target_goals"] != [1941,2098,2016,2609,2201,2040,2047]
            or sweep["status"] != "OFFLINE_CONTINUATION_SWEEP_PASS_NOT_EXECUTABLE"
            or sweep["legs"][0]["goals"] != staged["target_goals"]):
        raise ValueError("r76 staged source or sweep differs")
    build = root / ".firmware-tools/build-configured-diagnostic-candidate-r76--default-4mb-no-psram"
    image = (build / "RoArm-M3_example.ino.bin").read_bytes()
    if (sha(image) != APP_SHA or len(image) != APP_BYTES or len(image) > 0x140000
            or compiled["artifact_hashes"]["RoArm-M3_example.ino.bin"] != APP_SHA
            or not all(marker in image for marker in
                       (b"RCAIRAB201", b"/rocell/air-type-b-hover/start", b"AIRB1"))
            or b"/rocell/air-type/start" in image or b"AIR17" in image):
        raise ValueError("r76 app image differs")
    for suffix, digest in (("bootloader.bin", "b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7"),
                           ("partitions.bin", "148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1")):
        name = "RoArm-M3_example.ino." + suffix
        if sha((build / name).read_bytes()) != digest or compiled["artifact_hashes"][name] != digest:
            raise ValueError("Protected build artifact differs")
    report = dict(schema="rocell.r76_b_hover_review.v1",
                  target="configured-diagnostic-candidate-r76", app_sha256=APP_SHA,
                  app_bytes=APP_BYTES, app_offset=0x10000, app_slot_bytes=0x140000,
                  predecessor_revision=75, predecessor_sha256=R75_APP_SHA,
                  compile_export_id=COMPILE, compile_report_sha256=compile_digest,
                  stage_export_id=STAGE, stage_report_sha256=stage_digest,
                  sweep_export_id=PREVIEW, sweep_report_sha256=sweep_digest,
                  selector="AIRB1", maximum_writes=1,
                  source_goals=staged["source_goals"], target_goals=staged["target_goals"],
                  synchronized_servo_ids=[11,12,13,14,15,16,17],
                  requires_durable_export_receipt=True, retry_allowed=False,
                  settings_preserved_by_design=True, hardware_access=False,
                  firmware_uploaded=False, deployment_authorized=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r76-b-hover-review"}, [], attachments={
        "r76-b-hover-review.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Review export invalid")
    return saved["path"]


if __name__ == "__main__":
    print(review(Path(__file__).resolve().parents[1]))
