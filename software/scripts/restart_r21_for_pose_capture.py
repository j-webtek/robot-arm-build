"""One approved startup from the stopped r21 trial, without servo/settings writes.

This does not recover, reconcile goals or admit movement. Opening/resetting the
controller may have physical effects; explicit startup approval is required.
"""
import argparse
import json
from pathlib import Path
import sys
import time

from rocell.application.first_motion_contract import canonical
from rocell.application.observed_pose_installation import review_observed_startup
from rocell.application.hold_transport_snapshot import HoldHTTPReader, STATUS
from rocell.application.held_pair_transport import STATUS as PAIR_STATUS
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.servo_start_authorization import _hex
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def validate_stopped(hold, pair, boot):
    """Status evidence is not a joint measurement or proof of physical stability."""
    _hex(boot, 16)
    for value, expected in (
        (hold, dict(schema='rocell.hold_transport.v1', instance_id=boot,
                    state='FAULT', reason='HOLD_HANDED_OFF', records=0, storage_fault=False)),
        (pair, dict(schema='rocell.held_pair_transport.v1', boot_id=boot,
                    state='STOPPED', reason='LEG_NOT_ARRIVED', records=23, storage_fault=False))):
        if type(value) is not dict or any(canonical(value.get(k)) != canonical(v) for k,v in expected.items()):
            raise ValueError('Expected stopped r21 trial no longer matches; no reset')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('startup-export','stage-export','installation-export'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--authorized-startup',action='store_true',required=True)
    args=parser.parse_args(); root=Path(__file__).resolve().parents[1]
    binding=review_observed_startup(root,startup_export=args.startup_export,
        stage_export=args.stage_export,installation_export=args.installation_export)
    boot=binding['expected_boot']; exports=root/'runs/wizard-exports'
    name='r21-pose-restart-'+boot+'.json'
    if (exports/name).exists():raise ValueError('Startup allowance consumed; no retry')
    import serial
    from serial.tools.list_ports import comports
    ports=[p for p in comports() if p.device=='COM7' and p.vid==0x10c4 and p.pid==0xea60
           and p.serial_number=='52E4E1E8337FEF119E92181CEDD322A4']
    if len(ports)!=1:raise ValueError('Expected USB adapter not identified')
    pinned=root/'.firmware-tools/esptool-api-4.6';sys.path.insert(0,str(pinned))
    import esptool
    from esptool.reset import HardReset
    if esptool.__version__!='4.6' or not Path(esptool.__file__).resolve().is_relative_to(pinned.resolve()):
        raise ValueError('Unexpected reset implementation')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    reader=HoldHTTPReader(binding['address'])
    observations=[]
    for _ in range(2):
        hold=decode_diagnostic_json(reader._get(STATUS,maximum_bytes=512,timeout_seconds=3),maximum=512)
        pair=decode_diagnostic_json(reader._get(PAIR_STATUS,maximum_bytes=1024,timeout_seconds=3),maximum=1024)
        validate_stopped(hold,pair,boot);observations.append(dict(hold=hold,pair=pair))
    if observations[0]!=observations[1]:raise ValueError('Controller status changed; no reset')
    report=dict(schema='rocell.r21_pose_restart.v1',previous_boot=boot,
        status='PREPARED',observations=observations,retry_allowed=False,
        servo_command_sent=False,settings_written=False,flash_written=False)
    def save():
        result=exporter.export({'mode':'r21-pose-startup'},[],
            attachments={'r21-pose-restart.json':canonical(report)})
        if not verify_export(Path(result['path']))['valid']:raise ValueError('Export verification failed')
        return result
    prepared=save()
    publish_reservation_bytes(exports,name,canonical(dict(previous_boot=boot,
        intent_export=Path(prepared['path']).name,authorized=True,retry_allowed=False)),maximum_bytes=2048)
    port=serial.Serial(port=None,baudrate=115200,timeout=2,write_timeout=2)
    port.dtr=False;port.rts=False;port.port='COM7'
    report['status']='RESET_UNCERTAIN'
    try:
        port.open();HardReset(port)()
        report['status']='ONE_RESET_SENT_STARTUP_NOT_YET_VERIFIED'
    finally:
        try:port.close()
        finally:saved=save()
    time.sleep(18)  # Reviewed boot has a bounded 15-second Wi-Fi connection window.
    print(json.dumps(dict(export_path=saved['path'],status=report['status'],previous_boot=boot)))


if __name__=='__main__':main()
