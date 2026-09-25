"""Read-only reconstruction of one exact saved USB diagnostic export.

Uses the application's existing manifest and USB codecs, including their byte
limits and path checks. No wizard, original store, lease, process, camera or arm
is opened. A verified copy is diagnostic evidence, not hardware qualification
or proof of an authentic commissioning store. Raw device/operator data is not
printed; review the retained files privately before sharing them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "software/src"))

from rocell.application.physical_usb_identity_export import (  # noqa: E402
    restore_usb_identity_diagnostics,
)
from rocell.application.wizard_diagnostic_export import (  # noqa: E402
    WizardDiagnosticExportError,
    _parse_json,
    _read,
    verify_export,
)


class UsbExportVerificationError(ValueError):
    """A closed verifier failure; never contains a dump of private subjects."""


def verify(
    directory: Path, *, expected_original_sha256: str | None = None
) -> dict[str, Any]:
    """Verify and reconstruct copied bytes, without reopening their originals.

    Read only names from the already validated manifest, not filenames supplied
    by the inner snapshot. Recheck every copied payload against that manifest,
    and verify its identity again after reconstruction to detect changed files.
    This is bounded diagnostic consistency, not a cryptographic trust anchor.
    """
    integrity = verify_export(directory)
    if integrity["valid"] is not True:
        raise UsbExportVerificationError("MANIFEST_VERIFICATION_FAILED")

    payloads = {}
    for descriptor in integrity["files"]:
        name = descriptor["name"]
        if name != "report.json" and not name.startswith("attachment-"):
            continue
        raw = _read(directory / name, max(1, descriptor["bytes"]))
        if (
            len(raw) != descriptor["bytes"]
            or hashlib.sha256(raw).hexdigest() != descriptor["sha256"]
        ):
            raise UsbExportVerificationError("EXPORT_CHANGED_DURING_READ")
        payloads[name] = raw

    report = _parse_json(payloads.pop("report.json"))
    if type(report) is not dict or type(report.get("snapshot")) is not dict:
        raise UsbExportVerificationError("USB_SNAPSHOT_REQUIRED")
    snapshot = report["snapshot"]
    restored = restore_usb_identity_diagnostics(
        snapshot,
        payloads,
        expected_original_diagnostics_sha256=expected_original_sha256,
    )
    after = verify_export(directory)
    if (
        after["valid"] is not True
        or after["manifest_sha256"] != integrity["manifest_sha256"]
        or after["files"] != integrity["files"]
    ):
        raise UsbExportVerificationError("EXPORT_CHANGED_DURING_VERIFICATION")

    # Restoration already checks all four flags; expose the unchanged ceiling.
    return dict(
        valid=True,
        status="VERIFIED_USB_DIAGNOSTIC_COPY",
        export_schema=snapshot["schema"],
        diagnostics_schema=restored["schema"],
        source_sha256=restored["source_sha256"],
        manifest_sha256=integrity["manifest_sha256"],
        original_diagnostics_sha256=snapshot["original_diagnostics_sha256"],
        exported_diagnostics_sha256=snapshot["exported_diagnostics_sha256"],
        original_bytes_preserved=snapshot["original_bytes_preserved"],
        credential_redaction_applied=snapshot["credential_redaction_applied"],
        reconstruction_status=snapshot["reconstruction_status"],
        reconstructed_subject_count=len(snapshot["coverage"]),
        attachment_bytes=sum(map(len, payloads.values())),
        physical_authority=False,
        hardware_qualified=False,
        original_store_authenticated=False,
        original_store_reopened=False,
        meaning="Verified saved diagnostic bytes only; no hardware or stage permission.",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Exact absolute export directory")
    parser.add_argument(
        "--expected-original-sha256",
        help="Optional independently recorded original-diagnostics SHA-256 pin",
    )
    args = parser.parse_args(argv)
    try:
        result = verify(
            args.directory, expected_original_sha256=args.expected_original_sha256
        )
    except (ValueError, OSError, WizardDiagnosticExportError):
        # Detailed native identifiers and arbitrary exception text stay private.
        print(
            json.dumps(
                dict(valid=False, status="USB_DIAGNOSTIC_VERIFICATION_FAILED"),
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
