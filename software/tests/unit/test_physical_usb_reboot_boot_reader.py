"""Fixed boot-reader seam over a complete original-shaped, MODELED store.

The original codecs and shared Session reader are real. Leases, manifests,
campaign discovery and all hardware observations are modeled. No boot observer,
native process, USB, camera or arm access is allowed by this test.
"""

from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from rocell.application import physical_camera_session as session
from rocell.application import physical_usb_reboot_boot as collector_module
from test_physical_camera_usb_reboot_readback import (
    ready,
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    workspace,
    empty_campaigns,
    no_devices,
    reboot_subjects,
    reboot_boot,
)
import test_physical_camera_usb_reboot_readback as originals


NEW_LAUNCH = "wizard-" + "e" * 32


def test_fixed_reader_uses_existing_scope_and_preserves_original_binding(
    ready, monkeypatch
):
    monkeypatch.setattr(originals, "REBOOT_LAUNCH", NEW_LAUNCH)
    made = reboot_subjects(ready, monkeypatch)
    owner, _, state = ready
    bound = owner.descriptor()
    with state["store"].stage_transaction() as tx:
        # Model the actual session-directory shape and an already-held lease.
        # Do not replace the reader, subject verifiers or original byte checks.
        tx._session.directory = Path(bound["directory"]) / bound["session_id"]
        checks = []
        monkeypatch.setattr(tx, "_check_scope", lambda: checks.append("scope"))
        kwargs = dict(
            workspace=Path(bound["workspace"]),
            source_sha256=bound["source_sha256"],
            launch_session_id=NEW_LAUNCH,
            expected_header_sha256=state["header"].header_sha256,
            cancellation=Event(),
            deadline_ns=state["now"] + 180_000_000_000,
        )
        before, enters = tx.snapshot(), state["enters"]
        retained = dict(state["payloads"])
        snapshot, workflow, predecessor = session.read_usb_reboot_boot_originals(
            tx, **kwargs
        )
        assert snapshot == before == tx.snapshot()
        assert checks and state["enters"] == enters  # No nested transaction.
        assert state["payloads"] == retained  # Read-only, no head/role migration.
        assert workflow["binding"]["launch_id"] == bound["launch_id"]
        phase = workflow["usb_qualification_reboot"]
        assert phase["operator_event"]["document"]["launch_session_id"] == NEW_LAUNCH
        assert phase["state"] == "REVIEWED"
        assert predecessor["reconnect"].payload == made.predecessor["reconnect"].payload

        # A genuine full reader returns earlier source/design/receipt references,
        # unlike an isolated stage-4 collector fixture. Exercise the consumer's
        # inventory and exact-role joins before relying on long public acceptance.
        assert {ref.stage for ref in snapshot.evidence} == set(
            collector_module.STAGE_ORDER[:4]
        )
        assert collector_module._inventory(snapshot) == tuple(
            sorted(
                collector_module.canonical(ref.to_dict()) for ref in snapshot.evidence
            )
        )
        intent = collector_module.UsbRebootBootIntent(
            collector_module.canonical(phase["boot_request"]["document"])
        )
        preparation, previous_boot = collector_module._checked_originals(
            tx,
            intent,
            collector_module.qualification._reference(
                phase["boot_request"]["reference"]
            ),
            snapshot,
            workflow,
            predecessor,
        )
        assert preparation.sha256 == phase["preparation"]["evidence_sha256"]
        assert previous_boot.payload == predecessor["reconnect_sources"]["host_boot"]

        # These invalid contexts must fail before rereading any original payload.
        cancelled = Event()
        cancelled.set()
        for changes in (
            {"cancellation": cancelled},
            {"deadline_ns": True},
            {"deadline_ns": state["now"]},
            {"launch_session_id": "not-a-launch"},
            {"source_sha256": "f" * 64},
            {"expected_header_sha256": "f" * 64},
        ):
            reads = state["reads"]
            with pytest.raises(session.PhysicalCameraSessionError):
                session.read_usb_reboot_boot_originals(tx, **(kwargs | changes))
            assert state["reads"] == reads

        # An unchanged payload set does not excuse a changed journal head after
        # the full audit. Exercise the final same-snapshot check explicitly.
        real_snapshot, calls = tx.snapshot, []

        def changed_after_read():
            calls.append(None)
            value = real_snapshot()
            return (
                replace(value, head=replace(value.head, head_sha256="f" * 64))
                if len(calls) >= 3
                else value
            )

        with monkeypatch.context() as patch:
            patch.setattr(tx, "snapshot", changed_after_read)
            with pytest.raises(
                session.PhysicalCameraSessionError,
                match="CAMERA_SESSION_CHANGED_AFTER_AUDIT",
            ):
                session.read_usb_reboot_boot_originals(tx, **kwargs)

        reboot_boot(made, monkeypatch, kind="requested")
        with pytest.raises(session.PhysicalCameraSessionError):
            session.read_usb_reboot_boot_originals(tx, **kwargs)
        assert state["enters"] == enters
