"""Capture one read-only r96 HTTP identity and correlate retained originals.

This script never opens the serial port.  It performs exactly one GET against
the fixed r96 capability endpoint, with no retry or redirect behavior, and then
writes one local evidence candidate.  It cannot approve qualification.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import re
import sys
import uuid

from rocell.application.installed_controller_passive_evidence_v1 import (
    assemble_installed_controller_passive_evidence_v1,
    canonical_json,
)


HOST = "192.168.0.225"
ENDPOINT = "/rocell/registration-ladder/capabilities"
EXPECTED_BOOT = "4390cfab5cd74a16fd5048406c1b5adf"
MAXIMUM_RESPONSE_BYTES = 512


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--usb-port", default="COM7")
    parser.add_argument("--usb-pnp-instance-id", required=True)
    return parser.parse_args()


def _one_get() -> dict:
    connection = http.client.HTTPConnection(HOST, 80, timeout=3)
    try:
        connection.request("GET", ENDPOINT)
        response = connection.getresponse()
        raw = response.read(MAXIMUM_RESPONSE_BYTES + 1)
    finally:
        connection.close()
    if response.status != 200 or len(raw) > MAXIMUM_RESPONSE_BYTES:
        raise RuntimeError("bounded r96 capability response unavailable")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("r96 capability response is not UTF-8 JSON") from exc
    if type(value) is not dict or value.get("boot_id") != EXPECTED_BOOT:
        raise RuntimeError("r96 boot identity changed; stop without serial access")
    return value


def main() -> int:
    args = _arguments()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("passive evidence output already exists")
    if not re.fullmatch(r"COM[1-9][0-9]{0,3}", args.usb_port):
        raise ValueError("invalid explicit USB port")
    root = Path(__file__).resolve().parents[1]
    app = (
        root / ".firmware-tools/build-configured-diagnostic-candidate-r96--default-4mb-no-psram"
        / "RoArm-M3_example.ino.bin"
    ).read_bytes()
    journal = (
        root / "private-backups/controller-20260918-session1/app-r96-deployment-events.jsonl"
    ).read_bytes()
    export = (
        root / "runs/wizard-exports"
        / "wizard-20260925T192321044325Z-585d3a0f6d1c4669ade120dae20dfd47"
    )
    captured = datetime.now(timezone.utc)
    evidence = assemble_installed_controller_passive_evidence_v1(
        capture_id=f"r96-passive-{captured.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex}",
        captured_at_utc=captured.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        usb_port=args.usb_port,
        usb_pnp_instance_id=args.usb_pnp_instance_id,
        installed_app_bytes=app,
        deployment_journal_bytes=journal,
        final_export_manifest_bytes=(export / "manifest.json").read_bytes(),
        final_feedback_attachment_bytes=(
            export / "attachment-registration-ladder-leg.json").read_bytes(),
        live_capabilities=_one_get(),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json(evidence.to_dict()) + b"\n")
    print(json.dumps({
        "output": str(output),
        "evidence_sha256": evidence.evidence_sha256,
        "controller_session_id": evidence.controller_session_id,
        "review_disposition": "UNREVIEWED",
        "qualification_evidence_ready": False,
        "serial_port_opened": False,
        "controller_restarted": False,
        "hardware_writes": 0,
        "movement_commands": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
