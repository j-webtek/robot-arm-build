"""Real full original history and public camera workflow; hardware is MODELED.

No original-reader/facts/capacity/clock or runtime-verifier replacement results
occur here: test-only timing wrappers always delegate the unchanged actual call.
The inherited fixture models the isolated workspace source identity and
received/USB/boot observations. Native process ownership is incapable; this is
not physical qualification or a claim that early fixture-only stages use the UI.
"""

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
from threading import Event
from time import monotonic_ns
from types import SimpleNamespace

import pytest

from rocell.application import camera_activation_runtime_policy as runtime_policy
from rocell.application import camera_probe_original_scope as probe_scope
from rocell.application import camera_probe_admission as probe_admission
from rocell.application import camera_probe_setup_service as probe_setup
from rocell.application import physical_camera_activation_campaign as campaign
from rocell.application import physical_camera_dispatch as dispatch
from rocell.application import physical_camera_mode_entry_service as mode_entry
from rocell.application import physical_camera_capture_workflow as capture_workflow
from rocell.application.camera_activation_expectation import expectation_from_enrollment
from rocell.application.camera_configuration_wizard_contract import (
    CAPTURE_ACTION_ID,
    EXPORT_ACTION_ID,
)
from rocell.application.camera_configuration_attempt_export import (
    restore_configuration_attempt_export,
)
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraTransaction,
)
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_actions import (
    ACTION_BY_ID,
    WizardError,
    portable_setup_operator_valid,
    validate_action_input,
)
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows import native_camera_activation_supervisor as supervisor
from rocell.providers.windows.native_camera_parent_admission import (
    NativeCameraParentHandshake,
)
from rocell.providers.windows.native_camera_activation_protocol import (
    NativeCameraActivationRequest,
    parse_owned_activation_result,
)
from rocell.providers.windows.native_camera_activation_registration import (
    build_record_relative_path,
    helper_relative_path,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
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
    reopen_public,
    test_public_four_phase_assessment_review_export_and_fresh_reopen as establish_complete,
)
from test_arrival_usb_reconnect_ntfs_acceptance import fresh_public_metadata
from test_camera_activation_application_handoff import PIXELS
from test_native_camera_activation_evidence import modeled
from test_native_camera_activation_protocol import fixture as result_fixture, ready_for
from test_native_camera_activation_supervisor import ModelOwner, no_physical_owner
from test_physical_camera_identity_readback import identity_inputs
from test_windows_camera_driver_metadata import driver_fixture
from camera_admission_timing_trace import CameraAdmissionTimingTrace

ROOT = Path(__file__).resolve().parents[3]
REFRESH_OPERATOR = "MODELED-refresh-operator"
SETTINGS_OPERATOR = "MODELED-settings-operator"
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Genuine Windows NTFS required")


def observe_executing_source(workspace: Path, expected: str) -> dict[str, str | None]:
    """Audit the actual checkout, separately from the modeled fixture identity.

    Retain unreadable-source failures as data in the terminal checkpoint so a
    secondary audit error cannot mask an earlier workflow failure. A successful
    workflow must separately require MATCH before the test can pass.
    """
    try:
        observed = source_fingerprint(workspace)
    except Exception as error:
        return dict(
            expected=expected,
            observed=None,
            status="SOURCE_AUDIT_ERROR",
            error_type=type(error).__name__,
        )
    return dict(
        expected=expected,
        observed=observed,
        status="MATCH" if observed == expected else "SOURCE_CHANGED",
        error_type=None,
    )


def require_unchanged_execution_source(audit: dict[str, str | None] | None) -> None:
    assert (
        audit is not None
        and audit["status"] == "MATCH"
        and audit["observed"] == audit["expected"]
        and audit["error_type"] is None
    ), f"Fixed-source acceptance requires an unchanged readable checkout: {audit}"


def require_disconnected_camera_restart(view: dict) -> None:
    """Check a new launch without interpreting saved pixels as a connection."""
    assert view["physical_authority"] is False
    assert view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED"
    assert view["camera"]["image_id"] is None
    assert view["physical_camera"]["connected"] is False
    card = view["camera_configuration_attempt"]
    assert card["settings_reference_retained"] is False
    assert card["export_available"] is False and card["attempts"] == []


def camera_timing_targets():
    """Exact production method/import aliases, never alternative implementations."""
    return (
        *(
            (M1PhysicalCameraTransaction, name, "M1PhysicalCameraTransaction." + name)
            for name in (
                "snapshot",
                "_audit_records",
                "_admission_observation",
                "_fresh_admission",
                "revalidate_consumed_permit",
            )
        ),
        *(
            (PhysicalOnboardingM1Runtime, name, "M1Runtime." + name)
            for name in (
                "_verify_with_snapshot",
                "_global_snapshots",
                "_open_session_with_snapshot",
            )
        ),
        *(
            (NativeCameraParentHandshake, name, "NativeCameraParentHandshake." + name)
            for name in ("begin", "check_release", "_current_permit")
        ),
        (
            probe_admission,
            "_capacity_from_current_records",
            "camera_probe.capacity_from_current_records",
        ),
        *(
            (
                probe_scope.VerifiedCameraProbeOriginal,
                name,
                "VerifiedCameraProbeOriginal." + name,
            )
            for name in ("_read_current_records", "_check_context")
        ),
        (
            campaign,
            "verify_reviewed_activation_runtime",
            "camera_activation.verify_reviewed_activation_runtime",
        ),
    )


@pytest.fixture(autouse=True)
def copied_camera_runtime(workspace, monkeypatch):
    """Copy the closed file roster before original retention, without overwrites."""
    names = {runtime_policy._NATIVE_PREFIX + n for n in runtime_policy._NATIVE_INPUTS}
    for purpose in ("probe", "capture"):
        names.update(
            (build_record_relative_path(purpose), helper_relative_path(purpose))
        )
    hashes = {}
    for relative in sorted(names):
        source, destination = ROOT / relative, workspace / relative
        assert destination.is_relative_to(workspace)
        assert not destination.exists(), relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        hashes[relative] = digest(source.read_bytes())
        assert digest(destination.read_bytes()) == hashes[relative]
    model_isolated_camera_source(monkeypatch)
    return hashes


def model_isolated_camera_source(monkeypatch):
    """Model only source identity for this intentionally partial test workspace.

    Each production caller still invokes its source check. This does not patch
    the shared checker, fixed-file pinning, readback, admission or clock logic.
    Keep the capture-ingestion check in the roster: it is reached after the
    native campaign, so an omission otherwise wastes the entire slow history.
    """

    for module in (
        runtime_policy,
        probe_scope,
        probe_setup,
        campaign,
        dispatch,
        mode_entry,
        capture_workflow,
    ):
        monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)


def enroll_public(app, runner, monkeypatch):
    app._camera_helper = identity_inputs(
        source=SOURCE, launch=app.session_id, return_owners=True
    )["helper"]
    operations = fresh_public_metadata(
        SimpleNamespace(arrival=app, runner=runner),
        monkeypatch,
        identity_receipt_factory=complete_metadata_peer,
    )
    assert app._probe_metadata_current()
    assert len(app._probe_metadata_publication["operations"]) == 4
    return operations


def complete_metadata_peer(previous):
    """New capable-shaped observations for the same synthetic USB peer.

    The USB-only peer omits a complete parent walk. This fresh activation peer
    models a complete walk, preserving independently observed unit/driver facts.
    It is chosen before collection, not used to amend an existing record.
    """
    fresh = driver_fixture()
    fresh["requested_endpoint"] = previous["requested_endpoint"]
    fresh["mapping"]["interface_path"] = previous["mapping"]["interface_path"]
    fresh["device"] = deepcopy(previous["device"])
    if previous.get("driver") is not None:
        for key in ("provider", "service", "version", "inf_path"):
            if previous["driver"][key]["availability"] == "OBSERVED":
                fresh["driver"][key] = deepcopy(previous["driver"][key])
    return fresh


def native_packet(request, purpose, observed_metadata):
    """Fresh synthetic observations, independent of the request's expected facts.

    Metadata comes from the separately collected incapable peer. Only protocol
    correlation hashes use the actual new request. Production comparison still
    rejects any changed endpoint/device/driver in those independent observations.
    """
    ready = ready_for(request)
    fields = request.to_dict()
    _, _, raw = result_fixture(purpose)
    raw.update(
        request_sha256=request.request_sha256, permit_sha256=fields["permit_sha256"]
    )
    observation = raw["activation_identity"]
    observation.update(
        expected_identity_sha256=request.expectation.sha256,
        original_identity_sha256=request.expectation.to_dict()[
            "original_identity_sha256"
        ],
        metadata=deepcopy(observed_metadata),
    )
    observation["metadata"]["limits"].update(duration_ms=4500, max_parent_nodes=16)
    receipt = raw["native_receipt"]
    observed_endpoint = observed_metadata["requested_endpoint"]
    receipt["selected_endpoint"] = receipt["devices"][0]["symbolic_link"] = (
        observed_endpoint
    )
    if purpose == "capture":
        settings = json.loads(fields["capture_json"])
        assert settings["controls"] == ""
        receipt["requested_mode"] = {
            k: settings[k]
            for k in ("width", "height", "fps_numerator", "fps_denominator", "subtype")
        }
        receipt["requested_mode"]["stride_bytes"] = int(
            settings["requested_stride_bytes"]
        )
        receipt["frames"][0]["media_timestamp_100ns"] = 0
    return ready, raw


def install_incapable_owner(directory, monkeypatch, enrollment, *, purpose):
    """Replace only the process edge; never replace software approval or dispatch."""
    observations = deepcopy(enrollment.export_snapshot()["identity_packet"]["receipt"])
    owners = []

    def new_owner():
        base, args = modeled(directory, purpose)
        owner = ModelOwner(base, args)
        start, send = owner.start, owner.send_final_input
        capture_directory = None

        def bound_start(registration, wire, *, check, keep_stdin_open):
            nonlocal capture_directory
            request = NativeCameraActivationRequest(canonical(json.loads(wire)))
            ready, raw = native_packet(request, purpose, observations)
            owner.ready, owner.result = ready.payload + b"\n", canonical(raw) + b"\n"
            if purpose == "capture":
                capture_directory = Path(
                    json.loads(request.to_dict()["capture_json"])["output_directory"]
                )
                assert capture_directory.is_relative_to(directory)
            start(registration, wire, check=check, keep_stdin_open=keep_stdin_open)

        def bound_send(wire, *, check):
            send(wire, check=check)
            if capture_directory is not None:
                # Only the new server-assigned test output, after actual release.
                assert not capture_directory.exists()
                capture_directory.mkdir(parents=True)
                (capture_directory / "frame-000000.yuy2").write_bytes(PIXELS)

        owner.start, owner.send_final_input = bound_start, bound_send
        owners.append(owner)
        return owner

    monkeypatch.setattr(supervisor, "_new_owner", new_owner)
    return owners


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_copied_runtime_is_actually_verified(workspace, copied_camera_runtime, purpose):
    runtime = runtime_policy.reviewed_activation_runtime_candidate(
        workspace, purpose=purpose, source_sha256=SOURCE
    )
    report = runtime_policy.verify_reviewed_activation_runtime(
        runtime, cancellation=Event(), deadline_ns=monotonic_ns() + 10_000_000_000
    )
    assert report["files_checked"] == 26 and report["bytes_read"] > 0
    assert report["status"] == "REVIEWED_SOFTWARE_MATCHED"
    assert report["device_operations"] == 0


def test_refresh_operator_matches_preview_and_execution_rule():
    # Catch a bad synthetic label before constructing the multi-minute history.
    supplied = dict(operator_id=REFRESH_OPERATOR)
    assert portable_setup_operator_valid(REFRESH_OPERATOR)
    assert (
        validate_action_input(ACTION_BY_ID["physical_camera_refresh"], supplied)
        == supplied
    )


def test_settings_operator_uses_the_existing_portable_id_language():
    assert portable_setup_operator_valid(SETTINGS_OPERATOR)


def test_timing_targets_delegate_exact_production_functions_and_restore_lookup():
    targets = camera_timing_targets()
    missing = object()
    previous = [
        (owner, name, getattr(owner, name), vars(owner).get(name, missing))
        for owner, name, _ in targets
    ]
    trace = CameraAdmissionTimingTrace()
    with trace.instrument(targets):
        for owner, name, delegated, _ in previous:
            assert getattr(owner, name).__wrapped__ is delegated
    for owner, name, delegated, local_definition in previous:
        assert getattr(owner, name) is delegated
        assert vars(owner).get(name, missing) is local_definition
    # Installation/restoration performs no production calls or time observation.
    assert trace.snapshot()["started_spans"] == 0


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_public_metadata_peer_matches_incapable_activation(
    make_service, monkeypatch, purpose
):
    app, runner, _ = make_service(mode="physical")
    enroll_public(app, runner, monkeypatch)
    expected = expectation_from_enrollment(
        app._native_camera, source_sha256=SOURCE, launch_session_id=app.session_id
    )
    fields = result_fixture(purpose)[0].to_dict()
    fields.update(
        endpoint=expected.to_dict()["endpoint"],
        endpoint_sha256=digest(expected.to_dict()["endpoint"].encode()),
        activation_identity_json=expected.payload.decode("ascii"),
    )
    request = NativeCameraActivationRequest(canonical(fields))
    metadata = app._native_camera.export_snapshot()["identity_packet"]["receipt"]
    ready, raw = native_packet(request, purpose, metadata)
    parsed = parse_owned_activation_result(
        canonical(raw),
        request=request,
        ready=ready,
        expected_child_pid=123,
        returncode=0,
    )
    assert parsed.activation.independently_matches and parsed.receipt.cleanup_confirmed
    changed = deepcopy(metadata)
    changed["driver"]["version"]["value"] = "MODELED_CHANGED_DRIVER"
    _, bad = native_packet(request, purpose, changed)
    with pytest.raises(ValueError):
        parse_owned_activation_result(
            canonical(bad),
            request=request,
            ready=ready,
            expected_child_pid=123,
            returncode=0,
        )


@pytest.mark.slow
def test_full_original_history_reopen_prepare_probe_settings_capture_export(
    absence_arrival, monkeypatch, tmp_path, copied_camera_runtime
):
    completed = []
    executing_source = source_fingerprint(ROOT)
    source_audit = None

    def successor(previous_app, new_app, predecessor):
        nonlocal source_audit
        _public(
            previous_app,
            mode_entry.ACTION,
            dict(operator_id="MODELED entry operator", file_only=True),
        )
        entered = previous_app._physical_camera_setup.original_source_workflow()
        app, runner = new_app("camera-full-history-reopen")
        operations, exports, owners = [], [], []
        post_capture_restart = None
        setup = app._physical_camera_setup
        # Created only in the successor, after the complete earlier history.
        # No tracing wrapper touches the inherited USB/boot fixture sequence.
        timings = CameraAdmissionTimingTrace(max_entries=4096)

        def act(action, values):
            # The actual public operation also owns a worker thread. Shared
            # action labels cover it until the unchanged public waiter returns
            # or raises; all patched method/import aliases are then restored.
            with timings.instrument(camera_timing_targets()), timings.action(action):
                operation, ticket, seconds = timings.wrap(_public, "public_action")(
                    app, action, values
                )
            operations.append(dict(operation=operation, ticket=ticket, seconds=seconds))
            return operation

        try:
            assert reopen_public(app) == entered
            assert not app._probe_metadata_current()
            assert (
                app.view()["camera"]["status"]
                == app.view()["arm"]["status"]
                == "NOT_CONNECTED"
            )
            enroll_public(app, runner, monkeypatch)
            act("physical_camera_refresh", dict(operator_id=REFRESH_OPERATOR))
            for action in (probe_setup.PREPARE, probe_setup.REVIEW):
                act(action, dict(operator_id="MODELED probe reviewer", file_only=True))
            reviewed = setup.original_source_workflow()
            assert (
                reviewed["camera_probe_preparation"]["state"]
                == "REVIEWED_FOR_ADMISSION"
            )
            for key in predecessor:
                if key not in {
                    "schema",
                    "session_head_sha256",
                    "evidence_inventory_sha256",
                }:
                    assert reviewed[key] == predecessor[key], key
            probe_owners = install_incapable_owner(
                tmp_path, monkeypatch, app._native_camera, purpose="probe"
            )
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
            settings = {f["name"]: f["default"] for f in fields if "default" in f}
            settings.update(
                mode_choice_id=fields[0]["options"][0]["value"],
                operator_id=SETTINGS_OPERATOR,
            )
            act("physical_camera_configuration", settings)
            assert app._configuration_wizard.view()["settings_reference_retained"]
            capture_owners = install_incapable_owner(
                tmp_path, monkeypatch, app._native_camera, purpose="capture"
            )
            captured = act(
                CAPTURE_ACTION_ID,
                dict(
                    operator_id="MODELED capture operator",
                    arm_actuator_supply_disconnected=True,
                    bounded_configuration_capture_consent=True,
                ),
            )
            owners.extend(capture_owners)
            assert len(capture_owners) == 1 and capture_owners[0].cleaned
            assert app.image(app.view()["camera"]["image_id"])[0].startswith(b"\x89PNG")
            exported = act(
                EXPORT_ACTION_ID, dict(attempt_choice_id=captured["operation_id"])
            )
            folder = Path(exported["result"]["steps"][0]["report"]["receipt"]["path"])
            exports.append(str(folder))
            assert (
                folder.parent == app.export_directory and verify_export(folder)["valid"]
            )
            exported_snapshot = json.loads((folder / "report.json").read_bytes())[
                "snapshot"
            ]
            exported_parts = {
                part.name.removeprefix("attachment-"): part.read_bytes()
                for part in folder.glob("attachment-*.json")
            }
            assert restore_configuration_attempt_export(
                exported_snapshot, exported_parts
            ) == app._configuration_wizard.packet(captured["operation_id"])
            assert app._probe_attempt_packet() == original_probe
            assert setup.original_source_workflow() == reviewed
            assert (
                app._log.verify(app._log.directory)["status"]
                == "VERIFIED_DIAGNOSTIC_ONLY"
            )
            assert [s["state"] for s in setup.session.view()["stages"]] == [
                "PASS"
            ] * 4 + ["WAITING_OPERATOR"] + ["PENDING"] * 10
            assert app.view()["physical_authority"] is False
            assert app.view()["arm"]["status"] == "NOT_CONNECTED"
            assert app.view()["physical_camera"]["connected"] is False
            assert all(call[0] == "inventory_devices" for call in runner.calls)
            # A cached Setup view alone cannot prove the post-capture original.
            # Use the explicit public reader again, then check stable subjects;
            # mutable ledger heads/inventories are independently reauthenticated.
            act("physical_camera_refresh", dict(operator_id=REFRESH_OPERATOR))
            reread = setup.original_source_workflow()
            for key, value in reviewed.items():
                if key not in {"session_head_sha256", "evidence_inventory_sha256"}:
                    assert reread[key] == value, key
            assert setup.session.view()["verification"]["leases"] == {
                "active_or_stale_owners": [],
                "reconciliation_required": False,
            }
            assert [s["state"] for s in setup.session.view()["stages"]] == [
                "PASS"
            ] * 4 + ["WAITING_OPERATOR"] + ["PENDING"] * 10
            # P1.5: a same-instance refresh is not a restart. Close the camera
            # application, create another instance and explicitly select the
            # same original store. Do not transplant current metadata/owners.
            retained_capture = app._configuration_wizard.packet(
                captured["operation_id"]
            )
            original_directory = setup.session.descriptor()["directory"]
            app.shutdown()
            post_capture_restart = dict(status="STARTED")
            restarted, restarted_runner = new_app("camera-post-capture-reopen")
            require_disconnected_camera_restart(restarted.view())
            reopened_original = reopen_public(restarted)
            assert reopened_original == reread
            assert restarted.session_id != app.session_id
            assert (
                restarted._physical_camera_setup.session.descriptor()["directory"]
                == original_directory
            )
            require_disconnected_camera_restart(restarted.view())
            assert not restarted._probe_metadata_current()
            assert restarted._probe_attempt_packet() is None
            with pytest.raises(WizardError):
                restarted.prepare_action(
                    CAPTURE_ACTION_ID,
                    dict(
                        operator_id="MODELED restarted operator",
                        arm_actuator_supply_disconnected=True,
                        bounded_configuration_capture_consent=True,
                    ),
                    restarted.view()["revision"],
                )
            assert not restarted_runner.calls
            assert len(probe_owners) == len(capture_owners) == 1
            assert verify_export(folder)["valid"]
            assert (
                restore_configuration_attempt_export(exported_snapshot, exported_parts)
                == retained_capture
            )
            restarted_session = restarted._physical_camera_setup.session.view()
            assert restarted_session["verification"]["leases"] == {
                "active_or_stale_owners": [],
                "reconciliation_required": False,
            }
            assert [s["state"] for s in restarted_session["stages"]] == ["PASS"] * 4 + [
                "WAITING_OPERATOR"
            ] + ["PENDING"] * 10
            assert (
                restarted._log.verify(restarted._log.directory)["status"]
                == "VERIFIED_DIAGNOSTIC_ONLY"
            )
            post_capture_restart = dict(
                status="PASSED",
                snapshot=restarted.view(),
                original=reopened_original,
                original_directory=original_directory,
                previous_launch_id=app.session_id,
                capture_request_held=True,
                automatic_replay=False,
            )
            completed.append(captured["operation_id"])
        finally:
            source_audit = observe_executing_source(ROOT, executing_source)
            (tmp_path / "camera-full-history-checkpoint.json").write_bytes(
                canonical(
                    dict(
                        executing_source_sha256=executing_source,
                        executing_source_audit=source_audit,
                        original=setup.original_source_workflow(),
                        snapshot=app.view(),
                        operations=operations,
                        exports=exports,
                        original_probe=app._probe_attempt_packet(),
                        configuration_attempts=app._configuration_wizard.view(),
                        copied_native_sha256=copied_camera_runtime,
                        completed=completed,
                        post_capture_restart=post_capture_restart,
                        admission_timing_trace=timings.snapshot(),
                        meaning="REAL_NTFS_FULL_READER_CURRENT_METADATA_LOGS_RUNTIME_PINS__MODELED_SOURCE_HARDWARE_PROCESS",
                    )
                )
            )

    establish_complete(absence_arrival, monkeypatch, tmp_path, after_complete=successor)
    assert len(completed) == 1
    require_unchanged_execution_source(source_audit)
