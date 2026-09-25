"""One installed-r90 source-pose acquisition; never sends a movement command."""

import argparse
import hashlib
import http.client
import json
from pathlib import Path

from rocell.application.pose_observation_capture import capture_pose
from rocell.application.product_ghost_export_review import _read
from rocell.application.servo_diagnostic_http import DiagnosticHTTPReader
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


REVIEW = "wizard-20260925T115402595189Z-52243d92ed6a4a9fb9d235b5236d2bf6"
APP_SHA = "f3d5705b16eedfd49b11fec668da1709eee71d50345ceb07eadf26f0384fe129"
RELEASE_SHA = "65f0106f05de4e8edf68fbd7729a807ebab179c4b86b9e5e37bba5dca9d7a538"


def get(address: str, path: str, limit: int) -> tuple[int, bytes]:
    address = DiagnosticHTTPReader(address, 80).address
    connection = http.client.HTTPConnection(address, 80, timeout=3)
    try:
        connection.request("GET", path, headers={"Accept-Encoding": "identity"})
        response = connection.getresponse()
        raw = response.read(limit + 1)
        status = response.status
    finally:
        connection.close()
    if len(raw) > limit:
        raise ValueError("Controller response exceeds bound")
    return status, raw


def inspect(root: Path, address: str) -> dict:
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    reviewed, _ = _read(exports, REVIEW, "attachment-r90-pose-hover-candidate-review.json")
    app = (root / ".firmware-tools/build-configured-diagnostic-candidate-r90--default-4mb-no-psram"
           / "RoArm-M3_example.ino.bin").read_bytes()
    journal = (root / "private-backups/controller-20260918-session1"
               / "app-r90-deployment-events.jsonl")
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    if (reviewed.get("app_sha256") != APP_SHA
            or reviewed.get("release_sha256") != RELEASE_SHA
            or hashlib.sha256(app).hexdigest() != APP_SHA
            or [row.get("stage") for row in rows] != [
                "RESERVED", "IDENTITY_AND_PREWRITE_VERIFIED", "WRITE_ATTEMPT_STARTED",
                "FLASH_VERIFIED", "ONE_STARTUP_ATTEMPT", "STARTUP_RESET_SENT"]
            or rows[1].get("mac") != "fc:e8:c0:f8:d5:38"
            or rows[3].get("app_sha256") != APP_SHA
            or rows[3].get("protected_regions_unchanged") is not True):
        raise ValueError("r90 installation not verified")
    status, raw = get(address, "/rocell/reviewed-hover/capabilities", 512)
    if status != 200:
        raise ValueError("r90 public capabilities unavailable")
    caps = json.loads(raw)
    if (type(caps) is not dict or caps.get("schema") != "rocell.reviewed_hover_capabilities.v1"
            or caps.get("stamped_release_sha256") != RELEASE_SHA
            or caps.get("motion_authorized") is not False
            or caps.get("live_release_available") is not True
            or caps.get("maximum_legs") != 16):
        raise ValueError("r90 runtime capabilities differ")
    boot = caps.get("boot_id")
    if (type(boot) is not str or len(boot) != 32 or
            any(char not in "0123456789abcdef" for char in boot) or
            (exports / f"pose-observation-{boot}.json").exists() or
            (exports / f"reviewed-hover-live-{boot}.json").exists()):
        raise ValueError("Invalid or consumed r90 boot")
    route_status, route_raw = get(address, "/rocell/pose/record?index=0", 128)
    if route_status != 404 or route_raw != b'{"error":"POSE_RECORD_UNAVAILABLE"}':
        raise ValueError("r90 acquisition route not present and idle")
    return dict(schema="rocell.r90_pose_startup_preflight.v1",
                status="ROUTE_PRESENT_NO_RECORD", boot_id=boot,
                release_sha256=RELEASE_SHA, installed_app_sha256=APP_SHA,
                installed_journal_sha256=hashlib.sha256(journal.read_bytes()).hexdigest(),
                route_status=route_status, route_response=route_raw.decode("ascii"),
                movement_command_sent=False, source_pose_verified=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--capture-no-motion", action="store_true")
    parser.add_argument("--address", default="192.168.0.225")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = inspect(root, args.address)
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r90-pose-startup-preflight"}, [],
                            attachments={"r90-pose-startup-preflight.json":
                                         json.dumps(report, sort_keys=True).encode()})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("r90 startup preflight export invalid")
    if args.preflight_only:
        print(json.dumps(dict(report=report, export=saved["path"],
                              pose_capture_attempted=False)))
        return
    result = capture_pose(root / "runs/wizard-exports", address=args.address,
                          expected_boot=report["boot_id"], scan_id="r90-pose-1",
                          authorized=True)
    print(json.dumps(dict(startup_export=saved["path"], capture=result)))


if __name__ == "__main__":
    main()
