"""Fresh real NTFS public entry/export/reopen; hardware observations are modeled.

The full four-phase predecessor is constructed once in this new test directory.
No saved acceptance store is imported and no device/process provider runs. Source
identity in the isolated modeled workspace is fixed by the existing fixtures;
the executing repository build is recorded separately, never called hardware proof.
"""

from copy import deepcopy
import json
import os

import pytest

from rocell.application import physical_camera_mode_entry_service as entry
from rocell.application.physical_camera_mode_entry_projection import (
    mode_entry_projection_valid,
)
from rocell.application.physical_usb_identity_export import (
    restore_usb_identity_diagnostics,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.ui.terminal import _PhysicalSetupDisplay, _UsbQualificationDisplay
from test_arrival_usb_complete_ntfs_acceptance import (
    absence_arrival,
    nominal_arrival,
    actual_arrival,
    workspace,
    no_devices,
    make_service,
    matching_nominal_received_label,
    modeled_platform_name,
    restart_workspace_profiles,
    SOURCE,
    _public,
    _ticket,
    reopen_public,
    test_public_four_phase_assessment_review_export_and_fresh_reopen as establish_complete,
)


@pytest.mark.slow
@pytest.mark.skipif(
    os.name != "nt", reason="Fresh genuine NTFS original store required"
)
def test_public_entry_full_original_exports_and_fresh_reopen(
    absence_arrival, monkeypatch, tmp_path
):
    from pathlib import Path

    monkeypatch.setattr(entry, "source_fingerprint", lambda _: SOURCE)
    completed = []

    def successor(app, new_app, predecessor):
        setup = app._physical_camera_setup
        operations, exports = [], []
        values = dict(operator_id="Camera setup operator", file_only=True)
        try:
            before = app.view()
            assert before["camera_mode_entry"]["status"] == "READY_TO_ENTER"
            assert (
                _PhysicalSetupDisplay.setup(before["physical_camera_setup"]) is not None
            )
            assert mode_entry_projection_valid(
                before["camera_mode_entry"], before["physical_camera_setup"]
            )
            operation, ticket, elapsed = _public(app, entry.ACTION, values)
            operations.append(dict(operation=operation, ticket=ticket, seconds=elapsed))
            assert operation["completion_log_persisted"] is True
            assert operation["result"]["device_open_count"] == 0
            current = setup.original_source_workflow()
            assert (
                current["schema"]
                == "rocell.physical_camera_source_workflow_readback.v15"
            )
            assert current["camera_mode_entry"]["state"] == "ENTERED"
            # Compare all predecessor records, not just a list of selected hashes.
            assert {
                k: current[k]
                for k in predecessor
                if k
                not in {"schema", "session_head_sha256", "evidence_inventory_sha256"}
            } == {
                k: v
                for k, v in predecessor.items()
                if k
                not in {"schema", "session_head_sha256", "evidence_inventory_sha256"}
            }
            stages = setup.session.view()["stages"]
            assert [row["state"] for row in stages] == ["PASS"] * 4 + [
                "WAITING_OPERATOR"
            ] + ["PENDING"] * 10
            assert (
                app.execute_action(ticket["ticket_id"])["operation_id"]
                == operation["operation_id"]
            )
            with pytest.raises(WizardError):
                _ticket(app, entry.ACTION, values)
            for action, action_values in (
                ("physical_usb_identity_export", dict(confirm_metadata_export=True)),
                ("export_logs", {}),
            ):
                exported, _, seconds = _public(app, action, action_values)
                operations.append(dict(operation=exported, seconds=seconds))
                receipt = (
                    exported["result"]["receipt"]
                    if action == "export_logs"
                    else exported["result"]["steps"][0]["report"]["metadata_export"]
                )
                folder = Path(receipt["path"])
                exports.append(str(folder))
                assert (
                    folder.parent == app.export_directory
                    and verify_export(folder)["valid"]
                )
                if action == "export_logs":
                    saved = json.loads(
                        (folder / "attachment-camera-mode-entry.json").read_bytes()
                    )
                    assert saved["original_bytes_preserved"] is True
                    assert saved["original"] == current["camera_mode_entry"]
                    assert saved["attempt"] == setup._mode_entry_attempt
                else:
                    report = json.loads((folder / "report.json").read_bytes())[
                        "snapshot"
                    ]
                    restored = restore_usb_identity_diagnostics(
                        report,
                        {
                            part["attachment"]: (
                                folder / part["attachment"]
                            ).read_bytes()
                            for part in report["parts"]
                        },
                    )
                    assert (
                        restored["qualification_complete"]
                        == predecessor["usb_qualification_complete"]
                    )
            assert setup.original_source_workflow() == current
            fresh, runner = new_app("reopen-after-camera-mode-entry")
            assert reopen_public(fresh) == current
            view = fresh.view()
            assert (
                _PhysicalSetupDisplay.setup(view["physical_camera_setup"]) is not None
            )
            assert mode_entry_projection_valid(
                view["camera_mode_entry"], view["physical_camera_setup"]
            )
            assert view["camera_mode_entry"]["status"] == "ENTERED"
            assert (
                view["camera_mode_entry"]["attempted"] is False
            )  # Original, not a replay.
            _UsbQualificationDisplay._validate(view["usb_qualification"], view)
            assert view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED"
            assert view["physical_authority"] is False and not runner.calls
            with pytest.raises(WizardError):
                _ticket(fresh, entry.ACTION, values)
            assert setup.original_source_workflow() == current
            completed.append(digest(canonical(current)))
        finally:
            (tmp_path / "camera-entry-public-checkpoint.json").write_bytes(
                canonical(
                    dict(
                        original=setup.original_source_workflow(),
                        entry_diagnostics=setup.mode_entry_diagnostics(),
                        snapshot=app.view(),
                        operations=operations,
                        exports=exports,
                        completed=completed,
                        meaning="REAL_NTFS_LOGS_PUBLIC_TICKETS__MODELED_SOURCE_HARDWARE_PROCESS_FACTS",
                    )
                )
            )

    establish_complete(absence_arrival, monkeypatch, tmp_path, after_complete=successor)
    assert len(completed) == 1
