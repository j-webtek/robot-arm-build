"""Independent offline r91 source/image/route review; never opens a device."""
import hashlib
import json
from pathlib import Path
import subprocess

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.reviewed_hover_recovery_admission import (
    recovery_manifest, validate_recovery_manifest,
)
from rocell.application.reviewed_hover_release_identity import (
    render_release_stamp, verify_release_pair,
)
from rocell.application.wizard_diagnostic_export import (
    WizardDiagnosticExporter, verify_export,
)


TARGET = "configured-diagnostic-candidate-r91"
STAGE = "wizard-20260925T132159536186Z-6178f1d1529945e594e061a3ccef2309"
COMPILE = "wizard-20260925T132349806995Z-da12dbd84fbc43e795e64eb8da6e7361"
EXPECTED_CHANGED = {"reviewed_hover_board.h", "reviewed_hover_composition.h",
                    "reviewed_hover_owner.h", "reviewed_hover_release_stamp.h",
                    "reviewed_hover_routes.h"}
EXPECTED_ADDED = {"reviewed_hover_recovery_board_adapter.h",
                  "reviewed_hover_recovery_admission.h",
                  "reviewed_hover_recovery_policy.h"}


def review(root: Path) -> dict:
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    stage, _ = _read(exports, STAGE, "attachment-r91-hover-recovery-stage.json")
    compiled, _ = _read(exports, COMPILE, "attachment-compile-review.json")
    sha = lambda data: hashlib.sha256(data).hexdigest()
    if (stage.get("status") != "STAGED_OFFLINE" or
            stage.get("predecessor_app_sha256") !=
            "f3d5705b16eedfd49b11fec668da1709eee71d50345ceb07eadf26f0384fe129" or
            stage.get("predecessor_release_sha256") !=
            "65f0106f05de4e8edf68fbd7729a807ebab179c4b86b9e5e37bba5dca9d7a538" or
            stage.get("recipe_sha256") != validate_recovery_manifest(recovery_manifest()) or
            set(stage.get("changed_files", {})) != EXPECTED_CHANGED or
            set(stage.get("added_files", {})) != EXPECTED_ADDED or
            stage.get("route_owner") != "recovery_hover_only" or
            stage.get("extra_route") != "pose_observation_acquisition_only" or
            stage.get("firmware_uploaded") is not False or
            compiled.get("status") != "COMPILED" or
            compiled.get("target") != TARGET or
            compiled.get("build_profile") != "default-4mb-no-psram"):
        raise ValueError("r91 stage or compile contract differs")
    compiled_sources = {name.replace("\\", "/"): digest for name, digest in
                        compiled["source_hashes"].items()
                        if not name.replace("\\", "/").endswith(
                            "/reviewed_hover_release_stamp.h")}
    if compiled_sources != stage["source_hashes"]:
        raise ValueError("r91 compiled source differs from staged release")
    source_bytes = {name: (root / name).read_bytes() for name in compiled_sources}
    staged = root / ".firmware-tools" / TARGET / "RoArm-M3_example"
    stamp = (staged / "reviewed_hover_release_stamp.h").read_bytes()
    if stamp != render_release_stamp(stage["release_sha256"]):
        raise ValueError("r91 embedded release stamp differs")
    build = root / f".firmware-tools/build-{TARGET}--default-4mb-no-psram"
    app = (build / "RoArm-M3_example.ino.bin").read_bytes()
    if not 0 < len(app) <= 0x140000:
        raise ValueError("r91 app outside app-only slot")
    record = dict(schema="rocell.reviewed_hover_release_review.v1",
                  release_sha256=stage["release_sha256"], app_sha256=sha(app),
                  app_bytes=len(app), app_offset=0x10000, app_slot_bytes=0x140000,
                  recipe_sha256=stage["recipe_sha256"],
                  source_hashes=compiled_sources,
                  toolchain_lock_sha256=compiled["toolchain_lock_sha256"],
                  build_profile="default-4mb-no-psram", target=TARGET,
                  compile_review_sha256=sha(canonical(compiled)),
                  hardware_access=False, firmware_uploaded=False,
                  deployment_authorized=False)
    verify_release_pair(record, compile_report=compiled,
                        source_bytes=source_bytes, app_image=app)
    required_routes = (b"/rocell/recovery-hover/start",
                       b"/rocell/recovery-hover/capabilities",
                       b"/rocell/pose/capture", b"/rocell/pose/record")
    forbidden_routes = (b"/rocell/reviewed-hover/start",
                        b"/rocell/reviewed-hover/capabilities")
    if (any(route not in app for route in required_routes) or
            any(route in app for route in forbidden_routes)):
        raise ValueError("r91 linked route selection differs")
    nm = root / ".firmware-tools/data/packages/esp32/tools/esp-x32/2302/bin/xtensa-esp32-elf-nm.exe"
    symbols = subprocess.run([str(nm), "-C", str(build / "RoArm-M3_example.ino.elf")],
                             check=True, capture_output=True, text=True,
                             timeout=30).stdout
    required_symbols = ("registerShoulderSessionRoutes()",
                        "registerPoseObservationRoutes()", "pollPoseObservation()")
    forbidden_symbols = ("registerDiagnosticRoutes()", "webCtrlServer()",
                         "initHttpWebServer()")
    if (any(symbol not in symbols for symbol in required_symbols) or
            any(symbol in symbols for symbol in forbidden_symbols)):
        raise ValueError("r91 linked entrypoints differ")
    return dict(schema="rocell.r91_hover_recovery_candidate_review.v1",
                status="COMPILED_ROUTE_PRESENT_NOT_DEPLOYED",
                app_sha256=sha(app), app_bytes=len(app),
                release_sha256=stage["release_sha256"],
                recipe_sha256=stage["recipe_sha256"],
                predecessor_app_sha256=stage["predecessor_app_sha256"],
                app_offset=0x10000, app_slot_bytes=0x140000,
                linked_entrypoints=list(required_symbols),
                absent_entrypoints=list(forbidden_symbols),
                recovery_route_present=True, pose_route_present=True,
                r90_route_absent=True, hardware_access=False,
                firmware_uploaded=False, deployment_authorized=False,
                movement_tested=False)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    report = review(root)
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r91-hover-recovery-candidate-review"}, [],
        attachments={"r91-hover-recovery-candidate-review.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r91 candidate review export invalid")
    print(json.dumps(dict(report=report, export=saved["path"])))
