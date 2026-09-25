"""Public wizard tickets exercise selection without any physical inventory.

Physical-mode tests inject serialized OS-shaped results; that test injection
is not an application API for minting physical observations or endpoint permits.
"""

from copy import deepcopy
from pathlib import Path
import threading
import time

import pytest

from rocell.application import arrival_wizard_service as service_module
from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_connection_contracts import canonical_sha256
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.wizard_inventory_fixture import rehearsal_device_inventory
from rocell.application import wizard_worker


WORKSPACE = Path(__file__).resolve().parents[3]


def physical_fixture_report():
    report = rehearsal_device_inventory("nominal")
    report["serial_inventory"]["source"] = "PYSERIAL_LIST_PORTS"
    for candidate in report["serial_inventory"]["candidates"]:
        candidate["source"] = "PYSERIAL_LIST_PORTS"
    report["report_sha256"] = canonical_sha256(
        {key: value for key, value in report.items() if key != "report_sha256"}
    )
    return report


class InventoryRunner:
    def __init__(self):
        self.calls = []
        self.report = None
        self.release = threading.Event()
        self.release.set()
        self.entered = threading.Event()
        self.fail = False

    def run(self, action_id, values, *, cell_id, cancel, progress):
        self.calls.append(action_id)
        self.entered.set()
        while not self.release.wait(0.01):
            if cancel.is_set():
                break
        if self.fail:
            raise RuntimeError("Injected inventory transport failure")
        result = wizard_worker.run(
            WORKSPACE,
            "rehearse_device_inventory",
            {"scenario": values.get("scenario", "nominal")},
            cell_id,
        )
        result["action_id"] = action_id
        result["metadata_inventory_performed"] = action_id == "inventory_devices"
        if self.report is not None:
            result["steps"][0]["report"] = deepcopy(self.report)
        if cancel.is_set():
            return {
                "schema": "rocell.wizard_diagnostic_completion.v1",
                "action_id": action_id,
                "status": "CANCELLED",
                "message": "Fixture cancelled",
                "elapsed_s": 0.0,
                "output_limit_exceeded": False,
                "physical_authority": False,
            }
        return result


@pytest.fixture
def setup(tmp_path, monkeypatch):
    from rocell.application import physical_device_inventory as inventory
    from rocell.arm.serial_transport import SerialTransport
    from rocell.vision.usb_opencv import UsbOpenCvCamera

    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected physical/provider access")

    monkeypatch.setattr(inventory.SubprocessArgvCommandRunner, "run", forbidden)
    monkeypatch.setattr(inventory, "inventory_serial_ports_with_pyserial", forbidden)
    monkeypatch.setattr(SerialTransport, "connect", forbidden)
    monkeypatch.setattr(UsbOpenCvCamera, "open", forbidden)
    source = {"hash": "a" * 64}
    monkeypatch.setattr(service_module, "source_fingerprint", lambda _: source["hash"])
    instances = []

    def create(mode="rehearsal"):
        runner = InventoryRunner()
        if mode == "physical":
            runner.report = physical_fixture_report()
        service = ArrivalWizardService(
            WORKSPACE,
            mode=mode,
            runner=runner,
            log_directory=tmp_path / "logs",
            export_directory=tmp_path / "exports",
        )
        instances.append((service, runner))
        return service, runner, source

    yield create
    for service, runner in instances:
        runner.release.set()
        service.shutdown()


def ticket(service, action, **values):
    return service.prepare_action(action, values, service.view()["revision"])


def complete(service, receipt):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        operation = service.operation(receipt["operation_id"])
        if operation["status"] not in {"QUEUED", "RUNNING"}:
            return operation
        threading.Event().wait(0.01)
    pytest.fail("Timed out; operation was not replayed")


def action(service, action_id, **values):
    return complete(
        service,
        service.execute_action(ticket(service, action_id, **values)["ticket_id"]),
    )


def choice(service, device="CAMERA"):
    return service.view()["device_selection"]["devices"][device]["candidates"][0][
        "choice_id"
    ]


def review_values(service, device="CAMERA"):
    return dict(
        choice_id=choice(service, device),
        reviewer_id="metadata-reviewer",
        metadata_only=True,
    )


def test_construct_view_prepare_do_not_run_inventory_or_restore_selection(setup):
    service, runner, _ = setup()
    assert service.view()["device_selection"]["status"] == "NO_INVENTORY"
    ticket(service, "rehearse_device_inventory", scenario="nominal")
    assert not runner.calls
    for item in service.view()["actions"]:
        if item["action_id"] in {"review_camera_candidate", "review_arm_candidate"}:
            assert not item["enabled"]
            assert "default" not in item["fields"][0]
            assert item["fields"][2]["default"] is False


@pytest.mark.parametrize("mode", ["rehearsal", "physical"])
def test_exact_inventory_review_export_and_no_physical_promotion(setup, mode):
    service, runner, _ = setup(mode)
    args = (
        {"scenario": "nominal"} if mode == "rehearsal" else {"power_disconnected": True}
    )
    run_id = "rehearse_device_inventory" if mode == "rehearsal" else "inventory_devices"
    assert action(service, run_id, **args)["status"] == "SUCCEEDED"
    preview = ticket(service, "review_camera_candidate", **review_values(service))
    assert "Exact metadata selection" in " ".join(preview["effects"])
    assert service.view()["device_selection"]["devices"]["CAMERA"]["review"] is None
    receipt = service.execute_action(preview["ticket_id"])
    assert complete(service, receipt)["status"] == "SUCCEEDED"
    assert (
        service.execute_action(preview["ticket_id"])["operation_id"]
        == receipt["operation_id"]
    )
    assert (
        action(service, "review_arm_candidate", **review_values(service, "SERIAL"))[
            "status"
        ]
        == "SUCCEEDED"
    )
    assert runner.calls == [run_id]  # Review never calls the worker/provider.
    state = service.view()
    assert state["camera"]["status"] == state["arm"]["status"] == "NOT_CONNECTED"
    assert state["physical_authority"] is False
    assert all(stage["state"] == "PHYSICAL_PENDING" for stage in state["stages"])
    assert action(service, "export_logs")["status"] == "SUCCEEDED"
    exported = Path(service.view()["exports"]["items"][-1]["path"])
    assert verify_export(exported)["valid"]
    import json

    attachments = [
        json.loads(path.read_text()) for path in exported.glob("attachment-*.json")
    ]
    retained = [
        step["report"] for item in attachments for step in item.get("steps", [])
    ]
    assert any("inventory_report" in item for item in retained)
    fresh, _, _ = setup(mode)
    assert fresh.view()["device_selection"]["status"] == "NO_INVENTORY"


@pytest.mark.parametrize("scenario", ["missing-identity", "duplicate-identity"])
def test_incomplete_or_ambiguous_identity_stays_visible_after_review(setup, scenario):
    service, _, _ = setup()
    assert (
        action(service, "rehearse_device_inventory", scenario=scenario)["status"]
        == "SUCCEEDED"
    )
    for device, review_id in (
        ("CAMERA", "review_camera_candidate"),
        ("SERIAL", "review_arm_candidate"),
    ):
        assert service.view()["device_selection"]["devices"][device]["candidates"][0][
            "identity_blockers"
        ]
        assert (
            action(service, review_id, **review_values(service, device))["status"]
            == "SUCCEEDED"
        )
        reviewed = service.view()["device_selection"]["devices"][device]["review"]
        assert reviewed["qualified"] is False
        assert reviewed["connected"] is False


@pytest.mark.parametrize(
    "replacement", ["nominal", "partial-inventory", "transport-failure", "cancel"]
)
def test_refresh_invalidates_both_reviews_even_if_new_inventory_fails(
    setup, replacement
):
    service, runner, _ = setup()
    action(service, "rehearse_device_inventory", scenario="nominal")
    old_choice = choice(service)
    action(service, "review_camera_candidate", **review_values(service))
    action(service, "review_arm_candidate", **review_values(service, "SERIAL"))
    stale = ticket(service, "review_camera_candidate", **review_values(service))
    runner.entered.clear()
    runner.release.clear()
    runner.fail = replacement == "transport-failure"
    refresh = ticket(
        service,
        "rehearse_device_inventory",
        scenario=(
            replacement
            if replacement in {"nominal", "partial-inventory"}
            else "nominal"
        ),
    )
    receipt = service.execute_action(refresh["ticket_id"])
    assert runner.entered.wait(2)
    pending = service.view()["device_selection"]
    assert all(
        not row["candidates"] and row["review"] is None
        for row in pending["devices"].values()
    )
    with pytest.raises(WizardError):
        service.execute_action(stale["ticket_id"])
    if replacement == "cancel":
        action(service, "stop_operation")
    runner.release.set()
    outcome = complete(service, receipt)
    assert outcome["status"] == (
        "SUCCEEDED"
        if replacement == "nominal"
        else "CANCELLED" if replacement == "cancel" else "FAILED"
    )
    with pytest.raises(WizardError):
        ticket(
            service,
            "review_camera_candidate",
            choice_id=old_choice,
            reviewer_id="reviewer",
            metadata_only=True,
        )
    if replacement == "partial-inventory":
        assert (
            outcome["result"]["steps"][0]["report"]["camera_inventory"][
                "collection_complete"
            ]
            is False
        )


@pytest.mark.parametrize(
    "values",
    [
        {"metadata_only": False},
        {"metadata_only": 1},
        {"choice_id": "COM91"},
        {"endpoint": "COM91"},
        {"physical_authority": True},
    ],
)
def test_raw_endpoints_and_missing_consent_rejected_before_review(setup, values):
    service, runner, _ = setup()
    action(service, "rehearse_device_inventory", scenario="nominal")
    with pytest.raises(WizardError):
        ticket(
            service, "review_camera_candidate", **{**review_values(service), **values}
        )
    assert runner.calls == ["rehearse_device_inventory"]


def test_source_drift_clears_candidate_choices(setup):
    service, _, source = setup()
    action(service, "rehearse_device_inventory", scenario="nominal")
    selected = ticket(service, "review_camera_candidate", **review_values(service))
    source["hash"] = "b" * 64
    with pytest.raises(WizardError, match="Source changed"):
        service.execute_action(selected["ticket_id"])
    assert service.view()["device_selection"]["devices"]["CAMERA"]["candidates"] == []


def test_completion_log_failure_does_not_publish_candidate_review(setup, monkeypatch):
    service, _, _ = setup()
    action(service, "rehearse_device_inventory", scenario="nominal")
    original = service._log.append

    def fail_completion(kind, details):
        if kind == "ACTION_FINISHED":
            raise OSError("Injected disk failure")
        return original(kind, details)

    monkeypatch.setattr(service._log, "append", fail_completion)
    assert (
        action(service, "review_camera_candidate", **review_values(service))["status"]
        == "FAILED"
    )
    assert service.view()["device_selection"]["devices"]["CAMERA"]["review"] is None


def test_cancelled_review_does_not_publish_staged_acknowledgement(setup, monkeypatch):
    from rocell.application.wizard_device_selection import WizardDeviceSelection

    service, _, _ = setup()
    action(service, "rehearse_device_inventory", scenario="nominal")
    original = WizardDeviceSelection.review

    def cancel_after_preparation(staged, *args, **kwargs):
        report = original(staged, *args, **kwargs)
        service._cancel.set()
        return report

    monkeypatch.setattr(WizardDeviceSelection, "review", cancel_after_preparation)
    assert (
        action(service, "review_camera_candidate", **review_values(service))["status"]
        == "CANCELLED"
    )
    assert service.view()["device_selection"]["devices"]["CAMERA"]["review"] is None


def test_mode_separation_requires_explicit_power_ack_and_no_fixture_in_physical(setup):
    service, runner, _ = setup("physical")
    with pytest.raises(WizardError):
        ticket(service, "inventory_devices", power_disconnected=False)
    with pytest.raises(WizardError):
        ticket(service, "rehearse_device_inventory", scenario="nominal")
    runner.report = rehearsal_device_inventory("nominal")
    assert (
        action(service, "inventory_devices", power_disconnected=True)["status"]
        == "FAILED"
    )
    assert service.view()["device_selection"]["devices"]["CAMERA"]["candidates"] == []
