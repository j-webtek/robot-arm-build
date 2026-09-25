"""Send exactly one attended, no-retry r96 registration-ladder leg."""
import hashlib
import http.client
import json
from pathlib import Path
import re
import sys

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.registration_ladder_preview import (
    SOURCE_GOALS, SOURCE_POSITIONS, TARGET_GOALS,
)
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

from deploy_reviewed_hover_r89 import PORT, USB_SERIAL
from review_r96_registration_ladder import APP_SHA
from run_r92_gripper_open import receive, snapshot


def capabilities() -> dict:
    connection = http.client.HTTPConnection("192.168.0.225", 80, timeout=3)
    try:
        connection.request("GET", "/rocell/registration-ladder/capabilities")
        response = connection.getresponse(); raw = response.read(513)
        if response.status != 200 or len(raw) > 512:
            raise ValueError("Registration identity unavailable")
        data = json.loads(raw)
    finally:
        connection.close()
    boot = data.get("boot_id") if type(data) is dict else None
    if (type(data) is not dict or set(data) != {
            "schema", "boot_id", "maximum_legs", "automatic_progression",
            "gripper_writes", "motion_authorized"} or
            data["schema"] != "rocell.registration_ladder.v1" or
            data["maximum_legs"] != 1 or data["automatic_progression"] is not False or
            data["gripper_writes"] is not False or data["motion_authorized"] is not False or
            type(boot) is not str or not re.fullmatch(r"[0-9a-f]{32}", boot)):
        raise ValueError("Unexpected registration app identity")
    return data


def main(*, catch_removed_and_path_clear: bool) -> dict:
    if catch_removed_and_path_clear is not True:
        raise ValueError("Fresh catch-removed and full-path clearance confirmation required")
    root = Path(__file__).resolve().parents[1]; exports = root / "runs/wizard-exports"
    app = (root / ".firmware-tools/build-configured-diagnostic-candidate-r96--default-4mb-no-psram"
           / "RoArm-M3_example.ino.bin").read_bytes()
    if hashlib.sha256(app).hexdigest() != APP_SHA:
        raise ValueError("Installed r96 candidate no longer pinned")
    journal = root / "private-backups/controller-20260918-session1/app-r96-deployment-events.jsonl"
    stages = [json.loads(line) for line in journal.read_text().splitlines()]
    if ([row.get("stage") for row in stages] != [
            "RESERVED", "IDENTITY_AND_PREWRITE_VERIFIED", "WRITE_ATTEMPT_STARTED",
            "FLASH_VERIFIED", "ONE_STARTUP_ATTEMPT", "STARTUP_RESET_SENT"] or
            stages[3].get("app_sha256") != APP_SHA or
            stages[3].get("protected_regions_unchanged") is not True):
        raise ValueError("r96 install journal differs")
    caps = capabilities(); boot = caps["boot_id"]
    marker = exports / f"registration-leg-1-{boot}.json"
    if marker.exists():
        raise ValueError("Registration leg already attempted on this boot")
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
    report = dict(schema="rocell.registration_ladder_leg_attempt.v1", boot_id=boot,
                  app_sha256=APP_SHA, leg=1, category="NOT_STARTED",
                  target_goals=list(TARGET_GOALS), one_write_max=True,
                  retry_allowed=False, automatic_progression=False,
                  catch_removed_and_path_clear=True, physical_contact=False,
                  physical_landmark_observed=False, board_transform_verified=False)

    def save():
        saved = exporter.export({"mode": "r96-registration-ladder-leg"}, [],
            attachments={"registration-ladder-leg.json": canonical(report)})
        if not verify_export(Path(saved["path"]))["valid"]:
            raise ValueError("Registration export failed")
        return saved["path"]

    port = serial.Serial(port=None, baudrate=115200, timeout=0.25, write_timeout=2)
    port.dtr = False; port.rts = False; port.port = PORT
    try:
        port.open()
        if capabilities() != caps:
            raise ValueError("Controller restarted on serial open")
        port.write(b"STATUS\n"); port.flush()
        if receive(port, "STATUS:", 3) != f"STATUS:{boot}:0:0:0":
            raise ValueError("Controller registration status differs")
        before = snapshot(port, boot); report["before"] = before
        if (before["goals"] != list(SOURCE_GOALS) or
                any(abs(a-b) > 16 for a,b in zip(before["positions"], SOURCE_POSITIONS))):
            raise ValueError("Fresh registration source differs")
        selected = [i for i in range(7) if TARGET_GOALS[i] != SOURCE_GOALS[i]]
        if selected != [0] or abs(TARGET_GOALS[0]-SOURCE_GOALS[0]) != 60:
            raise ValueError("Unreviewed registration target")
        report.update(category="INTENT_EXPORTED", selected_joints=selected,
                      speed=20, acceleration=1)
        report["intent_export"] = save()
        publish_reservation_bytes(exports, marker.name,
            canonical(dict(boot_id=boot, leg=1,
                           intent_export=Path(report["intent_export"]).name,
                           retry_allowed=False)), maximum_bytes=1024)
        port.write(f"LEG:{boot}:1\n".encode("ascii")); port.flush()
        report["write_attempted"] = True
        if receive(port, "LEG_SENT:", 8) != f"LEG_SENT:{boot}:1:1":
            raise ValueError("Registration acknowledgement differs")
        if receive(port, "LEG_VERIFIED:", 12) != f"LEG_VERIFIED:{boot}:1":
            raise ValueError("Controller registration verification differs")
        port.write(b"STATUS\n"); port.flush()
        if receive(port, "STATUS:", 3) != f"STATUS:{boot}:1:0:0":
            raise ValueError("Controller registration terminal status differs")
        after = snapshot(port, boot); report["after"] = after
        if (after["goals"] != list(TARGET_GOALS) or
                abs(after["positions"][0] - TARGET_GOALS[0]) > 12 or
                any(abs(after["positions"][i] - before["positions"][i]) > 16
                    for i in range(1, 7))):
            raise ValueError("Final registration readback differs")
        report["category"] = "LEG_VERIFIED"
    except BaseException as error:
        report.update(category="STOPPED_UNCERTAIN", error_type=type(error).__name__,
                      error=str(error))
    finally:
        if port.is_open:
            port.close()
    report["final_export"] = save()
    return report


if __name__ == "__main__":
    raise SystemExit("Invoke main(catch_removed_and_path_clear=True) after live confirmation")
