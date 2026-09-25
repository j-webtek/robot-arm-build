"""Actual public BASELINE actions and NTFS originals; physical facts MODELED.

Arrival tickets, queue, completion log, source/header-bound M1 records, boot
collector, export and fresh readback are real. Only earlier received facts,
fresh metadata provenance and the boot observer's in-memory executor are
modeled. Its INJECTED_CIM_EXECUTOR result must end BOOT_HELD, never a USB query.
No physical provider, child process, camera, USB, CIM or serial call is allowed.
"""

from copy import deepcopy
import json
import os
from pathlib import Path
from threading import Event
import time
from types import SimpleNamespace
import uuid

import pytest

from rocell.application import arrival_wizard_service as arrival_module
from rocell.application import physical_camera_setup_service as setup_impl
from rocell.application import physical_usb_identity_service as usb_module
from rocell.application import physical_usb_identity_dispatch as dispatch_module
from rocell.application import physical_usb_trial_boot as boot_module
from rocell.application.physical_intake_evidence_service import (
    PhysicalIntakeEvidenceService,
)
from rocell.application.physical_source_qualification_service import (
    PhysicalSourceQualificationService,
)
from rocell.application.physical_static_camera_onboarding_service import (
    PhysicalStaticCameraOnboardingService,
)
from rocell.application.physical_received_camera_service import (
    PhysicalReceivedCameraService,
)
from rocell.application.physical_usb_identity_export import (
    restore_usb_identity_diagnostics,
)
from rocell.application.physical_onboarding import (
    STAGE_ORDER,
    _parse_evidence_reference,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows import host_boot_observation as host
from rocell.providers.windows import owned_usb_identity_runner as usb_runner
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.ui.terminal import _UsbQualificationDisplay

from test_arrival_wizard_service import make_service, _ticket
from test_arrival_usb_identity_composed import _copy_fixed_native
from test_arrival_usb_phase_composed import publish_modeled_acquisitions, REVIEW_VALUES
from test_physical_camera_usb_phase_ntfs import (
    actual_declared_trial,
    workspace,
    no_devices,
)
from test_physical_camera_identity_readback import identity_inputs
from test_physical_camera_identity_service_ntfs import (
    adopt_actual_original,
    read_original,
)
from test_physical_camera_session import SOURCE, session_fixture, perform
import test_physical_usb_trial_boot as boot_fixture


def _complete(arrival, operation_id):
    deadline = time.monotonic() + 210
    while time.monotonic() < deadline:
        operation = arrival.operation(operation_id)
        if operation["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            return operation
        Event().wait(0.02)
    pytest.fail(f"Same public operation remained unresolved: {operation_id}")


def _public(arrival, action, values):
    ticket = _ticket(arrival, action, values)
    started = time.monotonic()
    queued = arrival.execute_action(ticket["ticket_id"])
    operation = _complete(arrival, queued["operation_id"])
    assert operation["status"] == "SUCCEEDED", json.dumps(operation, indent=2)
    assert operation["completion_log_persisted"] is True
    assert operation["result_retention"] == "FULL_JSON_RETAINED"
    assert (
        arrival.execute_action(ticket["ticket_id"])["operation_id"]
        == operation["operation_id"]
    )
    return operation, ticket, round(time.monotonic() - started, 3)


@pytest.fixture
def actual_arrival(workspace, make_service, monkeypatch):
    for module in (setup_impl, usb_module, dispatch_module, boot_module):
        monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    case, original = actual_declared_trial(workspace, monkeypatch)
    session, prerequisites, state = case
    identity, acquisition = adopt_actual_original(session, original)
    setup = identity.setup
    _copy_fixed_native(workspace)
    with monkeypatch.context() as launch:
        launch.setattr(
            arrival_module,
            "uuid",
            SimpleNamespace(uuid4=lambda: uuid.UUID(setup.launch_id[7:])),
        )
        arrival, runner, source = make_service(mode="physical")
    arrival._physical_camera_setup = setup
    arrival._physical_camera = acquisition
    arrival._camera_identity_records = identity
    arrival._physical_intake_evidence = PhysicalIntakeEvidenceService(setup)
    arrival._source_qualification = PhysicalSourceQualificationService(setup)
    arrival._static_camera_onboarding = PhysicalStaticCameraOnboardingService(setup)
    arrival._received_camera = PhysicalReceivedCameraService(setup)
    arrival._usb_identity = usb_module.PhysicalUsbIdentityService(setup)
    for owner in (
        arrival._physical_intake_evidence,
        arrival._source_qualification,
        arrival._static_camera_onboarding,
        arrival._received_camera,
        arrival._usb_identity,
    ):
        owner.observe_setup()

    def forbidden(*args, **kwargs):
        pytest.fail(
            "BOOT_HELD acceptance reached a process, physical provider or USB dispatcher"
        )

    monkeypatch.setattr(
        dispatch_module.PhysicalUsbIdentityDispatchOwner, "perform", forbidden
    )
    monkeypatch.setattr(usb_runner.OwnedUsbIdentityRunner, "run", forbidden)
    monkeypatch.setattr(usb_runner, "_new_owner", forbidden)
    monkeypatch.setattr(host, "_system_powershell", forbidden)
    monkeypatch.setattr(host, "_native_owner", forbidden)
    observations = []

    class NoProcessObserver:
        def observe(self, request, *, cancellation, deadline_ns, admission_check):
            assert deadline_ns == request.expires_at_ns
            # Keep the real collector and its original admission callback. The
            # injected executor is incapable of starting CIM or any process.
            monkeypatch.setattr(boot_fixture, "WALL", time.time_ns())
            report = boot_fixture.owned_report(
                request, admission_check=admission_check, cancellation=cancellation
            )
            assert report.to_dict()["origin"] == "INJECTED_CIM_EXECUTOR"
            observations.append(report)
            return report

    monkeypatch.setattr(boot_module, "WindowsHostBootObserver", NoProcessObserver)
    return SimpleNamespace(
        arrival=arrival,
        owner=arrival._usb_identity,
        setup=setup,
        session=session,
        original=original,
        state=state,
        workspace=workspace,
        runner=runner,
        observations=observations,
        forbidden=forbidden,
    )


@pytest.mark.skipif(
    os.name != "nt", reason="Actual NTFS original owner and leases required"
)
def test_actual_public_baseline_begin_boot_held_export_and_fresh_reopen(
    actual_arrival, monkeypatch, tmp_path
):
    case = actual_arrival
    arrival, owner = case.arrival, case.owner
    before = deepcopy(case.original)
    assert before["schema"].endswith(".v9")
    assert owner.qualification_view()["next_action"] == usb_module.BEGIN
    pending = []
    original_perform = owner.perform

    def before_completion(*args, **kwargs):
        result = original_perform(*args, **kwargs)
        if args[0] in {
            usb_module.BEGIN,
            usb_module.PREPARE,
            usb_module.PHASE_REVIEW,
            usb_module.PHASE_COLLECT,
        }:
            card = arrival.view()["usb_qualification"]
            assert card["publication"]["status"] == "PENDING"
            assert card["baseline"] is None and card["next_action"] is None
            pending.append(args[0])
        return result

    monkeypatch.setattr(owner, "perform", before_completion)
    # Preview is cached; original transactions and native calls are forbidden.
    with monkeypatch.context() as inert:
        inert.setattr(case.session, "stage_transaction", case.forbidden)
        ticket = _ticket(
            arrival,
            usb_module.BEGIN,
            dict(operator_id="Phase Operator", file_only=True),
        )
    begun = arrival.execute_action(ticket["ticket_id"])
    begin_op = _complete(arrival, begun["operation_id"])
    assert begin_op["status"] == "SUCCEEDED", json.dumps(begin_op, indent=2)
    assert begin_op["completion_log_persisted"] is True
    assert (
        arrival.execute_action(ticket["ticket_id"])["operation_id"]
        == begin_op["operation_id"]
    )
    initial = case.setup.original_source_workflow()
    assert initial["schema"].endswith(".v10")
    phase = initial["usb_qualification_baseline"]
    assert phase["state"] == "PREPARATION_REQUESTED" and len(phase["events"]) == 2
    assert not case.observations and not case.runner.calls

    # Explicitly MODELED metadata + successful publication ledger. This lane
    # does not claim to run the OS inventory actions; their callback integration
    # is exercised independently in the composed Arrival tests.
    inputs = identity_inputs(source=SOURCE, launch=owner.launch_id, return_owners=True)
    arrival._native_camera = inputs["native_camera"]
    arrival._camera_helper = inputs["helper"]
    publish_modeled_acquisitions(arrival)
    prepare_op, _, prepare_seconds = _public(
        arrival, usb_module.PREPARE, dict(operator_id="Phase Operator", file_only=True)
    )
    review_op, _, review_seconds = _public(
        arrival, usb_module.PHASE_REVIEW, REVIEW_VALUES
    )
    reviewed = case.setup.original_source_workflow()["usb_qualification_baseline"]
    assert (
        reviewed["state"] == "REVIEWED" and len(reviewed["events"][-1]["evidence"]) == 6
    )
    assert not case.observations
    collect_op, collect_ticket, collect_seconds = _public(
        arrival,
        usb_module.PHASE_COLLECT,
        dict(
            confirm_host_boot=True,
            confirm_usb_query=True,
            confirm_no_capture_or_arm=True,
        ),
    )
    assert collect_seconds < 180
    assert len(case.observations) == 1
    result = collect_op["result"]
    assert result["counter_coverage"] == "NO_DEVICE_IO"
    assert result["steps"][0]["report"]["usb_query_attempted"] is False
    for field in (
        "device_open_count",
        "serial_write_count",
        "power_event_count",
        "motion_command_count",
        "contact_command_count",
    ):
        assert result[field] == 0
    assert (
        result["physical_authority"] is False and result["hardware_qualified"] is False
    )
    current = case.setup.original_source_workflow()
    baseline = current["usb_qualification_baseline"]
    assert baseline["state"] == "BOOT_HELD"
    assert len(baseline["events"]) == 6
    assert (
        baseline["execution"]
        is baseline["phase_record"]
        is baseline["original_campaign"]
        is None
    )
    assert canonical(baseline["host_boot"]["document"]) == case.observations[0].payload
    assert baseline["host_boot"]["retention"] == "M1_FULL_BYTES_READ_BACK"
    assert baseline["host_boot"]["document"]["origin"] == "INJECTED_CIM_EXECUTOR"
    card = arrival.view()["usb_qualification"]
    # Preserve an independently inspectable terminal checkpoint even if a
    # later display/export assertion fails. No original store is rewritten.
    (tmp_path / "public-actions-checkpoint.json").write_bytes(
        canonical(
            dict(
                snapshot=arrival.view(),
                original_baseline=baseline,
                operations=[begin_op, prepare_op, review_op, collect_op],
            )
        )
    )
    _UsbQualificationDisplay._validate(card, arrival.view())
    assert card["baseline"]["host_boot"]["original_state"] == "BOOT_HELD"
    assert card["next_action"] == usb_module.EXPORT
    assert all(r["state"] == "PENDING" for r in case.session.view()["stages"][4:])
    for key in before:
        if key not in {"schema", "session_head_sha256", "evidence_inventory_sha256"}:
            assert current[key] == before[key], key
    with pytest.raises(WizardError):
        _ticket(
            arrival,
            usb_module.PHASE_COLLECT,
            dict(
                confirm_host_boot=True,
                confirm_usb_query=True,
                confirm_no_capture_or_arm=True,
            ),
        )
    assert (
        arrival.execute_action(collect_ticket["ticket_id"])["operation_id"]
        == collect_op["operation_id"]
    )
    assert len(case.observations) == 1

    exported, _, _ = _public(
        arrival, usb_module.EXPORT, {"confirm_metadata_export": True}
    )
    directory = Path(
        exported["result"]["steps"][0]["report"]["metadata_export"]["path"]
    )
    assert directory.parent == arrival.export_directory
    assert verify_export(directory)["valid"]
    export_snapshot = json.loads((directory / "report.json").read_bytes())["snapshot"]
    restored = restore_usb_identity_diagnostics(
        export_snapshot,
        {
            row["attachment"]: (directory / row["attachment"]).read_bytes()
            for row in export_snapshot["parts"]
        },
    )
    assert export_snapshot["original_bytes_preserved"] is True
    assert restored["qualification_baseline"] == baseline
    assert restored["qualification_trial"] == current["usb_qualification_trial"]
    assert (
        canonical(restored["qualification_baseline"]["host_boot"]["document"])
        == case.observations[0].payload
    )
    assert (
        arrival._log.verify(arrival._log.directory)["status"]
        == "VERIFIED_DIAGNOSTIC_ONLY"
    )
    for operation in (begin_op, prepare_op, review_op, collect_op, exported):
        logs = [
            e
            for e in arrival._log.events()
            if e["kind"] == "ACTION_FINISHED"
            and e["details"]["operation_id"] == operation["operation_id"]
        ]
        assert (
            len(logs) == 1
            and logs[0]["details"]["result_sha256"] == operation["result_sha256"]
        )

    fresh = session_fixture(case.workspace)
    perform(fresh, "refresh")
    reopened = read_original(fresh, current["session_header_sha256"])
    assert reopened == current
    fresh_identity, _ = adopt_actual_original(
        fresh, reopened, launch_id="wizard-" + "9" * 32
    )
    fresh_owner = usb_module.PhysicalUsbIdentityService(fresh_identity.setup)
    fresh_owner.observe_setup()
    assert fresh_owner.retained_diagnostics()["qualification_baseline"] == baseline
    assert fresh_owner.blocked_reason(usb_module.PHASE_COLLECT) is not None
    assert fresh_owner.qualification_view()["next_action"] == usb_module.EXPORT
    assert all(r["state"] == "PENDING" for r in fresh.view()["stages"][4:])
    assert len(case.observations) == 1 and not case.runner.calls
    assert pending == [
        usb_module.BEGIN,
        usb_module.PREPARE,
        usb_module.PHASE_REVIEW,
        usb_module.PHASE_COLLECT,
    ]
    receipt = dict(
        schema="rocell.test_usb_phase_ntfs_acceptance.v1",
        original_directory=case.session.descriptor()["directory"],
        diagnostic_log=str(arrival._log.directory),
        export_directory=str(directory),
        export_manifest_sha256=digest((directory / "manifest.json").read_bytes()),
        header_sha256=current["session_header_sha256"],
        head_sha256=current["session_head_sha256"],
        phase_id=baseline["phase_id"],
        state=baseline["state"],
        host_boot_sha256=baseline["host_boot"]["evidence_sha256"],
        role_sha256s={
            r: baseline[r]["evidence_sha256"]
            for r in (
                "enrollment",
                "preparation",
                "policy_review",
                "runtime_review",
                "identity",
                "boot_request",
                "host_boot",
            )
        },
        operation_ids={
            op["action_id"]: op["operation_id"]
            for op in (begin_op, prepare_op, review_op, collect_op, exported)
        },
        prepare_seconds=prepare_seconds,
        review_seconds=review_seconds,
        collect_seconds=collect_seconds,
        physical_facts="EXPLICITLY_MODELED",
        boot_origin="INJECTED_CIM_EXECUTOR",
        processes_created=0,
        usb_queries=0,
        physical_authority=False,
    )
    (tmp_path / "acceptance.json").write_bytes(canonical(receipt))
    print(json.dumps(receipt, indent=2))
