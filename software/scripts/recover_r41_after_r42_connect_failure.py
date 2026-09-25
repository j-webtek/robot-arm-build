"""One recovery startup after the exact prewrite r42 connection failure.

This does not flash, reconnect the ROM loader, issue servo commands, or retry the
installation. It refuses to operate unless the retained deployment journal proves
that the r42 attempt stopped before the write-attempt stage.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_installation_evidence import review_pair_installation
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R42_SHA256 = "6d3405b3b42db9347ec02445b0937886ca0fba82bf38d905e3989ad48c8f71ea"
FAILED_JOURNAL_SHA256 = "30abc7feff8027500a38c712b3e239be59cb81ae438ca6139495737dd3bde8ea"


def validate_failure(raw: bytes) -> list[dict]:
    if hashlib.sha256(raw).hexdigest() != FAILED_JOURNAL_SHA256:
        raise ValueError("Failed r42 journal changed")
    rows = [json.loads(line) for line in raw.splitlines()]
    expected = dict(stage="RESERVED", app_sha256=R42_SHA256, offset=65536, bytes=1156992)
    if (
        len(rows) != 2
        or rows[0] != expected
        or rows[1].get("stage") != "STOPPED"
        or rows[1].get("error_type") != "FatalError"
        or rows[1].get("retry") is not False
        or not rows[1].get("error", "").startswith(
            "Failed to connect to ESP32: Download mode successfully detected, but getting no sync reply:"
        )
    ):
        raise ValueError("Not the exact prewrite-only r42 failure; no reset")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorized-recovery-startup", action="store_true", required=True)
    parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    exports = root / "runs/wizard-exports"
    journal = root / "private-backups/controller-20260918-session1/app-r42-deployment-events.jsonl"
    raw = journal.read_bytes()
    validate_failure(raw)
    installation = review_pair_installation(root, revision=41)
    claim = "r42-prewrite-recovery-r41-startup.json"
    if (exports / claim).exists():
        raise ValueError("Recovery startup already attempted")

    import serial
    from serial.tools.list_ports import comports

    matches = [
        port
        for port in comports()
        if port.device == "COM7"
        and port.vid == 0x10C4
        and port.pid == 0xEA60
        and port.serial_number == "52E4E1E8337FEF119E92181CEDD322A4"
    ]
    if len(matches) != 1:
        raise ValueError("Expected USB adapter not identified")

    pinned = root / ".firmware-tools/esptool-api-4.6"
    sys.path.insert(0, str(pinned))
    import esptool
    from esptool.reset import HardReset

    if esptool.__version__ != "4.6" or not Path(esptool.__file__).resolve().is_relative_to(pinned.resolve()):
        raise ValueError("Unexpected reset implementation")

    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    report = dict(
        schema="rocell.r42_prewrite_recovery_r41_startup.v1",
        status="PREPARED",
        installation=installation,
        failed_journal_sha256=FAILED_JOURNAL_SHA256,
        servo_command_sent=False,
        flash_written=False,
        settings_written=False,
        retry_allowed=False,
    )

    def save():
        result = exporter.export(
            {"mode": "r42-prewrite-recovery-r41-startup"},
            [],
            attachments={"recovery-startup.json": canonical(report)},
        )
        if not verify_export(Path(result["path"]))["valid"]:
            raise ValueError("Export failed")
        return result

    intent = save()
    publish_reservation_bytes(
        exports,
        claim,
        canonical(dict(intent_export=Path(intent["path"]).name, authorized=True, retry_allowed=False)),
        maximum_bytes=2048,
    )
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
            result = save()
    time.sleep(18)
    print(canonical(dict(export_path=result["path"], status=report["status"])).decode())


if __name__ == "__main__":
    main()
