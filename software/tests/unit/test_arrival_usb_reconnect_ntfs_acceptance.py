"""Real public v12 storage, logs and runner gates; hardware facts MODELED.

Run only in a fresh preserved --basetemp. Never reuse a path containing M1
originals. This test does not commission the received camera or robot arm.
"""

from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application import physical_usb_identity_service as usb_service
from rocell.application import physical_usb_reconnect_service as reconnect
from rocell.application import physical_usb_reconnect_boot as reconnect_boot
from rocell.application import physical_usb_trial_boot as baseline_boot
from rocell.application.physical_camera_usb_reconnect_constants import (
    USB_RECONNECT_ROLE_BYTES,
)
from rocell.application.physical_usb_identity_export import (
    EXPORT_V5_SCHEMA,
    restore_usb_identity_diagnostics,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
)
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows import owned_usb_identity_runner as runner_module
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.ui.terminal import _UsbQualificationDisplay

from test_arrival_usb_absence_ntfs_acceptance import (
    absence_arrival,
    nominal_arrival,
    actual_arrival,
    workspace,
    no_devices,
    make_service,
    SOURCE,
    _public,
    _ticket,
    read_original,
    adopt_actual_original,
    session_fixture,
    perform,
    test_actual_public_baseline_to_absence_all_roles_export_and_fresh_reopen as establish_absence,
)
from test_physical_camera_usb_qualification import usb_native_enrollment
from test_physical_received_camera import (
    fixture as received_model_fixture,
    prerequisites,
)
import test_physical_received_camera_readback as received_readback_fixture
from test_usb_reconnect_runner_model import REAL_RUNNER, REAL_RUN, ModeledObservedPipe


NOMINAL_SERIAL = "MODELED-ONLY"


def nominal_received_fixture(*args, **kwargs):
    """Choose coherent simulated input BEFORE creating any original subject.

    The general receipt fixture models another serial. Only this nominal public
    reconnect lane uses the serial emitted by its generic/descriptor peers.
    No previously retained receipt, reference, plan or verdict is rewritten.
    """
    notebook, reference, inspection, binding = received_model_fixture(*args, **kwargs)
    return (
        notebook,
        reference,
        replace(inspection, observed_camera_serial=NOMINAL_SERIAL),
        binding,
    )


@pytest.fixture(autouse=True)
def matching_nominal_received_label(monkeypatch):
    # This module-scoped test choice takes effect before actual_arrival builds
    # its fresh received originals. Other test modules retain their defaults.
    monkeypatch.setattr(
        received_readback_fixture, "modeled_receipt", nominal_received_fixture
    )


def test_nominal_input_serials_agree_before_original_retention(prerequisites):
    original = received_model_fixture(prerequisites, observed=True)
    selected = received_readback_fixture.modeled_receipt(prerequisites, observed=True)
    assert original[2].observed_camera_serial == "MODELED-NOT-HARDWARE-001"
    assert selected[2] == replace(original[2], observed_camera_serial=NOMINAL_SERIAL)
    assert selected[:2] == original[:2] and selected[3] == original[3]
    native = usb_native_enrollment(SOURCE, "wizard-nominal-input-check")
    assert (
        native["generic_review"]["candidate_record"]["usb_identity"]["unit_serial"]
        == selected[2].observed_camera_serial
        == NOMINAL_SERIAL
    )
    # Check the descriptor peer's actual strict decoded fixture, not a supplied
    # expectation or a patched validation function.
    from test_owned_usb_identity_runner import usb_fixture
    from test_physical_usb_presence_binding import observed_native

    request = usb_fixture(incapable=False).prepared.request
    observation = observed_native(request).to_dict()
    assert {row["value"] for row in observation["serial_descriptors"]} == {
        NOMINAL_SERIAL
    }


@pytest.mark.skipif(os.name != "nt", reason="Genuine NTFS original/M1 leases required")
def test_nominal_public_prefix_retains_matching_received_serial(actual_arrival):
    plan = actual_arrival.original["usb_qualification_trial"]["plan"]["document"]
    assert plan["received_label"]["serial"] == NOMINAL_SERIAL
    received = actual_arrival.state["received_subjects"].subjects["submission"]
    assert received.to_dict()["inspection"]["observed_camera_serial"] == NOMINAL_SERIAL
    assert not actual_arrival.observations


@pytest.fixture(autouse=True)
def modeled_platform_name(monkeypatch):
    # platform.system() can spawn cmd.exe on Windows when its cache is empty.
    # UI eligibility is explicitly modeled, so do not let that incidental
    # subprocess defeat the fixture's stronger no-process prohibition.
    import platform

    # Arrival now uses sys.platform directly. Patch the actual standard-library query
    # for any remaining provider-selection code, not a removed Arrival import.
    monkeypatch.setattr(platform, "system", lambda: "Windows")


def test_public_metadata_peer_uses_actual_coordinator_and_logs(
    make_service, monkeypatch
):
    """Cheap integration check before creating a long-lived original M1 chain."""
    from test_physical_camera_identity_readback import identity_inputs

    arrival, worker, _ = make_service(mode="physical")
    supplied = identity_inputs(
        source=SOURCE, launch=arrival.session_id, return_owners=True
    )
    arrival._camera_helper = supplied["helper"]
    operations = fresh_public_metadata(
        SimpleNamespace(arrival=arrival, runner=worker), monkeypatch
    )
    assert len(operations) == 3
    assert [op["action_id"] for op in operations] == [
        "inventory_devices",
        "native_camera_inventory",
        "native_camera_identity",
    ]
    assert all(op["completion_log_persisted"] for op in operations)
    assert (
        arrival._log.verify(arrival._log.directory)["status"]
        == "VERIFIED_DIAGNOSTIC_ONLY"
    )


def fresh_public_metadata(case, monkeypatch, *, identity_receipt_factory=None):
    """Actual tickets/log publication, with metadata bytes from a test peer."""
    arrival = case.arrival
    original = usb_native_enrollment(
        SOURCE, arrival.session_id, suffix="after-reconnect-public"
    )
    helper = arrival._camera_helper
    descriptor = dict(
        provenance="WINDOWS_NATIVE_METADATA",
        helper_sha256=helper.registration().payload["helper_sha256"],
    )
    inventory, identity = deepcopy(original["inventory_packet"]), deepcopy(
        original["identity_packet"]
    )
    if identity_receipt_factory is not None:
        # A successor can select fuller incapable observations BEFORE any
        # acquisition/log/retention. Never rewrite previously retained metadata.
        identity["receipt"] = identity_receipt_factory(identity["receipt"])
    inventory.update(descriptor)
    identity.update(descriptor)
    calls = []

    class MetadataPeer:
        def descriptor(self):
            return dict(descriptor)

        def inventory(self):
            calls.append("inventory")
            return deepcopy(inventory)

        def identity(self, candidate):
            calls.append("identity")
            assert candidate.symbolic_link == identity["receipt"]["requested_endpoint"]
            return deepcopy(identity)

    arrival._native_camera = WizardNativeCameraEnrollment(
        "physical", arrival.session_id, SOURCE, descriptor
    )
    arrival._native_camera_provider = MetadataPeer()
    arrival._native_fixture_provider = False
    base_run = case.runner.run

    def inventory_worker(action, values, **kwargs):
        assert action == "inventory_devices"
        result = base_run(action, values, **kwargs)
        result["steps"] = [
            dict(
                name="metadata_inventory",
                exit_code=0,
                report=deepcopy(original["generic_review"]["inventory_report"]),
            )
        ]
        return result

    monkeypatch.setattr(case.runner, "run", inventory_worker)
    operations = []
    operations.append(
        _public(arrival, "inventory_devices", dict(power_disconnected=True))[0]
    )
    choice = arrival._device_selection.choices("CAMERA")[0]["value"]
    _public(
        arrival,
        "review_camera_candidate",
        dict(
            choice_id=choice, reviewer_id="MODELED generic reviewer", metadata_only=True
        ),
    )
    operations.append(
        _public(arrival, "native_camera_inventory", dict(metadata_only=True))[0]
    )
    choice = arrival._native_camera.choices()[0]["value"]
    operations.append(
        _public(
            arrival,
            "native_camera_identity",
            dict(choice_id=choice, metadata_only=True),
        )[0]
    )
    _public(
        arrival,
        "native_camera_review",
        dict(
            choice_id=choice, reviewer_id="MODELED native reviewer", metadata_only=True
        ),
    )
    assert calls == ["inventory", "identity"]
    assert all(op["completion_log_persisted"] for op in operations)
    return operations


def checkpoint(path, case, operations, peers, *, complete=False):
    path.write_bytes(
        canonical(
            dict(
                schema="rocell.test_usb_reconnect_public_checkpoint.v1",
                complete=complete,
                original=case.setup.original_source_workflow(),
                snapshot=case.arrival.view(),
                diagnostics=case.owner.retained_diagnostics(),
                operations=operations,
                modeled_pipe_peers=peers,
                observations="MODELED_METADATA_BOOT_USB_PROCESS_NO_ACTUAL_DEVICE_OR_PROCESS",
                original_directory=case.session.descriptor()["directory"],
            )
        )
    )


@pytest.mark.skipif(os.name != "nt", reason="Genuine NTFS original/M1 leases required")
def test_public_absence_to_reconnect_all_original_roles_logs_export_reopen(
    absence_arrival, monkeypatch, tmp_path
):
    case = absence_arrival
    # Fail before spending minutes on baseline/absence if the nominal input
    # model becomes inconsistent again. A real mismatch must remain held.
    assert (
        case.original["usb_qualification_trial"]["plan"]["document"]["received_label"][
            "serial"
        ]
        == NOMINAL_SERIAL
    )
    establish_absence(case, tmp_path)
    before = deepcopy(case.setup.original_source_workflow())
    assert before["schema"].endswith(".v11")
    monkeypatch.setattr(reconnect_boot, "source_fingerprint", lambda _: SOURCE)
    monkeypatch.setattr(
        reconnect_boot, "WindowsHostBootObserver", baseline_boot.WindowsHostBootObserver
    )
    monkeypatch.setattr(runner_module, "source_fingerprint", lambda _: SOURCE)
    peers, runs, operations = [], [], []

    class ObservedSupervisor(REAL_RUNNER):
        def run(self, *, cancellation, deadline_ns):
            assert not runs
            peer = {}
            peers.append(peer)
            with monkeypatch.context() as effect:
                effect.setattr(
                    runner_module,
                    "_new_owner",
                    lambda: ModeledObservedPipe(
                        self._prepared, cancellation, record=peer
                    ),
                )
                # All scope callbacks and real timing gates execute unchanged.
                evidence = REAL_RUN(
                    self, cancellation=cancellation, deadline_ns=deadline_ns
                )
            runs.append((self._permit, evidence))
            peer.update(evidence=evidence.to_dict(), evidence_sha256=evidence.sha256)
            return evidence

    monkeypatch.setattr(runner_module, "OwnedUsbIdentityRunner", ObservedSupervisor)
    arrival = case.arrival
    forms = (
        (
            "begin",
            dict(
                operator_id="Reconnect Operator",
                file_only=True,
                confirm_reconnected=True,
            ),
            "PREPARATION_REQUESTED",
        ),
        ("prepare", dict(operator_id="Reconnect Operator", file_only=True), "PREPARED"),
        (
            "review",
            dict(
                reviewer_id="Reconnect Reviewer",
                confirm_policy_review=True,
                confirm_runtime_review=True,
                confirm_exact_target=True,
                confirm_boot_metadata=True,
            ),
            "REVIEWED",
        ),
        (
            "boot_collect",
            dict(confirm_host_boot=True, confirm_no_capture_or_arm=True),
            "BOOT_RETAINED",
        ),
        (
            "collect",
            dict(confirm_usb_query=True, confirm_no_capture_or_arm=True),
            "RETAINED_BLOCKED",
        ),
    )
    path = tmp_path / "reconnect-public-checkpoint.json"
    metadata = []
    for index, (kind, values, state) in enumerate(forms):
        action = "physical_usb_reconnect_" + kind
        try:
            operation, ticket, elapsed = _public(arrival, action, values)
            operations.append(
                dict(action_id=action, seconds=elapsed, operation=operation)
            )
            current = case.setup.original_source_workflow()
            assert current["schema"].endswith(".v12")
            phase = current["usb_qualification_reconnect"]
            assert phase["state"] == state, phase["state"]
            assert (
                arrival.execute_action(ticket["ticket_id"])["operation_id"]
                == operation["operation_id"]
            )
            assert len(runs) == int(index == 4)
            assert len(case.observations) == (3 if index >= 3 else 2)
            if index == 0:
                metadata = fresh_public_metadata(case, monkeypatch)
                # Actual metadata actions deliberately withdraw the original
                # Setup publication. Verify the same original explicitly;
                # this is not a reopened interval or a hardware replay.
                assert case.setup.view()["publication"]["status"] == "HISTORICAL_HELD"
                assert (
                    arrival.view()["usb_qualification"]["next_action"]
                    == "physical_camera_refresh"
                )
                _UsbQualificationDisplay._validate(
                    arrival.view()["usb_qualification"], arrival.view()
                )
                ledger_before = deepcopy(case.owner._reconnect.ledger)
                with pytest.raises(WizardError):
                    _ticket(
                        arrival,
                        "physical_usb_reconnect_prepare",
                        dict(operator_id="Reconnect Operator", file_only=True),
                    )
                _public(
                    arrival,
                    "physical_camera_refresh",
                    dict(operator_id="reconnect-operator"),
                )
                assert case.setup.view()["publication"]["status"] == "CURRENT"
                assert case.owner._reconnect.ledger == ledger_before
                assert (
                    case.setup.original_source_workflow()[
                        "usb_qualification_reconnect"
                    ]["phase_id"]
                    == phase["phase_id"]
                )
            _UsbQualificationDisplay._validate(
                arrival.view()["usb_qualification"], arrival.view()
            )
        finally:
            checkpoint(path, case, operations, peers)

    current = case.setup.original_source_workflow()
    phase = current["usb_qualification_reconnect"]
    assert (
        len(USB_RECONNECT_ROLE_BYTES) == 11
        and sum(USB_RECONNECT_ROLE_BYTES.values()) == 1224 * 1024
    )
    assert len(phase["events"]) == 7 and len(phase["events"][-1]["evidence"]) == 11
    assert all(
        phase[role]["retention"] == "M1_FULL_BYTES_READ_BACK"
        for role in USB_RECONNECT_ROLE_BYTES
    )
    for role, maximum in USB_RECONNECT_ROLE_BYTES.items():
        assert len(canonical(phase[role]["document"])) <= maximum
    ledger = phase["preparation"]["document"]["acquisition_ledger"]
    assert len(ledger["entries"]) == 3
    assert [row["operation_id"] for row in ledger["entries"]] == [
        op["operation_id"] for op in metadata
    ]
    assert [row["result_sha256"] for row in ledger["entries"]] == [
        op["result_sha256"] for op in metadata
    ]
    permit, evidence = runs[0]
    assert evidence.status == "OBSERVED", evidence.to_dict()["primary_error"]
    assert canonical(phase["execution"]["document"]) == evidence.payload
    assert phase["operation"]["evidence_sha256"] == permit.registration.operation_sha256
    assert phase["original_campaign"]["result"]["state"] == "SEALED_KNOWN"
    assert not phase["original_campaign"]["result"]["quarantine_latched"]
    retained = phase["phase_record"]["document"]
    assert retained["status"] == "RECONNECT_OBSERVATIONS_RETAINED", retained["checks"]
    assert retained["boot_relation"] == "SAME_HOST_SAME_BOOT"
    assert all(row["passed"] for row in retained["checks"])
    for name in (
        "physical_authority",
        "hardware_qualified",
        "canonical_stage_pass",
        "camera_capture_authorized",
    ):
        assert retained[name] is False
    for key, value in before.items():
        if key not in ("schema", "session_head_sha256", "evidence_inventory_sha256"):
            assert current[key] == value, key
    exported, _, _ = _public(
        arrival, usb_service.EXPORT, dict(confirm_metadata_export=True)
    )
    directory = Path(
        exported["result"]["steps"][0]["report"]["metadata_export"]["path"]
    )
    assert (
        directory.parent == arrival.export_directory
        and verify_export(directory)["valid"]
    )
    report = json.loads((directory / "report.json").read_bytes())["snapshot"]
    assert report["schema"] == EXPORT_V5_SCHEMA
    restored = restore_usb_identity_diagnostics(
        report,
        {
            row["attachment"]: (directory / row["attachment"]).read_bytes()
            for row in report["parts"]
        },
    )
    assert restored["qualification_reconnect"] == phase
    fresh = session_fixture(case.workspace)
    perform(fresh, "refresh")
    reopened = read_original(fresh, current["session_header_sha256"])
    assert reopened == current
    identity, _ = adopt_actual_original(fresh, reopened, launch_id="wizard-" + "a" * 32)
    owner = usb_service.PhysicalUsbIdentityService(identity.setup)
    owner.observe_setup()
    assert owner.retained_diagnostics()["qualification_reconnect"] == phase
    for kind, values, _ in forms:
        action = "physical_usb_reconnect_" + kind
        assert owner.blocked_reason(action) is not None
        with pytest.raises(WizardError):
            _ticket(arrival, action, values)
    assert all(row["state"] == "PENDING" for row in fresh.view()["stages"][4:])
    assert len(runs) == 1 and len(case.observations) == 3
    checkpoint(path, case, operations, peers, complete=True)
    receipt = dict(
        schema="rocell.test_usb_reconnect_public_acceptance.v1",
        original_directory=case.session.descriptor()["directory"],
        export_directory=str(directory),
        manifest_sha256=digest((directory / "manifest.json").read_bytes()),
        phase_id=phase["phase_id"],
        phase_sha256=phase["phase_record"]["evidence_sha256"],
        permit_sha256=permit.permit_sha256,
        evidence_sha256=evidence.sha256,
        header_sha256=current["session_header_sha256"],
        head_sha256=current["session_head_sha256"],
        real_original_m1=True,
        real_reconnect_supervisor=True,
        actual_processes=0,
        actual_hardware_queries=0,
        observation_provenance="EXPLICITLY_MODELED",
        physical_authority=False,
    )
    (tmp_path / "reconnect-acceptance.json").write_bytes(canonical(receipt))
    print(json.dumps(receipt, indent=2), flush=True)
