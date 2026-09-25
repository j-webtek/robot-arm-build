"""One unchanged-r77 startup to enable post-fault read-only pose acquisition."""
import argparse
import json
from pathlib import Path
import sys
import time

from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_installation_evidence import review_pair_installation
from rocell.application.hold_transport_snapshot import HoldHTTPReader, STATUS
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


FAULT="wizard-20260924T231012845117Z-4906f73579e64de797ecbd3ad2ac9f29"
STATUS_EXPORT="wizard-20260924T232506596686Z-78cd7bcbfd4c4ca6b645d0ef79917ebc"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--startup-export",required=True)
    parser.add_argument("--authorized-startup",action="store_true",required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    exports=root/"runs/wizard-exports"
    installation=review_pair_installation(root,revision=77)
    binding=review_recovery_startup(root,args.startup_export,revision=77)
    boot=binding["expected_boot"]
    fault,_=_read(exports,FAULT,"attachment-air-typing-final-fault.json")
    state,_=_read(exports,STATUS_EXPORT,"attachment-r77-postfault-status.json")
    if (fault["boot"]!=boot or fault["completed_legs"]!=3 or fault["leg"]!=4
            or fault["retry_allowed"] is not False or state["boot"]!=boot
            or state["raw_status"]!="SOURCE_POSE_REJECTED|4"
            or state["request_method"]!="GET" or state["movement_command_sent"] is not False):
        raise ValueError("Pinned r77 postfault evidence differs")
    claim=exports/f"r77-pose-restart-{boot}.json"
    if claim.exists():raise ValueError("Startup already attempted for this boot")
    current=json.loads(HoldHTTPReader(binding["address"])(STATUS,maximum_bytes=512,
                                                              timeout_seconds=3))
    if current.get("instance_id")!=boot or current.get("storage_fault") is not False:
        raise ValueError("Live boot differs; no restart")

    pinned=root/".firmware-tools/esptool-api-4.6"
    sys.path.insert(0,str(pinned))
    import esptool
    import serial
    from esptool.reset import HardReset
    from serial.tools.list_ports import comports
    if esptool.__version__!="4.6" or not Path(esptool.__file__).resolve().is_relative_to(pinned.resolve()):
        raise ValueError("Unexpected reset implementation")
    matches=[port for port in comports() if port.device=="COM7" and port.vid==0x10c4
             and port.pid==0xea60 and port.serial_number=="52E4E1E8337FEF119E92181CEDD322A4"]
    if len(matches)!=1:raise ValueError("Expected USB adapter not identified")
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    report=dict(schema="rocell.r77_pose_restart.v1",previous_boot=boot,
                installation=installation,fault_export=FAULT,status_export=STATUS_EXPORT,
                status="PREPARED",flash_written=False,settings_written=False,
                servo_command_sent=False,retry_allowed=False)
    def save():
        saved=exporter.export({"mode":"r77-postfault-pose-startup"},[],attachments={
            "r77-pose-restart.json":canonical(report)})
        if not verify_export(Path(saved["path"]))["valid"]:
            raise ValueError("Restart export verification failed")
        return saved
    intent=save()
    publish_reservation_bytes(exports,claim.name,canonical(dict(previous_boot=boot,
        intent_export=Path(intent["path"]).name,authorized=True,retry_allowed=False)),
        maximum_bytes=2048)
    port=serial.Serial(port=None,baudrate=115200,timeout=2,write_timeout=2)
    port.dtr=False;port.rts=False;port.port="COM7"
    report["status"]="RESET_UNCERTAIN"
    try:
        port.open()
        HardReset(port)()
        report["status"]="ONE_RESET_SENT_STARTUP_NOT_YET_VERIFIED"
    finally:
        try:port.close()
        finally:saved=save()
    time.sleep(18)
    print(json.dumps(dict(export_path=saved["path"],status=report["status"],previous_boot=boot)))


if __name__=="__main__":main()
