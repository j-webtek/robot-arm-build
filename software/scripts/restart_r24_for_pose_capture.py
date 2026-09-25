"""One reviewed diagnostic startup for pose capture; no flash or servo writes."""
import argparse
import json
from pathlib import Path
import sys
import time
from rocell.application.first_motion_contract import canonical
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.shoulder_session_http import ShoulderSessionHTTP
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def validate_stopped(value, boot, revision=24):
    if revision not in (24,29):raise ValueError('Unreviewed restart revision')
    expected=dict(schema='rocell.shoulder_session_status.v1',boot_id=boot,
        command_id='r23-shoulder-hold',state='FAULT',reason='SHOULDERS_NOT_PASSIVE',
        sequence=0,preload_writes=0,enable_delivery='NOT_ATTEMPTED',
        record_available=False,whole_arm_ready=False,lift_authorized=False)
    if revision==29:
        expected.update(command_id='shoulder-stable-clearance24-v1',reason='RISE_STATE_CHANGED',
                        sequence=5,preload_writes=1,record_available=True)
    if canonical(value)!=canonical(expected):
        raise ValueError('Expected r24 fault no longer matches; no reset')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export',required=True)
    parser.add_argument('--revision',type=int,choices=(24,29),default=24)
    parser.add_argument('--authorized-startup',action='store_true',required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    binding=review_recovery_startup(root,args.startup_export,revision=args.revision)
    boot=binding['expected_boot'];exports=root/'runs/wizard-exports'
    name=f'r{args.revision}-pose-restart-'+boot+'.json'
    if (exports/name).exists():raise ValueError('Startup already attempted; no retry')
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
    transport=ShoulderSessionHTTP(binding['address'])
    observations=[]
    for _ in range(2):
        value=json.loads(transport('GET','/rocell/shoulder-session/status',b'',3))
        validate_stopped(value,boot,args.revision);observations.append(value)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    report=dict(schema=f'rocell.r{args.revision}_pose_restart.v1',previous_boot=boot,status='PREPARED',
        observations=observations,retry_allowed=False,servo_command_sent=False,
        settings_written=False,flash_written=False)
    def save():
        saved=exporter.export({'mode':f'r{args.revision}-pose-startup'},[],
            attachments={f'r{args.revision}-pose-restart.json':canonical(report)})
        if not verify_export(Path(saved['path']))['valid']:raise ValueError('Export verification failed')
        return saved
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
    time.sleep(18)  # Allow the existing firmware's bounded Wi-Fi startup window.
    print(json.dumps(dict(export_path=saved['path'],status=report['status'],previous_boot=boot)))


if __name__=='__main__':main()
