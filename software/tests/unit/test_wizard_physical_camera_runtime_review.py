"""Independent public file-review/retention tests, never native or device tests.

Integration uses the actual inspector on the fixed installed development files.
Only the workspace-fingerprint seam is fixed for test isolation. No report is
fabricated, and file agreement is not received-camera or runtime qualification.
"""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from rocell.application import arrival_wizard_service as arrival
from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.native_camera_protocol import canonical


WORKSPACE = Path(__file__).resolve().parents[3]
INSPECT = "physical_camera_runtime_inspect"
REVIEW = "physical_camera_runtime_review"
INSPECT_INPUT = {"operator_id": "file-operator", "file_inspection_only": True}
REVIEW_INPUT = {"reviewer_id": "file-reviewer", "file_review_only": True}


@pytest.fixture
def smoke():
    path = WORKSPACE / "software/scripts/wizard_physical_camera_runtime_smoke.py"
    spec = importlib.util.spec_from_file_location(
        "runtime_review_smoke_under_test", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ActionService:
    """Script-only terminal operation model; no application/store implementation."""

    def __init__(self, smoke):
        self.calls = []
        self.current_name = None
        self.outcome = {
            "operation_id": "modeled-operation",
            "status": "SUCCEEDED",
            "result_sha256": "a" * 64,
            "completion_log_persisted": True,
            "result": {
                "physical_authority": False,
                "metadata_inventory_performed": False,
                **{key: 0 for key in smoke.ZERO_COUNTERS},
            },
        }
        self.export_outcome = deepcopy(self.outcome)
        self.export_outcome["operation_id"] = "modeled-export"
        self.export_outcome["result"]["receipt"] = {
            "path": "modeled/export/path",
            "valid": True,
            "status": "VERIFIED_DIAGNOSTIC_ONLY",
            "manifest_sha256": "b" * 64,
        }

    def view(self):
        return {"revision": 4}

    def prepare_action(self, name, values, revision):
        self.calls.append(("prepare", name, deepcopy(values), revision))
        self.current_name = name
        return {"ticket_id": "modeled-ticket", "effects": ["FILE_READ_ONLY"]}

    def execute_action(self, ticket):
        self.calls.append(("execute", ticket))
        return {
            "operation_id": (
                "modeled-export"
                if self.current_name == "export_logs"
                else "modeled-operation"
            )
        }

    def operation(self, operation_id):
        self.calls.append(("operation", operation_id))
        return deepcopy(
            self.export_outcome if self.current_name == "export_logs" else self.outcome
        )


@pytest.mark.parametrize(
    "name",
    [
        "physical_camera_initialize",
        "native_camera_inventory",
        "physical_camera_probe",
        "physical_camera_capture",
        "arm_connect",
        "run_baseline",
    ],
)
def test_smoke_refuses_every_action_outside_fixed_file_workflow(smoke, name):
    service = ActionService(smoke)
    with pytest.raises(RuntimeError, match="closed file-only"):
        smoke.action(service, name)
    assert service.calls == []


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "TIMED_OUT"])
def test_smoke_terminal_failure_exports_once_without_replay(smoke, status):
    service = ActionService(smoke)
    service.outcome["status"] = status
    with pytest.raises(smoke.TerminalActionFailure, match="no action replay") as error:
        smoke.action(service, INSPECT, INSPECT_INPUT)
    assert [row[1] for row in service.calls if row[0] == "prepare"] == [
        INSPECT,
        "export_logs",
    ]
    assert len([row for row in service.calls if row[0] == "execute"]) == 2
    assert error.value.operation == service.outcome
    assert error.value.failure_export_attempted is True
    assert error.value.failure_export_operation == service.export_outcome
    assert error.value.failure_export_error is None


@pytest.mark.parametrize("export_status", ["FAILED", "CANCELLED", "TIMED_OUT"])
def test_smoke_failed_export_is_secondary_and_never_recursive(smoke, export_status):
    service = ActionService(smoke)
    service.outcome["status"] = "FAILED"
    service.export_outcome["status"] = export_status
    with pytest.raises(smoke.TerminalActionFailure) as error:
        smoke.action(service, INSPECT, INSPECT_INPUT)
    assert error.value.operation == service.outcome
    assert error.value.failure_export_operation == service.export_outcome
    assert isinstance(error.value.failure_export_error, smoke.TerminalActionFailure)
    assert [row[1] for row in service.calls if row[0] == "prepare"] == [
        INSPECT,
        "export_logs",
    ]


def test_smoke_rejected_export_preserves_original_terminal_failure(smoke):
    service = ActionService(smoke)
    service.outcome["status"] = "FAILED"
    original_prepare = service.prepare_action
    rejected = ValueError("Modeled export preparation rejection")

    def reject(name, values, revision):
        if name == "export_logs":
            service.calls.append(("prepare", name, deepcopy(values), revision))
            raise rejected
        return original_prepare(name, values, revision)

    service.prepare_action = reject
    with pytest.raises(smoke.TerminalActionFailure) as error:
        smoke.action(service, INSPECT, INSPECT_INPUT)
    assert error.value.operation == service.outcome
    assert error.value.failure_export_error is rejected
    assert error.value.failure_export_operation is None
    assert [row[1] for row in service.calls if row[0] == "prepare"] == [
        INSPECT,
        "export_logs",
    ]
    assert len([row for row in service.calls if row[0] == "execute"]) == 1


def test_smoke_unknown_export_preserves_failure_without_claiming_saved_bundle(
    smoke, monkeypatch, capsys
):
    service = ActionService(smoke)
    service.outcome["status"] = "FAILED"
    service.export_outcome["status"] = "RUNNING"
    clock = iter([0, 1, 2, 93])
    monkeypatch.setattr(smoke.time, "monotonic", lambda: next(clock))
    with pytest.raises(smoke.TerminalActionFailure) as error:
        smoke.action(service, INSPECT, INSPECT_INPUT)
    assert error.value.operation == service.outcome
    assert isinstance(error.value.failure_export_error, smoke.ActionOutcomeUnknown)
    assert error.value.failure_export_operation is None
    assert [row[1] for row in service.calls if row[0] == "prepare"] == [
        INSPECT,
        "export_logs",
    ]
    output = capsys.readouterr().out
    assert '"export_outcome": "UNKNOWN"' in output
    assert "failure diagnostic export retained" not in output


def test_smoke_direct_export_failure_cannot_export_itself(smoke):
    service = ActionService(smoke)
    service.export_outcome["status"] = "FAILED"
    with pytest.raises(smoke.TerminalActionFailure) as error:
        smoke.action(service, "export_logs")
    assert error.value.operation == service.export_outcome
    assert error.value.failure_export_attempted is False
    assert [row[1] for row in service.calls if row[0] == "prepare"] == ["export_logs"]


@pytest.mark.parametrize("value", [1, False, None])
def test_smoke_rejects_nonzero_boolean_or_missing_effect_counts(smoke, value):
    service = ActionService(smoke)
    service.outcome["result"]["device_open_count"] = value
    with pytest.raises(RuntimeError, match="effect count"):
        smoke.action(service, INSPECT, INSPECT_INPUT)


def test_smoke_unknown_running_outcome_does_not_submit_export_or_retry(
    smoke, monkeypatch
):
    service = ActionService(smoke)
    service.outcome["status"] = "RUNNING"
    clock = iter([0, 91])
    monkeypatch.setattr(smoke.time, "monotonic", lambda: next(clock))
    with pytest.raises(TimeoutError, match="outcome unknown"):
        smoke.action(service, INSPECT, INSPECT_INPUT)
    assert [row[0] for row in service.calls] == ["prepare", "execute"]


def test_smoke_source_mismatch_precedes_application_construction(smoke, monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["runtime-smoke", "--expected-source-sha256", "a" * 64]
    )
    monkeypatch.setattr(smoke, "source_fingerprint", lambda _: "b" * 64)
    monkeypatch.setattr(
        smoke,
        "ArrivalWizardService",
        lambda *_a, **_k: pytest.fail("No launch on wrong source"),
    )
    with pytest.raises(RuntimeError, match="Freeze mismatch before launch"):
        smoke.main()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    from rocell.application import physical_camera_acquisition_service as acquisition
    from rocell.application import physical_device_inventory as inventory
    from rocell.application import physical_camera_runtime_inspection as inspector
    from rocell.arm.serial_transport import SerialTransport
    from rocell.application.physical_camera_session import PhysicalCameraSession
    from rocell.application.physical_device_inventory import SubprocessArgvCommandRunner
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
    from rocell.providers.windows.owned_native_camera_runner import (
        OwnedNativeCameraRunner,
    )
    from rocell.vision.usb_opencv import UsbOpenCvCamera

    # Inert status must not depend on platform.uname() having been warmed by an
    # earlier test. Its Windows version fallback can spawn a shell subprocess.
    import platform

    monkeypatch.setattr(platform, "_uname_cache", None)

    def forbidden(*_args, **_kwargs):
        pytest.fail(
            "Native/device/inventory/M1 operation forbidden in file-review tests"
        )

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(OwnedNativeCameraRunner, "run", forbidden)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, forbidden)
    for name in ("initialize", "refresh", "stage_transaction"):
        monkeypatch.setattr(PhysicalCameraSession, name, forbidden)
    monkeypatch.setattr(SubprocessArgvCommandRunner, "run", forbidden)
    monkeypatch.setattr(inventory, "inventory_serial_ports_with_pyserial", forbidden)
    monkeypatch.setattr(SerialTransport, "connect", forbidden)
    monkeypatch.setattr(UsbOpenCvCamera, "open", forbidden)
    source = {"hash": "a" * 64}
    monkeypatch.setattr(arrival, "source_fingerprint", lambda _: source["hash"])
    monkeypatch.setattr(inspector, "source_fingerprint", lambda _: source["hash"])
    actual = inspector.inspect_physical_camera_runtime_pair
    calls, reports, services = [], [], []
    hook = {"after": None}

    def inspect(workspace, **kwargs):
        calls.append(
            deepcopy(
                {
                    key: value
                    for key, value in kwargs.items()
                    if key not in {"cancellation", "progress"}
                }
            )
        )
        report = actual(workspace, **kwargs)
        reports.append(report)
        if hook["after"]:
            hook["after"](kwargs, report)
        return report

    monkeypatch.setattr(acquisition, "inspect_physical_camera_runtime_pair", inspect)

    def make(mode="physical"):
        export_workspace = tmp_path / ("case-" + str(len(services)))
        export_workspace.mkdir()
        (export_workspace / "software/runs").mkdir(parents=True)
        service = ArrivalWizardService(
            WORKSPACE,
            mode=mode,
            log_directory=export_workspace / "logs",
            export_directory=export_workspace / "software/runs/wizard-exports",
        )
        services.append(service)
        return service, calls, reports, hook, source, export_workspace

    yield make
    for service in services:
        service.shutdown()


def prepare(service, name, values):
    return service.prepare_action(name, values, service.view()["revision"])


def complete(service, receipt):
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        result = service.operation(receipt["operation_id"])
        if result["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            return result
        threading.Event().wait(0.005)
    pytest.fail("Original outcome unknown; test does not replay")


def action(service, name, values=None):
    return complete(
        service,
        service.execute_action(prepare(service, name, values or {})["ticket_id"]),
    )


def successful(service, name, values=None):
    result = action(service, name, values)
    assert result["status"] == "SUCCEEDED", result
    assert result["completion_log_persisted"] is True
    return result


def runtime_view(service):
    return service.view()["physical_camera"]["runtime_inspection"]


def read_export(smoke, setup_values, *, report, review, publication):
    service, _, _, _, _, export_workspace = setup_values
    exported = successful(service, "export_logs")
    return smoke.verify_runtime_export(
        exported["result"]["receipt"],
        workspace=export_workspace,
        expected_source_sha256=service.source_sha256,
        launch_session_id=service.session_id,
        probe_candidate=service._physical_camera.probe_runtime,
        capture_candidate=service._physical_camera.capture_runtime,
        expected_report_sha256=report.sha256,
        expected_review=review,
        expected_document=report.to_dict(),
        publication=publication,
    )


def test_constructor_views_and_preview_are_inert_and_physical_only(setup, smoke):
    service, calls, _, _, _, _ = setup()
    initial_setup = service.view()["physical_camera_setup"]
    for _ in range(3):
        assert runtime_view(service)["status"] == "NOT_INSPECTED"
        smoke.assert_no_hardware(service.view(), initial_setup=initial_setup)
    ticket = prepare(service, INSPECT, INSPECT_INPUT)
    assert ticket["physical_authority"] is False and calls == []
    assert not service._physical_camera.directory.exists()
    rehearsal, _, _, _, _, _ = setup("rehearsal")
    for name, values in ((INSPECT, INSPECT_INPUT), (REVIEW, REVIEW_INPUT)):
        with pytest.raises(WizardError):
            prepare(rehearsal, name, values)
    assert calls == []


@pytest.mark.parametrize(
    "bad",
    [
        {"file_inspection_only": False},
        {"file_inspection_only": 1},
        {"operator_id": ""},
        {"path": "some-helper.exe"},
        {"expected_sha256": "b" * 64},
        {"scenario": "nominal"},
        {"dispatch_enabled": True},
    ],
)
def test_inspection_inputs_are_closed_without_default_consent(setup, bad):
    service, calls, *_ = setup()
    with pytest.raises(WizardError):
        prepare(service, INSPECT, {**INSPECT_INPUT, **bad})
    assert calls == []


def test_actual_inspection_review_and_eviction_preserve_full_export(setup, smoke):
    values = setup()
    service, calls, reports, *_ = values
    initial_setup = service.view()["physical_camera_setup"]
    ticket = prepare(service, INSPECT, INSPECT_INPUT)
    receipt = service.execute_action(ticket["ticket_id"])
    inspected = complete(service, receipt)
    assert inspected["status"] == "SUCCEEDED", inspected
    assert (
        service.execute_action(ticket["ticket_id"])["operation_id"]
        == receipt["operation_id"]
    )
    assert len(calls) == 1
    report = reports[0]
    retained = inspected["result"]["steps"][0]["report"]
    assert retained["inspection"] == report.to_dict()
    assert retained["inspection_sha256"] == report.sha256
    assert retained["review"] is None
    assert runtime_view(service)["inspection"] == report.safe_summary()
    baseline = smoke.verify_installed_baseline(report)
    assert baseline["probe"]["source_status"] == "GAPS"
    assert baseline["capture"] == report.to_dict()["purposes"]["capture"]
    for label in ("file-operator", "FILE-OPERATOR"):
        with pytest.raises(WizardError):
            prepare(service, REVIEW, {**REVIEW_INPUT, "reviewer_id": label})
    reviewed = successful(service, REVIEW, REVIEW_INPUT)
    state = runtime_view(service)
    assert state["status"] == "REVIEW_RECORDED"
    review = state["review"]
    assert review["inspection_sha256"] == report.sha256
    assert review["review_operation_id"] == reviewed["operation_id"]
    assert review["distinct_operator_labels"] is True
    assert review["status"] == "ACKNOWLEDGED_HELD_REPORT"
    assert len(calls) == 1
    for index in range(9):
        successful(
            service,
            "record_note",
            {
                "note": f"File-only independent retention test {index}; no physical evidence."
            },
        )
    assert service.operation(inspected["operation_id"])["result"] is None
    assert service.operation(reviewed["operation_id"])["result"] is None
    assert runtime_view(service) == state
    restored, checked = read_export(
        smoke, values, report=report, review=review, publication="CURRENT_FILE_REPORT"
    )
    assert (
        restored.payload == report.payload and checked["attachment_bytes"] < 256 * 1024
    )
    assert len(calls) == 1
    smoke.assert_no_hardware(service.view(), initial_setup=initial_setup)


def test_new_inspection_retires_old_review_and_stales_review_ticket(setup):
    service, calls, _, hook, *_ = setup()
    successful(service, INSPECT, INSPECT_INPUT)
    pending = prepare(service, REVIEW, REVIEW_INPUT)
    successful(service, REVIEW, REVIEW_INPUT)
    seen = []
    hook["after"] = lambda *_: seen.append(runtime_view(service))
    successful(service, INSPECT, INSPECT_INPUT)
    assert seen and seen[0]["review"] is None
    assert runtime_view(service)["review"] is None
    with pytest.raises(WizardError):
        service.execute_action(pending["ticket_id"])
    assert len(calls) == 2


@pytest.mark.parametrize("fault", ["source", "stop"])
def test_late_source_or_stop_retains_exact_historical_inspection(setup, smoke, fault):
    values = setup()
    service, calls, reports, hook, source, _ = values

    def after(kwargs, _report):
        if fault == "source":
            source["hash"] = "b" * 64
        else:
            kwargs["cancellation"].set()

    hook["after"] = after
    result = action(service, INSPECT, INSPECT_INPUT)
    assert result["status"] in {"FAILED", "CANCELLED", "TIMED_OUT"}, result
    assert len(calls) == len(reports) == 1
    assert runtime_view(service)["status"] == "HISTORICAL_HELD"
    assert runtime_view(service)["review"] is None
    restored, _ = read_export(
        smoke, values, report=reports[0], review=None, publication="HISTORICAL_HELD"
    )
    assert restored.payload == reports[0].payload


@pytest.mark.parametrize("name", [INSPECT, REVIEW])
def test_completion_log_failure_never_publishes_current_review(
    setup, smoke, monkeypatch, name
):
    values = setup()
    service, _, reports, *_ = values
    if name == REVIEW:
        successful(service, INSPECT, INSPECT_INPUT)
    append = service._log.append

    def fail(kind, details):
        if kind == "ACTION_FINISHED":
            raise OSError("Modeled logging failure; no device operation")
        return append(kind, details)

    monkeypatch.setattr(service._log, "append", fail)
    result = action(service, name, INSPECT_INPUT if name == INSPECT else REVIEW_INPUT)
    assert result["status"] == "FAILED", result
    assert runtime_view(service)["status"] == "HISTORICAL_HELD"
    assert runtime_view(service)["review"] is None
    monkeypatch.setattr(service._log, "append", append)
    restored, _ = read_export(
        smoke, values, report=reports[-1], review=None, publication="HISTORICAL_HELD"
    )
    assert restored.payload == reports[-1].payload


def test_direct_export_after_source_drift_withdraws_current_review_without_reinspection(
    setup, smoke
):
    values = setup()
    service, calls, reports, _, source, _ = values
    successful(service, INSPECT, INSPECT_INPUT)
    successful(service, REVIEW, REVIEW_INPUT)
    review = runtime_view(service)["review"]
    source["hash"] = "b" * 64
    restored, _ = read_export(
        smoke, values, report=reports[0], review=review, publication="HISTORICAL_HELD"
    )
    assert restored.payload == reports[0].payload and len(calls) == 1
    assert runtime_view(service)["status"] == "HISTORICAL_HELD"


@pytest.mark.parametrize(
    "bad",
    [
        {"file_review_only": False},
        {"file_review_only": 1},
        {"reviewer_id": ""},
        {"inspection_sha256": "f" * 64},
        {"runtime_path": "some-helper.exe"},
        {"accept_runtime": True},
    ],
)
def test_review_inputs_cannot_supply_trust_or_implicit_consent(setup, bad):
    service, calls, *_ = setup()
    successful(service, INSPECT, INSPECT_INPUT)
    before = runtime_view(service)
    with pytest.raises(WizardError):
        prepare(service, REVIEW, {**REVIEW_INPUT, **bad})
    assert runtime_view(service) == before and len(calls) == 1


@pytest.mark.parametrize("fault", ["raise", "alter_bound_hash"])
def test_result_validation_failure_preserves_original_but_never_current(
    setup, smoke, monkeypatch, fault
):
    values = setup()
    service, _, reports, *_ = values
    validate = service._validated_result

    def altered(action_id, value):
        if action_id != INSPECT:
            return validate(action_id, value)
        if fault == "raise":
            raise WizardError("RESULT_RETENTION_LIMIT", "Modeled validation failure")
        result = validate(action_id, value)
        result["steps"][0]["report"]["inspection_sha256"] = "f" * 64
        return result

    monkeypatch.setattr(service, "_validated_result", altered)
    result = action(service, INSPECT, INSPECT_INPUT)
    assert result["status"] == "FAILED", result
    assert runtime_view(service)["status"] == "HISTORICAL_HELD"
    assert runtime_view(service)["review"] is None
    monkeypatch.setattr(service, "_validated_result", validate)
    restored, _ = read_export(
        smoke, values, report=reports[0], review=None, publication="HISTORICAL_HELD"
    )
    assert restored.payload == reports[0].payload


def test_review_views_and_export_do_not_reinspect_native_files(
    setup, smoke, monkeypatch
):
    values = setup()
    service, calls, reports, *_ = values
    successful(service, INSPECT, INSPECT_INPUT)
    original_open, original_stat = Path.open, Path.stat
    native_root = WORKSPACE / "software/native/windows_camera"

    def guarded_open(path, *args, **kwargs):
        assert not path.is_relative_to(native_root), "Implicit native-file reread"
        return original_open(path, *args, **kwargs)

    def guarded_stat(path, *args, **kwargs):
        assert not path.is_relative_to(
            native_root
        ), "Implicit native-file metadata query"
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(Path, "stat", guarded_stat)
    for _ in range(3):
        assert runtime_view(service)["inspection"] == reports[0].safe_summary()
    ticket = prepare(service, REVIEW, REVIEW_INPUT)
    reviewed = complete(service, service.execute_action(ticket["ticket_id"]))
    assert reviewed["status"] == "SUCCEEDED", reviewed
    review = runtime_view(service)["review"]
    restored, _ = read_export(
        smoke,
        values,
        report=reports[0],
        review=review,
        publication="CURRENT_FILE_REPORT",
    )
    assert restored.payload == reports[0].payload and len(calls) == 1


@pytest.mark.parametrize(
    "fault", ["report_hash", "manifest_hash", "document", "source", "launch"]
)
def test_export_checker_refuses_changed_original_identity_or_document(
    setup, smoke, fault
):
    values = setup()
    service, _, reports, _, _, export_workspace = values
    successful(service, INSPECT, INSPECT_INPUT)
    report = reports[0]
    exported = successful(service, "export_logs")["result"]["receipt"]
    options = {
        "workspace": export_workspace,
        "expected_source_sha256": service.source_sha256,
        "launch_session_id": service.session_id,
        "probe_candidate": service._physical_camera.probe_runtime,
        "capture_candidate": service._physical_camera.capture_runtime,
        "expected_report_sha256": report.sha256,
        "expected_review": None,
        "expected_document": report.to_dict(),
    }
    if fault == "report_hash":
        options["expected_report_sha256"] = "f" * 64
    elif fault == "manifest_hash":
        exported["manifest_sha256"] = "f" * 64
    elif fault == "document":
        options["expected_document"]["binding"]["operator_id"] = "another-operator"
    elif fault == "source":
        options["expected_source_sha256"] = "f" * 64
    else:
        options["launch_session_id"] = "wizard-" + "f" * 32
    with pytest.raises((ValueError, RuntimeError)):
        smoke.verify_runtime_export(exported, **options)


def test_smoke_known_failure_exports_actual_original_report_on_same_live_service(
    setup, smoke, capsys
):
    service, calls, reports, hook, _, export_workspace = setup()
    hook["after"] = lambda kwargs, _report: kwargs["cancellation"].set()
    with pytest.raises(smoke.TerminalActionFailure) as error:
        smoke.action(service, INSPECT, INSPECT_INPUT)
    original = error.value
    assert original.operation["status"] == "CANCELLED"
    assert original.failure_export_attempted is True
    assert original.failure_export_error is None
    assert original.failure_export_operation["status"] == "SUCCEEDED"
    assert not service._closed
    assert [row["action_id"] for row in service._operations.values()] == [
        INSPECT,
        "export_logs",
    ]
    assert len(calls) == len(reports) == 1
    report = reports[0]
    restored, checked = smoke.verify_runtime_export(
        original.failure_export_operation["result"]["receipt"],
        workspace=export_workspace,
        expected_source_sha256=service.source_sha256,
        launch_session_id=service.session_id,
        probe_candidate=service._physical_camera.probe_runtime,
        capture_candidate=service._physical_camera.capture_runtime,
        expected_report_sha256=report.sha256,
        expected_review=None,
        expected_document=report.to_dict(),
        publication="HISTORICAL_HELD",
    )
    assert restored.payload == report.payload
    output = capsys.readouterr().out
    assert "failure diagnostic export retained" in output
    assert json.dumps(checked["path"])[1:-1] in output
    assert '"valid": true' in output
