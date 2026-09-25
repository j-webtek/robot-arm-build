"""Actual isolated NTFS originals, explicitly MODELED physical observations.

No camera/USB/CIM/serial or child process is invoked. These tests exercise the
real original-store APIs and readback, not public acquisition or qualification.
"""

import os
import time

import pytest

from rocell.application import physical_camera_session as session
from rocell.application import physical_camera_usb_trial_readback as trial
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.providers.windows.native_camera_protocol import canonical
from test_physical_camera_identity_readback import (
    actual_identity_entry,
    actual_transaction_state,
    identity_subjects,
    identity_inputs,
    no_devices,
    workspace,
)
from test_physical_camera_usb_phase_readback import phase_subjects, LAUNCH
from test_physical_camera_session import session_fixture, perform
from test_physical_camera_intake_session import read

TRIAL_ID = "usbtrial-" + "e" * 32


def actual_declared_trial(workspace, monkeypatch):
    """Reusable real v9 original prefix; all received facts are MODELED."""
    case = actual_identity_entry(
        workspace, monkeypatch, include_configuration_epochs=True
    )
    owner, prerequisites, state = case
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        state.update(
            actual_transaction_state(tx), events=tx.snapshot().committed_events
        )
        identity_subjects(case, **identity_inputs())
    perform(owner, "refresh")
    before = read(owner, state["header"].header_sha256)
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        current = actual_transaction_state(tx)
        current["advance"](
            V2StageState.WAITING_OPERATOR,
            trial.usb_qualification_event("REQUESTED", TRIAL_ID),
            trial.usb_qualification_predecessor_references(before),
            stage=STAGE_ORDER[3],
        )
        plan = trial.build_original_usb_qualification_plan(
            prerequisites,
            before,
            trial_id=TRIAL_ID,
            operator_id="MODELED-file-declaration",
            launch_session_id=LAUNCH,
            cable_label="MODELED cable",
            port_label="MODELED port",
            created_at_utc_ns=time.time_ns(),
        )
        reference = current["add"](
            plan.payload,
            label=trial.TRIAL_LABEL_PREFIX + TRIAL_ID,
            stage=STAGE_ORDER[3],
        )
        current["advance"](
            V2StageState.REVIEW_PENDING,
            trial.usb_qualification_event("DECLARED", TRIAL_ID),
            (reference,),
            stage=STAGE_ORDER[3],
        )
    perform(owner, "refresh")
    original = read(owner, state["header"].header_sha256)
    return case, original


def actual_phase_prefix(workspace, monkeypatch, *, stop="reviewed"):
    """Reusable actual original REVIEWED (or partial) v10, no process calls."""
    case, original = actual_declared_trial(workspace, monkeypatch)
    owner, _, state = case
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        state.update(
            actual_transaction_state(tx), events=tx.snapshot().committed_events
        )
        made = phase_subjects(case, stop=stop, actual_original=original)
    perform(owner, "refresh")
    made.retained = read(owner, state["header"].header_sha256)
    return made


@pytest.mark.skipif(os.name != "nt", reason="Real original NTFS owner required")
def test_actual_ntfs_reviewed_baseline_originals_reopen_without_acquisition(
    workspace, monkeypatch
):
    made = actual_phase_prefix(workspace, monkeypatch)
    owner, _, state = made.case
    before = made.retained
    row = before["usb_qualification_baseline"]
    assert before["schema"] == session.SOURCE_WORKFLOW_USB_PHASE_SCHEMA
    assert row["state"] == "REVIEWED"
    assert len(row["events"]) == 4
    assert row["host_boot"] is None and row["execution"] is None
    assert row["original_campaign"] is None
    for role, subject in made.subjects.items():
        assert canonical(row[role]["document"]) == (
            subject if type(subject) is bytes else subject.payload
        )
        assert row[role]["reference"] == made.refs[role].to_dict()
    original_descriptor = owner.descriptor()
    fresh = session_fixture(workspace)
    perform(fresh, "refresh")
    reopened = read(fresh, state["header"].header_sha256)
    assert reopened == before
    assert fresh.descriptor() == original_descriptor
    assert all(r["state"] == "PENDING" for r in fresh.view()["stages"][4:])
    assert session._decode_cached_source_workflow(canonical(reopened)) == reopened
