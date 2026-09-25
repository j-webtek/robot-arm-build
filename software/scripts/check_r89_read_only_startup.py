"""One read-only r89 startup check; never sends a motion or reservation request."""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.servo_diagnostic_http import DiagnosticHTTPReader
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


APP_SHA = "89c0d91334ab4362d392a3e3e66433c216d7e1740842dbba1b87881b722236b0"
RELEASE_SHA = "653729599a9ba29baed5095b3ed156810b38396065a0b6a3a06fe6c7dd74ab1a"


def check(root: Path, address: str) -> dict:
    root = Path(root).resolve()
    address = DiagnosticHTTPReader(address, 80).address
    journal = root / "private-backups/controller-20260918-session1/app-r89-attempt2-deployment-events.jsonl"
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    if ([row.get("stage") for row in rows] != [
            "RESERVED", "IDENTITY_AND_PREWRITE_VERIFIED", "WRITE_ATTEMPT_STARTED",
            "FLASH_VERIFIED", "ONE_STARTUP_ATTEMPT", "STARTUP_RESET_SENT"] or
            rows[3].get("app_sha256") != APP_SHA or
            rows[3].get("protected_regions_unchanged") is not True):
        raise ValueError("Verified one-startup r89 installation required")
    app = (root / ".firmware-tools/build-configured-diagnostic-candidate-r89--default-4mb-no-psram"
           / "RoArm-M3_example.ino.bin").read_bytes()
    if hashlib.sha256(app).hexdigest() != APP_SHA:
        raise ValueError("Local installed-image reference differs")
    exporter = WizardDiagnosticExporter(root / "runs/wizard-exports")
    exporter.prepare(create=True)
    report = dict(schema="rocell.r89_read_only_startup.v1", address=address,
                  app_sha256=APP_SHA, release_sha256=RELEASE_SHA,
                  status="INCONCLUSIVE", motion_request_sent=False,
                  reservation_request_sent=False, authenticated_status=None)
    boot = None
    try:
        connection = http.client.HTTPConnection(address, 80, timeout=3)
        try:
            connection.request("GET", "/rocell/reviewed-hover/capabilities",
                               headers={"Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError("Capabilities HTTP status differs")
            raw = response.read(513)
        finally:
            connection.close()
        if len(raw) > 512:
            raise ValueError("Capabilities response exceeds bound")
        caps = json.loads(raw)
        if (type(caps) is not dict or set(caps) != {
                "schema", "boot_id", "live_release_available",
                "motion_authorized", "maximum_legs", "stamped_release_sha256"} or
                caps["schema"] != "rocell.reviewed_hover_capabilities.v1" or
                caps["live_release_available"] is not True or
                caps["motion_authorized"] is not False or
                caps["maximum_legs"] != 16 or
                caps["stamped_release_sha256"] != RELEASE_SHA or
                type(caps["boot_id"]) is not str or
                re.fullmatch(r"[0-9a-f]{32}", caps["boot_id"]) is None or
                caps["boot_id"] == "0" * 32):
            raise ValueError("r89 capabilities identity/policy differs")
        boot = caps["boot_id"]
        report["boot_id"] = boot
        marker = root / "runs/wizard-exports" / f"r89-read-only-status-{boot}.json"
        with marker.open("x", encoding="utf-8") as handle:
            json.dump({"schema": "rocell.r89_status_one_use.v1", "boot_id": boot,
                       "app_sha256": APP_SHA}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        key = load_reviewed_key(root)
        client = CharacterizationHTTP(address, key=key, boot=boot)
        status = client("GET", "/rocell/reviewed-hover/status").decode("ascii")
        report["authenticated_status"] = status
        # The native owner exposes the next leg as one-based even in New.
        if status != "NEW|1":
            raise ValueError("Reviewed-hover owner is not unused")
        report["status"] = "READ_ONLY_STARTUP_VERIFIED"
    except Exception as error:
        report["status"] = "READ_ONLY_STARTUP_FAILED"
        report["error_type"] = type(error).__name__
        report["error"] = str(error)
    saved = exporter.export({"mode": "r89-read-only-startup"}, [],
                            attachments={"r89-read-only-startup.json":
                                         json.dumps(report, sort_keys=True).encode()})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Startup report export failed")
    return {"status": report["status"], "export": saved["path"],
            "boot_id": boot, "error": report.get("error")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", default="192.168.0.225")
    args = parser.parse_args()
    print(json.dumps(check(Path(__file__).resolve().parents[1], args.address)))


if __name__ == "__main__":
    main()
