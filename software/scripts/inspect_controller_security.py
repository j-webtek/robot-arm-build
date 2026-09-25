"""Authorized compatibility inspection: named read-only ESP32 security getters."""
import json
from pathlib import Path
import sys


def inspect_security(esp):
    mac = ':'.join(f'{value:02x}' for value in esp.read_mac())
    if mac != 'fc:e8:c0:f8:d5:38':
        raise ValueError('Unexpected controller identity')
    # Getter failures propagate; unreadable never becomes "disabled".
    return {
        'schema': 'rocell.controller_security_review.v1',
        'controller_mac': mac,
        'chip_revision': esp.get_chip_revision(),
        'secure_boot_enabled': bool(esp.get_secure_boot_enabled()),
        'flash_encryption_enabled': bool(esp.get_flash_encryption_enabled()),
        'encrypted_download_disabled': bool(esp.get_encrypted_download_disabled()),
        'efuses_written': False,
        'key_material_read': False,
    }


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / '.firmware-tools/esptool-api-4.6'))
    import esptool
    import serial
    if esptool.__version__ != '4.6':
        raise ValueError('Unexpected esptool version')
    port = serial.Serial(port=None, baudrate=115200, timeout=3, write_timeout=10)
    port.dtr = False
    port.rts = False
    port.port = 'COM7'
    try:
        port.open()
        esp = esptool.ESP32ROM(port, baud=115200)
        esp.connect('default_reset', attempts=2)
        report = inspect_security(esp)
        destination = root / 'private-backups/controller-20260918-session1/security-review.json'
        with destination.open('x', encoding='utf-8') as output:
            json.dump(report, output, indent=2)
        print(json.dumps(report), flush=True)
    finally:
        # No deliberate application restart; driver close behavior remains external.
        port.close()


if __name__ == '__main__':
    main()
