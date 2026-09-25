"""Public Arrival action, actual Setup/reader and both UIs over MODELED storage.

M1 durability/leases and received device/boot facts are modeled. Original-role
codecs, stage-entry code, Arrival ticket/log/publication, ordinary export files
and renderers are real. This is not fresh NTFS or hardware qualification.
"""

from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import subprocess
from threading import Event
import time

import pytest

from rocell.application import physical_camera_mode_entry_service as entry_service
from rocell.application import physical_camera_setup_service as setup_impl
from rocell.application.physical_camera_mode_entry_projection import (
    mode_entry_projection_valid,
)
from rocell.application.physical_camera_mode_entry import (
    CameraModeEntry,
    camera_mode_entry_label,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.commissioning_camera_persistence import (
    physical_camera_source_binding,
)
from rocell.application.physical_onboarding_m1 import (
    M1CellDescriptor,
    M1RuntimeVerification,
)
from rocell.ui.terminal import _PhysicalSetupDisplay
from test_physical_camera_usb_complete_readback import (
    ready,
    received_ready,
    identity_ready,
    source_model,
    intake_model,
    model,
    workspace,
    empty_campaigns,
    complete_subjects,
    refresh_read,
    change_last_event,
)
from test_physical_camera_intake_setup import setup_flow
from test_arrival_wizard_service import make_service, _ticket, _run
from test_wizard_workspace_source_ui import render_snapshot
from test_usb_observed_projection import forbid_native_execution
import test_physical_camera_usb_reboot_readback as original_fixture


def typed_modeled_storage(case, monkeypatch):
    """Serialize the modeled ledger using the actual public M1 record type.

    The original-reader fixture intentionally exposes a minimal private record.
    A public UI test needs the complete storage record, not relaxed UI checks.
    Ledger facts remain modeled; this neither qualifies NTFS nor changes any
    previously collected subject, reference, event, or original byte.
    """
    owner, _, state = case
    bound = owner.descriptor()
    cell = M1CellDescriptor.build(
        cell_id=bound["cell_id"],
        source_binding_sha256=physical_camera_source_binding(bound["source_sha256"]),
        durability_qualification_sha256="1" * 64,
        created_at_ns=1_800_000_000_000_000_003,
    )
    original_verify = state["store"].verification

    def verification(session_id):
        private = original_verify(session_id)
        return M1RuntimeVerification(
            cell=cell,
            qualification_anchor_sha256="2" * 64,
            startup_qualification_sha256="3" * 64,
            attempt_head_sha256=private.attempt_head_sha256,
            attempt_event_count=0,
            unresolved_attempt_ids=(),
            uncertain_attempt_ids=(),
            quarantine_head_sha256=private.quarantine_head_sha256,
            quarantine_count=0,
            quarantined=False,
            session_id=bound["session_id"],
            session_header_sha256=private.session_header_sha256,
            session_head_sha256=private.session_head_sha256,
            session_reconciliation_required=False,
            active_lease_owners=(),
            evidence_inventory_sha256=private.evidence_inventory_sha256,
            challenge_sha256=private.challenge_sha256,
        )

    monkeypatch.setattr(state["store"], "verification", verification)
    # The modeled refresh callback is file-only and deliberately has no startup.
    owner._cached["operation"] = "REFRESH"


def test_public_entry_preserves_history_publishes_and_exports(
    ready, setup_flow, make_service, monkeypatch, tmp_path
):
    app, runner, _ = make_service(mode="physical")
    typed_modeled_storage(ready, monkeypatch)
    monkeypatch.setattr(original_fixture, "REBOOT_LAUNCH", "wizard-" + "e" * 32)
    complete_subjects(ready, monkeypatch, review_launch_id=app.session_id)
    original = refresh_read(ready)
    setup, state = app._physical_camera_setup, ready[2]
    # Explicit modeled original selection before any entry is requested. No
    # existing receipt, launch identity, original file or journal is relabeled.
    setup.session = ready[0]
    setup._adopt_source_workflow(original)
    setup._publication = dict(status="CURRENT", operation_id="MODELED-original-read")
    app._usb_identity.observe_setup()
    monkeypatch.setattr(entry_service, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(setup_impl, "source_fingerprint", lambda _: state["source"])
    last = [
        max(
            time.time_ns(),
            original["usb_qualification_complete"]["events"][-1]["occurred_at_ns"],
        )
    ]

    def utc():
        last[0] += 1000
        return last[0]

    monkeypatch.setattr(entry_service, "time_ns", utc)
    original_scope = state["store"].stage_transaction

    @contextmanager
    def scope(*args, **kwargs):
        with original_scope(*args, **kwargs) as tx:

            def store_entry(payload, **kw):
                # Model the narrow entry seam, not a generic write that ignores
                # V2's reviewed-stage guard. Real M1/V2 coverage is separate.
                snapshot = tx.snapshot()
                assert snapshot.next_action.stage is STAGE_ORDER[4]
                assert snapshot.next_action.stage_state is V2StageState.PENDING
                assert not any(
                    ref.stage in STAGE_ORDER[4:] for ref in snapshot.evidence
                )
                assert kw["expected_head_sha256"] == snapshot.head.head_sha256
                document = CameraModeEntry(payload).to_dict()
                return state["add"](
                    payload,
                    label=camera_mode_entry_label(document["entry_id"]),
                    media="application/json",
                    stage=STAGE_ORDER[4],
                )

            def ordinary_store(*args, **kwargs):
                pytest.fail("entry must not bypass ordinary V2 stage restrictions")

            tx.store_camera_mode_entry = store_entry
            tx.store_evidence = ordinary_store

            def commit(stage, status, **kw):
                state["advance"](status, kw["detail_code"], kw["evidence"], stage=stage)
                change_last_event(state, occurred_at_ns=kw["occurred_at_ns"])
                return tx.snapshot()

            tx.commit_stage_state = commit
            yield tx

    monkeypatch.setattr(state["store"], "stage_transaction", scope)
    previous = dict(state["payloads"])
    before = app.view()
    (tmp_path / "modeled-before-entry-view.json").write_text(
        json.dumps(before, indent=2), encoding="utf-8"
    )
    assert (
        _PhysicalSetupDisplay.storage_session(
            before["physical_camera_setup"]["session"]
        )
        is not None
    ), "Modeled public storage record must use the full M1 schema"
    assert _PhysicalSetupDisplay.setup(before["physical_camera_setup"]) is not None
    assert before["camera_mode_entry"]["status"] == "READY_TO_ENTER"
    assert mode_entry_projection_valid(
        before["camera_mode_entry"], before["physical_camera_setup"]
    )
    for text in render_snapshot(before):
        assert (
            "Camera setup entry" in text
            and "CAMERA_MODE_ENTRY_NOT_VERIFIED" not in text
        )
        assert "USB_QUALIFICATION_NOT_VERIFIED" not in text

    def no_process(*args, **kwargs):
        pytest.fail("file-only camera entry attempted a native process")

    ticket = _ticket(
        app,
        entry_service.ACTION,
        dict(operator_id="MODELED setup operator", file_only=True),
    )
    assert state["payloads"] == previous and not setup._mode_entry_attempted
    with monkeypatch.context() as guard:
        guard.setattr(subprocess, "Popen", no_process)
        receipt = app.execute_action(ticket["ticket_id"])
        limit = time.monotonic() + 210
        while time.monotonic() < limit:
            outcome = app.operation(receipt["operation_id"])
            if outcome["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
                break
            Event().wait(0.05)
        else:
            pytest.fail("Entry did not finish within its bounded public deadline")
    assert outcome["status"] == "SUCCEEDED", outcome
    current = app.view()
    (tmp_path / "modeled-after-entry-view.json").write_text(
        json.dumps(current, indent=2), encoding="utf-8"
    )
    entry = current["camera_mode_entry"]
    assert entry["status"] == "ENTERED" and entry["publication"]["status"] == "CURRENT"
    assert mode_entry_projection_valid(entry, current["physical_camera_setup"])
    assert previous.items() <= state["payloads"].items()
    assert len(state["payloads"]) == len(previous) + 1
    assert current["camera"]["status"] == current["arm"]["status"] == "NOT_CONNECTED"
    assert current["usb_qualification"]["publication"]["status"] == "HISTORICAL_HELD"
    for text in render_snapshot(current):
        assert "ENTERED" in text
        assert "CAMERA_MODE_ENTRY_NOT_VERIFIED" not in text
        assert "USB_QUALIFICATION_NOT_VERIFIED" not in text
    saved = dict(state["payloads"])
    assert (
        app.execute_action(ticket["ticket_id"])["operation_id"]
        == receipt["operation_id"]
    )
    with pytest.raises(WizardError):
        _ticket(
            app,
            entry_service.ACTION,
            dict(operator_id="MODELED setup operator", file_only=True),
        )
    assert state["payloads"] == saved and not runner.calls

    exported = _run(app, "export_logs")
    (tmp_path / "modeled-export-operation.json").write_text(
        json.dumps(exported, indent=2), encoding="utf-8"
    )
    assert exported["status"] == "SUCCEEDED", json.dumps(exported, indent=2)
    folder = Path(exported["result"]["receipt"]["path"])
    assert verify_export(folder)["valid"] is True
    attachment = json.loads((folder / "attachment-camera-mode-entry.json").read_bytes())
    original_entry = setup.original_source_workflow()["camera_mode_entry"]
    assert attachment["original"] == original_entry
    assert attachment["attempt"] == setup._mode_entry_attempt
    assert attachment["original_bytes_preserved"] is True
    assert (
        attachment["original"]["entry"]["document"]["binding"]["complete_review_sha256"]
        == original["usb_qualification_complete"]["review"]["evidence_sha256"]
    )
    assert state["payloads"] == saved  # Export cannot repeat a stage or device action.
