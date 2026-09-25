"""One-attempt, app-slot-only r92 -> r93 gripper loader install."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

from rocell.providers.windows.diagnostic_image_store import load_image

if __package__:
    from .deploy_reviewed_diagnostic_app import longer_reset_rom
    from .deploy_reviewed_hover_r89 import MAC, PORT, USB_SERIAL
    from .review_r93_gripper_candidate import review, APP_SHA, R92_SHA
else:
    from deploy_reviewed_diagnostic_app import longer_reset_rom
    from deploy_reviewed_hover_r89 import MAC, PORT, USB_SERIAL
    from review_r93_gripper_candidate import review, APP_SHA, R92_SHA

BACKUP_SHA = "d9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9"
FILESYSTEM_SHA = "45320bab56ec1d8e889078a50e2aa0ef79d4d65c59e5dcb89c7a7880f08e7267"


def prepare(root: Path) -> dict:
    root = Path(root).resolve()
    review(root)
    tools = root / ".firmware-tools"
    path = (tools / "build-configured-diagnostic-candidate-r93--default-4mb-no-psram"
            / "RoArm-M3_example.ino.bin")
    prior_path = (tools / "build-configured-diagnostic-candidate-r92--default-4mb-no-psram"
                  / "RoArm-M3_example.ino.bin")
    image, prior = path.read_bytes(), prior_path.read_bytes()
    sha = lambda data: hashlib.sha256(data).hexdigest()
    if sha(image) != APP_SHA or sha(prior) != R92_SHA or not 0 < len(image) <= 0x140000:
        raise ValueError("Pinned app images or slot bounds differ")
    private = root / "private-backups/controller-20260918-session1"
    rows = [json.loads(line) for line in
            (private / "app-r92-deployment-events.jsonl").read_text().splitlines()]
    if ([row.get("stage") for row in rows] != [
            "RESERVED", "IDENTITY_AND_PREWRITE_VERIFIED", "WRITE_ATTEMPT_STARTED",
            "FLASH_VERIFIED", "ONE_STARTUP_ATTEMPT", "STARTUP_RESET_SENT"] or
            rows[0].get("app_sha256") != R92_SHA or
            rows[1].get("mac") != MAC or
            rows[3].get("app_sha256") != R92_SHA or
            rows[3].get("protected_regions_unchanged") is not True):
        raise ValueError("Installed r92 journal differs")
    backup = (private / "flash-pair-a.bin").read_bytes()
    filesystem = load_image(private / "observed-pose-plus10-candidate.dpapi")
    if (len(backup) != 0x400000 or sha(backup) != BACKUP_SHA or
            len(filesystem) != 0x160000 or sha(filesystem) != FILESYSTEM_SHA):
        raise ValueError("Protected original backup differs")
    journal = private / "app-r93-deployment-events.jsonl"
    if journal.exists():
        raise ValueError("r93 install already attempted; no retry")
    return dict(image=image, path=path, prior=prior,
                partition_md5=hashlib.md5(backup[0x8000:0x8c00]).hexdigest(),
                filesystem_md5=hashlib.md5(filesystem).hexdigest(), journal=journal)


def install(root: Path, prepared: dict, *, supported_for_reset: bool) -> None:
    if supported_for_reset is not True:
        raise ValueError("Physical catch and cleared drop path required")
    root = Path(root).resolve()
    if prepared != prepare(root):
        raise ValueError("Pinned inputs changed")
    pinned = root / ".firmware-tools/esptool-api-4.6"
    sys.path.insert(0, str(pinned))
    import serial
    from serial.tools.list_ports import comports
    import esptool
    from esptool import cmds, loader
    if (serial.__version__ != "3.5" or esptool.__version__ != "4.6" or
            not Path(serial.__file__).resolve().is_relative_to(pinned.resolve()) or
            not Path(esptool.__file__).resolve().is_relative_to(pinned.resolve())):
        raise ValueError("Unpinned installer runtime")
    matches = [item for item in comports() if item.device == PORT and
               item.vid == 0x10c4 and item.pid == 0xea60 and
               item.serial_number == USB_SERIAL]
    if len(matches) != 1:
        raise ValueError("Expected controller USB adapter absent")
    loader.WRITE_BLOCK_ATTEMPTS = 1
    with prepared["journal"].open("x", encoding="utf-8") as journal:
        def event(stage, **fields):
            row = dict(stage=stage, **fields)
            journal.write(json.dumps(row) + "\n")
            journal.flush(); os.fsync(journal.fileno())
            print(json.dumps(row), flush=True)

        event("RESERVED", app_sha256=APP_SHA, offset=0x10000,
              bytes=len(prepared["image"]))
        port = serial.Serial(port=None, baudrate=115200, timeout=3,
                             write_timeout=10)
        port.dtr = False; port.rts = False; port.port = PORT
        try:
            port.open()
            esp = longer_reset_rom(esptool, port)
            esp.connect("default_reset", attempts=1)
            mac = ":".join(f"{value:02x}" for value in esp.read_mac())
            if (mac != MAC or esp.secure_download_mode or esp.stub_is_disabled or
                    esp.get_secure_boot_enabled() or
                    esp.get_flash_encryption_enabled()):
                raise ValueError("Controller identity/security differs")
            stub = esp.run_stub()
            if stub.flash_id() != 0x164020:
                raise ValueError("Flash identity differs")
            if (stub.flash_md5sum(0x10000, len(prepared["prior"])) !=
                    hashlib.md5(prepared["prior"]).hexdigest() or
                    stub.flash_md5sum(0x8000, 3072) != prepared["partition_md5"] or
                    stub.flash_md5sum(0x290000, 0x160000) != prepared["filesystem_md5"]):
                raise ValueError("Predecessor/protected region differs")
            protected = [(0, 0x10000), (0x150000, 0x2b0000)]
            before = [stub.flash_md5sum(start, size) for start, size in protected]
            event("IDENTITY_AND_PREWRITE_VERIFIED", mac=mac)
            stream = io.BytesIO(prepared["image"])
            stream.name = str(prepared["path"])
            args = SimpleNamespace(addr_filename=[(0x10000, stream)],
                compress=True, no_compress=False, no_stub=False, force=False,
                encrypt=False, encrypt_files=None, erase_all=False, verify=False,
                ignore_flash_encryption_efuse_setting=False,
                flash_size="keep", flash_mode="keep", flash_freq="keep")
            event("WRITE_ATTEMPT_STARTED")
            cmds.write_flash(stub, args)
            readback = stub.read_flash(0x10000, len(prepared["image"]))
            if readback != prepared["image"] or hashlib.sha256(readback).hexdigest() != APP_SHA:
                raise ValueError("App readback mismatch")
            if before != [stub.flash_md5sum(start, size) for start, size in protected]:
                raise ValueError("Protected region changed")
            event("FLASH_VERIFIED", app_sha256=APP_SHA,
                  protected_regions_unchanged=True)
            event("ONE_STARTUP_ATTEMPT")
            stub.hard_reset()
            event("STARTUP_RESET_SENT", application_health_verified=False)
        except BaseException as error:
            event("STOPPED", error_type=type(error).__name__,
                  error=str(error), retry=False)
            raise
        finally:
            port.close()
