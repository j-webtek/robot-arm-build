"""Public native-enrollment actions with real packet parsers, no OS/device calls.

Physical-mode tests inject explicitly test-owned OS-shaped receipts. They test
mode boundaries; they are not received-hardware observations or qualification.
"""

from pathlib import Path
import threading
import time

import pytest

from rocell.application import arrival_wizard_service as module
from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_connection_contracts import canonical_sha256
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.wizard_inventory_fixture import rehearsal_device_inventory
from rocell.application.wizard_native_camera_metadata import (
    RehearsalNativeCameraMetadataProvider,
)


WORKSPACE = Path(__file__).resolve().parents[3]


class GenericInventory:
    def __init__(self, physical):
        self.physical = physical
        self.scenario = "nominal"

    def run(self, action_id, values, **kwargs):
        assert action_id in {"rehearse_device_inventory", "inventory_devices"}
        report = rehearsal_device_inventory(values.get("scenario", self.scenario))
        if self.physical:
            report["serial_inventory"]["source"] = "PYSERIAL_LIST_PORTS"
            for row in report["serial_inventory"]["candidates"]:
                row["source"] = "PYSERIAL_LIST_PORTS"
            report["report_sha256"] = canonical_sha256(
                {key: value for key, value in report.items() if key != "report_sha256"}
            )
        return {
            "schema": "rocell.wizard_worker_result.v1",
            "action_id": action_id,
            "status": "SUCCEEDED",
            "steps": [{"name": "metadata_inventory", "exit_code": 0, "report": report}],
            "device_open_count": 0,
            "serial_write_count": 0,
            "power_event_count": 0,
            "motion_command_count": 0,
            "contact_command_count": 0,
            "metadata_inventory_performed": self.physical,
            "physical_authority": False,
        }


class MetadataProvider:
    def __init__(self, scenario="nominal", physical=False):
        self.fixture = RehearsalNativeCameraMetadataProvider(scenario)
        self.physical = physical
        self.calls = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.fail = None
        self.mutate = None

    def descriptor(self):
        value = dict(self.fixture.descriptor())
        if self.physical:
            value["provenance"] = "WINDOWS_NATIVE_METADATA"
        return value

    def _record(self, kind, packet):
        self.calls.append(kind)
        self.entered.set()
        if not self.release.wait(10):
            raise RuntimeError("Fixture deadline; no replay")
        if self.fail == kind:
            raise RuntimeError("Injected metadata transport failure")
        if self.physical:
            packet["provenance"] = "WINDOWS_NATIVE_METADATA"
        if self.mutate is not None:
            self.mutate(kind, packet)
        return packet

    def inventory(self):
        return self._record("inventory", self.fixture.inventory())

    def identity(self, candidate):
        return self._record("identity", self.fixture.identity(candidate))


@pytest.fixture
def setup(tmp_path, monkeypatch):
    from rocell.application import physical_device_inventory as inventory
    from rocell.providers.windows import camera_worker_client as native
    from rocell.arm.serial_transport import SerialTransport
    from rocell.vision.usb_opencv import UsbOpenCvCamera

    def forbidden(*args, **kwargs):
        raise AssertionError("Physical/native calls forbidden in this lane")

    monkeypatch.setattr(native.subprocess, "Popen", forbidden)
    monkeypatch.setattr(native.WindowsCameraWorkerClient, "probe", forbidden)
    monkeypatch.setattr(native.WindowsCameraWorkerClient, "capture", forbidden)
    monkeypatch.setattr(inventory.SubprocessArgvCommandRunner, "run", forbidden)
    monkeypatch.setattr(inventory, "inventory_serial_ports_with_pyserial", forbidden)
    monkeypatch.setattr(SerialTransport, "connect", forbidden)
    monkeypatch.setattr(UsbOpenCvCamera, "open", forbidden)
    source = {"hash": "a" * 64}
    monkeypatch.setattr(module, "source_fingerprint", lambda _: source["hash"])
    instances = []

    def create(mode="rehearsal", scenario="nominal", default_provider=False):
        provider = MetadataProvider(scenario, mode == "physical")
        service = ArrivalWizardService(
            WORKSPACE,
            mode=mode,
            runner=GenericInventory(mode == "physical"),
            native_camera_provider=None if default_provider else provider,
            log_directory=tmp_path / "logs",
            export_directory=tmp_path / "exports",
        )
        instances.append((service, provider))
        return service, provider, source

    yield create
    for service, provider in instances:
        provider.release.set()
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
    pytest.fail("Exact operation did not complete; never replayed")


def action(service, action_id, **values):
    return complete(
        service,
        service.execute_action(ticket(service, action_id, **values)["ticket_id"]),
    )


def generic_review(service):
    physical = service.mode == "physical"
    assert (
        action(
            service,
            "inventory_devices" if physical else "rehearse_device_inventory",
            **({"power_disconnected": True} if physical else {"scenario": "nominal"}),
        )["status"]
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


def discover(service):
    generic_review(service)
    inputs = {"metadata_only": True}
    if service._native_fixture_provider:
        inputs["scenario"] = "nominal"
    result = action(service, "native_camera_inventory", **inputs)
    assert result["status"] == "SUCCEEDED", result
    return service.view()["native_camera_enrollment"]["candidates"][0]["choice_id"]


def resolve_review(service, selected):
    result = action(
        service, "native_camera_identity", choice_id=selected, metadata_only=True
    )
    assert result["status"] == "SUCCEEDED", result
    result = action(
        service,
        "native_camera_review",
        choice_id=selected,
        reviewer_id="endpoint-reviewer",
        metadata_only=True,
    )
    assert result["status"] == "SUCCEEDED", result
    return result


@pytest.mark.parametrize("mode", ["rehearsal", "physical"])
def test_default_startup_and_views_are_inert_and_physical_provider_absent(setup, mode):
    service, provider, _ = setup(mode, default_provider=True)
    view = service.view()
    assert not provider.calls
    assert view["native_camera_enrollment"]["status"] == (
        "NO_INVENTORY" if mode == "rehearsal" else "PROVIDER_UNAVAILABLE"
    )
    for item in view["actions"]:
        if item["action_id"].startswith("native_camera_"):
            assert not item["enabled"]
            for field in item["fields"]:
                if field["type"] == "checkbox":
                    assert field["default"] is False
                if field["name"] == "choice_id":
                    assert "default" not in field and field["options"] == []
    assert all(stage["state"] == "PHYSICAL_PENDING" for stage in view["stages"])


@pytest.mark.parametrize("mode", ["rehearsal", "physical"])
def test_full_public_mapping_review_and_verified_export(setup, mode):
    service, provider, _ = setup(mode)
    selected = discover(service)
    assert provider.calls == ["inventory"]
    preview = ticket(
        service, "native_camera_identity", choice_id=selected, metadata_only=True
    )
    assert provider.calls == ["inventory"]
    assert "Exact native metadata request" in " ".join(preview["effects"])
    receipt = service.execute_action(preview["ticket_id"])
    assert complete(service, receipt)["status"] == "SUCCEEDED"
    assert (
        service.execute_action(preview["ticket_id"])["operation_id"]
        == receipt["operation_id"]
    )
    assert provider.calls == ["inventory", "identity"]
    assert (
        action(
            service,
            "native_camera_review",
            choice_id=selected,
            reviewer_id="endpoint-reviewer",
            metadata_only=True,
        )["status"]
        == "SUCCEEDED"
    )
    snapshot = service.view()["native_camera_enrollment"]
    assert snapshot["status"] == "ENDPOINT_METADATA_REVIEWED"
    assert snapshot["identity"]["exact_endpoint_observed"] is True
    assert snapshot["identity"]["generic_device_match"] is True
    assert snapshot["identity"]["container_match"] is True
    assert snapshot["review"]["binding_sha256"]
    assert service._native_camera.binding() is not None
    for flag in ("connected", "qualified", "persistent_binding", "physical_authority"):
        assert snapshot[flag] is False
    assert service.view()["camera"]["status"] == "NOT_CONNECTED"
    assert all(row["state"] == "PHYSICAL_PENDING" for row in service.view()["stages"])
    result = action(service, "export_logs")
    assert result["status"] == "SUCCEEDED"
    exported = service.view()["exports"]["items"][-1]
    verified = verify_export(Path(exported["path"]))
    assert verified["valid"] and verified["physical_authority"] == "NONE"
    # The exact native wire packet and binding artifact survive full-result
    # retention, rather than only a success-looking status projection.
    retained = service._native_camera.export_snapshot()
    assert retained["inventory_packet"]["receipt"]["cleanup"]
    assert retained["identity_packet"]["receipt"]["requested_endpoint"]
    assert (
        retained["binding_artifact"]["binding_sha256"]
        == snapshot["review"]["binding_sha256"]
    )


@pytest.mark.parametrize("scenario", ["missing-mapping", "wrong-device"])
def test_mismatch_remains_reviewable_but_never_binds(setup, scenario):
    service, _, _ = setup(scenario=scenario)
    selected = discover(service)
    resolve_review(service, selected)
    view = service.view()["native_camera_enrollment"]
    assert view["status"] == "REVIEW_HELD"
    assert view["identity"]["blockers"]
    assert service._native_camera.binding() is None
    assert view["review"]["binding_sha256"] is None


def test_duplicate_names_are_distinct_explicit_endpoints(setup):
    service, provider, _ = setup(scenario="duplicate-name")
    discover(service)
    choices = service.view()["native_camera_enrollment"]["candidates"]
    assert len(choices) == 2
    assert choices[0]["friendly_name"] == choices[1]["friendly_name"]
    assert choices[0]["choice_id"] != choices[1]["choice_id"]
    assert choices[0]["endpoint_sha256"] != choices[1]["endpoint_sha256"]
    assert provider.calls == ["inventory"]
    resolve_review(service, choices[1]["choice_id"])
    assert service._native_camera.binding() is None


@pytest.mark.parametrize("stage", ["inventory", "identity"])
@pytest.mark.parametrize("outcome", ["failure", "cancel", "invalid-packet"])
def test_refresh_retires_old_binding_before_dispatch_and_failure_never_restores(
    setup, stage, outcome
):
    service, provider, _ = setup()
    selected = discover(service)
    resolve_review(service, selected)
    assert service._native_camera.binding() is not None
    provider.release.clear()
    provider.entered.clear()
    if outcome == "failure":
        provider.fail = stage
    elif outcome == "invalid-packet":
        provider.mutate = lambda kind, packet: packet.update(helper_sha256="f" * 64)
    values = {"metadata_only": True}
    if stage == "identity":
        values["choice_id"] = selected
    receipt = service.execute_action(
        ticket(service, "native_camera_" + stage, **values)["ticket_id"]
    )
    assert provider.entered.wait(2)
    assert service._native_camera.binding() is None
    if outcome == "cancel":
        assert action(service, "stop_operation")["status"] == "SUCCEEDED"
    provider.release.set()
    result = complete(service, receipt)
    assert result["status"] in {"FAILED", "CANCELLED"}
    assert service._native_camera.binding() is None
    if stage == "inventory":
        assert service.view()["native_camera_enrollment"]["candidates"] == []
    else:
        assert service.view()["native_camera_enrollment"]["identity"] is None


def test_generic_camera_rereview_invalidates_native_endpoint_and_old_tickets(setup):
    service, provider, _ = setup()
    selected = discover(service)
    resolve_review(service, selected)
    pending = ticket(
        service, "native_camera_identity", choice_id=selected, metadata_only=True
    )
    generic = service.view()["device_selection"]["devices"]["CAMERA"]["review"]
    assert (
        action(
            service,
            "review_camera_candidate",
            choice_id=generic["choice_id"],
            reviewer_id="new-reviewer",
            metadata_only=True,
        )["status"]
        == "SUCCEEDED"
    )
    assert service._native_camera.binding() is None
    assert service.view()["native_camera_enrollment"]["candidates"] == []
    with pytest.raises(WizardError):
        service.execute_action(pending["ticket_id"])
    assert provider.calls == ["inventory", "identity"]


def test_source_drift_invalidates_native_without_lookup(setup):
    service, provider, source = setup()
    selected = discover(service)
    resolve_review(service, selected)
    source["hash"] = "b" * 64
    with pytest.raises(WizardError, match="Source changed"):
        ticket(
            service, "native_camera_identity", choice_id=selected, metadata_only=True
        )
    assert service._native_camera.binding() is None
    assert provider.calls == ["inventory", "identity"]


@pytest.mark.parametrize(
    "bad",
    [
        {"endpoint": "raw"},
        {"helper_sha256": "f" * 64},
        {"metadata_only": False},
        {"metadata_only": 1},
        {"choice_id": "camera-index-0"},
    ],
)
def test_browser_cannot_supply_endpoint_registration_or_implicit_consent(setup, bad):
    service, provider, _ = setup()
    selected = discover(service)
    with pytest.raises(WizardError):
        ticket(
            service,
            "native_camera_identity",
            **{"choice_id": selected, "metadata_only": True, **bad},
        )
    assert provider.calls == ["inventory"]


def test_completion_log_failure_discards_staged_binding(setup, monkeypatch):
    service, _, _ = setup()
    selected = discover(service)
    assert (
        action(
            service, "native_camera_identity", choice_id=selected, metadata_only=True
        )["status"]
        == "SUCCEEDED"
    )
    original = service._log.append

    def fail_finish(kind, details):
        if kind == "ACTION_FINISHED":
            raise OSError("Injected completion log failure")
        return original(kind, details)

    monkeypatch.setattr(service._log, "append", fail_finish)
    result = action(
        service,
        "native_camera_review",
        choice_id=selected,
        reviewer_id="reviewer",
        metadata_only=True,
    )
    assert result["status"] == "FAILED"
    assert service._native_camera.binding() is None
    assert service.view()["native_camera_enrollment"]["candidates"] == []


def test_default_rehearsal_runs_without_registered_physical_helper(setup):
    service, _, _ = setup(default_provider=True)
    selected = discover(service)
    resolve_review(service, selected)
    assert service._native_camera.binding() is not None
    assert (
        service.view()["native_camera_enrollment"]["provenance"]["provider_provenance"]
        == "INCAPABLE_FIXTURE"
    )


def test_redacted_wire_metadata_is_retained_as_failure_not_exact_binding(setup):
    service, provider, _ = setup()
    generic_review(service)

    def secret_label(kind, packet):
        if kind == "inventory":
            packet["receipt"]["devices"][0][
                "friendly_name"
            ] = "camera token=fixture-private"

    provider.mutate = secret_label
    result = action(service, "native_camera_inventory", metadata_only=True)
    assert result["status"] == "FAILED"
    assert result["result"]["code"] == "BOUND_METADATA_REDACTED"
    assert result["result"]["original_result_sha256"]
    assert "fixture-private" not in str(result["result"])
    assert service.view()["native_camera_enrollment"]["candidates"] == []
    assert service._native_camera.binding() is None
    assert provider.calls == ["inventory"]


def test_source_drift_during_query_preserves_returned_packet_without_publication(setup):
    service, provider, source = setup()
    selected = discover(service)
    provider.release.clear()
    provider.entered.clear()
    receipt = service.execute_action(
        ticket(
            service, "native_camera_identity", choice_id=selected, metadata_only=True
        )["ticket_id"]
    )
    assert provider.entered.wait(2)
    source["hash"] = "b" * 64
    provider.release.set()
    result = complete(service, receipt)
    assert result["status"] == "FAILED"
    retained = result["result"]
    assert retained["code"] == "SOURCE_CHANGED"
    assert retained["source_at_dispatch_sha256"] == "a" * 64
    assert retained["source_after_lookup_sha256"] == "b" * 64
    assert retained["steps"][0]["report"]["identity_packet"]["receipt"][
        "requested_endpoint"
    ]
    assert service._native_camera.binding() is None
    assert service.view()["native_camera_enrollment"]["candidates"] == []
    exported = action(service, "export_logs")
    assert exported["status"] == "SUCCEEDED"
    assert verify_export(Path(service.view()["exports"]["items"][-1]["path"]))["valid"]


def test_cancel_before_native_dispatch_does_not_call_provider(setup, monkeypatch):
    service, provider, _ = setup()
    generic_review(service)
    original = service._run

    def cancel_before_run(operation_id, action_id, values, cancellation):
        cancellation.set()
        return original(operation_id, action_id, values, cancellation)

    monkeypatch.setattr(service, "_run", cancel_before_run)
    result = action(service, "native_camera_inventory", metadata_only=True)
    assert result["status"] == "CANCELLED"
    assert not provider.calls
    assert service.view()["native_camera_enrollment"]["candidates"] == []
