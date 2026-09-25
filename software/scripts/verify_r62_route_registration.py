"""Read-only r62 route-presence check; sends no signed or servo request."""
import json
from pathlib import Path
import urllib.error
import urllib.request

from rocell.application.first_motion_contract import canonical
from rocell.application.hold_transport_snapshot import HoldHTTPReader, STATUS
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

STARTUP = "wizard-20260923T011452527448Z-ccd23eda5c794a38afcb5fd1f7034c8b"


def http_status(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as response:return response.status
    except urllib.error.HTTPError as error:return error.code


def main():
    root=Path(__file__).resolve().parents[1]
    binding=review_recovery_startup(root,STARTUP,revision=62)
    address=binding["address"]
    observed=json.loads(HoldHTTPReader(address)._get(STATUS,maximum_bytes=512,timeout_seconds=3))
    if observed.get("instance_id")!=binding["expected_boot"] or observed.get("state")!="IDLE":
        raise ValueError("Controller boot changed or not idle")
    target=http_status(f"http://{address}/rocell/large-pose-lift/status")
    missing=http_status(f"http://{address}/rocell/no-such-route")
    if target!=403 or missing!=404:raise ValueError("T1 route registration not distinguished")
    report={"schema":"rocell.r62_unsigned_route_presence.v1",
            "boot":binding["expected_boot"],"lift_status_http":target,
            "unknown_path_http":missing,"route_registered":True,
            "authenticated_exchange_verified":False,"servo_command_sent":False,
            "movement_authorized":False}
    exports=root/"runs/wizard-exports";exporter=WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved=exporter.export({"mode":"r62-unsigned-route-presence"},[],attachments={
        "r62-route-presence.json":canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:raise ValueError("Route export failed")
    print(json.dumps({"export":saved["path"],**report}))


if __name__=="__main__":main()
