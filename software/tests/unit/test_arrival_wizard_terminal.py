from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from rocell.ui.terminal import POLL_WINDOW_STEPS, run_terminal_wizard


def action(
    action_id: str = "plan_task",
    *,
    enabled: bool = True,
    fields: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "label": action_id.replace("_", " "),
        "enabled": enabled,
        "blocked_reasons": [] if enabled else ["Physical release is not qualified"],
        "fields": fields or [],
        "description": "Registered diagnostic only",
    }


class Service:
    def __init__(self, actions: list[dict[str, Any]] | None = None) -> None:
        self.actions = actions if actions is not None else [action()]
        self.calls: list[tuple[Any, ...]] = []
        self.operation_status = "SUCCEEDED"
        self.execute_error: Exception | None = None
        self.prepare_error: Exception | None = None
        self.shutdown_count = 0

    def view(self) -> dict[str, Any]:
        self.calls.append(("view",))
        return {
            "revision": 7,
            "mode": "rehearsal",
            "cell_id": "CELL-A",
            "session_id": "session-test",
            "source_status": "SOURCE_BOUND",
            "authority": "NONE",
            "actions": deepcopy(self.actions),
            "exports": {"directory": "assigned-exports"},
        }

    def prepare_action(
        self, action_id: str, input: dict[str, Any], expected_revision: int
    ) -> dict[str, Any]:
        self.calls.append(("prepare", action_id, input, expected_revision))
        if self.prepare_error:
            raise self.prepare_error
        return {
            "ticket_id": "ticket-1",
            "label": action_id,
            "effects": ["Synthetic diagnostic only"],
            "warnings": ["No physical authority"],
            "expires_in_s": 30,
        }

    def execute_action(self, ticket_id: str) -> dict[str, Any]:
        self.calls.append(("execute", ticket_id))
        if self.execute_error:
            raise self.execute_error
        return {"operation_id": "operation-1", "status": "QUEUED"}

    def operation(self, operation_id: str) -> dict[str, Any]:
        self.calls.append(("operation", operation_id))
        return {
            "operation_id": operation_id,
            "status": self.operation_status,
            "result": {"physical_authority": False},
        }

    def image(self, image_id: str) -> tuple[bytes, str]:
        raise AssertionError("Terminal never opens image sources")

    def shutdown(self) -> None:
        self.shutdown_count += 1


def run(
    service: Service, replies: list[Any], *, sleep: Any = None
) -> tuple[int, list[str], list[str]]:
    responses = iter(replies)
    output: list[str] = []
    prompts: list[str] = []

    def read(prompt: str) -> str:
        prompts.append(prompt)
        response = next(responses, EOFError())
        if isinstance(response, BaseException):
            raise response
        return response

    code = run_terminal_wizard(
        service,
        read_line=read,
        write_line=output.append,
        sleep=sleep or (lambda delay: None),
    )
    return code, output, prompts


def dispatched(service: Service, name: str) -> list[tuple[Any, ...]]:
    return [call for call in service.calls if call[0] == name]


def test_start_view_and_quit_do_not_prepare_execute_or_shutdown() -> None:
    service = Service()
    code, output, _ = run(service, ["view", "quit"])
    assert code == 0
    assert service.calls == [("view",), ("view",)]
    assert service.shutdown_count == 0
    assert "rehearsal" in "\n".join(output)
    assert "SOURCE_BOUND" in "\n".join(output)


@pytest.mark.parametrize(
    "confirmation", ["", "no", "y", ":back", "yes to all hardware"]
)
def test_preview_never_executes_without_exact_yes(confirmation: str) -> None:
    service = Service()
    code, output, _ = run(service, ["1", confirmation, "quit"])
    assert code == 0
    assert dispatched(service, "prepare") == [("prepare", "plan_task", {}, 7)]
    assert dispatched(service, "execute") == []
    assert "ticket-1" in "\n".join(output)


def test_exact_ticket_confirmation_executes_once_and_polls_read_only() -> None:
    service = Service()
    code, output, _ = run(service, ["plan_task", "yes", "quit"])
    assert code == 0
    assert dispatched(service, "execute") == [("execute", "ticket-1")]
    assert dispatched(service, "operation") == [("operation", "operation-1")]
    assert "SUCCEEDED" in "\n".join(output)
    assert service.shutdown_count == 0


def test_schema_fields_are_typed_and_passed_with_displayed_revision() -> None:
    fields = [
        {
            "name": "device",
            "label": "Device",
            "type": "select",
            "required": True,
            "options": [
                {"value": "keyboard", "label": "Keyboard"},
                {"value": "phone", "label": "Phone"},
            ],
        },
        {
            "name": "text",
            "label": "Text",
            "type": "textarea",
            "required": True,
            "max_length": 64,
        },
        {"name": "count", "label": "Count", "type": "number", "min": 1, "max": 10},
        {
            "name": "power_disconnected",
            "label": "Power disconnected",
            "type": "checkbox",
            "required": True,
        },
    ]
    service = Service([action(fields=fields)])
    code, _, _ = run(service, ["1", "2", "hi", "3", "yes", "yes", "quit"])
    assert code == 0
    assert dispatched(service, "prepare") == [
        (
            "prepare",
            "plan_task",
            {"device": "phone", "text": "hi", "count": 3, "power_disconnected": True},
            7,
        )
    ]


def test_back_from_field_cancels_before_preparation() -> None:
    service = Service(
        [
            action(
                fields=[
                    {"name": "text", "label": "Text", "type": "text", "required": True}
                ]
            )
        ]
    )
    run(service, ["1", ":back", "quit"])
    assert not dispatched(service, "prepare")


def test_select_without_default_does_not_choose_first_candidate_on_enter() -> None:
    service = Service(
        [
            action(
                fields=[
                    {
                        "name": "candidate_id",
                        "label": "Camera candidate",
                        "type": "select",
                        "required": True,
                        "options": [{"value": "camera-1", "label": "Camera 1"}],
                    }
                ]
            )
        ]
    )
    run(service, ["1", "", "quit"])
    assert not dispatched(service, "prepare")


@pytest.mark.parametrize("raw", ["", "no", "true", "1", "yes --allow-hardware"])
def test_required_checkbox_never_infers_blanket_hardware_confirmation(raw: str) -> None:
    service = Service(
        [
            action(
                fields=[
                    {
                        "name": "power_disconnected",
                        "label": "Power disconnected",
                        "type": "checkbox",
                        "required": True,
                        "default": True,
                    }
                ]
            )
        ]
    )
    run(service, ["1", raw, "quit"])
    assert not dispatched(service, "prepare")
    assert not dispatched(service, "execute")


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "1e999", "true", "-1", "11"])
def test_invalid_number_never_reaches_service(raw: str) -> None:
    service = Service(
        [
            action(
                fields=[
                    {
                        "name": "count",
                        "label": "Count",
                        "type": "number",
                        "min": 1,
                        "max": 10,
                    }
                ]
            )
        ]
    )
    run(service, ["1", raw, "quit"])
    assert not dispatched(service, "prepare")


@pytest.mark.parametrize(
    "field",
    [
        {"name": "text", "type": "text"},
        {"name": "text", "label": "Text", "type": "file"},
        {"name": "authority", "label": "Authority", "type": "checkbox"},
        {"name": "path", "label": "Path", "type": "text"},
        {"name": "raw_bytes", "label": "Bytes", "type": "text"},
        {"name": "text", "label": "Text", "type": "text", "unknown": True},
    ],
)
def test_unknown_and_raw_hardware_fields_fail_closed(field: dict[str, Any]) -> None:
    service = Service([action(fields=[field])])
    run(service, ["1", "quit"])
    assert not dispatched(service, "prepare")


def test_held_physical_action_cannot_be_selected_by_name_or_number() -> None:
    service = Service([action("camera_connect", enabled=False)])
    _, output, _ = run(service, ["camera_connect", "1", "quit"])
    assert not dispatched(service, "prepare")
    assert "Physical release is not qualified" in "\n".join(output)


@pytest.mark.parametrize(
    "menu", ["--allow-hardware", "COM3", "C:/arbitrary.exe", "all", "export C:/folder"]
)
def test_menu_never_becomes_a_shell_or_authority_surface(menu: str) -> None:
    service = Service()
    run(service, [menu, "quit"])
    assert not dispatched(service, "prepare")


def test_export_shortcut_uses_only_registered_export_action() -> None:
    service = Service([action("export_logs")])
    code, output, _ = run(service, ["export", "yes", "quit"])
    assert code == 0
    assert dispatched(service, "prepare") == [("prepare", "export_logs", {}, 7)]
    assert "assigned-exports" in "\n".join(output)


def test_stale_prepare_failure_is_not_retried() -> None:
    service = Service()
    service.prepare_error = ValueError("STALE_REVISION")
    _, output, _ = run(service, ["1", "quit"])
    assert len(dispatched(service, "prepare")) == 1
    assert not dispatched(service, "execute")
    assert "STALE_REVISION" in "\n".join(output)


def test_uncertain_execute_failure_never_resubmits_ticket() -> None:
    service = Service()
    service.execute_error = RuntimeError("Operation result not received")
    _, output, _ = run(service, ["1", "yes", "quit"])
    assert len(dispatched(service, "execute")) == 1
    assert "no retry was automatic" in "\n".join(output)


def test_long_operation_polling_is_bounded_and_back_does_not_dispatch() -> None:
    service = Service()
    service.operation_status = "RUNNING"
    sleeps: list[float] = []
    _, output, _ = run(service, ["1", "yes", "back", "quit"], sleep=sleeps.append)
    assert len(dispatched(service, "operation")) == POLL_WINDOW_STEPS
    assert len(sleeps) == POLL_WINDOW_STEPS
    assert sum(sleeps) == 15.0
    assert len(dispatched(service, "execute")) == 1
    assert "still running" in "\n".join(output)


def test_monitoring_interrupt_uses_explicit_registered_stop_preview() -> None:
    service = Service([action(), action("stop_operation")])
    service.operation_status = "RUNNING"

    def interrupt(delay: float) -> None:
        raise KeyboardInterrupt()

    _, output, _ = run(service, ["1", "yes", "stop", "yes", "quit"], sleep=interrupt)
    assert [call[1] for call in dispatched(service, "prepare")] == [
        "plan_task",
        "stop_operation",
    ]
    assert len(dispatched(service, "execute")) == 2
    assert "not a robot emergency stop" in "\n".join(output)


def test_stop_confirmation_can_be_declined_without_implicit_cancel() -> None:
    service = Service([action(), action("stop_operation")])
    service.operation_status = "RUNNING"
    _, output, _ = run(service, ["1", "yes", "stop", "", "quit"])
    assert len(dispatched(service, "prepare")) == 2
    assert len(dispatched(service, "execute")) == 1
    assert "does not prove power-off" in "\n".join(output)


def test_eof_and_menu_interrupt_exit_without_actions() -> None:
    for response in (EOFError(), KeyboardInterrupt()):
        service = Service()
        code, _, _ = run(service, [response])
        assert code == 0
        assert not dispatched(service, "prepare")
        assert service.shutdown_count == 0


def test_output_escapes_terminal_control_sequences() -> None:
    item = action()
    item["label"] = "label\x1b[2Jhidden"
    service = Service([item])
    _, output, _ = run(service, ["quit"])
    joined = "\n".join(output)
    assert "\x1b" not in joined
    assert "\\u001b" in joined


def test_unknown_operation_status_is_not_assumed_complete_or_retried() -> None:
    service = Service()
    service.operation_status = "UNKNOWN"
    _, output, _ = run(service, ["1", "yes", "quit"])
    assert len(dispatched(service, "execute")) == 1
    assert "Unknown operation state" in "\n".join(output)
