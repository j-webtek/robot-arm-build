"""One attended 50-count r93 gripper close step; never retries or follows on."""
import json
from pathlib import Path
import sys

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

if __package__:
    from .deploy_reviewed_hover_r89 import PORT, USB_SERIAL
    from .review_r93_gripper_candidate import APP_SHA
    from .run_r93_gripper_open import capabilities, receive, snapshot
else:
    from deploy_reviewed_hover_r89 import PORT, USB_SERIAL
    from review_r93_gripper_candidate import APP_SHA
    from run_r93_gripper_open import capabilities, receive, snapshot

OPEN_BOOT = "cd62bcdcc519b852a0e26fab81c5a8c8"
OPEN_AFTER_POS = [2041, 2081, 2034, 2608, 2233, 2041, 1852]
OPEN_AFTER_GOAL = [2047, 2075, 2039, 2600, 2233, 2040, 1849]


def main(*, stylus_seated_hands_clear: bool) -> dict:
    if stylus_seated_hands_clear is not True:
        raise ValueError("Stylus seating and hands-clear confirmation required")
    root = Path(__file__).resolve().parents[1]
    exports = root / "runs/wizard-exports"
    previous = (exports / "wizard-20260925T151545691214Z-a81b0e7d50474706978fbfa12e9198e8"
                / "attachment-gripper-open-attempt.json")
    if not verify_export(previous.parent)["valid"]:
        raise ValueError("Opening evidence export invalid")
    opening = json.loads(previous.read_text())
    if (opening.get("category") != "OPEN_VERIFIED" or
            opening.get("boot_id") != OPEN_BOOT or
            opening.get("app_sha256") != APP_SHA or
            opening.get("after") != dict(positions=OPEN_AFTER_POS, goals=OPEN_AFTER_GOAL)):
        raise ValueError("Opening evidence differs")
    caps = capabilities(); boot = caps["boot_id"]
    if boot != OPEN_BOOT:
        raise ValueError("Controller boot changed since opening")
    marker = exports / f"gripper-close-1-{boot}.json"
    if marker.exists():
        raise ValueError("Close step one already attempted; no retry")
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
    report = dict(schema="rocell.gripper_close_step.v1", boot_id=boot,
                  app_sha256=APP_SHA, category="NOT_STARTED", step=1,
                  one_write_max=True, retry_allowed=False,
                  other_joint_write=False, stylus_seated_hands_clear=True,
                  grip_retention_verified=False)
    def save():
        saved = exporter.export({"mode": "r93-gripper-close-step1"}, [],
            attachments={"gripper-close-step1.json": canonical(report)})
        if not verify_export(Path(saved["path"]))["valid"]:
            raise ValueError("Close-step export failed")
        return saved["path"]
    port = serial.Serial(port=None, baudrate=115200, timeout=0.25, write_timeout=2)
    port.dtr = False; port.rts = False; port.port = PORT
    try:
        port.open()
        if capabilities() != caps:
            raise ValueError("Controller restarted on serial open")
        before = snapshot(port, boot)
        report["before"] = before
        if (before["goals"] != OPEN_AFTER_GOAL or
                any(abs(a - b) > 16 for a, b in
                    zip(before["positions"][:6], OPEN_AFTER_POS[:6])) or
                abs(before["positions"][6] - OPEN_AFTER_GOAL[6]) > 25):
            raise ValueError("Live pose differs from verified opened pose")
        expected_target = before["positions"][6] + 50
        if expected_target > opening["before"]["positions"][6]:
            raise ValueError("Close step would exceed original jaw count")
        report.update(category="INTENT_EXPORTED", expected_target_count=expected_target,
                      command="CLOSE", gripper_servo_id=17, speed=30,
                      acceleration=1)
        report["intent_export"] = save()
        publish_reservation_bytes(exports, marker.name,
            canonical(dict(boot_id=boot, step=1,
                           expected_target_count=expected_target,
                           intent_export=Path(report["intent_export"]).name,
                           retry_allowed=False)), maximum_bytes=1024)
        port.write(f"CLOSE:{boot}:1\n".encode("ascii")); port.flush()
        report["write_attempted"] = True
        sent = receive(port, "CLOSE_SENT:", 8)
        fields = sent.split(":")
        if (len(fields) != 4 or fields[:3] != ["CLOSE_SENT", boot, "1"] or
                not fields[3].isdigit() or
                abs(int(fields[3]) - expected_target) > 8):
            raise ValueError("Close acknowledgement differs")
        target = int(fields[3]); report["actual_target_count"] = target
        report["sent"] = sent
        verified = receive(port, "CLOSE_VERIFIED:", 12)
        fields = verified.split(":")
        if (len(fields) != 3 or fields[0] != "CLOSE_VERIFIED" or
                not all(value.isdigit() for value in fields[1:]) or
                abs(int(fields[1]) - before["positions"][6]) > 8 or
                abs(int(fields[2]) - target) > 25):
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
        report["category"] = "CLOSE_STEP_VERIFIED"
    except BaseException as error:
        report.update(category="STOPPED_UNCERTAIN", error_type=type(error).__name__,
                      error=str(error))
    finally:
        if port.is_open:
            port.close()
    report["final_export"] = save()
    return report


if __name__ == "__main__":
    raise SystemExit("Invoke main(stylus_seated_hands_clear=True) only after operator confirmation")
