"""One approved powered/supported r16 startup after a verified recovery.

Retains the completed recovery before pulsing controller EN once. No flash,
filesystem or servo writes. Never retry an uncertain reset.
"""
import argparse
import json
from pathlib import Path
import sys
import time
from rocell.application.first_motion_contract import canonical
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.supported_recovery_review import replay_recovery
from rocell.application.hold_transport_export import capture_recovery_transport
from rocell.application.hold_transport_snapshot import RecoveryHTTPReader
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export', required=True)
    parser.add_argument('--recovery-export', required=True)
    parser.add_argument('--stage-export')
    parser.add_argument('--installation-export')
    parser.add_argument('--authorized-powered-supported-startup', action='store_true', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    exports = root / 'runs/wizard-exports'
    if bool(args.stage_export) != bool(args.installation_export):
        parser.error('Both observed-pose settings receipts are required')
    profile = 'supported'
    if args.stage_export:
        from rocell.application.observed_pose_installation import review_observed_startup
        binding = review_observed_startup(root, startup_export=args.startup_export,
            stage_export=args.stage_export, installation_export=args.installation_export)
        profile = 'six_count'
    else:
        binding = review_recovery_startup(root, args.startup_export)
    recovery_path = (exports / args.recovery_export).resolve()
    if recovery_path.parent != exports.resolve(): raise ValueError('Direct recovery export required')
    result = replay_recovery(recovery_path)
    records = json.loads((recovery_path/'attachment-recovery-records.json').read_bytes())
    boot = binding['expected_boot']
    if result['category'] != 'CONTROLLER_REPORTED_RECOVERY_VERIFIED' or any(r['boot_id'] != boot for r in records):
        raise ValueError('Verified same-boot recovery required')
    before = capture_recovery_transport(exports, RecoveryHTTPReader(binding['address']),
                                        expected_boot=boot, profile=profile)
    summary = before['summary']
    if summary['category'] != 'TRANSPORT_CAPTURED' or canonical(summary['records']) != canonical(records):
        raise ValueError('Current recovery evidence changed; no restart')
    import serial
    from serial.tools.list_ports import comports
    ports = [p for p in comports() if p.device=='COM7' and p.vid==0x10c4 and p.pid==0xea60
             and p.serial_number=='52E4E1E8337FEF119E92181CEDD322A4']
    if len(ports)!=1: raise ValueError('Expected USB adapter not identified')
    pinned = root / '.firmware-tools/esptool-api-4.6'
    sys.path.insert(0,str(pinned))
    import esptool
    from esptool.reset import HardReset
    if esptool.__version__!='4.6' or not Path(esptool.__file__).resolve().is_relative_to(pinned.resolve()):
        raise ValueError('Unexpected reset implementation')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    publish_reservation_bytes(exports,'r16-powered-restart-'+boot+'.json',canonical(dict(
        previous_boot=boot, before_export=Path(before['export_path']).name,
        authorized=True,retry_allowed=False,servo_command_sent=False)),maximum_bytes=2048)
    report=dict(previous_boot=boot,status='RESET_UNCERTAIN',retry_allowed=False,
                servo_command_sent=False,flash_written=False)
    port=serial.Serial(port=None,baudrate=115200,timeout=2,write_timeout=2)
    port.dtr=False;port.rts=False;port.port='COM7'
    try:
        port.open()
        HardReset(port)()
        report['status']='ONE_RESET_SENT_STARTUP_NOT_YET_VERIFIED'
    finally:
        port.close()
        saved=exporter.export({'mode':'r16-powered-startup'},[],
            attachments={'r16-restart.json':canonical(report)})
    # Allow the reviewed boot's bounded Wi-Fi connection window; no reset retry.
    time.sleep(18)
    print(json.dumps(dict(export_path=saved['path'],**report)))


if __name__=='__main__': main()
