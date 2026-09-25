"""Run exactly one attended r94 non-contact B-key leg over local USB.

Each invocation consumes one durable leg marker. Never retries, returns or
automatically advances to the next leg.
"""
import hashlib
import http.client
import json
from pathlib import Path
import re
import sys

from rocell.application.first_motion_contract import canonical
from rocell.application.ghost_typing_resume_preview import (
    SOURCE_GOALS, SOURCE_POSITIONS, TARGETS, review_source,
)
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

if __package__:
    from .deploy_reviewed_hover_r89 import PORT, USB_SERIAL
    from .deploy_r94_ghost_b import APP_SHA
    from .run_r93_gripper_open import receive, snapshot
else:
    from deploy_reviewed_hover_r89 import PORT, USB_SERIAL
    from deploy_r94_ghost_b import APP_SHA
    from run_r93_gripper_open import receive, snapshot


def capabilities() -> dict:
    connection = http.client.HTTPConnection("192.168.0.225", 80, timeout=3)
    try:
        connection.request("GET", "/rocell/ghost-b/capabilities")
        response = connection.getresponse()
        raw = response.read(513)
        if response.status != 200 or len(raw) > 512:
            raise ValueError("Ghost-B identity unavailable")
        data = json.loads(raw)
    finally:
        connection.close()
    boot = data.get("boot_id") if type(data) is dict else None
    if (type(data) is not dict or set(data) != {
            "schema", "boot_id", "maximum_legs", "automatic_progression",
            "gripper_writes", "motion_authorized"} or
            data["schema"] != "rocell.ghost_b.v1" or
            data["maximum_legs"] != 5 or
            data["automatic_progression"] is not False or
            data["gripper_writes"] is not False or
            data["motion_authorized"] is not False or
            type(boot) is not str or not re.fullmatch(r"[0-9a-f]{32}", boot)):
        raise ValueError("Unexpected Ghost-B identity")
    return data


def _source(exports: Path, leg: int, boot: str) -> tuple[list[int], list[int]]:
    if leg == 1:
        return list(SOURCE_POSITIONS), list(SOURCE_GOALS)
    marker = exports / f"ghost-b-leg-{leg - 1}-{boot}.json"
    if not marker.exists():
        raise ValueError("Prior leg has no durable reservation")
    claim = json.loads(marker.read_text())
    if claim.get("boot_id") != boot or claim.get("leg") != leg - 1:
        raise ValueError("Prior leg reservation differs")
    completion = exports / f"ghost-b-leg-{leg - 1}-final-{boot}.json"
    if not completion.exists():
        raise ValueError("Prior leg has no verified completion pointer")
    pointer = json.loads(completion.read_text())
    previous = exports / pointer["final_export"] / "attachment-ghost-b-leg.json"
    if not verify_export(previous.parent)["valid"]:
        raise ValueError("Prior leg export invalid")
    row = json.loads(previous.read_text())
    if (row.get("category") != "LEG_VERIFIED" or
            row.get("boot_id") != boot or
            row.get("leg") != leg - 1 or
            row.get("app_sha256") != APP_SHA):
        raise ValueError("Prior leg evidence differs")
    after = row["after"]
    if after["goals"] != list(TARGETS[leg - 2]):
        raise ValueError("Prior leg target differs")
    return after["positions"], after["goals"]


def main(*, leg: int, catch_removed_and_path_clear: bool) -> dict:
    if type(leg) is not int or not 1 <= leg <= 5:
        raise ValueError("Expected one of the five reviewed B legs")
    if catch_removed_and_path_clear is not True:
        raise ValueError("Fresh catch-outside-path and clearance confirmation required")
    root = Path(__file__).resolve().parents[1]
    exports = root / "runs/wizard-exports"
    review_source(exports)
    app = (root / ".firmware-tools/build-configured-diagnostic-candidate-r94--default-4mb-no-psram"
           / "RoArm-M3_example.ino.bin").read_bytes()
    if hashlib.sha256(app).hexdigest() != APP_SHA:
        raise ValueError("Installed candidate image no longer pinned")
    journal = root / "private-backups/controller-20260918-session1/app-r94-deployment-events.jsonl"
    stages = [json.loads(line) for line in journal.read_text().splitlines()]
    if ([row.get("stage") for row in stages] != [
            "RESERVED", "IDENTITY_AND_PREWRITE_VERIFIED", "WRITE_ATTEMPT_STARTED",
            "FLASH_VERIFIED", "ONE_STARTUP_ATTEMPT", "STARTUP_RESET_SENT"] or
            stages[3].get("app_sha256") != APP_SHA or
            stages[3].get("protected_regions_unchanged") is not True):
        raise ValueError("r94 install not verified")
    caps = capabilities(); boot = caps["boot_id"]
    marker = exports / f"ghost-b-leg-{leg}-{boot}.json"
    if marker.exists():
        raise ValueError("This leg was already attempted on this boot")
    source_pos, source_goal = _source(exports, leg, boot)
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
    report = dict(schema="rocell.ghost_b_leg_attempt.v1", boot_id=boot,
                  app_sha256=APP_SHA, leg=leg, category="NOT_STARTED",
                  target_goals=list(TARGETS[leg - 1]), one_write_max=True,
                  retry_allowed=False, automatic_progression=False,
                  catch_removed_and_path_clear=True, physical_key_contact=False)
    def save():
        saved = exporter.export({"mode": "r94-ghost-b-leg"}, [],
            attachments={"ghost-b-leg.json": canonical(report)})
        if not verify_export(Path(saved["path"]))["valid"]:
            raise ValueError("Ghost-B export failed")
        return saved["path"]
    port = serial.Serial(port=None, baudrate=115200, timeout=0.25, write_timeout=2)
    port.dtr = False; port.rts = False; port.port = PORT
    try:
        port.open()
        if capabilities() != caps:
            raise ValueError("Controller restarted on serial open")
        port.write(b"STATUS\n"); port.flush()
        status = receive(port, "STATUS:", 3)
        if status != f"STATUS:{boot}:{leg - 1}:0:0":
            raise ValueError("Controller sequence status differs")
        before = snapshot(port, boot)
        report["before"] = before
        tolerance = 16 if leg == 1 else 12
        if (before["goals"] != source_goal or
                any(abs(a - b) > tolerance for a, b in
                    zip(before["positions"], source_pos))):
            raise ValueError("Fresh source differs from verified prior pose")
        selected = [i for i in range(7)
                    if TARGETS[leg - 1][i] != source_goal[i]]
        if (not selected or 6 in selected or
                max(abs(TARGETS[leg - 1][i] - source_goal[i])
                    for i in selected) > 60):
            raise ValueError("Unreviewed leg target")
        report.update(category="INTENT_EXPORTED",
                      selected_joints=selected, speed=20, acceleration=1)
        report["intent_export"] = save()
        publish_reservation_bytes(exports, marker.name,
            canonical(dict(boot_id=boot, leg=leg,
                           intent_export=Path(report["intent_export"]).name,
                           retry_allowed=False)), maximum_bytes=1024)
        port.write(f"LEG:{boot}:{leg}\n".encode("ascii")); port.flush()
        report["write_attempted"] = True
        sent = receive(port, "LEG_SENT:", 8)
        if sent != f"LEG_SENT:{boot}:{leg}:{len(selected)}":
            raise ValueError("Leg acknowledgement differs")
        report["sent"] = sent
        verified = receive(port, "LEG_VERIFIED:", 12)
        if verified != f"LEG_VERIFIED:{boot}:{leg}":
            raise ValueError("Controller leg verification differs")
        report["controller_verification"] = verified
        port.write(b"STATUS\n"); port.flush()
        status = receive(port, "STATUS:", 3)
        if status != f"STATUS:{boot}:{leg}:0:0":
            raise ValueError("Controller terminal status differs")
        after = snapshot(port, boot)
        report["after"] = after
        if (after["goals"] != list(TARGETS[leg - 1]) or
                any(abs(after["positions"][i] -
                        (TARGETS[leg - 1][i] if i in selected else before["positions"][i]))
                    > (12 if i in selected else 16) for i in range(7))):
            raise ValueError("Final all-joint readback differs")
        report["category"] = "LEG_VERIFIED"
    except BaseException as error:
        report.update(category="STOPPED_UNCERTAIN", error_type=type(error).__name__,
                      error=str(error))
    finally:
        if port.is_open:
            port.close()
    report["final_export"] = save()
    if report["category"] == "LEG_VERIFIED":
        # The reservation is immutable; a separate completion pointer allows
        # the next invocation to verify this leg without rewriting the claim.
        publish_reservation_bytes(exports, f"ghost-b-leg-{leg}-final-{boot}.json",
            canonical(dict(final_export=Path(report["final_export"]).name)),
            maximum_bytes=1024)
    return report


if __name__ == "__main__":
    raise SystemExit("Invoke main(leg=N, catch_removed_and_path_clear=True) only after live confirmation")
