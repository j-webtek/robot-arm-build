"""Cached absence diagnostics only; never replay the original query.

Physical/source/storage facts in the portable case are explicitly modeled.
The optional preserved public01 checkpoint contains genuine NTFS/public logs
and modeled observations. Both renderers are inert; the browser harness uses
only a finite Node fake-DOM subprocess, never a production helper or device.
"""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from rocell.application.physical_usb_identity_export import (
    prepare_usb_identity_diagnostics_export,
    restore_usb_identity_diagnostics,
)
from test_wizard_usb_absence_ui import (
    ready,
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    workspace,
    empty_campaigns,
    setup_flow,
    complete_setup,
    prerequisite_summary,
    forbid_native_execution,
    absence_subjects,
    presence_result,
    refresh_read,
    adopt,
    snapshot,
    check_rendered,
)


HEADING = "Physical-node query evidence unavailable"
WARNING = (
    "No owned execution evidence is available for this retained request or partial "
    "attempt. Do not infer that the query did not run or that effects were zero. "
    "Export the original campaign and terminal reasons; do not replay this request."
)
CHECKPOINT = (
    Path(__file__).resolve().parents[3]
    / ".codex-preserved/usb-absence-public-20260909-01"
    / "test_actual_public_baseline_to0/absence-public-checkpoint.json"
)


def assert_unknown(texts):
    for text in texts:
        assert HEADING in text and WARNING in text
        # Inspect only the new notice; earlier BASELINE has independent known
        # counters and must not be relabeled UNKNOWN by this UI-only change.
        notice = text.split(HEADING, 1)[1].split(WARNING, 1)[0]
        # The existing browser facts formatter humanizes underscores; terminal
        # keeps the literal keys. Both must show the same explicit unknowns.
        readable = notice.replace("_", " ")
        assert "NOT REPORTED" in readable
        for key in (
            "api_calls",
            "device_handle_opens",
            "configuration_writes",
            "frames",
        ):
            assert key.replace("_", " ") in readable
        assert notice.count("UNKNOWN") == 4


def test_modeled_terminal_without_artifact_is_unknown_in_both_renderers(
    ready, setup_flow, complete_setup, monkeypatch
):
    made = absence_subjects(ready, monkeypatch, stop="query")
    presence_result(made, unknown=True)
    terminal = made.campaign_originals[0]["original"]
    # Explicit modeled terminal-only audit output, not a fabricated observation.
    terminal.update(
        evidence=None,
        evidence_sha256=None,
        reference=None,
        retention="M1_TERMINAL_READ_BACK_NO_EVIDENCE",
    )
    terminal["result"]["reason_codes"] = ["MODELED_WORKER_FAILURE"]
    workflow = refresh_read(ready)
    assert workflow["usb_qualification_absence"]["state"] == "ORIGINAL_CAMPAIGN_HELD"
    owner = adopt(setup_flow[0], workflow)
    view = snapshot(owner, complete_setup)
    absence = view["usb_qualification"]["absence"]
    assert (
        absence["execution"]
        is absence["observation"]
        is absence["phase_record"]
        is None
    )
    assert_unknown(check_rendered(view))

    # Renderer-only prefix variants: do not suggest a query happened before the
    # final review, but do not infer no effects after a partial reviewed attempt.
    for state, has_review, expected in (
        ("QUERY_REQUESTED", True, True),
        ("INCOMPLETE", True, True),
        ("INCOMPLETE", False, False),
        ("RUNTIME_REVIEWED", True, False),
    ):
        variant = deepcopy(view)
        row = variant["usb_qualification"]["absence"]
        row["state"] = state
        if not has_review:
            row["runtime_review"] = None
        texts = check_rendered(variant)
        if expected:
            assert_unknown(texts)
        else:
            assert all(HEADING not in text for text in texts)


@pytest.mark.skipif(
    not CHECKPOINT.is_file(), reason="Preserved local public01 checkpoint absent"
)
def test_actual_failed_public01_cached_render_and_exact_v4_roundtrip():
    saved = json.loads(CHECKPOINT.read_bytes())
    view, diagnostics = saved["snapshot"], saved["diagnostics"]
    assert saved["complete"] is False
    assert view["usb_qualification"]["status"] == "HISTORICAL_HELD"
    assert view["usb_qualification"]["absence"]["state"] == "QUERY_REQUESTED"
    assert_unknown(check_rendered(view))
    report, parts = prepare_usb_identity_diagnostics_export(
        diagnostics,
        source_sha256=diagnostics["source_sha256"],
        launch_id=diagnostics["launch_session_id"],
    )
    restored = restore_usb_identity_diagnostics(
        report, {"attachment-" + name: payload for name, payload in parts.items()}
    )
    assert restored == diagnostics
    original = restored["qualification_absence_attempt"]["dispatch"]["original"]
    assert original["result"]["state"] == "SEALED_UNCERTAIN"
    assert original["result"]["receipt"] is original["evidence"] is None
    assert original["result"]["quarantine_latched"] is True
    assert original["result"]["reason_codes"] == [
        "WORKER_OR_POST_ARM_PUBLICATION_FAILED",
        "OwnedUsbPresenceEvidenceError",
    ]
    assert restored["qualification_absence"]["phase_record"] is None
    assert report["summary"]["qualification_absence_sha256"] is None
    assert report["reconstruction_status"] == "ORIGINAL_BYTES_RECONSTRUCTIBLE"
