"""One attended gripper-open attempt over the verified local USB serial port.

Never retries a write, closes the gripper, or commands another joint.
"""
import hashlib
import http.client
import json
from pathlib import Path
import re
import sys
import time

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

if __package__:
    from .deploy_reviewed_hover_r89 import PORT, USB_SERIAL
    from .deploy_r92_gripper_loading import APP_SHA
else:
    from deploy_reviewed_hover_r89 import PORT, USB_SERIAL
    from deploy_r92_gripper_loading import APP_SHA

ADDRESS = "192.168.0.225"
EXPECTED_POS = [2041, 2081, 2033, 2609, 2233, 2041, 2047]
EXPECTED_GOAL = [2047, 2075, 2039, 2600, 2233, 2040, 2047]


def capabilities() -> dict:
    connection = http.client.HTTPConnection(ADDRESS, 80, timeout=3)
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
            "schema", "boot_id", "one_open_write_max", "other_joint_writes"} or
            data["schema"] != "rocell.gripper_loader.v1" or
            data["one_open_write_max"] is not True or
            data["other_joint_writes"] is not False or
            type(boot) is not str or not re.fullmatch(r"[0-9a-f]{32}", boot)):
        raise ValueError("Unexpected gripper-loader identity")
    return data


def receive(port, prefix: str, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = port.readline(256)
        if not raw:
            continue
        line = raw.decode("ascii", errors="replace").strip()
        if line.startswith("FAULT:"):
            raise ValueError(line)
        if line.startswith(prefix):
            return line
    raise TimeoutError(f"No {prefix} response")


def snapshot(port, boot: str) -> dict:
    port.write(b"SNAP\n"); port.flush()
    fields = receive(port, "SNAP:", 5).split(":")
    if len(fields) != 16 or fields[1] != boot:
        raise ValueError("Snapshot identity or length differs")
    values = [int(value) for value in fields[2:]]
    if any(not 0 <= value <= 4095 for value in values):
        raise ValueError("Snapshot count outside servo range")
    return dict(positions=values[:7], goals=values[7:])


def main(*, hands_clear: bool) -> dict:
    if hands_clear is not True:
        raise ValueError("Fresh hands-clear confirmation required")
    root = Path(__file__).resolve().parents[1]
    exports = root / "runs/wizard-exports"
    app = (root / ".firmware-tools/build-configured-diagnostic-candidate-r92--default-4mb-no-psram"
           / "RoArm-M3_example.ino.bin").read_bytes()
    if hashlib.sha256(app).hexdigest() != APP_SHA:
        raise ValueError("Installed candidate image no longer pinned")
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
    report = dict(schema="rocell.gripper_open_attempt.v1", boot_id=boot,
                  app_sha256=APP_SHA, category="NOT_STARTED", one_write_max=True,
                  retry_allowed=False, other_joint_write=False,
                  hands_clear_confirmed=True)
    def save():
        saved = exporter.export({"mode": "r92-gripper-open"}, [],
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
        target = before["positions"][6] - 200
        report.update(category="INTENT_EXPORTED", target_count=target,
                      command="OPEN", gripper_servo_id=17, speed=40,
                      acceleration=1)
        report["intent_export"] = save()
        publish_reservation_bytes(exports, marker.name,
            canonical(dict(boot_id=boot, target_count=target,
                           intent_export=Path(report["intent_export"]).name,
                           retry_allowed=False)), maximum_bytes=1024)
        # Exactly one actuator request. A lost response is an uncertain attempt,
        # never grounds for retransmission.
        port.write(f"OPEN:{boot}\n".encode("ascii")); port.flush()
        report["write_attempted"] = True
        sent = receive(port, "OPEN_SENT:", 8)
        if sent != f"OPEN_SENT:{boot}:{target}":
            raise ValueError("Opening acknowledgement differs")
        report["sent"] = sent
        verified = receive(port, "OPEN_VERIFIED:", 12)
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
