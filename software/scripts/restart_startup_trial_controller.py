"""One explicitly approved USB-only restart; no bootloader, flash or servo command."""
import argparse
import json
from pathlib import Path
import sys
import time

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.servo_diagnostic_http import DiagnosticHTTPReader
from rocell.application.servo_transport_export import capture_transport_export
from rocell.application.servo_start_authorization import _hex


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--authorized-supported-usb-only', action='store_true')
    mode.add_argument('--authorized-r33-startup', action='store_true')
    mode.add_argument('--authorized-r34-startup', action='store_true')
    mode.add_argument('--authorized-r48-startup', action='store_true')
    mode.add_argument('--authorized-r49-startup', action='store_true')
    mode.add_argument('--authorized-r50-startup', action='store_true')
    mode.add_argument('--authorized-r51-startup', action='store_true')
    mode.add_argument('--authorized-r52-startup', action='store_true')
    mode.add_argument('--authorized-r53-startup', action='store_true')
    mode.add_argument('--authorized-r54-startup', action='store_true')
    mode.add_argument('--authorized-r55-startup', action='store_true')
    mode.add_argument('--authorized-r56-startup', action='store_true')
    mode.add_argument('--authorized-r57-startup', action='store_true')
    mode.add_argument('--authorized-r58-startup', action='store_true')
    mode.add_argument('--authorized-r60-startup', action='store_true')
    mode.add_argument('--authorized-r61-startup', action='store_true')
    parser.add_argument('--startup-export')
    parser.add_argument('--previous-boot', required=True)
    args = parser.parse_args()
    _hex(args.previous_boot, 16)
    root = Path(__file__).resolve().parents[1]
    exports = (root / 'runs/wizard-exports').resolve()
    revision = (61 if args.authorized_r61_startup else 60 if args.authorized_r60_startup else 58 if args.authorized_r58_startup else 57 if args.authorized_r57_startup else 56 if args.authorized_r56_startup else 55 if args.authorized_r55_startup else 54 if args.authorized_r54_startup else 53 if args.authorized_r53_startup else 52 if args.authorized_r52_startup else 51 if args.authorized_r51_startup else 50 if args.authorized_r50_startup else 49 if args.authorized_r49_startup else 48 if args.authorized_r48_startup else 34 if args.authorized_r34_startup
                else 33 if args.authorized_r33_startup else None)
    if revision is not None:
        from rocell.application.supported_recovery_installation import review_recovery_startup
        if not args.startup_export:raise ValueError('Startup binding required')
        binding=review_recovery_startup(root,args.startup_export,revision=revision)
        if binding['expected_boot']!=args.previous_boot:raise ValueError('Boot mismatch')
    def capture():
        if revision is None:
            return capture_transport_export(exports, DiagnosticHTTPReader('192.168.0.225'), startup=True)
        # r33 uses hold-transport status, not the earlier startup-trial schema.
        from rocell.application.hold_transport_snapshot import HoldHTTPReader, STATUS
        from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
        raw=HoldHTTPReader(binding['address'])._get(STATUS,maximum_bytes=512,timeout_seconds=3)
        status=json.loads(raw)
        if status.get('schema')!='rocell.hold_transport.v1':raise ValueError('Unexpected r33 status schema')
        exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
        saved=exporter.export({'mode':f'r{revision}-restart-observation'},[],attachments={'status.json':raw})
        if not verify_export(Path(saved['path']))['valid']:raise ValueError('Status export failed')
        return dict(summary=dict(status=status),export_path=saved['path'])
    before = capture()
    status = before['summary'].get('status')
    if not isinstance(status, dict) or status['instance_id'] != args.previous_boot:
        raise ValueError('Previous boot identity not confirmed; no reset')
    pinned = root / '.firmware-tools/esptool-api-4.6'
    sys.path.insert(0, str(pinned))
    import serial
    from serial.tools.list_ports import comports
    ports = [p for p in comports() if p.device == 'COM7' and p.vid == 0x10c4 and
             p.pid == 0xea60 and p.serial_number == '52E4E1E8337FEF119E92181CEDD322A4']
    if len(ports) != 1: raise ValueError('Expected USB adapter not identified')
    import esptool
    from esptool.reset import HardReset
    if esptool.__version__ != '4.6' or not Path(esptool.__file__).resolve().is_relative_to(
            pinned.resolve()):
        raise ValueError('Unexpected reset implementation')
    publish_reservation_bytes(exports, 'usb-restart-' + args.previous_boot + '.json',
        canonical(dict(previous_boot=args.previous_boot, authorized=True, retry_allowed=False,
                       servo_command_sent=False)), maximum_bytes=2048)
    port = serial.Serial(port=None, baudrate=115200, timeout=2, write_timeout=2)
    port.dtr = False
    port.rts = False
    port.port = 'COM7'
    try:
        port.open()
        HardReset(port)()
    finally:
        port.close()
    time.sleep(5)
    after = capture()
    current = after['summary'].get('status')
    if (not isinstance(current, dict) or current['instance_id'] == args.previous_boot or
            current['state'] != 'IDLE' or current['reason'] != 'NOT_CONFIGURED' or current['records'] != 0):
        raise ValueError('New idle boot unverified; do not retry reset')
    print(json.dumps(dict(status='NEW_IDLE_BOOT_VERIFIED', before_export=before['export_path'],
        after_export=after['export_path'], boot_id=current['instance_id'], motion_sent=False)))


if __name__ == '__main__': main()
