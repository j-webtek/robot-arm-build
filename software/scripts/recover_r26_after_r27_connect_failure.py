"""One recovery startup after the exact prewrite r27 connection failure.

Never flashes, reconnects the ROM loader, issues servo commands or retries.
Refuse unless the failed deployment journal proves no write stage was entered.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_installation_evidence import review_pair_installation
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def validate_failure(rows):
    expected=dict(stage='RESERVED',app_sha256='c46e1ab78cb6b38c1244f1da8dd8b459340704b65af093c3b1875ed3d6158bba',
                  offset=65536,bytes=1145280)
    if (len(rows)!=2 or rows[0]!=expected or rows[1].get('stage')!='STOPPED'
            or rows[1].get('error_type')!='FatalError' or rows[1].get('retry') is not False
            or not rows[1].get('error','').startswith('Failed to connect to ESP32: Download mode successfully detected, but getting no sync reply:')):
        raise ValueError('Not the exact prewrite-only failure; no reset')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorized-recovery-startup',action='store_true',required=True)
    parser.parse_args()
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    journal=root/'private-backups/controller-20260918-session1/app-r27-deployment-events.jsonl'
    raw=journal.read_bytes();validate_failure([json.loads(line) for line in raw.splitlines()])
    installation=review_pair_installation(root,revision=26)
    claim='r27-prewrite-recovery-startup.json'
    if (exports/claim).exists():raise ValueError('Recovery startup already attempted')
    import serial
    from serial.tools.list_ports import comports
    matches=[p for p in comports() if p.device=='COM7' and p.vid==0x10c4 and p.pid==0xea60
             and p.serial_number=='52E4E1E8337FEF119E92181CEDD322A4']
    if len(matches)!=1:raise ValueError('Expected USB adapter not identified')
    pinned=root/'.firmware-tools/esptool-api-4.6';sys.path.insert(0,str(pinned))
    import esptool
    from esptool.reset import HardReset
    if esptool.__version__!='4.6' or not Path(esptool.__file__).resolve().is_relative_to(pinned.resolve()):
        raise ValueError('Unexpected reset implementation')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    report=dict(schema='rocell.r27_prewrite_recovery_startup.v1',status='PREPARED',
        installation=installation,failed_journal_sha256=hashlib.sha256(raw).hexdigest(),
        servo_command_sent=False,flash_written=False,settings_written=False,retry_allowed=False)
    def save():
        result=exporter.export({'mode':'r27-prewrite-recovery-startup'},[],
            attachments={'recovery-startup.json':canonical(report)})
        if not verify_export(Path(result['path']))['valid']:raise ValueError('Export failed')
        return result
    intent=save()
    publish_reservation_bytes(exports,claim,canonical(dict(intent_export=Path(intent['path']).name,
        authorized=True,retry_allowed=False)),maximum_bytes=2048)
    port=serial.Serial(port=None,baudrate=115200,timeout=2,write_timeout=2)
    port.dtr=False;port.rts=False;port.port='COM7'
    report['status']='RESET_UNCERTAIN'
    try:
        port.open();HardReset(port)()
        report['status']='ONE_RESET_SENT_STARTUP_NOT_YET_VERIFIED'
    finally:
        try:port.close()
        finally:result=save()
    time.sleep(18)
    print(canonical(dict(export_path=result['path'],status=report['status'])).decode())


if __name__=='__main__':main()
