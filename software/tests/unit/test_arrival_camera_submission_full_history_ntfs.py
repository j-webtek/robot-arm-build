"""Complete original history and public operating submission, no physical I/O.

The inherited history models received/USB/boot observations and fixture source
identity. Only the camera process edge and its synthetic observations/pixels are
replaced here. Original readers, runtime-file checks, admission, clocks, quotas,
stage writes, logs, export and restart adoption all run unchanged. Passing this
test is software composition evidence, never physical camera qualification.
"""

from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
from threading import Event
from time import monotonic

import pytest

from rocell.application import camera_operating_submission_service as submission_service
from rocell.application.camera_operating_proposal_wizard import ACTION as PROPOSAL
from rocell.application.camera_operating_submission import CameraOperatingSubmission
from rocell.application.camera_operating_submission_wizard import ACTION as SUBMIT
from rocell.application.camera_operating_submission_projection import (
    validate_submission_projection,
)
from rocell.application.wizard_actions import ACTION_BY_ID, WizardError
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.camera_worker_client import NativeCameraMode
from rocell.providers.windows.native_camera_protocol import canonical

import test_arrival_camera_full_history_ntfs as history
from test_arrival_camera_full_history_ntfs import (
    absence_arrival,
    nominal_arrival,
    actual_arrival,
    workspace,
    no_devices,
    make_service,
    matching_nominal_received_label,
    modeled_platform_name,
    restart_workspace_profiles,
    copied_camera_runtime,
    no_physical_owner,
)
from test_arrival_wizard_service import _ticket

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Actual Windows NTFS required")
FRAME_BYTES = 5472 * 3648 * 2
MODE = NativeCameraMode(5472, 3648, 8, 1, stride_bytes=10944)


def install_full_size_peer(monkeypatch):
    """Independent fixed observations, not a mirror of requested capabilities."""
    original_packet = history.native_packet

    def packet(request, purpose, metadata):
        ready, raw = original_packet(request, purpose, metadata)
        receipt = raw["native_receipt"]
        receipt["modes"] = [asdict(MODE)]
        if purpose == "capture":
            receipt["observed_mode"] = asdict(MODE)
            receipt["frames"][0].update(length_bytes=FRAME_BYTES, stride_bytes=10944)
        return ready, raw

    monkeypatch.setattr(history, "native_packet", packet)
    monkeypatch.setattr(history, "PIXELS", b"\x40\x80\x80\x80" * (FRAME_BYTES // 4))
    # As in the inherited fixture, only this partial workspace's source identity
    # is modeled. The separate executing-source audit uses the real checker.
    monkeypatch.setattr(
        submission_service, "source_fingerprint", lambda _: history.SOURCE
    )


def public_action(app, action, values, observations):
    """Wait for the same public operation, never retry or extend its deadline.

    The older history helper waits 210 seconds for 180-second actions. This
    action has an existing 300-second budget, so the test waiter derives its
    ceiling from the production definition plus 30 seconds for terminal cleanup.
    It does not change any production deadline or native minimum lifetime.
    """
    ticket = _ticket(app, action, values)
    started = monotonic()
    queued = app.execute_action(ticket["ticket_id"])
    deadline = started + ACTION_BY_ID[action].timeout_s + 30
    operation = None
    try:
        while monotonic() < deadline:
            operation = app.operation(queued["operation_id"])
            if operation["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
                break
            Event().wait(0.02)
        assert operation is not None and operation["status"] == "SUCCEEDED", json.dumps(
            operation, indent=2
        )
        assert operation["completion_log_persisted"] is True
        assert operation["result_retention"] == "FULL_JSON_RETAINED"
        assert (
            app.execute_action(ticket["ticket_id"])["operation_id"]
            == operation["operation_id"]
        )
        return operation
    finally:
        observations.append(
            dict(
                action_id=action,
                ticket=ticket,
                operation=operation,
                seconds=round(monotonic() - started, 3),
            )
        )


def exported_submission(app, observations):
    """Reconstruct exact compound bytes from the real bounded general export."""
    expected = app._operating_submission.packet()
    before = {p for p in app.export_directory.iterdir() if p.is_dir()}
    public_action(app, "export_logs", {}, observations)
    created = {p for p in app.export_directory.iterdir() if p.is_dir()} - before
    assert len(created) == 1
    folder = created.pop()
    assert folder.parent == app.export_directory and verify_export(folder)["valid"]
    wrapper = json.loads(
        (folder / "attachment-camera-operating-submissions.json").read_bytes()
    )
    assert wrapper["original_bytes_preserved"] is True
    packet = wrapper["diagnostics"]
    assert packet == expected
    original = deepcopy(packet["original_readback"])
    record = original["submission"]
    sha = record.pop("document_sha256")
    subject = CameraOperatingSubmission(canonical(packet["documents"][sha]))
    assert subject.sha256 == sha == record["evidence_sha256"]
    record["document"] = subject.to_dict()
    assert (
        original
        == app._physical_camera_setup.original_source_workflow()[
            "camera_operating_submission"
        ]
    )
    assert (
        not packet["physical_authority"] and not packet["current_connection_restored"]
    )
    return str(folder)


def test_full_size_peer_preserves_independent_mode_observations(monkeypatch):
    """Catch an incorrect test peer before constructing the long history."""
    install_full_size_peer(monkeypatch)
    request = history.result_fixture("capture")[0]
    requested = json.loads(request.to_dict()["capture_json"])
    _, raw = history.native_packet(request, "capture", history.driver_fixture())
    receipt = raw["native_receipt"]
    assert receipt["observed_mode"] == asdict(MODE)
    assert receipt["modes"] == [asdict(MODE)]
    assert receipt["requested_mode"]["width"] == requested["width"]
    assert receipt["requested_mode"] != receipt["observed_mode"]
    assert receipt["frames"][0]["length_bytes"] == len(history.PIXELS) == FRAME_BYTES
    assert receipt["frames"][0]["stride_bytes"] == 10944
    assert ACTION_BY_ID[SUBMIT].timeout_s == 300


@pytest.mark.slow
def test_full_original_history_public_submission_reopen_and_export(
    absence_arrival, monkeypatch, tmp_path, copied_camera_runtime, record_property
):
    install_full_size_peer(monkeypatch)
    executing_source = source_fingerprint(history.ROOT)
    completed, source_audit = [], None

    def successor(previous_app, new_app, predecessor):
        nonlocal source_audit
        history._public(
            previous_app,
            history.mode_entry.ACTION,
            dict(operator_id="MODELED entry operator", file_only=True),
        )
        entered = previous_app._physical_camera_setup.original_source_workflow()
        app, runner = new_app("operating-full-history")
        setup = app._physical_camera_setup
        operations, exports, owners, owner_groups = [], [], [], []
        reopened = None
        timings = history.CameraAdmissionTimingTrace(max_entries=4096)

        def act(action, values):
            with timings.instrument(history.camera_timing_targets()), timings.action(
                action
            ):
                return public_action(app, action, values, operations)

        try:
            history.require_disconnected_camera_restart(app.view())
            assert history.reopen_public(app) == entered
            history.enroll_public(app, runner, monkeypatch)
            act("physical_camera_refresh", dict(operator_id=history.REFRESH_OPERATOR))
            for action in (history.probe_setup.PREPARE, history.probe_setup.REVIEW):
                act(action, dict(operator_id="MODELED probe reviewer", file_only=True))
            reviewed = setup.original_source_workflow()
            for key in predecessor:
                if key not in {
                    "schema",
                    "session_head_sha256",
                    "evidence_inventory_sha256",
                }:
                    assert reviewed[key] == predecessor[key], key

            probe_owners = history.install_incapable_owner(
                tmp_path, monkeypatch, app._native_camera, purpose="probe"
            )
            # The list is populated during dispatch, including failed dispatch.
            # Register it now so failure diagnostics cannot report zero owners
            # merely because execution raised before the success-only extend.
            owner_groups.append(probe_owners)
            act(
                "physical_camera_probe",
                dict(
                    operator_id="MODELED probe operator",
                    arm_actuator_supply_disconnected=True,
                    bounded_probe_consent=True,
                ),
            )
            owners.extend(probe_owners)
            assert len(probe_owners) == 1 and probe_owners[0].cleaned
            original_probe = deepcopy(app._probe_attempt_packet())

            fields = app._physical_camera.configuration_fields()
            mode_field = next(f for f in fields if f["name"] == "mode_choice_id")
            assert len(mode_field["options"]) == 1
            settings = {f["name"]: f["default"] for f in fields if "default" in f}
            settings.update(
                mode_choice_id=mode_field["options"][0]["value"],
                operator_id=history.SETTINGS_OPERATOR,
            )
            act("physical_camera_configuration", settings)
            captures = []
            for _ in range(2):
                capture_owners = history.install_incapable_owner(
                    tmp_path, monkeypatch, app._native_camera, purpose="capture"
                )
                owner_groups.append(capture_owners)
                captured = act(
                    history.CAPTURE_ACTION_ID,
                    dict(
                        operator_id="MODELED capture operator",
                        arm_actuator_supply_disconnected=True,
                        bounded_configuration_capture_consent=True,
                    ),
                )
                captures.append(captured["operation_id"])
                owners.extend(capture_owners)
                assert len(capture_owners) == 1 and capture_owners[0].cleaned
                assert app.image(app.view()["camera"]["image_id"])[0].startswith(
                    b"\x89PNG"
                )
                exported = act(
                    history.EXPORT_ACTION_ID,
                    dict(attempt_choice_id=captured["operation_id"]),
                )
                folder = Path(
                    exported["result"]["steps"][0]["report"]["receipt"]["path"]
                )
                exports.append(str(folder))
                assert verify_export(folder)["valid"]
                snapshot = json.loads((folder / "report.json").read_bytes())["snapshot"]
                parts = {
                    part.name.removeprefix("attachment-"): part.read_bytes()
                    for part in folder.glob("attachment-*.json")
                }
                assert history.restore_configuration_attempt_export(
                    snapshot, parts
                ) == app._configuration_wizard.packet(captured["operation_id"])
            assert len(set(captures)) == 2
            act(
                PROPOSAL,
                dict(
                    operator_id="MODELED proposal operator",
                    rationale="Assess two explicitly selected full-size captures.",
                    variance_rationale="Evaluate observed 8 fps without changing the 9-fps reference.",
                ),
            )
            values = dict(
                operator_id="MODELED submission operator",
                capture_1=captures[0],
                capture_2=captures[1],
                save_for_review=True,
            )
            submitted = act(SUBMIT, values)
            record_property("submission_public_seconds", operations[-1]["seconds"])
            assert submitted["result"]["device_open_count"] == 0
            original = setup.original_source_workflow()
            row = original["camera_operating_submission"]
            assert original["schema"].endswith(".v17")
            assert row["state"] == "SUBMITTED_REVIEW_REQUIRED"
            assert row["original_stage_authenticated"] and not row["stage_passed"]
            assert [
                r["request_key"]
                for r in row["submission"]["document"]["assessment"]["captures"]
            ] == captures
            assert [s["state"] for s in setup.session.view()["stages"]] == [
                "PASS"
            ] * 4 + ["REVIEW_PENDING"] + ["PENDING"] * 10
            view = app.view()
            assert (
                validate_submission_projection(
                    view["camera_operating_submission"],
                    source_sha256=view["source_binding_sha256"],
                    launch_session_id=app.session_id,
                )
                == view["camera_operating_submission"]
            )
            assert (
                view["camera_operating_submission"]["publication"]["status"]
                == "CURRENT"
            )
            assert (
                not view["physical_authority"]
                and view["arm"]["status"] == "NOT_CONNECTED"
            )
            assert app._probe_attempt_packet() == original_probe
            assert len(owners) == 3 and all(owner.cleaned for owner in owners)
            assert all(call[0] == "inventory_devices" for call in runner.calls)
            exports.append(exported_submission(app, operations))
            with pytest.raises(WizardError):
                _ticket(app, SUBMIT, values)

            original_directory = setup.session.descriptor()["directory"]
            app.shutdown()
            restarted, restarted_runner = new_app("operating-submission-reopen")
            history.require_disconnected_camera_restart(restarted.view())
            reopened = history.reopen_public(restarted)
            assert reopened == original and restarted.session_id != app.session_id
            assert (
                restarted._physical_camera_setup.session.descriptor()["directory"]
                == original_directory
            )
            history.require_disconnected_camera_restart(restarted.view())
            assert restarted._operating_submission.packet()["attempts"] == []
            assert (
                not restarted._probe_metadata_current()
                and restarted._probe_attempt_packet() is None
            )
            fresh_view = restarted.view()
            assert (
                validate_submission_projection(
                    fresh_view["camera_operating_submission"],
                    source_sha256=fresh_view["source_binding_sha256"],
                    launch_session_id=restarted.session_id,
                )
                == fresh_view["camera_operating_submission"]
            )
            assert fresh_view["camera_operating_submission"][
                "original_stage_authenticated"
            ]
            with pytest.raises(WizardError):
                _ticket(restarted, SUBMIT, values)
            exports.append(exported_submission(restarted, operations))
            assert not restarted_runner.calls and len(owners) == 3
            assert restarted._physical_camera_setup.session.view()["verification"][
                "leases"
            ] == dict(active_or_stale_owners=[], reconciliation_required=False)
            assert (
                restarted._log.verify(restarted._log.directory)["status"]
                == "VERIFIED_DIAGNOSTIC_ONLY"
            )
            completed.append(submitted["operation_id"])
        finally:
            source_audit = history.observe_executing_source(
                history.ROOT, executing_source
            )
            (tmp_path / "camera-submission-full-history-checkpoint.json").write_bytes(
                canonical(
                    dict(
                        executing_source_audit=source_audit,
                        original=setup.original_source_workflow(),
                        snapshot=app.view(),
                        operations=operations,
                        exports=exports,
                        reopened=reopened,
                        completed=completed,
                        copied_native_sha256=copied_camera_runtime,
                        owner_count=sum(len(group) for group in owner_groups),
                        owner_observations=[
                            dict(
                                created=owner.created,
                                resumed=owner.resumed,
                                cleaned=owner.cleaned,
                            )
                            for group in owner_groups
                            for owner in group
                        ],
                        retained_probe_attempt=app._probe_attempt_packet(),
                        admission_timing_trace=timings.snapshot(),
                        meaning="REAL_FULL_ORIGINAL_HISTORY_PUBLIC_SUBMISSION_REOPEN_EXPORT__MODELED_SOURCE_HARDWARE_PROCESS",
                        physical_authority=False,
                        hardware_qualified=False,
                    )
                )
            )

    history.establish_complete(
        absence_arrival, monkeypatch, tmp_path, after_complete=successor
    )
    assert len(completed) == 1
    history.require_unchanged_execution_source(source_audit)
