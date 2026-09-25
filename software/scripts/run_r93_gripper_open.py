"""One attended r93 gripper opening; no retries or other actuator commands."""
import hashlib
import http.client
import json
from pathlib import Path
import re
import sys

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

if __package__:
    from .deploy_reviewed_hover_r89 import PORT, USB_SERIAL
    from .review_r93_gripper_candidate import APP_SHA
    from .run_r92_gripper_open import receive, snapshot, EXPECTED_POS, EXPECTED_GOAL
else:
    from deploy_reviewed_hover_r89 import PORT, USB_SERIAL
    from review_r93_gripper_candidate import APP_SHA
    from run_r92_gripper_open import receive, snapshot, EXPECTED_POS, EXPECTED_GOAL


def capabilities() -> dict:
    connection = http.client.HTTPConnection("192.168.0.225", 80, timeout=3)
    try:
        connection.request("GET", "/rocell/gripper-loader/capabilities")
        response = connection.getresponse()
        raw = response.read(513)
        if response.status != 200 or len(raw) > 512:
            raise ValueError("Gripper-loader identity unavailable")
        data = json.loads(raw)
    finally:
        connection.close()
    boot = data.get("boot_id") if type(data) is dict else None
    if (type(data) is not dict or set(data) != {
            "schema", "boot_id", "one_open_write_max", "manual_close_steps_max",
            "automatic_close", "other_joint_writes"} or
            data["schema"] != "rocell.gripper_loader.v2" or
            data["one_open_write_max"] is not True or
            data["manual_close_steps_max"] != 4 or
            data["automatic_close"] is not False or
            data["other_joint_writes"] is not False or
            type(boot) is not str or not re.fullmatch(r"[0-9a-f]{32}", boot)):
        raise ValueError("Unexpected gripper-loader identity")
    return data


def main(*, hands_clear: bool) -> dict:
    if hands_clear is not True:
        raise ValueError("Fresh hands-clear confirmation required")
    root = Path(__file__).resolve().parents[1]
    exports = root / "runs/wizard-exports"
    app = (root / ".firmware-tools/build-configured-diagnostic-candidate-r93--default-4mb-no-psram"
           / "RoArm-M3_example.ino.bin").read_bytes()
    if hashlib.sha256(app).hexdigest() != APP_SHA:
        raise ValueError("Installed candidate image no longer pinned")
    journal = root / "private-backups/controller-20260918-session1/app-r93-deployment-events.jsonl"
    stages = [json.loads(line) for line in journal.read_text().splitlines()]
    if ([row.get("stage") for row in stages] != [
            "RESERVED", "IDENTITY_AND_PREWRITE_VERIFIED", "WRITE_ATTEMPT_STARTED",
            "FLASH_VERIFIED", "ONE_STARTUP_ATTEMPT", "STARTUP_RESET_SENT"] or
            stages[3].get("app_sha256") != APP_SHA or
            stages[3].get("protected_regions_unchanged") is not True):
        raise ValueError("r93 install not verified")
    caps = capabilities(); boot = caps["boot_id"]
    marker = exports / f"gripper-open-{boot}.json"
    if marker.exists():
        raise ValueError("This boot already has an opening attempt")
    pinned = root / ".firmware-tools/esptool-api-4.6"
    sys.path.insert(0, str(pinned))
    import serial
    from serial.tools.list_ports import comports
    if serial.__version__ != "3.5" or not Path(serial.__file__).resolve().is_relative_to(pinned):
        raise ValueError("Unpinned serial implementation")
    matches = [item for item in comports() if item.device == PORT and
               item.vid == 0x10c4 and item.pid == 0xea60 and
               item.serial_number == USB_SERIAL]
    if len(matches) != 1:
        raise ValueError("Controller USB adapter differs")
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    report = dict(schema="rocell.gripper_open_attempt.v2", boot_id=boot,
                  app_sha256=APP_SHA, category="NOT_STARTED", one_write_max=True,
                  retry_allowed=False, other_joint_write=False,
                  hands_clear_confirmed=True)
    def save():
        saved = exporter.export({"mode": "r93-gripper-open"}, [],
            attachments={"gripper-open-attempt.json": canonical(report)})
        if not verify_export(Path(saved["path"]))["valid"]:
            raise ValueError("Gripper export failed")
        return saved["path"]
    port = serial.Serial(port=None, baudrate=115200, timeout=0.25, write_timeout=2)
    port.dtr = False; port.rts = False; port.port = PORT
    try:
        port.open()
        if capabilities() != caps:
            raise ValueError("Controller restarted on serial open")
        before = snapshot(port, boot)
        report["before"] = before
        if (before["goals"] != EXPECTED_GOAL or
                any(abs(actual - expected) > 40 for actual, expected in
                    zip(before["positions"], EXPECTED_POS)) or
                before["positions"][6] < 1000):
            raise ValueError("Current pose differs from reviewed source")
        expected_target = before["positions"][6] - 200
        report.update(category="INTENT_EXPORTED", expected_target_count=expected_target,
                      command="OPEN", gripper_servo_id=17, speed=40,
                      acceleration=1)
        report["intent_export"] = save()
        publish_reservation_bytes(exports, marker.name,
            canonical(dict(boot_id=boot, expected_target_count=expected_target,
                           intent_export=Path(report["intent_export"]).name,
                           retry_allowed=False)), maximum_bytes=1024)
        port.write(f"OPEN:{boot}\n".encode("ascii")); port.flush()
        report["write_attempted"] = True
        sent = receive(port, "OPEN_SENT:", 8)
        sent_parts = sent.split(":")
        if (len(sent_parts) != 3 or sent_parts[:2] != ["OPEN_SENT", boot] or
                not sent_parts[2].isdigit() or
                abs(int(sent_parts[2]) - expected_target) > 8):
            raise ValueError("Opening acknowledgement differs")
        target = int(sent_parts[2])
        report["actual_target_count"] = target
        report["sent"] = sent
        verified = receive(port, "OPEN_VERIFIED:", 12)
        verified_parts = verified.split(":")
        if (len(verified_parts) != 3 or verified_parts[0] != "OPEN_VERIFIED" or
                not all(value.isdigit() for value in verified_parts[1:]) or
                abs(int(verified_parts[1]) - before["positions"][6]) > 8 or
                abs(int(verified_parts[2]) - target) > 25):
            raise ValueError("Controller verification counts differ")
        report["controller_verification"] = verified
        port.write(b"STATUS\n"); port.flush()
        status = receive(port, "STATUS:", 3)
        if status != f"STATUS:{boot}:1:1:1":
            raise ValueError("Controller terminal status differs")
        after = snapshot(port, boot)
        report["after"] = after
        if (after["goals"][:6] != before["goals"][:6] or
                any(abs(a - b) > 16 for a, b in
                    zip(after["positions"][:6], before["positions"][:6])) or
                after["goals"][6] != target or
                abs(after["positions"][6] - target) > 25):
            raise ValueError("Final all-joint readback differs")
        report["category"] = "OPEN_VERIFIED"
    except BaseException as error:
        report.update(category="STOPPED_UNCERTAIN", error_type=type(error).__name__,
                      error=str(error))
    finally:
        if port.is_open:
            port.close()
    report["final_export"] = save()
    return report


if __name__ == "__main__":
    raise SystemExit("Invoke main(hands_clear=True) only after live operator confirmation")
