"""Public v14 review acceptance: real NTFS/logs, modeled hardware observations.

Every run constructs its own entire original four-phase predecessor. Public
tickets, completion logs, current original readback, export and reopening are
real. No live host boot, USB query, camera, serial or robot process may execute.
The reboot fixture owns application cleanup even if the successor fails.
"""

from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from rocell.application import physical_usb_complete_service as complete
from rocell.application.physical_usb_identity_export import (
    EXPORT_V7_SCHEMA,
    restore_usb_identity_diagnostics,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.ui.terminal import _UsbQualificationDisplay
from test_arrival_usb_reboot_ntfs_acceptance import (
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
    arrival_module,
    new_reboot_app,
    reopen_public,
    _public,
    _ticket,
    test_public_reboot_all_actions_export_and_fresh_reopen as establish_reboot,
)


def test_fresh_launch_exposes_no_complete_review_or_hardware_authority(
    workspace, monkeypatch, tmp_path
):
    monkeypatch.setattr(arrival_module, "source_fingerprint", lambda _: SOURCE)
    app, runner = new_reboot_app(workspace, tmp_path, "complete-startup-smoke")
    try:
        view = app.view()
        actions = {row["action_id"]: row for row in view["actions"]}
        for action in complete.ACTIONS:
            assert not actions[action]["enabled"]
            assert actions[action]["timeout_s"] == 180
            assert all(
                field["default"] is False
                for field in actions[action]["fields"]
                if field["type"] == "checkbox"
            )
        decision = next(
            field
            for field in actions[complete.REVIEW]["fields"]
            if field["name"] == "decision"
        )
        assert decision["default"] == "REJECT"
        assert view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED"
        assert view["physical_authority"] is False
        assert not view["operations"] and not runner.calls
    finally:
        app.shutdown()


@pytest.mark.slow
@pytest.mark.skipif(os.name != "nt", reason="Real NTFS original/storage acceptance")
def test_public_four_phase_assessment_review_export_and_fresh_reopen(
    absence_arrival, monkeypatch, tmp_path, *, after_complete=None
):
    observed = []

    def successor(app, new_app, predecessor):
        owner, setup = app._usb_identity, app._physical_camera_setup
        operations, directories = [], []
        forms = (
            (
                complete.ASSESS,
                dict(confirm_file_assessment=True, confirm_identity_only=True),
                "REVIEW_PENDING",
            ),
            (
                complete.REVIEW,
                dict(
                    reviewer_id="Final independent reviewer",
                    decision="ACKNOWLEDGE_EXACT",
                    confirm_exact_assessment=True,
                    confirm_identity_only=True,
                ),
                "REVIEWED_PASS",
            ),
        )
        try:
            initial = app.view()["usb_qualification"]
            assert initial["schema"] == "rocell.wizard_usb_qualification.v6"
            assert (
                initial["next_action"] == complete.ASSESS
                and initial["complete"] is None
            )
            for action, values, expected in forms:
                if action == complete.REVIEW:
                    original = setup.original_source_workflow()
                    bad = dict(
                        values,
                        reviewer_id=original["usb_qualification_trial"]["plan"][
                            "document"
                        ]["operator_id"],
                    )
                    with pytest.raises(WizardError, match="distinct"):
                        _ticket(app, action, bad)
                    assert setup.original_source_workflow() == original
                operation, ticket, elapsed = _public(app, action, values)
                operations.append(
                    dict(
                        action_id=action,
                        seconds=elapsed,
                        operation=operation,
                        ticket=ticket,
                    )
                )
                assert operation["result"]["counter_coverage"] == "NO_DEVICE_IO"
                assert operation["result"]["device_open_count"] == 0
                report = operation["result"]["steps"][0]["report"]
                assert (
                    report["usb_query_attempted"] is False
                    and report["execution"] is None
                )
                assert report["qualification"]["publication"]["status"] == "PENDING"
                assert all(
                    report["qualification"][key] is None
                    for key in (
                        "plan",
                        "baseline",
                        "absence",
                        "reconnect",
                        "reboot",
                        "complete",
                    )
                )
                current = setup.original_source_workflow()
                assert current["schema"].endswith(".v14")
                assert current["usb_qualification_complete"]["state"] == expected
                for suffix in ("trial", "baseline", "absence", "reconnect", "reboot"):
                    key = "usb_qualification_" + suffix
                    assert current[key] == predecessor[key]
                view = app.view()
                _UsbQualificationDisplay._validate(view["usb_qualification"], view)
                assert view["usb_qualification"]["publication"]["status"] == "CURRENT"
                assert all(
                    view["usb_qualification"][key] is False
                    for key in (
                        "physical_authority",
                        "hardware_qualified",
                        "camera_capture_authorized",
                        "arm_access_authorized",
                    )
                )
                assert all(
                    row["state"] == "PENDING"
                    for row in setup.session.view()["stages"][4:]
                )
                if action == complete.REVIEW:
                    assessment_hash = current["usb_qualification_complete"][
                        "assessment"
                    ]["evidence_sha256"]
                    assert any(
                        assessment_hash in effect for effect in ticket["effects"]
                    )
                with pytest.raises(WizardError):
                    _ticket(app, action, values)

            final = setup.original_source_workflow()
            row = final["usb_qualification_complete"]
            assert len(row["events"]) == 3
            assert all(
                row[role]["retention"] == "M1_FULL_BYTES_READ_BACK"
                for role in ("series", "assessment", "review")
            )
            assert row["review"]["document"]["review_launch_id"] == app.session_id
            assert setup.session.view()["stages"][3]["state"] == "PASS"
            assert app.view()["usb_qualification"]["next_action"] == complete.EXPORT
            original_diagnostics = deepcopy(owner.retained_diagnostics())
            original_digest = digest(canonical(original_diagnostics))
            exported, _, _ = _public(
                app, complete.EXPORT, dict(confirm_metadata_export=True)
            )
            directory = Path(
                exported["result"]["steps"][0]["report"]["metadata_export"]["path"]
            )
            directories.append(str(directory))
            assert (
                directory.parent == app.export_directory
                and verify_export(directory)["valid"]
            )
            report = json.loads((directory / "report.json").read_bytes())["snapshot"]
            assert report["schema"] == EXPORT_V7_SCHEMA
            restored = restore_usb_identity_diagnostics(
                report,
                {
                    part["attachment"]: (directory / part["attachment"]).read_bytes()
                    for part in report["parts"]
                },
            )
            assert digest(canonical(restored)) == original_digest
            assert restored == original_diagnostics
            assert restored["qualification_complete"] == row
            assert (
                app._log.verify(app._log.directory)["status"]
                == "VERIFIED_DIAGNOSTIC_ONLY"
            )

            fresh, runner = new_app("reopen-after-complete-review")
            assert reopen_public(fresh) == final
            view = fresh.view()
            _UsbQualificationDisplay._validate(view["usb_qualification"], view)
            assert view["usb_qualification"]["complete"]["state"] == "REVIEWED_PASS"
            for action, values, _ in forms:
                with pytest.raises(WizardError):
                    _ticket(fresh, action, values)
            assert view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED"
            assert view["physical_authority"] is False and not runner.calls
            assert all(
                stage["state"] == "PENDING"
                for stage in fresh._physical_camera_setup.session.view()["stages"][4:]
            )
            observed.append(
                dict(
                    original_sha256=digest(canonical(final)),
                    diagnostics_sha256=original_digest,
                    export_directory=str(directory),
                )
            )
            if after_complete is not None:
                # A separately tested successor may use this freshly built
                # accepted original. Never seed a new run from a saved store.
                after_complete(app, new_app, final)
        finally:
            # Preserve the exact failed or passing state before fixture cleanup.
            # The path is new for this test; it is never an input to another run.
            (tmp_path / "complete-public-checkpoint.json").write_bytes(
                canonical(
                    dict(
                        original=setup.original_source_workflow(),
                        diagnostics=owner.retained_diagnostics(),
                        snapshot=app.view(),
                        operations=operations,
                        exports=directories,
                        observations=observed,
                        meaning="REAL_NTFS_LOGS_PUBLIC_TICKETS__MODELED_HARDWARE_ONLY",
                    )
                )
            )

    establish_reboot(absence_arrival, monkeypatch, tmp_path, after_reboot=successor)
    assert len(observed) == 1
