"""Public new-launch v13 acceptance: real NTFS/logs, MODELED hardware peers.

Use a fresh preserved --basetemp. This constructs the complete original prefix
under one build; it never migrates/reuses a saved acceptance store. Metadata,
host boot, USB descriptors and process observations are explicit test models.
No production process, CIM, USB, camera or arm provider may execute.
"""

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import time
from types import SimpleNamespace

import pytest

from rocell.application import arrival_wizard_service as arrival_module
from rocell.application import physical_camera_reopen_registry as registry
from rocell.application import physical_usb_reboot_boot as reboot_boot
from rocell.application import physical_usb_reboot_service as reboot
from rocell.application import physical_camera_setup_service as setup_impl
from rocell.application.physical_camera_acquisition_service import (
    PhysicalCameraAcquisitionService,
)
from rocell.application.physical_camera_usb_reboot_constants import (
    USB_REBOOT_ROLE_BYTES,
)
from rocell.application.physical_usb_identity_export import (
    EXPORT_V6_SCHEMA,
    restore_usb_identity_diagnostics,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows import owned_usb_identity_runner as runner_module
from rocell.providers.windows.host_boot_observation import HostBootObservation, _utc_ns
from rocell.providers.windows.usb_identity_protocol import canonical
from rocell.ui.terminal import _UsbQualificationDisplay
from test_arrival_usb_reconnect_ntfs_acceptance import (
    absence_arrival,
    nominal_arrival,
    actual_arrival,
    workspace,
    no_devices,
    make_service,
    matching_nominal_received_label,
    modeled_platform_name,
    SOURCE,
    fresh_public_metadata,
    _public,
    _ticket,
    test_public_absence_to_reconnect_all_original_roles_logs_export_reopen as establish_reconnect,
)
from test_arrival_wizard_service import FakeRunner
from test_physical_camera_identity_readback import identity_inputs
from test_usb_reconnect_runner_model import REAL_RUNNER, REAL_RUN, ModeledObservedPipe
from test_host_boot_observation import response
import test_physical_usb_trial_boot as boot_fixture
import test_physical_camera_session as session_models
import test_physical_camera_session_readback as prerequisite_models
import test_physical_camera_source_workflow_readback as source_models
import test_physical_camera_intake_session as intake_models
import test_physical_source_qualification_readback as qualification_models


@pytest.fixture(autouse=True)
def restart_workspace_profiles(workspace, monkeypatch):
    """Seed normal launch inputs before any original commissioning state.

    The predecessor uses an Arrival shell on the repository workspace with its
    Setup owner bound to the isolated store. A genuinely new Arrival instance
    on that isolated workspace also needs its two ordinary display profiles.
    Copy controlled inputs up front, never retrofit a retained failed store.
    """
    repository = Path(__file__).resolve().parents[3]
    for relative in (
        "software/config/camera_profiles/arducam_b0477_imx283_16mm.json",
        "software/config/arm_connection.json",
    ):
        source, destination = repository / relative, workspace / relative
        assert source.is_file() and not destination.exists()
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        assert destination.read_bytes() == source.read_bytes()
    # Standalone store tests use arbitrary CELL/SESSION labels. Public discovery
    # requires the real application's source/launch-derived lineage. Choose it
    # before building any prerequisite, header, evidence or attempt; never alter
    # old originals or relax the registry's lineage check.
    acquisition = PhysicalCameraAcquisitionService(
        workspace,
        launch_id=session_models.LAUNCH,
        source_sha256=SOURCE,
        mode="physical",
    )
    for fixtures in (
        session_models,
        prerequisite_models,
        source_models,
        intake_models,
        qualification_models,
    ):
        monkeypatch.setattr(fixtures, "CELL", acquisition.cell_id)
        monkeypatch.setattr(fixtures, "SESSION", acquisition.session_id)


def new_reboot_app(workspace, tmp_path, label):
    """The same real constructor for cheap startup and full public acceptance."""
    runner = FakeRunner()
    app = arrival_module.ArrivalWizardService(
        workspace,
        runner=runner,
        mode="physical",
        export_directory=tmp_path / "reboot-exports",
        log_directory=tmp_path / (label + "-diagnostics"),
    )
    return app, runner


def test_new_launch_workspace_starts_disconnected_without_originals(
    workspace, monkeypatch, tmp_path
):
    monkeypatch.setattr(arrival_module, "source_fingerprint", lambda _: SOURCE)
    before = {
        str(path.relative_to(workspace)): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file()
    }
    app, runner = new_reboot_app(workspace, tmp_path, "startup-smoke")
    try:
        view = app.view()
        assert app.workspace == workspace
        assert view["source_binding_sha256"] == SOURCE
        assert view["status"] == "READY_FOR_DIAGNOSTICS"
        assert view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED"
        assert view["camera"]["profile_id"]
        assert view["arm"]["profile"]
        assert view["physical_authority"] is False
        assert view["diagnostics"]["event_count"] == 0 and not runner.calls
        # The inert owner exists, but no original store has been initialized.
        assert not Path(
            app._physical_camera_setup.session.descriptor()["directory"]
        ).exists()
    finally:
        app.shutdown()
    assert {
        str(path.relative_to(workspace)): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file()
    } == before


def reopen_public(arrival):
    operation, _, _ = _public(
        arrival, "physical_camera_discover", {"operator_id": "reboot-operator"}
    )
    choices = arrival._physical_camera_setup.reopen_choices()
    assert len(choices) == 1, json.dumps(operation, indent=2)
    _public(
        arrival,
        "physical_camera_reopen",
        {
            "operator_id": "reboot-operator",
            "choice_id": choices[0]["value"],
        },
    )
    return arrival._physical_camera_setup.original_source_workflow()


@pytest.mark.skipif(os.name != "nt", reason="real NTFS original initialization")
def test_fresh_original_is_discoverable_with_production_lineage(
    workspace, monkeypatch, tmp_path
):
    for module in (arrival_module, registry, setup_impl, session_models.module):
        monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    original = session_models.session_fixture(workspace)
    session_models.perform(original)
    expected = original.descriptor()
    app, runner = new_reboot_app(workspace, tmp_path, "lineage-smoke")
    try:
        # Empty original: reopening does not invent prerequisite evidence.
        workflow = reopen_public(app)
        assert all(
            workflow[role] is None
            for role in ("prerequisites", "receipt", "assessment", "review")
        )
        reopened = app._physical_camera_setup.session.descriptor()
        assert all(
            reopened[k] == expected[k]
            for k in ("directory", "cell_id", "session_id", "launch_id")
        )
        assert app.session_id != expected["launch_id"]
        assert (
            app.view()["camera"]["status"]
            == app.view()["arm"]["status"]
            == "NOT_CONNECTED"
        )
        assert not runner.calls
    finally:
        app.shutdown()


@pytest.mark.slow
@pytest.mark.skipif(os.name != "nt", reason="real original prefix and public reopening")
def test_fresh_trial_prefix_reopens_through_public_application(
    workspace, monkeypatch, tmp_path
):
    from test_physical_camera_usb_phase_ntfs import actual_declared_trial

    for module in (arrival_module, registry, setup_impl, session_models.module):
        monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    _, expected = actual_declared_trial(workspace, monkeypatch)
    app, runner = new_reboot_app(workspace, tmp_path, "prefix-reopen-smoke")
    try:
        assert reopen_public(app) == expected
        assert not runner.calls
    finally:
        app.shutdown()


@pytest.mark.slow
@pytest.mark.skipif(os.name != "nt", reason="Real original NTFS/M1 storage required")
def test_public_reboot_all_actions_export_and_fresh_reopen(
    absence_arrival, monkeypatch, tmp_path, *, after_reboot=None
):
    prior = absence_arrival
    establish_reconnect(prior, monkeypatch, tmp_path)
    original = deepcopy(prior.setup.original_source_workflow())
    prior.arrival.shutdown()
    boot_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    assert original["usb_qualification_reconnect"]["phase_record"]["document"][
        "context"
    ]["finished_at_utc_ns"] < _utc_ns(boot_time)
    # Only broad checkout identity is modeled; originals, policies, fixed-file
    # pins, readback, owned-scope callbacks and production clocks stay real.
    for module in (registry, reboot_boot, runner_module):
        monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    created = []

    def new_app(label):
        app, runner = new_reboot_app(prior.workspace, tmp_path, label)
        created.append(app)
        return app, runner

    observations, runs, peers, operations = [], [], [], []
    real_execution = boot_fixture.execution

    class ModeledRebootObserver:
        def observe(self, request, *, cancellation, deadline_ns, admission_check):
            assert not observations and deadline_ns == request.expires_at_ns
            with monkeypatch.context() as model:
                model.setattr(boot_fixture, "WALL", time.time_ns())
                model.setattr(
                    boot_fixture,
                    "execution",
                    lambda req, **kw: real_execution(
                        req,
                        raw=response(
                            req,
                            last_boot_up_time_utc=boot_time,
                            confirmation_boot_up_time_utc=boot_time,
                        ),
                        **kw,
                    ),
                )
                injected = boot_fixture.owned_report(
                    request, admission_check=admission_check, cancellation=cancellation
                )
            # Explicitly physical-shaped MODEL input, not a promoted observation
            # from the received host. The production observer is never called.
            document = injected.to_dict()
            document["origin"] = "WINDOWS_LOCAL_CIM"
            report = HostBootObservation(canonical(document))
            observations.append(report)
            return report

    class ModeledSupervisor(REAL_RUNNER):
        def run(self, *, cancellation, deadline_ns):
            assert not runs
            peer = {}
            peers.append(peer)
            with monkeypatch.context() as model:
                model.setattr(
                    runner_module,
                    "_new_owner",
                    lambda: ModeledObservedPipe(
                        self._prepared, cancellation, record=peer
                    ),
                )
                evidence = REAL_RUN(
                    self, cancellation=cancellation, deadline_ns=deadline_ns
                )
            runs.append((self._permit, evidence))
            return evidence

    monkeypatch.setattr(reboot_boot, "WindowsHostBootObserver", ModeledRebootObserver)
    monkeypatch.setattr(runner_module, "OwnedUsbIdentityRunner", ModeledSupervisor)
    try:
        app, runner = new_app("after-reboot")
        assert app.session_id != prior.arrival.session_id
        assert reopen_public(app) == original
        owner = app._usb_identity
        app._camera_helper = identity_inputs(
            source=SOURCE, launch=app.session_id, return_owners=True
        )["helper"]
        case = SimpleNamespace(arrival=app, runner=runner)
        forms = (
            (
                reboot.BEGIN,
                dict(
                    operator_id="Reboot Operator",
                    file_only=True,
                    confirm_host_restarted=True,
                ),
                "PREPARATION_REQUESTED",
            ),
            (
                reboot.PREPARE,
                dict(operator_id="Reboot Operator", file_only=True),
                "PREPARED",
            ),
            (
                reboot.REVIEW,
                dict(
                    reviewer_id="Reboot Reviewer",
                    confirm_policy_review=True,
                    confirm_runtime_review=True,
                    confirm_exact_target=True,
                    confirm_boot_metadata=True,
                ),
                "REVIEWED",
            ),
            (
                reboot.BOOT_COLLECT,
                dict(confirm_host_boot=True, confirm_no_capture_or_arm=True),
                "BOOT_RETAINED",
            ),
            (
                reboot.COLLECT,
                dict(confirm_usb_query=True, confirm_no_capture_or_arm=True),
                "RETAINED_BLOCKED",
            ),
        )
        metadata = []
        for index, (action, values, expected) in enumerate(forms):
            try:
                operation, _, elapsed = _public(app, action, values)
                operations.append(
                    dict(action_id=action, seconds=elapsed, operation=operation)
                )
                current = app._physical_camera_setup.original_source_workflow()
                assert current["schema"].endswith(".v13")
                assert current["usb_qualification_reboot"]["state"] == expected
                assert len(observations) == int(index >= 3) and len(runs) == int(
                    index == 4
                )
                if index == 0:
                    metadata = fresh_public_metadata(case, monkeypatch)
                    assert (
                        app.view()["usb_qualification"]["next_action"]
                        == "physical_camera_refresh"
                    )
                    ledger = deepcopy(owner._reboot.ledger)
                    _public(
                        app,
                        "physical_camera_refresh",
                        dict(operator_id="reboot-operator"),
                    )
                    assert owner._reboot.ledger == ledger
                _UsbQualificationDisplay._validate(
                    app.view()["usb_qualification"], app.view()
                )
            finally:
                (tmp_path / "reboot-public-checkpoint.json").write_bytes(
                    canonical(
                        dict(
                            original=app._physical_camera_setup.original_source_workflow(),
                            diagnostics=owner.retained_diagnostics(),
                            snapshot=app.view(),
                            operations=operations,
                            peers=peers,
                            observations="MODELED_NO_ACTUAL_DEVICE_OR_PROCESS",
                        )
                    )
                )
        phase = current["usb_qualification_reboot"]
        assert len(phase["events"]) == 7
        assert all(
            phase[role]["retention"] == "M1_FULL_BYTES_READ_BACK"
            for role in USB_REBOOT_ROLE_BYTES
        )
        final = phase["phase_record"]["document"]
        assert final["status"] == "REBOOT_OBSERVATIONS_RETAINED" and all(
            c["passed"] for c in final["checks"]
        )
        assert phase["original_campaign"]["result"]["state"] == "SEALED_KNOWN"
        assert not phase["original_campaign"]["result"]["quarantine_latched"]
        ledger = phase["preparation"]["document"]["acquisition_ledger"]["entries"]
        assert [r["operation_id"] for r in ledger] == [
            r["operation_id"] for r in metadata
        ]
        for key in (
            "usb_qualification_baseline",
            "usb_qualification_absence",
            "usb_qualification_reconnect",
        ):
            assert current[key] == original[key]
        exported, _, _ = _public(app, reboot.EXPORT, dict(confirm_metadata_export=True))
        directory = Path(
            exported["result"]["steps"][0]["report"]["metadata_export"]["path"]
        )
        assert (
            directory.parent == app.export_directory
            and verify_export(directory)["valid"]
        )
        report = json.loads((directory / "report.json").read_bytes())["snapshot"]
        assert report["schema"] == EXPORT_V6_SCHEMA
        restored = restore_usb_identity_diagnostics(
            report,
            {
                row["attachment"]: (directory / row["attachment"]).read_bytes()
                for row in report["parts"]
            },
        )
        assert restored["qualification_reboot"] == phase
        fresh, _ = new_app("reopen-after-reboot")
        assert reopen_public(fresh) == current
        for action, values, _ in forms:
            with pytest.raises(WizardError):
                _ticket(fresh, action, values)
        assert all(
            row["state"] == "PENDING"
            for row in fresh._physical_camera_setup.session.view()["stages"][4:]
        )
        if after_reboot is not None:
            # Test-only successor seam: the callback receives the newly built,
            # publicly reopened original while lifecycle cleanup stays here.
            # Never load or migrate an earlier acceptance store for a successor.
            after_reboot(fresh, new_app, deepcopy(current))
        assert len(observations) == len(runs) == 1
    finally:
        for app in created:
            view = app.view()
            # Also preserve failures during discover/reopen, before the first
            # reboot action enters the per-action checkpoint block above.
            (tmp_path / f"reboot-application-{app.session_id}.json").write_bytes(
                canonical(
                    dict(
                        snapshot=view,
                        diagnostics=app._usb_identity.retained_diagnostics(),
                        operations=[
                            app.operation(row["operation_id"])
                            for row in view["operations"]
                        ],
                    )
                )
            )
            app.shutdown()
