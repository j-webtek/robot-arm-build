"""Pure memory Win32 fixtures: this suite never loads a DLL or opens a port."""

from __future__ import annotations

import ast
import ctypes
from dataclasses import replace
import hashlib
import inspect
import json
from typing import Any

import pytest

from rocell.application.physical_connection_contracts import (
    EvidenceOrigin,
    RoArmUsbSerialIdentity,
    UsbDriverIdentity,
)
from rocell.providers.windows.arm_feedback_worker import ReviewedControllerBinding
from rocell.providers.windows import nonpurging_serial_api as api_module
from rocell.providers.windows.nonpurging_serial_api import (
    CommTimeouts,
    DcbSettings,
    FIXED_QUERY,
    IncapableWin32Scenario,
    IncapableWin32SerialApi,
    IoToken,
    NATIVE_HOLD,
    NativeSerialError,
    WindowsNativeSerialApi,
    validate_native_io_token,
)
from rocell.providers.windows.nonpurging_serial_backend import (
    NonPurgingSerialConnection,
)


def binding(*, physical: bool = False) -> ReviewedControllerBinding:
    identity = RoArmUsbSerialIdentity(
        "ffff",
        "0002",
        "SYNTHETIC-NOT-A-DEVICE",
        "USB\\VID_FFFF&PID_0002\\SYNTHETIC-NOT-A-DEVICE",
        "usb-unit:ffff:0002:SYNTHETIC-NOT-A-DEVICE",
        "COM404",
        UsbDriverIdentity("SYNTHETIC", "synthetic", "1.0", "synthetic.inf"),
    )
    return ReviewedControllerBinding(
        identity,
        "1" * 64,
        "2" * 64,
        "3" * 64,
        "4" * 64,
        "5" * 64,
        (
            EvidenceOrigin.PHYSICAL_OBSERVATION
            if physical
            else EvidenceOrigin.SYNTHETIC_REHEARSAL
        ),
    )


def connection(
    **values: Any,
) -> tuple[NonPurgingSerialConnection, IncapableWin32SerialApi]:
    fixture = IncapableWin32SerialApi(IncapableWin32Scenario(**values))
    return NonPurgingSerialConnection(binding(), api=fixture), fixture


def names(fixture: IncapableWin32SerialApi) -> list[str]:
    return [name for name, _ in fixture.trace]


@pytest.fixture(autouse=True)
def forbid_native_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("No test may load kernel32 or any other native DLL")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(ctypes, "CDLL", forbidden)


def test_construction_and_status_are_inert_and_closed() -> None:
    owner, fixture = connection()
    assert fixture.trace == ()
    report = owner.status()
    assert report["phase"] == "CLOSED_UNOPENED"
    assert not owner.is_open
    assert report["resource_counts"]["acquired"] == 0
    assert fixture.trace == ()
    native = WindowsNativeSerialApi()
    assert native.status()["native_api_loaded"] is False
    held = NonPurgingSerialConnection(binding(physical=True), api=native)
    assert held.status()["physical_hold"] == NATIVE_HOLD


def test_native_open_held_before_dll_loading_and_no_second_attempt() -> None:
    owner = NonPurgingSerialConnection(binding(physical=True))
    with pytest.raises(NativeSerialError, match=NATIVE_HOLD):
        owner.open()
    report = owner.status()
    assert report["api_calls"] == {"create_file": 1}
    assert report["resource_counts"]["acquired"] == 0
    assert report["cleanup_confirmed"]
    assert all(value == 0 for value in report["actual_effect_counts"].values())
    with pytest.raises(NativeSerialError, match="ONE_USE_CONNECTION"):
        owner.open()


def test_sealed_fixture_cannot_relabel_physical_or_inject_foreign_api() -> None:
    with pytest.raises(NativeSerialError, match="ORIGIN_MISMATCH"):
        NonPurgingSerialConnection(
            binding(physical=True), api=IncapableWin32SerialApi()
        )
    with pytest.raises(NativeSerialError, match="ORIGIN_MISMATCH"):
        NonPurgingSerialConnection(binding(), api=WindowsNativeSerialApi())
    with pytest.raises(NativeSerialError, match="REVIEWED_BINDING_REQUIRED"):
        NonPurgingSerialConnection("COM404")  # type: ignore[arg-type]

    class ForeignApi(IncapableWin32SerialApi):
        pass

    with pytest.raises(NativeSerialError, match="UNREGISTERED_NATIVE_API"):
        NonPurgingSerialConnection(binding(), api=ForeignApi())


def test_nominal_fixed_settings_exclusive_open_read_and_exact_cleanup() -> None:
    owner, fixture = connection(read_fragment_bytes=7)
    owner.open()
    assert owner.is_open
    create = fixture.trace[0]
    assert create == (
        "create_file",
        ("\\\\.\\COM404", 0xC0000000, 0, None, 3, 0x40000080, None),
    )
    assert owner.in_waiting == 0
    assert owner.write(FIXED_QUERY) == 10
    result = bytearray()
    while owner.in_waiting:
        result.extend(owner.read(min(7, owner.in_waiting), timeout_ms=50))
    assert bytes(result) == IncapableWin32Scenario().response_bytes
    owner.close()
    before = fixture.trace
    owner.close()
    report = owner.status()
    assert fixture.trace == before
    assert report["phase"] == "CLOSED"
    assert report["settings_readback_verified"]
    assert report["native_settings_requested"] == {
        "baud_rate": 115200,
        "flags": 1,
        "byte_size": 8,
        "parity": 0,
        "stop_bits": 0,
        "xon_limit": 128,
        "xoff_limit": 128,
        "xon_char": 17,
        "xoff_char": 19,
        "error_char": 0,
        "eof_char": 0,
        "event_char": 0,
    }
    assert report["native_timeouts_requested"] == {
        "read_interval_ms": 0,
        "read_multiplier_ms": 0,
        "read_constant_ms": 1000,
        "write_multiplier_ms": 0,
        "write_constant_ms": 1000,
    }
    assert report["resource_counts"] == {
        "acquired": 3,
        "close_attempted": 3,
        "close_confirmed": 3,
        "unresolved": 0,
    }
    assert report["confirmed_write_bytes"] == 10
    assert report["retained_read_bytes"] == len(result)
    assert report["read_bytes_sha256"] == hashlib.sha256(result).hexdigest()
    assert report["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    assert not report["physical_authority"] and not report["arm_connected"]
    assert fixture.open_handles == ()
    assert names(fixture).count("submit_write") == 1
    assert names(fixture)[-3:] == ["close_event:2", "close_event:1", "close_port"]


@pytest.mark.parametrize("field", ["startup_bytes", "prewrite_read_bytes"])
def test_prewrite_bytes_cannot_be_drained_to_manufacture_quietness(field: str) -> None:
    owner, fixture = connection(**{field: b"boot credentials should remain private\n"})
    owner.open()
    data = owner.read(100)
    assert data == b"boot credentials should remain private\n"
    assert owner.in_waiting == 0
    with pytest.raises(NativeSerialError, match="PREEXISTING_INPUT_OBSERVED"):
        owner.write(FIXED_QUERY)
    assert "submit_write" not in names(fixture)
    report = owner.status()
    assert report["startup_input_observed"]
    assert report["largest_prewrite_input_bytes"] == len(data)
    assert "credentials" not in json.dumps(report)
    owner.close()


def test_open_and_close_preserve_unread_startup_bytes_without_write() -> None:
    owner, fixture = connection(startup_bytes=b"old response\n")
    owner.open()
    assert fixture.remaining_input == b"old response\n"
    with pytest.raises(NativeSerialError, match="PREEXISTING_INPUT_OBSERVED"):
        owner.write(FIXED_QUERY)
    owner.close()
    assert fixture.remaining_input == b"old response\n"
    assert "submit_read" not in names(fixture)
    assert "submit_write" not in names(fixture)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"T":0}\n',
        b'{"T":105}',
        b'{"T":105}\r\n',
        '{"T":105}\n',
        bytearray(FIXED_QUERY),
    ],
)
def test_no_raw_commands_or_alternate_wire_forms(payload: Any) -> None:
    owner, fixture = connection()
    owner.open()
    with pytest.raises(NativeSerialError, match="FIXED_T105_ONLY"):
        owner.write(payload)
    assert "submit_write" not in names(fixture)
    owner.close()


def test_write_not_replayed_and_connection_not_reopened() -> None:
    owner, fixture = connection()
    owner.open()
    owner.write(FIXED_QUERY)
    with pytest.raises(NativeSerialError, match="ONE_WRITE_ONLY"):
        owner.write(FIXED_QUERY)
    with pytest.raises(NativeSerialError, match="ONE_USE_CONNECTION"):
        owner.open()
    owner.close()
    assert names(fixture).count("submit_write") == 1
    assert names(fixture).count("create_file") == 1


@pytest.mark.parametrize("count", [0, 1, 9])
def test_short_write_retains_count_no_remainder_and_closes(count: int) -> None:
    owner, fixture = connection(short_write=count)
    owner.open()
    with pytest.raises(NativeSerialError, match="SHORT_WRITE_NO_RETRY"):
        owner.write(FIXED_QUERY)
    with pytest.raises(NativeSerialError, match="CONNECTION_NOT_USABLE"):
        owner.write(FIXED_QUERY)
    owner.close()
    assert owner.status()["confirmed_write_bytes"] == count
    assert names(fixture).count("submit_write") == 1
    assert fixture.open_handles == ()


@pytest.mark.parametrize(
    "operation,acquired",
    [
        ("create_file", 0),
        ("create_event:1", 1),
        ("create_event:2", 2),
        ("get_state", 3),
        ("set_state", 3),
        ("get_timeouts", 3),
        ("set_timeouts", 3),
        ("queue_status", 1),
    ],
)
def test_open_failures_close_every_acquired_handle_once(
    operation: str, acquired: int
) -> None:
    owner, fixture = connection(fail_operations=(operation,))
    with pytest.raises(NativeSerialError, match="WIN32_CALL_FAILED"):
        owner.open()
    report = owner.status()
    assert report["resource_counts"]["acquired"] == acquired
    assert report["resource_counts"]["close_confirmed"] == acquired
    assert report["primary_error"]["code"] == "WIN32_CALL_FAILED"
    assert fixture.open_handles == ()
    assert "submit_write" not in names(fixture)
    trace = fixture.trace
    owner.close()
    assert fixture.trace == trace


@pytest.mark.parametrize(
    "scenario,code",
    [
        ({"state_mismatch": True}, "SETTINGS_READBACK_MISMATCH"),
        ({"timeout_mismatch": True}, "TIMEOUT_READBACK_MISMATCH"),
        ({"communication_error": 16}, "COMMUNICATION_ERROR_OBSERVED"),
    ],
)
def test_readback_drift_and_communication_errors_hold_without_recovery(
    scenario: dict[str, Any], code: str
) -> None:
    owner, fixture = connection(**scenario)
    with pytest.raises(NativeSerialError, match=code):
        owner.open()
    assert fixture.open_handles == ()
    assert "submit_write" not in names(fixture)
    assert owner.status()["primary_error"]["code"] == code
    if "communication_error" in scenario:
        assert owner.status()["communication_error_mask"] == 16


@pytest.mark.parametrize("operation", ["submit_read", "submit_write"])
def test_submission_failure_retains_primary_and_can_close(operation: str) -> None:
    owner, fixture = connection(fail_operations=(operation,))
    owner.open()
    with pytest.raises(NativeSerialError, match="WIN32_CALL_FAILED"):
        owner.read(1) if operation == "submit_read" else owner.write(FIXED_QUERY)
    owner.close()
    assert not owner.status()["pending_io_unresolved"]
    assert fixture.open_handles == ()


@pytest.mark.parametrize("kind", ["read", "write"])
def test_pending_completion_uses_bounded_wait_and_no_cancel_on_success(
    kind: str,
) -> None:
    owner, fixture = connection(pending_kind=kind)
    owner.open()
    if kind == "read":
        assert owner.read(1, timeout_ms=17) == b""
        assert ("complete_io", (101, 17)) in fixture.trace
    else:
        assert owner.write(FIXED_QUERY) == 10
        assert ("complete_io", (101, 1000)) in fixture.trace
    owner.close()
    assert "cancel_io" not in names(fixture)
    assert fixture.open_handles == ()


@pytest.mark.parametrize("kind", ["read", "write"])
def test_timeout_cancel_aborted_is_not_success_and_cleanup_is_confirmed(
    kind: str,
) -> None:
    owner, fixture = connection(pending_kind=kind, pending_outcome="timeout")
    owner.open()
    with pytest.raises(NativeSerialError, match="IO_DEADLINE_EXPIRED"):
        owner.read(1) if kind == "read" else owner.write(FIXED_QUERY)
    assert names(fixture).count("cancel_io") == 1
    assert names(fixture).count("complete_io") == 2
    assert ("complete_io", (101, 250)) in fixture.trace
    owner.close()
    report = owner.status()
    assert report["phase"] == "CLOSED_FAILED"
    assert report["primary_error"]["code"] == "IO_DEADLINE_EXPIRED"
    assert report["cleanup_confirmed"]
    assert report["confirmed_write_bytes"] == 0


@pytest.mark.parametrize("cancel_outcome", ["completed", "not_found_completed"])
def test_cancel_race_completed_write_is_counted_but_remains_failed(
    cancel_outcome: str,
) -> None:
    owner, fixture = connection(
        pending_kind="write", pending_outcome="timeout", cancel_outcome=cancel_outcome
    )
    owner.open()
    with pytest.raises(NativeSerialError, match="IO_DEADLINE_EXPIRED"):
        owner.write(FIXED_QUERY)
    owner.close()
    report = owner.status()
    assert report["confirmed_write_bytes"] == 10
    assert report["phase"] == "CLOSED_FAILED"
    assert names(fixture).count("submit_write") == 1
    assert names(fixture).count("cancel_io") == 1


def test_late_read_retains_private_bytes_and_latches_prewrite_input() -> None:
    secret = b"Authorization: Bearer do-not-display\n"
    owner, fixture = connection(
        prewrite_read_bytes=secret,
        pending_kind="read",
        pending_outcome="timeout",
        cancel_outcome="completed",
    )
    owner.open()
    with pytest.raises(NativeSerialError, match="IO_DEADLINE_EXPIRED"):
        owner.read(100)
    assert owner.late_read_bytes == secret
    report = owner.status()
    assert report["startup_input_observed"]
    assert report["late_read_bytes"] == len(secret)
    assert "do-not-display" not in json.dumps(report)
    assert fixture.remaining_input == b""
    owner.close()


@pytest.mark.parametrize("fault", ["stuck", "cancel_fail", "completion_fail"])
def test_unconfirmed_cancellation_retains_resources_and_never_retries_cleanup(
    fault: str,
) -> None:
    values: dict[str, Any] = {"pending_kind": "read", "pending_outcome": "timeout"}
    if fault == "stuck":
        values["cancel_outcome"] = "stuck"
    else:
        values["fail_operations"] = (
            ("cancel_io",) if fault == "cancel_fail" else ("complete_io",)
        )
    owner, fixture = connection(**values)
    owner.open()
    with pytest.raises(NativeSerialError):
        owner.read(1)
    with pytest.raises(NativeSerialError, match="CLEANUP_UNCONFIRMED"):
        owner.close()
    report = owner.status()
    assert report["pending_io_unresolved"]
    assert report["resource_counts"]["unresolved"] == 3
    assert report["resource_counts"]["close_attempted"] == 0
    assert report["cleanup_errors"]
    assert len(fixture.open_handles) == 3
    trace = fixture.trace
    with pytest.raises(NativeSerialError, match="CLEANUP_UNCONFIRMED"):
        owner.close()
    assert fixture.trace == trace
    assert names(fixture).count("cancel_io") == 1


def test_terminal_io_failure_can_close_without_cancel() -> None:
    owner, fixture = connection(pending_kind="read", pending_outcome="failed")
    owner.open()
    with pytest.raises(NativeSerialError, match="IO_COMPLETED_WITH_ERROR"):
        owner.read(1)
    owner.close()
    assert fixture.open_handles == ()
    assert "cancel_io" not in names(fixture)


@pytest.mark.parametrize("operation", ["close_port", "close_event:1", "close_event:2"])
def test_each_close_failure_retained_separately_from_primary(operation: str) -> None:
    owner, fixture = connection(short_write=1, fail_operations=(operation,))
    owner.open()
    with pytest.raises(NativeSerialError, match="SHORT_WRITE_NO_RETRY"):
        owner.write(FIXED_QUERY)
    with pytest.raises(NativeSerialError, match="CLEANUP_UNCONFIRMED"):
        owner.close()
    report = owner.status()
    assert report["primary_error"]["code"] == "SHORT_WRITE_NO_RETRY"
    assert report["cleanup_errors"][0]["code"] == "WIN32_CALL_FAILED"
    assert report["resource_counts"] == {
        "acquired": 3,
        "close_attempted": 3,
        "close_confirmed": 2,
        "unresolved": 1,
    }
    trace = fixture.trace
    with pytest.raises(NativeSerialError, match="CLEANUP_UNCONFIRMED"):
        owner.close()
    assert fixture.trace == trace


@pytest.mark.parametrize("fault", ["bool_count", "overcount", "nonbytes"])
def test_malformed_completion_is_never_treated_as_known_io(fault: str) -> None:
    owner, fixture = connection(invalid_completion=fault)
    owner.open()
    with pytest.raises(NativeSerialError):
        owner.read(1)
    report = owner.status()
    assert report["phase"] == "FAILED"
    assert report["retained_read_bytes"] == 0
    # The fixture's cancellation can establish an aborted completion, but it
    # cannot change the invalid initial receipt into a successful read.
    owner.close()
    assert fixture.open_handles == ()


@pytest.mark.parametrize(
    "size,timeout", [(True, 1), (0, 1), (1025, 1), (1, False), (1, 0), (1, 1001)]
)
def test_read_integer_and_timeout_bounds(size: Any, timeout: Any) -> None:
    owner, fixture = connection()
    owner.open()
    with pytest.raises(NativeSerialError, match="INVALID_ARGUMENT"):
        owner.read(size, timeout_ms=timeout)
    assert "submit_read" not in names(fixture)
    owner.close()


def test_read_call_budget_is_finite() -> None:
    owner, fixture = connection()
    owner.open()
    for _ in range(4096):
        assert owner.read(1) == b""
    with pytest.raises(NativeSerialError, match="READ_BUDGET_EXHAUSTED"):
        owner.read(1)
    owner.close()
    assert names(fixture).count("submit_read") == 4096


def test_nontext_and_extra_response_bytes_are_preserved_for_shared_wire_validator() -> (
    None
):
    data = b"\xff\x00garbage\nextra\n"
    owner, fixture = connection(response_bytes=data)
    owner.open()
    owner.write(FIXED_QUERY)
    assert owner.read(100) == data
    assert owner.status()["retained_read_bytes"] == len(data)
    owner.close()
    # This backend deliberately does not duplicate the T1051 wire parser.
    assert fixture.open_handles == ()


@pytest.mark.parametrize(
    "changes",
    [
        {"event": True},
        {"event": 0},
        {"size": True},
        {"size": 0},
        {"size": 65538},
        {"kind": "reset"},
        {"payload": bytearray(FIXED_QUERY)},
        {"size": 11},
        {"size": 9},
        {"payload": b'{"T":0}\n'},
        {"submitted": True},
        {"cancelled": True},
        {"storage": object()},
    ],
)
def test_pure_io_token_validation_prevents_native_copy_overread(
    changes: dict[str, Any],
) -> None:
    token = replace(IoToken(102, "write", len(FIXED_QUERY), FIXED_QUERY), **changes)
    with pytest.raises(NativeSerialError):
        validate_native_io_token(token)
    with pytest.raises(NativeSerialError):
        WindowsNativeSerialApi().submit_io(101, token)


def test_valid_token_still_cannot_bypass_native_hold() -> None:
    token = IoToken(102, "write", 10, FIXED_QUERY)
    validate_native_io_token(token)
    validate_native_io_token(IoToken(102, "read", 1))
    with pytest.raises(NativeSerialError, match=NATIVE_HOLD):
        WindowsNativeSerialApi().submit_io(101, token)
    assert token.storage is None and token.submitted is False
    with pytest.raises(NativeSerialError, match="UNREVIEWED_IO"):
        validate_native_io_token(IoToken(102, "read", 1, b"x"))


@pytest.mark.parametrize(
    "path",
    [
        "COM404",
        "\\\\.\\COM0",
        "\\\\.\\COM4097",
        "\\\\.\\com4",
        "C:\\data.txt",
        "\\\\server\\COM4",
        "\\\\.\\COM4\\extra",
    ],
)
def test_native_boundary_never_accepts_arbitrary_file_or_network_paths(
    path: str,
) -> None:
    with pytest.raises(NativeSerialError, match="EXACT_COM_PATH_REQUIRED"):
        WindowsNativeSerialApi().create_file(path)
    with pytest.raises(NativeSerialError, match="EXACT_COM_PATH_REQUIRED"):
        IncapableWin32SerialApi().create_file(path)


@pytest.mark.parametrize("port", [1, 404, 4096])
def test_exact_com_path_remains_physically_held(port: int) -> None:
    with pytest.raises(NativeSerialError, match=NATIVE_HOLD):
        WindowsNativeSerialApi().create_file("\\\\.\\COM" + str(port))


@pytest.mark.parametrize(
    "values",
    [
        {"startup_bytes": b"x" * 65538},
        {"startup_bytes": "text"},
        {"short_write": False},
        {"short_write": 10},
        {"pending_kind": "raw"},
        {"state_mismatch": 1},
        {"read_fragment_bytes": 0},
        {"fail_operations": ["create_file"]},
        {"fail_operations": ("PurgeComm",)},
    ],
)
def test_fixture_schema_is_closed(values: dict[str, Any]) -> None:
    with pytest.raises(NativeSerialError):
        IncapableWin32Scenario(**values)


def test_win32_structure_layout_is_reviewable_without_native_library() -> None:
    assert ctypes.sizeof(api_module._DCB) == 28
    assert ctypes.sizeof(api_module._TIMEOUTS) == 20
    assert ctypes.sizeof(api_module._COMSTAT) == 12
    assert ctypes.sizeof(api_module._OVERLAPPED) == (
        32 if ctypes.sizeof(ctypes.c_void_p) == 8 else 20
    )
    assert api_module._DCB.byte_size.offset == 18
    assert api_module._DCB.flags.offset == 8


def test_native_call_surface_has_no_buffer_clear_fallback_or_control_line_api() -> None:
    tree = ast.parse(inspect.getsource(api_module.WindowsNativeSerialApi))
    strings = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    forbidden = {
        "PurgeComm",
        "SetupComm",
        "FlushFileBuffers",
        "EscapeCommFunction",
        "SetCommBreak",
        "ClearCommBreak",
        "ResetEvent",
    }
    assert not strings.intersection(forbidden)
    assert not attributes.intersection(forbidden)
    owner, fixture = connection()
    owner.open()
    owner.close()
    assert not any(
        "purge" in name.lower() or "flush" in name.lower() or "reset" in name.lower()
        for name in names(fixture)
    )
