"""Public v10 BASELINE to v11 ABSENCE; genuine NTFS and modeled observations.

Tickets, queue, logs, exact original packages, leases, consumed permits and five
rechecks, retained campaign, export and fresh reopening are real. Earlier
source/received/native/boot/USB/Job observations inherit explicitly MODELED
fixture provenance. The fixed presence file inspection is actual; no production
helper, process, CIM, USB, camera, serial or other device operation may execute.
"""

from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from rocell.application import physical_usb_absence_boot as absence_boot
from rocell.application import physical_usb_absence_service as absence
from rocell.application import physical_usb_presence_dispatch as presence_dispatch
from rocell.application import physical_usb_trial_boot as baseline_boot
from rocell.application import physical_usb_identity_service as usb_service
from rocell.application.physical_camera_usb_absence_constants import (
    USB_ABSENCE_ROLE_BYTES,
    usb_absence_event,
)
from rocell.application.physical_usb_identity_export import (
    EXPORT_V4_SCHEMA,
    restore_usb_identity_diagnostics,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows import usb_presence_registration as registration
from rocell.providers.windows import owned_usb_presence_runner as presence_runner
from rocell.providers.windows import owned_usb_presence_evidence as owned
from rocell.providers.windows.host_boot_observation import compare_boot_observations
from rocell.providers.windows.usb_presence_protocol import canonical, digest
from rocell.ui.terminal import _UsbQualificationDisplay

from test_arrival_usb_phase_ntfs_nominal import (
    nominal_arrival,
    actual_arrival,
    workspace,
    no_devices,
    make_service,
    test_actual_public_nominal_baseline_all_original_roles_export_and_reopen as establish_baseline,
    _public,
    _ticket,
    read_original,
    adopt_actual_original,
    session_fixture,
    perform,
    SOURCE,
)
from test_usb_absence_model_timing import run_timed_presence_model

WORKSPACE = Path(__file__).resolve().parents[3]
FORMS = (
    (
        absence.BEGIN,
        dict(
            operator_id="MODELED Absence Operator",
            confirm_unplug_report=True,
            confirm_file_inspection=True,
        ),
    ),
    (
        absence.BOOT_REVIEW,
        dict(reviewer_id="MODELED Boot Reviewer", confirm_exact_boot_scope=True),
    ),
    (
        absence.BOOT_COLLECT,
        dict(confirm_boot_observation=True, confirm_no_usb_query=True),
    ),
    (
        absence.RUNTIME_REVIEW,
        dict(
            reviewer_id="MODELED Presence Reviewer",
            confirm_policy_review=True,
            confirm_runtime_review=True,
            confirm_exact_target=True,
        ),
    ),
    (
        absence.COLLECT,
        dict(confirm_presence_query=True, confirm_no_capture_or_arm=True),
    ),
)


def copy_exact_presence_runtime(workspace):
    """Copy only fixed already-built files, refusing differing destinations."""
    paths = [(name, sha, size) for name, sha, size in registration.FIXED_SOURCE_PINS]
    paths += [
        (
            registration.BUILD_RECORD_PATH,
            registration.BUILD_RECORD_SHA256,
            registration.BUILD_RECORD_BYTES,
        ),
        (
            registration.HELPER_PATH,
            registration.HELPER_SHA256,
            registration.HELPER_BYTES,
        ),
    ]
    original_root = WORKSPACE / registration.NATIVE_DIRECTORY
    copied_root = workspace / registration.NATIVE_DIRECTORY
    for relative, sha, size in paths:
        source, target = (original_root / relative).resolve(), (
            copied_root / relative
        ).resolve()
        assert source.is_relative_to(WORKSPACE) and target.is_relative_to(workspace)
        payload = source.read_bytes()
        assert len(payload) == size and digest(payload) == sha
        if target.exists():
            assert (
                target.read_bytes() == payload
            ), f"Never overwrite differing fixture file: {target}"
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)


@pytest.fixture
def absence_arrival(nominal_arrival, monkeypatch):
    case = nominal_arrival
    copy_exact_presence_runtime(case.workspace)
    # The full isolated checkout fingerprint is explicitly MODELED. Fixed file
    # hashes/lengths/readback and all other production validators remain real.
    for module in (absence_boot, presence_dispatch, registration):
        monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    monkeypatch.setattr(
        absence_boot, "WindowsHostBootObserver", baseline_boot.WindowsHostBootObserver
    )
    monkeypatch.setattr(presence_runner, "_new_owner", case.forbidden)
    case.presence_runs, case.presence_scope_intervals, case.presence_model_attempts = (
        [],
        [],
        [],
    )

    class ModeledPresenceRunner:
        def __init__(self, prepared, *, permit, authorization, application_guard):
            self.prepared, self.permit = prepared, permit
            self.authorization, self.guard = authorization, application_guard

        def run(self, *, cancellation, deadline_ns):
            assert not case.presence_model_attempts
            record = {}
            case.presence_model_attempts.append(record)
            try:
                evidence = run_timed_presence_model(
                    self.prepared,
                    permit=self.permit,
                    authorization=self.authorization,
                    guard=self.guard,
                    cancellation=cancellation,
                    deadline_ns=deadline_ns,
                    record=record,
                )
            finally:
                case.presence_scope_intervals[:] = [
                    (
                        row["boundary"],
                        round((row["finished_ns"] - row["started_ns"]) / 1e9, 6),
                    )
                    for row in record.get("scope_checks", [])
                ]
            # Return honest retained failures as the real runner does. Nominal
            # acceptance is asserted only after original terminal/readback.
            case.presence_runs.append((self.permit, evidence))
            return evidence

    monkeypatch.setattr(
        presence_runner, "OwnedUsbPresenceRunner", ModeledPresenceRunner
    )
    return case


def checkpoint(path, case, operations, *, complete=False):
    # Save a durable diagnostic checkpoint even if a later publication/export
    # check fails. No original M1 record is changed or replayed by this write.
    path.write_bytes(
        canonical(
            dict(
                snapshot=case.arrival.view(),
                original=case.setup.original_source_workflow(),
                diagnostics=case.owner.retained_diagnostics(),
                operations=operations,
                complete=complete,
                observations="EXPLICITLY_MODELED_NO_PROCESS_OR_DEVICE",
                original_directory=case.session.descriptor()["directory"],
                presence_scope_checks_seconds=case.presence_scope_intervals,
                presence_model_attempts=case.presence_model_attempts,
            )
        )
    )


@pytest.mark.skipif(
    os.name != "nt", reason="Genuine NTFS original and M1 leases required"
)
def test_actual_public_baseline_to_absence_all_roles_export_and_fresh_reopen(
    absence_arrival, tmp_path
):
    case = absence_arrival
    # Invoke the existing full acceptance helper, including all original v10
    # roles, exact baseline export and fresh original reopen. This is not a
    # handcrafted PASS prefix or an adopted service/readback bypass.
    establish_baseline(case, tmp_path)
    arrival = case.arrival
    baseline_original = deepcopy(case.setup.original_source_workflow())
    assert baseline_original["schema"].endswith(".v10")
    assert (
        baseline_original["usb_qualification_baseline"]["state"] == "RETAINED_BLOCKED"
    )
    assert len(case.usb_runs) == len(case.observations) == 1 and not case.presence_runs
    operations, tickets, timings = [], [], []
    expected_states = (
        "PREPARED",
        "BOOT_REVIEWED",
        "PRESENCE_REVIEW_PREPARED",
        "RUNTIME_REVIEWED",
        "RETAINED_BLOCKED",
    )
    checkpoint_path = tmp_path / "absence-public-checkpoint.json"
    for index, ((action, values), expected) in enumerate(zip(FORMS, expected_states)):
        try:
            operation, ticket, elapsed = _public(arrival, action, values)
        except BaseException:
            checkpoint(checkpoint_path, case, operations)
            raise
        operations.append(operation)
        tickets.append(ticket)
        timings.append((action, elapsed))
        checkpoint(checkpoint_path, case, operations)
        current = case.setup.original_source_workflow()
        assert current["schema"].endswith(".v11")
        phase = current["usb_qualification_absence"]
        assert phase["state"] == expected, phase["state"]
        assert len(case.usb_runs) == 1 and not case.runner.calls
        assert len(case.observations) == (1 if index < 2 else 2)
        assert len(case.presence_runs) == (1 if index == 4 else 0)
        result = operation["result"]
        assert result["schema"] == absence.RESULT_SCHEMA
        assert result["device_open_count"] == 0
        assert result["presence_api_call_count"] == (4 if index == 4 else 0)
        assert result["presence_query_attempted"] is (index == 4)
        if index < 4:
            assert result["counter_coverage"] == "NO_DEVICE_IO"
        for field in (
            "serial_write_count",
            "power_event_count",
            "motion_command_count",
            "contact_command_count",
        ):
            assert result[field] == 0
        assert result["physical_authority"] is result["hardware_qualified"] is False
        # Reuse the exact public ticket, never rerun an effectful action.
        assert (
            arrival.execute_action(ticket["ticket_id"])["operation_id"]
            == operation["operation_id"]
        )
        assert len(case.observations) == (1 if index < 2 else 2)
        assert len(case.presence_runs) == (1 if index == 4 else 0)
        checkpoint(checkpoint_path, case, operations)

    current = case.setup.original_source_workflow()
    phase = current["usb_qualification_absence"]
    roles = tuple(USB_ABSENCE_ROLE_BYTES)
    assert len(roles) == 9
    assert len(phase["events"]) == 10
    assert len(phase["events"][-1]["evidence"]) == 9
    assert all(phase[role]["retention"] == "M1_FULL_BYTES_READ_BACK" for role in roles)
    assert all(
        len(canonical(phase[role]["document"])) <= USB_ABSENCE_ROLE_BYTES[role]
        for role in roles
    )
    permit, evidence = case.presence_runs[0]
    assert evidence.status == "ABSENT"
    assert evidence.actual_counts == dict(
        api_calls=4, device_handle_opens=0, configuration_writes=0, frames=0
    )
    assert permit.request.request_key == "usb-absence-" + phase["phase_id"]
    assert canonical(phase["execution"]["document"]) == evidence.payload
    assert phase["execution"]["evidence_sha256"] == evidence.sha256
    assert phase["original_campaign"]["evidence"] == evidence.to_dict()
    original_result = phase["original_campaign"]["result"]
    assert (
        original_result["state"] == "SEALED_KNOWN"
        and not original_result["quarantine_latched"]
    )
    assert original_result["receipt"]["reads"] == 4
    assert (
        original_result["receipt"]["opens"] == original_result["receipt"]["closes"] == 0
    )
    assert original_result["receipt"]["final_power_state"] == "UNKNOWN"
    assert phase["original_campaign_event"]["state"] == "SEALED_KNOWN"
    assert phase["phase_id"] == phase["operation"]["document"]["operation_id"]
    assert phase["operation"]["evidence_sha256"] == permit.registration.operation_sha256
    assert (
        phase["phase_id"] != baseline_original["usb_qualification_baseline"]["phase_id"]
    )
    trial_id = current["usb_qualification_trial"]["plan"]["document"]["binding"][
        "trial_id"
    ]
    requested, prepared = phase["events"][5:7]
    assert requested["detail_code"] == usb_absence_event(
        "PRESENCE_REVIEW_REQUESTED", phase["phase_id"]
    )
    assert prepared["detail_code"] == usb_absence_event(
        "PRESENCE_REVIEW_PREPARED", phase["phase_id"]
    )
    assert prepared["sequence"] == requested["sequence"] + 1
    assert (
        requested["evidence"]
        == prepared["evidence"]
        == sorted(
            [phase[role]["reference"] for role in roles[:6]],
            key=lambda reference: reference["evidence_id"],
        )
    )
    review_event, query_event = phase["events"][-3:-1]
    assert review_event["detail_code"] == usb_absence_event(
        "RUNTIME_REVIEWED", phase["phase_id"], trial_id=trial_id
    )
    assert query_event["detail_code"] == usb_absence_event(
        "QUERY_REQUESTED", phase["phase_id"], trial_id=trial_id
    )
    assert query_event["sequence"] == review_event["sequence"] + 1
    assert (
        query_event["evidence"]
        == review_event["evidence"]
        == [phase["runtime_review"]["reference"]]
    )
    assert (
        compare_boot_observations(*case.observations)["status"] == "SAME_HOST_SAME_BOOT"
    )
    completed = phase["phase_record"]["document"]
    assert completed["status"] == "ABSENCE_OBSERVATIONS_RETAINED", completed["checks"]
    assert (
        completed["presence_outcome"] == "ABSENT"
        and completed["boot_relation"] == "SAME_HOST_SAME_BOOT"
    )
    assert all(row["passed"] for row in completed["checks"])
    assert completed["physical_node_absence_observed"] is True
    for field in (
        "canonical_stage_pass",
        "physical_authority",
        "hardware_qualified",
        "camera_capture_authorized",
        "native_release_allowed",
        "mechanical_unplug_verified",
        "continuous_absence_verified",
    ):
        assert completed[field] is False
    assert [row[0] for row in case.presence_scope_intervals] == list(owned.BOUNDARIES)
    assert all(row["state"] == "PENDING" for row in case.session.view()["stages"][4:])
    for key, value in baseline_original.items():
        if key not in ("schema", "session_head_sha256", "evidence_inventory_sha256"):
            assert current[key] == value, key
    snapshot = arrival.view()
    _UsbQualificationDisplay._validate(snapshot["usb_qualification"], snapshot)
    assert (
        snapshot["usb_qualification"]["next_action"] == "physical_usb_reconnect_begin"
    )
    checkpoint(checkpoint_path, case, operations, complete=True)
    exported, _, _ = _public(
        arrival, usb_service.EXPORT, {"confirm_metadata_export": True}
    )
    export_path = Path(
        exported["result"]["steps"][0]["report"]["metadata_export"]["path"]
    )
    assert (
        export_path.parent == arrival.export_directory
        and verify_export(export_path)["valid"]
    )
    export_snapshot = json.loads((export_path / "report.json").read_bytes())["snapshot"]
    assert (
        export_snapshot["schema"] == EXPORT_V4_SCHEMA
        and export_snapshot["original_bytes_preserved"] is True
    )
    restored = restore_usb_identity_diagnostics(
        export_snapshot,
        {
            row["attachment"]: (export_path / row["attachment"]).read_bytes()
            for row in export_snapshot["parts"]
        },
    )
    assert restored["qualification_absence"] == phase
    assert (
        restored["qualification_baseline"]
        == baseline_original["usb_qualification_baseline"]
    )
    for role in roles:
        assert (
            digest(canonical(restored["qualification_absence"][role]["document"]))
            == phase[role]["evidence_sha256"]
        )
    fresh = session_fixture(case.workspace)
    perform(fresh, "refresh")
    reopened = read_original(fresh, current["session_header_sha256"])
    assert reopened == current
    fresh_identity, _ = adopt_actual_original(
        fresh, reopened, launch_id="wizard-" + "a" * 32
    )
    fresh_owner = usb_service.PhysicalUsbIdentityService(fresh_identity.setup)
    fresh_owner.observe_setup()
    assert fresh_owner.retained_diagnostics()["qualification_absence"] == phase
    for action, values in FORMS:
        assert fresh_owner.blocked_reason(action) is not None
        with pytest.raises(WizardError):
            _ticket(arrival, action, values)
    assert (
        len(case.observations) == 2
        and len(case.usb_runs) == len(case.presence_runs) == 1
    )
    assert all(row["state"] == "PENDING" for row in fresh.view()["stages"][4:])
    assert (
        arrival._log.verify(arrival._log.directory)["status"]
        == "VERIFIED_DIAGNOSTIC_ONLY"
    )
    receipt = dict(
        schema="rocell.test_usb_absence_public_acceptance.v1",
        original_directory=case.session.descriptor()["directory"],
        export_directory=str(export_path),
        manifest_sha256=digest((export_path / "manifest.json").read_bytes()),
        phase_id=phase["phase_id"],
        baseline_phase_id=baseline_original["usb_qualification_baseline"]["phase_id"],
        attempt_id=permit.attempt_id,
        permit_sha256=permit.permit_sha256,
        evidence_sha256=evidence.sha256,
        phase_sha256=phase["phase_record"]["evidence_sha256"],
        header_sha256=current["session_header_sha256"],
        head_sha256=current["session_head_sha256"],
        action_seconds=timings,
        scope_checks_seconds=case.presence_scope_intervals,
        observations="EXPLICITLY_MODELED_BOOT_USB_PRESENCE_AND_PROCESS_FACTS",
        actual_processes=0,
        actual_hardware_queries=0,
        actual_fixed_file_inspection=True,
        modeled_native_counts=evidence.actual_counts,
        real_original_m1=True,
        canonical_stage_pass=False,
        state=phase["state"],
    )
    (tmp_path / "absence-acceptance.json").write_bytes(canonical(receipt))
    print(json.dumps(receipt, indent=2), flush=True)
