"""One-use r89→r90 app-only install and one startup; no motion/provisioning.

Preflight is local and read-only. Authorized mode checks exact USB, MAC,
predecessor app and protected flash, then writes one app image. No retry.
"""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

if __package__:
    from .deploy_reviewed_diagnostic_app import longer_reset_rom
    from .deploy_reviewed_hover_r89 import MAC, PORT, USB_SERIAL
    from .preflight_r90_pose_hover_install import preflight
else:
    from deploy_reviewed_diagnostic_app import longer_reset_rom
    from deploy_reviewed_hover_r89 import MAC, PORT, USB_SERIAL
    from preflight_r90_pose_hover_install import preflight
from rocell.providers.windows.diagnostic_image_store import load_image


R90_SHA = "f3d5705b16eedfd49b11fec668da1709eee71d50345ceb07eadf26f0384fe129"
R89_SHA = "89c0d91334ab4362d392a3e3e66433c216d7e1740842dbba1b87881b722236b0"


def prepare(root: Path) -> dict:
    root = Path(root).resolve()
    report = preflight(root)
    image_path = (root / ".firmware-tools/build-configured-diagnostic-candidate-r90--default-4mb-no-psram"
                  / "RoArm-M3_example.ino.bin")
    prior_path = (root / ".firmware-tools/build-configured-diagnostic-candidate-r89--default-4mb-no-psram"
                  / "RoArm-M3_example.ino.bin")
    image, prior = image_path.read_bytes(), prior_path.read_bytes()
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    if (report["status"] != "LOCAL_PREFLIGHT_VERIFIED"
            or sha(image) != R90_SHA or sha(prior) != R89_SHA
            or report["app_sha256"] != R90_SHA or report["app_bytes"] != len(image)
            or report["predecessor_app_sha256"] != R89_SHA
            or report["app_offset"] != 0x10000
            or report["app_slot_bytes"] != 0x140000):
        raise ValueError("Pinned r90 installation inputs differ")
    private = root / "private-backups/controller-20260918-session1"
    backup = (private / "flash-pair-a.bin").read_bytes()
    filesystem = load_image(private / "observed-pose-plus10-candidate.dpapi")
    return dict(image=image, image_path=image_path, prior=prior,
                partition_md5=hashlib.md5(backup[0x8000:0x8c00]).hexdigest(),
                filesystem_md5=hashlib.md5(filesystem).hexdigest(),
                release_sha256=report["release_sha256"],
                journal=private / "app-r90-deployment-events.jsonl")


def install(root: Path, prepared: dict) -> None:
    from serial.tools.list_ports import comports
    matches = [item for item in comports() if item.device == PORT and
               item.vid == 0x10c4 and item.pid == 0xea60 and
               item.serial_number == USB_SERIAL]
    if len(matches) != 1:
        raise ValueError("Expected controller USB adapter not identified")
    pinned = root / ".firmware-tools/esptool-api-4.6"
    sys.path.insert(0, str(pinned))
    import esptool
    from esptool import cmds, loader
    import serial
    if (esptool.__version__ != "4.6" or
            not Path(esptool.__file__).resolve().is_relative_to(pinned.resolve())):
        raise ValueError("Unexpected esptool implementation")
    loader.WRITE_BLOCK_ATTEMPTS = 1
    image = prepared["image"]
    with prepared["journal"].open("x", encoding="utf-8") as journal:
        def event(stage: str, **fields) -> None:
            row = dict(stage=stage, **fields)
            journal.write(json.dumps(row) + "\n")
            journal.flush()
            os.fsync(journal.fileno())
            print(json.dumps(row), flush=True)

        event("RESERVED", app_sha256=R90_SHA, offset=0x10000,
              bytes=len(image), release_sha256=prepared["release_sha256"])
        port = serial.Serial(port=None, baudrate=115200, timeout=3, write_timeout=10)
        port.dtr = False
        port.rts = False
        port.port = PORT
        try:
            port.open()
            esp = longer_reset_rom(esptool, port)
            esp.connect("default_reset", attempts=1)
            mac = ":".join(f"{value:02x}" for value in esp.read_mac())
            if (mac != MAC or esp.secure_download_mode or esp.stub_is_disabled or
                    esp.get_secure_boot_enabled() or esp.get_flash_encryption_enabled()):
                raise ValueError("Controller identity/security state differs")
            stub = esp.run_stub()
            if stub.flash_id() != 0x164020:
                raise ValueError("Unexpected flash identity")
            if (stub.flash_md5sum(0x10000, len(prepared["prior"])) !=
                    hashlib.md5(prepared["prior"]).hexdigest() or
                    stub.flash_md5sum(0x8000, 3072) != prepared["partition_md5"] or
                    stub.flash_md5sum(0x290000, 0x160000) != prepared["filesystem_md5"]):
                raise ValueError("Installed predecessor or protected region differs")
            protected = [(0, 0x10000), (0x150000, 0x2b0000)]
            before = [stub.flash_md5sum(start, size) for start, size in protected]
            event("IDENTITY_AND_PREWRITE_VERIFIED", mac=mac)
            stream = io.BytesIO(image)
            stream.name = str(prepared["image_path"])
            args = SimpleNamespace(addr_filename=[(0x10000, stream)],
                compress=True, no_compress=False, no_stub=False, force=False,
                encrypt=False, encrypt_files=None, erase_all=False, verify=False,
                ignore_flash_encryption_efuse_setting=False,
                flash_size="keep", flash_mode="keep", flash_freq="keep")
            event("WRITE_ATTEMPT_STARTED")
            cmds.write_flash(stub, args)
            readback = stub.read_flash(0x10000, len(image))
            if readback != image or hashlib.sha256(readback).hexdigest() != R90_SHA:
                raise ValueError("Application readback mismatch")
            after = [stub.flash_md5sum(start, size) for start, size in protected]
            if before != after:
                raise ValueError("Protected region changed")
            event("FLASH_VERIFIED", app_sha256=R90_SHA,
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--install-app-only-and-startup", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    prepared = prepare(root)
    if args.preflight_only:
        print(json.dumps(dict(status="R90_INSTALL_PREFLIGHT_VERIFIED",
                              app_sha256=R90_SHA, predecessor_sha256=R89_SHA,
                              release_sha256=prepared["release_sha256"],
                              hardware_access=False, firmware_uploaded=False)))
        return
    install(root, prepared)


if __name__ == "__main__":
    main()
