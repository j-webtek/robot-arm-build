from __future__ import annotations

from importlib import reload
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from rocell.application import wizard_worker as worker


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def no_devices(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Tests fail before any host inventory or physical endpoint can open."""
    from rocell.application import physical_device_inventory as inventory
    from rocell.arm.serial_transport import SerialTransport
    from rocell.vision.usb_opencv import UsbOpenCvCamera

    calls: list[str] = []

    def forbidden(*args: Any, **kwargs: Any) -> None:
        calls.append("unexpected host access")
        raise AssertionError("Worker test attempted physical device access")

    monkeypatch.setattr(SerialTransport, "connect", forbidden)
    monkeypatch.setattr(UsbOpenCvCamera, "open", forbidden)
    for name in (
        "inventory_windows_pnp_cameras",
        "inventory_linux_video_cameras_from_sysfs",
        "inventory_serial_ports_with_pyserial",
    ):
        monkeypatch.setattr(inventory, name, forbidden)
    return calls


def test_import_and_catalog_loading_have_no_activation(no_devices: list[str]) -> None:
    reload(worker)
    assert no_devices == []


@pytest.mark.parametrize(
    "scenario",
    [
        "nominal",
        "boot-bytes",
        "short-write",
        "timeout",
        "identity-change",
        "close-failure",
    ],
)
def test_new_arm_worker_contract_runs_only_closed_incapable_scenarios(
    scenario: str, no_devices: list[str]
) -> None:
    result = worker.run(
        WORKSPACE, "arm_feedback_contract", {"scenario": scenario}, "CELL-A"
    )
    assert result["status"] == "SUCCEEDED"
    assert result["device_open_count"] == result["serial_write_count"] == 0
    report = result["steps"][0]["report"]
    assert report["expected_outcome_matched"] is True
    assert report["arm_connected"] is False
    assert report["durable_coordinator_authority"] is False
    assert all(value == 0 for value in report["actual_effect_counts"].values())
    assert no_devices == []


@pytest.mark.parametrize(
    "action_id",
    [
        "camera_connect",
        "arm_connect",
        "execute_task",
        "export_logs",
        "record_note",
        "stop_operation",
    ],
)
def test_reserved_and_parent_owned_actions_cannot_run_in_worker(
    action_id: str, monkeypatch: pytest.MonkeyPatch, no_devices: list[str]
) -> None:
    calls = []
    monkeypatch.setattr(worker, "_cli", lambda *args: calls.append(args))
    input = {"note": "test"} if action_id == "record_note" else {}
    with pytest.raises(ValueError, match="cannot be executed"):
        worker.run(WORKSPACE, action_id, input, "CELL-A")
    assert calls == []
    assert no_devices == []


@pytest.mark.parametrize(
    "action_id",
    ["raw_serial", "run_shell", "rocell.arm.serial_transport", "C:/bad.exe"],
)
def test_unregistered_action_is_rejected_before_dispatch(action_id: str) -> None:
    with pytest.raises(ValueError, match="Unknown registered"):
        worker.run(WORKSPACE, action_id, {}, "CELL-A")


@pytest.mark.parametrize("device", ["keyboard", "phone"])
def test_compile_task_uses_actual_existing_cli_without_hardware(
    device: str, no_devices: list[str]
) -> None:
    result = worker.run(
        WORKSPACE, "plan_task", {"device": device, "text": "hi"}, "CELL-A"
    )
    assert result["status"] == "SUCCEEDED"
    report = result["steps"][0]["report"]
    assert report["schema"] == "rocell.plan_result.v1"
    assert report["execution_authorized"] is False
    assert report["action_plan"]["actions"]
    assert result["physical_authority"] is False
    assert result["device_open_count"] == result["serial_write_count"] == 0
    assert result["motion_command_count"] == result["contact_command_count"] == 0
    assert no_devices == []


@pytest.mark.parametrize("action_id", ["plan_task", "simulate_task"])
def test_hyphen_prefixed_text_stays_one_cli_value(
    action_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def cli(workspace: Path, args: list[str]) -> dict[str, Any]:
        calls.append(args)
        return {"exit_code": 0, "report": {}, "stderr": ""}

    monkeypatch.setattr(worker, "_cli", cli)
    worker.run(WORKSPACE, action_id, {"text": "--help", "device": "keyboard"}, "CELL-A")
    assert "--text=--help" in calls[0]
    assert "--help" not in calls[0]


def test_actual_baseline_composes_software_only_checks(no_devices: list[str]) -> None:
    result = worker.run(WORKSPACE, "run_baseline", {}, "CELL-A")
    assert [step["name"] for step in result["steps"]] == [
        "build_alignment",
        "host",
        "foundation",
        "connections",
    ]
    assert all("exit_code" in step for step in result["steps"])
    assert result["steps"][-1]["report"]["hardware_accessed"] is False
    assert all(
        value is False for value in result["steps"][-1]["report"]["authority"].values()
    )
    assert result["metadata_inventory_performed"] is False
    assert result["physical_authority"] is False
    assert no_devices == []


@pytest.mark.parametrize(
    "action_id,fault",
    [("camera_rehearsal", "stale-camera-frame"), ("arm_rehearsal", "dirty-arm-buffer")],
)
def test_connection_faults_are_bounded_registered_cli_data(
    action_id: str, fault: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def cli(workspace: Path, args: list[str]) -> dict[str, Any]:
        calls.append(args)
        return {
            "exit_code": 0,
            "report": {"status": "EXPECTED_FAULT_BLOCKED"},
            "stderr": "",
        }

    monkeypatch.setattr(worker, "_cli", cli)
    result = worker.run(WORKSPACE, action_id, {"fault": fault}, "CELL-A")
    assert result["status"] == "SUCCEEDED"
    assert calls == [
        [
            "rehearse-physical-connections",
            "--fault",
            fault,
            "--require-expected",
            "--json",
        ]
    ]


def test_failed_cli_step_is_retained_not_promoted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        worker,
        "_cli",
        lambda *args: {
            "exit_code": 2,
            "report": {"reason": "test hold"},
            "stderr": "details",
        },
    )
    result = worker.run(WORKSPACE, "camera_profile", {}, "CELL-A")
    assert result["status"] == "FAILED"
    assert result["steps"][0]["stderr"] == "details"


@pytest.mark.parametrize("system", ["Windows", "Linux"])
def test_inventory_is_explicit_and_uses_mocked_metadata_only(
    system: str, monkeypatch: pytest.MonkeyPatch, no_devices: list[str]
) -> None:
    from rocell.application import physical_device_inventory as inventory

    observed: list[Any] = []
    camera_record, serial_record = object(), object()
    monkeypatch.setattr(worker.platform, "system", lambda: system)
    monkeypatch.setattr(
        inventory, "inventory_windows_pnp_cameras", lambda runner: camera_record
    )
    monkeypatch.setattr(
        inventory, "inventory_linux_video_cameras_from_sysfs", lambda: camera_record
    )
    monkeypatch.setattr(
        inventory, "inventory_serial_ports_with_pyserial", lambda: serial_record
    )

    def compose(**kwargs: Any) -> Any:
        observed.append(kwargs)
        return SimpleNamespace(to_dict=lambda: {"status": "MOCK_METADATA_ONLY"})

    monkeypatch.setattr(inventory, "compose_physical_device_inventory_report", compose)
    result = worker.run(
        WORKSPACE, "inventory_devices", {"power_disconnected": True}, "CELL-A"
    )
    assert result["metadata_inventory_performed"] is True
    assert observed[0]["camera_inventory"] is camera_record
    assert observed[0]["serial_inventory"] is serial_record
    assert result["device_open_count"] == 0
    assert no_devices == []


def test_inventory_confirmation_is_required_before_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(worker, "_inventory", lambda: calls.append("inventory"))
    with pytest.raises(ValueError):
        worker.run(WORKSPACE, "inventory_devices", {}, "CELL-A")
    assert calls == []


def test_stdout_limit_counts_utf8_bytes_not_characters() -> None:
    output = worker.BoundedText(4)
    assert output.write("éé") == 2
    with pytest.raises(ValueError, match="byte budget"):
        output.write("a")
    assert output.getvalue() == "éé"


class _Console:
    def __init__(self, payload: bytes = b"") -> None:
        self.buffer = io.BytesIO(payload)

    def write(self, value: str) -> int:
        self.buffer.write(value.encode("utf-8"))
        return len(value)

    def flush(self) -> None:
        return


def _main(
    payload: bytes, monkeypatch: pytest.MonkeyPatch
) -> tuple[int, dict[str, Any]]:
    input, output = _Console(payload), _Console()
    with monkeypatch.context() as local:
        local.setattr(worker.sys, "stdin", input)
        local.setattr(worker.sys, "stdout", output)
        code = worker.main()
    return code, json.loads(output.buffer.getvalue())


def _payload(**changes: Any) -> bytes:
    return json.dumps(
        {
            "workspace": str(WORKSPACE),
            "action_id": "plan_task",
            "input": {"device": "keyboard", "text": "hi"},
            "cell_id": "CELL-A",
            **changes,
        }
    ).encode()


def test_valid_worker_wire_request_is_bound_to_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []

    def run(*args: Any) -> dict[str, Any]:
        calls.append(args)
        return {
            "schema": "rocell.wizard_worker_result.v1",
            "status": "SUCCEEDED",
            "physical_authority": False,
        }

    monkeypatch.setattr(worker, "run", run)
    code, result = _main(_payload(), monkeypatch)
    assert code == 0
    assert result["physical_authority"] is False
    assert calls == [
        (WORKSPACE, "plan_task", {"device": "keyboard", "text": "hi"}, "CELL-A")
    ]


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"[]",
        b"null",
        b"{",
        b"x" * (16 * 1024 + 1),
        b'{"workspace":"one","workspace":"two","action_id":"plan_task","input":{},"cell_id":"CELL-A"}',
        b'{"workspace":"one","action_id":"plan_task","input":{"text":"a","text":"b"},"cell_id":"CELL-A"}',
    ],
)
def test_bad_worker_json_cannot_dispatch(
    payload: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(worker, "run", lambda *args: calls.append(args))
    code, result = _main(payload, monkeypatch)
    assert code == 1
    assert result["schema"] == "rocell.wizard_worker_error.v1"
    assert result["physical_authority"] is False
    assert calls == []


@pytest.mark.parametrize(
    "changes",
    [
        {"extra": "arbitrary"},
        {"workspace": str(WORKSPACE.parent)},
        {"workspace": "missing-workspace-for-test"},
        {"cell_id": ""},
        {"cell_id": "c" * 65},
        {"cell_id": True},
    ],
)
def test_closed_wire_schema_and_workspace_binding(
    changes: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(worker, "run", lambda *args: calls.append(args))
    code, result = _main(_payload(**changes), monkeypatch)
    assert code == 1
    assert result["status"] == "FAILED"
    assert calls == []


def test_oversized_worker_result_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        worker, "run", lambda *args: {"large": "a" * (worker.MAX_OUTPUT + 1)}
    )
    code, result = _main(_payload(), monkeypatch)
    assert code == 1
    assert result["message"] == "Result exceeded budget"
