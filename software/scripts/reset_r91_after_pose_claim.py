"""One controller-only restart after r91's pose-capture reservation fault.

No flash write, servo command, or torque-off. Physical catch/support must be
in place before --one-startup-no-motion. External servo power stays connected.
"""

import argparse
import json
from pathlib import Path
import sys

from run_r90_pose_observation import get
from run_r91_recovery_cycle import BOOT, R91_RELEASE_SHA
from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


STATUS_EXPORT = "wizard-20260925T135702313279Z-63065a25d9334fcd85a2ea1ea004acb6"
USB_SERIAL = "52E4E1E8337FEF119E92181CEDD322A4"


def preflight(root: Path, address: str) -> dict:
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    status, _ = _read(exports, STATUS_EXPORT, "attachment-result.json")
    if (status.get("schema") != "rocell.r91_rejected_start_status_intent.v1" or
            status.get("boot_id") != BOOT or
            status.get("status") != "AUTHENTICATED_READ_ONLY_STATUS" or
            status.get("status_response") != "RESERVATION_FAILED|1" or
            status.get("movement_command_sent") is not False):
        raise ValueError("Exact read-only reservation fault evidence required")
    if (not (exports / f"pose-observation-{BOOT}.json").exists() or
            not (exports / f"recovery-hover-live-{BOOT}.json").exists() or
            (exports / f"r91-reset-after-pose-{BOOT}.json").exists()):
        raise ValueError("Expected claimed boot or reset-attempt state differs")
    code, raw = get(address, "/rocell/recovery-hover/capabilities", 512)
    caps = json.loads(raw)
    if (code != 200 or caps.get("boot_id") != BOOT or
            caps.get("stamped_release_sha256") != R91_RELEASE_SHA or
            caps.get("maximum_legs") != 5):
        raise ValueError("r91 boot changed; do not reset")
    return dict(schema="rocell.r91_pose_claim_reset_preflight.v1",
                old_boot_id=BOOT, release_sha256=R91_RELEASE_SHA,
                status="EXACT_POSE_CLAIMED_BOOT_VERIFIED",
                flash_written=False, movement_command_sent=False,
                torque_off_command_sent=False, reset_sent=False,
                physical_support_verified=False, retry_allowed=False)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--one-startup-no-motion", action="store_true")
    parser.add_argument("--supported-for-reset", action="store_true")
    parser.add_argument("--address", default="192.168.0.225")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    exports = root / "runs/wizard-exports"
    report = preflight(root, args.address)
    if args.preflight_only:
        print(json.dumps(report))
        return
    if not args.supported_for_reset:
        raise ValueError("Physical support for startup torque loss required")
    pinned = root / ".firmware-tools/esptool-api-4.6"
    sys.path.insert(0, str(pinned))
    import serial
    from serial.tools.list_ports import comports
    import esptool
    from esptool.reset import HardReset
    if (serial.__version__ != "3.5" or esptool.__version__ != "4.6" or
            not Path(serial.__file__).resolve().is_relative_to(pinned.resolve()) or
            not Path(esptool.__file__).resolve().is_relative_to(pinned.resolve())):
        raise ValueError("Unexpected pinned reset tooling")
    matches = [port for port in comports() if port.device == "COM7"
               and port.vid == 0x10C4 and port.pid == 0xEA60
               and port.serial_number == USB_SERIAL]
    if len(matches) != 1:
        raise ValueError("Expected controller USB adapter not identified")
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    report["physical_support_verified"] = True
    saved = exporter.export({"mode": "r91-pose-claim-reset-intent"}, [],
                            attachments={"intent.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Reset intent export invalid")
    publish_reservation_bytes(exports, f"r91-reset-after-pose-{BOOT}.json",
        canonical(dict(old_boot_id=BOOT, intent_export=Path(saved["path"]).name,
                       retry_allowed=False)), maximum_bytes=2048)
    port = serial.Serial(port=None, baudrate=115200, timeout=2, write_timeout=2)
    port.dtr = False
    port.rts = False
    port.port = "COM7"
    report["status"] = "RESET_OUTCOME_UNCERTAIN"
    try:
        port.open()
        HardReset(port)()
        report["status"] = "ONE_RESET_SENT_STARTUP_NOT_YET_VERIFIED"
        report["reset_sent"] = True
    finally:
        try:
            port.close()
        finally:
            saved = exporter.export({"mode": "r91-pose-claim-reset-result"}, [],
                                    attachments={"result.json": canonical(report)})
            if not verify_export(Path(saved["path"]))["valid"]:
                raise ValueError("Reset result export invalid")
    print(json.dumps(dict(status=report["status"], export=saved["path"])))


if __name__ == "__main__":
    main()
