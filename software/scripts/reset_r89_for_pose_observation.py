"""One r89 startup for acquisition-only pose diagnostics; no flash or movement."""

import argparse
import json
from pathlib import Path
import sys

from preflight_r89_live_campaign import current_capabilities, local_install_review
from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


USB_SERIAL = "52E4E1E8337FEF119E92181CEDD322A4"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--one-startup-no-motion", action="store_true")
    parser.add_argument("--address", default="192.168.0.225")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    exports = root / "runs/wizard-exports"
    installation = local_install_review(root)
    current = current_capabilities(args.address)
    old_boot = current["boot_id"]
    if old_boot != installation["previous_boot_id"]:
        raise ValueError("Expected consumed pre-diagnostic boot differs")
    marker = f"r89-pose-observation-reset-{old_boot}.json"
    if (exports / marker).exists():
        raise ValueError("One reset already attempted from this boot")
    if args.preflight_only:
        print(json.dumps(dict(status="R89_POSE_RESET_PREFLIGHT_VERIFIED",
                              old_boot_id=old_boot, hardware_access=False,
                              movement_command_sent=False)))
        return

    import serial
    from serial.tools.list_ports import comports

    matches = [port for port in comports() if port.device == "COM7"
               and port.vid == 0x10C4 and port.pid == 0xEA60
               and port.serial_number == USB_SERIAL]
    if len(matches) != 1:
        raise ValueError("Expected controller USB adapter not identified")
    pinned = root / ".firmware-tools/esptool-api-4.6"
    sys.path.insert(0, str(pinned))
    import esptool
    from esptool.reset import HardReset

    if esptool.__version__ != "4.6" or not Path(esptool.__file__).resolve().is_relative_to(pinned.resolve()):
        raise ValueError("Unexpected reset implementation")
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    report = dict(schema="rocell.r89_pose_observation_reset.v1",
                  status="PREPARED", old_boot_id=old_boot,
                  installation_journal_sha256=installation["installed_journal_sha256"],
                  flash_written=False, movement_command_sent=False,
                  retry_allowed=False)

    def save() -> dict:
        saved = exporter.export({"mode": "r89-pose-observation-reset"}, [],
                                attachments={"r89-pose-observation-reset.json":
                                             canonical(report)})
        if not verify_export(Path(saved["path"]))["valid"]:
            raise ValueError("Reset report export failed")
        return saved

    intent = save()
    publish_reservation_bytes(exports, marker,
                              canonical(dict(intent_export=Path(intent["path"]).name,
                                             old_boot_id=old_boot, retry_allowed=False)),
                              maximum_bytes=2048)
    port = serial.Serial(port=None, baudrate=115200, timeout=2, write_timeout=2)
    port.dtr = False
    port.rts = False
    port.port = "COM7"
    report["status"] = "RESET_UNCERTAIN"
    try:
        port.open()
        HardReset(port)()
        report["status"] = "ONE_RESET_SENT_STARTUP_NOT_YET_VERIFIED"
    finally:
        try:
            port.close()
        finally:
            saved = save()
    print(json.dumps(dict(status=report["status"], export=saved["path"],
                          old_boot_id=old_boot)))


if __name__ == "__main__":
    main()
