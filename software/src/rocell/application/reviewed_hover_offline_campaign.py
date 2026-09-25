"""Simulation-only review and durable export of reviewed-hover records.

Receipt values are returned for protocol tests; this module has no network,
serial, controller route, or movement capability and sends no receipt.
"""
from __future__ import annotations

from pathlib import Path

from .first_motion_contract import canonical
from .reviewed_hover_manifest import validate_manifest
from .reviewed_hover_record import assess_reviewed_hover_leg
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def review_offline_campaign(records: list[bytes], *, manifest: dict, boot: str,
                            export_root: Path) -> dict:
    reviewed = validate_manifest(manifest)
    if type(records) is not list or len(records) != reviewed["leg_count"]:
        raise ValueError("Exact finite record list required")
    exporter = WizardDiagnosticExporter(Path(export_root).resolve())
    exporter.prepare(create=True)
    rows: list[dict] = []
    exports: list[str] = []
    receipts: list[bytes] = []
    for leg, raw in enumerate(records, 1):
        try:
            row = assess_reviewed_hover_leg(raw, manifest=manifest, boot=boot,
                                             leg=leg, previous=rows[-1] if rows else None)
            row["source_kind"] = "simulation"
            saved = exporter.export({"mode": "reviewed-hover-offline-leg"}, [],
                attachments={
                    "reviewed-hover-record.hex.txt": raw.hex().encode("ascii"),
                    "reviewed-hover-assessment.json": canonical(row),
                })
            if not verify_export(Path(saved["path"]))["valid"]:
                raise ValueError("Leg export invalid")
        except Exception as error:
            fault = exporter.export({"mode": "reviewed-hover-offline-fault"}, [],
                attachments={
                    "reviewed-hover-fault.json": canonical(dict(
                        schema="rocell.reviewed_hover_offline_fault.v1",
                        failed_leg=leg, completed_legs=len(rows), prior_exports=exports,
                        error_type=type(error).__name__, retry_allowed=False,
                        receipt_issued_for_failed_leg=False)),
                    "reviewed-hover-fault-record.hex.txt":
                        raw.hex().encode("ascii") if type(raw) is bytes else b"",
                })
            if not verify_export(Path(fault["path"]))["valid"]:
                raise ValueError("Fault export invalid") from error
            raise ValueError("Offline campaign stopped; evidence: " + fault["path"]) from error
        rows.append(row)
        exports.append(saved["path"])
        # Value only: no controller transport exists in this offline module.
        receipts.append(f'{leg}:{row["record_sha256"]}'.encode("ascii"))
    return dict(status="REVIEWED_HOVER_OFFLINE_RECORDS_VERIFIED",
                rows=rows, exports=exports, simulated_receipts=receipts,
                controller_receipts_sent=False, hardware_access=False,
                motion_authorized=False)
