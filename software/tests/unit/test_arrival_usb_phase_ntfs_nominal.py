"""Public nominal BASELINE with real NTFS/M1 and MODELED physical facts.

This is hardware-free software acceptance, not received-camera qualification.
The public owner, original leases, consumed permits, all five revalidations,
logs, stage role transfers and exports are real. Boot/USB/process observations
are explicitly constructed test data through the strict production codecs.
No actual process, CIM query, USB query or physical helper may run.
"""

from copy import deepcopy
import json
import os
from pathlib import Path
import time

import pytest

from rocell.application import physical_usb_identity_dispatch as dispatch_module
from rocell.application import physical_usb_trial_boot as boot_module
from rocell.application import physical_usb_identity_service as usb_module
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_usb_identity_export import (
    restore_usb_identity_diagnostics,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
)
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows import owned_usb_identity_runner as runner_module
from rocell.providers.windows import owned_usb_identity_evidence as owned
from rocell.providers.windows import usb_identity_protocol as usb
from rocell.providers.windows.host_boot_observation import HostBootObservation
from rocell.ui.terminal import _UsbQualificationDisplay

from test_arrival_usb_phase_ntfs_acceptance import (
    actual_arrival,
    workspace,
    no_devices,
    make_service,
    _public,
    _ticket,
    publish_modeled_acquisitions,
    REVIEW_VALUES,
    identity_inputs,
    SOURCE,
    read_original,
    adopt_actual_original,
    session_fixture,
    perform,
)
from test_physical_camera_usb_qualification import usb_native_enrollment
from test_physical_camera_usb_readback import modeled_clean_held_evidence
from test_physical_usb_presence_binding import observed_native
from test_owned_usb_identity_runner import usb_fixture
import test_physical_usb_trial_boot as boot_fixture


# Capture before the imported held fixture installs its refusal-only guard.
# This restores the exact production dispatcher, not an alternative admission.
REAL_DISPATCH = dispatch_module.PhysicalUsbIdentityDispatchOwner.perform


def modeled_observed_evidence(prepared, *, deadline, started, utc, checks):
    """Strict complete descriptors/trace + modeled owner observations, no IO."""
    observation = observed_native(prepared.request)
    raw = modeled_clean_held_evidence(prepared).to_dict()
    ready_wire = owned.stream_bytes(raw["stdout"], owned.MAX_EVIDENCE_BYTES)[
        : raw["ready_length"]
    ]
    ready = usb.UsbIdentityReady(ready_wire.rstrip(b"\n"))
    result = dict(
        schema=usb.RESULT_SCHEMA,
        request_sha256=prepared.request.request_sha256,
        child_pid=31415,
        challenge_sha256=ready.challenge_sha256,
        permit_sha256=prepared.request.to_dict()["permit_sha256"],
        native_receipt=observation.to_dict(),
    )
    raw["process"]["returncode"] = 0
    raw.update(
        status="OBSERVED",
        original_deadline_ns=deadline,
        started_monotonic_ns=started,
        finished_monotonic_ns=time.monotonic_ns(),
        started_utc_ns=utc,
        finished_utc_ns=time.time_ns(),
        scope_checks=checks,
        stdout=owned.stream_record(ready_wire + usb.canonical(result), complete=True),
    )
    evidence = owned.OwnedUsbIdentityRunEvidence(usb.canonical(raw))
    assert evidence.status == "OBSERVED"
    assert evidence.process_cleanup_confirmed and evidence.usb_cleanup_confirmed
    assert evidence.observation.to_dict() == observation.to_dict()
    return evidence


def test_nominal_modeled_evidence_uses_full_strict_codecs_without_process():
    case = usb_fixture(incapable=False)
    started, utc = time.monotonic_ns(), time.time_ns()
    checks = [
        dict(
            boundary=name,
            started_ns=time.monotonic_ns(),
            finished_ns=time.monotonic_ns(),
            passed=True,
        )
        for name in owned.BOUNDARIES
    ]
    evidence = modeled_observed_evidence(
        case.prepared,
        deadline=started + 25_000_000_000,
        started=started,
        utc=utc,
        checks=checks,
    )
    counts = evidence.bounded_effect_summary()["actual_counts"]
    assert counts["hub_open_attempts"] == counts["close_attempts"] == 3
    assert counts["remaining_open_handles"] == 0
    assert len(evidence.payload) < 128 * 1024


def fresh_modeled_usb_metadata(arrival):
    """Model a complete v2 driver/USB target using real enrollment owners."""
    owner = arrival._usb_identity
    helper = identity_inputs(source=SOURCE, launch=owner.launch_id, return_owners=True)[
        "helper"
    ]
    original = usb_native_enrollment(
        SOURCE, owner.launch_id, suffix="new-trial-nominal"
    )
    descriptor = dict(
        provenance="WINDOWS_NATIVE_METADATA",
        helper_sha256=helper.registration().payload["helper_sha256"],
    )
    inventory, identity = deepcopy(original["inventory_packet"]), deepcopy(
        original["identity_packet"]
    )
    inventory.update(descriptor)
    identity.update(descriptor)
    native = WizardNativeCameraEnrollment(
        "physical", owner.launch_id, SOURCE, descriptor
    )
    native.ingest_inventory(
        inventory,
        operation_id="nominal-fresh-native-inventory",
        generic_review=original["generic_review"],
    )
    choice = native.choices()[0]["value"]
    native.retain_identity(
        choice, identity, operation_id="nominal-fresh-native-identity"
    )
    native.review(choice, "MODELED-endpoint-reviewer")
    arrival._native_camera, arrival._camera_helper = native, helper
    publish_modeled_acquisitions(arrival)


@pytest.fixture
def nominal_arrival(actual_arrival, monkeypatch):
    case = actual_arrival
    monkeypatch.setattr(
        dispatch_module.PhysicalUsbIdentityDispatchOwner, "perform", REAL_DISPATCH
    )
    case.usb_runs, case.scope_intervals = [], []

    class ModeledPhysicalBootObserver:
        def observe(self, request, *, cancellation, deadline_ns, admission_check):
            assert deadline_ns == request.expires_at_ns
            monkeypatch.setattr(boot_fixture, "WALL", time.time_ns())
            injected = boot_fixture.owned_report(
                request, admission_check=admission_check, cancellation=cancellation
            )
            # Explicitly MODEL physical-shaped data for this test; never upgrade
            # the actual injected observation or add a production bypass flag.
            document = injected.to_dict()
            document["origin"] = "WINDOWS_LOCAL_CIM"
            report = HostBootObservation(usb.canonical(document))
            case.observations.append(report)
            return report

    class ModeledObservedRunner:
        """Only effect observations are modeled; consumed M1 checks are real."""

        def __init__(self, prepared, *, permit, authorization, application_guard):
            self.prepared, self.permit = prepared, permit
            self.authorization, self.guard = authorization, application_guard

        def run(self, *, cancellation, deadline_ns):
            started, utc = time.monotonic_ns(), time.time_ns()
            assert not case.usb_runs and self.guard() is None
            self.authorization.acknowledge(self.permit)
            checks = []
            for boundary in owned.BOUNDARIES:
                assert not cancellation.is_set() and time.monotonic_ns() < deadline_ns
                before = time.monotonic_ns()
                self.authorization.revalidate(self.permit)
                finished = time.monotonic_ns()
                checks.append(
                    dict(
                        boundary=boundary,
                        started_ns=before,
                        finished_ns=finished,
                        passed=True,
                    )
                )
                case.scope_intervals.append(
                    (boundary, round((finished - before) / 1e9, 6))
                )
            evidence = modeled_observed_evidence(
                self.prepared,
                deadline=deadline_ns,
                started=started,
                utc=utc,
                checks=checks,
            )
            case.usb_runs.append((self.permit, evidence))
            return evidence

    monkeypatch.setattr(
        boot_module, "WindowsHostBootObserver", ModeledPhysicalBootObserver
    )
    monkeypatch.setattr(runner_module, "OwnedUsbIdentityRunner", ModeledObservedRunner)
    return case


@pytest.mark.skipif(
    os.name != "nt", reason="Actual NTFS original and M1 leases required"
)
def test_actual_public_nominal_baseline_all_original_roles_export_and_reopen(
    nominal_arrival, tmp_path
):
    case = nominal_arrival
    arrival, owner = case.arrival, case.owner
    _public(
        arrival,
        usb_module.BEGIN,
        dict(operator_id="MODELED Phase Operator", file_only=True),
    )
    fresh_modeled_usb_metadata(arrival)
    prepare_op, _, prepare_seconds = _public(
        arrival,
        usb_module.PREPARE,
        dict(operator_id="MODELED Phase Operator", file_only=True),
    )
    review_op, _, review_seconds = _public(
        arrival, usb_module.PHASE_REVIEW, REVIEW_VALUES
    )
    before = deepcopy(case.setup.original_source_workflow())
    operation, ticket, collect_seconds = _public(
        arrival,
        usb_module.PHASE_COLLECT,
        dict(
            confirm_host_boot=True,
            confirm_usb_query=True,
            confirm_no_capture_or_arm=True,
        ),
    )
    assert len(case.observations) == len(case.usb_runs) == 1
    assert not case.runner.calls
    permit, evidence = case.usb_runs[0]
    current = case.setup.original_source_workflow()
    baseline = current["usb_qualification_baseline"]
    role_names = (
        "enrollment",
        "preparation",
        "policy_review",
        "runtime_review",
        "identity",
        "boot_request",
        "host_boot",
        "execution",
        "phase_record",
    )
    assert baseline["state"] == "RETAINED_BLOCKED" and len(baseline["events"]) == 8
    assert len(baseline["events"][-1]["evidence"]) == 9
    assert all(
        baseline[r]["retention"] == "M1_FULL_BYTES_READ_BACK" for r in role_names
    )
    assert usb.canonical(baseline["execution"]["document"]) == evidence.payload
    assert baseline["execution"]["evidence_sha256"] == evidence.sha256
    assert baseline["original_campaign"]["evidence"] == evidence.to_dict()
    original_result = baseline["original_campaign"]["result"]
    assert (
        original_result["state"] == "SEALED_KNOWN"
        and not original_result["quarantine_latched"]
    )
    assert original_result["permit_sha256"] == permit.permit_sha256
    assert original_result["receipt"]["evidence_sha256s"] == [evidence.sha256]
    assert baseline["original_campaign_event"]["state"] == "SEALED_KNOWN"
    phase = baseline["phase_record"]["document"]
    assert phase["status"] == "OBSERVATIONS_RETAINED", phase["checks"]
    assert all(row["passed"] for row in phase["checks"])
    assert phase["canonical_stage_pass"] is False
    assert (
        phase["execution"]["operation_sha256"] == permit.registration.operation_sha256
    )
    assert phase["execution"]["usb3_operating"] is True
    assert phase["execution"]["attempt_id"] == permit.attempt_id
    report = operation["result"]["steps"][0]["report"]
    assert report["usb_query_attempted"] is True
    assert operation["result"]["device_open_count"] == 3
    assert (
        operation["result"]["counter_coverage"]
        == evidence.safe_summary()["counter_coverage"]
    )
    assert operation["result"]["physical_authority"] is False
    assert operation["result"]["hardware_qualified"] is False
    assert [row[0] for row in case.scope_intervals] == list(owned.BOUNDARIES)
    assert all(row["state"] == "PENDING" for row in case.session.view()["stages"][4:])
    for role in (
        "prerequisites",
        "configuration_epochs",
        "qualification_cycles",
        "static_contract",
        "received_camera_cycles",
        "camera_identity_cycles",
        "usb_qualification_trial",
    ):
        assert current[role] == before[role]
    snapshot = arrival.view()
    _UsbQualificationDisplay._validate(snapshot["usb_qualification"], snapshot)
    # A complete original BASELINE now leads to the separately confirmed,
    # file-only unplug report. Export remains available; no next query runs.
    assert snapshot["usb_qualification"]["next_action"] == "physical_usb_absence_begin"
    assert (
        arrival.execute_action(ticket["ticket_id"])["operation_id"]
        == operation["operation_id"]
    )
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
    checkpoint = dict(
        snapshot=snapshot,
        original_baseline=baseline,
        operations=[prepare_op, review_op, operation],
        observations_are_modeled=True,
    )
    (tmp_path / "nominal-public-checkpoint.json").write_bytes(usb.canonical(checkpoint))
    exported, _, _ = _public(
        arrival, usb_module.EXPORT, {"confirm_metadata_export": True}
    )
    export_path = Path(
        exported["result"]["steps"][0]["report"]["metadata_export"]["path"]
    )
    assert (
        export_path.parent == arrival.export_directory
        and verify_export(export_path)["valid"]
    )
    export_snapshot = json.loads((export_path / "report.json").read_bytes())["snapshot"]
    restored = restore_usb_identity_diagnostics(
        export_snapshot,
        {
            row["attachment"]: (export_path / row["attachment"]).read_bytes()
            for row in export_snapshot["parts"]
        },
    )
    assert export_snapshot["original_bytes_preserved"] is True
    assert restored["qualification_baseline"] == baseline
    for role in role_names:
        assert (
            usb.digest(
                usb.canonical(restored["qualification_baseline"][role]["document"])
            )
            == baseline[role]["evidence_sha256"]
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
    assert fresh_owner.blocked_reason(usb_module.PHASE_COLLECT) is not None
    assert fresh_owner.retained_diagnostics()["qualification_baseline"] == baseline
    assert all(row["state"] == "PENDING" for row in fresh.view()["stages"][4:])
    assert len(case.usb_runs) == len(case.observations) == 1
    assert (
        arrival._log.verify(arrival._log.directory)["status"]
        == "VERIFIED_DIAGNOSTIC_ONLY"
    )
    receipt = dict(
        schema="rocell.test_nominal_usb_phase_acceptance.v1",
        original_directory=case.session.descriptor()["directory"],
        export_directory=str(export_path),
        manifest_sha256=usb.digest((export_path / "manifest.json").read_bytes()),
        phase_id=baseline["phase_id"],
        attempt_id=permit.attempt_id,
        permit_sha256=permit.permit_sha256,
        evidence_sha256=evidence.sha256,
        phase_sha256=baseline["phase_record"]["evidence_sha256"],
        header_sha256=current["session_header_sha256"],
        head_sha256=current["session_head_sha256"],
        prepare_seconds=prepare_seconds,
        review_seconds=review_seconds,
        collect_seconds=collect_seconds,
        scope_checks_seconds=case.scope_intervals,
        observations="EXPLICITLY_MODELED_BOOT_USB_AND_PROCESS_FACTS",
        actual_processes=0,
        actual_hardware_queries=0,
        modeled_native_counts=evidence.bounded_effect_summary()["actual_counts"],
        real_original_m1=True,
        canonical_stage_pass=False,
        state=baseline["state"],
    )
    (tmp_path / "nominal-acceptance.json").write_bytes(usb.canonical(receipt))
    print(json.dumps(receipt, indent=2))
