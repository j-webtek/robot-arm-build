"""Offline review of r89's unavailable pose endpoint; never contacts hardware."""

import hashlib
import json
from pathlib import Path
import subprocess

from preflight_r89_live_campaign import local_install_review
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


CAPTURE = "wizard-20260925T114529494205Z-a62d81e5d3394c3990fd85a16690ae59"
RESET = "wizard-20260925T114424765909Z-0306d824772049bcbafc0f56069145c3"


def review(root: Path) -> dict:
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    installed = local_install_review(root)
    reset, _ = _read(exports, RESET, "attachment-r89-pose-observation-reset.json")
    capture, _ = _read(exports, CAPTURE, "attachment-pose-capture.json")
    if (reset.get("status") != "ONE_RESET_SENT_STARTUP_NOT_YET_VERIFIED"
            or reset.get("old_boot_id") != installed["previous_boot_id"]
            or capture.get("subject", {}).get("expected_boot") == reset["old_boot_id"]
            or capture.get("subject", {}).get("expected_id") != "r89-pose-2"
            or capture.get("responses") != []
            or capture.get("category") != "INCONCLUSIVE"
            or capture.get("error_type") != "PoseHTTPStatus"
            or capture.get("http_status") != 404
            or capture.get("progression_authority") is not False):
        raise ValueError("Pinned capture failure differs")

    build = root / ".firmware-tools/build-configured-diagnostic-candidate-r89--default-4mb-no-psram"
    app = (build / "RoArm-M3_example.ino.bin").read_bytes()
    if hashlib.sha256(app).hexdigest() != installed["app_sha256"]:
        raise ValueError("Installed app candidate differs")
    nm = root / ".firmware-tools/data/packages/esp32/tools/esp-x32/2302/bin/xtensa-esp32-elf-nm.exe"
    symbols = subprocess.run([str(nm), "-C", str(build / "RoArm-M3_example.ino.elf")],
                             check=True, capture_output=True, text=True).stdout
    staged = root / ".firmware-tools/configured-diagnostic-candidate-r89/RoArm-M3_example"
    boot = (staged / "diagnostic_boot.h").read_text(encoding="utf-8")
    pair_routes = (staged / "configured_pair_board_routes.h").read_text(encoding="utf-8")
    if ("registerShoulderSessionRoutes();" not in boot
            or "registerDiagnosticRoutes();" in boot
            or "registerPoseObservationRoutes();" not in pair_routes
            or "registerShoulderSessionRoutes()" not in symbols
            or "registerPoseObservationRoutes()" in symbols
            or "registerDiagnosticRoutes()" in symbols
            or b"/rocell/reviewed-hover/start" not in app
            or b"/rocell/pose/capture" in app
            or b"/rocell/pose/record" in app):
        raise ValueError("Expected r89 linker/route selection differs")
    return dict(schema="rocell.r89_pose_route_failure_review.v1",
                status="POSE_ROUTE_NOT_LINKED_IN_INSTALLED_R89",
                installed_app_sha256=installed["app_sha256"],
                release_sha256=installed["release_sha256"],
                failed_capture_boot_id=capture["subject"]["expected_boot"],
                failed_capture_http_status=404,
                installed_entrypoint="registerShoulderSessionRoutes",
                absent_entrypoint="registerPoseObservationRoutes",
                pose_route_markers_present=False,
                movement_command_sent=False, firmware_written=False,
                source_pose_verified=False, live_campaign_authorized=False,
                required_change="Build a separately reviewed single-owner image with an acquisition-only source-pose path, or prove source pose by an equivalent independent diagnostic before live movement.")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = review(root)
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r89-pose-route-failure-review"}, [],
                            attachments={"r89-pose-route-failure-review.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Route audit export invalid")
    print(json.dumps(dict(report=report, export=saved["path"])))


if __name__ == "__main__":
    main()
