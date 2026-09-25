"""Public file-only USB trial declaration on a real original NTFS session.

The inherited source/isolation/received-unit/identity facts are explicitly
MODELED. M1 files, journals, leases, service clocks, public tickets, completion
logs, exports and fresh readback are real. No camera, USB, CIM, serial or child
process is permitted; no trial phase or physical qualification is collected.
"""

from copy import deepcopy
import json
import os
from pathlib import Path
import time

import pytest

from rocell.application.physical_camera_usb_qualification import UsbQualificationPlan
from rocell.application.physical_onboarding import (
    STAGE_ORDER,
    _parse_evidence_reference,
)
from rocell.application.physical_usb_identity_export import (
    restore_usb_identity_diagnostics,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.ui.terminal import _UsbQualificationDisplay

from test_arrival_usb_identity_composed import (
    usb_arrival,
    workspace,
    no_devices,
    make_service,
    _complete,
    _run,
)
from test_arrival_wizard_service import _ticket
from test_physical_camera_identity_service_ntfs import (
    adopt_actual_original,
    read_original,
)
from test_physical_camera_session import session_fixture, perform


VALUES = dict(
    operator_id="file-only-trial-operator",
    cable_label="MODELED original cable alpha",
    port_label="MODELED original rear port",
    confirm_file_only=True,
)


def _exported_original(directory):
    assert verify_export(directory)["valid"]
    snapshot = json.loads((directory / "report.json").read_bytes())["snapshot"]
    restored = restore_usb_identity_diagnostics(
        snapshot,
        {
            row["attachment"]: (directory / row["attachment"]).read_bytes()
            for row in snapshot["parts"]
        },
    )
    assert snapshot["original_bytes_preserved"] is True
    return snapshot, restored


@pytest.mark.skipif(os.name != "nt", reason="Actual original NTFS and leases required")
@pytest.mark.parametrize("usb_arrival", ["no-query-permitted"], indirect=True)
def test_actual_public_trial_declaration_export_and_fresh_original_reopen(
    usb_arrival, monkeypatch
):
    case = usb_arrival
    arrival, owner, module = case.arrival, case.owner, case.module
    prefix = deepcopy(case.setup.original_source_workflow())
    assert prefix["schema"] == "rocell.physical_camera_source_workflow_readback.v7"
    assert prefix["configuration_epochs"] is not None
    assert not case.calls and not case.runner.calls
    assert owner.qualification_view()["next_action"] == module.DECLARE

    def forbidden(*args, **kwargs):
        pytest.fail(
            "file-only trial declaration reached a USB campaign or native runner"
        )

    # Fail before even the modeled runner can execute. The shared no_devices
    # fixture independently forbids every process and camera-worker entrypoint.
    from rocell.application.physical_usb_identity_dispatch import (
        PhysicalUsbIdentityDispatchOwner,
    )
    from rocell.providers.windows import owned_usb_identity_runner as runner

    monkeypatch.setattr(PhysicalUsbIdentityDispatchOwner, "perform", forbidden)
    monkeypatch.setattr(runner.OwnedUsbIdentityRunner, "run", forbidden)

    # Preview/confirmation is cached: it cannot open an original transaction.
    with monkeypatch.context() as inert:
        inert.setattr(case.session, "stage_transaction", forbidden)
        ticket = _ticket(arrival, module.DECLARE, VALUES)
    assert "no usb" in " ".join(ticket["effects"]).lower()
    assert owner.qualification_view()["plan"] is None
    pending_seen = []
    original_perform = owner.perform

    def pending_before_completion(*args, **kwargs):
        result = original_perform(*args, **kwargs)
        if args[0] == module.DECLARE:
            assert owner.qualification_view()["publication"]["status"] == "PENDING"
            assert owner.qualification_view()["plan"] is None
            assert arrival.view()["usb_qualification"]["plan"] is None
            pending_seen.append(True)
        return result

    monkeypatch.setattr(owner, "perform", pending_before_completion)
    started = time.monotonic()
    queued = arrival.execute_action(ticket["ticket_id"])
    operation = _complete(arrival, queued["operation_id"])
    elapsed = time.monotonic() - started
    assert operation["status"] == "SUCCEEDED", json.dumps(operation, indent=2)
    assert 0 < elapsed < 120
    assert pending_seen == [True]
    assert operation["completion_log_persisted"] is True
    assert operation["result_retention"] == "FULL_JSON_RETAINED"
    result = operation["result"]
    assert result["counter_coverage"] == "NO_DEVICE_IO"
    assert result["schema"] == module.RESULT_SCHEMA
    assert result["hardware_qualified"] is False
    assert result["physical_authority"] is False
    for field in (
        "device_open_count",
        "serial_write_count",
        "power_event_count",
        "motion_command_count",
        "contact_command_count",
    ):
        assert result[field] == 0
    events = arrival._log.events()
    completed = [
        row
        for row in events
        if row["kind"] == "ACTION_FINISHED"
        and row["details"]["operation_id"] == operation["operation_id"]
    ]
    assert len(completed) == 1
    assert completed[0]["details"]["result_sha256"] == operation["result_sha256"]
    assert (
        arrival._log.verify(arrival._log.directory)["status"]
        == "VERIFIED_DIAGNOSTIC_ONLY"
    )

    current = case.setup.original_source_workflow()
    assert current["schema"] == "rocell.physical_camera_source_workflow_readback.v9"
    trial = current["usb_qualification_trial"]
    assert trial["state"] == "PLAN_DECLARED"
    plan = UsbQualificationPlan(canonical(trial["plan"]["document"]))
    assert plan.sha256 == trial["plan"]["evidence_sha256"]
    assert trial["plan"]["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert (
        trial["request_event"]["occurred_at_ns"]
        <= plan.to_dict()["created_at_utc_ns"]
        <= trial["declaration_event"]["occurred_at_ns"]
    )
    for key in (
        "prerequisites",
        "configuration_epochs",
        "qualification_cycles",
        "static_contract",
        "received_camera_cycles",
        "camera_identity_cycles",
    ):
        assert current[key] == prefix[key]
    assert "usb_baseline" not in current
    snapshot = arrival.view()
    card = snapshot["usb_qualification"]
    assert _UsbQualificationDisplay.validate(card, snapshot) == card
    assert card["status"] == "DECLARED" and card["next_action"] == module.BEGIN
    assert card["publication"]["status"] == "CURRENT"
    assert card["plan"]["plan_sha256"] == plan.sha256
    assert snapshot["usb_identity"]["status"] == "HISTORICAL_HELD"
    assert all(row["state"] == "PENDING" for row in case.session.view()["stages"][4:])

    # A duplicate execute returns the same operation; fresh declaration is held.
    assert (
        arrival.execute_action(ticket["ticket_id"])["operation_id"]
        == operation["operation_id"]
    )
    assert pending_seen == [True]
    with pytest.raises(WizardError):
        _ticket(arrival, module.DECLARE, VALUES)

    exported, _ = _run(arrival, module.EXPORT, {"confirm_metadata_export": True})
    directory = Path(
        exported["result"]["steps"][0]["report"]["metadata_export"]["path"]
    )
    assert directory.parent == arrival.export_directory
    export_snapshot, restored = _exported_original(directory)
    assert restored["qualification_trial"] == trial
    assert (
        canonical(restored["qualification_trial"]["plan"]["document"]) == plan.payload
    )
    general, _ = _run(arrival, "export_logs", {})
    general_directory = Path(general["result"]["receipt"]["path"])
    assert verify_export(general_directory)["valid"]
    general_report = json.loads((general_directory / "report.json").read_bytes())
    assert (
        general_report["snapshot"]["usb_qualification"]["plan"]["plan_sha256"]
        == plan.sha256
    )
    assert len(list(general_directory.glob("attachment-*"))) <= 8

    # New original owner, real leases and raw bytes: no service-cache adoption
    # stands in for reopening, and no historical action is replayed.
    fresh = session_fixture(case.workspace)
    perform(fresh, "refresh")
    reopened = read_original(fresh, current["session_header_sha256"])
    assert reopened == current
    with fresh.stage_transaction(
        expected_challenge_sha256=fresh.view()["verification"]["challenge_sha256"]
    ) as tx:
        before = tx.snapshot()
        assert (
            tx.read_stage_evidence(
                _parse_evidence_reference(trial["plan"]["reference"])
            )
            == plan.payload
        )
        assert len([ref for ref in before.evidence if ref.stage is STAGE_ORDER[3]]) == 6
        assert tx.snapshot().head == before.head
    # Opening even a read-only raw stage scope withdraws the cached admission
    # view. Re-audit before a new service binds that session; never bypass it.
    perform(fresh, "refresh")
    assert read_original(fresh, current["session_header_sha256"]) == reopened
    fresh_identity, fresh_acquisition = adopt_actual_original(
        fresh, reopened, launch_id="wizard-" + "9" * 32
    )
    fresh_owner = module.PhysicalUsbIdentityService(fresh_identity.setup)
    fresh_owner.observe_setup()
    fresh_card = fresh_owner.qualification_view()
    assert fresh_card["plan"] == card["plan"]
    assert fresh_card["launch_session_id"] != card["launch_session_id"]
    assert fresh_owner.blocked_reason(module.DECLARE) is not None
    assert fresh_owner.retained_diagnostics()["qualification_trial"] == trial
    assert fresh_acquisition.view()["reviewed_endpoint"] is None
    assert all(row["state"] == "PENDING" for row in fresh.view()["stages"][4:])
    assert not case.calls and not case.runner.calls
    print(
        json.dumps(
            dict(
                public_declaration_seconds=round(elapsed, 3),
                operation_id=operation["operation_id"],
                original_directory=case.session.descriptor()["directory"],
                session_id=case.session.descriptor()["session_id"],
                original_header_sha256=current["session_header_sha256"],
                original_head_sha256=current["session_head_sha256"],
                trial_id=trial["trial_id"],
                plan_sha256=plan.sha256,
                dedicated_export=str(directory),
                dedicated_manifest_sha256=digest(
                    (directory / "manifest.json").read_bytes()
                ),
                generic_export=str(general_directory),
                generic_manifest_sha256=digest(
                    (general_directory / "manifest.json").read_bytes()
                ),
                earlier_hardware_facts="EXPLICITLY_MODELED",
                hardware_or_phase_collection_performed=False,
            ),
            indent=2,
        )
    )
