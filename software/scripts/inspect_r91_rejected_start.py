"""One authenticated, read-only status reconciliation after rejected r91 start.

The prior start received a verified non-2xx response at sequence zero. This
tool may issue only a sequence-one GET; it never retries start or moves.
"""

import json
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from run_r90_pose_observation import get
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

from run_r91_recovery_cycle import BOOT, R91_RELEASE_SHA


FAULT_EXPORT = "wizard-20260925T135506905728Z-d67f59792812420184e904b5f2fcfa65"


def inspect(root: Path, address: str) -> dict:
    root = Path(root).resolve()
    exports = root / "runs/wizard-exports"
    fault, _ = _read(exports, FAULT_EXPORT, "attachment-reviewed-hover-fault.json")
    marker = exports / f"recovery-hover-live-{BOOT}.json"
    claimed = json.loads(marker.read_text(encoding="utf-8"))
    if (fault.get("schema") != "rocell.reviewed_hover_recovery_live_fault.v1" or
            fault.get("failed_leg") != 0 or fault.get("completed_legs") != 0 or
            fault.get("last_status") is not None or fault.get("retry_allowed") is not False or
            fault.get("transport_uncertainty") is not None or
            claimed.get("boot_id") != BOOT or
            claimed.get("release_sha256") != R91_RELEASE_SHA or
            claimed.get("retry_allowed") is not False):
        raise ValueError("Exact rejected-start evidence required")
    code, raw = get(address, "/rocell/recovery-hover/capabilities", 512)
    caps = json.loads(raw)
    if (code != 200 or caps.get("boot_id") != BOOT or
            caps.get("stamped_release_sha256") != R91_RELEASE_SHA):
        raise ValueError("Controller boot/release changed")
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    intent = dict(schema="rocell.r91_rejected_start_status_intent.v1",
                  boot_id=BOOT, prior_fault_export_id=FAULT_EXPORT,
                  authenticated_sequence=1, request="GET /rocell/recovery-hover/status",
                  retry_allowed=False, movement_command_sent=False)
    saved = exporter.export({"mode": "r91-rejected-start-read-only-intent"}, [],
                            attachments={"intent.json": canonical(intent)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Read-only intent export invalid")
    publish_reservation_bytes(exports, f"r91-rejected-start-status-{BOOT}.json",
                              canonical(dict(intent_export=Path(saved["path"]).name,
                                             **intent)), maximum_bytes=2048)
    report = dict(**intent, status="INCONCLUSIVE", status_response=None)
    try:
        key = load_reviewed_key(root)
        client = CharacterizationHTTP(address, key=key, boot=BOOT,
                                       read_only_initial_sequence=1)
        response = client("GET", "/rocell/recovery-hover/status")
        if len(response) > 128:
            raise ValueError("Status response exceeds bound")
        report["status_response"] = response.decode("ascii")
        report["status"] = "AUTHENTICATED_READ_ONLY_STATUS"
    except Exception as error:
        report["status"] = "READ_ONLY_STATUS_FAILED"
        report["error_type"] = type(error).__name__
    saved = exporter.export({"mode": "r91-rejected-start-read-only-result"}, [],
                            attachments={"result.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Read-only result export invalid")
    return dict(status=report["status"], response=report["status_response"],
                export=saved["path"], movement_command_sent=False)


if __name__ == "__main__":
    print(json.dumps(inspect(Path(__file__).resolve().parents[1], "192.168.0.225")))
