"""Public arm-metadata joins with an injected runner and actual pure codecs.

No Windows query, child process, COM open, camera call or M1 action is executed.
Physical-mode inputs below are explicitly test-owned physical-shaped records;
changing their typed provenance tests a boundary, not received-unit evidence.
"""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time

import pytest

from rocell.application import arrival_wizard_service as arrival
from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_connection_contracts import (
    EvidenceOrigin,
    canonical_sha256,
)
from rocell.application.physical_device_inventory import InventorySource
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.wizard_inventory_fixture import rehearsal_device_inventory
from rocell.application.wizard_native_arm_metadata import (
    decode_controller_snapshot,
    rehearse_native_arm_metadata_snapshot,
    summarize_native_arm_metadata,
)


WORKSPACE = Path(__file__).resolve().parents[3]
PHYSICAL = "inspect_native_arm_metadata"
REHEARSAL = "rehearse_native_arm_metadata"
COUNTERS = (
    "device_open_count",
    "serial_write_count",
    "power_event_count",
    "motion_command_count",
    "contact_command_count",
)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def modeled_physical_snapshot(scenario):
    """Reconstruct exact existing types; never label this test an OS observation."""
    snapshot = decode_controller_snapshot(
        rehearse_native_arm_metadata_snapshot(scenario), "rehearsal"
    )
    batch = replace(
        snapshot.serial_inventory,
        source=InventorySource.PYSERIAL_LIST_PORTS,
        candidates=tuple(
            replace(candidate, source=InventorySource.PYSERIAL_LIST_PORTS)
            for candidate in snapshot.serial_inventory.candidates
        ),
    )
    snapshot = replace(
        snapshot,
        serial_inventory=batch,
        origin=EvidenceOrigin.PHYSICAL_OBSERVATION,
        native_source="WINDOWS_CM_METADATA",
    )
    return json.loads(snapshot.payload())


class FixtureRunner:
    """Only a runner seam; metadata reconstruction/correlation stays production."""

    def __init__(self, mode):
        self.mode = mode
        self.calls = []
        self.snapshots = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.scenario = "nominal"
        self.mutate = None
        self.after = None
        self.outcome = "SUCCEEDED"
        self.failure = None

    def run(self, action_id, values, *, cell_id, cancel, progress):
        self.calls.append((action_id, deepcopy(values)))
        assert not any(key.startswith("_") for key in values)
        if action_id in {"inventory_devices", "rehearse_device_inventory"}:
            report = rehearsal_device_inventory(values.get("scenario", "nominal"))
            if self.mode == "physical":
                report["serial_inventory"]["source"] = "PYSERIAL_LIST_PORTS"
                for candidate in report["serial_inventory"]["candidates"]:
                    candidate["source"] = "PYSERIAL_LIST_PORTS"
                report["report_sha256"] = canonical_sha256(
                    {
                        key: value
                        for key, value in report.items()
                        if key != "report_sha256"
                    }
                )
            step = "metadata_inventory"
        else:
            assert action_id == (PHYSICAL if self.mode == "physical" else REHEARSAL)
            self.entered.set()
            assert self.release.wait(10), "Fixture wait expired; never replayed"
            if self.failure is not None:
                raise self.failure
            if cancel.is_set():
                return self.completion(action_id, "CANCELLED")
            scenario = values.get("scenario", self.scenario)
            report = (
                modeled_physical_snapshot(scenario)
                if self.mode == "physical"
                else rehearse_native_arm_metadata_snapshot(scenario)
            )
            if self.mutate:
                self.mutate(report)
            self.snapshots.append(deepcopy(report))
            step = "native_arm_metadata_snapshot"
        result = {
            "schema": "rocell.wizard_worker_result.v1",
            "action_id": action_id,
            "status": (
                self.outcome if step == "native_arm_metadata_snapshot" else "SUCCEEDED"
            ),
            "steps": [{"name": step, "exit_code": 0, "report": report}],
            **{key: 0 for key in COUNTERS},
            "metadata_inventory_performed": self.mode == "physical",
            "physical_authority": False,
        }
        if step == "native_arm_metadata_snapshot" and self.after:
            self.after(result, cancel)
        return result

    @staticmethod
    def completion(action_id, status):
        return {
            "schema": "rocell.wizard_diagnostic_completion.v1",
            "action_id": action_id,
            "status": status,
            "message": "Injected diagnostic completion; no OS query.",
            "elapsed_s": 0.0,
            "output_limit_exceeded": False,
            "physical_authority": False,
        }


@pytest.fixture
def setup(tmp_path, monkeypatch):
    from rocell.application import physical_device_inventory as inventory
    from rocell.application.physical_camera_session import PhysicalCameraSession
    from rocell.arm.serial_transport import SerialTransport
    from rocell.providers.windows.controller_metadata import (
        WindowsControllerMetadataAcquirer,
    )
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
    from rocell.vision.usb_opencv import UsbOpenCvCamera

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "No actual OS, native, device, process or M1 calls in this lane"
        )

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(WindowsControllerMetadataAcquirer, "__init__", forbidden)
    monkeypatch.setattr(WindowsControllerMetadataAcquirer, "__call__", forbidden)
    monkeypatch.setattr(inventory, "inventory_serial_ports_with_pyserial", forbidden)
    monkeypatch.setattr(inventory.SubprocessArgvCommandRunner, "run", forbidden)
    monkeypatch.setattr(SerialTransport, "connect", forbidden)
    monkeypatch.setattr(UsbOpenCvCamera, "open", forbidden)
    monkeypatch.setattr(WindowsCameraWorkerClient, "probe", forbidden)
    monkeypatch.setattr(WindowsCameraWorkerClient, "capture", forbidden)
    for name in ("initialize", "refresh", "stage_transaction"):
        monkeypatch.setattr(PhysicalCameraSession, name, forbidden)
    source = {"hash": "a" * 64}
    # Host platform is also modeled: Python's uncached platform.system() can
    # otherwise launch `ver` on Windows before the first public view.
    monkeypatch.setattr(arrival.sys, "platform", "win32")
    monkeypatch.setattr(arrival, "source_fingerprint", lambda _: source["hash"])
    services = []

    def make(mode="rehearsal"):
        chosen = tmp_path / ("case-" + str(len(services)))
        chosen.mkdir()
        runner = FixtureRunner(mode)
        service = ArrivalWizardService(
            WORKSPACE,
            mode=mode,
            runner=runner,
            log_directory=chosen / "logs",
            export_directory=chosen / "chosen-exports",
        )
        services.append((service, runner))
        return service, runner, source, chosen

    yield make
    for service, runner in services:
        runner.release.set()
        service.shutdown()


def ticket(service, action_id, **values):
    return service.prepare_action(action_id, values, service.view()["revision"])


def complete(service, receipt):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        operation = service.operation(receipt["operation_id"])
        if operation["status"] not in {"QUEUED", "RUNNING"}:
            return operation
        threading.Event().wait(0.005)
    pytest.fail("Unknown operation outcome; no repeat or extra action")


def action(service, action_id, **values):
    return complete(
        service,
        service.execute_action(ticket(service, action_id, **values)["ticket_id"]),
    )


def generic_review(service):
    physical = service.mode == "physical"
    result = action(
        service,
        "inventory_devices" if physical else "rehearse_device_inventory",
        **({"power_disconnected": True} if physical else {"scenario": "nominal"}),
    )
    assert result["status"] == "SUCCEEDED", result
    candidate = service.view()["device_selection"]["devices"]["SERIAL"]["candidates"][0]
    result = action(
        service,
        "review_arm_candidate",
        choice_id=candidate["choice_id"],
        reviewer_id="generic-arm-reviewer",
        metadata_only=True,
    )
    assert result["status"] == "SUCCEEDED", result
    return service._device_selection.reviewed_candidate("SERIAL")


def inspect_values(service, scenario="nominal"):
    return (
        (PHYSICAL, {"power_disconnected": True, "metadata_only": True})
        if service.mode == "physical"
        else (REHEARSAL, {"scenario": scenario, "metadata_only": True})
    )


def inspect(service, scenario="nominal"):
    name, values = inspect_values(service, scenario)
    return action(service, name, **values)


def correlated(operation):
    result = operation["result"]
    assert result["steps"][0]["name"] == "native_arm_metadata_correlation", result
    return result["steps"][0]["report"]


def export(service):
    result = action(service, "export_logs")
    assert result["status"] == "SUCCEEDED", result
    directory = Path(service.view()["exports"]["items"][-1]["path"])
    assert verify_export(directory)["valid"]
    attachment = directory / "attachment-native-arm-metadata.json"
    return directory, json.loads(attachment.read_bytes())


@pytest.mark.parametrize("mode", ["physical", "rehearsal"])
def test_construct_view_and_preview_are_inert_and_require_current_generic_review(
    setup, mode
):
    service, runner, _, _ = setup(mode)
    assert service.view()["native_arm_metadata"]["status"] == "NOT_INSPECTED"
    assert service.view()["native_arm_metadata"]["report"] is None
    name, values = inspect_values(service)
    assert not next(
        row for row in service.view()["actions"] if row["action_id"] == name
    )["enabled"]
    with pytest.raises(WizardError):
        ticket(service, name, **values)
    assert not runner.calls
    generic_review(service)
    before = deepcopy(runner.calls)
    ticket(service, name, **values)
    assert runner.calls == before
    assert not runner.snapshots


@pytest.mark.parametrize("mode", ["physical", "rehearsal"])
def test_full_public_metadata_join_exact_bindings_and_chosen_export(setup, mode):
    service, runner, source, chosen = setup(mode)
    review = generic_review(service)
    name, values = inspect_values(service)
    prepared = ticket(service, name, **values)
    receipt = service.execute_action(prepared["ticket_id"])
    result = complete(service, receipt)
    assert result["status"] == "SUCCEEDED", result
    assert result["completion_log_persisted"] is True
    assert (
        service.execute_action(prepared["ticket_id"])["operation_id"]
        == receipt["operation_id"]
    )
    assert len(runner.snapshots) == 1
    report = correlated(result)
    assert report["status"] == "METADATA_CORRELATED"
    assert report["snapshot"] == runner.snapshots[0]
    assert (
        report["snapshot_sha256"]
        == decode_controller_snapshot(report["snapshot"], mode).snapshot_sha256
    )
    assert report["binding"] == {
        "mode": mode,
        "session_id": service.session_id,
        "source_sha256": source["hash"],
        "operation_id": receipt["operation_id"],
        "generic_review_sha256": hashlib.sha256(canonical(review)).hexdigest(),
        "generic_report_sha256": review["report_sha256"],
        "generic_candidate_sha256": review["candidate"]["candidate_sha256"],
        "generic_inventory_operation_id": review["operation_id"],
    }
    state = service.view()
    assert state["native_arm_metadata"]["status"] == "CURRENT"
    assert state["native_arm_metadata"]["report"] == summarize_native_arm_metadata(
        report
    )
    assert state["arm"]["status"] == "NOT_CONNECTED"
    assert state["camera"]["status"] == "NOT_CONNECTED"
    assert all(stage["state"] == "PHYSICAL_PENDING" for stage in state["stages"])
    for flag in ("connected", "qualified", "persistent_binding", "physical_authority"):
        assert report[flag] is False
    for flag in ("connected", "qualified", "physical_authority"):
        assert state["native_arm_metadata"][flag] is False
    assert all(report["effects"][key] == 0 for key in COUNTERS)
    directory, retained = export(service)
    assert directory.parent == chosen / "chosen-exports"
    assert retained["schema"] == "rocell.wizard_native_arm_metadata_export.v1"
    assert retained["publication"] == "CURRENT"
    assert retained["source_sha256"] == source["hash"]
    assert retained["session_id"] == service.session_id
    assert retained["result"]["steps"][0]["report"] == report
    assert retained["physical_authority"] is False
    assert len(runner.snapshots) == 1


@pytest.mark.parametrize(
    "scenario", ["missing-fields", "duplicate-mapping", "changed-device", "incomplete"]
)
def test_actual_fixture_faults_are_retained_current_held_metadata_not_authority(
    setup, scenario
):
    service, runner, _, _ = setup()
    generic_review(service)
    result = inspect(service, scenario)
    assert result["status"] == "SUCCEEDED", result
    report = correlated(result)
    assert report["status"] == "HELD"
    assert report["blockers"]
    assert report["snapshot"] == runner.snapshots[-1]
    view = service.view()["native_arm_metadata"]
    assert view["status"] == "CURRENT"  # Current observation, not accepted identity.
    assert view["report"]["status"] == "HELD"
    assert view["qualified"] is False and view["report"]["persistent_binding"] is False


@pytest.mark.parametrize("mode", ["physical", "rehearsal"])
@pytest.mark.parametrize(
    "bad",
    [
        {"metadata_only": False},
        {"metadata_only": 1},
        {"port": "COM91"},
        {"persistent_port_path": "opaque"},
        {"source_sha256": "f" * 64},
        {"_arm_review_sha256": "f" * 64},
    ],
)
def test_no_browser_control_of_native_paths_hashes_or_implicit_consent(
    setup, mode, bad
):
    service, runner, _, _ = setup(mode)
    generic_review(service)
    name, values = inspect_values(service)
    with pytest.raises(WizardError):
        ticket(service, name, **{**values, **bad})
    assert not runner.snapshots


@pytest.mark.parametrize("bad", [1, None])
def test_physical_action_rejects_nonboolean_power_report(setup, bad):
    service, runner, _, _ = setup("physical")
    generic_review(service)
    with pytest.raises(WizardError):
        ticket(service, PHYSICAL, power_disconnected=bad, metadata_only=True)
    assert not runner.snapshots


@pytest.mark.parametrize("mode", ["physical", "rehearsal"])
def test_modes_cannot_substitute_each_others_action(setup, mode):
    service, runner, _, _ = setup(mode)
    generic_review(service)
    wrong = REHEARSAL if mode == "physical" else PHYSICAL
    values = (
        {"scenario": "nominal", "metadata_only": True}
        if wrong == REHEARSAL
        else {"power_disconnected": True, "metadata_only": True}
    )
    with pytest.raises(WizardError):
        ticket(service, wrong, **values)
    assert not runner.snapshots


def test_native_snapshot_survives_rotating_results_and_cached_reads_do_not_replay(
    setup,
):
    service, runner, _, _ = setup()
    generic_review(service)
    operation = inspect(service)
    report = correlated(operation)
    for index in range(9):
        assert (
            action(service, "record_note", note=f"Metadata-only note {index}")["status"]
            == "SUCCEEDED"
        )
    assert operation["operation_id"] not in service._full_results
    for _ in range(3):
        assert service.view()["native_arm_metadata"]["status"] == "CURRENT"
    _, retained = export(service)
    assert retained["result"]["steps"][0]["report"] == report
    assert len(runner.snapshots) == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(unrecognized=True),
        lambda value: value.update(physical_authority=True),
        lambda value: value.update(native_source="WINDOWS_CM_METADATA"),
        lambda value: value["serial_inventory"].update(batch_sha256="f" * 64),
    ],
)
def test_bad_snapshot_is_preserved_but_never_correlated(setup, mutate):
    service, runner, _, _ = setup()
    generic_review(service)
    runner.mutate = mutate
    result = inspect(service)
    assert result["status"] == "FAILED", result
    assert service.view()["native_arm_metadata"]["status"] == "HISTORICAL_HELD"
    assert service.view()["native_arm_metadata"]["report"] is None
    _, retained = export(service)
    assert retained["publication"] == "HISTORICAL_HELD"
    assert retained["result"]["steps"][0]["report"] == runner.snapshots[0]


def test_redaction_preserves_safe_failure_without_claiming_original_wire(setup):
    service, runner, _, _ = setup()
    generic_review(service)
    runner.mutate = lambda value: value["native_observations"][0].update(
        driver_provider="token=arm-secret-value"
    )
    result = inspect(service)
    assert result["status"] == "FAILED", result
    assert result["result"]["code"] == "BOUND_METADATA_REDACTED"
    assert "arm-secret-value" not in json.dumps(result)
    assert service.view()["native_arm_metadata"]["report"] is None
    directory, retained = export(service)
    assert retained["publication"] == "HISTORICAL_HELD"
    assert (
        "arm-secret-value"
        not in (directory / "attachment-native-arm-metadata.json").read_text()
    )


@pytest.mark.parametrize("failure", ["stop", "source", "completion-log"])
def test_late_failure_retains_exact_completed_report_without_current_publication(
    setup, monkeypatch, failure
):
    service, runner, source, _ = setup()
    generic_review(service)
    if failure == "completion-log":
        original = service._log.append

        def fail_finish(kind, details):
            if kind == "ACTION_FINISHED":
                raise OSError("Injected completion log failure")
            return original(kind, details)

        monkeypatch.setattr(service._log, "append", fail_finish)
    else:

        def after(result, cancel):
            if failure == "stop":
                cancel.set()
            else:
                source["hash"] = "b" * 64

        runner.after = after
    operation = inspect(service)
    assert operation["status"] in {"FAILED", "CANCELLED"}, operation
    assert len(runner.snapshots) == 1
    assert service.view()["native_arm_metadata"]["status"] == "HISTORICAL_HELD"
    assert service.view()["native_arm_metadata"]["report"] is None
    if failure == "completion-log":
        monkeypatch.setattr(service._log, "append", original)
    _, retained = export(service)
    assert retained["publication"] == "HISTORICAL_HELD"
    full = retained["result"]["steps"][0]["report"]
    assert full["snapshot"] == runner.snapshots[0]
    assert full["binding"]["source_sha256"] == "a" * 64
    assert len(runner.snapshots) == 1


def test_generic_review_change_revokes_old_ticket_and_retains_original_history(setup):
    service, runner, _, _ = setup()
    original_review = generic_review(service)
    operation = inspect(service)
    report = correlated(operation)
    name, values = inspect_values(service)
    stale = ticket(service, name, **values)
    assert (
        action(
            service,
            "review_arm_candidate",
            choice_id=original_review["candidate"]["choice_id"],
            reviewer_id="different-reviewer",
            metadata_only=True,
        )["status"]
        == "SUCCEEDED"
    )
    assert service.view()["native_arm_metadata"]["status"] == "HISTORICAL_HELD"
    with pytest.raises(WizardError):
        service.execute_action(stale["ticket_id"])
    _, retained = export(service)
    assert retained["publication"] == "HISTORICAL_HELD"
    assert retained["result"]["steps"][0]["report"] == report
    assert len(runner.snapshots) == 1


def test_current_generic_review_changed_at_final_boundary_denies_publication(setup):
    service, runner, _, _ = setup()
    original = generic_review(service)

    def change_review(result, cancel):
        # Fault injection at the service-owned context boundary, not a public
        # concurrent action or implicit source of hardware observations.
        with service._lock:
            service._device_selection.review(
                original["candidate"]["choice_id"], "SERIAL", "changed-in-flight"
            )

    runner.after = change_review
    operation = inspect(service)
    assert operation["status"] == "FAILED", operation
    assert operation["result"]["code"] == "ARM_REVIEW_CHANGED"
    assert service.view()["native_arm_metadata"]["status"] == "HISTORICAL_HELD"
    _, retained = export(service)
    assert retained["publication"] == "HISTORICAL_HELD"
    assert (
        retained["result"]["steps"][0]["report"]["binding"]["generic_review_sha256"]
        == hashlib.sha256(canonical(original)).hexdigest()
    )
    assert len(runner.snapshots) == 1


def test_explicit_stop_during_injected_wait_never_collects_or_replays(setup):
    service, runner, _, _ = setup()
    generic_review(service)
    runner.release.clear()
    name, values = inspect_values(service)
    receipt = service.execute_action(ticket(service, name, **values)["ticket_id"])
    assert runner.entered.wait(2)
    assert action(service, "stop_operation")["status"] == "SUCCEEDED"
    runner.release.set()
    result = complete(service, receipt)
    assert result["status"] == "CANCELLED", result
    assert not runner.snapshots
    assert service.view()["native_arm_metadata"]["status"] == "HISTORICAL_HELD"


def test_direct_export_observes_source_drift_and_keeps_original_source(setup):
    service, runner, source, _ = setup()
    generic_review(service)
    report = correlated(inspect(service))
    source["hash"] = "b" * 64
    _, retained = export(service)
    assert retained["publication"] == "HISTORICAL_HELD"
    assert retained["source_sha256"] == "a" * 64
    assert retained["result"]["steps"][0]["report"] == report
    assert len(runner.snapshots) == 1


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "TIMED_OUT"])
def test_supervisor_terminal_completion_is_retained_not_a_metadata_success(
    setup, status
):
    service, runner, _, _ = setup()
    generic_review(service)

    def completion(result, cancel):
        if status == "FAILED":
            result["status"] = "FAILED"
            result["steps"][0]["exit_code"] = 1
            return
        replacement = runner.completion(REHEARSAL, status)
        result.clear()
        result.update(replacement)

    runner.after = completion
    operation = inspect(service)
    assert operation["status"] == status, operation
    assert service.view()["native_arm_metadata"]["status"] == "HISTORICAL_HELD"
    assert service.view()["native_arm_metadata"]["report"] is None
    _, retained = export(service)
    assert retained["publication"] == "HISTORICAL_HELD"
    if status == "FAILED":
        assert retained["result"]["status"] == "FAILED"
        assert retained["result"]["steps"][0]["report"] == runner.snapshots[0]
    else:
        assert retained["result"] == runner.completion(REHEARSAL, status)
    assert len(runner.snapshots) == 1


@pytest.mark.parametrize("field", [*COUNTERS, "physical_authority"])
def test_worker_claim_of_device_effect_is_rejected_before_correlation(setup, field):
    service, runner, _, _ = setup()
    generic_review(service)
    runner.after = lambda result, cancel: result.update(
        {field: True if field == "physical_authority" else 1}
    )
    operation = inspect(service)
    assert operation["status"] == "FAILED", operation
    assert service.view()["native_arm_metadata"]["report"] is None
    assert service.view()["native_arm_metadata"]["status"] == "HISTORICAL_HELD"
    assert len(runner.snapshots) == 1


def test_intent_log_failure_retires_previous_current_report_without_new_dispatch(
    setup, monkeypatch
):
    service, runner, _, _ = setup()
    generic_review(service)
    report = correlated(inspect(service))
    original = service._log.append

    def fail_intent(kind, details):
        if kind == "ACTION_EXECUTED":
            raise OSError("Injected intent logging failure")
        return original(kind, details)

    monkeypatch.setattr(service._log, "append", fail_intent)
    result = inspect(service)
    assert result["status"] == "FAILED", result
    assert len(runner.snapshots) == 1
    assert service.view()["native_arm_metadata"]["status"] == "HISTORICAL_HELD"
    monkeypatch.setattr(service._log, "append", original)
    _, retained = export(service)
    assert retained["publication"] == "HISTORICAL_HELD"
    assert retained["result"]["steps"][0]["report"] == report


def test_generic_inventory_refresh_invalidates_metadata_even_when_collection_fails(
    setup,
):
    service, runner, _, _ = setup()
    generic_review(service)
    report = correlated(inspect(service))
    result = action(service, "rehearse_device_inventory", scenario="partial-inventory")
    assert result["status"] == "FAILED", result
    assert service.view()["native_arm_metadata"]["status"] == "HISTORICAL_HELD"
    assert service.view()["device_selection"]["devices"]["SERIAL"]["review"] is None
    _, retained = export(service)
    assert retained["publication"] == "HISTORICAL_HELD"
    assert retained["result"]["steps"][0]["report"] == report
    assert len(runner.snapshots) == 1


def test_detached_view_and_operation_mutation_cannot_rewrite_exported_original(setup):
    service, runner, _, _ = setup()
    generic_review(service)
    operation = inspect(service)
    report = deepcopy(correlated(operation))
    operation["result"]["steps"][0]["report"]["snapshot"]["native_source"] = "FORGED"
    view = service.view()
    view["native_arm_metadata"]["report"]["status"] = "FORGED"
    view["native_arm_metadata"]["report"]["binding"]["source_sha256"] = "f" * 64
    assert service.view()["native_arm_metadata"][
        "report"
    ] == summarize_native_arm_metadata(report)
    _, retained = export(service)
    assert retained["result"]["steps"][0]["report"] == report
    assert len(runner.snapshots) == 1


def test_source_change_before_execution_refuses_old_ticket_without_native_dispatch(
    setup,
):
    service, runner, source, _ = setup()
    generic_review(service)
    name, values = inspect_values(service)
    prepared = ticket(service, name, **values)
    source["hash"] = "b" * 64
    with pytest.raises(WizardError):
        service.execute_action(prepared["ticket_id"])
    assert not runner.snapshots
    assert service.view()["native_arm_metadata"]["status"] == "HISTORICAL_HELD"
