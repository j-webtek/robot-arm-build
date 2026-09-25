"""Read-only development verification of one retained NC-01 export.

Runs the real export integrity checker and terminal renderer, plus the existing
Node fake-DOM harness for app.js. This is not a real-browser or physical hardware
test. No campaign, M1 reopen, calculator, device action or file write is invoked.
Requires the development test helpers and Node; it is not a runtime wizard API.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys


WORKSPACE = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(WORKSPACE / "software/src"),
    str(WORKSPACE / "software/tests/unit"),
]

from rocell.application.wizard_diagnostic_coordinator import (
    source_fingerprint,
)  # noqa: E402
from rocell.application.wizard_diagnostic_export import verify_export  # noqa: E402
from test_arrival_wizard_reopen_ui import browser  # noqa: E402
from test_arrival_wizard_terminal import Service, run  # noqa: E402


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify(
    directory: Path, *, source: str, receipt: str, attachment: str, evaluation: str
) -> dict:
    integrity = verify_export(directory)
    assert integrity["valid"] is True, integrity
    before_source = source_fingerprint(WORKSPACE)
    assert before_source == source
    attachment_path = directory / "attachment-noncontact-readiness.json"
    report_path = directory / "report.json"
    attachment_bytes, report_bytes = (
        attachment_path.read_bytes(),
        report_path.read_bytes(),
    )
    assert sha(attachment_bytes) == attachment
    envelope = json.loads(attachment_bytes)
    assert envelope["schema"] == "rocell.noncontact_diagnostic_export.v1"
    assert envelope["original_bytes_preserved"] is True
    assert envelope["publication"] == "CURRENT_GAP_REPORT"
    assert envelope["physical_authority"] is False
    retained = envelope["receipt"]
    retained_bytes = canonical(retained)
    assert sha(retained_bytes) == receipt
    assert retained["workspace_source_sha256"] == source
    numerical = retained["evaluation"]
    numerical_bytes = canonical(numerical)
    assert sha(numerical_bytes) == evaluation == retained["evaluation_sha256"]
    assert numerical["outcome"] == "BLOCKED"
    assert numerical["physical_authority"] is False
    assert all(
        type(count) is int and count == 0
        for count in numerical["actual_physical_effects"].values()
    )
    snapshot = json.loads(report_bytes)["snapshot"]
    assert snapshot["source_binding_sha256"] == source
    rehearsal = snapshot["commissioning_rehearsal"]
    compact = rehearsal["noncontact_evaluation"]
    assert compact["evaluation_sha256"] == evaluation
    assert compact["safe_summary"] == numerical["safe_summary"]
    assert compact["checks"] == numerical["checks"]
    assert compact["selected_inputs_sha256"] == numerical["selected_inputs_sha256"]
    assert rehearsal["session_id"] == retained["session_id"]
    assert rehearsal["session_origin"] == "REOPENED_EXISTING"
    assert rehearsal["stage"] == "noncontact_acceptance"
    assert rehearsal["stage_state"] == "BLOCKED"
    # Exactly thirteen rehearsal passes, the blocked gap report and pending
    # handoff; none of these statuses promotes any physical-stage progress.
    states = Counter(row["state"] for row in rehearsal["stages"])
    assert states == {"PASS": 13, "BLOCKED": 1, "PENDING": 1}, states
    assert len(snapshot["stages"]) == 15
    assert all(row["state"] == "PHYSICAL_PENDING" for row in snapshot["stages"])
    summary = compact["safe_summary"]
    assert summary["accuracy"]["status"] == "BLOCKED_UNBOUNDED"
    assert summary["accuracy"]["conservative_error_micrometers"] is None
    assert summary["accuracy"]["remaining_margin_micrometers"] is None
    controls = {row["case_id"]: row for row in summary["accuracy"]["controls"]}
    assert controls["finite_control"]["remaining_margin_micrometers"] == 3000
    assert controls["target_margin"]["remaining_margin_micrometers"] == -1500
    assert (
        sum(
            row["check_kind"] == "NOMINAL" and row["passed"] is False
            for row in compact["checks"]
        )
        == 3
    )
    assert sum(row["passed"] is True for row in compact["checks"]) == 5

    # Pass the exact exported full view to the real JS source in the fake DOM.
    page = browser(rehearsal, snapshot=deepcopy(snapshot))
    assert page["status"] == "Local service connected", page["error"]
    assert page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert page["dialogOpen"] is False

    class ExportView(Service):
        def view(self):
            self.calls.append(("view",))
            return deepcopy(snapshot)

    service = ExportView()
    code, output, _ = run(service, ["quit"])
    assert code == 0
    assert service.calls == [("view",)]
    assert service.shutdown_count == 0
    terminal = "\n".join(output)
    for rendered in (page["text"], terminal):
        assert "Retained noncontact readiness gaps" in rendered
        assert "Noncontact projection is missing" not in rendered
        assert "The retained check projection is missing" not in rendered
        assert "Nominal build readiness" in rendered
        assert "BLOCKED_UNBOUNDED" in rendered
        assert "Real-build accuracy" in rendered
        assert "Separate synthetic accuracy controls" in rendered
        assert "3000" in rendered and "-1500" in rendered
        assert "No power, movement or contact is authorized" in rendered
        assert "cannot advance to handoff" in rendered
        assert evaluation in rendered
    assert (
        "NOMINAL CHECK PASSED REHEARSAL"
        not in page["text"].split("Retained noncontact readiness gaps", 1)[1]
    )
    assert (
        "NOMINAL_CHECK_PASSED_REHEARSAL"
        not in terminal.split("Retained noncontact readiness gaps", 1)[1].split(
            "Original rehearsal", 1
        )[0]
    )
    # Re-read only the selected export and source identities; original bytes
    # must remain unchanged after presentation. No acceptance verifier is run.
    assert attachment_path.read_bytes() == attachment_bytes
    assert report_path.read_bytes() == report_bytes
    assert source_fingerprint(WORKSPACE) == before_source
    return {
        "verification": "PASSED_READ_ONLY_EXPORT_AND_PRESENTATION",
        "export_integrity_valid": True,
        "source_sha256": source,
        "receipt_sha256": receipt,
        "attachment_sha256": attachment,
        "evaluation_sha256": evaluation,
        "receipt_bytes": len(retained_bytes),
        "attachment_bytes": len(attachment_bytes),
        "evaluation_bytes": len(numerical_bytes),
        "report_bytes": len(report_bytes),
        "original_session_id": rehearsal["session_id"],
        "rehearsal_states": dict(states),
        "physical_stages_pending": 15,
        "nominal_checks_blocked": 3,
        "synthetic_controls_passed": 5,
        "real_accuracy": "BLOCKED_UNBOUNDED",
        "finite_control_margin_micrometers": 3000,
        "target_margin_fault_micrometers": -1500,
        "browser_check": "REAL_APP_JS_IN_FAKE_DOM_NOT_REAL_BROWSER",
        "browser_requests": page["requests"],
        "terminal_exit_code": code,
        "terminal_calls": [list(call) for call in service.calls],
        "physical_authority": False,
        "original_export_unchanged": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    for name in ("source", "receipt", "attachment", "evaluation"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = verify(
        args.directory.absolute(),
        source=args.source,
        receipt=args.receipt,
        attachment=args.attachment,
        evaluation=args.evaluation,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
