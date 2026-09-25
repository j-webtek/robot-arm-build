"""Public helper-registration workflow; no native execution or device access.

Physical-mode coverage reads only the repository's fixed catalogued files.
All endpoint metadata in this lane comes from incapable rehearsal providers.
"""

from pathlib import Path
import threading
import time

import pytest

from rocell.application import arrival_wizard_service as module
from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_camera_helper_inspection import (
    CameraHelperInspectionError,
    create_metadata_provider,
    inspect_camera_helper,
)
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.wizard_inventory_fixture import rehearsal_device_inventory


WORKSPACE = Path(__file__).resolve().parents[3]


class FixtureInventory:
    def run(self, action_id, values, **kwargs):
        assert action_id == "rehearse_device_inventory"
        return {
            "schema": "rocell.wizard_worker_result.v1",
            "action_id": action_id,
            "status": "SUCCEEDED",
            "steps": [
                {
                    "name": "metadata_inventory",
                    "exit_code": 0,
                    "report": rehearsal_device_inventory(values["scenario"]),
                }
            ],
            "device_open_count": 0,
            "serial_write_count": 0,
            "power_event_count": 0,
            "motion_command_count": 0,
            "contact_command_count": 0,
            "metadata_inventory_performed": False,
            "physical_authority": False,
        }


class Inspector:
    def __init__(self):
        self.calls = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.failure = None

    def __call__(self, workspace, **kwargs):
        self.calls.append(kwargs)
        self.entered.set()
        assert self.release.wait(10), "Fixture deadline; never replay"
        if self.failure:
            raise self.failure
        return inspect_camera_helper(workspace, **kwargs)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    from rocell.providers.windows import camera_worker_client as native
    from rocell.application import physical_device_inventory as inventory
    from rocell.arm.serial_transport import SerialTransport
    from rocell.vision.usb_opencv import UsbOpenCvCamera

    def forbidden(*args, **kwargs):
        raise AssertionError("Native/OS/device actions forbidden in helper tests")

    monkeypatch.setattr(native.subprocess, "Popen", forbidden)
    monkeypatch.setattr(
        native.WindowsCameraWorkerClient, "enumerate_metadata", forbidden
    )
    monkeypatch.setattr(
        native.WindowsCameraWorkerClient, "resolve_identity_metadata", forbidden
    )
    monkeypatch.setattr(native.WindowsCameraWorkerClient, "probe", forbidden)
    monkeypatch.setattr(native.WindowsCameraWorkerClient, "capture", forbidden)
    monkeypatch.setattr(inventory.SubprocessArgvCommandRunner, "run", forbidden)
    monkeypatch.setattr(inventory, "inventory_serial_ports_with_pyserial", forbidden)
    monkeypatch.setattr(SerialTransport, "connect", forbidden)
    monkeypatch.setattr(UsbOpenCvCamera, "open", forbidden)
    source = {"hash": "a" * 64}
    monkeypatch.setattr(module, "source_fingerprint", lambda _: source["hash"])
    services = []

    def create(mode="rehearsal", factory=None):
        inspector = Inspector()
        service = ArrivalWizardService(
            WORKSPACE,
            mode=mode,
            runner=FixtureInventory(),
            helper_inspector=inspector,
            helper_provider_factory=factory,
            log_directory=tmp_path / "logs",
            export_directory=tmp_path / "exports",
        )
        services.append((service, inspector))
        return service, inspector, source

    yield create
    for service, inspector in services:
        inspector.release.set()
        service.shutdown()


def prepare(service, name, **values):
    return service.prepare_action(name, values, service.view()["revision"])


def complete(service, receipt):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = service.operation(receipt["operation_id"])
        if result["status"] not in {"QUEUED", "RUNNING"}:
            return result
        threading.Event().wait(0.005)
    pytest.fail("Operation did not finish; never replayed")


def action(service, name, **values):
    return complete(
        service, service.execute_action(prepare(service, name, **values)["ticket_id"])
    )


def inspect(service, scenario="nominal", operator="operator"):
    values = {"operator_id": operator, "metadata_only": True}
    if service.mode == "rehearsal":
        values["scenario"] = scenario
    return action(service, "camera_helper_inspect", **values)


def register(service, scenario="nominal"):
    assert inspect(service, scenario)["status"] == "SUCCEEDED"
    return action(
        service, "camera_helper_review", reviewer_id="reviewer", metadata_only=True
    )


def generic_review(service):
    assert (
        action(service, "rehearse_device_inventory", scenario="nominal")["status"]
        == "SUCCEEDED"
    )
    candidate = service.view()["device_selection"]["devices"]["CAMERA"]["candidates"][0]
    assert (
        action(
            service,
            "review_camera_candidate",
            choice_id=candidate["choice_id"],
            reviewer_id="generic-reviewer",
            metadata_only=True,
        )["status"]
        == "SUCCEEDED"
    )


@pytest.mark.parametrize("mode", ["rehearsal", "physical"])
def test_startup_views_and_preview_never_inspect_or_execute(setup, mode):
    service, inspector, _ = setup(mode)
    for _ in range(3):
        view = service.view()
        assert view["camera_helper_registration"]["status"] == "NO_INSPECTION"
    values = {"operator_id": "operator", "metadata_only": True}
    if mode == "rehearsal":
        values["scenario"] = "nominal"
    pending = prepare(service, "camera_helper_inspect", **values)
    assert "fixed catalogued files" in " ".join(pending["effects"])
    assert inspector.calls == []
    assert view["diagnostics"]["event_count"] == 0
    assert view["camera"]["status"] == "NOT_CONNECTED"


@pytest.mark.parametrize("scenario", ["nominal", "missing-helper", "hash-drift"])
def test_inspection_and_review_register_only_eligible_metadata(setup, scenario):
    service, inspector, _ = setup()
    result = register(service, scenario)
    assert result["status"] == "SUCCEEDED", result
    view = service.view()["camera_helper_registration"]
    eligible = scenario == "nominal"
    assert view["status"] == (
        "METADATA_HELPER_REGISTERED" if eligible else "REVIEW_HELD"
    )
    assert (service._native_camera_provider is not None) is eligible
    assert (service._camera_helper.registration() is not None) is eligible
    assert len(inspector.calls) == 1
    assert result["result"]["metadata_inventory_performed"] is False
    assert all(row["state"] == "PHYSICAL_PENDING" for row in service.view()["stages"])
    assert service.view()["camera"]["status"] == "NOT_CONNECTED"
    assert action(service, "export_logs")["status"] == "SUCCEEDED"
    exported = service.view()["exports"]["items"][-1]
    assert verify_export(Path(exported["path"]))["valid"]


def test_physical_file_inspection_does_not_execute_helper_or_open_camera(setup):
    service, inspector, _ = setup("physical")
    result = inspect(service)
    assert result["status"] == "SUCCEEDED", result
    report = result["result"]["steps"][0]["report"]["inspection_report"]
    assert report["inspection_provenance"] == "WORKSPACE_FILE_INSPECTION"
    assert report["inspection_status"] == "HASH_DRIFT", report
    assert report["metadata_eligible"] is False
    assert report["blockers"] == ["HASH_DRIFT"]
    assert report["files"][0]["status"] == "MATCHED"
    assert report["files"][1]["status"] == "MATCHED"
    assert {
        row["relative_path"] for row in report["files"] if row["status"] == "HASH_DRIFT"
    } == {
        "software/native/windows_camera/camera_worker.cpp",
        "software/native/windows_camera/CMakeLists.txt",
        "software/native/windows_camera/identity_metadata.h",
        "software/native/windows_camera/identity_metadata.cpp",
        "software/native/windows_camera/identity_metadata_tests.cpp",
        "software/native/windows_camera/identity_metadata_wire_test.py",
        # This current client differs from the unchanged historical catalog.
        "software/src/rocell/providers/windows/camera_worker_client.py",
    }
    assert report["historical_full_build_match"] is False
    assert "CLIENT_CHANGED_SINCE_BUILD_RECORD" in report["warnings"]
    assert service._native_camera_provider is None
    # Acknowledging a held report must not approve the historical runtime.
    reviewed = action(
        service, "camera_helper_review", reviewer_id="reviewer", metadata_only=True
    )
    assert reviewed["status"] == "SUCCEEDED", reviewed
    assert service.view()["camera_helper_registration"]["status"] == "REVIEW_HELD"
    assert service._native_camera_provider is None
    assert service._camera_helper.registration() is None
    assert service.view()["camera"]["status"] == "NOT_CONNECTED"
    assert len(inspector.calls) == 1


def test_same_operator_label_cannot_review_and_preview_does_not_mutate(setup):
    service, inspector, _ = setup()
    assert inspect(service)["status"] == "SUCCEEDED"
    before = service.view()["camera_helper_registration"]
    with pytest.raises(WizardError) as error:
        prepare(
            service, "camera_helper_review", reviewer_id="OPERATOR", metadata_only=True
        )
    assert error.value.code == "REVIEWER_MUST_DIFFER"
    assert service.view()["camera_helper_registration"] == before
    assert len(inspector.calls) == 1


@pytest.mark.parametrize(
    "bad",
    [
        {"path": "fake.exe"},
        {"metadata_only": False},
        {"operator_id": ""},
        {"scenario": "run-native"},
    ],
)
def test_closed_inputs_do_not_accept_paths_hashes_or_implicit_consent(setup, bad):
    service, inspector, _ = setup()
    with pytest.raises(WizardError):
        prepare(
            service,
            "camera_helper_inspect",
            **{
                "operator_id": "operator",
                "metadata_only": True,
                "scenario": "nominal",
                **bad,
            }
        )
    assert inspector.calls == []


def test_managed_rehearsal_continues_through_native_endpoint_review(setup):
    service, _, _ = setup()
    assert register(service)["status"] == "SUCCEEDED"
    generic_review(service)
    inventory = action(
        service, "native_camera_inventory", scenario="nominal", metadata_only=True
    )
    assert inventory["status"] == "SUCCEEDED", inventory
    choice = service.view()["native_camera_enrollment"]["candidates"][0]["choice_id"]
    assert (
        action(service, "native_camera_identity", choice_id=choice, metadata_only=True)[
            "status"
        ]
        == "SUCCEEDED"
    )
    assert (
        action(
            service,
            "native_camera_review",
            choice_id=choice,
            reviewer_id="endpoint-reviewer",
            metadata_only=True,
        )["status"]
        == "SUCCEEDED"
    )
    assert service._native_camera.binding() is not None
    assert service._camera_helper.registration() is not None
    assert not hasattr(service._native_camera_provider, "capture")
    assert not hasattr(service._native_camera_provider, "probe")


@pytest.mark.parametrize("outcome", ["cancel", "failure", "source-drift"])
def test_refresh_revokes_before_dispatch_and_never_restores(setup, outcome):
    service, inspector, source = setup()
    assert register(service)["status"] == "SUCCEEDED"
    inspector.entered.clear()
    inspector.release.clear()
    if outcome == "failure":
        inspector.failure = ValueError("Injected read failure")
    receipt = service.execute_action(
        prepare(
            service,
            "camera_helper_inspect",
            operator_id="operator",
            metadata_only=True,
            scenario="nominal",
        )["ticket_id"]
    )
    assert inspector.entered.wait(2)
    assert service._native_camera_provider is None
    assert service._camera_helper.registration() is None
    if outcome == "cancel":
        assert action(service, "stop_operation")["status"] == "SUCCEEDED"
    elif outcome == "source-drift":
        source["hash"] = "b" * 64
    inspector.release.set()
    result = complete(service, receipt)
    assert result["status"] in {"FAILED", "CANCELLED"}
    assert service._native_camera_provider is None
    assert service._camera_helper.registration() is None
    if outcome == "source-drift":
        assert result["result"]["code"] == "SOURCE_CHANGED"
        assert result["result"]["steps"][0]["report"]["inspection_report"]


@pytest.mark.parametrize("stage", ["camera_helper_inspect", "camera_helper_review"])
def test_completion_log_failure_cannot_publish_inspection_or_registration(
    setup, monkeypatch, stage
):
    service, _, _ = setup()
    if stage == "camera_helper_review":
        assert inspect(service)["status"] == "SUCCEEDED"
    original = service._log.append

    def fail(kind, details):
        if kind == "ACTION_FINISHED":
            raise OSError("Injected completion failure")
        return original(kind, details)

    monkeypatch.setattr(service._log, "append", fail)
    result = (
        inspect(service)
        if stage == "camera_helper_inspect"
        else action(service, stage, reviewer_id="reviewer", metadata_only=True)
    )
    assert result["status"] == "FAILED"
    assert service._native_camera_provider is None
    assert service._camera_helper.registration() is None


def test_metadata_revalidation_failure_revokes_registration_and_retains_report(setup):
    calls = []

    def factory(workspace, registration, **kwargs):
        provider = create_metadata_provider(workspace, registration, **kwargs)

        class FailingProvider:
            def descriptor(self):
                return provider.descriptor()

            def inventory(self):
                calls.append("revalidation")
                report = inspect_camera_helper(
                    workspace,
                    source_sha256=kwargs["source_sha256"],
                    mode="rehearsal",
                    scenario="hash-drift",
                )
                raise CameraHelperInspectionError(
                    "HELPER_FILE_CHANGED",
                    "Exact helper files changed.",
                    inspection_report=report,
                )

        return FailingProvider()

    service, _, _ = setup(factory=factory)
    assert register(service)["status"] == "SUCCEEDED"
    generic_review(service)
    result = action(
        service, "native_camera_inventory", scenario="nominal", metadata_only=True
    )
    assert result["status"] == "FAILED", result
    assert result["result"]["steps"][0]["report"]["inspection_report"]
    assert calls == ["revalidation"]
    assert service._camera_helper.registration() is None
    assert service._native_camera_provider is None
    assert service.view()["native_camera_enrollment"]["candidates"] == []


def test_redacted_bound_inspection_is_diagnostic_failure_not_registration(setup):
    service, _, _ = setup()
    result = inspect(service, operator="operator token=fixture-private")
    assert result["status"] == "FAILED", result
    assert result["result"]["code"] == "BOUND_METADATA_REDACTED"
    assert "fixture-private" not in str(result["result"])
    assert service._camera_helper.registration() is None
    assert service.view()["camera_helper_registration"]["inspection"] is None
    assert service._native_camera_provider is None


@pytest.mark.parametrize("changed", ["helper_sha256", "provenance"])
def test_factory_descriptor_must_match_exact_reviewed_context(setup, changed):
    def factory(workspace, registration, **kwargs):
        provider = create_metadata_provider(workspace, registration, **kwargs)

        class Mismatch:
            def descriptor(self):
                descriptor = dict(provider.descriptor())
                descriptor[changed] = (
                    "f" * 64
                    if changed == "helper_sha256"
                    else "WINDOWS_NATIVE_METADATA"
                )
                return descriptor

        return Mismatch()

    service, _, _ = setup(factory=factory)
    result = register(service)
    assert result["status"] == "FAILED", result
    assert result["result"]["code"] == "HELPER_PROVIDER_MISMATCH"
    assert service._camera_helper.registration() is None
    assert service._native_camera_provider is None


def test_new_inspection_invalidates_pending_review_ticket(setup):
    service, _, _ = setup()
    assert inspect(service)["status"] == "SUCCEEDED"
    pending = prepare(
        service, "camera_helper_review", reviewer_id="reviewer", metadata_only=True
    )
    assert inspect(service, "hash-drift")["status"] == "SUCCEEDED"
    with pytest.raises(WizardError):
        service.execute_action(pending["ticket_id"])
    assert service._camera_helper.registration() is None
    assert service._native_camera_provider is None


def test_cancel_before_helper_dispatch_never_calls_inspector(setup, monkeypatch):
    service, inspector, _ = setup()
    original = service._run

    def cancel_before_run(operation_id, action_id, values, cancellation):
        cancellation.set()
        return original(operation_id, action_id, values, cancellation)

    monkeypatch.setattr(service, "_run", cancel_before_run)
    result = inspect(service)
    assert result["status"] == "CANCELLED", result
    assert result["result"]["code"] == "HELPER_CANCELLED"
    assert inspector.calls == []
    assert service._native_camera_provider is None
