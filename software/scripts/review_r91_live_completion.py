"""Verify five exported r91 legs and make one read-only terminal-status GET.

This reviewer never sends start, next, receipt, or a servo command.
"""

import json
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.product_ghost_export_review import _read
from rocell.application.reviewed_hover_recovery_admission import POSES
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


BOOT = "fd1421c7f4737db0e21fa16e0cdf85eb"
LEG_EXPORTS = [
    "wizard-20260925T140618155449Z-694c01ad55e647049650be32e266dd01",
    "wizard-20260925T140619712343Z-8e5f2ab92e684e06987564e0b81b27d9",
    "wizard-20260925T140621128573Z-4cbb2eed52f54ac2bb747ae35259f8cf",
    "wizard-20260925T140622724269Z-3c416db29f0c4837b8d32597aa823768",
    "wizard-20260925T140624401004Z-870759202c404d48b0d93b2af4d46a88",
]


def review(root: Path, address: str) -> dict:
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    if not (exports / f"recovery-hover-live-{BOOT}.json").exists():
        raise ValueError("Exact live boot claim required")
    rows = []
    for leg, export_id in enumerate(LEG_EXPORTS, 1):
        if not verify_export(exports / export_id)["valid"]:
            raise ValueError("Leg export invalid")
        row, _ = _read(exports, export_id, "attachment-reviewed-hover-assessment.json")
        if (row.get("status") != "REVIEWED_HOVER_LEG_VERIFIED" or
                row.get("boot") != BOOT or row.get("leg") != leg or
                row.get("pose_id") != POSES[leg - 1] or
                row.get("source_kind") != "live_controller" or
                len(row.get("target_errors_counts", [])) != 7 or
                row.get("physical_accuracy_verified") is not False or
                (rows and row["authenticated_next_sequence"] <=
                 rows[-1]["authenticated_next_sequence"])):
            raise ValueError("Leg evidence or progression differs")
        rows.append(row)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    intent = dict(schema="rocell.r91_terminal_status_intent.v1", boot_id=BOOT,
                  leg_export_ids=LEG_EXPORTS, authenticated_sequence=55,
                  request="GET /rocell/recovery-hover/status",
                  movement_command_sent=False, retry_allowed=False)
    saved = exporter.export({"mode": "r91-terminal-status-intent"}, [],
                            attachments={"intent.json": canonical(intent)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Terminal intent export invalid")
    publish_reservation_bytes(exports, f"r91-terminal-status-{BOOT}.json",
        canonical(dict(intent_export=Path(saved["path"]).name, **intent)),
        maximum_bytes=2048)
    report = dict(**intent, status="INCONCLUSIVE", terminal_response=None,
                  maximum_abs_joint_error_counts=max(abs(error) for row in rows
                                                     for error in row["target_errors_counts"]))
    try:
        key = load_reviewed_key(root)
        client = CharacterizationHTTP(address, key=key, boot=BOOT,
                                       read_only_initial_sequence=55)
        response = client("GET", "/rocell/recovery-hover/status")
        report["terminal_response"] = response.decode("ascii")
        report["status"] = ("COMPLETE_CONFIRMED" if response ==
                            b"REVIEWED_HOVER_COMPLETE|5" else "TERMINAL_STATE_DIFFERS")
    except Exception as error:
        report["status"] = "TERMINAL_QUERY_FAILED"
        report["error_type"] = type(error).__name__
    saved = exporter.export({"mode": "r91-live-cycle-review"}, [],
                            attachments={"review.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Cycle review export invalid")
    return dict(status=report["status"], response=report["terminal_response"],
                maximum_abs_joint_error_counts=report["maximum_abs_joint_error_counts"],
                export=saved["path"], movement_command_sent=False)


if __name__ == "__main__":
    print(json.dumps(review(Path(__file__).resolve().parents[1], "192.168.0.225")))
