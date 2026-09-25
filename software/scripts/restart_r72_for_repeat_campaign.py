"""One reviewed startup of installed r72 after the completed first twelve-leg wrist campaign.

This performs no flash, filesystem, settings, torque, or servo command. The
startup is one-use for the exact previously observed boot and is retained before
the USB reset is sent.
"""
import argparse
import json
from pathlib import Path
import sys
import time

from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_installation_evidence import review_pair_installation
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export',required=True)
    parser.add_argument('--authorized-startup',action='store_true',required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    installation=review_pair_installation(root,revision=72)
    binding=review_recovery_startup(root,args.startup_export,revision=72)
    boot=binding['expected_boot'];exports=root/'runs/wizard-exports'
    claim=exports/f'r72-heldout-restart-{boot}.json'
    if claim.exists():raise ValueError('r72 startup already attempted for this boot')

    from rocell.application.hold_transport_snapshot import HoldHTTPReader, STATUS
    from rocell.application.product_ghost_export_review import _read
    summary,_=_read(exports,'wizard-20260924T184928945241Z-a5a64a08eb254bd0bb0a2b7110fdc2da','attachment-r72-campaign-summary.json')
    if boot!=summary['boot'] or summary['verified_legs']!=12:
        raise ValueError('Expected completed first r72 campaign differs')
    current=json.loads(HoldHTTPReader(binding['address'])(STATUS,maximum_bytes=512,timeout_seconds=3))
    if current.get('instance_id')!=boot or current.get('storage_fault') is not False:
        raise ValueError('Live boot differs; no reset')

    sys.path.insert(0,str(root/'.firmware-tools/esptool-api-4.6'))
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
    report=dict(schema='rocell.r72_heldout_restart.v1',status='PREPARED',
        previous_boot=boot,installation=installation,flash_written=False,
        settings_written=False,servo_command_sent=False,retry_allowed=False)
    def save():
        saved=exporter.export({'mode':'r72-heldout-startup'},[],attachments={
            'r72-heldout-restart.json':canonical(report)})
        if not verify_export(Path(saved['path']))['valid']:raise ValueError('Export verification failed')
        return saved
    intent=save()
    publish_reservation_bytes(exports,claim.name,canonical(dict(previous_boot=boot,
        intent_export=Path(intent['path']).name,authorized=True,retry_allowed=False)),maximum_bytes=2048)
    port=serial.Serial(port=None,baudrate=115200,timeout=2,write_timeout=2)
    port.dtr=False;port.rts=False;port.port='COM7';report['status']='RESET_UNCERTAIN'
    try:
        port.open();HardReset(port)();report['status']='ONE_RESET_SENT_STARTUP_NOT_YET_VERIFIED'
    finally:
        try:port.close()
        finally:saved=save()
    time.sleep(18)
    print(json.dumps(dict(export_path=saved['path'],status=report['status'],previous_boot=boot)))


if __name__=='__main__':main()
